## CONTRADICTIONS (must resolve before one line of code)

**C1. BM25 availability is now accurate but the research isn't.** Three objections declare "pg_search is unavailable on new Neon projects" as a confirmed blocker and use it to invalidate the retrieval headline. That was true in March 2026. Neon shipped `lakebase_text` with a `lakebase_bm25` index type in June 2026, available to all Postgres 16+ users, with standard tsvector compatibility and no extension port required. The objections' central technical premise is now obsolete. The research fleet needs a clean position: hybrid BM25+vector on Neon IS buildable today via `CREATE INDEX ... USING lakebase_bm25`. Whether to build it is a separate question, but the constraint that drove multiple "delete everything" arguments is gone.

**C2. Citations API: use it or delete it.** generation-and-grounding headline recommends Citations API as the grounding mechanism. generation-and-grounding/over-engineering says delete it entirely and use self-describing text headers with a 10-line string check. These are mutually exclusive implementation choices for the single most user-visible trust feature. The "incompatibility with structured outputs" argument in the headline is real (`output_config.format` vs `citations.enabled`) but does NOT conflict with tool use - the search tool (`web_search_20260209`) and Citations API coexist natively. The actual constraint is narrower than stated. Pick one grounding mechanism before building the generation route.

**C3. Cached corpus prefix: include or delete.** cost-caching-ops headline recommends a 12-15k-token summary of all 49 properties in the cached system prompt. Four separate objections (cost/failure-modes, cost/scale-forward, generation/over-engineering, retrieval/over-engineering) identify this as a second source of truth that actively subverts the SQL routing layer - the model will answer Type A from the stale in-context table rather than calling the tool. This contradiction is architectural: if you build the SQL tool for Type A correctness, the cached corpus table undermines it. Resolution required: either cache the corpus (no SQL tool for Type A) or use the SQL tool (no corpus in the prompt for Type A). The two together are not belt-and-braces; they are conflicting authorities.

**C4. Tool interface cannot express ORDER BY.** retrieval-architecture/over-engineering proposes two tools: `find_properties({filters})` and `get_properties({ids})`. retrieval-architecture/failure-modes correctly notes that acceptance questions Q10 ("closest to airport") and Q11 ("closest to safari gate") are ranking queries - ORDER BY over a child relation - which a predicate-only filter tool cannot express. No research dimension provides a concrete tool signature that handles both `WHERE rooms < 20` and `ORDER BY airport_km ASC LIMIT 5` on a multi-airport child table. This must be specified before the backend tool schema is written.

**C5. PNG extraction: 2x-then-cap fails the whole corpus.** document-extraction headline recommends `2x upscale then cap at 4096px height`. document-extraction/failure-modes proves with arithmetic that this NARROWS the tallest files below their original resolution (794x5150 becomes 631px wide after the cap). The two objections give different fixes (tile at native width vs tile at native width then 2x each tile). Neither the headline nor the objections agree on an implementation. Given that a misread room count or driving distance is described as a permanently trust-destroying failure, this is not cosmetic.

**C6. Source viewer for PDFs: three incompatible choices.** frontend-ux headline recommends react-pdf. frontend-ux/over-engineering recommends an iframe. frontend-ux/failure-modes recommends rendering PDFs to PNG at ingestion and serving as `<img>`. These require different R2 storage strategies (raw PDF vs rendered PNGs), different API route logic, and different citation link formats. Choose one before designing the R2 key structure.

**C7. Schema shape: flat vs child tables vs EAV.** The properties table design is contested across six objections but never resolved into a single DDL. The specific conflicts: (a) airports/railheads/gates must be child rows (one-to-many confirmed by Vayal Veedu with 3 airports) vs scalar columns in the tool interface which assume one value; (b) amenities as bare BOOLEAN vs tri-state `present|absent_explicit|not_stated` vs `attrs JSONB`; (c) prices as a scalar `price_min_inr` that is incomparable across meal plan codes vs a `property_rates` child table. An engineer cannot write the migration until these are settled.

---

## MISSING ARCHITECTURAL CONCERNS

**M1. CVE-2025-29927 directly attacks the auth design.** The shared-password implementation places auth logic in Next.js middleware. CVE-2025-29927 (patched in Next.js 15.2.3) allows middleware bypass via a crafted `x-middleware-subrequest` header. On any version below 15.2.3, the password gate is skippable without a valid credential. None of the research mentions this vulnerability. The fix is pinning Next.js >=15.2.3 and verifying it at deploy time, but it must be an explicit constraint, not assumed.

