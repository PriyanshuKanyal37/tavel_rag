# Travel Inn Frontend Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the static Travel Inn prototype with a production-quality React client connected to the implemented FastAPI RAG backend, exposing streaming activity, working notes, citations, source evidence, shared history, property search, and resilient edge states.

**Architecture:** A Vite single-page app owns presentation and transient stream state; FastAPI remains the system of record for auth, sessions, turns, retrieval, sources, and properties. A typed fetch client handles JSON endpoints, a custom POST-SSE reader handles `/ask`, and a reducer serializes events so stale streams cannot corrupt a newly selected conversation. Development uses a Vite proxy to keep the browser same-origin with FastAPI.

**Tech Stack:** React 19, TypeScript, Vite, CSS Modules or focused CSS files, `marked` plus DOMPurify (or an equivalent sanitizing markdown renderer), Vitest/React Testing Library, Playwright, and native `fetch`/`ReadableStream`/`AbortController`. Do not add an AI SDK: the backend contract is a custom POST stream.

---

## File map

- Create `frontend/package.json`, `frontend/tsconfig.json`, `frontend/tsconfig.node.json`, `frontend/vite.config.ts`, and `frontend/index.html` for the app shell, scripts, and FastAPI proxy.
- Create `frontend/src/main.tsx` and `frontend/src/App.tsx` for bootstrapping and top-level auth/session orchestration.
- Create `frontend/src/types/api.ts` for the exact backend response and SSE event unions.
- Create `frontend/src/lib/apiClient.ts` for authenticated JSON requests, status normalization, and source URL TTL handling.
- Create `frontend/src/lib/sse.ts` for chunk-safe POST-SSE parsing and abort behavior.
- Create `frontend/src/state/chatReducer.ts` and `frontend/src/state/useChatState.ts` for deterministic event reduction and request identity.
- Create `frontend/src/components/auth/LoginScreen.tsx`, `frontend/src/components/layout/AppShell.tsx`, `frontend/src/components/layout/Sidebar.tsx`, and `frontend/src/components/layout/ThemeToggle.tsx` for authentication, navigation, history, profile, responsive rails, and light/dark mode.
- Create `frontend/src/components/chat/ChatHeader.tsx`, `Transcript.tsx`, `ActivityTimeline.tsx`, `ThoughtDisclosure.tsx`, `Composer.tsx`, and `TurnState.tsx` for the chat surface and every stream boundary.
- Create `frontend/src/components/sources/EvidenceRail.tsx`, `SourceCard.tsx`, and `SourceViewer.tsx` for citation selection, signed URLs, page/crop fallback, and keyboard-accessible source inspection.
- Create `frontend/src/components/properties/PropertyBrowser.tsx`, `PropertyDetail.tsx`, and `FactCard.tsx` for model-free property search and evidence browsing.
- Create `frontend/src/styles/tokens.css`, `frontend/src/styles/app.css`, and component styles for the Travel Inn palette, density, responsive layout, focus states, and reduced motion.
- Create `frontend/src/lib/*.test.tsx`, `frontend/src/state/*.test.ts`, and `frontend/e2e/chat.spec.ts` for parser, reducer, API, component, and browser-flow coverage.
- Modify `backend/api/app.py` in the stream finalization path to emit the informational `compacting` event before persistence; add the corresponding backend contract test.
- Create `qa/reports/frontend-integration-verification.md` with commands, results, screenshots, and known environment limits.

### Task 1: Scaffold the React application and local API boundary

**Files:**
- Create: `frontend/package.json`, `frontend/tsconfig.json`, `frontend/tsconfig.node.json`, `frontend/vite.config.ts`, `frontend/index.html`
- Create: `frontend/src/main.tsx`, `frontend/src/App.tsx`

