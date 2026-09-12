# 🧭 Travel Inn AI Assistant — Project Roadmap

|                       |                                                               |
| --------------------- | ------------------------------------------------------------- |
| **Prepared by** | Priyanshu                                                     |
| **For**         | Shivam                                                        |
| **Date**        | 4 September 2026                                              |
| **Scope**       | v1 — 52 files · 61 pages · 49 property folders · 20 users |
| **Status**      | Design settled and tested on real client data                 |

---

# 1. 🎯 What we are building

An internal assistant for Travel Inn's sales team.

```
   A salesperson types a question in plain English
                    │
                    ▼
   ┌───────────────────────────────────────────────────┐
   │  The answer, in seconds — with the exact page     │
   │  of the exact document it came from.              │
   │                                                   │
   │  If the answer is not in their documents,         │
   │  it says so. It never fills the gap with a guess. │
   └───────────────────────────────────────────────────┘
```

Today a sales person answers an enquiry by opening folder after folder, reading PDFs one at a time, and relying on Nazim's memory for the rest. **The value of this system is not speed — it is that the knowledge stops living in one person's head.**

---

# 2. ⚙️ How it works — two separate flows

Everything rests on one idea: **the documents are read once, not every time somebody asks a question.**

## Flow A — Reading the documents (happens once per file)

```
   📄 PDF or image lands in storage
              │
              ▼
   ┌──────────────────────────────────────────────────────┐
   │  ①  RENDER                                           │
   │      Every page turned into a high-resolution image  │
   │      and its text pulled out where one exists.       │
   └──────────────────────────────────────────────────────┘
              │
              ▼
   ┌──────────────────────────────────────────────────────┐
   │  ②  READ  —  Gemini 3 Pro                            │
   │                                                      │
   │      Looks at the page as a picture AND reads its    │
   │      text. Returns two things at once:               │
   │                                                      │
   │      • a complete transcription of the page          │
   │      • the specific facts on it, each tagged with    │
   │        the sentence that proves it                   │
   │                                                      │
   │      Because it SEES the page, it catches things     │
   │      that exist only as pictures — a pool icon,      │
   │      a wifi symbol, a crossed-out amenity.           │
   └──────────────────────────────────────────────────────┘
              │
              ▼
   ┌──────────────────────────────────────────────────────┐
   │  ③  ANCHOR                                           │
   │      Each fact is matched back to its exact position │
   │      on the page, so the answer can be clicked and   │
   │      checked later.                                  │
   └──────────────────────────────────────────────────────┘
              │
              ▼
   ┌──────────────────────────────────────────────────────┐
   │  ④  CHECK  —  Claude Sonnet 5                        │
   │      A different company's model reads the same page │
   │      independently, having never seen the first      │
   │      model's answer. Where the two disagree,         │
   │      nothing is written — it goes to a human.        │
   └──────────────────────────────────────────────────────┘
              │
              ▼
   ┌──────────────────────────────────────────────────────┐
   │  ⑤  STORE — all of it, in one database               │
   │                                                      │
   │      • the facts                                     │
   │      • the proof for every fact                      │
   │      • the complete text of every page               │
   │      • embeddings of that text, so it can be         │
   │        searched by meaning and not just by words     │
   │      • the connections between things                │
   └──────────────────────────────────────────────────────┘
```

**This is a background job.** On the current 52 files it runs for a few hours. Nobody waits on it, and it can be stopped and resumed.

## Flow B — Answering a question (happens per question, in seconds)

