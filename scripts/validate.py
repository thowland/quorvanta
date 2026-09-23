#!/usr/bin/env python3
"""Integrity checks for the QUORVANTA synthetic therapy pack.

Run from anywhere:  python3 scripts/validate.py [--denylist PATH]

Exits non-zero if any check fails. Standard library only.

--denylist names a plain-text file of real brand, company or product names
(one per line, # for comments) that must not appear in the pack. Keep that
file outside the repository: the pack must not contain real names, and a
denylist inside it would.
"""

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "sources"

# Real public-service numbers that the fiction deliberately keeps.
ALLOWED_PHONES = {
    "1-800-FDA-1088",  # FDA MedWatch
    "1-800-222-1222",  # US Poison Control
}
FICTION_PHONE = re.compile(r"^1-800-555-01\d\d$")
# Standards bodies whose canonical URLs FHIR resources and EPCIS documents must carry.
ALLOWED_HOSTS = {"hl7.org", "terminology.hl7.org", "ref.gs1.org"}

errors = []


def fail(msg):
    errors.append(msg)


def load(rel):
    return json.loads((SRC / rel).read_text())


def text(rel):
    return (SRC / rel).read_text()


def check_json_files():
    for path in sorted(SRC.rglob("*.json")):
        rel = path.relative_to(SRC)
        try:
            data = json.loads(path.read_text())
        except json.JSONDecodeError as e:
            fail(f"{rel}: invalid JSON: {e}")
            continue
        if "_notice" not in data:
            fail(f"{rel}: missing _notice field")


def check_markdown_notices():
    for path in sorted([*SRC.rglob("*.md"), *SRC.rglob("*.xml")]):
        head = "\n".join(path.read_text().splitlines()[:6]).lower()
        if "invented" not in head and "fictitious" not in head:
            fail(f"{path.relative_to(SRC)}: no fiction notice in the first lines")


def check_claims_and_references(claims_doc, refs_doc):
    claims = {c["id"]: c for c in claims_doc["claims"]}
    refs = {r["id"]: r for r in refs_doc["references"]}
    findings = {f["id"]: rid for rid, r in refs.items() for f in r["findings"]}

    for cid, c in claims.items():
        for cit in c["reference"].get("citations", []):
            if cit not in findings:
                fail(f"claim {cid}: citation {cit} does not exist")
            elif c["status"] == "approved" and refs[findings[cit]]["status"] != "approved":
                fail(f"claim {cid}: approved claim cites non-approved {cit}")
        for req in c.get("requires", []):
            if req not in claims:
                fail(f"claim {cid}: requires unknown claim {req}")

    for cid in claims_doc["rules"]["isi_claims"]:
        if cid not in claims:
            fail(f"rules.isi_claims: unknown claim {cid}")

    return claims, refs, findings


def check_claim_users(claims, promo_doc, dtc_doc):
    def check_ids(owner, ids):
        for cid in ids:
            if cid not in claims:
                fail(f"{owner}: unknown claim {cid}")
            elif claims[cid]["status"] != "approved":
                fail(f"{owner}: uses {claims[cid]['status']} claim {cid}")

    for piece in promo_doc["pieces"]:
        for unit in piece["units"]:
            check_ids(f"{piece['id']} {unit['id']}", unit["claims"])
    for c in dtc_doc["claims"]:
        check_ids(f"dtc {c['id']}", c["derives_from"])


def check_promo_renderings(promo_doc):
    renderings = {
        "PROMO-ISI": "promotional/promo-isi.md",
        "PROMO-DETAIL-AID": "promotional/promo-detail-aid.md",
        "PROMO-DOSING-CARD": "promotional/promo-dosing-card.md",
    }
    for piece in promo_doc["pieces"]:
        rel = renderings.get(piece["id"])
        if rel is None:
            fail(f"{piece['id']}: no Markdown rendering registered in validate.py")
            continue
        md = text(rel)
        if piece["job_code"] not in md:
            fail(f"{rel}: job code {piece['job_code']} missing")
        for unit in piece["units"]:
            if unit["text"] not in md:
                fail(f"{rel}: text of {unit['id']} does not match the JSON")


def check_gaps_and_srds(gaps_doc, srds_doc, refs):
    gaps = {g["id"]: g for g in gaps_doc["gaps"]}
    srds = {s["id"]: s for s in srds_doc["srds"]}
    for gid, g in gaps.items():
        sid = g.get("srd_id")
        if sid is None:
            continue
        if sid not in srds:
            fail(f"{gid}: srd_id {sid} does not exist")
        elif srds[sid]["gap_id"] != gid:
            fail(f"{gid}: points to {sid}, which points back to {srds[sid]['gap_id']}")
    for sid, s in srds.items():
        if s["gap_id"] not in gaps:
            fail(f"{sid}: gap_id {s['gap_id']} does not exist")
        for rid in s["references"]:
            if rid not in refs:
                fail(f"{sid}: reference {rid} does not exist")
    return gaps, srds


def check_markdown_pairs(refs, findings, srds, form_doc):
    md = text("claims/references.md")
    for rid in refs:
        if f"**{rid}**" not in md:
            fail(f"claims/references.md: missing {rid}")
    for fid in findings:
        if f"`{fid}`" not in md:
            fail(f"claims/references.md: missing finding {fid}")

    md = text("medical-information/srds.md")
    for sid, s in srds.items():
        if f"## {sid} {s['title']}" not in md:
            fail(f"medical-information/srds.md: missing or retitled {sid}")

    md = text("access/start-form.md")
    for section in form_doc["sections"]:
        for field in section.get("fields", []):
            if f"{field['id']}." not in md:
                fail(f"access/start-form.md: missing field {field['id']}")


def check_readme_counts(claims, refs, gaps, srds, dtc_doc, form_doc):
    readme = text("README.md")
    statuses = [c["status"] for c in claims.values()]
    ref_ok = sum(r["status"] == "approved" for r in refs.values())
    fields = sum(len(s.get("fields", [])) for s in form_doc["sections"])
    dmt = sum(c["qualifiers"].get("data_source") == "DMT" for c in claims.values())
    access = sum(c["category"] == "access" for c in claims.values())
    expected = [
        (rf"(\d+) claims \((\d+) approved, (\d+) withdrawn, including (\d+) access claims\)",
         (len(claims), statuses.count("approved"), statuses.count("withdrawn"), access)),
        (r"(\d+) fictitious references \((\d+) approved, (\d+) not approved",
         (len(refs), ref_ok, len(refs) - ref_ok)),
        (r"(\d+) Medical Information standard response documents", (len(srds),)),
        (r"(\d+) direct-to-consumer claims", (len(dtc_doc["claims"]),)),
        (r"(\d+) sections, (\d+) fields", (len(form_doc["sections"]), fields)),
        (r"(\d+) topics the library leaves uncovered", (len(gaps),)),
        (r"(\d+) of the (\d+) claims carry `data_source: \"DMT\"`", (dmt, len(claims))),
    ]
    for pattern, want in expected:
        m = re.search(pattern, readme)
        if not m:
            fail(f"README.md: count sentence not found: /{pattern}/")
            continue
        got = tuple(int(g) for g in m.groups())
        if got != want:
            fail(f"README.md: '{m.group(0)}' should read {want}")


def check_fiction_markers(denylist):
    for path in sorted(SRC.rglob("*")):
        if path.suffix not in {".md", ".json", ".xml"}:
            continue
        rel = path.relative_to(SRC)
        body = path.read_text()
        for phone in re.findall(r"1-800-[A-Z0-9]{3}-[A-Z0-9]{4}", body):
            if phone not in ALLOWED_PHONES and not FICTION_PHONE.match(phone):
                fail(f"{rel}: phone {phone} is outside 1-800-555-01xx")
        for phone in re.findall(r"\(\d{3}\) \d{3}-\d{4}", body):
            if not re.fullmatch(r"\(\d{3}\) 555-01\d\d", phone):
                fail(f"{rel}: phone {phone} is outside 555-01xx")
        for doi in re.findall(r"\b10\.\d{4,}/", body):
            if doi != "10.5555/":
                fail(f"{rel}: DOI prefix {doi} is not 10.5555")
        for host in sorted(set(re.findall(r"\b(?:[a-z0-9-]+\.)+(?:com|org|net|gov|io|co|us)\b", body, re.I)) - ALLOWED_HOSTS):
            fail(f"{rel}: real-looking domain {host}; use .example")
        lowered = body.lower()
        for name in denylist:
            if re.search(rf"\b{re.escape(name.lower())}\b", lowered):
                fail(f"{rel}: denylisted name '{name}'")


# ---------------------------------------------------------------- patient services

TAG = re.compile(r"`\[([^\]`]+)\]`")
PLACEHOLDER = re.compile(r"\{\{\s*([a-z_.]+)\s*\}\}")
DOMAINS = {"bv", "pa", "copay", "bridge", "pap", "shipment"}
GOVERNMENT_TYPES = {"medicare", "medicaid", "tricare", "va", "other_government"}
BRIDGE_DAYS = 60
COPAY_MAX = 16000


def resolve(obj, path):
    for part in path.split("."):
        if not isinstance(obj, dict) or part not in obj:
            return False, None
        obj = obj[part]
    return True, obj



ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def format_value(v):
    from datetime import date
    if isinstance(v, bool) or v is None:
        raise ValueError("cannot fill a null or boolean value")
    if isinstance(v, int):
        return f"{v:,}"
    if isinstance(v, list):
        items = [format_value(x) for x in v]
        return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]
    if isinstance(v, str) and ISO_DATE.match(v):
        d = date.fromisoformat(v)
        return f"{d.strftime('%B')} {d.day}, {d.year}"
    return str(v)


def fill(template, case, statuses):
    """Fill {{placeholders}} from a case record, as ps-responses.json rules describe."""
    def value(path):
        if path.endswith(".status_text"):
            domain = path.split(".")[0]
            code = case["shipments"][-1]["status"] if domain == "last_shipment" else case[domain]["status"]
            return fill(statuses[code]["patient_text"], case, statuses)
        if path == "copay.remaining":
            return format_value(case["copay"]["annual_max"] - case["copay"]["used_ytd"])
        if path == "bridge.days_remaining":
            return format_value(BRIDGE_DAYS - case["bridge"]["days_dispensed"])
        found, v = resolve(case, path)
        if not found:
            raise ValueError(f"{path} not in case record")
        return format_value(v)
    return PLACEHOLDER.sub(lambda m: value(m.group(1)), template)


