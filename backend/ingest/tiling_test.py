"""Settle the tiling question by measurement, not argument.

Three modes on the same files, same prompt, same model:
    whole   the page as-is  (today's behaviour: downscaled to 48-73 eff DPI)
    t2400   794-wide strips, 2400 tall
    t1200   794-wide strips, 1200 tall

Graded on facts found, entities found, visual facts, and -- the metric that
matters -- what fraction of text evidence can be located in the OCR text
layer. That layer is produced by RapidOCR, not by the vision model, so it is
independent ground truth.

    python -m backend.ingest.tiling_test --budget 60
"""
import argparse
import json
import time

from google import genai

from backend import config
from backend.ingest import extract as ex
from backend.ingest import ocr as ocr_mod
from backend.ingest import prompt as prompt_mod
from backend.ingest import render

FILES = [
    "Nepal/Red Panda Outpost Property Update.png",        # worst: 794x5150, 48 eff DPI
    "Assam/Tezpur/_Postcard Tezpur Property Update.png",  # icon-heavy
    "Karnataka/Kabini/Kaav Safari Lodge Property Update.png",
]
MODES = {"whole": None, "t2400": 2400, "t1200": 1200}


def norm(s: str) -> str:
    return "".join(c for c in (s or "").lower() if c.isalnum())


def grounded(facts: list[dict], ocr_text: str) -> tuple[int, int]:
    """How many text-evidence quotes actually appear in the OCR layer."""
    hay = norm(ocr_text)
    tx = [f for f in facts if f.get("evidence_type") != "visual" and f.get("evidence")]
    ok = sum(1 for f in tx if norm(f["evidence"])[:60] and norm(f["evidence"])[:60] in hay)
    return ok, len(tx)


def dedup(facts: list[dict]) -> list[dict]:
    seen, out = set(), []
    for f in facts:
        k = (norm(f.get("entity_name")), f.get("key"), norm(f.get("value")),
             f.get("scope_key"), norm(f.get("scope_value")))
        if k not in seen:
            seen.add(k)
            out.append(f)
    return out


def run_mode(client, path, img, full_ocr, mode, height, budget_left):
    pages = ([render.Page(1, img, 0, img.height)] if height is None
             else render.tile(img, height=height))
    facts, ents, cost, secs = [], [], 0.0, 0.0
    for p in pages:
        if cost > budget_left:
            return None
        text = ocr_mod.slice_text(full_ocr, p.y_offset, p.y_offset + p.image.height)
        t0 = time.time()
        r = ex.call_with_retry(
            client, config.EXTRACT_MODEL, render.png_bytes(p.image),
            prompt_mod.build_prompt(text, p.index, len(pages), path.name,
                                    is_tile=height is not None))
        secs += time.time() - t0
        u = r.usage_metadata
        tin = getattr(u, "prompt_token_count", 0) or 0
        tout = ((getattr(u, "candidates_token_count", 0) or 0) +
                (getattr(u, "thoughts_token_count", 0) or 0))
        cost += config.price_inr(config.EXTRACT_MODEL, tin, tout)
        try:
            d = json.loads(r.text)
        except Exception:
            continue
        facts += d.get("facts", [])
        ents += d.get("entities", [])
    uniq = dedup(facts)
    ok, tot = grounded(uniq, full_ocr["text"])
    return {
        "mode": mode, "calls": len(pages), "raw_facts": len(facts),
        "facts": len(uniq),
        "entities": len({norm(e.get("name")) for e in ents if e.get("name")}),
        "visual": sum(1 for f in uniq if f.get("evidence_type") == "visual"),
        "grounded": f"{ok}/{tot}" if tot else "0/0",
        "ground_pct": round(100 * ok / tot, 1) if tot else 0.0,
        "inr": round(cost, 2), "secs": round(secs, 1),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--budget", type=float, default=60.0)
    args = ap.parse_args()
    config.require("GEMINI_KEY")
    client = genai.Client(api_key=config.GEMINI_KEY)

    spent, rows = 0.0, []
    for rel in FILES:
        path = config.SOURCE_DIR / rel.replace("/", "\\")
        if not path.exists():
            print(f"MISSING {rel}")
            continue
        img = render.Image.open(path).convert("RGB")
        print(f"\n=== {path.name}  {img.width}x{img.height} ===")
        full_ocr = ocr_mod.read(img)
        print(f"    OCR: {len(full_ocr['lines'])} lines, conf {full_ocr['mean_conf']:.3f}")
        for mode, h in MODES.items():
            if spent >= args.budget:
                print("    budget reached, stopping")
                break
            r = run_mode(client, path, img, full_ocr, mode, h, args.budget - spent)
            if r is None:
                print(f"    {mode:<6} skipped (budget)")
                continue
            spent += r["inr"]
            r["file"] = path.name[:28]
            rows.append(r)
            print(f"    {mode:<6} {r['calls']} calls  facts {r['facts']:>3} "
                  f"(raw {r['raw_facts']:>3})  ents {r['entities']:>2}  "
                  f"visual {r['visual']:>2}  grounded {r['grounded']:>7} "
                  f"({r['ground_pct']:>5.1f}%)  INR {r['inr']:5.2f}  {r['secs']:5.1f}s")

    out = config.WORK / "tiling_test.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rows, indent=1), encoding="utf-8")

    print(f"\n{'':28} {'mode':<7}{'facts':>6}{'ents':>6}{'vis':>5}{'grounded':>10}{'INR':>7}")
    for r in rows:
        print(f"{r['file']:<28} {r['mode']:<7}{r['facts']:>6}{r['entities']:>6}"
              f"{r['visual']:>5}{r['ground_pct']:>9.1f}%{r['inr']:>7.2f}")
    agg = {}
    for r in rows:
        a = agg.setdefault(r["mode"], {"facts": 0, "vis": 0, "inr": 0.0, "g": []})
        a["facts"] += r["facts"]; a["vis"] += r["visual"]
        a["inr"] += r["inr"]; a["g"].append(r["ground_pct"])
    print(f"\n{'TOTAL':<28} {'mode':<7}{'facts':>6}{'':>6}{'vis':>5}{'grounded':>10}{'INR':>7}")
    for m, a in agg.items():
        print(f"{'':<28} {m:<7}{a['facts']:>6}{'':>6}{a['vis']:>5}"
              f"{sum(a['g'])/len(a['g']):>9.1f}%{a['inr']:>7.2f}")
    print(f"\nspent INR {spent:.2f} of {args.budget:.2f}   -> {out}")


if __name__ == "__main__":
    main()
