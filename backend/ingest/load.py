"""Write validated extraction into Neon.

Entity resolution is BLOCKED BY GEOGRAPHY. Without that, "KAAV Safari Lodge"
(Karnataka) and "The Safari Lodge Kanha" (Madhya Pradesh) scored 0.577 on
trigram similarity and silently merged -- two properties 1,500 km apart.
The generic words in this domain carry no identifying information, so we
strip them before comparing and require 0.80 to merge.
"""
import argparse
import collections
import json
import re

from psycopg.types.json import Json

from backend import config, db
from backend.ingest import ocr as ocr_mod
from backend.ingest import validate as validate_mod
from backend.ingest import vocab as vocab_mod

STOPWORDS = {
    "the", "a", "an", "and", "by", "at", "in", "on", "of",
    "hotel", "hotels", "resort", "resorts", "lodge", "lodges", "palace",
    "camp", "camps", "retreat", "safari", "jungle", "house", "villa",
    "fort", "haveli", "jungalow", "outpost", "property", "update",
}

# No CONNECTION_KINDS table here. Which labels create an edge, and which
# distance/duration keys belong to them, comes from attribute_vocabulary.


def core_name(s: str) -> str:
    toks = [t for t in re.split(r"[^a-z0-9]+", (s or "").lower()) if t]
    keep = [t for t in toks if t not in STOPWORDS]
    return " ".join(keep or toks)


def resolve_entity(cur, name, etype, state, city, doc_state=None):
    """exact -> alias -> trigram, blocked by state. Anything merely plausible
    is created separately and flagged, never merged."""
    state = state or doc_state

    cur.execute("select id from entities where lower(canonical_name)=lower(%s)", (name,))
    if (r := cur.fetchone()):
        return r[0], "exact", None
    cur.execute("select id from entities where %s = any(aliases)", (name.lower(),))
    if (r := cur.fetchone()):
        return r[0], "alias", None

    cur.execute(
        "select id, canonical_name, similarity(%s, core) s from ("
        "  select id, canonical_name, state,"
        "         regexp_replace(lower(canonical_name),'[^a-z0-9]+',' ','g') core"
        "  from entities) t "
        "where (%s::text is null or state is null or state = %s::text) "
        "order by similarity(%s, core) desc limit 1",
        (core_name(name), state, state, core_name(name)))
    r = cur.fetchone()
    if r and r[2] is not None and r[2] >= 0.80:
        return r[0], "trigram", None

    note = None
    if r and r[2] is not None and r[2] >= 0.50:
        note = f"near-miss {r[2]:.2f} vs {r[1]!r}"
    cur.execute(
        "insert into entities (entity_type,canonical_name,state,city) "
        "values (%s,%s,%s,%s) returning id",
        (etype or "other", name, state, city))
    return cur.fetchone()[0], "new", note


def _hours(f):
    """Normalise a drive-time fact to HOURS.

    The page writes "15 mins" and "2 hours" interchangeably. Storing the bare
    number put `duration_h = 15` on a 4.3 km airport transfer -- 15 hours to
    drive 4 km. The unit has to decide, not the number.
    """
    n = _num(f)
    if n is None:
        return None
    unit = (f.get("value_unit") or "").lower()
    text = (f.get("value") or "").lower()
    if unit.startswith("min") or (not unit and "min" in text):
        return round(n / 60, 3)
    if unit.startswith("sec"):
        return round(n / 3600, 4)
    if unit.startswith(("hour", "hr", "h")) or "hour" in text or "hr" in text:
        return n
    # No usable unit: a bare number over 12 on a drive time is minutes in
    # practice -- nobody drives 15 hours to an airport 4 km away.
    return round(n / 60, 3) if n > 12 else n


def _num(f):
    v = f.get("value_number")
    if v is None:
        val = (f.get("value") or "").strip().replace(",", "")
        if re.fullmatch(r"-?\d+(\.\d+)?", val):
            v = float(val)
    if v is None:
        return None
    return int(v) if float(v).is_integer() else float(v)


NEGATIVE = re.compile(r"\b(not|no|never|yet to be|awaiting|pending|absent|unavailable)\b", re.I)
POSITIVE = re.compile(r"\b(yes|available|present|offered|provided|has|included|inspected|operational)\b", re.I)


def coerce_boolean(f, v, stats) -> dict:
    """A boolean label whose value arrived as a sentence.

    "Not yet personally inspected by the product team" plainly means false, and
    losing it to the boolean rule would throw away Travel Inn's own due-diligence
    flag. Reading a leading negation is parsing, not inference -- but anything
    ambiguous is left alone so rule 1 sends it to review rather than guessing.
    """
    if v.resolve(f.get("key", "")) not in v.boolean_keys:
        return f
    raw = (f.get("value") or "").strip()
    if raw.lower() in ("true", "false"):
        return f
    neg, pos = NEGATIVE.search(raw), POSITIVE.search(raw)
    if neg and (not pos or neg.start() < pos.start()):
        decided = "false"
    elif pos and not neg:
        decided = "true"
    else:
        return f                       # ambiguous: let rule 1 hold it
    stats["boolean_coerced"] += 1
    ev = f.get("evidence") or raw      # keep the sentence as the proof
    return {**f, "value": decided, "value_type": "boolean", "evidence": ev}


