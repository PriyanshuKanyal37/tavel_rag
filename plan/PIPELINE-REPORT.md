# 🗂️ Ingestion Pipeline — What Was Built and What It Does

*Run: 8 September 2026 · 51 documents · 2,136 facts · 403 entities · total API spend ≈ ₹30*

How 52 property brochures became evidence-backed facts in Postgres — every stage, every
file, every column, and why the vocabulary can grow without anyone rewriting a prompt.

| | |
|---|---|
| **Reader** | Claude Opus 5 (subagents) |
| **OCR** | RapidOCR PP-OCRv6, local CPU |
| **Embeddings** | `gemini-embedding-2` |
| **Database** | Neon Postgres 18 + pgvector 0.8.6 + pg_trgm 1.6 |
| **File storage** | Cloudflare R2 |

---

# 1. 🔄 What actually ran, end to end

Seven stages. Order matters — each consumes what the previous produced.

| # | Stage | Tool | Cost |
|---|---|---|---|
| 1 | **Inventory & de-duplicate** | `prep.py` | free |
| 2 | **Render and tile** | `render.py` · pypdfium2 · Pillow | free |
| 3 | **OCR the images** | `ocr.py` · RapidOCR | free |
| 4 | **Upload to R2** | `storage.py` | ₹0 (free tier) |
| 5 | **Read every page** | Workflow · 48 Opus subagents | ₹0 (subscription) |
| 6 | **Validate, resolve, load** | `validate.py` · `load.py` | free |
| 7 | **Embed and index** | `embed.py` · Gemini | ≈ ₹3 |

## The numbers

```
   Documents          51        (52 files - 1 duplicate)
   Page tiles        234
   Facts extracted 4,341
   Facts stored    2,136
   Entities          403
   Connections       110
```

## Stage detail

**1 — Inventory & de-duplicate.** Every file is hashed with SHA-1. The hash *is* the
identity, so two byte-identical files collapse to one row automatically. Ramathra Fort
was filed under both `Karauli\` and `Ramathra\` — 52 files, 51 documents.

**2 — Render and tile.** PDFs are vector, so they render at any DPI. The 37 PNGs are
fixed at 794px wide, 96 DPI, up to 5,150px tall — sent whole they get crushed to 397px.
Both are cut into strips at native width so nothing is ever downscaled. Strips overlap
12% so a line of text is never cut in half.

**3 — OCR the images.** All 15 PDFs carried a text layer. All 37 images carried **zero**.
RapidOCR reads them at native resolution and returns text *plus bounding boxes*.

**4 — Upload.** Original file, every rendered tile, and a thumbnail of each — all keyed
by content hash, so re-running never duplicates anything.

**5 — Read every page.** One Opus subagent per document. Each opens its own tiles,
cross-checks against the OCR text, writes structured JSON. **48 agents, zero failures,
86 facts per document on average.**

**6 — Validate, resolve, load.** Ten deterministic rules run before anything is written.
Entities resolve exact → alias → trigram, **blocked by state**. Failures go to the review
queue with a reason, never silently into the data.

**7 — Embed and index.** One 1,536-dimension vector per document plus an HNSW index.
The only stage that spends Gemini credit.

---

# 2. 🤖 Where Gemini went, and why you don't see it

You're right that it's missing. Gemini was the planned reader for every page. **It read
two pages, then I stopped it.**

```
   gemini-3.1-pro-preview
     page 1   in= 3,637   out= 6,523   ₹8.13
     page 2   in= 3,638   out= 7,876   ₹9.67
                          projected across 24 PDF pages  ->  ₹216
