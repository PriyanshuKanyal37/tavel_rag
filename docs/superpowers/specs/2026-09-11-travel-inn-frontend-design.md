# Travel Inn Frontend Integration Design

**Date:** 2026-09-11  
**Status:** Proposed for review

## Goal

Replace the static prototype behavior with a React/Vite/TypeScript client that uses the implemented FastAPI backend for shared authentication, conversations, streamed answers, source evidence, and property browsing while preserving the calm Travel Inn visual system.

The production UX decisions are grounded in the companion benchmark at [`prototype/research/chat-rag-interface-benchmark-2026-09-11.md`](../../../prototype/research/chat-rag-interface-benchmark-2026-09-11.md). The benchmark compares documented interaction patterns from ChatGPT, Claude, Gemini, RAG research, and accessibility guidance, then maps each pattern to the Travel Inn backend rather than copying a vendor UI.

## Architecture

The frontend will be a Vite single-page application in `frontend/`. FastAPI remains the system of record. The browser will never persist conversations, source URLs, or credentials in local storage. A small typed API client will own JSON requests and errors; a dedicated SSE reader will own the POST `/ask` stream; React state will own the current session and transient stream activity.

The API base is configured through `VITE_API_BASE`. Development will use a Vite proxy to the FastAPI server where possible, avoiding browser CORS during local work. If the frontend is served on a separate origin, backend `CORS_ORIGINS` must include that exact origin and local HTTP must use `COOKIE_SECURE=0`. Every authenticated request uses `credentials: "include"`.

## Authentication and shared history

On startup, the app calls `GET /api/auth/me`. A successful response gives the shared account name and email for the bottom-left profile. A `401` shows the login screen. Login posts `{password}` to `/api/auth/login`; the browser accepts the HttpOnly `tirag_session` cookie and then reloads account and sessions. Logout posts `/api/auth/logout`, clears client state, and returns to login.

The sidebar loads `GET /api/chat/sessions`, displays the server order, and selects a session with `GET /api/chat/sessions/{id}`. New chat creates a server session before the first question. Delete calls `DELETE /api/chat/sessions/{id}` and explicitly warns that the conversation disappears for every signed-in user. A stale or deleted session reloads the session list and selects another available thread.

The client state is divided into:

```ts
type AuthState =
  | { status: "loading" }
  | { status: "signed-out" }
  | { status: "signed-in"; account: { name: string; email: string } };

type Session = { id: number; title: string | null; last_active: string; tokens_est: number };
type Turn = {
  seq: number;
  role: "user" | "assistant";
  text: string;
  status: "complete" | "streaming" | "interrupted" | "failed";
  sources: SourceRef[];
  cost_inr: number | null;
  ms: number | null;
  created_at: string;
};
type SessionDetail = {
  id: number;
  title: string | null;
  working_set: { sha1: string; level: "full" | "facts" | "summary"; turn_added: number }[];
  summary: string | null;
  turns: Turn[];
};
```

Chat history comes from the server after every completed, interrupted, failed, or cancelled request. Optimistic UI is only a temporary rendering aid and is reconciled with `GET /sessions/{id}`.

## Streaming contract and activity model

The `/api/chat/sessions/{id}/ask` endpoint is a POST returning `text/event-stream`, so the client will use `fetch`, `ReadableStream`, `TextDecoder`, and `AbortController`. Native `EventSource` is not suitable. The parser buffers bytes until a blank-line frame, accepts `event:` plus one or more `data:` lines, parses JSON, and dispatches frames in arrival order.

The reducer handles these events:

| Event | UI behavior |
|---|---|
| `mode` | Start the activity timeline with Fast, Thinking, or Researching; show `why`, estimated seconds, and max rounds. An escalation is visibly labelled. |
| `step` | Append a retrieval round with round number, source/detail, found/opened/chars/count, and optional missing field. |
| `thought` | Append to a collapsed “Working notes” disclosure. Thought text never enters the answer string. |
| `token` | Append only to the answer body and show a live cursor while streaming. |
| `sources` | Replace the answer’s source references and open/update the evidence rail. |
| `done` | Set completion metadata: mode, model, rounds, cost, seconds, found/count, and truncated. |
| `error` | Preserve any partial answer, mark failed/interrupted according to whether text exists, and show retry/search-harder actions. |
| `compacting` | Show a context update activity with before/after levels and token estimate. This requires a small backend event addition because current compaction is silent. |

The stream has a request id. Events from an older request are ignored after a session switch or a new request. `AbortController.abort()` stops the browser stream; once the reader closes, the client reloads the session because the backend saves the exchange as `interrupted` in its generator `finally` block. A disconnect before any token shows a failed/retry state; a disconnect after tokens keeps the partial answer and offers retry. A `done` event updates display metadata, but reconciliation waits for the stream to close so compaction and persistence have completed.

The current backend exposes external calendar lookup as `step {source:"calendar", from:"table"|"web"}`. The activity timeline will render a web lookup only as an external calendar step and will never present it as property evidence. Web URLs are not currently emitted to the browser; clickable web citations are out of scope unless a future `web_search` event is added.

The backend currently forwards Gemini thought parts. The UI keeps them collapsed by default and labels them as working notes. It must not infer or reconstruct hidden reasoning from answer tokens.

## Conversation UI

The shell keeps the existing Travel Inn palette and calm reading hierarchy:

- `AppShell`: responsive three-region layout, theme persistence, global auth/error boundary.
- `Sidebar`: brand, New chat, history grouped by server timestamps, search, delete-for-everyone confirmation, bottom-left profile.
- `ChatHeader`: conversation title, mode/status badge, navigation toggle, Sources toggle.
- `Transcript`: `role="log"`, user turns, assistant turns, activity timeline, answer markdown, citation buttons, interrupted/failed/truncated/no-data/conflict states.
- `ActivityTimeline`: mode and retrieval steps with current/completed status, elapsed indicator, optional calendar web step, and compaction activity.
- `ThoughtDisclosure`: collapsed by default, keyboard accessible, never mixed into answer content.
- `Composer`: 1–4,000 character validation, Enter to submit, Shift+Enter for newline, draft preservation, Stop button during streaming, disabled duplicate submit.
- `EvidenceRail`: source list, selected citation, metadata, page viewer, crop action, original-document action, signed-link refresh.
- `PropertyBrowser`: model-free search and filters backed by `/api/properties`, with detail/facts/connections/documents views.
- `LoginScreen`, `LoadingState`, `EmptyState`, `OfflineState`, `ErrorState`, and `HelpDialog`.

Answer markdown will be sanitized before rendering. Citation tokens will be represented as buttons linked by source index, with out-of-range or missing references rendered as an explicit unavailable citation rather than a broken control.

The visual hierarchy follows an answer-first layout: the response occupies the widest readable column, the activity trace is progressively disclosed, and evidence is one click away. Activity and working notes are visually quieter than the answer, use a polite status live region, and collapse after completion. A citation opens the same selected source whether it is clicked inline or in the aggregate rail, so the user never has to reconcile two evidence views.

## Source evidence behavior

Source references are normalized from the backend’s `{sha1, rel_path, page}` shape. The client fetches `/api/sources/{sha1}` for metadata and requests `/page/{n}`, `/original`, or `/page/{n}/crop?fact={id}` only when opened. Signed URLs expire after 15 minutes and are held in memory with their expiry; they are never stored in local storage or session history. An expired image retries once with a newly minted URL.

PDF documents may return `404` for crop because only image evidence has bounding boxes. The rail will explain that no crop is available and fall back to the signed page image or original. Wrong document/page and missing evidence are handled as unavailable evidence, not as a generic application crash.

## Properties workspace

The property browser never invokes the model. Search uses `GET /api/properties?q=...`; filters use `state`, `city`, `entity_type`, `near`, `has_pool`, and `rooms_max`. Detail panels call the property, facts, connections, and documents endpoints lazily. Null connection distance/duration values render “not recorded”; they are never displayed as zero. Fact cards preserve `asserted_as`, scope, evidence quote, source hash, and page.

## Backend contract additions

To satisfy the requested visual activity coverage, the backend stream will add one optional event immediately before persistence:

```json
event: compacting
data: {"working_set": 12, "tokens_before": 18400, "tokens_after": 7600,
       "demoted": [{"sha1":"…","from":"full","to":"facts"}]}
```

The event is informational. The client still reloads the session after `done`, abort, or error and treats the database response as authoritative. No source URL or private credential is sent in this event.

## Edge-case behavior

- `401`: pause the current action, show login, then retry only after explicit successful login.
- `429`: show the backend’s throttling message and do not loop retries automatically.
- `404` session: refresh shared history and select a valid session.
- `422`: show the exact input validation message and keep the draft.
- Empty/no-data answer: show it as a successful boundary response, not an error.
- Ambiguous name: render the returned candidates and ask the user to choose; never silently choose one.
- Conflict: show both cited values and qualifiers.
- `done.truncated=true`: show an incomplete-search warning and a Search harder action.
- Stream error before text: failed state with retry; after text: interrupted state with partial text.
- User stop: abort, preserve draft/partial answer, reload the persisted turn.
- Network loss: show reconnect/retry without duplicating tokens.
- Concurrent shared-browser updates: refresh the selected session after completion so another user’s turn is visible.
- Signed URL expiry or source 404: refresh once, then show an evidence-specific fallback.
- 4,000-character limit: block submit with remaining-count feedback.
- Hindi or mixed-script text: preserve Unicode end to end; add a manual QA case because backend coverage is currently untested.
- Reduced motion, keyboard focus, 320px reflow, and screen-reader announcements are acceptance checks.

## Testing strategy

- Unit tests with Vitest for API error normalization, SSE frame parsing across arbitrary chunk boundaries, reducer transitions, citation normalization, signed-link expiry, and input validation.
- Component tests for login, history selection/deletion, activity timeline, thought disclosure, source rail fallback, interrupted/failed/truncated states, and responsive toggles.
- Browser tests with Playwright against a deterministic mock SSE server for full login → session → ask → activity → source → retry flows, plus a real FastAPI smoke run when credentials and Neon/R2 are available.
- Accessibility checks for focus-visible controls, dialog focus trap/Escape/restore, `role="log"` live updates, contrast, reduced motion, and mobile reflow.
- Preserve the backend’s existing Python logic/database/API tests; add contract assertions for the new `compacting` event and ensure the existing SSE event order remains mode → step/thought/token → sources → done.

## Deliberate non-goals

There will be no admin/review UI, private-user threads, itinerary planner, model-selection control, persistent signed URLs, client-side reimplementation of retrieval, or web search for property facts. The shared account and shared history remain the backend’s current product decision.