def check_patient_services(claims, refs, network):
    terms = load("patient-services/program-terms.json")
    lib = load("patient-services/ps-responses.json")
    statuses_doc = load("patient-services/case-statuses.json")
    glossary = load("patient-services/glossary.json")
    rules = load("patient-services/conversation-rules.json")
    gaps = load("test-design/ps-known-gaps.json")
    cases_doc = load("test-design/ps-cases.json")
    dtc = {c["id"]: c for c in load("patient/dtc-claims.json")["claims"]}

    provisions = {}
    for s in terms["sections"]:
        for pr in s["provisions"]:
            if pr["id"] in provisions:
                fail(f"program-terms: duplicate provision {pr['id']}")
            provisions[pr["id"]] = pr["text"]
    md = text("patient-services/program-terms.md")
    for pid, ptext in provisions.items():
        if f"`{pid}` {ptext}" not in md:
            fail(f"patient-services/program-terms.md: {pid} missing or out of date; run scripts/render.py")
    ref = refs.get(terms["summarised_by"])
    if ref is None:
        fail(f"program-terms: summarised_by {terms['summarised_by']} does not exist")
    elif f"v{terms['terms_version']}" not in ref["location"] or terms["effective"] not in ref["location"]:
        fail(f"{ref['id']}: location '{ref['location']}' does not match program terms v{terms['terms_version']}, {terms['effective']}")

    def check_cites(owner, cites):
        for cid in cites:
            if cid in provisions:
                continue
            if cid in dtc:
                if dtc[cid]["status"] != "approved":
                    fail(f"{owner}: cites {dtc[cid]['status']} {cid}")
                continue
            fail(f"{owner}: citation {cid} does not exist")

    responses = {r["id"]: r for r in lib["responses"]}
    fixed = set(lib["fixed_messages"])
    for rid, r in responses.items():
        check_cites(rid, r["citations"])
        if not r["citations"]:
            fail(f"{rid}: no citations")
        for req in r["requires"]:
            if req not in responses:
                fail(f"{rid}: requires unknown response {req}")
        has_ph = bool(PLACEHOLDER.search(r["text"]))
        if has_ph != r["verified_only"]:
            fail(f"{rid}: verified_only is {r['verified_only']} but text {'has' if has_ph else 'has no'} placeholders")

    statuses = {}
    for s in statuses_doc["statuses"]:
        if s["code"] in statuses:
            fail(f"case-statuses: duplicate code {s['code']}")
        if s["domain"] not in DOMAINS:
            fail(f"case-statuses: {s['code']} has unknown domain {s['domain']}")
        statuses[s["code"]] = s
        check_cites(s["code"], s["citations"])

    for g in glossary["terms"]:
        for rid in g["see_also"]:
            if rid not in responses:
                fail(f"glossary {g['id']}: see_also {rid} does not exist")

    rule_ids = {"VER"} | {e["id"] for e in rules["escalations"]} | {c["id"] for c in rules["compliance"]}
    for e in rules["escalations"]:
        if e["fixed_message"] not in fixed:
            fail(f"conversation-rules {e['id']}: unknown fixed message {e['fixed_message']}")
    for c in rules["callers"]:
        if c.get("fixed_message") and c["fixed_message"] not in fixed:
            fail(f"conversation-rules caller {c['role']}: unknown fixed message {c['fixed_message']}")
        check_cites(f"conversation-rules caller {c['role']}", c.get("citations", []))
    for c in rules["compliance"]:
        check_cites(c["id"], c.get("citations", []))
    check_cites("conversation-rules VER", rules["identity_verification"]["citations"])

    known = set(responses) | fixed | rule_ids
    for rel in ["patient-services/bi-letters.md", "patient-services/ivr-call-flow.md", "patient-services/agent-scripts.md"]:
        for tag in TAG.findall(text(rel)):
            for token in (t.strip() for t in tag.split(",")):
                if token not in known:
                    fail(f"{rel}: tag {token} does not exist")

    cases = {c["case_id"]: c for c in cases_doc["cases"]}
    for g in gaps["gaps"]:
        for r in g["refs"]:
            if r not in known:
                fail(f"{g['id']}: ref {r} does not exist")
        for cid in g["case_ids"]:
            if cid not in cases:
                fail(f"{g['id']}: case {cid} does not exist")

    computed = set(lib["rules"]["computed_fields"]) - {"<domain>.status_text", "last_shipment"}
    computed |= {f"{d}.status_text" for d in DOMAINS} | {"last_shipment.status_text"}
    sources = [r["text"] for r in responses.values()] + [s["patient_text"] for s in statuses.values()]
    sources += [text(f"patient-services/{f}") for f in ("bi-letters.md", "agent-scripts.md")]
    for src in sources:
        for ph in PLACEHOLDER.findall(src):
            if ph not in computed and not any(resolve(c, ph)[0] for c in cases.values()):
                fail(f"placeholder {{{{{ph}}}}} does not resolve in any case record")

    readme = text("README.md")
    expected = [
        (r"(\d+) numbered provisions in (\d+) sections", (len(provisions), len(terms["sections"]))),
        (r"(\d+) approved patient-services responses \((\d+) of them case-specific",
         (len(responses), sum(r["verified_only"] for r in responses.values()))),
        (r"(\d+) fixed messages\b", (len(fixed),)),
        (r"(\d+) case status codes", (len(statuses),)),
        (r"(\d+) plain-language insurance terms", (len(glossary["terms"]),)),
        (r"(\d+) escalations and (\d+) compliance rules", (len(rules["escalations"]), len(rules["compliance"]))),
        (r"(\d+) synthetic QuorvantaConnect case records", (len(cases),)),
        (r"(\d+) patient-services situations", (len(gaps["gaps"]),)),
    ]
    for pattern, want in expected:
        m = re.search(pattern, readme)
        if not m:
            fail(f"README.md: count sentence not found: /{pattern}/")
        elif tuple(int(g) for g in m.groups()) != want:
            fail(f"README.md: '{m.group(0)}' should read {want}")

    check_cases(cases_doc, statuses, network)


def check_cases(cases_doc, statuses, network):
    as_of = cases_doc["as_of"]
    by_domain = {}
    for code, s in statuses.items():
        by_domain.setdefault(s["domain"], set()).add(code)
    pharmacies = {p["id"]: p for p in network["pharmacies"]}
    from datetime import date, timedelta

    for c in cases_doc["cases"]:
        cid = c["case_id"]
        ins = c["insurance"]
        gov = ins["government_program"] or ins["type"] in GOVERNMENT_TYPES
        commercial = ins["type"] == "commercial" and not gov

        for dom in ("bv", "pa", "copay", "bridge", "pap"):
            if c[dom]["status"] not in by_domain[dom]:
                fail(f"{cid}: {dom}.status {c[dom]['status']} is not a {dom} code")
        for s in c["shipments"]:
            if s["status"] not in by_domain["shipment"]:
                fail(f"{cid}: shipment status {s['status']} is not a shipment code")
            per_day = 2 if s["dose"] == "titration" else 4
            if s["capsules"] != s["days"] * per_day:
                fail(f"{cid}: shipment {s['date']} has {s['capsules']} capsules for {s['days']} {s['dose']} days")

        if c["shipments"] and c["shipments"][-1]["source"] in ("bridge", "pap") and c["pharmacy"] and c["pharmacy"]["id"] != "SP-04":
            fail(f"{cid}: latest shipment is {c['shipments'][-1]['source']} product, which only SP-04 dispenses")

        dob = date.fromisoformat(c["patient"]["dob"])
        ref = date.fromisoformat(as_of)
        age = ref.year - dob.year - ((ref.month, ref.day) < (dob.month, dob.day))
        if age < 18:
            fail(f"{cid}: patient is under 18")
        if not re.fullmatch(r"\(\d{3}\) 555-01\d\d", c["patient"]["phone"]):
            fail(f"{cid}: patient phone {c['patient']['phone']} is outside 555-01xx")

        cp = c["copay"]
        if cp["annual_max"] != COPAY_MAX:
            fail(f"{cid}: copay.annual_max is not {COPAY_MAX}")
        if not 0 <= cp["used_ytd"] <= COPAY_MAX:
            fail(f"{cid}: copay.used_ytd out of range")
        if cp["status"] in ("COPAY_ACTIVE", "COPAY_MAX_REACHED") and not commercial:
            fail(f"{cid}: {cp['status']} but patient is not commercially insured without government coverage")
        if cp["status"] == "COPAY_INELIGIBLE_GOVERNMENT" and not gov:
            fail(f"{cid}: COPAY_INELIGIBLE_GOVERNMENT but no government program")
        if cp["status"] == "COPAY_MAX_REACHED" and cp["used_ytd"] != COPAY_MAX:
            fail(f"{cid}: COPAY_MAX_REACHED but used_ytd is {cp['used_ytd']}")

        br = c["bridge"]
        bridge_days = sum(s["days"] for s in c["shipments"] if s["source"] == "bridge"
                          and date.fromisoformat(s["date"]) > ref - timedelta(days=365))
        if br["days_dispensed"] != bridge_days:
            fail(f"{cid}: bridge.days_dispensed {br['days_dispensed']} but bridge shipments total {bridge_days}")
        if br["days_dispensed"] > BRIDGE_DAYS:
            fail(f"{cid}: bridge exceeds {BRIDGE_DAYS} days")
        if br["status"] == "BRIDGE_EXHAUSTED" and br["days_dispensed"] != BRIDGE_DAYS:
            fail(f"{cid}: BRIDGE_EXHAUSTED but {br['days_dispensed']} days dispensed")
        if br["status"] in ("BRIDGE_ACTIVE", "BRIDGE_EXHAUSTED", "BRIDGE_ENDED_FINAL_DENIAL", "BRIDGE_ENDED_COVERAGE_APPROVED") and not commercial:
            fail(f"{cid}: {br['status']} but patient is not eligible for bridge supply")
        if br["status"] == "BRIDGE_ACTIVE" and c["pa"]["status"] not in ("PA_SUBMITTED", "APPEAL_SUBMITTED", "NETWORK_EXCEPTION_PENDING", "PA_DENIED"):
            fail(f"{cid}: BRIDGE_ACTIVE without a pending PA, appeal or network exception")

        pp = c["pap"]
        if pp["status"] == "PAP_INCOMPLETE" and not pp["missing_documents"]:
            fail(f"{cid}: PAP_INCOMPLETE with no missing_documents")
        if pp["status"] in ("PAP_APPROVED", "PAP_EXPIRED"):
            decided = date.fromisoformat(pp["decided_on"])
            if date.fromisoformat(pp["approved_through"]) > decided + timedelta(days=366):
                fail(f"{cid}: Foundation approval longer than 12 months")
        if pp["status"] == "PAP_MEDICAID_PENDING":
            if date.fromisoformat(pp["approved_through"]) > date.fromisoformat(pp["decided_on"]) + timedelta(days=90):
                fail(f"{cid}: Medicaid-pending supply longer than 90 days")

        ph = c["pharmacy"]
        if ph:
            p = pharmacies.get(ph["id"])
            if p is None:
                fail(f"{cid}: pharmacy {ph['id']} is not in the network")
            elif (p["name"], p["phone"]) != (ph["name"], ph["phone"]):
                fail(f"{cid}: pharmacy name or phone does not match {ph['id']}")
        req = ins["required_pharmacy"]
        if req not in (None, "non-network") and req not in pharmacies:
            fail(f"{cid}: required_pharmacy {req} is not a network pharmacy")
        if req in pharmacies and ph and ph["id"] not in (req, "SP-04"):
            fail(f"{cid}: plan requires {req} but pharmacy is {ph['id']}")

        for contact in c["authorized_contacts"]:
            if contact.get("scope") not in ("status", "full"):
                fail(f"{cid}: authorised contact {contact.get('name')} has no valid scope")



