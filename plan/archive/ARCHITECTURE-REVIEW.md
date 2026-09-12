# Travel Inn Sales Assistant — Architecture Review

**Reviewing:** `ARCHITECTURE.md` (Version 1 MVP, dated 17 Aug 2026, 442 lines)
**Review date:** 3 Sep 2026
**For:** Shivam / Priyanshu (Ladder)
**Status of the document:** Design direction correct. **Not build-ready.** Eight items must be fixed on paper before any infrastructure is created.

---

## 1. Verdict

The central insight is right and well argued: this is a database application with a language interface, not a vector search engine. Lookup and filter first, vectors only as a fallback, typed tools instead of model-written SQL, no property list in the prompt. Every external fact the document relies on was checked against primary sources and holds (model IDs, prices, Neon extension status and regions, the Next.js CVE, iron-session rotation, R2, Vercel, Upstash).

The problems are internal to the document:

| Area | Problem |
|---|---|
| Schema | The ER diagram does not implement the rules the prose promises (tri-state facts, rates table, multi-document properties, group documents). |
| Routing | Two of the five corpus-wide acceptance questions route to the exact mechanism the document says cannot answer them. |
| Property resolution | Defends against a collision that does not happen and misses the alias failure that does. |
| Decisions | Neon Singapore is locked while India data residency is an unanswered blocking question with an immutable region. |
| Security | The auth instruction is written for Next.js 15 middleware; Next.js 16 no longer picks up `middleware.ts` by default. |
| Timeline | 9–12 days is roughly half of what the feature list needs for one developer. |
| Cost | The top of the monthly range (₹8,000) exceeds the ₹5,000 cap already quoted to the client. |
| Scope | A deliverable promised in the scoping document (logging of every question) is absent from the schema. |

All of it is fixable in about a day of editing. None of it should be discovered after a Neon project exists or after the first demo.

---

## 2. How this review was done

**Read in full:** `ARCHITECTURE.md`, `ANSWERS.md`, `OPEN-ITEMS.md`, `QUESTION-BANK-ANALYSIS.md`, `notes/image_fields.md`, all nine `research/*.md` dimension files, `research/_gaps.md`, the first 295 lines of `research/_challenges.md`, all six `verify_*.py` / `*_check.py` scripts, `audit.py`, `audit.json`.

**Data checks run** (scripts in the session scratchpad):
- Image dimensions, DPI, heights, duplicate hashes, PDF page counts and text volume, undated PDFs, tile counts — all from `audit.json`.
- The "2× then cap at 4096px" arithmetic for the tallest file.
- Property names inside the two group documents (Postcard PDF text layer; Oberoi PNG tiles viewed directly).
- pg_trgm-style trigram similarity for every name pair the document cites as a near-collision, plus the filename-versus-title mismatches.

**Three subagents:**
1. Web fact-check of 21 external claims against vendor documentation (Google, Anthropic, Neon, Vercel, Next.js, iron-session, Cloudflare, Upstash).
2. Cross-check of `ARCHITECTURE.md` against the remaining 700 lines of `research/_challenges.md` and the three client-context files (`docs/fathom-transcript-173787829.txt`, `docs/claude_chat.md`, `docs/Travel-Inn-Pilot-Scoping.docx`).
3. Adversarial principal-engineer review of schema, routing, resolution, locked decisions, cost, timeline, omissions and demo-day risk.
4. (Second round, same day) Web research on model choice per pipeline stage: current Gemini and Claude lineups, vision and PDF limits, OCR benchmarks, embeddings, judge-model guidance and lifecycle policies, checked against Anthropic's model catalogue. Results in section 17.

Findings below are only those confirmed by the files, the data, or a primary source. Where a claim comes from a subagent's web check and I could not independently reproduce it, the source is named.

---

## 3. Fact-check of external claims

| # | Claim in the document / research | Verdict | Correct current fact |
|---|---|---|---|
| 1 | `gemini-3.1-pro-preview`, $2 / $12 per 1M, re-rated $4 / $18 above 200k context, preview | TRUE | Confirmed on the Gemini pricing page. `_gaps.md` item M3 ("no 3.x Gemini exists") was wrong. |
| 2 | `gemini-3.7-flash` GA, $0.75 / $3.75 | TRUE | GA since 13 Aug 2026 at that price through Dec 2026 (rises in 2027). |
| 3 | `gemini-embedding-2` GA, $0.20 / 1M | TRUE | Default 3072 dims; Matryoshka truncation to 1536 and 768 explicitly supported, so `halfvec(1536)` is valid. `gemini-embedding-001` ($0.15) remains available and is sufficient for text-only. |
| 4 | Gemini Batch API 50% off | TRUE | Applies to embeddings too. |
| 5 | Gemini tiles images at 768×768, 258 tokens per tile | TRUE | Gemini 3.x adds `media_resolution` (low / medium / high / ultra_high) per media part. |
| 6 | Claude downscales images above 1568px on the long edge | OUTDATED | Claude models from 4.7 onward have a high-resolution tier: up to 2576px long edge, up to 4784 image tokens, automatic. Token count is patch-based (⌈w/28⌉ × ⌈h/28⌉). The research note that "Claude resizes to 2576px" was right for current models. |
| 7 | Citations API cannot cite images | TRUE | Text, PDF with extractable text, and custom_content only. Incompatible with `output_config.format`. |
| 8 | Anthropic Message Batches 50% off | TRUE | Also applies to cache read and write. |
| 9 | ParadeDB `pg_search` deprecated on Neon for new projects (2026-03-19) | TRUE | Removed from existing projects on 2026-09-21. Irrelevant to this design since `tsvector` is used. |
| 10 | Neon `lakebase_text` / `lakebase_bm25` works on standard `tsvector` | TRUE | Requires Postgres 16+. Recently out of preview; confirm availability on the actual plan before depending on it. |
| 11 | Neon has no India region; nearest is Singapore; region immutable | TRUE | AWS regions: us-east-1/2, us-west-2, eu-central-1, eu-west-2, ap-southeast-1 (Singapore), ap-southeast-2, sa-east-1. All Azure regions deprecated Apr 2026. |
| 12 | Neon supports pgvector 0.8 with `halfvec`, and `pg_trgm` | TRUE | pgvector 0.8.0, pg_trgm 1.6. |
| 13 | Neon auto-suspend default 5 minutes | TRUE | Wake is typically 300–500 ms; configurable or disable-able on paid plans. |
| 14 | CVE-2025-29927 fixed in Next.js 15.2.3 (also 14.2.25, 13.5.9, 12.3.5) | TRUE | Vercel-hosted deployments were protected at the edge regardless of version; only self-hosted apps needed the upgrade. |
| 15 | "Next.js ≥ 15.2.3" as the pin | OUTDATED | Next.js 16 is current stable (16.3.x). `middleware.ts` was renamed to `proxy.ts`; from 16.2 the framework no longer looks for `middleware.ts` by default, so an unmigrated gate builds fine and protects nothing. `proxy.ts` is Node runtime only. |
| 16 | Vercel AI SDK v6 (frontend research) / v7 (backend research) | OUTDATED (v6) | v7 is current. `useChat` still exists with streaming and typed data parts that can be streamed before text. |
| 17 | Vercel Pro ≈ $20 / month; Hobby not for commercial use | TRUE | Hobby is personal, non-commercial only. Pro is required. |
| 18 | Fluid Compute 300 s default, 800 s max on Pro | TRUE | A 1800 s beta exists. |
| 19 | iron-session supports multi-key rotation `{1: old, 2: new}` | TRUE | Highest key encrypts, all keys decrypt. |
| 20 | R2 free tier 10 GB, egress free | TRUE | 207 MB of source files stays free. |
| 21 | Upstash Redis free tier | TRUE | 500,000 commands per month (changed from a daily cap in Mar 2025). |

