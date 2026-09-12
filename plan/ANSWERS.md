# Travel Inn — Data Audit & Build Estimate

**From:** Priyanshu → Shivam
**Date:** 17 Aug 2026
**Source:** All 52 files in the SharePoint `Property Updates` export, inspected individually

---

## Numbers

| | |
|---|---|
| Build time | **1 week** to testable build; 8–10 days total |
| One-time ingestion | **₹230** both models (~₹115 via Batch API) |
| Monthly running | **₹3,000–5,000** at 50 queries/day |
| Client timeline | Keep 4–6 weeks. Show Nazim in 2. |
| Quote running cost | ₹5,000/month, capped, separate line item |

---

## 1. Scale

| | |
|---|---|
| Files | 52 |
| Size | 206.8 MB |
| States | 17 |
| Distinct properties | ~49 |
| Formats | 36 PNG · 15 PDF · 1 JPEG |

"350 GB" is the whole product drive. This tree is 207 MB.

Coverage skewed: MP 10, Rajasthan 7, UP 6, Karnataka 5. Himachal, Odisha, Uttarakhand, West Bengal have 1 each.

## 2. File quality

**PDFs: 15/15 native selectable text.** Verified by per-page character counts on every file (226–933 words each). No OCR required.

Catch: text extracts in z-order, not reading order. Roswyn's sections come out scrambled.

**PNGs: 37 files (71% of corpus).** All 794px wide, 96 DPI. Clean digital design exports, not scans — body text crisp and legible. No text layer.

Tesseract will fail on these: multi-column layouts, text over photos, captions inside image grids.

The single `.jpeg` (Vayal Veedu) is 0.43 MB vs ~2 MB PNG average — compression artifacts on text. Only real quality risk.

## 3. Template consistency — four templates

| Template | Count | Dates |
|---|---|---|
| PDF, numbered 01–06 | 10 of 15 PDFs | to May 2026 |
| PNG "A PROPERTY UPDATE" | 32 PNGs | Feb 2025 – Feb 2026 |
| Older "A Hotel Update" | 5 files | all Sep–Dec 2024 |
| One-offs | Drenmo, Laalee, Oberoi Rajgarh, Postcard Hotels, Baasa | mixed |

Different field sets:

- **PNG:** Location / Airport / Railhead / Accommodations / Best Time / Nearest Gate
- **PDF:** Introduction / Why this property / Dining / Upsides & amenities / Inventory & category / Routing & special note

Reconciling four templates into one schema is the main ingestion work.

## 4. Duplicates

- **1 exact duplicate** (matching SHA1): `Ramathra Fort - Property Update.pdf` in both `Rajasthan/Karauli/` and `Rajasthan/Ramathra/`. Ramathra Fort is in Karauli district — second folder redundant.
- 5 files with `(1)` download suffixes.
- **Filename ≠ property name in 4 cases:**

| File path | Actual title |
|---|---|
| `Ladakh/Leh/Postcard Leh Property Update.png` | The Postcard in the Himalayan Willows |
| `Assam/Tezpur/_Postcard Tezpur Property Update.png` | The Postcard in the Durrung Tea Estate |
| `West Bengal/Siliguri/Courtyard Siliguri...png` | Courtyard by Marriott Siliguri |
| `MP/Bhopal/Sadar Manzil Product Update (1).png` | Sadar Manzil Heritage by Atmosphere, Bhopal |

## 5. Integrity

Zero password-protected. Zero corrupted. All 52 opened cleanly.

## 6. Incomplete data

- **Drenmo** — 226 words over 3 pages, one page image-only, no date.
- **Postcard Hotels** — 7 pages, 574 words. Mostly imagery.
- **8 of 15 PDFs have no date anywhere in the text.**

Corpus spans Sep 2024 → May 2026. Oldest doc is 23 months old.

## 7. Answer accuracy — the Nazim risk

### Star ratings do not exist

**Zero mentions across all 15 PDFs.** The template has no star-rating field. Confirmed visually on **Taj Mahal New Delhi** — the most likely candidate in the corpus — which reads only *"Managed by Taj Hotels – IHCL"*.

