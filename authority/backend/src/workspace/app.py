"""Atlas Authority workspace API — everything except chat.

Routes (all JWT-authorized except GET /health):
  GET    /health                              reachability probe for the console
  GET    /site/change-requests                review queue
  POST   /site/change-requests                create draft (site_edit | data_patch)
  POST   /site/change-requests/{id}/approve   owners only — executes via the pathway
  POST   /site/change-requests/{id}/reject    owners only
  GET    /media                               media vault listing (presigned GETs)
  POST   /media/uploads                       presigned PUT into the vault
  GET    /social/config                       per-platform configured/not — never a secret
  PUT    /social/oauth/{platform}             store OAuth app credentials (vault only)
  DELETE /social/oauth/{platform}             schedule credential deletion

Approving a data_patch commits the patch file to a fresh
authority/patch/* branch on GITHUB_REPO and opens a draft pull request;
GitHub Actions applies it with tools/ccdata.py and the console-verify
battery gates the merge. This function can never edit a console file
directly — the pathway is the API's only write path to a figure.
"""
from __future__ import annotations

import base64
import json
import os
import re
import time
import urllib.error
import urllib.request
import uuid

import boto3
from boto3.dynamodb.conditions import Key

TABLE = boto3.resource("dynamodb").Table(os.environ["TABLE_NAME"])
S3 = boto3.client("s3")
SECRETS = boto3.client("secretsmanager")

MEDIA_BUCKET = os.environ["MEDIA_BUCKET"]
GITHUB_REPO = os.environ["GITHUB_REPO"]
GITHUB_TOKEN_SECRET = os.environ["GITHUB_TOKEN_SECRET"]
SOCIAL_PREFIX = os.environ["SOCIAL_SECRET_PREFIX"]

DOTTED_PATH = re.compile(r"^[A-Za-z0-9_]+(\.[A-Za-z0-9_]+)*$")
PLATFORMS = ("meta", "google_business", "tiktok", "youtube", "x")
ENTITIES = ("composite", "tsa", "osa", "bellaroma", "wellness")
IMAGE_TYPES = ("image/jpeg", "image/png", "image/webp", "image/gif", "image/avif")
MAX_UPLOAD = 15 * 1024 * 1024


def _resp(code: int, body: dict) -> dict:
    return {"statusCode": code, "headers": {"Content-Type": "application/json"}, "body": json.dumps(body)}


def _claims(event: dict) -> dict:
    return (((event.get("requestContext") or {}).get("authorizer") or {}).get("jwt") or {}).get("claims") or {}


def _actor(claims: dict) -> str:
    return claims.get("email") or claims.get("cognito:username") or "unknown"


def _groups(claims: dict) -> list:
    g = claims.get("cognito:groups") or ""
    if isinstance(g, list):
        return g
    return [x for x in re.split(r"[\[\]\s,]+", str(g)) if x]


def _role(claims: dict) -> str:
    g = _groups(claims)
    if "owners" in g:
        return "owner"
    if "editors" in g:
        return "editor"
    return "viewer"


def _audit(actor: str, action: str, detail: dict) -> None:
    ttl = int(time.time()) + int(os.environ.get("AUDIT_TTL_DAYS", "365")) * 86_400
    TABLE.put_item(Item={
        "pk": "AUDIT",
        "sk": f"{int(time.time() * 1000)}#{uuid.uuid4().hex[:8]}",
        "actor": actor, "action": action,
        "detail": json.dumps(detail, default=str)[:4000], "ttl": ttl,
    })


# ── change requests ─────────────────────────────────────────────────────

def _public_cr(item: dict) -> dict:
    keep = ("id", "type", "entity", "status", "target", "instruction", "summary",
            "ops", "note", "created_by", "created_at", "pr_url", "slot", "key")
    return {k: item[k] for k in keep if k in item}


def list_crs() -> dict:
    items = TABLE.query(KeyConditionExpression=Key("pk").eq("CR"), Limit=200)["Items"]
    items.sort(key=lambda i: i.get("created_at", 0), reverse=True)
    return _resp(200, {"items": [_public_cr(i) for i in items]})