# ---------------------------------------------------------------- disease, landscape, scenarios

TAGGED_PARA = re.compile(r"^(.*\S) `\[([A-Z0-9, -]+)\]`$")


def check_disease(refs, findings):
    doc = load("disease/disease-facts.json")
    facts = {f["id"]: f for f in doc["facts"]}
    forbidden = [re.compile(rf"\b{re.escape(w)}\b", re.I) for w in doc["forbidden_terms"]]
    for fid, f in facts.items():
        for cit in f["citations"]:
            if cit not in findings:
                fail(f"{fid}: citation {cit} does not exist")
            elif refs[findings[cit]]["status"] != "approved":
                fail(f"{fid}: cites non-approved {cit}")
        for field in ("text", "patient_text"):
            for pat in forbidden:
                if f[field] and pat.search(f[field]):
                    fail(f"{fid}: {field} mentions forbidden term '{pat.pattern}'")
    for rel, field in (("disease/brennick-syndrome-overview.md", "text"),
                       ("disease/understanding-brennick-syndrome.md", "patient_text")):
        body = text(rel)
        body_no_notice = "\n".join(l for l in body.splitlines() if not l.startswith(">"))
        for pat in forbidden:
            if pat.search(body_no_notice):
                fail(f"{rel}: unbranded piece mentions forbidden term '{pat.pattern}'")
        for line in body.splitlines():
            m = TAGGED_PARA.match(line)
            if not m:
                continue
            ids = [i.strip() for i in m.group(2).split(",")]
            missing = [i for i in ids if i not in facts]
            if missing:
                fail(f"{rel}: unknown disease facts {missing}")
                continue
            parts = [facts[i][field] for i in ids]
            if None in parts:
                fail(f"{rel}: {ids} includes a fact with no {field}")
            elif m.group(1) != " ".join(parts):
                fail(f"{rel}: paragraph tagged {ids} does not match the approved {field}")
    return facts


def check_landscape():
    doc = load("landscape/competitors.json")
    brands = [t["brand"] for t in doc["therapies"]] + [t["generic"] for t in doc["therapies"]]
    allowed = ("landscape/", "test-design/", "README.md")
    for path in sorted(SRC.rglob("*")):
        rel = str(path.relative_to(SRC))
        if path.suffix not in {".md", ".json"} or rel.startswith(allowed):
            continue
        body = path.read_text()
        for b in brands:
            if re.search(rf"\b{re.escape(b)}\b", body, re.I):
                fail(f"{rel}: mentions competitor '{b}' outside landscape/ and test-design/")


def closure(ids, table):
    out, stack = set(), list(ids)
    while stack:
        i = stack.pop()
        if i in out or i not in table:
            continue
        out.add(i)
        stack.extend(table[i].get("requires", []))
    return out


def check_scenarios(claims_doc, disease, known_gap_ids, srd_ids):
    base = "test-design/scenarios/"
    faults = {f["id"]: f for f in load(base + "fault-types.json")["faults"]}
    claims = {c["id"]: c for c in claims_doc["claims"]}
    fixed_hcp = set(claims_doc["fixed_messages"])
    efficacy = {cid for cid, c in claims.items() if c["category"] == "efficacy"}

    def known_faults(owner, ids):
        for f in ids:
            if f not in faults:
                fail(f"{owner}: unknown fault {f}")

    inbound = {s["id"]: s for s in load(base + "hcp-inbound.json")["scenarios"]}
    for sid, s in inbound.items():
        for cid in s["claims"]:
            if cid not in claims or claims[cid]["status"] != "approved":
                fail(f"{sid}: claim {cid} missing or not approved")
        if set(s["claims"]) != closure(s["claims"], claims):
            fail(f"{sid}: claims are not closed over requires; missing {sorted(closure(s['claims'], claims) - set(s['claims']))}")
        if s["isi_required"] != bool(set(s["claims"]) & efficacy):
            fail(f"{sid}: isi_required does not match use of efficacy claims")
        for d in s["disease_facts"]:
            if d not in disease:
                fail(f"{sid}: unknown disease fact {d}")
        for r in s["routes"]:
            if r != "answer" and r not in fixed_hcp:
                fail(f"{sid}: unknown route {r}")
        if s["gap_id"] and s["gap_id"] not in known_gap_ids:
            fail(f"{sid}: unknown gap {s['gap_id']}")
        known_faults(sid, s["provokes"])

    fault_coverage = set()
    fm = claims_doc["fixed_messages"]
    for r in load(base + "hcp-outbound.json")["responses"]:
        rid, s = r["id"], inbound.get(r["inbound_id"])
        if s is None:
            fail(f"{rid}: unknown inbound {r['inbound_id']}")
            continue
        known_faults(rid, r["faults"])
        if r["verdict"] == "fail":
            if not r["faults"]:
                fail(f"{rid}: failing response names no fault")
            fault_coverage |= set(r["faults"])
            continue
        if r["faults"]:
            fail(f"{rid}: passing response lists faults")
        if set(r["cited_claims"]) != set(s["claims"]) or set(r["disease_facts"]) != set(s["disease_facts"]):
            fail(f"{rid}: cited claims or disease facts differ from {s['id']}")
        if r["fixed_messages"] != [x for x in s["routes"] if x != "answer"]:
            fail(f"{rid}: fixed messages differ from {s['id']} routes")
        if r["isi_appended"] != s["isi_required"]:
            fail(f"{rid}: isi_appended does not match {s['id']}")
        for cid in r["cited_claims"]:
            if cid in claims and claims[cid]["text"] not in r["response"]:
                fail(f"{rid}: approved text of {cid} not verbatim in response")
        for d in r["disease_facts"]:
            if d in disease and disease[d]["text"] not in r["response"]:
                fail(f"{rid}: text of {d} not verbatim in response")
        for f in r["fixed_messages"]:
            if f in fm and fm[f] not in r["response"]:
                fail(f"{rid}: fixed message {f} not verbatim in response")

    lib = load("patient-services/ps-responses.json")
    responses = {r["id"]: r for r in lib["responses"]}
    fixed_ps = lib["fixed_messages"]
    rules = load("patient-services/conversation-rules.json")
    rule_ids = {e["id"] for e in rules["escalations"]} | {c["id"] for c in rules["compliance"]}
    statuses = {s["code"]: s for s in load("patient-services/case-statuses.json")["statuses"]}
    cases = {c["case_id"]: c for c in load("test-design/ps-cases.json")["cases"]}
    pgaps = {g["id"] for g in load("test-design/ps-known-gaps.json")["gaps"]}
    entitled = {"patient", "legal_representative", "authorised_contact"}

    convs = {c["id"]: c for c in load(base + "ps-conversations.json")["conversations"]}
    for cid, c in convs.items():
        case = cases.get(c["case_id"]) if c["case_id"] else None
        if c["case_id"] and case is None:
            fail(f"{cid}: unknown case {c['case_id']}")
            continue
        for g in c["gap_ids"]:
            if g not in pgaps:
                fail(f"{cid}: unknown gap {g}")
        known_faults(cid, c["provokes"])
        role, name = c["caller"]["role"], c["caller"]["name"]
        verified = False
        for n, turn in enumerate(c["turns"], 1):
            e = turn["expected"]
            known_faults(f"{cid} turn {n}", e["avoid"])
            for x in e["fixed"]:
                if x not in fixed_ps:
                    fail(f"{cid} turn {n}: unknown fixed message {x}")
            for x in e["rules"]:
                if x not in rule_ids:
                    fail(f"{cid} turn {n}: unknown rule {x}")
            for x in e["responses"]:
                if x not in responses:
                    fail(f"{cid} turn {n}: unknown response {x}")
            if set(e["responses"]) != closure(e["responses"], responses):
                fail(f"{cid} turn {n}: responses not closed over requires")
            if e["verification"] in ("succeeds", "fails") and case:
                p = case["patient"]
                details = (p["last_name"] in turn["user"] and format_value(p["dob"]) in turn["user"]
                           and (p["zip"] in turn["user"] or case["case_id"] in turn["user"]))
                names = [x["name"] for x in case["authorized_contacts"]]
                if case["legal_representative"]:
                    names.append(case["legal_representative"]["name"])
                caller_ok = role == "patient" or (role in entitled and name in names)
                ok = details and caller_ok
                if (e["verification"] == "succeeds") != ok:
                    fail(f"{cid} turn {n}: verification marked {e['verification']} but details and caller say otherwise")
            if e["verification"] == "succeeds":
                verified = True
            for x in e["responses"]:
                if x in responses and responses[x]["verified_only"] and not (verified and role in entitled):
                    fail(f"{cid} turn {n}: case-specific {x} before successful verification")

    for r in load(base + "ps-outbound.json")["replies"]:
        rid, c = r["id"], convs.get(r["conversation_id"])
        if c is None or not 1 <= r["turn"] <= len(c["turns"]):
            fail(f"{rid}: unknown conversation or turn")
            continue
        known_faults(rid, r["faults"])
        if r["verdict"] == "fail":
            if not r["faults"]:
                fail(f"{rid}: failing reply names no fault")
            fault_coverage |= set(r["faults"])
            continue
        e = c["turns"][r["turn"] - 1]["expected"]
        if r["cited_responses"] != e["responses"] or r["fixed_messages"] != e["fixed"]:
            fail(f"{rid}: cited responses or fixed messages differ from {c['id']} turn {r['turn']}")
            continue
        case = cases.get(c["case_id"])
        try:
            parts = [fixed_ps[f] for f in r["fixed_messages"]]
            parts += [fill(responses[x]["text"], case, statuses) if responses[x]["verified_only"] else responses[x]["text"]
                      for x in r["cited_responses"]]
        except (ValueError, TypeError, KeyError) as ex:
            fail(f"{rid}: cannot fill expected reply: {ex}")
            continue
        if r["reply"] != " ".join(parts):
            fail(f"{rid}: reply is not the approved wording filled from {c['case_id']}")

    readme = text("README.md")
    hout = load(base + "hcp-outbound.json")["responses"]
    pout = load(base + "ps-outbound.json")["replies"]
    count = lambda xs, v: sum(x["verdict"] == v for x in xs)
    expected = [
        (r"(\d+) fault types \((\d+) for the HCP bot, (\d+) for the patient-services assistant, (\d+) for adverse event intake and (\d+) for field records\)",
         (len(faults),) + tuple(sum(f.startswith(p) for f in faults) for p in ("HF", "PF", "SF", "CF"))),
        (r"(\d+) labelled HCP questions", (len(inbound),)),
        (r"(\d+) labelled HCP bot responses \((\d+) pass, (\d+) fail\)", (len(hout), count(hout, "pass"), count(hout, "fail"))),
        (r"(\d+) multi-turn patient-services conversations", (len(convs),)),
        (r"(\d+) labelled patient-services replies \((\d+) pass, (\d+) fail\)", (len(pout), count(pout, "pass"), count(pout, "fail"))),
        (r"(\d+) approved unbranded disease facts", (len(disease),)),
    ]
    for pattern, want in expected:
        m = re.search(pattern, readme)
        if not m:
            fail(f"README.md: count sentence not found: /{pattern}/")
        elif tuple(int(g) for g in m.groups()) != want:
            fail(f"README.md: '{m.group(0)}' should read {want}")

    return faults, fault_coverage



