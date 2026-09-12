"""Approve vocabulary by evidence, with nobody in the loop.

    python -m backend.ingest.autoapprove            # dry run, changes nothing
    python -m backend.ingest.autoapprove --apply
    python -m backend.ingest.autoapprove --min 2 --apply
    python -m backend.ingest.autoapprove --revert   # put them back

THE RULE: a label is approved when it appears on at least `--min` DISTINCT
properties, and its held values agree on a type.

Why that rule and not "approve everything". Approval decides what is QUERYABLE --
what you can filter, count, sort and compare on. A label used by exactly one
property cannot be compared against anything, so approving it buys nothing and
costs a longer label list for the planner to read on every question. Of 346 held
labels, 266 are used once. The full text still answers questions about them; it
always did.

Approving is only half. The held facts live in review_queue and are materialised
by a reload -- see `--status`.
"""
import argparse
import collections
import sys

from backend import db, retry

MIN_PROPERTIES = 3


def survey(cur):
    """Held facts grouped by label: which properties, which value types."""
    cur.execute("""select key, entity, detail->>'value_type'
                   from review_queue where reason = 'new_key' and not resolved""")
    ents, types, facts = (collections.defaultdict(set), collections.defaultdict(collections.Counter),
                          collections.Counter())
    for key, entity, vtype in cur.fetchall():
        ents[key].add(entity)
        types[key][vtype or "text"] += 1
        facts[key] += 1
    return ents, types, facts


def choose(ents, types, facts, minimum: int):
    picked, skipped = [], []
    for key in sorted(ents, key=lambda k: (-len(ents[k]), k)):
        n = len(ents[key])
        vtype, agree = types[key].most_common(1)[0]
        consistent = agree / sum(types[key].values()) >= 0.6
        if n >= minimum and consistent:
            picked.append((key, n, facts[key], vtype))
        else:
            skipped.append((key, n, facts[key],
                            "too few properties" if n < minimum else "mixed value types"))
    return picked, skipped


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--min", type=int, default=MIN_PROPERTIES,
                    help=f"distinct properties a label needs (default {MIN_PROPERTIES})")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--revert", action="store_true", help="set auto-approved labels back")
    ap.add_argument("--status", action="store_true")
    args = ap.parse_args()

    with db.connect(tries=20) as conn, conn.cursor() as cur:
        if args.status:
            cur.execute("select status, count(*) from attribute_vocabulary group by 1 order by 1")
            print("vocabulary:", dict(cur.fetchall()))
            cur.execute("select count(*) from review_queue where reason='new_key' and not resolved")
            held = cur.fetchone()[0]
            cur.execute("select count(*) from fact_evidence")
            print(f"held facts: {held}   live facts: {cur.fetchone()[0]}")
            print("\nApproving a label does not move its facts. They are materialised by")
            print("a reload from backend/work/out — which costs no Gemini, the extraction")
            print("JSON is already on disk. See PART 10 of the plan before running it.")
            return

        if args.revert:
            cur.execute("update attribute_vocabulary set status = 'proposed' "
                        "where status = 'approved' and definition = 'auto: seen on "
                        "several properties' returning key")
            keys = [r[0] for r in cur.fetchall()]
            if args.apply:
                conn.commit()
            print(f"{'reverted' if args.apply else 'would revert'} {len(keys)} label(s)")
            return

        ents, types, facts = survey(cur)
        picked, skipped = choose(ents, types, facts, args.min)

        print(f"{len(ents)} held labels, {sum(facts.values())} held facts\n")
        print(f"APPROVE — on {args.min}+ properties, consistent type")
        for key, n, f, vtype in picked:
            print(f"   {key:<32} {n:>2} properties  {f:>3} facts  {vtype}")
        one = sum(1 for s in skipped if s[1] == 1)
        mixed = sum(1 for s in skipped if s[3] == "mixed value types")
        print(f"\nLEAVE PROPOSED — {len(skipped)} labels, "
              f"{sum(s[2] for s in skipped)} facts")
        print(f"   {one} appear on exactly ONE property "
              f"({sum(s[2] for s in skipped if s[1] == 1)} facts): nothing to filter,")
        print("   count or compare with, and the document text answers them anyway.")
        print(f"   {len(skipped) - one - mixed} appear on 2 — below the threshold.")
        if mixed:
            print(f"   {mixed} have inconsistent value types and are not safe to query.")

        if not args.apply:
            print(f"\nDRY RUN. Nothing changed. Re-run with --apply to approve "
                  f"{len(picked)} label(s).")
            return

        for key, _n, _f, vtype in picked:
            cur.execute(
                "insert into attribute_vocabulary (key, definition, value_type, status) "
                "values (%s, 'auto: seen on several properties', %s, 'approved') "
                "on conflict (key) do update set status = 'approved', "
                "value_type = coalesce(attribute_vocabulary.value_type, excluded.value_type), "
                "definition = coalesce(attribute_vocabulary.definition, excluded.definition)",
                (key, vtype))
        conn.commit()
        print(f"\napproved {len(picked)} label(s). Reversible: --revert --apply")
        print("Their facts are still held; a reload materialises them (--status).")


if __name__ == "__main__":
    try:
        retry.call(main, tries=20, delay=4)
    except Exception as exc:
        why = retry.explain(exc)
        if not why:
            raise
        sys.exit(f"\n✗ {why}")
