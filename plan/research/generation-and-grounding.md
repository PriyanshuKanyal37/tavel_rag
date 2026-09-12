# generation-and-grounding

## HEADLINE
Use Anthropic Citations API for all text-grounded answers, but the 37 PNG/JPEG files require a two-stage workaround: extract text at ingestion, store as custom_content blocks, then cite the extracted text at query time - image-level citation is explicitly not supported.

## RECOMMENDATION
For semantic/descriptive queries (type B): use Citations API with citations.enabled=true on custom_content documents (extracted text blocks from PNGs) and PDF/plain-text documents. For filter/aggregate queries (type A): bypass the LLM entirely with SQL on Postgres structured columns - Citations API is incompatible with structured outputs so do not attempt to combine them. Layer a tight system-prompt refusal constraint on all paths. Add LLM-as-judge faithfulness monitoring in production. Model: claude-sonnet-4-5 or claude-opus-5 (all active models support citations as of June 2025).

## WHY
Travel Inn's corpus is 71% images (37 of 52 files) with no text layer. Citations API cannot cite images. The extraction pipeline (Gemini + Claude) already converts image content to structured text during ingestion. That extracted text, stored as custom_content blocks in Postgres, is the exact format Citations API is designed for - each block index maps back to the source image filename, giving the UI what it needs to say "Source: corbett-lodge.png". For the PDF files (15 of 52, with selectable text) the API cites by page number natively, which is clean. The filter query type is a harder constraint: Citations API + structured output format are a 400-error pair per the official docs. SQL on structured columns (room count, price, airport distance) is both faster and produces correct aggregate answers, which pure vector search fails at entirely.

## ALTERNATIVES

### Anthropic Citations API (native) -> **USE**
- PRO: Guaranteed valid pointers to source spans - cited_text does not count as output tokens; 15% better recall accuracy vs. prompt-engineered citations per Anthropic internal eval; works with prompt caching (cache_control ephemeral on document blocks); all active models supported as of June 30 2025 GA; char_location/page_location/content_block_location schemas are machine-readable and directly renderable in UI
- CON: Image citations not supported - 37 of 52 files need an extraction workaround; incompatible with structured outputs (output_config.format = 400 error); must enable on all or none of documents in a request; citations must be enabled uniformly, which means you cannot mix cited and uncited documents in one call

### Prompt-engineered citations (inline markers) -> **REJECT**
- PRO: Works with any model, any document type including images; can be combined with structured outputs; no API version dependency
- CON: RefusalBench (arxiv 2510.10390, Oct 2025) shows frontier models fail grounded refusal below 50% accuracy on multi-document tasks; prompt-only citations can hallucinate quote text - the model may output a plausible-sounding but fabricated excerpt; cited_text counts as output tokens (cost penalty); Anthropic's own eval shows 15% lower recall vs. native Citations API

### Post-hoc attribution (re-rank after generation) -> **PHASE-2**
- PRO: Decoupled from generation; can attribute across image and text sources uniformly; works with any response format
- CON: Two LLM calls per query (latency ~2x); attribution to original span is approximate - often finds the closest matching chunk, not the exact cited span; does not prevent hallucination, only detects it after the fact; adds ~300-500ms at minimum on a warm path

### Self-RAG / Chain-of-Verification -> **PHASE-2**
- PRO: CoVe pattern (generate, verify, revise) measurably reduces factual errors on QA benchmarks; GRACE (arxiv 2601.04525, Jan 2026) shows RL-based abstention training beats prompting
- CON: Self-RAG adds 2-4 LLM calls per query; CoVe verification questions must themselves be grounded; GRACE requires fine-tuning, not feasible for this project; RefusalBench finding that scale and reasoning do not improve refusal means chain-of-thought alone will not fix the core gap; overkill for a 49-property v1 corpus

### LLM-as-judge faithfulness monitoring (RAGAS / FaithJudge) -> **USE**
- PRO: Standard production observability pattern for RAG in 2025-2026; catches hallucinations in sampled traffic without blocking the user path; RAGAS faithfulness metric is reference-free; FaithJudge (EMNLP 2025) uses human-annotated examples for higher accuracy
- CON: Asynchronous - does not prevent the hallucinated answer from reaching the user; adds cost per sampled request; requires a golden eval set to calibrate thresholds

## KEY FINDINGS
- Citations API GA June 30 2025: supports plain_text (char indices), PDF (page numbers 1-indexed exclusive), and custom_content (block indices 0-indexed exclusive). Image citations explicitly not supported per docs: 'Only text citations are currently supported. Image citations are not yet possible.'
- Response schema per official docs: { type: 'char_location', cited_text: '...', document_index: 0, document_title: '...', start_char_index: 0, end_char_index: 50 }. cited_text does not count toward output tokens in either direction (input or output), making citation-heavy responses cheaper than prompt-based quoting.
- Citations API is incompatible with structured outputs (output_config.format): combining them returns a 400 error. This is a hard constraint for Travel Inn's filter/aggregate query type (A).
- RefusalBench (arxiv 2510.10390, Oct 2025): even frontier models drop below 50% refusal accuracy on multi-document RAG tasks. Neither scale nor chain-of-thought reasoning improves this - targeted alignment training is required. Prompt-only grounded refusal is structurally unreliable.
- Anthropic internal evaluation: Citations API achieves 15% better recall accuracy than custom prompt-engineered citation implementations.
- GRACE (arxiv 2601.04525, Jan 2026): RL-based training for grounded response and abstention outperforms prompt-based abstention, but requires fine-tuning. Not practical for this project.
- System prompt grounded refusal wording reduces hallucinated claims by 40-60% on known-hallucination-prone query sets (practitioner data from getmaxim.ai, 2025-2026). Best pattern: 'Answer ONLY from the provided context. If the context does not contain the answer, respond: [specific refusal template with next-step guidance].'
- Citations + prompt caching are compatible: apply cache_control: { type: 'ephemeral' } on document blocks. Citation response blocks themselves cannot be cached but the source documents can, which matters for repeated queries against the same property files.

