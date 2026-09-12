"""Fold the Opus subagents' output into the same shape Gemini's produces.

Each subagent writes work/claude_out/<sha1>.json with just its extraction.
This joins that to the manifest (OCR blob, paths, tile geometry) so load.py
cannot tell which model read the document -- one loader, one set of rules,
one review queue, whichever reader produced the facts.
"""
import argparse
import json

from backend import config

MODEL = "claude-opus-5"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", nargs="+", default=["manifest_image.json"])
    ap.add_argument("--src", default="claude_out")
    ap.add_argument("--out", default="out")
    a = ap.parse_args()

    manifest = {}
    for name in a.manifest:
        for m in json.loads((config.WORK / name).read_text(encoding="utf-8")):
            manifest[m["sha1"]] = m
    src = config.WORK / a.src
    out = config.WORK / a.out
    out.mkdir(parents=True, exist_ok=True)

    written = skipped = 0
    empty = []
    for fp in sorted(src.glob("*.json")):
        d = json.loads(fp.read_text(encoding="utf-8"))
        sha = d.get("sha1") or fp.stem
        m = manifest.get(sha)
        if not m:
            print(f"  no manifest entry for {sha}, skipping")
            skipped += 1
            continue

        by_index = {p["index"]: p for p in m["pages"]}
        pages = []
        for p in d.get("pages", []):
            data = p.get("data")
            if not data or not (data.get("facts") or data.get("transcription")):
                continue
            geo = by_index.get(p.get("page"), {})
            pages.append({"page": p.get("page"), "y_offset": geo.get("y_offset", 0),
                          "data": data})
        if not pages:
            empty.append(m["rel"])
            continue

        (out / f"{sha}.json").write_text(json.dumps({
            "sha1": sha, "rel": m["rel"], "ext": m["ext"], "model": MODEL,
            "is_tiled": m["is_tiled"], "page_count": len(pages),
            "ocr": m.get("ocr"), "pages": pages,
        }, ensure_ascii=False), encoding="utf-8")
        written += 1
        facts = sum(len(p["data"].get("facts", [])) for p in pages)
        ents = sum(len(p["data"].get("entities", [])) for p in pages)
        print(f"  {written:>2}. {facts:>3} facts {ents:>2} ents  {m['rel'][:58]}")

    print(f"\nwrote {written}, skipped {skipped}")
    if empty:
        print(f"EMPTY ({len(empty)}) - these produced nothing and need a re-run:")
        for r in empty:
            print(f"   {r}")
    missing = set(manifest) - {f.stem for f in src.glob("*.json")}
    if missing:
        print(f"\nNO OUTPUT AT ALL ({len(missing)}):")
        for sha in sorted(missing):
            print(f"   {manifest[sha]['rel']}")


if __name__ == "__main__":
    main()