def create_cr(body: dict, actor: str) -> dict:
    kind = body.get("type")
    entity = body.get("entity") or "composite"
    if entity not in ENTITIES:
        return _resp(400, {"error": "unknown entity"})
    cr_id = uuid.uuid4().hex
    item = {"pk": "CR", "sk": cr_id, "id": cr_id, "type": kind, "entity": entity,
            "status": "pending", "created_by": actor, "created_at": int(time.time()),
            "source": "console"}
    if kind == "site_edit":
        target = str(body.get("target") or "").strip()[:300]
        instruction = str(body.get("instruction") or "").strip()[:4000]
        if not target or not instruction:
            return _resp(400, {"error": "target and instruction required"})
        item.update(target=target, instruction=instruction,
                    summary=str(body.get("summary") or target)[:200])
    elif kind == "data_patch":
        ops = body.get("ops")
        note = str(body.get("note") or "").strip()
        if not isinstance(ops, list) or not ops:
            return _resp(400, {"error": "ops must be a non-empty array"})
        if not note:
            return _resp(400, {"error": "the freshness-honesty note is required"})
        for i, op in enumerate(ops):
            if op.get("op") not in ("set", "append"):
                return _resp(400, {"error": f"op[{i}]: op must be set|append"})
            if not DOTTED_PATH.match(str(op.get("path") or "")):
                return _resp(400, {"error": f"op[{i}]: bad dotted path"})
            if "value" not in op:
                return _resp(400, {"error": f"op[{i}]: value required"})
        item.update(ops=ops, note=note[:2000])
    elif kind == "media_swap":
        item.update(target=str(body.get("slot") or "")[:300], key=str(body.get("key") or "")[:400],
                    summary="media swap: " + str(body.get("slot") or "")[:160])
    else:
        return _resp(400, {"error": "type must be site_edit | data_patch | media_swap"})
    TABLE.put_item(Item=item)
    _audit(actor, "cr.create", {"id": cr_id, "type": kind, "entity": entity})
    return _resp(200, _public_cr(item))


def _get_cr(cr_id: str) -> dict | None:
    return TABLE.get_item(Key={"pk": "CR", "sk": cr_id}).get("Item")


def approve_cr(cr_id: str, actor: str, role: str) -> dict:
    if role != "owner":
        return _resp(403, {"error": "owners approve; ask Dr. Cuzalina or Austin"})
    item = _get_cr(cr_id)
    if not item:
        return _resp(404, {"error": "not found"})
    if item["status"] != "pending":
        return _resp(409, {"error": f"already {item['status']}"})
    if item["type"] == "data_patch":
        try:
            pr_url = _open_patch_pr(item, actor)
        except Exception as e:  # surfaced to the console verbatim-ish, logged fully
            _audit(actor, "cr.approve.error", {"id": cr_id, "error": str(e)})
            return _resp(502, {"error": f"GitHub hand-off failed: {e}"})
        item.update(status="approved", pr_url=pr_url)
    else:
        # site edits / media swaps queue for the estate ship path
        item.update(status="approved")
    item.update(approved_by=actor, approved_at=int(time.time()))
    TABLE.put_item(Item=item)
    _audit(actor, "cr.approve", {"id": cr_id, "type": item["type"]})
    return _resp(200, _public_cr(item))


def reject_cr(cr_id: str, actor: str, role: str) -> dict:
    if role != "owner":
        return _resp(403, {"error": "owners only"})
    item = _get_cr(cr_id)
    if not item:
        return _resp(404, {"error": "not found"})
    item.update(status="rejected", rejected_by=actor, rejected_at=int(time.time()))
    TABLE.put_item(Item=item)
    _audit(actor, "cr.reject", {"id": cr_id})
    return _resp(200, _public_cr(item))


# ── GitHub hand-off (stdlib only) ───────────────────────────────────────

def _gh_token() -> str:
    sec = SECRETS.get_secret_value(SecretId=GITHUB_TOKEN_SECRET)
    val = sec.get("SecretString") or ""
    try:
        return json.loads(val).get("token") or val
    except json.JSONDecodeError:
        return val


