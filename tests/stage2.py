"""Stage 2 — the graded regression suite. Fifteen questions, three scores.

    python -m tests.stage2 --plan            # what it would run, and the cost. FREE.
    python -m tests.stage2 --smoke           # 4 cheap cases, ~₹3
    python -m tests.stage2 --budget 22       # the full run

Three scores, kept separate on purpose. An answer can be right off the wrong
document, and a wrong answer can cite perfectly:

  RETRIEVAL  did the documents that hold the answer actually get cited?
  ANSWER     is the content right, and does it refuse where it should?
  CITATIONS  does every [n] marker point at a source that exists?

The third is mechanical and catches the worst failure silently: a confident
answer citing [7] when only five sources were supplied.

Every expectation below was read out of the corpus, not assumed.
"""
import argparse
import re
import sys
import time

from backend import config, db, retry
from backend.ingest import vocab as vocab_mod
from backend.query import answer as answer_mod

REFUSAL = ("do not state", "does not state", "not stated", "no record", "not recorded",
           "not available", "not provide", "not contain", "not mention", "not specify",
           "does not appear", "no information", "not covered", "unrecorded", "unknown")

# id, section, question, must_cite, must_contain, forbid, expect
CASES = [
    ("overview", "1 Overview",
     "Tell me about Bagh Tola. What kind of property is it and what experience does it offer?",
     ["Bagh Tola"], ["tent"], [], "answer"),

    ("airport", "2 Location",
     "What is the nearest airport to Bagh Tola, and how far is it?",
     ["Bagh Tola"], ["jabalpur", "203"], [], "answer"),

    ("gate", "3 Safari",
     "Which safari gate is closest to Bagh Tola, and how long does it take to reach?",
     ["Bagh Tola"], ["khitauli"], [], "answer"),

    ("activities", "4 Activities",
     "What can guests do at Ramathra Fort apart from safari?",
     ["Ramathra"], ["boat"], [], "answer"),

    ("wifi", "5 Facilities",
     "Does Nature's Nest Goa have Wi-Fi?",
     ["Nature's Nest"], ["wi-fi", "wifi"], [], "answer"),

    ("vegan", "6 Food",
     "Can Rambha Palace cater for vegan guests?",
     ["Rambha"], ["vegan"], [], "answer"),

    ("children", "7 Families",
     "Is The Baasa Bandhavgarh suitable for families with children?",
     ["Baasa"], ["child"], [], "answer"),

    ("conservation", "8 Conservation",
     "What conservation or community initiatives does Haldu Tola support?",
     ["Haldu Tola"], ["communit"], [], "answer"),

    ("departure", "9 Itinerary",
     "A client flies out of Jabalpur at 14:30. What time should they leave Bagh Tola, "
     "allowing 2 hours at the airport?",
     ["Bagh Tola"], ["09:00"], ["09:35", "10:00"], "answer"),

    ("compare", "10 Sales",
     "Compare The Safari Lodge Kanha and Courtyard House Kanha for a luxury "
     "international client.",
     ["Safari Lodge Kanha", "Courtyard House Kanha"], ["kanha"], [], "answer"),

    ("spa_count", "11 Quick search",
     "How many of our properties have a spa?",
     [], ["18"], [], "answer"),

    ("multihop", "12 Additional",
     "Which properties near Kanha have a pool and fewer than 20 rooms?",
     ["Courtyard House Kanha", "Safari Lodge Kanha"],
     ["courtyard", "safari lodge"], [], "answer"),

    # ---- the corpus cannot answer these. Refusing IS the pass condition. ----
    ("currency", "5 Facilities · gap",
     "Does Ramathra Fort accept payment in USD or GBP?",
     [], [], [], "refuse"),

    ("drivetime", "9 Itinerary · gap",
     "What is the driving time from Ramathra Fort to Kurja Jawai?",
     [], [], ["approximately 4", "approximately 5", "roughly 4", "roughly 5"], "refuse"),

    # This replaced "does Bagh Tola arrange safari permits and bookings?", which
    # was a BAD TEST. The word "permit" appears in no document, so I expected a
    # refusal -- but the page says "Forest Department jeeps (booked via lodge)",
    # which answers the booking half honestly. The system was right and the test
    # was wrong. A gap case has to be a topic the corpus cannot touch AT ALL.
    ("usb", "5 Facilities · gap",
     "Does Bagh Tola provide USB charging points in the rooms?",
     [], [], [], "refuse"),
]

