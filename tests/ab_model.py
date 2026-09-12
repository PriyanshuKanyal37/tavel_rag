"""Flash vs Pro for the ANSWER, on judgement-heavy questions.

    python -m tests.ab_model
    python -m tests.ab_model --only compare

The plan is computed ONCE per question and replayed to both models, so retrieval
and the prompt are identical and the only variable is who writes the answer.
Costs real money: pro is roughly 7x flash per token.
"""
import argparse
import copy
import sys
import time

from backend import config, db
from backend.ingest import vocab as vocab_mod
from backend.query import answer as answer_mod

QUESTIONS = [
    ("compare", "Compare Ramathra Fort and Kurja Jawai for a family with children."),
    ("photographer", "Which property near Bandhavgarh would you recommend for a serious "
                     "wildlife photographer, and why?"),
    ("multihop", "Which properties near Kanha have a pool and fewer than 20 rooms?"),
    ("honesty", "What is the driving time from Ramathra Fort to Kurja Jawai?"),
]
MODELS = [config.ANSWER_MODEL, config.ANSWER_MODEL_DEEP]


def run(cur, question, spec, client, model):
    text, cost, secs = "", 0.0, time.time()
    for kind, p in answer_mod.converse(
            cur, question, None, client,
            plan_fn=lambda *a, **k: copy.deepcopy(spec), answer_model=model):
        if kind == "token":
            text += p
        elif kind == "done":
            cost = p["cost_inr"]
    return text.strip(), cost, time.time() - secs


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    # this run cost ₹40 once and does not need repeating; its conclusion is in
    # answer.model_for(). Raise the budget deliberately if you rerun it.
    ap.add_argument("--budget", type=float, default=config.TEST_BUDGET_INR)
    args = ap.parse_args()

    client = answer_mod.client_for()
    vocabulary = vocab_mod.load()
    spent, rows = 0.0, []

    with db.connect() as conn, conn.cursor() as cur:
        for qid, question in QUESTIONS:
            if args.only and args.only != qid:
                continue
            if spent >= args.budget:
                print(f"\n⛔ budget ₹{args.budget} reached")
                break
            spec = answer_mod.plan_mod.make(question, vocabulary, "", client)
            spent += spec.get("_cost_inr", 0.0)
            print(f"\n{'=' * 78}\n▶ {qid} [mode={spec['mode']}]: {question}")
            for model in MODELS:
                text, cost, secs = run(cur, question, spec, client, model)
                spent += cost
                print(f"\n── {model}  ₹{cost}  {secs:.1f}s  {len(text)} chars\n{text[:1400]}")
                rows.append((qid, model, cost, round(secs, 1), len(text)))

    print(f"\n{'=' * 78}\n{'question':<14} {'model':<26} {'INR':<7} {'secs':<6} chars")
    for r in rows:
        print(f"{r[0]:<14} {r[1]:<26} {r[2]:<7} {r[3]:<6} {r[4]}")
    print(f"\nspent ₹{spent:.2f}")
    print("\nJudge on: correct? every claim cited? admits what is missing? useful on a call?")


if __name__ == "__main__":
    sys.exit(main())