# ---------------------------------------------------------------- product identifiers

NDC = re.compile(r"^00000-\d{4}-\d{2}$")
LOT = re.compile(r"^(Q[A-Z])(\d{2})([A-L])(\d{3})$")


def gtin14(ndc11):
    lab, prod, pkg = ndc11.split("-")
    body = "003" + lab[1:] + prod + pkg
    total = sum(int(d) * (3 if i % 2 == 0 else 1) for i, d in enumerate(reversed(body)))
    return body + str((10 - total % 10) % 10)


def check_product(claims):
    from datetime import date, timedelta
    doc = load("product/product-identifiers.json")
    as_of = date.fromisoformat(doc["as_of"])
    packages = {p["id"]: p for p in doc["packages"]}
    label = text("label/label.md")
    sup004 = claims.get("SUP-004", {}).get("text", "")
    md = text("product/product-identifiers.md")
    for pid, p in packages.items():
        if not NDC.match(p["ndc"]):
            fail(f"{pid}: NDC {p['ndc']} does not use the unassigned 00000 labeler")
        if p["gtin"] != gtin14(p["ndc"]):
            fail(f"{pid}: GTIN {p['gtin']} should be {gtin14(p['ndc'])}")
        for where, body in (("label/label.md", label), ("claim SUP-004", sup004), ("product-identifiers.md", md)):
            if p["ndc"] not in body:
                fail(f"{where}: NDC {p['ndc']} missing")
    lots = {}
    for lot in doc["lots"]:
        lid = lot["lot"]
        if lid in lots:
            fail(f"lot {lid}: duplicate")
        lots[lid] = lot
        m = LOT.match(lid)
        pkg = packages.get(lot["package"])
        made = date.fromisoformat(lot["manufactured"])
        if not m or pkg is None:
            fail(f"lot {lid}: bad format or unknown package")
            continue
        if m.group(1) != pkg["lot_prefix"] or int(m.group(2)) != made.year % 100 or "ABCDEFGHIJKL".index(m.group(3)) + 1 != made.month:
            fail(f"lot {lid}: prefix, year or month letter does not match package and manufacture date")
        y, mo = made.year + (made.month + 24) // 12, (made.month + 24) % 12 + 1
        end = date(y, mo, 1) - timedelta(days=1)
        if lot["expiry"] != str(end):
            fail(f"lot {lid}: expiry should be {end}")
        if lot["status"] != ("expired" if end < as_of else "released"):
            fail(f"lot {lid}: status does not match expiry as of {as_of}")
        if made < date.fromisoformat(pkg["introduced"]) - timedelta(days=120):
            fail(f"lot {lid}: made long before {pkg['id']} was introduced")
        if lid not in md:
            fail(f"product-identifiers.md: lot {lid} missing; run scripts/render.py")

    m = re.search(r"register of (\d+) lots", text("README.md"))
    if not m or int(m.group(1)) != len(lots):
        fail(f"README.md: lot register count should read {len(lots)}")

    for c in load("test-design/ps-cases.json")["cases"]:
        by_date = {}
        for s in c["shipments"]:
            by_date.setdefault((s["date"], s["package"]), []).append(s)
        for (day, pid), group in by_date.items():
            pkg = packages.get(pid)
            where = f"{c['case_id']} shipment {day}"
            if pkg is None:
                fail(f"{where}: unknown package {pid}")
                continue
            if sum(s["capsules"] for s in group) != pkg["capsules"]:
                fail(f"{where}: {sum(s['capsules'] for s in group)} capsules but {pid} holds {pkg['capsules']}")
            if (pid == "PKG-STARTER") != any(s["dose"] == "titration" for s in group):
                fail(f"{where}: starter bottle must be exactly the first-fill titration shipment")
            if date.fromisoformat(day) < date.fromisoformat(pkg["introduced"]):
                fail(f"{where}: {pid} shipped before it was introduced")
            for s in group:
                if s["lot"] is None:
                    if s["status"] not in ("SHIP_SCHEDULED", "SHIP_AWAITING_PATIENT"):
                        fail(f"{where}: shipped without a lot")
                    continue
                lot = lots.get(s["lot"])
                if lot is None or lot["package"] != pid:
                    fail(f"{where}: lot {s['lot']} unknown or for another package")
                    continue
                days = sum(x["days"] for x in group)
                if date.fromisoformat(lot["manufactured"]) > date.fromisoformat(day):
                    fail(f"{where}: lot {s['lot']} made after it shipped")
                if date.fromisoformat(lot["expiry"]) < date.fromisoformat(day) + timedelta(days=days):
                    fail(f"{where}: lot {s['lot']} expires before the supply is used")


# ---------------------------------------------------------------- safety, field force, payer

def business_days(holidays):
    from datetime import date, timedelta
    hol = {date.fromisoformat(d) for d in holidays}

    def add(day, n):
        d = date.fromisoformat(day)
        while n:
            d += timedelta(days=1)
            if d.weekday() < 5 and d not in hol:
                n -= 1
        return str(d)

    def is_bd(day):
        d = date.fromisoformat(day)
        return d.weekday() < 5 and d not in hol
    return add, is_bd


def npi_ok(npi):
    if not re.fullmatch(r"9\d{9}", npi):
        return False
    total = 0
    for i, d in enumerate(reversed([int(x) for x in "80840" + npi])):
        if i % 2 == 1:
            d = d * 2 - 9 if d > 4 else d * 2
        total += d
    return total % 10 == 0


def check_safety(lots):
    from datetime import date, timedelta
    ref = load("safety/safety-reference.json")
    terms = {t["id"]: t for t in ref["terms"]}
    sits = {s["id"] for s in ref["special_situations"]}
    criteria = {c["id"] for c in ref["seriousness_criteria"]}
    minimum = {c["id"] for c in ref["minimum_criteria"]}
    headings = set(re.findall(r"^### (\d+\.\d+)", text("label/label.md"), re.M))
    for tid, t in terms.items():
        if t["listed"] != bool(t["label_sections"]):
            fail(f"{tid}: listed is {t['listed']} but label_sections is {t['label_sections']}")
        for s in t["label_sections"]:
            if s not in headings:
                fail(f"{tid}: label section {s} does not exist")
    add_bd, _ = business_days(ref["business_calendar"]["holidays"])

    base = "test-design/scenarios/"
    convs = {c["id"] for c in load(base + "ps-conversations.json")["conversations"]}
    inbound = {s["id"] for s in load(base + "hcp-inbound.json")["scenarios"]}
    calls = {c["id"]: c for c in load("crm/call-log.json")["calls"]}
    cases = {c["case_id"] for c in load("test-design/ps-cases.json")["cases"]}
    hcps = {h["id"] for h in load("crm/field-force.json")["hcps"]}
    channels = {"drug_safety", "medical_information", "field", "hcp_chatbot", "quorvantaconnect_assistant",
                "quorvantaconnect_nurse", "patient_community_page"}

    def derive(r):
        """The expected assessment, recomputed from the report's own facts."""
        e = r["expected"]
        valid = not e["missing_criteria"]
        events = e["events"]
        serious = any(ev["serious_criteria"] for ev in events)
        listed = all(ev["listed"] for ev in events)
        ctype = ("not_valid" if not valid else "adverse_event" if events
                 else "special_situation" if e["special_situations"] else "product_complaint")
        day0 = None
        if ctype in ("adverse_event", "special_situation"):
            complete = [x["on"] for x in r["receipts"] if x["criteria_complete"]]
            day0 = min(complete) if complete else None
        if ctype == "adverse_event" and any(ev["serious_criteria"] and not ev["listed"] for ev in events):
            rep, due = "expedited_15_day", str(date.fromisoformat(day0) + timedelta(days=15))
        elif ctype in ("adverse_event", "special_situation"):
            rep, due = "periodic", None
        else:
            rep, due = "not_reportable", None
        first = min(x["on"] for x in r["receipts"])
        ds = [x["on"] for x in r["receipts"] if x["by"] == "drug_safety"]
        late = bool(r["receipts"][0]["by"] != "drug_safety" and ds and ds[0] > add_bd(first, 1))
        return {"case_type": ctype, "valid": valid, "serious": serious, "listed": listed if events else None,
                "reportability": rep, "day_0": day0, "due": due, "internal_forward_late": late}

    reports = {}
    for r in load(base + "ae-intake.json")["reports"]:
        rid, e = r["id"], r["expected"]
        reports[rid] = r
        if r["case_id"] and r["case_id"] not in cases:
            fail(f"{rid}: unknown case {r['case_id']}")
        if r["hcp_id"] and r["hcp_id"] not in hcps:
            fail(f"{rid}: unknown prescriber {r['hcp_id']}")
        dates = [x["on"] for x in r["receipts"]]
        if dates != sorted(dates):
            fail(f"{rid}: receipts are not in date order")
        for x in r["receipts"]:
            if x["by"] not in channels:
                fail(f"{rid}: unknown receiving channel {x['by']}")
            ref_id = x["ref"]
            if ref_id and not (ref_id in convs or ref_id in inbound or ref_id in calls):
                fail(f"{rid}: receipt ref {ref_id} does not exist")
            if x["by"] == "field":
                call = calls.get(ref_id)
                fwd = [f["forwarded_on"] for f in call["adverse_event_forwards"] if f["report_id"] == rid] if call else []
                ds = [y["on"] for y in r["receipts"] if y["by"] == "drug_safety"]
                if not call or call["date"] != x["on"] or fwd != ds[:1]:
                    fail(f"{rid}: field receipt does not match {ref_id} in crm/call-log.json")
        for m in e["missing_criteria"]:
            if m not in minimum:
                fail(f"{rid}: unknown minimum criterion {m}")
        for ev in e["events"]:
            t = terms.get(ev["term"])
            if t is None:
                fail(f"{rid}: unknown term {ev['term']}")
                continue
            if ev["listed"] != (t["listed"] and (not ev["fatal"] or t["fatal_outcome_listed"])):
                fail(f"{rid}: event {ev['term']} listed flag does not follow safety-reference.json")
            for c in ev["serious_criteria"]:
                if c not in criteria:
                    fail(f"{rid}: unknown seriousness criterion {c}")
        for s in e["special_situations"]:
            if s not in sits:
                fail(f"{rid}: unknown special situation {s}")
        pc = e["product_complaint"]
        if pc and pc["lot"] is not None and pc["lot_status"] != ("in_register" if pc["lot"] in lots else "not_in_register"):
            fail(f"{rid}: lot_status for {pc['lot']} does not match the lot register")
        for k, v in derive(r).items():
            if e[k] != v:
                fail(f"{rid}: expected.{k} is {e[k]!r}; the rules give {v!r}")

    coverage = set()
    items = load(base + "ae-assessments.json")["assessments"]
    for a in items:
        r = reports.get(a["report_id"])
        if r is None:
            fail(f"{a['id']}: unknown report {a['report_id']}")
            continue
        same = a["assessment"] == r["expected"]
        if a["verdict"] == "pass" and (not same or a["faults"]):
            fail(f"{a['id']}: passing assessment differs from {r['id']} expected, or lists faults")
        if a["verdict"] == "fail":
            if same or not a["faults"]:
                fail(f"{a['id']}: failing assessment equals the expected one or names no fault")
            coverage |= set(a["faults"])
    readme = text("README.md")
    expected = [
        (r"(\d+) event terms \((\d+) in the label", (len(terms), sum(t["listed"] for t in terms.values()))),
        (r"(\d+) special situations", (len(sits),)),
        (r"(\d+) adverse event reports", (len(reports),)),
        (r"(\d+) labelled intake assessments \((\d+) pass, (\d+) fail\)",
         (len(items), sum(a["verdict"] == "pass" for a in items), sum(a["verdict"] == "fail" for a in items))),
    ]
    readme_counts(readme, expected)
    return reports, coverage


