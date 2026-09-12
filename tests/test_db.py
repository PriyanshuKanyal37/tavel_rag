"""Stage 1.3 and the SQL behind 1.1. Read-only against Neon. No model calls.

Neon's host resolves intermittently from here, so every connection is retried
in-process; relaunching the interpreter does not help.
"""
import sys

from tests import runner

from backend import db, retry
from backend.query import retrieve

_CUR, _KEEP = [], []


def _open():
    cm = db.connect()                # held in _KEEP: if it is collected, psycopg
    conn = cm.__enter__()            # closes the connection under us
    _KEEP.append(cm)
    return conn


def cur():
    if not _CUR:
        _CUR.append(retry.call(_open, tries=40, delay=4).cursor())
    return _CUR[0]


def _direct(sql, params=None):
    cur().execute(sql, params)
    return cur().fetchone()[0]


# ------------------------------------------------------------------ 1.1 count
def test_count_is_uncapped_where_the_list_is_capped():
    total = retrieve.count_where(cur(), [])
    assert total == _direct("select count(*) from entities")
    # an explicit small cap, so this holds whatever the default limit becomes
    assert len(retrieve.entities_where(cur(), [], limit=50)) == 50 < total


def test_the_default_list_limit_covers_the_whole_corpus():
    """It was 200 against 408 entities, so a broad filter showed half the names
    while quoting a correct total. That was a cost cap, not a design."""
    total = retrieve.count_where(cur(), [])
    assert len(retrieve.entities_where(cur(), [])) == total


def test_count_of_an_unknown_label_is_zero_not_an_error():
    assert retrieve.count_where(cur(), [("no_such_label", "true", "")]) == 0


def test_coverage_partitions_the_scope_exactly():
    hotels = _direct("select count(*) from entities where entity_type = 'hotel'")
    rec, miss = retrieve.coverage(cur(), ["has_pool"], entity_type="hotel")["has_pool"]
    assert rec + miss == hotels
    assert miss > 0, "the honest denominator is the whole point"


def test_conflicting_finds_the_double_room_count():
    rows = retrieve.conflicting(cur(), ["room_count"])
    names = {r[0] for r in rows}
    assert "Oberoi Rajgarh Palace" in names, names
    vals = next(set(r[2]) for r in rows if r[0] == "Oberoi Rajgarh Palace")
    assert vals == {"65 rooms", "66 rooms"}, vals


# ------------------------------------------------------------------ 1.3 scope
def test_city_returns_only_that_city():
    rows = retrieve.entities_where(cur(), [], city="Bhopal")
    assert rows, "expected Bhopal properties"
    for r in rows:
        assert _direct("select lower(city) from entities where id = %s", (r[0],)) == "bhopal"
    assert retrieve.count_where(cur(), [], city="Bhopal") == len(rows)


def test_city_narrows_below_its_state():
    city = retrieve.count_where(cur(), [], city="Jaipur", entity_type="hotel")
    state = retrieve.count_where(cur(), [], state="Rajasthan", entity_type="hotel")
    assert 0 < city < state, f"Jaipur {city} should be inside Rajasthan {state}"


def test_city_with_no_properties_is_empty_not_an_error():
    assert retrieve.count_where(cur(), [], city="Reykjavik") == 0
    assert retrieve.entities_where(cur(), [], city="Reykjavik") == []


def test_near_joins_the_graph_and_finds_the_kanha_properties():
    rows = retrieve.entities_where(cur(), [], near="Kanha", entity_type="hotel")
    names = {r[1] for r in rows}
    assert {"Courtyard House Kanha", "The Safari Lodge Kanha", "Outpost 12"} <= names, names


def test_near_composes_with_a_condition():
    everything = retrieve.count_where(cur(), [], near="Kanha", entity_type="hotel")
    pooled = retrieve.count_where(cur(), [("has_pool", "true", "")],
                                  near="Kanha", entity_type="hotel")
    assert pooled <= everything
    assert pooled == len(retrieve.entities_where(
        cur(), [("has_pool", "true", "")], near="Kanha", entity_type="hotel"))


def test_near_something_unconnected_is_empty_not_an_error():
    assert retrieve.count_where(cur(), [], near="Atlantis") == 0


def test_kanha_edges_carry_durations_but_no_distances():
    """Guards the Stage 1.3 expectation that was corrected: the plan promised
    distances here and the data has none."""
    rows = retrieve.near_target(cur(), "Kanha")
    assert len(rows) == 3, rows
    assert all(r[3] is None for r in rows), "no distance is recorded on any Kanha edge"
    assert sum(r[4] is not None for r in rows) == 2, "exactly two carry a duration"


def test_no_property_to_property_edges_exist():
    n = _direct("select count(*) from connections c "
                "join entities a on a.id = c.from_entity "
                "join entities b on b.id = c.to_entity "
                "where a.entity_type = 'hotel' and b.entity_type = 'hotel'")
    assert n == 0, f"a lodge-to-lodge transfer time would change §5.4; found {n}"


