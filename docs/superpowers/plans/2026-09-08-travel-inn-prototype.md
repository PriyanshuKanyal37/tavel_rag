# Travel Inn navigable prototype plan

**Goal:** Refine the approved calm Claude-style direction into a fully navigable local prototype with sample conversations, evidence, theme switching, and keyboard access.

**Scope:** Sales knowledge workspace only. All generated replies, chat history, saved answers and feedback are local mock data. No backend, authentication, cloud publishing or production AI calls.

**Architecture:** Standalone HTML, CSS and ES modules in `prototype/`; a local-only Node static server. Separate fixture data from rendering and state. Browser-local persistence with graceful fallback. Keep the existing backend and planning files untouched.

**Source classes:** W3C accessibility standards and APG, official platform documentation, original HCI research and established design-system documentation. Parent synthesizes research; two independent research agents cover chat/evidence UX and accessibility.

## Progress

- [x] Research and reconcile evidence. Two focused subagents covered chat/trust and WCAG/ARIA/reflow; source ledger and limits are in `prototype/research/report-source.md`.
- [x] Build refined mock. `prototype/index.html` is a standalone local app; `prototype/server.cjs` serves it; four real document preview tiles are under `prototype/assets/`.
- [x] Independent review. Checked controls, source updates, persistence, modal inertness/focus return and prototype-only console output; corrected stale evidence during streaming and modal focus restoration.
- [x] Verify and deliver. Static, HTTP, DOM/accessibility snapshot, interaction and screenshot checks are recorded in `qa/reports/prototype-verification.md`.

## Navigation and states

- New chat: centered greeting and editable composer, four actionable example prompts.
- Conversation: readable answer text, comparison tables/lists, inline citations, sources, copy/save/rate/retry actions and follow-ups.
- Sidebar: searchable recent history grouped by day, active state, rename/remove mock chat, saved answers and document library.
- Library: text filtering of sample documents; each opens the source viewer.
- Sources: contextual evidence quote plus actual locally copied document preview; document sections, zoom, save, original link.
- Search dialog: keyboard shortcut, searchable chat titles and message content, results navigate.
- Light/dark: small top-right button, persistent semantic colors; reduced-motion support.
- Mock responses: simulated streaming, stop and retry, follow-up context, unknown-data response and source inconsistency examples. No fabricated real AI verification badge.
- Help/settings: shortcuts, explanation of demo data, reset only prototype storage.
- Responsive: collapsed sidebar on small screens, accessible navigation overlay, source viewer fills the available viewport.

## Verification acceptance

1. All visible buttons and navigation targets respond; no inert decorative controls.
2. Eight seeded histories open distinct content; search, save, rename, delete/undo, feedback and new mock messages work.
3. Citation IDs resolve only to supplied fixtures. Counts and visible labels match those fixtures.
4. Theme persists after reload; light/dark text colors meet defined contrast targets.
5. Dialogs support Escape and restore focus; composer Enter submits and Shift+Enter inserts a newline; keyboard focus visible.
6. Long answers scroll without moving the composer off screen; narrow layouts retain navigation and source access.
7. No secret/config reads, production services, client messages or writes outside prototype/design/QA files.
8. Final report distinguishes code/static and browser-verified results from untested assistive technology behavior. No claim of absolute perfection.

Planning tool note: `update_plan` is not available in this session; this file records the plan instead. The workspace is not a Git repository, so no commit/worktree operation applies.
