"""Evidence crops: the few lines a fact was actually read from.

A citation that opens a whole page still leaves someone scanning it. The crop
puts the sentence on screen.

THE COORDINATE TRAP. `fact_evidence.bbox` is in the coordinates of the ORIGINAL
image, while `fact_evidence.page` is a TILE index for the 37 tall PNGs. Cropping
a tile with these numbers lands on the wrong line, or off the image entirely --
27 of 40 sampled boxes do not fit their tile, because the tiles are 1450px tall
and the originals run to 5150px. Crops are cut from `originals/`, never `pages/`.

Made on demand and cached in R2. Pre-generating 2,043 crops nobody may click is
work with no reader.
"""
import io

from PIL import Image

from backend import config, storage

PAD = 14            # px of breathing room, so the line is not shaved
MIN_SIDE = 24       # a sliver is not evidence


class NoEvidence(Exception):
    """The fact carries no bbox, so there is nothing to crop."""


def fact_box(cur, fact_id: int):
    cur.execute("""select f.sha1, f.bbox, d.ext, f.page, left(coalesce(f.evidence,''), 90)
                   from fact_evidence f join documents d on d.sha1 = f.sha1
                   where f.id = %s""", (fact_id,))
    row = cur.fetchone()
    if not row:
        raise NoEvidence(f"no fact {fact_id}")
    if not row[1]:
        raise NoEvidence(f"fact {fact_id} has no bounding box")
    return row


def make(cur, fact_id: int, force: bool = False) -> str:
    """Returns the R2 key of the crop, cutting it first if it is not there."""
    sha1, bbox, ext, _page, _ev = fact_box(cur, fact_id)
    key = storage.crop_key(sha1, fact_id)
    if not force and storage.exists(key):
        return key

    source = storage.original_key(sha1, ext or "")
    if not storage.exists(source):
        raise NoEvidence(f"original missing for {sha1[:8]}")
    body = storage.client().get_object(Bucket=config.R2_BUCKET, Key=source)["Body"].read()
    im = Image.open(io.BytesIO(body))
    if im.mode not in ("RGB", "L"):
        im = im.convert("RGB")

    w, h = im.size
    x0, y0, x1, y1 = (float(v) for v in bbox)
    box = (max(0, int(x0) - PAD), max(0, int(y0) - PAD),
           min(w, int(x1) + PAD), min(h, int(y1) + PAD))
    if box[2] - box[0] < MIN_SIDE or box[3] - box[1] < MIN_SIDE:
        raise NoEvidence(f"fact {fact_id} box is degenerate: {bbox}")

    out = io.BytesIO()
    im.crop(box).save(out, format="PNG", optimize=True)
    storage.put(key, out.getvalue(), "image/png")
    return key
