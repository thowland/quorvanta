"""HCPs: prescribers and other clinicians at the generated offices."""

from datetime import timedelta

from population.core import AS_OF, Entity, NpiAllocator, People, register

CREDENTIALS = {"MD": 60, "DO": 15, "NP": 15, "PA-C": 10}
SPECIALTIES = {"Neurology": 72, "Internal medicine": 8, "Family medicine": 8, "Physical medicine and rehabilitation": 4,
               "Neuro-ophthalmology": 3, "Pediatric neurology": 5}
SEGMENTS = {"A": 10, "B": 25, "C": 35, "D": 30}
NICKNAMES = {"William": "Bill", "Robert": "Bob", "Elizabeth": "Liz", "Katherine": "Kate", "Michael": "Mike",
             "Jennifer": "Jen", "Christopher": "Chris", "Margaret": "Peggy", "Richard": "Rick", "Susan": "Sue"}


@register
class Hcps(Entity):
    name = "hcps"
    id_prefix = "PHCP"
    default_count = 600
    requires = ("offices",)
    references = {"primary_office_id": "offices", "other_office_ids[]": "offices",
                  "previous_office_id": "offices", "quality_flags[].of": "hcps"}
    must_match = {"state": ["primary_office_id", "state"], "phone": ["primary_office_id", "phone"]}
    notice = ("FICTITIOUS. Generated clinicians who do not exist. Names pair a Faker first name with a double-barrelled "
              "surname and never repeat a core cast member. NPI-shaped ids begin with 91 (the core cast uses 90), which the "
              "national registry never assigns, and carry a valid check digit. Phones use 555-01xx; emails use .example.")
    usage = ("A prescriber universe for targeting, segmentation, territory alignment and master-data testing, alongside the "
             "30 hand-built HCPs in crm/field-force.json. state is the primary office's state. A duplicate shares its "
             "original's NPI, which is how a matching tool should find it.")
    flags = {
        "duplicate": "A second record for the same clinician (same NPI, name variant); 'of' is the original.",
        "moved": "Changed practice; previous_office_id holds the old one and moved_on the date.",
        "npi_deactivated": "The NPI was deactivated on deactivated_on; the record is still in the file.",
        "retired_still_targeted": "Retired, but still carries a segment and a call plan.",
    }

    def generate(self, ctx, count):
        rng = ctx.rng(self.name)
        people = People(ctx, self.name)
        npis = NpiAllocator(ctx.rng(self.name + ":npi"))
        offices = [o for o in ctx.records("offices") if o["type"] != "health_system" and not o["quality_flags"]]
        by_state = {}
        for o in offices:
            by_state.setdefault(o["state"], []).append(o)
        out = []
        while len(out) < count:
            i = len(out)
            if rng.random() < 0.02 and len(out) > 20:
                src = rng.choice([h for h in out if not h["quality_flags"]])
                first = NICKNAMES.get(src["first_name"], src["first_name"][0] + ".")
                last = rng.choice([src["last_name"].replace("-", " "), src["last_name"].split("-")[0]])
                out.append(dict(src, id=self.make_id(i), first_name=first, last_name=last,
                                quality_flags=[{"type": "duplicate", "of": src["id"]}]))
                continue
            office = rng.choice(offices)
            first, last, _ = people.person()
            cred = rng.choices(list(CREDENTIALS), weights=list(CREDENTIALS.values()))[0]
            spec = rng.choices(list(SPECIALTIES), weights=list(SPECIALTIES.values()))[0]
            seg = rng.choices(list(SEGMENTS), weights=list(SEGMENTS.values()))[0]
            others = [o["id"] for o in rng.sample(by_state[office["state"]], k=min(len(by_state[office["state"]]) - 1, rng.choice([0, 0, 0, 1, 2])))
                      if o["id"] != office["id"]]
            rec = {"id": self.make_id(i), "npi": npis.next(), "first_name": first, "last_name": last,
                   "credential": cred, "specialty": spec, "primary_office_id": office["id"], "other_office_ids": others,
                   "state": office["state"], "phone": office["phone"],
                   "email": people.email(first, last, office["email_domain"]),
                   "consent": {"approved_email": rng.random() < 0.55}, "no_see": rng.random() < 0.05,
                   "segment": seg, "call_plan_per_quarter": {"A": 6, "B": 4, "C": 2, "D": 0}[seg],
                   "status": "active", "previous_office_id": None, "moved_on": None, "deactivated_on": None,
                   "quality_flags": []}
            if rec["no_see"]:
                rec["call_plan_per_quarter"] = 0
            roll = rng.random()
            if roll < 0.03 and len(by_state[office["state"]]) > 1:
                prev = rng.choice([o for o in by_state[office["state"]] if o["id"] != office["id"]])
                rec["previous_office_id"] = prev["id"]
                rec["moved_on"] = str(AS_OF - timedelta(days=rng.randrange(20, 300)))
                rec["quality_flags"].append({"type": "moved"})
            elif roll < 0.04:
                rec["status"] = "npi_deactivated"
                rec["deactivated_on"] = str(AS_OF - timedelta(days=rng.randrange(10, 500)))
                rec["quality_flags"].append({"type": "npi_deactivated"})
            elif roll < 0.05 and seg != "D":
                rec["status"] = "retired"
                rec["quality_flags"].append({"type": "retired_still_targeted"})
            out.append(rec)
        return out
