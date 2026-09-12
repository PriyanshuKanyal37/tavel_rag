"""The nine load-time rules. Nothing reaches the database unchecked.

Every rule exists because a real model got it wrong on the client's real
files during testing. A fact that fails is NOT written -- it goes to the
review queue with the reason attached.
"""
import re

DURATION_WORDS = r"(hours?|hrs?\b|minutes?|mins?\b)"
SYMBOL_WORDS = ("icon", "tick", "check", "cross", "mark", "chart", "map", "logo",
                "caption", "symbol", "label", "table", "grid", "legend", "badge",
                "yes", "no", "✓", "✗", "×")
PHOTO_OPENERS = ("photograph", "photo ", "image of", "image show", "picture of",
                 "picture show", "photos show", "images show")


def _norm(s: str) -> str:
    return "".join(c for c in (s or "").lower() if c.isalnum())


# ---------------------------------------------------------------- per-fact
def rule1_boolean(f, v) -> str | None:
    """has_pool = 'No swimming pool' -- a sentence in a boolean field.

    Which keys are boolean comes from the vocabulary's value_type, not from a
    naming convention, so a future domain's `is_export_controlled` is covered
    without touching this function.
    """
    if f.get("key") in v.boolean_keys:
        val = (f.get("value") or "").strip().lower()
        if val not in ("true", "false"):
            return f"boolean value is not true/false: {f.get('value')!r}"
    return None


def rule2_distance_not_duration(f, v) -> str | None:
    """'4 hours from Jabalpur Airport' stored as airport_km = 4."""
    key, val, ev = f.get("key", ""), (f.get("value") or "").strip(), f.get("evidence") or ""
    if key not in v.distance_keys or not val:
        return None
    unit = (f.get("value_unit") or "").lower()
    if unit and re.fullmatch(DURATION_WORDS, unit):
        return f"{key} carries a duration unit {unit!r}"
    v = re.escape(val)
    near_duration = re.search(rf"{v}\s*{DURATION_WORDS}", ev, re.I)
    near_distance = re.search(rf"{v}\s*(km|kms|kilomet)", ev, re.I)
    if near_duration and not near_distance:
        return f"{key}={val} but the quote reads as a duration"
    return None


def rule4_units_in_unit_field(f) -> str | None:
    """The NUMBER must be machine-readable somewhere.

    "203 km" in `value` is fine and is what the contract asks for -- as long as
    value_number carries 203. It is only a defect when the number exists solely
    glued to a unit inside the text, because then nothing can filter or sort on it.
    """
    val, unit = (f.get("value") or "").strip(), (f.get("value_unit") or "").strip()
    if f.get("value_number") is not None:
        return None
    if unit and val.lower().endswith(unit.lower()) and len(val) > len(unit):
        if re.match(r"^-?[\d.,]+\s*", val) and re.search(r"\d", val):
            return f"number only readable inside the text: {val!r} + unit {unit!r}, no value_number"
    return None


def rule6_joined_values(f) -> str | None:
    """'Eco-certified; strong local feedback' is two facts wearing one value."""
    val = (f.get("value") or "").strip()
    if f.get("value_type") == "list":
        return None
    if ";" in val:
        return f"joined value (semicolon): {val!r}"
    parts = [p.strip() for p in val.split(",") if p.strip()]
    if len(parts) >= 3 and all(len(p) > 3 for p in parts):
        return f"joined value ({len(parts)} comma-separated): {val!r}"
    return None


def rule7_quote_on_page(f, haystack: str) -> str | None:
    """The quote must actually be on the page. Checked against the OCR/text
    layer where one exists -- ground truth no vision model produced."""
    if f.get("evidence_type") == "visual":
        return None                    # rule 9 handles visual evidence
    ev = _norm(f.get("evidence"))[:60]
    if not ev:
        return "no evidence quote"
    if ev not in haystack:
        return f"quote not found on page: {(f.get('evidence') or '')[:70]!r}"
    return None


def rule9_visual_cites_symbol(f) -> str | None:
    """A photograph never creates a fact on its own.

    3 of 17 visual facts in the first run were inferred from decorative
    photos. The grounding check passes on these -- the quote is real, the
    inference is not -- so this is the only rule that catches them.
    """
    if f.get("evidence_type") != "visual":
        return None
    ev = (f.get("evidence") or "").lower()
    # A gallery label is a picture's title, not a claim. Verified across the
    # corpus: 46 of 169 verification failures came from captions that only
    # NAME the pictured room -- "POOL VIEW" -> has_pool=true on documents whose
    # text never mentions a pool. A caption only counts as evidence when it
    # states something beyond the room's name.
    quoted = re.findall(r"['\"‘’“”]([^'\"‘’“”]{2,60})"
                        r"['\"‘’“”]", f.get("evidence") or "")
    if "caption" in ev or "label" in ev:
        for q in quoted:
            words = [w for w in re.split(r"[^A-Za-z0-9]+", q) if w]
            # a bare name: few words, no digits, no yes/no marker
            if (len(words) <= 4 and not any(w.isdigit() for w in words)
                    and not any(w.lower() in ("yes", "no", "available", "not") for w in words)):
                return (f"caption {q!r} only names the picture; a gallery label "
                        f"is not a claim about the property")

    if any(s in ev for s in SYMBOL_WORDS):
        return None
    if any(ev.lstrip().startswith(p) or p in ev for p in PHOTO_OPENERS):
        return f"visual fact inferred from a photograph, no symbol cited: {ev[:70]!r}"
    return f"visual fact cites no symbol: {ev[:70]!r}"


