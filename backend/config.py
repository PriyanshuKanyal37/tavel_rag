"""Every tunable in one place. Nothing else reads os.environ directly."""
import os
import pathlib

from dotenv import load_dotenv

BACKEND = pathlib.Path(__file__).resolve().parent
ROOT = BACKEND.parent
load_dotenv(BACKEND / ".env")

# ---------------------------------------------------------------- paths
SOURCE_DIR = ROOT / "data" / "raw" / "Property Updates"
WORK = BACKEND / "work"            # renders, tiles, extraction JSON. All regenerable.
RENDERS = WORK / "renders"
OUT = WORK / "out"

# ---------------------------------------------------------------- models
# Pinned exactly. Aliases like "gemini-flash-latest" get repointed without
# notice -- we measured one doing it, for 11% fewer facts at the same price.
EXTRACT_MODEL = "gemini-3.1-pro-preview"
EMBED_MODEL = os.getenv("GEMINI_EMBEDDING_MODEL", "gemini-embedding-2")

# How much of a document reaches its embedding. The model accepts 8,192 tokens;
# this cap is in CHARACTERS, so ~4 chars/token puts 24,000 at roughly 6,000
# tokens with headroom to spare.
#
# It was 8,000 characters -- about 2,000 tokens, four times stricter than the
# model needs -- and it silently truncated the four longest documents. Ramathra
# Fort lost 1,130 characters from its vector while its full text sat intact in
# the database, so the document was harder to FIND than it was to read.
# Anything longer than this cap must be split, not clipped: see ingest/embed.py.
EMBED_MAX_CHARS = 24_000

# The answering path. Thinking is decided PER QUESTION now, by the mode the
# planner assigns (query/answer.py). An earlier note here said thinking was off
# because it was slow; the real fault was a max_output_tokens ceiling that the
# hidden reasoning ate, and the mode ladder raises that ceiling with the mode.
PLAN_MODEL = "gemini-3.8-flash"     # extract parameters and classify the mode
ANSWER_MODEL = "gemini-3.8-flash"   # write the reply, streamed
# Judgement modes may warrant the pro tier. Measure before adopting:
# tests/ab_model.py. Pinned, never "gemini-pro-latest" -- an alias was
# repointed under us once already.
ANSWER_MODEL_DEEP = "gemini-3.1-pro-preview"

# "503 This model is currently experiencing high demand" is common enough to
# have killed three live runs in one day, and no amount of retrying helps
# while a whole model is saturated. These siblings answer the same prompt.
# Order matters: nearest capability first.
# A fallback must accept the SAME config, not merely exist. gemini-3.6-flash is
# deliberately absent: it answers a plain prompt but rejects a response_schema
# with 400, so putting it here turned a transient 503 into a hard failure.
# Probed, not assumed -- see PART 11.
#
#   3.8-flash          plain OK · schema OK · thinking HIGH OK
#   3.5-flash          plain OK · schema OK · thinking HIGH OK
#   3-flash-preview    plain OK · schema OK · thinking HIGH OK
#   3.6-flash          plain OK · schema 400  ← excluded
MODEL_FALLBACKS = {
    "gemini-3.8-flash": ["gemini-3.5-flash", "gemini-3-flash-preview"],
    "gemini-3.1-pro-preview": ["gemini-3.8-flash", "gemini-3.5-flash"],
}


def model_chain(model: str) -> list:
    """The model, then whatever can stand in for it."""
    return [model] + MODEL_FALLBACKS.get(model, [])

# How many documents to send is no longer a count. It is a character budget
# spent down a priority ladder -- see query/gather.py BUDGET_CHARS. The old
# SEND_WHOLE_MAX / TOP_COMPLETE pair is gone: two fixed counts could not express
# "the named property always, then whatever else still fits".

# USD per 1M tokens (input, output). Verify against the vendor page before quoting.
PRICES = {
    "gemini-3.1-pro-preview": (2.00, 12.00),
    "gemini-3.8-flash": (0.30, 2.50),
}
USD_INR = 95.0                     # the pilot used 88; that was stale

# TWO KEYS, TWO DIFFERENT PROBLEMS. Neither error message says which.
#
#   GEMINI_API_KEY_2  the PAID project. Real throughput, prepaid balance spent.
#                     Says "prepayment credits are depleted".
#   GEMINI_API_KEY    a FREE TIER project. 20 requests per day, per model.
#                     Answers one test call, then says "quota exceeded" -- which
#                     reads like the paid failure and is not.
#
# The paid key is preferred, because it is the only one that can carry real use.
# `python -m backend.api.cli keys` reports which is which in five seconds.
GEMINI_KEY = os.getenv("GEMINI_API_KEY_2") or os.getenv("GEMINI_API_KEY")

# ---------------------------------------------------------------- rendering
PDF_DPI = 300                      # PDFs are vector: render at whatever we want

