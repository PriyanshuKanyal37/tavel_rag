"""What the model is told about the conversation so far.

THE BUG THIS REPLACES. The history was "the last 10 turns, each cut to 400
characters". Measured on a real 60-turn conversation that came to 296,124
characters, the model was handed 4,094 of them -- 1.4% -- against an input
window of 1,048,576 tokens. A 3,000-character answer was remembered as its
first 400, so a follow-up like "of those, which are in Rajasthan?" was asked
about a list the model could no longer see. That is not the model forgetting;
it is us not telling it.

The budget here is deliberately generous and still bounded, because history is
re-sent on EVERY question: a budget spent once is spent again on every later
turn in the same conversation. 48,000 characters is about 12,000 tokens, which
at flash input rates is well under a rupee per question, and covers a long real
conversation whole.

One turn may not crowd out the rest. A 20,000-character answer would eat half
the budget on its own, so a single turn is clipped -- at 4,000 characters, ten
times the old whole-history cap, which leaves essentially every real answer
intact.
"""
from __future__ import annotations

import re

# EVERY ANSWER RENUMBERS ITS OWN SOURCES FROM [1]. So "[3]" in a previous answer
# names a different document from "[3]" in this one, and leaving those numbers in
# the prompt invites the model to copy a marker that now points somewhere else --
# a citation chip opening the wrong file, which is the one thing this product
# exists to get right. Measured at up to 48 stale markers in a real conversation.
# They carry no meaning outside their own answer, so they go.
CITE = re.compile(r"\s*\[\d{1,3}\]")

# Looked at at all. A hard stop so a thousand-turn thread cannot be walked.
MAX_TURNS = 40
# One turn's share.
PER_TURN_CHARS = 4_000
# The whole history. ~12,000 tokens of a 1,048,576-token window.
TOTAL_CHARS = 48_000

CLIPPED = " …[earlier part of this message trimmed]"


def build(rows, budget: int = TOTAL_CHARS, per_turn: int = PER_TURN_CHARS) -> str:
    """Assemble the history text. `rows` are (role, text), NEWEST FIRST.

    Returns oldest-first, because that is the order it reads in. Newest turns
    are kept whole and the budget runs out at the far end, so what gets dropped
    is always the oldest thing -- never the question just asked.
    """
    kept, spent = [], 0
    for role, text in rows or []:
        body = " ".join(CITE.sub("", text or "").split())
        if not body:
            continue
        if len(body) > per_turn:
            # keep the START of the message: a list's opening names matter more
            # to a follow-up than its closing caveat
            body = (body[:per_turn].rsplit(" ", 1)[0] or body[:per_turn]) + CLIPPED
        line = f"{role}: {body}"
        if kept and spent + len(line) > budget:
            break
        kept.append(line)
        spent += len(line)
    return "\n".join(reversed(kept))


if __name__ == "__main__":                      # ponytail: self-check, no framework
    # a whole answer survives, where the old 400-char cut would have halved it
    long_answer = "The Postcard Hideaway has a pool. " * 60          # ~2,040 chars
    out = build([("assistant", long_answer), ("user", "which have a pool?")])
    assert long_answer.strip() in out, "a 2,000-char answer is kept whole"
    assert out.index("user:") < out.index("assistant:"), "oldest first"
    assert CLIPPED not in out, "nothing clipped when it fits"

    # one enormous turn is clipped, not allowed to eat the budget
    huge = "x" * 30_000
    out = build([("assistant", huge)])
    assert len(out) < PER_TURN_CHARS + len(CLIPPED) + 20, len(out)
    assert out.endswith(CLIPPED)

    # the budget drops the OLDEST turns, never the newest
    rows = [(("user" if i % 2 else "assistant"), f"turn {i} " + "y" * 3_000)
            for i in range(30)]                  # newest first, 30 turns
    out = build(rows)
    assert len(out) <= TOTAL_CHARS + PER_TURN_CHARS, len(out)
    assert "turn 0 " in out, "the newest turn is always present"
    assert "turn 29 " not in out, "the oldest is what gets dropped"

    # a single turn bigger than the whole budget still comes back, clipped
    out = build([("user", "z" * 200_000)])
    assert out.startswith("user: zzz") and out.endswith(CLIPPED)

    # degenerate inputs
    assert build([]) == "" and build(None) == ""
    assert build([("user", "   "), ("user", "real")]) == "user: real"

    # newlines inside a turn must not break the role-per-line shape
    out = build([("assistant", "line one\nline two\n\nline three")])
    assert out == "assistant: line one line two line three", out

    # stale citation numbers must never reach the prompt
    out = build([("assistant", "Bagh Tola is 203 km away [1], [2]. Kanha has a pool [13].")])
    for m in ("[1]", "[2]", "[13]"):
        assert m not in out, out
    assert "Bagh Tola is 203 km away" in out and "Kanha has a pool" in out, out
    assert not CITE.search(build([("assistant", "a [1] b [2] c [3]")]))

    print(f"history: all checks passed "
          f"({TOTAL_CHARS:,} chars total, {PER_TURN_CHARS:,} per turn, {MAX_TURNS} turns)")
