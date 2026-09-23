"""Registry, fiction-safe helpers and writer for the generated population.

To add an entity type (labs, say), create scripts/population/entities/labs.py:

    from population.core import Entity, register

    @register
    class Labs(Entity):
        name = "labs"                    # the --entity value
        id_prefix = "PLAB"               # record ids are PLAB-00001, PLAB-00002, ...
        default_count = 100
        requires = ("offices",)          # entities whose records this one references
        references = {"office_ids[]": "offices"}   # field -> entity; [] marks a list
        must_match = {"state": ["office_ids[]", "state"]}   # optional: copied fields that must agree
        notice = "FICTITIOUS. ..."
        usage = "..."

        def generate(self, ctx, count):
            offices = ctx.records("offices")
            return [{"id": self.make_id(i), ...} for i in range(count)]

It is picked up automatically. The validator reads each file's header and checks
ids, declared references, must_match fields, quality flags, NPIs, emails, dates
of birth and phones without any change there.
"""

import json
import random
import re
import unicodedata
import zlib
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SRC = ROOT / "sources"
OUT = SRC / "population"
AS_OF = date(2026, 9, 22)

REGISTRY = {}


def register(cls):
    REGISTRY[cls.name] = cls()
    return cls


class Entity:
    name = ""
    id_prefix = ""
    default_count = 100
    requires = ()
    references = {}
    must_match = {}     # field -> [reference field, field on the referenced record] that it must equal
    notice = ""
    usage = ""
    flags = {}          # quality flag type -> meaning, written to the file as a legend
    patterns = {}       # optional: domain pattern type -> meaning (clinical or business, not data errors)
    header = {}         # optional: extra header content, such as a code catalog
    count_means = "records"   # what --count sets, if not the number of records

    @property
    def path(self):
        return OUT / f"{self.name}.json"

    def make_id(self, i):
        return f"{self.id_prefix}-{i + 1:05d}"

    def generate(self, ctx, count):
        raise NotImplementedError


# ---- geography -----------------------------------------------------------------
# Rough population weights and one or more real area codes per state. Phone numbers
# are always (area code) 555-01xx, the range reserved for fiction.
# US census divisions, for labs and other services with a regional footprint.
DIVISIONS = {
    "New England": ["CT", "ME", "MA", "NH", "RI", "VT"], "Mid-Atlantic": ["NJ", "NY", "PA"],
    "East North Central": ["IL", "IN", "MI", "OH", "WI"], "West North Central": ["IA", "KS", "MN", "MO", "NE", "ND", "SD"],
    "South Atlantic": ["DE", "DC", "FL", "GA", "MD", "NC", "SC", "VA", "WV"], "East South Central": ["AL", "KY", "MS", "TN"],
    "West South Central": ["AR", "LA", "OK", "TX"], "Mountain": ["AZ", "CO", "ID", "MT", "NV", "NM", "UT", "WY"],
    "Pacific": ["AK", "CA", "HI", "OR", "WA"],
}

STATES = {
    "AL": (5.1, ["205"]), "AK": (0.7, ["907"]), "AZ": (7.4, ["602", "520"]), "AR": (3.0, ["501"]),
    "CA": (39.0, ["213", "415", "619", "916"]), "CO": (5.9, ["303"]), "CT": (3.6, ["203"]), "DE": (1.0, ["302"]),
    "DC": (0.7, ["202"]), "FL": (22.0, ["305", "813", "407"]), "GA": (11.0, ["404", "912"]), "HI": (1.4, ["808"]),
    "ID": (1.9, ["208"]), "IL": (12.5, ["312", "217"]), "IN": (6.8, ["317"]), "IA": (3.2, ["515"]),
    "KS": (2.9, ["316"]), "KY": (4.5, ["502"]), "LA": (4.6, ["504", "225"]), "ME": (1.4, ["207"]),
    "MD": (6.2, ["410"]), "MA": (7.0, ["617", "413"]), "MI": (10.0, ["313", "616"]), "MN": (5.7, ["612"]),
    "MS": (2.9, ["601"]), "MO": (6.2, ["314", "816"]), "MT": (1.1, ["406"]), "NE": (2.0, ["402"]),
    "NV": (3.2, ["702"]), "NH": (1.4, ["603"]), "NJ": (9.3, ["201", "609"]), "NM": (2.1, ["505"]),
    "NY": (20.0, ["212", "518", "716"]), "NC": (10.8, ["919", "704"]), "ND": (0.8, ["701"]), "OH": (11.8, ["614", "216"]),
    "OK": (4.0, ["405"]), "OR": (4.2, ["503"]), "PA": (13.0, ["215", "412"]), "RI": (1.1, ["401"]),
    "SC": (5.3, ["803"]), "SD": (0.9, ["605"]), "TN": (7.0, ["615", "901"]), "TX": (30.0, ["713", "214", "512"]),
    "UT": (3.4, ["801"]), "VT": (0.6, ["802"]), "VA": (8.7, ["804", "703"]), "WA": (7.8, ["206", "509"]),
    "WV": (1.8, ["304"]), "WI": (5.9, ["414", "608"]), "WY": (0.6, ["307"]),
}

# Surname stock: Latin-script Faker locales, so double-barrelled names mix origins
# the way the hand-written cast does.
SURNAME_LOCALES = ["en_US", "es_MX", "en_GB", "pl_PL", "it_IT", "de_DE", "fr_FR", "pt_BR", "nl_NL",
                   "sv_SE", "fi_FI", "tr_TR", "yo_NG", "zu_ZA", "ga_IE"]