**Model pricing note.** `ANSWERS.md` costed Claude Sonnet 5 at $3 / $15. Anthropic's current model table lists `claude-sonnet-5` at $2 / $10; the cost research mentioned an introductory window ending 31 Aug 2026. Either way the document's inference estimate is conservative. Confirm the live price in the console before quoting.

---

## 4. Data checks against the corpus

| Check | Result | Consequence |
|---|---|---|
| File count and formats | 52 files: 36 PNG, 15 PDF, 1 JPEG | Matches the document. |
| Top-level folders | 16, including "General Property Updates" and Nepal | `ANSWERS.md` says 17 states; cosmetic. |
| Image widths | All 37 images are exactly 794 px wide, 96 DPI | Rule 1 (slice, never shrink) is correctly motivated. |
| Image heights | 2100 min, 3350 median, 5150 max; all 37 exceed 2048 px | The "2× then cap at 4096" recipe would have triggered on every file. |
| 2× then cap on 794×5150 | 631 px wide | The document's arithmetic is correct. |
| Tiles already cut | 128 tiles across 37 images, 794×~1100 | Matches Layer 1. |
| Exact duplicate | Ramathra Fort PDF, identical SHA1 in two folders | Rule 5 (hash dedupe) is correct. |
| PDF pages / text | 24 pages, 69,138 chars of native text | Dual-input strategy is correctly motivated. |
| Undated PDFs | 9 unique (10 entries including the Ramathra duplicate) | `ANSWERS.md` says 8. The document has no display rule for them. |
| Oberoi group PNG (Sep 2024) | Covers 8 hotels: Vindhyavilas, Rajgarh Palace, Maidens, Trident Jaipur, Grand, Clarkes, Cecil, Wildflower Hall | One document, many properties. |
| Postcard group PDF | Names about 12 Postcard properties (Chicalim, Chitwan, Gir, Jawai, Kanha, Leh, Mandalay Hall, Durrung Tea Estate, Himalayas, Arabian Sea, Mandovi River, Goa) | One document, many properties. Postcard Leh and Postcard Tezpur also have their own PNGs. |
| Oberoi Rajgarh PDF | Carries "NOVEMBER 2025", says "recently opened", spa "not yet operational" | Same property as the Sep 2024 group sheet. One property, two documents. |
| Property count | 49 single-property files, but roughly 65–70 named properties once group sheets are counted | "Checked all 49" is not a true statement about the corpus. |

**Trigram similarity** (pg_trgm rules: lowercase, per-word padding, 3-grams, Jaccard):

| Pair | Similarity |
|---|---|
| Bagh Tola vs Haldu Tola | 0.31 |
| Machaan vs Machaan Wilderness Lodge | 0.32 |
| Sadar Manzil vs Sadar Manzil Heritage by Atmosphere, Bhopal | 0.32 |
| Kaav vs Kaav Safari Lodge | **0.28** |
| Postcard Leh vs The Postcard in the Himalayan Willows | **0.24** |
| Kathoni vs Kaav Safari Lodge | 0.08 |
| Postcard Leh vs Dolkhar Ladakh | 0.04 |
| pg_trgm default `similarity()` threshold | 0.30 |

A full property name matches itself at 1.0 and its nearest neighbour at about 0.3, so the document's "near-collisions" do not collide. Short forms and the four filename-versus-title mismatches fall *below* the default threshold and fail to resolve. See Blocker 5.

---

## 5. Blockers — fix before anyone creates infrastructure

### Blocker 1 — Data residency is locked, not decided

**Where:** `ARCHITECTURE.md` L123 and L428 lock "Neon Postgres · Singapore". Part 8 (L415–421) lists only two client decisions.
**Evidence:** `OPEN-ITEMS.md` item 1 is marked BLOCKING and unanswered. The scoping document (`docs/Travel-Inn-Pilot-Scoping.docx`, section 4, question 19) asked Travel Inn where data may be processed and stored; none of the three client-context files records an answer. Neon has no India region and the region cannot be changed after project creation (verified).
**Why it matters:** an "India only" answer after build means a new project, full re-ingest and new connection strings. It also affects both model providers, since Anthropic and Google process requests outside India.
**Fix:** make residency decision 0 in Part 8. Keep the DDL provider-neutral (pgvector and pg_trgm run identically on RDS/Aurora Mumbai or Supabase Mumbai). Do not create the Neon project until the answer is in writing. Note the model-provider implication in the same paragraph.

### Blocker 2 — The schema cannot hold the corpus

