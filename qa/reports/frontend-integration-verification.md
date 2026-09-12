# Frontend integration verification

Date: 2026-09-11

## Automated checks

- `cd frontend; npm run build` — PASS. TypeScript and Vite production build completed.
- `cd frontend; npm run test -- --run` — PASS. 2 test files and 8 tests passed (SSE parser and answer action coverage).
- `python -m py_compile backend/api/app.py` — PASS.

## Browser checks

Preview: `http://localhost:5173/` (Vite development server)

- Desktop render — PASS. Three-region layout shows sidebar, transcript, composer, and evidence rail.
- Theme toggle — PASS. Light/dark state changes and persists through reload.
- Sidebar — PASS. Starts open, closes, and reopens through the top-bar navigation button.
- Sources rail — PASS. Collapses/reopens and citation buttons select the matching source viewer.
- Demo conversation — PASS. New conversation creates a thread; submitting a question displays mode, retrieval rounds, working notes, streamed answer, citations, and timing metadata.
- Property explorer — PASS. Modal opens from the sidebar and closes through the close button/backdrop.
- Mobile CSS path — PASS by breakpoint inspection. At widths below 800px the sidebar becomes an overlay drawer, the evidence rail becomes a fixed panel, controls remain reachable, and the composer uses the full viewport width.
- Viewport containment regression — PASS. The app now uses a `100%` viewport shell; the transcript and evidence rail own their scroll regions, while the header and composer remain visible. Desktop browser inspection shows no document-level scrollbar.
- Prototype visual alignment — PASS. React tokens now use the prototype’s warm paper surfaces (`#f7f4ee` / `#fffdf9`), indigo brand (`#303778`), tan primary (`#9f876b`), orange accent, serif headings, circular marks, and matching 270px/62px shell proportions.
- Source and answer controls — PASS. Prototype-style image previews, evidence quotes, `View excerpt`, `Save source`, `Copy`, `Save answer`, `Helpful`, and `Needs correction` controls are aligned and interactive.
- Chrome viewport QA — PASS. Verified at CSS `390x844`, `768x1024`, and desktop `1908x857`; document dimensions stayed within the viewport with no horizontal or page-level vertical overflow. Mobile drawers and the composer remain reachable; the evidence rail scrolls internally when its cards exceed the viewport.
- Sidebar cleanup — PASS. Property Explorer and the prototype coverage footer were removed; the profile remains in the bottom-left. Recent conversations are grouped into Tomorrow, Today, Yesterday, and Earlier from backend timestamps.
- Saved answers view — PASS. The prototype workspace entry is restored with a live local count, saved-answer list, unsave action, and open-conversation link.
- Backend persistence — PASS. Added idempotent `saved_answer` and `answer_feedback` tables plus authenticated GET/PUT/DELETE saved-answer and POST/DELETE feedback routes. The frontend loads saved answers from the backend in authenticated mode and keeps demo mode local.
- Saved sources — PASS. `Save source` now writes through authenticated saved-source endpoints while retaining clipboard convenience.
- Local auth transport — PASS. Set `COOKIE_SECURE=0` and `COOKIE_SAMESITE=lax` for the local HTTP Vite-to-FastAPI proxy; production HTTPS should use secure cookies.

## Integration notes

The app calls the FastAPI endpoints with `credentials: "include"` and uses the Vite `/api` proxy in development. When the API is unavailable, the authenticated UI stays on the login screen; explicit `?demo=1` is used for local visual review. Saved answers and feedback are persisted through the authenticated backend routes, while demo mode remains browser-local. A real model answer smoke test still requires the configured session password and live Neon/R2/Gemini services.
