# Chunking and Indexing Strategy

## HEADLINE
Section-aware chunking (one chunk per named section) combined with pre-extracted boolean/numeric SQL columns is the right architecture — vector search alone is structurally incapable of answering the filter/aggregate query type, and no chunking trick fixes that.

## RECOMMENDATION
Use a three-tier index: (1) Postgres SQL columns for every filterable fact extracted at ingest — room_count, has_pool, price_min_inr, nearest_airport_km, state, staff_inspected; (2) section-level halfvec(1536) embeddings, one chunk per named section per property, with a deterministic header prefix prepended to every chunk before embedding; (3) full property text stored as parent, returned to the LLM after retrieval. Route query type A entirely through SQL. Route query type B through hybrid BM25 + vector on the section chunks with metadata pre-filter. Never route amenity/feature presence queries through vector search alone.

## WHY
The 52-document corpus has two structurally incompatible query types. Filter/aggregate queries — "fewer than 20 rooms", "has a pool", "under Rs 15,000" — are logically impossible for any vector search strategy to answer correctly at 49 properties because top-k retrieval returns a subset and the model confidently hallucinates the rest of the population (confirmed by SRAG paper, March 2026, arxiv 2603.26670). That is a routing problem, not a chunking problem. On the semantic side, each brochure is 600-900 words (~450-675 tokens), well inside gemini-embedding-2's context window, so whole-doc embedding is technically feasible, but embedding the whole doc means a query about dining options retrieves the whole property and the LLM must read 11 sections to find the answer — section-level chunks make the retrieval signal more precise. The Snowflake Finance RAG study (2026) found section-aware chunking beats naive fixed splits by 5-10 points, and the advantage disappears only when global metadata is already appended — which our header prefix provides for free. The FloTorch 2026 benchmark placed recursive 512-token splitting at 69% accuracy with section-aware above it for structured documents, while semantic chunking dropped to 54% by producing 43-token fragments. Each named section in these brochures is a natural, complete semantic unit; forcing token-count splits across section boundaries is strictly worse.

## ALTERNATIVES

### One document = one chunk (whole-doc embedding) -> **REJECT**
- PRO: Simplest. 49 vectors. No section detection needed. Works if queries are always property-level. Whole doc fits in gemini-embedding-2 context window at 450-675 tokens.
- CON: Loses section-level retrieval precision. Query 'what dining options does X have?' retrieves the whole doc and forces the LLM to extract from noise. Scales poorly: at Phase 2 (500 properties) retrieval degrades without section anchors. Cannot answer cross-property filter queries regardless.

### Fixed-size recursive character splitting (512 tokens, 50-100 overlap) -> **REJECT**
- PRO: Benchmark winner in FloTorch 2026 at 69% accuracy on mixed corpora. Simple to implement with LangChain RecursiveCharacterTextSplitter.from_tiktoken_encoder(). LangChain gotcha: use tiktoken encoder, not character count, or 512 chars maps to ~128 tokens.
- CON: At 600-900 word docs, chunks fall mid-section and destroy section coherence. The corpus has explicit named section boundaries that are strictly better split points than token counts. Produces orphaned fragments like half of an AMENITIES list.

### Section-aware chunking (one chunk per named section) -> **USE**
- PRO: Respects document structure. 11 sections x 49 properties = ~539 chunks — trivially small, HNSW index instantaneous. Section heading prepended as prefix (free, no LLM call per chunk). Section-to-section retrieval enables 'what are the dining options at X' to return only the DINING chunk. Parent document returned for LLM context after retrieval.
- CON: Requires section detection during ingest (regex or LLM-based). Section sizes vary: QUICK FACTS may be 30 words, INTRODUCTION 150 words — embedding quality is uneven for very short sections. Must be implemented per-template (4 different templates in corpus).

### Parent-document retrieval (small sentence-window children, section parents) -> **REJECT**
- PRO: Best precision-recall tradeoff in theory: tiny child chunks nail the retrieval signal, parent section provides LLM context. H-RAG at SemEval-2026 showed meaningful improvement for multi-turn conversations.
- CON: Overkill at 539 section chunks. Sentence-level children (~15-20 tokens each) hit the 43-token fragment problem documented in FloTorch — LLM context is too sparse to answer. The section IS the right parent already; adding another tier is complexity with no gain at this corpus size.