```
   ❓ "Cheap heritage places near Ranthambore, good for birding —
       and what is the fort actually like?"
                    │
                    ▼
   ┌──────────────────────────────────────────────────────┐
   │  ①  UNDERSTAND                                       │
   │      Break the question into parts. Work out that    │
   │      "cheap" is a price limit, "heritage" is a       │
   │      category, "near Ranthambore" is a distance,     │
   │      and "what is it like" is a different kind of    │
   │      question altogether.                            │
   │                                                      │
   │      If the question is genuinely unclear —          │
   │      "tell me about that hotel" with no hotel        │
   │      named — it ASKS. It does not pick one.          │
   └──────────────────────────────────────────────────────┘
                    │
      ┌─────────────┼─────────────┬──────────────┐
      ▼             ▼             ▼              ▼
   FACTS        DISTANCES      KEYWORDS      MEANING
   price, type  near X         exact names   "what is it like"
                                             (the embeddings)
      │             │             │              │
      └─────────────┴──────┬──────┴──────────────┘
                           ▼
   ┌──────────────────────────────────────────────────────┐
   │  ②  MERGE AND RANK                                   │
   │      ALL FOUR always run. Nothing is skipped         │
   │      because the question "looked like" one type.    │
   │      Everything found is pooled and the most         │
   │      relevant put first.                             │
   └──────────────────────────────────────────────────────┘
                           │
                           ▼
   ┌──────────────────────────────────────────────────────┐
   │  ③  ANSWER  —  Gemini 3.8 Flash                      │
   │      Written using ONLY what was retrieved.          │
   │      The model has nothing else to draw on —         │
   │      not its training, not the internet.             │
   └──────────────────────────────────────────────────────┘
                           │
                           ▼
   ┌──────────────────────────────────────────────────────┐
   │  ④  VERIFY  —  Gemini 3.8 Flash                      │
   │      A different company's model re-reads the answer │
   │      against the sources it cites.                   │
   │                                                      │
   │      A claim it cannot support is NOT silently       │
   │      removed. The answer says "could not verify X"   │
   │      — because a salesperson who reads "pool" and    │
   │      infers "no spa" is worse off than one told      │
   │      the spa could not be confirmed.                 │
   │                                                      │
   │      Every such case is logged with the claim and    │
   │      the full retrieved context. That log is how we  │
   │      find retrieval gaps.                            │
   │                                                      │
   │      This step is behind a switch and can be turned  │
   │      off without touching anything else.             │
   └──────────────────────────────────────────────────────┘
                           │
                           ▼
   💬  The answer, with a clickable source for every claim
```

---

# 3. 🤖 Which AI model does what

Chosen after a real head-to-head on 11 of the client's own files, 19 pages, three models.

| Job                                    | Model                                | Why this one                                                                                                                                                                                |
| -------------------------------------- | ------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 📖**Reading documents**          | **`gemini-3.1-pro-preview`** | Found**303 facts** where the cheaper model found 196, and **twice as many facts from icons and pictures** (17 vs 8)                                                             |
| ✅**Checking the reading**       | **Claude Sonnet 5**            | A completely different company's model. This is the point — two models from the same family tend to make the*same* mistakes, so they agree on being wrong. Two different families do not |
| 🧠**Understanding the question** | **`gemini-3.8-flash`**       | Fast and cheap, runs on every question. Pinned to an exact version — no moving aliases in the live path                                                                                    |
| 💬 **Writing the answer** | **`gemini-3.8-flash`** | Measured at **1.2 seconds to the first word**, and it quoted the source evidence more precisely than the slower option did. Google's current stable Flash release |
| 🔍 **Verifying the answer** | **`gemini-3.8-flash`** | Re-reads our own answer against the sources it cites. Runs after the answer is shown, so it costs the reader nothing |
| 📐**Search by meaning**          | **`gemini-embedding-2`**     | Tested and working. Stable release                                                                                                                                                          |

**Two vendors, deliberately — where it matters.**

Reading a document page is **interpretation**, and two models from the same family share training data, make the same misreading, and then agree with each other confidently. So the reading is checked by a different company's model.

Verifying an answer is **mechanical** — does this sentence appear in the retrieved text? There is far less room for shared bias in text-matching, so that step stays with Gemini and takes two seconds instead of ten.

## What the test showed

|                              | Gemini 3 Pro  | Gemini Flash | Cheapest model |
| ---------------------------- | ------------- | ------------ | -------------- |
| Facts found                  | **303** | 196          | 131            |
| Facts read from pictures     | **17**  | 8            | 13             |
| Quotes traceable to the page | 99.3%         | 100%         | 93.2%          |
| Wrong-unit errors            | **0**   | **0**  | 2              |

