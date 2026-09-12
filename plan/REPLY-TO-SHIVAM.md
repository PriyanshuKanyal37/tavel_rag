# Re: Travel Inn Roadmap — Answers to Q1–Q8

**From:** Priyanshu · **To:** Shivam · **Date:** 5 September 2026

> ⚠️ **Superseded in two places since this was written.**
> The latency figures in Q3 were measured before we found that Gemini's models reason before answering by default. With that turned off the system now answers in **~3.5 seconds, not 15.2** — and the verification step is no longer the thing to worry about.
> The "55% more facts" figure came from a run using a moving model alias; against a pinned model ID it is **39%**. Both corrected below where they appear.


Your four accepted changes are all correct and I've taken them. Answers to Q1–Q8 below, in order.

**Three things you should know before you read on, because they change numbers you already have:**

| | |
|---|---|
| 🔴 **The page count was wrong.** | 52 files contain **61 pages**, not the ~150 I costed against. 15 PDFs hold 24 pages between them (twelve are single-page), plus 37 single-page images. **All ingestion costs drop by about 60%.** |
| 🔴 **Gemini 3.1 Pro has no stable release.** | `gemini-3.1-pro-preview` is the *only* 3.1 Pro that exists. Your Q2 instinct was right and it forces a real decision. Details below. |
| 🔴 **"65–70 properties" is not a verified number.** | It's an inference. It should not go to Sukanya in that form. |

---

# Q1. Timeline, honestly

**No, 8–10 days does not hold. It is 3–4 weeks.**

The audit estimate was made before three things were in scope: the source-viewer with page highlighting, the cross-vendor read at ingestion, and an automated test suite. Each traces to a client requirement, but they weren't in the number.

| | |
|---|---|
| Foundation — storage, schema, entity model, ingestion pipeline, all four search paths | ~2 weeks |
| Chat interface | ~1 week |
| Eval loop | ~1 week, overlapping |
| **Total** | **3–4 weeks** |

## On eval iterations — you're right that this is what eats time

You're also right that Claude Code doesn't speed it up. The loop is: run the 61 pages → validate → read the failures → change the instruction → re-run. **My estimate is 3–5 full iterations.**

Each one costs:

```
   full 61-page extraction on Pro       ~1.7 hours (wall clock, unattended)
   automated validation                 minutes
   reading the failures + fixing        1–3 hours of my time
   ─────────────────────────────────────────────────
   ≈ one working day per iteration
```

**The basis for 3–5:** the 11-file test needed two instruction fixes before the output was clean — the unit error and the joined multi-value fields. That's two iterations on a fifth of the corpus. The full corpus has more template variety, so more, but the same *classes* of error should not recur once fixed.

**Where I could be wrong:** if the four missing labels (see Q4) turn out to have knock-on effects I haven't seen, or if the 2024-template files behave differently from the 2025 ones, it could be 6–8. I'll know after iteration two and I'll tell you then rather than at week three.

## The review queue is real work and I've budgeted it

You're right that it isn't optional. Scaling from the test: 11 files produced **74 held labels and 1 ambiguous match**. Across 52 files that's roughly **350 items**. Most are duplicates of the same few labels — `airport_drive_time` alone accounted for 13 of 74 — so the distinct decisions are far fewer, maybe 40–60. **Call it half a day, and it happens before Nazim sees anything.**

---

# Q2. Exact model IDs — and you found a real problem

I pulled the live model list from the API. Here is the situation.

## There is no stable Gemini 3.1 Pro

```
   gemini-3.1-pro-preview              ← the only 3.1 Pro that exists
   gemini-3.1-pro-preview-customtools  ← also preview

   There is no  gemini-3.1-pro.
```

Stable, non-preview models that do exist: `gemini-3.8-flash`, `gemini-3.7-flash`, `gemini-3.6-flash`, `gemini-3.5-flash`, `gemini-2.5-pro`, `gemini-embedding-2`.

## And `gemini-flash-latest` is worse than a preview

It's an **alias**. Google can repoint it at a different model without telling us, and our extraction behaviour changes silently between runs. **That is unacceptable in either path** and I'm removing it.