```

The pilot had measured **₹2.64 per page**. The real figure was **₹9**, because structured
extraction produces long JSON and Pro charges $12 per million output tokens. The PDFs
alone would have consumed almost your entire remaining balance — and the 37 images
hadn't started.

You had already covered this case: *"If anything goes wrong with Gemini, use Claude
Opus 5 as the extractor also."* A 3× cost overrun is something going wrong.

> **The reasoning behind the swap.** Ingestion happens **once**. The query path runs
> **every day, for every salesperson, forever**. Spending a fixed API balance on the
> one-time job — when a subscription model can do it for free — is the wrong way round.
> Your ~₹275 is now reserved for answering questions.

## Who does what now

| Job | Runs on | Cost | Status |
|---|---|---|---|
| Reading documents | Claude Opus 5 subagents | ₹0 | 51/51 done |
| OCR text layer | RapidOCR, local CPU | ₹0 | 37/37 done |
| Verifying facts | Claude Opus 5 subagents | ₹0 | **3/51 — sample only** |
| **Embeddings** | **`gemini-embedding-2`** | ≈ ₹3 | 51/51 done |
| Answering questions *(not built)* | `gemini-3.8-flash` | ≈ ₹0.95/question | next phase |

So Gemini is genuinely present — it produced all 51 document vectors — but that is a
single quiet stage, which is why it isn't visible in the run.

---

# 3. 🔬 Is the OCR actually any good?

Yes — measurably, and it beat the technique everyone recommends.

RapidOCR runs PP-OCRv6 through ONNX on the CPU. No GPU, no API, no per-page cost.
Across all 37 images, mean character confidence was **0.953 – 0.992**.

## The upscaling test, on the worst file in the corpus

| Input | Lines | Mean confidence | Verdict |
|---|---|---|---|
| **Native, no upscale** | 9 | **0.991** | ✅ Best |
| Lanczos ×2 | 9 | 0.987 | Slightly worse |
| Lanczos ×3 | 9 | 0.984 | Worse again |

Standard advice is to upscale small text ~3× before OCR. On these files it **hurt**.
The pages are clean digital exports, not scans — the glyph edges are already exact, so
interpolation only softens them. We read at native resolution.

## Why OCR earns its place three times over

1. **It gives images a text layer.** The PDFs had one; the images had none. Now both do.
2. **It makes the grounding check honest.** Rule 7 asks *"is this quote really on the
   page?"* Checking a model's quote against that same model's transcription is circular.
   RapidOCR is an independent witness that never saw the extraction.
3. **It supplies coordinates.** 1,347 facts carry a bounding box, so the interface can
   show the exact spot on the page a fact came from.

> **One nuance:** where OCR and the vision model disagree, **the image wins**. Opus
> corrected `"JULY 2D15"` → `JULY 2025` and `"245,500"` → `Rs 45,500`. That's the design —
> OCR is precise about characters it reads well and confidently wrong about the rest, so
> it advises rather than decides.

---

# 4. 📁 The code, file by file

Two layers: four shared modules at the root of `backend/`, and the ingestion steps under
`backend/ingest/`. Roughly 1,700 lines.

## Shared foundation

| File | Lines | What it does — and why it exists |
|---|---|---|
| `config.py` | 82 | **Every tunable in one place.** Model IDs, prices, tile heights, paths, credentials. The only file that reads `.env`, so nothing else can quietly depend on an environment variable. |
| `db.py` | 55 | **Neon connections.** Pooled for queries, direct for DDL and index builds — `CREATE EXTENSION` and HNSW builds are unreliable through a pooler. |
| `storage.py` | 84 | **Cloudflare R2.** Owns the file-naming convention. Writer and reader call the same functions, so the two can never drift apart. |
| `schema.sql` | 106 | **The tables.** Re-runnable — every statement is `if not exists`. |

## Ingestion steps

| File | Lines | What it does — and why it exists |
|---|---|---|
| `render.py` | 124 | Turns a source file into the images a model sees. PDF → pages at chosen DPI; image → overlapping strips at native width. |
| `ocr.py` | 113 | RapidOCR wrapper. Returns text, per-line confidence and boxes. `locate()` finds where a quote sits on the page — that's the bounding box. |
| `prompt.py` | 355 | **The extraction contract.** The 43-label vocabulary with a definition and a "not this" for each, the reading instruction, the exact JSON schema. Every reader is given this same file, which is what makes Gemini and Opus interchangeable. |
| `prep.py` | 121 | Runs render + OCR + upload for the whole corpus and writes a manifest. Costs nothing, so it can be re-run freely. |
| `jobs.py` | 55 | Splits the manifest into one small job file per document, so a subagent gets only its own tiles and its own text. |
| `extract.py` | 188 | The Gemini path: resumable, budget-capped, retries transient errors but never a 429. *Currently unused — kept so the pipeline doesn't depend on one vendor.* |
| `merge_claude.py` | 78 | Folds subagent output into the same shape Gemini produces, so the loader cannot tell which model read a document. |
| `validate.py` | 284 | **The ten rules.** Every one exists because a real model got it wrong on your real files. Has a runnable self-check. |
| `load.py` | 291 | Entity resolution and the write into Postgres. Also derives connection edges and attaches bounding boxes. |
| `embed.py` | 72 | One vector per document plus the HNSW index. |
| `run.py` | 89 | The command line: `schema · extract · load · embed · status · reset`. |
| `tiling_test.py` | 150 | The three-way bakeoff that decides tile height. Not part of a normal run. |

## Everyday commands

```bash
python -m backend.ingest.run status          # what's in the DB and the bucket
python -m backend.ingest.prep --reader claude   # render, OCR, upload
python -m backend.ingest.load                # validate + write
python -m backend.ingest.embed               # vectors + index

