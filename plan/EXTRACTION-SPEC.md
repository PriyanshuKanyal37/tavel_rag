# 📐 Extraction Specification

**The two artefacts that define the schema.** These decide what counts as a fact and how it is named. Reviewed before the full run.

**Status:** as used in the 11-file test. Gaps identified against the 30 acceptance questions are listed at the bottom and must be closed before the full run.

---

## 1. The instruction given to the reading model

This is sent with every page, alongside the page image and its extracted text.

```
You are extracting structured data from ONE PAGE of a travel-industry
property document, for a destination management company's internal database.

Return JSON matching the provided schema. Nothing else.

FIELDS

transcription
  Every word visible on the page, in natural reading order. Include headings,
  table cells, captions, and any text inside images or graphics. Do not
  summarise. Do not skip small print.

entities
  The real-world things this page describes. Usually one hotel. Sometimes many
  (a group update listing a dozen properties). Occasionally a destination or
  a park. Give each a name exactly as printed.

facts
  Every factual statement the page makes about an entity.

FACT RULES

  key
    MUST be one of the VOCABULARY keys listed below.
    If the page states something real that no vocabulary key covers, set
    key="_new" and put your proposed snake_case name in proposed_key.
    Do not force a fact into a key that does not fit.

  entity_name
    Which entity this fact is about. Must match one of the names in entities.

  value
    The value as a string. Numbers as digits ("12", "18500"). Booleans as
    "true"/"false". Preserve units in the unit field, not here.

  scope
    Leave empty unless the fact is CONDITIONAL. Use it when a value applies
    only to some rooms, some seasons, some nationalities, some months.
    Examples: {"unit_scope":"villas"} {"season":"peak"} {"nationality":"foreign"}
    A page saying "pool at the villas only" is has_pool=true with
    scope={"unit_scope":"villas"} - NOT an unqualified true.

  asserted_as
    stated   - the page says it plainly
    negated  - the page says it is NOT available / does NOT exist
    hedged   - the page is vague, conditional, or non-committal
    Never emit a fact for something the page simply does not mention.

  evidence
    For evidence_type="text": copy the EXACT sentence or phrase from the page,
    character for character. It must appear verbatim in your own transcription.
    Do not paraphrase, do not tidy punctuation, do not expand abbreviations.

    For evidence_type="visual": there is no sentence. Describe precisely what
    you see and where. e.g. "swimming pool pictogram, third icon in the
    amenities row beneath the header".

  evidence_type
    "text"   - stated in words
    "visual" - shown only as an icon, pictogram, symbol, or inside a photograph

  confidence
    high   - unambiguous
    medium - readable but could be misinterpreted
    low    - a guess; you are not sure

ABSOLUTE RULES

  1. NEVER infer, assume, or use outside knowledge. If the page does not say
     it, it does not exist. You are not being asked what you know about this
     hotel - only what this page states.
  2. "No pool" is a FACT (has_pool / negated). It is not the same as the page
     being silent about pools. Silence produces no fact at all.
  3. Text evidence must be a literal substring of the page. This is checked
     automatically and violations are rejected.
  4. Prices: record the number and currency exactly as printed. If the page
     shows a range, use the lower bound and note the range in evidence.
  5. If a page describes many properties, produce one entity per property and
     attribute every fact to the correct one. Do not merge them.
```

---

## 2. The approved label list

**29 labels currently approved.** The model may use ONLY these. Anything else must be proposed as new and held for human approval — it is never written into the data.

| # | Label | What it holds |
|---|---|---|
| 1 | `room_count` | number of keys/rooms |
| 2 | `room_categories` | named room types |
| 3 | `price_from_inr` | lowest published rate |
| 4 | `meal_plan` | AP / MAP / CP / EP |
| 5 | `has_pool` | swimming pool |
| 6 | `has_spa` | spa |
| 7 | `has_wifi` | wifi |
| 8 | `has_ac` | air conditioning |
| 9 | `has_restaurant` | restaurant / dining |
| 10 | `best_months` | best time to visit |
| 11 | `closed_months` | when closed |
| 12 | `check_in` | check-in time |
| 13 | `check_out` | check-out time |
| 14 | `nearest_airport` | named airport |
| 15 | `airport_km` | distance to airport |
| 16 | `nearest_railhead` | named station |
| 17 | `railhead_km` | distance to station |
| 18 | `nearest_gate` | named safari gate |
| 19 | `gate_km` | distance to gate |
| 20 | `star_rating` | star classification |
| 21 | `heritage_grade` | heritage classification |
| 22 | `property_type` | lodge / camp / palace etc |
| 23 | `ideal_for` | guest types suited |
| 24 | `activities` | experiences offered |
| 25 | `child_policy` | children rules |
| 26 | `pet_policy` | pets |
| 27 | `accessibility` | mobility access |
| 28 | `group_affiliation` | chain or group |
| 29 | `contact_email` | contact address |
---

## 3. ❌ Gaps found against the 30 acceptance questions

Checked every one of the 30 shortlisted questions against the list above. **Four of the fifteen structured questions currently fail on a missing label.** All four must be added before the full run.

| Missing label | Blocks | Evidence |
|---|---|---|
| `airport_drive_time` | **Q2** "How long does the road journey from the nearest airport take?" · **Q3** "compare airports by distance and driving time" | Proposed by the model **13 separate times** during testing. It is the single most-needed label |
| `railhead_drive_time` | **Q5** "how far is the station, and how long does the transfer take?" | Same pattern — distance is captured, time is discarded |
| `gate_drive_time` | **Q6** "which safari gate is closest, and how long to reach it?" | Same pattern |
| `naturalists` | **Q26** "are trained naturalists or guides provided?" | Model proposed `in_house_naturalists` during testing |

### Two further gaps that are not label problems

| Gap | Blocks | Fix |
|---|---|---|
| **Multiple airports per property** | **Q3** explicitly asks to *compare* airport options. One property has three. | Handled by the qualifier mechanism — three `airport_km` entries, each scoped to a named airport. Needs the instruction to emit them separately |
| **Park association** | **Q12** "which national park is it associated with?" · **Q13** "which reserve is it closest to?" | Not a label — a connection between two things. Requires the connections table to be populated, which is in scope but was not exercised in the test |

### Revised label count

**29 approved → 33 after adding the four above.** The rest of the 30 questions are served either by an existing label or by full-text search over the page.

---

## 4. Why this document matters

There are no fixed columns in this system. **This instruction and this list are the schema.** They decide what is captured, what it is called, and what must never be guessed.

Two of the errors found during testing were faults in this document, not in the model:

- **A duration recorded as a distance.** The page said *"4 hours from the airport."* With no `airport_drive_time` label available, the value was forced into `airport_km` and stored as *4 kilometres.* Fixed by adding the label — and by automatically rejecting any distance whose supporting quote is written in hours.
- **Multi-value facts joined into one string.** *"Bird watching, village walk, boating"* stored as a single value cannot be cited, because that exact string does not appear on the page. Fixed by requiring one fact per value, each with its own quote.

Both were instruction problems. Both were found before the real system was built.
