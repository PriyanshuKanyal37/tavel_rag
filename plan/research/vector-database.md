# vector-database

## HEADLINE
pgvector on Neon is the correct choice for this project at all phases described, with halfvec(1536) as the mandatory type and iterative scans enabled — the cold-start behavior on Neon is the single real operational concern to mitigate.

## RECOMMENDATION
Use pgvector 0.8.0 on Neon with halfvec(1536) and HNSW index (m=16, ef_construction=64, ef_search=100). Enable iterative scans (hnsw.iterative_scan = 'relaxed_order') for all filter queries. Set maintenance_work_mem to 4GB during index builds. Add a keep-alive ping on a 4-minute cron to prevent compute suspend between user sessions.

## WHY
This project's dual query types (filter/aggregate across all 49-500 properties AND semantic per-property) are solved by SQL WHERE + pgvector ORDER BY with iterative scans — a capability exclusive to pgvector sitting inside a relational database. Qdrant, Milvus, Weaviate, Pinecone, and Turbopuffer all lack native SQL joins, so filter query type A requires either a second service or shipping all candidate IDs back to application code. At 500k vectors and a team of 10-100 non-technical users at low QPS, pgvector on Neon eliminates an entire service from the ops surface with no real performance penalty. The leaning in the brief is correct.

## ALTERNATIVES

### pgvector + Neon (recommended) -> **USE**
- PRO: Single service for relational + vector. SQL WHERE + ORDER BY combined with iterative scans (0.8.0) handles filter/aggregate queries natively. halfvec(1536) fits within 4,000-dim cap with 50% storage savings and 23% faster index build. 500k vectors fit comfortably in RAM. No separate service to operate. Neon's pgvector 0.8.0 is confirmed supported.
- CON: Cold start after 5-min idle adds 500ms-2s to first query; HNSW buffer cache evicted on suspend means first ANN query after wake reads from distributed storage. At 5-10M vectors HNSW must fit in RAM — ceiling exists but is well above Phase 2 scope (500k chunks).

### pgvectorscale (StreamingDiskANN) on Neon -> **PHASE-2**
- PRO: 9x smaller index on disk vs HNSW. Extends viable scale to hundreds of millions of vectors. Handles 16,000 dims. DiskANN's streaming traversal applies filters during graph walk, not after — better filtered recall than HNSW. 28x lower p95 latency vs Pinecone at 50M vectors.
- CON: Not available on Neon as a managed extension — requires self-hosted Postgres or Timescale Cloud. Adds operational complexity. Unnecessary until 5-10M vectors.

### Qdrant -> **REJECT**
- PRO: Best tail latency in class: 39% better p95 and 48% better p99 than pgvector at 99% recall on 50M x 768d. Payload-indexed HNSW applies filters during graph traversal (no post-filter drop). 3.3h vs 11.1h build time at 50M vectors.
- CON: No SQL joins — filter type A queries require application-side join logic. Adds a separate service. pgvector beats Qdrant 11x on throughput (QPS). At this project's scale (10 users, 500k vectors), tail latency difference is irrelevant.

### Pinecone -> **REJECT**
- PRO: Serverless, zero ops, fast onboarding.
- CON: No SQL joins. At 100M vectors, $5,000-6,000/month vs $1,500 self-hosted Postgres. pgvector benchmark showed 28x lower latency at same recall. Filter type A unsolvable without application round-trips.

### Turbopuffer -> **REJECT**
- PRO: Object-storage backed at $0.02/GB (vs $2+/GB in-memory). Sub-10ms p50 on warm namespaces. Trusted by Cursor, Notion, Linear in production. True hybrid BM25 + vector search.
- CON: Cold-start problem on object storage — warm namespace requirement. No relational model; filter logic lives in application code. Single-tenant property table joins are clunky. Adds a service boundary.

### LanceDB -> **REJECT**
- PRO: Embedded-first, open source, object-storage backed, very low cost. Good for local dev.
- CON: Embedded architecture not production-ready for concurrent multi-user server workloads. No managed cloud offering with SLA at this stack's tier.

### Milvus / Weaviate -> **REJECT**
- PRO: Purpose-built scale to billions. Weaviate has native hybrid BM25+vector. Milvus handles multi-tenant well.
- CON: Significant operational complexity — Milvus requires etcd, MinIO, Kafka coordination. Weaviate schema model and SDK churn add cognitive overhead. Neither offers a benefit over pgvector at 500k vectors for a 10-person internal tool.

