"""How much of the question bank can this corpus POSSIBLY answer? Free, offline.

The architecture document estimates ~133 of 175 questions work today. That was
an architectural judgement, never a measurement. This measures the floor: for
each section of the bank, how many of the 51 documents contain any of the words
that section's questions are about.

It cannot tell you an answer is GOOD. It can tell you an answer is IMPOSSIBLE,
which is the half that was being guessed.

    python -m tests.corpus_coverage
"""
import sys

from backend import db, retry

# section -> the vocabulary its questions actually need in the text
SECTIONS = {
    "1 Overview": ["room", "unit", "cottage", "suite", "villa", "tent"],
    "2 Location": ["airport", "railway", "railhead", "station", "km", "drive"],
    "3 Safari": ["safari", "gate", "zone", "naturalist", "jeep", "permit"],
    "4 Activities": ["activit", "experience", "walk", "cycl", "village", "birding"],
    "5 Facilities": ["pool", "spa", "wi-fi", "wifi", "gym", "laundry", "bar"],
    "6 Food": ["cuisine", "dining", "meal", "vegetarian", "vegan", "kitchen"],
    "7 Families": ["child", "family", "families", "honeymoon", "elderly", "senior"],
    "8 Conservation": ["conservation", "community", "sustainab", "local employ"],
    "9 Itinerary": ["hour", "hrs", "night", "combine", "route", "itinerar"],
    "10 Sales": ["recommend", "ideal for", "best suited", "highlight", "usp"],
    "11 Quick search": ["pool", "spa", "room", "private", "jeep"],
    "12 Additional": ["photograph", "shared", "full day", "buffer", "festival", "closure"],
}

# things the bank asks about that are simply not in this corpus at all
KNOWN_GAPS = ["gluten", "packed breakfast", "star rating", "currency exchange",
              "tipping box", "adapter", "usb", "generator", "wheelchair"]


def main() -> None:
    with db.connect() as conn, conn.cursor() as cur:
        cur.execute("select count(*) from documents")
        total = cur.fetchone()[0]

        def docs_with(term: str) -> int:
            cur.execute("select count(*) from documents where lower(transcription) like %s",
                        (f"%{term.lower()}%",))
            return cur.fetchone()[0]

        print(f"{total} documents\n")
        print(f"{'section':<18} {'best term':<18} {'docs':<7} coverage")
        print("-" * 60)
        weak = []
        for name, terms in SECTIONS.items():
            hits = sorted(((docs_with(t), t) for t in terms), reverse=True)
            best_n, best_t = hits[0]
            pct = 100 * best_n // total
            bar = "█" * (pct // 5) + "·" * (20 - pct // 5)
            print(f"{name:<18} {best_t:<18} {best_n:<7} {bar} {pct}%")
            if pct < 50:
                weak.append((name, best_t, best_n))

        print("\nper-term detail for the weakest sections")
        for name, _, _ in weak:
            row = ", ".join(f"{t}={docs_with(t)}" for t in SECTIONS[name])
            print(f"  {name:<18} {row}")

        print("\ntopics the bank asks about that appear in NO document")
        for g in KNOWN_GAPS:
            n = docs_with(g)
            flag = "  ← absent" if n == 0 else ""
            print(f"  {g:<20} {n} document(s){flag}")

        print("\nRead this as a ceiling, not a score. A section at 20% means four")
        print("questions in five must be answered 'the documents do not say'.")


if __name__ == "__main__":
    try:
        retry.call(main, tries=20, delay=4)
    except Exception as exc:
        why = retry.explain(exc)
        if not why:
            raise
        sys.exit(f"\n✗ {why}")
