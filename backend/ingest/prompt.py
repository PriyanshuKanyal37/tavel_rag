"""The extraction contract: vocabulary, instruction, response schema.

Ported from pilot/prompt_v2.py, which measured 29 facts vs 17 for the flat
version on the same page. Two additions since:

  * the assert-vs-decorate rule. 3 of 17 visual facts in the first run were
    inferred from decorative photographs ("photographs showing marmots and
    brown bears" -> activities = wildlife viewing). The grounding check cannot
    catch these: the quote is real, the inference is not.
  * definitions for the labels that testing proved are confusable.
"""

# key -> (definition, what it is NOT)
VOCABULARY: dict[str, tuple[str, str]] = {
    "room_count": ("Number of rooms/keys/units/tents.", "Not the number of categories."),
    "room_categories": ("Number of distinct room types.", ""),
    "room_size": ("Floor area of a room category.", ""),
    "price_from": ("Lowest published tariff.", ""),
    "meal_plan": ("EP, CP, MAP, AP or a described inclusion.", ""),
    "has_pool": ("Whether a swimming pool exists.", "true/false only, never a sentence."),
    "has_spa": ("Whether a spa exists.", "true/false only."),
    "has_wifi": ("Whether wifi is available.", "true/false only."),
    "has_ac": ("Whether rooms are air conditioned.", "true/false only."),
    "has_restaurant": ("Whether a restaurant/dining venue exists.", "true/false only."),
    "has_bar": ("Whether a bar exists.", "true/false only."),
    "best_months": ("Recommended months to visit.", ""),
    "closed_months": ("Months the property is shut.", ""),
    "check_in": ("Check-in time.", ""),
    "check_out": ("Check-out time.", ""),
    "nearest_airport": ("Name of the closest airport.", "Single-valued. A second airport needs a scope."),
    "airport_km": ("Road distance to the airport, in KILOMETRES.", "NOT a duration. '4 hours' is not 4 km."),
    "airport_drive_time": ("Driving time to the airport, in hours or minutes.", "NOT a distance."),
    "nearest_railhead": ("Name of the closest railway station.", "Single-valued."),
    "railhead_km": ("Road distance to the railhead, in KILOMETRES.", "NOT a duration."),
    "railhead_drive_time": ("Driving time to the railhead.", "NOT a distance."),
    "nearest_gate": ("Name of the closest park entry gate.", "Single-valued."),
    "gate_km": ("Distance to the gate, in KILOMETRES.", "NOT a duration."),
    "gate_drive_time": ("Driving time to the gate.", "NOT a distance."),
    "nearest_park": ("Name of the closest national park or reserve.", "Single-valued."),
    "park_km": ("Distance to the park, in KILOMETRES.", "NOT a duration."),
    "park_drive_time": ("Driving time to the park.", "NOT a distance."),
    "star_rating": ("OFFICIAL hotel classification from a government tourism body (HRACC in India).",
                    "NOT a guest review score. A TripAdvisor/Google/booking-site score is review_rating."),
    "review_rating": ("Guest review average. Always record the source in scope_key='source'.",
                      "NOT an official star classification."),
    "heritage_grade": ("Official heritage classification.", ""),
    "property_type": ("Fort, lodge, camp, palace, resort, homestay ...", ""),
    "usp": ("The property's stated selling proposition.", ""),
    "ideal_for": ("Traveller type the property suits.", "One fact per traveller type."),
    "activities": ("An activity offered.", "One fact per activity. Must be STATED, not inferred from a photo."),
    "dining": ("A dining venue or offering.", ""),
    "naturalists": ("Naturalist/guide provision.", ""),
    "child_policy": ("Rules about children.", ""),
    "pet_policy": ("Rules about pets.", ""),
    "accessibility": ("Access provision or limitation.", ""),
    "altitude_m": ("Altitude above sea level, in metres.", ""),
    "group_affiliation": ("Chain, group or collection the property belongs to.", ""),
    "contact_email": ("Contact email printed on the page.", ""),
    "conservation": ("Conservation or sustainability claim.", ""),
}

