"""Speaker programs: promotional talks on the QUORVANTA speaker deck, with attendance, meals, honoraria and travel."""

import json
from collections import defaultdict
from datetime import date, timedelta

from population.core import AS_OF, PLACE_ENDS, PLACE_STEMS, SRC, Entity, register

FIRST_PROGRAM = date(2024, 3, 19)
RULES = SRC / "speaker-programs/speaker-program-rules.json"
RESTAURANT_KINDS = ["Kitchen", "Grill", "Bistro", "Chophouse", "Table", "Brasserie"]
HOTEL_ROOMS = ["Juniper", "Linden", "Larch", "Quill", "Rowan", "Heron"]
STARTS = {"in_person": "18:30", "in_office": "12:15", "virtual": "19:00"}


def deck_versions():
    """(first use, job code) of each filed version of the speaker deck, oldest first."""
    rules = json.loads(RULES.read_text())
    subs = json.loads((SRC / "regulatory/opdp-submissions.json").read_text())["submissions"]
    return sorted((m["first_use"], m["material_id"]) for s in subs for m in s["materials"] if m.get("piece") == rules["deck_piece"])


def per_person(p):
    eaters = sum(a["ate"] for a in p["attendees"]) + sum(a["ate"] for a in p["staff_attendees"]) + p["guests"] \
        + (1 if p["speaker_ate"] else 0)
    return p["meal_total"] / eaters if eaters else 0.0


def program_flags(programs, speakers, rules):
    """SPK-01 to SPK-08 for every program, in date order (repeat attendance and the annual cap depend on earlier ones)."""
    versions = deck_versions()
    by_id = {s["id"]: s for s in speakers}
    seen, year_total = defaultdict(list), defaultdict(float)
    for p in sorted(programs, key=lambda p: (p["date"], p["id"] or "")):
        flags = [f for f in p["quality_flags"] if f["type"] == "payment_not_reported"]
        s, d = by_id[p["speaker_id"]], p["date"]
        current = [code for fu, code in versions if fu <= d][-1]
        if not s["contract"]["from"] <= d <= s["contract"]["to"]:
            flags.append({"type": "speaker_not_contracted"})
        if not any(t["deck"] == p["deck_job_code"] and t["trained_on"] < d for t in s["trainings"]):
            flags.append({"type": "untrained_speaker"})
        if p["deck_job_code"] != current:
            flags.append({"type": "superseded_deck"})
        if p["venue"]["type"] not in rules["allowed_venue_types"]:
            flags.append({"type": "entertainment_venue"})
        if p["status"] == "completed":
            if p["honorarium"] != rules["honoraria"][p["format"]][s["tier"]]:
                flags.append({"type": "honorarium_off_rate"})
            year_total[(s["id"], d[:4])] += p["honorarium"]
            if year_total[(s["id"], d[:4])] > rules["annual_honoraria_cap"]:
                flags.append({"type": "over_annual_cap"})
            pp = per_person(p)
            state = rules["state_restrictions"].get(p["venue"]["state"], {})
            if pp > rules["meal_cap_per_person"]:
                flags.append({"type": "meal_over_cap"})
            if p["meal_total"] and (not state.get("meals", True) or pp > state.get("meal_cap_per_person", float("inf"))):
                flags.append({"type": "state_meal_restriction"})
            if p["guests"]:
                flags.append({"type": "guest_meal"})
            signed = [a["hcp_id"] for a in p["attendees"] if a["signed_in"]]
            if len(signed) < rules["minimum_attendees"]:
                flags.append({"type": "low_attendance"})
            cutoff = str(date.fromisoformat(d) - timedelta(days=rules["repeat_window_days"]))
            for h in signed:
                if any(cutoff < prev < d for prev in seen[h]):
                    flags.append({"type": "repeat_attendee", "hcp_id": h})
                seen[h].append(d)
        p["quality_flags"] = flags