**M2. Data residency must gate the database project creation.** OPEN-ITEMS #1 lists India data residency as "BLOCKING" and correctly notes the Neon region is immutable at project creation. No research dimension resolves this. Neon has no `ap-south-1` region (nearest is Singapore). If Travel Inn's contracts with foreign tour operators or Indian data law require India-resident storage, Neon is disqualified before any schema is designed. The decision tree is: get written yes/no from Sukanya/Gaurav on residency requirement -> if yes, move to AWS RDS/Aurora ap-south-1 (Mumbai) + pgvector (identical schema) or Supabase Mumbai -> if no, Neon Singapore. This decision has no technical substitute and must precede any database work.

**M3. The "gemini-3.1-pro-preview" model does not exist.** The brief specifies `gemini-3.1-pro-preview` as the extraction model. Google's current naming is `gemini-2.5-pro` and `gemini-2.5-flash`. There is no 3.x Gemini model. A preview model suffix is also explicitly warned against by document-extraction/failure-modes ("avoid pinning a -preview model for a job you will re-run on every schema change"). The architecture document must name real, GA model IDs, or extraction cannot be scripted.

**M4. No update workflow for the source files.** The corpus lives in "Gaurav's personal OneDrive" (per OPEN-ITEMS). When a property is updated - seasonally changed prices, a new brochure replacing a 2024 sheet - there is no designed path from OneDrive to R2 to re-ingestion to the live DB. The research repeatedly says "re-ingest is a local script" but never specifies: who runs it, when, triggered by what signal, with what impact on the live system during re-ingest, and how the sales team knows that yesterday's answer about pricing is now stale. This is the highest-probability day-1 operational failure.

**M5. Star ratings are absent from all source files but are the primary quoting parameter.** ANSWERS.md confirms zero mentions of star ratings across 52 files. Multiple objections flag this. No research dimension provides a resolution. The architecture needs an explicit answer: either (a) a `manual_overrides(property_id, field, value, set_by, set_at)` table editable by the founder for facts the brochures don't contain, or (b) a hard-coded refusal for star rating queries. Without one of these, a question that is described as the primary quoting parameter returns a grounded refusal on day one, which is a demo-killing failure that is fully preventable.

**M6. The build sequence has a chicken-and-egg problem.** The schema depends on knowing what the extraction pipeline can reliably produce. The extraction pipeline depends on having a target schema to validate against. The evaluation golden set depends on the schema being stable. The frontend citation links depend on the R2 key structure. No research dimension establishes a build order. A concrete sequence: (1) extract all 52 files with a loose schema, (2) human review to establish ground truth and settle contested fields (the tri-state amenities, multi-airport, meal plans), (3) finalize DDL, (4) write ingest script, (5) build API, (6) build frontend. Deviating from this order forces rebuilds.

**M7. No admin/re-ingest interface means the client is permanently dependent on the builder.** The system has no non-technical interface for adding a new property or updating an existing one. At handover, the only path to update the data is to run a local Node script with database credentials. This means either (a) a developer must be involved for every data update forever, or (b) a minimal admin interface (a CSV upload or a "re-ingest from R2" button behind the same shared password) must be scoped into v1. This is a handover blocker that is completely absent from the research.

**M8. GUC isolation via `sql.transaction([])` is confirmed viable but needs an explicit code pattern.** backend-production/failure-modes and scale-forward both raise the SET LOCAL issue with the HTTP driver. The research confirms `transaction([SET LOCAL ..., SELECT ...])` batches into one HTTP request with correct GUC isolation. However, this pattern must be the standard helper for all vector queries in the codebase - a loose `SET` call anywhere becomes a silent no-op. No research dimension codifies this as a required pattern, which means an engineer reading the recommendations could implement it wrong.

---

## OPERATIONAL GAPS (bite post-launch)

**O1. Shared password rotation has no designed path.** iron-session uses an encrypted cookie keyed to the password. If the password must rotate (a former employee), every active session is invalidated with no warning. With 10 users who may be mid-demo with a foreign tour operator when the password changes, this is a trust event. The iron-session password field supports incremental key rotation (`{1: old, 2: new}`), which allows graceful migration. This mechanism exists but is not mentioned anywhere in the research.

