"""Run Gemini 3.1 Pro over tiles Opus has already read, so the two can be compared.

Same tiles, same contract, same OCR text layer. The only variable is the reader.

    python -m backend.ingest.gemini_compare --sha <sha1> --budget 40
"""
import argparse
import json
import pathlib
import time

from google import genai

from backend import config
from backend.ingest import extract as ex
from backend.ingest import prompt as prompt_mod


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sha", required=True)
    ap.add_argument("--budget", type=float, default=40.0)
    ap.add_argument("--tiles", type=int, default=0, help="cap tiles read (0 = all)")
    a = ap.parse_args()

    config.require("GEMINI_KEY")
    job = json.loads((config.WORK / "jobs" / f"{a.sha}.json").read_text(encoding="utf-8"))
    tiles = job["tiles"][:a.tiles] if a.tiles else job["tiles"]
    ocr_text = job.get("ocr_text", "")

    client = genai.Client(api_key=config.GEMINI_KEY)
    print(f"{job['rel']}\n{len(tiles)} tile(s), budget INR {a.budget:.2f}\n")

    spent, pages = 0.0, []
    for t in tiles:
        if spent + 12 > a.budget:
            print("  stopping: next call could exceed budget")
            break
        png = pathlib.Path(t["path"]).read_bytes()
        # same slice of the text layer the Opus agent was given
        text = ocr_text if len(tiles) == 1 else ocr_text
        t0 = time.time()
        r = ex.call_with_retry(
            client, config.EXTRACT_MODEL, png,
            prompt_mod.build_prompt(text, t["index"], len(tiles),
                                    pathlib.Path(job["rel"]).name, is_tile=job["is_tiled"]))
        u = r.usage_metadata
        tin = getattr(u, "prompt_token_count", 0) or 0
        tout = ((getattr(u, "candidates_token_count", 0) or 0) +
                (getattr(u, "thoughts_token_count", 0) or 0))
        cost = config.price_inr(config.EXTRACT_MODEL, tin, tout)
        spent += cost
        try:
            d = json.loads(r.text)
        except Exception as e:
            print(f"  tile {t['index']}  UNPARSEABLE  ({e})")
            continue
        pages.append({"page": t["index"], "y_offset": t["y_offset"], "data": d})
        print(f"  tile {t['index']}/{len(tiles)}  in={tin:6} out={tout:5} "
              f"INR {cost:5.2f}  {time.time()-t0:5.1f}s  "
              f"facts={len(d.get('facts', []))} ents={len(d.get('entities', []))}")

    out = config.WORK / "gemini_compare"
    out.mkdir(parents=True, exist_ok=True)
    dest = out / f"{a.sha}.json"
    dest.write_text(json.dumps({
        "sha1": a.sha, "rel": job["rel"], "ext": job["ext"],
        "model": config.EXTRACT_MODEL, "is_tiled": job["is_tiled"],
        "page_count": len(pages), "inr": round(spent, 2), "pages": pages,
    }, ensure_ascii=False), encoding="utf-8")

    facts = sum(len(p["data"].get("facts", [])) for p in pages)
    print(f"\n{facts} facts, INR {spent:.2f} spent -> {dest}")


if __name__ == "__main__":
    main()