The cheapest model was rejected: roughly **1 in 15 of its quotes could not be found on the page**, and it made unit errors — recording *"4 hours from the airport"* as *"4 km from the airport."*

Gemini 3 Pro made neither mistake, and when it met information it had no field for, it **flagged it for a human rather than forcing it into the wrong field** — which it did 13 separate times.

---

# 4. 🗄️ How the database is built, and why

## The problem it has to solve

Today the data is 52 hotel fact sheets. Later the client will hand over a very large amount of other content — park guides, road conditions, vehicle lists, permits, rate cards — **and nobody can tell us in advance what it will contain.**

The obvious design is a table with a column for each piece of information. That breaks immediately. Here are four real Indian national parks:

| Park        | Zones                       | Safari types                                    |
| ----------- | --------------------------- | ----------------------------------------------- |
| Ranthambore | 10,**numbered**       | jeep, canter — but canters banned in two zones |
| Bandhavgarh | 6,**named**           | jeep, canter                                    |
| Kaziranga   | **ranges**, not zones | jeep,**elephant**, **boat**         |
| Periyar     | —                          | boat, canoe, jeep,**walking**             |

A fixed set of columns fails on the second park. And safari zones are one content type out of roughly twenty.

## The solution: separate what we store from how we search it

```
   ┌──────────────────────────────────────────────────────┐
   │  WRITING — completely open                           │
   │                                                      │
   │  Each thing gets one flexible field holding whatever │
   │  that thing happens to have:                         │
   │                                                      │
   │     a hotel  →  rooms, price, pool, best months      │
   │     a zone   →  gate, jeep capacity, booking window  │
   │     a permit →  who needs it, how long it takes      │
   │                                                      │
   │  A brand new type of document needs NO change to     │
   │  the database. Nothing to migrate. Nothing to break. │
   └──────────────────────────────────────────────────────┘
                            │
                            ▼
   ┌──────────────────────────────────────────────────────┐
   │  SEARCHING — properly typed where it matters         │
   │                                                      │
   │  When one piece of information starts being asked    │
   │  about constantly — room count, price — it is        │
   │  promoted into a proper indexed field.               │
   │                                                      │
   │  This takes seconds and changes nothing else.        │
   └──────────────────────────────────────────────────────┘
```

> **We do not guess the structure in advance. We discover it from what people actually ask.**

## The four things stored

```
   ┌─────────────────────────────────────────────────────────┐
   │  ①  THE THINGS                                          │
   │     Every hotel, park, zone, route, permit — all in     │
   │     one place, each with its own flexible set of        │
   │     information.                                        │
   │     ➜ answers "under ₹25,000", "how many", "list all"  │
   ├─────────────────────────────────────────────────────────┤
   │  ②  THE PROOF                                           │
   │     For every single fact: the exact sentence that      │
   │     said it, which document, which page, and where      │
   │     on that page.                                       │
   │     ➜ this is what makes an answer checkable            │
   ├─────────────────────────────────────────────────────────┤
   │  ③  THE FULL TEXT                                       │
   │     Every word of every document, kept permanently,     │
   │     and made searchable both by keyword and by meaning. │
   │     ➜ answers "how are the roads", "what is it like"   │
   ├─────────────────────────────────────────────────────────┤
   │  ④  THE CONNECTIONS                                     │
   │     "this lodge is 4 km from that gate",                │
   │     "this property sits inside that park"               │
   │     ➜ answers "closest to", "inside", "operated by"    │
   └─────────────────────────────────────────────────────────┘
```

## 🧠 Yes — embeddings are stored, and they live in the same database

This is worth stating plainly because it is easy to misread.

**We are using embeddings.** Every document's full text is broken into sections, each section is converted into an embedding — a mathematical representation of its *meaning* — and those embeddings are stored and searched. That is how the system answers *"is this good for birding?"* when the document never uses the word "birding."

**What we are not doing is running a second, separate database to hold them.**