## The decision I'm making, and the reasoning

Your audit rule was "no preview models in the answering path." I'm keeping that rule and splitting on it:

| Step | Model ID | Preview? | Why acceptable |
|---|---|---|---|
| **Reading documents** (one-time) | `gemini-3.1-pro-preview` | ⚠️ **yes** | Runs once, on our infrastructure, output human-reviewed, and fully re-runnable for ₹174 if Google changes it. A change cannot reach the client without passing through the review queue first |
| **Checking the reading** | Claude Sonnet 5 | no | |
| **Understanding the question** (live) | `gemini-3.8-flash` | **no** | Pinned. Replaces the `-latest` alias |
| **Writing the answer** (live) | Claude Sonnet 5 | no | |
| **Verifying the answer** (live) | `gemini-3.8-flash` | **no** | Pinned |
| **Embeddings** | `gemini-embedding-2` | **no** | Stable |

**So: nothing with a `-preview` suffix and nothing with a moving alias runs in the live answering path.** The one preview model is confined to a one-time, reviewed, re-runnable batch job.

**The alternative, if you want zero preview anywhere:** `gemini-2.5-pro` for extraction. It's stable and pinned, but a generation behind, and I have not measured it. Extraction quality is the thing the pilot showed varies most between models — Pro found 39% more facts than Flash — so I'd want to run the bakeoff on 2.5 Pro before switching. **That's half a day. Say the word and I'll do it before the full run rather than after.**

⚠️ One note on `gemini-3.8-flash`: it is callable and listed by the API, but as your research flagged, it is not yet in Google's official model documentation. It is not marked preview either. I'm pinning it and will hold `gemini-3.5-flash` as the fallback, which is both stable and documented.

---

# Q3. Latency, measured

Measured on real retrieved context of production size — 2,161 input tokens to the answering model, six runs, streaming enabled.

**You're right that it matters, and the number is worse than "in seconds" implied.**

| | p50 | p95 |
|---|---|---|
| ⏱️ **Text starts appearing on screen** | **13.1s** | **14.9s** |
| Answer complete, verify **off** | 13.2s | 15.1s |
| Answer complete, verify **on** | **15.2s** | **17.1s** |
| *cost of the verify step alone* | *2.0s* | *2.0s* |

## The verify step is not the problem

This is the finding that matters. Per-leg:

```
   understand the question       2.4s
   WRITE THE ANSWER            10.8s   ← 71% of the total
   verify the answer            2.0s
```

**Turning verify off saves 2 seconds out of 15.** Your config flag is still right to have — it's a runtime cost on a foundation that doesn't need it — but switching it off does not get us from 15s to 3s. It gets us to 13s.

## Why the answer leg is slow

Time-to-first-token was **10.7 seconds**. The model produces nothing at all for ten seconds, then streams the answer quickly. Gemini 3.1 Pro is a reasoning model — it thinks internally before emitting anything, and streaming doesn't hide that.

**Two things follow:**

**1. The measurement is a proxy, not the plan.** I measured with Gemini 3.1 Pro because I have no Anthropic key on this machine. **The actual plan is Claude Sonnet 5 for answering**, which does not do extended reasoning by default and should start streaming considerably sooner. I will re-measure with a real key before the build and give you the true figure. I'm not going to quote you a Sonnet number I haven't measured.

**2. If it is still too slow, the lever is the answer model — not verify.** Measured, same prompt, same context:

| Answer model | Time to first token | Complete |
|---|---|---|
| `gemini-3.1-pro-preview` | **10.7s** | 10.8s |
| `gemini-3.8-flash` | **5.0s** | 5.0s |
| `gemini-3.5-flash` | 5.7s | 5.7s |

**Flash is less than half the time.** End to end that is roughly **7.4s to first text instead of 13.1s** — which is on the right side of the line you drew between 3 and 12.

The trade is answer quality, and it is measurable rather than a matter of opinion: we run both against the 30 acceptance questions and see whether Flash actually answers worse. **I'd rather present you that comparison than guess.** If Flash holds up, we take it and the latency problem goes away.

