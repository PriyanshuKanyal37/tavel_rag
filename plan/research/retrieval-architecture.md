# retrieval-architecture

## HEADLINE
The correct architecture is a dual-table Postgres design (structured metadata + vector chunks) with LLM tool-calling query routing - not pure vector search - because filter/aggregate queries need full-corpus SQL scans that vector search physically cannot provide.

## RECOMMENDATION
Implement a three-layer retrieval stack in Neon Postgres: (1) a typed `properties` table with every structured field as a native column (room_count INTEGER, price_min_inr INTEGER, nearest_airport_km INTEGER, has_pool BOOLEAN, state TEXT, etc.) populated by the extraction pipeline; (2) a `property_chunks` table with pgvector embeddings (halfvec 1536) and a tsvector column for BM25-grade full-text search via the pg_textsearch or ParadeDB extension; (3) Claude tool-calling as the query router - the LLM classifies intent and emits one of three typed tool calls: filter_properties({room_count_lt: 20}) -> parameterized SQL scan over all 49 rows, semantic_search({query, optional_filters}) -> hybrid RRF over chunk table, or describe_property({name}) -> full card fetch. Add Cohere Rerank 3.5 or BGE-reranker-v2-m3 as a second-stage reranker over the top-20 semantic candidates, dropping to top-5 for the LLM. Apply Anthropic Contextual Retrieval at ingestion time: generate a 100-token situating paragraph per chunk using claude-haiku-3-5 with prompt caching at ~$1.02/million tokens one-time cost.

