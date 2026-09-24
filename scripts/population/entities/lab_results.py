"""Lab results: monitoring blood tests for patients on QUORVANTA, on the label's schedule."""

from datetime import date, timedelta

from population.core import AS_OF, Entity, register

# Codes verified against the NLM LOINC search. Reference ranges are typical adult values chosen for this pack.
TESTS = {
    "WBC": {"loinc": "6690-2", "name": "Leukocytes [#/volume] in Blood by Automated count", "unit": "10*9/L", "low": 4.0, "high": 11.0},
    "LYMPH": {"loinc": "731-0", "name": "Lymphocytes [#/volume] in Blood by Automated count", "unit": "10*9/L", "low": 1.0, "high": 4.8},
    "ALT": {"loinc": "1742-6", "name": "Alanine aminotransferase [Enzymatic activity/volume] in Serum or Plasma", "unit": "U/L", "low": 7, "high": 40},
    "AST": {"loinc": "1920-8", "name": "Aspartate aminotransferase [Enzymatic activity/volume] in Serum or Plasma", "unit": "U/L", "low": 10, "high": 40},
    "ALP": {"loinc": "6768-6", "name": "Alkaline phosphatase [Enzymatic activity/volume] in Serum or Plasma", "unit": "U/L", "low": 40, "high": 129},
    "TBIL": {"loinc": "1975-2", "name": "Bilirubin.total [Mass/volume] in Serum or Plasma", "unit": "mg/dL", "low": 0.1, "high": 1.2},
    "CREAT": {"loinc": "2160-0", "name": "Creatinine [Mass/volume] in Serum or Plasma", "unit": "mg/dL", "low": 0.6, "high": 1.3},
    "EGFR": {"loinc": "98979-8", "name": "Glomerular filtration rate [Volume Rate/Area] in Serum, Plasma or Blood by Creatinine-based formula (CKD-EPI 2021)/1.73 sq M",
             "unit": "mL/min/{1.73_m2}", "low": 60, "high": None},
}
PANELS = {"CBC": ["WBC", "LYMPH"], "HEPATIC": ["ALT", "AST", "ALP", "TBIL"], "RENAL": ["CREAT", "EGFR"]}


def ckd_epi_2021(creat, age, sex):
    """eGFR (mL/min/1.73 m2) from serum creatinine (mg/dL), by the 2021 race-free CKD-EPI equation."""
    k, a = (0.7, -0.241) if sex == "female" else (0.9, -0.302)
    v = 142 * min(creat / k, 1) ** a * max(creat / k, 1) ** -1.200 * 0.9938 ** age
    return round(v * (1.012 if sex == "female" else 1))


def age_on(dob, day):
    b, d = date.fromisoformat(dob), date.fromisoformat(day)
    return d.year - b.year - ((d.month, d.day) < (b.month, b.day))


def flag(test, value):
    t = TESTS[test]
    if t["low"] is not None and value < t["low"]:
        return "L"
    if t["high"] is not None and value > t["high"]:
        return "H"
    return "N"


