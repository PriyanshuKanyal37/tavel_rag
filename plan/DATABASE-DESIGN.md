# 🏛️ Travel Inn — System Architecture

**What we are building, and why each decision was made.**

| | |
|---|---|
| Author | Priyanshu · 4 September 2026 |
| Status | Design settled · 4 client answers pending · 1 test to run |
| Audience | Anyone who needs to understand or challenge the design |

---

# 1. 🎯 What we are building

A question-answering system over Travel Inn's own documents, for their sales team.

```
   Salesperson types a question
              │
              ▼
   ┌──────────────────────────────────────────┐
   │  System finds the answer in their own    │
   │  documents — and shows the exact page    │
   │  it came from.                           │
   └──────────────────────────────────────────┘
              │
              ▼
   If it isn't in the documents, it says so.
   It never fills the gap with a guess.
```

**Three constraints shape every decision below:**

| | Constraint |
|---|---|
| 📈 | 52 files today. **300–500 GB later, of content nobody can describe yet.** |
| 🎯 | A wrong answer costs a client quote. **Silence is acceptable. Invention is not.** |
| 🤝 | At the end, everything transfers to the client's own accounts. |

---

# 2. 🧠 First principles — deriving the design

Ignore everything already built. **Any** system that answers questions from documents must solve four problems. Here they are, and here is what each one forces.

---

## Problem 1 — How does a document become knowledge?

A PDF is pixels and text. A question is a sentence. Something must bridge them.

**Two possible times to do the work:**

```
   ┌─────────────────────────────────────────────────────────┐
   │ ⓐ AT QUESTION TIME                                       │
   │    Read the documents fresh, every time someone asks.   │
   │                                                         │
   │    ✅ Always current. Nothing to maintain.               │
   │    ❌ Slow — 20+ seconds before the answer starts.       │
   │    ❌ Expensive — pay to re-read everything, every time. │
   │    ❌ Impossible at 300 GB. Nothing that large fits.     │
   ├─────────────────────────────────────────────────────────┤
   │ ⓑ AT INGESTION TIME  ← our choice                        │
   │    Read each document ONCE. Store what it says.         │
   │                                                         │
   │    ✅ Fast — questions touch only the store.             │
   │    ✅ Cheap — read once, answer forever.                 │
   │    ✅ Scales — 300 GB is an ingestion job, not a limit.  │
   │    ❌ Must re-ingest when a document changes.            │
   └─────────────────────────────────────────────────────────┘
```

**We tested (a) rather than assuming.** Measured evidence: giving a model an entire document set performs *worse* than giving it a curated slice — 34.3 vs 47.3 on the same model, same documents. More context is not more information; past a point the right answer gets buried.

> **Decision 1: extract once, at ingestion.**
> **We would revisit if:** the corpus stayed permanently tiny and changed hourly. It won't.

---

## Problem 2 — What shape does that knowledge take?

This is the hardest question, because **we don't know what's coming.** Today: hotels. Later: parks, roads, permits, vehicles, rate cards.

**Why the obvious answer fails.** Take one content type — safari zones:

| Park | Zones | Vehicles | Modes |
|---|---|---|---|
| Ranthambore | 10 **numbered** | jeeps + canters, but **not** in zones 7–8 | jeep, canter |
| Bandhavgarh | 6 **named** | jeeps + only 2 canters | jeep, canter |
| Kaziranga | **ranges**, not zones | — | jeep, 🐘 elephant, 🛶 boat |
| Periyar | — | — | boat, canoe, jeep, 🥾 walking |

```sql
   create table safari_zones (
     zone_number      int,      -- ❌ Bandhavgarh's are names
     canter_available boolean   -- ❌ true, except zones 7-8
   );                           -- ❌ and Kaziranga has boats
```

**A fixed column list fails on the second park.** And this is one content type out of roughly twenty.

**So the storage must be shapeless.** But shapeless storage cannot be filtered or counted, and *"which properties are under ₹25,000"* is the question that produces a quote.

**Resolving the contradiction — separate what we store from how we query it:**

```
   ┌────────────────────────────────────────────────────────┐
   │  WRITE SIDE — completely open                          │
   │                                                        │
   │  {"room_count": 12, "safari_mode": "boat",             │
   │   "closed_months": "Jul-Sep", "permit": "ILP"}         │
   │                                                        │
   │  New document type = new keys. Nothing to change.      │
   ├────────────────────────────────────────────────────────┤
   │  READ SIDE — typed where it matters                    │
   │                                                        │
   │  When a key gets asked about constantly, PROMOTE it    │
   │  to a real indexed column — one line of SQL, no        │
   │  table rewrite, reversible.                            │
   └────────────────────────────────────────────────────────┘
```