## What I'd propose

For a salesperson on a live call, 13 seconds of blank screen is the problem, not 15 seconds to completion. So:

- **Show the retrieval working.** *"Checking 49 properties… found 7 matches… reading their pages…"* Progress that reflects real steps, not a spinner. This is the difference between 13 seconds of waiting and 13 seconds of watching.
- **Stream the answer** the moment the first token arrives.
- **Run verify after display, not before** — flagging a claim a second later rather than delaying everything by 2s. This changes the design slightly and I'd want your view: it means a claim can briefly appear before being marked unverified.

I'll bring you real Sonnet numbers before committing to any of it.

---

# Q4. Does the label list cover all 30 test questions?

**No. Four of the fifteen structured questions currently fail on a missing label.** You were right to ask, and right about which one.

| Missing label | Blocks | Note |
|---|---|---|
| `airport_drive_time` | **Q2** *"how long does the road journey take?"* · **Q3** *"compare airports by distance and driving time"* | Exactly the one you named. Proposed by the model **13 times** in the test |
| `railhead_drive_time` | **Q5** *"how far is the station, and how long is the transfer?"* | Same pattern |
| `gate_drive_time` | **Q6** *"which gate is closest, and how long to reach it?"* | Same pattern |
| `naturalists` | **Q26** *"are trained naturalists provided?"* | Model proposed `in_house_naturalists` |

**Two further gaps that are not label problems:**

- **Q3 asks to *compare* multiple airports.** One property in the data has three. This needs three separate distance entries per property, each tagged with which airport — the qualifier mechanism handles it, but the instruction has to be told to emit them separately.
- **Q12 and Q13 ask which national park a property belongs to.** That is a connection between two things, not a label. It requires the connections table to be populated — in scope, but not exercised in the 11-file test.

**Label count goes 29 → 33.** Everything else among the 30 maps to an existing label or to full-text search. Full mapping is in `EXTRACTION-SPEC.md`.

---

# Q5. The extraction instruction and label list

**Attached: `EXTRACTION-SPEC.md`.** It contains the complete instruction sent with every page, the 29 currently-approved labels with what each holds, and the gap analysis from Q4.

Read section 4 in particular. **Two of the errors found in testing were faults in that document, not in the model** — the duration-stored-as-distance, and multi-value facts joined into one uncitable string. Both were fixed by changing the instruction.

---

# Q6. Where the numbers moved

Three separate causes. **One of them is my error.**

## Properties: 49 → "65–70" — inference, and it should not be quoted

The audit's 49 counted property folders. Some documents describe many properties at once: the Postcard group update is 7 pages covering roughly a dozen. In the 11-file test, **11 files produced 36 distinct entities** — including two national parks the model identified on its own, which is correct behaviour but is not what Sukanya means by "property".

**I have no verified count and should not have implied one.** The honest position:

> *"49 property folders. Some documents cover multiple properties, so the true count is higher — we will know exactly after the full ingestion run."*

I'll give you the real number after the run. It should not appear in a client document before then.

## Storage: 207 MB → 250 MB — my error, and it's a conflation

**206.8 MB is correct** and is the source files. The 250 MB in the roadmap included the rendered page images we generate for the source viewer. **Those are our working files, not their data**, and I mixed them into one figure. Corrected: their data is 207 MB.

## Questions: 150 → 186 — the bank grew, and 186 is right

186 is the verified count in the document Sukanya sent. The earlier ~150 predates that document. **30 answerable · ~95 partial · ~60 with no data at all.**

## And the one you didn't catch: pages

**52 files contain 61 pages, not the ~150 I costed against.** Twelve of the fifteen PDFs are a single page.

### Corrected costs

| | |
|---|---|
| Reading all 61 pages with Gemini 3.1 Pro | **₹174** |
| Independent check on every page with Claude Sonnet 5 | **₹238** |
| Building the indexes | ₹3 |
| **Total, one-time** | **≈ ₹415** *(was ₹1,020)* |

