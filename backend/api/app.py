"""The HTTP surface. Everything except /health and /auth/login needs a cookie.

The chat endpoint streams Server-Sent Events because an AGENT answer may not
produce its first word for fifteen seconds; the mode and step events carry the
feedback until then.
"""
import contextlib
import json
import re
import sys
import time
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, StringConstraints

from backend import config, db, storage
from backend.api import auth, crops, throttle
from backend.ingest import vocab as vocab_mod
from backend.query import (answer as answer_mod, history as history_mod, retrieve,
                           title as title_mod)
from backend.query.answer import converse          # patched in tests

@contextlib.asynccontextmanager
async def lifespan(_app: FastAPI):
    """Hand the pool back on the way out.

    Without this every `--reload` restart abandons its Neon connections and
    leaves them open until the server times them out, so an afternoon of editing
    slowly eats the connection limit.
    """
    yield
    db.close_pool()


app = FastAPI(title="Travel Inn RAG", docs_url="/api/docs", lifespan=lifespan)

# allow_credentials is the point: the login cookie does not travel without it,
# and a wildcard origin is not permitted alongside credentials.
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
ACCOUNT = Depends(auth.account_dep)

# Every model call this service makes happens inside /ask, so one gate on that
# endpoint is the whole budget guard. Two windows: one so a single caller cannot
# monopolise the service, one so the whole team together cannot empty the
# month's credit in an afternoon.
ASK_PER_CALLER = throttle.Window(throttle.ASK_PER_MIN)
ASK_OVERALL = throttle.Window(throttle.ASK_PER_MIN_ALL)

_VOCAB = []


_CLIENT = []


def vocabulary():
    if not _VOCAB:
        _VOCAB.append(vocab_mod.load())
    return _VOCAB[0]


def gemini():
    """Built once, lazily, so importing the app needs no API key.

    Passing None here would not fail loudly -- gather() skips semantic search
    when it has no client, so every answer would quietly lose its safety net.
    """
    if not _CLIENT:
        _CLIENT.append(answer_mod.client_for())
    return _CLIENT[0]


class Login(BaseModel):
    password: str


class NewSession(BaseModel):
    title: str | None = None


class Ask(BaseModel):
    # An empty question spends a model call to answer nothing, and a novel-length
    # one spends a lot more. Both were accepted.
    #
    # strip_whitespace comes FIRST, then min_length. Without it "   " is three
    # characters long, passes min_length=1, and reaches the planner -- which is
    # what a chat box sends when someone hits enter on an empty line.
    question: Annotated[str, StringConstraints(
        strip_whitespace=True, min_length=1, max_length=4000)]


class SavedAnswer(BaseModel):
    id: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)]
    text: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=20000)]
    session_id: int | None = None


REASONS = "wrong_fact|missing|wrong_source|outdated|other"


class Feedback(BaseModel):
    answer_id: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)]
    kind: Annotated[str, StringConstraints(strip_whitespace=True, pattern="^(helpful|correction)$")]
    # A correction is only worth storing if it says what was wrong.
    reason: Annotated[str, StringConstraints(strip_whitespace=True, pattern=f"^({REASONS})$")] | None = None
    note: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)] | None = None


# ---------------------------------------------------------------- health
@app.get("/api/health")
def health():
    return {"ok": True}


@app.get("/api/health/deep")
def health_deep(account=ACCOUNT):
    out = {"neon": False, "r2": False, "gemini_key": bool(config.GEMINI_KEY)}
    try:
        out |= {"neon": True, **db.stats()}
    except Exception as e:
        out["neon_error"] = str(e)[:200]
    try:
        storage.client().head_bucket(Bucket=config.R2_BUCKET)
        out["r2"] = True
    except Exception as e:
        out["r2_error"] = str(e)[:200]
    return out


