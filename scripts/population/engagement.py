"""Outreach engine for the generated population: which texts a patient is due, and when.

It reads the rules, messages and campaigns in sources/engagement/ and replays them for one
patient at a time, in time order, against the patient's fills and inbound replies. The
generator for sms-messages drives it with a responder that invents replies; the generator
for campaign-memberships summarizes the schedule it produces. scripts/validate.py checks
the result with its own, independent implementation of the same rules.
"""

import heapq
import json
import unicodedata
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from population.core import SRC

RULES = json.loads((SRC / "engagement/campaign-rules.json").read_text())
MESSAGES = {m["id"]: m for m in json.loads((SRC / "engagement/approved-messages.json").read_text())["messages"]}
LANGUAGES = {"English", "Spanish"}
KEYWORDS = {kind: set(words) for kind, words in RULES["keywords"].items() if kind != "match"}
ZONES = RULES["time_zones"]["zones"]
CAMPAIGN_KINDS = ("CMP-NEVERSTART", "CMP-DISCON-RISK")


def keyword(text):
    """opt_in, opt_out, help, or None for free text."""
    word = unicodedata.normalize("NFKD", text.strip()).encode("ascii", "ignore").decode().upper()
    return next((kind for kind, words in KEYWORDS.items() if word in words), None)


def zone(state):
    return ZoneInfo(ZONES[state])


def local_start(day, state):
    return datetime.combine(day, time(0, 0), zone(state)).astimezone(timezone.utc)


def at_local(day, hour, minute, state):
    return datetime.combine(day, time(hour, minute), zone(state)).astimezone(timezone.utc)


def local_date(dt, state):
    return dt.astimezone(zone(state)).date()


def iso(dt):
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def age_on(dob, day):
    b = date.fromisoformat(dob)
    return day.year - b.year - ((day.month, day.day) < (b.month, b.day))


def body(message_id, language):
    return MESSAGES[message_id]["versions"][language]


class Person:
    """What the rules need to know about a patient, from a population record or a hand-built case."""

    def __init__(self, pid, dob, state, language, insurance_type, government, enrolled_on, contact_consent,
                 text_reminders, started_on, discontinued_on, canceled_on):
        self.id, self.dob, self.state, self.language = pid, dob, state, language
        self.commercial_only = insurance_type == "commercial" and not government
        self.enrolled_on = date.fromisoformat(enrolled_on) if enrolled_on else None
        self.contact_consent, self.text_reminders = contact_consent, text_reminders
        self.started_on = date.fromisoformat(started_on) if started_on else None
        self.discontinued_on = date.fromisoformat(discontinued_on) if discontinued_on else None
        self.canceled_on = date.fromisoformat(canceled_on) if canceled_on else None

    @classmethod
    def from_population(cls, p):
        th, ins = p["therapy"], p["insurance"]
        return cls(p["id"], p["dob"], p["state"], p["language"], ins["type"], ins["government_program"],
                   p["program"]["enrolled_on"] if p["program"]["status"] == "enrolled" else None,
                   p["communications"]["contact_consent"], p["communications"]["text_reminders"],
                   th["started_on"], th["discontinued_on"], th["prescription_canceled_on"])

    def adult(self, day):
        return age_on(self.dob, day) >= 18

    def textable(self, day):
        return self.enrolled_on is not None and self.adult(day) and self.language in LANGUAGES

    def discontinued(self, day):
        return self.discontinued_on is not None and self.discontinued_on <= day


def candidates(person, fills, as_of):
    """Every step that could fall due, as (day, campaign, track, day0, step, message, fill ship date or None)."""
    out = []
    e = person.enrolled_on
    if e is None:
        return out
    out.append((e, "CMP-ACTIVATION", None, e, 0, "MSG-ACT-01", None))
    out.append((e + timedelta(days=7), "CMP-ACTIVATION", None, e, 7, "MSG-ACT-01", None))
    cost = "MSG-NS-COST-COMMERCIAL" if person.commercial_only else "MSG-NS-COST-OTHER"
    for step, msg in ((14, "MSG-NS-STATUS"), (21, cost), (35, "MSG-NS-FIRST-FILL")):
        out.append((e + timedelta(days=step), "CMP-NEVERSTART", None, e, step, msg, None))
    if person.started_on:
        out.append((person.started_on + timedelta(days=10), "CMP-DISCON-RISK", "first_month", person.started_on, 10, "MSG-DR-NURSE", None))
    for f in fills:
        due = f["shipped_on"] + timedelta(days=f["days_supply"])
        out.append((due - timedelta(days=3), "PGM-REFILL-REMINDERS", None, due, -3, "MSG-REM-REFILL", f["shipped_on"]))
        for step, msg in ((7, "MSG-DR-LATE-HELP"), (14, "MSG-DR-LATE-HCP")):
            out.append((due + timedelta(days=step), "CMP-DISCON-RISK", "late_refill", due, step, msg, f["shipped_on"]))
    return sorted((c for c in out if c[0] <= as_of), key=lambda c: (c[0], c[1], c[4]))


