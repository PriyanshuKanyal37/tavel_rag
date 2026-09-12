"""Admin, from the command line. There are no admin screens, by decision.

    python -m backend.api.cli set-password --email team@travelinn.local
    python -m backend.api.cli sessions            # who is signed in
    python -m backend.api.cli revoke-all          # sign every browser out
    python -m backend.api.cli calendar-load dates.json
    python -m backend.api.cli calendar-list
"""
import argparse
import getpass
import json
import pathlib
import sys

from backend import db, retry
from backend.api import auth


def set_password(args) -> None:
    pw = args.password or getpass.getpass("password: ")
    if len(pw) < 10:
        sys.exit("use at least 10 characters — one password protects everything")
    auth.provision(args.email, args.name, pw)
    print(f"account ready: {args.email} ({args.name})")
    print("change the address later with:  update app_account set email='…' where id=1;")


def sessions(args) -> None:
    with db.connect() as conn, conn.cursor() as cur:
        cur.execute("select id, created_at, last_seen, expires_at, revoked_at, "
                    "coalesce(user_agent,'') from login_session "
                    "order by last_seen desc limit 40")
        rows = cur.fetchall()
    print(f"{'session':<38} {'last seen':<22} state")
    for sid, _created, seen, expires, revoked, ua in rows:
        state = ("revoked" if revoked else
                 "expired" if expires and expires.timestamp() < seen.timestamp() else "live")
        print(f"{str(sid):<38} {str(seen)[:19]:<22} {state:<8} {ua[:40]}")
    print(f"\n{len(rows)} shown")


def revoke_all(args) -> None:
    with db.connect() as conn, conn.cursor() as cur:
        cur.execute("update login_session set revoked_at = now() where revoked_at is null")
        n = cur.rowcount
        conn.commit()
    print(f"revoked {n} session(s) — every browser must sign in again")


def calendar_load(args) -> None:
    """JSON list of {kind, name, starts_on, ends_on?, note?, source_url?, verified_on?}.

    source_url is not decoration. A date with no source is a date nobody can check.
    """
    rows = json.loads(pathlib.Path(args.file).read_text(encoding="utf-8"))
    missing = [r["name"] for r in rows if not r.get("source_url")]
    if missing and not args.allow_unsourced:
        sys.exit(f"no source_url on: {missing}\nadd one, or pass --allow-unsourced")
    with db.connect() as conn, conn.cursor() as cur:
        for r in rows:
            cur.execute(
                "insert into calendar_event (kind, name, starts_on, ends_on, note, "
                "source_url, verified_on) values (%s,%s,%s,%s,%s,%s,%s) "
                "on conflict (kind, name, starts_on, entity_id) do update set "
                "ends_on=excluded.ends_on, note=excluded.note, "
                "source_url=excluded.source_url, verified_on=excluded.verified_on",
                (r["kind"], r["name"], r["starts_on"], r.get("ends_on"), r.get("note"),
                 r.get("source_url"), r.get("verified_on")))
        conn.commit()
    print(f"loaded {len(rows)} calendar row(s)")


def calendar_list(args) -> None:
    with db.connect() as conn, conn.cursor() as cur:
        cur.execute("select kind, name, starts_on, ends_on, source_url, verified_on "
                    "from calendar_event order by starts_on limit 200")
        rows = cur.fetchall()
    if not rows:
        print("calendar_event is empty — date questions will fall through to web search")
        return
    for kind, name, a, b, url, checked in rows:
        print(f"  {kind:<14} {name:<26} {a}{' to ' + str(b) if b else ''}"
              f"  {'✓' + str(checked) if checked else '(unverified)'}  {url or ''}")
    print(f"\n{len(rows)} row(s)")


def keys(args) -> None:
    """Which Gemini keys actually work. One cheap call each, ~₹0.0004."""
    import os

    from google import genai

    from backend import config
    for name in ("GEMINI_API_KEY", "GEMINI_API_KEY_2", "GEMINI_API_KEY_3"):
        key = os.getenv(name)
        if not key:
            print(f"  {name:<20} not set")
            continue
        client = genai.Client(api_key=key)
        try:
            # 503 "model overloaded" is transient and says nothing about the key.
            # Without retrying, a busy minute looks exactly like a dead key.
            retry.call(lambda: client.models.generate_content(
                model=config.PLAN_MODEL, contents="say ok"), tries=4, delay=3)
            print(f"  {name:<20} ✅ works    ...{key[-6:]}"
                  + ("   ← in use" if key == config.GEMINI_KEY else ""))
        except Exception as exc:                    # noqa: BLE001
            print(f"  {name:<20} ❌ ...{key[-6:]}  {(retry.explain(exc) or str(exc))[:70]}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("set-password")
    p.add_argument("--email", default="team@travelinn.local")
    p.add_argument("--name", default="Travel Inn")
    p.add_argument("--password", default="")
    p.set_defaults(fn=set_password)

    sub.add_parser("sessions").set_defaults(fn=sessions)
    sub.add_parser("revoke-all").set_defaults(fn=revoke_all)

    p = sub.add_parser("calendar-load")
    p.add_argument("file")
    p.add_argument("--allow-unsourced", action="store_true")
    p.set_defaults(fn=calendar_load)

    sub.add_parser("calendar-list").set_defaults(fn=calendar_list)
    sub.add_parser("keys").set_defaults(fn=keys)

    args = ap.parse_args()
    retry.call(lambda: args.fn(args), tries=20, delay=4)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        why = retry.explain(exc)
        if not why:
            raise
        sys.exit(f"\n✗ {why}")