SMOKE = ("airport", "vegan", "currency", "spa_count")
CITE = re.compile(r"\[(\d+)\]")


# A number with a unit is a claim about the documents. Times are excluded on
# purpose: the calculator DERIVES 09:00, so it is correctly absent from any page.
MEASURE = re.compile(
    r"(\d[\d,]*(?:\.\d+)?)\s*(km|kms|kilometre|kilometer|rooms?|units?|keys?|"
    r"ft|feet|acres?|hours?|hrs?|minutes?|mins?)\b", re.I)


FAMILY = {
    "distance": ("km", "kms", "kilometre", "kilometres", "kilometer", "kilometers"),
    "time": ("hour", "hours", "hr", "hrs", "minute", "minutes", "min", "mins"),
    "rooms": ("room", "rooms", "unit", "units", "key", "keys"),
    "area": ("ft", "feet", "acre", "acres"),
}


def _family(unit: str) -> str:
    unit = unit.lower().rstrip(".")
    for name, members in FAMILY.items():
        if unit in members:
            return name
    return unit


def unsupported_numbers(text: str, cited: str) -> list:
    """Numbers the answer states that the sources do not state WITH THAT UNIT.

    Two rounds of this. First it checked nothing, so "Jabalpur airport is 999 km
    away" scored green. Then it checked the number alone, which let "3.5 km"
    through because the page said "3.5 hours" -- the right digits attached to
    the wrong quantity, which is exactly how a plausible wrong answer reads.
    """
    if not cited:
        return []
    haystack = cited.replace(",", "")
    bad = []
    for raw, unit in MEASURE.findall(text):
        n = raw.replace(",", "")
        want = _family(unit)
        supported = False
        for c_raw, c_unit in MEASURE.findall(haystack):
            if _family(c_unit) != want:
                continue
            if c_raw.replace(",", "") == n or _same_number(c_raw, n):
                supported = True
                break
        if not supported:
            bad.append(f"{raw} {unit}")
    return bad[:5]


def _same_number(a: str, b: str) -> bool:
    try:
        return abs(float(a.replace(",", "")) - float(b)) < 1e-9
    except ValueError:
        return False


def grade(case, text, sources, cited: str = ""):
    """Returns (retrieval_ok, answer_ok, citations_ok, notes)."""
    _id, _sec, _q, must_cite, must_contain, forbid, expect = case
    low, notes = text.lower(), []
    paths = " | ".join(s["rel_path"] for s in sources).lower()

    retrieval = all(c.lower() in paths for c in must_cite)
    if not retrieval:
        notes.append("missing doc: " + ", ".join(c for c in must_cite
                                                 if c.lower() not in paths))

    refused = any(p in low for p in REFUSAL)
    if expect == "refuse":
        answer_ok = refused
        if not refused:
            notes.append("should have refused")
    else:
        answer_ok = any(m in low for m in must_contain) if must_contain else True
        if not answer_ok:
            notes.append(f"none of {must_contain} in answer")
    hit = [f for f in forbid if f in low]
    if hit:
        answer_ok = False
        notes.append(f"forbidden: {hit}")

    bad = [n for n in CITE.findall(text) if not 1 <= int(n) <= len(sources)]
    citations = not bad
    if bad:
        notes.append(f"citations out of range: {sorted(set(bad))} of {len(sources)}")

    # A citation that points at a real source but does not support the number is
    # the failure that matters. This is the entailment half of the score.
    invented = unsupported_numbers(text, cited)
    if invented:
        citations = False
        notes.append(f"numbers not in any cited source: {invented}")
    return retrieval, answer_ok, citations, notes