class Replay:
    """Replays one patient's outreach in time order.

    respond(outbound) returns inbound replies as (datetime, text) pairs; send_time(day) picks the
    moment a scheduled text goes out. Both are supplied by the caller.
    """

    def __init__(self, person, fills, as_of, respond, send_time, reply_delay, inbound=()):
        self.p, self.as_of = person, as_of
        self.inbound = list(inbound)
        self.suppressed = []      # (candidate, reason): steps that fell due but were not sent
        self.fills = sorted(fills, key=lambda f: f["shipped_on"])
        self.respond, self.send_time, self.reply_delay = respond, send_time, reply_delay
        self.events = []          # outbound and inbound, in time order
        self.keywords = []        # (datetime, opt_in/opt_out)
        self.members = {}         # (campaign, track, day0) -> membership dict
        self._q, self._n = [], 0

    def _push(self, when, kind, data):
        self._n += 1
        heapq.heappush(self._q, (when, self._n, kind, data))

    def opted_in(self, when):
        state = None
        for t, k in self.keywords:
            if t < when:
                state = k
        return state == "opt_in"

    def any_keyword_before(self, when):
        return any(t < when for t, _ in self.keywords)

    def fill_before(self, day):
        return any(f["shipped_on"] < day for f in self.fills)

    def later_fill_before(self, ref, day):
        """A fill shipped after the one shipped on ref, and before day."""
        return any(ref < f["shipped_on"] < day for f in self.fills)

    def run(self):
        p = self.p
        for c in candidates(p, self.fills, self.as_of):
            self._push(local_start(c[0], p.state), "evaluate", c)
        for t, text in self.inbound:
            self._push(t, "inbound", text)
        while self._q:
            when, _, kind, data = heapq.heappop(self._q)
            if local_date(when, self.p.state) > self.as_of:
                continue
            getattr(self, "_" + kind)(when, data)
        return self

    # A step is judged at the start of its day; if due, it is sent later that day.
    def _evaluate(self, when, c):
        day, campaign, track, day0, step, msg, ref = c
        p = self.p
        key = (campaign, track, day0)
        m = self.members.get(key)
        if campaign in CAMPAIGN_KINDS and m is None and step != self._first_step(campaign, track):
            return
        if campaign == "CMP-ACTIVATION" and step == 7 and (m is None or self.any_keyword_before(when)):
            return
        reason = None
        if p.enrolled_on is None:
            return
        if not p.adult(day):
            reason = "to_minor"
        elif p.language not in LANGUAGES:
            reason = "unsupported_language"
        elif campaign == "CMP-ACTIVATION":
            if not p.contact_consent:
                return
        else:
            if not self.opted_in(when):
                reason = "after_opt_out" if any(k == "opt_out" for t, k in self.keywords if t < when) else "no_opt_in"
            elif campaign == "PGM-REFILL-REMINDERS":
                if not p.text_reminders:
                    reason = "no_reminder_choice"
                elif p.discontinued(day) or self.later_fill_before(ref, day):
                    reason = "situation_ended"
            elif not self._situation_holds(campaign, track, ref, day):
                reason = "situation_ended"
        if reason:
            self.suppressed.append((c, reason))
            return
        if m is None and (campaign in CAMPAIGN_KINDS or campaign == "CMP-ACTIVATION"):
            self.members[key] = {"campaign_id": campaign, "track": track, "day0": day0, "entered_on": day, "sends": []}
        self._push(self.send_time(day, p.state, c), "send", (c, key))

    @staticmethod
    def _first_step(campaign, track):
        return 14 if campaign == "CMP-NEVERSTART" else 10 if track == "first_month" else 7

    def _situation_holds(self, campaign, track, ref, day):
        p = self.p
        if campaign == "CMP-NEVERSTART":
            return not self.fill_before(day) and not (p.canceled_on and p.canceled_on <= day)
        if track == "first_month":
            return not p.discontinued(day)
        return not p.discontinued(day) and not self.later_fill_before(ref, day)

    def _send(self, when, data):
        c, key = data
        day, campaign, track, day0, step, msg, ref = c
        needs_optin = campaign != "CMP-ACTIVATION"
        if needs_optin and not self.opted_in(when):
            return
        if campaign == "CMP-ACTIVATION" and step == 7 and self.any_keyword_before(when):
            return
        ev = {"direction": "outbound", "at": when, "message_id": msg, "language": self.p.language,
              "body": body(msg, self.p.language), "campaign_id": campaign,
              "schedule": {"track": track, "day0": str(day0), "step": step}, "in_reply_to": None}
        self.events.append(ev)
        m = self.members.get(key)
        if m is not None:
            m["sends"].append(ev)
        for t, text in self.respond(ev):
            self._push(t, "inbound", text)

    def _inbound(self, when, text):
        kind = keyword(text)
        ev = {"direction": "inbound", "at": when, "body": text, "keyword": kind,
              "routed_to": None if kind else "case_manager"}
        self.events.append(ev)
        if kind in ("opt_in", "opt_out"):
            self.keywords.append((when, kind))
        reply = {"opt_in": "MSG-ACT-02", "opt_out": "MSG-STOP", "help": "MSG-HELP"}.get(kind)
        if kind is None and self.opted_in(when):
            reply = "MSG-REPLY-RECEIVED"
        if reply:
            out = {"direction": "outbound", "at": when + self.reply_delay(), "message_id": reply, "language": self.p.language,
                   "body": body(reply, self.p.language), "campaign_id": None, "schedule": None, "in_reply_to": ev}
            self.events.append(out)
            for t, text2 in self.respond(out):
                self._push(t, "inbound", text2)


