"""QuorvantaConnect staff: case managers, nurses, intake coordinators and supervisors, with queues and shifts."""

import json
from datetime import date, timedelta

from population.core import AS_OF, SRC, Entity, People, register

LAUNCH = date(2024, 2, 26)           # QuorvantaConnect opened with commercial availability
DOMAIN = "quorvantaconnect.example"
ZONE = "America/New_York"            # program hours are Eastern Time (PGM-GEN)
PROGRAM_HOURS = ("08:00", "20:00")
WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri"]
SHIFTS = {"early": ("08:00", "16:30"), "late": ("11:30", "20:00")}
# Roster beside the case managers, whose number --count sets.
OTHERS = {"supervisor": 4, "nurse": 8, "intake_coordinator": 4}
QUEUES = {"case_manager": ["case_management"], "nurse": ["nurse_line"], "intake_coordinator": ["intake"],
          "supervisor": ["escalations"]}
DEPARTED = 2                          # case managers who have left but still hold patients (patients.json flags them)


@register
class QcStaff(Entity):
    name = "qc-staff"
    id_prefix = "PSTF"
    default_count = 20
    count_means = "case managers"
    requires = ()
    references = {"supervisor_id": "qc-staff"}
    notice = ("FICTITIOUS. Generated staff of a patient support program that does not exist. Addresses use .example; "
              "staff have no direct phone numbers and are reached through the program line.")
    usage = (f"The QuorvantaConnect roster on the as_of date: case managers (--count sets how many, including the four the "
             "hand-built cases in test-design/ps-cases.json name), nurses (PGM-NURSE), intake coordinators and "
             "supervisors. Each person has a supervisor (supervisors report to none), queues, languages and a weekly "
             f"shift in Eastern Time inside program hours, {PROGRAM_HOURS[0]} to {PROGRAM_HOURS[1]} Monday to Friday; every "
             "program hour is covered by at least one case manager, one nurse and one Spanish-speaking case manager. "
             "Spanish-language patients are assigned a Spanish-speaking case manager; patients in other languages "
             "use an interpreter with any case manager. Staff who have left keep their record, with status left and "
             "left_on. patterns marks the core case managers, who are the same people the hand-built cases name.")
    patterns = {
        "core_cast_member": "The case manager of that name in test-design/ps-cases.json; the same person, not a namesake.",
    }

    def generate(self, ctx, count):
        rng = ctx.rng(self.name)
        people = People(ctx, self.name)
        cases = json.loads((SRC / "test-design/ps-cases.json").read_text())["cases"]
        core = {}
        for c in cases:
            dates = [d for d in (c["bv"]["completed_on"], c["copay"]["enrolled_on"], c["pa"]["submitted_on"],
                                 c["pap"]["applied_on"]) if d] + [s["date"] for s in c["shipments"]]
            m = core.setdefault(c["case_manager"], {"first": min(dates, default=str(AS_OF)), "spanish": False})
            m["first"] = min([m["first"]] + dates)
            m["spanish"] |= c["patient"]["language"] == "Spanish"

        def hired(before=AS_OF):
            span = (before - LAUNCH).days
            return LAUNCH - timedelta(days=rng.randrange(0, 90)) + timedelta(days=rng.randrange(max(span, 1)))

        def person(role, first=None, last=None, spanish=None, shift=None, before=AS_OF):
            if first is None:
                first, last, _ = people.person()
            spanish = rng.random() < 0.25 if spanish is None else spanish
            start, end = SHIFTS[shift or rng.choice(list(SHIFTS))]
            return {"id": None, "first_name": first, "last_name": last, "role": role, "supervisor_id": None,
                    "queues": list(QUEUES[role]) + (["spanish_language"] if spanish and role == "case_manager" else []),
                    "languages": ["English", "Spanish"] if spanish else ["English"],
                    "schedule": {"days": list(WEEKDAYS), "start": start, "end": end, "time_zone": ZONE},
                    "email": People.email(first, last, DOMAIN), "hired_on": str(hired(before)), "status": "active",
                    "left_on": None, "patterns": [], "quality_flags": []}

        out = [person("supervisor", shift=s) for s in ("early", "late", "early", "late")[:OTHERS["supervisor"]]]
        for name, m in sorted(core.items()):
            first, last = name.split(" ", 1)
            rec = person("case_manager", first, last, spanish=m["spanish"], before=date.fromisoformat(m["first"]))
            rec["patterns"].append({"type": "core_cast_member", "of": "case_manager"})
            out.append(rec)
        # Generated case managers: both shifts and Spanish on both, whatever the random draws.
        for i in range(max(count - len(core), 4)):
            out.append(person("case_manager", spanish=True if i < 2 else None, shift=("early", "late")[i % 2]))
        for role in ("nurse", "intake_coordinator"):
            for i in range(OTHERS[role]):
                out.append(person(role, shift=("early", "late")[i % 2]))
        # Two case managers who have since left; their patients have not all been reassigned.
        for rec in rng.sample([r for r in out if r["role"] == "case_manager" and not r["patterns"]
                               and "spanish_language" not in r["queues"]], DEPARTED):
            left = AS_OF - timedelta(days=rng.randrange(20, 120))
            rec.update(status="left", left_on=str(left), hired_on=str(min(date.fromisoformat(rec["hired_on"]), left - timedelta(days=200))))

        for i, rec in enumerate(out):
            rec["id"] = self.make_id(i)
        supervisors = [r["id"] for r in out if r["role"] == "supervisor"]
        for i, rec in enumerate(r for r in out if r["role"] != "supervisor"):
            rec["supervisor_id"] = supervisors[i % len(supervisors)]
        return out
