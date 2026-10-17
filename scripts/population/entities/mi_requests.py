"""Medical information requests: unsolicited questions from generated prescribers, each routed to an SRD, the label, a custom response or a referral."""

import json
from datetime import date, datetime, timedelta

from population.core import AS_OF, SRC, Entity, register
from population import engagement as eng

START = date(2026, 1, 1)
MI_STATE = "MA"          # Medical Information works from Waltham; receipt and response dates are its local dates
SLA_BUSINESS_DAYS = 2
REPEAT_WINDOW_DAYS = 30
SEGMENT_WEIGHT = {"A": 5, "B": 3, "C": 2, "D": 1}
CHANNELS = {"phone": 45, "email": 20, "web_form": 15, "field_rep": 20}
DELIVERY = {"phone": "verbal_and_email", "email": "email", "web_form": "email"}

# Every question is general or prospective. None reports a patient's exposure, overdose or event:
# those are adverse event or special-situation reports and belong in labeled scenarios.
TOPICS = {
    "MIT-01": ("srd", "SRD-001", 3, ["Is there any data on QUORVANTA in adolescents?",
                                     "Has QUORVANTA been studied in patients under 18?"]),
    "MIT-02": ("srd", "SRD-002", 4, ["Is there any data on QUORVANTA in patients over 65?",
                                     "Do older patients need a different dose of QUORVANTA?"]),
    "MIT-03": ("srd", "SRD-003", 3, ["What is known about QUORVANTA in hepatic impairment?",
                                     "Is any dose adjustment needed for liver impairment?"]),
    "MIT-04": ("srd", "SRD-004", 3, ["Can QUORVANTA be used in patients on dialysis?",
                                     "Is there any data in end-stage renal disease?"]),
    "MIT-05": ("srd", "SRD-005", 6, ["Can patients on QUORVANTA receive live vaccines?",
                                     "What is the guidance on vaccinations during treatment?"]),
    "MIT-06": ("srd", "SRD-006", 3, ["Is there any data on QUORVANTA and breastfeeding?",
                                     "Is QUORVANTA excreted in human milk?"]),
    "MIT-07": ("srd", "SRD-007", 5, ["How does QUORVANTA compare with other disease-modifying therapies?",
                                     "Is there head-to-head efficacy data for QUORVANTA?"]),
    "MIT-08": ("srd", "SRD-008", 8, ["Is QUORVANTA better tolerated than dimethyl tavorate?",
                                     "Is there less flushing or GI upset with QUORVANTA than with dimethyl tavorate?"]),
    "MIT-09": ("srd", "SRD-009", 2, ["Is there any data on QUORVANTA in primary progressive Brennick syndrome?"]),
    "MIT-10": ("srd", "SRD-010", 6, ["What should patients do if they miss a dose of QUORVANTA?",
                                     "Is there guidance on missed doses?"]),
    "MIT-11": ("srd", "SRD-011", 1, ["Is there any information on overdose with QUORVANTA?"]),
    "MIT-12": ("srd", "SRD-012", 3, ["Can QUORVANTA be combined with another disease-modifying therapy?"]),
    "MIT-13": ("srd", "SRD-013", 4, ["Is there efficacy data for QUORVANTA beyond two years?",
                                     "What long-term data is available?"]),
    "MIT-14": ("srd", "SRD-014", 3, ["How does QUORVANTA work?",
                                     "What is the mechanism of action of soriximel tavorate?"]),
    "MIT-15": ("srd", "SRD-015", 4, ["Can QUORVANTA capsules be opened for a patient who cannot swallow them?",
                                     "Is there an alternative for patients with difficulty swallowing capsules?"]),
    "MIT-16": ("srd", "SRD-016", 3, ["Does QUORVANTA interact with hormonal contraceptives?",
                                     "Is there data with contraceptives other than levonorgestrel and ethinyl estradiol?"]),
    "MIT-17": ("srd", "SRD-017", 5, ["Can QUORVANTA be started in a patient with a low lymphocyte count?",
                                     "What lymphocyte count is needed before starting QUORVANTA?"]),
    "MIT-18": ("srd", "SRD-018", 6, ["How should patients switch to QUORVANTA from another therapy?",
                                     "Is a washout needed when switching to QUORVANTA?"]),
    "MIT-19": ("prescribing_information", "2.2", 4, ["What is the titration schedule for QUORVANTA?"]),
    "MIT-20": ("prescribing_information", "2.4", 4, ["How often should lymphocyte counts be checked on QUORVANTA?"]),
    "MIT-21": ("prescribing_information", "2.1", 3, ["Which tests are needed before starting QUORVANTA?"]),
    "MIT-22": ("prescribing_information", "16", 2, ["How should QUORVANTA be stored?"]),
    "MIT-23": ("prescribing_information", "2.5", 2, ["Is a dose adjustment needed in renal impairment?"]),
    "MIT-24": ("custom_response", None, 2, ["Is there any data on QUORVANTA in conditions other than Brennick syndrome?"]),
    "MIT-25": ("referral", "QuorvantaConnect", 5, ["How do patients get help with coverage for QUORVANTA?",
                                                    "Which pharmacies can dispense QUORVANTA?"]),
    "MIT-26": ("referral", "other_manufacturer", 2, ["What is the dosing of a different oral therapy my patients take?"]),
    "MIT-27": ("referral", "Quality", 1, ["Who can answer a question about a specific QUORVANTA lot?"]),
}