What exists instead: prose positioning — *"Luxury / Boutique Heritage Residence"*, *"boutique wilderness lodge"*, *"Mid & Upper-mid segment"*.

Ravi named star rating as the primary quoting parameter. It cannot be answered from this data by any system.

### Pool — answerable but unreliable

11/15 PDFs mention it, in five incompatible forms:

| Form | Example |
|---|---|
| Structured amenity | "Outdoor swimming pool (depth approx. 4.5 ft)" |
| Explicit negative | "The property does not have a swimming pool" |
| Hedged negative | "The current website does not promote a swimming pool" |
| Room category only | "Grand Chalet with Plunge Pool", "Deluxe Pool View" |
| Typo | "Swiming Pool Small Sized" |

Needs negation handling plus room-vs-property disambiguation. Must become an extracted boolean field.

### Group affiliation — present, unstructured

"Taj Hotels – IHCL", "a Morgans Originals hotel", "IHCL under ama Stays & Trails", "Sawai Hospitality". Answerable once extracted.

### Contradictions in the pilot data

- Oberoi Hotels PNG (Sep 2024) says Rajgarh Palace *"should open by March 2025"*; `Oberoi Rajgarh Palace Property Update.pdf` describes it operating with full room inventory. Both in scope.
- Sawantwadi Palace and Kurja Jawai share a **character-identical sentence** about spa/library being "upcoming additions". One is likely wrong.
- Stale forward claims: *"By the second week of January, property is expected to have all facilities including the Spa fully operational."*

---

## 8. Architecture — hybrid retrieval

Both layers built in phase 1, so phase 2 (Experiences, wider drive) is data ingestion, not re-architecture.

**1. Structured property table — filter layer.**
49 rows × ~40 fields. Star/category, pool, spa, group, room count, price band, distances, season. SQL over 49 rows returns *all* matches, not a top-k sample.

**2. Vector index — semantic layer.**
~400–600 chunks of prose. For open-ended questions: "which lodges suit birders", "somewhere quiet for a couple".

### Routing rule

**Filter and aggregate questions never route through vector search.**

"Which properties have a pool" over a vector index retrieves 5 chunks and misses 44 — then answers confidently, in front of the head of sales.

| Question type | Route |
|---|---|
| Countable / filterable | SQL over property table |
| Descriptive / open-ended | Vector retrieval |
| Both | Run each, merge |

The router is the piece to get right in the eval pass.

### Storage

- **pgvector on Neon** — same DB as the property table. No new service, no added cost.
- **Embeddings via `gemini-embedding-2`** ($0.20/1M) — already in the stack for extraction, so no third vendor. ~₹1.40 to embed the whole corpus.
- **Folder path captured as metadata** on both the property row and every chunk. The team declined to restructure by location, so "hotels in Satpura" only works if the path is indexed.

---

## 9. Stack

| Layer | Choice |
|---|---|
| Frontend + backend | Next.js on **Render Starter**, single service |
| Database | **Neon** (property table + pgvector + query logs) |
| Region | **Singapore** — Render is single-region, closest to Delhi |
| Answering model | **`claude-sonnet-5`** |
| Extraction | **`gemini-3.1-pro-preview` + `claude-sonnet-5`**, cross-checked |
| Embeddings | **`gemini-embedding-2`** |

**Ingestion runs offline** — one-time local batch, results pushed to the DB. No Python service in production.

**Do not use Render's free tier.** Free services spin down after 15 min idle, ~50s cold start. A salesperson waits 50 seconds and reports the tool is broken. Starter ($7/mo) has no spin-down.

### Extraction — AI model for both PDFs and PNGs

Same pipeline for all 52 files. One code path, not two.

**PDFs get image + text together.** Render each page to an image *and* pass the PyMuPDF-extracted text in the same call. The image gives reading order and layout; the text guarantees character accuracy on values like "4.5 ft" and "203 km" where a vision misread is silent and permanent. Neither alone does both.

**PNG tiling.** PNGs are 794 × ~3,200px. Past ~2,576px on the long edge they get downscaled, shrinking already-small 96 DPI text. Slice into ~1,100px strips at native width — ~3 tiles per file, ~111 total.