**Where:** ER diagram L125–160, cardinality `documents ||--o{ properties` at L127. Contradiction rule at L270 ("show both with their dates").
**Evidence:** Oberoi Rajgarh Palace appears in two documents (Sep 2024 group PNG, Nov 2025 PDF). The Oberoi PNG covers eight hotels; the Postcard PDF covers about twelve. So a document has many properties *and* a property has many documents.
**Why it matters:** with a one-to-many link, one of Oberoi Rajgarh's two documents must lose, so the contradiction rule is unrepresentable. The group sheets either become nothing (then "what is the latest on Oberoi Grand" cannot be answered although the data exists) or become rows (then "Checked all 49" is false). Ingest currently has no step that splits one file into N properties. `_gaps.md` O4 (COUNT wrong on day one) survives the SHA dedupe because it is a different bug.
**Fix:** a `document_properties(document_sha, property_id)` join table; every fact, rate and point of interest carries its `document_sha`; a unique constraint on the normalised canonical name so a group sheet and an individual sheet cannot create two rows. Decide explicitly, in the document, whether group-sheet properties become rows. Recommended: yes, with a `card_type` of `group_update` and sparse facts, and "Checked all N" computed from the table, never hard-coded.

### Blocker 3 — The schema contradicts its own rules

**Where:** Layer 2 prose L164–186 vs ER L138–159; router example L206–210; Part 7 L408.
**Evidence, item by item:**
- Tri-state facts are promised (L168–186), then `staff_inspected` is typed `bool` (L146). `notes/image_fields.md` has "NOT personally inspected" (Agoratoli, Kaav), "personally visited" (Machaan) and nothing for Bagh Tola and Outpost 12. A bool turns absent into "not inspected", the exact failure L182 warns about.
- `has_pool`, the entire worked example, has no column. Tri-state can only live in `jsonb facts` (L145), which is unindexed and has no key vocabulary, so the promised "9 list / 6 say no / 34 not stated" line (L184–186) has nothing to compute from.
- L166 says "Airports and rates get their own tables." Only `property_airports` exists. `price_min_inr` and `meal_plan` are flat columns, so the router's own example `WHERE price_min_inr <= 25000` (L208) compares a room-only EPAI rate with an all-inclusive APAI rate. The corpus mixes MAP ₹9,250, APAI ₹19,200–47,000, EPAI ₹35,000, CPAI ₹41,500 (`QUESTION-BANK-ANALYSIS.md` Q15). This is a money problem, not a trust problem.
- The example sorts by `gate_km` (L207–208). No table has that column. Railheads and gates are also one-to-many (Courtyard Siliguri has two stations; Agoratoli has two gates) and have no tables.
- Ranking "closest to the airport" over a child table needs `ORDER BY MIN(km)`, not `ORDER BY column`. `_gaps.md` C4 is treated as cleared; the compiled SQL at L208 shows it is not.
- Part 7 says the cards are not chunked (L408) while the `chunks` table has a `section` column (L154–159).
**Fix:** one agreed DDL (section 9 below): `property_pois` with a `kind` column, `property_rates`, `property_facts` with `asserted_as`, `card_embeddings` with one row per card, `documents` with `doc_date` and provenance columns.

### Blocker 4 — Two acceptance questions route to the mechanism the document says cannot answer them

**Where:** Part 2 flowchart L36–46 and the sentence at L34 ("Vector search returns the top 5 of 49 and stops. It cannot know it missed 12."). Tools table L215–219.
**Evidence:** of the five corpus-wide [C] questions in `QUESTION-BANK-ANALYSIS.md`, Q9 (fewer than 20 rooms), Q10 (closest to airport) and Q11 (closest to gate) are SQL. Q21 ("Which properties are good for families?") and Q28 ("Which properties have the strongest conservation or community engagement programmes?") name no property and have no typed filter, so the router sends them to `search_semantic`, which is top-k. Q28 additionally asks for "strongest", a ranking no column encodes.
**Why it matters:** these are the client's own test questions. A five-item answer when the head of sales knows a sixth is the trust-ending event the document is built to prevent.
**Fix, two parts:** (a) extract `ideal_for` and a `tags` array (conservation, community, wellness, birding …) as typed columns so Q21 becomes a real filter with a "not stated" count; (b) add a corpus-wide qualitative path that returns *every* property's one-line digest (about 50–70 rows, roughly 5k tokens) and lets the model rank, instead of top-k. This is not the L225 trap: that objection is about a stale cached copy competing with the tool; this is a fresh read from the same database on every call.

Also in the routing layer:
- Q29 (compare A and B) needs `get_property` to accept a list of names; the flowchart shows one call. PNG and PDF templates have disjoint field sets, so the answer needs one "template gap" notice, not eight refusals.
- Q3 (three airports at Vayal Veedu) needs a stated return contract for `get_property`: property row, all points of interest, all rates, full transcription.
- Q15 (meals included) needs the MAP / APAI / EPAI / CPAI codes expanded; a four-row table in the system prompt.

### Blocker 5 — Property resolution defends the wrong failure

**Where:** Layer 4 L229–245; near-collision list at L241.
**Evidence:** the trigram table in section 4. "Bagh Tola" and "Haldu Tola" are not "one letter apart"; they share the word "Tola" and score 0.31. Kathoni / Kaav score 0.08. Postcard Leh / Dolkhar is a location coincidence, not a name one. "Machaan / Machaan Wilderness Lodge" is one property. Meanwhile `ANSWERS.md` L67–75 lists four files whose names differ from the document title, two of which are ground truth for acceptance questions (Postcard Leh for Q10, Courtyard Siliguri for Q4/Q5), and "Kaav" (Q17–19) scores below the default threshold. There is no alias table in the design, and `ANSWERS.md` L152 requires folder path as metadata ("hotels in Satpura"), which is also absent.
**Fix:** `aliases text[]` on `properties`, seeded from filename stem, folder path and document title; resolution order exact → prefix / `word_similarity()` → `similarity()` as tiebreaker only; the canonical list passed as an **enum in the tool schema** with `strict: true`, so the model cannot emit an unknown name and resolves aliases with its own language knowledge. Add `folder_path` to `properties`. Keep the "did you mean" prompt for genuine ties.

### Blocker 6 — The auth instruction is stale for current Next.js

**Where:** Layer 7 L319; Part 9 L433 ("Next.js ≥ 15.2.3").
**Evidence:** Next.js 16 is current. `middleware.ts` became `proxy.ts`, and from 16.2 the framework no longer picks up `middleware.ts` by default; the build succeeds and the gate silently does not run. `proxy.ts` is Node runtime only. Separately, Vercel's edge already blocked CVE-2025-29927 for Vercel-hosted apps, so the version pin buys less than the document implies.
**Fix:** rewrite the line as "Next.js 16.x, password gate in `proxy.ts` (Node runtime), verified by a deploy test that requests a protected route without a cookie and expects a redirect." Keep the CVE note as history, not as the control.

