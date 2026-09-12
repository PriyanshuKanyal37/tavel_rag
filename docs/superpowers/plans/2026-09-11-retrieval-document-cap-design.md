# Retrieval Context-Budget-Only Implementation Plan

> **For agentic workers:** Executed inline in the current session.

**Goal:** Remove the separate per-turn document-count cap so the 800,000-token context budget is the full-document retrieval guard.

**Architecture:** `gather()` opens ranked candidates until the character equivalent of the context budget is spent. Filter matches are eligible for full text without a separate match-count cutoff. Agent rounds merge under the same budget. Semantic retrieval keeps its top-25 candidate search setting, and the 60-name display cap remains independent.

**Tech Stack:** Python, pytest, Markdown architecture documentation.

---

### Completed changes

- Removed `MAX_DOCUMENTS` from `backend/query/gather.py`.
- Removed `FULLTEXT_MAX_MATCHES` from filter-to-document expansion.
- Applied the context budget to named documents as well as lower-priority candidates.
- Added a budget bound when merging agent retrieval rounds.
- Updated retrieval tests and architecture documentation.
- Verified the focused retrieval suite: 101 passed.
- The maintained `tests/` suite has one unrelated existing failure in `tests/test_api.py::test_ask_streams_events_in_order_and_ends_with_done`: the implementation emits the existing `compacting` event after `done`, while the test expects `done` to be the final event.