**O2. The session has no rate limit on the login route.** cost-caching-ops/failure-modes mentions this in passing. A shared password on a public Vercel URL with no rate limit on `/api/login` is trivially brute-forceable. The endpoint must have at minimum 5-attempt/15-minute/IP throttling. With Vercel's WAF on Pro tier this is a firewall rule; without it, it requires explicit middleware code.

**O3. Stale data has no UI signal.** Multiple objections identify that the corpus spans Sep 2024 to May 2026, with some files 23 months old. A price answer with no date context leads to a wrong quote to a foreign operator. The research recommends `doc_date` columns but no research dimension specifies what the user sees in the UI. The citation must show "as of [date]" for every factual claim. For the 8 PDFs with no date in text, the display must say "undated source" not a guessed date.

**O4. The corpus has a live known duplicate that invalidates COUNT queries.** Ramathra Fort exists in two folders with identical SHA1. No research dimension specifies when deduplication runs (at ingestion? at query time?) or what the dedup key is (SHA1? canonical property name?). Until this is explicitly resolved in the ingestion script, "which properties have fewer than 20 rooms" may return 50 rows for 49 properties, and any COUNT is wrong.

**O5. The Oberoi Rajgarh contradiction needs a specific resolution before the demo.** Two in-scope files (PNG says "should open March 2025", PDF describes it operating) give opposite answers. The demo will almost certainly surface one of the two answers. "Surface both with dates and let the sales team verify" is the correct policy, but it must be explicitly implemented: if two source documents for the same property disagree on a field, the answer must say so with both source dates rather than picking one confidently.

**O6. No mobile or low-bandwidth story.** The frontend research is desktop-only. Indian sales staff working on-site at properties or in transit will use phones. At 794x5150px PNGs being served from R2 (2-6 MB per document), a source panel that opens on mobile consumes a meaningful data plan and takes 10+ seconds on 4G. A viewport-optimized source viewer and lazy image loading are not addressed.

---

## WHAT MUST BE DECIDED IN WRITING BEFORE BUILDING

In priority order, these are decisions with no technical substitute:

1. India data residency: yes or no (gates database provider and region)
2. Canonical schema DDL: flat columns + child tables (airports, rates) + tri-state amenities - one agreed DDL
3. Generation grounding mechanism: Citations API or self-describing headers (one choice)
4. Cached corpus prefix: include or exclude from system prompt (one choice, with the SQL tool behavior following)
5. Tool interface: exact TypeScript signatures for all tools including ranking queries
6. Star ratings gap: manual override table or hard-coded refusal
7. Update workflow: who triggers re-ingest, how, and what the sales team sees
8. PNG extraction: tiling strategy (exact dimensions and overlap)
9. Source viewer: react-pdf vs iframe vs rendered PNG (with R2 key structure following)
10. Next.js version pin: >=15.2.3 explicit constraint

Sources:
- [The pg_search extension - Neon Docs](https://neon.com/docs/extensions/pg_search)
- [Lakebase Search: vector and BM25 on Neon](https://neon.com/blog/lakebase-search-on-neon)
- [Lakebase Search - Neon Docs](https://neon.com/docs/ai/lakebase-search)
- [CVE-2025-29927: Next.js Middleware Authorization Bypass](https://projectdiscovery.io/blog/nextjs-middleware-authorization-bypass)
- [CVE-2025-29927 - JFrog Analysis](https://jfrog.com/blog/cve-2025-29927-next-js-authorization-bypass/)
- [Efficiently manage database connection pools with Fluid compute | Vercel](https://vercel.com/kb/guide/efficiently-manage-database-connection-pools-with-fluid-compute)
- [Connecting to Neon from Vercel - Neon Docs](https://neon.com/docs/guides/vercel-connection-methods)
- [Structured outputs - Claude Platform Docs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs)
- [Anthropic's new Citations API - Simon Willison](https://simonwillison.net/2025/Jan/24/anthropics-new-citations-api/)
- [iron-session GitHub](https://github.com/vvo/iron-session)
- [Next.js Authentication Guide 2026 - Clerk](https://clerk.com/articles/nextjs-authentication-guide-2026)
- [Building a knowledge base with Vector and BM25 search using Neon Lakebase extensions](https://neon.com/guides/lakebase-vector-bm25-search)