"""Stage 3 — the API. Real Neon, no Gemini: the answer path is stubbed.

Everything the chat endpoint needs from the model is injected, so every route,
the login, revocation, concurrency and SSE framing are tested for nothing.
"""
import atexit
import sys
import uuid

from fastapi.testclient import TestClient

from tests import runner

from backend import config, db, retry
from backend.api import app as app_mod
from backend.api import auth as auth_mod

PASSWORD = "stage-three-test-password"
_C = []


def _restore_account(email, name, pw_hash):
    """Put the real credential back. Running the suite must not leave the shared
    login set to a password that is written in this file."""
    with db.connect(tries=20) as conn, conn.cursor() as cur:
        cur.execute("update app_account set email=%s, name=%s, password_hash=%s, "
                    "active=true where id=1", (email, name, pw_hash))
        conn.commit()


def client_and_reset():
    """One app, one account, a clean slate of sessions."""
    if not _C:
        def setup():
            with db.connect(tries=20) as conn, conn.cursor() as cur:
                cur.execute("select email, name, password_hash from app_account where id=1")
                before = cur.fetchone()
            if before:
                atexit.register(_restore_account, *before)
            auth_mod.provision("team@travelinn.local", "Travel Inn", PASSWORD)

        retry.call(setup, tries=20, delay=4)
        _C.append(TestClient(app_mod.app, base_url="https://testserver"))
    return _C[0]


def login(c, password=PASSWORD):
    return c.post("/api/auth/login", json={"password": password})


def fake_converse(*a, **k):
    yield ("mode", {"mode": "fast", "why": "stub", "est_seconds": 1, "max_rounds": 1})
    yield ("step", {"round": 1, "found": 2, "opened": 1, "count": None, "chars": 10})
    yield ("token", "Bagh Tola ")
    yield ("token", "has 10 units [1].")
    yield ("sources", {"sources": [{"sha1": "abc123", "rel_path": "Bagh Tola.pdf", "page": 1}]})
    yield ("done", {"mode": "fast", "model": "stub", "rounds": 1, "truncated": False,
                    "found": 2, "count": None, "cost_inr": 0.0, "seconds": 0.1})


def stub(fn=fake_converse):
    app_mod.converse = fn


def new_thread(c):
    stub()
    r = c.post("/api/chat/sessions", json={"title": "test"})
    assert r.status_code == 200, r.text
    return r.json()["id"]


def drop(cid):
    with db.connect(tries=20) as conn, conn.cursor() as cur:
        cur.execute("delete from conversation where id = %s", (cid,))
        conn.commit()


# ---------------------------------------------------------------- auth
def test_health_needs_no_login():
    assert client_and_reset().get("/api/health").status_code == 200


def test_a_protected_route_without_a_cookie_is_401():
    c = TestClient(app_mod.app, base_url="https://testserver")
    assert c.get("/api/auth/me").status_code == 401


def test_login_with_the_wrong_password_is_401_and_sets_nothing():
    c = TestClient(app_mod.app, base_url="https://testserver")
    r = login(c, "not the password")
    assert r.status_code == 401
    assert auth_mod.COOKIE not in r.cookies


def test_login_then_me_returns_the_shared_account():
    c = client_and_reset()
    assert login(c).status_code == 200
    me = c.get("/api/auth/me")
    assert me.status_code == 200 and me.json()["email"] == "team@travelinn.local"


def test_two_browsers_share_one_account():
    a, b = TestClient(app_mod.app, base_url="https://testserver"), TestClient(app_mod.app, base_url="https://testserver")
    assert login(a).status_code == 200 and login(b).status_code == 200
    assert a.get("/api/auth/me").status_code == 200
    assert b.get("/api/auth/me").status_code == 200


def test_logout_really_revokes_that_cookie():
    """A stateless signed cookie could not do this. The session row can."""
    a = TestClient(app_mod.app, base_url="https://testserver")
    login(a)
    token = a.cookies.get(auth_mod.COOKIE)
    assert a.post("/api/auth/logout").status_code == 200

    replay = TestClient(app_mod.app, base_url="https://testserver")
    replay.cookies.set(auth_mod.COOKIE, token)
    assert replay.get("/api/auth/me").status_code == 401, "a copied cookie still worked"


