# document-extraction

## HEADLINE
For design-heavy PNG brochures at 96 DPI, pure vision-LLM extraction (Gemini 2.5 Flash/Pro with structured JSON) beats every traditional or layout-aware alternative; PDFs need a dual-input strategy combining the z-order text layer with a rendered page image; both paths converge on a single Pydantic schema with per-template few-shot examples.

## RECOMMENDATION
Use Gemini 2.5 Flash as the primary extractor for all 52 documents. Feed PNG/JPEG files as 2x-upscaled images (target ~1588px wide, ~192 effective DPI) to stay above the 150 DPI accuracy cliff for small text. For the 15 native-text PDFs, send a dual input per page: the raw pypdf/pdfplumber text string (to anchor against hallucination) plus a Pillow-rendered 200 DPI PNG of the page (to correct z-order scrambling). Force a single Pydantic v2 schema via response_schema= in the Gemini API; add 2-3 few-shot JSON examples per template variant in the system prompt. Run Claude Sonnet 4.5 as a second-pass validator on 100% of numeric fields (room counts, distances, prices) and flag any field where the two models disagree by more than a tolerance threshold for human review. Given only 52 source files, cross-model validation costs under $2 total.

## WHY
The 37 PNG and 1 JPEG files have NO text layer whatsoever, making traditional OCR (Tesseract, PaddleOCR) and layout-aware parsers (Docling, Azure Document Intelligence) the wrong tool - they are all designed for documents that either have a text layer or are scans. These files are clean digital exports with text baked into the pixel grid. Only vision-LLMs can read text overlaid on photograph backgrounds or inside image grids. Docling's own documentation confirms it does not support image-only inputs (lacks handwriting/scanned support). The 15 native-text PDFs have the opposite problem: pypdf extracts text in z-order (design-tool paint order), not reading order, so the raw text is unusable alone. Sending both anchors the LLM: the text layer catches hallucination on strings, the image corrects reading order and captures any text that is part of an embedded image element. The 96 DPI source images place small property details (room counts, distances like '4.5 ft') at 8-12 pixel text height, marginally above the 7-pixel accuracy floor identified in resolution research - 2x upscaling to ~192 effective DPI adds a reliable safety margin at near-zero cost. Reducto would be the right managed-service choice if the corpus were thousands of pages, but at 52 files the cost difference is irrelevant and direct API control is preferable for building the extraction schema.

## ALTERNATIVES

### Tesseract / PaddleOCR -> **REJECT**
- PRO: Free, offline, fast, no API costs
- CON: Completely fails on text overlaid on photographs and multi-column design layouts; no semantic understanding; cannot handle the PNG files at all without pre-segmentation

### Azure Document Intelligence / AWS Textract / Google Document AI -> **REJECT**
- PRO: Production SLAs, strong on structured forms and tables, decent multi-column support
- CON: Azure 82.7%, AWS Textract 80.9%, Google Document AI 64.6% on complex tables (RD-TableBench); designed for forms/invoices, not Canva-style brochures; significantly more expensive than direct vision-LLM API at this scale; cannot handle PNG image-only files well

### Docling -> **REJECT**
- PRO: 97.9% table accuracy on DocLayNet benchmark, free, local, good multi-column text
- CON: Explicitly does not support image-only documents (PNG/JPEG). Multi-column accuracy degrades on non-academic layouts. Slow: 65 seconds for 50 pages

### LlamaParse (Agentic Plus mode) -> **CONSIDER**
- PRO: Handles embedded images, LlamaExtract with field-level confidence scoring, ~6 seconds per document, MCP server integration, BYOC enterprise option
- CON: $0.056/page in Agentic Plus mode; 9.8% failure rate on LongExtractBench vs Reducto's 0%; struggles with multi-column layouts per benchmark; adds external dependency for what Gemini API already handles natively

### Reducto AI (Agentic mode) -> **PHASE-2**
- PRO: 99.6% precision/recall on LongExtractBench, 90.2% on complex tables, multi-pass hybrid (vision + OCR + VLM), bounding-box citations, enterprise VPC deployment
- CON: $0.015-$0.06/page; overkill for 52 files; external dependency; less control over schema enforcement than direct Gemini API calls

### Gemini 2.5 Flash (primary extractor) -> **USE**
- PRO: $1 per 6,000 pages; near-perfect OCR per benchmark reports; supports response_schema= JSON Schema forcing via Pydantic; natively combines text layer + visual for PDF inputs; processes tall images via 768x768 tiling at 258 tokens/tile
- CON: Google explicitly notes imprecision at exact spatial location within PDFs; single-pass VLM can hallucinate on dense or ambiguous layouts without the dual-input anchor

