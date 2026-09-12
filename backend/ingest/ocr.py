"""Give the 37 images the text layer they have never had.

All 15 PDFs carry a text layer (mean 4,609 chars). All 37 images carry ZERO.
That asymmetry is why the grounding check -- "the quote must appear on the
page", verified against a source no model produced -- can only run on PDFs today.

RapidOCR (PP-OCRv6, ONNX, CPU) closes it. Measured on the worst file in the
corpus at NATIVE resolution: 99.1% mean confidence. Lanczos upscaling made it
worse (98.7% at 2x, 98.4% at 3x), so we do not upscale.

Boxes come back too, which is what makes evidence crops possible.
"""
import functools

import numpy as np
from PIL import Image

from backend import config


@functools.lru_cache(maxsize=1)
def _engine():
    from rapidocr import RapidOCR
    return RapidOCR()


def read(img: Image.Image) -> dict:
    """OCR one image at native resolution.

    Returns {"text": str, "lines": [{"text","conf","bbox":[x0,y0,x1,y1]}],
             "mean_conf": float, "engine": str}
    """
    if config.OCR_UPSCALE != 1:
        img = img.resize((img.width * config.OCR_UPSCALE, img.height * config.OCR_UPSCALE),
                         Image.LANCZOS)
    res = _engine()(np.array(img.convert("RGB")))

    def as_list(name):
        # these come back as numpy arrays, so `or []` would raise on truthiness
        v = getattr(res, name, None)
        return [] if v is None else list(v)

    txts, scores, boxes = as_list("txts"), as_list("scores"), as_list("boxes")

    lines = []
    for i, t in enumerate(txts):
        bbox = None
        if i < len(boxes) and boxes[i] is not None:
            pts = np.asarray(boxes[i], dtype=float).reshape(-1, 2) / config.OCR_UPSCALE
            bbox = [float(pts[:, 0].min()), float(pts[:, 1].min()),
                    float(pts[:, 0].max()), float(pts[:, 1].max())]
        lines.append({"text": t,
                      "conf": float(scores[i]) if i < len(scores) else None,
                      "bbox": bbox})

    # reading order: top to bottom, then left to right
    lines.sort(key=lambda l: (round((l["bbox"][1] if l["bbox"] else 0) / 12),
                              l["bbox"][0] if l["bbox"] else 0))
    ok = [l["conf"] for l in lines if l["conf"] is not None]
    return {
        "text": "\n".join(l["text"] for l in lines),
        "lines": lines,
        "mean_conf": sum(ok) / len(ok) if ok else 0.0,
        "engine": "rapidocr-ppocrv6",
    }


def slice_text(ocr: dict, y0: float, y1: float) -> str:
    """The OCR text falling inside one tile's vertical band."""
    out = []
    for l in ocr["lines"]:
        b = l["bbox"]
        if b is None or (b[1] < y1 and b[3] > y0):
            out.append(l["text"])
    return "\n".join(out)


def locate(ocr: dict, quote: str) -> list[float] | None:
    """Bounding box of a quote on the page, for evidence crops.

    Matches on a normalised prefix -- the model's quote and the OCR line agree
    on characters far more reliably than on whitespace or punctuation.
    """
    def norm(s):
        return "".join(c for c in (s or "").lower() if c.isalnum())

    q = norm(quote)
    if len(q) < 8:
        return None
    hits = [l["bbox"] for l in ocr["lines"] if l["bbox"] and norm(l["text"]) and
            (norm(l["text"])[:40] in q or q[:40] in norm(l["text"]))]
    if not hits:
        return None
    return [min(h[0] for h in hits), min(h[1] for h in hits),
            max(h[2] for h in hits), max(h[3] for h in hits)]


def demo() -> None:
    import pathlib
    p = config.SOURCE_DIR / "Nepal" / "Red Panda Outpost Property Update.png"
    if not pathlib.Path(p).exists():
        print("sample missing, skipping"); return
    img = Image.open(p).convert("RGB").crop((28, 1180, 400, 1400))
    r = read(img)
    assert r["text"], "OCR produced nothing"
    assert r["mean_conf"] > 0.90, r["mean_conf"]
    assert any(l["bbox"] for l in r["lines"]), "no boxes returned"
    assert locate(r, "Nearest Railhead in India") is not None, "locate() failed on a known line"
    print(f"ocr OK - {len(r['lines'])} lines, conf {r['mean_conf']:.3f}, boxes present")


if __name__ == "__main__":
    demo()
