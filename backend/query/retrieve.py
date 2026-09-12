"""The retrieval surface: every source, each callable on its own.

Nothing here chooses. gather.py runs whichever sources the question implies and
labels the results; picking one source and discarding the others leaves a wrong
guess with no fallback. What each source is FOR:

    count_where     "how many have a pool" -- never similarity search, which
                    returns the 25 most pool-ish documents, not a number
    find_entities   "tell me about Ramathra Fort" -- exact, alias, then trigram
    near_target     "which lodges are near Kanha" -- the connections graph
    semantic        "somewhere romantic in the hills" -- the only place
                    similarity is the right question

Documents come back WHOLE. One averages ~4,900 characters, so chunking would
lose the layout and gain nothing at this size.
"""
import dataclasses

from backend import db


@dataclasses.dataclass
class Doc:
    sha1: str
    rel_path: str
    page_count: int
    transcription: str
    entity_names: list[str]


@dataclasses.dataclass
class Fact:
    entity: str
    key: str
    value: str
    unit: str | None
    scope: dict | None
    asserted_as: str
    evidence: str
    sha1: str
    page: int


# ---------------------------------------------------------------- entities
def find_entities(cur, term: str, limit: int = 8) -> list[tuple[int, str, str, float]]:
    """Exact, then alias, then trigram. Returns (id, name, state, score)."""
    cur.execute(
        "select id, canonical_name, coalesce(state,''), "
        "       greatest(similarity(canonical_name, %s), "
        "                case when lower(canonical_name) = lower(%s) then 1.0 else 0 end) s "
        "from entities "
        "where lower(canonical_name) = lower(%s) or %s = any(aliases) "
        "   or canonical_name %% %s "
        "order by s desc, length(canonical_name) limit %s",
        (term, term, term, term.lower(), term, limit))
    return [(r[0], r[1], r[2], float(r[3])) for r in cur.fetchall()]


def _numeric(val) -> bool:
    """Can this value take part in a numeric comparison at all?"""
    try:
        float(str(val).strip())
        return True
    except (TypeError, ValueError):
        return False


def _where(conditions: list[tuple[str, str, str]], entity_type: str | None = None,
           state: str | None = None, city: str | None = None,
           near: str | None = None, ids: list = None) -> tuple[str, list]:
    """The shared WHERE clause for the filter path. conditions are (key, op, value).

    Built once so the COUNT and the LIST can never describe different sets. Two
    hand-written clauses drift, and when they do the number above the rows stops
    matching the rows.
    """
    sql: list[str] = []
    params: list = []
    for key, op, val in conditions:
        # A numeric operator with a non-numeric value is a planner slip, not a
        # query: "How many properties are in Rajasthan?" came back as
        # (state, "=", "Rajasthan"), and Postgres types the parameter from the
        # numeric comparison and aborts the whole request. Treat it as the text
        # match the model plainly meant.
        if op in ("<", "<=", ">", ">=", "=") and not _numeric(val):
            op = "contains"
        if op in ("<", "<=", ">", ">=", "="):
            sql.append(f" and (facts->>%s) ~ '^-?[0-9.]+$' and (facts->>%s)::numeric {op} %s")
            params += [key, key, val]
        elif op == "exists":
            sql.append(" and facts ? %s")
            params.append(key)
        elif op == "true":
            sql.append(" and lower(facts->>%s) = 'true'")
            params.append(key)
        elif op == "false":
            sql.append(" and lower(facts->>%s) = 'false'")
            params.append(key)
        else:  # contains
            # A multi-valued label is stored as a JSON ARRAY: seven properties
            # list boating among their activities, and `facts->>'activities'`
            # on an array does not match any single one of them. Search the
            # elements too, or every multi-valued filter silently returns zero.
            sql.append(
                " and (lower(facts->>%s) like %s"
                " or exists (select 1 from jsonb_array_elements_text("
                "      case when jsonb_typeof(facts->%s) = 'array'"
                "           then facts->%s else '[]'::jsonb end) el"
                "    where lower(el) like %s))")
            like = f"%{str(val).lower()}%"
            params += [key, like, key, key, like]
    if entity_type:
        sql.append(" and entity_type = %s")
        params.append(entity_type)
    if state:
        sql.append(" and state ilike %s")
        params.append(state)
    if city:
        sql.append(" and city ilike %s")
        params.append(city)
    if ids:
        # The user NAMED the properties. Counting the condition across the
        # whole corpus and labelling it authoritative answers a question
        # nobody asked: "does Courtyard House Kanha have a pool?" came back
        # with 31.
        sql.append(" and id = any(%s)")
        params.append(list(ids))
    if near:
        # "properties near Kanha" -- the graph, as a filter. Trigram on the far
        # side so "Kanha" reaches "Kanha National Park".
        sql.append(" and id in (select c.from_entity from connections c "
                   "join entities t on t.id = c.to_entity "
                   "where t.canonical_name %% %s or lower(t.canonical_name) = lower(%s))")
        params += [near, near]
    return "".join(sql), params