### RAPTOR hierarchical summarization -> **REJECT**
- PRO: Handles multi-hop cross-document queries well. GPT-4 + RAPTOR improved QuALITY benchmark by 20 points absolute. Useful when thematic clusters must be surfaced ('which properties in Madhya Pradesh are best for tigers?').
- CON: Designed for large corpora needing semantic clustering across hundreds to thousands of documents. At 49 properties, clustering adds cost (Claude/Gemini calls per cluster), latency at ingest, and complexity with no measurable retrieval gain over direct section search. The cross-property queries in this system are filter queries answered by SQL anyway.

### Semantic chunking (split on embedding similarity breakpoints) -> **REJECT**
- PRO: Adapts chunk size to content rather than forcing token counts.
- CON: FloTorch 2026 benchmark: 54% end-to-end accuracy vs 69% for recursive. Produces 43-token fragments that have too little context for correct answer generation. Ignores explicit section headers that are strictly better boundary signals. Do not use.

## KEY FINDINGS
- Each brochure is 600-900 words (~450-675 tokens), well under gemini-embedding-2's context limit — chunking is optional for embedding capacity, but still valuable for retrieval precision at section granularity.
- FloTorch 2026 benchmark (50 documents): recursive 512-token splitting 69% accuracy, semantic chunking 54% accuracy. Semantic chunking failed because its chunks averaged 43 tokens — too sparse for LLM context generation.
- Vectara NAACL 2025 study: chunking configuration has as much impact on retrieval quality as the choice of embedding model itself. Wrong chunking opens a 9% recall gap (Weaviate 2025 benchmark).
- SRAG (arxiv 2603.26670, March 2026): filter/aggregate queries structurally cannot be answered by vector similarity. The fix is pre-extracted structured metadata as SQL columns, not better chunking or larger k.
- The negation problem ('no swimming pool') is not solvable by vector search. Dense embeddings of 'no swimming pool' are high-similarity to 'swimming pool' — they share the same semantic space. The ONLY reliable fix is a boolean SQL column has_pool extracted at ingest, and routing amenity presence queries through SQL WHERE, not vector search.
- Anthropic Contextual Retrieval (Sept 2024): prepending a 50-100 token LLM-generated context per chunk before embedding reduced retrieval failures by 49-67% on hybrid BM25+vector setups. For this corpus, a deterministic heading prefix ('Property: X | State: Y | Section: AMENITIES') achieves the same effect for free — no LLM call per chunk.
- Snowflake Finance RAG 2026: section-aware chunking beats fixed splits by 5-10 points; the gap shrinks when global metadata is appended to chunks — meaning the header prefix approach captures most of the structural benefit without a separate chunking algorithm.
- Phase 2 at 500 properties: 11 sections x 500 = 5,500 chunks. HNSW index on halfvec(1536) in pgvector handles this trivially. The schema chosen for v1 needs no redesign for Phase 2.

## PITFALLS
- LangChain RecursiveCharacterTextSplitter default chunk_size=512 is in CHARACTERS not tokens. At ~4 chars/token, 512 chars produces ~128 actual tokens. Always use RecursiveCharacterTextSplitter.from_tiktoken_encoder() with model='cl100k_base' or equivalent.
- Routing all queries through vector search — including 'which properties have fewer than 20 rooms' — is the single highest-risk failure mode. The model will answer confidently from the top-5 retrieved docs and hallucinate the rest of the 49-property population. This destroys sales team trust permanently (as the requirements state). Query type detection and SQL routing for filter/aggregate is non-negotiable.
- Extracting has_pool=true from a document that says 'No swimming pool' during ingest. The LLM extraction prompt must explicitly handle negation. Test case: a document saying 'unlike many jungle lodges, we do not offer a swimming pool' must yield has_pool=false. Add explicit system prompt instruction: 'If a feature is mentioned only in negation (does not have, no X, unlike properties that offer X), set the boolean to false.'
- Embedding section chunks without the property name in the chunk text. If AMENITIES chunk for 'Bandhavgarh Jungle Lodge' contains only the amenities list with no property identifier, a query 'what amenities does Bandhavgarh have?' may retrieve the right chunk but the LLM cannot confirm provenance. Always prefix: 'Property: [name] | State: [state] | Section: [SECTION_NAME]'.
- Relying on vector similarity to distinguish 'properties near Ranthambore' from 'properties near Bandhavgarh'. Geographic proximity is a numeric problem (nearest_airport_km column), not a semantic one. Airport distance queries must go through SQL range filters, not vector search.
- The four different templates across the corpus (current image, older 2024 image, one variant, PDF) mean section detection cannot use a single regex. Each template needs its own extraction path. Treating all 52 files identically at ingest will produce garbled sections from templates whose heading format differs.