### Blocker 7 — The cost range breaks a number already quoted

**Where:** Part 5 L358–364 (₹4,000–8,000). `ANSWERS.md` L18 quoted "₹5,000/month, capped, separate line item".
**Evidence:** the ₹8,000 top assumes paid tiers for Neon and R2. R2 stays free at 207 MB. Neon's free tier covers this scale; the paid Launch plan is only needed if cold starts must be eliminated. Inference at 50 queries/day with two calls per query (router, then answer) is about ₹3,000 at list prices. Realistic total is about ₹5,000, or about ₹6,500 with Neon Launch.
**Fix:** present one realistic figure with the cap; set the Anthropic console monthly spend limit; add a daily spend counter that degrades to the Browse page rather than showing an API error. State in one sentence why hosting moved from Render Starter (₹620) to Vercel Pro (₹1,750); `ANSWERS.md` chose Render for single-region simplicity and no cold start, and the document never says why that changed.

### Blocker 8 — A promised deliverable is missing

**Where:** ER diagram L125–160; Layer 8 L326–347; Part 8 L420.
**Evidence:** the scoping document lists "logging of every question asked" in the first-build deliverables table. No log table exists. The same document promises "if material changes during the pilot and you send us the updated files, we will re-run the ingestion once at no additional cost", yet Part 8 presents re-ingestion as an unresolved question. Five separate challenge sections independently recommended a single log table as the highest-value v1 evaluation asset.
**Fix:** `queries(ts, question, tool, args, property_ids, answer, latency_ms, thumb)` plus a thumbs-down button. Half a day. State the one free re-ingestion as a built mechanism (the local script, run by Ladder, on request) and keep the "re-ingest button" as the handover item.

---

## 6. Major issues — fix in the document before sharing

| # | Issue | Evidence | Fix |
|---|---|---|---|
| M1 | **Group affiliation is missing.** | Ravi in the transcript (about 00:05) lists star rating, pool, room count and group as the quoting parameters. `ANSWERS.md` §7 says it is present but unstructured. Absent from the schema and from Part 8. | Add `group_affiliation` as an extracted typed column. |
| M2 | **No date derivation or supersession rule.** | Layer 6 promises "as of Jun 2025 on every claim" (L306). PNGs carry a printed header date (for example "SEP 2024"); nine PDFs carry no date; five 2024 "Hotel Update" sheets may be superseded by newer sheets for the same property. Nothing says which date is used or what an undated source shows. | Rule: printed sheet date → SharePoint modified date → NULL rendered as "undated source". `superseded_by` on documents; newest wins for routine answers, older shown only on an actual value conflict. |
| M3 | **The 2× upscale was dropped without a reason.** | Research called the 150 DPI cliff essential; Rule 1 slices at native 794 px width and never says why upscaling was abandoned. Claude 4.7+ accepts 2576 px on the long edge and Gemini has `media_resolution`, so a 2× strip (1588×2200) survives both models. | Test three files at native versus 2× strips before locking. Either answer is fine; an untested omission is not. |
| M4 | **Truncated streams read as complete.** | Four challenge sections flagged it. A list cut off by a timeout has no terminal marker, so it looks finished. | Specify the route duration, abort handling, and a "cut off, retry" state in the UI. |
| M5 | **Login rate limit keyed per IP.** | L320. Ten reps behind one office NAT share one bucket; five failed attempts lock everyone out. | Key per session cookie plus a higher global cap, or raise the per-IP threshold. |
| M6 | **Only citation existence is checked.** | L264. A correctly cited but wrong or rounded number passes. | Add a second regex: every number in the answer must appear verbatim in the supplied context. Ten lines. |
| M7 | **Spend cap absent.** | Part 5 gives estimates; Layer 7's only limiter is the login rate limit. | Console spend limit plus daily counter (see Blocker 7). |
| M8 | **Scoping question 20 unanswered.** | The scoping document asked whether anything in the pilot data should be hidden from sales. The shared password gives everyone identical access. | Get the answer; if yes, it changes the auth design. |
| M9 | **Neon cold start unaddressed.** | Default auto-suspend after 5 minutes; with 10 sporadic users most first queries of a session are cold. The research's 4-minute keep-alive cron was correctly rejected. | Set auto-suspend to 30–60 minutes on a paid plan, or accept the 300–500 ms wake behind the streaming label. Say which. |
| M10 | **Provider outage behaviour unspecified.** | L308 demands no dead spinner but nothing specifies retries, error strings, or a Browse-page fallback. | One retry, distinct error messages per failure type, Browse page always available. |
| M11 | **JPEG quality risk unmentioned.** | `ANSWERS.md` L45 names Vayal Veedu's JPEG as the only real quality risk; it is the sole ground truth for acceptance Q3. | Hand-verify that file's extraction first. |
| M12 | **Star ratings have no default.** | Part 8 leaves it to the client. If they never decide, Ravi's first question fails on demo day. | Ship the override table regardless, seeded with the prose positioning already in the sheets ("Luxury / Boutique Heritage Residence"). Two hours. |
| M13 | **`get_property` contract unstated.** | Q3, Q20, Q26, Q27 depend on child rows and the full transcription being returned. | Write the return shape into Part 9. |
| M14 | **"Fixed list of 49" vs re-ingest.** | L245 says identity resolves against a fixed list; L420 adds a re-ingest button. | The list is the `properties` table, regenerated on ingest. |

---

## 7. Minor issues and document hygiene

- L33: "Bagh Tola and Haldu Tola are one letter apart" is false. Replace with the real risk (aliases and short forms).
- L241: "Machaan / Machaan Wilderness Lodge" is one property; "Postcard Leh / Dolkhar" is a location coincidence. Remove or reword.
- L223: "roughly 60% of hallucinated answers … trace to invented column names" is an unsourced blog statistic. Remove or cite.
- L4: "Every decision below survived that challenge or was changed because of it" is overstated. The challenge log raised price comparability, query logging, stream truncation, spend caps and residency; the document addresses none. Soften the sentence or address them.
- L12: "52 design files" and L29 "49 rows" should say 52 files, 51 after dedupe, about 49 single-property sheets plus two group sheets.
- L193: "~2 MB" of vectors is correct only for section-level chunks; one embedding per card is about 150 KB. Consistent with Part 7 either way, but pick one.
- L114: Rule 4 (cross-model diff) and L340 (full human pass over every field) are both kept. That is fine, but say that the human pass is the ground truth and the diff only orders the human's attention; the over-engineering challenge argued to drop the diff and the document does not answer it.
- L268: the Citations API argument ("all our text is derived") is true for the 37 images and not for the 15 native-text PDFs. The decision to skip is still right; the reasoning should say so.
- L293: name the AI SDK major version (v7) so nobody scaffolds from v5/v6 examples.
- L319: `_gaps.md` M1 was adopted, but see Blocker 6 for the current framework behaviour.
- Layer 8: name who does the human review. If it is Gaurav or Nazim, the timeline depends on the client.
- `ANSWERS.md` says 8 undated PDFs; the text-layer check finds 9 unique. Reconcile.

