# External corroboration / citation queue — ordered by measured leverage

Ordering source: the AI-SOV baseline's citation leaderboard
(`CC_DATA.sov.citations`, 4-run baseline — healthgrades.com cited in 260
answers, yelp.com 245, webmd.com 241, vitals.com 235, realself.com 211;
own site 44) plus the 2026-08-04 reputation census. The queue exists to
raise **external corroboration of the same canonical entity record**
(`entity.json`) — the laws still bind: *no citation, no claim*;
solicitation stays banned (AUTH-04); nothing here touches a phone field
until the OPS-23 canonical-number decision lands.

## Tier 1 — corrections on surfaces AI engines already cite (do first)

1. **Healthgrades** (OPS-8) — #1 cited domain in the baseline (260
   answers) and our 4.8★/170 sits under the wrong name
   ("Dr. Lawrence Cuzalina, DDS"). Correcting one field re-points the
   single highest-leverage citation surface at the canonical entity.
2. **NPPES** (OPS-2) — stale 2007 record (wrong name, dental taxonomy)
   feeds every downstream medical directory; fix upstream before touching
   the directories it feeds.
3. **Yelp** (OPS-20) — #3 cited (245); three duplicate listings split the
   entity. Claim + dedupe to one listing per location. Yelp is licensed
   AI supply; solicitation stays OUT of ask-routing.
4. **WebMD** — #5 cited (241); 5.0★/65 wearing a "license expired"
   display flag against a valid OK license 20503. Verify board-record
   display.
5. **Vitals** — #6 cited (235); align name/NAP.
6. **RealSelf** (OPS-9) — #9 cited (211); 3.4★/16 unclaimed is the
   weakest surface on the board. Claim + complete; no solicitation.
7. **RateMDs** — 4.4★/70, #3 of 34 Tulsa; align name/NAP.
8. **SRC** (OPS-10) — merge the two duplicate master-surgeon listings;
   surgicalreview.org is a credential corroborator for the sameAs graph.

## Tier 2 — entity infrastructure (unlocks the knowledge panel)

9. **Wikidata** (OPS-16) — paste the prepared QuickStatements (person,
   then org); QIDs are the backbone the sameAs graph and knowledge panel
   hang from.
10. **JSON-LD @graph on both sites** — alternateName
    ("Lawrence Angelo Cuzalina") + 12-node sameAs; ships site-side via
    practice-stack; tracked here so the queue is complete.
11. **Bing Places + Bing Webmaster** (OPS-3/OPS-27) — Bing feeds Copilot
    and parts of the ChatGPT browsing stack; claiming it is citation
    building for AI answers, not legacy search hygiene.
12. **Apple Business Connect** (OPS-19) — TSA + Bella Roma place cards.

## Tier 3 — authority corroboration (the "1-of-16" story)

13. **Publisher-side fixes** (OPS-11) — the Elsevier/Amazon
    "Angela Cuzalina" misspelling breaks author-entity matching for 2012
    volume citations.
14. **Publication surfacing** — 27 enumerated publications + the AJCS
    2024 first-author BBL study (cited in the ABCS 2024 national safety
    statement) become sameAs/citation nodes once the entity graph exists.
15. **Fellowship numbers** (OPS-17) — inception year + cumulative fellows
    trained unlock the 1-of-16 claim with a number attached (no citation,
    no claim — this is the citation).
16. **OSA parity pass** — once the 301 consolidation is live and the OSA
    GBP is built out, repeat Tier 1 for the OKC market (Fogleman +
    practice listings); citations that today reference
    okccosmeticsurgeon.com are updated to the brand host as each surface
    is worked.

## 2026-08-25 sweep addendum (search-index observations)

The entity sweep behind `entity.json → sweep_2026_08_25` adds three items
to Tier 1 and sharpens two existing ones:

- **Yelp — OSA market**: there is NO Oklahoma Surgical Arts listing.
  Instead **"Parkway Medical" still occupies OSA's exact address** and a
  **"Cosmetic Surgery Center"** listing (405-265-9255, 9617 S
  Pennsylvania) carries the old brand at an old address. Converting/
  retiring these two IS the OSA Yelp citation build — do it with the
  Tulsa dedupe in item 3.
- **Facebook — legacy page**: `facebook.com/OklahomaCosmeticSurgery`
  ("Cosmetic Surgery Center") is live alongside the new OSA page — merge
  or retire so each market has one page.
- **Tebra category fix**: tebra.com lists OSA as "OBGYN" — correct it;
  Tebra powers the legacy site platform, so the record likely syndicates.
- Healthgrades (item 1) also needs the **(405) 698-3858 phone variant**
  removed and the **duplicate group listings (u39gbb9/x2dv64)** merged.
- Vitals (item 5) is filed under a `/dentists/` URL path — the specialty
  correction rides the NPPES fix (item 2).

## Sequencing rule

Tier 1 items are independent and can run in parallel — except any field
carrying a phone number, which waits on OPS-23. Tier 2 item 9 precedes
item 10 (the QIDs go into the graph). After Tiers 1-2 are worked and the
redirect map verifies clean, the architecture freezes and ATLAS baselines
the GSC / GBP / AI-SOV / consult trajectory.