def readme_counts(readme, expected):
    for pattern, want in expected:
        m = re.search(pattern, readme)
        if not m:
            fail(f"README.md: count sentence not found: /{pattern}/")
        elif tuple(int(g) for g in m.groups()) != want:
            fail(f"README.md: '{m.group(0)}' should read {want}")


def check_field_force(claims_doc, srd_ids, reports):
    ff = load("crm/field-force.json")
    ref = load("safety/safety-reference.json")
    add_bd, is_bd = business_days(ref["business_calendar"]["holidays"])
    claims = {c["id"]: c for c in claims_doc["claims"]}
    efficacy = {cid for cid, c in claims.items() if c["category"] == "efficacy"}
    pieces = {p["id"] for p in load("promotional/promo-materials.json")["pieces"]}
    cases = {c["case_id"]: c for c in load("test-design/ps-cases.json")["cases"]}
    hcos = {h["id"]: h for h in ff["hcos"]}
    hcps = {h["id"]: h for h in ff["hcps"]}
    staff = {s["id"]: s for s in ff["staff"]}
    territory_of = {}
    for t in ff["territories"]:
        if t["rep_id"] not in staff or t["manager_id"] not in staff:
            fail(f"{t['id']}: unknown rep or manager")
        for st in t["states"]:
            if st in territory_of:
                fail(f"{t['id']}: state {st} is also in {territory_of[st]['id']}")
            territory_of[st] = t
    for h in ff["hcos"]:
        if not re.fullmatch(r"\(\d{3}\) 555-01\d\d", h["phone"]):
            fail(f"{h['id']}: phone {h['phone']} is outside 555-01xx")
    npis = set()
    for hid, h in hcps.items():
        if not npi_ok(h["npi"]):
            fail(f"{hid}: NPI {h['npi']} is not 9-prefixed with a valid check digit")
        if h["npi"] in npis:
            fail(f"{hid}: duplicate NPI")
        npis.add(h["npi"])
        o = hcos.get(h["hco_id"])
        if o is None or (o["state"], o["phone"]) != (h["state"], h["phone"]):
            fail(f"{hid}: HCO missing, or state or phone differs from it")
        if h["state"] not in territory_of:
            fail(f"{hid}: state {h['state']} is in no territory")
        for cid in h["case_ids"]:
            if cid not in cases or cases[cid].get("prescriber_id") != hid:
                fail(f"{hid}: case {cid} does not name this prescriber")
    for cid, c in cases.items():
        p = hcps.get(c.get("prescriber_id"))
        if p is None or cid not in p["case_ids"]:
            fail(f"{cid}: prescriber_id {c.get('prescriber_id')} missing or not linked back")

    isi = claims_doc["rules"]["isi_claims"]
    templates = {}
    for t in load("crm/approved-emails.json")["templates"]:
        templates[t["id"]] = t
        for cid in t["claims"] + isi:
            if cid not in claims or claims[cid]["status"] != "approved":
                fail(f"{t['id']}: claim {cid} missing or not approved")
            elif claims[cid]["text"] not in t["body"]:
                fail(f"{t['id']}: text of {cid} not verbatim in the body")
        for p in t["pieces"]:
            if p not in pieces:
                fail(f"{t['id']}: unknown piece {p}")

    patient_marks = []
    for c in cases.values():
        patient_marks += [c["patient"]["last_name"], c["case_id"], format_value(c["patient"]["dob"])]

    def private(body):
        return [m for m in patient_marks if m in body]

    log = load("crm/call-log.json")
    for call in log["calls"]:
        cid, h = call["id"], hcps.get(call["hcp_id"])
        if h is None:
            fail(f"{cid}: unknown prescriber {call['hcp_id']}")
            continue
        if not is_bd(call["date"]) or call["date"] > log["as_of"]:
            fail(f"{cid}: {call['date']} is not a business day on or before {log['as_of']}")
        found = set()
        ter = territory_of.get(h["state"])
        if h["no_see"] or not ter or ter["rep_id"] != call["rep_id"]:
            found.add("CF-08")
        if call["channel"] == "approved_email":
            if call["template_id"] not in templates:
                fail(f"{cid}: unknown email template {call['template_id']}")
            if not h["consent"]["approved_email"]:
                found.add("CF-08")
        for p in call["pieces"]:
            if p not in pieces:
                fail(f"{cid}: unknown piece {p}")
        for x in call["claims"]:
            if x not in claims or claims[x]["status"] != "approved":
                fail(f"{cid}: claim {x} missing or not approved")
        if set(call["claims"]) != closure(call["claims"], claims):
            fail(f"{cid}: claims are not closed over requires")
        if set(call["claims"]) & efficacy and "PROMO-ISI" not in call["pieces"]:
            fail(f"{cid}: efficacy claims without PROMO-ISI")
        for mi in call["medical_information_requests"]:
            if mi["srd_id"] not in srd_ids:
                fail(f"{cid}: unknown SRD {mi['srd_id']}")
            if mi["submitted_on"] != call["date"]:
                found.add("CF-02")
        for f in call["adverse_event_forwards"]:
            if f["report_id"] not in reports:
                fail(f"{cid}: unknown adverse event report {f['report_id']}")
            if f["forwarded_on"] > add_bd(call["date"], 1):
                found.add("CF-03")
        if private(call["notes"]):
            found.add("CF-05")
        if found != set(call["deviations"]):
            fail(f"{cid}: deviations {sorted(call['deviations'])} but the record shows {sorted(found)}")

    coverage = set()
    notes = load("test-design/scenarios/crm-notes.json")["items"]
    for n in notes:
        nid, h = n["id"], hcps.get(n["hcp_id"])
        if h is None:
            fail(f"{nid}: unknown prescriber {n['hcp_id']}")
            continue
        if n["verdict"] == "fail":
            if not n["faults"]:
                fail(f"{nid}: failing item names no fault")
            coverage |= set(n["faults"])
            continue
        if n["faults"]:
            fail(f"{nid}: passing item lists faults")
        if h["no_see"]:
            fail(f"{nid}: passing item for a no-see prescriber")
        if n["kind"] == "approved_email":
            t = templates.get(n["template_id"])
            if t is None or n["text"] != t["body"] or not h["consent"]["approved_email"]:
                fail(f"{nid}: passing email is not its template, unaltered, to a consenting prescriber")
        elif private(n["text"]):
            fail(f"{nid}: passing call note contains patient details {private(n['text'])}")
    readme_counts(text("README.md"), [
        (r"(\d+) prescribers at (\d+) accounts", (len(hcps), len(hcos))),
        (r"(\d+) field calls", (len(log["calls"]),)),
        (r"(\d+) approved email templates", (len(templates),)),
        (r"(\d+) labelled call notes and emails \((\d+) pass, (\d+) fail\)",
         (len(notes), sum(n["verdict"] == "pass" for n in notes), sum(n["verdict"] == "fail" for n in notes))),
    ])
    return coverage


PA_EVENTS = ("pa_request", "pa_decision", "appeal_request", "appeal_decision", "network_exception_request")
BV_RESULT = {"BV_COMPLETE_COVERED": "covered", "BV_COMPLETE_PA_REQUIRED": "pa_required",
             "BV_COMPLETE_NOT_COVERED": "not_covered", "BV_COMPLETE_OUT_OF_NETWORK": "out_of_network"}


