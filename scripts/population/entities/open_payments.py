"""Open Payments: the transfers of value from speaker programs, as Arden Quay reports them to the federal program."""

import json
from collections import defaultdict

from population.core import Entity, register
from population.entities.speaker_programs import RULES, per_person

RECIPIENT_TYPE = {"MD": "Covered Recipient Physician", "DO": "Covered Recipient Physician",
                  "NP": "Covered Recipient Non-Physician Practitioner", "PA-C": "Covered Recipient Non-Physician Practitioner"}


def expected_payments(programs, speakers, rules):
    """Every payment OPR-01 to OPR-03 require, as (program id, hcp id, nature) -> amount, before any omission."""
    by_sid = {s["id"]: s for s in speakers}
    owed = {}
    for p in programs:
        if p["status"] != "completed":
            continue
        pp = round(per_person(p), 2)
        speaker = by_sid[p["speaker_id"]]["hcp_id"]
        for a in p["attendees"]:
            if a["signed_in"] and a["ate"]:
                owed[(p["id"], a["hcp_id"], "food_and_beverage")] = pp
        if p["speaker_ate"] and p["meal_total"]:
            owed[(p["id"], speaker, "food_and_beverage")] = pp
        if p["honorarium"]:
            owed[(p["id"], speaker, "speaker_compensation")] = float(p["honorarium"])
        if p["travel_total"]:
            owed[(p["id"], speaker, "travel_and_lodging")] = p["travel_total"]
    dates = {p["id"]: p["date"] for p in programs}
    totals = defaultdict(float)
    for (pid, h, _), amt in owed.items():
        totals[(h, dates[pid][:4])] += amt
    th = rules["open_payments"]["thresholds"]
    return {k: v for k, v in owed.items()
            if v >= th[dates[k[0]][:4]]["single"] or totals[(k[1], dates[k[0]][:4])] >= th[dates[k[0]][:4]]["aggregate"]}


@register
class OpenPayments(Entity):
    name = "open-payments"
    id_prefix = "POPR"
    default_count = 1
    count_means = "(not used)"
    requires = ("speaker-programs", "speakers", "hcps")
    references = {"program_id": "speaker-programs", "recipient_hcp_id": "hcps"}
    must_match = {"recipient_npi": ["recipient_hcp_id", "npi"], "first_name": ["recipient_hcp_id", "first_name"],
                  "last_name": ["recipient_hcp_id", "last_name"], "state": ["recipient_hcp_id", "state"]}
    notice = ("FICTITIOUS. Open Payments records for payments that were never made, by a company that does not exist, to "
              "prescribers who do not exist. NPI-shaped ids begin with 91. The layout follows the public general payments "
              "data loosely and is not the federal submission format.")
    usage = ("One record per payment or transfer of value to a covered recipient from a speaker program in "
             "population/speaker-programs.json, as reported under speaker-programs/speaker-program-rules.json (OPR-01 to "
             "OPR-04). nature_of_payment and form_of_payment use the federal program's category names. report_status "
             "follows the program year: 2024 and 2025 are published; 2026 is not yet submitted. A recipient may dispute a "
             "published record; dispute records it. The validator recomputes the full set of records from the programs.")
    flags = {
        "amount_misallocated": "The meal was divided among covered recipients only, not everyone who ate (OPR-03).",
        "reported_no_show": "A meal reported for a prescriber who registered but did not sign in (OPR-03).",
    }
    patterns = {
        "disputed": "The recipient disputed the record in the review period; dispute holds the outcome.",
        "below_single_threshold": "Below the single threshold, reported because the recipient's year reached the aggregate.",
    }

    def generate(self, ctx, count):
        rng = ctx.rng(self.name)
        rules = json.loads(RULES.read_text())
        op = rules["open_payments"]
        programs, speakers = ctx.records("speaker-programs"), ctx.records("speakers")
        hcps = {h["id"]: h for h in ctx.records("hcps")}
        dates = {p["id"]: p["date"] for p in programs}
        owed = expected_payments(programs, speakers, rules)
        for p in programs:
            for f in p["quality_flags"]:
                if f["type"] == "payment_not_reported":
                    owed.pop((p["id"], f["hcp_id"], f["nature"]))
        rows = {k: (v, [], []) for k, v in owed.items()}

        # One in-office lunch divided among the covered recipients alone, and one no-show reported, then disputed.
        office = next(p for p in sorted(programs, key=lambda p: p["date"]) if p["format"] == "in_office" and p["staff_attendees"]
                      and p["status"] == "completed" and p["date"][:4] == "2025" and not p["quality_flags"])
        covered = [k for k in rows if k[0] == office["id"] and k[2] == "food_and_beverage"]
        wrong = round(office["meal_total"] / len(covered), 2)
        for k in covered:
            rows[k] = (wrong, [{"type": "amount_misallocated"}], [])
        noshow = next(p for p in sorted(programs, key=lambda p: p["date"]) if p["date"][:4] == "2025" and p["status"] == "completed"
                      and any(not a["signed_in"] for a in p["attendees"]) and not p["quality_flags"] and p is not office)
        h = next(a["hcp_id"] for a in noshow["attendees"] if not a["signed_in"])
        rows[(noshow["id"], h, "food_and_beverage")] = (
            round(per_person(noshow), 2), [{"type": "reported_no_show"}],
            [{"type": "disputed"}])
        disputes = {(noshow["id"], h, "food_and_beverage"): {
            "opened_on": "2026-04-21", "reason": "The recipient did not attend the program.",
            "status": "unresolved_at_publication"}}
        # A correct record disputed and kept.
        fair = rng.choice(sorted(k for k, v in rows.items() if k[2] == "food_and_beverage" and not v[1] and dates[k[0]][:4] == "2025"))
        rows[fair] = (rows[fair][0], [], [{"type": "disputed"}])
        disputes[fair] = {"opened_on": "2026-05-06", "reason": "The recipient says they did not eat.",
                          "status": "resolved_no_change", "resolved_on": "2026-05-19",
                          "resolution": "The sign-in sheet shows the recipient signed in at the dinner; the record stands."}

        th = op["thresholds"]
        out = []
        for (pid, hid, nature), (amount, flags, patterns) in sorted(rows.items(), key=lambda kv: (dates[kv[0][0]], kv[0])):
            year = dates[pid][:4]
            h = hcps[hid]
            if amount < th[year]["single"]:
                patterns = patterns + [{"type": "below_single_threshold"}]
            out.append({"id": None, "program_id": pid, "recipient_hcp_id": hid, "recipient_npi": h["npi"],
                        "first_name": h["first_name"], "last_name": h["last_name"], "state": h["state"],
                        "recipient_type": RECIPIENT_TYPE[h["credential"]], "date_of_payment": dates[pid],
                        "amount": amount, "nature_of_payment": op["natures_of_payment"][nature],
                        "form_of_payment": op["forms_of_payment"][nature], "product": "QUORVANTA", "program_year": int(year),
                        "report_status": "published" if op["program_years"][year]["published_on"] else "not_yet_submitted",
                        "dispute": disputes.get((pid, hid, nature)), "patterns": patterns, "quality_flags": flags})
        for i, r in enumerate(out):
            r["id"] = self.make_id(i)
        return out
