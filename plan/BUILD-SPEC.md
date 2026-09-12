# 🔧 Travel Inn — Internal Build Specification

|                                   |                                                                                                                                                                        |
| --------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **For**                     | Whoever builds this — including us in three months                                                                                                                    |
| **Date**                    | 7 September 2026                                                                                                                                                       |
| **Scope**                   | Backend, database, ingestion, retrieval, answering, evaluation                                                                                                         |
| **Not in here**             | Frontend and chat interface — those have their own document                                                                                                           |
| **Document types in scope** | PDFs · images · Office documents ·**spreadsheets**. **No audio, no video.** Confirmed with the client — this materially simplifies the ingestion layer |
| **Companion**               | `CLIENT-ROADMAP.md` is the version for Shivam. This one has the detail                                                                                               |

> **Everything marked ✅ MEASURED was tested on Travel Inn's real files.**
> **Everything marked 🟡 ASSUMED has not been tested and is flagged where it appears.**

---

# 1. 🎯 What we are building, and the promise it makes

A question-answering system over Travel Inn's own documents, for their sales team of about twenty people.

```
   A salesperson types a question in plain English
                    │
                    ▼
   ┌───────────────────────────────────────────────────┐
   │  The answer in a few seconds — and the exact      │
   │  page of the exact document it came from,         │
   │  one click away.                                  │
   │                                                   │
   │  If the answer is not in their documents,         │
   │  it says so. It does not fill the gap.            │
   └───────────────────────────────────────────────────┘
```

## The three guarantees the whole design serves

|       | Guarantee                                           | How it is kept                                                                                                                        |
| ----- | --------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------- |
| 1️⃣ | **It only ever answers from their documents** | The answering model is given retrieved text and nothing else. It has no access to its training data or the internet for these answers |
| 2️⃣ | **Every claim can be checked in two seconds** | Every fact carries the sentence that proves it, the document, the page, and the position on the page                                  |
| 3️⃣ | **Silence rather than invention**             | A claim that cannot be traced to a source is removed or marked unverified before display                                              |

## What must never be promised

> ❌ **Never say "100% accurate" or "no hallucination."**
>
> Commercial AI products sold on exactly that claim have been independently measured at 17% and 33% error. Google's best grounded product measures around 13%.
>
> ✅ **Say instead:** *"It answers only from your documents, and shows you the exact page for every claim."* That is a promise about architecture, which we control.

---

# 2. 🤖 Models — which, where, and why

Chosen by measurement on eleven of the client's own files, nineteen pages, four models compared.

| Step                                | Model                      | Setting                           | Status                     |
| ----------------------------------- | -------------------------- | --------------------------------- | -------------------------- |
| 📖**Read the documents**      | `gemini-3.1-pro-preview` | default                           | ✅ MEASURED                |
| ✅**Check the reading**       | Claude Sonnet 5            | default                           | 🟡 ASSUMED — never tested |
| 🧠**Understand the question** | `gemini-3.8-flash`       | **thinking off**            | ✅ MEASURED                |
| 💬**Write the answer**        | `gemini-3.8-flash`       | **thinking off**, streaming | ✅ MEASURED                |
| 🔍**Verify the answer**       | `gemini-3.8-flash`       | thinking off                      | ✅ MEASURED                |
| 📐**Embeddings**              | `gemini-embedding-2`     | truncate 3072 → 1536             | ✅ MEASURED                |

**Every model ID above is pinned exactly.** No aliases such as `gemini-flash-latest` — Google can repoint those without notice, and we measured one doing exactly that: the alias found 11% fewer facts and ran 23% slower than the pinned model for identical money.

## The one preview model, and why it is acceptable there

`gemini-3.1-pro-preview` is the only Gemini 3.1 Pro that exists — there is no stable release. It carries a preview label, and it appears **only in the one-time ingestion job**:

## What the bakeoff actually showed

|                                         | **3.1 Pro** | **3.8 Flash** | 3.1 Flash Lite |
| --------------------------------------- | ----------------- | ------------------- | -------------- |
| Facts extracted                         | **303**     | 218                 | 131            |
| Things identified                       | **42**      | 32                  | 31             |
| 🖼️ Facts read from icons and pictures | **17**      | 10                  | 13             |
| Quotes traceable to the page            | 99.3%             | **100%**      | 93.2%          |
| Wrong-unit errors                       | **0**       | **0**         | 2              |
| Cost across all 52 files                | ₹174             | ₹52                | ₹5            |
| Time for all 52 files                   | 101 min           | **24 min**    | 57 min         |

**Pro finds 39% more facts and 70% more from images, for ₹122 more across the entire corpus.** Not a real trade-off.

**Flash Lite is disqualified** — roughly one quote in fifteen could not be found on the page.

## The thinking setting — measured, and counter-intuitive

Gemini 3.x models reason internally before answering by default. **Turning it off made answers faster *and* better.**

|                    | Thinking ON             | Thinking OFF                         |
| ------------------ | ----------------------- | ------------------------------------ |
| Time to first word | 4.8s                    | **1.2s**                       |
| Output produced    | **35 tokens**     | **244 tokens**                 |
| Citation quality   | named the property only | **quoted the actual evidence** |

⚠️ **The 35-token result is a bug, not a preference.** The invisible reasoning was consuming the output budget and truncating the answer. We would have shipped incomplete answers and blamed the prompt.

**Rule: thinking off everywhere by default.** 🟡 The one open question is whether genuinely hard synthesis — *"compare these two properties across eight dimensions"* — needs it. That gets tested against the 30 acceptance questions before launch, and if it does, the planner routes those to a thinking-on call.

## The second reader — what testing changed

The original design had Claude Sonnet 5 **verifying** Gemini's output: a second model looking at the first model's answers and confirming them. **Testing showed that is the wrong mechanism.**

```
   ❌ VERIFY
      Sonnet sees Gemini's output and checks it.
      → It can only check what Gemini FOUND.
      → It cannot find what Gemini MISSED.

   ✅ TWO INDEPENDENT READERS
      Both read the page from scratch. Neither sees
      the other's answer. Then merge, and route
      disagreements to review.
      → Each finds what the other misses.
```

**Measured on two of the client's pages, same prompt, same images:**

|                                | Gemini 3.1 Pro                      | Claude Sonnet 5                 |
| ------------------------------ | ----------------------------------- | ------------------------------- |
| Facts found                    | 41 / 28                             | **53 / 46**               |
| Entities found                 | **9 / 5**                     | 4 / 2                           |
| Duplicate facts                | **0**                         | 2                               |
| Used approved labels correctly | **✅**                        | ❌ invented one unnecessarily   |
| Label accuracy                 | **✅ `tripadvisor_rating`** | ❌ filed it as`star_rating`   |
| Evidence precision             | **✅ one span per fact**      | ❌ one span shared by two facts |
| Boolean values                 | ❌ stored as a sentence             | **✅ correct**            |
| Cost per page                  | **₹9.81**                    | ₹18.70                         |
| Time per page                  | **~40s**                      | ~76s                            |

**They are good at different things, and neither is checking the other:**

```
   GEMINI   more DISCIPLINED
            correct labels · zero duplicates · precise quotes
            · finds ENTITIES — airports, stations, destinations,
              which is what makes "closest to" answerable

   SONNET   more THOROUGH
            ~30% more facts, including genuinely valuable ones
            Gemini missed entirely — e.g. "not yet personally
            inspected by our product team"
            — but with noise that must be cleaned first
```

**Gemini stays the primary reader.** For a system where a wrong value costs a client quote, discipline outweighs volume.

**Sonnet runs as a second independent reader**, and its output passes through the same validation as Gemini's. It is never trusted directly — in testing it produced duplicates, joined values, and one confidently mislabelled fact.

⚠️ **This is two pages.** The pattern was consistent across both, which is suggestive. It is not proof. Four or five more pages would settle it, at roughly ₹30 plus $0.40.

### Cost of running both

```
   Gemini across all 61 pages     ₹600
   Sonnet across all 61 pages   ₹1,140
   ───────────────────────────────
                                ₹1,740  one-time
```

**A defensible middle option:** run Sonnet only on pages Gemini flags as uncertain, or on image-heavy pages where icons carry meaning — roughly ₹300 instead of ₹1,140, keeping the cross-vendor signal where it earns most.

