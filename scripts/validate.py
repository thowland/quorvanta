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
    for path in sorted(SRC.rglob("*.md")):
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
        if path.suffix not in {".md", ".json"}:
            continue
        rel = path.relative_to(SRC)
        body = path.read_text()
        for phone in re.findall(r"1-800-[A-Z0-9]{3}-[A-Z0-9]{4}", body):
            if phone not in ALLOWED_PHONES and not FICTION_PHONE.match(phone):
                fail(f"{rel}: phone {phone} is outside 1-800-555-01xx")
        for doi in re.findall(r"\b10\.\d{4,}/", body):
            if doi != "10.5555/":
                fail(f"{rel}: DOI prefix {doi} is not 10.5555")
        for host in sorted(set(re.findall(r"\b(?:[a-z0-9-]+\.)+(?:com|org|net|gov|io|co|us)\b", body, re.I))):
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
        (r"(\d+) fault types \((\d+) for the HCP bot, (\d+) for",
         (len(faults), sum(f.startswith("HF") for f in faults), sum(f.startswith("PF") for f in faults))),
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

    for f in faults:
        if f not in fault_coverage:
            fail(f"fault-types: {f} has no failing example in the outbound sets")



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
    check_scenarios(claims_doc, disease, {g["id"] for g in gaps_doc["gaps"]}, {s["id"] for s in srds_doc["srds"]})
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