## PITFALLS
- Do not send PNG or JPEG files directly to Citations API expecting image-level citations - the API will not cite image content. You must extract text at ingestion time and pass it as a custom_content document. The citation will point to the extracted text block, not the image pixels. The UI must then map block_index back to the source filename stored in Postgres.
- Citations API and structured outputs are mutually exclusive. If you try to use output_config.format (e.g., for JSON-structured filter answers) alongside citations.enabled=true, you will get a 400 error. Keep filter/aggregate queries (type A) on the SQL path, never through the Citations API path.
- Do not rely on system-prompt grounded refusal alone. RefusalBench shows sub-50% accuracy on multi-doc tasks. The Citations API provides structural enforcement (every claim gets a pointer) but does not prevent uncited prose in the same text block. You need both: API-level citation enforcement plus a system prompt that says 'Do not make any factual claim you cannot cite.'
- The context field on a document block is passed to the model but is NOT citable. Do not put facts (driving distances, room counts) in the context field expecting them to be cited - they won't be. Only content inside source.data is citable.
- citations.enabled must be set uniformly across all documents in a request - all on or all off. You cannot enable citations on the PDF document but leave them off on the plain-text chunk in the same API call.
- For PDF files: the text extraction is z-order not reading order (stated in project context). Anthropic's PDF extraction is also sentence-based and may mis-order multi-column layout text. For the 15 PDFs, validate extraction quality before trusting sentence-level char_location citations - a citation to 'page 2' on a multi-column layout PDF may reference the wrong column's sentence.
- A sales user seeing 'I cannot answer this' without a next step will distrust the tool immediately. The refusal must always include an actionable follow-up: which team member to contact, or which SharePoint folder to check. Hard-code these routing hints into the system prompt per question category.

## IMPLEMENTATION NOTES
- Image pipeline to Citations API: during ingestion, extract structured fields from PNG/JPEG using Gemini vision. Store extracted text as an array of labeled blocks in Postgres (e.g., [{label: 'location', text: 'Corbett, Uttarakhand'}, {label: 'room_count', text: '18 rooms'}]). At query time, serialize these blocks into the custom_content source format: { type: 'document', source: { type: 'content', content: [ {type: 'text', text: 'location: Corbett...'}, ... ] }, title: 'corbett-lodge.png', citations: { enabled: true } }. The citation response will include content_block_index pointing to the specific block, which you map back to the label for UI display.
- System prompt structure for grounded refusal (put constraints in system, not user turn to prevent override): 'You are a property information assistant for Travel Inn DMC. Answer ONLY from the documents provided in this conversation. Do not use general knowledge about hotels, India, or travel. For every factual claim, you must have a citation. If the provided documents do not contain enough information to answer, respond exactly: "The property data I have does not include [specific missing detail] for [property name]. To get this, contact [founder name] or check the [folder path] folder in SharePoint." Never estimate, approximate, or infer data that is not explicitly stated.'
- Response format for sales audience: instruct the model to use a scannable structure. Example instruction: 'Format answers as: a one-sentence direct answer, then a bulleted breakdown of supporting details, then a [Source: filename, page/block] footer for each bullet. Keep the total response under 200 words unless the user asks for detail.'
- Production faithfulness monitoring: sample 5-10% of live queries asynchronously. Run a RAGAS faithfulness check (or a simple LLM-as-judge prompt: 'Does every factual claim in [ANSWER] appear verbatim or by clear implication in [CONTEXT]? Score 0-1.') Store scores in Postgres with the query_id. Alert when 7-day rolling faithfulness drops below 0.85.
- Prompt caching for the property corpus: wrap each document block with cache_control: { type: 'ephemeral' }. With 49 properties and typical query patterns, cache hit rates should be high. The minimum cacheable block size is 1024 tokens for claude-sonnet, 2048 for opus. Aggregate multiple small property chunks into one document block if individual files are below the threshold.
- For the 15 PDFs with z-order extraction: before using Citations API page citations in production, run a validation pass - extract the PDF text via Anthropic's built-in extraction, display it to a human reviewer, and flag any properties where multi-column layout causes visible mis-ordering. For those specific files, convert to custom_content with manually ordered blocks instead of relying on automatic PDF sentence chunking.
- Confidence indicators for sales UI: do not show numeric confidence percentages (confuses non-technical users). Instead show: (1) the count of source documents cited ('Based on 2 property sheets'), (2) a visual distinction between 'directly stated' vs. 'inferred' answers - avoid the latter entirely for this use case, (3) a clear 'Not in our data' badge when the refusal fires, styled differently from error states.

## SOURCES
- https://platform.claude.com/docs/en/build-with-claude/citations
- https://claude.com/blog/introducing-citations-api
- https://simonwillison.net/2025/Jan/24/anthropics-new-citations-api/
- https://arxiv.org/abs/2510.10390
- https://arxiv.org/pdf/2601.04525
- https://aclanthology.org/2025.emnlp-industry.54/
- https://www.stackai.com/blog/prompt-engineering-for-rag-pipelines-the-complete-guide-to-prompt-engineering-for-retrieval-augmented-generation
- https://www.getmaxim.ai/articles/rag-evaluation-a-complete-guide-for-2025/
- https://apito.ai/en/blog/dev-guides/claude-citations-api-guide/