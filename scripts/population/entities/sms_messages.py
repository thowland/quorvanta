"""SMS messages: every automated text to and from generated patients, with keyword replies and campaign steps."""

from datetime import date, timedelta

from population.core import AS_OF, Entity, register
from population import engagement as eng

FREE_TEXT = {
    "English": ["Thanks", "Ok thank you", "Who is this?", "Got it", "Can someone call me after 5?", "Please call me"],
    "Spanish": ["Gracias", "Ok gracias", "¿Quién es?", "Por favor llámeme"],
}
OPT_IN_WORD = {"English": ["YES", "Yes", "yes"], "Spanish": ["SI", "Sí", "si"]}
OPT_OUT_WORD = {"English": ["STOP", "Stop", "stop"], "Spanish": ["STOP", "ALTO"]}
HELP_WORD = {"English": ["HELP"], "Spanish": ["AYUDA"]}

# How many suppressed steps are sent anyway, per reason, so a consent or suppression check has breaches to find.
LEAKS = {"to_minor": 2, "unsupported_language": 2, "no_opt_in": 3, "after_opt_out": 3,
         "no_reminder_choice": 2, "situation_ended": 3}


@register
class SmsMessages(Entity):
    name = "sms-messages"
    id_prefix = "PSMS"
    default_count = 1
    count_means = "(not used)"
    requires = ("patients", "refills")
    references = {"patient_id": "patients", "in_reply_to": "sms-messages"}
    notice = ("FICTITIOUS. Generated text messages between a support program that does not exist and patients who do not "
              "exist. Phone numbers use the reserved 555-01xx range.")
    usage = ("Every automated text QuorvantaConnect sent a generated patient, and every reply, from enrollment to the as_of "
             "date, following engagement/campaign-rules.json, approved-messages.json and campaigns.json. Times are UTC; "
             "quiet hours are judged in the patient's local time from their state. Outbound texts carry the approved "
             "message id and body in the patient's language. Scheduled texts carry campaign_id and schedule (the track, "
             "the reference date day0 and the step's day offset); keyword replies carry in_reply_to. Inbound texts carry "
             "the keyword they match, or routed_to for free text. A handful of texts break a rule on purpose, and each "
             "names the rule it breaks in quality_flags; every other text can be recomputed from the patient, their "
             "fills and the inbound keywords. Free text here never mentions a side effect; those replies are labeled "
             "scenarios, not population data.")
    flags = {
        "to_minor": "Sent to a patient under 18 (ENG-09).",
        "unsupported_language": "Sent to a patient whose language has no approved version, in English (ENG-07).",
        "no_opt_in": "A campaign or reminder text to a patient who never opted in (ENG-01).",
        "after_opt_out": "A campaign or reminder text after the patient's opt-out keyword (ENG-03).",
        "no_reminder_choice": "A refill reminder to a patient who did not choose text reminders (ENG-02).",
        "situation_ended": "A step sent after its campaign's situation ended: a never-start text after the first fill or a "
                           "canceled prescription, or a refill or discontinuation-risk text after the next fill or after "
                           "treatment stopped (ENG-10).",
        "quiet_hours": "Sent outside 8 a.m. to 9 p.m. in the patient's local time (ENG-05).",
        "wrong_cost_version": "The copay version of the never-start cost text sent to a patient with government or no insurance (ENG-11).",
        "duplicate_step": "A campaign step sent again after it had already been sent.",
        "frequency_cap": "The third or later campaign text in 7 consecutive days (ENG-06).",
    }

    def generate(self, ctx, count):
        rng = ctx.rng(self.name)
        fills = {}
        for f in ctx.records("refills"):
            if not f["quality_flags"]:
                fills.setdefault(f["patient_id"], []).append({"shipped_on": date.fromisoformat(f["shipped_on"]), "days_supply": f["days_supply"]})

        def send_time(day, state, c=None):
            return eng.at_local(day, rng.randrange(9, 20), rng.randrange(60), state)

        def reply_delay():
            return timedelta(seconds=rng.randrange(20, 90))

        replays = []
        for p in ctx.records("patients"):
            if p["program"]["status"] != "enrolled" or any(f["type"] == "duplicate" for f in p["quality_flags"]):
                continue
            person = eng.Person.from_population(p)
            lang = p["language"] if p["language"] in eng.LANGUAGES else "English"
            eagerness = rng.random()

            def respond(ev, lang=lang, eagerness=eagerness):
                msg, t = ev["message_id"], ev["at"]
                if msg == "MSG-ACT-01":
                    step = ev["schedule"]["step"]
                    roll = rng.random()
                    yes = 0.72 if step == 0 else 0.40
                    if roll < yes * (0.6 + 0.6 * eagerness):
                        return [(t + timedelta(minutes=rng.randrange(1, 1500)), rng.choice(OPT_IN_WORD[lang]))]
                    if roll > 0.96:
                        return [(t + timedelta(minutes=rng.randrange(1, 600)), rng.choice(OPT_OUT_WORD[lang]))]
                    if roll > 0.94:
                        return [(t + timedelta(minutes=rng.randrange(1, 300)), rng.choice(HELP_WORD[lang]))]
                    return []
                if msg == "MSG-HELP" and rng.random() < 0.6:
                    return [(t + timedelta(minutes=rng.randrange(2, 120)), rng.choice(OPT_IN_WORD[lang]))]
                if msg == "MSG-STOP" and rng.random() < 0.08:
                    return [(t + timedelta(days=rng.randrange(5, 60), minutes=rng.randrange(1440)), "START")]
                if ev["campaign_id"] is not None and msg != "MSG-ACT-01":
                    roll = rng.random()
                    if roll < 0.012:
                        return [(t + timedelta(minutes=rng.randrange(1, 2000)), rng.choice(OPT_OUT_WORD[lang]))]
                    if roll < 0.035:
                        return [(t + timedelta(minutes=rng.randrange(1, 2000)), rng.choice(FREE_TEXT[lang]))]
                    if roll < 0.042:
                        return [(t + timedelta(minutes=rng.randrange(1, 500)), rng.choice(HELP_WORD[lang]))]
                return []

            r = eng.Replay(person, fills.get(p["id"], []), AS_OF, respond, send_time, reply_delay).run()
            replays.append((p, r))

        self._breaches(rng, replays, send_time)

        out = []
        for p, r in replays:
            ids = {}
            for ev in sorted(r.events, key=lambda e: e["at"]):
                rec = {"id": self.make_id(len(out)), "patient_id": p["id"], "direction": ev["direction"], "at": eng.iso(ev["at"]),
                       "message_id": ev.get("message_id"), "language": ev.get("language"), "body": ev["body"],
                       "campaign_id": ev.get("campaign_id"), "schedule": ev.get("schedule"),
                       "in_reply_to": ids.get(id(ev["in_reply_to"])) if ev.get("in_reply_to") else None,
                       "keyword": ev.get("keyword"), "routed_to": ev.get("routed_to"),
                       "quality_flags": [{"type": t} for t in ev.get("flags", [])]}
                ids[id(ev)] = rec["id"]
                out.append(rec)
        return out

    def _breaches(self, rng, replays, send_time):
        """Send a few suppressed steps anyway, and bend a few scheduled ones, each flagged with the rule it breaks."""
        leaks = {}
        for p, r in replays:
            for c, reason in r.suppressed:
                leaks.setdefault(reason, []).append((p, r, c))
        for reason, n in LEAKS.items():
            pool = leaks.get(reason, [])
            for p, r, c in rng.sample(pool, min(n, len(pool))):
                day, campaign, track, day0, step, msg, ref = c
                lang = p["language"] if p["language"] in eng.LANGUAGES else "English"
                r.events.append({"direction": "outbound", "at": send_time(day, p["state"]), "message_id": msg, "language": lang,
                                 "body": eng.body(msg, lang), "campaign_id": campaign,
                                 "schedule": {"track": track, "day0": str(day0), "step": step}, "in_reply_to": None,
                                 "flags": [reason]})

        def scheduled(pred):
            return [(p, r, ev) for p, r in replays for ev in r.events
                    if ev["direction"] == "outbound" and ev.get("schedule") and not ev.get("flags") and pred(p, ev)]

        # Quiet hours: a scheduled text on the right day at the wrong hour, where no reply that day depends on its time.
        pool = scheduled(lambda p, ev: ev["campaign_id"] != "CMP-ACTIVATION")
        for p, r, ev in rng.sample(pool, 3):
            day = eng.local_date(ev["at"], p["state"])
            if any(e["direction"] == "inbound" and eng.local_date(e["at"], p["state"]) == day for e in r.events):
                continue
            ev["at"] = eng.at_local(day, rng.choice([6, 7, 21, 22]), rng.randrange(60), p["state"])
            ev["flags"] = ["quiet_hours"]
        # The copay version of the cost text to patients it does not apply to.
        pool = scheduled(lambda p, ev: ev["message_id"] == "MSG-NS-COST-OTHER")
        for p, r, ev in rng.sample(pool, min(2, len(pool))):
            ev["message_id"] = "MSG-NS-COST-COMMERCIAL"
            ev["body"] = eng.body("MSG-NS-COST-COMMERCIAL", ev["language"])
            ev["flags"] = ["wrong_cost_version"]
        # One never-start step sent three times in three days: two duplicates, the last also over the cap.
        pool = scheduled(lambda p, ev: ev["campaign_id"] == "CMP-NEVERSTART" and ev["schedule"]["step"] == 14)
        for p, r, ev in rng.sample(pool, min(1, len(pool))):
            day = eng.local_date(ev["at"], p["state"])
            for extra, flags in ((1, ["duplicate_step"]), (2, ["duplicate_step", "frequency_cap"])):
                r.events.append(dict(ev, at=send_time(day + timedelta(days=extra), p["state"]), flags=flags))
