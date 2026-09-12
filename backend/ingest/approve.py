"""Apply a curated vocabulary approval file.

Reads the generated SQL, takes the canonical INSERTs at face value, and turns
each "update review_queue set key = 'X' ... where key in (...)" into ALIAS ROWS
so the folding happens at LOAD time instead of once, after the fact.

    python -m backend.ingest.approve --dry
    python -m backend.ingest.approve --apply
"""
import argparse
import pathlib
import re

from backend import config, db

SQL = config.WORK / "vocab_approve.sql"

INSERT_RE = re.compile(
    r"insert into attribute_vocabulary\s*\([^)]*\)\s*values\s*\((.*?)\)\s*on conflict",
    re.I | re.S)
FOLD_RE = re.compile(
    r"update review_queue set key = '([^']+)'.*?where reason = 'new_key' and key in \((.*?)\)",
    re.I | re.S)


def _split_values(blob: str) -> list[str]:
    """Split a VALUES tuple on commas that are outside quotes."""
    out, cur, q = [], "", False
    i = 0
    while i < len(blob):
        c = blob[i]
        if c == "'":
            if q and i + 1 < len(blob) and blob[i + 1] == "'":
                cur += "''"; i += 2; continue
            q = not q
        if c == "," and not q:
            out.append(cur.strip()); cur = ""
        else:
            cur += c
        i += 1
    out.append(cur.strip())
    return [v[1:-1].replace("''", "'") if v.startswith("'") else (None if v.lower() == "null" else v)
            for v in out]


def parse(path: pathlib.Path):
    text = path.read_text(encoding="utf-8")
    labels = []
    for m in INSERT_RE.finditer(text):
        v = _split_values(m.group(1))
        if len(v) >= 8:
            labels.append(dict(zip(
                ("key", "definition", "not_this", "value_type",
                 "unit_kind", "cardinality", "relation_kind", "status"), v[:8])))
    aliases = {}
    for m in FOLD_RE.finditer(text):
        canon = m.group(1)
        for a in re.findall(r"'([^']+)'", m.group(2)):
            if a != canon:
                aliases[a] = canon
    return labels, aliases


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default=str(SQL))
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    labels, aliases = parse(pathlib.Path(args.file))
    print(f"{len(labels)} canonical labels, {len(aliases)} aliases folding into "
          f"{len(set(aliases.values()))} of them")
    for lab in labels:
        n = sum(1 for a, c in aliases.items() if c == lab["key"])
        print(f"  {lab['key']:<32} {lab['value_type']:<9} {lab['cardinality']:<7}"
              f"{'rel:' + lab['relation_kind'] if lab['relation_kind'] else '':<22} +{n} aliases")

    if not args.apply:
        print("\ndry run. re-run with --apply to write.")
        return

    with db.connect() as conn, conn.cursor() as cur:
        cur.executemany(
            "insert into attribute_vocabulary "
            "(key,definition,not_this,value_type,unit_kind,cardinality,relation_kind,status) "
            "values (%(key)s,%(definition)s,%(not_this)s,%(value_type)s,%(unit_kind)s,"
            "%(cardinality)s,%(relation_kind)s,'approved') "
            "on conflict (key) do update set definition=excluded.definition, "
            "not_this=excluded.not_this, value_type=excluded.value_type, "
            "unit_kind=excluded.unit_kind, cardinality=excluded.cardinality, "
            "relation_kind=excluded.relation_kind, status='approved', alias_of=null",
            labels)
        cur.executemany(
            "insert into attribute_vocabulary (key,status,alias_of) values (%s,'alias',%s) "
            "on conflict (key) do update set status='alias', alias_of=excluded.alias_of",
            list(aliases.items()))
        conn.commit()
        cur.execute("select status, count(*) from attribute_vocabulary group by 1 order by 2 desc")
        print("\nvocabulary now:", dict(cur.fetchall()))


if __name__ == "__main__":
    main()
