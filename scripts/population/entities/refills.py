"""Refills: every fill shipped to a generated patient, without claims or serial numbers."""

import json
from datetime import date, timedelta

from population.core import AS_OF, SRC, Entity, register

NETWORK = ["SP-01", "SP-02", "SP-03", "SP-04"]
LATE_DAYS = 7          # a fill shipped this many days or more after the previous one ran out is late
LAPSE_DAYS = 30        # on treatment, but nothing shipped for this long after the last fill ran out


def pharmacy_for(patient, plans):
    """The plan's required pharmacy, the health system's own pharmacy, SP-04 for Foundation supply, or any network pharmacy."""
    ins = patient["insurance"]
    if ins["type"] == "none":
        return "SP-04"
    plan = plans.get(ins["plan_name"])
    if plan and plan["name"] == "Halverson Health Employee Plan":
        return "SP-05"
    if plan and (plan.get("required_pharmacy") or "").startswith("SP-"):
        return plan["required_pharmacy"]
    return None


@register
class Refills(Entity):
    name = "refills"
    id_prefix = "PRFL"
    default_count = 1
    count_means = "(not used)"
    requires = ("patients",)
    references = {"patient_id": "patients", "quality_flags[].of": "refills"}
    notice = ("FICTITIOUS. Generated fills of a product that does not exist, for patients who do not exist. Pharmacy ids "
              "are the network in access/specialty-pharmacy-network.json.")
    usage = ("One record per fill shipped to a patient who started QUORVANTA, from the first fill (a starter bottle, on "
             "patients.therapy.started_on) to the last one before the as_of date or before treatment was discontinued. "
             "Every fill is a 30-day supply; due_on is the day it runs out. The pharmacy is the plan's required pharmacy, "
             "SP-05 for the Halverson Health plan, SP-04 for uninsured patients on Foundation supply, or otherwise one "
             "network pharmacy per patient. There are no claims, prices, lots or serial numbers; only the 29 hand-built "
             "cases carry those. --count is not used.")
    flags = {
        "duplicate": "The same fill sent twice by the pharmacy under a new record id; 'of' is the original.",
    }
    patterns = {
        "late_fill": f"Shipped {LATE_DAYS} or more days after the previous fill ran out.",
        "lapsed_at_as_of": f"The last fill for a patient still recorded as on treatment ran out more than {LAPSE_DAYS} days before the as_of date.",
    }

    def generate(self, ctx, count):
        rng = ctx.rng(self.name)
        plans = {p["name"]: p for p in json.loads((SRC / "payer/plans.json").read_text())["plans"]}
        out = []
        for p in ctx.records("patients"):
            th = p["therapy"]
            if not th["started_on"] or any(f["type"] == "duplicate" for f in p["quality_flags"]):
                continue
            pharmacy = pharmacy_for(p, plans) or rng.choice(NETWORK)
            source = "foundation" if p["insurance"]["type"] == "none" else "plan"
            stop = date.fromisoformat(th["discontinued_on"]) if th["discontinued_on"] else None
            # A few patients still recorded as on treatment simply stop refilling.
            lapse_after = rng.randrange(2, 12) if not stop and rng.random() < 0.04 else None
            shipped = date.fromisoformat(th["started_on"])
            n = 0
            while shipped <= AS_OF and (stop is None or shipped < stop) and (lapse_after is None or n < lapse_after):
                n += 1
                due = shipped + timedelta(days=30)
                rec = {"id": self.make_id(len(out)), "patient_id": p["id"], "pharmacy_id": pharmacy, "source": source,
                       "fill_number": n, "package": "PKG-STARTER" if n == 1 else "PKG-120", "capsules": 92 if n == 1 else 120,
                       "days_supply": 30, "shipped_on": str(shipped), "due_on": str(due), "patterns": [], "quality_flags": []}
                if n > 1 and (shipped - prev_due).days >= LATE_DAYS:
                    rec["patterns"].append({"type": "late_fill", "days_late": (shipped - prev_due).days})
                out.append(rec)
                if rng.random() < 0.01:
                    out.append(dict(rec, id=self.make_id(len(out)), patterns=[], quality_flags=[{"type": "duplicate", "of": rec["id"]}]))
                prev_due, last = due, rec
                delay = rng.choices([rng.randrange(-5, 1), rng.randrange(1, 7), rng.randrange(7, 21), rng.randrange(21, 61)],
                                    weights=[70, 20, 8, 2])[0]
                shipped = due + timedelta(days=delay)
            if th["status"] == "on_therapy" and (AS_OF - prev_due).days > LAPSE_DAYS:
                last["patterns"].append({"type": "lapsed_at_as_of", "due_on": str(prev_due)})
        return out