python -m backend.ingest.validate            # self-check: the ten rules
python -m backend.ingest.render              # self-check: tiles cover, no gaps
python -m backend.ingest.ocr                 # self-check: OCR + box location
```

---

# 5. 🗃️ The database, table by table

Seven tables. The shape is deliberate: **facts are rows, not columns.** A new kind of
information adds rows, never a schema migration.

## How the pieces relate

```
   documents  one source file  --+--  entity_documents  --  entities  one real thing
                                 |                             |
                                 +------  fact_evidence  ------+   one claim + its proof
                                                               |
                                            connections  ------+   property -> airport / park

   attribute_vocabulary   which labels are queryable
   review_queue           everything that didn't qualify, with the reason
```

## `documents` — 51 rows

*One row per source file. The unit a salesperson is shown when they click a citation.*

| Column | What it's for |
|---|---|
| `sha1` | **Primary key — the content hash.** Doubles as the filename in R2, so the same file uploaded twice de-duplicates itself with no extra logic. |
| `rel_path` | The client's own folder path, e.g. `Karnataka\Kabini\Kaav…`. Their taxonomy is more reliable than asking a model to infer geography, so this is where the state used for entity blocking comes from. |
| `ext` | File type. Decides whether it was rendered as a PDF or tiled as an image. |
| `page_count` | Pages for a PDF, tiles for an image. |
| `is_tiled` | Whether it was cut into strips. Needed to map a fact back to a position on the original page. |
| `transcription` | What the vision model read. Every word on the page. |
| `text_layer` | The PDF's embedded text, or the OCR output for an image. **Independent of the model** — this is what rule 7 checks quotes against. |
| `ocr_engine` | Which OCR produced it. Lets you re-run one engine's output without touching others. |
| `extractor` | Which model read this document. Makes a bad batch traceable to its reader. |
| `embedding` | `vector(1536)` — the meaning vector for similarity search. |
| `superseded_by` | When a revised brochure arrives the old one is **not deleted** — it points at its replacement. A disagreement between two versions stays visible instead of one silently winning. |
| `created_at` | When it was ingested. |

## `entities` — 403 rows

*One row per real-world thing: a hotel, a park, an airport, a destination. This is what
a question is about.*

Breakdown: 136 destinations · 74 hotels · 51 parks · 48 airports · 44 other · 19 groups ·
19 railheads · 12 experiences.

| Column | What it's for |
|---|---|
| `entity_type` | hotel · destination · park · airport · railhead · group · experience · other. Lets you ask *"which hotels…"* without matching a park of the same name. |
| `canonical_name` | The name we settled on. |
| `aliases` | Other names the same thing appears under, so "KAAV" and "Kaav Safari Lodge" resolve together. |
| `state` / `city` | **The safety mechanism.** Two properties in different states are never merge candidates however similar their names. Without this, KAAV Safari Lodge (Karnataka) merged into The Safari Lodge Kanha (Madhya Pradesh) — 1,500 km apart. |
| `digest` | A short summary, for showing a property in a list. |
| `facts` | `jsonb` — a flat mirror of the simple values, e.g. `{"room_count": 12, "has_pool": "true"}`. This is the **fast filter path**: *"properties with a pool under 20 rooms"* reads this one column instead of joining thousands of evidence rows. |
| `room_count` | A **generated column** pulled out of that JSON and indexed. This is how a label gets promoted to a real database column with no migration and no table rewrite — the pattern any future label follows. |

## `fact_evidence` — 2,136 rows

*The heart of the system. One row per claim, and **every claim carries its own proof**.
Nothing here is ever a bare assertion.*

| Column | What it's for |
|---|---|
| `entity_id` | Which thing this is about. |
| `key` | The label, e.g. `room_count`. Must exist in the vocabulary or the fact is held for review. |
| `scope` | **The column that prevents wrong answers.** `{"category":"Deluxe Room"}` marks a value as describing a *part*, not the whole. Without it, `room_count = 12` (the property) and `room_count = 4` (one room type) are indistinguishable and *"how many rooms?"* can answer 4. **389 facts are scoped.** |
| `value_text` | The value as printed — `"203 km"`, `"Oct – Mar"`. |
| `value_num` | The number pulled out, so you can filter and sort. Without this, *"under 20 rooms"* is impossible. |
| `value_unit` | km · hours · minutes · sq.ft. **Not decoration** — this column is what caught 34 drive times stored as hours that were really minutes. |
| `value_currency` | INR · USD · EUR. Prices are meaningless without it. |
| `asserted_as` | `stated` · `negated` · `hedged`. **"No spa" is a fact; silence is not.** 24 facts are negations, and *"indicative price"* is recorded as hedged rather than as a firm number. |
| `evidence` | The exact words from the page. This is what gets shown to the salesperson. |
| `evidence_type` | `text` or `visual`. Visual facts came from an icon, tick, map or chart — and are held to a stricter rule. |
| `page` | Which page or tile. Together with `sha1`, this locates the source image in R2. |
| `bbox` | Where on that page the evidence sits. **1,347 facts have one**, which is what lets the interface crop and highlight the exact line. |
| `sha1` | Which document it came from. |
| `section` / `block_kind` | Which part of the page — "QUICK FACTS", and whether it was prose, a key/value box, a list or a table. A value from a labelled box is more trustworthy than one from flowing prose. |
| `confidence` | How sure the reader was. |
| `rank` | `preferred` · `normal` · `deprecated`. When two documents disagree, the loser is **marked, never deleted** — so a contradiction stays auditable. |

## `connections` — 110 rows

*Relationships between entities, so proximity questions are answerable by arithmetic
instead of by reading text.*

| Column | What it's for |
|---|---|
| `from_entity` → `to_entity` | Property → airport, park or station. |
| `kind` | nearest_airport · nearest_park · nearest_gate · nearest_railhead. |
| `distance_km` | Road distance. Makes *"within 50 km of the gate"* a numeric comparison. |
| `duration_h` | Drive time, **always normalised to hours** — the page writes "15 mins" and "2 hours" interchangeably. |
| `sha1` / `evidence` | Which document said so, and the exact sentence. |

## `review_queue` — 2,253 open

*Everything that did not qualify, with the reason. **This is not an error log** — it is
the work list, and the largest part of it is opportunity rather than failure.*

| Reason | Count | What it means |
|---|---|---|
| **new_key** | 1,996 | A real fact whose label isn't in the vocabulary yet. Waiting for promotion, not broken. |
| rule failures | 209 | Genuinely rejected — bad boolean, unfound quote, joined value, photo-inferred visual. |
| possible_duplicate | 48 | Two names that *might* be one property. Flagged for a human, never auto-merged. |

## `entity_documents` — link table

Which documents mention which entities. A group brochure covering eight Oberoi hotels
links to all eight.

## `attribute_vocabulary` — 43 rows

The list of labels that are queryable, each with a `definition` and an explicit
`not_this`. Covered in full below.

---

# 6. 📚 Vocabulary — and how it grows by itself

This is the mechanism that decides whether the system stays useful as the data grows.
Worth understanding precisely, because it is almost always built the wrong way round.

## What it is

A vocabulary is the set of labels a fact may be filed under — `room_count`, `has_pool`,
`airport_km`. There are 43 today, each with a one-line meaning and, where confusable, an
explicit warning:

```
   star_rating
     Official hotel classification issued by a government
     tourism body (HRACC in India).
     NOT a review score. TripAdvisor, Google and booking-site
     ratings go in review_rating, with the source recorded.