### Claude Sonnet 4.5 / 5 vision (cross-validator) -> **USE**
- PRO: Different model family eliminates correlated errors; structured output via tool_use; strong at following precise schema constraints
- CON: More expensive than Gemini Flash for high-volume extraction; at 794x3200px costs ~2,196 tokens image input per file (resizes long edge to 2,576px max)

### Unstructured.io -> **REJECT**
- PRO: Purpose-built for automation pipelines, strong semantic element labeling
- CON: 75% cell accuracy on complex tables; 51 seconds per page processing time; does not handle image-only files well

## KEY FINDINGS
- Tiling math for 794x3200px: Gemini uses ceil(794/768) x ceil(3200/768) = 2x5 = 10 tiles at 258 tokens each = 2,580 input tokens per image. Claude resizes long edge to 2,576px then charges (640x2576)/750 = ~2,196 tokens. Both are well within context limits.
- 96 DPI is below the 150 DPI threshold where vision-LLM OCR accuracy measurably declines. Upscaling 2x with Pillow (LANCZOS) before sending raises effective DPI to 192 and yields +15-30% accuracy on small text per 2025 resolution research. Target text height >= 14px after upscale.
- OmniDocBench (CVPR 2025, 1,651 pages): GLM-OCR 94.6%, PaddleOCR-VL-1.5 >94%, Gemini 3 Pro 90.3% - but the benchmark is now considered saturated on academic PDF types and underweights design/brochure formats. Scores do not directly predict performance on Travel Inn's corpus.
- Dual-input for PDFs is a real, documented technique: Gemini 2.5 Pro internally combines text-layer tokens with visual rendering when processing native PDFs (confirmed by Google documentation). Manually replicating this for all PDFs - extracting raw text via pdfplumber + rendering pages at 200 DPI via pdf2image/Pillow - gives the model both anchors and lets it self-correct z-order scrambling.
- Cross-model diffing: recent clinical data extraction research (May 2026, medRxiv) validates multi-LLM disagreement as a scalable quality detector. For structured numeric fields (room counts, km distances, prices), a simple Python dict diff between Gemini and Claude outputs catches extraction errors without ground truth. Agreement on a field is strong evidence of correctness.
- Reducto leads managed parsers: 99.6% precision on LongExtractBench vs LlamaParse's 77.5% recall and 9.8% failure rate. Cost at $0.015/page standard, $0.03-$0.06/page agentic. Becomes relevant at Phase 2 (~500 GB / ~500k chunks) where per-page cost dominates engineering time.
- Gemini 2.5 Flash cost: approximately $0.000167 per page for the image input tokens alone at current pricing. Processing all 52 source files once costs under $0.05 in extraction tokens - validation passes with Claude add perhaps $0.50 total. Extraction is essentially free at this corpus size.
- Template normalization via schema-first prompting is the documented industry approach (Unstract, LlamaExtract, Reducto all use it): define one Pydantic v2 model with Optional fields for template-specific items (e.g., safari_gate_km appears in wildlife lodge templates but not city hotel templates), then include 2-3 few-shot JSON examples per template variant in the system prompt. The LLM maps visual position to semantic field without requiring separate code paths per template.

## PITFALLS
- Sending 96 DPI images without upscaling: text like '4.5 km' at ~10px height is right at the hallucination boundary. Misread distances in a sales tool destroy trust permanently (as your requirements note). Always upscale to >=192 effective DPI before extraction.
- Using pypdf or PyMuPDF text extraction alone for the PDFs: z-order text export from design-tool PDFs produces character soup. The word 'Ranthambore' might appear in the middle of a price string because both were on the same layer. Feed the rendered image alongside the text, never text alone.
- Schema fields with null vs absent: when a property lacks a field (e.g., no pool, no safari gate), Gemini will sometimes return the string 'N/A' or omit the field entirely depending on prompt wording. Pin this in the schema: use Optional[str] = None and explicitly instruct 'return null, not the string N/A or Not applicable'.
- Correlated hallucination: if you use Gemini Flash for both extraction and validation, errors correlate. Cross-model diffing only works if the validator is a different model family (Claude vs Gemini). Do not use gemini-2.5-flash and gemini-2.5-pro as your two validators - they share training and will agree on the same wrong answer.
- Token budget on validation: a 794x5150px image (the tallest in corpus) hits ceil(794/768) x ceil(5150/768) = 2x7 = 14 Gemini tiles = 3,612 tokens just for image input. After upscaling 2x the image is 1588x10300px - this is 3x14 = 42 tiles = 10,836 tokens. Cap upscale dimensions: upscale to 2x but then cap at a max height of 4096px (Pillow thumbnail with aspect ratio), yielding at most 3x6 = 18 tiles per image.
- Phase 2 scaling assumption: the current leaning of Gemini embedding + direct Gemini extraction works at 52 files. At 500k chunks, per-page extraction cost and parallelism become the bottleneck. Reducto's batch queue (20% discount) and VPC deployment option are the Phase 2 path, not a Phase 1 concern.