## What the structured prompt changed

The first extraction returned a flat blob of text and a flat list of facts. The current one returns the page as it is laid out. **Measured on the same file:**

|                           | flat | structured                             |
| ------------------------- | ---- | -------------------------------------- |
| Facts                     | 17   | **29**                           |
| Entities                  | 1    | **5**                            |
| Sections with block types | —   | **14**                           |
| Typed values              | none | number · quantity · boolean · money |

**What the flat version was silently losing on that one page:**

```
   ✗ usp                    the entire selling proposition
   ✗ park_drive_time        2 hours to Ranthambore
   ✗ one of three "ideal for" bullets
   ✗ has_bar
   ✗ the room breakdown      4 keys @ 300 sq.ft · 6 @ 324 · 2 @ 625
   ✗ three national parks    as entities in their own right
```

**Roughly 40% of the factual content of the page.**

## ⚠️ Prices double on 1 January 2027

```
   Gemini Flash          now        from 1 Jan 2027
   input          $0.75 / 1M   →   $1.50 / 1M
   output         $3.75 / 1M   →   $7.50 / 1M
   cached read    $0.075 / 1M  →   $0.15 / 1M
   cache storage  $0.50/M/hr   →   $1.00/M/hr
```

Every running cost in this document doubles on that date. It must be reflected in anything quoted to the client on a twelve-month basis.

---

# 3. 📦 File storage — Cloudflare R2

Original documents and rendered pages live in R2. **Nothing but text ever enters the database.**

## What is stored

| Folder               | Contents                                       | Purpose                                                    |
| -------------------- | ---------------------------------------------- | ---------------------------------------------------------- |
| **originals**  | The client's PDFs and images, untouched        | The source of truth. Never modified                        |
| **pages**      | Every page rendered as an image at 300 DPI     | What opens when a salesperson clicks a citation            |
| **thumbnails** | Small previews of each page                    | Instant hover preview, loads in milliseconds               |
| **crops**      | Cut-out regions for facts that came from icons | *"We read this as no spa"* — with the actual icon shown |

## The rules

|                                                                      |                                                                                                                                                                                        |
| -------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 🔑**Filenames are the fingerprint of the file's own contents** | The same file uploaded twice produces the same name and de-duplicates itself. This already worked correctly in testing on a document filed in two different folders                    |
| 🔒**Originals are never overwritten**                          | A revised document is a new entry. The old one stays, marked superseded, with its date. This is how a disagreement between two documents stays visible instead of one silently winning |
| 🚫**Nothing is publicly reachable**                            | Every view goes through a short-lived private link issued by our backend after a login check. Links expire in fifteen minutes                                                          |
| 📶**Progressive loading enabled**                              | Large PDFs stream page by page instead of downloading whole                                                                                                                            |

## Cost

```
   Today            250 MB      ₹0     (inside the 10 GB free tier)
   At 300 GB        300 GB      ₹430/month
   Downloads        unlimited   ₹0     ← R2 charges nothing for egress, ever
```

**The zero-egress point is why R2 and not S3.** Twenty people clicking source pages all day would be a metered cost on S3. Here it is free.

---

# 4. 🔄 Ingestion — how a document becomes knowledge

Runs once per document, as a background job. **Nobody waits on it.** It can be stopped and resumed at any point, and already-processed files are skipped.

## Step 1 — Intake

The file's contents are fingerprinted. If that fingerprint already exists, the file is skipped entirely — this is how duplicates handle themselves. Otherwise the original is uploaded to R2 and a document record is created.

## Step 2 — Render

Every page is turned into an image at **300 DPI**, and its embedded text is pulled out where the file has any.

> ⚠️ Below 150 DPI, character accuracy drops under 90%. Below 100 DPI it is unusable. **The client's 37 images are natively around 96 DPI** — clean digital renders rather than scans, so it may not matter, but this is on the list to test rather than assume.

Thumbnails are generated in the same pass.

## Step 3 — Read the page

**One call to `gemini-3.1-pro-preview` per page**, given the page image *and* its extracted text together.

It returns the page **as it is actually laid out**, not as a flat blob:

```
   ① THE DOCUMENT'S STRUCTURE
      title · subtitle · which template it follows
      └── sections, in order, each with its heading
          └── blocks, each labelled with what KIND it is:
              prose · key-value pairs · bulleted list ·
              table · caption · footer

   ② A COMPLETE TRANSCRIPTION
      every word on the page, including text inside
      pictures and graphics

   ③ THE FACTS, each attached to the block it came from
      • which thing it is about
      • a label — approved if one fits, PROPOSED if not
      • the value, TYPED — a number as a number, money
        with its currency, a distance with its unit
      • the EXACT sentence that proves it
      • which section and block it sits in
      • whether it is stated, negated, or hedged
      • whether it came from text or from a picture
      • a structured qualifier, if the fact is conditional
```

### ⚠️ Block types are not cosmetic — they prevent a real error

The client template puts a row of boxes at the top of every page, each with a value above its label:

```
   Karauli, Rajasthan     LOCATION
   2 hours                FROM RANTHAMBORE N.P.
   Oct - Mar              BEST TIME TO VISIT
```

**Read as prose, the model pairs these by guessing.** Two documented ways it goes wrong:

|                            |                                                                             |
| -------------------------- | --------------------------------------------------------------------------- |
| **Cross-pairing**    | *"2 hours BEST TIME TO VISIT"* — a value attached to the wrong label     |
| **Column splitting** | All three values in one run, all three labels in another, nothing connected |

**We already have one confirmed instance of this class of error:** *"4 hours FROM JABALPUR AIRPORT"* was stored as `airport_km = 4`. The value was separated from its unit and its label.

**Asked to return a key-value block as key-value pairs, the pairing becomes explicit** — and a wrong pairing is visible rather than silent.

**Both outputs come from one call.** The model reads the page once; two calls would double the cost for the same reading.

**Because it sees the page rather than just reading its text, it catches facts that exist only as pictures.** Three properties in testing were correctly recorded as having no spa — from a crossed-out massage icon, with no text anywhere on the page saying so.

### The tri-state, and why it matters

| Value                  | Meaning                                             |
| ---------------------- | --------------------------------------------------- |
| **stated**       | The page says it                                    |
| **negated**      | The page says it is**not** available          |
| **hedged**       | The page is vague or conditional                    |
| *(nothing recorded)* | The page is silent — which is not the same as "no" |

*"No swimming pool"* is a fact. Silence is an absence. Collapsing those two into a boolean is how a system tells a salesperson there is no pool at a property that has one.

### Qualifiers — a fact can be conditional

Some facts are only true under conditions:

```
   entry fee ₹50      when nationality = Indian
   entry fee ₹1,100   when nationality = foreign
   pool available     when unit type = villas
   rate ₹24,000       when season = peak
```

**Two facts differing only by qualifier are not a conflict.** They are two correct statements. Without this distinction the system flags them as contradictory and discards one.

### What counts as visual evidence — and what must never be treated as evidence

The documents are travel brochures. **They are mostly photographs** — landscapes, wildlife, rooms, food, vehicles, people. A reader that treats pictures as claims will manufacture hundreds of plausible, unverifiable facts.

**The distinction the system must make on every image:**

```
   ┌───────────────────────────────────────────────────┐
   │  Is this image ASSERTING something,                       │
   │  or is it DECORATING the page?                            │
   └───────────────────────────────────────────────────┘
```

| ✅ The image**is** the statement — extract                | ❌ The image**decorates** — never extract                 |
| ---------------------------------------------------------------- | ---------------------------------------------------------------- |
| Icons in a facilities, features, amenities or inclusions block   | Landscape, scenery, sunset photographs                           |
| Anything carrying a tick, cross, Yes, No or check mark           | Wildlife and animal photographs                                  |
| A table, price grid or chart drawn as a picture rather than text | People, lifestyle and "mood" shots                               |
| A map showing a location, a route, a park boundary               | Vehicles pictured with no claim attached                         |
| A logo indicating a chain, group or certification                | Room and interior photographs with no caption asserting anything |
| A caption that makes a factual claim about what it labels        |                                                                  |

**The test:** would a reader say *the document claims this* — or would they say *I worked it out from the picture*? **If it is the second, it is not a fact.**

> **A photograph never creates a fact on its own.** It can only corroborate something the page already asserts in words or symbols.