def test_logging_out_of_one_browser_leaves_the_other_signed_in():
    a, b = TestClient(app_mod.app, base_url="https://testserver"), TestClient(app_mod.app, base_url="https://testserver")
    login(a)
    login(b)
    a.post("/api/auth/logout")
    assert a.get("/api/auth/me").status_code == 401
    assert b.get("/api/auth/me").status_code == 200, "one account, but separate sessions"


def test_an_expired_session_is_rejected():
    a = TestClient(app_mod.app, base_url="https://testserver")
    login(a)
    sid = a.cookies.get(auth_mod.COOKIE)
    with db.connect(tries=20) as conn, conn.cursor() as cur:
        cur.execute("update login_session set expires_at = now() - interval '1 hour' "
                    "where id = %s", (uuid.UUID(sid),))
        conn.commit()
    assert a.get("/api/auth/me").status_code == 401


def test_repeated_wrong_passwords_are_throttled():
    auth_mod.FAILURES.clear()
    c = TestClient(app_mod.app, base_url="https://testserver")
    codes = [login(c, "wrong").status_code for _ in range(auth_mod.MAX_FAILURES + 2)]
    assert 429 in codes, f"no throttling: {codes}"
    auth_mod.FAILURES.clear()


def test_an_inactive_account_cannot_log_in():
    c = TestClient(app_mod.app, base_url="https://testserver")
    with db.connect(tries=20) as conn, conn.cursor() as cur:
        cur.execute("update app_account set active = false where id = 1")
        conn.commit()
    try:
        assert login(c).status_code == 401
    finally:
        with db.connect(tries=20) as conn, conn.cursor() as cur:
            cur.execute("update app_account set active = true where id = 1")
            conn.commit()


def test_saved_answers_and_feedback_round_trip():
    c = client_and_reset()
    login(c)
    answer_id = "test-save:1"
    try:
        saved = c.put(f"/api/saved-answers/{answer_id}", json={
            "id": answer_id, "text": "A grounded answer", "session_id": None,
        })
        assert saved.status_code == 200, saved.text
        got = c.get("/api/saved-answers")
        assert got.status_code == 200 and got.json()["answers"][0]["id"] == answer_id
        feedback = c.post("/api/answer-feedback", json={"answer_id": answer_id, "kind": "helpful"})
        assert feedback.status_code == 200, feedback.text
    finally:
        c.delete(f"/api/saved-answers/{answer_id}")
        c.delete(f"/api/answer-feedback/{answer_id}")


# ---------------------------------------------------------------- chat
def test_ask_streams_events_in_order_and_ends_with_done():
    c = client_and_reset()
    login(c)
    cid = new_thread(c)
    try:
        with c.stream("POST", f"/api/chat/sessions/{cid}/ask",
                      json={"question": "Tell me about Bagh Tola"}) as r:
            assert r.status_code == 200
            kinds = [l[7:] for l in r.iter_lines() if l.startswith("event: ")]
        assert kinds[0] == "mode" and kinds[-1] == "done"
        assert "token" in kinds and "sources" in kinds
    finally:
        drop(cid)


def test_both_turns_are_saved_and_survive_a_reload():
    c = client_and_reset()
    login(c)
    cid = new_thread(c)
    try:
        with c.stream("POST", f"/api/chat/sessions/{cid}/ask",
                      json={"question": "Tell me about Bagh Tola"}) as r:
            list(r.iter_lines())
        got = c.get(f"/api/chat/sessions/{cid}").json()
        assert [t["role"] for t in got["turns"]] == ["user", "assistant"]
        assert got["turns"][1]["status"] == "complete"
        assert "Bagh Tola" in got["turns"][1]["text"]
        assert got["turns"][1]["sources"], "citations must survive the reload"
    finally:
        drop(cid)


