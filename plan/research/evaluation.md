# Evaluation

## HEADLINE
Faithfulness is the non-negotiable ship gate for hallucination risk, but the aggregate filter queries (Type A) expose a structural blind spot in every standard RAG metric — they require set-completeness eval (Document F1@k) which none of the off-the-shelf frameworks implement out of the box.

## RECOMMENDATION
Day-1 stack: DeepEval (v1.x, pip install deepeval, MIT license) as the pytest-based CI gate on a golden dataset of 30 known-answer Q&As, with faithfulness threshold ≥0.85 and answer correctness threshold ≥0.80 as hard pass/fail. Ragas (v0.2+) for the canonical metric formulas and synthetic test-case generation from your 52 source files. Arize Phoenix (free, self-hosted Docker, OTel-native) for production tracing once the app is live. Do NOT add Braintrust ($249/month Pro minimum) or LangSmith until the team outgrows the free stack. For Type A aggregate queries, write a custom set-recall evaluator that computes D-F1@k (Document F1 at k): intersection of retrieved property set vs gold property set, divided by gold set size — this is not in any framework and must be hand-rolled in ~20 lines.

## WHY
Travel Inn has two query types with fundamentally different failure modes. Type B (semantic: "tell me about Ranthambore Lodge") fails in ways standard metrics catch: a low faithfulness score surfaces a hallucinated room count. Type A (aggregate: "which properties have fewer than 20 rooms") fails silently in ways standard metrics cannot catch at all: top-k vector retrieval returns 5 of 49 properties, the model answers confidently from those 5, faithfulness scores 1.0 (every claim IS grounded in the retrieved 5), but the answer is catastrophically incomplete. The sales team sends a quote missing 44 qualifying properties. This is the most dangerous failure mode for this product and it is invisible to every standard RAG metric. The hybrid architecture (SQL for structured fields + pgvector for semantic) means retrieval must be evaluated at two separate layers — the SQL/structured path must return 100% of qualifying rows, not a semantically relevant subset.

## ALTERNATIVES

### DeepEval (v1.x, Confident AI) -> **USE**
- PRO: Pytest-native CI gate; 50+ pre-built metrics including faithfulness, contextual precision/recall, hallucination, and custom G-Eval; blocks regressions on every commit; LLMTestCase structure maps cleanly to this project's input/retrieval_context/output triple; open source core is free
- CON: Judge LLM calls cost money at scale (uses GPT-4o or Sonnet by default, configurable); no built-in set-completeness metric for Type A queries; UI (Confident AI platform) behind paid tier

### Ragas (v0.2+) -> **USE**
- PRO: Canonical formulas for the 5 core RAG metrics; open source, no commercial tier; Multimodal Faithfulness metric is relevant since your source files are images; generates synthetic test cases from your corpus without human labeling
- CON: CI/CD integration is weaker than DeepEval (no pytest plugin); all metrics require reference answers, meaning you still need a golden dataset; slower to iterate on custom metrics

### Arize Phoenix -> **PHASE-2**
- PRO: Free, fully self-hosted (Docker/Helm), air-gappable which matters if client data is sensitive; OTel-native so traces bind to both retrieval and generation spans separately; 50+ pre-built eval templates; afternoon setup time
- CON: Heavier infrastructure than a small v1 needs on day one; eval templates still need customization for Type A queries; not a CI gate by itself

### Braintrust -> **PHASE-2**
- PRO: Full eval lifecycle including production monitoring and team collaboration; stores golden datasets and run history; free Starter tier is genuinely usable for one engineer
- CON: Pro tier is $249/month with no mid-tier; tracing billed at $3/GB ingestion; proprietary platform lock-in; overkill for a 10-person sales team on v1

### LangSmith (LangChain) -> **REJECT**
- PRO: Tight LangChain/LangGraph integration; dataset management and human feedback UI
- CON: This project is NOT using LangChain; the integration advantage is zero; usage-based pricing adds up; redundant with Arize Phoenix

### TruLens (Snowflake/TruEra) -> **REJECT**
- PRO: Couples tracing with evaluation inline; RAG Triad (groundedness, context relevance, answer relevance) is a clean mental model
- CON: Development velocity has slowed since Snowflake acquisition in 2024 (noted by multiple 2026 sources); DeepEval and Ragas have shipped more application-layer features since; the RAG Triad is a subset of what DeepEval offers

### Promptfoo (v0.9+) -> **PHASE-2**
- PRO: CLI-first matrix testing across prompts and models; built-in red-teaming plugins; excellent for prompt regression when you are iterating on system prompts
- CON: Not RAG-native; no contextual precision/recall; not useful until you are comparing multiple prompt variants or models side-by-side

