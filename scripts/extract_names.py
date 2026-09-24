#!/usr/bin/env python3
"""List every invented non-person name in the pack, for clearance before release.

Run from anywhere:  python3 scripts/extract_names.py

Writes scripts/names-to-check.csv: one row per name, with a
priority, what kind of check it needs, and where it is used. People, cities,
real public programs and standards bodies are left out. The status and notes
columns are for whoever does the checking; re-running keeps them for names
that are still in the pack. Standard library only.
"""

import csv
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "sources"
OUT = ROOT / "scripts" / "names-to-check.csv"

CHECKS = {
    "brand": "Trademark registers (USPTO and major markets), FDA drug name databases, web search",
    "nonproprietary": "WHO INN and USAN lists, chemical name databases, web search",
    "company": "Company registries, trademark registers, web search",
    "program": "Trademark registers, web search (patient support programs, foundations, registries)",
    "ticker": "Stock exchange symbol lookup",
    "trial": "Clinical trial registries (study acronyms), web search",
    "disease": "Medical terminologies and literature, web search",
    "organization": "Web search; professional bodies and journals",
    "payer": "Health plan, PBM and insurer names; trademark registers, web search",
    "pharmacy": "Pharmacy and specialty pharmacy names; state board listings, web search",
    "provider": "Practice, clinic and health system names; web search",
    "lab": "Laboratory names; web search",
    "supply_chain": "Logistics and packaging company names; web search",
    "reference": "A real product or vendor named in prose; decide whether it may stay",
}
PRIORITY = {"brand": "A", "nonproprietary": "A", "company": "A", "program": "A", "ticker": "A", "trial": "A",
            "disease": "A", "organization": "B", "payer": "B", "pharmacy": "B", "supply_chain": "B", "reference": "A",
            "provider": "B", "lab": "B"}


# Generic words stripped from the end of a name to find the distinctive stem worth searching for.
GENERIC = {"PPO", "HMO", "EPO", "HDHP", "Bronze", "Silver", "Gold", "Marketplace", "Choice", "Advantage", "Medicare",
           "Part", "D", "pharmacy", "benefits", "Benefits", "Services", "Rx", "Specialty", "Pharmacy", "System", "Plan",
           "Plans", "Employee", "Employer", "Health", "Neurology", "Associates", "Clinic", "Center", "Care", "Group",
           "Medical", "Physicians", "Partners", "Laboratories", "Laboratory", "Diagnostics", "Regional", "Clinical",
           "Pathology", "Institute", "Neuroscience", "Neurological", "Community", "Family", "Logistics", "Packaging"}


def stem(name, kind):
    if kind not in ("payer", "pharmacy", "provider", "lab", "supply_chain"):
        return name
    words = re.sub(r"\s*\(.*?\)", "", name).split()
    while len(words) > 1 and words[-1] in GENERIC:
        words.pop()
    return " ".join(words)


def load(rel):
    return json.loads((SRC / rel).read_text())