# ---------------------------------------------------------------- auth
@app.post("/api/auth/login")
def login(body: Login, request: Request, response: Response):
    who = request.client.host if request.client else "?"
    token = auth.sign_in(body.password, who, request.headers.get("user-agent", ""))
    response.set_cookie(auth.COOKIE, token, httponly=True, secure=config.COOKIE_SECURE,
                        samesite=config.COOKIE_SAMESITE,
                        max_age=auth.SESSION_HOURS * 3600)
    return {"ok": True}


@app.post("/api/auth/logout")
def logout(request: Request, response: Response, account=ACCOUNT):
    auth.revoke(request.cookies.get(auth.COOKIE))
    response.delete_cookie(auth.COOKIE)
    return {"ok": True}


@app.get("/api/auth/me")
def me(account=ACCOUNT):
    return account


# ---------------------------------------------------------------- answer workspace
@app.get("/api/saved-answers")
def saved_answers(account=ACCOUNT):
    with db.connect() as conn, conn.cursor() as cur:
        cur.execute("select answer_id, text, session_id, created_at from saved_answer order by created_at desc")
        rows = cur.fetchall()
    return {"answers": [{"id": r[0], "text": r[1], "session_id": r[2], "saved_at": r[3]} for r in rows]}


@app.put("/api/saved-answers/{answer_id}")
def save_answer(answer_id: str, body: SavedAnswer, account=ACCOUNT):
    if answer_id != body.id:
        raise HTTPException(400, "answer id does not match the path")
    with db.connect() as conn, conn.cursor() as cur:
        cur.execute("""insert into saved_answer (answer_id, text, session_id)
                      values (%s, %s, %s)
                      on conflict (answer_id) do update set text=excluded.text,
                      session_id=excluded.session_id""", (body.id, body.text, body.session_id))
        conn.commit()
    return {"ok": True}


@app.delete("/api/saved-answers/{answer_id}")
def unsave_answer(answer_id: str, account=ACCOUNT):
    with db.connect() as conn, conn.cursor() as cur:
        cur.execute("delete from saved_answer where answer_id = %s", (answer_id,))
        conn.commit()
    return {"ok": True}


@app.post("/api/answer-feedback")
def answer_feedback(body: Feedback, account=ACCOUNT):
    with db.connect() as conn, conn.cursor() as cur:
        cur.execute("""insert into answer_feedback (answer_id, kind, reason, note)
                      values (%s, %s, %s, %s)
                      on conflict (answer_id) do update set kind=excluded.kind,
                      reason=excluded.reason, note=excluded.note,
                      created_at=now()""",
                    (body.answer_id, body.kind, body.reason, body.note))
        conn.commit()
    return {"ok": True}


@app.get("/api/answer-feedback")
def list_answer_feedback(account=ACCOUNT):
    with db.connect() as conn, conn.cursor() as cur:
        cur.execute("select answer_id, kind, reason, note, created_at "
                    "from answer_feedback order by created_at desc limit 500")
        rows = cur.fetchall()
    return {"feedback": [{"answer_id": r[0], "kind": r[1], "reason": r[2],
                          "note": r[3], "created_at": r[4]} for r in rows]}


@app.delete("/api/answer-feedback/{answer_id}")
def clear_answer_feedback(answer_id: str, account=ACCOUNT):
    with db.connect() as conn, conn.cursor() as cur:
        cur.execute("delete from answer_feedback where answer_id = %s", (answer_id,))
        conn.commit()
    return {"ok": True}


@app.get("/api/saved-sources")
def saved_sources(account=ACCOUNT):
    with db.connect() as conn, conn.cursor() as cur:
        cur.execute("select sha1, created_at from saved_source order by created_at desc")
        rows = cur.fetchall()
    return {"sources": [{"sha1": r[0], "saved_at": r[1]} for r in rows]}


@app.put("/api/saved-sources/{sha1}")
def save_source(sha1: str, account=ACCOUNT):
    with db.connect() as conn, conn.cursor() as cur:
        _document(cur, sha1)
        cur.execute("insert into saved_source (sha1) values (%s) on conflict (sha1) do nothing", (sha1,))
        conn.commit()
    return {"ok": True}


