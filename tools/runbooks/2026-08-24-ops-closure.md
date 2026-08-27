# Ops closure runbook — the 2026-08-24 batch of 10

Every item in this batch is a **human/vendor act no software can perform**:
a button only the owner can click, a decision only the owners can make, a
disk only the operator can reach. What a session CAN do is done: the console's
permission queue now carries all 33 items (registry sync patch
`2026-08-24-ops-registry-sync.json`), and every batch item has a staged
closure declaration under `tools/patches/staged/` ready to flip its status
the moment the act is real.

**What this session could NOT verify:** network egress is blocked in the
build environment, so no live re-probe ran. The freshest observations remain:
DNS TXT (`K_DY…` present, foreign `BFXT…` present) and the robots.txt
AI-block **re-confirmed 2026-08-07T22:38Z**; Semrush organic family pulled
2026-08-23. If any of those changed since, the steps below still verify them
first-hand as you go.

**Closing mechanics** (same for every item): do the act → fill `<DATE>` +
`<EVIDENCE>` in `tools/patches/staged/close-OPS-n.json` →
`python3 tools/ccdata.py patch <that file>` → `python3 tools/ccdata.py check`
→ commit. Or simply tell a console session "OPS-n done: <what you saw>" and
it runs the mechanics. CI refuses an unfilled placeholder, so a blind apply
cannot deploy.

---

## 1 · OPS-18 — Click Verify in Google Search Console (owner · 2 min)

**NO BACKFILL: every unclicked day is permanently lost search history.**
The required DNS TXT (`K_DY…`) was observed in DNS on 08-07 — the Verify
click is the only remaining half.

1. search.google.com/search-console → add/select the **Domain** property
   `tulsasurgicalarts.com` → **Verify** (DNS TXT method — the record is
   already live).
2. Settings → Users and permissions → add the service account as **Full**
   user (unlocks the 11 gated engine variables).
3. Enable the Generative-AI performance report.

Verify: property shows Verified; the SA appears in the user list.
Unblocks: OPS-24 (audit the foreign `BFXT…` TXT — who else holds a domain
claim; revoke or document), OPS-12 (indexed-URL export → redirects.json).

## 2 · OPS-1 — Cloudflare robots.txt: AI-block OFF + Sitemap line (owner · 2 min)

Oldest overdue P0; 9 AI crawlers still disallowed at last confirmation.

1. Cloudflare dash → zone `tulsasurgicalarts.com` → the **managed robots.txt
   AI-crawler block → OFF**.
2. Add `Sitemap: https://tulsasurgicalarts.com/sitemap.xml` to robots.txt.

Verify: fetch `https://tulsasurgicalarts.com/robots.txt` — zero AI-agent
Disallow blocks, Sitemap line present. (Side note from 08-07: origin was
unstable that night — 2/3 PSI runs timed out; if fetches hang, that is the
separate uptime-monitor escalation, not this toggle.)

## 3 · OPS-31 — Back up the causal ledger off the one Mac (operator · ~15 min)

The append-only intervention ledger (`ATLAS_VALIDATION_ARCHIVE`) exists on
one disk — the worst damage-to-effort ratio on the board. Box/Drive replica
IDs are already recorded in the atlas-engine config.

1. **Copy, never move** — replicate the archive to BOTH recorded replicas
   (Box + Drive).
2. Verify the replica: file count and spot checksums match the source.

Verify: both replicas list the same record count as the Mac copy.

## 4 · OPS-23 — NAP canonical-number decision (Austin + Dr. C · 1 decision)

Three numbers circulate (group-console dossier): `918-392-0880` (site —
likely the Yext tracked number), `(918) 392-7900` (GBP, WebMD/Vitals),
`(405) 698-3858` (Healthline syndication — wrong area code, kill on sight).

Decision frame: the canonical must be the **real practice line, never a
tracking number** — tracked numbers in citations are the classic
NAP-consistency defect. 60-second test: call both; the one the front desk
answers natively is canonical. If `392-0880` is confirmed Yext-tracked, the
canonical is `(918) 392-7900`.