@register
class LabResults(Entity):
    name = "lab-results"
    id_prefix = "PLRS"
    default_count = 400
    count_means = "patients monitored"
    requires = ("patients", "labs")
    references = {"patient_id": "patients", "lab_id": "labs", "ordering_hcp_id": "hcps", "quality_flags[].of": "lab-results"}
    notice = ("FICTITIOUS. Generated laboratory results for patients who do not exist, taking a product that does not exist. "
              "The values are simulated and are not medical information. Test codes are LOINC codes (see the LICENSE file "
              "for the LOINC notice); reference ranges are typical adult values chosen for this pack.")
    usage = ("One record per specimen. For every patient who started QUORVANTA (patients.therapy.started_on): a baseline "
             "complete blood count, liver tests and renal function before starting (label 2.1); a blood count 3 months "
             "after starting and every 6 months after that (2.4); liver tests when clinically indicated; and, for "
             "patients who stopped because of lymphopenia, blood counts until recovery (5.4). eGFR is computed from "
             "creatinine, age and sex by the CKD-EPI 2021 equation. patterns marks clinically meaningful situations; "
             "quality_flags marks data problems. --count sets how many patients are monitored.")
    flags = {
        "unit_mismatch": "The lymphocyte count is reported in cells/uL (unit '/uL') instead of 10*9/L, so it reads 1000 times too high.",
        "duplicate": "The same result sent twice under a new record id; 'of' is the original.",
        "canceled_specimen": "The specimen could not be tested (status canceled, cancel_reason set) and was recollected.",
        "lab_certificate_lapsed": "Reported by a lab whose CLIA certificate had lapsed before collection.",
    }
    patterns = {
        "low_baseline_lymphocytes": "Baseline lymphocyte count below 1.0 x 10^9/L. The label has no data on starting in low counts (5.4; GAP-08).",
        "prolonged_severe_lymphopenia": "Lymphocyte counts below 0.5 x 10^9/L for at least 6 months up to this result; the label says to consider interrupting treatment (5.4).",
        "alt_above_3x_uln": "ALT more than 3 times the upper limit of normal.",
        "hepatic_signal": "ALT above 5 times and total bilirubin above 2 times the upper limit of normal (5.5).",
        "moderate_renal_impairment_at_baseline": "Baseline eGFR 30 to 59; the label does not recommend QUORVANTA in moderate or severe renal impairment (8.6).",
        "severe_renal_impairment_at_baseline": "Baseline eGFR below 30 (8.6).",
        "missed_previous_scheduled_cbc": "The scheduled blood count before this one was never done.",
        "overdue_at_as_of": "The next scheduled blood count is more than 30 days overdue on the as_of date; 'due' gives the date.",
        "follow_up_after_discontinuation": "A blood count after stopping QUORVANTA for lymphopenia, continued until recovery (5.4).",
    }
    header = {"tests": TESTS, "panels": PANELS}

    def generate(self, ctx, count):
        rng = ctx.rng(self.name)
        patients = [p for p in ctx.records("patients") if p["therapy"]["started_on"]][:count]
        labs = [l for l in ctx.records("labs") if not l["quality_flags"] or l["quality_flags"][0]["type"] == "certificate_lapsed"]
        out = []
        hepatic_signal_done = False

        lapsed = [l for l in labs if l["certificate_lapsed_on"]]

        def lab_for(state):
            # Some patients in the lapsed lab's area keep using it, so its late results exist.
            if lapsed and state in lapsed[0]["states_served"] and rng.random() < 0.35:
                return lapsed[0]
            options = [l for l in labs if state in l["states_served"]]
            national = [l for l in options if l["type"] == "national_reference_lab"]
            return rng.choice(national) if national and rng.random() < 0.6 else rng.choice(options)

        for p in patients:
            start = date.fromisoformat(p["therapy"]["started_on"])
            stop = date.fromisoformat(p["therapy"]["discontinued_on"]) if p["therapy"]["discontinued_on"] else None
            lymph_stop = p["therapy"]["discontinued_reason"] == "lymphopenia"
            lab = lab_for(p["state"])

            # Patient-level trajectory.
            l0 = min(3.8, max(1.05, rng.gauss(1.95, 0.45)))
            if rng.random() < 0.03:
                l0 = rng.uniform(0.65, 0.95)
            severe = lymph_stop or rng.random() < 0.05
            drop = rng.uniform(0.75, 0.85) if severe else min(0.45, max(0.05, rng.gauss(0.25, 0.08)))
            alt0 = min(38, max(9, rng.gauss(22, 7)))
            alt_bump = rng.choice([1.0] * 8 + [1.6, 2.2]) if rng.random() < 0.9 else rng.uniform(3.2, 4.5)
            # Exactly one liver-injury signal, in the first patient with enough time on treatment.
            signal = not hepatic_signal_done and not severe and stop is None and (AS_OF - start).days > 180
            hepatic_signal_done = hepatic_signal_done or signal
            renal_roll = rng.random()
            creat_scale = 2.4 if renal_roll < 0.005 else 1.55 if renal_roll < 0.045 else 1.0
            base_creat = (0.75 if p["sex"] == "female" else 0.95) * creat_scale * rng.uniform(0.85, 1.15)

            def lymph_at(day):
                months = (day - start).days / 30.4
                if months <= 0:
                    return l0
                v = l0 * (1 - drop * min(months / (7 if severe else 12), 1))
                if stop and day > stop:
                    weeks = (day - stop).days / 7
                    v_stop = l0 * (1 - drop)
                    v = v_stop + (l0 - v_stop) * min(weeks / (84 if severe else 18), 1)
                return max(0.12, v + rng.gauss(0, 0.05 if severe else 0.08))

            # Schedule: baseline, month 3, then every 6 months; liver tests when clinically indicated.
            visits = [(start - timedelta(days=rng.randrange(7, 40)), "baseline", ["CBC", "HEPATIC", "RENAL"])]
            due = start + timedelta(days=91)
            skip_one = rng.random() < 0.08
            skipped = None
            while due <= AS_OF and (stop is None or due <= stop):
                day = due + timedelta(days=rng.randrange(-10, 15))
                if day > AS_OF or (stop and day > stop):
                    break
                reason = "month_3" if due == start + timedelta(days=91) else "every_6_months"
                if skip_one and skipped is None and rng.random() < 0.5:
                    skipped = due
                else:
                    panels = ["CBC"] + (["HEPATIC"] if reason == "month_3" and rng.random() < 0.4 else [])
                    visits.append((day, reason, panels))
                due = due + timedelta(days=182 if reason != "month_3" else 182)
            if alt_bump > 1 or signal:
                early = start + timedelta(days=rng.randrange(30, 150))
                if early <= AS_OF and (stop is None or early <= stop):
                    visits.append((early, "clinically_indicated", ["HEPATIC"]))
            if stop and lymph_stop:
                day = stop + timedelta(days=42)
                while day <= AS_OF:
                    visits.append((day, "post_discontinuation_follow_up", ["CBC"]))
                    if lymph_at(day) >= 0.9:
                        break
                    day += timedelta(days=rng.randrange(42, 63))
            visits.sort(key=lambda v: v[0])

            severe_since = None
            prev_scheduled_missing = skipped
            for day, reason, panels in visits:
                d = str(day)
                age = age_on(p["dob"], d)
                results, patterns, quality = [], [], []
                for panel in panels:
                    for test in PANELS[panel]:
                        if test == "LYMPH":
                            v = round(lymph_at(day), 2)
                        elif test == "WBC":
                            v = round(lymph_at(day) + rng.uniform(2.8, 5.2), 1)
                        elif test in ("ALT", "AST"):
                            months = (day - start).days / 30.4
                            mult = alt_bump if 0 < months < 6 and reason == "clinically_indicated" else 1.0
                            base = alt0 if test == "ALT" else alt0 * rng.uniform(0.8, 1.05) + 3
                            v = round(base * mult * rng.uniform(0.9, 1.1))
                            if signal and reason == "clinically_indicated":
                                v = round(rng.uniform(5.6, 7.5) * TESTS[test]["high"])
                        elif test == "ALP":
                            v = round(rng.gauss(80, 18))
                        elif test == "TBIL":
                            v = round(rng.uniform(2.6, 3.4) if signal and reason == "clinically_indicated" else max(0.2, rng.gauss(0.6, 0.18)), 1)
                        elif test == "CREAT":
                            v = round(base_creat * rng.uniform(0.95, 1.05), 2)
                        else:
                            v = ckd_epi_2021(results[-1]["value"], age, p["sex"])
                        t = TESTS[test]
                        results.append({"test": test, "loinc": t["loinc"], "value": v, "unit": t["unit"],
                                        "ref_low": t["low"], "ref_high": t["high"], "flag": flag(test, v)})
                values = {r["test"]: r["value"] for r in results}
                if "LYMPH" in values:
                    if values["LYMPH"] < 0.5:
                        severe_since = severe_since or day
                        if (day - severe_since).days >= 182:
                            patterns.append({"type": "prolonged_severe_lymphopenia", "since": str(severe_since)})
                    else:
                        severe_since = None
                if reason == "baseline":
                    if values["LYMPH"] < 1.0:
                        patterns.append({"type": "low_baseline_lymphocytes"})
                    if values["EGFR"] < 30:
                        patterns.append({"type": "severe_renal_impairment_at_baseline"})
                    elif values["EGFR"] < 60:
                        patterns.append({"type": "moderate_renal_impairment_at_baseline"})
                if values.get("ALT", 0) > 200 and values.get("TBIL", 0) > 2.4:
                    patterns.append({"type": "hepatic_signal"})
                elif values.get("ALT", 0) > 120:
                    patterns.append({"type": "alt_above_3x_uln"})
                if reason == "post_discontinuation_follow_up":
                    patterns.append({"type": "follow_up_after_discontinuation"})
                if prev_scheduled_missing and reason in ("every_6_months", "month_3") and day > prev_scheduled_missing:
                    patterns.append({"type": "missed_previous_scheduled_cbc", "due": str(prev_scheduled_missing)})
                    prev_scheduled_missing = None
                if lab["certificate_lapsed_on"] and d > lab["certificate_lapsed_on"]:
                    quality.append({"type": "lab_certificate_lapsed"})
                rec = {"id": self.make_id(len(out)), "patient_id": p["id"], "ordering_hcp_id": p["prescriber_id"],
                       "lab_id": lab["id"], "accession": f"{lab['clia'][-4:]}-{rng.randrange(10 ** 8):08d}",
                       "collected_on": d, "reported_on": str(day + timedelta(days=rng.choice([1, 1, 2, 3]))),
                       "reason": reason, "panels": panels, "status": "final", "cancel_reason": None,
                       "results": results, "patterns": patterns, "quality_flags": quality}
                roll = rng.random()
                if roll < 0.01 and "HEPATIC" in panels and reason != "baseline":
                    out.append(dict(rec, status="canceled", cancel_reason="hemolyzed specimen", results=[], patterns=[],
                                    quality_flags=quality + [{"type": "canceled_specimen"}]))
                    rec = dict(rec, id=self.make_id(len(out)), collected_on=str(day + timedelta(days=2)),
                               reported_on=str(day + timedelta(days=3)))
                elif roll < 0.02 and "LYMPH" in values:
                    rec["results"] = [dict(r, value=round(r["value"] * 1000), unit="/uL") if r["test"] == "LYMPH" else r for r in results]
                    rec["quality_flags"] = quality + [{"type": "unit_mismatch"}]
                if rec["reported_on"] > str(AS_OF):
                    rec["reported_on"] = str(AS_OF)
                out.append(rec)
                if rng.random() < 0.01:
                    out.append(dict(rec, id=self.make_id(len(out)), quality_flags=rec["quality_flags"] + [{"type": "duplicate", "of": rec["id"]}]))
            last_cbc = max((date.fromisoformat(r["collected_on"]) for r in out
                            if r["patient_id"] == p["id"] and "CBC" in r["panels"] and r["status"] == "final"), default=None)
            if (stop is None and last_cbc and prev_scheduled_missing and (AS_OF - prev_scheduled_missing).days > 30
                    and last_cbc < prev_scheduled_missing):
                last = next(r for r in reversed(out) if r["patient_id"] == p["id"] and r["status"] == "final")
                last["patterns"].append({"type": "overdue_at_as_of", "due": str(prev_scheduled_missing)})
        return out