@app.delete("/api/saved-sources/{sha1}")
def unsave_source(sha1: str, account=ACCOUNT):
    with db.connect() as conn, conn.cursor() as cur:
        cur.execute("delete from saved_source where sha1 = %s", (sha1,))
        conn.commit()
    return {"ok": True}


# ---------------------------------------------------------------- chat
@app.post("/api/chat/sessions")
def create_session(body: NewSession, account=ACCOUNT):
    with db.connect() as conn, conn.cursor() as cur:
        # last_active too: the sidebar groups by it, and a row described without
        # one was filed under "Earlier" while its own label read "Just now".
        cur.execute("insert into conversation (title) values (%s) "
                    "returning id, created_at, last_active", (body.title,))
        cid, created, active = cur.fetchone()
        conn.commit()
    return {"id": cid, "title": body.title, "created_at": created,
            "last_active": active}


@app.get("/api/chat/sessions")
def list_sessions(account=ACCOUNT):
    with db.connect() as conn, conn.cursor() as cur:
        cur.execute("select id, title, last_active, tokens_est from conversation "
                    "order by last_active desc limit 200")
        rows = cur.fetchall()
    return {"sessions": [{"id": r[0], "title": r[1], "last_active": r[2],
                          "tokens_est": r[3]} for r in rows]}


# Searching titles alone can only find a thread whose name you already
# remember. This reads the messages: ask for "pool" and it finds the answer that
# listed the properties with one, even in a thread called "hi".
WORD = re.compile(r"[^\W_]+", re.UNICODE)


@app.get("/api/chat/search")
def search_sessions(q: str = "", account=ACCOUNT):
    terms = WORD.findall(q or "")[:8]
    if not terms:
        return {"results": []}
    # Prefix on every word so the list narrows as the reader types: "poo"
    # has to find "pool" before they finish spelling it. Built from word
    # characters only, so there is no tsquery syntax to escape.
    tsq = " & ".join(f"{t.lower()}:*" for t in terms)
    like = f"%{q.strip()}%"
    with db.connect() as conn, conn.cursor() as cur:
        cur.execute(
            # One query object built from both configs, so a word matched under
            # either one still gets highlighted in the snippet.
            "with q as (select to_tsquery('english', %(tsq)s) || to_tsquery('simple', %(tsq)s) as tq) "
            "select c.id, c.title, c.last_active, (c.title ilike %(like)s) as on_title, "
            # ts_headline tokenises with ONE config, so the config that did not
            # make the match marks nothing and hands back a plain opening
            # sentence. Take whichever of the two actually marked something.
            "       case when m.simple_hl like %(marked)s then m.simple_hl "
            "            else m.english_hl end as snippet, m.role "
            "  from conversation c, q "
            "  left join lateral ( "
            "       select ts_headline('simple',  t.text, q.tq, %(opts)s) as simple_hl, "
            "              ts_headline('english', t.text, q.tq, %(opts)s) as english_hl, "
            "              t.role "
            "         from turn t "
            "        where t.conversation_id = c.id "
            "          and (to_tsvector('english', t.text) @@ q.tq "
            "            or to_tsvector('simple',  t.text) @@ q.tq) "
            "        order by t.seq limit 1) m on true "
            " where c.title ilike %(like)s or m.role is not null "
            # a name you half-remember beats a passing mention in an answer
            " order by on_title desc, c.last_active desc limit 50",
            {"like": like, "tsq": tsq, "marked": "%<b>%",
             "opts": "MaxWords=22,MinWords=9,MaxFragments=1,ShortWord=2"})
        rows = cur.fetchall()
    return {"results": [{"id": r[0], "title": r[1], "last_active": r[2],
                         "on_title": r[3], "snippet": r[4], "role": r[5]}
                        for r in rows]}


