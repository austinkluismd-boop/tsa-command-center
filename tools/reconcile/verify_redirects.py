#!/usr/bin/env python3
"""verify_redirects.py — live verification battery for redirects.json.

Run this from a machine with open egress (the cloud sandbox that produced
redirects.json could not reach the practice hosts — its egress policy 403s
them, so every rule ships as verify.status == "PENDING-LIVE-FETCH").

What it does, per redirect rule and per host rule:
  1. requests every legacy variant (http/https x apex/www) with redirects
     followed (10-hop cap), recording the full chain of (url, status)
  2. grades the chain:
       PASS  - permanent redirect (301/308), lands on the expected target
               (or a URL on the target host for host-level rules), final 200,
               <= 2 hops
       WARN  - temporary redirect (302/307), > 2 hops, final URL on the
               right host but not the mapped path, or canonical mismatch
       FAIL  - no redirect, 4xx/5xx, or lands off the target host
  3. fetches the final page and extracts <link rel="canonical"> and
     <meta name="robots"> - a target that canonicals elsewhere or is
     noindexed fails the indexation half of the reconciliation
  4. checks robots.txt and sitemap.xml on each destination host
     (Sitemap: directive present, sitemap reachable, sitemap contains no
     legacy-host URLs)

Output: redirects.verified.json next to the input (the same document with
verify blocks filled in) plus a ready-to-review CC_DATA patch stub under
tools/patches/ recording the counts. Apply the patch with
`python3 tools/ccdata.py patch` only after reviewing it - the one edit
pathway still applies.

Stdlib only. Usage:
  python3 tools/reconcile/verify_redirects.py [--in tools/reconcile/redirects.json]
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
UA = "tsa-command-center-reconcile/1.0 (redirect verification; operator-run)"
MAX_HOPS = 10
TIMEOUT = 20

CANONICAL_RE = re.compile(
    r'<link[^>]+rel=["\']canonical["\'][^>]*href=["\']([^"\']+)["\']|'
    r'<link[^>]+href=["\']([^"\']+)["\'][^>]*rel=["\']canonical["\']', re.I)
ROBOTS_META_RE = re.compile(
    r'<meta[^>]+name=["\']robots["\'][^>]*content=["\']([^"\']+)["\']', re.I)


def _open(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    ctx = ssl.create_default_context()
    return urllib.request.urlopen(req, timeout=TIMEOUT, context=ctx)


def follow(url: str) -> dict:
    """Follow redirects manually so every hop is recorded."""
    chain = []
    current = url
    body = ""
    for _ in range(MAX_HOPS):
        req = urllib.request.Request(current, headers={"User-Agent": UA}, method="GET")

        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *a, **k):
                return None

        opener = urllib.request.build_opener(NoRedirect)
        try:
            resp = opener.open(req, timeout=TIMEOUT)
            status = resp.status
            chain.append({"url": current, "status": status})
            if status < 300:
                try:
                    body = resp.read(262144).decode("utf-8", "replace")
                except Exception:
                    body = ""
            break
        except urllib.error.HTTPError as e:
            status = e.code
            chain.append({"url": current, "status": status})
            if status in (301, 302, 303, 307, 308):
                loc = e.headers.get("Location", "")
                if not loc:
                    break
                current = urllib.parse.urljoin(current, loc)
                continue
            break
        except Exception as e:  # DNS failure, TLS, timeout
            chain.append({"url": current, "status": None, "error": str(e)[:200]})
            break
    else:
        chain.append({"url": current, "status": None, "error": "redirect loop (>10 hops)"})
    return {"chain": chain, "final_url": chain[-1]["url"], "final_status": chain[-1].get("status"), "body": body}


def canonical_of(body: str) -> str | None:
    m = CANONICAL_RE.search(body or "")
    if not m:
        return None
    return (m.group(1) or m.group(2) or "").strip() or None


def host_of(url: str) -> str:
    return re.sub(r"^https?://", "", url).split("/")[0].lower().removeprefix("www.")


def grade(rule_target: str, result: dict, host_level: bool) -> tuple[str, list[str]]:
    notes = []
    chain = result["chain"]
    if result["final_status"] is None:
        return "FAIL", [f"unreachable: {chain[-1].get('error', 'unknown')}"]
    if result["final_status"] >= 400:
        return "FAIL", [f"final status {result['final_status']}"]
    hops = [h for h in chain if h.get("status") in (301, 302, 303, 307, 308)]
    if not hops:
        return "FAIL", ["no redirect served - legacy URL still resolves 200 in place"]
    verdict = "PASS"
    if any(h["status"] in (302, 303, 307) for h in hops):
        verdict = "WARN"; notes.append("temporary redirect in chain - must be 301/308 to pass equity")
    if len(hops) > 2:
        verdict = "WARN"; notes.append(f"{len(hops)} hops - flatten to one")
    target_host = host_of(rule_target)
    if host_of(result["final_url"]) != target_host:
        return "FAIL", [f"lands on {host_of(result['final_url'])}, expected {target_host}"]
    if not host_level:
        want = rule_target.rstrip("/")
        got = result["final_url"].split("?")[0].rstrip("/")
        if got.lower() != want.lower():
            verdict = "WARN"; notes.append(f"lands on {got}, mapped target was {want}")
    canon = canonical_of(result["body"])
    if canon:
        if host_of(canon) != target_host:
            verdict = "WARN"; notes.append(f"target canonicals off-host: {canon}")
    else:
        notes.append("no canonical tag on target (add self-referential canonical)")
    rm = ROBOTS_META_RE.search(result["body"] or "")
    if rm and "noindex" in rm.group(1).lower():
        return "FAIL", [f"target is noindex ({rm.group(1)})"]
    return verdict, notes


def check_host_hygiene(host: str) -> dict:
    out = {"host": host}
    try:
        with _open(f"https://{host}/robots.txt") as r:
            robots = r.read(65536).decode("utf-8", "replace")
        out["robots_status"] = 200
        out["sitemap_directive"] = bool(re.search(r"(?mi)^\s*sitemap\s*:", robots))
        out["ai_agents_disallowed"] = sorted({
            ua for ua in ("GPTBot", "ClaudeBot", "Google-Extended", "CCBot", "Amazonbot",
                          "Applebot-Extended", "Bytespider", "meta-externalagent",
                          "CloudflareBrowserRenderingCrawler")
            if re.search(rf"(?mi)^\s*user-agent\s*:\s*{re.escape(ua)}\b", robots)})
    except Exception as e:
        out["robots_error"] = str(e)[:200]
    for sm in (f"https://{host}/sitemap.xml", f"https://{host}/sitemap_index.xml"):
        try:
            with _open(sm) as r:
                xml = r.read(1048576).decode("utf-8", "replace")
            out["sitemap"] = sm
            out["sitemap_status"] = 200
            out["sitemap_urls"] = len(re.findall(r"<loc>", xml))
            foreign = sorted({host_of(u) for u in re.findall(r"<loc>\s*([^<]+?)\s*</loc>", xml)
                              if host_of(u) != host.removeprefix("www.")})
            if foreign:
                out["sitemap_foreign_hosts"] = foreign
            break
        except Exception:
            continue
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--in", dest="inp", type=Path, default=HERE / "redirects.json")
    a = ap.parse_args()
    doc = json.loads(a.inp.read_text(encoding="utf-8"))
    today = dt.date.today().isoformat()

    counts = {"PASS": 0, "WARN": 0, "FAIL": 0}
    for section in ("host_rules", "rules"):
        for rule in doc.get(section, []):
            legacy = rule.get("legacy") or rule.get("legacy_url")
            target = rule.get("target") or rule.get("target_url")
            variants = rule.get("variants") or [legacy]
            worst, all_notes, chains = "PASS", [], []
            order = {"PASS": 0, "WARN": 1, "FAIL": 2}
            for v in variants:
                res = follow(v)
                verdict, notes = grade(target, res, section == "host_rules")
                chains.append({"variant": v, "verdict": verdict, "notes": notes,
                               "chain": res["chain"]})
                if order[verdict] > order[worst]:
                    worst = verdict
                all_notes += [f"{v}: {n}" for n in notes]
            rule["verify"] = {"status": worst, "date": today, "variants": chains}
            counts[worst] += 1
            print(f"{worst:4}  {legacy}  ->  {target}" + (f"  [{'; '.join(all_notes[:2])}]" if all_notes else ""))

    # tsa_rules are apply-if-dead: a legacy-tree page still serving 200 is
    # healthy as-is; only a dead one needs its repair 301 applied
    for rule in doc.get("tsa_rules", []):
        legacy, target = rule["legacy_url"], rule["target_url"]
        res = follow(legacy)
        if res["final_status"] == 200 and not any(
                h.get("status") in (301, 302, 303, 307, 308) for h in res["chain"]):
            verdict, notes = "PASS", ["alive - serves 200 in place, no repair needed"]
        elif res["final_status"] and res["final_status"] >= 400:
            verdict, notes = "FAIL", [f"dead ({res['final_status']}) - apply the repair 301 to {target}"]
        elif res["final_status"] is None:
            verdict, notes = "FAIL", [f"unreachable: {res['chain'][-1].get('error', 'unknown')}"]
        else:
            verdict, notes = grade(target, res, host_level=False)
            notes = ["redirect already in place; graded against the mapped target"] + notes
        rule["verify"] = {"status": verdict, "date": today, "notes": notes,
                          "chain": res["chain"]}
        counts[verdict] += 1
        print(f"{verdict:4}  {legacy}  [{notes[0]}]")

    doc["hygiene"] = [check_host_hygiene(h) for h in doc.get("destination_hosts", [])]
    doc["verified_at"] = today
    out = a.inp.with_suffix(".verified.json")
    out.write_text(json.dumps(doc, indent=1, ensure_ascii=True) + "\n", encoding="utf-8")
    print(f"\nwrote {out}  ({counts['PASS']} PASS / {counts['WARN']} WARN / {counts['FAIL']} FAIL)")

    patch = {
        "target": "cc_data",
        "note": (f"Live redirect verification {today} via tools/reconcile/verify_redirects.py "
                 f"(operator-run, open egress). {counts['PASS']} PASS / {counts['WARN']} WARN / "
                 f"{counts['FAIL']} FAIL. Review chains in redirects.verified.json before applying."),
        "ops": [
            {"op": "set", "path": "reconciliation.verify",
             "value": {"date": today, "pass": counts["PASS"], "warn": counts["WARN"],
                       "fail": counts["FAIL"], "tool": "tools/reconcile/verify_redirects.py"}},
        ],
    }
    pf = ROOT / "tools" / "patches" / f"{today}-redirect-verify.json"
    pf.write_text(json.dumps(patch, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    print(f"wrote patch stub {pf} - review, then: python3 tools/ccdata.py patch {pf.relative_to(ROOT)}")
    sys.exit(0 if counts["FAIL"] == 0 else 1)


if __name__ == "__main__":
    main()
