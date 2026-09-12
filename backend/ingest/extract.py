"""Read every page with Gemini. Resumable, budget-capped, uploads as it goes.

Budget check PROJECTS the next call's cost before making it. Checking
"spent >= cap" afterwards is how a $0.50 cap became $0.764 in testing.
"""
import argparse
import json
import pathlib
import time

from google import genai
from google.genai import types

from backend import config, storage
from backend.ingest import ocr as ocr_mod
from backend.ingest import prompt as prompt_mod
from backend.ingest import render

TRANSIENT = ("503", "UNAVAILABLE", "500", "INTERNAL", "504", "DEADLINE", "RESOURCE_EXHAUSTED_RETRY")
PRIOR_INR_PER_CALL = 2.85          # measured on the pilot; refined as we go


def call_with_retry(client, model, png: bytes, text: str, tries: int = 5):
    delay = 4
    for attempt in range(1, tries + 1):
        try:
            return client.models.generate_content(
                model=model,
                contents=[types.Part.from_bytes(data=png, mime_type="image/png"), text],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=prompt_mod.SCHEMA,
                ),
            )
        except Exception as e:
            msg = str(e)
            # 429 is quota, not load. Retrying makes it worse and costs money.
            if "429" in msg or ("RESOURCE_EXHAUSTED" in msg and "retry" not in msg.lower()):
                raise
            if attempt == tries or not any(t in msg for t in TRANSIENT):
                raise
            time.sleep(delay)
            delay *= 2


def source_files() -> list[pathlib.Path]:
    exts = {".pdf", ".png", ".jpg", ".jpeg"}
    return sorted(p for p in config.SOURCE_DIR.rglob("*")
                  if p.is_file() and p.suffix.lower() in exts)


def process_file(client, path: pathlib.Path, outdir: pathlib.Path, model: str,
                 spent: float, budget: float, upload: bool) -> tuple[float, dict | None]:
    sha = render.sha1_of(path)
    dest = outdir / f"{sha}.json"
    rel = str(path.relative_to(config.SOURCE_DIR))
    if dest.exists():
        return spent, None

    pages, texts, tiled = render.pages_for(path)

    # Images get an OCR text layer (they have none). OCR the FULL source once,
    # then slice per tile -- boxes stay in source coordinates for evidence crops.
    full_ocr = None
    if path.suffix.lower() != ".pdf":
        full_ocr = ocr_mod.read(render.Image.open(path).convert("RGB"))
        texts = [ocr_mod.slice_text(full_ocr, p.y_offset, p.y_offset + p.image.height)
                 for p in pages]

    if upload:
        storage.put_if_absent(storage.original_key(sha, path.suffix.lower()),
                              path.read_bytes())
        for p in pages:
            png = render.png_bytes(p.image)
            storage.put_if_absent(storage.page_key(sha, p.index), png, "image/png")
            storage.put_if_absent(storage.thumb_key(sha, p.index),
                                  render.thumb_bytes(p.image), "image/jpeg")

    result = {
        "sha1": sha, "rel": rel, "ext": path.suffix.lower(), "model": model,
        "is_tiled": tiled, "page_count": len(pages),
        "ocr": ({"engine": full_ocr["engine"], "mean_conf": full_ocr["mean_conf"],
                 "text": full_ocr["text"], "lines": full_ocr["lines"]} if full_ocr else None),
        "pages": [],
    }

    per_call = PRIOR_INR_PER_CALL
    for p, text in zip(pages, texts):
        if spent + per_call > budget:
            print(f"  !! budget would be exceeded ({spent:.2f} + ~{per_call:.2f} "
                  f"> {budget:.2f}). Stopping before this call.")
            break
        png = render.png_bytes(p.image)
        t0 = time.time()
        try:
            r = call_with_retry(client, model, png,
                                prompt_mod.build_prompt(text, p.index, len(pages),
                                                        path.name, is_tile=tiled))
        except Exception as e:
            result["pages"].append({"page": p.index, "error": str(e)[:400]})
            print(f"  p{p.index}/{len(pages)}  ERROR {str(e)[:90]}")
            continue

        u = r.usage_metadata
        tin = getattr(u, "prompt_token_count", 0) or 0
        tout = ((getattr(u, "candidates_token_count", 0) or 0) +
                (getattr(u, "thoughts_token_count", 0) or 0))
        cost = config.price_inr(model, tin, tout)
        spent += cost
        per_call = max(per_call, cost)          # projection uses the worst seen

        try:
            data = json.loads(r.text)
        except Exception as e:
            result["pages"].append({"page": p.index, "error": f"unparseable: {e}",
                                    "inr": round(cost, 4)})
            print(f"  p{p.index}/{len(pages)}  UNPARSEABLE JSON")
            continue

        result["pages"].append({
            "page": p.index, "y_offset": p.y_offset,
            "tin": tin, "tout": tout, "inr": round(cost, 4),
            "seconds": round(time.time() - t0, 1), "data": data,
        })
        print(f"  p{p.index}/{len(pages)}  in={tin:6} out={tout:5} INR {cost:5.2f} "
              f"{time.time()-t0:5.1f}s  entities={len(data.get('entities', []))} "
              f"facts={len(data.get('facts', []))}")

    good = [p for p in result["pages"] if p.get("data")]
    if not good:
        # Never persist an all-failed file: resume would skip it forever.
        print(f"  !! no page succeeded, not saving {rel}")
        return spent, None

    dest.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    return spent, result


def main() -> None:
    ap = argparse.ArgumentParser(description="Extract every page with Gemini.")
    ap.add_argument("--budget", type=float, default=config.DEFAULT_BUDGET_INR)
    ap.add_argument("--model", default=config.EXTRACT_MODEL)
    ap.add_argument("--out", default="out")
    ap.add_argument("--limit", type=int, default=0, help="stop after N files")
    ap.add_argument("--only", default="", help="substring filter on the path")
    ap.add_argument("--kind", choices=("pdf", "image", "all"), default="all")
    ap.add_argument("--no-upload", action="store_true", help="skip R2")
    args = ap.parse_args()

    config.require("GEMINI_KEY")
    outdir = config.WORK / args.out
    outdir.mkdir(parents=True, exist_ok=True)
    client = genai.Client(api_key=config.GEMINI_KEY)

    files = source_files()
    if args.kind == "pdf":
        files = [f for f in files if f.suffix.lower() == ".pdf"]
    elif args.kind == "image":
        files = [f for f in files if f.suffix.lower() != ".pdf"]
    if args.only:
        files = [f for f in files if args.only.lower() in str(f).lower()]
    if args.limit:
        files = files[:args.limit]

    print(f"model {args.model}   files {len(files)}   budget INR {args.budget:.2f}   "
          f"upload={'no' if args.no_upload else 'yes'}\n")

    spent, done, skipped = 0.0, 0, 0
    for i, path in enumerate(files, 1):
        rel = path.relative_to(config.SOURCE_DIR)
        if spent >= args.budget:
            print(f"\nbudget reached at INR {spent:.2f}. Re-run to continue.")
            break
        print(f"[{i}/{len(files)}] {rel}")
        before = spent
        spent, res = process_file(client, path, outdir, args.model, spent,
                                  args.budget, upload=not args.no_upload)
        if res is None and spent == before:
            skipped += 1
            print("  (already done)")
        elif res:
            done += 1

    print(f"\ndone {done}   already-had {skipped}   spent INR {spent:.2f} of {args.budget:.2f}")


if __name__ == "__main__":
    main()
