"""Campaign memberships: who entered each outreach campaign, on which day, and how they left."""

from datetime import date, datetime, timedelta

from population.core import AS_OF, Entity, register
from population import engagement as eng


@register
class CampaignMemberships(Entity):
    name = "campaign-memberships"
    id_prefix = "PCMB"
    default_count = 1
    count_means = "(not used)"
    requires = ("patients", "refills", "sms-messages")
    references = {"patient_id": "patients", "sends[]": "sms-messages"}
    notice = "FICTITIOUS. Generated campaign memberships for a support program that does not exist and patients who do not exist."
    usage = ("One record per patient per campaign entry, from engagement/campaigns.json: CMP-ACTIVATION from enrollment, "
             "CMP-NEVERSTART from day 14 after enrollment with no first fill, and CMP-DISCON-RISK on its first_month and "
             "late_refill tracks (one late_refill membership per late fill). day0 is the campaign's reference date; "
             "exit_reason and exited_on follow from the patient's fills, keywords and therapy, and are null while a "
             "membership is still open on the as_of date. sends lists the scheduled texts sent under the membership. "
             "Patients who met a campaign's situation but could not be texted (no opt-in, a minor, a language without "
             "approved texts) have no membership; they are the audience a case manager's call list has to cover.")

    def generate(self, ctx, count):
        fills, inbound, sent = {}, {}, {}
        for f in ctx.records("refills"):
            if not f["quality_flags"]:
                fills.setdefault(f["patient_id"], []).append({"shipped_on": date.fromisoformat(f["shipped_on"]), "days_supply": f["days_supply"]})
        for m in ctx.records("sms-messages"):
            at = datetime.fromisoformat(m["at"].replace("Z", "+00:00"))
            if m["direction"] == "inbound":
                inbound.setdefault(m["patient_id"], []).append((at, m["body"]))
            elif m["schedule"] and {f["type"] for f in m["quality_flags"]} <= {"quiet_hours", "wrong_cost_version"}:
                # Steps sent at the wrong hour or in the wrong version still belong to their membership;
                # leaked and duplicate steps do not.
                s = m["schedule"]
                sent[(m["patient_id"], m["campaign_id"], s["track"], s["day0"], s["step"])] = (at, m["id"])
        out = []
        for p in ctx.records("patients"):
            if p["program"]["status"] != "enrolled" or any(f["type"] == "duplicate" for f in p["quality_flags"]):
                continue
            pid = p["id"]

            def send_time(day, state, c, pid=pid):
                hit = sent.get((pid, c[1], c[2], str(c[3]), c[4]))
                return hit[0] if hit else eng.at_local(day, 23, 59, state)

            r = eng.Replay(eng.Person.from_population(p), fills.get(pid, []), AS_OF, lambda ev: [], send_time,
                           lambda: timedelta(seconds=30), inbound.get(pid, [])).run()
            for m in eng.memberships(r):
                ids = []
                for ev in m["sends"]:
                    s = ev["schedule"]
                    ids.append(sent[(pid, ev["campaign_id"], s["track"], s["day0"], s["step"])][1])
                out.append({"id": self.make_id(len(out)), "patient_id": pid, "campaign_id": m["campaign_id"], "track": m["track"],
                            "day0": m["day0"], "entered_on": m["entered_on"], "exited_on": m["exited_on"],
                            "exit_reason": m["exit_reason"], "sends": ids, "quality_flags": []})
        return out
