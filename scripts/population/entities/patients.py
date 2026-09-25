"""Patients: support-program identities, without shipments or claims."""

import json
from datetime import date, timedelta

from population.core import AS_OF, SRC, Entity, People, register

INSURANCE = {"commercial": 55, "medicare": 25, "medicaid": 12, "tricare": 2, "va": 1, "none": 5}
LANGUAGES = {"English": 85, "Spanish": 12, "Vietnamese": 1, "Polish": 1, "Portuguese": 1}
RELATIONSHIPS = ["spouse", "partner", "adult child", "parent", "sibling", "friend"]
# Why an enrolled patient has no first fill. coverage_pending also covers first fills that have not shipped yet.
NOT_STARTED = ["coverage_pending", "cost", "patient_undecided", "unreachable", "prescriber_canceled"]
DISCONTINUATION = ["gastrointestinal events", "flushing", "lymphopenia", "patient decision", "insurance", "other"]
# Plans in payer/plans.json that only make sense in some states: the Medicaid managed-care plans
# are state programs and the Halverson plan covers that health system's own employees.
PLAN_STATES = {"Lakeshore Community Care (Medicaid)": {"NY"}, "Tallgrass Community Health (Medicaid)": {"OH"},
               "Halverson Health Employee Plan": {"IL", "IN", "WI", "MI"}}


