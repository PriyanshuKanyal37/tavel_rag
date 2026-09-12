# cost-caching-ops

## HEADLINE
Prompt caching on your stable system prompt plus a cached metadata table cuts per-query cost ~50% for filter queries; skip semantic caching entirely in v1 — the false-positive risk destroys trust faster than it saves money.

## RECOMMENDATION
Cache the system prompt and a full 49-property metadata summary table with a 1-hour TTL using Anthropic cache_control markers; use the Message Batches API (50% discount) for all extraction during ingestion; instrument every LLM call with Langfuse (self-hosted, MIT licensed); set a hard monthly workspace spend cap in the Anthropic Console; skip semantic caching in v1; secure with Next.js middleware + iron-session encrypted cookie storing a bcrypt-hashed shared password; pursue ZDR only when deal terms or client names enter query logs.

## WHY
Travel Inn has two query types with wildly different caching safety profiles. Type A (filter/aggregate) requires ALL 49 properties to answer correctly — a cached property metadata table (roughly 12,000-15,000 tokens) in the system prompt, refreshed at most daily, gets cache-hit reads at $0.30/MTok instead of $3.00/MTok, cutting the input cost on every filter query by ~75%. Type B (descriptive) retrieves 3-5 property chunks dynamically — these CANNOT cache because the retrieved context changes per query. Semantic caching is actively dangerous for this corpus: "which properties have fewer than 20 rooms" and "which have fewer than 25 rooms" sit close in embedding space but have different correct answers, and production data shows false positive rates reaching 99% below cosine similarity 0.92 — one wrong driving distance quoted to a foreign tour operator ends the tool's credibility. The query volume (50-1000/day) does not justify the implementation complexity or correctness risk of GPTCache or any equivalent.

## ALTERNATIVES

### Semantic caching (GPTCache or Redis Vector Cache) -> **REJECT**
- PRO: 20-45% hit rate in production on general traffic; ~60-70% on FAQ-style workloads; zero LLM cost on hits
- CON: False positive rates reach 99% at thresholds below 0.90; RAG-specific failure: cached answer ignores the retrieved context that modified the query; factual numeric queries (room counts, distances) are the most sensitive to wrong answers and the hardest to threshold safely; adds Redis or Postgres operational surface; no ROI at 50-1000 queries/day

### Anthropic prompt caching — 5-min TTL -> **CONSIDER**
- PRO: Write at 1.25x base ($3.75/MTok for Sonnet 4.6); read at 0.10x ($0.30/MTok); free to use, no extra infrastructure; cache read is a 90% discount off standard input price
- CON: 5-min TTL means idle gaps between queries blow the cache; system with sporadic usage will pay cache-write costs repeatedly; early March 2026 saw a silent regression where Anthropic dropped default TTL from 1hr to 5min causing 20-32% cost inflation for unaware users

### Anthropic prompt caching — 1-hour TTL -> **USE**
- PRO: Same 0.10x read price; survives natural query gaps in a business-hours-only internal tool; ProjectDiscovery moved dynamic content out of system prompt and raised cache hit rate from 7% to 84%, cutting costs 59%; best fit for a stable property metadata table re-used across all filter queries
- CON: Write costs 2.0x base ($6.00/MTok for Sonnet 4.6); if the table is written once per hour and read 10+ times, it pays back quickly; if queries are sporadic (fewer than ~4/hour), 5-min TTL is cheaper

### Anthropic Message Batches API for ingestion -> **USE**
- PRO: 50% discount across all token types (Sonnet 4.6: $1.50 input, $7.50 output per MTok); async, results within 24 hours; ideal for one-time extraction of 52 files and periodic re-ingestion
- CON: Cannot be used for real-time query answering; 24-hour turnaround means it is ingestion-only