# ...but "whatever we want" still has to survive the reader's own downscaler.
# A4 at 300 DPI is 2480x3508; Claude caps the long edge at ~1568, so that page
# would arrive at 1108x1568 -- 134 effective DPI, under the 150 DPI line where
# character accuracy falls off. At 180 DPI an A4 page is 1489x2105, and tiled
# at 1450 every strip is 1489x1450: under the ceiling on BOTH axes, so nothing
# is resampled and the full 180 DPI reaches the model.
PDF_DPI_CLAUDE = 180

# The 37 source PNGs are 794px wide, 96 DPI, up to 5150px tall. Sent whole,
# the long edge blows the vision encoder's budget and the WHOLE page is scaled
# down -- measured as low as 397px wide (48 effective DPI). A tile is short
# enough that nothing is ever downscaled, so it arrives at native resolution.
TILE_WIDTH_NATIVE = True           # never upscale: interpolation adds no information
TILE_HEIGHT = 2400                 # overridden by the bakeoff; see ingest/tiling_test.py
TILE_OVERLAP = 0.12                # fraction, so a text line is never cut in half

# OCR runs at NATIVE resolution. Measured on the worst file: 99.1% mean
# confidence at 1x, and Lanczos upscaling made it *worse* (0.987 at 2x,
# 0.984 at 3x). The "upscale to 3x for OCR" heuristic does not apply to
# clean digital renders.
OCR_UPSCALE = 1

# ---------------------------------------------------------------- storage
R2_ACCOUNT_ID = os.getenv("R2_ACCOUNT_ID")
R2_ACCESS_KEY_ID = os.getenv("R2_ACCESS_KEY_ID")
R2_SECRET_ACCESS_KEY = os.getenv("R2_SECRET_ACCESS_KEY")
R2_BUCKET = os.getenv("R2_BUCKET")
R2_ENDPOINT = f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com" if R2_ACCOUNT_ID else None
PRESIGN_TTL = 15 * 60              # BUILD-SPEC section 3: links expire in 15 minutes

# ---------------------------------------------------------------- database
# Cookies are Secure by default, so they never travel over plain http. Set
# COOKIE_SECURE=0 only for local development against http://localhost.
# Connection pool. A Neon dial costs ~1s, so the API keeps a few warm.
POOL_MIN = int(os.getenv("POOL_MIN", "2"))
POOL_MAX = int(os.getenv("POOL_MAX", "12"))
POOL_MAX_IDLE = float(os.getenv("POOL_MAX_IDLE", "120"))      # Neon idles connections out
POOL_MAX_LIFETIME = float(os.getenv("POOL_MAX_LIFETIME", "1800"))
POOL_TIMEOUT = float(os.getenv("POOL_TIMEOUT", "10"))         # wait for a free connection

COOKIE_SECURE = os.getenv("COOKIE_SECURE", "1") != "0"

# SameSite decides whether the browser sends the cookie on a request the API's
# own page did not start. "strict" is right when the frontend is served from the
# same site as the API. Put them on different domains and "strict" silently
# drops the cookie on every call -- the login succeeds, everything after is 401,
# and the CORS allowances below look broken when they are not. That deployment
# needs COOKIE_SAMESITE=none, which browsers honour only over https.
COOKIE_SAMESITE = os.getenv("COOKIE_SAMESITE", "strict").lower()
if COOKIE_SAMESITE not in ("strict", "lax", "none"):
    raise SystemExit("COOKIE_SAMESITE must be strict, lax or none")
if COOKIE_SAMESITE == "none" and not COOKIE_SECURE:
    raise SystemExit("COOKIE_SAMESITE=none requires COOKIE_SECURE=1")

# Origins the browser frontend may call from. A Secure cookie is not sent
# over plain http, so local development needs COOKIE_SECURE=0 as well --
# without it the login succeeds and every later request is a 401, which
# looks like an auth bug rather than a cookie policy.
CORS_ORIGINS = [o.strip() for o in os.getenv(
    "CORS_ORIGINS",
    "http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173"
).split(",") if o.strip()]

DSN = os.getenv("PILOT_DSN")               # pooled: normal queries
DSN_DIRECT = os.getenv("PILOT_DSN_DIRECT") or DSN   # unpooled: DDL and index builds

# ---------------------------------------------------------------- safety
DEFAULT_BUDGET_INR = 500.0         # ingestion hard stop; the whole corpus is ~275

# Every live test run stops at this many rupees unless --budget says otherwise.
# Deliberately small: one AGENT question on the pro model is ~₹6, so a careless
# ten-question run is most of a month's remaining credit. The default should be
# a smoke test; spending more has to be a decision someone typed.
TEST_BUDGET_INR = 3.0


def price_inr(model: str, tokens_in: int, tokens_out: int) -> float:
    pin, pout = PRICES.get(model, (0.0, 0.0))
    return ((tokens_in / 1e6) * pin + (tokens_out / 1e6) * pout) * USD_INR


def require(*names: str) -> None:
    """Fail loudly at startup rather than three minutes into a batch."""
    missing = [n for n in names if not globals().get(n)]
    if missing:
        raise SystemExit(f"missing in backend/.env: {', '.join(missing)}")