> **Decision 2: schema-free writes, typed reads. The schema is discovered from what people ask, not guessed in advance.**

**One thing this makes mandatory.** Shapeless storage without a controlled vocabulary is chaos:

```
   "swimming pool" ─┐
   "outdoor pool"  ─┼─▶ three different keys, one real fact
   "pool"          ─┘
              ▼
   "How many have a pool?" finds one third of them —
   and reports the count with total confidence. 🔴
```

Our own audit found **pool stated five different ways** across just 52 files. So: one table lists every allowed key. The extractor may write only those. Anything new goes to a human, gets a canonical name, and every future document uses it.

> **Normalise the key, not just the value.**

---

## Problem 3 — How do we find the right knowledge?

Sales questions are **not all the same kind of question**, and this is the insight the whole retrieval design rests on.

```
   ┌──────────────────────────────────────────────────────────┐
   │ "How are the roads to Kanha?"                            │
   │  ➜ the answer is a SENTENCE someone wrote                │
   │  ➜ needs MEANING matching                                │
   ├──────────────────────────────────────────────────────────┤
   │ "Which properties are under ₹25,000?"                    │
   │  ➜ the answer is ARITHMETIC over every property          │
   │  ➜ needs EXACT comparison across ALL rows                │
   ├──────────────────────────────────────────────────────────┤
   │ "Which lodge is closest to Mukki gate?"                  │
   │  ➜ the answer is a RANKING over a relationship           │
   │  ➜ needs SORTING by a joined value                       │
   └──────────────────────────────────────────────────────────┘
```

**Why one method cannot serve all three.** Semantic search works by turning text into a point in space and finding nearby points. Two things break:

```
   ① The document says "₹12,500". The question says "under ₹25,000".
      As text, these share almost nothing. Embeddings compare
      MEANING, not MAGNITUDE. There is no direction in that space
      for "less than".

   ② Semantic search always returns exactly k results.
      Ask for 20, get 20 — whether 3 match or 300.
      It ranks. It does not count.
      "How many" is not a question a ranking system can answer.
```

Measured: semantic search scores **0%** on counting questions — not "poor", *zero*. And **32%** on questions combining several conditions, where structured querying scores **86%**.

**So we run three retrievers, and route between them:**

| Retriever | Answers | Fails at |
|---|---|---|
| 🔢 **Structured** | filters, counts, comparisons, sorting, "list all" | anything not extracted as a field |
| 🔤 **Keyword** | exact names, numbers, rare words | paraphrases |
| 🧠 **Semantic** | meaning when the words don't match | numbers, counting, exhaustiveness |

> **Decision 3: route by question type. Three retrievers with three different failure modes, so they don't fail together.**

**The routing rule matters more than it looks.** It must trigger on *any* filter — not only on the word "how many":

| Question | Route |
|---|---|
| "How many have a pool?" | 🔢 structured |
| "Pet-friendly places in Kanha" | 🔢 **structured** — a filter, even though it reads like a search |
| "Anything with a pool near a gate?" | 🔢 **structured** — two filters and a relation |
| "How are the roads?" | 📝 prose |

Rows 2 and 3 are the everyday sales questions. A narrow rule sends them to the path that fails.

---

## Problem 4 — How do we know the answer is true?

Three layers, because no single one is sufficient.

```
   ① THE MODEL CANNOT DRAW ON ANYTHING ELSE
      It sees only retrieved text. Not its training data,
      not the internet, not a plausible guess.

   ② EVERY CLAIM IS CHECKED BEFORE DISPLAY
      Does the cited sentence actually support this claim?
      No match ➜ the claim is deleted, not softened.

   ③ THE HUMAN CAN VERIFY IN TWO SECONDS
      Every answer carries a link that opens the real document,
      scrolled and highlighted at the exact spot.
```

**Layer ③ is the one that actually makes this trustworthy.** Not because the machine is perfect — because a person can confirm it instantly, and will, on anything that matters.

**What we can and cannot promise:**

| | |
|---|---|
| ✅ Say | *"It answers only from your documents, and shows the exact page for every claim."* |
| ❌ Never say | *"100% accurate."* · *"No hallucination."* |

