"""Decide what a question needs, and how hard to work on it.

Two jobs, one call, thinking off. It extracts the parameters retrieval will use
and it classifies the question into a MODE. It does NOT choose a retrieval
source: gather runs every source the parameters imply (see gather.py), because
discarding three cheap sources to protect one guess leaves a wrong guess with no
fallback.
"""
import json

from google import genai
from google.genai import types

from backend import config, retry

MODES = ("chat", "fast", "think", "agent")
LENGTHS = ("brief", "normal", "long")


MODE_HELP = """  chat   the message asks NOTHING about a property, a place or the documents.
         Greetings, thanks, "who are you", "what can you do", "never mind".
         These are answered from nothing: no retrieval runs, no sources exist.
         "Hi"  "thanks!"  "what can you help with?"
  fast   one property or one field, a count, or a plain filter.
         "Does Ramathra Fort have a pool?"  "How many are in Rajasthan?"
  think  comparison across several dimensions, a recommendation, ANY arithmetic,
         or anything where sources are likely to disagree.
         "Which suits a family better, A or B?"
  agent  conditions spanning several sources, or an open-ended search of the
         whole corpus that one query cannot express.
         "Near Kanha, with a pool, under 20 rooms."

`chat` is the exception to the rule below: it is decided on its own. If the
message names or implies ANY property, place, rate, amenity or date, it is not
chat, however short it is. "Kanha?" is fast, not chat. If it is purely social or
about the assistant itself, it IS chat, and retrieving documents for it wastes a
search and attaches sources to an answer that cites nothing.

Among fast/think/agent, when genuinely torn choose the HIGHER mode. Being slow
and right costs a rupee; being fast and wrong costs a client."""

SCHEMA = {
    "type": "object",
    "required": ["mode", "restated"],
    "properties": {
        "mode": {"type": "string", "enum": list(MODES)},
        "why": {"type": "string", "description": "one short clause; shown in the UI"},
        "restated": {"type": "string",
                     "description": "the question with pronouns and references resolved "
                                    "from the conversation, standing on its own"},
        "entities": {"type": "array", "items": {"type": "string"},
                     "description": "property/place names mentioned, as written"},
        "conditions": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["key", "op"],
                "properties": {
                    "key": {"type": "string", "description": "a vocabulary label"},
                    "op": {"type": "string",
                           "enum": ["true", "false", "exists", "contains",
                                    "=", "<", "<=", ">", ">="]},
                    "value": {"type": "string"},
                },
            },
        },
        "scope": {
            "type": "object",
            "properties": {
                "state": {"type": "string", "description": "Indian state, if named"},
                "city": {"type": "string", "description": "city or town, if named"},
                "entity_type": {"type": "string", "description": "hotel | park | airport | ..."},
                "near": {"type": "string",
                         "description": "for 'properties near X', the X. Joins the graph."},
            },
        },
        "keys": {"type": "array", "items": {"type": "string"},
                 "description": "vocabulary labels the answer will need"},
        "aggregate": {"type": "string", "enum": ["count", "none"]},
        "answer_length": {
            "type": "string", "enum": ["brief", "normal", "long"],
            "description": "how much room the ANSWER needs, independent of how "
                           "hard the search is. brief = a number, a yes/no, or "
                           "one line. normal = a short list or a paragraph. "
                           "long = the user asked to enumerate a whole set "
                           "('list every...', 'all of them', 'one line each')."},
        "connection_kind": {"type": "string",
                            "description": "nearest_airport | nearest_park | nearest_gate | "
                                           "nearest_railhead | member_of"},
        "needs_external_dates": {"type": "boolean",
                                 "description": "true ONLY for festival/holiday/closure dates"},
        "date_terms": {"type": "array", "items": {"type": "string"},
                       "description": "festival, holiday or closure names asked about, "
                                      "e.g. ['Holi','Diwali']. Only with needs_external_dates."},
        "needs_calculation": {"type": "boolean",
                              "description": "true if the answer requires arithmetic"},
        "arrive_by": {"type": "string",
                      "description": "24-hour clock time the client must ARRIVE by, "
                                     "e.g. a flight departure. Only if the question gives one."},
        "buffer_hours": {"type": "number",
                         "description": "airport reporting time in hours; 2 if unstated"},
    },
}