**Cross-model QA.** Extraction errors are permanent — a misread room count or missed "does *not* have a pool" is baked into every future answer. Running one model twice correlates errors. Run Gemini and Sonnet 5 separately and diff the JSON: agreements across two different models are near-certainly right, only disagreements need human eyes. Adds ~₹130.

### Verified model IDs and pricing (checked 17 Aug 2026)

| Model | ID | Input /1M | Output /1M | Status |
|---|---|---|---|---|
| Gemini 3.1 Pro | `gemini-3.1-pro-preview` | $2.00 | $12.00 | **Preview** |
| Gemini 3.7 Flash | `gemini-3.7-flash` | $0.75 | $3.75 | GA |
| Gemini Embedding 2 | `gemini-embedding-2` | $0.20 | — | GA |
| Claude Sonnet 5 | `claude-sonnet-5` | $3.00 | $15.00 | GA |

Gemini 3.1 Pro re-rates the **whole request** to $4.00/$18.00 above 200k context. Our tiles and pages are far under that, so standard rates apply.

**On preview status:** `gemini-3.1-pro-preview` is not GA. That is acceptable *only* because extraction is a one-time offline batch — it runs once and the script is throwaway. **Do not put a preview model in the answering path.** Sonnet 5 answers; Gemini only extracts.

**Batch API is 50% off** on Gemini. Extraction has no latency requirement, so it fits batch exactly — halves the ingestion cost.

---

## 10. Costs

### One-time

| Pass | Model | Cost |
|---|---|---|
| 37 PNGs → ~111 tiles (151k in / 33k out) | `claude-sonnet-5` | $0.95 |
| 15 PDFs → 22 page-images + text (121k in / 14k out) | `claude-sonnet-5` | $0.56 |
| Both, second pass for cross-check | `gemini-3.1-pro-preview` | $1.11 |
| ~500 chunks embedded (~80k tokens) | `gemini-embedding-2` | $0.02 |
| **Total, both models + embeddings** | | **$2.64 ≈ ₹230** |

Halves to ~₹115 on Gemini's Batch API. Budget **₹1,500** for the build including re-runs — re-embedding on every schema change costs ₹1.40, so don't optimise around it.

### Monthly

Per query: cached property-table read + fresh prose + answer ≈ **$0.024 ≈ ₹2.10**

At 50 queries/day (~1,100/month), 1-hour cache TTL:

| | |
|---|---|
| Inference (Sonnet 5) | ₹2,500–4,000 |
| Render Starter | ₹620 |
| Neon | ₹0 |
| **Total** | **₹3,100–4,600** |

Quote **₹5,000/month with a usage cap**, separate from the pilot fee.

---

## 11. Timeline

**8–10 working days.**

| | Days |
|---|---|
| Four templates → one schema | 2–3 |
| Extraction: 37 PNGs + 15 PDFs | 2 |
| Amenity normalisation (negation, room-vs-property, typos) | 1–2 |
| Hybrid retrieval + router + citations + grounded refusal | 1–2 |
| Frontend + deploy | 1 |
| Eval against the 15–20 sales questions | 2–3 |

Ingestion and schema, not retrieval or frontend.

**Client-facing: keep 4–6 weeks.** The gap is client latency — questions arrive, Nazim's team tests on their schedule, feedback, fix, retest. Two weeks against a six-week commitment reads as excellent; the same work against a one-week promise reads as late.

---

## 12. Raise before quoting

Technical risk is low. Data risk is high and specific:

> Star rating does not exist in any of the 52 files. Pool is unreliable in four of the five forms it appears in.

If the 15–20 questions lean on star ratings and amenity filters — which, given Ravi's framing, they will — **the pilot fails on data coverage, not on the build.**

Fix sits on their side: product team adds a structured block to the template — star/category, pool Y/N, spa Y/N, group, room count, price band. A few hours to retrofit 49 docs.

Agree it **before the number goes out**, so a data gap doesn't read later as a build failure.

---








okay for the A1 answer, you are asking what is inside the 300+ GB of data. Generally I do not know but the structure of the data can be:
- PDF
- images
- scanned PDF
- words
Most of them are similar to what we have but I am not sure about it so I can't confirm anything.