def memberships(replay):
    """Each membership with its exit, worked out from the patient's data after the replay."""
    p, fills = replay.p, replay.fills
    out = []
    for (campaign, track, day0), m in sorted(replay.members.items(), key=lambda kv: (kv[1]["entered_on"], kv[0][0], str(kv[0][1]))):
        entered = m["entered_on"]
        kws = [(local_date(t, p.state), k) for t, k in replay.keywords]
        opt_out = next((d for d, k in kws if k == "opt_out" and d >= entered), None)
        exits = []
        if campaign == "CMP-ACTIVATION":
            first = next(((d, k) for d, k in kws if d >= entered), None)
            if first and first[0] <= day0 + timedelta(days=14):
                exits.append((first[0], "opted_in" if first[1] == "opt_in" else "opted_out"))
            else:
                exits.append((day0 + timedelta(days=14), "no_reply"))
        elif campaign == "CMP-NEVERSTART":
            first_fill = min((f["shipped_on"] for f in fills), default=None)
            if first_fill:
                exits.append((first_fill, "first_fill"))
            if p.canceled_on:
                exits.append((p.canceled_on, "prescriber_canceled"))
            if opt_out:
                exits.append((opt_out, "opted_out"))
            exits.append((day0 + timedelta(days=35), "completed"))
        elif track == "first_month":
            exits.append((day0 + timedelta(days=10), "completed"))
        else:
            ref = day0 - timedelta(days=30)
            nxt = min((f["shipped_on"] for f in fills if f["shipped_on"] > ref), default=None)
            if nxt:
                exits.append((nxt, "refilled"))
            if p.discontinued_on:
                exits.append((p.discontinued_on, "discontinued"))
            if opt_out:
                exits.append((opt_out, "opted_out"))
            exits.append((day0 + timedelta(days=14), "completed"))
        exits = [x for x in exits if x[0] >= entered]
        exited = min(exits) if exits else None
        if exited and exited[0] > replay.as_of:
            exited = None
        out.append({"campaign_id": campaign, "track": track, "day0": str(day0), "entered_on": str(entered),
                    "exited_on": str(exited[0]) if exited else None, "exit_reason": exited[1] if exited else None,
                    "sends": m["sends"]})
    return out
