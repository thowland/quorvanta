"""Office staff: office managers, prior authorization coordinators, nurses and billing staff."""

from datetime import timedelta

from population.core import AS_OF, Entity, People, register

ROLES = {"office_manager": 30, "prior_authorization_coordinator": 25, "nurse": 20, "medical_assistant": 15, "billing_specialist": 10}
DUTIES = {
    "office_manager": ["benefits_verification", "start_forms", "refills"],
    "prior_authorization_coordinator": ["prior_authorization", "appeals", "benefits_verification"],
    "nurse": ["start_forms", "refills", "patient_education"],
    "medical_assistant": ["start_forms", "refills"],
    "billing_specialist": ["benefits_verification", "copay_questions"],
}


@register
class OfficeStaff(Entity):
    name = "office-staff"
    id_prefix = "POFS"
    default_count = 250
    requires = ("offices",)
    references = {"office_ids[]": "offices", "quality_flags[].of": "office-staff"}
    notice = ("FICTITIOUS. Generated office staff who do not exist. Phones are the office's 555-01xx number with an "
              "extension; emails use .example.")
    usage = ("The people who deal with QuorvantaConnect for a practice: they send Start Forms, prepare prior "
             "authorizations and receive benefits letters. They are not prescribers and cannot sign the Start Form's "
             "prescriber section. Every open office gets an office manager before any office gets a second staff member.")
    flags = {
        "duplicate": "A second record for the same person, with a name variant; 'of' is the original.",
        "departed": "Has left the practice (status departed, departed_on set) but is still listed as a contact.",
        "multi_office": "Works for more than one office, for example through a shared billing service. Not an error.",
    }

    def generate(self, ctx, count):
        rng = ctx.rng(self.name)
        people = People(ctx, self.name)
        offices = [o for o in ctx.records("offices") if o["type"] != "health_system" and o["status"] == "active"
                   and not o["quality_flags"]]
        out = []

        def person(i, office, role):
            first, last, _ = people.person()
            rec = {"id": self.make_id(i), "first_name": first, "last_name": last, "role": role,
                   "office_ids": [office["id"]], "phone": f"{office['phone']} x{rng.randrange(200, 400)}",
                   "email": people.email(first, last, office["email_domain"]),
                   "duties": DUTIES[role], "quorvantaconnect_portal": office["quorvantaconnect_portal"] and rng.random() < 0.8,
                   "status": "active", "departed_on": None, "quality_flags": []}
            return rec

        for office in offices:
            if len(out) >= count:
                break
            out.append(person(len(out), office, "office_manager"))
        while len(out) < count:
            i = len(out)
            if rng.random() < 0.02 and len(out) > 10:
                src = rng.choice([s for s in out if not s["quality_flags"]])
                out.append(dict(src, id=self.make_id(i), last_name=src["last_name"].split("-")[-1],
                                quality_flags=[{"type": "duplicate", "of": src["id"]}]))
                continue
            office = rng.choice(offices)
            role = rng.choices(list(ROLES), weights=list(ROLES.values()))[0]
            rec = person(i, office, role)
            roll = rng.random()
            if roll < 0.05 and role == "billing_specialist":
                extra = rng.choice([o for o in offices if o["id"] != office["id"]])
                rec["office_ids"].append(extra["id"])
                rec["quality_flags"].append({"type": "multi_office"})
            elif roll < 0.08:
                rec["status"] = "departed"
                rec["departed_on"] = str(AS_OF - timedelta(days=rng.randrange(15, 240)))
                rec["quality_flags"].append({"type": "departed"})
            out.append(rec)
        return out
