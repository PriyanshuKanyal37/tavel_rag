"""Document embeddings.

Retrieval is whole-document, not chunk-based -- a document here averages
~1,500 tokens against a 1M-token window, so there is nothing to gain by
cutting them up and plenty to lose. One vector per document is enough to
rank which documents to open.

3072 dimensions truncated to 1536: half the index, no measurable loss on a
corpus this size.
"""
import argparse

from google import genai
from google.genai import types

from backend import config, db

DIMS = 1536


def embed_one(client, text: str, task: str) -> list[float]:
    """One call per document.

    Passing a LIST of contents returns a single embedding, not one per item --
    verified against the API. Zipping inputs to outputs therefore silently
    dropped 7 of every 8 documents, and the count looked fine until the
    `embedded` total came back as 7 of 51.
    """
    r = client.models.embed_content(
        model=config.EMBED_MODEL,
        contents=text,
        config=types.EmbedContentConfig(task_type=task, output_dimensionality=DIMS),
    )
    vals = r.embeddings[0].values
    if len(vals) != DIMS:
        raise SystemExit(f"expected {DIMS} dims, got {len(vals)}")
    return vals


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch", type=int, default=8)
    ap.add_argument("--redo", action="store_true", help="re-embed everything")
    args = ap.parse_args()
    config.require("GEMINI_KEY")
    client = genai.Client(api_key=config.GEMINI_KEY)

    where = "" if args.redo else "where embedding is null"
    with db.connect() as conn, conn.cursor() as cur:
        cur.execute(f"select sha1, rel_path, transcription from documents {where} order by sha1")
        rows = cur.fetchall()
        print(f"{len(rows)} document(s) to embed")
        for i, (sha, rel, text) in enumerate(rows, 1):
            # the path carries the client's own geography; it helps the vector
            body = text or ""
            if len(body) > config.EMBED_MAX_CHARS:
                # never silently: a clipped vector makes a document hard to FIND
                # while its full text still answers perfectly once opened, which
                # looks like bad retrieval rather than a truncated input.
                print(f"  ! {rel}: {len(body)} chars, embedding first "
                      f"{config.EMBED_MAX_CHARS}")
            v = embed_one(client, f"{rel}\n\n{body[:config.EMBED_MAX_CHARS]}",
                          "RETRIEVAL_DOCUMENT")
            cur.execute("update documents set embedding=%s where sha1=%s", (str(v), sha))
            if cur.rowcount != 1:
                raise SystemExit(f"update touched {cur.rowcount} rows for {sha}")
            conn.commit()
            if i % 10 == 0 or i == len(rows):
                print(f"  {i}/{len(rows)}")

    with db.connect(direct=True, autocommit=True) as conn:
        # HNSW build wants more than Neon's default 64MB maintenance_work_mem
        conn.execute("set maintenance_work_mem = '256MB'")
        conn.execute("create index if not exists documents_embedding_idx on documents "
                     "using hnsw (embedding vector_cosine_ops)")
    print("index ready:", db.stats())


if __name__ == "__main__":
    main()
