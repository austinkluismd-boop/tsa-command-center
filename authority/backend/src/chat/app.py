"""Atlas Assistant — Claude on Amazon Bedrock behind the workspace API.

The assistant can *draft* two kinds of change (site edits and CC_DATA
patches) via tools; every draft lands in the change-request queue as a
pending item and nothing executes until a human approves it in Site
Studio. The one-edit-pathway law is structural here: this function has no
write access to any console file, only to the queue.
"""
from __future__ import annotations

import json
import os
import re
import time
import uuid

import boto3
from anthropic import (
    AnthropicBedrockMantle,
    APIConnectionError,
    APIStatusError,
    RateLimitError,
)

MODEL_ID = os.environ["BEDROCK_MODEL_ID"]
TABLE = boto3.resource("dynamodb").Table(os.environ["TABLE_NAME"])

_client = None


def client() -> AnthropicBedrockMantle:
    global _client
    if _client is None:
        _client = AnthropicBedrockMantle(aws_region=os.environ["BEDROCK_REGION"])
    return _client


DOTTED_PATH = re.compile(r"^[A-Za-z0-9_]+(\.[A-Za-z0-9_]+)*$")

MAX_TURNS = 4            # bounded tool loop
MAX_MESSAGES = 20        # history window
MAX_CONTENT = 8_000      # chars per message
MAX_CONTEXT = 20_000     # chars of corpus digest

SYSTEM = """You are the Atlas Assistant inside the Atlas Authority Command Center — the
console Dr. Cuzalina's practice estate (Tulsa Surgical Arts, Oklahoma
Surgical Arts, Bella Roma Med Spa, TSA Wellness) uses to discuss and queue
website changes.

Estate laws you must never break:
1. Provenance law — a figure is called MEASURED only when the source of
   record (CC_DATA) says provenance "measurement". Never present a demo,
   modeled, or composite figure as a measurement.
2. One edit pathway — figures change only through reviewed data patches
   (set/append ops on dotted CC_DATA paths, applied by tools/ccdata.py).
   You never edit anything directly; you draft proposals that humans
   approve.
3. Freshness honesty — when some figures are re-measured and others are
   not, say so explicitly; never blend mixed vintages into one claim. A
   data patch's note must name what was and was NOT re-measured.

You receive a corpus digest for the tenant currently in scope. Answer from
it; if it does not contain what you need, say so rather than inventing.

When the user wants a change:
- Website copy/layout/imagery → use propose_site_edit with the target and a
  precise instruction a webmaster could execute.
- A figure or ledger value → use propose_data_patch with exact dotted paths
  and an honest note.
Confirm what you drafted and remind them it awaits approval in Site Studio.
Keep replies concise and concrete; this is a working console, not a demo.
"""

TOOLS = [
    {
        "name": "propose_site_edit",
        "description": (
            "Draft a website change request (copy, layout, imagery, navigation) "
            "for the tenant in scope. It is queued as PENDING for human approval "
            "and then ships via the estate's ship path. Use one call per distinct "
            "change."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "additionalProperties": False,
            "required": ["target", "instruction", "summary"],
            "properties": {
                "target": {
                    "type": "string",
                    "description": "Page or section, e.g. '/procedures/rhinoplasty — hero copy'",
                },
                "instruction": {
                    "type": "string",
                    "description": "Precise instruction a webmaster could execute without follow-up questions.",
                },
                "summary": {
                    "type": "string",
                    "description": "One-line summary for the review queue.",
                },
            },
        },
    },
    {
        "name": "propose_data_patch",
        "description": (
            "Draft a CC_DATA patch (the ONLY pathway a figure can change). "
            "Ops are set/append on dotted paths, exactly the tools/ccdata.py "
            "grammar. The note MUST name what was re-measured and what was not. "
            "On approval this becomes a pull request gated by the console-verify "
            "battery."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "additionalProperties": False,
            "required": ["ops", "note"],
            "properties": {
                "ops": {
                    "type": "array",
                    "minItems": 1,
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["op", "path", "value"],
                        "properties": {
                            "op": {"type": "string", "enum": ["set", "append"]},
                            "path": {"type": "string"},
                            "value": {},
                        },
                    },
                },
                "note": {
                    "type": "string",
                    "description": "Freshness-honesty note: what was and was NOT re-measured.",
                },
            },
        },
    },
]


def _resp(code: int, body: dict) -> dict:
    return {
        "statusCode": code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }


def _claims(event: dict) -> dict:
    return (((event.get("requestContext") or {}).get("authorizer") or {}).get("jwt") or {}).get(
        "claims"
    ) or {}


def _actor(claims: dict) -> str:
    return claims.get("email") or claims.get("cognito:username") or "unknown"