def test_an_interrupted_answer_is_saved_as_interrupted():
    def blows_up(*a, **k):
        yield ("mode", {"mode": "fast", "why": "", "est_seconds": 1, "max_rounds": 1})
        yield ("token", "half an ans")
        raise RuntimeError("connection reset")

    c = client_and_reset()
    login(c)
    cid = new_thread(c)
    try:
        stub(blows_up)
        with c.stream("POST", f"/api/chat/sessions/{cid}/ask",
                      json={"question": "q"}) as r:
            list(r.iter_lines())
        turns = c.get(f"/api/chat/sessions/{cid}").json()["turns"]
        assert turns[1]["status"] == "interrupted", turns[1]
        assert turns[1]["text"].startswith("half an ans"), "keep what was written"
    finally:
        stub()
        drop(cid)


def test_a_second_thread_does_not_inherit_the_first_ones_context():
    c = client_and_reset()
    login(c)
    a, b = new_thread(c), new_thread(c)
    try:
        with c.stream("POST", f"/api/chat/sessions/{a}/ask", json={"question": "q"}) as r:
            list(r.iter_lines())
        assert c.get(f"/api/chat/sessions/{a}").json()["working_set"]
        assert c.get(f"/api/chat/sessions/{b}").json()["working_set"] == []
    finally:
        drop(a)
        drop(b)


def test_concurrent_asks_do_not_lose_a_document_from_the_working_set():
    """The unique(conversation, seq) constraint does not protect a JSONB column
    that is read, merged and written back. A row lock does."""
    c = client_and_reset()
    login(c)
    cid = new_thread(c)
    try:
        for sha in ("doc-A", "doc-B"):
            def one(*a, _s=sha, **k):
                yield ("mode", {"mode": "fast", "why": "", "est_seconds": 1, "max_rounds": 1})
                yield ("token", "x")
                yield ("sources", {"sources": [{"sha1": _s, "rel_path": f"{_s}.pdf",
                                                "page": None}]})
                yield ("done", {"mode": "fast", "model": "s", "rounds": 1,
                                "truncated": False, "found": 1, "count": None,
                                "cost_inr": 0.0, "seconds": 0.1})
            stub(one)
            with c.stream("POST", f"/api/chat/sessions/{cid}/ask",
                          json={"question": "q"}) as r:
                list(r.iter_lines())
        held = {w["sha1"] for w in c.get(f"/api/chat/sessions/{cid}").json()["working_set"]}
        assert held == {"doc-A", "doc-B"}, f"union, not replacement: {held}"
    finally:
        stub()
        drop(cid)


def test_conversations_are_shared_between_browsers():
    a, b = TestClient(app_mod.app, base_url="https://testserver"), TestClient(app_mod.app, base_url="https://testserver")
    login(a)
    login(b)
    stub()
    cid = a.post("/api/chat/sessions", json={"title": "shared"}).json()["id"]
    try:
        assert any(s["id"] == cid for s in b.get("/api/chat/sessions").json()["sessions"])
    finally:
        drop(cid)


def test_asking_in_a_missing_conversation_is_404():
    c = client_and_reset()
    login(c)
    with c.stream("POST", "/api/chat/sessions/99999999/ask", json={"question": "q"}) as r:
        assert r.status_code == 404


# ---------------------------------------------------------------- properties
def test_properties_filter_and_count_agree():
    c = client_and_reset()
    login(c)
    r = c.get("/api/properties", params={"has_pool": "true", "entity_type": "hotel"}).json()
    assert r["count"] == 31, r["count"]
    assert len(r["properties"]) == 31


def test_a_property_returns_its_facts_with_evidence():
    c = client_and_reset()
    login(c)
    pid = c.get("/api/properties", params={"q": "Bagh Tola"}).json()["properties"][0]["id"]
    facts = c.get(f"/api/properties/{pid}/facts").json()["facts"]
    assert facts and all("evidence" in f for f in facts)


