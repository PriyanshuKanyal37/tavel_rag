"""Ask the knowledge base a question.

    python -m backend.query.ask "Which lodges have a pool and under 20 rooms?"
    python -m backend.query.ask --chat            # multi-turn, keeps the working set
    python -m backend.query.ask --show-thinking "Compare A and B"

Progress prints to stderr, the answer to stdout, so `... > out.txt` keeps only
the answer. In agent mode the first word can be fifteen seconds away, which is
why the steps stream as they happen.
"""
import argparse
import sys
import time

from backend import db, retry
from backend.ingest import vocab as vocab_mod
from backend.query import answer as answer_mod

DIM, OFF = "\x1b[2m", "\x1b[0m"
BADGE = {"fast": "⚡ fast", "think": "🤔 thinking", "agent": "🔁 researching"}


def _err(text: str) -> None:
    print(f"{DIM}{text}{OFF}", file=sys.stderr, flush=True)


def ask(cur, question: str, vocabulary, client, history: str = "",
        held: list = None, show_thinking: bool = False, quiet: bool = False):
    """Prints the answer. Returns (text, cost_inr, opened_sha1s)."""
    out, opened, thinking = [], list(held or []), False
    for kind, payload in answer_mod.converse(
            cur, question, vocabulary, client, history=history, held=held):
        if kind == "mode" and not quiet:
            why = f" — {payload['why']}" if payload.get("why") else ""
            tag = " (escalated)" if payload.get("escalated") else ""
            _err(f"  {BADGE.get(payload['mode'], payload['mode'])}{tag}{why}"
                 f"  ~{payload['est_seconds']}s")
        elif kind == "step" and not quiet:
            if payload.get("missing"):
                _err(f"    round {payload['round']}: still needs {payload['missing']}")
            else:
                bits = [f"found {payload['found']}", f"{payload['opened']} opened",
                        f"{payload['chars']:,} chars"]
                if payload.get("count") is not None:
                    bits.insert(0, f"count {payload['count']}")
                _err(f"    round {payload['round']}: " + ", ".join(bits))
        elif kind == "thought":
            if show_thinking:
                if not thinking:
                    _err("    ── thinking ──")
                    thinking = True
                print(f"{DIM}{payload}{OFF}", file=sys.stderr, end="", flush=True)
        elif kind == "token":
            out.append(payload)
            print(payload, end="", flush=True)
        elif kind == "sources":
            opened = [s["sha1"] for s in payload["sources"]]
            if not quiet:
                print()
                _err("  sources: " + " ".join(
                    f"[{i}]{s['rel_path'].split(chr(92))[-1][:26]}"
                    for i, s in enumerate(payload["sources"], 1)) or "  sources: none")
        elif kind == "done" and not quiet:
            d = payload
            cut = "  ⚠ cut short by a limit" if d["truncated"] else ""
            _err(f"  {d['mode']} · {d['rounds']} round(s) · {d['seconds']}s · "
                 f"₹{d['cost_inr']}{cut}")
            return "".join(out), d["cost_inr"], opened
    return "".join(out), 0.0, opened


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("question", nargs="*")
    ap.add_argument("--chat", action="store_true", help="multi-turn")
    ap.add_argument("--show-thinking", action="store_true")
    ap.add_argument("--quiet", action="store_true", help="answer only")
    args = ap.parse_args()

    client = answer_mod.client_for()
    vocabulary = vocab_mod.load()
    spent, history, held = 0.0, [], []

    with db.connect() as conn, conn.cursor() as cur:
        if not args.chat:
            q = " ".join(args.question)
            if not q:
                sys.exit("give a question, or --chat")
            _, cost, _ = ask(cur, q, vocabulary, client,
                             show_thinking=args.show_thinking, quiet=args.quiet)
            return

        print("chat — blank line or ctrl-c to leave\n")
        while True:
            try:
                q = input("› ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if not q:
                break
            t = time.time()
            text, cost, opened = ask(
                cur, q, vocabulary, client, history="\n".join(history[-10:]),
                held=held, show_thinking=args.show_thinking, quiet=args.quiet)
            spent += cost
            held = list(dict.fromkeys(held + opened))   # union, never replacement
            history += [f"Q: {q}", f"A: {text[:600]}"]
            _err(f"  session ₹{spent:.2f} · working set {len(held)} document(s) "
                 f"· {time.time() - t:.1f}s\n")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:                 # a service failure is not a crash
        why = retry.explain(exc)
        if not why:
            raise
        sys.exit(f"\n✗ {why}")