def collect():
    names = {}

    def add(name, kind, where):
        name = re.sub(r",? Inc\.$", "", name.strip())
        if name and name not in names:
            names[name] = (kind, where)

    product = load("claims/claims-library.json")["product"]
    add(product["brand"], "brand", "product")
    add(product["generic"], "nonproprietary", "product")
    add(product["predecessor"]["name"], "nonproprietary", "product predecessor")
    add("monomethyl tavorate", "nonproprietary", "active metabolite")
    add("hydroxypropyl glavorimide", "nonproprietary", "inactive metabolite")
    add(product["company"], "company", "manufacturer")
    add(product["condition"]["name"], "disease", "condition")
    add(product["condition"]["disability_scale"].split(" (")[0], "disease", "disability scale")
    add("International Brennick Syndrome Consortium", "organization", "disease body")
    add("QuorvantaConnect", "program", "patient support program")
    add("Arden Quay Patient Assistance Foundation", "program", "patient assistance foundation")
    add("QUORVANTA Pregnancy Registry", "program", "pregnancy exposure registry")
    add("AQBX", "ticker", "stock ticker in the press releases (Nasdaq)")
    add("Jev", "reference", "sources/README.md, claim schema section")

    for t in load("landscape/competitors.json")["therapies"]:
        add(t["brand"], "brand", "competitor")
        add(t["generic"], "nonproprietary", "competitor")
        add(t["company"], "company", "competitor company")

    for r in load("claims/references.json")["references"]:
        venue = re.sub(r" \(fictitious.*\)$", "", r["venue"])
        if "Arden Quay" not in venue:
            add(venue, "organization", "journal, meeting or preprint server")
        for a in r["authors"]:
            if "Group" in a:
                add(re.sub(r"^for the ", "", a), "organization", "study group")
    text = "\n".join(p.read_text() for p in SRC.rglob("*.md"))
    for trial in sorted(set(re.findall(r"\b(BRIGHTWATER|CASTLEREAGH|EVERGARTER(?:-\d)?)\b", text))):
        add(trial, "trial", "study name")

    for p in load("access/specialty-pharmacy-network.json")["pharmacies"]:
        add(p["name"], "pharmacy", "specialty pharmacy network")
        parent = re.sub(r" \(fictitious.*\)$", "", p["parent"])
        if parent != "Independent":
            add(parent, "payer" if "PBM" in p["parent"] else "provider", "pharmacy parent")
    plans = load("payer/plans.json")
    for pr in plans["processors"]:
        if not pr["name"].startswith("TRICARE"):
            add(pr["name"], "payer", "pharmacy benefit processor")
    for pl in plans["plans"]:
        if pl["name"] != "TRICARE":
            add(pl["name"], "payer", "health plan")
        if pl["required_pharmacy_name"]:
            add(pl["required_pharmacy_name"].split(" (")[0], "pharmacy", "plan-mandated pharmacy outside the network")
    for p in load("channel/trading-partners.json")["parties"]:
        if p["role"] in ("contract_packager", "3pl"):
            add(p["name"].split(" (")[0], "supply_chain", p["role"].replace("_", " "))
    for h in load("crm/field-force.json")["hcos"]:
        add(h["name"], "provider", "account in crm/field-force.json")

    pop = SRC / "population"
    if pop.exists():
        for o in json.loads((pop / "offices.json").read_text())["records"]:
            if not o["quality_flags"] and o["type"] != "health_system_site":
                add(o["name"], "provider", "generated office")
        for l in json.loads((pop / "labs.json").read_text())["records"]:
            if not l["quality_flags"] or l["quality_flags"][0]["type"] != "duplicate":
                if l["type"] in ("national_reference_lab", "regional_lab"):
                    add(l["name"], "lab", "generated lab")
    return names


def main():
    names = collect()
    files = [p for p in sorted(SRC.rglob("*")) if p.suffix in {".md", ".json", ".xml"}]
    bodies = {p: p.read_text() for p in files}
    kept = {}
    if OUT.exists():
        with OUT.open() as f:
            for row in csv.DictReader(f):
                kept[row["name"]] = (row.get("status", ""), row.get("notes", ""))
    rows = []
    for name, (kind, role) in names.items():
        pattern = re.compile(rf"(?<![\w-]){re.escape(name)}(?![\w])")
        hits = {str(p.relative_to(SRC)): len(pattern.findall(b)) for p, b in bodies.items() if pattern.search(b)}
        status, notes = kept.get(name, ("", ""))
        rows.append({"priority": PRIORITY[kind], "kind": kind, "name": name, "stem": stem(name, kind), "role": role,
                     "check": CHECKS[kind],
                     "occurrences": sum(hits.values()), "files": len(hits),
                     "used_in": "; ".join(sorted(hits)[:6]) + ("; ..." if len(hits) > 6 else ""),
                     "status": status, "notes": notes})
    order = list(CHECKS)
    rows.sort(key=lambda r: (r["priority"], order.index(r["kind"]), r["name"].lower()))
    with OUT.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    by = {}
    for r in rows:
        by[(r["priority"], r["kind"])] = by.get((r["priority"], r["kind"]), 0) + 1
    print(f"wrote {OUT.relative_to(ROOT)}: {len(rows)} names, {len({r['stem'] for r in rows})} distinct stems")
    for (p, k), n in sorted(by.items(), key=lambda kv: (kv[0][0], order.index(kv[0][1]))):
        print(f"  {p} {k:15} {n}")
    dropped = sorted(set(kept) - set(names))
    if dropped:
        print(f"note: {len(dropped)} names with saved status are no longer in the pack: {', '.join(dropped[:5])}")


if __name__ == "__main__":
    main()
