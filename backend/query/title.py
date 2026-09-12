"""Name a conversation once, from what it turned out to be about.

The opening message is a bad name and a cheap one: "hi" costs nothing and says
nothing. This module is the one paid step, and it runs exactly once per thread,
after two questions have actually needed the corpus.

Both questions go in, not just the first. Sending only the first would make the
call pointless -- it would be rewording a sentence we already have. The second
question is what says whether the thread is one subject or two, and that is the
only thing a title has to get right.
"""
from __future__ import annotations

from .. import config

# Measured against the sidebar, not chosen by taste: an entry shows about 34
# characters at 12px before the ellipsis eats the rest, so a six-word title is
# a four-word title plus "...". Ask for fewer words and they all survive.
MAX_CHARS = 40
MAX_QUESTIONS = 5

PROMPT = """Name this conversation the way a person would name a folder.

The questions asked, in order:
%s

Rules:
- 3 to 5 words. Never more than %d characters.
- Name the SUBJECT, not the act of asking. "Pool properties in Uttarakhand",
  never "User asks about pools".
- If the questions cover two subjects, name the one they spent most on.
- Use the names of places and properties when they appear; those are what
  someone will scan for.
- No quotes, no trailing full stop, no "Travel Inn" prefix -- every
  conversation here is about Travel Inn.
- Write it in the language the questions are written in."""

SCHEMA = {"type": "object", "required": ["title"],
          "properties": {"title": {"type": "string"}}}


def _tidy(text: str) -> str:
    """Trim to the sidebar's width, on a word boundary, and strip the habits
    models fall into: wrapping quotes, a trailing stop, a "Title:" preamble."""
    out = " ".join((text or "").split())
    if ":" in out[:12] and out.split(":", 1)[0].lower() in ("title", "name"):
        out = out.split(":", 1)[1].strip()
    out = out.strip("\"'“”‘’ ").rstrip(".!,;: ")
    if len(out) > MAX_CHARS:
        cut = out[:MAX_CHARS].rsplit(" ", 1)[0]
        out = cut or out[:MAX_CHARS]
    return out.strip()


def suggest(client, questions: list[str]) -> str:
    """A short name, or "" if the model cannot be reached.

    Never raises. A thread with no new name keeps the one it already has, which
    is always a real question by the time this is called -- a failure here costs
    a nicer name, never a usable one.
    """
    asked = [q.strip() for q in (questions or []) if q and q.strip()][:MAX_QUESTIONS]
    if not asked:
        return ""
    numbered = "\n".join(f"{i}. {q[:300]}" for i, q in enumerate(asked, 1))
    try:
        from google.genai import types
        reply = client.models.generate_content(
            model=config.PLAN_MODEL,
            contents=PROMPT % (numbered, MAX_CHARS),
            config=types.GenerateContentConfig(
                response_mime_type="application/json", response_schema=SCHEMA,
                # A name needs no deliberation, and thinking tokens here would
                # cost more than the answer that earned them.
                thinking_config=types.ThinkingConfig(thinking_budget=0),
                max_output_tokens=64))
        import json
        return _tidy(json.loads(reply.text).get("title", ""))
    except Exception:                           # noqa: BLE001 - a name is not worth an error
        return ""


SEED_CHARS = 48


def seed(restated: str, question: str) -> str:
    """The free name: the first real question, trimmed to read like a title.

    The planner already rewrites "does that one have a pool" into a sentence
    that stands on its own, so this costs nothing and reads far better than the
    raw text. A thread with only ever ONE real question keeps this name, so it
    earns more than a blind slice: the trailing question mark goes and the rest
    is cut on a word boundary rather than mid-word.

    NOTHING here inspects the wording. A list of English opening phrases would
    shorten "What are the rates at X" nicely and then mangle the same question
    asked in Hindi, so the only rule is length. Shortening by meaning is the
    model's job, and the model runs on the second real question.
    """
    text = " ".join(((restated or "").strip() or (question or "")).split())
    text = text.rstrip("?. ").strip()
    if len(text) <= SEED_CHARS:
        return text
    return (text[:SEED_CHARS].rsplit(" ", 1)[0] or text[:SEED_CHARS]) + "…"


if __name__ == "__main__":                      # ponytail: self-check, no framework
    assert _tidy('  "Pool properties in Uttarakhand."  ') == "Pool properties in Uttarakhand"
    assert _tidy("Title: Rates at Kinwani House") == "Rates at Kinwani House"
    assert _tidy("a" * 80) == "a" * 40
    assert len(_tidy("Uttarakhand property rates and availability for March")) <= MAX_CHARS
    assert _tidy("Uttarakhand property rates and availability") == "Uttarakhand property rates and"
    assert _tidy("") == ""
    assert seed("", "Which properties have a pool?") == "Which properties have a pool"
    assert seed("Does Kinwani House have a pool?", "does it have a pool") == \
        "Does Kinwani House have a pool"
    # the wording is never inspected, so a question in any language survives whole
    assert seed("", "How many properties are in Rajasthan?") == "How many properties are in Rajasthan"
    assert seed("", "उत्तराखंड में कितनी संपत्तियाँ हैं?") == "उत्तराखंड में कितनी संपत्तियाँ हैं"
    long = seed("", "Compare the room rates at every Uttarakhand property we have on file today")
    assert len(long) <= SEED_CHARS + 1, long
    assert long.endswith("…") and not long[:-1].endswith(" "), long
    assert seed("", "a" * 90) == "a" * SEED_CHARS + "…"
    assert suggest(None, []) == "" and suggest(None, ["  "]) == ""
    print("title: all checks passed")