KEYS = list(VOCABULARY)

SYSTEM = """You are reading ONE PAGE of a travel-industry document for a
destination management company's internal knowledge base.

Return JSON matching the schema. Nothing else.

=====================================================================
PART 1 - THE PAGE'S STRUCTURE
=====================================================================

Report the page as it is ACTUALLY LAID OUT. Do not flatten it.

sections
  The page's own divisions, in order. Many documents number them
  ("01 - Introduction"). Use the heading exactly as printed. If the
  page has no headings, use one section with an empty heading.

blocks
  Within each section, the distinct pieces of content. For each,
  say what KIND it is:

    prose      running paragraphs
    key_value  a label paired with a value. VERY COMMON here - a row
               of boxes at the top of a page, each with a value above
               or beside its label
    list       bulleted or numbered items
    table      rows and columns
    caption    text attached to an image
    footer     contact details, disclaimers, page furniture

CRITICAL - key_value blocks:
  Return label/value pairs AS PAIRS. Do not flatten them into a
  sentence. Getting this wrong attaches a value to the wrong label
  and the error is invisible afterwards.

      Karauli, Rajasthan     LOCATION
      2 hours                FROM RANTHAMBORE N.P.

  ->  pairs: [{label: "LOCATION", value: "Karauli, Rajasthan"},
              {label: "FROM RANTHAMBORE N.P.", value: "2 hours"}]

  A value may appear ABOVE, BELOW, LEFT or RIGHT of its label. Match
  by visual grouping, not by reading order.

=====================================================================
PART 2 - THE TRANSCRIPTION
=====================================================================

Every word visible on the page, in natural reading order, including
text inside images, labelled icons, captions and footers.

Do not summarise. Do not skip small print.

=====================================================================
PART 3 - THE FACTS
=====================================================================

Extract EVERY factual statement the page makes. Do not filter.

  key           a VOCABULARY label if one genuinely fits, else "_new"
                with your snake_case suggestion in proposed_key.
                NEVER force a fact into a label that does not fit.
                NEVER drop a fact because no label exists.
  value_type    number | money | quantity | date | boolean | text | list
  value         the value as text (always fill this)
  value_number  the numeric part, when there is one
  value_unit    km, hours, minutes, rooms, acres, sq.ft ...
  value_currency  when value_type is money

    "12 units"   -> number,   12, unit "units"
    "203 km"     -> quantity, 203, unit "km"
    "3.5 hours"  -> quantity, 3.5, unit "hours"
    "INR 18,500" -> money,    18500, currency "INR"

    A DISTANCE AND A DURATION ARE DIFFERENT FACTS. "203 km / 3.5 hours"
    is TWO facts.

  section / block_kind   where on the page it came from
  evidence      the EXACT text from the page, character for character
  evidence_type "text" or "visual"
  asserted_as   stated | negated | hedged
  scope_key / scope_value   when the fact is CONDITIONAL
  confidence    high | medium | low

=====================================================================
PART 4 - WHAT COUNTS AS VISUAL EVIDENCE
=====================================================================

These pages are mostly PHOTOGRAPHS. Treating a picture as a claim
manufactures plausible, unverifiable facts. Before recording any
visual fact, ask:

    Is this image ASSERTING something, or DECORATING the page?

  EXTRACT (the image IS the statement):
    - icons in a facilities / features / amenities / inclusions block
    - anything carrying a tick, cross, Yes, No or check mark
    - a table, price grid or chart drawn as a picture
    - a map showing a location, route or boundary
    - a logo indicating a chain, group or certification
    - a caption that STATES SOMETHING BEYOND NAMING the picture
      ("Pool open year-round", "Spa - not yet operational")

  NEVER EXTRACT from a caption that only NAMES what is pictured:
    "POOL VIEW", "COURTYARD", "COMMON AREA", "MEDITATION/YOGA ROOM",
    "DINING", "BEDROOM", "STAR LIGHT ROOM"
  A gallery label is a picture's title, not a claim about the property.
  It CANNOT create a has_* boolean or a facility. If the property really
  has a pool, the page will say so in words or mark it in a facilities
  block -- use that instead. Verified failure: "POOL VIEW" produced
  has_pool=true on documents whose text never mentions a pool at all.

  NEVER EXTRACT (the image decorates):
    - landscape, scenery, sunset photographs
    - wildlife and animal photographs
    - people, lifestyle and "mood" shots
    - vehicles with no claim attached
    - room or interior photographs with no caption asserting anything

THE TEST: would a reader say "the document claims this", or would
they say "I worked it out from the picture"? If the second, it is
NOT a fact.

A PHOTOGRAPH NEVER CREATES A FACT ON ITS OWN. It can only corroborate
something the page already asserts in words or symbols.

  WRONG: activities = wildlife viewing
         evidence "photographs showing marmots and brown bears"
  WRONG: has_restaurant = true
         evidence "photograph showing a dining room with a long table"
  WRONG: has_pool = true
         evidence "photo caption reading 'POOL VIEW'"
  RIGHT: has_pool = true
         evidence "swimming pool ladder icon next to the word 'Yes'"

ONE MORE THING, AND IT MATTERS MORE THAN ANY OF THE ABOVE:
  If the page CONTRADICTS an amenity, the contradiction wins. A page that
  shows a spa photo and also prints "(Spa is currently under development
  and not yet operational)" asserts has_spa = FALSE, asserted_as "negated".
  Never let a picture or a heading override words that deny it.

Evidence for a visual fact must name the SYMBOL you read -- an icon,
tick, cross, mark, chart, map, logo or caption. Evidence that begins
"photograph showing..." with no tick, label or caption attached will
be rejected.

=====================================================================
ABSOLUTE RULES
=====================================================================
  1. Never infer. Never use outside knowledge. Only what this page says.
  2. "No pool" is a FACT (negated). Silence is not a fact.
  3. Text evidence must appear verbatim in your transcription.
  4. ONE FACT PER VALUE. Never join values with commas.
     Seven activities are seven facts.
  5. SUB-PARTS MUST BE SCOPED.
       Accommodation: 12 units in 3 categories
       Deluxe Room 04 keys 300 sq.ft / Luxury Tent 06 keys / Suite 02 keys
     MUST produce:
       room_count = 12  scope: (none)              <- property total
       room_count = 4   scope_key "category" scope_value "Deluxe Room"
       room_count = 6   scope_key "category" scope_value "Luxury Tent"
       room_count = 2   scope_key "category" scope_value "Luxury Suite"
     Without the scope, "how many rooms?" can answer 2.
  6. Do NOT create an entity for Travel Inn itself, or for any agency,
     publisher or contact block in the page furniture. Otherwise name EVERY
     real subject the page identifies as an entity -- including geography
     mentioned in passing (a river, a biosphere reserve, a state), not only
     the property the page is about.
     entity_type is free text. Use hotel / destination / park / experience /
     group / airport / railhead where they fit, and propose a better word when
     they do not. Never force a subject into "other".
  7. If the page names several things, produce one entity per thing and
     attribute every fact to the correct one. Use ONE spelling of a name
     throughout the document -- "KAAV" on one tile and "KAAV Safari Lodge" on
     the next orphans every fact attached to the short form.
  9. When a page restates a total that is also broken down by category, record
     BOTH: the unscoped total and each scoped part.
  8. A boolean fact's value must be exactly "true" or "false".
"""


