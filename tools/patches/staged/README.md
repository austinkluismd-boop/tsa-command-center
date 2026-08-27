# Staged closure declarations — NOT applied

Each `close-OPS-n.json` here is a **pre-written closure declaration** for one
row of the permission queue (`CC_DATA.ops`). None of them has been applied.
Statuses are operator declarations: a staged patch may be applied **only
after the human act it describes has actually been performed**.

To close an item:

1. Do the act. The patch's `note` field states exactly what "done" means.
2. Edit the patch: replace `<DATE>` with the day the act happened and the
   `<EVIDENCE - operator declaration required>` placeholder with what was
   actually observed (screens seen, confirmation states, the decision made).
3. `python3 tools/ccdata.py patch tools/patches/staged/close-OPS-n.json`
4. `python3 tools/ccdata.py check` → must print `CCDATA CHECK: PASS`
5. Commit desktop.html + mobile.html + authority/index.html + the
   filled-in patch together.

Guard rails: `ccdata.py check` (and therefore CI) **fails** any console whose
CC_DATA carries an unfilled `<EVIDENCE`/`<DATE>` placeholder, so a staged
patch applied blind cannot ship. The `ops.N.` indices in these files assume
the registry's standing order (`ops[n]` is `OPS-(n+1)`); if the registry is
ever reordered, regenerate or re-check the indices before applying.

The execution runbook for the 2026-08-24 closure batch lives at
`tools/runbooks/2026-08-24-ops-closure.md`.