Commercial legal-AI products sold as hallucination-free measure at **17%** and **33%**. Google's best grounded product measures ~**13%**. That promise is not available to anyone. Ours is a promise about **architecture**, which we control.

---

# 3. 🗺️ The architecture

## Ingestion — happens once per document

```
   📄 PDF / image
        │
        ▼
   ┌────────────────────────────────────────────────────────┐
   │ ① OCR                                                  │
   │    Every word, with its exact position on the page.    │
   │    Deterministic — an engine measuring pixels, not     │
   │    a model guessing coordinates.                       │
   └────────────────────────────────────────────────────────┘
        │
        ▼
   ┌────────────────────────────────────────────────────────┐
   │ ② VISION MODEL reads the page                          │
   │    Sees the image AND the OCR text together.           │
   │    Returns: full transcription + typed facts, each     │
   │    with the sentence that proves it.                   │
   └────────────────────────────────────────────────────────┘
        │
        ▼
   ┌────────────────────────────────────────────────────────┐
   │ ③ ANCHOR each fact to the page                         │
   │    Match the value back to ①'s coordinates.            │
   │    We never trust the model's own idea of where        │
   │    something is on the page.                           │
   └────────────────────────────────────────────────────────┘
        │
        ▼
   ┌────────────────────────────────────────────────────────┐
   │ ④ SECOND MODEL verifies                                │
   │    Different vendor ➜ different mistakes.              │
   │    Where they disagree ➜ a human decides.              │
   │    (This step is what takes ~97% to ~99%.)             │
   └────────────────────────────────────────────────────────┘
        │
        ▼
   💾 stored: facts · evidence · transcription · embeddings
```

## Answering — happens per question

```
   ❓ "Which heritage places in Jaipur are under ₹20k,
       and how are the roads?"
        │
        ▼
   ┌────────────────────────────────────────────────────────┐
   │ ① UNDERSTAND                                           │
   │    Split into parts. Resolve "there"/"it" from the     │
   │    conversation. If genuinely ambiguous — ASK,         │
   │    don't guess.                                        │
   └────────────────────────────────────────────────────────┘
        │
        ├──▶ 🔢 structured   city=Jaipur, heritage, price<20000
        ├──▶ 🔗 relations    distance to airport / gate
        ├──▶ 🔤 keyword      exact names and numbers
        └──▶ 🧠 semantic     "how are the roads"
                    │
                    ▼
   ┌────────────────────────────────────────────────────────┐
   │ ② MERGE and RERANK                                     │
   │    Combine results, reorder by true relevance.         │
   │    (Reranking moves the best result from ~position 8   │
   │     to position 1. Not optional.)                      │
   └────────────────────────────────────────────────────────┘
        │
        ▼
   ┌────────────────────────────────────────────────────────┐
   │ ③ ANSWER — from retrieved text only                    │
   └────────────────────────────────────────────────────────┘
        │
        ▼
   ┌────────────────────────────────────────────────────────┐
   │ ④ VERIFY — every claim against its source              │
   │    Unsupported claim ➜ removed before display          │
   └────────────────────────────────────────────────────────┘
        │
        ▼
   💬 Answer + clickable source for every claim
```

---

# 4. ⚖️ Why these choices — and what would change them

*This is the section to argue with.*

---

## 4.1 Why one database, and why Postgres

**The honest re-derivation.** We need four capabilities:

| # | Capability | Needed for |
|---|---|---|
| A | Exact filtering, counting, sorting | "under ₹25,000", "how many" |
| B | **Joins** | "closest to a gate" — joining entity → relation → distance |
| C | Keyword search | exact property names, numbers |
| D | Vector search | "how are the roads" |

**What each candidate actually gives us:**

| Option | A | B | C | D | Verdict |
|---|---|---|---|---|---|
| **Vector DB alone** (Qdrant, Pinecone, Weaviate) | ❌ | ❌ | 🟡 | ✅ | **Fails the questions that make money.** Cannot count, cannot join |
| **Elasticsearch / OpenSearch** | ✅ | ❌ | ✅ | ✅ | Genuinely strong — best keyword search, native hybrid, real aggregations. **But no joins**, and B is not optional |
| **Vespa** | ✅ | 🟡 | ✅ | ✅ | The most capable single engine. **Rejected on team size** — steep operational cost for a 2-person build |
| **Postgres + a vector DB** | ✅ | ✅ | 🟡 | ✅ | Each part best-in-class. **But two systems to sync, and you cannot join across them** — "under ₹25k AND semantically similar" needs one query, not two round-trips and manual merging |
| ⭐ **Postgres alone** | ✅ | ✅ | 🟡 | ✅ | Every capability in one place, one transaction, one backup, one transfer |

