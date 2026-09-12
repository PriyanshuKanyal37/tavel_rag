# backend-production

## HEADLINE
Use Node runtime Route Handlers with Fluid Compute on Pro plan, Neon HTTP driver with pooled URL, Langfuse OTel for traces, and run ingestion as a local script — the current leaning holds on all major choices.

## RECOMMENDATION
Next.js 15+ App Router on Vercel Pro with Fluid Compute enabled (default for new projects since April 23, 2025). Chat API as a Node-runtime Route Handler at app/api/chat/route.ts with `export const maxDuration = 800`. Neon serverless driver (`@neondatabase/serverless`) using HTTP transport with Neon's built-in PgBouncer pooled connection string. Rate limiting via `@upstash/ratelimit` in middleware. Observability via Langfuse with `@langfuse/otel` wired into `instrumentation.ts`. Ingestion as a local TypeScript script, never on Vercel.

## WHY
This project has two characteristics that dominate every decision: (1) the LLM call is I/O-heavy with unpredictable latency (Anthropic claude-sonnet-5 + Gemini cross-check on retrieval), and (2) each request is stateless but the corpus lookup touches Neon with pgvector. Fluid Compute is purpose-built for this: one instance handles many concurrent waiting requests, and you pay only for active CPU, not the 2-15 seconds waiting on the model. The Node runtime is non-negotiable because OTel/NodeSDK, the Neon WebSocket driver, and AI SDK v7's full streaming support all require Node.js 22+ — none run in the Edge isolate. The ingestion pipeline (52 files, Vision API + embedding per file) will always exceed 300s on a Hobby plan and will frequently hit 800s on Pro, making it wrong for Vercel entirely. A local script is the right fit for a one-time offline batch.

## ALTERNATIVES

### Server Actions for chat streaming -> **REJECT**
- PRO: Simpler DX, no separate HTTP endpoint, co-located with UI
- CON: Server Actions do not support true SSE/streaming token delivery to the browser the way Route Handlers do. They use a form-action model that does not compose cleanly with AI SDK's createUIMessageStreamResponse. Will cause UX regressions on slow LLM calls.

### Edge runtime for chat route -> **REJECT**
- PRO: Lower cold start latency (~0ms vs ~200ms Node cold start), globally distributed
- CON: OTel NodeSDK and LangfuseSpanProcessor are Node.js-only. Neon WebSocket transport unavailable. AI SDK v7 requires Node 22+. Edge bundle ceiling is 1-4 MB — AI SDK + OTel + Langfuse deps alone exceed this. The 25s first-byte deadline is an additional constraint on top of model latency.

### Standard pg / node-postgres with TCP pool -> **REJECT**
- PRO: Familiar API, compatible with all Postgres tooling including migrations
- CON: TCP connections from serverless functions cause connection storms — each cold start opens a new TCP connection. Neon will rate-limit you above ~100 concurrent connections on shared plans. With Fluid Compute handling many concurrent requests per instance, file descriptor exhaustion (1024 FD limit shared across all concurrent executions) becomes real.

### Helicone for LLM observability -> **REJECT**
- PRO: 5-minute setup, just change base URL, automatic cost tracking
- CON: Helicone is a proxy and sees only flat request lists — it cannot capture the parent-child span structure needed for RAG (embedding query, vector retrieval, rerank, generate). You lose per-step latency attribution which is essential for debugging retrieval quality.

### LangSmith for observability -> **REJECT**
- PRO: Strong evaluation tooling, widely adopted
- CON: Value collapses outside LangChain/LangGraph. This project uses Vercel AI SDK with manual orchestration, not LangChain. You would maintain an alien SDK integration for no gain over Langfuse.

### Vercel Cron for ingestion -> **REJECT**
- PRO: Managed scheduling, no separate infrastructure
- CON: 52-file batch with Vision API + embedding will exceed 300s (Hobby) or even 800s (Pro) per run. Vercel Cron invokes a Function endpoint with the same duration limits. No benefit over a local script for a one-time operation.

### pgBouncer external (self-managed) -> **REJECT**
- PRO: More control over pool parameters
- CON: Neon's built-in PgBouncer is already bundled in every Neon project as a separate pooled connection string. Adding an external pgBouncer creates double pooling which the Neon docs explicitly warn against. One extra moving part for zero gain.