---

## 8. Acceptance-test walk-through (30 questions)

Route each question through the three tools as the document specifies. "OK" means the design answers it completely if the fixes above are applied; "Risk" means the current document fails or under-answers it.

| # | Type | Question (short) | Route | Status | Note |
|---|---|---|---|---|---|
| 1 | P | Nearest airport and distance (Bagh Tola) | get_property | OK | Needs POI child rows in the return contract. |
| 2 | P | Road journey time from airport | get_property | OK | Same. |
| 3 | P | Multiple airport options compared (Vayal Veedu) | get_property | Risk | Needs child rows; source is the JPEG quality risk. |
| 4 | P | Nearest railway station (Courtyard Siliguri) | get_property | Risk | Alias: filename ≠ title (0.61 similarity, passes) but "Courtyard Siliguri" must map to the canonical row. Two stations → child rows. |
| 5 | P | Railway distance and transfer time | get_property | Risk | Same as 4. |
| 6 | P | Closest safari gate (Camp Tiger Lily) | get_property | OK | POI kind = gate. |
| 7 | P | Best time for wildlife (Machaan) | get_property | OK | Typed field. Short form "Machaan" resolves at 0.32; fine with prefix match. |
| 8 | P | Keys and room categories | get_property | OK | Inventory needs a per-category structure (jsonb or child table). |
| 9 | C | Fewer than 20 rooms | find_properties | OK | 20 expected rows; grade on completeness. |
| 10 | C | Closest to the airport | find_properties sort | Risk | Needs `ORDER BY MIN(km)` over POIs, kind = airport. Not expressible on the ER as drawn. |
| 11 | C | Closest to the safari gate | find_properties sort | Risk | Same, kind = gate; `gate_km` column does not exist. |
| 12 | P | Location and associated park (Agoratoli) | get_property | OK | Typed. |
| 13 | P | Nearest park and gate (Haldu Tola) | get_property | OK | Typed. |
| 14 | P | Large resort / boutique / camp | get_property | OK | Prose; needs transcription in return. |
| 15 | P | Meals included, meal plan options | get_property | Risk | Needs rates table and plan-code expansion. |
| 16 | P | Tell me about the property | get_property | OK | Transcription. |
| 17 | P | What makes it different (Kaav) | get_property | Risk | "Kaav" scores 0.28; fails without alias/prefix match. |
| 18 | P | Main selling points | get_property | OK | Transcription. |
| 19 | P | Top five selling points | get_property | OK | Transcription. |
| 20 | P | Good for wildlife enthusiasts / birders | get_property | OK | IDEAL FOR; better as tags. |
| 21 | C | Which properties are good for families | search_semantic | **Risk** | Qualitative corpus-wide; top-k. Needs tags filter or exhaustive digest path. |
| 22 | P | Activities apart from safari | get_property | OK | Transcription. |
| 23 | P | Walking safaris, boat safaris, cycling | get_property | OK | Transcription. |
| 24 | P | Cultural / community experiences | get_property | OK | Transcription. |
| 25 | P | Wildlife guests can expect | get_property | OK | Transcription. |
| 26 | P | Trained naturalists | get_property | OK | Transcription. |
| 27 | P | Conservation initiatives | get_property | OK | Transcription. |
| 28 | C | Strongest conservation programmes | search_semantic | **Risk** | Qualitative ranking corpus-wide; top-k. Needs exhaustive digest path. |
| 29 | P | Compare A and B on eight dimensions | get_property ×2 | Risk | Tool takes one name; templates have disjoint fields. |
| 30 | P | Who NOT to recommend it to | get_property | OK | TRAVEL INN RECOMMENDS section. |

Nine of thirty are at risk on the document as written. All nine are covered by Blockers 3, 4 and 5.

---

## 9. Recommended schema (provider-neutral)

This settles Blockers 2, 3 and 8 and `_gaps.md` C7. Adjust names freely; keep the shape.

```sql
create table documents (
  sha256            text primary key,
  r2_key            text not null,
  title             text,
  template          text,        -- 'png_2025' | 'png_2024' | 'pdf_numbered' | 'one_off' | 'group_update'
  doc_date          date,        -- printed sheet date; NULL = "undated source"
  superseded_by     text references documents(sha256),
  transcription     text not null,
  raw_fields        jsonb,
  extractor_model   text, prompt_version text, schema_version text,
  ingested_at       timestamptz default now()
);

create table properties (
  id                serial primary key,
  canonical_name    text unique not null,
  aliases           text[] not null default '{}',
  state             text, folder_path text, park text,
  group_affiliation text,
  room_count        int,
  best_time         text,
  ideal_for         text[],      -- 'families','birders','photographers',...
  tags              text[],      -- 'conservation','community','wellness',...
  digest            text,        -- one line, used by the exhaustive corpus-wide path
  card_type         text         -- 'property' | 'group_update'
);

create table document_properties (
  document_sha  text references documents(sha256),
  property_id   int  references properties(id),
  primary key (document_sha, property_id)
);

create table property_pois (             -- airports, railheads, gates: one-to-many
  property_id  int references properties(id),
  kind         text check (kind in ('airport','railhead','gate')),
  name         text, km numeric, minutes int,
  document_sha text references documents(sha256)
);

create table property_rates (
  property_id  int references properties(id),
  amount_inr   int, meal_plan text, basis text, category text, season text,
  document_sha text references documents(sha256)
);

create table property_facts (            -- tri-state, never a bare boolean
  property_id  int references properties(id),
  key          text,                     -- 'pool','spa','wifi','staff_inspected',...
  asserted_as  text check (asserted_as in ('stated','negated','absent','room_scoped','hedged')),
  value        text, evidence text, source_section text,
  document_sha text references documents(sha256),
  primary key (property_id, key, document_sha)
);

create table card_embeddings (           -- one row per card, not per section
  property_id  int references properties(id),
  document_sha text references documents(sha256),
  embedding    halfvec(1536)
);

create table manual_overrides (          -- star rating and anything the sheets lack
  property_id int, key text, value text, set_by text, set_at timestamptz default now()
);

create table queries (                   -- the promised log
  id bigserial primary key, ts timestamptz default now(),
  question text, tool text, args jsonb, property_ids int[],
  answer text, latency_ms int, thumb smallint
);

create index on properties using gin (to_tsvector('english', coalesce(digest,'')));
create index on properties using gin (canonical_name gin_trgm_ops);
create index on property_facts (key, asserted_as);
```