## WHY
Travel Inn has exactly two query modes that are architecturally incompatible if you use a single retrieval path. "Fewer than 20 rooms" is a full-table scan predicate - vector top-k by definition returns a subset of the corpus (typically 5-20 documents) and cannot guarantee it saw the correct answer. The only correct mechanism is SQL WHERE room_count < 20 executed over all 49 rows. "Somewhere quiet for a couple" is a semantic query with no structured predicate, where SQL fails and vectors excel. The tool-calling router is the only design that routes each query to the correct engine without forcing users to phrase queries differently. Text-to-SQL (option a) fails in production because 60% of hallucinated answers trace to malformed SQL or hallucinated column names; typed tool parameters compile to parameterized queries with no injection risk. Full-corpus-in-context (option d) is technically feasible at v1 (49 properties at ~2-4KB each = ~100K tokens, within Claude's 200K window) but costs ~$2/query vs ~$0.00008 for RAG, and becomes impossible at Phase 2 scale (500 properties). The hybrid BM25+vector path with RRF handles the majority of "smart filter + semantic" queries like "luxury tented camps in Rajasthan under Rs 25,000" where both lexical match and semantic similarity contribute. pgvector's native tsvector (ts_rank) is corpus-blind - it does not compute IDF across the 49-property corpus, which matters for rare property terms; ParadeDB or pg_textsearch v1.3.0 provides true corpus-aware BM25 in-process.

## ALTERNATIVES

### Pure vector search (current implicit assumption) -> **REJECT**
- PRO: Simple, one table, no routing complexity
- CON: Physically cannot answer filter/aggregate queries - returns top-k subset, not all matching rows. The project brief already identifies this failure. Confirmed by all 2025-2026 benchmarks.

### Text-to-SQL (LLM generates raw SQL strings) -> **REJECT**
- PRO: Flexible, no schema upfront, handles ad-hoc aggregations
- CON: 60% of hallucinated answers in agentic RAG systems trace to silent SQL errors or hallucinated column names. Schema leakage in prompt. No injection safety without extra middleware. Harder to test and observe.

### Tool/function calling with typed filter parameters (recommended) -> **USE**
- PRO: LLM emits structured JSON, compiled to parameterized SQL, no injection risk, predictable schema, easy to log and test, handles both pure-filter and hybrid queries
- CON: Filter schema must be designed upfront and kept in sync with extraction pipeline. New structured fields require schema migration.

### Metadata pre-filter then vector search only -> **CONSIDER**
- PRO: Handles 'lodges in Rajasthan with a pool' pattern, supported natively in pgvector
- CON: Still fails pure aggregation ('which have fewer than 20 rooms' when ALL 49 must be checked). Pre-filtering is a subset of tool-calling, not a replacement. Returns wrong results when filtered set is empty.

### Full corpus in context (1M window) -> **REJECT**
- PRO: Zero retrieval engineering, eliminates lost-in-retrieval failures, Anthropic recommends it below 200K tokens. 49 properties at 2-4KB each fits inside Claude's context.
- CON: ~$2+ per query vs $0.00008 for RAG (1250x cost). 45-60s latency at 1M tokens vs ~1s for RAG. Impossible at Phase 2 (500 properties = 1M+ tokens). 30%+ accuracy degradation for content in middle of long contexts.

### Anthropic Contextual Retrieval (contextual embeddings + contextual BM25) -> **PHASE-2**
- PRO: 49% retrieval failure reduction, 67% with reranking. One-time ingestion cost $1.02/million tokens. Works with existing pgvector + BM25 setup.
- CON: Anthropic explicitly states it is only worth implementing above ~200K tokens. Travel Inn v1 (49 properties) sits right at this threshold. Adds ingestion pipeline complexity.

### ColBERT / late interaction models -> **PHASE-2**
- PRO: 100x faster than cross-encoders at high QPS, near cross-encoder quality, precomputed doc embeddings
- CON: Overkill at 10-100 users. Requires separate infrastructure (RAGatouille). Cross-encoder reranker over top-20 is cheaper and simpler at this scale.

### Late chunking (Jina AI approach) -> **REJECT**
- PRO: Preserves cross-boundary semantic context in long narrative documents
- CON: Property cards are short, self-contained one-pagers (~2-4KB). Late chunking benefits documents where meaning crosses chunk boundaries. Not this use case. Requires jina-embeddings-v3 specifically.

### GraphRAG -> **REJECT**
- PRO: Good for cross-document synthesis queries (which properties are near each other, relationship chains)
- CON: High implementation complexity, high token consumption, extraction quality issues documented in 2025. Overkill for 49 properties.

## KEY FINDINGS
- RRF (Reciprocal Rank Fusion) with k=60 is the 2025-2026 standard for fusing BM25 + vector results. It operates on rank position, not score scale, eliminating calibration problems between heterogeneous retrievers. Measured 7.4% NDCG lift on WANDS e-commerce benchmark over either retriever alone.
- pgvector's native ts_rank does NOT compute IDF (inverse document frequency) - it evaluates documents in isolation, unable to distinguish rare vs common terms across the 49-property corpus. ParadeDB (open source, pg extension) or pg_textsearch v1.3.0 (reached production-ready mid-2026) provide true corpus-aware BM25 inside Postgres.
- Anthropic Contextual Retrieval achieves 49% retrieval failure reduction (5.7% to 2.9%) with contextual embeddings + contextual BM25 combined, and 67% reduction (5.7% to 1.9%) when also applying reranking. One-time ingestion cost is $1.02 per million document tokens using prompt caching with claude-haiku. However, Anthropic explicitly states this is only worth it for corpora exceeding approximately 200K tokens.
- Cross-encoder reranking (Cohere Rerank 3.5, BGE-reranker-v2-m3, or ms-marco-MiniLM-L6-v2) adds 50-200ms latency over a candidate pool of 20-50 docs, and consistently yields 5-15 NDCG@10 improvement. At 500 chunks, retrieving top-20 with hybrid then reranking to top-5 is the right pattern. MiniLM-class processes 1800 docs/second; this is cheap at 500 chunks.
- Full-corpus-in-context costs approximately $2+ per query at 1M tokens vs $0.00008 for RAG - a 1250x cost difference. Average recall on realistic multi-fact retrieval hovers around 60% for long-context (not 99.7% cited in needle-in-haystack benchmarks), with 30%+ accuracy degradation for content in the middle of very long contexts.
- Tool-calling query routing is the production-proven pattern for dual query modes. The LLM classifies intent and emits typed JSON that compiles to parameterized SQL - no SQL injection risk, no schema leakage, easy to log. 60% of hallucinated answers in agentic RAG systems trace to unhandled SQL errors when using raw text-to-SQL.
- Late chunking (Jina AI) benefits long narrative documents where meaning crosses chunk boundaries. Property fact sheets are discrete, self-contained units under 4KB - late chunking adds complexity with no benefit here.
- ColBERT v2 (via RAGatouille Python package) is two orders of magnitude faster than cross-encoders at scale but requires separate infrastructure. Not justified at 10-100 concurrent users; revisit at Phase 2 when QPS demands it.

## PITFALLS
- The critical missing piece in the current leaning is a structured metadata table. Without a typed Postgres table where each property is a row with INTEGER/BOOLEAN/TEXT columns, filter/aggregate queries ('fewer than 20 rooms', 'under Rs 15,000') cannot be answered correctly regardless of retrieval sophistication.
- Using ts_rank instead of true BM25: Postgres native full-text search does not compute global corpus statistics (IDF). For a 49-property corpus where some terms (e.g., 'wildlife', 'heritage') appear in many docs, ts_rank cannot down-weight them. Install ParadeDB or pg_textsearch for corpus-aware BM25.
- Vector search top-k is bounded. If you set top_k=10 and ask 'which properties have fewer than 20 rooms', you will get answers from 10 of 49 properties even if 30 of them qualify. The model will answer confidently wrong. This is the failure mode the brief correctly anticipates.
- The extraction pipeline must produce structured JSON with typed fields to populate the metadata table. If gemini/claude extraction outputs free-text descriptions, the structured table is empty and filter queries fail. Design the extraction schema first, validated against actual property cards.
- Score thresholds for grounded refusal cannot be set once and left. Reranker scores are not calibrated absolute relevance measures - a 0.7 from Cohere Rerank means something different from a 0.7 from BGE. Use top-N cutoff (pass top-3 chunks) plus a judge-LLM faithfulness check rather than a score floor.
- Contextual Retrieval adds ingestion latency (one LLM call per chunk). At 52 source files, this is a one-time batch job, not a real-time concern. But the contextualization prompt must reference the FULL property card, not just adjacent chunks - a common implementation error.
- The RRF constant k=60 is a sensible default but not a magic number. For a corpus this small (49 properties), a weighted variant (0.7 * semantic + 0.3 * BM25) may outperform plain RRF because semantic signal dominates for description queries. Measure on a held-out eval set.

## IMPLEMENTATION NOTES
- Schema: CREATE TABLE properties (id UUID PK, name TEXT, state TEXT, room_count INTEGER, price_min_inr INTEGER, price_max_inr INTEGER, nearest_airport_km INTEGER, nearest_airport_name TEXT, nearest_railhead_km INTEGER, closest_safari_gate_km INTEGER, closest_safari_gate_min INTEGER, has_pool BOOLEAN, meal_plan_code TEXT, best_time TEXT, inspection_confirmed BOOLEAN, source_file TEXT, extracted_at TIMESTAMPTZ). This is what makes filter queries possible.
- Schema: CREATE TABLE property_chunks (id UUID PK, property_id UUID FK REFERENCES properties, chunk_text TEXT, context_prefix TEXT, embedding halfvec(1536), fts_vector tsvector, chunk_index INTEGER, source_file TEXT). The context_prefix stores the 100-token Contextual Retrieval prefix. The fts_vector column is updated via trigger: BEFORE INSERT OR UPDATE SET fts_vector = to_tsvector('english', context_prefix || ' ' || chunk_text).
- Hybrid search query in Postgres (pure SQL, no ORM magic needed): CTE fulltext AS (SELECT id, ROW_NUMBER() OVER (ORDER BY ts_rank(fts_vector, query) DESC) r FROM property_chunks, plainto_tsquery('english', $1) query WHERE fts_vector @@ query LIMIT 40), CTE semantic AS (SELECT id, ROW_NUMBER() OVER (ORDER BY embedding <=> $2::halfvec) r FROM property_chunks LIMIT 40), then RRF: SELECT id, SUM(1.0/(60+r)) score FROM (SELECT id, r FROM fulltext UNION ALL SELECT id, r FROM semantic) GROUP BY id ORDER BY score DESC LIMIT 20. For true BM25 IDF, replace ts_rank with ParadeDB's pdb.score().
- Query router tool definitions for Claude: tool 1 filter_properties with parameters room_count_lt (optional int), room_count_gt (optional int), price_max_inr (optional int), has_pool (optional bool), state (optional string), inspection_confirmed (optional bool) - these map directly to typed SQL WHERE clauses; tool 2 semantic_search with parameters query (string), state_filter (optional string), limit (int default 5); tool 3 describe_property with parameters name (string). The system prompt must include the full properties table column list and example values so the LLM knows what is filterable.
- Reranking: after semantic_search returns top-20 chunks, pass them to BGE-reranker-v2-m3 (self-hosted, 568M params) or Cohere Rerank 3.5 API. Rerank to top-5 before feeding to claude-sonnet. For filter_properties results, no reranking needed - results are SQL-exact. Typical overhead: 80-200ms for BGE on CPU, 50-80ms on GPU, ~150ms for Cohere API call.
- Contextual Retrieval ingestion: for each chunk, call claude-haiku-3-5 with prompt 'Here is the full property card: <full_card>. Here is a chunk from it: <chunk>. Give a 2-3 sentence context situating this chunk within the property card for retrieval purposes.' Use prompt caching on the full card (cache_control: ephemeral on the document block). Cost at 800-token chunks, 49 properties, ~5 chunks each = ~245 chunks; negligible one-time cost.
- Grounded refusal: after retrieving top-5 chunks, add a judge step in the system prompt: 'If the retrieved context does not contain enough information to answer confidently, respond with: I cannot find that information in Travel Inn's property data. The source I checked was [file]. Do not estimate or infer.' This is a prompt constraint, not a separate model call.
- Halfvec storage: halfvec(1536) in Neon Postgres stores each dimension as float16 (2 bytes) vs float32 (4 bytes), halving storage. At 245 chunks x 1536 dims = 375K floats = 750KB in halfvec vs 1.5MB in vector. Negligible at v1 scale but good practice for Phase 2. HNSW index: CREATE INDEX ON property_chunks USING hnsw (embedding halfvec_cosine_ops) WITH (m=16, ef_construction=64). At Phase 2 (500k chunks), bump ef_construction to 128.
- Phase 2 readiness: the dual-table design scales directly. Add more rows to properties table, more chunks to property_chunks. Switch from BGE self-hosted to ColBERT v2 via RAGatouille when QPS exceeds ~50 concurrent users. Add Contextual Retrieval (justified above 200K tokens, which Phase 2 will easily exceed). Partitioning property_chunks by state reduces scan cost for state-filtered semantic searches.

## SOURCES
- https://www.anthropic.com/engineering/contextual-retrieval
- https://www.paradedb.com/blog/hybrid-search-in-postgresql-the-missing-manual
- https://redis.io/blog/top-reranking-models-rag-accuracy/
- https://tianpan.co/blog/2026-04-09-long-context-vs-rag-production-decision-framework
- https://denser.ai/blog/hybrid-search-for-rag/
- https://towardsdatascience.com/building-cost-efficient-agentic-rag-on-long-text-documents-in-sql-tables/
- https://ragflow.io/blog/rag-review-2025-from-rag-to-context
- https://medium.com/data-science-collective/hybrid-search-for-rag-bm25-vectors-when-each-wins-402f24abaeea
- https://arxiv.org/html/2604.01733v1
- https://futureagi.com/blog/agentic-rag-systems-2025/
- https://jina.ai/news/late-chunking-in-long-context-embedding-models/
- https://medium.com/kx-systems/late-chunking-vs-contextual-retrieval-the-math-behind-rags-context-problem-d5a26b9bbd38
- https://dev.to/gabrielanhaia/hybrid-search-in-100-lines-bm25-pgvector-with-rrf-merge-58cn
- https://bigdataboutique.com/blog/rag-reranking-improving-retrieval-quality-with-cross-encoders
- https://medium.com/coinmonks/contextual-retrieval-anthropics-method-for-cutting-rag-failures-b28d98d57c48