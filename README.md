# Travel Inn Knowledge Assistant

A retrieval-augmented question answering tool over Travel Inn's own property
documents, for the sales team. Ask in prose, get a short answer with a citation
on every claim, and click a citation to see the page it came from.

## What is here

```
backend/    FastAPI service: planner, retrieval, answering, SSE streaming
  api/      HTTP surface, auth, evidence crops, rate limiting
  query/    the four answer modes, gather, history, titles
  schema.sql
frontend/   React 19 + TypeScript + Vite
tests/      backend tests
docs/       notes
```

The corpus itself is not in this repository. The supplier documents and the
page images derived from them are client material and already live in Neon and
Cloudflare R2, which is what the service reads.

## Running it locally

```
.\dev.ps1
```

Backend on `127.0.0.1:8000`, frontend on `127.0.0.1:5173`, both reloading on
save. Use `-ApiPort 8001` if something else already holds 8000.

Copy `backend/.env.example` to `backend/.env` and fill it in first.

## How answers work

A planner reads the question and picks one of four modes, then retrieval
gathers material and the answer is streamed back.

| Mode | Retrieval | Reasoning | Output ceiling |
|---|---|---|---|
| chat | none | off | 1,024 |
| fast | one pass | off | 2,048 - 16,384 |
| think | one pass | high | 16,384 |
| agent | up to 4 rounds | high | 24,576 |

`max_output_tokens` is one bucket shared by the model's hidden reasoning and
the visible reply, so every ceiling has to hold both. Ceilings that only held
the reply truncated answers mid-sentence.

Only the sources an answer actually cites are shown as evidence, renumbered
`1..N` so the first chip is the first source.

## Deployment

See `render.yaml`. The frontend rewrites `/api/*` to the backend so the login
cookie stays same-origin.

## Tests

```
cd frontend
npm test              # unit
npm run test:ui       # responsive + WCAG contrast
npm run test:routes   # routing and deep links
npm run test:live     # end to end, needs a running backend and spends credit
```

Three backend modules carry their own checks:

```
python -m backend.query.history
python -m backend.query.title
python -m backend.api.throttle
```