```

That second half is not documentation — it is load-bearing. An earlier test filed a
*TripAdvisor* 5-star score as an official government classification. With the definition
in place, the reader got it right and put it in `review_rating` with the source scoped.

> ## 🔑 The rule that makes it scale
>
> **The vocabulary decides what is QUERYABLE. It never decides what is CAPTURED.**
>
> A fact with an unknown label is never discarded. It is extracted in full — value,
> evidence, page, position — and parked in the review queue with the reader's proposed
> name. Nothing is lost while the label list catches up with the data.

## How it grows

```
   reader meets a fact no label fits
         |
   emits  key = "_new",  proposed_key = "wildlife_species"
         |
   loader parks it in review_queue — full evidence intact
         |
   a human promotes the label   (insert one row)
         |
   facts become queryable.  No prompt change. No migration.
```

The corpus has already done this. These are the labels **your own documents asked for**,
ranked by how often they appeared:

| Proposed label | Facts | What it captures |
|---|---|---|
| `room_feature` | 98 | Private plunge pool, four-poster bed, sit-out |
| `location` | 69 | Free-text placement not covered by state/city |
| `wildlife_species` | 47 | Tiger, leopard, red panda — real safari sell |
| `nearby_attraction` | 30 | Monasteries, forts, markets |
| `setting` | 29 | Riverside, hilltop, forest edge |
| `suggested_combination` | 29 | Which properties pair on one itinerary |
| `amenity` | 23 | Facilities outside the `has_*` booleans |
| `alternate_airport` | 22 | **The verifier's fix** — the second airport, kept away from `nearest_airport` |
| `bird_species` | 21 | Named species for birding clients |
| `suggested_routing` | 20 | How to get there in an itinerary |
| `architecture_style` | 17 | Colonial, Rajput, contemporary |
| `market_segment` | 17 | Who the property suits commercially |

Promoting the top dozen moves roughly **1,200 more facts** into the queryable set. Note
what that list is: not guesswork about what a travel corpus might contain, but the corpus
stating its own requirements, with counts.

## Why this survives 300 GB

- **No prompt rewrite.** The reader is told *"use a label if one fits, otherwise propose
  one"*. That instruction doesn't change when the vocabulary goes from 43 labels to 400.
- **No schema migration.** Facts are rows. A new label is one `insert into
  attribute_vocabulary`, not an `alter table`.
- **No re-extraction.** The facts are already stored with full evidence. Promoting a
  label makes existing rows queryable retroactively.
- **Promotion to a real column when it earns it.** If `wildlife_species` becomes a hot
  filter, it follows the `room_count` pattern: a generated column plus an index, with no
  table rewrite.
- **Unknown data types are visible, not silent.** A new document category shows up as a
  cluster of new proposed keys — the review queue tells you the shape of your data changed.

> ## ⚠️ The one thing that does need attention
>
> Promotion is currently **manual**, and deliberately so — an auto-promoting vocabulary
> would accept `star_rating` and `rating` and `hotel_stars` as three different labels and
> quietly fragment the data.
>
> The sensible middle, once volume justifies it: auto-promote a proposed label once it
> appears across *N distinct documents*, with a human only reviewing names similar to an
> existing label. That is a small addition, and the counts to drive it are already being
> collected.

---

# 7. 📦 File storage — how a citation finds its page

Nothing but text goes into the database. Every image lives in Cloudflare R2, and the link
between them is the content hash.

## What's in the bucket

| Prefix | Objects | Contents | Used for |
|---|---|---|---|
| `originals/` | 51 | The client's files, untouched | Source of truth. Never modified. |
| `pages/` | 234 | Every page and tile as PNG | What opens when a salesperson clicks a citation |
| `thumbs/` | 234 | ~40 KB JPEG previews | Instant hover preview |
| `crops/` | — | Cut-out evidence regions | **Not built yet** — the `bbox` data now exists to generate them |

## The naming convention

Keys are **derived** from the content hash, never stored in Postgres:

```
   documents.sha1 = 0743fd01b940...

   originals/0743fd01b940....png           1,697 KB
   pages/0743fd01b940.../p001.png            767 KB
   thumbs/0743fd01b940.../p001.jpg            41 KB
