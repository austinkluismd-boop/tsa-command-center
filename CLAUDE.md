# TSA Command Center — session laws

This repo publishes the practice's consoles on GitHub Pages. **Every push to
`main` deploys.** These laws exist because the group console once shipped a
demo composite wearing a MEASURED chip to an investor audience. They are
enforced by CI; this file tells you how to work inside them.

## The three laws

1. **Provenance/label law.** A figure may wear a `MEASURED` chip only if the
   source of record (`window.CC_DATA`, embedded in desktop.html/mobile.html)
   says `provenance: "measurement"`. A demo composite renders as `DEMO`,
   always, on every console. The check reads CC_DATA live — never hardcode
   around it.
2. **Zero-network law.** No console loads any external resource at view
   time — no CDN scripts, no font fetches, no remote images. Fonts are
   embedded as data URIs (reuse the faces already in desktop.html).
   Navigation `<a>` links are fine; `<link>`/`<script>`/`<img>` fetches are
   not.
3. **One edit pathway.** Never hand-edit figures — in the flagship consoles
   OR in `group/index.html`. Data changes go through:
   ```
   1. write a patch file under tools/patches/   (see the 2026-08-23 example:
      set/append ops on dotted paths + a note recording what was and was
      NOT re-measured)
   2. python3 tools/ccdata.py patch tools/patches/<file>.json
      (patches desktop AND mobile in one operation — they are byte-identical
      by construction and must stay that way)
   3. python3 tools/ccdata.py check     ← must print CCDATA CHECK: PASS
   ```
   Every patch is logged in `CC_DATA.meta.data_updates`.

## Freshness honesty

When you refresh some figures but not others (API units run out, a source is
gated), every figure carries its own vintage: date chips on tiles
(`08-23` vs `08-12`), capture notes naming exactly what was and was not
re-pulled. Mixed-vintage numbers inside one sentence are forbidden — split
the sentence or date both halves.

## Before any push

```
python3 tools/ccdata.py check          # the 9-check battery CI will run
```
For console changes, also load the page in a real browser (Playwright or
otherwise) and confirm: every tab/view renders, zero console errors, zero
network requests. The interaction batteries described in README.md are the
standard.

## Deploy gate

`.github/workflows/console-verify.yml` runs the battery on every push/PR.
Pages deploys from `main` on push regardless of check results — **branch
protection requiring `console-verify` is what makes a red check
undeployable**; keep it enabled. If it is not enabled, treat a red check as
a stop-ship and revert before anything else.

## Estate map (where the rest lives)

- `practice-stack` (private) — the platform suite: mission-control,
  measurement components, astro-site engine, AWS ship path. Its own
  CLAUDE.md carries the suite laws.
- `atlas-engine` (private) — the data engine + causal ledger. The consoles'
  measured figures should trace to observations in its DATA_LAKE; when you
  refresh data here, also run it through `atlas import` there so every
  surface carries the same measurement.
- The **live practice sites** are served from CloudFront via
  `practice-stack/ops/aws/ship_estate.sh` — never from this repo.