### This is already happening, and it is the hardest error to catch

Of the seventeen visual facts produced in the first extraction run, **fourteen were legitimate and three were invented**:

| ✅ Legitimate — the icon IS the claim                                        | ❌ Invented — inferred from a photograph                                                    |
| ----------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------- |
| `has_pool = true` — *"swimming pool ladder icon next to the word 'Yes'"* | `activities = wildlife viewing` — *"photographs showing marmots and brown bears"*       |
| `has_spa = false` — *"massage table icon with the word 'No' next to it"* | `activities = hiking` — *"photograph of a person walking with a backpack"*              |
|                                                                               | `has_restaurant = true` — *"photograph showing a dining room with a long wooden table"* |

**A photograph of marmots is not a statement that wildlife viewing is offered.** A dining room in a picture might be a shared kitchen, a breakfast nook, or someone's private living room.

⚠️ **And these are harder to catch than any other error class**, because the grounding check passes. *"Photograph showing marmots"* genuinely describes the page — the quote is real. **The inference is not.** Nothing downstream of the grounding check would flag it.

---

## Step 4 — Anchor each fact to its position on the page

Each extracted value is matched back against the page's own word positions.

| Match quality | Result                                                                  |
| ------------- | ----------------------------------------------------------------------- |
| Strong        | Exact box around the sentence — a precise highlight                    |
| Partial       | Highlight the whole paragraph,**labelled "approximate location"** |
| None          | No box; flagged for review                                              |

Before matching, both sides are normalised — ligatures expanded, hyphenation across line breaks joined, whitespace collapsed. These are the documented reasons exact matching fails.

> **We never use the model's own idea of where something sits on the page.** A language model *predicts* coordinates; a text-position engine *measures* them. For something that has to be exact, prediction is the wrong mechanism.

For facts that came from a picture, the region is cropped out and stored — the crop becomes the citation.

## Step 5 — Independent check

**Claude Sonnet 5 reads the same page from scratch**, having never seen Gemini's output.

```
   both agree              →  written, marked high confidence
   only one found it       →  written, flagged
   values differ           →  NOT WRITTEN. Goes to human review.
```

🟡 **This step is untested.** The principle is sound and well-supported, but the actual disagreement rate on these files is unknown. It needs an Anthropic key and about ₹250 to close.

## Step 6 — The vocabulary gate

⚠️ **The vocabulary decides what is QUERYABLE. It must never decide what is CAPTURED.**

```
   ① THE MODEL EXTRACTS EVERYTHING FACTUAL IT SEES
      No filtering at this stage. If no approved label
      fits, it proposes one and attaches the evidence.

   ② THE VOCABULARY THEN SORTS IT
      approved label   →  filterable, countable, sortable
      proposed label   →  stored, searchable by meaning,
                          held for a human to name

   Nothing is ever discarded for lack of a label.
```

### Why this rule exists — measured on a real page

Testing on the Ramathra Fort sheet produced 17 facts from a page containing considerably more. **Everything below is plainly printed on that page and appears in the transcription, but became no fact at all:**

| On the page                                                                    | Why it was lost                                                                                                     |
| ------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------- |
| *"USP: Blend of heritage, wilderness, lake views..."*                        | no`usp` label existed                                                                                             |
| *"2 hours FROM RANTHAMBORE N.P."*                                            | no label for distance to a park —**and this is one of the most-asked question types in the client own bank** |
| *"17th-century hilltop fortress"*                                            | no label                                                                                                            |
| *"sits between Keoladeo Ghana Bird Sanctuary and Ranthambore Tiger Reserve"* | no label                                                                                                            |
| *"hosted by the Raj Pal family"*                                             | no label                                                                                                            |
| *"Guests combining Agra, Jaipur and Ranthambore"*                            | one of three bullets under a label that DID exist — silently dropped                                               |

> **Roughly 40% of the factual content of that page never became a fact.** The gate was designed to stop *"pool"* becoming three different labels. As originally built it was also quietly throwing away real information.

### What the gate still does, and must keep doing

```
   "swimming pool" ─┐
   "outdoor pool"  ─┼──▶ three labels, one real fact
   "pool"          ─┘
                    ▼
   "How many have a pool?" finds a third of them —
   and reports the count with complete confidence.
```

Pool is stated **five different ways across just 52 files**. Consistent naming is not optional — it simply must not come at the price of losing what has no name yet.

In testing the model proposed 74 new labels and every one was held for approval. It proposed the same missing label — drive time from the airport — **thirteen separate times**, which told us precisely what the list was missing.

## Step 7 — Identify what the page is about

Each named thing is matched against what we already have:

```
   exact name match           →  same thing
   known short form or alias  →  same thing
   name starts with           →  same thing
   close spelling             →  same thing, ONLY if same state
   anything less certain      →  new record + flagged for review
```

### ⚠️ The rule that came from a real failure

In testing, **Kaav Safari Lodge (Karnataka) was silently merged into The Safari Lodge Kanha (Madhya Pradesh)** — two entirely different properties fifteen hundred kilometres apart — because both names contain "Safari Lodge."

Three fixes, all now mandatory:

|                                              |                                                                                                          |
| -------------------------------------------- | -------------------------------------------------------------------------------------------------------- |
| **Compare only within the same state** | Kabini and Kanha can never be candidates for each other                                                  |
| **Ignore generic words when matching** | *safari · lodge · palace · resort · fort · the* carry no identifying information in this industry |
| **Never merge on a maybe**             | A plausible-but-uncertain match creates a separate record and flags it. It does not merge silently       |

### Short names need an alias list

```
   "Kaav"           vs  "Kaav Safari Lodge"                    → far too low to match
   "Postcard Leh"   vs  "The Postcard in the Himalayan Willows" → worse
```

**These are exactly what people type.** So at ingestion we record, for every property: the short form, the version without "The", the version without the chain prefix, and common misspellings. Spelling similarity is the last resort, never the first.

### Geography comes from the folder path, not the model

The client's folder tree is their own taxonomy and is far more reliable than asking a model to infer location from prose. In testing the model populated state for 8 of 45 things; the folder path gave 30 of 50.

⚠️ **With one caveat found in testing:** the folder tells you the *document's* subject, not every thing mentioned inside it. A Rajasthan document that mentions a Maharashtra property in passing will mislabel it. Only the document's primary subject inherits the folder's geography.

## Step 8 — Break the text into pieces and index it

The full transcription is split on **layout boundaries** — headings, sections, table edges — never mid-table and never at an arbitrary character count.

**Each piece carries its position in the hierarchy before it is indexed:**

```
   ❌ stored as:  "12 rooms, pool, closed in monsoon"
                   whose? where? which season?

   ✅ stored as:  "Rajasthan ▸ Karauli ▸ Ramathra Fort ▸
                   Accommodation ▸ 12 rooms, pool, closed in monsoon"
```

This is worth 49% fewer retrieval failures in published measurement, and it costs nothing.

Pieces are around 800 tokens with **no overlap** — a January 2026 systematic study found overlap gives no measurable benefit, only index cost.

### Two versions of every piece are stored, and both are embedded

```
   RAW
   "Accommodation: 12 units in 3 categories.
    USP: Blend of heritage, wilderness, lake views."
   → the client exact wording, untouched

   PROCESSED
   "Rajasthan ▸ Karauli ▸ Ramathra Fort ▸ 01 Introduction
    Accommodation: 12 units in 3 categories.
    USP: Blend of heritage, wilderness, lake views."
   → findable by "heritage Rajasthan" even though the
     paragraph contains neither word
```

**Why both:** the processed version retrieves far better, but if section detection ever mis-segments a page, the raw text is still searchable. Costs roughly ₹3 across the whole corpus and doubles a table that is about 1 GB at full scale.

⚠️ **The benefit of keeping the raw version is unproven.** Log which version produces the winning result. If the raw path never wins across the 90 test questions, drop it.

### The context prefix is templated, not generated

```
   raw chunk text
        + the document state, city and entity   (already known)
        + the section heading it sits in        (already known)
        ▼
   processed chunk → embed → store
```

**No model call. No cost.** The published version of this technique uses a small LLM call per chunk, because those teams had no document structure to draw on. **We will — the structured extraction returns the hierarchy.** Free and deterministic beats paid and variable when the output is the same.