**So the case for Postgres is not "Postgres is good." It is three specific things:**

```
   1️⃣  JOINS ARE NOT OPTIONAL
       "Which lodge under ₹25k is closest to Mukki gate
        and suits birders?"
       ➜ entity + facts + relations, filtered, sorted, in ONE query.
       ➜ Search engines and vector DBs cannot do this. Only a
         relational engine can.

   2️⃣  ONE SYSTEM = ONE TRANSFER
       At handover the client gets a single link and owns
       everything. Two databases = two migrations = two
       chances to fail, and one of them (Cloudflare R2)
       already can't be transferred.

   3️⃣  THE SCALE ISN'T THERE YET
       Phase 2 is ~500,000 entities. pgvector is comfortable
       to 10 million. We are 20× under the limit.
       Choosing a distributed vector database for this is
       buying a truck to carry a bag.
```

**Where Postgres is genuinely weaker — stated plainly:**

| Weakness | What we do |
|---|---|
| Its full-text search is **not true BM25** — ranking is cruder than Elasticsearch | Add a proper BM25 extension, or let the reranker compensate. Measure first |
| Vector index building is **memory-hungry** | Use half-precision vectors, embed at section level not fine chunks |
| No built-in reranking | Reranking is an API call anyway, not a database feature |

**🔀 What would change this decision:**

> **If phase 2 turns out to be tens of millions of vectors**, the vector layer moves out — to Turbopuffer, Qdrant, or similar. The design is deliberately built so that this is a swap of one component, not a rewrite. Everything else stays.
>
> **Trigger:** vector count crosses ~10 million, or index build time exceeds the maintenance window.

---

## 4.2 Why not a graph database

The data *is* a graph — properties near airports, inside parks, operated by groups. So why not use one?

| | |
|---|---|
| **Our queries are one hop** | *"What is X's room count?"* · *"What is near Y?"* Relational and graph engines perform identically at 1–2 hops. The gap only opens at 3+ |
| **It breaks the transfer** | The Postgres graph extension isn't available on any managed host we'd use. It means self-hosting, which forfeits the one-click handover |
| **The pattern doesn't hold up** | A note-taking app with exactly our problem shape moved *off* a graph database *to* Postgres — 70% infrastructure cost cut, and it exposed data-quality bugs the "flexible" store had been silently swallowing |

**🔀 What would change this:** questions becoming genuinely chained — *"which permits are valid for this vehicle class on this route in this season."* Three hops. Not our questions today.

---

## 4.3 Why facts are stored as documents, not as rows

The intuitive design is one row per fact: `(entity, key, value)`. We do **not** do that.

```
   Filtering on 3 attributes at once with one-row-per-fact
   means joining the same table 3 times.

   Measured: a document-style column beat that pattern by
   15,000× on lookups, using 3× less disk.

   Documented breaking point: a few million rows.
   Our projection: ~15 million. 🔴
```

Two large e-commerce platforms built on the row-per-fact pattern and both abandoned it. So:

- **Filtering** happens in a single document-style column — fast, indexed, no joins.
- **Evidence** lives in a separate table, read only *after* we know which entity — a direct lookup, never a filter.

> One table for *finding*, one for *proving*. Neither does the other's job.

---

## 4.4 Why the vision model reads pages, but OCR places them

Two different jobs, and the same tool is not best at both.

| Job | Tool | Why |
|---|---|---|
| **Understanding** — what does this page say? | Vision model | Reads layout, icons, tables, context |
| **Locating** — where exactly on the page? | OCR engine | **Deterministic.** It measures pixel positions. A language model *predicts* coordinates, and prediction is the wrong mechanism for something that must be exact |

Model coordinate quality varies enormously — one produces usable boxes, one needs careful setup, one scored **5 correct out of 200**. Rather than depend on that, we take positions from the OCR and use the model only for meaning.

**🔀 What would change this:** if the bake-off shows the vision model's own coordinates are reliable on our documents, we drop the OCR pass and save a step.

---

## 4.5 Why a second model checks the first

Running the same model twice catches almost nothing — it makes the same mistake twice, confidently.

A **different vendor's** model has different training data and different blind spots. Where two disagree is a strong signal something is wrong.

```
   one model                        ~97%
   + second model + human on the    ~99%+
     10-15% they disagree about
```

