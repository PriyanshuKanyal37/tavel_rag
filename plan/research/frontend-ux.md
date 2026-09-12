# frontend-ux

## HEADLINE
Use Vercel AI SDK 6 + shadcn/ui June 2026 chat primitives + assistant-ui for the shell; the critical trust lever is a source side-panel that opens the actual R2 document, not a filename.

## RECOMMENDATION
Ship with: assistant-ui 0.15.x as the runtime shell (Thread, Composer, MessageScroller), shadcn/ui June 2026 chat components (MessageScroller, Bubble, Marker, shimmer) for message layout, Vercel AI SDK 6 useChat hook for streaming state, and ai-sdk elements (elements.ai-sdk.dev) for the Inline Citation and Sources components. For document viewing: react-pdf (mozilla/pdf.js wrapper, actively maintained) for PDFs and plain img in a Sheet (shadcn side panel) for PNG/JPEG. This gives you roughly 80% of the UI without writing custom component code.

## WHY
Travel Inn's sales team are the product's end users and they are non-technical. One hallucinated driving distance destroys permanent trust (stated hard requirement). The entire trust architecture therefore flows from citations being verifiable — not just filenames, but clickable source cards that open the actual R2 asset inline. The dual query type (filter vs semantic) requires two distinct UX states: "Filtering 49 properties..." vs "Searching descriptions...", which maps naturally to Vercel AI SDK 6's data parts streaming. The shadcn June 2026 chat release and ai-sdk elements are purpose-built for exactly this composition, eliminating weeks of scroll-anchor/streaming/skeleton engineering that every RAG chat app reinvents.

## ALTERNATIVES

### assistant-ui as full framework (not just shell) -> **USE**
- PRO: Provides Thread management, message branching, BranchPicker (regenerate), resumable streams across disconnects, multi-thread sidebar, voice dictation — all headless, fully composable with shadcn/ui and Tailwind. YC-backed, actively maintained (v0.15.17, published ~4 days ago as of research date). Integrates natively with Vercel AI SDK runtime.
- CON: Adds a dependency layer. Headless means you still write all visual styles. Thread/message branching is overkill for v1 with 10 users. 0.x versioning means API can shift.

### shadcn/ui June 2026 chat primitives (MessageScroller, Bubble, Marker, shimmer) -> **USE**
- PRO: Official shadcn release, zero extra dependency (already in leaning). MessageScroller handles scroll-anchoring during streaming — the hardest part to get right. shimmer component covers the thinking state. Marker handles tool-call status rows.
- CON: No runtime/state management — you still wire useChat yourself. Less opinionated than assistant-ui.

### ai-sdk elements (elements.ai-sdk.dev) -> **USE**
- PRO: Provides Inline Citation, Sources, Suggestion (cold-start prompts), Chain of Thought, Shimmer, Queue status — all with deep Vercel AI SDK integration and shadcn/ui conventions. Directly solves the citation rendering problem without custom code.
- CON: Newer, less battle-tested than assistant-ui. Documentation depth unclear at time of research.

### react-pdf (@react-pdf-viewer/core) -> **REJECT**
- PRO: Feature-rich, 20+ plugins including page search, annotations, full-screen.
- CON: No active updates since early 2023. Dead in practice.

### react-pdf (from react-pdf npm / mozilla pdf.js) -> **USE**
- PRO: Actively maintained mozilla pdf.js wrapper. Sufficient for rendering PDFs in a side panel. No annotation needs for v1.
- CON: Needs canvas rendering setup. Not a full viewer UI — you compose it yourself.

### Generative UI / React Server Components for structured property cards -> **PHASE-2**
- PRO: Vercel AI SDK 6 supports tool calls that render custom React components (generative UI). For filter queries ('which properties have a pool?'), returning a structured property card grid is far better UX than a paragraph of text.
- CON: Requires defining tool schemas and React component renderers. Extra implementation surface.

