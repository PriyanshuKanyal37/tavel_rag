"""The vocabulary: the only place the pipeline knows anything about a domain.

Nothing else in the codebase names a hotel, a park or an airport. The prompt is
BUILT from these rows; the validation rules are DRIVEN by them; the connection
edges are decided by them. Teaching the system a new kind of data is an INSERT.

    from backend.ingest import vocab
    v = vocab.load()                 # {key: Label}
    v.approved                       # only the queryable ones
    v.scalar_keys                    # cardinality 'scalar'  -> rules 3 and 8
    v.distance_keys                  # unit_kind 'distance'  -> rule 2
    v.boolean_keys                   # value_type 'boolean'  -> rule 1
    v.relation_keys                  # {key: relation_kind}  -> connections

The SEED below is the starting set for THIS corpus. It is written to the table
once, on an empty database, and after that the table is authoritative -- edit
rows, not this file.
"""
import dataclasses

from backend import db

# key: (definition, not_this, value_type, unit_kind, cardinality, relation_kind)
SEED: dict[str, tuple] = {
    # --- capacity -------------------------------------------------------
    "room_count": ("Number of rooms, keys, units or tents.", "Not the number of categories.",
                   "number", "count", "scalar", None),
    "room_categories": ("Number of distinct room types.", "", "number", "count", "scalar", None),
    "room_size": ("Floor area of a room category.", "", "quantity", "area", "multi", None),
    "price_from": ("Lowest published tariff.", "", "money", "currency", "scalar", None),
    "meal_plan": ("EP, CP, MAP, AP or a described inclusion.", "", "text", "none", "multi", None),
    # --- facilities (booleans) ------------------------------------------
    "has_pool": ("Whether a swimming pool exists.", "Never a sentence.", "boolean", "none", "scalar", None),
    "has_spa": ("Whether a spa exists.", "Never a sentence.", "boolean", "none", "scalar", None),
    "has_wifi": ("Whether wifi is available.", "Never a sentence.", "boolean", "none", "scalar", None),
    "has_ac": ("Whether rooms are air conditioned.", "Never a sentence.", "boolean", "none", "scalar", None),
    "has_restaurant": ("Whether a restaurant or dining venue exists.", "Never a sentence.",
                       "boolean", "none", "scalar", None),
    "has_bar": ("Whether a bar exists.", "Never a sentence.", "boolean", "none", "scalar", None),
    # --- seasonality ----------------------------------------------------
    "best_months": ("Recommended months to visit.", "", "text", "none", "multi", None),
    "closed_months": ("Months the property is shut.", "", "text", "none", "multi", None),
    "check_in": ("Check-in time.", "", "text", "none", "scalar", None),
    "check_out": ("Check-out time.", "", "text", "none", "scalar", None),
    # --- proximity: the NAME columns create graph edges ------------------
    "nearest_airport": ("Name of the CLOSEST airport.", "Single-valued. A farther airport is alternate_airport.",
                        "text", "none", "scalar", "nearest_airport"),
    "airport_km": ("Road distance to the nearest airport, in KILOMETRES.",
                   "NOT a duration. '4 hours' is not 4 km.", "quantity", "distance", "scalar", None),
    "airport_drive_time": ("Driving time to the nearest airport.", "NOT a distance.",
                           "quantity", "duration", "scalar", None),
    "nearest_railhead": ("Name of the CLOSEST railway station.", "Single-valued.",
                         "text", "none", "scalar", "nearest_railhead"),
    "railhead_km": ("Road distance to the railhead, in KILOMETRES.", "NOT a duration.",
                    "quantity", "distance", "scalar", None),
    "railhead_drive_time": ("Driving time to the railhead.", "NOT a distance.",
                            "quantity", "duration", "scalar", None),
    "nearest_gate": ("Name of the CLOSEST park entry gate.", "Single-valued.",
                     "text", "none", "scalar", "nearest_gate"),
    "gate_km": ("Distance to the gate, in KILOMETRES.", "NOT a duration.",
                "quantity", "distance", "scalar", None),
    "gate_drive_time": ("Driving time to the gate.", "NOT a distance.",
                        "quantity", "duration", "scalar", None),
    "nearest_park": ("Name of the CLOSEST national park or reserve.", "Single-valued.",
                     "text", "none", "scalar", "nearest_park"),
    "park_km": ("Distance to the NEAREST park, in KILOMETRES.",
                "NOT the distance to some other park. Use nearby_destination_km for those.",
                "quantity", "distance", "scalar", None),
    "park_drive_time": ("Driving time to the nearest park.", "NOT a distance.",
                        "quantity", "duration", "scalar", None),
    "alternate_airport": ("A farther airport the page also names.",
                          "NOT the nearest one.", "text", "none", "multi", "alternate_airport"),
    "nearby_destination_km": ("Distance to a named place that is NOT the nearest of its kind.",
                              "", "quantity", "distance", "multi", None),
    # --- classification -------------------------------------------------
    "star_rating": ("OFFICIAL classification from a government tourism body (HRACC in India).",
                    "NOT a guest review score. TripAdvisor/Google scores are review_rating.",
                    "number", "count", "scalar", None),
    "review_rating": ("Guest review average. Record the source in scope_key 'source'.",
                      "NOT an official star classification.", "number", "count", "multi", None),
    "heritage_grade": ("Official heritage classification.", "", "text", "none", "scalar", None),
    "property_type": ("Fort, lodge, camp, palace, resort, homestay ...", "",
                      "text", "none", "scalar", None),
    "group_affiliation": ("Chain, group or collection it belongs to.", "",
                          "text", "none", "multi", "member_of"),
    # --- descriptive (multi by nature) ----------------------------------
    "usp": ("The stated selling proposition.", "", "text", "none", "multi", None),
    "ideal_for": ("A traveller type it suits.", "One fact per type.", "text", "none", "multi", None),
    "activities": ("An activity offered.", "One per activity. Must be STATED, not inferred from a photo.",
                   "text", "none", "multi", None),
    "dining": ("A dining venue or offering.", "One per venue.", "text", "none", "multi", None),
    "naturalists": ("Naturalist or guide provision.", "", "text", "none", "multi", None),
    "child_policy": ("Rules about children.", "", "text", "none", "multi", None),
    "pet_policy": ("Rules about pets.", "", "text", "none", "multi", None),
    "accessibility": ("An access provision or limitation.", "", "text", "none", "multi", None),
    "altitude_m": ("Altitude above sea level, in metres.", "", "quantity", "distance", "scalar", None),
    "contact_email": ("Contact email printed on the page.", "", "text", "none", "multi", None),
    "conservation": ("A conservation or sustainability claim.", "", "text", "none", "multi", None),
}

