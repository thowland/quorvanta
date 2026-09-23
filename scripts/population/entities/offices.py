"""Offices: practices, clinics and the health systems some of them belong to."""

from datetime import timedelta

from population.core import AS_OF, PLACE_ENDS, PLACE_STEMS, Entity, People, ascii_slug, register

TYPES = {  # type: (weight, name endings)
    "private_practice": (45, ["Neurology", "Neurology Associates", "Neurology Clinic", "Neurological Care"]),
    "multispecialty_group": (20, ["Medical Group", "Physicians", "Health Partners"]),
    "academic_medical_center": (6, ["Neuroscience Institute", "Neurology Center"]),
    "community_health_center": (10, ["Community Health Center", "Family Health Center"]),
}


@register
class Offices(Entity):
    name = "offices"
    id_prefix = "POFC"
    default_count = 150
    references = {"parent_id": "offices", "quality_flags[].of": "offices"}
    must_match = {"state": ["parent_id", "state"]}
    notice = ("FICTITIOUS. Generated offices, clinics and health systems that do not exist. Names are built from invented "
              "place-words; cities are Faker inventions with real state codes and ZIP codes; phone numbers use the reserved "
              "555-01xx range and web domains use .example.")
    usage = ("Accounts for CRM, account-hierarchy and master-data testing. A health_system record has sites: offices whose "
             "parent_id points to it, in the same state. quality_flags marks deliberate data problems (see the legend); "
             "a matching or cleansing tool should find them.")
    flags = {
        "duplicate": "A second record for the same office, with a name variant and the same phone; 'of' is the original.",
        "closed": "The office has closed (status closed, closed_on set); HCP records may still point to it.",
    }

    def generate(self, ctx, count):
        rng = ctx.rng(self.name)
        people = People(ctx, self.name)
        names, out = set(), []

        def place():
            while True:
                p = rng.choice(PLACE_STEMS) + rng.choice(PLACE_ENDS)
                if p not in names:
                    return p

        def base(i, name, typ, state, parent=None):
            names.add(name.split()[0])
            phone = people.phone(state)
            return {"id": self.make_id(i), "name": name, "type": typ, "parent_id": parent, "city": people.city(),
                    "state": state, "zip": people.zip(state), "phone": phone,
                    "fax": phone[:-2] + f"{(int(phone[-2:]) + 1) % 100:02d}",
                    "email_domain": f"{ascii_slug(name)}.example", "quorvantaconnect_portal": rng.random() < 0.4,
                    "status": "active", "closed_on": None, "quality_flags": []}

        systems = max(1, count // 12)
        for i in range(systems):
            p = place()
            out.append(base(i, f"{p} Health", "health_system", people.state()))
        while len(out) < count:
            i = len(out)
            roll = rng.random()
            if roll < 0.02 and len(out) > systems + 5:
                src = rng.choice([o for o in out[systems:] if not o["quality_flags"]])
                variant = (src["name"].replace("Associates", "Assoc.").replace(" and ", " & ")
                           if "Associates" in src["name"] else src["name"] + " LLC")
                dup = dict(src, id=self.make_id(i), name=variant, email_domain=src["email_domain"],
                           quality_flags=[{"type": "duplicate", "of": src["id"]}])
                out.append(dup)
                continue
            if roll < 0.25:
                parent = rng.choice(out[:systems])
                site = base(i, f"{parent['name']} Neurology, {people.city()}", "health_system_site", parent["state"], parent["id"])
                out.append(site)
                continue
            typ = rng.choices(list(TYPES), weights=[t[0] for t in TYPES.values()])[0]
            rec = base(i, f"{place()} {rng.choice(TYPES[typ][1])}", typ, people.state())
            if rng.random() < 0.03:
                rec["status"] = "closed"
                rec["closed_on"] = str(AS_OF - timedelta(days=rng.randrange(30, 400)))
                rec["quality_flags"].append({"type": "closed"})
            out.append(rec)
        return out