### Hand-rolled eval harness -> **CONSIDER**
- PRO: Exact control; no framework overhead; set-completeness for Type A queries requires this anyway
- CON: Maintenance burden; reinvents faithfulness and context recall poorly; avoid for metrics that frameworks already implement correctly

## KEY FINDINGS
- Faithfulness vs. Correctness are distinct: Faithfulness (0-1 score) checks whether every claim in the answer is grounded in retrieved context — it catches hallucination WITHIN what was retrieved. Answer Correctness compares the final answer against a reference ground truth — it catches cases where retrieval was incomplete so the model answered from the wrong subset. For Travel Inn, BOTH matter: faithfulness catches invented driving distances, correctness catches missing properties in a filter query. Neither alone is sufficient.
- Context Recall is the 'silent regression' metric: defined as (necessary chunks retrieved / total necessary chunks required). It requires reference answers to compute, scores 0-1, and a drop in recall is invisible to the user until the model confidently answers from incomplete context. For Type B queries this is the second most important metric after faithfulness. Target ≥0.85.
- Standard RAG metrics score 1.0 on catastrophically wrong Type A answers: if the retriever returns 5 contextually relevant properties (out of 49 matching) and the model faithfully summarizes those 5, faithfulness = 1.0, context precision = 1.0, answer relevancy = 1.0. The answer is still wrong. This is not a gap in the metrics — it is a category error. Type A queries require retrieval completeness evaluation, not retrieval relevance evaluation.
- Document F1@k (D-F1@k) from the GlobalRAG benchmark (ACL 2025, arxiv 2510.26205) is the correct metric for Type A: it computes F1 between the retrieved document set and the gold required document set, measuring coverage completeness rather than semantic relevance. For 'properties with fewer than 20 rooms' the gold set is all matching rows from the structured store; D-F1@k = 1.0 only when every qualifying property is retrieved.
- DeepEval's pytest integration is the fastest path to a regression gate: `deepeval test run test_rag.py` in GitHub Actions blocks merges when any metric drops below threshold. The LLMTestCase structure (input, actual_output, retrieval_context, expected_output) maps directly to this project's query/answer/source-docs triple. Thresholds of 0.5 are the DeepEval defaults; for hallucination-critical systems raise faithfulness to 0.85.
- Per-sentence groundedness catches more than whole-answer faithfulness: a 0.9 faithfulness score can hide one fabricated sentence in a 10-sentence answer. For distance/time claims specifically (nearest airport, safari gate km/hours) where one wrong number destroys a quote, sentence-level groundedness checking is worth the extra LLM calls. DeepEval's HallucinationMetric operates at claim level; Ragas Faithfulness decomposes the answer into statements then checks each.
- The 2025-2026 standard two-layer eval pattern: (1) offline gold-set CI gate on every commit (DeepEval + pytest), (2) online sampling of 5-20% of production traffic with automated scoring (Arize Phoenix or Braintrust), (3) weekly human calibration of 20-30 samples targeting Cohen's kappa ≥0.6 between LLM judge and human. For v1 with 10 sales staff, start at layer 1 only.
- Ragas v0.2 Multimodal Faithfulness is relevant but limited: it evaluates whether image-derived answers are grounded in image content, but it requires the image to be passed through a multimodal model at eval time — meaning eval cost doubles for image-sourced properties. Pragmatic alternative: run multimodal extraction once at ingestion, store structured JSON, then evaluate faithfulness against the JSON text, not the raw image.

## PITFALLS
- Evaluating Type A queries with standard top-k retrieval metrics and calling it done: faithfulness, context precision, and answer relevancy all score high while the answer is missing 80% of qualifying properties. The correct fix is to route Type A queries through the SQL/structured path (pgvector alone cannot do set-complete retrieval) and evaluate that path separately with set recall, not semantic similarity.
- Using threshold=0.5 (DeepEval default) for faithfulness on a sales tool: a 50% faithfulness score means half the claims are potentially fabricated. For a system where one wrong driving distance destroys trust permanently, set faithfulness threshold ≥0.85 and fail the CI build below it. Do not soften this threshold to make tests pass.
- Conflating retrieval failure with generation failure in debugging: if a query returns a wrong answer, the failure is either (a) the retriever did not fetch the right documents, or (b) the model hallucinated despite correct documents. Without logging retrieval_context separately in every test case, you cannot diagnose which. Always capture and store the actual retrieval_context alongside input and output in your test harness.
- Relying on the 30 golden Q&As as a complete regression suite: 30 questions cover edge cases you thought of, not the ones the sales team will discover in week 2. Add a feedback loop from day 1 — a thumbs-down button in the UI writes the query + bad answer to a Neon table that becomes the regression suite feed. The golden set grows organically from real failures.
- Using LLM-as-judge for evaluation without pinning the judge model and prompt version: judge model upgrades change scores non-monotonically. A Sonnet 3.5 judge and a Sonnet 4.x judge will disagree on the same answer. Pin the judge model (e.g., claude-sonnet-4-5 with a fixed system prompt hash) and treat score changes after a judge upgrade as a calibration event, not a regression.