def cited_text(cur, sources) -> str:
    """EVERYTHING the model was given for these documents, not just their prose.

    The first version compared only against transcriptions and flagged
    "15 minutes (0.25 hours)" as invented. The page does say 15 minutes; 0.25 is
    OUR normalisation of it, handed over in the graph block. A number we supplied
    is not a number the model made up, so facts and connection values count as
    support too.
    """
    shas = [s["sha1"] for s in sources if s.get("sha1")]
    if not shas:
        return ""
    parts = []
    cur.execute("select transcription from documents where sha1 = any(%s)", (shas,))
    parts += [r[0] or "" for r in cur.fetchall()]
    cur.execute("select coalesce(value_text,''), coalesce(value_unit,'') "
                "from fact_evidence where sha1 = any(%s)", (shas,))
    parts += [f"{a} {b}" for a, b in cur.fetchall()]
    # UNITS MATTER HERE. The check is unit-aware, so bare numbers in this
    # haystack support nothing: "5 0.25" cannot back "0.25 hours". These are our
    # own normalised values and the model is right to quote them, so they go in
    # spelled the way an answer would say them.
    cur.execute("select props->>'distance_km', props->>'duration_h' "
                "from connections where sha1 = any(%s)", (shas,))
    for km, hours in cur.fetchall():
        if km:
            parts.append(f"{km} km")
        if hours:
            parts.append(f"{hours} hours")
    return "\n".join(parts)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--budget", type=float, default=config.TEST_BUDGET_INR)
    ap.add_argument("--only", default="")
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--cheap", action="store_true", help="force flash even on AGENT")
    ap.add_argument("--plan", action="store_true", help="list the cases and exit. Free.")
    args = ap.parse_args()

    picked = [c for c in CASES
              if (not args.only or c[0] == args.only)
              and (not args.smoke or c[0] in SMOKE)]

    if args.plan:
        print(f"{'id':<14} {'section':<22} expect  question")
        for c in picked:
            print(f"{c[0]:<14} {c[1]:<22} {c[6]:<7} {c[2][:60]}")
        print(f"\n{len(picked)} cases. Estimated ₹18–22 at full, ~₹6 with --cheap.")
        print("Nothing was called. Add --budget to actually run it.")
        return

    client = answer_mod.client_for()
    vocabulary = vocab_mod.load()
    model = config.ANSWER_MODEL if args.cheap else None
    spent, rows = 0.0, []
    print(f"{len(picked)} cases · budget ₹{args.budget}"
          + ("  · flash forced" if args.cheap else ""))

    with db.connect() as conn, conn.cursor() as cur:
        for case in picked:
            cid, section, question = case[0], case[1], case[2]
            if spent >= args.budget:
                print(f"\n⛔ budget ₹{args.budget} reached — {len(rows)} of "
                      f"{len(picked)} cases ran")
                break
            text, sources, mode, cost, t0 = "", [], "", 0.0, time.time()
            for kind, p in answer_mod.converse(cur, question, vocabulary, client,
                                               answer_model=model):
                if kind == "token":
                    text += p
                elif kind == "mode":
                    mode = p["mode"]
                elif kind == "sources":
                    sources = p["sources"]
                elif kind == "done":
                    cost = p["cost_inr"]
            spent += cost
            r, a, c, notes = grade(case, text, sources, cited_text(cur, sources))
            rows.append((cid, section, mode, r, a, c, cost, notes))
            print(f"\n▶ {cid} [{section}] {mode} ₹{cost} {time.time() - t0:.0f}s")
            print(f"   retrieval {'✅' if r else '❌'}  answer {'✅' if a else '❌'}  "
                  f"citations {'✅' if c else '❌'}"
                  + ("   " + "; ".join(notes) if notes else ""))
            print(f"   {text.strip()[:260]}")

    print(f"\n{'=' * 74}\n{'id':<14} {'section':<22} {'mode':<7} ret ans cit    INR")
    for cid, section, mode, r, a, c, cost, _ in rows:
        print(f"{cid:<14} {section:<22} {mode:<7} "
              f"{'✅' if r else '❌'}   {'✅' if a else '❌'}   {'✅' if c else '❌'}  {cost:>6}")
    n = len(rows) or 1
    print(f"\nretrieval {sum(r[3] for r in rows)}/{n} · "
          f"answer {sum(r[4] for r in rows)}/{n} · "
          f"citations {sum(r[5] for r in rows)}/{n} · spent ₹{spent:.2f}")
    sys.exit(0 if all(r[3] and r[4] and r[5] for r in rows) else 1)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        why = retry.explain(exc)
        if not why:
            raise
        sys.exit(f"\n✗ {why}")