def test_property_connections_mark_missing_distances_rather_than_hiding_them():
    c = client_and_reset()
    login(c)
    pid = c.get("/api/properties", params={"q": "Courtyard House Kanha"}
                ).json()["properties"][0]["id"]
    edges = c.get(f"/api/properties/{pid}/connections").json()["connections"]
    assert edges
    assert any(e["distance_km"] is None for e in edges), "null, not omitted"


# ---------------------------------------------------------------- sources
def test_an_unknown_document_is_404():
    c = client_and_reset()
    login(c)
    assert c.get("/api/sources/" + "0" * 40).status_code == 404


def test_a_known_document_reports_its_pages():
    c = client_and_reset()
    login(c)
    with db.connect(tries=20) as conn, conn.cursor() as cur:
        cur.execute("select sha1 from documents limit 1")
        sha = cur.fetchone()[0]
    got = c.get(f"/api/sources/{sha}").json()
    assert got["sha1"] == sha and got["page_count"] >= 1


def test_the_chat_endpoint_passes_a_real_gemini_client():
    """The stub hid this: the endpoint passed None, and gather() silently skips
    semantic search without a client, so every API answer lost its safety net."""
    seen = {}

    def capture(cur, question, vocab, client, **k):
        seen["client"] = client
        yield from fake_converse()

    c = client_and_reset()
    login(c)
    cid = new_thread(c)
    try:
        stub(capture)
        with c.stream("POST", f"/api/chat/sessions/{cid}/ask", json={"question": "q"}) as r:
            list(r.iter_lines())
        assert seen.get("client") is not None, "gather() would skip semantic search"
        assert hasattr(seen["client"], "models"), seen["client"]
    finally:
        stub()
        drop(cid)


def test_a_disconnected_browser_still_has_its_turn_saved():
    """The save ran only when the generator finished normally. A real browser
    disconnect closes it early, and the whole exchange was lost from history."""
    def slow(*a, **k):
        yield ("mode", {"mode": "fast", "why": "", "est_seconds": 1, "max_rounds": 1})
        yield ("token", "half an answer")
        yield ("token", " and more")
        yield ("done", {"mode": "fast", "model": "s", "rounds": 1, "truncated": False,
                        "found": 1, "count": None, "cost_inr": 0.0, "seconds": 0.1})

    import asyncio

    c = client_and_reset()
    login(c)
    cid = new_thread(c)

    async def take_one_then_leave():
        body = app_mod.ask(cid, app_mod.Ask(question="q"),
                           account={"email": "x"}).body_iterator
        await body.__anext__()          # one event reaches the browser
        await body.aclose()             # ...and then it goes away

    try:
        stub(slow)
        asyncio.run(take_one_then_leave())
        turns = c.get(f"/api/chat/sessions/{cid}").json()["turns"]
        assert len(turns) == 2, f"the turn was lost on disconnect: {turns}"
        assert turns[1]["status"] == "interrupted", turns[1]["status"]
        assert turns[0]["text"] == "q", "the question must survive too"
    finally:
        stub()
        drop(cid)


def test_cross_origin_requests_are_allowed():
    """A frontend on another port is blocked by the browser without this."""
    c = client_and_reset()
    r = c.options("/api/health", headers={"Origin": "http://localhost:5173",
                                          "Access-Control-Request-Method": "GET"})
    assert r.headers.get("access-control-allow-origin"), r.headers
    assert r.headers.get("access-control-allow-credentials") == "true", \
        "the login cookie needs credentialed CORS"


# ---------------------------------------------------------------- crops
def _a_fact_with_a_box():
    with db.connect(tries=20) as conn, conn.cursor() as cur:
        cur.execute("select id, sha1, page, bbox from fact_evidence "
                    "where bbox is not null order by id limit 1")
        return cur.fetchone()


