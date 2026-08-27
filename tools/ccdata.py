#!/usr/bin/env python3
"""ccdata.py — the ONE edit pathway for the Command Center's embedded data.

The consoles are self-contained HTML files whose source of record is the
window.CC_DATA object embedded on a single line of desktop.html/mobile.html.
Hand-editing that line (or hand-editing figures in group/index.html that
mirror it) is how the two consoles drifted apart once already — a demo
composite rendered as MEASURED on the investor console. This tool is the
guard against that class of defect:

  extract   — pull CC_DATA out of a console as pretty JSON (stdout or file)
  patch     — apply a reviewed patch file (set/append ops on dotted paths;
              a numeric segment indexes into a list, e.g. ops.17.status)
              to desktop.html AND mobile.html AND authority/index.html in
              one operation, so the consoles can never diverge
  check     — the consistency battery (run by CI on every push):
                1. desktop.html and mobile.html are byte-identical
                2. the landing page's Authority Index chip equals
                   CC_DATA.authority.index.score
                3. provenance/label law: the group console may label the
                   Authority Index MEASURED only if the source of record
                   says provenance == "measurement" — read live from
                   CC_DATA, never hardcoded
                4. zero-network law: no console loads any http(s) resource
                   (links for navigation are fine; <link>/<script>/<img>
                   fetches are not)
                5. closure honesty: no unfilled <EVIDENCE>/<DATE> closure
                   placeholders in CC_DATA — a staged closure-declaration
                   patch (tools/patches/staged/) applied without the
                   operator's evidence is a false "done"
                6. the group console's <title> version matches its sidebar
                7. the authority console's CC_DATA line is byte-identical
                   to the flagship's
                8. provenance law on the authority console: chips are only
                   assembled at render time from CC_DATA provenance — a
                   hardcoded MEASURED chip anywhere in the file fails
                9. the authority console's <title> version matches its rail

Patch file format (JSON):
  {"target": "cc_data",
   "ops": [
     {"op": "set",    "path": "semrush.organic.keywords", "value": 3500},
     {"op": "append", "path": "semrush.organic.series",  "value": {...}}
   ]}

Every patch leaves an entry in CC_DATA.meta.data_updates so the payload
carries its own edit history.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONSOLES = [ROOT / "desktop.html", ROOT / "mobile.html"]
GROUP = ROOT / "group" / "index.html"
LANDING = ROOT / "index.html"
# the Authority console carries the same CC_DATA line as the flagship and is
# patched in the same operation, so the three can never diverge
AUTHORITY = ROOT / "authority" / "index.html"

CC_RE = re.compile(r"^window\.CC_DATA = (.*);$", re.M)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def extract(path: Path) -> dict:
    m = CC_RE.search(_read(path))
    if not m:
        sys.exit(f"REFUSED: no `window.CC_DATA = ...;` line found in {path}")
    return json.loads(m.group(1))


def embed(path: Path, data: dict) -> None:
    html = _read(path)
    new_line = "window.CC_DATA = " + json.dumps(
        data, ensure_ascii=True, separators=(",", ":")) + ";"
    html, n = CC_RE.subn(new_line.replace("\\", "\\\\"), html, count=1)
    if n != 1:
        sys.exit(f"REFUSED: CC_DATA line not replaced exactly once in {path}")
    path.write_text(html, encoding="utf-8")


def _resolve(data: dict, dotted: str, create: bool = False):
    """Walk a dotted path. A numeric segment indexes into a list (e.g.
    ops.17.status is ops[17]["status"]) — indices must already exist; the
    pathway never grows a list except through op=append."""
    parts = dotted.split(".")
    node = data
    for p in parts[:-1]:
        if isinstance(node, list):
            if not p.isdigit() or int(p) >= len(node):
                sys.exit(f"REFUSED: path {dotted!r} — {p!r} is not an existing index of a {len(node)}-item list")
            node = node[int(p)]
        elif p not in node:
            if create:
                node[p] = {}
                node = node[p]
            else:
                sys.exit(f"REFUSED: path {dotted!r} — {p!r} absent (no silent creation without op=set-new)")
        else:
            node = node[p]
    return node, parts[-1]


def _leaf_set(node, leaf: str, value, dotted: str) -> None:
    if isinstance(node, list):
        if not leaf.isdigit() or int(leaf) >= len(node):
            sys.exit(f"REFUSED: path {dotted!r} — {leaf!r} is not an existing index of a {len(node)}-item list")
        node[int(leaf)] = value
    else:
        node[leaf] = value


def _leaf_get(node, leaf: str, dotted: str):
    if isinstance(node, list):
        if not leaf.isdigit() or int(leaf) >= len(node):
            sys.exit(f"REFUSED: path {dotted!r} — {leaf!r} is not an existing index of a {len(node)}-item list")
        return node[int(leaf)]
    return node.get(leaf)


def apply_patch(patch_path: Path, stamp: str | None) -> None:
    patch = json.loads(_read(patch_path))
    if patch.get("target") != "cc_data":
        sys.exit("REFUSED: patch target must be 'cc_data'")
    ops = patch.get("ops", [])
    if not ops:
        sys.exit("REFUSED: empty patch")
    base = extract(CONSOLES[0])
    for op in ops:
        node, leaf = _resolve(base, op["path"], create=(op["op"] == "set"))
        if op["op"] == "set":
            _leaf_set(node, leaf, op["value"], op["path"])
        elif op["op"] == "append":
            target = _leaf_get(node, leaf, op["path"])
            if not isinstance(target, list):
                sys.exit(f"REFUSED: append target {op['path']!r} is not a list")
            target.append(op["value"])
        else:
            sys.exit(f"REFUSED: unknown op {op['op']!r}")
    log = base.setdefault("meta", {}).setdefault("data_updates", [])
    log.append({
        "date": stamp or dt.date.today().isoformat(),
        "patch": patch_path.name,
        "note": patch.get("note", ""),
    })
    targets = CONSOLES + ([AUTHORITY] if AUTHORITY.exists() else [])
    for c in targets:
        embed(c, base)
    print(f"patched {len(ops)} op(s) into {' + '.join(str(c.relative_to(ROOT)) for c in targets)}")


# ---------------- consistency battery ----------------

def _fail(msgs: list, why: str) -> None:
    msgs.append("FAIL  " + why)


def _ok(msgs: list, what: str) -> None:
    msgs.append("ok    " + what)


def check() -> int:
    msgs: list = []

    # 1. desktop == mobile
    if _read(CONSOLES[0]) == _read(CONSOLES[1]):
        _ok(msgs, "desktop.html == mobile.html (byte-identical)")
    else:
        _fail(msgs, "desktop.html != mobile.html — the two consoles have diverged")

    data = extract(CONSOLES[0])
    idx = (data.get("authority") or {}).get("index") or {}
    score, prov = idx.get("score"), idx.get("provenance")
    pillars = [p for p in (idx.get("pillars") or []) if p.get("score") is not None]

    # 2. landing chip == source of record
    landing = _read(LANDING)
    m = re.search(r"Authority Index <b>([0-9.]+)</b>", landing)
    if not m:
        _fail(msgs, "landing page: Authority Index chip not found")
    elif float(m.group(1)) != float(score):
        _fail(msgs, f"landing chip says {m.group(1)} but CC_DATA says {score}")
    else:
        _ok(msgs, f"landing Authority chip {m.group(1)} == CC_DATA {score}")

    # 3. provenance/label law on the group console
    group = _read(GROUP)
    tile = re.search(r'AUTHORITY INDEX\s*<span class="tag (\w+)">([^<]*)</span>.{0,400}?class="foot">([^<]*)<', group, re.S)
    if not tile:
        _fail(msgs, "group console: AUTHORITY INDEX tile not found")
    else:
        cls, label, foot = tile.group(1), tile.group(2), tile.group(3)
        if prov != "measurement" and (cls == "meas" or "MEASURED" in label.upper()):
            _fail(msgs, f"group console labels Authority Index {label!r} but CC_DATA provenance is {prov!r} — a demo composite must never wear a MEASURED chip")
        else:
            _ok(msgs, f"group Authority tile label {label!r} consistent with provenance {prov!r}")
        pm = re.search(r"(\d+) pillars", foot)
        if pm and int(pm.group(1)) != len(pillars):
            _fail(msgs, f"group tile claims {pm.group(1)} pillars; CC_DATA carries {len(pillars)} scored pillars")
        elif pm:
            _ok(msgs, f"group tile pillar count {pm.group(1)} == CC_DATA {len(pillars)}")

    # 4. zero-network law
    load_re = re.compile(r'<(?:link|script|img)[^>]+(?:href|src)="(https?://[^"]+)"', re.I)
    for f in [*CONSOLES, GROUP, LANDING, AUTHORITY]:
        hits = [u for u in load_re.findall(_read(f))]
        if hits:
            _fail(msgs, f"{f.relative_to(ROOT)}: loads external resource(s) at view time: {hits[:3]}")
        else:
            _ok(msgs, f"{f.relative_to(ROOT)}: zero external resource loads")

    # 5. closure honesty: a staged closure-declaration patch applied with its
    #    placeholders intact is a false "done" — refuse it
    raw = json.dumps(data, ensure_ascii=True)
    hit = next((m for m in ("<EVIDENCE", "<DATE>") if m in raw), None)
    if hit:
        _fail(msgs, f"CC_DATA carries an unfilled closure placeholder {hit!r} — a staged closure patch was applied without the operator's evidence; revert or fill it in")
    else:
        _ok(msgs, "no unfilled closure placeholders in CC_DATA")

    # 6. group console version parity (title vs sidebar)
    tv = re.search(r"<title>[^<]*·\s*(v[\d.]+)</title>", group)
    sv = re.search(r"COMMAND CENTER\s*·\s*(v[\d.]+)", group)
    if tv and sv and tv.group(1) != sv.group(1):
        _fail(msgs, f"group console title says {tv.group(1)} but sidebar says {sv.group(1)}")
    elif tv and sv:
        _ok(msgs, f"group console version {tv.group(1)} consistent")
    else:
        _fail(msgs, "group console: version string not found in title and/or sidebar")

    # 7. authority console: CC_DATA line byte-identical to the flagship's
    authority = _read(AUTHORITY)
    fm = CC_RE.search(_read(CONSOLES[0]))
    am = CC_RE.search(authority)
    if not am:
        _fail(msgs, "authority console: no CC_DATA line — it must carry the source of record")
    elif am.group(0) != fm.group(0):
        _fail(msgs, "authority console: CC_DATA differs from the flagship — consoles have diverged; re-run ccdata.py patch")
    else:
        _ok(msgs, "authority CC_DATA line byte-identical to flagship")

    # 8. provenance/label law on the authority console: chips may only be
    #    assembled at render time from CC_DATA provenance (PROV_CLASS); a
    #    hardcoded MEASURED chip anywhere in the file is the forbidden defect
    if "PROVENANCE_CHIPS_FROM_CC_DATA" not in authority:
        _fail(msgs, "authority console: PROV_CLASS provenance-derivation marker missing")
    elif re.search(r"tag\s+t-meas", authority):
        _fail(msgs, "authority console: hardcoded MEASURED chip found — chips must derive from CC_DATA provenance")
    else:
        _ok(msgs, "authority chips derive from CC_DATA provenance (no hardcoded MEASURED chip)")
    if re.search(r'id="authority-index-tile"[^>]*></span>', authority):
        _ok(msgs, "authority index tile is an empty mount (filled from CC_DATA at render)")
    else:
        _fail(msgs, "authority console: index tile mount missing or pre-filled in static markup")

    # 9. authority console version parity (title vs rail)
    atv = re.search(r"<title>[^<]*·\s*(v[\d.]+)</title>", authority)
    asv = re.search(r"AUTHORITY CENTER\s*·\s*(v[\d.]+)", authority)
    if atv and asv and atv.group(1) != asv.group(1):
        _fail(msgs, f"authority console title says {atv.group(1)} but rail says {asv.group(1)}")
    elif atv and asv:
        _ok(msgs, f"authority console version {atv.group(1)} consistent")
    else:
        _fail(msgs, "authority console: version string not found in title and/or rail")

    print("\n".join(msgs))
    fails = sum(1 for m in msgs if m.startswith("FAIL"))
    print(f"\nCCDATA CHECK: {'PASS' if not fails else f'{fails} FAILURE(S)'}")
    return 1 if fails else 0


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    x = sub.add_parser("extract"); x.add_argument("--out", type=Path)
    p = sub.add_parser("patch"); p.add_argument("patch_file", type=Path); p.add_argument("--date")
    sub.add_parser("check")
    a = ap.parse_args()
    if a.cmd == "extract":
        out = json.dumps(extract(CONSOLES[0]), indent=1, ensure_ascii=True)
        if a.out:
            a.out.write_text(out, encoding="utf-8"); print(f"wrote {a.out}")
        else:
            print(out)
    elif a.cmd == "patch":
        apply_patch(a.patch_file, a.date)
    elif a.cmd == "check":
        sys.exit(check())


if __name__ == "__main__":
    main()