@app.get("/api/chat/sessions/{cid}")
def get_session(cid: int, account=ACCOUNT):
    with db.connect() as conn, conn.cursor() as cur:
        cur.execute("select title, working_set, summary from conversation where id = %s",
                    (cid,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(404, "no such conversation")
        cur.execute("select seq, role, text, status, sources, cost_inr, ms, created_at "
                    "from turn where conversation_id = %s order by seq", (cid,))
        turns = [{"seq": t[0], "role": t[1], "text": t[2], "status": t[3],
                  "sources": t[4], "cost_inr": t[5], "ms": t[6], "created_at": t[7]}
                 for t in cur.fetchall()]
    return {"id": cid, "title": row[0], "working_set": row[1], "summary": row[2],
            "turns": turns}


@app.delete("/api/chat/sessions/{cid}")
def delete_session(cid: int, account=ACCOUNT):
    with db.connect() as conn, conn.cursor() as cur:
        cur.execute("delete from conversation where id = %s", (cid,))
        gone = cur.rowcount
        conn.commit()
    if not gone:
        raise HTTPException(404, "no such conversation")
    return {"ok": True}


# The degrade ladder, in documents rather than tokens: the newest keep their full
# text, the next tier keeps its facts, everything older keeps a line. Rough token
# costs per level, only used to report tokens_est back to the caller.
WORKING_SET_FULL = 8
FULL_TOKENS, FACTS_TOKENS, SUMMARY_TOKENS = 1200, 150, 20


def _sse(event: str, payload) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, default=str)}\n\n"


def _save_turns(cid: int, question: str, text: str, status: str,
                sources: list, plan: dict, cost: float, ms: int, opened: list) -> dict:
    """One transaction, holding the conversation row.

    The unique(conversation_id, seq) constraint stops two turns taking the same
    number. It does NOT stop two requests reading working_set, each adding their
    own document, and the second write erasing the first. The row lock does.
    """
    with db.connect(tries=15) as conn, conn.cursor() as cur:
        cur.execute("select working_set, title_state from conversation "
                    "where id = %s for update", (cid,))
        row = cur.fetchone()
        if not row:
            return {}
        held = list(row[0] or [])
        title_state = row[1] or "first"
        known = {w.get("sha1") for w in held}
        cur.execute("select coalesce(max(seq), 0) from turn where conversation_id = %s",
                    (cid,))
        seq = cur.fetchone()[0] + 1
        cur.execute("insert into turn (conversation_id, seq, role, text, status) "
                    "values (%s,%s,'user',%s,'complete')", (cid, seq, question))
        cur.execute("insert into turn (conversation_id, seq, role, text, status, plan, "
                    "sources, cost_inr, ms) values (%s,%s,'assistant',%s,%s,%s,%s,%s,%s)",
                    (cid, seq + 1, text, status, json.dumps(plan),
                     json.dumps(sources), cost, ms))
        for sha in opened:
            if sha not in known:
                held.append({"sha1": sha, "level": "full", "turn_added": seq + 1})

        # COMPACTION. The working set is re-sent every turn, so an unbounded one
        # costs more each time and, worse, crowds new evidence out of the
        # shortlist. The oldest entries drop to a cheaper level rather than being
        # forgotten -- gather reloads any of them from the database on demand.
        held.sort(key=lambda w: w.get("turn_added") or 0, reverse=True)
        for i, entry in enumerate(held):
            entry["level"] = ("full" if i < WORKING_SET_FULL else
                              "facts" if i < WORKING_SET_FULL * 2 else "summary")
        tokens = sum(FULL_TOKENS if w["level"] == "full" else
                     FACTS_TOKENS if w["level"] == "facts" else SUMMARY_TOKENS
                     for w in held)
        # THE NAME. Small talk does not move this on: a thread that is only
        # pleasantries keeps its pleasantry of a name and never costs a call.
        # `first` -> `seeded` is free, `seeded` -> `settled` needs the model and
        # so happens outside this transaction, once, and never again.
        real = (plan or {}).get("mode", "fast") != "chat"
        out = {"title": None, "settle": False}
        if real and title_state == "first":
            out["title"] = title_mod.seed((plan or {}).get("restated", ""), question)
            cur.execute("update conversation set title = %s, title_state = 'seeded' "
                        "where id = %s", (out["title"], cid))
        elif real and title_state == "seeded":
            out["settle"] = True
        cur.execute("update conversation set working_set = %s, tokens_est = %s, "
                    "last_active = now(), title = coalesce(title, %s) where id = %s",
                    (json.dumps(held), tokens, question[:80], cid))
        conn.commit()
        return out


