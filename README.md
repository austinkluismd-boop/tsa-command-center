# Tulsa Surgical Arts — Command Center · Live Demo
**Atlas Authority™ platform · Austin M. Kluis, MD**

Public, fully-functional demonstration of the practice analytics console.

- **Landing / device router:** [`index.html`](https://austinkluismd-boop.github.io/tsa-command-center/)
- **Desktop demo:** [`desktop.html`](https://austinkluismd-boop.github.io/tsa-command-center/desktop.html)
- **Mobile demo:** [`mobile.html`](https://austinkluismd-boop.github.io/tsa-command-center/mobile.html)
- **Atlas Authority console:** [`authority/`](https://austinkluismd-boop.github.io/tsa-command-center/authority/) —
  tenant-tabbed corpus (Composite · TSA · OSA · Bella Roma · TSA Wellness),
  Site Studio, Media, Socials & OAuth, and the Atlas Assistant. Public page
  is the read-only shell; editing, login, and Claude-on-Bedrock chat come
  from the operator-deployed private workspace (`authority/backend/`,
  runbook in `authority/README.md`).

Both demos are the identical self-contained engine (one ~2 MB HTML file — vendored charts, embedded fonts, offline US basemap, **zero network requests at view time**). Seventeen sections (composite Engines view + Estate/Surgical/Injectable/Wellness scoping): Authority Index · Action Items · Signature Four · Paid Media · Patient Journey · Content Studio · Search · Competitive Intel · AI Visibility · Local & Reputation · Geo Intelligence · Site Experience · Engagement · Social & Audience · Interaction Maps · Methodology.

Data honesty: figures carry provenance chips — live-verified inputs (Semrush · CrUX field · Google Business Profile baseline, re-verified 2026-08-08; Semrush organic family re-pulled 2026-08-23) render as measurements; everything else is a clearly labeled demonstration series. *A report never asserts what it did not measure.*

## Edit pathway (the only sanctioned one)

The consoles' source of record is the `window.CC_DATA` object embedded in
`desktop.html`/`mobile.html` (and carried byte-identically by
`authority/index.html`). **Never hand-edit figures** — in those files,
`group/index.html`, or `authority/index.html`. Instead:

1. Write a patch file under `tools/patches/` (see
   `2026-08-23-semrush-refresh.json` for the format — set/append ops on
   dotted paths, plus a note recording what was and was not re-measured;
   a numeric segment indexes into a list, e.g. `ops.17.status`).
2. Apply it: `python3 tools/ccdata.py patch tools/patches/<file>.json` —
   this patches desktop, mobile and the authority console in one operation
   (they can never diverge) and appends the patch to
   `CC_DATA.meta.data_updates`.
3. Verify: `python3 tools/ccdata.py check` — byte-parity, landing-chip
   parity, the provenance/label law (a demo composite must never wear a
   MEASURED chip), the zero-network law, closure honesty (no unfilled
   `<EVIDENCE>`/`<DATE>` placeholders), and version parity.

The Ops tab's permission queue closes through the same pathway: each item
in the 2026-08-24 closure batch has a pre-written declaration under
`tools/patches/staged/` (applied **only after** the operator performs the
act, with the evidence filled in — see the README there), and the ordered
click-by-click path is `tools/runbooks/2026-08-24-ops-closure.md`.
Statuses are operator declarations, never a session's assumption.

CI (`.github/workflows/console-verify.yml`) runs the same battery on every
push and PR. Enable branch protection on `main` requiring the
`console-verify` check to make a red battery an undeployable one — Pages
deploys from `main` on push, so the protection rule is the hard gate.

Interaction verification (2026-08-08): the 226-check battery plus an adversarial live sweep on desktop (1440×900) and mobile (390×844) — tab routing, deep links, CSV/JSON exports, print snapshot, tooltips (hover + tap), live table search, interactive budget allocator (12 engine-tagged campaigns), amplification queue, pricing-ladder simulator, engine scope switching, parity matrix, zero console errors.