## IMPLEMENTATION NOTES
- Golden dataset structure for the 30 known-answer questions: store as JSONL with fields {id, query, query_type (A|B), expected_answer, gold_property_ids (for Type A), gold_source_docs, notes}. Separate Type A and Type B into different test files (test_filter_queries.py, test_semantic_queries.py) because they use different metrics and different pass/fail logic.
- DeepEval setup for Type B semantic queries: `pip install deepeval ragas`. In test_semantic_queries.py, use FaithfulnessMetric(threshold=0.85), ContextualRecallMetric(threshold=0.85, include_reason=True), and AnswerCorrectnessMetric(threshold=0.80). Pass retrieval_context as the list of actual source chunks returned by your retriever, not the full corpus.
- Custom set-recall evaluator for Type A queries (~20 lines): at test time, run the query, extract the list of property IDs returned in the answer, compare against gold_property_ids using set intersection. set_recall = len(returned_ids & gold_ids) / len(gold_ids). set_precision = len(returned_ids & gold_ids) / len(returned_ids). A passing test requires set_recall >= 1.0 (every qualifying property present). Any score below 1.0 is a hard fail — partial recall is a silent wrong answer.
- Retrieval-only test cases: write a separate test that calls only the retriever (SQL path for Type A, pgvector path for Type B) and checks retrieval_context quality before the LLM sees it. If retrieval_context contains the right chunks, generation failure is the LLM's problem. If it does not, fixing the prompt will not help — fix the retriever. This separation is the most valuable diagnostic the eval suite provides.
- Grounded refusal evaluation: add 5-10 questions to the golden dataset that the corpus definitively cannot answer (e.g., 'which properties accept American Express'). The expected_answer is a refusal. Score with a binary evaluator: did the model refuse (1) or hallucinate an answer (0). A hallucinated answer on a refusal-expected question is the worst failure mode — weight it as a blocker.
- CI integration: in GitHub Actions, set ANTHROPIC_API_KEY and run `deepeval test run test_semantic_queries.py --fail-or-exit-code` and the custom pytest file for Type A. Gate merges to main on both passing. Estimated cost per full run at 30 questions: approximately $0.15-0.40 using claude-sonnet-4-5 as judge (30 questions x 4 metric LLM calls x ~$0.003/call average). Run on every PR.
- Production tracing (add at launch, not day 1): instrument the Next.js backend with OpenTelemetry, send spans to a self-hosted Arize Phoenix Docker container (docker pull arizephoenix/phoenix:latest). Each span captures: query, retrieval_context (with source_doc_ids), final_answer, latency. Run Phoenix's built-in QA and Hallucination evaluators on a 10% sample of production traffic daily.
- Do not use BLEU, ROUGE, or CHRF scores for this project: these n-gram metrics are designed for machine translation and summarization, not QA. A correct answer that uses different phrasing from the reference answer will score near 0. Use LLM-as-judge (G-Eval or DeepEval's AnswerCorrectnessMetric) which handles paraphrase correctly. BLEU/ROUGE appear in Ragas' available metrics list — ignore them for this use case.

## SOURCES
- https://aiml.qa/llm-evaluation-framework-benchmark-2026/
- https://www.confident-ai.com/blog/how-to-evaluate-rag-applications-in-ci-cd-pipelines-with-deepeval
- https://futureagi.com/blog/rag-evaluation-metrics-2025/
- https://www.evidentlyai.com/llm-guide/rag-evaluation
- https://arxiv.org/html/2510.26205v2
- https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/
- https://github.com/Arize-ai/phoenix
- https://www.braintrust.dev/articles/rag-evaluation-metrics
- https://callsphere.ai/blog/rag-evaluation-frameworks-2026-ragas-trulens-deepeval
- https://atlan.com/know/llm-evaluation-frameworks-compared/
- https://kili-technology.com/blog/rag-evaluation-guide-measuring-retrieval-and-generation-as-separate-problems
- https://www.getmaxim.ai/articles/rag-evaluation-a-complete-guide-for-2025/