Each piece is then indexed twice: once for **keywords** and once for **meaning**.

⚠️ **Each stored embedding records which model and which chunking version produced it.** Without that, changing the embedding model or the chunk size means wiping everything and rebuilding with nothing to compare against — and the build order explicitly says *"add meaning-search where it measurably helps,"* which requires holding two versions side by side to measure.

## Step 8b — Validation before anything is written

⚠️ **Nothing goes into the database unchecked.** Every one of these rules exists because a real model got it wrong during testing, on the client's real files. This is what the load step is for.

| # | Rule                                                         | The error it catches                                                                                                                                                                                                                                                                    |
| - | ------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1 | **A boolean must be `true` or `false`**            | Gemini wrote`has_pool = "No swimming pool"` — a sentence in a boolean field. A filter behaves unpredictably against it                                                                                                                                                               |
| 2 | **A distance label must hold a distance**              | *"4 hours from Jabalpur Airport"* was stored as `airport_km = 4`. If the supporting quote is written in hours, the value is not kilometres                                                                                                                                          |
| 3 | **A "nearest X" label is single-valued**               | Two facts both labelled`nearest_airport` is a contradiction — the label means *the closest one*. A second airport needs a scope, and "nearest" is then DERIVED by taking the minimum, not asserted                                                                                 |
| 4 | **Units live in the unit field only**                  | `value: "5 acres"` with `unit: "acres"` means the number cannot be read cleanly from the value                                                                                                                                                                                      |
| 5 | **De-duplicate on entity + label + value + scope**     | Sonnet produced the same fact twice from two different sentences                                                                                                                                                                                                                        |
| 6 | **Reject joined values**                               | `"Eco-certified; strong local community feedback"` is two facts wearing one value. So is any comma-list                                                                                                                                                                               |
| 7 | **The quote must be on the page**                      | Checked against the transcription. A quote that cannot be located is rejected — this held at 167 of 168 in testing                                                                                                                                                                     |
| 8 | **Sub-part facts must carry a scope**                  | `room_count = 12` (the property) and `room_count = 2` (one category) are indistinguishable without it. *"How many rooms?"* could return 2                                                                                                                                         |
| 9 | **A visual fact must cite a symbol, not a photograph** | Evidence must reference an icon, tick, cross, mark, chart, map, logo or caption. Evidence beginning*"photograph showing…"* or *"image of…"* with no tick, label or caption attached is rejected to review. **Three of seventeen visual facts in the first run failed this** |

**A fact failing any rule is not written. It goes to review.** These are cheap deterministic checks that catch what a language model gets wrong — which is precisely why a load step exists rather than writing model output straight through.

### Approved labels need definitions, not just names

This is the other half of the same problem.

```
   ❌  star_rating

   ✅  star_rating
       Official hotel classification issued by a government
       tourism body (HRACC in India).
       NOT a review score. TripAdvisor, Google and booking-site
       ratings go in review_rating, with the source recorded.
```

**A label without a definition attracts the wrong value.** Sonnet filed a *"5-star rating on TripAdvisor"* under `star_rating` — a guest review average recorded as a government hotel classification. Gemini, given the same sentence, proposed `tripadvisor_rating`, which is correct.

Identical failure shape to `airport_km` attracting *"4 hours"*: an under-specified label pulls in a plausible-looking wrong value, and nothing downstream can tell.

**Every approved label carries a one-line definition, and where it is confusable, an explicit "not this."**

---

## Step 9 — Human review

A simple internal screen listing everything held back:

```
   ┌────────────────────────────────────────────┐
   │  Bagh Tola · room count                    │
   │  Gemini read: 12    Claude read: 14        │
   │  [the page image, region highlighted]      │
   │  ( 12 )   ( 14 )   ( neither )             │
   └────────────────────────────────────────────┘
```

Also shown here: proposed new labels awaiting a name, and uncertain property matches.

**This is the highest-value step in the whole pipeline.** Published results put confidence-routed human review at 99%+ end-to-end accuracy while sending only 10–15% of documents to a person. It costs a little of our time on the fraction that is genuinely uncertain.

**Scale for this corpus:** eleven files produced 74 held labels and one uncertain match. Across 52 files that is roughly 350 items — but most are repeats of the same few labels, so perhaps 40–60 distinct decisions. **Budget half a day, and clear it fully before anyone tests the system.**

> ⚠️ *"Where they disagree, nothing is written"* means anything left in this queue is a fact the system will claim not to know, about something plainly printed on the page. Clearing it is not optional.

---

# 5. 🗄️ The database — what it holds and why

**PostgreSQL, hosted on Supabase.** One database. Everything in it — facts, proof, full text, embeddings, connections.

## Why one database rather than a separate vector service

The typical sales question is *"under ₹25,000 **and** closest to Mukki gate **and** suits birders."*

```
   price          a fact
   distance       a connection
   "suits birders" a meaning
                   │
                   ▼
   In one database this is ONE query.

   Split across two systems it is two round trips
   that our code then stitches together by hand —
   and the stitching is where these systems get
   wrong answers.
```

Search engines and vector databases **cannot join**. That single capability is what the quoting question needs, and it is the whole product.

## Why Postgres survives the 300 GB question

**The 300 GB never enters the database. Only text does.**

```
   ✅ MEASURED on their real files:

   113 MB of source PDFs and images
        ↓
   50.8 KB of extracted text        =  0.045%
```

Their files are photo brochures — roughly 2,200 bytes of picture per byte of text.

| At 300 GB of source      |                      |
| ------------------------ | -------------------- |
| Extracted text           | ~230 MB              |
| Facts                    | ~420 MB              |
| Embeddings and index     | ~2.2 GB              |
| **Total database** | **≈ 4–5 GB** |

### ⚠️ One setting that must be switched on deliberately

Filtering before searching is central to the design — and it interacts badly with vector indexes at their default setting.

```
   THE DEFAULT, BROKEN BEHAVIOUR
   "birding lodges in Rajasthan"
        ↓
   the index finds the 20 nearest chunks OVERALL
        ↓
   THEN filters to Rajasthan
        ↓
   maybe 3 survive. You asked for 20 and got 3.
```

**pgvector supports iterative scanning**, which keeps searching until it genuinely has enough results that pass the filter. **It is off by default.** Without it, filtered searches silently under-return — and it presents as *"the search sometimes finds almost nothing"* weeks into a build.

**The honest ceiling:** Postgres handles vector search comfortably to around **10 million** embeddings. The realistic projection is well under one million. If phase 2 turns out to be dense text documents rather than photographs, the embedding column — and only that column — moves to a dedicated service. **One component swapped, not a rewrite.** That boundary is deliberate.

## The nine things stored

### Content

|                                 | Holds                                                                                                                                                                                                                                                                                                                                                         |
| ------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Documents**             | Every source file, its date, whether a newer version supersedes it,**every folder path it was found at** *(the same file appears in two folders in the current data — that is real information about how the client organises things)*, and a **sensitivity flag** so confidential material can be excluded before retrieval rather than after |
| **Pages**                 | The transcription**per page, not per document**. The page number is what a citation needs — flattening it into one blob throws that away                                                                                                                                                                                                               |
| **Things**                | Every hotel, park, zone, route, permit, supplier — names, aliases, geography, and**one flexible field holding whatever facts that particular thing happens to have**                                                                                                                                                                                   |
| **Document–thing links** | Which documents describe which things. One group PDF names twelve hotels; without this the eleven others are lost or the document is stored twelve times                                                                                                                                                                                                      |
| **Text pieces**           | The chunks, each indexed for both keywords and meaning                                                                                                                                                                                                                                                                                                        |

### Trust

|                       | Holds                                                                                                                                                                                                                   |
| --------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Evidence**    | One entry per fact — the exact sentence, which document, which page, where on that page, whether text or picture, any qualifier, a rank, and**when the fact is valid from and until**                            |
| **Connections** | *This lodge is 4 km from that gate. This property sits inside that park.* Typed relationships with distances and times — **and the source document, so two documents giving different distances both survive** |

### Values are typed, not just text

A value can be any of these, and the type is recorded:

