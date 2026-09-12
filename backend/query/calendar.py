"""Festival dates and closure windows: the table first, the web only if it must.

Web search is the one place the system may look outside the documents, and it is
fenced two ways. The tool is absent from every other request, so the capability
is not there to misjudge. And the lookup is its OWN call, carrying the date
question and no property material, because enabling the tool for a mixed
question ("when is Holi, and does this hotel have a pool?") opens it for the
whole request and nothing then stops the model searching the web about the hotel.

Nothing from here is ever a property fact. It is labelled (web) and stays labelled.
"""
from google.genai import types

from backend import config, retry

# Dates are facts about ONE year. Holi moves every Gregorian year and closure
# windows are reset annually, so a cached row carries the year it applies to and
# the date it was checked.
LOOKUP = """You are answering ONE narrow question: calendar dates.

Give the dates asked for, each with the year it applies to. If it is a park
closure or seasonal restriction, say which park and which season.

Answer ONLY about dates, festivals, holidays and closure periods. You have no
information about any hotel or property, and must not offer any.

QUESTION: %s"""


def from_table(cur, terms: list[str], year: int = None) -> list[dict]:
    """Rows we already hold. Free, exact, and always preferred."""
    if not terms:
        return []
    sql = ("select kind, name, starts_on, ends_on, note, source_url, verified_on "
           "from calendar_event where (" +
           " or ".join(["name ilike %s"] * len(terms)) + ")")
    params = [f"%{t}%" for t in terms]
    if year:
        sql += " and extract(year from starts_on) = %s"
        params.append(year)
    sql += " order by starts_on limit 60"
    cur.execute(sql, params)
    return [{"kind": r[0], "name": r[1], "starts_on": r[2], "ends_on": r[3],
             "note": r[4], "source_url": r[5], "verified_on": r[6]}
            for r in cur.fetchall()]


def from_web(client, question: str) -> dict:
    """A separate, calendar-only call. This is the ONLY request carrying a tool."""
    r = retry.call(lambda: client.models.generate_content(
        model=config.PLAN_MODEL,
        contents=LOOKUP % question,
        config=types.GenerateContentConfig(
            tools=[types.Tool(google_search=types.GoogleSearch())])))
    urls = []
    for cand in getattr(r, "candidates", None) or []:
        meta = getattr(cand, "grounding_metadata", None)
        for chunk in (getattr(meta, "grounding_chunks", None) or []):
            web = getattr(chunk, "web", None)
            if web is not None and getattr(web, "uri", None):
                urls.append(web.uri)
    return {"text": (r.text or "").strip(), "urls": urls[:6],
            "usage": getattr(r, "usage_metadata", None)}


def block(rows: list[dict], web: dict = None) -> str:
    """The context block. Table rows are ours; web claims are marked, always."""
    if rows:
        lines = [f"  - {r['name']} ({r['kind']}): {r['starts_on']}"
                 + (f" to {r['ends_on']}" if r["ends_on"] else "")
                 + (f"  [checked {r['verified_on']}]" if r["verified_on"] else "")
                 for r in rows]
        return ("[CALENDAR · from our own table · authoritative]\n" + "\n".join(lines))
    if web and web.get("text"):
        src = ("\n  sources: " + ", ".join(web["urls"])) if web.get("urls") else ""
        return ("[CALENDAR (web) · NOT from our documents · label it as a web result]\n"
                "This is a date lookup only. It says NOTHING about any property, and\n"
                "must never be cited as a document.\n" + web["text"] + src)
    return ""