def load_file(cur, d: dict, stats, resolutions, v, redo: bool = False) -> None:
    pages = [p for p in d["pages"] if p.get("data")]
    if not pages:
        return
    transcription = "\n\n".join(p["data"].get("transcription", "") for p in pages)
    ocr_blob = d.get("ocr") or {}
    text_layer = ocr_blob.get("text") or ""

    cur.execute(
        "insert into documents (sha1,rel_path,ext,page_count,is_tiled,transcription,"
        "text_layer,ocr_engine,extractor) values (%s,%s,%s,%s,%s,%s,%s,%s,%s) "
        "on conflict (sha1) do nothing",
        (d["sha1"], d["rel"], d["ext"], len(pages), d.get("is_tiled", False),
         transcription, text_layer or None, ocr_blob.get("engine"), d["model"]))
    if cur.rowcount == 0:
        if not redo:
            stats["duplicate_document_skipped"] += 1
            return
        # Approving a label changes nothing until the documents are read again,
        # and a plain reload skips anything already loaded. --redo drops just
        # THIS document's contributions and rebuilds them, so the operation is a
        # replace rather than an append -- run it twice and the counts hold.
        #
        # entities are deliberately left alone: they are shared between
        # documents, and entities.facts is merged with || so it re-converges.
        for table in ("fact_evidence", "connections"):
            cur.execute(f"delete from {table} where sha1 = %s", (d["sha1"],))
        cur.execute("delete from review_queue where sha1 = %s and not resolved",
                    (d["sha1"],))
        stats["documents_reprocessed"] += 1
    else:
        stats["documents"] += 1

    # The folder path is the client's own taxonomy -- far more reliable than
    # asking a model to infer geography from the text.
    parts = d["rel"].replace("\\", "/").split("/")
    doc_state = parts[0] if len(parts) > 1 else None
    if doc_state == "General Property Updates":
        doc_state = None

    ent_ids: dict[str, int] = {}
    for p in pages:
        for e in p["data"].get("entities", []):
            nm = (e.get("name") or "").strip()
            if not nm or nm.lower() in ent_ids:
                continue
            eid, how, note = resolve_entity(cur, nm, e.get("entity_type"),
                                            e.get("state"), e.get("city"), doc_state)
            ent_ids[nm.lower()] = eid
            resolutions[how] += 1
            if how == "new":
                stats["entities"] += 1
            if note:
                stats["flagged_near_miss"] += 1
                cur.execute("insert into review_queue (reason,entity,detail,sha1) "
                            "values ('possible_duplicate',%s,%s,%s)",
                            (nm, Json({"note": note}), d["sha1"]))
            cur.execute("insert into entity_documents values (%s,%s) on conflict do nothing",
                        (eid, d["sha1"]))

    # Mirror values are gathered per (entity, key) and written once, because a
    # MULTI-valued label needs an array. Writing each fact as it arrives kept
    # only the last one: seven properties list boating, and a filter for it
    # matched none of them.
    mirror = collections.defaultdict(list)

    # ---- validate across the whole document, then write what survives
    all_facts = []
    for p in pages:
        for f in p["data"].get("facts", []):
            f = dict(f)
            f["_page"] = p["page"]
            f["_y"] = p.get("y_offset", 0)
            all_facts.append(coerce_boolean(f, v, stats))

    # Both sources, not either. OCR is independent ground truth, but the reader
    # is instructed to CORRECT OCR errors against the image ("JULY 2D15" ->
    # "JULY 2025"), so a correctly-fixed quote is absent from the OCR text by
    # design. Requiring a hit in OCR alone rejected 456 good facts.
    haystack = f"{text_layer}\n{transcription}"
    accepted, rejected = validate_mod.validate(all_facts, haystack, v)

    for f, reason in rejected:
        cur.execute("insert into review_queue (reason,entity,key,detail,sha1) "
                    "values (%s,%s,%s,%s,%s)",
                    (reason[:60], f.get("entity_name"),
                     f.get("proposed_key") or f.get("key"), Json(f), d["sha1"]))
        stats["rejected"] += 1

    for f in accepted:
        key = f.get("key", "")
        # A reader that invented "room_features" meant the approved
        # "room_feature". Fold known aliases before the vocabulary gate, so a
        # naming variation does not cost us the fact.
        if key == "_new":
            key = v.resolve(f.get("proposed_key") or "_new")
        else:
            key = v.resolve(key)
        if key != f.get("key"):
            f = {**f, "key": key}
            stats["alias_folded"] += 1
        eid = ent_ids.get((f.get("entity_name") or "").strip().lower())
        if eid is None:
            cur.execute("insert into review_queue (reason,entity,key,detail,sha1) "
                        "values ('orphan_entity',%s,%s,%s,%s)",
                        (f.get("entity_name"), key, Json(f), d["sha1"]))
            stats["rejected_orphan"] += 1
            continue
        if key == "_new" or key not in v.approved:
            # Hold the fact AND register what the reader asked for, so the
            # vocabulary's own table shows what the corpus keeps demanding.
            proposed = f.get("proposed_key") or (key if key != "_new" else None)
            if proposed:
                vocab_mod.record_proposal(cur, proposed)
            cur.execute("insert into review_queue (reason,entity,key,detail,sha1) "
                        "values ('new_key',%s,%s,%s,%s)",
                        (f.get("entity_name"), proposed or key, Json(f), d["sha1"]))
            stats["held_new_key"] += 1
            continue

        scope = None
        if f.get("scope_key"):
            scope = Json({f["scope_key"]: f.get("scope_value")})

        bbox = None
        if ocr_blob.get("lines") and f.get("evidence_type") != "visual":
            b = ocr_mod.locate({"lines": ocr_blob["lines"]}, f.get("evidence"))
            if b:
                bbox = Json(b)
                stats["bbox_located"] += 1

        cur.execute(
            "insert into fact_evidence (entity_id,key,scope,value_text,value_num,"
            "value_unit,value_currency,asserted_as,evidence,evidence_type,page,bbox,"
            "sha1,section,block_kind,confidence) "
            "values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (eid, key, scope, (f.get("value") or "").strip(),
             _num(f) if key in v.numeric_keys else None,
             f.get("value_unit"), f.get("value_currency"),
             f.get("asserted_as", "stated"), f.get("evidence"),
             f.get("evidence_type", "text"), f.get("_page"), bbox, d["sha1"],
             f.get("section"), f.get("block_kind"), f.get("confidence")))
        stats["facts"] += 1

        if not f.get("scope_key"):      # the mirror the filter path reads
            n = _num(f) if key in v.numeric_keys else None
            mirror[(eid, key)].append(n if n is not None else (f.get("value") or "").strip())

    # ---- the mirror, written once per (entity, key)
    for (eid, key), values in mirror.items():
        uniq = list(dict.fromkeys(values))
        one = key in v.scalar_keys or len(uniq) == 1
        cur.execute("update entities set facts = facts || %s::jsonb where id=%s",
                    (Json({key: uniq[0] if one else uniq}), eid))

    # ---- connections: "nearest_airport = Bagdogra" becomes an edge
    by_key = collections.defaultdict(list)
    for f in accepted:
        by_key[(f.get("entity_name") or "").strip().lower(), f.get("key")].append(f)

    for (ename, key), fs in by_key.items():
        kind = v.relation_keys.get(key)
        if not kind:
            continue
        km_key = v.sibling(key, "distance")
        hr_key = v.sibling(key, "duration")
        src = ent_ids.get(ename)
        if src is None:
            continue
        for f in fs:
            target = (f.get("value") or "").strip()
            if not target:
                continue
            tid = ent_ids.get(target.lower())
            if tid is None:
                # The reader did not name it as an entity, so infer the type
                # from the relation itself rather than a hard-coded mapping.
                tid, _, _ = resolve_entity(cur, target, kind.replace("nearest_", ""),
                                           None, None, doc_state)
                ent_ids[target.lower()] = tid
            props = {}
            if km_key:
                km = next((_num(x) for x in by_key.get((ename, km_key), [])), None)
                if km is not None:
                    props["distance_km"] = km
            if hr_key:
                hr = next((_hours(x) for x in by_key.get((ename, hr_key), [])), None)
                if hr is not None:
                    props["duration_h"] = hr
            cur.execute(
                "insert into connections (from_entity,to_entity,kind,props,sha1,evidence) "
                "values (%s,%s,%s,%s,%s,%s)",
                (src, tid, kind, Json(props), d["sha1"], f.get("evidence")))
            stats["connections"] += 1


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default="out")
    ap.add_argument("--redo", action="store_true",
                    help="reprocess documents already loaded, replacing their facts. "
                         "Needed after approving vocabulary: a plain run skips them.")
    args = ap.parse_args()

    src = config.WORK / args.src
    files = sorted(src.glob("*.json"))
    if not files:
        raise SystemExit(f"no extraction JSON in {src}")

    stats, resolutions = collections.Counter(), collections.Counter()
    db.apply_schema()
    with db.connect() as conn, conn.cursor() as cur:
        v = vocab_mod.load(cur)          # seeds an empty table, then reads it back
        print(f"vocabulary: {len(v.approved)} approved, {len(v) - len(v.approved)} proposed")
        for fp in files:
            load_file(cur, json.loads(fp.read_text(encoding="utf-8")), stats,
                      resolutions, v, redo=args.redo)
        conn.commit()

    print(f"loaded from {src.name}  ({len(files)} files)")
    for k, v in sorted(stats.items()):
        print(f"  {k:28} {v}")
    print("\nentity resolution:")
    for k, v in resolutions.most_common():
        print(f"  {k:28} {v}")
    print("\ndatabase now:", db.stats())


if __name__ == "__main__":
    main()