| Type                                   | Why it is needed here                                                                                         |
| -------------------------------------- | ------------------------------------------------------------------------------------------------------------- |
| text · number · boolean              | The ordinary cases                                                                                            |
| **date**                         | Permit validity, park closure periods, contract expiry, rate seasons                                          |
| **money with its currency**      | Rates are in rupees, but source-market material quotes dollars and euros. A number alone is ambiguous         |
| **quantity with its unit**       | 203**km** and 203 **minutes** are not the same fact — this is exactly the error found in testing |
| **a reference to another thing** | *"operated by Oberoi"* should point at the Oberoi record, not store the word "Oberoi" as text               |
| list                                   | Multiple activities, multiple room categories                                                                 |

### Operations

|                           | Holds                                                                                        |
| ------------------------- | -------------------------------------------------------------------------------------------- |
| **Approved labels** | The list the extractor must obey, with what each holds and which kinds of thing may carry it |
| **Review queue**    | Model disagreements, proposed labels, uncertain matches                                      |
| **Query log**       | Every question, what each search returned, the answer, anything removed, and the thumbs      |

## The one flexible field — the heart of the design

Today the data is hotel fact sheets. Later it is park guides, road reports, permits, vehicle fleets — **and nobody can say what those will contain.**

```
   ❌ THE OBVIOUS DESIGN, AND WHY IT FAILS

   A column for each piece of information. Four real
   Indian national parks:

   Ranthambore   10 NUMBERED zones, jeeps + canters,
                 canters banned in two of them
   Bandhavgarh    6 NAMED zones
   Kaziranga      RANGES, not zones — jeep, elephant, BOAT
   Periyar        boat, canoe, jeep, walking

   A fixed column list breaks on the second park.
   And safari zones are one content type out of twenty.
```

```
   ✅ WHAT WE DO INSTEAD

   WRITING is completely open
   ├── a hotel   →  rooms, price, pool, best months
   ├── a zone    →  gate, jeep capacity, booking window
   └── a permit  →  who needs it, how long it takes

       A new kind of document needs NO database change.

   READING is properly typed
   └── when one piece of information starts being
       asked about constantly, it is promoted into a
       real indexed field — takes seconds, changes
       nothing else
```

> **We do not guess the structure in advance. We discover it from what people actually ask.**

## Conflicts — keep everything, rank it

Every fact carries a **rank**: preferred, normal, or deprecated.

```
   Two documents disagree
        │
        ▼
   BOTH are kept. Neither is deleted.
   The newer one is marked preferred and shown by default.
   The older stays visible in the source panel, with its date.
```

**A losing claim is never destroyed.** This is how the salesperson sees that a disagreement exists rather than trusting a silent winner. Two facts differing only by *qualifier* are not a conflict at all — they are both true.

## Hosting

|                            | Supabase             | DigitalOcean   | Neon                         |
| -------------------------- | -------------------- | -------------- | ---------------------------- |
| Cost                       | **$25/mo**     | $15.15/mo flat | ₹470–1,275*if it sleeps* |
| Predictable                | ✅                   | ✅             | ❌                           |
| Browse tables in a browser | ✅**built in** | ❌             | ✅                           |

**Supabase, for two reasons:** the table and SQL editors matter constantly during a build where extraction output needs checking, and they matter again at handover when the client gets something they can actually look at.

⚠️ **Two things to verify before committing:** that the fuzzy-name-matching extension is available, and that the chosen tier has enough memory to build the vector index in memory rather than on disk — the disk fallback runs 10 to 50 times slower.

**On Neon:** the earlier $75/month bill on another project decodes exactly to 720 hours — twenty-four hours a day, every day. Something held a connection open and it never slept once. The pricing model was not the problem; the lack of warning was.

---

# 6. 🔍 Retrieval — how a question finds its answer

## ⭐ The governing principle: send whole documents, not fragments

Their documents are small. The arithmetic settles the design:

```
   one property sheet        ≈  1,500 tokens of text
                             +     500 tokens of facts
                             ──────────────────
                             ≈  2,000 tokens

   the ENTIRE 52-file corpus ≈ 41,000 tokens
   Gemini 3.8 Flash window    = 1,048,576 tokens
```

**Chunking a 2,000-token document and retrieving five pieces of it solves a problem that does not exist — and creates one.**

```
   ❌ FRAGMENT RETRIEVAL
      "how many rooms at Ramathra?"
        → retrieves the 5 best chunks
        → the dining section is not among them
        → the follow-up "what's the food like?" answers
          "I don't have that" — about a document that
          describes the dining in three paragraphs

   ✅ WHOLE-DOCUMENT RETRIEVAL
      → identify WHICH documents are relevant
      → send each one COMPLETE: full text + all its facts
      → nothing can be missed, because nothing was left out
```

## The retrieval flow

```
   ❓ question arrives
        │
   ┌────▼─────────────────────────────────────────┐
   │  STAGE 1 — WHICH DOCUMENTS MATTER?                     │
   │                                                        │
   │  Four ways to identify them, run together:             │
   │    • the question names a property   → exact/alias      │
   │    • a filter matches things        → structured query  │
   │    • a relationship matches         → connections       │
   │    • meaning or keywords match      → search            │
   │                                                        │
   │  Output: a LIST OF DOCUMENTS, not a list of fragments  │
   └────┬─────────────────────────────────────────┘
        │
   ┌────▼─────────────────────────────────────────┐
   │  STAGE 2 — HOW MUCH OF EACH TO SEND                    │
   │                                                        │
   │   ≤ 15 documents   → send every one COMPLETE            │
   │                      (raw text + facts + sources)      │
   │                                                        │
   │   > 15 documents   → the top 10 complete, the rest as   │
   │                      their one-line summaries          │
   │                                                        │
   │   corpus-wide count → the STRUCTURED ANSWER only        │
   │                      ("13 of 36, all checked")         │
   │                      No document text needed at all    │
   └────┬─────────────────────────────────────────┘
        ▼
   the answering model receives whole documents
```

**15 documents × 2,000 tokens = 30,000 tokens.** Comfortable, and roughly ₹2 per question.

## ⚠️ Why not simply send everything, every time

The whole corpus is only 41,000 tokens, so it is technically possible. **Measured evidence says do not.**

```
   NVIDIA, same model, same documents:

      curated retrieval,  ~48K tokens   →  47.25
      whole document set, 117K tokens   →  34.26
                                           ─────
                    MORE context scored WORSE
```

And the cost: 41,000 tokens on every question is **₹2.90 instead of ₹0.95** — three times more, forever, including on questions that need one document.

**Whole relevant documents: yes. The whole corpus: no.**

## The four ways documents get identified

All four run. Nothing is skipped because a question "looked like" one type — misclassifying is a silent failure that returns a confident answer from the wrong method.

|                               | Identifies documents by                                             | Fails at                          |
| ----------------------------- | ------------------------------------------------------------------- | --------------------------------- |
| 🏨**Name match**        | The question names a property. Exact → alias → prefix → spelling | Questions that name nothing       |
| 🔢**Structured query**  | *under ₹25,000 · heritage · fewer than 20 rooms*               | Anything not extracted as a fact  |
| ↔️**Connections**     | *closest to a gate · inside this park · operated by*            | Anything not a relationship       |
| 🧠**Keyword + meaning** | *good for birders · how are the roads*                           | Numbers, counting, exhaustiveness |

**Three different failure modes, so they do not fail together.**

## Why meaning-search alone cannot work

The single most important retrieval fact in the design.

```
   ① "under ₹25,000" is ARITHMETIC, not language.

      The document says "₹18,500". The question says
      "under ₹25,000". As text these share almost nothing.
      Meaning-search compares MEANING, not SIZE. There is
      no direction in that space for "less than".

   ② Meaning-search always returns a fixed number of results.

      Ask for the top 20 and you get 20 — whether three
      things match or three hundred. It RANKS. It does not
      COUNT. "How many" is not a question a ranking system
      can answer.
```

Measured on enterprise benchmarks: meaning-search alone scores around **0% on counting questions** and **32% on questions combining several conditions**, where structured querying scores **86%**.

**Every quoting question is a filter and a count.** That is why the facts path exists.

## Filter before searching, never after

```
   ❌ search all 500 pieces, then filter to Rajasthan
      → similar-but-wrong text crowds out the right answer
        before you ever get to filter

   ✅ filter to Rajasthan first, then search 40 pieces
      → the wrong answers were never candidates
```