# ------------------------------------------------------------------ 4 calendar
def test_calendar_lookup_matches_by_name_and_year():
    from backend.query import calendar as cal
    c = cur()
    c.execute("insert into calendar_event (kind, name, starts_on, source_url, verified_on) "
              "values ('festival','__TEST Holi','2026-03-03','https://example.test','2026-01-01') "
              "on conflict do nothing")
    c.connection.commit()
    try:
        rows = cal.from_table(c, ["__TEST Holi"])
        assert len(rows) == 1 and rows[0]["source_url"] == "https://example.test"
        assert cal.from_table(c, ["__TEST Holi"], year=2026)
        assert cal.from_table(c, ["__TEST Holi"], year=2031) == []
        assert cal.from_table(c, []) == [], "no terms means no query"
    finally:
        c.execute("delete from calendar_event where name = '__TEST Holi'")
        c.connection.commit()


def test_calendar_block_marks_a_web_result_as_not_ours():
    from backend.query import calendar as cal
    b = cal.block([], {"text": "3 March 2026", "urls": ["https://x.test"]})
    assert "(web)" in b and "NOT from our documents" in b
    assert cal.block([], None) == ""


# ------------------------------------------------------------------ reloading
def _synthetic_doc():
    """A real extraction file under a throwaway sha1, so nothing live is touched."""
    import json
    import pathlib
    from backend import config
    src = sorted((config.WORK / "out").glob("*.json"))[0]
    d = json.loads(src.read_text(encoding="utf-8"))
    d["sha1"] = "0" * 39 + "1"
    d["rel"] = "TEST/reload-check.pdf"
    return d


def _counts(c, sha):
    c.execute("select (select count(*) from fact_evidence where sha1=%s), "
              "(select count(*) from connections where sha1=%s)", (sha, sha))
    return c.fetchone()


def _wipe(c, sha):
    for t in ("fact_evidence", "connections", "review_queue", "entity_documents"):
        c.execute(f"delete from {t} where sha1 = %s", (sha,))
    c.execute("delete from documents where sha1 = %s", (sha,))
    c.connection.commit()


def test_reloading_a_document_replaces_it_instead_of_doubling_it():
    """--redo exists because approving a label does nothing until the documents
    are read again, and without it load skips everything already loaded."""
    import collections
    from backend.ingest import load as load_mod
    from backend.ingest import vocab as vocab_mod
    c, d = cur(), _synthetic_doc()
    sha = d["sha1"]
    _wipe(c, sha)
    try:
        v = vocab_mod.load(c)
        st, rs = collections.Counter(), collections.Counter()
        load_mod.load_file(c, d, st, rs, v)
        c.connection.commit()
        first = _counts(c, sha)
        assert first[0] > 0, "nothing loaded; the fixture is wrong"

        load_mod.load_file(c, d, st, rs, v)          # no redo: must skip
        c.connection.commit()
        assert _counts(c, sha) == first, "a plain reload changed the data"
        assert st["duplicate_document_skipped"] >= 1

        load_mod.load_file(c, d, st, rs, v, redo=True)
        c.connection.commit()
        assert _counts(c, sha) == first, \
            f"redo doubled the document: {first} -> {_counts(c, sha)}"
    finally:
        _wipe(c, sha)


def test_a_multi_valued_label_is_filterable_through_the_mirror():
    """entities.facts kept only the LAST value per key, so nine evidence rows
    across seven properties mentioning boating matched nothing at all."""
    c = cur()
    c.execute("""select count(distinct entity_id) from fact_evidence
                 where key = 'activities' and lower(value_text) like '%boat%'""")
    in_evidence = c.fetchone()[0]
    assert in_evidence >= 5, "fixture changed; pick another multi-valued label"
    found = retrieve.count_where(c, [("activities", "contains", "boat")])
    assert found == in_evidence, f"filter found {found}, evidence has {in_evidence}"


def test_a_scalar_label_is_still_stored_as_one_value():
    c = cur()
    c.execute("""select facts->'has_pool' from entities
                 where facts ? 'has_pool' limit 1""")
    val = c.fetchone()[0]
    assert not isinstance(val, list), f"has_pool became an array: {val}"


def test_no_two_hotels_should_ever_be_auto_merged_on_name_similarity():
    """A guard against a tempting feature that would destroy data.

    The 26 similar hotel pairs are all THE POSTCARD chain -- Cuelim, Saligao,
    Velha, Leh, Jawai, Chitwan -- distinct properties in Goa, Ladakh, Rajasthan
    and Nepal sharing a brand. A brand prefix inflates trigram similarity, so any
    name-based auto-merge fuses real properties. Airports are worse: "Dabolim"
    and "Dabolin" differ by one letter and are the same place, while "Raipur" and
    "Jaipur" differ by one letter and are 800 km apart. No string rule tells
    those apart, so we do not merge automatically at all.
    """
    c = cur()
    c.execute("""select a.canonical_name, b.canonical_name,
                        round(similarity(a.canonical_name, b.canonical_name)::numeric, 2)
                 from entities a join entities b on a.id < b.id
                 where a.entity_type = 'hotel' and b.entity_type = 'hotel'
                   and similarity(a.canonical_name, b.canonical_name) > 0.45
                   and coalesce(a.state,'') = coalesce(b.state,'')""")
    same_state = c.fetchall()
    for an, bn, sim in same_state:
        assert an != bn
        assert sim < 0.80, f"{an} vs {bn} at {sim} would merge on load — check it"


if __name__ == "__main__":
    runner.main(sys.modules[__name__])