# Invented place-words for practice names. Common stems (Oak, Pine, Maple, Willow, Cedar,
# Stone, Meadow...) are left out because real practices use them.
PLACE_STEMS = ["Alder", "Bittern", "Bramble", "Burdock", "Campion", "Cinder", "Fennel", "Gorse", "Heron",
               "Juniper", "Kestrel", "Larch", "Linden", "Marram", "Nettle", "Otter", "Plover", "Quill",
               "Rowan", "Sable", "Sedge", "Sloe", "Sorrel", "Tansy", "Teasel", "Thistle", "Whin", "Wren", "Yarrow"]
PLACE_ENDS = ["brook", "combe", "crest", "dale", "fell", "ford", "gate", "haven", "hithe", "hollow", "hurst",
              "mere", "moor", "ridge", "shaw", "stead", "vale", "wick", "worth"]


def ascii_slug(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def npi_check(body9):
    total = 0
    for i, d in enumerate(reversed([int(x) for x in "80840" + body9])):
        if i % 2 == 0:
            d = d * 2 - 9 if d > 4 else d * 2
        total += d
    return str((10 - total % 10) % 10)


class Context:
    def __init__(self, seed, faker_module):
        self.seed = seed
        self.Faker = faker_module
        self._records = {}
        self.core_names = self._core_names()

    # Each entity gets its own seeded random source, so regenerating one entity is
    # reproducible whatever the counts of the others.
    def rng(self, entity):
        return random.Random(self.seed * 1_000_003 + zlib.crc32(entity.encode()))

    def faker(self, entity, locale="en_US"):
        f = self.Faker(locale)
        f.seed_instance(self.seed * 7 + zlib.crc32(f"{entity}:{locale}".encode()))
        return f

    def set_records(self, entity, records):
        self._records[entity] = records

    def records(self, entity):
        if entity not in self._records:
            path = OUT / f"{entity}.json"
            if not path.exists():
                raise SystemExit(f"{entity} is needed but {path.relative_to(ROOT)} does not exist; "
                                 f"generate it first or add --with-deps")
            self._records[entity] = json.loads(path.read_text())["records"]
        return self._records[entity]

    @staticmethod
    def _core_names():
        names = set()
        for rel, get in (("crm/field-force.json", lambda d: [f"{h['first_name']} {h['last_name']}" for h in d["hcps"]] + [s["name"] for s in d["staff"]]),
                         ("test-design/ps-cases.json", lambda d: [f"{c['patient']['first_name']} {c['patient']['last_name']}" for c in d["cases"]])):
            path = SRC / rel
            if path.exists():
                names |= set(get(json.loads(path.read_text())))
        return names


class People:
    """Names, contact details and ids that stay inside the pack's fiction ranges."""

    def __init__(self, ctx, entity):
        self.ctx = ctx
        self.rng = ctx.rng(entity + ":people")
        self.first = ctx.faker(entity)
        self.surname_fakers = [ctx.faker(entity, loc) for loc in SURNAME_LOCALES]
        self.used = set(ctx.core_names)

    def surname(self):
        while True:
            name = self.rng.choice(self.surname_fakers).last_name()
            if " " not in name and "'" not in name and len(name) > 2:
                return name

    def person(self, sex=None):
        """A first name and a double-barrelled surname that no core cast member has."""
        while True:
            sex = sex or self.rng.choice(["female", "male"])
            first = self.first.first_name_female() if sex == "female" else self.first.first_name_male()
            a, b = self.surname(), self.surname()
            if a == b:
                continue
            last = f"{a}-{b}"
            if f"{first} {last}" not in self.used:
                self.used.add(f"{first} {last}")
                return first, last, sex

    def state(self):
        states = list(STATES)
        return self.rng.choices(states, weights=[STATES[s][0] for s in states])[0]

    def phone(self, state):
        return f"({self.rng.choice(STATES[state][1])}) 555-01{self.rng.randrange(100):02d}"

    def zip(self, state):
        if state == "DC":
            return f"200{self.rng.randrange(1, 100):02d}"
        return self.first.zipcode_in_state(state)

    def city(self):
        return self.first.city()

    @staticmethod
    def email(first, last, domain):
        return f"{ascii_slug(first)}.{ascii_slug(last)}@{domain}"


class NpiAllocator:
    """10-digit NPI-shaped ids: 9, then 1 (the core cast uses 90...), 7 digits, check digit."""

    def __init__(self, rng):
        self.rng = rng
        self.used = set()

    def next(self):
        while True:
            body = "91" + f"{self.rng.randrange(10 ** 7):07d}"
            if body not in self.used:
                self.used.add(body)
                return body + npi_check(body)


def write(entity, records, ctx, faker_version):
    OUT.mkdir(exist_ok=True)
    doc = {
        "_notice": entity.notice,
        "population_version": "1.0.0",
        "entity": entity.name,
        "generated": {"generator": "scripts/generate_population.py", "faker_version": faker_version,
                      "seed": ctx.seed, "count": len(records), "as_of": str(AS_OF)},
        "usage": entity.usage,
        "id_prefix": entity.id_prefix,
        "references": entity.references,
        "must_match": entity.must_match,
        "quality_flags": entity.flags,
        **({"patterns": entity.patterns} if entity.patterns else {}),
        **entity.header,
        "records": records,
    }
    entity.path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n")
    return entity.path