That last step costs almost no money — it costs a little of your time, on only the fraction that's genuinely uncertain. **Best value in the entire pipeline.**

---

# 5. 🔨 Build order

Each step is measurable against the client's own 186 questions, so nothing is assumed.

| | Step | Proves |
|---|---|---|
| 1️⃣ | Extract all 52 files, human-review the disagreements | Extraction is trustworthy |
| 2️⃣ | Structured queries + keyword search. **No vectors yet.** Run all 186 questions | How far the simple path gets |
| 3️⃣ | Query routing | The right question reaches the right retriever |
| 4️⃣ | **Add vectors — only where step 2 measurably failed** | We know what they bought |
| 5️⃣ | Reranking | Best result at position 1 |
| 6️⃣ | Answer generation + claim verification | Nothing unsupported reaches the user |
| 7️⃣ | Source viewer with highlighting | The salesperson can check in 2 seconds |
| 8️⃣ | Frontend | The part the client actually judges |

**Why vectors come fourth, not first:** every company that built this added embeddings *after* a working structured system. We have 186 real questions to measure with, so the vector layer can be earned rather than assumed.

## A test worth building early

```
   Ask each question TWICE:
     ① through our retrieval  (the real path)
     ② with all 52 files given to the model directly  (the oracle)

   Different answers ➜ our retriever missed something.
```

This is the only way to measure **retrieval completeness** rather than answer quality. A legal RAG system scored 0.91 on answer quality while silently missing a required statute in 1 of 6 answers — because nobody measured this. At ~₹40 per run on our corpus, it's cheap insurance.

---

# 6. 💰 What it costs

**Reading the documents is one-time.** Questions never touch a file again.

| | One-time |
|---|---|
| All 52 files today | **~₹370** |
| If phase 2 is ~30,000 pages | **~₹43,500** |

*At much larger scale, the OCR step moves to a self-hosted open model — compute only, no per-page fee.*

| | Per month |
|---|---|
| Running it, 100–200 questions/day | **₹4,000–8,000** |

**Why 20 users is an advantage:** at this volume we can spend 15 seconds and several model calls on a single question for a few rupees. At 10,000 users we couldn't, and accuracy would have to drop. **The small team size is what makes this level of care affordable.**

⚠️ *Model pricing is moving fast and two of my sources disagree on one figure. Every number gets verified against the vendor's own page before it reaches a client quote.*

---

# 7. ❓ Open

## Needs a decision from the client

| | Question | Consequence |
|---|---|---|
| 1 | Is any data **commercially confidential** — net rates, supplier contracts? | If no: build nothing. If yes: a flag on documents, not a permissions system |
| 2 | When two documents disagree, what should happen? | Recommend: show the newer, flag that an older disagrees. Never silently pick |
| 3 | Chat with history, or a stateless search box? | Changes the UI and the question-understanding layer |
| 4 | Export an answer into an email, with sources? | Changes whether answers are plain text or structured |

## Needs a test

| | |
|---|---|
| 🔬 **Extraction bake-off** | Our images are lower resolution than OCR guidance recommends. They're clean digital renders rather than scans, so it may not matter — **but I won't assume.** 5 files, 3 models, native vs upscaled, scored against hand-read values |
| ⚖️ **Library licences** | The PDF library used in the audit scripts is AGPL — fine for internal analysis, **not for shipping**. Two free permissive alternatives identified; confirm before code depends on them |
| 🏰 **The star-rating theory** | India rates heritage properties on a separate scale from stars. Travel Inn's product is palaces and forts. **This may be why no star ratings appear in the data** — verify before telling the client their data is incomplete |

## Still open from earlier

Data residency · v1 scope · whether the 186-question bank is the acceptance test · **how much of the 300 GB is text rather than photos** (this decides the cost table)

---
---

# 📎 Appendix — Schema

*Reference for whoever writes the migration.*