def _settle_title(cid: int) -> str:
    """Name the thread from the questions that actually needed the corpus.

    Capped at five so a long thread cannot grow the prompt without limit; in
    practice this fires on the second real question and sees exactly two.
    """
    with db.connect() as conn, conn.cursor() as cur:
        cur.execute(
            "select u.text from turn u "
            "  join turn a on a.conversation_id = u.conversation_id "
            "             and a.seq = u.seq + 1 and a.role = 'assistant' "
            " where u.conversation_id = %s and u.role = 'user' "
            "   and coalesce(a.plan->>'mode', 'fast') <> 'chat' "
            " order by u.seq limit %s", (cid, title_mod.MAX_QUESTIONS))
        asked = [r[0] for r in cur.fetchall()]
    named = title_mod.suggest(gemini(), asked)
    if not named:
        return ""
    with db.connect() as conn, conn.cursor() as cur:
        # `title_state = 'seeded'` is the guard, not a WHERE on the id alone: two
        # answers finishing at once must not both rename the thread.
        cur.execute("update conversation set title = %s, title_state = 'settled' "
                    "where id = %s and title_state = 'seeded' returning title",
                    (named, cid))
        row = cur.fetchone()
        conn.commit()
    return named if row else ""


@app.post("/api/chat/sessions/{cid}/ask")
def ask(cid: int, body: Ask, request: Request, account=ACCOUNT):
    # Refused BEFORE the planner runs: the point is to spend nothing.
    who = request.client.host if request.client else "?"
    wait = max(ASK_PER_CALLER.check(who), ASK_OVERALL.check("*"))
    if wait:
        raise HTTPException(
            429,
            {"message": f"Too many questions at once. Try again in {wait} seconds.",
             "retry_after": wait},
            headers={"Retry-After": str(wait)})

    with db.connect() as conn, conn.cursor() as cur:
        cur.execute("select working_set from conversation where id = %s", (cid,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(404, "no such conversation")
        held = [w["sha1"] for w in (row[0] or []) if w.get("sha1")]
        cur.execute("select role, text from turn where conversation_id = %s "
                    "order by seq desc limit %s", (cid, history_mod.MAX_TURNS))
        history = history_mod.build(cur.fetchall())

    def stream():
        t0 = time.time()
        text, sources, plan, cost = "", [], {}, 0.0
        retrieved: list = []
        status = "interrupted"
        try:
            with db.connect() as conn, conn.cursor() as cur:
                for kind, payload in converse(cur, body.question, vocabulary(), gemini(),
                                              history=history, held=held):
                    if kind == "token":
                        text += payload
                    elif kind == "thought":
                        yield _sse("thought", {"text": payload})
                        continue
                    elif kind == "sources":
                        # Only the cited subset is published and stored. The
                        # renumbered text replaces what streamed, so [1] in the
                        # saved answer is the first card in the saved evidence.
                        sources = payload["sources"]
                        text = payload.get("text", text)
                        retrieved = payload.get("retrieved") or [s["sha1"] for s in sources]
                        payload = {"sources": sources}
                    elif kind == "mode":
                        # merge: an escalation re-announces the mode with a
                        # smaller payload, and replacing would drop `restated`
                        plan = {**plan, **payload}
                    elif kind == "done":
                        cost = payload.get("cost_inr", 0.0)
                        # An answer that ran out of room is NOT complete. Storing
                        # it as complete is what let a half-sentence look
                        # finished on every later reload.
                        status = "cut" if payload.get("answer_cut") else "complete"
                    yield _sse(kind, payload if isinstance(payload, dict)
                               else {"text": payload})
        except Exception as exc:                    # noqa: BLE001 - reported, not swallowed
            status = "failed" if not text else "interrupted"
            yield _sse("error", {"message": str(exc)[:300]})
        finally:
            # `finally`, not a trailing block: a browser that walks away CLOSES
            # this generator, and anything after the loop simply never runs. The
            # whole exchange used to vanish from history on a disconnect.
            #
            # Nothing is yielded from here -- a generator being closed cannot
            # yield -- so a save failure is logged rather than announced.
            try:
                # Persist before yielding any optional post-stream event. If the
                # client disconnects while waiting for that event, the answer
                # must already be durable in conversation history.
                # Evidence is what the answer cited; the working set is
                # everything retrieval opened, so a follow-up keeps the context
                # this answer looked at and chose not to quote.
                saved = _save_turns(cid, body.question, text, status, sources, plan,
                                    cost, int((time.time() - t0) * 1000),
                                    retrieved or [s["sha1"] for s in sources])
                if status == "complete" and saved.get("settle"):
                    # The one paid naming call a thread ever gets. Written to
                    # the database BEFORE it is announced: a reader who walks
                    # away mid-event must still find the new name on reload.
                    named = _settle_title(cid)
                    if named:
                        saved["title"] = named
                if saved.get("title"):
                    yield _sse("title", {"title": saved["title"]})
                if status == "complete":
                    # Inform the client that the persisted context is being
                    # compacted. The database remains authoritative after the
                    # stream closes; these estimates are deliberately
                    # informational and contain no signed URLs or credentials.
                    tokens_before = max(1, round((len(history) + len(text)) / 4))
                    tokens_after = max(1, round((len(history[-8000:]) + len(text)) / 4))
                    yield _sse("compacting", {
                        "working_set": len(held),
                        "tokens_before": tokens_before,
                        "tokens_after": tokens_after,
                        "demoted": [],
                    })
            except Exception as exc:                # noqa: BLE001
                print(f"  ! turn NOT saved for conversation {cid}: {exc}",
                      file=sys.stderr)

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"cache-control": "no-store",
                                      "x-accel-buffering": "no"})