- [ ] **Step 1: Write the package and proxy configuration.** Add scripts `dev`, `build`, `test`, `test:e2e`, and `lint`; configure Vite to proxy `/api` to `http://127.0.0.1:8000` and preserve cookies.
- [ ] **Step 2: Add the boot entry.** Render `<App />` inside `StrictMode`, import the global token and app styles, and set the document title to `Travel Inn · Knowledge Assistant`.
- [ ] **Step 3: Verify the scaffold.** Run `cd frontend; npm install; npm run build`; expect a successful Vite production build with no TypeScript errors.

### Task 2: Define backend types and the authenticated JSON client

**Files:**
- Create: `frontend/src/types/api.ts`
- Create: `frontend/src/lib/apiClient.ts`
- Test: `frontend/src/lib/apiClient.test.ts`

- [ ] **Step 1: Define exact types.** Model `Account`, `Session`, `Turn`, `SessionDetail`, `SourceRef`, property/fact/connection/document responses, and the SSE union `mode | step | thought | token | sources | compacting | done | error` using the backend field names (`rel_path`, `page`, `cost_inr`, `ms`).
- [ ] **Step 2: Implement `requestJson<T>(path, init)`.** Always set `credentials: "include"`; parse JSON errors into `{status, message, details}`; preserve 401, 404, 422, and 429 for UI decisions; never write auth or conversation data to local storage.
- [ ] **Step 3: Implement session/auth/source/property methods.** Expose `getMe`, `login`, `logout`, `listSessions`, `getSession`, `createSession`, `deleteSession`, property methods, and source metadata/page/original/crop methods. Cache signed URLs only in memory with `expiresAt = now + (expires_in * 1000) - 5000`.
- [ ] **Step 4: Test status normalization and URL refresh.** Mock `fetch` for a 401, 429, invalid JSON, a successful source URL, and an expired URL; run `npm run test -- apiClient.test.ts`; expect all cases to pass.

### Task 3: Build and test the chunk-safe POST-SSE reader

**Files:**
- Create: `frontend/src/lib/sse.ts`
- Test: `frontend/src/lib/sse.test.ts`

- [ ] **Step 1: Write failing parser tests.** Cover a frame split between arbitrary UTF-8 chunks, multiple `data:` lines, a final frame without a trailing blank line, malformed JSON, and an HTTP error before the stream starts.
- [ ] **Step 2: Implement `streamAsk(sessionId, question, signal, onEvent)`.** Use `fetch('/api/chat/sessions/{id}/ask', {method:'POST', body: JSON.stringify({question}), signal, headers:{'Content-Type':'application/json'}, credentials:'include'})`; decode with one `TextDecoder`, buffer until `\n\n`, parse `event:` and all `data:` lines, and dispatch typed events in arrival order.
- [ ] **Step 3: Make abort and disconnect explicit.** Re-throw `AbortError`; convert a non-abort premature close to a typed `StreamDisconnectedError`; do not retry inside the reader, so the reducer can preserve partial output and the app can reload server truth.
- [ ] **Step 4: Run the parser tests.** `npm run test -- sse.test.ts`; expect PASS for every split and error case.

### Task 4: Implement reducer-driven chat state and server reconciliation

**Files:**
- Create: `frontend/src/state/chatReducer.ts`, `frontend/src/state/useChatState.ts`
- Test: `frontend/src/state/chatReducer.test.ts`

- [ ] **Step 1: Write reducer tests.** Assert `mode → step → thought → token → sources → done` creates separate activity, notes, answer, and metadata; assert old request events are ignored after `SESSION_SWITCH`; assert `error`, abort, truncation, no-data, conflict, and retry states are distinct.
- [ ] **Step 2: Implement the state model.** Keep `auth`, `sessions`, `selectedSession`, `detail`, `draft`, `stream`, `sidebarOpen`, `sourcesOpen`, `selectedSource`, and `theme` in one typed state. Give each ask a monotonically increasing `requestId` and reject events whose id is stale.
- [ ] **Step 3: Implement actions.** Add startup auth, login/logout, session create/select/delete, draft update, ask start, event application, stop, stream failure, retry, and `reloadSession` after the reader closes. Treat `/sessions/{id}` as authoritative only after the stream has closed, including its `compacting` event, or after an abort/error reconciliation request.
- [ ] **Step 4: Run tests.** `npm run test -- chatReducer.test.ts`; expect PASS and no state mutation failures.

