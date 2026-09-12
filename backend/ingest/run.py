"""One command for the whole ingestion.

    python -m backend.ingest.run all --budget 400

Steps, each independently runnable and each resumable:

    schema    create extensions and tables on Neon
    extract   render/tile -> OCR -> Gemini -> work/out/*.json  (uploads to R2)
    load      validate -> entity resolution -> Neon
    embed     document vectors + HNSW index
    status    what is in the database and the bucket right now
"""
import argparse
import subprocess
import sys

from backend import config, db, storage

STEPS = ("schema", "extract", "load", "embed")


def _run(module: str, *extra: str) -> None:
    cmd = [sys.executable, "-m", module, *extra]
    print(f"\n$ {' '.join(cmd[2:])}\n" + "-" * 64)
    if subprocess.call(cmd) != 0:
        raise SystemExit(f"{module} failed")


def status() -> None:
    print("database :", db.stats())
    try:
        print("r2       :",
              {p: storage.count(p + "/") for p in ("originals", "pages", "thumbs", "crops")})
    except SystemExit as e:
        print("r2       :", e)
    with db.connect() as conn, conn.cursor() as cur:
        cur.execute("select reason, count(*) from review_queue where not resolved "
                    "group by reason order by 2 desc limit 12")
        rows = cur.fetchall()
    if rows:
        print("\nreview queue:")
        for reason, n in rows:
            print(f"  {n:>4}  {reason}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("step", choices=(*STEPS, "all", "status", "reset"))
    ap.add_argument("--budget", type=float, default=config.DEFAULT_BUDGET_INR)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--only", default="")
    ap.add_argument("--out", default="out")
    ap.add_argument("--no-upload", action="store_true")
    a = ap.parse_args()

    if a.step == "status":
        return status()
    if a.step == "reset":
        confirm = input("This DROPS every table. Type 'reset' to confirm: ")
        if confirm.strip() != "reset":
            raise SystemExit("aborted")
        db.reset(); db.apply_schema()
        return print("reset done:", db.stats())

    extract_args = ["--budget", str(a.budget), "--out", a.out]
    if a.limit:
        extract_args += ["--limit", str(a.limit)]
    if a.only:
        extract_args += ["--only", a.only]
    if a.no_upload:
        extract_args += ["--no-upload"]

    todo = STEPS if a.step == "all" else (a.step,)
    for s in todo:
        if s == "schema":
            db.apply_schema()
            print("schema applied:", db.stats())
        elif s == "extract":
            _run("backend.ingest.extract", *extract_args)
        elif s == "load":
            _run("backend.ingest.load", "--src", a.out)
        elif s == "embed":
            _run("backend.ingest.embed")
    status()


if __name__ == "__main__":
    main()