Ingest assertions before commit: `count(distinct canonical_name) = expected`, no two rows for one property, every property has at least one `document_properties` row.

---

## 10. Recommended tool contracts

```ts
get_property({ names: CanonicalName[] })
// names: enum of canonical names from the properties table, strict: true
// returns per property: row + pois[] + rates[] + facts[] + transcription + documents[] (with doc_date)

find_properties({
  state?, park?, room_count_lt?, room_count_gte?,
  fact?: { key, asserted_as: 'stated' | 'negated' },
  ideal_for?: string[], tags?: string[],
  price_max_inr?, meal_plan?,          // price filters require meal_plan or return the plan code per row
  sort_by?: 'airport_km' | 'gate_km' | 'railhead_km' | 'room_count' | 'price',
  limit?: number
})
// returns { matched_count, rows[], counts: { stated, negated, absent }, truncated: boolean }
// ranking uses ORDER BY MIN(km) over property_pois for the requested kind

list_digests({ question })
// returns every property's one-line digest; used for corpus-wide qualitative questions (Q21, Q28)

search_semantic({ query, property_id? })
// optional fallback, property-scoped when a property is named
```

Use `strict: true` on every tool so arguments validate exactly. Allow multi-step tool use (two calls for Q29). Keep the tool list order fixed so the cached prefix holds.

---

## 11. Timeline

The document's 9–12 working days (Part 6, L386–393) does not cover the feature list it describes. Estimate for one developer, no buffer:

| Work | Days |
|---|---|
| Extraction harness: tiling, PDF dual input, two outputs, two models, diff | 2 |
| Run extraction and triage disagreements | 1 |
| Human review of about 49 × 15 fields against the sheets | 1–1.5 (client-dependent if Gaurav or Nazim reviews) |
| DDL, aliases, group-document split, dates, supersession | 1.5 |
| Ingest script, R2 upload, PDF page renders, mobile image variants, embeddings | 2 |
| Tools, router, resolution, tri-state counts, MIN ranking, digests path | 2 |
| Generation prompt, citation and numeric regexes, contradiction and dating rules | 1 |
| Frontend: chat, two render paths, confirmation chip, source panel (PDF and image), Browse table, loading and error states | 3 |
| Auth in `proxy.ts`, rotation, rate limit, spend cap, query log and thumbs | 1 |
| Eval harness, 30 questions, iteration | 2.5 |
| Deploy, smoke test, override table, re-ingest path | 1 |
| **Total** | **≈ 18 (range 16–20)** |

The 4–6 week client commitment still holds, but it is no longer a buffer for the client's testing cycle; it is the build. The "show Nazim in two weeks" milestone from `ANSWERS.md` is reachable only as a narrowed demo: Ask page, Browse page and source panel on the fifteen Tier 1 questions.

---

## 12. Cost reconciliation

| Item | Document (Part 5) | Realistic at pilot scale |
|---|---|---|
| Vercel Pro | ₹1,750 | ₹1,750 (Hobby is non-commercial; Render Starter would be ₹620) |
| Neon | ₹0–1,500 | ₹0 on free tier; about ₹1,650 for Launch if cold starts must go |
| Cloudflare R2 | ₹0–650 | ₹0 (207 MB against a 10 GB free tier) |
| Claude inference at 50 queries/day | ₹2,500–4,000 | about ₹3,000 (two calls per query, conservative $3 / $15 pricing) |
| **Total** | **₹4,000–8,000** | **≈ ₹5,000, or ≈ ₹6,500 with Neon Launch** |

One-time extraction (₹230 for both models, ₹2 embeddings) is correct.

Quoted to the client: ₹5,000 per month, capped. Present that figure, enforce it in code, and set the console limit.

---

## 13. Demo-day failure scenarios

| Scenario | Cause | Prevention |
|---|---|---|
| Someone types "Postcard Leh" or "Kaav" and gets "I don't have a property by that name" while it is visible on the Browse page | No aliases; short forms below the trigram threshold | Blocker 5 |
| "Which properties are good for families?" returns five; the head of sales knows a sixth | Q21 routed to top-k | Blocker 4 |
| Ravi asks a star-rating question | No override table yet | M12 |
| "Compare X and Y" across a PNG and a PDF returns half the dimensions as refusals | Single-name tool, disjoint templates | Blocker 4 (Q29) |
| Oberoi Rajgarh answered confidently from one of its two sheets | One-to-many schema | Blocker 2 |
| A price filter ranks an APAI rate against an EPAI rate | No rates table | Blocker 3 |
| First question of the morning hangs, then a long list stops mid-way and looks complete | Cold start plus no truncation marker | M4, M9 |

---

## 14. What is right and should stay

- Lookup and filter before vectors; vectors only as a fallback (Part 2).
- Typed tools instead of model-written SQL; the property list kept out of the prompt (Layer 3).
- Tri-state facts as a concept and the three-count answer line (Layer 2).
- Child tables for one-to-many data (extend to railheads, gates and rates).
- Slice tall images, never shrink them; the 631 px arithmetic is correct (Layer 1).
- PDF image plus text in one call; one call returning transcription and fields; hash dedupe.
- Transcription as the durable asset with provenance columns.
- Self-describing source headers plus a regex check instead of the Citations API for a derived-text corpus.
- "Not in the data" as a plain statement; date on every claim; show both sides of a contradiction.
- Two render paths, the confirmation chip, the source panel that opens the real document, the Browse page, mobile-sized images.
- Shared password with rotation and a login rate limit.
- The real 30-question golden set instead of synthetic questions; retrieval and generation graded separately; completeness as the metric for set answers.
- The build order and the not-building list.
- `tsvector` now with `lakebase_bm25` as a one-index-definition upgrade later.

---

## 15. Action checklist

