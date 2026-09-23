"""Labs: the clinical laboratories that run monitoring blood tests for patients."""

from datetime import timedelta

from population.core import AS_OF, DIVISIONS, PLACE_ENDS, PLACE_STEMS, STATES, Entity, People, ascii_slug, register

KINDS = {  # type: (share, name endings)
    "national_reference_lab": (0.07, ["Laboratories", "Diagnostics"]),
    "regional_lab": (0.33, ["Regional Laboratory", "Clinical Laboratories", "Pathology Services"]),
    "hospital_lab": (0.35, ["Laboratory"]),
    "physician_office_lab": (0.25, ["Office Laboratory"]),
}


@register
class Labs(Entity):
    name = "labs"
    id_prefix = "PLAB"
    default_count = 60
    requires = ("offices",)
    references = {"office_id": "offices", "quality_flags[].of": "labs"}
    must_match = {"state": ["office_id", "state"]}
    notice = ("FICTITIOUS. Generated clinical laboratories that do not exist. CLIA-shaped certificate numbers begin with "
              "99D, a state code that is never issued. Phones use 555-01xx; domains use .example.")
    usage = ("Laboratories that run the monitoring blood tests in the label (complete blood count with lymphocyte count, "
             "liver tests and renal function). National labs serve every state; a regional lab serves its census "
             "division; hospital and physician-office labs belong to a generated office (office_id) and serve that "
             "state. results_delivery says how results reach the ordering office.")
    flags = {
        "duplicate": "A second record for the same lab (same CLIA number, name variant); 'of' is the original.",
        "certificate_lapsed": "The CLIA certificate lapsed on certificate_lapsed_on, yet results after that date exist.",
    }

    def generate(self, ctx, count):
        rng = ctx.rng(self.name)
        people = People(ctx, self.name)
        offices = [o for o in ctx.records("offices") if o["status"] == "active" and not o["quality_flags"]]
        systems = [o for o in offices if o["type"] in ("health_system", "academic_medical_center")]
        groups = [o for o in offices if o["type"] == "multispecialty_group"]
        division_of = {s: d for d, states in DIVISIONS.items() for s in states}
        used_clia, names, out = set(), set(), []

        def clia():
            while True:
                c = f"99D{rng.randrange(10 ** 7):07d}"
                if c not in used_clia:
                    used_clia.add(c)
                    return c

        def place():
            while True:
                p = rng.choice(PLACE_STEMS) + rng.choice(PLACE_ENDS)
                if p not in names:
                    names.add(p)
                    return p

        plan = []
        for kind, (share, _) in KINDS.items():
            plan += [kind] * max(1, round(count * share))
        plan = (plan * 2)[:count]
        rng.shuffle(plan)
        lapsed_done = False
        for i, kind in enumerate(plan):
            office = None
            if kind == "hospital_lab" and systems:
                office = systems.pop(rng.randrange(len(systems)))
            elif kind == "physician_office_lab" and groups:
                office = groups.pop(rng.randrange(len(groups)))
            elif kind in ("hospital_lab", "physician_office_lab"):
                kind = "regional_lab"
            if office:
                name, state = f"{office['name']} {KINDS[kind][1][0]}", office["state"]
            else:
                name = f"{place()} {rng.choice(KINDS[kind][1])}"
                states = list(STATES)
                state = rng.choices(states, weights=[STATES[s][0] for s in states])[0]
            served = (sorted(STATES) if kind == "national_reference_lab" else
                      sorted(DIVISIONS[division_of[state]]) if kind == "regional_lab" else [state])
            phone = people.phone(state)
            rec = {"id": self.make_id(i), "name": name, "type": kind, "office_id": office["id"] if office else None,
                   "clia": clia(), "city": office["city"] if office else people.city(), "state": state,
                   "zip": office["zip"] if office else people.zip(state), "phone": phone,
                   "email_domain": f"{ascii_slug(name)}.example", "states_served": served,
                   "patient_service_centers": {"national_reference_lab": rng.randrange(400, 1500), "regional_lab": rng.randrange(8, 60)}.get(kind, 1),
                   "results_delivery": sorted(rng.sample(["hl7_v2_feed", "portal", "fax"], k=rng.randint(1, 3))),
                   "certificate_lapsed_on": None, "quality_flags": []}
            if kind == "regional_lab" and not lapsed_done:
                rec["certificate_lapsed_on"] = str(AS_OF - timedelta(days=rng.randrange(60, 200)))
                rec["quality_flags"].append({"type": "certificate_lapsed"})
                lapsed_done = True
            out.append(rec)
        # One duplicate: the same lab entered twice under a name variant.
        src = next(r for r in out if r["type"] == "national_reference_lab")
        last = max(i for i, r in enumerate(out) if r is not src and not r["quality_flags"])
        out[last] = dict(src, id=out[last]["id"], name=src["name"].replace("Laboratories", "Labs").replace("Diagnostics", "Diagnostic Services"),
                       quality_flags=[{"type": "duplicate", "of": src["id"]}])
        return out