### pgvector + Postgres full-text search hybrid (RRF) -> **USE**
- PRO: Combines tsvector FTS with vector cosine scores using Reciprocal Rank Fusion. Zero additional infra. Catches keyword matches (specific property names, gate names, railhead names) that pure semantic search misses.
- CON: Not an alternative to vector search — a complement.

## KEY FINDINGS
- pgvector dimension hard limits: vector(float32) caps at 2,000 dims for HNSW/IVFFlat; halfvec(float16) caps at 4,000 dims; bit type caps at 64,000 dims. Gemini embedding-2 at 1536 dims fits all three. Use halfvec(1536).
- HNSW build memory formula: N × D × 4 bytes × 2 (graph overhead). For 500k × 1536 float32: ~6.1 GB. With halfvec: ~3.1 GB. Set maintenance_work_mem = 4GB or the build degrades 10-50x to disk I/O.
- halfvec(1536) vs vector(1536) on 1M DBpedia dataset: 50% storage reduction (3,076 vs 6,148 bytes/vector), 23% faster index build, 50% faster pre-warming after cold start, equivalent recall. This is a mandatory switch for Neon.
- Binary quantization at 1536 dims: without reranking recall drops to 60-69% (production failure). With reranking against full halfvec: 91-99.8% recall and 16x storage reduction. Only viable as a two-stage approach.
- pgvector 0.8.0 (released Oct 2024) is confirmed supported on Neon. Critical feature for this project: iterative index scans (hnsw.iterative_scan = relaxed_order/strict_order) prevent filter over-removal and enable filter-aggregate type A queries without sequential scans.
- pgvector stops being adequate above 5-10M vectors where HNSW must fit entirely in RAM (~150 GB at 50M×768d). Phase 2 scope (500k chunks) is well within HNSW's comfort zone on a 4-8 GB Neon compute instance.
- Neon cold start: 500ms-2s wake time after 5-min idle default. HNSW index buffer cache is evicted on suspend — first ANN query after resume reads from Neon distributed storage, adding latency spike. A 4-minute keep-alive ping prevents suspend during working hours.
- Matryoshka truncation: at 512 dims retains 94-98% of nDCG@10 vs full 1536. However, Gemini text-embedding-004 / embedding-2 is NOT confirmed Matryoshka-trained. Truncating Gemini embeddings without MRL training can lose significant recall. Do not truncate unless Gemini explicitly supports it.
- Qdrant vs pgvector on throughput: pgvector 471 QPS vs Qdrant 41 QPS at 99% recall on 50M×768d identical hardware. For this project's workload (10 users, low QPS), this is irrelevant — but it confirms pgvector is not a throughput bottleneck.
- IVFFlat vs HNSW for this project: HNSW is correct. IVFFlat builds 5-6x faster but requires retraining list centroids when data volume changes significantly. HNSW handles incremental inserts gracefully and delivers ~1.5ms vs ~2.4ms query latency at equivalent recall.

## PITFALLS
- Do NOT use vector(1536) — it hits pgvector's 2,000-dim HNSW indexing cap with no room to spare and wastes 2x storage vs halfvec(1536). Switch to halfvec(1536) from day one.
- Neon's default compute suspend at 5 minutes will evict the HNSW buffer cache. For an internal tool used sporadically, the first query of a session will be slow. Add a scheduled keep-alive query or increase auto-suspend to 30 minutes.
- Binary quantization alone at 1536 dims gives only 60-69% recall — a catastrophic failure mode for a sales tool where hallucinating a driving distance destroys trust. Only deploy BQ with a mandatory reranking pass against the full halfvec.
- Filter-aggregate queries (type A: 'which properties have < 20 rooms') will silently return wrong answers with naive top-k vector search. pgvector 0.8 iterative scans require explicit configuration: SET hnsw.iterative_scan = 'relaxed_order' and SET hnsw.max_scan_tuples = 20000 per session or in the connection pool setup.
- HNSW index build on Neon without adequate maintenance_work_mem falls back to disk-based build at 10-50x slower. Set SET maintenance_work_mem = '4GB' in the migration session, not globally (it affects all connections if set globally in postgresql.conf).
- Gemini text-embedding-002/004 is not documented as Matryoshka-trained. Do not truncate embedding dimensions to save storage — use halfvec(1536) instead, which is safe and supported.
- pgvectorscale (StreamingDiskANN Timescale extension) is not available on Neon. If scale exceeds 5M vectors in Phase 2, the migration path is to Timescale Cloud or self-hosted Postgres — plan for this in data model design but do not implement now.
- IVFFlat at this scale requires VACUUM ANALYZE and list retraining as data grows — HNSW does not. Do not use IVFFlat unless build time on initial load is the binding constraint.