### Task 5: Add the shared shell, history, profile, theme, and responsive rails

**Files:**
- Create: `frontend/src/components/auth/LoginScreen.tsx`, `frontend/src/components/layout/AppShell.tsx`, `Sidebar.tsx`, `ThemeToggle.tsx`
- Create: `frontend/src/styles/tokens.css`, `frontend/src/styles/app.css`

- [ ] **Step 1: Implement auth gating.** Call `getMe` on mount; show a centered login form for 401; submit password to `login`; show the account name/email in the bottom-left sidebar profile; expose logout there.
- [ ] **Step 2: Implement sidebar behavior.** Default open on desktop, closable with the hamburger, reopenable with an icon button, keyboard reachable, and collapsed to an overlay drawer under 900px. Remove the document library entry. Group server sessions by recent date, show token estimates, and confirm that delete removes the shared conversation for everyone.
- [ ] **Step 3: Implement theme persistence.** Store only `theme=light|dark` in local storage; apply `data-theme` to `document.documentElement`; make the compact top-right light/dark button expose its current state via `aria-label`.
- [ ] **Step 4: Verify layout and focus.** Run the app at 320px, 768px, and desktop widths; verify no horizontal scroll, visible focus rings, Escape closes overlays, and reduced-motion media removes decorative transitions.

### Task 6: Implement the chat transcript and progressive stream activity

**Files:**
- Create: `frontend/src/components/chat/ChatHeader.tsx`, `Transcript.tsx`, `ActivityTimeline.tsx`, `ThoughtDisclosure.tsx`, `Composer.tsx`, `TurnState.tsx`

- [ ] **Step 1: Render persisted turns.** Use `role="log"` with user and assistant turns; sanitize markdown before insertion; map inline `[n]` citations to buttons; render invalid indices as `source unavailable`.
- [ ] **Step 2: Render live activity.** Show mode (`Fast`, `Thinking`, `Researching`), reason, estimate, retrieval round/source/count, elapsed time, and a `role="status"` polite live message. Render `calendar + from:web` as `External calendar lookup` and keep it outside property evidence.
- [ ] **Step 3: Keep working notes separate.** Render `thought` text only inside a collapsed `Working notes` disclosure with `aria-expanded`; never append thought text to the answer or infer hidden reasoning from answer tokens. Collapse activity to one summary line after `done`, including rounds, duration, cost, and truncation.
- [ ] **Step 4: Implement composer controls.** Enforce 1–4,000 Unicode characters, Enter submit, Shift+Enter newline, remaining count, disabled duplicate submission, Stop during streaming, and Retry/Search harder actions for the appropriate boundary states.
- [ ] **Step 5: Add component tests.** Cover activity event rendering, separate notes, stop/retry, validation, no-data success, conflict, interrupted partial answer, and truncated search; run `npm run test -- Transcript ActivityTimeline Composer`.

### Task 7: Add citations, evidence rail, and signed source viewer

**Files:**
- Create: `frontend/src/components/sources/EvidenceRail.tsx`, `SourceCard.tsx`, `SourceViewer.tsx`
- Test: `frontend/src/components/sources/*.test.tsx`

- [ ] **Step 1: Implement shared citation selection.** Inline citation buttons and rail cards dispatch the same `SELECT_SOURCE` action; the selected source is highlighted and the rail toggle updates `aria-expanded`.
- [ ] **Step 2: Implement lazy evidence loading.** Fetch source metadata and signed page/original URLs on open; refresh once on expiry; never persist signed URLs. Show document path, page, evidence quote, qualifiers, and source hash.
- [ ] **Step 3: Implement crop fallback.** Try `/page/{n}/crop?fact={id}` only when a fact id exists; on 404 explain that a crop is unavailable and fall back to the page image/original; distinguish stale document/page errors from infrastructure errors.
- [ ] **Step 4: Test evidence behavior.** Mock metadata, expiry, crop 404, wrong page, and keyboard close/restore; run source component tests and expect PASS.