COLS = ("definition", "not_this", "value_type", "unit_kind", "cardinality", "relation_kind")


@dataclasses.dataclass(frozen=True)
class Label:
    key: str
    definition: str = ""
    not_this: str = ""
    value_type: str = "text"
    unit_kind: str = "none"
    cardinality: str = "multi"
    relation_kind: str | None = None
    status: str = "approved"
    alias_of: str | None = None


class Vocabulary(dict):
    """{key: Label} with the views the rules need."""

    @property
    def approved(self) -> dict[str, Label]:
        return {k: v for k, v in self.items() if v.status == "approved"}

    def _where(self, **kw) -> set[str]:
        return {k for k, v in self.approved.items()
                if all(getattr(v, a) == b for a, b in kw.items())}

    @property
    def scalar_keys(self) -> set[str]:
        return self._where(cardinality="scalar")

    @property
    def boolean_keys(self) -> set[str]:
        return self._where(value_type="boolean")

    @property
    def distance_keys(self) -> set[str]:
        return self._where(unit_kind="distance")

    @property
    def duration_keys(self) -> set[str]:
        return self._where(unit_kind="duration")

    @property
    def numeric_keys(self) -> set[str]:
        return {k for k, v in self.approved.items()
                if v.value_type in ("number", "money", "quantity")}

    @property
    def relation_keys(self) -> dict[str, str]:
        return {k: v.relation_kind for k, v in self.approved.items() if v.relation_kind}

    @property
    def aliases(self) -> dict[str, str]:
        """{alias key: canonical key}. Readers invent many names for one idea --
        room_feature / room_features / interior_feature. Folding them here means
        the fact is kept under the canonical label instead of being held."""
        return {k: v.alias_of for k, v in self.items() if v.alias_of}

    def resolve(self, key: str) -> str:
        """Canonical form of a key, following one alias hop."""
        lab = self.get(key)
        return lab.alias_of if lab and lab.alias_of else key

    def sibling(self, key: str, unit_kind: str) -> str | None:
        """The distance/duration partner of a relation key: nearest_airport -> airport_km."""
        stem = key.replace("nearest_", "")
        for cand in (f"{stem}_km", f"{stem}_drive_time"):
            v = self.get(cand)
            if v and v.unit_kind == unit_kind:
                return cand
        return None


def seed_if_empty(cur) -> int:
    """Write the starting set once. After that the table is authoritative."""
    cur.execute("select count(*) from attribute_vocabulary")
    if cur.fetchone()[0]:
        return 0
    rows = [(k, *vals, "approved") for k, vals in SEED.items()]
    cur.executemany(
        "insert into attribute_vocabulary "
        "(key,definition,not_this,value_type,unit_kind,cardinality,relation_kind,status) "
        "values (%s,%s,%s,%s,%s,%s,%s,%s) on conflict (key) do nothing", rows)
    return len(rows)


def load(cur=None) -> Vocabulary:
    """Read the vocabulary from the database. Seeds an empty table first."""
    def _read(c):
        seed_if_empty(c)
        c.execute("select key,definition,not_this,value_type,unit_kind,cardinality,"
                  "relation_kind,status,alias_of from attribute_vocabulary")
        return Vocabulary({r[0]: Label(*r) for r in c.fetchall()})

    if cur is not None:
        return _read(cur)
    with db.connect() as conn, conn.cursor() as c:
        v = _read(c)
        conn.commit()
        return v


def record_proposal(cur, key: str) -> None:
    """A reader asked for a label that does not exist. Count it, hold it."""
    cur.execute(
        "insert into attribute_vocabulary (key,status,proposed_count) values (%s,'proposed',1) "
        "on conflict (key) do update set proposed_count = attribute_vocabulary.proposed_count + 1",
        (key,))


def demo() -> None:
    v = Vocabulary({k: Label(k, *vals, "approved") for k, vals in SEED.items()})
    assert "room_count" in v.scalar_keys and "activities" not in v.scalar_keys
    assert "has_pool" in v.boolean_keys
    assert "airport_km" in v.distance_keys and "airport_drive_time" in v.duration_keys
    assert v.relation_keys["nearest_airport"] == "nearest_airport"
    assert v.sibling("nearest_airport", "distance") == "airport_km"
    assert v.sibling("nearest_airport", "duration") == "airport_drive_time"
    print(f"vocab OK - {len(v)} labels, {len(v.scalar_keys)} scalar, "
          f"{len(v.relation_keys)} relation-forming, {len(v.numeric_keys)} numeric")


if __name__ == "__main__":
    demo()
