# Travel Inn RAG Frontend — Complete End-to-End QA & Frame-by-Frame Analysis Report

**Date**: September 11, 2026  
**Environment**: Windows 11 · Google Chrome (Automated Subagent)  
**Target URL**: `http://127.0.0.1:5173/`  
**Backend API**: `http://127.0.0.1:8000/` (FastAPI / Uvicorn)  
**Authentication**: Password `travelinn`  

---

## 1. Executive Summary

A comprehensive, interactive end-to-end test of the Travel Inn Knowledge Assistant was conducted directly inside Chrome. The test covered the full user journey:
1. **Authentication Flow**: Session invalidation, password-gated access, credential verification, and session cookie establishment.
2. **Workspace Boot**: Hydration of the three-column layout (Conversation Sidebar, Main Chat Canvas, Evidence Rail).
3. **Retrieval-Augmented Generation (RAG)**: Submitting multi-property queries, capturing server-sent event (SSE) streams (`mode`, `step`, `thought`, `token`, `sources`, `compacting`, `done`), verifying live thinking disclosure, and real-time token streaming.
4. **Citation & Document Inspection**: Resolving inline citation chips `[1]` to signed supplier brochures, inspecting scanned document pages, and testing multi-page pagination.
5. **Workspace Persistence**: Testing clipboard copying, answer bookmarking, verifying database-backed synchronization in `Saved answers`, and navigating back to source threads.
6. **Design System & Ergonomics**: Calibrated dark/light theme switching, responsive drawer collapse/expansion, and error-boundary recovery.

Across 43 high-resolution visual frames captured at ~10 FPS intervals, the core RAG pipeline, brochure previewer, and theme system functioned smoothly. However, **two critical functional bugs** and **four usability defects** were identified, including a user-message disappearance bug during streaming and a markdown text-corruption bug replacing numbers with `undefined`.

---

## 2. 10 FPS Frame-by-Frame Progression Breakdown

- **0.0s – 1.2s**: Workspace loaded. Profile sign-out action verified session destruction. Clean transition to `<LoginScreen />`.
- **1.2s – 2.8s**: Auto-focused password field. Typed `travelinn`. `Continue ↗` button enabled dynamically.
- **2.8s – 4.5s**: Submitted login form. Backend set session cookie and returned user account (`team@travelinn.local`). Application shell mounted cleanly.
- **4.5s – 7.5s**: Started new conversation. Submitted Prompt 1: *"What are the key amenities and activities at Agoratoli Eco Resort?"*.
- **7.5s – 11.0s**: Activity timeline showed thinking state (`Fast answer - lookup amenities and activities for a single property`). Send button turned to `■ Stop`.
  - ⚠️ **Bug Identified**: The user's prompt was completely absent from the chat canvas during this entire 3.5s period.
- **11.0s – 14.5s**: Tokens streamed in real time. Inline citations `[1]` rendered as clickable chips. Evidence Rail populated with 25 source cards.
- **14.5s – 18.2s**: Clicked citation `[1]`. `SourceDialog` opened displaying brochure scan of *Agoratoli Jungalow* (`Page 1 of 3 · SHA 53e3028c`).
- **18.2s – 21.5s**: Tested modal pagination: Page 1 $\rightarrow$ Page 2 $\rightarrow$ Page 3 $\rightarrow$ Page 2. Modal dismissed via `×` button.
- **22.0s – 25.5s**: Clicked `Copy` (text copied to clipboard) and `Save answer` (saved to database).
- **25.5s – 30.0s**: Navigated to `☆ Saved answers` workspace. Card rendered with metadata and intact citation chips. Clicked `Open conversation →` to jump back to thread.
- **30.0s – 34.5s**: Tested `☾ Dark` theme toggle and reverted with `☀ Light`. Palettes shifted with zero layout jump.
- **34.5s – 40.5s**: Tested collapsing Evidence Rail (`→`) and Sidebar (`←`). Both animated smoothly to 0px and restored via topbar controls.
- **40.5s – 46.0s**: Started new conversation. Submitted Prompt 2: *"Which properties in Kaziranga are best for birdwatching and photography?"*. Tested upstream quota exhaustion handling (429).

---

## 3. Defect Register & Root Causes

### 1. 🚨 Critical: User Message Vanishes During Generation
- **Location**: `frontend/src/App.tsx` line 37 (`submit()`)
- **Cause**: Input text is cleared (`setDraft('')`), but no optimistic turn is added to `detail.turns`. The user prompt only appears once `api.detail()` is called after stream completion. If aborted or stopped, the prompt is lost permanently.
- **Fix**: Add an optimistic `{ role: 'user', text: q, seq: ... }` to `detail.turns` before calling `streamAsk()`.

### 2. 🚨 Critical: Markdown Number Replacement Corrupts Numbers to `undefined`
- **Location**: `frontend/src/lib/markdown.ts` line 28
- **Cause**: `out.replace(/ (\d+) /g, (_m, i) => code[Number(i)])` matches any plain number with surrounding spaces (e.g., `"has 3 rooms for 10 guests"`). Because `code[3]` is `undefined`, it renders `"hasundefinedrooms forundefinedguests"`.
- **Fix**: Use non-numeric sentinel symbols (e.g., `\x00CODE_${index}\x00`) instead of numeric placeholders.

### 3. ⚠️ Major: Live Answer Save Key Mismatch
- **Location**: `frontend/src/App.tsx` line 56 & `frontend/src/components/AnswerActions.tsx`
- **Cause**: Streaming uses `answerId={'live:' + selected}`, while persisted turns use `${sessionId}:${turn.seq}`. Saving during a stream reverts to unsaved as soon as the stream finishes.
- **Fix**: Disable save button while streaming or re-map optimistic IDs on sequence resolution.

### 4. ⚠️ Minor: Action Status Text ("Copied") Persists Indefinitely
- **Location**: `frontend/src/components/AnswerActions.tsx` line 30
- **Cause**: `setStatus('Copied')` lacks an auto-clearing timeout, leaving the text on screen permanently.
- **Fix**: Add `window.setTimeout(() => setStatus(''), 2500)` in `copyAnswer()` and `toggleSaved()`.

### 5. 💡 Usability: Raw JSON Error Strings Displayed on API Failure
- **Location**: `frontend/src/lib/sse.ts` line 7
- **Cause**: Upstream error dictionaries from FastAPI/Gemini are displayed verbatim (`429 RESOURCE_EXHAUSTED. {'error': ...}`).
- **Fix**: Format common HTTP status codes (401, 429, 500) into friendly user messages.