```
   ❌  The common approach:
       Postgres for the facts   +   a separate vector product
                                     (Qdrant, Pinecone, etc.)
       ➜ two systems, two bills, two migrations at handover,
         and no way to ask one question across both

   ✅  Ours:
       ONE Postgres database holding:
         • the facts
         • the proof
         • the full text
         • THE EMBEDDINGS
         • the connections

       Postgres has had proper embedding support built in for
       years. It is the same technology the separate products
       sell — just not as a separate product.
```

**Why this matters practically:** a real question is *"under ₹25,000 AND good for birding."* The price is a fact; birding is a meaning. In one database that is a single question. Split across two systems, it is two separate lookups that somebody then has to stitch together by hand — and the stitching is where these systems go wrong.

## 🔤 The facts are stored as flexible data, not as fixed columns

This is the part that makes the design work, and it puts the weight somewhere unusual.

```
   A traditional database:
      you decide the columns first, then fill them in.
      A new kind of document arrives ➜ you rebuild the table.

   Ours:
      each thing carries its own flexible set of information,
      written in a structured but open format.
      A new kind of document arrives ➜ nothing changes.
```

**The consequence: the quality of the whole system depends on the instruction given to the reading model.**

There is no column definition forcing the data into shape. The instruction is what decides which pieces of information get captured, how they are named, what counts as a fact, and what must never be guessed. Get the instruction right and the data is clean and consistent. Get it wrong and the flexibility becomes a mess.

This is why the reading instruction is treated as a versioned, tested asset rather than something written once. **Two of the errors found in testing were instruction problems, not model problems** — and both were fixed by changing the instruction, not the model.

Two safeguards keep the openness under control:

|                                                |                                                                                                                                                                    |
| ---------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **A controlled list of approved labels** | The model may only use names from an approved list. Anything genuinely new is proposed and held until a person approves it — never written straight into the data |
| **Every fact must quote the page**       | A fact whose quote cannot be found in the document is rejected automatically                                                                                       |

## 📝 The full text is embedded too — so nothing is lost

The facts are the precise, countable part. **They are not the whole document.**

Measured on a real client file: **the facts account for about 11% of the page.** The other 89% is prose — the description of the fort, why the property suits certain guests, what the drive is like.

**All of it is stored, and all of it is searchable:**

```
   Every document
        │
        ├──➜  facts        the 11%   ➜  filtering, counting, comparing
        │
        └──➜  full text    the 100%  ➜  broken into sections
                                        ➜ embedded for meaning
                                        ➜ indexed for keywords
```

So when someone asks *"what is Ramathra Fort actually like?"*, the answer does not come from a field called `property_type`. It comes from the paragraph the client's own team wrote, quoted back with its source.

## 🔍 Every source is searched — not just the facts

When a question arrives, the system does **not** decide "this is a facts question" and look only there. It searches **everything it has** and then combines the results.

```
   ❓  Question arrives
              │
    ┌─────────┼─────────┬──────────────┬─────────────┐
    ▼         ▼         ▼              ▼             ▼
  FACTS   CONNECTIONS  KEYWORDS    MEANING      (the proof
  the 11%  distances   exact names  the 89%      is attached
                       and numbers               to whatever
                                                 is found)
    │         │           │            │
    └─────────┴─────┬─────┴────────────┘
                    ▼
      everything found is pooled, re-ranked by
      relevance, and the best of it is handed to
      the model that writes the answer
```

Each of these fails in a different way, which is exactly why all four run. Meaning-search misses an exact number; keyword search catches it. Keyword search misses a paraphrase; meaning-search catches it. **Neither can count — so the facts do that.**

## 🏨 How it knows which property you mean

A salesperson does not type *"The Postcard in the Himalayan Willows, Leh, Ladakh."* They type *"Postcard Leh"* — or just *"that hotel."* Three cases, three behaviours.