def _gh(method: str, path: str, token: str, body: dict | None = None) -> dict:
    req = urllib.request.Request(
        "https://api.github.com" + path,
        data=json.dumps(body).encode() if body is not None else None,
        method=method,
        headers={
            "Authorization": "Bearer " + token,
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "atlas-authority-workspace",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        detail = e.read().decode()[:300]
        raise RuntimeError(f"GitHub {e.code} on {method} {path}: {detail}") from e


def _open_patch_pr(item: dict, actor: str) -> str:
    token = _gh_token()
    repo = GITHUB_REPO
    date = time.strftime("%Y-%m-%d")
    short = item["id"][:8]
    branch = f"authority/patch/{date}-{short}"
    fname = f"tools/patches/{date}-authority-{short}.json"
    patch = {
        "target": "cc_data",
        "note": item["note"] + f" [requested via Atlas Authority console by {actor}]",
        "ops": item["ops"],
    }
    main = _gh("GET", f"/repos/{repo}/git/ref/heads/main", token)
    base_sha = main["object"]["sha"]
    _gh("POST", f"/repos/{repo}/git/refs", token,
        {"ref": f"refs/heads/{branch}", "sha": base_sha})
    _gh("PUT", f"/repos/{repo}/contents/{fname}", token, {
        "message": f"authority: data patch {date}-{short} (queued from the command center)",
        "content": base64.b64encode(
            json.dumps(patch, indent=1, ensure_ascii=True).encode()
        ).decode(),
        "branch": branch,
    })
    pr = _gh("POST", f"/repos/{repo}/pulls", token, {
        "title": f"Authority data patch {date}-{short}",
        "head": branch,
        "base": "main",
        "draft": True,
        "body": (
            f"Data patch queued from the Atlas Authority console by **{actor}** "
            f"(entity scope: {item.get('entity')}).\n\n"
            f"**Note:** {item['note']}\n\n"
            f"The `apply-authority-patch` workflow applies this file via "
            f"`tools/ccdata.py patch` (desktop + mobile + authority in one "
            f"operation) and `console-verify` gates the merge. Review the ops, "
            f"wait for the battery, then mark ready & merge."
        ),
    })
    return pr.get("html_url") or ""


# ── media vault ─────────────────────────────────────────────────────────

def list_media() -> dict:
    items = TABLE.query(KeyConditionExpression=Key("pk").eq("MEDIA"), Limit=200)["Items"]
    items.sort(key=lambda i: i.get("created_at", 0), reverse=True)
    out = []
    for m in items:
        url = S3.generate_presigned_url(
            "get_object", Params={"Bucket": MEDIA_BUCKET, "Key": m["key"]}, ExpiresIn=900)
        out.append({"key": m["key"], "name": m.get("name"), "entity": m.get("entity"),
                    "slot": m.get("slot"), "size": int(m.get("size", 0)),
                    "contentType": m.get("contentType"), "uploaded_by": m.get("created_by"),
                    "url": url})
    return _resp(200, {"items": out})


def create_upload(body: dict, actor: str) -> dict:
    name = re.sub(r"[^A-Za-z0-9._-]", "_", str(body.get("name") or "asset"))[:120]
    ctype = str(body.get("contentType") or "")
    size = int(body.get("size") or 0)
    entity = body.get("entity") or "composite"
    slot = str(body.get("slot") or "")[:300]
    if ctype not in IMAGE_TYPES:
        return _resp(400, {"error": "images only (jpeg/png/webp/gif/avif)"})
    if not 0 < size <= MAX_UPLOAD:
        return _resp(400, {"error": "size must be 1B–15MB"})
    if entity not in ENTITIES:
        return _resp(400, {"error": "unknown entity"})
    key = f"media/{entity}/{uuid.uuid4().hex[:12]}-{name}"
    url = S3.generate_presigned_url(
        "put_object",
        Params={"Bucket": MEDIA_BUCKET, "Key": key, "ContentType": ctype},
        ExpiresIn=600,
    )
    TABLE.put_item(Item={
        "pk": "MEDIA", "sk": key, "key": key, "name": name, "entity": entity,
        "slot": slot, "size": size, "contentType": ctype,
        "created_by": actor, "created_at": int(time.time()),
    })
    if slot:
        create_cr({"type": "media_swap", "entity": entity, "slot": slot, "key": key}, actor)
    _audit(actor, "media.upload", {"key": key, "entity": entity, "slot": slot})
    return _resp(200, {"url": url, "key": key})


# ── social / OAuth credentials ──────────────────────────────────────────

def social_config() -> dict:
    platforms = {}
    for p in PLATFORMS:
        meta = TABLE.get_item(Key={"pk": "SOCIAL", "sk": p}).get("Item")
        configured = False
        try:
            SECRETS.describe_secret(SecretId=SOCIAL_PREFIX + p)
            configured = True
        except SECRETS.exceptions.ResourceNotFoundException:
            configured = False
        platforms[p] = {
            "configured": configured,
            "updated_at": (meta or {}).get("updated_at"),
            "updated_by": (meta or {}).get("updated_by"),
        }
    return _resp(200, {"platforms": platforms})


def social_put(platform: str, body: dict, actor: str, role: str) -> dict:
    if role not in ("owner", "editor"):
        return _resp(403, {"error": "editors or owners only"})
    if platform not in PLATFORMS:
        return _resp(400, {"error": "unknown platform"})
    client_id = str(body.get("client_id") or "").strip()
    client_secret = str(body.get("client_secret") or "").strip()
    if not client_id or not client_secret:
        return _resp(400, {"error": "client_id and client_secret required"})
    payload = json.dumps({"client_id": client_id, "client_secret": client_secret,
                          "redirect_uri": str(body.get("redirect_uri") or "")})
    sid = SOCIAL_PREFIX + platform
    try:
        SECRETS.put_secret_value(SecretId=sid, SecretString=payload)
    except SECRETS.exceptions.ResourceNotFoundException:
        SECRETS.create_secret(Name=sid, SecretString=payload,
                              Description=f"Atlas Authority OAuth app credentials — {platform}")
    stamp = time.strftime("%Y-%m-%d %H:%MZ", time.gmtime())
    TABLE.put_item(Item={"pk": "SOCIAL", "sk": platform,
                         "updated_at": stamp, "updated_by": actor})
    _audit(actor, "social.credentials", {"platform": platform})
    # the secret is never echoed back — write-only by design
    return _resp(200, {"platform": platform, "configured": True, "updated_at": stamp})


def social_delete(platform: str, actor: str, role: str) -> dict:
    if role != "owner":
        return _resp(403, {"error": "owners only"})
    if platform not in PLATFORMS:
        return _resp(400, {"error": "unknown platform"})
    try:
        SECRETS.delete_secret(SecretId=SOCIAL_PREFIX + platform, RecoveryWindowInDays=7)
    except SECRETS.exceptions.ResourceNotFoundException:
        pass
    TABLE.delete_item(Key={"pk": "SOCIAL", "sk": platform})
    _audit(actor, "social.credentials.delete", {"platform": platform})
    return _resp(200, {"platform": platform, "configured": False})


# ── router ──────────────────────────────────────────────────────────────

def handler(event, _ctx):
    path = (event.get("rawPath") or "").rstrip("/")
    method = ((event.get("requestContext") or {}).get("http") or {}).get("method", "GET")
    params = event.get("pathParameters") or {}
    claims = _claims(event)
    actor = _actor(claims)
    role = _role(claims)
    try:
        body = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError:
        return _resp(400, {"error": "invalid JSON body"})

    try:
        if path == "/health" and method == "GET":
            return _resp(200, {"ok": True, "service": "atlas-authority-workspace"})
        if path == "/site/change-requests" and method == "GET":
            return list_crs()
        if path == "/site/change-requests" and method == "POST":
            if role not in ("owner", "editor"):
                return _resp(403, {"error": "editors or owners only"})
            return create_cr(body, actor)
        if path.endswith("/approve") and method == "POST":
            return approve_cr(params.get("id", ""), actor, role)
        if path.endswith("/reject") and method == "POST":
            return reject_cr(params.get("id", ""), actor, role)
        if path == "/media" and method == "GET":
            return list_media()
        if path == "/media/uploads" and method == "POST":
            if role not in ("owner", "editor"):
                return _resp(403, {"error": "editors or owners only"})
            return create_upload(body, actor)
        if path == "/social/config" and method == "GET":
            return social_config()
        if path.startswith("/social/oauth/") and method == "PUT":
            return social_put(params.get("platform", ""), body, actor, role)
        if path.startswith("/social/oauth/") and method == "DELETE":
            return social_delete(params.get("platform", ""), actor, role)
        return _resp(404, {"error": "no such route"})
    except Exception as e:
        _audit(actor, "api.error", {"path": path, "error": str(e)})
        return _resp(500, {"error": "internal error — logged"})