@register
class SpeakerPrograms(Entity):
    name = "speaker-programs"
    id_prefix = "PSPG"
    default_count = 150
    count_means = "programs before plants"
    requires = ("speakers", "hcps", "offices", "office-staff")
    references = {"speaker_id": "speakers", "attendees[].hcp_id": "hcps", "staff_attendees[].staff_id": "office-staff",
                  "venue.office_id": "offices", "quality_flags[].hcp_id": "hcps"}
    notice = ("FICTITIOUS. Speaker programs for a product that does not exist, given by speakers who do not exist, at venues "
              "that do not exist. Venue names are invented.")
    usage = ("One record per QUORVANTA speaker program from launch to the as_of date, against "
             "speaker-programs/speaker-program-rules.json. deck_job_code is the deck version presented; host_rep_id the "
             "representative whose territory (crm/field-force.json) covers the venue's state. attendees are the prescribers "
             "who registered, with signed_in and ate; staff_attendees are office staff, who are not covered recipients; "
             "guests counts meals for people who are not healthcare professionals. speaker_ate says whether the speaker ate. "
             "meal_total, honorarium and travel_total are US dollars. Every quality flag follows from the record and the "
             "rules, except payment_not_reported, which marks a payment missing from population/open-payments.json.")
    flags = {
        "speaker_not_contracted": "The speaker's contract did not cover the program date (SPK-01).",
        "untrained_speaker": "The speaker had not been trained on the deck version presented (SPK-01).",
        "superseded_deck": "A deck version other than the one current on the program date was presented (SPK-02).",
        "honorarium_off_rate": "The honorarium is not the rate for the speaker's tier and the format (SPK-03).",
        "over_annual_cap": "The honorarium took the speaker's calendar-year total over the annual cap (SPK-03).",
        "meal_over_cap": "The meal cost per person exceeds the cap (SPK-04).",
        "state_meal_restriction": "A meal that the venue state's policy bans or caps lower (SPK-04).",
        "guest_meal": "A meal for a guest who is not a healthcare professional (SPK-05).",
        "low_attendance": "Fewer signed-in prescribers than the minimum (SPK-06).",
        "repeat_attendee": "hcp_id attended a program on the same deck within the repeat window (SPK-07).",
        "entertainment_venue": "A venue type outside the allowed list (SPK-08).",
        "payment_not_reported": "The payment to hcp_id of nature is missing from open-payments.json (OPR-04).",
    }
    patterns = {
        "cancelled": "Cancelled before it took place; no meal, honorarium or travel.",
        "no_shows": "Some registered prescribers did not sign in.",
        "speaker_travel": "The speaker traveled from another state.",
    }

    def generate(self, ctx, count):
        rng = ctx.rng(self.name)
        rules = json.loads(RULES.read_text())
        versions = deck_versions()
        speakers = ctx.records("speakers")
        hcps = [h for h in ctx.records("hcps") if h["status"] == "active" and not h["quality_flags"]]
        offices = {o["id"]: o for o in ctx.records("offices")}
        staff = [s for s in ctx.records("office-staff") if s["status"] == "active" and not s["quality_flags"]]
        ff = json.loads((SRC / "crm/field-force.json").read_text())
        territory_of = {st: t for t in ff["territories"] for st in t["states"]}
        speaker_hcps = {s["hcp_id"] for s in speakers}
        by_state = defaultdict(list)
        for h in hcps:
            if h["id"] not in speaker_hcps and h["state"] in territory_of:
                by_state[h["state"]].append(h)
        last_seen = {}
        programs = []

        def current_deck(d):
            return [code for fu, code in versions if fu <= str(d)][-1]

        def eligible(d, deck):
            return [s for s in speakers if s["contract"]["from"] <= str(d) <= s["contract"]["to"]
                    and any(t["deck"] == deck and t["trained_on"] < str(d) for t in s["trainings"])]

        def venue_name(kind):
            stem, end = rng.choice(PLACE_STEMS), rng.choice(PLACE_ENDS)
            if kind == "restaurant_private_room":
                return f"{stem}{end} {rng.choice(RESTAURANT_KINDS)}, private dining room"
            return f"{stem}{end} Hotel, {rng.choice(HOTEL_ROOMS)} Room"

        def make(d, s, fmt, state, deck=None, size=None, office=None, allow_repeat=()):
            """One program, or None if the state cannot fill it without repeat attendees."""
            deck = deck or current_deck(d)
            cutoff = str(d - timedelta(days=rules["repeat_window_days"]))
            fresh = lambda h: h["id"] not in last_seen or last_seen[h["id"]] <= cutoff or h["id"] in allow_repeat  # noqa: E731
            if fmt == "in_office":
                if office is None:
                    sites = defaultdict(list)
                    for h in by_state[state]:
                        if fresh(h):
                            sites[h["primary_office_id"]].append(h)
                    sites = [o for o, hs in sites.items() if len(hs) >= rules["minimum_attendees"] and offices[o]["status"] == "active"]
                    if not sites:
                        return None
                    office = rng.choice(sorted(sites))
                pool = [h for h in by_state[state] if h["primary_office_id"] == office and fresh(h)]
                venue = {"type": "office", "name": offices[office]["name"], "city": offices[office]["city"], "state": state,
                         "office_id": office}
            else:
                pool = [h for h in by_state[state] if fresh(h)] if fmt == "in_person" else \
                    [h for st in territory_of[state]["states"] for h in by_state[st] if fresh(h)]
                kind = "virtual" if fmt == "virtual" else rng.choice(["restaurant_private_room"] * 3 + ["hotel_meeting_room"])
                venue = {"type": kind, "name": "Arden Quay virtual program" if kind == "virtual" else venue_name(kind),
                         "city": None if kind == "virtual" else ctx.faker(self.name).city(), "state": state, "office_id": None}
            n = size or {"in_person": rng.randint(4, 10), "in_office": len(pool), "virtual": rng.randint(5, 14)}[fmt]
            n = min(n, len(pool), 9)
            if n < rules["minimum_attendees"]:
                return None
            chosen = sorted(rng.sample(pool, n), key=lambda h: h["id"])
            attendees = []
            for h in chosen:
                shown = rng.random() > 0.08
                attendees.append({"hcp_id": h["id"], "signed_in": shown, "ate": shown and fmt != "virtual"})
            while sum(a["signed_in"] for a in attendees) < rules["minimum_attendees"]:
                a = next(a for a in attendees if not a["signed_in"])
                a["signed_in"], a["ate"] = True, fmt != "virtual"
            staff_att = []
            if fmt == "in_office":
                here = [x for x in staff if office in x["office_ids"]]
                staff_att = [{"staff_id": x["id"], "ate": True} for x in sorted(rng.sample(here, min(len(here), rng.randint(1, 3))), key=lambda x: x["id"])]
            p = {"id": None, "date": str(d), "starts_at_local": STARTS[fmt], "format": fmt, "status": "completed",
                 "deck_job_code": deck, "speaker_id": s["id"], "host_rep_id": territory_of[state]["rep_id"], "venue": venue,
                 "attendees": attendees, "staff_attendees": staff_att, "guests": 0, "speaker_ate": fmt != "virtual",
                 "meal_total": 0.0, "honorarium": rules["honoraria"][fmt][s["tier"]], "travel_total": 0.0,
                 "patterns": [], "quality_flags": []}
            if fmt != "virtual":
                cap = rules["state_restrictions"].get(state, {}).get("meal_cap_per_person", rules["meal_cap_per_person"])
                lo, hi = (14, 34) if fmt == "in_office" else (58, 118)
                set_meal(p, min(rng.uniform(lo, hi), cap - 2))
            if fmt != "virtual" and state != s["state"]:
                p["travel_total"] = round(rng.uniform(380, 1150), 2)
                p["patterns"].append({"type": "speaker_travel"})
            if not all(a["signed_in"] for a in attendees):
                p["patterns"].append({"type": "no_shows"})
            for a in attendees:
                if a["signed_in"]:
                    last_seen[a["hcp_id"]] = str(d)
            programs.append(p)
            return p

        def set_meal(p, target_pp):
            p["meal_total"] = round(target_pp * eaters(p), 2)

        def eaters(p):
            return sum(a["ate"] for a in p["attendees"]) + sum(a["ate"] for a in p["staff_attendees"]) + p["guests"] \
                + (1 if p["speaker_ate"] else 0)

        def pick_state(s, fmt):
            if s["tier"] == "local":
                state = s["state"]
            elif s["tier"] == "regional":
                state = rng.choice(territory_of[s["state"]]["states"])
            else:
                states = sorted(by_state)
                state = rng.choices(states, weights=[len(by_state[x]) for x in states])[0]
            if rules["state_restrictions"].get(state, {}).get("meals") is False and fmt != "virtual":
                return None
            return state

        days = [FIRST_PROGRAM + timedelta(days=i) for i in range((AS_OF - FIRST_PROGRAM).days + 1)]
        days = [d for d in days if d.weekday() in (1, 2, 3)]
        tier_weight = {"national": 3, "regional": 2, "local": 1}
        made = 0
        for d in sorted(rng.sample(days, min(count, len(days)))):
            pool = eligible(d, current_deck(d))
            if not pool:
                continue
            for _ in range(10):
                s = rng.choices(pool, weights=[tier_weight[x["tier"]] for x in pool])[0]
                fmt = rng.choices(["in_person", "in_office", "virtual"], weights=[55, 30, 15])[0]
                state = pick_state(s, fmt)
                if state and make(d, s, fmt, state):
                    made += 1
                    break

        def on(d):
            d = date.fromisoformat(d) if isinstance(d, str) else d
            while d.weekday() not in (1, 2, 3):
                d += timedelta(days=1)
            return d

        planted = []

        def plant(d, s, fmt, state, latest=AS_OF, strict=False, **kw):
            """A program on the first possible date from d, in state, or (unless strict) the largest state that can fill it."""
            d = on(d)
            others = sorted((x for x in by_state if x not in rules["state_restrictions"] and x != state), key=lambda x: -len(by_state[x]))
            states = [state] if strict else [x for x in [state] if x] + others
            while d <= latest:
                for f in (fmt, "in_person"):
                    for st in states:
                        p = make(d, s, f, st, **kw)
                        if p:
                            planted.append(p)
                            return p
                d = on(d + timedelta(days=7))
            raise SystemExit(f"speaker-programs: could not plant a {fmt} program in {state} by {latest}")

        def take(pool, k):
            got = rng.sample([p for p in pool if p not in planted], k)
            planted.extend(got)
            return got

        in_person = [p for p in programs if p["format"] == "in_person"]
        by_sid = {s["id"]: s for s in speakers}
        # Meals over the cap, guest meals and low attendance, on existing programs.
        for p in take(in_person, 2):
            set_meal(p, rng.uniform(138, 162))
        for p in take(in_person, 2):
            pp = p["meal_total"] / eaters(p)
            p["guests"] = 1
            set_meal(p, pp)
        for p in take([p for p in in_person if sum(a["signed_in"] for a in p["attendees"]) >= 4], 2):
            pp = p["meal_total"] / eaters(p)
            for a in p["attendees"][2:]:
                a["signed_in"] = a["ate"] = False
            if {"type": "no_shows"} not in p["patterns"]:
                p["patterns"].append({"type": "no_shows"})
            set_meal(p, pp)
        # Repeat attendees: a prescriber from an earlier program in the same state signs in to a later one within the window.
        pairs = [(a, b) for a in in_person for b in in_person
                 if a["venue"]["state"] == b["venue"]["state"] and 30 < (date.fromisoformat(b["date"]) - date.fromisoformat(a["date"])).days < 300
                 and a not in planted and b not in planted]
        for a, b in rng.sample(pairs, min(3, len(pairs))):
            if b in planted:
                continue
            h = next((x["hcp_id"] for x in a["attendees"] if x["signed_in"] and x["hcp_id"] not in {y["hcp_id"] for y in b["attendees"]}), None)
            if h:
                pp = b["meal_total"] / eaters(b)
                b["attendees"] = sorted(b["attendees"] + [{"hcp_id": h, "signed_in": True, "ate": True}], key=lambda x: x["hcp_id"])
                set_meal(b, pp)
                planted.append(b)
        # A New Jersey dinner over the state's cap, and a winery.
        guest_speaker = next(s for s in speakers if s["tier"] == "national" and s["state"] != "NJ")
        p = plant(date(2025, 4, 8), guest_speaker, "in_person", "NJ", strict=True)
        set_meal(p, 78)
        p = plant(date(2025, 10, 14), guest_speaker, "in_person", None)
        p["venue"]["type"], p["venue"]["name"] = "winery", f"{rng.choice(PLACE_STEMS)}mere Cellars, tasting room"
        # A national speaker over the annual cap in 2025.
        heavy = next(s for s in speakers if s["tier"] == "national" and s is not guest_speaker)
        d = date(2025, 1, 14)
        while sum(p["honorarium"] for p in programs if p["speaker_id"] == heavy["id"] and p["date"][:4] == "2025") \
                <= rules["annual_honoraria_cap"] + rules["honoraria"]["in_person"]["national"]:
            plant(d, heavy, "in_person", rng.choice([st for st in by_state if st not in rules["state_restrictions"]]))
            d += timedelta(days=21)
        # The wrong rate, a lapsed contract, a missed training and the superseded deck after September 14, 2026.
        regional = next(s for s in speakers if s["tier"] == "regional")
        p = plant(date(2025, 6, 10), regional, "in_person", regional["state"])
        p["honorarium"] = rules["honoraria"]["in_person"]["national"]
        lapsed = next(s for s in speakers if any(x["type"] == "contract_lapsed" for x in s["patterns"]))
        plant(date(2026, 7, 21), lapsed, "in_person", lapsed["state"])
        missed = next(s for s in speakers if any(x["type"] == "not_trained_on_current_deck" for x in s["patterns"])
                      and s is not lapsed)
        plant(date(2026, 9, 15), missed, "in_office", missed["state"])
        old = next(s for s in speakers if s["tier"] == "local" and s is not missed and s is not lapsed)
        plant(date(2026, 9, 15), old, "in_person", old["state"], deck=versions[0][1])
        # A few cancellations.
        for p in take([p for p in programs if p["date"] < "2026-09-01" and p["speaker_id"] != heavy["id"]], 4):
            p.update(status="cancelled", meal_total=0.0, honorarium=0, travel_total=0.0, guests=0, speaker_ate=False,
                     staff_attendees=[], patterns=[{"type": "cancelled"}])
            for a in p["attendees"]:
                a["signed_in"] = a["ate"] = False
        # Two payments left out of Open Payments, in the 2025 program year.
        done = [p for p in programs if p["status"] == "completed" and p["date"][:4] == "2025" and p["format"] == "in_person"
                and p not in planted]
        p = rng.choice(done)
        p["quality_flags"].append({"type": "payment_not_reported", "hcp_id": next(a["hcp_id"] for a in p["attendees"] if a["ate"]),
                                   "nature": "food_and_beverage"})
        p = rng.choice([x for x in done if x["travel_total"]])
        p["quality_flags"].append({"type": "payment_not_reported", "hcp_id": by_sid[p["speaker_id"]]["hcp_id"],
                                   "nature": "travel_and_lodging"})

        programs.sort(key=lambda p: (p["date"], p["speaker_id"]))
        for i, p in enumerate(programs):
            p["id"] = self.make_id(i)
        program_flags(programs, speakers, rules)
        return programs