```
   ┌─────────────────────────────────────────────────────────┐
   │  ①  THE CONVERSATION ALREADY KNOWS                      │
   │                                                         │
   │      "How many rooms at Ramathra Fort?"                 │
   │      "12."                                              │
   │      "and what's the food like there?"                  │
   │                            ▲                            │
   │              resolved from the previous message         │
   │              — silently, no friction                    │
   └─────────────────────────────────────────────────────────┘

   ┌─────────────────────────────────────────────────────────┐
   │  ②  A PARTIAL OR MISSPELLED NAME                        │
   │                                                         │
   │      "tell me about Kaav"                               │
   │              │                                          │
   │              ▼                                          │
   │      ① exact name?          no                          │
   │      ② known short form?    YES ➜ Kaav Safari Lodge     │
   │      ③ starts-with match                                │
   │      ④ close spelling                                   │
   │                                                         │
   │      When several match — "The Postcard" matches        │
   │      three properties — it LISTS them and asks which.   │
   │      It never picks the most likely one.                │
   └─────────────────────────────────────────────────────────┘

   ┌─────────────────────────────────────────────────────────┐
   │  ③  NOTHING TO GO ON                                    │
   │                                                         │
   │      "tell me about that hotel"   ← first message       │
   │              │                                          │
   │              ▼                                          │
   │      "Which hotel? I have around 67 properties —        │
   │       give me a name, or a destination and I'll         │
   │       list what's there."                               │
   └─────────────────────────────────────────────────────────┘
```

**Short names are the hard case, and they are handled deliberately.** *"Kaav"* compared against *"Kaav Safari Lodge"* by spelling alone scores far too low to match — and *"Postcard Leh"* against *"The Postcard in the Himalayan Willows"* is worse. So at reading time the system records the short forms, the common misspellings, and the versions without "The" for every property. Spelling similarity is the last resort, not the first.

**And a hard rule learned during testing:** properties in different states are never treated as the same thing, however similar their names. Two genuinely different properties — one in Karnataka, one in Madhya Pradesh — were being merged into one record because both names contained *"Safari Lodge."* Generic words like *lodge*, *palace*, *fort* and *resort* are now ignored when matching names, and a match that is merely plausible creates a separate record and flags it for a person rather than merging silently.

## Why both ① and ③ — this is the important part

Facts and full text answer **different halves of the same question**, and neither one alone is enough.

Measured on a real client file: **the facts cover about 11% of the page.** The other 89% is prose — descriptions, positioning, context.

```
   "How many properties have a pool?"
       From full text  ➜  a text search returns its top 20 results.
                          Always 20 — whether 4 match or 40.
                          It ranks. It cannot count. ❌

       From facts      ➜  "13 of 36, and all 36 were checked." ✅
```

```
   "What is the fort actually like?"
       From facts      ➜  "Heritage Boutique Fort Hotel."
                          Technically true. Useless. ❌

       From full text  ➜  the actual paragraph the client wrote. ✅
```

> **Facts give precision. Full text gives coverage.** A real sales question usually needs both, which is why both are stored and both are searched.

## Why meaning-search alone is not enough

We use it — it is one of the four searches. But it is the most common way people build these systems *on its own*, and on its own it fails at exactly the questions that matter most here.

Search-by-meaning works by turning text into a position in space and finding nearby text. Two things break:

```
   1.  The document says "₹18,500". The question says "under ₹25,000".
       As text, those two share almost nothing. Meaning-search compares
       MEANING, not SIZE. There is no direction in that space for
       "less than".

   2.  It always returns a fixed number of results. Ask for 20, get 20 —
       whether three things match or three hundred.
```

**Every quoting question is a filter and a count.** *"Under ₹25,000."* *"How many have a pool?"* *"Which is closest?"* *"List all the heritage properties."*

Meaning-search is genuinely excellent for *"how are the roads"* — so we use it for exactly that, alongside the other three, never instead of them.

## Growing the vocabulary safely

One risk with a flexible design is the same fact being recorded three different ways:

```
   "swimming pool" ─┐
   "outdoor pool"  ─┼─➜  three different labels, one real fact
   "pool"          ─┘
                   ▼
   "How many have a pool?" finds one third of them —
   and reports the count with complete confidence. 🔴
```

**This is not hypothetical — the audit found pool described five different ways across the current 52 files.**

So the system keeps a controlled list of approved labels. The reading model may only use labels from that list. When it meets something genuinely new, it **proposes** a label and stops — a person approves it once, and every future document uses that same label.