def entities_where(cur, conditions: list[tuple[str, str, str]], entity_type: str | None = None,
                   state: str | None = None, city: str | None = None,
                   near: str | None = None, ids: list = None, limit: int = 1000):
    """Filter on the JSONB mirror -- 'properties with a pool under 20 rooms'.

    Reads entities.facts, so it is one index scan, not a join over evidence.
    The list is CAPPED. Never report len() of it as a total: use count_where().
    """
    where, params = _where(conditions, entity_type, state, city, near, ids)
    cur.execute(
        "select id, canonical_name, coalesce(state,''), entity_type, facts "
        "from entities where true" + where + " order by canonical_name limit %s",
        params + [limit])
    return cur.fetchall()


def count_where(cur, conditions: list[tuple[str, str, str]], entity_type: str | None = None,
                state: str | None = None, city: str | None = None,
                near: str | None = None, ids: list = None) -> int:
    """The same filter, UNCAPPED. This is the only number allowed to be quoted.

    entities_where() stops at `limit`, so len(rows) is a confident lie the moment
    the cap is reached -- and with 408 entities a count carrying no filter at all
    ("how many properties do we have?") already reaches it.
    """
    where, params = _where(conditions, entity_type, state, city, near, ids)
    cur.execute("select count(*) from entities where true" + where, params)
    return cur.fetchone()[0]


def coverage(cur, keys: list[str], entity_type: str | None = None,
             state: str | None = None, city: str | None = None,
             near: str | None = None, ids: list = None) -> dict[str, tuple[int, int]]:
    """How many entities in scope RECORD each key, and how many say nothing.

    The honest denominator. 31 properties record a pool and 3 record its absence,
    but 40 hotels carry no pool fact either way -- and those 40 are UNKNOWN, not
    "no pool". Without this number an answer cannot tell the difference.
    """
    if not keys:
        return {}
    # the denominator must describe the SAME set the count described: a Kanha
    # query counted 3 and then explained coverage over all 74 hotels.
    scope, params = _where([], entity_type, state, city, near, ids)
    out: dict[str, tuple[int, int]] = {}
    for key in dict.fromkeys(keys):
        cur.execute(
            "select count(*) filter (where facts ? %s), count(*) filter (where not (facts ? %s)) "
            "from entities where true" + scope, [key, key] + params)
        recorded, missing = cur.fetchone()
        out[key] = (recorded, missing)
    return out


def conflicting(cur, keys: list[str], entity_ids: list[int] | None = None):
    """Entities recording more than one UNSCOPED value for the same key.

    entities.facts holds exactly ONE value per key, so a filter or a sort quietly
    picks a side of a disagreement the documents actually state. Oberoi Rajgarh
    Palace records both "65 rooms" and "66 rooms"; the mirror shows 65.

    Scoped facts are excluded on purpose -- "4 Deluxe Rooms" alongside "65 rooms"
    is a part and a whole, not a contradiction.
    """
    if not keys:
        return []
    sql = ("select e.canonical_name, f.key, array_agg(distinct f.value_text), "
           "       e.facts->>f.key "
           "from entities e join fact_evidence f on f.entity_id = e.id "
           "where f.key = any(%s) and f.rank <> 'deprecated' and f.scope is null")
    params: list = [list(dict.fromkeys(keys))]
    if entity_ids:
        sql += " and e.id = any(%s)"
        params.append(entity_ids)
    sql += (" group by e.canonical_name, f.key, e.facts->>f.key "
            "having count(distinct f.value_text) > 1")
    cur.execute(sql, params)
    return cur.fetchall()


