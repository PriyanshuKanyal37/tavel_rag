"""Everything a frontend needs, exercised against a real running server.

    COOKIE_SECURE=0 python -m tests.frontend_ready

A Secure cookie is not sent over plain http, so without that variable the login
succeeds and every check after it is a 401 -- which is exactly what a frontend
developer will hit on localhost. That is the point of running it this way.
"""
import atexit
import threading
import time

import httpx
import uvicorn

from backend import db
from backend.api import auth
from backend.api.app import app

# The live account password is not ours to know. Borrow the row: keep the
# real hash, set a throwaway one, put the original back at the end.
PASSWORD = "frontend-readiness-probe"
with db.connect() as conn, conn.cursor() as cur:
    cur.execute("select password_hash from app_account where id = 1")
    REAL_HASH = cur.fetchone()[0]
    cur.execute("update app_account set password_hash = %s where id = 1",
                (auth.hash_password(PASSWORD),))
    conn.commit()


@atexit.register
def restore():
    """In atexit, not at the end: a failed check must not leave the shared
    account on a password that is written in this file."""
    with db.connect() as conn, conn.cursor() as cur:
        cur.execute("update app_account set password_hash = %s where id = 1",
                    (REAL_HASH,))
        conn.commit()

PORT = 8137
BASE = f"http://127.0.0.1:{PORT}/api"

cfg = uvicorn.Config(app, host="127.0.0.1", port=PORT, log_level="error")
srv = uvicorn.Server(cfg)
threading.Thread(target=srv.run, daemon=True).start()
for _ in range(60):
    try:
        httpx.get(f"{BASE}/health", timeout=2)
        break
    except Exception:
        time.sleep(0.5)

ok = []


def check(label, passed, detail=""):
    ok.append(passed)
    print(f"  {'✅' if passed else '❌'} {label:<46} {detail}")


r = httpx.get(f"{BASE}/health", timeout=5)
check("health, no login needed", r.status_code == 200, r.text[:40])

r = httpx.options(f"{BASE}/health", timeout=5, headers={
    "Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET"})
check("CORS preflight from a frontend origin",
      bool(r.headers.get("access-control-allow-origin")),
      r.headers.get("access-control-allow-origin", "(none)"))
check("CORS allows credentials (the login cookie)",
      r.headers.get("access-control-allow-credentials") == "true")

r = httpx.get(f"{BASE}/auth/me", timeout=5)
check("protected route without a cookie is 401", r.status_code == 401)

c = httpx.Client(base_url=BASE, timeout=30)
r = c.post("/auth/login", json={"password": PASSWORD})
check("login with the real password", r.status_code == 200, r.text[:40])
check("cookie was issued", auth.COOKIE in c.cookies)

r = c.get("/auth/me")
check("/auth/me after login", r.status_code == 200, r.text[:60])

r = c.post("/chat/sessions", json={"title": "frontend readiness"})
cid = r.json().get("id") if r.status_code == 200 else None
check("create a conversation", cid is not None, f"id={cid}")

r = c.get("/chat/sessions")
check("list conversations", r.status_code == 200,
      f"{len(r.json().get('sessions', []))} threads")

r = c.get("/properties", params={"has_pool": "true", "entity_type": "hotel"})
check("browse properties without asking the model",
      r.status_code == 200 and r.json().get("count", 0) > 0,
      f"count={r.json().get('count')}")

pid = c.get("/properties", params={"q": "Bagh Tola"}).json()["properties"][0]["id"]
r = c.get(f"/properties/{pid}/connections")
edges = r.json().get("connections", [])
check("connections expose null distances as null",
      any(e["distance_km"] is None for e in edges), f"{len(edges)} edges")

r = c.get(f"/properties/{pid}/facts")
check("facts come with their evidence", len(r.json().get("facts", [])) > 0,
      f"{len(r.json().get('facts', []))} facts")

r = c.get("/health/deep")
deep = r.json() if r.status_code == 200 else {}
check("health/deep reaches Neon and R2",
      deep.get("neon") and deep.get("r2"),
      f"neon={deep.get('neon')} r2={deep.get('r2')} docs={deep.get('documents')}")

r = c.post(f"/chat/sessions/{cid}/ask", json={"question": "   "})
check("an empty question is rejected", r.status_code == 422, f"HTTP {r.status_code}")

if cid:
    c.delete(f"/chat/sessions/{cid}")


srv.should_exit = True
print(f"\n{sum(ok)}/{len(ok)} frontend prerequisites pass")