**The filters are not a fixed list.** The extractor discovers what metadata exists for each kind of document; the question planner decides which of it to use. Only the naming is controlled.

⚠️ **One setting that must be switched on deliberately.** Filtering interacts badly with vector indexes at their default setting:

```
   THE DEFAULT, BROKEN BEHAVIOUR
   "birding lodges in Rajasthan"
        ↓
   the index finds the 20 nearest chunks OVERALL
        ↓
   THEN filters to Rajasthan
        ↓
   maybe 3 survive. You asked for 20 and got 3.
```

**pgvector supports iterative scanning**, which keeps searching until it genuinely has enough results that pass the filter. **It is off by default.** Without it, filtered searches silently under-return — and it presents as *"the search sometimes finds almost nothing"* weeks into a build.

## Reordering

When more than 15 documents match, the pooled results are reordered by a dedicated relevance model to choose which 10 get sent complete. In published measurement this moves the best result from around eighth place to first.

Below 15 documents, reordering is unnecessary — everything is being sent anyway.

## Identifying which property is meant

```
   ① The conversation already knows
      "how many rooms at Ramathra?" → "12"
      "and the food there?"  ← resolved silently

   ② A partial or misspelled name
      exact → alias → starts-with → close spelling
      Several match? LIST THEM AND ASK. Never pick one.

   ③ Nothing to go on
      "tell me about that hotel" as a first message
      → "Which hotel? I have around 67 — give me a name,
         or a destination and I'll list what's there."
```

**Ambiguity is surfaced, never resolved by guessing.** Picking the most likely property is exactly how a salesperson quotes the wrong one.

## Follow-up questions — always identify again

```
   Q1: "how many rooms at Aahana?"  → sent the whole Aahana document
   Q2: "what's the food like?"       → the SAME document is still right
                                     → and it already contains the dining
```

**Whole-document retrieval largely dissolves the follow-up problem** — the answer to Q2 was already in what we sent for Q1.

Document identification still re-runs every turn, because the follow-up may have moved to a different property. It costs 0.05 seconds.

**And the current property is tracked explicitly in the conversation**, re-read from the user's own words each turn rather than from the previous rewrite — otherwise a small error on turn two compounds through turns three and four.

---

# 7. 💬 Answering

## The flow

```
   ①  UNDERSTAND — gemini-3.8-flash, thinking off      ~1.5s
      Split the question into parts. Turn "cheap" into an
      actual number by looking at the range in the data.
      Resolve "there" and "that hotel" from the conversation.
      If genuinely unclear — ASK, do not guess.

   ②  SEARCH — all four paths, in parallel             ~0.05s

   ③  REORDER by relevance                             ~0.4s

   ④  WRITE — gemini-3.8-flash, thinking off, streaming
      Given the retrieved text and nothing else.
      Every claim must carry its source.
      First words appear at ~1.2s.

   ⑤  VERIFY — after display, not before
      Re-reads our own answer against the sources it cites.
```

## Streaming

The answer appears word by word as it is generated, rather than all at once when finished.

```
   ❌ 3.5 seconds of blank screen, then everything at once
   ✅ progress at 0.3s, first words at ~3.1s, done at ~3.5s
```

**Same total time. Completely different experience.** And the progress messages are real stages, not decoration — *"checking 49 properties… found 7 matches… reading their pages…"* corresponds to steps ① to ③.

## Verification — selective, and after display

⚠️ **A claim that cannot be verified is not silently deleted.** The answer says *"could not verify X."*

> A salesperson who reads "pool" and infers "no spa" is worse off than one told plainly that the spa could not be confirmed. Silent removal turns a retrieval miss into an invisible omission.

**Every removal is logged with the claim and the full retrieved context.** That log is the direct measure of retrieval gaps.

| Always verify                             | Skip verification                                        |
| ----------------------------------------- | -------------------------------------------------------- |
| Prices, distances, room counts            | *"I don't have that in the data"* — nothing to verify |
| Answers making three or more claims       | Single-fact lookups with a direct quote attached         |
| Negations —*"no spa", "not available"* | Follow-ups on already-verified context                   |
| Anything the search scored weakly         |                                                          |

**The whole step sits behind a switch** and can be turned off without touching anything else.

---

# 8. 🔐 Conversations and session isolation

## The API has no memory — this shapes everything

```
   ┌────────────────────────────────────────────────────┐
   │  The language model stores NOTHING between calls.  │
   │  Every call is the first it has ever seen.         │
   │  It does not know who you are.                     │
   └────────────────────────────────────────────────────┘
```

**"Remembering" a conversation means resending it.** Every turn, we send the whole relevant history again. This is how every chat product works, including ChatGPT — they simply hide the cost inside a subscription.

## Sessions are ours, not Google's

There is no session concept in the Gemini API and **the session identifier never reaches Google.** It exists so *our* database knows which conversation is which.

```
   LOGIN    =  "are you allowed in?"      one shared password
   SESSION  =  "which conversation is this?"  a random ID per browser
```

**One shared login does not mean one shared conversation.** They are unrelated concepts.

## How isolation actually works

```
   Priya's browser                    Nazim's browser
   session a7f3…                      session 91c4…
        │                                  │
        └────────────┐        ┌────────────┘
                     ▼        ▼
              ┌────────────────────┐
              │   our backend      │
              │  every read is     │  ← the entire
              │  filtered by       │    isolation mechanism
              │  session id        │
              └─────────┬──────────┘
                        ▼
              ┌────────────────────┐
              │  the database      │
              │  a7f3 │ 91c4       │  ← never mixed
              └─────────┬──────────┘
                        ▼
              ┌────────────────────┐
              │  Gemini            │
              │  sees one          │
              │  conversation      │  ← cannot leak;
              │  remembers nothing │    it stores nothing
              └────────────────────┘
```

The identifier is generated by our backend and stored in a cookie that page scripts cannot read.

## Edge cases that matter

|                                               |                                                                                                                                                                                                 |
| --------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 🖥️**Two people, one office computer** | Same browser means same conversation.**The one real risk.** Fixed with a visible "New chat" button and by showing whose conversation is open                                              |
| 🕐**Left open overnight**               | Sessions expire after about twelve hours of inactivity                                                                                                                                          |
| 🔄**Server restarts**                   | Nothing lost — conversations live in the database, not in memory. This is precisely why we do not use the SDK's built-in chat helper, which keeps everything in memory and loses it on restart |
| 🧹**Old conversations**                 | Kept. They are the query log, and the evidence base for pricing phase 2                                                                                                                         |

## Keeping conversations from growing forever

```
   last 5 turns        kept word for word
   everything older    rolled into a one-or-two sentence summary
   the current property  always carried
```

Without this, turn thirty costs forty times turn one for no benefit. **With it, prompt size stays flat no matter how long the conversation runs.**

A 2026 study found recent turns kept verbatim outperform summarised ones — so summarise only what falls out of the window, never eagerly.

## Follow-up questions — always retrieve again

```
   Q1: "how many rooms at Aahana?"  → retrieved the quick-facts section
   Q2: "what's the food like?"       → the dining section was NEVER retrieved
                                     → reusing Q1's context answers
                                       "I don't have that"
                                     → about something plainly on the page
```

**So: retrieve fresh every turn.** It costs 0.05 seconds. Being wrong costs a wrong answer.

**But do carry the previous turn's results forward as additional candidates.** Free, and it catches whatever the rewritten question missed.

**And track the current property explicitly**, re-read from the user's own words each turn rather than from the previous rewrite — otherwise a small error on turn two compounds through turns three and four.

---

# 9. 💾 Caching

Repeated content is charged at **one tenth** the normal rate. Not free — ten times cheaper.

## Two kinds, and we only need one

|                    | Automatic                               | Explicit                                     |
| ------------------ | --------------------------------------- | -------------------------------------------- |
| Who does it        | Google                                  | Us                                           |
| Code               | **none**                          | create, refresh, expire, handle failure      |
| Cost               | **free**                          | storage charged per hour whether used or not |
| Minimum to trigger | **4,096 tokens** of shared prefix | —                                           |

**We use the automatic kind only.** Explicit caching would save roughly **₹114 a month** and add four new things that can break. Not a trade worth making.

## The one design decision it requires