### Vercel KV for rate limiting -> **REJECT**
- PRO: Native Vercel integration, no separate account
- CON: Vercel KV is powered by Upstash under the hood anyway. Direct Upstash connection gives the same performance with more control and a more generous free tier (10k requests/day free vs Vercel KV's limits). No reason to use the wrapper.

## KEY FINDINGS
- Fluid Compute is now the default execution model for all new Vercel projects (since April 23, 2025). One instance handles many concurrent requests. For LLM workloads with 2-15s I/O waits, Vercel charges only active CPU time, not wait time — this makes Fluid Compute significantly cheaper than old serverless for this use case (up to 85% cost reduction reported).
- Exact duration limits (from official Vercel docs, last updated 2026-08-24): Hobby = 300s hard max. Pro/Enterprise = 300s default, 800s max (GA), 1800s extended max (beta, requires function-level config). Edge runtime must begin streaming within 25s and can stream for max 300s total. Set `export const maxDuration = 800` in app/api/chat/route.ts for Pro plan.
- Edge runtime is incompatible with three critical dependencies: OTel NodeSDK (Langfuse instrumentation), AI SDK v7 which requires Node.js 22+, and Neon WebSocket transport. Edge bundle ceiling of 1-4 MB would be exceeded by AI SDK + OTel + Langfuse alone. Use Node runtime for the chat route.
- Neon serverless driver: use `neon()` HTTP transport (from @neondatabase/serverless) with Neon's pooled connection string (the -pooler URL from Neon dashboard) for all app queries including pgvector similarity search. Each invocation fires one HTTP round trip — approximately 3 round trips vs 8 for TCP — no persistent connection held. This avoids the 1,024 file descriptor limit that Vercel enforces across all concurrent executions on a single Fluid instance.
- Double pooling is a documented Neon pitfall: do NOT combine Neon's pooled URL with a client-side `new Pool()`. Use the pooled Neon URL with the bare `neon()` function. Use the direct (non-pooler) URL only for database migrations.
- Vercel request body size limit is 4.5 MB hard limit. Chat history passed in the POST body must be trimmed client-side for long conversations or you will hit FUNCTION_PAYLOAD_TOO_LARGE in production (does not happen in local dev).
- Langfuse is the correct observability choice for this RAG stack. It captures nested spans (retrieval → embedding → rerank → generate) via OTel GenAI semantic conventions. Wire it in instrumentation.ts with @langfuse/otel + @langfuse/vercel-ai-sdk. Free cloud tier: 50,000 events/month — sufficient for 10 sales agents at launch. AI SDK v7 (GA September 2025) emits telemetry by default once registered; v6 required experimental_telemetry: { isEnabled: true } per call.
- Ingestion pipeline must be a local script. Reasons: Vision API call per image (Gemini 3.1-pro-preview) + embedding call per chunk + pgvector upsert, across 52 files with 4 templates — total wall time will exceed 300s for the full corpus. It is a one-time offline batch. Phase 2 (500 GB, ~500k chunks) should move to a dedicated worker (Modal.com or a spot EC2 with a simple Python script), not Vercel.

## PITFALLS
- Missing maxDuration export is the single most common production failure. In local dev, Next.js has no timeout. On Vercel, the default is 300s and any LLM call that exceeds it returns a 504 FUNCTION_INVOCATION_TIMEOUT to the user. Add `export const maxDuration = 800` at the top of app/api/chat/route.ts. This must be a named export in the route file itself — next.config.ts does not override per-route duration.
- instrumentation.ts requires `experimental.instrumentationHook: true` in next.config.ts for Next.js versions below 15. In Next.js 15+ it is built-in. If this flag is missing, OTel and Langfuse are silently not initialized and you get zero traces in production with no error.
- Never prefix LLM API keys or database URLs with NEXT_PUBLIC_. A 2025 study found 0.45% of Vercel-hosted services were actively leaking live secret keys in frontend JavaScript. ANTHROPIC_API_KEY, NEON_DATABASE_URL, LANGFUSE_SECRET_KEY, CHAT_PASSWORD — all server-only, no NEXT_PUBLIC_ prefix. The CHAT_PASSWORD for single shared auth must never appear in client bundles.
- File system is unavailable on Vercel Functions at runtime. Any ingestion code that reads PDF/image files from local disk must not be deployed or imported by app routes. Keep scripts/ entirely separate and add it to .vercelignore. The current plan to store files in Cloudflare R2 is correct — never attempt to bundle source documents into the function.
- Standard TCP-based pg will cause connection storms and file descriptor exhaustion with Fluid Compute. Each concurrent request on the same Fluid instance shares 1,024 file descriptors. 10 concurrent chat requests each holding a TCP pg connection = 10 FDs minimum, plus Node.js runtime usage. Use HTTP transport (neon() function) which closes the connection after each query.
- AI SDK v7 streaming response format changed from v6. If you copy code from articles or templates using StreamingTextResponse (v5/v6 API), it will fail in production with a type error. The correct v7 pattern is: createUIMessageStreamResponse({ stream: toUIMessageStream({ stream: result.stream }) }).
- Neon scale-to-zero can add 500ms-2s cold start latency on the database side if your Neon compute has been idle. For a sales team tool used during business hours this is acceptable. But the first query of each day will be slow. Disable scale-to-zero on the Neon compute if the team reports it, or use Neon's always-on option on paid plans.

## IMPLEMENTATION NOTES
- Project structure: app/api/chat/route.ts (Node runtime, maxDuration=800, POST streaming), app/page.tsx (useChat hook client), middleware.ts (Edge OK: password check + Upstash rate limit redirect), instrumentation.ts (Node: OTel + Langfuse), lib/db.ts (neon() with NEON_DATABASE_URL pooled), lib/queries.ts (vector search + structured filter SQL), lib/rate-limit.ts (Ratelimit instance), scripts/ingest/ (local only, .vercelignore'd).
- app/api/chat/route.ts must export: `export const runtime = 'nodejs'` and `export const maxDuration = 800`. Without both, Vercel may default to shorter timeouts or apply Edge restrictions.
- Neon connection: two env vars required — NEON_DATABASE_URL (pooled, -pooler hostname, for all app queries) and NEON_DATABASE_URL_DIRECT (direct hostname, for ingestion script migrations with drizzle-kit push or pg-migrate). Never use the direct URL in app routes.
- Rate limiting in middleware.ts: `import { Ratelimit } from '@upstash/ratelimit'; import { Redis } from '@upstash/redis'`. Use `Ratelimit.slidingWindow(10, '1 m')` for the /api/chat path keyed by IP (req.ip from x-forwarded-for). Return 429 with Retry-After header. When per-user accounts arrive in Phase 2, switch the key to the session userId.
- instrumentation.ts setup for AI SDK v7 + Langfuse: `import { registerTelemetry } from 'ai'; import { LangfuseSpanProcessor } from '@langfuse/otel'; import { LangfuseVercelAiSdkIntegration } from '@langfuse/vercel-ai-sdk'; import { NodeSDK } from '@opentelemetry/sdk-node'`. Env vars: LANGFUSE_SECRET_KEY, LANGFUSE_PUBLIC_KEY, LANGFUSE_BASEURL (defaults to cloud). To add RAG retrieval as a named span, wrap the pgvector query in a manual OTel span: `tracer.startActiveSpan('retrieval', async (span) => { ... span.end() })`.
- Ingestion script idempotency: create a source_documents table with columns (id, file_path, file_hash TEXT UNIQUE, extracted_json JSONB, processed_at TIMESTAMPTZ). Compute SHA-256 of each source file before processing. Use `INSERT ... ON CONFLICT (file_hash) DO NOTHING` to skip already-processed files. For chunk upserts: (source_doc_id, chunk_index) as composite unique key with ON CONFLICT DO UPDATE.
- Secrets list for Vercel Environment Variables (all server-only, mark Sensitive): ANTHROPIC_API_KEY, GEMINI_API_KEY (ingestion only, can omit from Vercel), NEON_DATABASE_URL, NEON_DATABASE_URL_DIRECT, LANGFUSE_SECRET_KEY, LANGFUSE_PUBLIC_KEY, UPSTASH_REDIS_REST_URL, UPSTASH_REDIS_REST_TOKEN, CHAT_PASSWORD. Scope GEMINI_API_KEY to local/.env.local only since it is not needed by any deployed Vercel function.
- Add to .vercelignore: scripts/, *.pdf, *.png, *.jpeg — source documents and ingestion scripts must not be bundled. Add to next.config.ts: `experimental: { instrumentationHook: true }` if on Next.js 14; remove this flag on Next.js 15+ where it is automatic.
- For the hybrid query problem (filter/aggregate vs semantic): the chat route must detect query intent and route accordingly. Filter queries (rooms < 20, price < 15000) should hit a SQL query against the structured JSONB fields — not vector search. Semantic queries hit pgvector. A simple classifier prompt before the main call (one token, 'filter' or 'semantic') adds ~200ms but prevents confident hallucinations on aggregate questions. This is the most important architectural decision for query correctness, not infrastructure.

## SOURCES
- https://vercel.com/docs/functions/limitations
- https://vercel.com/blog/how-fluid-compute-works-on-vercel
- https://vercel.com/docs/fluid-compute
- https://vercel.com/changelog/higher-defaults-and-limits-for-vercel-functions-running-fluid-compute
- https://vercel.com/changelog/vercel-functions-can-now-run-up-to-30-minutes
- https://neon.com/docs/connect/choose-connection
- https://neon.com/docs/serverless/serverless-driver
- https://ai-sdk.dev/docs/getting-started/nextjs-app-router
- https://langfuse.com/integrations/frameworks/vercel-ai-sdk
- https://langfuse.com/changelog/2026-06-26-vercel-ai-sdk-7
- https://particula.tech/blog/helicone-vs-langfuse-vs-langsmith-llm-observability
- https://upstash.com/blog/nextjs-ratelimiting
- https://vercel.com/docs/functions/configuring-functions/duration
- https://makerkit.dev/blog/tutorials/server-actions-vs-route-handlers
- https://dub.co/blog/zod-api-validation
- https://oneuptime.com/blog/post/2026-01-24-fix-nextjs-edge-runtime-limitations/view