# ---------------------------------------------------------------- cross-fact
def rule3_single_valued(facts, v) -> dict[int, str]:
    """nearest_X means THE closest one. It cannot be scoped and cannot repeat.

    Found by the Opus verifier on all three pilot documents: the model recorded
    the FAR airport under nearest_airport, sometimes with scope_key "rank" =
    "alternate airport". Scoping does not repair it -- the KEY still asserts
    "nearest", so a nearest-airport lookup returns a 5-hour drive when a
    2-hour one exists. A ranked alternate belongs under its own key, and
    "nearest" is DERIVED by taking the minimum, never asserted.
    """
    # "the nearest X" style keys: scalar AND naming another entity.
    single = {k for k in v.scalar_keys if v.relation_keys.get(k)}
    bad, seen = {}, {}
    for i, f in enumerate(facts):
        k = f.get("key")
        if k not in single:
            continue
        if f.get("scope_key"):
            bad[i] = (f"{k} is single-valued and cannot carry a scope "
                      f"({f.get('scope_key')}={f.get('scope_value')!r}); a ranked "
                      f"alternate needs its own key, and 'nearest' is derived "
                      f"from the minimum distance")
            continue
        ent = _norm(f.get("entity_name"))
        prev = seen.get((ent, k))
        if prev is not None and _norm(facts[prev].get("value")) != _norm(f.get("value")):
            bad[i] = (f"{k} is single-valued but a second unscoped value appeared "
                      f"({facts[prev].get('value')!r} vs {f.get('value')!r})")
        else:
            seen[(ent, k)] = i
    return bad


def rule3b_nearest_is_actually_nearest(facts, v) -> dict[int, str]:
    """Cross-check the claim against the distances on the same page.

    If nearest_airport is asserted and the page also gives a SMALLER
    airport_km somewhere else, the label is on the wrong airport. The
    key -> distance-key pairing is derived from the vocabulary.
    """
    bad = {}
    dist_key = {k: v.sibling(k, "distance") for k in v.relation_keys}
    dist_key = {k: d for k, d in dist_key.items() if d}
    by_ent_key = {}
    for f in facts:
        n = f.get("value_number")
        if n is None:
            v = (f.get("value") or "").replace(",", "").strip()
            n = float(v) if re.fullmatch(r"-?\d+(\.\d+)?", v) else None
        if n is not None:
            by_ent_key.setdefault((_norm(f.get("entity_name")), f.get("key")), []).append(n)

    for i, f in enumerate(facts):
        k = f.get("key")
        if k not in dist_key:
            continue
        ds = by_ent_key.get((_norm(f.get("entity_name")), dist_key[k]), [])
        if len(ds) > 1 and max(ds) > min(ds):
            bad[i] = (f"{k} asserted while {dist_key[k]} has several values "
                      f"({sorted(ds)}); nearest must be derived from the minimum")
    return bad


def rule5_dedup(facts) -> dict[int, str]:
    """Same fact from two sentences, or from two overlapping tiles."""
    bad, seen = {}, {}
    for i, f in enumerate(facts):
        k = (_norm(f.get("entity_name")), f.get("key"), _norm(f.get("value")),
             f.get("scope_key"), _norm(f.get("scope_value")))
        if k in seen:
            bad[i] = f"duplicate of fact #{seen[k]}"
        else:
            seen[k] = i
    return bad


def rule8_subpart_needs_scope(facts, v) -> dict[int, str]:
    """room_count=12 (property) and room_count=2 (one category) are
    indistinguishable without a scope. 'How many rooms?' could answer 2."""
    bad = {}
    groups: dict[tuple, list[int]] = {}
    for i, f in enumerate(facts):
        groups.setdefault((_norm(f.get("entity_name")), f.get("key")), []).append(i)
    for (_, key), idxs in groups.items():
        if key not in v.scalar_keys or len(idxs) < 2:
            continue
        vals = {_norm(facts[i].get("value")) for i in idxs}
        unscoped = [i for i in idxs if not facts[i].get("scope_key")]
        if len(vals) > 1 and len(unscoped) > 1:
            for i in unscoped[1:]:
                bad[i] = (f"{key} has {len(vals)} different values and "
                          f"{len(unscoped)} of them carry no scope")
    return bad