## IMPLEMENTATION NOTES
- Upscale pipeline (Python): from PIL import Image; img = Image.open(path); w,h = img.size; scale = 2.0; new_w, new_h = int(w*scale), int(h*scale); if new_h > 4096: scale = 4096/h; new_w,new_h = int(w*scale),int(h*scale); img = img.resize((new_w,new_h), Image.LANCZOS). Save as PNG, then send to Gemini.
- PDF dual-input: use pdfplumber for text extraction (better column awareness than pypdf), use pdf2image with dpi=200 for rendering. Send both in the same Gemini call: contents=[{type:text, text:raw_text_layer_here}, {type:image_url, ...rendered_png}] with prompt 'The text layer below was extracted from the PDF but may be in draw order, not reading order. Use the image to determine correct reading order and map fields to the schema.'
- Pydantic schema (partial example): class PropertyRecord(BaseModel): property_name: str; location: str; nearest_airport: list[AirportRef]; nearest_railhead: Optional[str]=None; safari_gate: Optional[SafariGateRef]=None; room_count_total: Optional[int]=None; room_categories: list[RoomCategory]; best_time_to_visit: Optional[str]=None; price_from_inr: Optional[int]=None; meal_plan_code: Optional[str]=None; staff_inspected: Optional[bool]=None. Pass via response_mime_type='application/json', response_schema=PropertyRecord.model_json_schema().
- Gemini API call: model = 'gemini-2.5-flash'; generation_config = {response_mime_type: 'application/json', response_schema: PropertyRecord.model_json_schema(), temperature: 0.1}. Temperature 0.1, not 0, to avoid repetition loops on structured output while staying deterministic.
- Cross-model diff function: def diff_extractions(g: dict, c: dict, numeric_fields: list[str]) -> list[str]: flags=[]; for f in numeric_fields: gv,cv = g.get(f), c.get(f); if gv is not None and cv is not None and gv != cv: flags.append(f'{f}: Gemini={gv} Claude={cv}'); return flags. Any non-empty flags list routes the document to manual review queue.
- Template classification: add a classification step before extraction. Send just the image to Gemini with prompt 'Which template is this: (A) current image one-pager, (B) 2024 image one-pager, (C) variant image one-pager, (D) PDF layout? Respond with A, B, C, or D.' Then select the matching few-shot example block for the extraction prompt. Costs 1 API call per document, negligible at 52 files.
- Storage: store upscaled PNGs and extracted JSON in Cloudflare R2 alongside source files. R2 zero-egress cost means re-running extraction during schema changes is free. Commit the extraction schema version alongside each JSON so you can identify which schema version produced each record.
- Validation at scale (Phase 2): at 500k chunks, switch from full cross-model validation to sampled validation (5% random + 100% of flagged documents) plus a deterministic check: if json.loads() fails or any required field is null, auto-retry with Reducto as fallback at $0.015/page.

## SOURCES
- https://llms.reducto.ai/best-llm-ready-document-parsers-2025
- https://llms.reducto.ai/document-parser-comparison
- https://www.vellum.ai/blog/document-data-extraction-llms-vs-ocrs
- https://blog.roboflow.com/image-token-cost-vlm/
- https://procycons.com/en/blogs/pdf-data-extraction-benchmark/
- https://www.llamaindex.ai/blog/omnidocbench-is-saturated-what-s-next-for-ocr-benchmarks
- https://github.com/opendatalab/OmniDocBench
- https://winbuzzer.com/2025/04/21/gemini-2-5-pro-appears-to-be-first-ai-model-to-fully-understand-pdf-layouts-enabling-precise-citations-xcxwbn/
- https://ai.google.dev/gemini-api/docs/structured-output
- https://unstract.com/blog/ai-document-processing-no-manual-templates-custom-schema-support/
- https://www.medrxiv.org/content/10.64898/2026.05.04.26352392v1.full
- https://medium.com/google-cloud/gemini-2-5-flash-the-ai-backbone-for-smarter-document-processing-6b8f4a18135a
- https://arxiv.org/pdf/2503.23667