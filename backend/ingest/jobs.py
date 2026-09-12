"""Split the manifest into one small job file per document.

The Opus workflow fans out one subagent per document. A subagent cannot be
handed the whole manifest (it carries every OCR line for every file), so each
gets a compact job file naming its own tiles and its own text layer.
"""
import argparse
import json

from backend import config


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", nargs="+", default=["manifest_image.json"])
    ap.add_argument("--skip-done", action="store_true",
                    help="omit documents already extracted into claude_out/")
    a = ap.parse_args()

    manifest = []
    for name in a.manifest:
        manifest += json.loads((config.WORK / name).read_text(encoding="utf-8"))
    jobs_dir = config.WORK / "jobs"
    jobs_dir.mkdir(parents=True, exist_ok=True)
    done = {p.stem for p in (config.WORK / "claude_out").glob("*.json")} \
        if (config.WORK / "claude_out").exists() else set()

    listing = []
    for m in manifest:
        if a.skip_done and m["sha1"] in done:
            continue
        job = {
            "sha1": m["sha1"], "rel": m["rel"], "ext": m["ext"],
            "is_tiled": m["is_tiled"], "tile_count": m["page_count"],
            "tiles": [{"index": p["index"], "path": p["path"],
                       "size": f'{p["width"]}x{p["height"]}',
                       "y_offset": p["y_offset"]} for p in m["pages"]],
            "ocr_text": (m.get("ocr") or {}).get("text", ""),
            "ocr_conf": (m.get("ocr") or {}).get("mean_conf"),
            "out_path": str(config.WORK / "claude_out" / f'{m["sha1"]}.json'),
        }
        fp = jobs_dir / f'{m["sha1"]}.json'
        fp.write_text(json.dumps(job, ensure_ascii=False, indent=1), encoding="utf-8")
        listing.append({"sha1": m["sha1"], "rel": m["rel"],
                        "job": str(fp), "tiles": m["page_count"]})

    (config.WORK / "claude_out").mkdir(parents=True, exist_ok=True)
    out = config.WORK / "jobs.json"
    out.write_text(json.dumps(listing, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(listing)} job(s) -> {out}")
    print(f"{sum(j['tiles'] for j in listing)} tiles total")


if __name__ == "__main__":
    main()