# ---------------------------------------------------------------- properties
@app.get("/api/properties")
def properties(q: str = "", state: str = "", city: str = "", entity_type: str = "",
               near: str = "", has_pool: str = "", rooms_max: int = 0, account=ACCOUNT):
    conds = []
    if has_pool:
        conds.append(("has_pool", "true" if has_pool.lower() == "true" else "false", ""))
    if rooms_max:
        conds.append(("room_count", "<=", str(rooms_max)))
    with db.connect() as conn, conn.cursor() as cur:
        if q:
            hits = retrieve.find_entities(cur, q, limit=20)
            return {"count": len(hits),
                    "properties": [{"id": h[0], "name": h[1], "state": h[2]} for h in hits]}
        kw = dict(entity_type=entity_type or None, state=state or None,
                  city=city or None, near=near or None)
        total = retrieve.count_where(cur, conds, **kw)
        rows = retrieve.entities_where(cur, conds, **kw)
    return {"count": total,
            "properties": [{"id": r[0], "name": r[1], "state": r[2],
                            "entity_type": r[3], "facts": r[4]} for r in rows]}


@app.get("/api/properties/{pid}")
def one_property(pid: int, account=ACCOUNT):
    with db.connect() as conn, conn.cursor() as cur:
        cur.execute("select canonical_name, entity_type, state, city, aliases, facts "
                    "from entities where id = %s", (pid,))
        r = cur.fetchone()
        if not r:
            raise HTTPException(404, "no such property")
    return {"id": pid, "name": r[0], "entity_type": r[1], "state": r[2], "city": r[3],
            "aliases": r[4], "facts": r[5]}