DEFAULTS = {"mode": "fast", "why": "", "restated": "", "entities": [], "conditions": [],
            "scope": {}, "keys": [], "aggregate": None, "connection_kind": None,
            "answer_length": "normal",
            "needs_external_dates": False, "needs_calculation": False,
            "date_terms": [], "arrive_by": None, "buffer_hours": None}


class PlanError(Exception):
    """The planner did not return something we can act on."""


def build(question: str, vocabulary, history: str = "") -> str:
    labels = ", ".join(sorted(vocabulary.approved))
    hist = f"\n\nCONVERSATION SO FAR (for resolving pronouns only):\n{history}\n" if history else ""
    return f"""You are planning how to answer a question about a travel company's
property knowledge base. You do NOT answer it. You decide what to fetch and how
hard to work.

MODE — pick exactly one:
{MODE_HELP}

AVAILABLE LABELS (use these exact strings in `conditions` and `keys`. If the
question needs something not listed, leave conditions empty — the full text of
the documents still answers it):
{labels}

CONDITION OPERATORS:
  true / false   a boolean label, e.g. key "has_pool" op "true"
  exists         the property states this label at all
  contains       substring match on the value
  = < <= > >=    numeric comparison, e.g. key "room_count" op "<=" value "20"

RULES
  * `restated` must stand alone. "does it have a pool" after talking about
    Ramathra Fort becomes "Does Ramathra Fort have a pool?"
  * Put every property or place NAME in `entities`, spelled as the user wrote it.
  * `scope.near` is for "properties near X" — it joins the connections graph.
    `entities` is for "tell me about X".
    NEVER put the same place in BOTH. "Which lodges are near Kanha?" is
    scope.near="Kanha" with entities EMPTY — Kanha is the landmark, not the
    thing being asked about. Naming it in entities as well restricts the count
    to the park itself, which is not a property, so the answer comes back zero.
  * `aggregate` is "count" only when the user wants a NUMBER, not a list.
  * `answer_length` is about the REPLY, not the search. A one-property lookup
    that asks for every room type is "long". A whole-corpus search that asks
    "is there one?" is "brief". When unsure, "normal".
  * `needs_external_dates` is true ONLY for festival, public-holiday or park
    closure dates. Never for anything about a property.
{hist}
QUESTION: {question}

Return JSON matching the schema. Nothing else."""


def _normalise(raw: dict) -> dict:
    spec = {**DEFAULTS, **{k: v for k, v in (raw or {}).items() if v is not None}}
    if spec["mode"] not in MODES:
        spec["mode"] = "fast"
    if spec.get("answer_length") not in LENGTHS:
        spec["answer_length"] = "normal"
    if spec["aggregate"] == "none":
        spec["aggregate"] = None
    spec["scope"] = {k: v for k, v in (spec["scope"] or {}).items() if v}
    return spec


def make(question: str, vocabulary, history: str = "", client=None) -> dict:
    client = client or genai.Client(api_key=config.GEMINI_KEY)
    prompt = build(question, vocabulary, history)
    cfg = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=SCHEMA,
        thinking_config=types.ThinkingConfig(thinking_budget=0),
    )
    last = None
    for _ in range(2):          # one recovery attempt, then a clear failure
        # Six tries, exponential, ~62s per model, then a sibling. A 503 spike on
        # the planner killed a whole fifteen-question run at case three.
        r, _used = retry.over_models(
            config.model_chain(config.PLAN_MODEL),
            lambda m: client.models.generate_content(model=m, contents=prompt,
                                                     config=cfg),
            tries=6)
        try:
            spec = _normalise(json.loads(r.text))
        except (json.JSONDecodeError, TypeError) as e:
            last = e
            prompt += "\n\nYour previous reply was not valid JSON. Return ONLY the JSON object."
            continue
        u = r.usage_metadata
        spec["_cost_inr"] = config.price_inr(
            config.PLAN_MODEL,
            getattr(u, "prompt_token_count", 0) or 0,
            (getattr(u, "candidates_token_count", 0) or 0) +
            (getattr(u, "thoughts_token_count", 0) or 0))
        spec["restated"] = spec["restated"] or question
        return spec
    raise PlanError(f"planner returned invalid json twice: {last}")