def check_payer():
    doc = load("payer/plans.json")
    procs = {p["id"]: p for p in doc["processors"]}
    forms = {f["id"]: f for f in doc["formularies"]}
    plans = {p["id"]: p for p in doc["plans"]}
    rejects = {r["code"] for r in doc["reject_codes"]}
    criteria = {c["id"] for c in doc["pa_criteria"]}
    network = {p["id"] for p in load("access/specialty-pharmacy-network.json")["pharmacies"]}
    packages = {p["ndc"]: p for p in load("product/product-identifiers.json")["packages"]}
    cases = {c["case_id"]: c for c in load("test-design/ps-cases.json")["cases"]}
    for p in procs.values():
        if not re.fullmatch(r"000\d{3}", p["bin"]):
            fail(f"{p['id']}: BIN {p['bin']} is not in the 000 fiction range")
    for f in forms.values():
        q = f["quorvanta"]
        if q["pa_criteria"] and q["pa_criteria"] not in criteria:
            fail(f"{f['id']}: unknown PA criteria {q['pa_criteria']}")
        if (q["prior_authorization"] != "none") != bool(q["pa_criteria"]):
            fail(f"{f['id']}: prior_authorization and pa_criteria disagree")
    by_name = {}
    for p in plans.values():
        by_name[p["name"]] = p
        if p["processor_id"] not in procs or p["pcn"] not in procs[p["processor_id"]]["pcns"]:
            fail(f"{p['id']}: unknown processor or PCN")
        if p["formulary_id"] not in forms:
            fail(f"{p['id']}: unknown formulary")
        if p["required_pharmacy"] not in (None, "non-network") and p["required_pharmacy"] not in network:
            fail(f"{p['id']}: required pharmacy {p['required_pharmacy']} is not in the network")

    tx_doc = load("payer/transactions.json")
    covs = {c["id"]: c for c in tx_doc["coverages"]}
    members = set()
    for c in covs.values():
        p = plans.get(c["plan_id"])
        if c["case_id"] not in cases or p is None:
            fail(f"{c['id']}: unknown case or plan")
            continue
        if (c["bin"], c["pcn"]) != (procs[p["processor_id"]]["bin"], p["pcn"]):
            fail(f"{c['id']}: BIN or PCN differs from {p['id']}")
        if c["member_id"] in members:
            fail(f"{c['id']}: duplicate member id")
        members.add(c["member_id"])

    txs = tx_doc["transactions"]
    ids = [t["id"] for t in txs]
    if len(set(ids)) != len(ids):
        fail("payer/transactions.json: duplicate transaction ids")
    year = tx_doc["as_of"][:4]
    for cid, case in cases.items():
        mine = [t for t in txs if t["case_id"] == cid]
        current = [c for c in covs.values() if c["case_id"] == cid and c["order"] == "primary" and c["end"] is None]
        plan_name = case["insurance"]["plan_name"]
        if plan_name is None:
            if current or mine:
                fail(f"{cid}: no plan in the case but coverage or transactions exist")
            continue
        if len(current) != 1 or plans[current[0]["plan_id"]]["name"] != plan_name:
            fail(f"{cid}: current primary coverage does not match plan {plan_name}")
            continue
        cur = current[0]
        plan = plans[cur["plan_id"]]
        form = forms[plan["formulary_id"]]["quorvanta"]
        if plan["required_pharmacy"] != case["insurance"]["required_pharmacy"]:
            fail(f"{cid}: required pharmacy differs from {plan['id']}")
        cur_tx = [t for t in mine if t["coverage_id"] == cur["id"]]
        for t in mine:
            c = covs.get(t["coverage_id"])
            if c is None or c["case_id"] != cid:
                fail(f"{t['id']}: coverage {t['coverage_id']} is not this case's")
                continue
            active = c["start"] <= t["date"] and (c["end"] is None or t["date"] <= c["end"])
            if t["type"] == "claim":
                pkg = packages.get(t["ndc"])
                if pkg is None or t["quantity"] != pkg["capsules"]:
                    fail(f"{t['id']}: NDC or quantity does not match a package")
                if t["pharmacy_id"] not in network:
                    fail(f"{t['id']}: pharmacy {t['pharmacy_id']} is not in the network")
                for code in t["reject_codes"]:
                    if code not in rejects:
                        fail(f"{t['id']}: unknown reject code {code}")
                if t["result"] == "paid":
                    req = plans[c["plan_id"]]["required_pharmacy"]
                    if not active or t["reject_codes"] or t["patient_pay"] != (c["patient_cost_share"] if c["order"] == "primary" else 0):
                        fail(f"{t['id']}: paid claim outside coverage, with rejects, or with the wrong patient pay")
                    if req in network and t["pharmacy_id"] != req:
                        fail(f"{t['id']}: plan requires {req}")
                elif t["patient_pay"] is not None or not t["reject_codes"] or ("RJ-04" in t["reject_codes"]) == active:
                    fail(f"{t['id']}: rejected claim has patient pay, no reject code, or a coverage reject that does not match the dates")
            elif not active:
                fail(f"{t['id']}: {t['type']} outside the coverage period")

        shipped = sorted({(s["date"], s["package"]) for s in case["shipments"]
                          if s["source"] == "plan" and s["status"] in ("SHIP_SHIPPED", "SHIP_DELIVERED")})
        by_ndc = {p["id"]: p["ndc"] for p in packages.values()}
        paid = sorted((t["date"], t["ndc"]) for t in mine if t["type"] == "claim" and t["result"] == "paid"
                      and covs[t["coverage_id"]]["order"] == "primary")
        if paid != [(d, by_ndc[p]) for d, p in shipped]:
            fail(f"{cid}: paid primary claims do not match plan shipments")
        free = {s["date"] for s in case["shipments"] if s["source"] in ("bridge", "pap")}
        if free & {d for d, _ in paid}:
            fail(f"{cid}: a bridge or Foundation shipment was billed to the plan")

        spent, total = {}, 0
        for t in (t for t in mine if t["type"] == "copay_claim"):
            yr = t["date"][:4]
            c = covs[t["coverage_id"]]
            due = min(c["patient_cost_share"], 16000 - spent.get(yr, 0))
            if t["program_paid"] != due or t["patient_pay"] != c["patient_cost_share"] - due:
                fail(f"{t['id']}: copay program paid {t['program_paid']}, rules give {due}")
            if plans[c["plan_id"]]["type"] != "commercial" or case["insurance"]["government_program"] and c["end"] is None:
                fail(f"{t['id']}: copay claim for non-commercial or government-covered patient")
            spent[yr] = spent.get(yr, 0) + t["program_paid"]
        if spent.get(year, 0) != case["copay"]["used_ytd"]:
            fail(f"{cid}: copay claims in {year} total {spent.get(year, 0)}, case says {case['copay']['used_ytd']}")

        checks = [t for t in cur_tx if t["type"] == "benefit_check"]
        bvs = case["bv"]
        if bvs["status"] == "BV_NEEDS_INFO":
            if checks:
                fail(f"{cid}: BV_NEEDS_INFO but a benefit check exists")
            continue
        if not checks or checks[-1]["date"] != bvs["completed_on"]:
            fail(f"{cid}: last benefit check does not match bv.completed_on")
            continue
        bc = checks[-1]
        if (bc["result"] != BV_RESULT[bvs["status"]] or bc["patient_cost_share"] != bvs["expected_cost_share"]
                or bvs["expected_cost_share"] != cur["patient_cost_share"]):
            fail(f"{cid}: benefit check result or cost share differs from the case")
        if (bc["result"] == "not_covered") != (form["status"] == "not_covered"):
            fail(f"{cid}: benefit check and formulary disagree on coverage")
        if bc["result"] == "out_of_network" and plan["required_pharmacy"] != "non-network":
            fail(f"{cid}: out_of_network without a non-network mandate")
        before = [s for s in case["shipments"] if s["date"] < bc["date"]]
        after = [s for s in case["shipments"] if s["date"] >= bc["date"]]
        new_start = not before and bool(after) and after[0]["package"] == "PKG-STARTER"
        needs_pa = form["prior_authorization"] == "all" or form["prior_authorization"] == "new_starts" and new_start
        on_file = any(t["type"] == "pa_decision" and t["outcome"] == "approved" and t["date"] <= bc["date"]
                      and t["valid_through"] >= bc["date"] for t in cur_tx)
        if bc["result"] in ("covered", "pa_required") and (bc["result"] == "pa_required") != (needs_pa and not on_file):
            fail(f"{cid}: benefit check says {bc['result']} but the formulary and authorizations say otherwise")
        if bool(bc["authorization_on_file"]) != (needs_pa and on_file):
            fail(f"{cid}: authorization_on_file does not match the transactions")

        pa = case["pa"]
        ev = [t for t in cur_tx if t["type"] in PA_EVENTS and t["date"] >= bc["date"]]
        reqs = [t for t in ev if t["type"] in ("pa_request", "network_exception_request")]
        decisions = [t for t in ev if t["type"] in ("pa_decision", "appeal_decision")]
        appeals = [t for t in ev if t["type"] == "appeal_request"]
        denial = [t for t in ev if t["type"] == "pa_decision" and t["outcome"] == "denied"]
        for t in ev:
            if t["type"] == "pa_request":
                if t["criteria_id"] != form["pa_criteria"]:
                    fail(f"{t['id']}: criteria {t['criteria_id']} are not the formulary's")
                if t["new_start"] != new_start:
                    fail(f"{t['id']}: new_start does not match the case's shipments")
        want = {
            "submitted_on": reqs[0]["date"] if reqs else None,
            "decided_on": decisions[-1]["date"] if decisions else None,
            "appeal_submitted_on": appeals[-1]["date"] if appeals else None,
            "denial_reason": denial[-1]["reason"] if denial else None,
        }
        for k, v in want.items():
            if pa[k] != v:
                fail(f"{cid}: pa.{k} is {pa[k]} but transactions give {v}")
        last = decisions[-1] if decisions else None
        status = ("PA_NOT_REQUIRED" if not reqs and bc["result"] != "not_covered" else
                  "PA_AWAITING_OFFICE" if not reqs else
                  "NETWORK_EXCEPTION_PENDING" if reqs[0]["type"] == "network_exception_request" else
                  "PA_SUBMITTED" if not decisions and not appeals else
                  "APPEAL_SUBMITTED" if appeals and (not last or last["type"] == "pa_decision") else
                  "PA_APPROVED" if last["type"] == "pa_decision" and last["outcome"] == "approved" else
                  "PA_DENIED" if last["type"] == "pa_decision" else
                  "APPEAL_APPROVED" if last["outcome"] == "approved" else "APPEAL_DENIED_FINAL")
        if pa["status"] != status:
            fail(f"{cid}: pa.status is {pa['status']} but transactions give {status}")

    fhir = load("payer/formulary-fhir.json")["bundle"]
    res = {(e["resource"]["resourceType"], e["resource"]["id"]): e["resource"] for e in fhir["entry"]}
    for f in forms.values():
        item = res.get(("Basic", f"{f['id']}-quorvanta"))
        if ("InsurancePlan", f["id"]) not in res or (item is None) != (f["quorvanta"]["status"] != "covered"):
            fail(f"payer/formulary-fhir.json: {f['id']} out of date; run scripts/render.py")
            continue
        if item:
            got = {e["url"].rsplit("usdf-", 1)[1]: e for e in item["extension"]}
            q = f["quorvanta"]
            if (got["DrugTierID-extension"]["valueCodeableConcept"]["coding"][0]["code"] != q["tier"]
                    or got["PriorAuthorization-extension"]["valueBoolean"] != (q["prior_authorization"] != "none")
                    or got["StepTherapyLimit-extension"]["valueBoolean"] != q["step_therapy"]):
                fail(f"payer/formulary-fhir.json: {f['id']} out of date; run scripts/render.py")
    if len(res) != len(fhir["entry"]) or len([r for r in res if r[0] == "InsurancePlan"]) != len(forms):
        fail("payer/formulary-fhir.json: entries do not match plans.json; run scripts/render.py")
    readme_counts(text("README.md"), [
        (r"(\d+) plans on (\d+) formularies", (len(plans), len(forms))),
        (r"(\d+) coverage records and (\d+) payer transactions", (len(covs), len(txs))),
    ])