@app.get("/api/properties/{pid}/facts")
def property_facts(pid: int, account=ACCOUNT):
    with db.connect() as conn, conn.cursor() as cur:
        facts = retrieve.facts_for(cur, [pid])
    return {"facts": [{"key": f.key, "value": f.value, "unit": f.unit, "scope": f.scope,
                       "asserted_as": f.asserted_as, "evidence": f.evidence,
                       "sha1": f.sha1, "page": f.page} for f in facts]}


@app.get("/api/properties/{pid}/connections")
def property_connections(pid: int, account=ACCOUNT):
    with db.connect() as conn, conn.cursor() as cur:
        edges = retrieve.nearest(cur, [pid])
    # nulls stay null. An omitted distance reads as zero to a frontend.
    return {"connections": [{"from": e[0], "kind": e[1], "to": e[2],
                             "distance_km": float(e[3]) if e[3] is not None else None,
                             "duration_h": float(e[4]) if e[4] is not None else None,
                             "evidence": e[5], "sha1": e[6]} for e in edges]}


@app.get("/api/properties/{pid}/documents")
def property_documents(pid: int, account=ACCOUNT):
    with db.connect() as conn, conn.cursor() as cur:
        cur.execute("select d.sha1, d.rel_path, d.page_count from documents d "
                    "join entity_documents ed on ed.sha1 = d.sha1 where ed.entity_id = %s",
                    (pid,))
        rows = cur.fetchall()
    return {"documents": [{"sha1": r[0], "rel_path": r[1], "page_count": r[2]}
                          for r in rows]}


# ---------------------------------------------------------------- sources
def _document(cur, sha1: str):
    cur.execute("select sha1, rel_path, ext, page_count, is_tiled from documents "
                "where sha1 = %s", (sha1,))
    row = cur.fetchone()
    if not row:
        raise HTTPException(404, "no such document")
    return row


@app.get("/api/sources/{sha1}")
def source(sha1: str, account=ACCOUNT):
    with db.connect() as conn, conn.cursor() as cur:
        r = _document(cur, sha1)
    return {"sha1": r[0], "rel_path": r[1], "ext": r[2], "page_count": r[3],
            "is_tiled": r[4]}


@app.get("/api/sources/{sha1}/page/{n}")
def source_page(sha1: str, n: int, account=ACCOUNT):
    with db.connect() as conn, conn.cursor() as cur:
        r = _document(cur, sha1)
    if not 1 <= n <= (r[3] or 1):
        raise HTTPException(404, "no such page")
    # minted per request: these expire in 15 minutes, so storing one stores rubbish
    return {"url": storage.presign(storage.page_key(sha1, n)),
            "expires_in": config.PRESIGN_TTL}


@app.get("/api/sources/{sha1}/page/{n}/crop")
def source_crop(sha1: str, n: int, fact: int, account=ACCOUNT):
    """Just the lines the fact was read from. Cut from the ORIGINAL image, not
    the page tile — the two use different coordinates (see api/crops.py)."""
    with db.connect() as conn, conn.cursor() as cur:
        _document(cur, sha1)
        try:
            box = crops.fact_box(cur, fact)
            if box[0] != sha1:
                raise HTTPException(404, "that fact is not in this document")
            if box[3] is not None and int(box[3]) != n:
                # a real fact reached through the wrong page URL still returned
                # 200, so a frontend could show the crop under the wrong page
                raise HTTPException(404, f"fact {fact} is on page {box[3]}, not {n}")
            key = crops.make(cur, fact)
        except crops.NoEvidence as e:
            raise HTTPException(404, str(e)) from e
    return {"url": storage.presign(key), "expires_in": config.PRESIGN_TTL}


@app.get("/api/sources/{sha1}/original")
def source_original(sha1: str, account=ACCOUNT):
    with db.connect() as conn, conn.cursor() as cur:
        r = _document(cur, sha1)
    return {"url": storage.presign(storage.original_key(sha1, r[2] or "")),
            "expires_in": config.PRESIGN_TTL}
