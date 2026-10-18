"""Speakers: generated prescribers contracted and trained to present the QUORVANTA speaker deck."""

import json
from datetime import date, timedelta

from population.core import SRC, Entity, register

TIERS = [("national", 4), ("regional", 8), ("local", 12)]
LAUNCH_DECK, CURRENT_DECK = "AQB-QV-SPD-0224", "AQB-QV-SPD-0926"


@register
class Speakers(Entity):
    name = "speakers"
    id_prefix = "PSPR"
    default_count = 24
    requires = ("hcps",)
    references = {"hcp_id": "hcps"}
    must_match = {"speaker_npi": ["hcp_id", "npi"], "first_name": ["hcp_id", "first_name"],
                  "last_name": ["hcp_id", "last_name"], "state": ["hcp_id", "state"]}
    notice = ("FICTITIOUS. A speaker roster of generated prescribers who do not exist, for a product that does not exist. "
              "NPI-shaped ids begin with 91.")
    usage = ("Prescribers contracted by Arden Quay to present the speaker deck (speaker-programs/speaker-program-rules.json). "
             "tier sets the honorarium; contract gives the dates the speaker may present; trainings lists each deck version "
             "(by job code) the speaker was trained on, and when. A speaker may present a version only after training on it "
             "(SPK-01).")
    flags = {}
    patterns = {
        "recruited_after_launch": "Joined the roster after the launch training wave.",
        "contract_lapsed": "The contract ended before the as_of date and was not renewed.",
        "not_trained_on_current_deck": "Has no training on the current deck version.",
    }

    def generate(self, ctx, count):
        rng = ctx.rng(self.name)
        covered = {st for t in json.loads((SRC / "crm/field-force.json").read_text())["territories"] for st in t["states"]}
        pool = [h for h in ctx.records("hcps") if h["state"] in covered and h["credential"] in ("MD", "DO") and h["specialty"] == "Neurology"
                and h["segment"] in ("A", "B") and h["status"] == "active" and not h["quality_flags"] and not h["no_see"]]
        chosen = sorted(rng.sample(pool, count), key=lambda h: h["id"])
        tiers = [t for t, n in TIERS for _ in range(n)]
        tiers = (tiers * (count // len(tiers) + 1))[:count]
        rng.shuffle(tiers)
        out = []
        for i, h in enumerate(chosen):
            patterns = []
            if i < count * 3 // 4:
                start = date(2024, 2, 5) + timedelta(days=rng.randrange(25))
            else:
                start = date(2024, 9, 1) + timedelta(days=rng.randrange(400))
                patterns.append({"type": "recruited_after_launch"})
            end = date(start.year + 3, start.month, 1) - timedelta(days=1)
            trainings = [{"deck": LAUNCH_DECK, "trained_on": str(max(start, date(2024, 2, 26)) + timedelta(days=rng.randrange(3, 15)))}]
            out.append({"id": self.make_id(i), "hcp_id": h["id"], "speaker_npi": h["npi"], "first_name": h["first_name"],
                        "last_name": h["last_name"], "credential": h["credential"], "state": h["state"], "tier": tiers[i],
                        "contract": {"from": str(start), "to": str(end)}, "trainings": trainings, "patterns": patterns})
        # The September 2026 deck: trained on September 8 to 12, except one lapsed speaker and one who missed it.
        lapsed, missed = out[1], out[2]
        lapsed["contract"]["to"] = "2026-06-30"
        lapsed["patterns"].append({"type": "contract_lapsed"})
        for s in out:
            if s is lapsed or s is missed:
                s["patterns"].append({"type": "not_trained_on_current_deck"})
                continue
            s["trainings"].append({"deck": CURRENT_DECK, "trained_on": str(date(2026, 9, 8) + timedelta(days=rng.randrange(5)))})
        return out
