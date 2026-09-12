"""Turn a source file into the images the vision model actually sees.

Two different problems, two different treatments:

  PDFs    are vector. Render at any DPI we like (300). No ceiling, no loss.

  PNGs    are raster, fixed at 794x96dpi, and up to 5150px TALL. Sent whole,
          the long edge exceeds the vision encoder's budget and the entire
          page is scaled down -- measured at 397px wide / 48 effective DPI on
          the worst file. Upscaling does not help: enlarging makes the
          downscale proportionally harsher and cancels out exactly (a 4x
          FSRCNN run delivered a byte-identical 397px).

          Tiling is the only fix. A short strip never trips the ceiling, so it
          arrives at native 794px. This is what a human does when they zoom.
"""
import dataclasses
import hashlib
import io
import pathlib

import pypdfium2 as pdfium
from PIL import Image

from backend import config


@dataclasses.dataclass
class Page:
    index: int              # 1-based page or tile number
    image: Image.Image
    y_offset: int = 0       # top of this tile within the full source image
    source_height: int = 0  # full source height, for mapping boxes back


def sha1_of(path: pathlib.Path) -> str:
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _pdf_pages(path: pathlib.Path, dpi: int | None = None) -> tuple[list[Page], list[str]]:
    dpi = dpi or config.PDF_DPI
    doc = pdfium.PdfDocument(str(path))
    pages, texts = [], []
    for i in range(len(doc)):
        pg = doc[i]
        img = pg.render(scale=dpi / 72).to_pil().convert("RGB")
        pages.append(Page(index=i + 1, image=img, source_height=img.height))
        try:
            texts.append(pg.get_textpage().get_text_bounded() or "")
        except Exception:
            texts.append("")
    return pages, texts


def tile(img: Image.Image, height: int | None = None, overlap: float | None = None) -> list[Page]:
    """Cut a tall image into strips at NATIVE width.

    Overlapping, so a line of text is never severed at a boundary. Never
    upscales -- interpolation adds no information, and the source is a clean
    digital render with nothing to reconstruct.
    """
    height = height or config.TILE_HEIGHT
    overlap = config.TILE_OVERLAP if overlap is None else overlap
    if img.height <= height:
        return [Page(index=1, image=img, y_offset=0, source_height=img.height)]

    step = max(1, int(height * (1 - overlap)))
    tops = list(range(0, max(1, img.height - height + step), step))
    if tops[-1] + height < img.height:          # never drop the tail
        tops.append(img.height - height)

    out = []
    for i, top in enumerate(tops, 1):
        top = min(top, max(0, img.height - height))
        box = (0, top, img.width, min(img.height, top + height))
        out.append(Page(index=i, image=img.crop(box), y_offset=top, source_height=img.height))
    return out


def pages_for(path: pathlib.Path) -> tuple[list[Page], list[str], bool]:
    """Returns (pages, per-page text layer, was_tiled)."""
    if path.suffix.lower() == ".pdf":
        pages, texts = _pdf_pages(path)
        return pages, texts, False
    img = Image.open(path).convert("RGB")
    pages = tile(img)
    return pages, [""] * len(pages), len(pages) > 1


def png_bytes(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, "PNG", optimize=True)
    return buf.getvalue()


def thumb_bytes(img: Image.Image, width: int = 320) -> bytes:
    t = img.copy()
    t.thumbnail((width, width * 8), Image.LANCZOS)
    buf = io.BytesIO()
    t.convert("RGB").save(buf, "JPEG", quality=78, optimize=True)
    return buf.getvalue()


def demo() -> None:
    """Self-check: tiles must cover the whole image and overlap, never gap."""
    img = Image.new("RGB", (794, 5150), "white")
    ts = tile(img, height=2400, overlap=0.12)
    assert len(ts) >= 3, len(ts)
    assert all(t.image.width == 794 for t in ts), "native width must be preserved"
    assert ts[0].y_offset == 0
    assert ts[-1].y_offset + ts[-1].image.height == 5150, "tail must be covered"
    for a, b in zip(ts, ts[1:]):
        assert b.y_offset < a.y_offset + a.image.height, "gap between tiles"
    short = tile(Image.new("RGB", (794, 2100)), height=2400)
    assert len(short) == 1 and short[0].image.height == 2100
    print(f"render OK - 794x5150 -> {len(ts)} tiles, all 794 wide, no gaps")


if __name__ == "__main__":
    demo()