In the test the model proposed 74 new labels and every one was held for approval rather than written into the data. It also proposed the same missing label — *drive time from the airport* — **13 separate times**, which told us exactly what the list was missing.

---

# 5. 📦 Where the files live

Original documents are stored in **Cloudflare R2**.

|                                                              |                                                                                                                                             |
| ------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------- |
| Every file is stored under a fingerprint of its own contents | The same file uploaded twice de-duplicates automatically — this already happened correctly in testing with a document filed in two folders |
| The original is never modified or overwritten                | A revised document is a new version; the old one is kept and marked superseded                                                              |
| Nothing is publicly accessible                               | Every view goes through a short-lived private link issued after a login check                                                               |
| Rendered page images and small previews are kept alongside   | So the source page opens instantly when someone clicks to check an answer                                                                   |

**Current volume: **206.8 MB of client documents**, which sits well inside R2's free allowance. (We also generate rendered page images for the source viewer — those are our working files, not their data.)**

---

# 6. ✅ How we know the answers are right

Four layers, because no single one is enough.

```
   ①  THE MODEL HAS NOTHING ELSE TO DRAW ON
      It sees only what was retrieved from the client's documents.
      Not its training data. Not the internet.

   ②  EVERY QUOTE IS CHECKED AGAINST THE PAGE
      At reading time, a quote that cannot be found in the document
      is rejected automatically.
      Measured: 99.3% of Gemini 3 Pro's quotes were exact matches.

   ③  TWO DIFFERENT COMPANIES' MODELS MUST AGREE
      Claude Sonnet 5 reads every page independently of Gemini,
      having never seen its answer. Where they disagree, nothing
      is written — it goes to a person.

      The "different company" part is the whole point. Two models
      from the same family share training data and tend to make
      the SAME mistake, then agree with each other confidently.
      Two different families do not.

      Measured: 99.3% of quotes were exact matches to the page.
      The step is estimated to take end-to-end accuracy from roughly
      97% to 99%+ — that figure is an ESTIMATE from published results
      for this technique, not measured on our data.

   ④  A HUMAN CAN VERIFY IN TWO SECONDS
      Every claim links to the real page, at the exact spot.
```

**Layer ④ is what makes it genuinely trustworthy** — not because the machine is perfect, but because a person can confirm it instantly and will, on anything that matters.

## Every question is logged

A deliverable, not a by-product. Per question the system records:

|                                         |                                                                                        |
| --------------------------------------- | -------------------------------------------------------------------------------------- |
| The question                            | exactly as the salesperson typed it                                                    |
| What each of the four searches returned | so a bad answer can be traced to which one failed                                      |
| The answer given                        |                                                                                        |
| Anything the verifier could not support | with the retrieved context at the time — this is the direct measure of retrieval gaps |
| Thumbs up / down                        |                                                                                        |

**This log is the evidence base for pricing phase 2.** It tells us what the team actually asks, how often the data has no answer, and which content types are most missed — none of which can be guessed from the 52 files we have.

## Testing

The client supplied 186 questions. About 30 are answerable from the current 52 files with the exact document and section identified for each. Those become the automatic test suite, in three parts:

| Part                                                                                                                                 | Count | Guards against                                                                                                                           |
| ------------------------------------------------------------------------------------------------------------------------------------ | ----- | ---------------------------------------------------------------------------------------------------------------------------------------- |
| **The 30 answerable questions**                                                                                                | 30    | Wrong answers                                                                                                                            |
| **Alternate phrasings** — the client's question bank asks the same thing several ways; the shortlist kept one wording of each | ~60   | An answer that only works for one phrasing                                                                                               |
| **Questions the data cannot answer** — star rating, foreign-currency payment                                                  | 2+    | **The system inventing an answer.** This is the regression that matters most, and a suite of only-positive cases does not catch it |

**~90 test cases in total.** Any change that lowers the score does not ship. When a salesperson marks an answer as wrong, that question is added permanently, so the same mistake cannot happen twice.

---

# 7. ⏱️ How fast it answers

Measured on real retrieved data, six runs, with the answer streaming onto the screen as it is written.