```

Three consequences fall out for free:

- **De-duplication is automatic.** The same file always produces the same key. Ramathra
  Fort exists once in the bucket despite being filed in two folders.
- **Re-running is safe.** `put_if_absent` skips anything already there — no duplicate
  uploads, no wasted bandwidth.
- **Nothing can drift.** Writer and reader both call `storage.page_key()`, so there is
  one definition of where a file lives.

## What happens when a salesperson clicks a source

```
   fact_evidence row:  sha1 = 0743fd01...   page = 1   bbox = [28,1180,400,1400]
         |
   backend checks they're signed in
         |
   storage.page_key(sha1, page)  ->  pages/0743fd01.../p001.png
         |
   storage.presign(key)          ->  signed URL, valid 15 minutes
         |
   browser opens it, bbox highlights the exact line
```

> ## 🚫 Never store a URL in the database
>
> A signed URL **expires in 15 minutes**, so a URL written into a row is stale the moment
> anyone reads it back — and it embeds an access key. Store the hash; mint the URL per
> request. Signing is local HMAC, so there is no network call and no added latency.

## Access, and cost

- **The bucket is private.** Nothing is publicly reachable. A viewer needs no Cloudflare
  account and no keys — they click, and the backend signs a link after checking the session.
- **Signed links are bearer credentials.** For those 15 minutes anyone holding the link
  can open it. That is the correct trade-off, and it's why the expiry is short.
- **Egress is free, permanently.** R2 charges nothing for downloads — twenty people
  opening source pages all day costs ₹0. That is the specific reason for R2 over S3.
- **Storage today is ₹0** inside the 10 GB free tier; at 300 GB it is about ₹430/month.

---

# 8. 📈 Will this hold as the data grows?

Your standing requirement: it must work for whatever arrives later, without rewriting the
prompt, the pipeline or the schema. The honest reckoning:

| Concern | Answer |
|---|---|
| **New kinds of facts** | ✅ **Handled.** Proposed keys → review → promote. No prompt or schema change. |
| **New document layouts** | ✅ **Handled.** The reader reports the page as laid out, not against a template. Group updates with 8–16 properties already worked. |
| **New file types** | 🟡 **Small change.** PDF, PNG, JPEG work today. A new type needs one branch in `render.py` — everything downstream unchanged. |
| **More documents** | ✅ **Handled.** Extraction is per-document and resumable. Ten thousand files is the same code and more time. |
| **Retrieval at volume** | ✅ **Handled to ~10M vectors.** HNSW index in place. Beyond that, a dedicated vector store — far past 300 GB of source. |
| **Loading speed** | ❌ **Needs work.** 13 minutes for 51 documents, because every insert is a separate round-trip to Singapore. `executemany` batching would make it under a minute. Fix before the corpus grows. |
| **Neon free tier** | 🟡 **Watch it.** 512 MB branch limit. Text is tiny (0.045% of source size) but embeddings are not — roughly 6 KB per document. |

---

# 9. 🚧 What is genuinely still open

The run being finished is not the same as the work being finished.

| Item | State | Effort |
|---|---|---|
| **Verification sweep** | 3 of 51 documents checked. The sample found a real systematic bug, so the other 48 are unverified. | free · ~1 hr |
| **Promote the vocabulary** | 1,996 facts waiting. Top 12 labels would release ~1,200. | ½ day |
| **Batch the loader** | 13 min → under 1 min. | 1 hr |
| **Evidence crops** | `bbox` exists on 1,347 facts; the `crops/` generation step isn't written. | ½ day |
| **The query path** | Not started. Retrieval, answering, streaming, citation UI. | next phase |
| **Frontend** | Its own document, still unwritten. | — |

## ❌ Three bugs found this run — all of them mine

**Validation contradicted the prompt.** Rule 8 rejected multi-valued facts the contract
explicitly asks for. 2,797 good facts lost, until fixed. Rejections fell from 2,963 to 209.

**Embeddings silently dropped 7 of every 8.** The API returns one vector for a list of
inputs; the code reported "51/51" while writing 7. Only checking the stored count caught it.

**Drive times stored minutes as hours.** 34 of 85 edges — a 4.3 km airport transfer
reading "15 hours". `fact_evidence` had the units right; only the derived column was wrong.

All three are fixed and re-verified. The pattern is worth noting: **every one reported
success while being wrong.** That is the argument for the review queue and the self-checks.