```sql
-- ═══════════════════════════════════════════════════════════
--  SOURCE FILES — immutable
-- ═══════════════════════════════════════════════════════════
create table documents (
  sha256          text primary key,
  r2_key          text not null,
  title           text,
  doc_type        text,
  doc_date        date,
  page_count      int,
  transcription   text not null,   -- kept forever: re-extraction insurance
  extractor_model text,
  prompt_version  text,
  superseded_by   text references documents(sha256),
  deleted_at      timestamptz,
  created_at      timestamptz default now()
);

-- ═══════════════════════════════════════════════════════════
--  ENTITIES — hotel, park, zone, route, vehicle, permit, anything
--  `facts` is the open write surface AND the filter surface
-- ═══════════════════════════════════════════════════════════
create table entities (
  id             bigserial primary key,
  entity_type    text not null,
  canonical_name text not null,
  aliases        text[] not null default '{}',
  state          text,
  city           text,
  digest         text,             -- one-line summary
  facts          jsonb not null default '{}',   -- SCALARS ONLY, keep under ~2KB
  created_at     timestamptz default now()
);

create index on entities using gin (facts jsonb_path_ops);
create index on entities (entity_type);
create index on entities using gin (canonical_name gin_trgm_ops);

create table entity_documents (        -- one group PDF names many properties
  entity_id    bigint references entities(id),
  document_sha text   references documents(sha256),
  primary key (entity_id, document_sha)
);

-- ═══════════════════════════════════════════════════════════
--  CONTROLLED VOCABULARY
--  The extractor may write ONLY keys listed here.
-- ═══════════════════════════════════════════════════════════
create table attribute_vocabulary (
  key           text primary key,
  display_label text,
  value_type    text not null,      -- bool | number | text | enum
  unit          text,
  entity_types  text[],
  synonyms      text[],
  created_by    text,
  created_at    timestamptz default now()
);

-- ═══════════════════════════════════════════════════════════
--  EVIDENCE — claim + qualifier + reference + rank
--  Read by (entity_id, key). NEVER filtered on.
-- ═══════════════════════════════════════════════════════════
create table fact_evidence (
  entity_id    bigint references entities(id),
  key          text not null references attribute_vocabulary(key),

  -- QUALIFIER: changes what the fact MEANS.
  -- Two rows differing only by scope are NOT a conflict.
  -- "₹50 for Indians" and "₹1,100 for foreigners" are both true.
  scope        jsonb,

  value_text   text,
  value_num    numeric,
  asserted_as  text not null check (asserted_as in
                 ('stated','negated','absent','scoped','hedged')),

  -- REFERENCE: where it came from.
  evidence     text not null,     -- the exact sentence
  section      text,
  document_sha text references documents(sha256),
  page         int,
  bbox         numeric[],         -- 0-1 fractions of page size
  bbox_source  text,              -- 'ocr' | 'model' | 'fuzzy'

  -- RANK: conflict resolution. Never delete a losing claim.
  rank         text not null default 'normal'
                 check (rank in ('preferred','normal','deprecated')),
  confidence   numeric
);

create unique index on fact_evidence
  (entity_id, key, document_sha, coalesce(scope, '{}'::jsonb));
create index on fact_evidence (entity_id, key) where rank <> 'deprecated';

-- ═══════════════════════════════════════════════════════════
--  RELATIONS — typed edges
-- ═══════════════════════════════════════════════════════════
create table relation_types (
  kind       text primary key,    -- near_airport | inside | operated_by | ...
  label      text,
  from_types text[],
  to_types   text[],
  symmetric  boolean default false
);

create table relations (
  from_entity  bigint references entities(id),
  to_entity    bigint references entities(id),
  kind         text not null references relation_types(kind),
  km           numeric,
  minutes      int,
  document_sha text references documents(sha256),
  primary key (from_entity, to_entity, kind)
);

-- ═══════════════════════════════════════════════════════════
--  OPERATIONS
-- ═══════════════════════════════════════════════════════════
create table manual_overrides (
  entity_id bigint references entities(id),
  key       text,
  value     text,
  set_by    text,
  set_at    timestamptz default now(),
  primary key (entity_id, key)
);

create table review_queue (
  id           bigserial primary key,
  entity_id    bigint references entities(id),
  key          text,
  model_a_value text,
  model_b_value text,
  resolved_by  text,
  resolved_at  timestamptz
);

create table queries (
  id           bigserial primary key,
  ts           timestamptz default now(),
  user_id      text,
  session_id   text,
  question     text,
  tools_called jsonb,
  entity_ids   bigint[],
  answer       text,
  citations    jsonb,
  latency_ms   int,
  thumb        smallint,
  thumb_reason text
);

create table embeddings (
  document_sha text references documents(sha256),
  section      text,
  content      text,
  embedding    halfvec(1536),
  primary key (document_sha, section)
);
```

**Promoting a hot key to a real column:**

```sql
alter table entities add column safari_mode text
  generated always as (facts->>'safari_mode') virtual;

create index on entities (safari_mode) where safari_mode is not null;
```

No table rewrite. Computed on read. Reversible.