# ---------------------------------------------------------------- facts
def facts_for(cur, entity_ids: list[int], keys: list[str] | None = None,
              limit: int = 2000) -> list[Fact]:
    """Live facts with their evidence. Deprecated claims are never returned."""
    if not entity_ids:
        return []
    sql = ("select e.canonical_name, f.key, f.value_text, f.value_unit, f.scope, "
           "       f.asserted_as, f.evidence, f.sha1, f.page "
           "from fact_evidence f join entities e on e.id = f.entity_id "
           "where f.entity_id = any(%s) and f.rank <> 'deprecated'")
    params: list = [entity_ids]
    if keys:
        sql += " and f.key = any(%s)"
        params.append(keys)
    sql += " order by e.canonical_name, f.key limit %s"
    params.append(limit)
    cur.execute(sql, params)
    return [Fact(*r) for r in cur.fetchall()]


# ---------------------------------------------------------------- graph
def nearest(cur, entity_ids: list[int], kind: str | None = None, limit: int = 40):
    """Connection edges, ordered by distance. 'Closest to the gate' lives here."""
    sql = ("select a.canonical_name, c.kind, b.canonical_name, "
           "       (c.props->>'distance_km')::numeric, (c.props->>'duration_h')::numeric, "
           "       c.evidence, c.sha1 "
           "from connections c join entities a on a.id = c.from_entity "
           "join entities b on b.id = c.to_entity where true")
    params: list = []
    if entity_ids:
        sql += " and c.from_entity = any(%s)"
        params.append(entity_ids)
    if kind:
        sql += " and c.kind = %s"
        params.append(kind)
    sql += " order by (c.props->>'distance_km')::numeric nulls last limit %s"
    params.append(limit)
    cur.execute(sql, params)
    return cur.fetchall()


def near_target(cur, target_term: str, kind: str | None = None, limit: int = 20):
    """Reverse direction: 'which properties are near Kanha?'"""
    sql = ("select a.canonical_name, c.kind, b.canonical_name, "
           "       (c.props->>'distance_km')::numeric, (c.props->>'duration_h')::numeric, "
           "       c.evidence, c.sha1 "
           "from connections c join entities a on a.id = c.from_entity "
           "join entities b on b.id = c.to_entity "
           "where b.canonical_name %% %s")
    params: list = [target_term]
    if kind:
        sql += " and c.kind = %s"
        params.append(kind)
    sql += " order by (c.props->>'distance_km')::numeric nulls last limit %s"
    params.append(limit)
    cur.execute(sql, params)
    return cur.fetchall()


# ---------------------------------------------------------------- semantic
def embed_query(client, text: str) -> list[float]:
    """Here rather than in gather so the whole retrieval surface is one module."""
    from backend.ingest.embed import embed_one
    return embed_one(client, text, "RETRIEVAL_QUERY")


def semantic(cur, vector: list[float], k: int = 10) -> list[tuple[str, str, float]]:
    """HNSW similarity over whole documents. The only route where 'similar' is
    the right question -- and iterative scan is ON so a filtered search cannot
    silently under-return."""
    cur.execute("set local hnsw.iterative_scan = relaxed_order")
    cur.execute(
        "select sha1, rel_path, 1 - (embedding <=> %s::vector) sim "
        "from documents where embedding is not null "
        "order by embedding <=> %s::vector limit %s",
        (str(vector), str(vector), k))
    return [(r[0], r[1], float(r[2])) for r in cur.fetchall()]


# ---------------------------------------------------------------- documents
def documents(cur, sha1s: list[str]) -> list[Doc]:
    if not sha1s:
        return []
    cur.execute(
        "select d.sha1, d.rel_path, d.page_count, d.transcription, "
        "       coalesce(array_agg(distinct e.canonical_name) "
        "         filter (where e.canonical_name is not null), '{}') "
        "from documents d "
        "left join entity_documents ed on ed.sha1 = d.sha1 "
        "left join entities e on e.id = ed.entity_id "
        "where d.sha1 = any(%s) group by d.sha1", (sha1s,))
    return [Doc(*r) for r in cur.fetchall()]