### Langfuse for observability (self-hosted) -> **USE**
- PRO: MIT licensed; predefined Claude pricing models built-in including Sonnet 4.6; per-generation token + cost tracking with custom metadata (query_type, session_id, properties_retrieved); free to self-host on a $5/month VPS; integrates with Next.js via JS SDK in a single wrapper
- CON: Self-hosting adds one more thing to operate; cloud tier is free up to 50k events/month which covers 50 queries/day comfortably

### Helicone for observability -> **REJECT**
- PRO: One-line header injection; fastest setup
- CON: Acquired by Mintlify in early 2026; product direction unclear post-acquisition; Langfuse is more stable for production commitment

### Anthropic Spend Limits API (programmatic per-user caps) -> **PHASE-2**
- PRO: Full API control: GET effective limits, POST overrides, monitor period_to_date_spend; supports automation
- CON: Enterprise plan only — not available on standard API accounts; v1 has no per-user accounts anyway; Console workspace cap achieves the same protection for v1

### Next.js middleware + iron-session (shared password, v1 auth) -> **USE**
- PRO: Stateless encrypted cookie; no database; ~2KB dependency; httpOnly + secure + sameSite=strict by default; bcrypt hash in env var keeps plaintext out of code; upgradeable to NextAuth.js later without rewriting the middleware layer
- CON: Single shared secret means no audit trail per user; revocation requires rotating the env var and redeploying; acceptable for 10 internal users, not for 50-100

### Zero Data Retention (ZDR) from Anthropic -> **PHASE-2**
- PRO: Inputs and outputs not stored at rest after API response; strongest privacy posture for commercially sensitive supplier data
- CON: Enterprise plan required plus separate enablement by Anthropic (contact sales); standard API already limits retention to ~30 days; for v1 with no PII and no client names in queries, standard API is sufficient

## KEY FINDINGS
- Anthropic Sonnet 4.6 prompt caching: 5-min TTL writes at $3.75/MTok, 1-hour TTL writes at $6.00/MTok, reads at $0.30/MTok (90% off) for both — the read price is identical regardless of TTL tier.
- Cache invalidation is byte-exact: any whitespace change, reordered tool definition, or timestamp injected into the prefix silently breaks the cache. A March 2026 infrastructure regression silently dropped default TTL from 1hr to 5min for some accounts, causing 20-32% unexpected cost inflation — always explicitly set cache_control breakpoints rather than relying on defaults.
- ProjectDiscovery production case study: moving dynamic content out of system prompt raised cache hit rate from 7% to 84% and cut total costs 59%. The takeaway for Travel Inn: the 49-property metadata summary table belongs in the cached prefix; the dynamically retrieved full-text chunks belong after the last cache_control marker.
- Semantic caching false positive rates reach 99% at cosine similarity thresholds below 0.90; factual/RAG workloads require 0.92+ threshold; even then, researchers conclude 'pure semantic similarity is not a sound proxy for answer validity in parameter-rich industrial queries.' The query mix here (room counts, km distances, price ranges) is maximally sensitive to this failure.
- Message Batches API: 50% flat discount — Sonnet 4.6 drops to $1.50 input / $7.50 output per MTok for async processing. One-time extraction of 52 files and periodic re-ingestion are the correct use case.
- Realistic cost model: at 50 queries/day (~1,500/month) total cost is approximately $60-70/month all-in (LLM + Neon + R2 + embedding). At 300 queries/day (~9,000/month) approximately $200-240/month. At 1,000 queries/day (~30,000/month) approximately $560-710/month. LLM inference is 65-75% of the bill; corpus size growth barely affects per-query cost unless context windows expand significantly.
- Hard spend cap: set a monthly workspace spend limit in the Anthropic Console (all API tiers, not just Enterprise). The programmatic Spend Limits API (per-user, REST endpoints) is Enterprise-only. For v1 with one shared API key, the Console cap is sufficient; set it at 2x expected monthly spend and add a Langfuse alert at 80% of that threshold.
- Anthropic ZDR (Zero Data Retention): requires Enterprise plan plus separate enablement by Anthropic. Standard API retains inputs/outputs for up to 30 days for trust and safety. For a v1 internal tool with no PII and commercial-but-not-regulated supplier data, standard API is acceptable. Escalate to ZDR when foreign tour operator names, negotiated rates, or client deal terms start appearing in query logs.
- Note on current leaning: the cited 'claude-sonnet-5 introductory pricing' ($2 input / $10 output per MTok) was listed as valid through August 31, 2026. That window has now closed; verify current Sonnet pricing in the console before finalizing budget models — standard rate is $3 input / $15 output per MTok.