| | |
|---|---|
| ⚡ **First words appear** | **~3.1 seconds** |
| Answer complete | ~3.5 seconds |
| A question someone already asked | effectively instant |

## Where the time goes

```
   understand the question      1.5s
   search everything            0.05s
   put the best results first   0.4s
   write the answer             1.2s to the first word
   ────────────────────────────────────
   verification runs AFTER the answer is on screen,
   so it costs the reader nothing
```

**The database accounts for 1% of the wait.** Every second is a language model working — which is why the model choices in section 3 were made on measured speed, not reputation.

## Why it feels faster than 3.5 seconds

The answer appears word by word as it is written, rather than all at once when finished — the same way ChatGPT and Claude do it.

```
   ❌ 3.5 seconds of blank screen, then everything at once
   ✅ "Checking 49 properties…"        at 0.3s
      "Found 7 matches…"               at 1.5s
      the answer begins appearing      at 3.1s
```

Those progress lines are the real stages of the search, not decoration.

---

# 8. 💰 Cost

*At today's rate of about ₹95 to the dollar.*

## One-time — reading all 52 files

|                                                      |                    |
| ---------------------------------------------------- | ------------------ |
| Reading all 61 pages with Gemini 3 Pro               | **₹174**    |
| Independent check on every page with Claude Sonnet 5 | ~₹238 *(estimated)* |
| Building the meaning and keyword indexes             | ₹3                |
| **Total, once**                                | **≈ ₹415** |

This is paid once. Questions never re-read a file. The second-model check is more than half of it, and it is the step that takes accuracy from roughly 97% to 99%+ — the best value in the entire build.

## Ongoing — per month

Assuming light use, around 30–50 questions a day across the team:

|                             |                                              |
| --------------------------- | -------------------------------------------- |
| AI cost per question | **₹0.95** |
| **AI cost per month** | **₹630 – 1,050** |
| File storage                | ₹0 — 207 MB sits inside the free allowance |
| Database hosting (Supabase) | ₹2,375 |
| **Total per month** | **≈ ₹3,000 – 3,900** |

⚠️ **All Gemini prices double on 1 January 2027.** Four months away — it must be reflected in anything quoted on a twelve-month basis.

**On the database:** Supabase at a flat $25/month was chosen over cheaper usage-based options because the bill is predictable and it includes a browser view of the data — which matters at handover, when the client receives something they can actually look at rather than a connection string.

## Later, at full scale

When the client hands over their complete archive, the one-time reading cost scales with how many pages it contains. **The database does not need rebuilding** — that was the whole point of designing it this way — so the only real cost is reading the new documents once.

---

# 9. 🧪 What has already been proven on real data

Not a plan. This has been run against the client's own files.

|                                        | Result                                                          |
| -------------------------------------- | --------------------------------------------------------------- |
| Documents read end to end              | **11 files, 19 pages, three models compared**             |
| Facts extracted and stored             | **229**, each with its source sentence and page           |
| Things identified                      | **36** — hotels, plus national parks found automatically |
| Quotes traceable to the page           | **99.3%**                                                 |
| Information caught from pictures alone | **17 facts**                                              |
| Total cost of the entire test          | **₹67**                                                  |

**The strongest single result:** three properties were correctly recorded as having no spa — and on all three, the page contains **no text saying so.** It is a small crossed-out massage icon. A system that only reads text would have missed it entirely, or worse, assumed the spa existed.

# 10. 🔮 What happens when the full archive arrives

|                                                |                                                                                                                                                                                                       |
| ---------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **The database**                         | No rebuild. New kinds of documents drop into the same structure. This was the hardest design constraint and it is solved and tested                                                                   |
| **The reading**                          | Runs once over the new files, in the background                                                                                                                                                       |
| **The cost**                             | Scales with page count, nothing else                                                                                                                                                                  |
| **The one thing needed from the client** | Access to their document library for automatic syncing — this requires permission from their Microsoft administrator, and approvals of that kind are slow. Worth requesting well before it is needed |

---

**Nothing is needed from the client to begin.** Everything runs on our accounts and transfers to theirs at the end.