def vocab_block(vocabulary=None) -> str:
    """Render the label list for the prompt.

    Built from the DATABASE when a vocabulary is supplied, so approving a new
    label changes what the reader is told without touching this file.
    """
    if vocabulary is None:
        return "\n".join(
            f"  {k}: {d}" + (f"  [NOT: {n}]" if n else "")
            for k, (d, n) in VOCABULARY.items())
    out = []
    for k, lab in sorted(vocabulary.approved.items()):
        line = f"  {k}: {lab.definition or '(no definition yet)'}"
        if lab.not_this:
            line += f"  [NOT: {lab.not_this}]"
        bits = [b for b in (lab.value_type, lab.unit_kind if lab.unit_kind != "none" else "",
                            "single-valued" if lab.cardinality == "scalar" else "") if b]
        if bits:
            line += f"  <{' · '.join(bits)}>"
        out.append(line)
    return "\n".join(out)


def build_prompt(page_text: str, page_no: int, total: int, filename: str,
                 is_tile: bool = False, vocabulary=None) -> str:
    text = (page_text or "").strip()
    if text:
        block = ("\n\nTEXT LAYER FOR THIS PAGE (use it for exact spellings and "
                 "numbers; the IMAGE is the source of truth for layout, icons "
                 f"and anything the text layer missed):\n---\n{text[:12000]}\n---")
    else:
        block = "\n\nThis page has NO text layer. Read everything from the image."

    unit = "TILE" if is_tile else "PAGE"
    note = ("\n\nThis is one horizontal STRIP of a taller page, cut so the image "
            "reaches you at full resolution. Strips overlap, so content near the "
            "top or bottom edge may repeat in a neighbour. Extract what you can "
            "read; do not guess at anything cut off mid-sentence."
            if is_tile else "")

    return (f"{SYSTEM}\n\nVOCABULARY (use these labels; each has a strict meaning):\n"
            f"{vocab_block(vocabulary)}\n\nFILE: {filename}\n{unit}: {page_no} of {total}"
            f"{note}{block}")