@register
class MiRequests(Entity):
    name = "mi-requests"
    id_prefix = "PMIR"
    default_count = 450
    requires = ("hcps",)
    references = {"hcp_id": "hcps"}
    notice = ("FICTITIOUS. Generated medical information requests from prescribers who do not exist, "
              "about a product that does not exist.")
    usage = (f"One record per unsolicited medical information request from a generated prescriber between {START} and the "
             "as_of date. topic is a code from the topics catalog in this header, which says how Medical Information "
             "answers it: with an SRD from medical-information/srds.json, with the prescribing information, with a custom "
             "response, or by referral. Requests reach Medical Information by phone, email, the web form, or from a "
             "representative (field_rep), who submits the question on the day the prescriber asked it (asked_on) and "
             f"does not answer it. received_at and responded_at are UTC; Medical Information's dates are {MI_STATE} local "
             f"dates, on the business calendar in safety/safety-reference.json. The response is due within "
             f"{SLA_BUSINESS_DAYS} business days of receipt; turnaround_business_days counts them, and a request still "
             "open at as_of has responded_at null. Question wording is general and never reports an adverse event or "
             "special situation. The SRDs in srds.json are the current versions.")
    flags = {
        "late_response": f"Answered, or still open, after the {SLA_BUSINESS_DAYS}-business-day response target.",
        "rep_submitted_late": "A representative submitted the question after the day the prescriber asked it.",
        "logged_to_duplicate": "Logged against a duplicate prescriber record instead of its original.",
    }
    patterns = {
        "repeat_request": f"The same prescriber asked about the same topic within {REPEAT_WINDOW_DAYS} days; 'of' is the earlier request.",
    }
    header = {
        "response_target_business_days": SLA_BUSINESS_DAYS,
        "topics": {code: {"route": route, ({"srd": "srd_id", "prescribing_information": "label_section",
                                            "referral": "referred_to"}.get(route, "target")): target,
                          "question_examples": qs}
                   for code, (route, target, _, qs) in TOPICS.items()},
    }

    def generate(self, ctx, count):
        rng = ctx.rng(self.name)
        ff = json.loads((SRC / "crm/field-force.json").read_text())
        rep_for = {st: t["rep_id"] for t in ff["territories"] for st in t["states"]}
        holidays = {date.fromisoformat(d) for d in
                    json.loads((SRC / "safety/safety-reference.json").read_text())["business_calendar"]["holidays"]}
        hcps = ctx.records("hcps")
        clean = [h for h in hcps if h["status"] == "active" and not any(f["type"] == "duplicate" for f in h["quality_flags"])]
        frequent = set(h["id"] for h in rng.sample(clean, 8))
        weights = [SEGMENT_WEIGHT[h["segment"]] * (6 if h["id"] in frequent else 1) for h in clean]
        codes = list(TOPICS)
        topic_weights = [TOPICS[c][2] for c in codes]
        days = (AS_OF - START).days

        def is_bd(d):
            return d.weekday() < 5 and d not in holidays

        def add_bd(d, n):
            while n:
                d += timedelta(days=1)
                if is_bd(d):
                    n -= 1
            return d

        def next_bd(d):
            while not is_bd(d):
                d += timedelta(days=1)
            return d

        def bd_between(a, b):
            n, d = 0, a
            while d < b:
                d += timedelta(days=1)
                n += is_bd(d)
            return n

        def make(h, topic, asked, channel, late_rep=False, late_answer=False):
            route, target, _, qs = TOPICS[topic]
            rec = {"id": None, "hcp_id": h["id"], "topic": topic, "question": rng.choice(qs), "channel": channel}
            if channel == "field_rep":
                rep = rep_for[h["state"]]
                sub = next_bd(asked + timedelta(days=rng.randrange(2, 6))) if late_rep else asked
                received = eng.at_local(sub, rng.randrange(16, 20), rng.randrange(60), h["state"])
                rec.update({"submitted_by": rep, "asked_on": str(asked)})
            elif channel == "phone":
                received = eng.at_local(asked, rng.randrange(8, 17), rng.randrange(60), h["state"])
            else:
                received = eng.at_local(asked, rng.randrange(6, 23), rng.randrange(60), h["state"])
            got = eng.local_date(received, MI_STATE)
            start = got if is_bd(got) else next_bd(got)
            due = add_bd(start, SLA_BUSINESS_DAYS)
            if channel == "phone" and route == "referral" and is_bd(got):
                answered = got
            elif late_answer:
                answered = add_bd(start, SLA_BUSINESS_DAYS + rng.randrange(1, 5))
            else:
                answered = add_bd(start, rng.choice([0, 0, 1, 1, 1, 2]))
            responded = eng.at_local(answered, rng.randrange(9, 17), rng.randrange(60), MI_STATE) if answered <= AS_OF else None
            if responded is not None and responded <= received:
                responded = received + timedelta(minutes=rng.randrange(5, 50))
            rec["received_at"] = eng.iso(received)
            rec["response"] = {
                "route": route,
                "srd_id": target if route == "srd" else None,
                "label_section": target if route == "prescribing_information" else None,
                "referred_to": target if route == "referral" else None,
                "delivered_by": None if responded is None else
                ("verbal" if route == "referral" and channel == "phone" else
                 rng.choice(["email", "fax"]) if channel == "field_rep" else DELIVERY[channel]),
                "responded_at": None if responded is None else eng.iso(responded),
            }
            done = eng.local_date(responded, MI_STATE) if responded else AS_OF
            rec["turnaround_business_days"] = bd_between(start, done) if responded else None
            flags = []
            if done > due:
                flags.append("late_response")
            if channel == "field_rep" and rec["asked_on"] != str(eng.local_date(received, h["state"])):
                flags.append("rep_submitted_late")
            rec["quality_flags"] = [{"type": f} for f in flags]
            rec["patterns"] = []
            return rec

        def asked_day():
            return next_bd(START + timedelta(days=rng.randrange(days)))

        def channel_for(h):
            chans = [c for c in CHANNELS if c != "field_rep" or (rep_for.get(h["state"]) and not h["no_see"])]
            return rng.choices(chans, weights=[CHANNELS[c] for c in chans])[0]

        out = []
        while len(out) < count:
            h = rng.choices(clean, weights=weights)[0]
            asked = asked_day()
            if asked > AS_OF:
                continue
            out.append(make(h, rng.choices(codes, weights=topic_weights)[0], asked, channel_for(h),
                            late_answer=rng.random() < 0.03))
            # Some prescribers come back to the same topic within a few weeks.
            if rng.random() < 0.06:
                again = next_bd(asked + timedelta(days=rng.randrange(3, REPEAT_WINDOW_DAYS - 3)))
                if again <= AS_OF:
                    out.append(make(h, out[-1]["topic"], again, channel_for(h)))

        # Representatives who submitted a question days after the call.
        field = [h for h in clean if rep_for.get(h["state"]) and not h["no_see"]]
        for h in rng.sample(field, 3):
            asked = asked_day()
            if asked + timedelta(days=10) <= AS_OF:
                out.append(make(h, rng.choices(codes, weights=topic_weights)[0], asked, "field_rep", late_rep=True))
        # Requests filed under a duplicate prescriber record.
        dups = [h for h in hcps if any(f["type"] == "duplicate" for f in h["quality_flags"]) and h["status"] == "active"]
        for h in rng.sample(dups, min(3, len(dups))):
            rec = make(h, rng.choices(codes, weights=topic_weights)[0], asked_day(), rng.choice(["phone", "email", "web_form"]))
            rec["quality_flags"].append({"type": "logged_to_duplicate"})
            out.append(rec)

        out = [r for r in out if r["received_at"] <= eng.iso(eng.at_local(AS_OF, 23, 59, MI_STATE))]
        out.sort(key=lambda r: (r["received_at"], r["hcp_id"]))
        last = {}
        for i, r in enumerate(out):
            r["id"] = self.make_id(i)
            key = (r["hcp_id"], r["topic"])
            got = eng.local_date(datetime.fromisoformat(r["received_at"].replace("Z", "+00:00")), MI_STATE)
            if key in last and (got - last[key][1]).days <= REPEAT_WINDOW_DAYS:
                r["patterns"].append({"type": "repeat_request", "of": last[key][0]})
            last[key] = (r["id"], got)
        return out