Monthly running cost is unaffected — it depends on questions asked, not pages stored.

## On "97% → 99%+"

You're right, and I'll label it. **99.3% quote traceability is measured** — 2 ungrounded quotes out of 303 facts, on 19 pages. **97% → 99%+ is an estimate** taken from published industry results for confidence-routed human review, not from our data. It will be marked as an estimate wherever it appears.

---

# Q7. Is the chat interface scoped?

**Yes, it is designed. It was left out of that document because I scoped the roadmap to backend, not because it's undecided.** Confirming each point:

| Proposal 2.3 commits to | Confirmed |
|---|---|
| Shared team login | ✅ Single shared password, as scoped. No per-user accounts in v1 — but the query log records a user field from day one, so per-user attribution can be added later without a migration |
| Plain-language input | ✅ Chat with conversation memory, so *"and what about the food there?"* resolves against the previous message. When a question genuinely has no property to attach to, it asks rather than guessing |
| Clickable source for every claim | ✅ See below |

## On "clickable source" — explicitly, it never leaves our app

```
   Answer claim  ──click──▶  the RENDERED PAGE IMAGE, served from R2
                             through a short-lived private link,
                             opened inline, scrolled and highlighted
                             at the exact spot the fact came from.

   ❌ Never a link to SharePoint.
   ❌ Never a download.
   ❌ Never "open the file and find it yourself."
```

We render every page to an image at ingestion for exactly this reason, and we record where on the page each fact sits. For facts that came from an icon rather than text, it shows the cropped icon itself — *"we read this as no spa: [image]"* — because there is no sentence to highlight.

**One caveat I'd rather state now:** where the exact quote can't be located on the page — hyphenation across a line break, or text the model joined from two separate columns — we highlight the whole paragraph and **label it "approximate location"** rather than drawing a precise box we aren't sure of. In the test this affected roughly 1% of facts.

---

# Q8. How often did verify-step deletions fire in testing?

**They never fired, because that step has not been built.** Flow B doesn't exist yet — the test covered ingestion only. I should not have implied otherwise.

**Here is the closest real number I have,** and it's the ingestion-side equivalent — a quote that could not be found on the page:

| | Gemini 3.1 Pro | Claude Sonnet 5 (checker) | flash-lite (rejected) |
|---|---|---|---|
| Facts extracted | 303 | — | 131 |
| Quotes not found on the page | **2** | — | 8 |
| Rate | **0.7%** | — | **6.8%** |

**Your instinct in the change request is the right one, though**, and it's the reason I'm taking it. At ingestion the two failure modes are distinguishable — the model either invented a quote or it didn't. **At answer time they are not.** A verifier that can't find support for "spa" cannot tell whether the model invented it or whether retrieval simply missed the page that says it. Those need different fixes, and the current design conflates them.

So, as you asked: **every deletion is logged with the deleted claim and the full retrieved context**, which makes retrieval gaps directly measurable. And I'm taking your second point too — **the answer will say "could not verify X" rather than silently dropping it.** A salesperson who reads "pool" and infers "no spa" is a worse outcome than one who reads "pool, and I couldn't confirm the spa."

I'll have the real deletion rate after the first full eval run and will report it as a number, not an impression.

---

# Changes taken from section 2

| | |
|---|---|
| ✅ Deletion logging + "could not verify" instead of silent removal | Taken, both parts |
| ✅ Negative cases in the test suite | The two deliberate "I don't know" questions added — star rating and foreign-currency payment. Grounding is the regression that matters most and you're right that the suite only guarded correctness |
| ✅ Rephrasings | 2–3 of Sukanya's alternate phrasings per question. **30 → ~90 test cases** |
| ✅ Query logging as a deliverable | Per question: the question as typed · what each of the four paths returned · the answer · anything the verifier removed · thumbs up/down. Treated as a deliverable, and it is the evidence base for phase-2 pricing |
| ✅ Reconcile the numbers | Done above. One was my error, one was a conflation, one was a wrong page count you hadn't seen yet |
| ✅ Verify step behind a config flag | Taken |
