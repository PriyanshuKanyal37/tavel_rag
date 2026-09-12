"""Render, tile, OCR and upload — everything before a model reads anything.

Costs nothing: local CPU only. Produces work/tiles/<sha1>/pNNN.png plus a
manifest, which is what the Opus subagent workflow consumes.

TILE HEIGHT DEPENDS ON WHICH MODEL WILL READ IT:

    Gemini   downscales above ~2576px on the long edge  -> tiles up to 2400
    Claude   downscales above ~1568px on the long edge  -> tiles up to 1450

Using Gemini's height for a Claude reader would silently reintroduce the exact
downscale problem tiling exists to remove: a 794x2400 tile arrives at Claude
as 519x1568, narrower than the untouched source.
"""
import argparse
import json

from backend import config, storage
from backend.ingest import ocr as ocr_mod
from backend.ingest import render

HEIGHTS = {"claude": 1450, "gemini": 2400}


def prep_file(path, tile_height: int, upload: bool, pdf_dpi: int | None = None) -> dict:
    sha = render.sha1_of(path)
    rel = str(path.relative_to(config.SOURCE_DIR))
    is_pdf = path.suffix.lower() == ".pdf"

    if is_pdf:
        rendered, page_texts = render._pdf_pages(path, dpi=pdf_dpi)
        # A rendered PDF page is tall too. Tile it for the same reason, keeping
        # each page's own text layer attached to every strip cut from it.
        pages, texts, n = [], [], 0
        for pg, txt in zip(rendered, page_texts):
            for t in render.tile(pg.image, height=tile_height):
                n += 1
                pages.append(render.Page(index=n, image=t.image, y_offset=t.y_offset,
                                         source_height=pg.image.height))
                texts.append(txt)
        # A PDF's embedded text is BETTER ground truth than OCR -- it is the
        # characters the designer typed, not a guess from pixels. Persist it in
        # the same slot OCR uses, so rule 7 can check quotes against something
        # the reader did not write. Omitting this made the grounding check
        # circular for exactly the 14 documents with the best evidence.
        joined = "\n\n".join(t for t in page_texts if t)
        full_ocr = {"engine": "pdf-text-layer", "mean_conf": 1.0,
                    "text": joined, "lines": []} if joined.strip() else None
        tiled = len(pages) > len(rendered)
    else:
        img = render.Image.open(path).convert("RGB")
        full_ocr = ocr_mod.read(img)
        pages = render.tile(img, height=tile_height)
        texts = [ocr_mod.slice_text(full_ocr, p.y_offset, p.y_offset + p.image.height)
                 for p in pages]
        tiled = len(pages) > 1

    outdir = config.WORK / "tiles" / sha
    outdir.mkdir(parents=True, exist_ok=True)
    entries = []
    for p, t in zip(pages, texts):
        png = render.png_bytes(p.image)
        fp = outdir / f"p{p.index:03d}.png"
        fp.write_bytes(png)
        entries.append({
            "index": p.index, "path": str(fp), "y_offset": p.y_offset,
            "width": p.image.width, "height": p.image.height,
            "text": t,
        })
        if upload:
            storage.put_if_absent(storage.page_key(sha, p.index), png, "image/png")
            storage.put_if_absent(storage.thumb_key(sha, p.index),
                                  render.thumb_bytes(p.image), "image/jpeg")
    if upload:
        storage.put_if_absent(storage.original_key(sha, path.suffix.lower()),
                              path.read_bytes())

    return {
        "sha1": sha, "rel": rel, "ext": path.suffix.lower(),
        "is_pdf": is_pdf, "is_tiled": tiled, "tile_height": tile_height,
        "page_count": len(pages), "pages": entries,
        "ocr": ({"engine": full_ocr["engine"], "mean_conf": full_ocr["mean_conf"],
                 "text": full_ocr["text"], "lines": full_ocr["lines"]} if full_ocr else None),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reader", choices=list(HEIGHTS), default="claude")
    ap.add_argument("--height", type=int, default=0, help="override tile height")
    ap.add_argument("--kind", choices=("image", "pdf", "all"), default="all")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--no-upload", action="store_true")
    a = ap.parse_args()

    from backend.ingest.extract import source_files
    files = source_files()
    if a.kind == "image":
        files = [f for f in files if f.suffix.lower() != ".pdf"]
    elif a.kind == "pdf":
        files = [f for f in files if f.suffix.lower() == ".pdf"]
    if a.limit:
        files = files[:a.limit]

    height = a.height or HEIGHTS[a.reader]
    pdf_dpi = config.PDF_DPI_CLAUDE if a.reader == "claude" else config.PDF_DPI
    print(f"reader={a.reader}  tile height={height}  pdf dpi={pdf_dpi}  "
          f"files={len(files)}  upload={'no' if a.no_upload else 'yes'}\n")

    manifest, tiles, seen = [], 0, set()
    for i, p in enumerate(files, 1):
        m = prep_file(p, height, upload=not a.no_upload, pdf_dpi=pdf_dpi)
        if m["sha1"] in seen:
            print(f"[{i}/{len(files)}] DUPLICATE of an earlier file, skipping  {m['rel']}")
            continue
        seen.add(m["sha1"])
        manifest.append(m)
        tiles += m["page_count"]
        conf = f"  ocr {m['ocr']['mean_conf']:.3f}" if m["ocr"] else ""
        print(f"[{i}/{len(files)}] {m['page_count']:>2} tiles{conf}  {m['rel'][:62]}")

    out = config.WORK / f"manifest_{a.kind}.json"
    out.write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n{len(manifest)} documents, {tiles} tiles -> {out}")


if __name__ == "__main__":
    main()