### Task 8: Implement the property workspace

**Files:**
- Create: `frontend/src/components/properties/PropertyBrowser.tsx`, `PropertyDetail.tsx`, `FactCard.tsx`
- Test: `frontend/src/components/properties/*.test.tsx`

- [ ] **Step 1: Add debounced property search.** Call `/api/properties` with `q`, `state`, `city`, `entity_type`, `near`, `has_pool`, and `rooms_max`; cancel stale requests with `AbortController`; show empty and 422 states.
- [ ] **Step 2: Add lazy detail tabs.** Load property, facts, connections, and documents on demand; show `not recorded` for null distance/duration; preserve `asserted_as`, scope, evidence, sha1, and page on fact cards.
- [ ] **Step 3: Test property states.** Cover search cancellation, no results, null connections, fact source selection, and server 404; run the property test suite.

### Task 9: Add the backend compaction event without changing retrieval semantics

**Files:**
- Modify: `backend/api/app.py` in the ask generator finalization immediately before `_save_turns`
- Test: existing backend API/SSE test module or `backend/tests/test_chat_stream.py`

- [ ] **Step 1: Write the contract assertion.** Feed a deterministic completed ask and assert the stream emits `sources` (when present), `done`, and optional `compacting` before the reader closes; then assert a session reload contains the persisted turn. Assert existing clients can ignore the optional event.
- [ ] **Step 2: Emit the event.** Serialize `{working_set, tokens_before, tokens_after, demoted:[{sha1,from,to}]}` from the compaction result, with no credentials or signed URLs. Keep `_save_turns` and status handling unchanged.
- [ ] **Step 3: Run backend checks.** Use the repository’s documented Python test command; expect the full existing suite plus the new event assertion to pass. If Neon/R2/Gemini are unavailable, run the deterministic/unit subset and record that limitation in QA.

### Task 10: Exercise the complete browser flow and document evidence

**Files:**
- Create: `frontend/e2e/chat.spec.ts`, deterministic mock SSE fixtures/server as needed under `frontend/e2e/fixtures/`
- Create: `qa/reports/frontend-integration-verification.md`

- [ ] **Step 1: Test the browser journey.** With Playwright, mock login, sessions, a streamed ask containing mode/step/thought/token/sources/done/compacting, source open, crop 404 fallback, Stop, Retry, Search harder, sidebar collapse, source collapse, theme toggle, and mobile drawer.
- [ ] **Step 2: Run accessibility checks.** Verify keyboard-only operation, focus-visible styling, dialog Escape/restore, `role="log"`, `role="status"`, `aria-expanded`, contrast, reduced motion, and 320px reflow.
- [ ] **Step 3: Run production verification.** Execute `npm run build`, `npm run test`, and `npm run test:e2e`; start FastAPI plus Vite and smoke-test `/api/health`, login, session load, and one real ask when credentials/services are available.
- [ ] **Step 4: Record evidence.** Add exact commands, pass/fail output, browser dimensions, screenshots of light/dark, streaming activity, source rail, and mobile sidebar to `qa/reports/frontend-integration-verification.md`; link the report from the final implementation PR.

## Self-review checklist

- The plan covers every backend surface required by the design: auth, shared sessions, POST-SSE ask, sources, properties, health smoke, signed URL expiry, and compaction visibility.
- No client-side conversation database, model selector, admin UI, itinerary planner, or property-fact web search is introduced.
- All event fields match `plan/BACKEND-ARCHITECTURE.md` and `backend/api/app.py`; `compacting` is explicitly marked as the one additive backend contract change.
- Run a final reserved-marker scan before execution and remove any unfinished-work markers or vague instructions from the plan.

Plan complete and saved to `docs/superpowers/plans/2026-09-11-travel-inn-frontend-integration.md`.