@register
class Patients(Entity):
    name = "patients"
    id_prefix = "PPAT"
    default_count = 500
    requires = ("hcps",)
    references = {"prescriber_id": "hcps", "quality_flags[].of": "patients"}
    notice = ("FICTITIOUS. Generated patients who do not exist. Names never repeat a core cast member; cities are Faker "
              "inventions; phone numbers use the reserved 555-01xx range.")
    usage = ("Support-program identities for identity-verification, matching and load testing. They carry insurance and a "
             "prescriber but no shipments, claims or case statuses; only the 29 hand-built cases in "
             "test-design/ps-cases.json have those. Plan names come from payer/plans.json, limited by state where a "
             "plan is regional; a Medicaid patient in a state with no pack plan gets '<state> Medicaid (fee-for-service)', "
             "which names the public program only. Patients are adults unless flagged minor. therapy.started_on is the ship "
             "date of the first fill (refills.json has every fill); for some it records when and why treatment stopped, "
             "and for enrolled patients with no first fill, why not and whether the prescriber canceled the prescription. "
             "communications holds the Start Form choices that texting depends on: contact_consent (E2) and text_reminders "
             "(C5); the text opt-in itself is in sms-messages.json. lab-results follow therapy.")
    flags = {
        "same_name": "Shares first and last name with 'of', with a different date of birth and ZIP code.",
        "same_name_and_dob": "Shares name and date of birth with 'of'; only the ZIP code tells them apart.",
        "duplicate": "The same person entered twice, with the hyphen dropped from the surname; 'of' is the original.",
        "moved": "Changed address; previous_zip holds the old ZIP code.",
        "minor": "Under 18 on the as_of date. The program is for adults (PGM-GEN.1) and a minor caller stops case discussion (ESC-08).",
    }

    def generate(self, ctx, count):
        rng = ctx.rng(self.name)
        people = People(ctx, self.name)
        plans = json.loads((SRC / "payer/plans.json").read_text())["plans"]
        plan_names = {t: [p["name"] for p in plans if p["type"] == t] for t in ("commercial", "medicare", "medicaid", "tricare")}
        hcps = [h for h in ctx.records("hcps") if h["status"] == "active" and not h["quality_flags"]
                and h["specialty"] != "Pediatric neurology"]
        by_state = {}
        for h in hcps:
            by_state.setdefault(h["state"], []).append(h)

        def dob(min_age, max_age):
            age = rng.randint(min_age, max_age)
            # Between 1 and 364 days before the as_of date, `age` years back: exactly `age` on as_of.
            return str(date(AS_OF.year - age, AS_OF.month, AS_OF.day) - timedelta(days=rng.randrange(1, 365)))

        out = []
        while len(out) < count:
            i = len(out)
            roll = rng.random()
            if roll < 0.06 and len(out) > 20:
                src = rng.choice([p for p in out if not p["quality_flags"]])
                kind = "same_name" if roll < 0.035 else "same_name_and_dob" if roll < 0.045 else "duplicate"
                rec = self._patient(i, rng, people, hcps, by_state, plan_names, dob)
                rec["first_name"], rec["last_name"] = src["first_name"], src["last_name"]
                if kind == "same_name_and_dob":
                    rec["dob"] = src["dob"]
                if kind == "duplicate":
                    rec = dict(src, id=self.make_id(i), last_name=src["last_name"].replace("-", " "))
                rec["quality_flags"] = [{"type": kind, "of": src["id"]}]
                out.append(rec)
                continue
            rec = self._patient(i, rng, people, hcps, by_state, plan_names, dob)
            if rng.random() < 0.02:
                rec["previous_zip"] = people.zip(rec["state"])
                rec["quality_flags"].append({"type": "moved"})
            elif rng.random() < 0.01:
                rec["dob"] = dob(15, 17)
                rec["quality_flags"].append({"type": "minor"})
            out.append(rec)
        self._journeys(ctx, out)
        return out

    def _journeys(self, ctx, out):
        """Therapy and contact choices, from their own random stream so they can change without renaming anyone."""
        rng = ctx.rng(self.name + ":journey")
        for rec in out:
            if any(f["type"] == "duplicate" for f in rec["quality_flags"]):
                continue
            th, comms = rec["therapy"], rec["communications"]
            if rec["program"]["status"] != "enrolled":
                continue
            enrolled_on = date.fromisoformat(rec["program"]["enrolled_on"])
            comms["contact_consent"] = rng.random() < 0.92
            comms["text_reminders"] = comms["contact_consent"] and rng.random() < 0.55
            if rng.random() < 0.12:
                reason = rng.choices(NOT_STARTED, weights=[30, 20, 20, 15, 15])[0]
                th["not_started_reason"] = reason
                if reason == "prescriber_canceled":
                    canceled = enrolled_on + timedelta(days=rng.randrange(18, 60))
                    if canceled <= AS_OF:
                        th["prescription_canceled_on"] = str(canceled)
                    else:
                        th["not_started_reason"] = "coverage_pending"
                continue
            # Days from enrollment to the first fill: most within two weeks, some after a prior authorization.
            wait = rng.choices([rng.randrange(5, 14), rng.randrange(14, 31), rng.randrange(31, 61)], weights=[45, 45, 10])[0]
            first = enrolled_on + timedelta(days=wait)
            if first > AS_OF:
                th["not_started_reason"] = "coverage_pending"
                continue
            th.update(status="on_therapy", started_on=str(first))
            days = (AS_OF - first).days
            if days > 120 and rng.random() < 0.10:
                stop = first + timedelta(days=rng.randrange(60, days))
                reason = rng.choices(DISCONTINUATION, weights=[25, 20, 30, 15, 10, 10])[0]
                th.update(status="discontinued", discontinued_on=str(stop), discontinued_reason=reason)
        # A duplicate record copies its original's journey, as a second entry for the same person would.
        by_id = {r["id"]: r for r in out}
        for rec in out:
            dup = next((f["of"] for f in rec["quality_flags"] if f["type"] == "duplicate"), None)
            if dup:
                rec["therapy"] = dict(by_id[dup]["therapy"])
                rec["communications"] = dict(by_id[dup]["communications"])

    def _patient(self, i, rng, people, hcps, by_state, plan_names, dob):
        first, last, sex = people.person()
        state = people.state()
        prescriber = rng.choice(by_state.get(state) or hcps)
        kind = rng.choices(list(INSURANCE), weights=list(INSURANCE.values()))[0]

        def pick(t):
            options = [n for n in plan_names[t] if state in PLAN_STATES.get(n, {state})]
            return rng.choice(options) if options else f"{state} Medicaid (fee-for-service)"
        plan = pick(kind) if kind in plan_names else ("VA health care" if kind == "va" else None)
        secondary = None
        if kind == "commercial" and rng.random() < 0.03:
            secondary = pick("medicaid")
        contacts = []
        if rng.random() < 0.12:
            cf, cl, _ = people.person()
            contacts.append({"name": f"{cf} {cl}", "relationship": rng.choice(RELATIONSHIPS),
                             "scope": rng.choice(["status", "full"])})
        rep = None
        if rng.random() < 0.02:
            rf, rl, _ = people.person()
            rep = {"name": f"{rf} {rl}", "relationship": "adult child", "document": "power of attorney"}
        enrolled = rng.random() < 0.85
        enrolled_on = AS_OF - timedelta(days=rng.randrange(1, 900)) if enrolled else None
        return {
            "id": self.make_id(i), "first_name": first, "last_name": last, "sex": sex, "dob": dob(18, 80),
            "city": people.city(), "state": state, "zip": people.zip(state), "previous_zip": None,
            "phone": people.phone(state), "language": rng.choices(list(LANGUAGES), weights=list(LANGUAGES.values()))[0],
            "prescriber_id": prescriber["id"],
            "insurance": {"type": kind, "plan_name": plan, "secondary_plan_name": secondary,
                          "government_program": kind in ("medicare", "medicaid", "tricare", "va") or secondary is not None},
            "program": {"status": "enrolled" if enrolled else rng.choice(["pending", "declined"]),
                        "enrolled_on": str(enrolled_on) if enrolled else None},
            "therapy": {"status": "not_started", "started_on": None, "discontinued_on": None, "discontinued_reason": None,
                        "not_started_reason": None, "prescription_canceled_on": None},
            "communications": {"contact_consent": False, "text_reminders": False},
            "authorized_contacts": contacts, "legal_representative": rep, "quality_flags": [],
        }
