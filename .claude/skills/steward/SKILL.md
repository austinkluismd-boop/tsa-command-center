---
name: steward
description: Repo conventions for sessions driving PRs on tsa-command-center
---

# Stewarding this repo

- Every push to `main` deploys to GitHub Pages. Do not merge a PR whose
  `console-verify` check is not green.
- Before pushing any change, run `python3 tools/ccdata.py check` locally —
  it is the same battery CI runs (byte-parity desktop==mobile, landing-chip
  parity, provenance/label law, zero-network law, version parity).
- Figures are never edited by hand; they go through
  `tools/ccdata.py patch` with a reviewed patch file under `tools/patches/`.
  If a PR hand-edits a number inside desktop.html, mobile.html, or
  group/index.html, that is the defect this repo's laws exist to prevent —
  flag it, do not merge it.
- desktop.html and mobile.html must remain byte-identical. A PR that
  changes one without the other is wrong by construction.
- This is a PUBLIC repo. No credentials, no internal hostnames, no
  patient-adjacent content, ever.
- Merge conventions: merge commits (no rebase/force-push on shared
  branches). Keep each PR to one concern.