def _audit(actor: str, action: str, detail: dict) -> None:
    ttl = int(time.time()) + int(os.environ.get("AUDIT_TTL_DAYS", "365")) * 86_400
    TABLE.put_item(
        Item={
            "pk": "AUDIT",
            "sk": f"{int(time.time() * 1000)}#{uuid.uuid4().hex[:8]}",
            "actor": actor,
            "action": action,
            "detail": json.dumps(detail)[:4000],
            "ttl": ttl,
        }
    )


def _store_proposal(kind: str, entity: str, actor: str, payload: dict) -> dict:
    cr_id = uuid.uuid4().hex
    item = {
        "pk": "CR",
        "sk": cr_id,
        "id": cr_id,
        "type": kind,
        "entity": entity,
        "status": "pending",
        "created_by": actor,
        "created_at": int(time.time()),
        "source": "assistant",
    }
    item.update(payload)
    TABLE.put_item(Item=item)
    return item


def _validate_patch(ops: list) -> str | None:
    for i, op in enumerate(ops):
        if not DOTTED_PATH.match(op.get("path", "")):
            return f"op[{i}]: path {op.get('path')!r} is not a dotted CC_DATA path"
    return None


def _public_cr(item: dict) -> dict:
    keep = ("id", "type", "entity", "status", "target", "instruction", "summary", "ops", "note")
    return {k: item[k] for k in keep if k in item}


def handler(event, _ctx):
    claims = _claims(event)
    actor = _actor(claims)
    try:
        body = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError:
        return _resp(400, {"error": "invalid JSON body"})

    entity = str(body.get("entity") or "composite")[:32]
    raw_msgs = body.get("messages") or []
    if not isinstance(raw_msgs, list) or not raw_msgs:
        return _resp(400, {"error": "messages required"})

    messages = []
    for m in raw_msgs[-MAX_MESSAGES:]:
        role = m.get("role")
        if role not in ("user", "assistant"):
            continue
        content = str(m.get("content") or "")[:MAX_CONTENT]
        if content:
            messages.append({"role": role, "content": content})
    if not messages or messages[-1]["role"] != "user":
        return _resp(400, {"error": "last message must be from the user"})

    context = json.dumps(body.get("context") or {}, ensure_ascii=True)[:MAX_CONTEXT]
    system = SYSTEM + "\n\nCorpus digest for the tenant in scope:\n" + context

    proposals = []
    reply_parts = []
    try:
        for _ in range(MAX_TURNS):
            with client().messages.stream(
                model=MODEL_ID,
                max_tokens=4096,
                system=system,
                tools=TOOLS,
                messages=messages,
            ) as stream:
                response = stream.get_final_message()

            if response.stop_reason == "refusal":
                reply_parts.append(
                    "I can't help with that request. If it's an estate change you "
                    "need, rephrase it and I'll draft it through the review queue."
                )
                break

            tool_results = []
            for block in response.content:
                if block.type == "text" and block.text.strip():
                    reply_parts.append(block.text)
                elif block.type == "tool_use":
                    tool_input = block.input  # validated by strict tool use
                    if block.name == "propose_data_patch":
                        err = _validate_patch(tool_input["ops"])
                        if err:
                            result = {"ok": False, "error": err}
                        else:
                            item = _store_proposal(
                                "data_patch",
                                entity,
                                actor,
                                {"ops": tool_input["ops"], "note": tool_input["note"]},
                            )
                            proposals.append(_public_cr(item))
                            result = {
                                "ok": True,
                                "id": item["id"],
                                "status": "pending — awaiting human approval in Site Studio",
                            }
                    elif block.name == "propose_site_edit":
                        item = _store_proposal(
                            "site_edit",
                            entity,
                            actor,
                            {
                                "target": tool_input["target"],
                                "instruction": tool_input["instruction"],
                                "summary": tool_input["summary"],
                            },
                        )
                        proposals.append(_public_cr(item))
                        result = {
                            "ok": True,
                            "id": item["id"],
                            "status": "pending — awaiting human approval in Site Studio",
                        }
                    else:
                        result = {"ok": False, "error": f"unknown tool {block.name}"}
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": json.dumps(result),
                        }
                    )

            if response.stop_reason == "tool_use" and tool_results:
                messages.append({"role": "assistant", "content": response.content})
                messages.append({"role": "user", "content": tool_results})
                continue
            break
    except RateLimitError:
        return _resp(429, {"error": "The assistant is rate-limited right now — try again in a moment."})
    except APIStatusError as e:
        _audit(actor, "chat.error", {"status": e.status_code})
        return _resp(502, {"error": f"Assistant backend error ({e.status_code})."})
    except APIConnectionError:
        return _resp(502, {"error": "Could not reach the assistant backend."})

    reply = "\n\n".join(p.strip() for p in reply_parts if p.strip()) or "(no reply)"
    _audit(actor, "chat.message", {"entity": entity, "proposals": [p["id"] for p in proposals]})
    return _resp(200, {"reply": reply, "proposals": proposals, "model": MODEL_ID})
