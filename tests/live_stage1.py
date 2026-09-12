"""Stage 1 acceptance against the real Gemini API and the real corpus.

    python -m tests.live_stage1              # all cases
    python -m tests.live_stage1 --budget 10  # stop early
    python -m tests.live_stage1 --only drive

Costs money. Stops dead when the budget is reached rather than overrunning it.
"""
import argparse
import sys

from backend import config, db, retry
from backend.ingest import vocab as vocab_mod
from backend.query import answer as answer_mod

# (id, question, expected mode or None, a check over the lowercased answer)
CASES = [
    ("pool", "Does Ramathra Fort have a swimming pool?", "fast", None),
    ("count", "How many of our properties have a swimming pool?", "fast",
     lambda a: "31" in a and ("unknown" in a or "not record" in a or "unrecorded" in a
                              or "no informa" in a)),
    ("city", "Which hotels do we have in Bhopal?", None,
     lambda a: "sadar manzil" in a),
    ("near", "Which properties are near Kanha National Park?", None,
     lambda a: "outpost 12" in a and "safari lodge" in a),
    ("conflict", "How many rooms does Oberoi Rajgarh Palace have?", None,
     lambda a: "65" in a and "66" in a),
    ("compare", "Compare Ramathra Fort and Kurja Jawai for a family with children.",
     "think", None),
    ("multihop", "Which properties near Kanha have a pool and fewer than 20 rooms?",
     "agent", None),
    ("drive", "What is the driving time from Ramathra Fort to Kurja Jawai?", None,
     lambda a: not any(w in a for w in ("hours from ramathra", "approximately"))
     and any(w in a for w in ("not state", "not record", "no record", "does not",
                              "not available", "not provide", "not contain"))),
    ("depart", "A client flies out of Jaipur at 14:30. What time should they leave "
               "Ramathra Fort, allowing 2 hours at the airport?", None, None),
    # a recommendation is a judgement, not a lookup. This case caught the answer
    # refusing to rank at all, which is a non-answer for a sales team.
    ("rank", "Across all our data, which are the strongest properties overall and why?",
     None, lambda a: not a.strip().startswith("the provided documents do not")
     and sum(n in a for n in ("oberoi", "taj", "bagh tola", "ramathra", "postcard",
                              "haveli", "kurja", "baasa")) >= 2),
    ("absent", "What is the star rating of Bagh Tola?", None,
     lambda a: any(w in a for w in ("not state", "not record", "no record", "does not",
                                    "not available", "not provide"))),
]


SMOKE = ("count", "drive", "city")      # ~₹2: a fast, a think, and the honesty case


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--budget", type=float, default=config.TEST_BUDGET_INR,
                    help=f"rupees; stops dead at this (default {config.TEST_BUDGET_INR})")
    ap.add_argument("--only", default="")
    ap.add_argument("--smoke", action="store_true",
                    help=f"just {', '.join(SMOKE)} — the cheap confidence check")
    ap.add_argument("--cheap", action="store_true",
                    help="force flash everywhere, including AGENT (~5x cheaper)")
    args = ap.parse_args()

    client = answer_mod.client_for()
    vocabulary = vocab_mod.load()
    spent, results = 0.0, []
    model = config.ANSWER_MODEL if args.cheap else None
    print(f"budget ₹{args.budget}"
          + ("  · flash forced" if args.cheap else "")
          + ("  · smoke only" if args.smoke else ""))

    with db.connect() as conn, conn.cursor() as cur:
        for cid, question, want_mode, check in CASES:
            if args.only and args.only != cid:
                continue
            if args.smoke and cid not in SMOKE:
                continue
            if spent >= args.budget:
                print(f"\n⛔ budget ₹{args.budget} reached, stopping")
                break
            print(f"\n{'=' * 78}\n▶ {cid}: {question}")
            text, mode, rounds, cost, truncated = "", "", 0, 0.0, False
            for kind, p in answer_mod.converse(cur, question, vocabulary, client,
                                               answer_model=model):
                if kind == "mode":
                    mode = p["mode"]
                    print(f"   mode={mode}  why={p.get('why', '')!r}")
                elif kind == "step":
                    print(f"   round {p['round']}: " + (
                        f"needs {p['missing']}" if p.get("missing") else
                        f"found={p['found']} opened={p['opened']} "
                        f"count={p.get('count')} chars={p['chars']:,}"))
                elif kind == "token":
                    text += p
                elif kind == "done":
                    rounds, cost, truncated = p["rounds"], p["cost_inr"], p["truncated"]
            spent += cost
            print(f"\n   ANSWER: {text.strip()[:900]}")

            ok, why = True, []
            if want_mode and mode != want_mode:
                ok, _ = False, why.append(f"mode {mode}, wanted {want_mode}")
            if check and not check(text.lower()):
                ok, _ = False, why.append("answer check failed")
            results.append((cid, ok, mode, rounds, cost, truncated))
            print(f"   {'✅ PASS' if ok else '❌ FAIL ' + '; '.join(why)}"
                  f"   {rounds} round(s) ₹{cost}  running ₹{spent:.2f}")

    print(f"\n{'=' * 78}\n{'case':<10} {'ok':<4} {'mode':<7} {'rnds':<5} {'INR':<6} cut")
    for cid, ok, mode, rounds, cost, cut in results:
        print(f"{cid:<10} {'✅' if ok else '❌':<4} {mode:<7} {rounds:<5} {cost:<6} "
              f"{'⚠' if cut else ''}")
    passed = sum(1 for r in results if r[1])
    print(f"\n{passed}/{len(results)} passed · spent ₹{spent:.2f}")
    sys.exit(0 if passed == len(results) else 1)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        why = retry.explain(exc)
        if not why:
            raise
        sys.exit(f"\n✗ {why}")