## PITFALLS
- Putting dynamic content (retrieved chunks, timestamps, session IDs, current date) anywhere before the last cache_control marker. This produces a 0% cache hit rate while still paying 1.25x or 2.0x write costs on every call. Audit the full assembled prompt in staging and assert that nothing after the final system-prompt block ever changes between requests.
- Using semantic caching for filter/aggregate queries (query type A). 'Which properties have a pool' and 'which properties have a pool and a gym' embed close to each other but require different correct answers. One wrong cached answer shared across the sales team — especially if it is a driving distance or a price — ends adoption.
- Forgetting that the 1-hour TTL cache-write costs 2.0x base. If fewer than ~4 queries hit within the hour, you pay more than uncached. At 50 queries/day that is roughly 2 queries/hour on average — borderline. Model actual usage patterns before committing to 1-hour TTL on the system prompt; 5-min TTL may be cheaper for very sparse early-morning/late-evening traffic.
- Logging raw query text to Langfuse or any external service. Sales queries will eventually contain client names, negotiated pricing, or deal-stage context — exactly the data that should never leave the organization. Log only metadata: token counts, cost, latency, session_id (opaque), query_type enum, and which property IDs were retrieved.
- Storing the shared password in plaintext in the .env file or hardcoding it in middleware. Use bcrypt hash stored as an environment variable; compare at login time. Plaintext passwords in env files routinely end up in commit history or Vercel environment variable exports.
- Assuming the Spend Limits API is available on a standard API account. It is Enterprise-only. Without it, the only programmatic spend guard is a middleware-layer token counter you build yourself (incrementing a Neon counter per request and returning 429 above a daily limit). For v1, the Console workspace cap is the simpler correct answer.
- Re-embedding documents on every ingestion run. Cache embeddings in the Neon database (store a content hash alongside the vector). On re-ingestion, skip any file whose SHA-256 matches the stored hash. This cuts Gemini Embedding API costs to near-zero on incremental updates and is a 3-line change to the ingestion script.