For A2 you are asking who had created the Phase 2 document. What is the Phase 2 document? I genuinely do not know. Please tell me. 

For A3 what types of data beyond the hotels? I do not know. Data can be anything which the travel agency needs so you have to research it.
I want to make a system which is not completely dependent on the structure of the data. The injection part is so goated and the database is so goated. It should be able to retrieve, for any question asked, whatever answer related to that question is present in the database. It should be able to find it not like it got hallucinated. I can't afford that. 

For A4 I do not think this spreadsheet will come but maybe on the safe side it may be. 

I liked your A5 question. You are thinking correctly for the future. You are asking me: suppose they update their data to 2027 rather than only the previous year, how is it going to be? I genuinely do not know. For now I think this will be the upcoming feature.

For now you can say that if something gets deleted it gets notified in the backend and the backend should know what got deleted. In place of it if anything is there then it should be replaced automatically. Genuinely do not put it in the current phase. Put it in the later ones, okay? 

Now Group B, B1, your question: Will any document be scanned or photographed as paper? It will be, yes, but is it really something concerning? I do not think it will be handwritten but something properly structured and easy to read, I guess. Maybe non-English things also. I do not know much but ideally all the things will be in English. 

Okay we can review the extracted data. For the 300 GB it will be very painful work but we can. For now for this phase, we have to focus on making the data we have proper and the system work properly. 
B4. I do not know the costing. Costing can be variable according to the quality, right? I need good quality but also not an overly overpriced thing. According to you tell me the best models for vision. I have seen that Opus is good but it is too expensive. Gemini is good but I do not know how good it is. Is it good to use it and are there any other things you can tell me? 
|
Now, Group C, C1: yes, the perfect recalls and never-wrongs will always be correct, okay? Also the answer will not be on a single line. It can be in multiple places. The tables should be so good that whatever data we give, it goes to the LLM before answering it so the LLM will be able to give the proper answer from the context it gets. 
Yes I highly think that you are saying right, Ned. 100% recall can't be there but the maximum, like 99%, 98%, can be there, right? I want to achieve that with proper retrieval.

I was also thinking: this is for the frontend part. Suppose they have asked the question and we get the answer, so we should give the reference to the image or PDF, the data, and all those things, okay? Can we do that? If it is wrong, the user's sales team actually can see live. 
Most importantly for the C2, I need the accuracy not the fastest. It should be fast but if fast can cause the wrong answer, then it will cost the travel agency lots of money and lead to the loss of customers. We do not need that, okay? We have to properly think about how it is going to be working, okay? All those things: how is it? Is there any eval loop or anything like that? 
For C3 I did not get your question properly but I am going to answer it. If it properly answers your question then good. If not, ask me again, okay?

Are you asking me for the different answer format for each question? That's why, in the middle of the retrieval and giving the answer, we are using a good LLM call. It will be able to see the retrieved answer and, according to the question, it can properly modify it or, you can say, make the proper answer that the user can easily read and understand. That's why. 

If the answer is not available in the data, it should not be giving anything. It should always say, "I do not have this data," or something like, "If the question is not complete, like just what the user has asked, which vehicle is available?" If it doesn't give any context and in that chat there is no previous message regarding the place, then it should ask the user which place or anything like that (which hotel) he is referring to. 
For your C5 yes, if the answer is related to the date, then it should refer to the date also, okay? 
TFor D2 I think the client is going to give us complete data but you do not have to worry about that. You must worry about this: we have to make the database or data structure right now so that whatever data is going to be coming, we can inject everything and retrieve everything. Is it possible genuinely? 
Also do not worry about the D3 question. 
Do not assume anything. If you have any other confusion or any other questions, please ask me. he user will be less. You can think of how many employees are in a sales team of travel agents, at most 10 or 20. 
For D2 I think the client is going to give us complete data but you do not have to worry about that. You must worry about this: we have to make the database or data structure right now so that whatever data is going to be coming, we can inject everything and retrieve everything. Is it possible genuinely? 
Also do not worry about the D3 question. 
Do not assume anything. If you have any other confusion or any other questions, please ask me. 