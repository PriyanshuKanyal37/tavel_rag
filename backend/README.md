# Travel Inn RAG — backend

Ingestion pipeline: source documents → Cloudflare R2 + Neon Postgres.

## Setup

```
cd Travel_rag
uv venv backend/.venv --python 3.12
uv pip install --python backend/.venv/Scripts/python.exe -r backend/requirements.txt
```

Credentials live in `backend/.env`. Nothing reads `os.environ` except `config.py`.

## Run

```
python -m backend.ingest.run status                  # what's in the DB and bucket
python -m backend.ingest.run all --budget 400        # the whole pipeline
python -m backend.ingest.run extract --limit 3       # try three files first
python -m backend.ingest.run extract --only Nepal    # one folder
```

Every step is resumable. `extract` skips any file whose JSON already exists, so
a run that stops on budget or a network failure continues where it left off.

## Steps

| | |
|---|---|
| `schema` | extensions + tables on Neon (idempotent) |
| `extract` | render/tile → OCR → Gemini → `work/out/*.json`, uploads to R2 |
| `load` | validate → entity resolution → Neon |
| `embed` | document vectors + HNSW index |

## Modules

```
config.py     every tunable, all env reading
db.py         Neon: pooled for queries, direct for DDL and index builds
storage.py    R2: keys DERIVED from the content hash, never stored in Postgres
schema.sql    tables

ingest/
  render.py       PDF → 300 DPI pages;  image → native-width tiles
  ocr.py          RapidOCR text layer + bounding boxes
  prompt.py       vocabulary with definitions, extraction instruction, schema
  extract.py      Gemini call: resumable, budget-capped, retry-on-transient
  validate.py     the nine rules
  load.py         entity resolution + write
  embed.py        document vectors
  run.py          CLI
  tiling_test.py  the three-way bakeoff that chose TILE_HEIGHT
```

## Two things that are easy to get wrong

**Never store a presigned URL.** It expires in 15 minutes. Store the content
hash; `storage.page_key()` derives the object key and `storage.presign()` mints
a fresh URL per request. Signing is local HMAC — no network call, no latency.

**Tiling is not optional for the 37 images.** They are 794px wide and up to
5150px tall. Sent whole, the long edge exceeds the vision encoder's budget and
the *entire page* is scaled down — measured at 397px wide, 48 effective DPI, on
`Nepal/Red Panda Outpost`. Upscaling cannot fix it: enlarging makes the
downscale proportionally harsher and cancels exactly (a 4× FSRCNN run delivered
a byte-identical 397px). A short strip never trips the ceiling.

## Self-checks

```
python -m backend.ingest.render      # tile coverage, no gaps
python -m backend.ingest.ocr         # OCR + bbox location on a real page
python -m backend.ingest.validate    # all nine rules, on known-bad facts
```
