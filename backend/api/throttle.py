"""A sliding-window cap on the one endpoint that spends money.

Login has its own throttle and it guards a password. This one guards the bill.
An /ask is not one model call: it is the planner, then embeddings, then the
answer, and on the second real question a naming call as well. So a request
here is worth several of them, and nothing stopped a loop, a stuck retry or an
impatient hand on the Enter key from emptying the month's budget in an hour.
Which is not hypothetical -- the cap was hit twice in a single afternoon.

Deliberately generous. A cap that interrupts real work would be worse than the
problem, so the defaults sit far above what a sales team can type, and only a
runaway ever meets them.

  ASK_PER_MIN      per caller, default 60/min
  ASK_PER_MIN_ALL  everyone together, default 120/min

# ponytail: in-process, so it is per-worker and resets on restart. With two
# workers the real ceiling is two ceilings. That is the right trade for an
# internal tool; move the counter to Postgres or Redis if it ever has to hold
# exactly across a fleet.
"""
from __future__ import annotations

import collections
import os
import threading
import time

WINDOW = 60.0
ASK_PER_MIN = int(os.getenv("ASK_PER_MIN", "60"))
ASK_PER_MIN_ALL = int(os.getenv("ASK_PER_MIN_ALL", "120"))
# A busy office is a handful of addresses, not thousands. The bound only exists
# so a long uptime behind changing addresses cannot grow the dict forever.
MAX_KEYS = 4096


class Window:
    """Counts hits per key over a rolling window. Locked: FastAPI runs sync
    endpoints in a threadpool, so two requests really do arrive at once."""

    def __init__(self, limit: int, window: float = WINDOW):
        self.limit = limit
        self.window = window
        self._hits: dict = collections.defaultdict(collections.deque)
        self._lock = threading.Lock()

    def check(self, key: str = "*", now: float = None) -> int:
        """Record a hit and return 0, or return the seconds to wait if full.

        The hit is NOT recorded when the caller is over the limit, so hammering
        a closed door cannot push the reopening further away.
        """
        now = time.time() if now is None else now
        with self._lock:
            if self.limit <= 0:
                return int(self.window)
            if len(self._hits) > MAX_KEYS:
                self._prune(now)
            seen = self._hits[key]
            while seen and now - seen[0] >= self.window:
                seen.popleft()
            if len(seen) >= self.limit:
                return max(1, int(self.window - (now - seen[0])) + 1)
            seen.append(now)
            return 0

    def _prune(self, now: float) -> None:
        for key in [k for k, v in self._hits.items()
                    if not v or now - v[-1] >= self.window]:
            del self._hits[key]


if __name__ == "__main__":                      # ponytail: self-check, no framework
    w = Window(limit=3, window=60.0)
    t = 1000.0
    assert [w.check("a", t + i) for i in range(3)] == [0, 0, 0], "first three pass"
    assert w.check("a", t + 3) > 0, "the fourth is held"
    assert w.check("b", t + 3) == 0, "a different caller is unaffected"
    # a blocked attempt must not extend the wait
    first = w.check("a", t + 10)
    assert w.check("a", t + 10) == first, "hammering does not push the door further away"
    assert w.check("a", t + 59) > 0, "still held inside the window"
    assert w.check("a", t + 61) == 0, "and free once the oldest hit ages out"

    # the window slides, it does not reset in blocks
    w2 = Window(limit=2, window=10.0)
    assert w2.check("x", 0) == 0 and w2.check("x", 9) == 0
    assert w2.check("x", 9.5) > 0
    assert w2.check("x", 10.5) == 0, "the hit from t=0 has aged out, the one from t=9 has not"
    assert w2.check("x", 11) > 0

    assert Window(limit=0).check("anyone") > 0, "a zero limit blocks everything"

    # concurrent callers must not both slip through the last slot
    race = Window(limit=50, window=60.0)
    passed = []
    def hammer():
        passed.extend(1 for _ in range(20) if race.check("shared") == 0)
    threads = [threading.Thread(target=hammer) for _ in range(10)]
    [t_.start() for t_ in threads]
    [t_.join() for t_ in threads]
    assert len(passed) == 50, f"exactly the limit got through, not {len(passed)}"
    print("throttle: all checks passed")