## IMPLEMENTATION NOTES
- Schema: CREATE TABLE property_chunks (id bigserial PRIMARY KEY, property_id int REFERENCES properties(id), chunk_text text, embedding halfvec(1536), chunk_type text, source_file text); — keep structured property fields (room_count, price_min_inr, has_pool, nearest_airport_km, etc.) in the properties table for SQL filtering.
- HNSW index: CREATE INDEX ON property_chunks USING hnsw (embedding halfvec_cosine_ops) WITH (m = 16, ef_construction = 64); — run with SET maintenance_work_mem = '4GB' before the CREATE INDEX statement.
- Query pattern for type A (filter-aggregate): SELECT p.name, pc.chunk_text, pc.embedding <=> $1 AS distance FROM property_chunks pc JOIN properties p ON pc.property_id = p.id WHERE p.room_count < 20 AND p.price_min_inr < 15000 SET LOCAL hnsw.iterative_scan = 'relaxed_order'; SET LOCAL hnsw.ef_search = 100; ORDER BY distance LIMIT 20;
- Full-text search hybrid (RRF): add a tsvector column (ts_chunk tsvector GENERATED ALWAYS AS (to_tsvector('english', chunk_text)) STORED) with GIN index. Combine with vector search using Reciprocal Rank Fusion in application code or a SQL CTE.
- Neon compute sizing: minimum 0.5 CU (2 GB RAM) for query serving; set autoscaling max to 4 CU (16 GB RAM) during index builds. At 500k × halfvec(1536), the working index in shared_buffers is ~3 GB — a 4 CU instance (16 GB RAM) handles this comfortably.
- Keep-alive: add a cron job (or Vercel cron) every 4 minutes that runs SELECT 1 against Neon during business hours (e.g., 8am-8pm IST) to prevent compute suspend during active use.
- pgvector version: confirm with SELECT extversion FROM pg_extension WHERE extname = 'vector'; — must be 0.8.0 for iterative scan support. On Neon, enable with CREATE EXTENSION IF NOT EXISTS vector;
- For Phase 2 scale (500k chunks target): 500,000 × halfvec(1536) = ~1.5 GB raw vector data, HNSW index ~3 GB in RAM — still fits a 4 CU Neon instance. pgvectorscale migration becomes relevant only above ~5M chunks.

## SOURCES
- https://www.dbi-services.com/blog/pgvector-a-guide-for-dba-part-2-indexes-update-march-2026/
- https://github.com/pgvector/pgvector/issues/769
- https://neon.com/blog/dont-use-vector-use-halvec-instead-and-save-50-of-your-storage-cost
- https://neon.com/docs/extensions/pgvector
- https://neon.com/blog/1-year-of-autoscaling-postgres-at-neon
- https://www.cloudthinker.io/blogs/neon-postgres-performance-guide
- https://www.tigerdata.com/blog/pgvector-vs-qdrant
- https://jkatz05.com/post/postgres/pgvector-scalar-binary-quantization/
- https://www.postgresql.org/about/news/pgvector-080-released-2952/
- https://dev.to/philip_mcclarence_2ef9475/ivfflat-vs-hnsw-in-pgvector-which-index-should-you-use-305p
- https://www.softwareseni.com/pgvector-pgvectorscale-and-the-postgres-vector-search-stack-explained/
- https://weaviate.io/blog/openais-matryoshka-embeddings-in-weaviate
- https://www.tigerdata.com/blog/pgvector-is-now-as-fast-as-pinecone-at-75-less-cost
- https://clawbot.ai/wiki/apis/turbopuffer-serverless-vector-database.html
- https://zilliz.com/comparison/lancedb-vs-turbopuffer