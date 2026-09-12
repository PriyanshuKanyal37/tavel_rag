"""Neon connections. Pooled for queries, direct for DDL and index builds."""
import contextlib
import socket
import sys
import threading

import psycopg
from psycopg.conninfo import conninfo_to_dict, make_conninfo
from psycopg_pool import ConnectionPool, PoolTimeout

from backend import config, retry

_ADDR: dict = {}        # hostname -> address, resolved once per process


def _pin_host(dsn: str) -> str:
    """Resolve the host once and connect by address thereafter.

    Measured on this network: 3 of 40 lookups of the Neon hostname fail, in
    bursts long enough to outlast a retry loop. Paying that lottery on every
    single connection is needless. psycopg accepts `hostaddr` beside `host`,
    dialling the address while TLS still verifies the NAME, so one good lookup
    serves the whole process.

    Never fatal: if resolution fails the plain DSN goes through and psycopg
    resolves it the usual way.
    """
    try:
        info = conninfo_to_dict(dsn)
    except Exception:                       # noqa: BLE001 - malformed DSN is psycopg's to report
        return dsn
    host = info.get("host")
    if not host or info.get("hostaddr"):
        return dsn
    if host not in _ADDR:
        try:
            _ADDR[host] = socket.getaddrinfo(host, None, socket.AF_INET)[0][4][0]
        except OSError:
            return dsn
    return make_conninfo(dsn, hostaddr=_ADDR[host])


def forget_host(dsn: str) -> None:
    """Drop a pinned address. Called between retries, in case it went stale."""
    try:
        _ADDR.pop(conninfo_to_dict(dsn).get("host"), None)
    except Exception:                       # noqa: BLE001
        _ADDR.clear()


# Opening a Neon connection costs about a second; the queries behind it cost
# milliseconds. A request that dials its own connection therefore spends ~99% of
# its life in the handshake, and an authenticated request dials twice -- once to
# resolve the session, once for the endpoint body. The pool below is what makes
# the API feel instant rather than sluggish; it is not an optimisation, it is the
# difference between 2s and 30ms per click.
_POOL: "ConnectionPool | None" = None
_POOL_LOCK = threading.Lock()


def _pool() -> "ConnectionPool":
    global _POOL
    if _POOL is None:
        with _POOL_LOCK:
            if _POOL is None:
                dsn = config.DSN
                if not dsn:
                    raise SystemExit("no DSN in backend/.env (PILOT_DSN)")
                _POOL = ConnectionPool(
                    _pin_host(dsn),
                    min_size=config.POOL_MIN, max_size=config.POOL_MAX,
                    # Neon closes idle connections; recycle before it does and
                    # check one out only after confirming it is still alive.
                    max_idle=config.POOL_MAX_IDLE, max_lifetime=config.POOL_MAX_LIFETIME,
                    check=ConnectionPool.check_connection,
                    timeout=config.POOL_TIMEOUT,
                    kwargs={"autocommit": False},
                    open=True, name="travelinn",
                )
    return _POOL


def close_pool() -> None:
    """Shut the pool down on process exit. Safe to call when none was opened."""
    global _POOL
    with _POOL_LOCK:
        if _POOL is not None:
            _POOL.close()
            _POOL = None


@contextlib.contextmanager
def connect(direct: bool = False, autocommit: bool = False, tries: int = 6):
    """Neon's hostname resolves intermittently from some networks, so the address
    is pinned above and the dial is retried here. Retrying in a shell loop does
    not help: the process restart is the expensive part and the DNS answer is no
    fresher.

    Pooled by default. `direct` and `autocommit` still dial their own connection:
    they are for DDL, index builds and the reset path, which must not run on a
    shared handle and are rare enough that a second of setup does not matter."""
    if not direct and not autocommit:
        try:
            with _pool().connection() as conn:
                yield conn
            return
        except PoolTimeout:
            # Every connection busy. Fall through and dial one rather than fail.
            print("  pool exhausted, dialling a direct connection", file=sys.stderr)

    dsn = config.DSN_DIRECT if direct else config.DSN
    if not dsn:
        raise SystemExit("no DSN in backend/.env (PILOT_DSN)")

    def dial():
        return psycopg.connect(_pin_host(dsn), autocommit=autocommit)

    def again(i, e):
        forget_host(dsn)                    # the pinned address may be the problem
        print(f"  neon unreachable ({e}), retry {i}", file=sys.stderr)

    with retry.call(dial, tries=tries, delay=3, on_retry=again) as conn:
        yield conn


def apply_schema() -> None:
    """Create extensions and tables. Idempotent. Runs on the direct endpoint --
    CREATE EXTENSION and index builds are unreliable through the pooler."""
    sql = (config.BACKEND / "schema.sql").read_text(encoding="utf-8")
    with connect(direct=True, autocommit=True) as conn:
        conn.execute(sql)


def reset() -> None:
    """Drop everything this project owns. Destructive and deliberate."""
    with connect(direct=True, autocommit=True) as conn:
        conn.execute("""
            drop table if exists fact_evidence, connections, entity_documents,
                                 entities, attribute_vocabulary, documents,
                                 review_queue cascade;
        """)


def stats() -> dict:
    q = {
        "documents": "select count(*) from documents",
        "entities": "select count(*) from entities",
        "facts": "select count(*) from fact_evidence",
        "connections": "select count(*) from connections",
        "review_open": "select count(*) from review_queue where not resolved",
        "vocabulary": "select count(*) from attribute_vocabulary",
        "embedded": "select count(*) from documents where embedding is not null",
    }
    out = {}
    with connect() as conn, conn.cursor() as cur:
        for k, sql in q.items():
            try:
                cur.execute(sql)
                out[k] = cur.fetchone()[0]
            except psycopg.Error:
                out[k] = None
                conn.rollback()
    return out
