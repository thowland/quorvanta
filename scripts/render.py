#!/usr/bin/env python3
"""Regenerate Markdown renderings from their canonical JSON.

Run from anywhere:  python3 scripts/render.py

Only documents whose Markdown is fully generated are handled here. Edit the
JSON, then re-run this script; never edit the generated Markdown by hand.
"""

import json
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "sources"


def render_program_terms():
    data = json.loads((SRC / "patient-services/program-terms.json").read_text())
    c = data["contact"]
    out = [
        f"# {data['program']} program terms and conditions (fictitious)",
        "",
        "> Everything here is invented. QuorvantaConnect, the Arden Quay Patient Assistance "
        "Foundation, and every amount, threshold and timeline do not exist. "
        "Generated from `program-terms.json` by `scripts/render.py`; do not edit by hand.",
        "",
        f"Version {data['terms_version']}, effective {data['effective']}. "
        f"Summarised in the bibliography as {data['summarised_by']}.",
        "",
        f"**{c['phone']}**, {c['hours']}. Fax {c['fax']}. {c['portal']}. {c['languages']}.",
    ]
    for section in data["sections"]:
        out += ["", f"## {section['title']}", ""]
        for p in section["provisions"]:
            out.append(f"- `{p['id']}` {p['text']}")
    path = SRC / "patient-services/program-terms.md"
    path.write_text("\n".join(out) + "\n")
    print(f"wrote {path.relative_to(SRC.parent)}")


def render_product_identifiers():
    data = json.loads((SRC / "product/product-identifiers.json").read_text())
    pr = data["product"]
    out = [
        "# QUORVANTA product identifiers (fictitious)",
        "",
        "> Everything here is invented. NDC labeler code 00000 is not an assigned labeler code, and no "
        "GTIN, lot or serial number here identifies a real product. "
        "Generated from `product-identifiers.json` by `scripts/render.py`; do not edit by hand.",
        "",
        f"{pr['brand']} ({pr['generic']}) {pr['strength']} {pr['dosage_form']}. {pr['capsule']}. "
        f"Shelf life {pr['shelf_life_months']} months. Storage: {pr['storage']}",
        "",
        "## Packages",
        "",
        "| Package | NDC | GTIN-14 | Capsules | Use | Lot prefix | Introduced |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for p in data["packages"]:
        out.append(f"| {p['name']} | {p['ndc']} | {p['gtin']} | {p['capsules']} | {p['use']} | {p['lot_prefix']} | {p['introduced']} |")
    out += ["", "## Formats", ""]
    names = {"ndc": "NDC", "gtin": "GTIN", "lot": "Lot", "expiry": "Expiry", "serial": "Serial"}
    out += [f"- **{names.get(k, k)}.** {v}" for k, v in data["formats"].items()]
    for pid, lines in data["bottle_label_text"].items():
        name = next(p["name"] for p in data["packages"] if p["id"] == pid)
        out += ["", f"## Bottle label: {name}", ""] + [f"- {l}" for l in lines]
    out += ["", f"## Lot register (as of {data['as_of']})", "", "| Lot | Package | Manufactured | Expiry | Status |", "| --- | --- | --- | --- | --- |"]
    for l in data["lots"]:
        out.append(f"| {l['lot']} | {l['package']} | {l['manufactured']} | {l['expiry']} | {l['status']} |")
    path = SRC / "product/product-identifiers.md"
    path.write_text("\n".join(out) + "\n")
    print(f"wrote {path.relative_to(SRC.parent)}")


if __name__ == "__main__":
    render_program_terms()
    render_product_identifiers()