def gs1_check(body):
    total = sum(int(d) * (3 if i % 2 == 0 else 1) for i, d in enumerate(reversed(body)))
    return str((10 - total % 10) % 10)


def check_channel():
    from datetime import date, timedelta
    product = load("product/product-identifiers.json")
    by_gtin = {p["gtin"]: p for p in product["packages"]}
    packages = {p["id"]: p for p in product["packages"]}
    lots = {l["lot"]: l for l in product["lots"]}
    network = {p["id"]: p for p in load("access/specialty-pharmacy-network.json")["pharmacies"]}
    tp = load("channel/trading-partners.json")
    loc_owner, sp_by_loc = {}, {}
    for p in tp["parties"]:
        ok_prefix = p["prefix"] == "0300000" if p["id"] == "TP-AQB" else re.fullmatch(r"02000(0[1-9]|1[01])", p["prefix"])
        if not ok_prefix:
            fail(f"{p['id']}: prefix {p['prefix']} is outside the fiction ranges")
        for g in [p["gln"]] + [l["gln"] for l in p["locations"]]:
            if not re.fullmatch(r"\d{13}", g) or gs1_check(g[:-1]) != g[-1] or not g.startswith(p["prefix"]):
                fail(f"{p['id']}: GLN {g} is malformed or has a wrong check digit")
        for l in p["locations"]:
            loc_owner[l["sgln"]] = p["id"]
            if p["role"] == "dispenser":
                sp_by_loc[l["sgln"]] = p["pharmacy_id"]
        if p["role"] == "dispenser":
            n = network.get(p["pharmacy_id"])
            if n is None or n["ncpdp"].split()[0] != p["ncpdp"]:
                fail(f"{p['id']}: not a network pharmacy, or NCPDP differs")

    def package_of(epc):
        m = re.fullmatch(r"urn:epc:id:sgtin:(\d{7})\.(\d{6})\.([A-Z0-9]{12})", epc)
        if not m:
            return None
        body = m.group(2)[0] + m.group(1) + m.group(2)[1:]
        return by_gtin.get(body + gs1_check(body))

    events = load("channel/epcis-events.json")["document"]["epcisBody"]["eventList"]
    state = {}                      # epc -> dict(lot, package, at, out, out_day)
    dispensed = {}                  # (serial, day, pharmacy)
    times = [e["eventTime"][:16] for e in events]
    if times != sorted(times):
        fail("channel/epcis-events.json: events are not in time order")
    for n, e in enumerate(events):
        day = e["eventTime"][:10]
        where = e.get("bizLocation", e.get("readPoint", {})).get("id")
        if where not in loc_owner:
            fail(f"EPCIS event {n}: unknown location {where}")
        epcs = e.get("epcList", []) + e.get("childEPCs", [])
        for epc in epcs:
            if epc.startswith("urn:epc:id:sscc:"):
                m = re.fullmatch(r"urn:epc:id:sscc:(\d{7})\.(\d{10})", epc)
                if not m:
                    fail(f"EPCIS event {n}: malformed SSCC {epc}")
                continue
            pkg = package_of(epc)
            if pkg is None:
                fail(f"EPCIS event {n}: {epc} is not a serial of a pack GTIN")
                continue
            s = state.get(epc)
            if e["bizStep"] == "commissioning":
                lot = lots.get(e["ilmd"]["cbvmda:lotNumber"])
                if s or lot is None or lot["package"] != pkg["id"] or lot["expiry"] != e["ilmd"]["cbvmda:itemExpirationDate"] or day < lot["manufactured"]:
                    fail(f"EPCIS event {n}: {epc} commissioned twice, or lot, package, expiry or date is wrong")
                    continue
                state[epc] = {"lot": lot, "at": where, "out": None}
                continue
            if s is None:
                fail(f"EPCIS event {n}: {epc} has events before commissioning")
                continue
            if s["out"]:
                fail(f"EPCIS event {n}: {epc} has events after it was {s['out']}")
            if e["type"] == "AggregationEvent" and e["action"] == "DELETE":
                s["at"] = where
            if e["bizStep"] == "dispensing":
                if where not in sp_by_loc or s["at"] != where:
                    fail(f"EPCIS event {n}: {epc} dispensed where it is not held")
                if date.fromisoformat(s["lot"]["expiry"]) < date.fromisoformat(day) + timedelta(days=30):
                    fail(f"EPCIS event {n}: {epc} dispensed from lot {s['lot']['lot']}, which expires before the supply is used")
                s["out"], s["out_day"] = "dispensed", day
                dispensed[epc.rsplit(".", 1)[1]] = (day, sp_by_loc.get(where), s["lot"]["lot"], pkg["ndc"])
            if e["disposition"] == "expired" and day <= s["lot"]["expiry"]:
                fail(f"EPCIS event {n}: {epc} marked expired before {s['lot']['expiry']}")
            if e["bizStep"] == "destroying":
                s["out"], s["out_day"] = "destroyed", day

    feed = load("channel/dispense-867.json")
    records = feed["records"]
    seen = set()
    for r in records:
        d = dispensed.get(r["serial"])
        if r["serial"] in seen or d != (r["dispense_date"], r["pharmacy_id"], r["lot"], r["ndc"]):
            fail(f"{r['record_id']}: no matching EPCIS dispensing event, or serial reused")
        seen.add(r["serial"])
    if len(seen) != len(dispensed):
        fail("channel/dispense-867.json: EPCIS dispensing events without an 867 record")
    npis = {h["npi"] for h in load("crm/field-force.json")["hcps"]}
    cases = {c["case_id"]: c for c in load("test-design/ps-cases.json")["cases"]}
    tx = load("payer/transactions.json")
    covs = {c["id"]: c for c in tx["coverages"]}
    claim_sp = {(t["case_id"], t["date"]): t["pharmacy_id"] for t in tx["transactions"]
                if t["type"] == "claim" and t["result"] == "paid" and covs[t["coverage_id"]]["order"] == "primary"}
    start, end = feed["period"]["start"], feed["period"]["end"]
    want, held = set(), set()
    for cid, c in cases.items():
        for s in c["shipments"]:
            if not start <= s["date"] <= end or s["lot"] is None:
                continue
            sp = "SP-04" if s["source"] in ("bridge", "pap") else claim_sp.get((cid, s["date"]))
            if s["status"] in ("SHIP_SHIPPED", "SHIP_DELIVERED"):
                want.add((cid, s["date"], packages[s["package"]]["ndc"], s["lot"], sp))
            else:
                held.add((cid, s["date"], s["lot"]))
    got = set()
    for r in records:
        if r["prescriber_npi"] not in npis:
            fail(f"{r['record_id']}: prescriber NPI {r['prescriber_npi']} is not in crm/field-force.json")
        if r["hub_case_id"]:
            got.add((r["hub_case_id"], r["dispense_date"], r["ndc"], r["lot"], r["pharmacy_id"]))
            c = cases[r["hub_case_id"]]
            npi = next((h["npi"] for h in load("crm/field-force.json")["hcps"] if h["id"] == c["prescriber_id"]), None)
            if r["prescriber_npi"] != npi or r["ship_to_state"] != c["patient"]["state"]:
                fail(f"{r['record_id']}: prescriber or state differs from {r['hub_case_id']}")
    if got != want:
        fail(f"channel/dispense-867.json: case dispenses differ from case shipments: missing {sorted(want - got)[:3]}, extra {sorted(got - want)[:3]}")
    for a in feed["held_allocations"]:
        epc = next((k for k in state if k.endswith("." + a["serial"])), None)
        if (a["case_id"], a["date"], a["lot"]) not in held or epc is None or state[epc]["out"] or state[epc]["lot"]["lot"] != a["lot"]:
            fail(f"held allocation {a['serial']}: not a held case shipment, or not on hand")

    periods = sorted({(r["period_start"], r["period_end"]) for r in load("channel/inventory-852.json")["reports"]})
    for r in load("channel/inventory-852.json")["reports"]:
        sp, a, b = r["pharmacy_id"], r["period_start"], r["period_end"]
        nxt = str(date.fromisoformat(b) + timedelta(days=1))
        mine = []
        for epc, s in state.items():
            if package_of(epc)["ndc"] != r["ndc"]:
                continue
            arrive = None
            for e in events:
                if e["type"] == "AggregationEvent" and e["action"] == "DELETE" and epc in e["childEPCs"] and sp_by_loc.get(e["bizLocation"]["id"]) == sp:
                    arrive = e["eventTime"][:10]
            if arrive:
                mine.append((arrive, s.get("out_day"), s["out"], s["lot"]["lot"]))
        on = lambda d: [m for m in mine if m[0] < d and (m[1] is None or m[1] >= d)]
        calc = {
            "opening_on_hand": len(on(a)),
            "received": sum(a <= m[0] <= b for m in mine),
            "dispensed": sum(m[2] == "dispensed" and a <= m[1] <= b for m in mine),
            "closing_on_hand": len(on(nxt)),
        }
        adj = -sum(m[2] == "destroyed" and a <= m[1] <= b for m in mine)
        lots_on = {}
        for m in on(nxt):
            lots_on[m[3]] = lots_on.get(m[3], 0) + 1
        for k, v in calc.items():
            if r[k] != v:
                fail(f"852 {sp} {r['ndc']} {a}: {k} is {r[k]}, EPCIS gives {v}")
        if sum(x["quantity"] for x in r["adjustments"]) != adj:
            fail(f"852 {sp} {r['ndc']} {a}: adjustments differ from EPCIS destruction events")
        if r["opening_on_hand"] + r["received"] - r["dispensed"] + sum(x["quantity"] for x in r["adjustments"]) != r["closing_on_hand"]:
            fail(f"852 {sp} {r['ndc']} {a}: the row does not balance")
        if {x["lot"]: x["quantity"] for x in r["lots_on_hand"]} != lots_on:
            fail(f"852 {sp} {r['ndc']} {a}: lots_on_hand differ from EPCIS")

    ships = load("channel/shipments.json")["shipments"]
    for s in ships:
        for line in s["lines"]:
            if line["lot"] not in lots or lots[line["lot"]]["expiry"] != line["expiry"]:
                fail(f"{s['id']}: lot or expiry is wrong")
            if "sscc" in line and (not re.fullmatch(r"\d{18}", line["sscc"]) or gs1_check(line["sscc"][:-1]) != line["sscc"][-1]):
                fail(f"{s['id']}: SSCC {line['sscc']} has a wrong check digit")
        if s["kind"] == "sale" and not s.get("dscsa"):
            fail(f"{s['id']}: sale without DSCSA transaction data")
        if re.search(r"price|amount|cost", json.dumps(s), re.I):
            fail(f"{s['id']}: carries a price; the pack has none")
    readme_counts(text("README.md"), [
        (r"(\d+) EPCIS events covering (\d+) serial numbers", (len(events), len(state))),
        (r"(\d+) dispense records \((\d+) of them case shipments\)", (len(records), sum(bool(r["hub_case_id"]) for r in records))),
        (r"(\d+) monthly inventory rows", (len(load("channel/inventory-852.json")["reports"]),)),
        (r"(\d+) product shipments", (len(ships),)),
    ])