```
   ✅ CORRECT ORDER                ❌ WRONG ORDER
   ┌────────────────────┐          ┌────────────────────┐
   │ instructions       │ cached   │ the question       │ changes
   │ approved labels    │ cached   │ chat history       │ changes
   │ query structure    │ cached   │ instructions       │ ← nothing
   ├────────────────────┤          │ approved labels    │   caches
   │ retrieved text     │ changes  │ query structure    │   at all
   │ chat history       │ changes  └────────────────────┘
   │ the question       │ changes
   └────────────────────┘
```

**Static content first. Always.** Get this wrong and we pay full price forever without ever knowing.

⚠️ Our static block is currently around 1,900 tokens — **below the 4,096 threshold**, so it will not cache on short conversations. It begins working around turn seven, when history pushes the repeated prefix past the minimum. Short conversations are cheap anyway.

## If we ever use Claude in the live path

⚠️ **Anthropic reduced their default cache lifetime from 60 minutes to 5 in early 2026.** A salesperson who reads an answer for six minutes before typing the next question misses the cache entirely and pays full price again. **The one-hour option must be requested explicitly.**

---

# 10. 📏 Evaluation

## The test suite — about 90 cases in three parts

| Part                                       | Count | Guards against                                                                                                                                                                     |
| ------------------------------------------ | ----- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **The answerable questions**         | 30    | Wrong answers. Each has the exact document and section that proves it                                                                                                              |
| **Alternate phrasings**              | ~60   | An answer that only works for one wording. The client's own bank asks the same thing several ways; the shortlist kept one phrasing of each                                         |
| **Questions the data cannot answer** | 2+    | **The system inventing an answer.** Star rating and foreign-currency payment. This is the regression that matters most, and a suite of only-positive cases does not catch it |

## Three things measured separately

```
   ① Did retrieval FIND the right document?
   ② Is the ANSWER correct?
   ③ Does every claim actually map to a real source?
```

⚠️ **These must be separate numbers.** A legal research system scored 0.91 on answer quality while silently missing a required statute in one answer in six — because nobody measured whether retrieval found *everything*. Answer quality and retrieval completeness are different things and a good score on one hides a bad score on the other.

## The completeness check

```
   Ask each test question TWICE:
     ① through our retrieval          (the real path)
     ② with all 52 files given to the model directly

   Different answers → our retrieval missed something.
```

Around ₹40 per full run. **The only way to measure what retrieval never saw.** Not a production path — a test instrument.

## Running it

Every change re-runs the suite. A change that lowers the score does not ship.

**The iteration loop runs on Flash, not Pro:**

```
   iterate on 3.8 Flash      24 min per full pass
   final run on 3.1 Pro     101 min, once
   ────────────────────────────────────────────
   3-5 iterations: ~2 hours instead of 5-8
```

The loop fixes *instruction* problems — a missing label, a joined multi-value field. **Flash surfaces those just as well** — both scored zero ungrounded quotes and zero unit errors. Pro's advantage is how much it finds, which is not what the loop is testing.

## The feedback loop

A thumbs-down requires a reason and logs the whole trace. **Each one becomes a permanent test case**, so the same mistake cannot happen twice.

---

# 11. ⏱️ Latency

## Measured, per step

| Step                         | Time                       |
| ---------------------------- | -------------------------- |
| Understand the question      | 1.5s                       |
| Four searches                | 0.05s                      |
| Reorder results              | 0.4s                       |
| **First words appear** | **~3.1s**            |
| Answer complete              | ~3.5s                      |
| Verification                 | after display, not counted |

**Under four seconds.** For a repeated question served from cache, effectively instant.

## Where the time actually goes

```
   database              0.05s      ←  1%
   language models       3.4s       ← 99%
```

**The database is irrelevant to latency.** Every second the salesperson waits is a language model working.

## How it got from 15.7 seconds to 3.5

| Change                                          | Saved                                                              |
| ----------------------------------------------- | ------------------------------------------------------------------ |
| **Thinking off**                          | **−5.8s** — and it fixed a truncation bug at the same time |
| Flash instead of a Pro-tier model for answering | −5.8s                                                             |
| Verification moved after display                | −2.0s perceived                                                   |
| Lighter model for understanding the question    | −0.9s                                                             |

## Engineering levers, ranked

|                                                                   | Impact here                                                                                                                                              |
| ----------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Cache repeated questions**                                | 🟢**Real.** Twenty people asking about the same 67 properties repeat themselves constantly. A hit skips everything                                 |
| **Stream the answer, verify afterwards**                    | 🟢 Real — the perceived wait drops sharply                                                                                                              |
| **Warm database connections**                               | 🟢 Boring, and a dominant cause of slow outliers. Two thirds of production systems of this kind exceed two seconds at the tail, largely from cold starts |
| **Start searching before the question is fully understood** | 🟡 Marginal for us. Ranked highest in the literature, but our searches take 0.05s — there is almost nothing to hide behind                              |

---

# 12. 💰 Cost

*At ₹95 to the dollar. All figures double on 1 January 2027.*

## One-time — reading all 52 files (61 pages)

|                                                   |                     |
| ------------------------------------------------- | ------------------- |
| Reading every page with`gemini-3.1-pro-preview` | **₹174**     |
| Independent check with Claude Sonnet 5            | ~₹238 🟡 estimated |
| Building the keyword and meaning indexes          | ₹3                 |
| **Total, once**                             | **≈ ₹415**  |

Paid once. Questions never re-read a file.

## Per question

|                       |                     |
| --------------------- | ------------------- |
| Understand            | ₹0.18              |
| Search and reorder    | ₹0.19              |
| Write the answer      | ₹0.40              |
| Verify (when it runs) | ₹0.18              |
| **Total**       | **≈ ₹0.95** |

## Monthly, at 30–50 questions a day

|                     |                               |
| ------------------- | ----------------------------- |
| Language models     | **₹630 – 1,050**      |
| Database (Supabase) | ₹2,375                       |
| File storage (R2)   | ₹0 today · ₹430 at 300 GB  |
| **Total**     | **≈ ₹3,000 – 3,900** |

## At full scale

The one-time reading cost scales with page count and nothing else. **The database does not need rebuilding** — that was the entire point of the design.

---

# 13. 🔨 Build order

Each step is measurable against the client's own questions, so nothing is assumed.

|   | Step                                                                            | Proves                                       |
| - | ------------------------------------------------------------------------------- | -------------------------------------------- |
| 1 | Storage, database, and the ingestion pipeline                                   | Documents become facts, with proof           |
| 2 | Extract all 52 files, clear the review queue                                    | Extraction is trustworthy                    |
| 3 | Facts and keyword search.**No meaning-search yet.** Run all 90 test cases | How far the simple path gets                 |
| 4 | Question routing across the paths                                               | The right question reaches the right method  |
| 5 | **Add meaning-search where step 3 measurably failed**                     | We know what it bought                       |
| 6 | Reordering by relevance                                                         | Best result first                            |
| 7 | Answer generation, streaming, verification                                      | Nothing unsupported reaches the user         |
| 8 | Conversations, sessions, memory                                                 | Follow-ups work; conversations stay separate |
| 9 | Query logging and the feedback loop                                             | Evidence for phase 2                         |

**Meaning-search comes fifth, not first.** Every company that has built this added embeddings *after* a working structured system. We have 90 real test questions to measure with, so it can be earned rather than assumed.

---

# 14. ⚠️ What is measured and what is not

## ✅ Measured on the client's real files

|                                                                            |                                                                                                                |
| -------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------- |
| **Four Gemini models compared** on extraction                        | 11 files, 19 pages                                                                                             |
| **Claude Sonnet 5 compared against Gemini** on the structured prompt | 2 pages, same images, same instruction                                                                         |
| **Flat vs structured extraction**                                    | Same file, same model — 17 facts → 29                                                                        |
| **Thinking on versus off**                                           | Speed and grounding. Off is faster AND better grounded                                                         |
| **Every latency figure**                                             | Six runs each, streaming enabled                                                                               |
| **Text-to-source ratio**                                             | 0.045% — which decides the whole scale question                                                               |
| **Grounding of every extracted fact**                                | 167 of 168 quotes verified present on the page, against the PDF's own text layer and cross-model transcription |
| **Entity resolution failure and its fix**                            | The Kaav / Kanha merge                                                                                         |
| **Unit errors and the vocabulary gap**                               | Duration stored as distance                                                                                    |
| **Sub-part scoping fix**                                             | `room_count` 12 / 4 / 6 / 2 now correctly scoped                                                             |
| **Total spend proving all of it**                                    | **≈ ₹200 and $0.39**                                                                                   |