def documents_for_entities(cur, entity_ids: list[int]) -> list[str]:
    if not entity_ids:
        return []
    cur.execute("select distinct sha1 from entity_documents where entity_id = any(%s)",
                (entity_ids,))
    return [r[0] for r in cur.fetchall()]


def corpus_size(cur) -> dict:
    cur.execute("select (select count(*) from documents), (select count(*) from entities), "
                "(select count(*) from fact_evidence)")
    d, e, f = cur.fetchone()
    return {"documents": d, "entities": e, "facts": f}


def demo() -> None:
    with db.connect() as conn, conn.cursor() as cur:
        print("corpus:", corpus_size(cur))

        hits = find_entities(cur, "Ramathra")
        print(f"\nname lookup 'Ramathra' -> {[(h[1], h[2], round(h[3], 2)) for h in hits[:3]]}")
        assert hits, "name lookup found nothing"

        # The count is its own uncapped query. Under the cap the two agree...
        pools = entities_where(cur, [("has_pool", "true", "")])
        n_pools = count_where(cur, [("has_pool", "true", "")])
        print(f"has_pool = true -> count {n_pools}, list {len(pools)}")
        assert n_pools == len(pools), "under the cap count and list must agree"

        # ...and ABOVE it they must not. An unfiltered count reaches the 200-row
        # list cap on 408 entities, which is exactly what used to be reported as
        # the total. If this assert ever fails, the bug is back.
        every = count_where(cur, [])
        capped = entities_where(cur, [])
        print(f"no filter    -> count {every}, list capped at {len(capped)}")
        assert every > len(capped), "the list should be capped below the true count"
        cur.execute("select count(*) from entities")
        assert every == cur.fetchone()[0], "count_where disagrees with a direct count"

        # a filter on a key nothing carries is 0, not an error
        assert count_where(cur, [("no_such_label_at_all", "true", "")]) == 0

        cur.execute("select count(*) from entities where entity_type = 'hotel'")
        hotels = cur.fetchone()[0]
        rec, miss = coverage(cur, ["has_pool"], entity_type="hotel")["has_pool"]
        print(f"has_pool over hotels -> {rec} recorded, {miss} state nothing")
        assert rec + miss == hotels, "coverage must partition the scope"

        confs = conflicting(cur, ["room_count"])
        print(f"conflicting room_count -> {len(confs)}")
        for name, key, vals, mirror in confs[:3]:
            print(f"   {name}: {vals}, filter uses {mirror}")

        small = entities_where(cur, [("room_count", "<=", "12")])
        print(f"room_count <= 12 -> {len(small)}: "
              f"{[r[1] for r in small[:4]]}")

        eid = hits[0][0]
        fs = facts_for(cur, [eid], limit=6)
        print(f"\nfacts for {hits[0][1]}:")
        for f in fs[:5]:
            print(f"   {f.key:<22} {str(f.value)[:34]:<34} [{f.asserted_as}]")
        assert fs, "no facts for a known entity"

        near = nearest(cur, [eid])
        print(f"\nconnections from {hits[0][1]}:")
        for a, kind, b, km, hr, _, _ in near[:4]:
            print(f"   {kind:<18} {b:<34} {km} km  {hr} h")

        rev = near_target(cur, "Kanha")
        print(f"\nproperties linked to 'Kanha' -> {len(rev)}")
        for a, kind, b, km, hr, _, _ in rev[:4]:
            print(f"   {a:<34} {kind:<16} {b:<22} {km} km")

        docs = documents(cur, documents_for_entities(cur, [eid]))
        print(f"\nwhole documents for that entity: {len(docs)}, "
              f"{sum(len(d.transcription) for d in docs)} chars")
        assert docs and docs[0].transcription, "document body missing"
    print("\nretrieve OK")


if __name__ == "__main__":
    demo()