## IMPLEMENTATION NOTES
- Prompt structure (order matters for caching): [1] cache_control: ephemeral on system instructions block (~2,000 tokens, stable) [2] cache_control: ephemeral on the 49-property metadata table (~12,000-15,000 tokens, refresh daily via a scheduled re-ingestion) [3] no cache_control on the dynamically retrieved full-text chunks [4] user query as the last user message. Anthropic allows max 4 cache_control markers per request.
- Property metadata table format for caching: one row per property with tab-delimited fields: name | state | nearest_airport_km | nearest_airport_hours | room_count | price_range_INR | meal_plan | has_pool | has_wildlife_gate_minutes | best_time_to_visit | inspection_status. 49 rows × ~280 tokens = ~13,700 tokens total. This table answers all type-A filter/aggregate queries without any vector retrieval — the LLM scans it directly.
- Batch API ingestion call pattern: POST /v1/messages/batches with an array of requests, each containing the extraction prompt + one file's content. Poll GET /v1/messages/batches/{batch_id} until processing_status = 'ended'. Expected turnaround: 2-8 hours for 52 files. Store batch_id in Neon to resume on failure without re-submitting completed items.
- Langfuse instrumentation (Next.js API route): wrap each Claude call in langfuse.generation({ name: 'rag-answer', model: 'claude-sonnet-4-6', input: assembledPrompt, metadata: { query_type: 'filter_aggregate' | 'descriptive', session_id: req.cookies.session_id, properties_retrieved: chunk_ids } }); call generation.end({ output: response.content[0].text, usage: { input: response.usage.input_tokens, output: response.usage.output_tokens, cache_read_input: response.usage.cache_read_input_tokens, cache_creation_input: response.usage.cache_creation_input_tokens } }). The cache_* token fields are what Anthropic returns in the API response.
- iron-session auth setup for Next.js: npm install iron-session; create middleware.ts that checks for a signed session cookie named 'travelinn_session'; on POST /api/auth/login, compare bcrypt.compare(body.password, process.env.SHARED_PASSWORD_HASH); if match, create session with await sealData({ loggedIn: true }, { password: process.env.SESSION_SECRET, ttl: 604800 }); set-cookie with httpOnly, secure, sameSite=strict, path=/. Rate-limit the login endpoint at 5 attempts per 15 minutes using Upstash Redis free tier (10,000 requests/day free).
- Console spend cap setup: Anthropic Console → Settings → Billing → Monthly spend limit → set to 2x your expected monthly spend (e.g., $150 if expecting $70/month). This is a hard block, not a soft alert. Also configure a Langfuse metric alert: when 30-day rolling cost_usd exceeds 80% of the cap, fire a webhook to a Slack channel.
- Embedding cache: add a column content_sha256 TEXT to the neon documents table alongside the embedding vector. In the ingestion script, before calling Gemini Embedding API, SELECT embedding FROM documents WHERE content_sha256 = $1; skip the API call if a row is returned. Cost: Gemini Embedding 2 at $0.00004/1K tokens — with 207MB of source files this is roughly $2-3 total for initial ingestion, negligible, but the pattern matters for the 500-file v2 corpus.
- Cost scaling to Phase 2 (500 properties, ~500K chunks): the metadata table grows from ~14K tokens to ~140K tokens. At 140K tokens, a 1-hour cache write costs $0.84 per cache miss (140K × $6/MTok); if hit 20+ times per hour this is still economical. Alternatively, move filter/aggregate queries to a SQL-based approach against a structured Neon table (property metadata as proper columns) so they bypass the LLM entirely for pure filter operations — this is the correct architectural split at scale.

## SOURCES
- https://www.respan.ai/articles/claude-prompt-caching
- https://github.com/anthropics/claude-code/issues/46829
- https://www.digitalapplied.com/blog/prompt-caching-2026-cut-llm-costs-engineering-guide
- https://brandonwie.dev/posts/anthropic-prompt-cache-ttl
- https://www.finout.io/blog/anthropic-api-pricing
- https://platform.claude.com/docs/en/manage-claude/spend-limits-api
- https://privacy.claude.com/en/articles/8956058-i-have-a-zero-data-retention-agreement-with-anthropic-what-products-does-it-apply-to
- https://langfuse.com/docs/observability/features/token-and-cost-tracking
- https://langfuse.com/resources/engineering/llm-cost-management
- https://portkey.ai/blog/semantic-caching-thresholds/
- https://dev.to/gauravdagde/llm-semantic-caching-the-95-hit-rate-myth-and-what-production-data-actually-shows-8ga
- https://www.spheron.network/blog/semantic-cache-llm-inference-gpu-cloud/
- https://arxiv.org/pdf/2607.04281
- https://spendark.com/blog/rag-system-cost/
- https://www.raftlabs.com/blog/rag-development-cost
- https://pristren.com/blog/anthropic-batch-api-guide/
- https://neuraltrust.ai/blog/llm-caching-strategies
- https://blog.ratu.dev/simple-password-protection-for-a-next-js-app-1ff21ada93a3
- https://dev.to/itwasmattgregg/easily-password-protect-nextjs-pages-with-iron-session-3ljo