def test_a_crop_is_cut_from_the_original_not_the_page_tile():
    """The regression guard for a real bug: bbox is in ORIGINAL coordinates while
    page is a tile index. 27 of 40 sampled boxes do not fit their tile, so a crop
    taken from the tile lands on the wrong line or off the image."""
    from PIL import Image
    from backend import config, storage
    from backend.api import crops
    fid, sha, _page, bbox = _a_fact_with_a_box()
    with db.connect(tries=20) as conn, conn.cursor() as cur:
        key = crops.make(cur, fid, force=True)
    blob = storage.client().get_object(Bucket=config.R2_BUCKET, Key=key)["Body"].read()
    w, h = Image.open(__import__("io").BytesIO(blob)).size
    want_w = bbox[2] - bbox[0] + 2 * crops.PAD
    want_h = bbox[3] - bbox[1] + 2 * crops.PAD
    assert abs(w - want_w) <= 2 * crops.PAD + 2, f"width {w} vs box {want_w}"
    assert abs(h - want_h) <= 2 * crops.PAD + 2, f"height {h} vs box {want_h}"


def test_the_crop_endpoint_returns_a_signed_url():
    c = client_and_reset()
    login(c)
    fid, sha, page, _ = _a_fact_with_a_box()
    r = c.get(f"/api/sources/{sha}/page/{page}/crop", params={"fact": fid})
    assert r.status_code == 200, r.text
    assert r.json()["url"].startswith("https://")


def test_a_fact_from_another_document_is_refused():
    c = client_and_reset()
    login(c)
    fid, sha, page, _ = _a_fact_with_a_box()
    with db.connect(tries=20) as conn, conn.cursor() as cur:
        cur.execute("select sha1 from documents where sha1 <> %s limit 1", (sha,))
        other = cur.fetchone()[0]
    r = c.get(f"/api/sources/{other}/page/1/crop", params={"fact": fid})
    assert r.status_code == 404, "a fact must not be croppable out of a foreign document"


def test_a_fact_without_a_box_cannot_be_cropped():
    from backend.api import crops
    with db.connect(tries=20) as conn, conn.cursor() as cur:
        cur.execute("select id from fact_evidence where bbox is null limit 1")
        row = cur.fetchone()
        if not row:
            return
        try:
            crops.make(cur, row[0])
        except crops.NoEvidence as e:
            assert "bounding box" in str(e)
        else:
            raise AssertionError("cropped a fact that has no box")


def test_a_whitespace_only_question_never_reaches_the_model():
    """A chat box sends "   " when someone hits enter on an empty line. Three
    spaces passed min_length=1 and bought a full planner call to answer nothing."""
    c = client_and_reset()
    login(c)
    cid = c.post("/api/chat/sessions", json={"title": "blank"}).json()["id"]
    for blank in ("   ", "\n", "\t \n "):
        r = c.post(f"/api/chat/sessions/{cid}/ask", json={"question": blank})
        assert r.status_code == 422, f"{blank!r} was accepted: HTTP {r.status_code}"
    drop(cid)


def test_the_login_cookie_carries_the_configured_samesite():
    """SameSite=strict drops the cookie when the frontend is on another domain:
    the login succeeds and every later call is 401. The policy is configuration,
    not a constant, so a cross-domain deployment can set none."""
    c = client_and_reset()
    header = login(c).headers.get("set-cookie", "")
    assert f"SameSite={config.COOKIE_SAMESITE}".lower() in header.lower(), header
    assert "HttpOnly" in header, "the session cookie must be unreadable from JS"


def test_samesite_none_without_secure_is_refused():
    """Browsers drop that combination silently. Fail at startup instead."""
    import importlib
    import os
    keep = os.environ.get("COOKIE_SAMESITE"), os.environ.get("COOKIE_SECURE")
    os.environ["COOKIE_SAMESITE"], os.environ["COOKIE_SECURE"] = "none", "0"
    try:
        importlib.reload(config)
    except SystemExit as e:
        assert "COOKIE_SECURE" in str(e)
    else:
        raise AssertionError("an unusable cookie policy was accepted")
    finally:
        for name, was in zip(("COOKIE_SAMESITE", "COOKIE_SECURE"), keep):
            os.environ.pop(name, None) if was is None else os.environ.__setitem__(name, was)
        importlib.reload(config)


if __name__ == "__main__":
    runner.main(sys.modules[__name__])
