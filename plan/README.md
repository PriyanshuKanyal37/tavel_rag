# 📁 Travel Inn — Planning Documents

**Start here.** Everything below is planning and design. Client source data lives in `../data/`, the working code in `../pilot/`.

---

## 🎯 The live documents

| File | What it is | Read it when |
|---|---|---|
| **[BUILD-SPEC.md](BUILD-SPEC.md)** | **The internal build document.** Everything, end to end — models, storage, ingestion, database, retrieval, answering, sessions, caching, evaluation, costs, build order. Marks clearly what is measured and what is assumed | **You are building it** |
| **[CLIENT-ROADMAP.md](CLIENT-ROADMAP.md)** | The version for Shivam. Same system, no stack detail, no internals | You want the picture without the depth |
| **[REPLY-TO-SHIVAM.md](REPLY-TO-SHIVAM.md)** | Answers to his eight questions on the roadmap — timeline, model IDs, latency, label coverage | You want the honest gaps and corrections |
| **[EXTRACTION-SPEC.md](EXTRACTION-SPEC.md)** | The instruction sent to the reading model, and the approved label list. **These two artefacts are the schema** | Before the full ingestion run |
| **[DATABASE-DESIGN.md](DATABASE-DESIGN.md)** | The architecture derived from first principles, with the reasoning and the trade-offs. Includes the full table definitions | You want to argue with a decision |
| **[QUESTION-BANK-ANALYSIS.md](QUESTION-BANK-ANALYSIS.md)** | The client's 186 questions mapped against what the data can actually answer. The 30 that pass become the test suite | You need to know what the pilot is judged on |
| **[OPEN-ITEMS.md](OPEN-ITEMS.md)** | What we still need from the client | Before a client conversation |
| **[ANSWERS.md](ANSWERS.md)** | The original data audit — 52 files inspected individually | You want the raw findings about their data |

---

## 📚 `research/`

Ten research briefs behind the design decisions, plus an adversarial challenge file. Each is sourced and dated.

```
   document-extraction.md          which vision model, and why
   retrieval-architecture.md       why four search paths, with measured numbers
   vector-database.md              why Postgres and not Qdrant
   chunking-and-indexing.md        chunk size, overlap, contextual retrieval
   generation-and-grounding.md     how answers stay tied to sources
   evaluation.md                   how correctness gets proven
   cost-caching-ops.md             the cost model
   backend-production.md           production concerns
   frontend-ux.md                  citation UX patterns
   _challenges.md                  adversarial objections to the design
   _gaps.md                        what the research did not cover
```

---

## 🗄️ `archive/`

Superseded, kept for history. **Do not build from these.**

| File | Superseded by |
|---|---|
| `ARCHITECTURE.md` | `DATABASE-DESIGN.md` — the fact-storage design in this version is wrong and was corrected |
| `ARCHITECTURE-REVIEW.md` | An external review of that earlier version. Its valid findings are already folded in |
| `image_fields.md` | A working note from the original audit |

---

## 🧪 Where the evidence lives

Not in this folder — in `../pilot/`. That is real, runnable code that produced the numbers quoted throughout these documents:

| | |
|---|---|
| `extract.py` · `prompt.py` | The extraction pipeline |
| `validate.py` | Grounding, unit and vocabulary checks |
| `bakeoff.py` | The model comparison |
| `latency.py` | The measured answer timings |
| `schema.sql` · `load.py` | The database, and loading extraction output into it |
| `out_pro/` `out_f38/` `out_flash/` `out/` | Raw results from four models on the client's real files |

**Total cost of everything measured so far: about ₹85.**