SPL_EXCERPT_CODES = {"34066-1", "43683-2", "34067-9", "34068-7", "43678-2", "34070-3", "43685-7", "34084-4", "34073-7", "43684-0", "49489-8"}


def check_spl():
    import xml.etree.ElementTree as ET
    sys.path.insert(0, str(ROOT / "scripts"))
    import render
    rel = "label/label-spl.xml"
    body = text(rel)
    if body != render.build_spl():
        fail(f"{rel}: out of date with label.md or product-identifiers.json; run scripts/render.py")
    try:
        root = ET.fromstring(body.encode())
    except ET.ParseError as e:
        fail(f"{rel}: not well-formed XML: {e}")
        return
    ns = {"v": "urn:hl7-org:v3"}
    if root.find("v:code", ns).get("code") != "34391-3":
        fail(f"{rel}: document code is not 34391-3")
    allowed = {c for c, _ in render.SPL_SECTIONS.values()} | {render.UNCLASSIFIED[0], "48780-1", "51945-4"}
    titles = set()
    for sec in root.iter("{urn:hl7-org:v3}section"):
        code = sec.find("v:code", ns).get("code")
        if code not in allowed:
            fail(f"{rel}: unexpected section code {code}")
        if sec.find("v:excerpt", ns) is not None and code not in SPL_EXCERPT_CODES:
            fail(f"{rel}: highlights in section {code}, where FDA does not allow them")
        t = sec.find("v:title", ns)
        titles.add("".join(t.itertext()) if t is not None else "")
    for m in re.finditer(r"^#{2,3} (\d+(?:\.\d+)?) (.+)$", text("label/label.md"), re.M):
        if f"{m.group(1)} {m.group(2)}" not in titles:
            fail(f"{rel}: label section {m.group(1)} is missing")
    packs = [p["ndc"] for p in load("product/product-identifiers.json")["packages"]]
    codes = [c.get("code") for c in root.iter("{urn:hl7-org:v3}code") if c.get("codeSystem") == render.NDC_OID]
    for ndc in packs:
        ten = render.ndc10(ndc)
        if not re.fullmatch(r"\d{5}-\d{3}-\d{2}", ten) or ten not in codes:
            fail(f"{rel}: 10-digit NDC for {ndc} missing or malformed")


def field_values(record, path):
    """Values at a dotted path; a segment ending in [] iterates a list."""
    values = [record]
    for part in path.split("."):
        nxt = []
        for v in values:
            if not isinstance(v, dict):
                continue
            key = part[:-2] if part.endswith("[]") else part
            got = v.get(key)
            if part.endswith("[]"):
                nxt.extend(got or [])
            elif got is not None:
                nxt.append(got)
        values = nxt
    return values


def check_population():
    """Generated entities in sources/population/: generic checks driven by each file's own header."""
    from datetime import date
    folder = SRC / "population"
    if not folder.exists():
        return
    ff = load("crm/field-force.json")
    core_npis = {h["npi"] for h in ff["hcps"]}
    core_names = {f"{h['first_name']} {h['last_name']}" for h in ff["hcps"]} | {s["name"] for s in ff["staff"]}
    core_names |= {f"{c['patient']['first_name']} {c['patient']['last_name']}" for c in load("test-design/ps-cases.json")["cases"]}
    plan_names = {p["name"] for p in load("payer/plans.json")["plans"]}
    docs = {}
    for path in sorted(folder.glob("*.json")):
        doc = json.loads(path.read_text())
        docs[doc["entity"]] = doc
    ids = {n: {r["id"] for r in d["records"]} for n, d in docs.items()}
    npi_owner = {}
    for name, doc in docs.items():
        where = f"population/{name}.json"
        gen = doc["generated"]
        if gen["count"] != len(doc["records"]) or len(ids[name]) != len(doc["records"]):
            fail(f"{where}: count or ids inconsistent")
        as_of = date.fromisoformat(gen["as_of"])
        by_id = {r["id"]: r for r in doc["records"]}
        for r in doc["records"]:
            rid = r["id"]
            if not re.fullmatch(rf"{doc['id_prefix']}-\d{{5}}", rid):
                fail(f"{where}: id {rid} does not match {doc['id_prefix']}-NNNNN")
            for path, target in doc["references"].items():
                for v in field_values(r, path):
                    if target not in ids:
                        fail(f"{where}: references {target}, which has not been generated")
                    elif v not in ids[target]:
                        fail(f"{where} {rid}: {path} {v} does not exist in {target}")
            for fld, (ref_path, other) in doc.get("must_match", {}).items():
                target = next(t for p, t in doc["references"].items() if p == ref_path)
                pool = {x["id"]: x for x in docs.get(target, {}).get("records", [])}
                for v in field_values(r, ref_path):
                    if v in pool and pool[v].get(other) != r.get(fld):
                        fail(f"{where} {rid}: {fld} differs from {ref_path} {v}'s {other}; regenerate {name}")
            flag_types = {f["type"] for f in r.get("quality_flags", [])}
            for t in flag_types - set(doc["quality_flags"]):
                fail(f"{where} {rid}: quality flag {t} is not in the file's legend")
            if f"{r.get('first_name')} {r.get('last_name')}" in core_names:
                fail(f"{where} {rid}: repeats a core cast member's name")
            for email in field_values(r, "email"):
                if not email.endswith(".example"):
                    fail(f"{where} {rid}: email {email} is not in .example")
            if "npi" in r:
                if not npi_ok(r["npi"]) or not r["npi"].startswith("91") or r["npi"] in core_npis:
                    fail(f"{where} {rid}: NPI {r['npi']} is not a 91-prefixed pack NPI, or collides with the core cast")
                dup = next((f["of"] for f in r["quality_flags"] if f["type"] == "duplicate"), None)
                if dup:
                    if by_id.get(dup, {}).get("npi") != r["npi"]:
                        fail(f"{where} {rid}: a duplicate must share its original's NPI")
                elif r["npi"] in npi_owner:
                    fail(f"{where} {rid}: NPI {r['npi']} also belongs to {npi_owner[r['npi']]}")
                else:
                    npi_owner[r["npi"]] = rid
            if "dob" in r:
                born = date.fromisoformat(r["dob"])
                age = as_of.year - born.year - ((as_of.month, as_of.day) < (born.month, born.day))
                if (age < 18) != ("minor" in flag_types):
                    fail(f"{where} {rid}: age {age} does not match its minor flag")
            ins = r.get("insurance")
            if ins:
                for plan in (ins["plan_name"], ins.get("secondary_plan_name")):
                    if plan and plan not in plan_names and plan != "VA health care" and not re.fullmatch(r"[A-Z]{2} Medicaid \(fee-for-service\)", plan):
                        fail(f"{where} {rid}: plan {plan} is not in payer/plans.json")


def read_denylist(path):
    if path is None:
        return []
    lines = Path(path).read_text().splitlines()
    return [l.strip() for l in lines if l.strip() and not l.strip().startswith("#")]


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--denylist", help="file of real names that must not appear (keep outside the repo)")
    args = parser.parse_args()

    check_json_files()
    check_markdown_notices()
    if errors:
        report()

    claims_doc = load("claims/claims-library.json")
    refs_doc = load("claims/references.json")
    promo_doc = load("promotional/promo-materials.json")
    dtc_doc = load("patient/dtc-claims.json")
    gaps_doc = load("test-design/known-gaps.json")
    srds_doc = load("medical-information/srds.json")
    form_doc = load("access/start-form.json")

    claims, refs, findings = check_claims_and_references(claims_doc, refs_doc)
    check_claim_users(claims, promo_doc, dtc_doc)
    check_promo_renderings(promo_doc)
    gaps, srds = check_gaps_and_srds(gaps_doc, srds_doc, refs)
    check_markdown_pairs(refs, findings, srds, form_doc)
    check_readme_counts(claims, refs, gaps, srds, dtc_doc, form_doc)
    check_patient_services(claims, refs, load("access/specialty-pharmacy-network.json"))
    check_product(claims)
    disease = check_disease(refs, findings)
    check_landscape()
    faults, coverage = check_scenarios(claims_doc, disease, {g["id"] for g in gaps_doc["gaps"]}, {s["id"] for s in srds_doc["srds"]})
    lots = {l["lot"] for l in load("product/product-identifiers.json")["lots"]}
    reports, ae_coverage = check_safety(lots)
    crm_coverage = check_field_force(claims_doc, set(srds), reports)
    check_payer()
    check_channel()
    check_spl()
    check_population()
    for owner, ids in [(r["id"], r["provokes"]) for r in reports.values()]:
        for f in ids:
            if f not in faults:
                fail(f"{owner}: unknown fault {f}")
    for f in sorted((ae_coverage | crm_coverage) - set(faults)):
        fail(f"labelled sets: unknown fault {f}")
    for f in faults:
        if f not in coverage | ae_coverage | crm_coverage:
            fail(f"fault-types: {f} has no failing example in the labelled sets")
    check_fiction_markers(read_denylist(args.denylist))
    report()


def report():
    if errors:
        for e in errors:
            print(f"FAIL  {e}")
        print(f"\n{len(errors)} problem(s) found.")
        sys.exit(1)
    print("All checks passed.")
    sys.exit(0)


if __name__ == "__main__":
    main()
