# URL / entity reconciliation — the pre-freeze battery

This directory is the working set for the estate's last structural move
before the architecture freeze: **legacy URL → new URL reconciliation,
canonicals/redirects/indexation, GBP/Bing/entity reconciliation, and the
external corroboration/citation queue**. Once every item here is applied
and verified, major architecture changes freeze and ATLAS measures the
resulting GSC / GBP / AI-SOV / consult trajectory against this baseline.

## What lives here

| file | role |
|---|---|
| `redirects.json` | **Source of record** for the legacy→new map (OPS-12's named deliverable). Per-URL evidence, proposed target, confidence, verification state. |
| `emit_artifacts.py` | Regenerates `apply/` from `redirects.json`. Never hand-edit `apply/`. |
| `apply/cloudflare_bulk_redirects.csv` | Paste into Cloudflare → Bulk Redirects (preferred path). |
| `apply/htaccess_okccosmeticsurgeon.txt` | Apache fallback if the legacy host stays on its current origin. |
| `apply/cloudfront_function.js` | CloudFront Function fallback for the practice-stack ship path. |
| `verify_redirects.py` | Live verification battery — run from an **open-egress** machine after applying. Fills `verify` blocks, checks canonicals/robots/sitemaps, emits a reviewed-patch stub for CC_DATA. |
| `entity.json` | The canonical entity record (TSA · OSA · Bella Roma) + per-surface reconciliation ledger (GBP, Bing, Apple, NPPES, directories). |
| `citations.md` | External corroboration / citation-building queue, ordered by measured AI-citation leverage. |

## The consolidation, in one paragraph

OSA's search equity is split: `okccosmeticsurgeon.com` (legacy, Tebra-
templated) holds ~5× the keywords; `oklahomasurgicalarts.com` holds the
brand. One 301 consolidation merges them — the Network Solutions
credential vaulted 2026-08-12 is the lever. On the TSA side the relaunch
left at least one indexed-but-404 tree (`/before-after-photos/*`) that
must 301 into `/gallery/{caseId}` per the gallery schema. Host-level
rules (http→https, apex↔www) and per-URL rules both live in
`redirects.json`; the catch-all guarantees no legacy URL escapes.

## Order of operations

1. **Apply** the map: move `okccosmeticsurgeon.com` DNS into the estate's
   Cloudflare account (registrar stays Network Solutions; only
   nameservers move) → import `apply/cloudflare_bulk_redirects.csv`.
   Alternative paths: the htaccess or CloudFront artifacts.
2. **Verify** from an open-egress machine:
   `python3 tools/reconcile/verify_redirects.py`
   — every rule must grade PASS (301, ≤2 hops, target 200, canonical
   self-referential, no noindex). Review the emitted patch stub, then
   apply it via `python3 tools/ccdata.py patch` so the consoles carry the
   verified state.
3. **Indexation**: complete GSC verification (OPS-18 — TXT is already
   serving), submit both hosts' sitemaps in GSC + Bing Webmaster Tools
   (OPS-3), then pull the GSC indexed-URL export and Wayback CDX for both
   hosts and diff against `redirects.json` — any indexed legacy URL not
   covered by a rule gets one (that diff closes OPS-12).
4. **Entity**: work `entity.json` surface by surface (GBP canonical NAP
   after the OPS-23 phone decision, Bing Places, Apple Business Connect,
   NPPES, directory corrections).
5. **Corroboration**: work `citations.md` top-down. No solicitation
   (AUTH-04); no citation, no claim.
6. **Freeze + measure**: architecture freeze; ATLAS baselines the
   GSC/GBP/AI-SOV/consult trajectory from the verified state.

## Provenance discipline

The 2026-08-25 inventories in `redirects.json` are **search-index
observations** (site:-scoped queries; each URL literally returned by the
index that day) — they are evidence of *indexation*, not a full crawl.
The cloud session that produced them could not reach the practice hosts
(egress policy), Wayback (blocked), or Semrush URL-level reports (API
units exhausted — see https://www.semrush.com/mcp-access); those gaps are
recorded per-item as `PENDING-LIVE-FETCH` / in `gated`, and the GSC +
CDX diff in step 3 is what closes them. Mixed vintages stay dated, per
the freshness law.