**Before any infrastructure exists**
1. Get residency (scoping Q19), v1 scope, the acceptance-test definition, and hidden-data (scoping Q20) answered in writing. Put all four in Part 8.
2. Replace the ER diagram with the schema in section 9. Decide group-sheet handling explicitly.
3. Replace the tools table with the contracts in section 10, including the exhaustive digest path and multi-name lookup.
4. Rewrite Layer 4 around aliases, prefix matching and the enum-constrained tool argument. Fix the near-collision examples.
5. Rewrite the Next.js line in Layer 7 around Next.js 16 and `proxy.ts`, with a deploy test.
6. Reconcile Part 5 with the ₹5,000 quote; add the spend cap and daily counter; explain Render → Vercel.
7. Add the queries table and thumbs-down; state the free mid-pilot re-ingestion as built.
8. Replace the timeline with 16–20 days and define the two-week demo scope.

**In the same edit**
9. Add group affiliation, date derivation, supersession, truncation handling, numeric regex, per-session rate limit, cold-start policy, outage behaviour, the JPEG check, the override-table default, the `get_property` return contract.
10. Remove the unsourced statistic and the incorrect name examples; soften the "every decision survived" sentence.

**First technical tasks once unblocked**
11. Extract three files at native and 2× strip resolution; compare against the sheets; lock the extraction resolution.
12. Hand-verify the Vayal Veedu JPEG and the Oberoi Rajgarh pair first.
13. Write the ingest assertions (distinct property count, no duplicate rows, every property linked to a document) before writing the ingest script.

---

## 16. Open questions for the client (consolidated)

| # | Question | Source | Blocks |
|---|---|---|---|
| 1 | Must data stay in India? | Scoping Q19, OPEN-ITEMS 1 | Database provider and region; model-provider posture |
| 2 | Is v1 the 52-file Property Updates set, or has scope grown to the 186-question bank? | OPEN-ITEMS 2 | Everything |
| 3 | Is the 30-question shortlist the acceptance test? | OPEN-ITEMS 3 | Definition of "pass" |
| 4 | Star ratings: override table maintained by the founder, or honest refusal? | Part 8 | Demo day |
| 5 | Should any pilot data be hidden from sales? | Scoping Q20 | Auth design |
| 6 | Who performs the human review of extracted fields, and by when? | Layer 8 | Timeline |
| 7 | Who are the testers and who signs off? | OPEN-ITEMS 7 | Pilot close |
| 8 | Shared password or Microsoft SSO for v1? | OPEN-ITEMS 9 | Auth design |
| 9 | Whose API accounts carry inference cost? | OPEN-ITEMS 5 | Billing |
| 10 | Group affiliation: is the prose in the sheets the source, or will the template add a field? | Transcript, ANSWERS §7 | Schema |

---

## 17. Model selection (researched 3 Sep 2026)

Researched against vendor documentation and public benchmarks, then checked against Anthropic's current model catalogue. Answering was already decided as Claude Sonnet 5; the research confirms that choice and settles the other stages.

### Model per purpose

| Purpose | Use | Fallback | Why |
|---|---|---|---|
| Extraction, primary pass (transcription + typed fields) | `claude-opus-5` | `claude-sonnet-5` | GA, 60-day retirement notice, high-resolution vision tier (2576 px long edge, 4784 image tokens), 1M context, strict tool schemas, 50% batch discount. Errors here are permanent and the whole job costs a few hundred rupees, so the strongest GA model is the right choice. |
| Extraction, cross-check pass | `gemini-3.1-pro-preview` with `media_resolution: high` | `gemini-3.8-flash` (GA) | A different model family is the point of the diff. Preview status is acceptable for the second opinion: a weaker replacement only produces more disagreements for the human to resolve, not worse final data. |
| Embeddings (semantic fallback only) | `gemini-embedding-2`, truncated to 1536 dims | `gemini-embedding-001` | Already in the stack, GA, Matryoshka truncation to 1536 confirmed. At 50–500 vectors the choice is immaterial; do not add a fourth vendor for it. |
| Answering and routing (one tool-use call) | `claude-sonnet-5` | `claude-opus-5`, only if the eval shows failures on compare or ranking questions | Price confirmed at $2 / $10 per 1M (the planned rise to $3 / $15 was cancelled), no retirement before mid-2027, native tool calling, 1M context. |
| Evaluation judge (automated regression runs) | `gemini-3.8-flash`, grading against the 30 human-verified answers | Human grading (cheaper at 30 questions) | The judge must come from a different family than the answerer; self-preference bias in LLM judges is confirmed in 2026 papers. Numeric fields are exact-match and need no judge. |
| Later field derivation from stored transcriptions (text only) | `claude-sonnet-5` via the Batches API | `gemini-3.8-flash` | Batch halves the price; reprocessing the whole corpus costs under ₹50. Fewer models to maintain. |
| Digests, alias seeds, "not stated" lists | No extra model | | Emitted by the primary extraction call. |

### What this changes in `ARCHITECTURE.md`

- **Part 9, models line (L435).** The extraction pair flips. The document has Gemini 3.1 Pro preview as primary and Sonnet 5 as the check. Google's preview lifecycle gives roughly two weeks' notice before removal, and Gemini 3 Pro preview was shut down four months after launch. The extraction script will be re-run during the pilot (the promised free re-ingestion) and at phase 2, so the primary transcription should come from a GA model with a 60-day floor. New line: `claude-sonnet-5` answers · `claude-opus-5` + `gemini-3.1-pro-preview` extract · `gemini-embedding-2` embeds · `gemini-3.8-flash` judges.
- **Layer 1, rule 2 (L112).** Both Claude and Gemini fuse the PDF text layer with a rendered page image automatically when the PDF bytes are sent. The hand-built dual input is unnecessary; the rule becomes "send the PDF". Page rendering code is still needed for the source panel.
- **Layer 8.** Add the judge model and the rule that the judge is never the answering model's family.

### Settings that matter

- Sonnet 5 runs adaptive thinking by default. Set `effort` explicitly: `medium` for answering; `low` is worth testing for the tool-selection turn. Sampling parameters (`temperature`, `top_p`, `top_k`) are rejected, so remove them from any copied code.
- The system prompt plus tool definitions must exceed 1,024 tokens to cache on Sonnet 5; the planned ~2k prompt qualifies. Keep tool order fixed and put anything volatile after the last cache breakpoint.
- For extraction on Claude, define one strict tool (`strict: true`) whose input schema is the record, rather than relying on structured-output mode with image input, which the docs do not explicitly confirm. Strict tools with images are documented.
- Do not split routing out to Haiku 4.5. Its cache minimum is 4,096 tokens so the prompt would not cache, the saving at 50 queries a day is a few rupees, and its earliest retirement date is October 2026 with no successor announced.
- Store the extractor model ID and prompt version per document (already in the proposed schema) so a re-run on a replacement model is auditable.
- Use the batch APIs for extraction (both vendors give 50% off) since there is no latency requirement.

