# Travel Inn prototype verification

**Run:** 8 September 2026 · local-only prototype

## Static checks

- `node --check` against both inline JavaScript blocks in `prototype/index.html`: passed (2 blocks, zero syntax errors).
- `Invoke-WebRequest http://localhost:4173/`: HTTP 200; the current HTML returned successfully.
- `Invoke-WebRequest http://localhost:4173/assets/agoratoli.png`: HTTP 200.
- Fixture inventory: 8 seeded conversations, 4 source fixtures, 4 local preview images.
- No package manager, environment variables, external API calls, database writes or credentials are used by the prototype.

## Browser checks (Chrome, 127.0.0.1:4173)

- Initial transcript, sidebar history, source rail and composer visible in the accessibility tree.
- Theme toggle changes light/dark semantic tokens; preference is written to local storage.
- Search opens a named modal, focuses its input, sets the app inert, filters seeded history, and Escape closes it with focus returned to the search trigger.
- Selecting a seeded history row changes the transcript and breadcrumb.
- Composer Enter starts a mock stream; Stop is exposed during streaming; final state returns to Ready and source cards update.
- Citation button changes the source rail to the selected source.
- Save answer updates the saved count; Saved answers renders the saved fixture and reopens its conversation.
- Source rail contains image previews, source metadata, excerpts, view action and save action.
- Profile identity is rendered in the bottom-left workspace footer; the top-right avatar and prototype coverage footer are absent.
- Document library navigation is absent.
- Desktop navigation hamburger collapses and reopens the sidebar; the button exposes matching `aria-expanded` and accessible labels.
- Sources button in the chat header collapses and reopens the evidence rail; the button and rail expose matching expanded/collapsed state.
- Prototype-only console filter (`127.0.0.1`) returned no error or warning entries.

## Limits

Manual NVDA/VoiceOver testing, axe/Lighthouse, 320 CSS pixel/400% zoom checks, touch keyboard behavior, and real backend streaming were not executed in this environment. The prototype is a navigable design artifact, not a production accessibility or correctness certification.
