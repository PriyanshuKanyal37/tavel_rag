"""One shared account, one session row per browser.

The cookie carries a random session id and nothing else. A signed cookie would
need a secret and still could not be revoked -- clearing it removes it from the
browser that asked while any copy stays valid until it expires. A row can be
revoked, which is what "log out" has to mean.

No bcrypt: hashlib.scrypt is in the standard library and is a stronger KDF than
anything worth adding a dependency for.
"""
import hashlib
import hmac
import os
import time
import uuid

from fastapi import Cookie, HTTPException

from backend import db

COOKIE = "tirag_session"
SESSION_HOURS = 12
MAX_FAILURES = 5                 # per window, per client
FAILURE_WINDOW = 300             # seconds
N, R, P = 1 << 14, 8, 1          # scrypt: ~16MB, ~100ms

# ponytail: in-process, so it resets on restart and is per-worker. Enough for one
# shared password on an internal tool; move to the database if it ever runs
# multi-worker and the throttle actually has to hold.
FAILURES: dict = {}


# ---------------------------------------------------------------- passwords
def hash_password(password: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.scrypt(password.encode(), salt=salt, n=N, r=R, p=P,
                        dklen=32, maxmem=64 * 1024 * 1024)
    return f"scrypt${N}${R}${P}${salt.hex()}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        kind, n, r, p, salt_hex, want = stored.split("$")
        if kind != "scrypt":
            return False
        dk = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt_hex),
                            n=int(n), r=int(r), p=int(p), dklen=len(want) // 2,
                            maxmem=64 * 1024 * 1024)
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(dk.hex(), want)


def provision(email: str, name: str, password: str) -> None:
    """Create or reset the single account. Called from the CLI, and by tests."""
    with db.connect() as conn, conn.cursor() as cur:
        cur.execute(
            "insert into app_account (id, email, password_hash, name) values (1,%s,%s,%s) "
            "on conflict (id) do update set email=excluded.email, "
            "password_hash=excluded.password_hash, name=excluded.name, active=true",
            (email, hash_password(password), name))
        conn.commit()


# ---------------------------------------------------------------- throttle
def _throttled(who: str) -> bool:
    hits = [t for t in FAILURES.get(who, []) if time.time() - t < FAILURE_WINDOW]
    FAILURES[who] = hits
    return len(hits) >= MAX_FAILURES


def _record_failure(who: str) -> None:
    FAILURES.setdefault(who, []).append(time.time())


# ---------------------------------------------------------------- sessions
def start_session(user_agent: str = "") -> str:
    with db.connect() as conn, conn.cursor() as cur:
        cur.execute("insert into login_session (expires_at, user_agent) "
                    "values (now() + make_interval(hours => %s), %s) returning id",
                    (SESSION_HOURS, user_agent[:300]))
        sid = cur.fetchone()[0]
        conn.commit()
    return str(sid)


def revoke(token: str) -> None:
    try:
        sid = uuid.UUID(token)
    except (ValueError, TypeError, AttributeError):
        return
    with db.connect() as conn, conn.cursor() as cur:
        cur.execute("update login_session set revoked_at = now() "
                    "where id = %s and revoked_at is null", (sid,))
        conn.commit()


def resolve(token: str):
    """The account behind a live session, or None. Also bumps last_seen."""
    try:
        sid = uuid.UUID(token)
    except (ValueError, TypeError, AttributeError):
        return None
    with db.connect() as conn, conn.cursor() as cur:
        cur.execute(
            "with live as ("
            "  update login_session set last_seen = now() "
            "  where id = %s and revoked_at is null and expires_at > now() returning id) "
            "select a.email, a.name from app_account a, live where a.active", (sid,))
        row = cur.fetchone()
        conn.commit()
    return {"email": row[0], "name": row[1]} if row else None


def sign_in(password: str, who: str, user_agent: str = "") -> str:
    if _throttled(who):
        raise HTTPException(429, "too many failed sign-ins; wait a few minutes")
    with db.connect() as conn, conn.cursor() as cur:
        cur.execute("select password_hash from app_account where id = 1 and active")
        row = cur.fetchone()
    if not row or not verify_password(password, row[0]):
        _record_failure(who)
        raise HTTPException(401, "wrong password")
    FAILURES.pop(who, None)
    return start_session(user_agent)


def current_account(**kw):
    """FastAPI dependency. Rejects a missing, revoked or expired session."""
    token = kw.get(COOKIE)
    account = resolve(token) if token else None
    if not account:
        raise HTTPException(401, "sign in first")
    return account


def account_dep(tirag_session: str = Cookie(default=None)):
    return current_account(**{COOKIE: tirag_session})