### Cost with this plan

| Item | Estimate |
|---|---|
| One-time extraction, both passes, via batch APIs | ₹450–900 depending on native or 2× strips |
| Answering at 50 queries/day on Sonnet 5 at $2 / $10 with prompt caching | ₹1,700–2,300 per month |
| Field re-derivation over the whole corpus (text only, batch) | under ₹50 per run |

The document assumed $3 / $15 for Sonnet 5, so its inference line (₹2,500–4,000) is about 40% high. This helps the ₹5,000 cap.

### Evidence and caveats

- **Vision limits.** Claude models from the 4.7 generation onward (Sonnet 5, Opus 5) accept up to 2576 px on the long edge and up to 4784 image tokens, automatically. Tokens are patch-based: ⌈width/28⌉ × ⌈height/28⌉. A native 794×1100 strip costs about 1,160 tokens; a 2× strip (1588×2200) about 4,500, still under the cap. Gemini tiles at 768×768 and its `media_resolution` setting controls the token budget per image (high = 1,120, ultra_high = 2,240); Google says quality saturates at medium for standard documents, which these brochures are not.
- **PDF handling.** Both vendors extract the text layer and render each page as an image and pass both to the model. Claude: 32 MB and 600 pages per request. Gemini: text layer is not billed, page images are.
- **Lifecycle.** Anthropic gives at least 60 days' notice before retiring a public model; the deprecation page lists no retirement before mid-2027 for Sonnet 5 or Opus 5, while Haiku 4.5's earliest date is October 2026. Google's preview models can be removed on roughly two weeks' notice.
- **Benchmarks.** No public benchmark tests 8–12 px text over photographs in design brochures. OmniDocBench and OCRBench are built from office and scanned documents; aggregators disagree with each other by several points (for example GPT-5.2 at 88.0 on one and 85.4 on another); no Opus 5 or Sonnet 5 scores are published yet. The one task-relevant signal is that Gemini Flash models rank near the bottom on raw OCR relative to their other vision skills (Roboflow, 2026), which is why Flash is a fallback and not a primary.
- **Judges.** Self-preference bias in LLM judges is confirmed across multiple 2026 papers, and practitioner guidance is never to use the answering model's family as the judge.
- **Embeddings.** Anthropic still recommends Voyage (now MongoDB) as its embedding partner, but adding a fourth vendor for a rarely used 50–500-vector fallback contradicts the document's own "no third vendor" reasoning. Gemini embedding 2 is GA, multimodal, and supports 1536 dims.

### Bake-off before locking

The research narrows the candidates; it does not settle them. Half a day settles it: three files (include the Vayal Veedu JPEG and the tallest PNG, Red Panda Outpost at 794×5150), at native and 2× strips, on Opus 5, Sonnet 5, Gemini 3.1 Pro and Gemini 3.8 Flash, scored against hand-read values for the 15 Tier 1 fields. This also produces the first rows of the ground-truth CSV.

---

## Appendix — Primary sources used in the fact-check

- Gemini pricing, models, embeddings, batch, media resolution: https://ai.google.dev/gemini-api/docs/pricing · https://ai.google.dev/gemini-api/docs/models/gemini-embedding-2 · https://ai.google.dev/gemini-api/docs/embeddings · https://ai.google.dev/gemini-api/docs/batch-api · https://ai.google.dev/gemini-api/docs/media-resolution · https://ai.google.dev/gemini-api/docs/tokens
- Claude vision, citations, batches: https://platform.claude.com/docs/en/build-with-claude/vision · https://platform.claude.com/docs/en/build-with-claude/citations · https://www.anthropic.com/news/message-batches-api
- Neon: https://neon.com/docs/extensions/pg_search · https://neon.com/docs/ai/lakebase-search · https://neon.com/docs/introduction/regions · https://neon.com/docs/extensions/pgvector · https://neon.com/docs/introduction/scale-to-zero
- Next.js and Vercel: https://vercel.com/blog/postmortem-on-next-js-middleware-bypass · https://nextjs.org/docs/app/guides/upgrading/version-16 · https://vercel.com/blog/ai-sdk-7 · https://vercel.com/pricing · https://vercel.com/docs/fluid-compute
- iron-session: https://github.com/vvo/iron-session
- Cloudflare R2: https://developers.cloudflare.com/r2/pricing/
- Upstash: https://upstash.com/pricing

**Model selection sources (section 17)**
- Gemini: https://ai.google.dev/gemini-api/docs/pricing · https://ai.google.dev/gemini-api/docs/models · https://ai.google.dev/gemini-api/docs/deprecations · https://ai.google.dev/gemini-api/docs/document-processing · https://ai.google.dev/gemini-api/docs/media-resolution · https://ai.google.dev/gemini-api/docs/embeddings · https://blog.google/innovation-and-ai/models-and-research/gemini-models/gemini-3-1-pro/
- Anthropic: https://platform.claude.com/docs/en/about-claude/pricing · https://platform.claude.com/docs/en/about-claude/model-deprecations · https://platform.claude.com/docs/en/build-with-claude/vision · https://platform.claude.com/docs/en/build-with-claude/pdf-support · https://platform.claude.com/docs/en/build-with-claude/structured-outputs · https://platform.claude.com/docs/en/build-with-claude/embeddings
- Benchmarks: https://playground.roboflow.com/models/google/gemini-3-7-flash · https://benchmarking.nanonets.com/benchmarks/omnidocbench · https://arxiv.org/html/2603.10910v1 · https://llm-stats.com/benchmarks/ocrbench-v2-(en) · https://mistral.ai/news/mistral-ocr-3/
- Embeddings: https://www.mongodb.com/press/mongodb-announces-acquisition-of-voyage-ai · https://openai.com/index/new-embedding-models-and-api-updates/
- LLM-as-judge bias: https://arxiv.org/abs/2410.21819 · https://arxiv.org/abs/2604.22891 · https://futureagi.com/blog/llm-as-judge-best-practices-2026/