## 🟡 Not tested — flagged wherever it appears

|                                                                    | What it needs                                                                                                                              |
| ------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------ |
| **Icon reading with the structured prompt**                  | The one file in both runs improved (3 → 4 visual facts), but the icon-heavy Postcard document was not re-tested.**2 pages, ≈₹20** |
| **Sonnet vs Gemini beyond two pages**                        | The pattern was consistent on both, but two pages is not proof.**4–5 pages, ≈₹30 + $0.40**                                        |
| **Answer quality with thinking off across all 30 questions** | One question tested. Faster and better-grounded on that one                                                                                |
| **Whether the 96 DPI images need upscaling**                 | 5 files, native versus doubled                                                                                                             |
| **Neon: `pg_trgm` availability and index-build memory**    | Half an hour                                                                                                                               |
| **Explicit cache lifetime limits**                           | Google's own documentation truncated before that detail                                                                                    |

## 🔧 Known gaps in the current pipeline

|                                                                       |                                                                                                                                                                                                                                   |
| --------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Approved labels have no definitions**                         | `star_rating` without one attracted a TripAdvisor score. Every label needs a one-line definition and, where confusable, an explicit "not this"                                                                                  |
| **Booleans arrive as sentences**                                | `has_pool = "No swimming pool"`. Caught by validation rule 1, but the prompt should not produce it                                                                                                                              |
| **"Nearest X" can arrive twice**                                | Two`nearest_airport` facts. Caught by rule 3; store as scoped `airport` and derive nearest by minimum                                                                                                                         |
| **Units repeated inside the value**                             | `"5 acres"` with unit `"acres"`                                                                                                                                                                                               |
| **Connections table not yet populated**                         | The structured extraction now returns the entities — airports, stations, parks — so the data exists. The loader does not yet write the relationships                                                                            |
| **Merge logic for two independent readers does not exist**      | Roughly a day: match on entity + label + scope, agree → write, differ → review, single-source → write flagged                                                                                                                  |
| **Facts are being inferred from decorative photographs**        | 3 of 17 visual facts in the first run. The grounding check cannot catch these — the quote is real, the inference is not. Needs the extraction instruction to make the assert-versus-decorate distinction, plus validation rule 9 |
| **Icon reading not re-verified with the structured extraction** | The 14 legitimate visual facts came from one document that has not been re-run since the instruction changed                                                                                                                      |

---

# 15. 🚧 Deliberately not built yet — and the trigger for each

An external review proposed roughly twenty-four additional tables. Each is defensible for a document-management platform. **None is defensible for 61 pages and twenty users today.** Recorded here so the reasoning survives, and so the trigger is written down rather than remembered.

| Not building                                                                                             | Would add | Build it when                                                                                                                                                                                                                                                                                |
| -------------------------------------------------------------------------------------------------------- | --------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Block-level structure** — paragraph, heading, table, cell as separate records                   | 3 tables  | **The first spreadsheet or rate card arrives.** A table cell needs its own citation, and a page-level highlight is not good enough for a number inside a grid. There are no tables in the current 52 files                                                                             |
| **Processing lineage** — runs, tasks, attempts as database records                                | 5 tables  | **Around 1,000 documents.** Our pipeline is already resumable and it was killed and restarted several times during testing without loss. That works at 61 pages; it stops being enough when a failed batch is expensive to find                                                        |
| **Normalised answer tracing** — retrieval runs, hits, answer claims, citations as separate tables | 6 tables  | **When debugging actually hurts.** At roughly 1,100 questions a month the existing log can be queried directly. This solves a problem we do not have                                                                                                                                   |
| **Full access control** — workspaces, users, roles, document permissions, audit                   | 6 tables  | **If the client says any data is confidential.** v1 is one shared password with no user accounts. The sensitivity flag on documents covers the real risk — a citation to something a person should not see — without building an identity system for a system that has no identities |
| **Separate blob / document / revision identity**                                                   | 4 tables  | Solves the same problem as the list-of-paths column already does                                                                                                                                                                                                                             |

> **The principle:** every one of these is the right answer to a real problem. None of those problems exists yet, and each has a specific, written trigger. Building them now would triple the schema to prevent failures that cannot currently occur.

---

# 16. ✅ What is complete, and what is left

## Settled, tested, written down

|                                 |                                                                               |
| ------------------------------- | ----------------------------------------------------------------------------- |
| Which models, and why           | Measured on the client's own files, four Gemini variants plus Claude Sonnet 5 |
| Structured extraction           | Sections, block kinds, typed values, scoped sub-parts — all verified working |
| The vocabulary rule             | Extract everything, gate only queryability                                    |
| What counts as visual evidence  | Assert versus decorate, with validation                                       |
| Nine load-time validation rules | Each traceable to a real error on real files                                  |
| Database structure              | Flexible facts, typed values, evidence, connections, conflict ranking         |
| Retrieval                       | Whole documents rather than fragments, with thresholds                        |
| Answering                       | Streaming, selective verification, unsupported claims marked not deleted      |
| Conversations and isolation     | Session identity, memory window, entity tracking                              |
| Caching                         | Implicit only, with the prompt-ordering requirement                           |
| Evaluation                      | 90 cases in three parts, retrieval measured separately from answers           |
| Latency                         | Every figure measured, not estimated                                          |
| Cost                            | One-time and monthly, both models                                             |
| Hosting and handover            | Decided, with the guardrails                                                  |

## Still to be done — in order of what blocks what

|   | Work                                                                                                                                             | Effort                      | Blocks                                                                       |
| - | ------------------------------------------------------------------------------------------------------------------------------------------------ | --------------------------- | ---------------------------------------------------------------------------- |
| 1 | **Write the label definitions** — every approved label needs a one-line meaning and, where confusable, an explicit "not this"             | ½ day                      | Extraction quality.`star_rating` without one attracted a TripAdvisor score |
| 2 | **Rework the extraction instruction** for the assert-versus-decorate rule                                                                  | ½ day                      | Stops facts being invented from photographs                                  |
| 3 | **Re-verify icon reading** on the icon-heavy document                                                                                      | ≈₹20                      | The last unproven claim about the vision model                               |
| 4 | **Build the nine validation rules** into the loader                                                                                        | 1 day                       | Nothing should be written before these exist                                 |
| 5 | **Build the merge step** for two independent readers                                                                                       | 1 day                       | Only if both models are used                                                 |
| 6 | **Populate the connections table** — extraction now returns airports, stations and parks; the loader does not yet write the relationships | ½ day                      | *"Which park is this near"*, *"closest to the gate"*                     |
| 7 | **Confirm the database host** — extension availability and index-build memory                                                             | ½ hour                     | Nothing, but cheap to check before committing                                |
| 8 | **Run the full corpus** and clear the review queue                                                                                         | 2 hrs machine, ½ day human | Everything downstream                                                        |

## Deliberately unanswered, and why

|                                                               |                                                                                          |
| ------------------------------------------------------------- | ---------------------------------------------------------------------------------------- |
| **Does hard synthesis need the slower reasoning mode?** | One question tested. Settled by running all 30 acceptance questions, not by deciding now |
| **Do the low-resolution images need upscaling?**        | Settled by a five-file comparison, not by argument                                       |
| **Is Sonnet worth ₹1,140 across the corpus?**          | Two pages suggest yes. Four or five more would prove it                                  |
| **Is any client data confidential?**                    | Their answer. The sensitivity flag exists either way                                     |

---

# 17. 🤝 Handover

|                            |                                                                                                                        |
| -------------------------- | ---------------------------------------------------------------------------------------------------------------------- |
| Database                   | Transfers to the client's own account                                                                                  |
| Hosting                    | Transfers with the project                                                                                             |
| API keys                   | Ours swapped for theirs                                                                                                |
| ⚠️**File storage** | **The one exception.** Buckets do not transfer between accounts — about 250 MB is re-uploaded. One hour of work |

**Nothing needs to be created by the client before we start.**

The one thing we cannot create ourselves, and which is slow, is access to their document library for automatic syncing in phase two. That needs permission from their Microsoft administrator. **Worth requesting well before it is needed.**