SCHEMA = {
    "type": "object",
    "required": ["document", "sections", "transcription", "entities", "facts"],
    "properties": {
        "document": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "subtitle": {"type": "string"},
                "template": {"type": "string"},
            },
        },
        "sections": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["heading", "blocks"],
                "properties": {
                    "number": {"type": "string"},
                    "heading": {"type": "string"},
                    "blocks": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": ["kind"],
                            "properties": {
                                "kind": {"type": "string",
                                         "enum": ["prose", "key_value", "list",
                                                  "table", "caption", "footer"]},
                                "text": {"type": "string"},
                                "pairs": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "label": {"type": "string"},
                                            "value": {"type": "string"},
                                        },
                                    },
                                },
                                "items": {"type": "array", "items": {"type": "string"}},
                            },
                        },
                    },
                },
            },
        },
        "transcription": {"type": "string"},
        "entities": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["name", "entity_type"],
                "properties": {
                    "name": {"type": "string"},
                    # Free text, not an enum. A fixed list of travel words would
                    # decide now what kinds of thing may exist in documents we
                    # have not seen. Common values today: hotel, destination,
                    # park, experience, group, airport, railhead -- but a reader
                    # that needs "airline", "visa_rule" or "vessel" must be able
                    # to say so instead of collapsing it into "other".
                    "entity_type": {"type": "string"},
                    "state": {"type": "string"},
                    "city": {"type": "string"},
                },
            },
        },
        "facts": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["entity_name", "key", "value", "value_type",
                             "evidence", "evidence_type", "asserted_as", "confidence"],
                "properties": {
                    "entity_name": {"type": "string"},
                    "key": {"type": "string"},
                    "proposed_key": {"type": "string"},
                    "value": {"type": "string"},
                    "value_type": {"type": "string",
                                   "enum": ["number", "money", "quantity", "date",
                                            "boolean", "text", "list"]},
                    "value_number": {"type": "number"},
                    "value_unit": {"type": "string"},
                    "value_currency": {"type": "string"},
                    "section": {"type": "string"},
                    "block_kind": {"type": "string"},
                    "evidence": {"type": "string"},
                    "evidence_type": {"type": "string", "enum": ["text", "visual"]},
                    "asserted_as": {"type": "string",
                                    "enum": ["stated", "negated", "hedged"]},
                    "scope_key": {"type": "string"},
                    "scope_value": {"type": "string"},
                    "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
                },
            },
        },
        "connections": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["from_name", "to_name", "kind"],
                "properties": {
                    "from_name": {"type": "string"},
                    "to_name": {"type": "string"},
                    "kind": {"type": "string"},
                    "distance_km": {"type": "number"},
                    "duration_h": {"type": "number"},
                    "evidence": {"type": "string"},
                },
            },
        },
    },
}
