"""Bounded retries for the two things that fail transiently here: Neon DNS and
the Gemini API.

Retrying is only ever right for a failure that might not repeat. A quota that is
exhausted will still be exhausted in ten seconds, and a TypeError will still be a
TypeError, so both are raised immediately rather than four times slower.
"""
import time

# worth another attempt
TRANSIENT = (
    "getaddrinfo", "temporarily unavailable", "connection reset", "connection closed",
    "connection refused", "timed out", "timeout", "unavailable", "deadline exceeded",
    "rate limit", "too many requests", "internalerror", "500", "502", "503", "504",
)
# checked FIRST: a 429 can be either, and these words decide which
PERMANENT = (
    "resource_exhausted", "quota exceeded", "quota_exceeded", "exceeded your current quota",
    "api key not valid", "api_key_invalid", "permission denied", "permission_denied",
    "unauthenticated", "invalid_argument", "billing",
)
# our own bugs
NEVER = (TypeError, ValueError, KeyError, AttributeError, AssertionError, ImportError)


def transient(exc: BaseException) -> bool:
    if isinstance(exc, NEVER):
        return False
    m = str(exc).lower()
    if any(p in m for p in PERMANENT):
        return False
    return any(t in m for t in TRANSIENT)


# A permanent failure needs an instruction, not a stack trace. The user meets
# these on the command line; the traceback tells them nothing they can act on.
EXPLAIN = (
    # checked in order; the free-tier line must come FIRST, because its message
    # also contains "quota exceeded" and the two problems need different actions
    ("free_tier", "This key is on the FREE TIER (20 requests per day, per model). "
                  "It is not a billing failure and waiting will not help today — "
                  "use a key on a project with billing enabled."),
    ("credits are depleted", "Gemini prepayment credits are exhausted. Add funds to "
                             "this project at https://ai.studio/projects."),
    ("quota exceeded", "Gemini quota exceeded for this project. Wait for the reset "
                       "or raise the limit in AI Studio."),
    ("resource_exhausted", "Gemini refused the call as out of quota or credit. "
                           "Check billing in AI Studio."),
    ("api key not valid", "GEMINI_API_KEY in backend/.env is not accepted. Re-issue it."),
    ("api_key_invalid", "GEMINI_API_KEY in backend/.env is not accepted. Re-issue it."),
    ("permission denied", "This key may not call that model. Check the project's access."),
    ("getaddrinfo", "Neon could not be resolved after several attempts. Check the network."),
)


def explain(exc: BaseException) -> str | None:
    """A plain sentence for a known failure, or None. Never invent one."""
    m = str(exc).lower()
    for needle, text in EXPLAIN:
        if needle in m:
            return text
    return None


MAX_DELAY = 32.0


def backoff(delay: float, attempt: int) -> float:
    """Exponential, capped. A flat delay is the wrong shape for the two things
    that actually fail here: 'model overloaded' and rate limits both want the
    caller to back away, not to knock at the same rhythm."""
    return min(delay * (2 ** attempt), MAX_DELAY)


def over_models(models, make_call, *, tries: int = 5, delay: float = 2.0, on_retry=None):
    """Try each model in turn; return (result, model_that_worked).

    "503 This model is currently experiencing high demand" is not our fault and
    not our users' problem, and it killed three live runs in one day. Retrying
    harder does not help when a whole model is saturated for minutes; a sibling
    answers immediately. A PERMANENT failure -- a dead key, an exhausted quota --
    is dead on every model, so it stops at the first one instead of burning
    through the list.
    """
    last = None
    for i, model in enumerate(models):
        try:
            return call(lambda: make_call(model), tries=tries, delay=delay,
                        on_retry=on_retry), model
        except Exception as e:
            if not transient(e):
                raise
            last = e
            if on_retry and i + 1 < len(models):
                on_retry(0, f"{model} unavailable, trying {models[i + 1]}")
    raise last


def call(fn, *, tries: int = 5, delay: float = 2.0, on_retry=None):
    """Run fn(), retrying only transient failures. Returns fn()'s value."""
    for i in range(tries):
        try:
            return fn()
        except Exception as e:
            if i == tries - 1 or not transient(e):
                raise
            if on_retry:
                on_retry(i + 1, e)
            time.sleep(backoff(delay, i))