Then: align site NAP to it, keep GBP as-is (or fix if the decision goes the
other way), exclude the canonical from the DNI pool, and deliberately kill
the Yext UTM/tracking remnants. **Record the chosen number in the closure
evidence** — it feeds the citation-auditor custody run and the DNI exclusion
list.

## 5 · OPS-32 — Clear the clinical-review corpus queue (clinician · review session)

The only gate between the measurement engine and the live site: TSA 10 +
OSA records (incl. the 2026-08-23 build-out) sit in
`DRAFT_PENDING_CLINICAL_REVIEW`. Dr. C reviews each record and ticks
ATTESTATION.md, then commits — engine-repo side; no console change until the
tick-and-commit lands.

## 6 · OPS-3 + OPS-26 + OPS-19 + OPS-27 — Bing + Apple surfaces (owner · ~30 min)

Bing feeds Copilot/ChatGPT local answers; Apple feeds Siri/Spotlight/Maps.

1. **Bing Webmaster Tools** (OPS-3, Bing half): after step 1 above, use
   "Import from Google Search Console" — it skips the DNS TXT dance. Submit
   sitemaps.
2. **Bing Places** (OPS-26): claim BOTH campuses (TSA + OSA). The IndexNow
   key file is committed engine-side; drop it at the live site root — the
   ping path is then one env var away.
3. **Apple Business Connect** (OPS-19): claim TSA + Bella Roma place cards;
   Maps-Ads posture decided after baseline.
4. **Apple Business Connect** (OPS-27): extend the claim to the OSA campus.

## 7 · OPS-33 — Live wellness page GLP-1 wording (owner · ~20 min)

Live regulatory exposure. The new engine gate guards engine **output** only —
the live page is hand-built, so the fix is by hand on the live tree, shipped
via `ops/aws/ship_estate.sh` (never from this repo).

## 8 · OPS-22 + OPS-28 — Semrush entitlement + live-feed secrets (owner · ~10 min)

1. semrush.com → Subscription info → **API units** (classic key →
   `SEMRUSH_API_KEY_CLASSIC`) and/or the API add-on so the v4 PAT activates;
   rotate the PAT after entitlement. Top up units at semrush.com/mcp-access.
2. atlas-authority-site → Settings → Secrets → add `SEMRUSH_API_KEY` +
   `CRUX_PSI_API_KEY`. The hourly Actions cron is already armed and degrades
   honestly without them — adding the secrets flips it from seed-replay to
   live pulls and un-stales the 08-08 authority-score/backlink figures.

## 9 · OPS-29 — Estate router publish + KVS cutover (owner · ~10 min, gated)

Gated on the practice-stack redirect PR merging. Then: `publish_router.sh`
(both) for the new families → KVS cutover per
`ops/aws/router-census/2026-08-23.md` §7 (create KeyValueStore, import
`tsa-legacy-map.json`, `KVS_CUTOVER=1` publish). Closes the ~50-path
remainder and removes the 10KB cap permanently.

## 10 · OPS-8 + OPS-9 + OPS-2 — Reputation & registry surfaces (~45 min)

1. **Healthgrades** (OPS-8, Austin): correct the "Lawrence Cuzalina, DDS"
   listing to the practice name — 170 reviews at 4.8★ are orphaned on the
   wrong name; the correction must retain the review history.
2. **RealSelf** (OPS-9, Dr. C): claim + verify the profile — 3.4★ unclaimed
   is the weakest surface.
3. **NPPES** (OPS-2, Dr. C): NPI `1376625830` via the I&A login — add
   other-name "Angelo Cuzalina" + MD taxonomy; record stale since 2007
   undermines registry corroboration. Verify next day via the public
   registry API.

---

Not in this batch but now visible in the queue: OPS-30 (Estate Concierge
port), OPS-24 (foreign TXT audit — do it right after step 1), and the rest
of the 33-row registry on the Ops tab.