# ---------------------------------------------------------------- driver
def validate(facts: list[dict], page_text: str, vocabulary) -> tuple[list[dict], list[tuple[dict, str]]]:
    """Returns (accepted, [(fact, reason), ...]).

    Every rule that needs to know something about a label asks the VOCABULARY,
    never a list written into this file. Adding a domain means adding rows.
    """
    hay = _norm(page_text)
    reasons: dict[int, str] = {}

    for i, f in enumerate(facts):
        for check in (rule1_boolean, rule2_distance_not_duration):
            r = check(f, vocabulary)
            if r:
                reasons.setdefault(i, r)
        for check in (rule4_units_in_unit_field, rule6_joined_values,
                      rule9_visual_cites_symbol):
            r = check(f)
            if r:
                reasons.setdefault(i, r)
        r = rule7_quote_on_page(f, hay)
        if r:
            reasons.setdefault(i, r)

    for cross in (rule3_single_valued, rule3b_nearest_is_actually_nearest,
                  rule8_subpart_needs_scope):
        for i, r in cross(facts, vocabulary).items():
            reasons.setdefault(i, r)
    for i, r in rule5_dedup(facts).items():
        reasons.setdefault(i, r)

    accepted = [f for i, f in enumerate(facts) if i not in reasons]
    rejected = [(facts[i], r) for i, r in sorted(reasons.items())]
    return accepted, rejected


def demo() -> None:
    page = "The lodge is 4 hours from Jabalpur Airport. 12 units in 3 categories. Deluxe Room 04 keys."
    facts = [
        {"key": "has_pool", "value": "No swimming pool", "evidence": "The lodge is 4 hours",
         "evidence_type": "text", "entity_name": "X"},
        {"key": "airport_km", "value": "4", "evidence": "4 hours from Jabalpur Airport",
         "evidence_type": "text", "entity_name": "X"},
        {"key": "usp", "value": "5 acres", "value_unit": "acres", "evidence": "12 units",
         "evidence_type": "text", "entity_name": "X"},
        {"key": "activities", "value": "wildlife viewing", "evidence_type": "visual",
         "evidence": "photographs showing marmots and brown bears", "entity_name": "X"},
        {"key": "has_spa", "value": "false", "evidence_type": "visual",
         "evidence": "massage table icon with the word 'No' next to it", "entity_name": "X"},
        # the corpus-wide failure: a gallery label read as an amenity claim
        {"key": "has_pool", "value": "true", "evidence_type": "visual",
         "evidence": "photo caption reading 'POOL VIEW'", "entity_name": "Y"},
        {"key": "room_count", "value": "12", "evidence": "12 units in 3 categories",
         "evidence_type": "text", "entity_name": "X"},
        {"key": "room_count", "value": "4", "evidence": "Deluxe Room 04 keys",
         "evidence_type": "text", "entity_name": "X"},
        {"key": "dining", "value": "Nowhere on the page", "evidence": "invented quote entirely",
         "evidence_type": "text", "entity_name": "X"},
        # the bug the Opus verifier found on all three pilot documents
        {"key": "nearest_airport", "value": "Guwahati Airport", "evidence": "12 units",
         "evidence_type": "text", "entity_name": "X",
         "scope_key": "rank", "scope_value": "alternate airport"},
    ]
    from backend.ingest.vocab import SEED, Label, Vocabulary
    v = Vocabulary({k: Label(k, *vals, "approved") for k, vals in SEED.items()})
    ok, bad = validate(facts, page, v)
    got = {f["key"] + "=" + f["value"] for f, _ in bad}
    assert "has_pool=No swimming pool" in got, "rule 1 missed"
    assert "airport_km=4" in got, "rule 2 missed"
    assert "usp=5 acres" in got, "rule 4 missed"
    assert "activities=wildlife viewing" in got, "rule 9 missed"
    assert "dining=Nowhere on the page" in got, "rule 7 missed"
    assert any(f["key"] == "room_count" for f, _ in bad), "rule 8 missed"
    assert any(f["key"] == "has_spa" for f in ok), "rule 9 wrongly rejected a real icon"
    assert "nearest_airport=Guwahati Airport" in got, "rule 3 missed the scoped-nearest bug"
    assert "has_pool=true" in got, "rule 9 missed the bare gallery-label caption"
    print(f"validate OK - {len(ok)} accepted, {len(bad)} rejected")
    for f, r in bad:
        print(f"   REJECT {f['key']:<14} {r}")


if __name__ == "__main__":
    demo()