### Conversation history sidebar with auto-named threads -> **PHASE-2**
- PRO: ChatGPT-style sidebar with AI-generated thread names from first query ('Safari lodges under 15k - Ranthambore') vastly better than timestamps. Users can recover answers days later.
- CON: v1 uses a single shared password — shared history is a privacy/confusion risk (sales rep A sees sales rep B's threads). Must wait for per-user auth (v2) to do this properly.

### Modal for source document viewing (instead of side panel) -> **REJECT**
- PRO: Simpler to implement. Familiar pattern.
- CON: Modal closes the chat context. User cannot compare the source document against the answer simultaneously. Side panel (shadcn Sheet with 40-50% width) is strictly better on desktop for a verification workflow.

## KEY FINDINGS
- Vercel AI SDK is now at v6 (non-breaking upgrade from v5). Key feature for Travel Inn: data parts let the server stream source metadata (property name, doc type, R2 URL) as separate typed stream parts before the answer text, so the client can render source cards while the answer is still generating. SDK gives you useChat state, streaming, abort, error state, and tool call states for free — you still write all visual components.
- shadcn/ui released native chat components in June 2026: MessageScroller (handles scroll anchoring during streaming — the part every RAG chat app gets wrong), Bubble (message surface), Marker (status/tool rows), Attachment, and a shimmer CSS utility for thinking states. These replace ~400 lines of custom scroll logic.
- Streaming cuts PERCEIVED wait time by 55-70% even when total generation time is identical, because users start reading before the model finishes. The 500ms-2s pre-first-token gap (while LLM processes) should show a contextual shimmer with the label 'Filtering 49 properties...' or 'Searching descriptions...' (not a generic spinner), set by your server via a data part event BEFORE the first text token.
- Citation integrity pattern (Vercel KB): the route writes source-url parts to the stream first, then merges the model text stream. Client-side, an [id] tag in the response only becomes a clickable link if a matching source exists in that message's parts. Unmatched tags render as plain text, never silently dropped. This prevents hallucinated citation links from appearing.
- For Travel Inn specifically: source cards should show property name, document type badge (PDF vs Image), and a 'View document' button. Clicking opens a shadcn Sheet (side panel, ~45% width) containing react-pdf for PDFs or a plain img tag for PNGs. Users verify the answer against the actual source without losing chat context. This is the single highest-trust feature you can ship.
- Grounded refusal UX: 'I don't know' should be specific, not generic. Pattern: 'I searched all 49 properties but none match all your filters. The closest match is [X] which has [Y] but not [Z]. You could relax the [constraint].' Research confirms this BUILDS trust in B2B contexts — users learn that when the system does answer confidently, it has the evidence. Generic 'I cannot help with that' is the failure mode.
- Cold-start suggested prompts must be domain-specific, not 'Ask me anything.' For Travel Inn: mix 4 prompts covering filter queries ('Which properties are within 2 hours of Delhi airport?', 'Show me lodges with fewer than 20 rooms') and semantic queries ('Tell me about Ranthambore options for a family with kids', 'Which properties have been physically inspected by Travel Inn staff?'). The 'staff inspected' field is a trust differentiator — surface it prominently.
- Top abandonment causes from research: (1) no example prompts at cold start, (2) confident wrong answer even once, (3) citations that are filenames with no way to verify, (4) generic error messages indistinguishable from form validation errors, (5) no streaming — blank panel for 3 seconds feels broken. All five are solvable in v1 with the stack described above.

## PITFALLS
- Single shared password in v1 means NO conversation history sidebar. If you store threads in Postgres, any user can see any other user's queries. Either (a) store history in sessionStorage only (lost on tab close, acceptable for v1), or (b) require a name/initials field at login that namespaces threads without full auth. Do not ship a shared history sidebar.
- react-pdf-viewer (@react-pdf-viewer/core) is dead — no updates since early 2023. Do not use it. Use react-pdf (the mozilla/pdf.js wrapper) instead. Its package is 'react-pdf' on npm, not to be confused.
- For PDFs with z-order text (stated in your data), the source viewer is showing the VISUAL document — react-pdf renders the PDF visually from the binary, not from extracted text. This is correct behavior and avoids the reading-order problem entirely. Do not try to render extracted text in the viewer.
- Treating AI errors (context limit hit, retrieval failure, model timeout) the same as form validation errors destroys trust. Each error type needs a distinct message: 'I could not retrieve property data right now — try again' is different from 'Your question is outside the property database scope.'
- Hallucinated citation links are worse than no citations. If a source [id] tag appears in model output but has no matching retrieved source, render it as plain text not a broken link. The Vercel KB pattern of source-first streaming (write sources, THEN stream model text) enforces this automatically.
- Do not show the 'Filtering 49 properties...' label and then return a vector-only top-k result for an aggregate query. The UX label sets an expectation of exhaustive search. If the backend is doing SQL-level filtering, the label is honest. If it is doing top-k vector retrieval, the label is lying. Match label to actual backend behavior.
- Image files (PNG) from R2: do not try to serve them directly from a signed URL in an img tag for inline preview if your R2 bucket is private. You need either (a) a Next.js API route that proxies with presigned URL and sets appropriate Cache-Control, or (b) a public R2 bucket subdomain. Broken images in a source panel are the fastest way to destroy the verification UX.
- Do not use Vercel AI SDK RSC (React Server Components generative UI) for the chat route in v1 — it adds complexity and the streaming behavior differs from useChat in ways that are hard to debug. Use the standard route handler + useChat pattern. RSC generative UI is worth revisiting for structured property card rendering in phase 2.

## IMPLEMENTATION NOTES
- Vercel AI SDK 6: use useChat from 'ai/react'. The hook gives you: messages (UIMessage[]), input, handleSubmit, isLoading, stop (abort), error, and data (custom data parts). Use the data field to receive source parts streamed before model text. Server route: import { streamText, createDataStreamResponse } from 'ai'; write source parts via dataStream.writeData({ type: 'sources', value: [...] }) before merging the model stream.
- Message part types to define: { type: 'text', content: string } and { type: 'sources', value: Array<{ id: string, propertyName: string, docType: 'pdf' | 'image', r2Key: string, pageOrRegion?: string }> }. The id is referenced inline as [1] in the model's text output via system prompt instruction.
- assistant-ui install: 'npm install @assistant-ui/react'. Use AssistantRuntimeProvider wrapping your layout, VercelUseChat runtime adapter for the useChat bridge. Thread, ThreadMessages, Composer all come pre-wired. Add your source citation rendering as a custom MessagePrimitive.Content override.
- shadcn/ui chat: 'npx shadcn add message-scroller bubble marker attachment'. MessageScroller props: messages={messages} className='flex-1 overflow-y-auto'. Marker variant='status' for showing 'Filtering 49 properties...' tool-call rows between user message and answer.
- Shimmer for thinking state: shadcn shimmer utility on a 2-line skeleton block. Show when isLoading=true and messages.at(-1)?.role === 'user' (no assistant reply yet). Replace with streaming text as first tokens arrive. Use a Marker with the contextual label ('Filtering properties...' vs 'Searching descriptions...') — set by a data part event the server sends immediately upon receiving the query type from your router.
- Source side panel: shadcn Sheet component, side='right', defaultWidth='45vw'. Inside: if docType==='pdf', render <Document file={presignedUrl}><Page pageNumber={1} /></Document> from react-pdf. If docType==='image', render <img src={presignedUrl} className='w-full h-auto' />. Presigned URL endpoint: GET /api/source-doc?key=r2Key returns a 15-minute presigned URL. Cache in sessionStorage to avoid repeated signing.
- Suggested prompts: render 4 cards in the empty Thread state using ai-sdk elements Suggestion component or a plain grid of shadcn Button variant='outline'. Hard-code 2 filter-type and 2 semantic-type examples. Include one that mentions 'staff inspected' to signal that field exists. Clicking a suggestion calls append({ role: 'user', content: promptText }) from useChat.
- Grounded refusal format: system prompt should instruct the model: 'If retrieved sources do not contain the answer, respond with exactly: INSUFFICIENT_DATA: [one sentence describing what was searched and what was missing]. Do not guess.' On the client, detect the INSUFFICIENT_DATA prefix and render it in a distinct amber-bordered Bubble variant with a 'Rephrase question' button that focuses the Composer — not as a generic error.
- Inline citations: after streaming completes, run a post-render pass replacing [1], [2] etc with <CitationChip id={n} onClick={() => openSheet(source)} /> components. Do this in a useMemo over the final message text, not during streaming (too many re-renders). CitationChip is a small Badge with the number and document type icon.
- For v1 conversation history: store messages in sessionStorage under a UUID key generated on first load. On page refresh, restore from sessionStorage. This gives per-tab persistence without Postgres and without shared-history leakage. Add Postgres-backed thread history only when per-user auth ships (phase 2).

## SOURCES
- https://vercel.com/blog/ai-sdk-5
- https://vercel.com/blog/ai-sdk-6
- https://vercel.com/kb/guide/building-ai-chat-app-with-rag-and-citations-on-vercel
- https://www.assistant-ui.com/
- https://github.com/assistant-ui/assistant-ui
- https://ui.shadcn.com/docs/changelog/2026-06-chat-components
- https://elements.ai-sdk.dev/
- https://www.shapeof.ai/patterns/citations
- https://uxpatterns.dev/patterns/ai-intelligence/ai-loading-states
- https://dev.to/flamehaven01/implementing-refusal-first-rag-why-we-architected-our-ai-to-say-i-dont-know-4h10
- https://thefrontkit.com/blogs/ai-chat-ui-best-practices
- https://builtin.com/articles/design-trust-conversational-ai
- https://www.shapeof.ai/patterns/stream-of-thought
- https://aiuxplayground.com/pattern/conversation-search/
- https://www.react-pdf-kit.dev/blog/top-6-pdf-viewers-for-reactjs-developers-in-2025
- https://www.nngroup.com/articles/explainable-ai/
- https://medium.com/bestfolios/building-trust-and-enhancing-interactions-7-essential-ai-ux-patterns-in-action-12e7604de435
- https://www.pertamapartners.com/insights/enterprise-ai-abandonment-2025