## IMPLEMENTATION NOTES
- Schema: two tables. `properties` (one row per property): id, name, state, city, nearest_airport_km INT, nearest_airport_name TEXT, nearest_railhead TEXT, safari_gate_minutes INT, room_count INT, price_min_inr INT, meal_plan TEXT, has_pool BOOL, has_wifi BOOL, staff_inspected BOOL, best_time_to_visit TEXT, source_file TEXT, full_text TEXT, full_embedding halfvec(1536). `property_sections` (one row per section per property): id, property_id UUID FK, section_name TEXT, section_text TEXT, chunk_text TEXT, embedding halfvec(1536).
- chunk_text construction before embedding: f'Property: {name} | State: {state} | Section: {section_name}\n\n{section_text}'. This is the deterministic contextual header. Embed chunk_text, store both chunk_text and raw section_text (for display without the header).
- Negation-safe ingest prompt for boolean extraction: 'Extract the following fields. For boolean fields: set TRUE only if the feature is explicitly confirmed present. Set FALSE if mentioned only in negation, absence, or not mentioned at all. Fields: has_pool, has_wifi, has_restaurant, has_bonfire, has_naturalist_guide...'. Store NULL only when the source document is silent and does not mention the feature at all, to distinguish unknown from confirmed-absent.
- Query routing: classify each incoming query before retrieval. Signal words for SQL routing: 'how many', 'which properties', 'fewer than', 'more than', 'closest', 'cheapest', 'under Rs', 'above Rs', 'all properties', 'list all', 'which have', 'which don't have'. Use a cheap claude-haiku-3 classify call or a regex pass before hitting pgvector.
- Hybrid search SQL pattern (pgvector + pg_trgm or ParadeDB pg_search for BM25): run two CTEs — fulltext rank via ts_rank on a tsvector column, vector rank via <=> cosine distance on embedding — fuse with RRF: score = 1.0/(60 + bm25_rank) + 1.0/(60 + vector_rank). Pre-filter both CTEs with WHERE property_id IN (SELECT id FROM properties WHERE state = 'Madhya Pradesh') when state is detected in query.
- HNSW index: CREATE INDEX ON property_sections USING hnsw (embedding halfvec_cosine_ops) WITH (m=16, ef_construction=64). At 539 chunks this is instantaneous; same index parameters work at 5,500 chunks for Phase 2.
- Source citation: every section chunk row carries property_id and source_file (R2 key). When the LLM answer is assembled, include the property name and source_file URL. The grounded-refusal rule: if no chunk with similarity > threshold (e.g., 0.75 cosine) is returned, the system returns 'I don't have that information for the properties in our database' rather than generating an answer.
- Ingest pipeline per template type: PDF — use pdfplumber with layout=True to extract text blocks, then regex-match known section headings. Images (PNG/JPEG) — use Gemini Vision (gemini-2.5-pro) to extract structured JSON per section, not raw text, because z-order extraction fails on multi-column layouts. Store extracted JSON before converting to section chunks.

## SOURCES
- https://www.premai.io/blog/rag-chunking-strategies-the-2026-benchmark-guide
- https://arxiv.org/pdf/2603.26670
- https://arxiv.org/pdf/2603.25333
- https://www.snowflake.com/en/engineering-blog/impact-retrieval-chunking-finance-rag/
- https://www.anthropic.com/engineering/contextual-retrieval
- https://dev.to/kartikeyraj/free-contextual-chunk-headers-heading-aware-chunking-for-hybrid-retrieval-560
- https://medium.com/data-science-collective/the-retrieval-mistake-most-rag-teams-havent-understood-8b864c034ee7
- https://www.paradedb.com/blog/hybrid-search-in-postgresql-the-missing-manual
- https://arxiv.org/pdf/2605.00631
- https://www.digitalapplied.com/blog/rag-chunking-strategies-2026-retrieval-quality-playbook
- https://denser.ai/blog/rag-chunking-strategies/
- https://arxiv.org/pdf/2401.18059