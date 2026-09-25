"""HCP emails: approved representative emails to generated prescribers, with delivery, opens, clicks and unsubscribes."""

import json
from datetime import date, datetime, time, timedelta, timezone

from population.core import AS_OF, SRC, Entity, register
from population import engagement as eng

START = date(2026, 1, 1)
SENDS_PER_SEGMENT = {"A": 6, "B": 4, "C": 2, "D": 1}
# The portal page each template links to (portal-sessions.json header has the page catalog).
TEMPLATE_PAGE = {"RTE-01": "access", "RTE-02": "dosing", "RTE-03": "safety"}
MACHINE_OPEN_SECONDS = 5
SCANNER_CLICK_SECONDS = 10


@register
class HcpEmails(Entity):
    name = "hcp-emails"
    id_prefix = "PEML"
    default_count = 1
    count_means = "(not used)"
    requires = ("hcps",)
    references = {"hcp_id": "hcps"}
    notice = ("FICTITIOUS. Generated approved emails from representatives who do not exist to prescribers who do not exist, "
              "about a product that does not exist. Addresses use .example.")
    usage = (f"One record per approved email a representative sent a generated prescriber between {START} and the as_of "
             "date, from a template in crm/approved-emails.json, by the representative whose territory "
             "(crm/field-force.json) covers the prescriber's state. events lists delivery, opens, clicks (with the portal "
             "page linked), bounces and unsubscribes, with UTC times. hcps.json holds each prescriber's email consent at "
             "the start of this log; an unsubscribe here ends it (engagement/campaign-rules.json ENG-12). Opens within "
             f"{MACHINE_OPEN_SECONDS} seconds of delivery are privacy-proxy prefetches and clicks within "
             f"{SCANNER_CLICK_SECONDS} seconds, before any human open, are security scanners (ENG-13); both carry machine: "
             "true and neither counts as engagement.")
    flags = {
        "email_without_consent": "Sent to a prescriber without approved-email consent, or after they unsubscribed (ENG-12).",
        "email_to_inactive": "Sent to a retired prescriber or one whose NPI had been deactivated (ENG-12).",
        "email_outside_territory": "Sent by a representative whose territory does not cover the prescriber's state (ENG-12).",
    }
    header = {"template_pages": TEMPLATE_PAGE}

    def generate(self, ctx, count):
        rng = ctx.rng(self.name)
        ff = json.loads((SRC / "crm/field-force.json").read_text())
        rep_for = {st: t["rep_id"] for t in ff["territories"] for st in t["states"]}
        templates = [t["id"] for t in json.loads((SRC / "crm/approved-emails.json").read_text())["templates"] if t["status"] == "approved"]
        hcps = ctx.records("hcps")
        days = (AS_OF - START).days
        out = []

        def business_time(day, state):
            while day.weekday() >= 5:
                day += timedelta(days=1)
            return eng.at_local(day, rng.randrange(8, 17), rng.randrange(60), state)

        def add(h, rep, sent, flags):
            rec = {"id": None, "hcp_id": h["id"], "sender_id": rep, "template_id": rng.choice(templates),
                   "to": h["email"], "sent_at": eng.iso(sent), "events": [], "quality_flags": [{"type": f} for f in flags]}
            ev = rec["events"]
            if rng.random() < 0.02:
                ev.append({"type": "bounced", "at": eng.iso(sent + timedelta(seconds=rng.randrange(2, 40)))})
                out.append(rec)
                return rec
            delivered = sent + timedelta(seconds=rng.randrange(1, 20))
            ev.append({"type": "delivered", "at": eng.iso(delivered)})
            page = TEMPLATE_PAGE[rec["template_id"]]
            if rng.random() < 0.3:
                ev.append({"type": "opened", "at": eng.iso(delivered + timedelta(seconds=rng.randrange(1, MACHINE_OPEN_SECONDS))), "machine": True})
            if rng.random() < 0.05:
                ev.append({"type": "clicked", "at": eng.iso(delivered + timedelta(seconds=rng.randrange(2, SCANNER_CLICK_SECONDS))),
                           "page": page, "machine": True})
            if rng.random() < 0.35:
                opened = delivered + timedelta(minutes=rng.randrange(3, 4000))
                ev.append({"type": "opened", "at": eng.iso(opened), "machine": False})
                if rng.random() < 0.22:
                    ev.append({"type": "clicked", "at": eng.iso(opened + timedelta(seconds=rng.randrange(15, 300))), "page": page, "machine": False})
                if rng.random() < 0.015:
                    ev.append({"type": "unsubscribed", "at": eng.iso(opened + timedelta(seconds=rng.randrange(20, 400)))})
            ev.sort(key=lambda e: e["at"])
            out.append(rec)
            return rec

        for h in hcps:
            rep = rep_for.get(h["state"])
            if rep is None or h["status"] != "active" or not h["consent"]["approved_email"] or h["quality_flags"]:
                continue
            n = SENDS_PER_SEGMENT[h["segment"]]
            unsubscribed = None
            for sent in sorted(business_time(START + timedelta(days=rng.randrange(days)), h["state"]) for _ in range(n)):
                if sent.date() > AS_OF or (unsubscribed and sent > unsubscribed):
                    continue
                rec = add(h, rep, sent, [])
                un = next((e["at"] for e in rec["events"] if e["type"] == "unsubscribed"), None)
                if un:
                    unsubscribed = datetime.fromisoformat(un.replace("Z", "+00:00"))

        # A few sends that break ENG-12, each flagged.
        def pick(pred, k):
            pool = [h for h in hcps if rep_for.get(h["state"]) and pred(h)]
            return rng.sample(pool, min(k, len(pool)))
        for h in pick(lambda h: h["status"] == "active" and not h["consent"]["approved_email"] and not h["quality_flags"], 2):
            add(h, rep_for[h["state"]], business_time(START + timedelta(days=rng.randrange(days)), h["state"]), ["email_without_consent"])
        for h in pick(lambda h: h["status"] != "active" and h["consent"]["approved_email"]
                      and (h["deactivated_on"] is None or h["deactivated_on"] < str(START)), 2):
            add(h, rep_for[h["state"]], business_time(START + timedelta(days=rng.randrange(days)), h["state"]), ["email_to_inactive"])
        unsubs = [r for r in out if any(e["type"] == "unsubscribed" for e in r["events"]) and not r["quality_flags"]]
        for r in rng.sample(unsubs, min(2, len(unsubs))):
            h = next(x for x in hcps if x["id"] == r["hcp_id"])
            un = datetime.fromisoformat(next(e["at"] for e in r["events"] if e["type"] == "unsubscribed").replace("Z", "+00:00"))
            later = business_time(un.date() + timedelta(days=rng.randrange(7, 40)), h["state"])
            if later.date() <= AS_OF:
                add(h, r["sender_id"], later, ["email_without_consent"])
        other = sorted({t["rep_id"] for t in ff["territories"]})
        for h in pick(lambda h: h["status"] == "active" and h["consent"]["approved_email"] and not h["quality_flags"], 1):
            wrong = next(r for r in other if r != rep_for[h["state"]])
            add(h, wrong, business_time(START + timedelta(days=rng.randrange(days)), h["state"]), ["email_outside_territory"])

        out.sort(key=lambda r: (r["sent_at"], r["hcp_id"]))
        for i, r in enumerate(out):
            r["id"] = self.make_id(i)
        return out
