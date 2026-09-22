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
