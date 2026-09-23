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


USDF = "http://hl7.org/fhir/us/davinci-drug-formulary"
PACK_TAG = {"system": "https://ardenquay.example/fhir/CodeSystem/pack-tags", "code": "fictitious",
            "display": "Invented test data; no real plan, formulary or drug"}


def ext(name, **value):
    return {"url": f"{USDF}/StructureDefinition/usdf-{name}-extension", **value}


def render_formulary_fhir():
    """FHIR R4 collection Bundle shaped after the HL7 US Drug Formulary IG (STU2).

    Deliberate non-conformance: FormularyDrug requires an RxNorm code, and an
    invented drug has none, so the drug is coded with a pack-local code system
    and its NDCs.
    """
    data = json.loads((SRC / "payer/plans.json").read_text())
    product = json.loads((SRC / "product/product-identifiers.json").read_text())
    stamp = f"{data['as_of']}T00:00:00Z"
    meta = lambda profile: {"lastUpdated": stamp, "profile": [f"{USDF}/StructureDefinition/usdf-{profile}"], "tag": [PACK_TAG]}
    drug = {
        "resourceType": "MedicationKnowledge", "id": "quorvanta-190-dr", "meta": meta("FormularyDrug"),
        "code": {"coding": [{"system": "https://ardenquay.example/fhir/CodeSystem/drug", "code": "QV-190-DR",
                             "display": "QUORVANTA (soriximel tavorate) 190 mg delayed-release capsule"}]
                 + [{"system": "http://hl7.org/fhir/sid/ndc", "code": p["ndc"], "display": p["name"]} for p in product["packages"]]},
        "status": "active",
        "doseForm": {"text": "delayed-release capsule"},
    }
    entries = [drug]
    for f in data["formularies"]:
        entries.append({
            "resourceType": "InsurancePlan", "id": f["id"], "meta": meta("Formulary"),
            "identifier": [{"system": "https://ardenquay.example/fhir/formulary-id", "value": f["id"]}],
            "status": "active",
            "type": [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/v3-ActCode", "code": "DRUGPOL"}]}],
            "name": f["name"], "period": f["period"],
        })
        q = f["quorvanta"]
        if q["status"] != "covered":
            continue
        limits = "; ".join(f"{v['quantity']} capsules per {v['days']} days ({k})" for k, v in q["quantity_limits"].items())
        info = [f"Quantity limit: {limits}."]
        if q["pa_criteria"]:
            info.append(f"Prior authorization criteria {q['pa_criteria']} in payer/plans.json.")
        info.append("Dispensed only by QUORVANTA network specialty pharmacies.")
        exts = [
            ext("FormularyReference", valueReference={"reference": f"InsurancePlan/{f['id']}"}),
            ext("AvailabilityStatus", valueCode="active"),
            ext("AvailabilityPeriod", valuePeriod=f["period"]),
            ext("PharmacyBenefitType", valueCodeableConcept={"coding": [{"system": f"{USDF}/CodeSystem/usdf-PharmacyBenefitTypeCS-TEMPORARY-TRIAL-USE", "code": "1-month-in-mail"}]}),
            ext("DrugTierID", valueCodeableConcept={"coding": [{"system": f"{USDF}/CodeSystem/usdf-DrugTierCS-TEMPORARY-TRIAL-USE", "code": q["tier"]}]}),
            ext("PriorAuthorization", valueBoolean=q["prior_authorization"] != "none"),
            ext("PriorAuthorizationNewStartsOnly", valueBoolean=q["prior_authorization"] == "new_starts"),
            ext("StepTherapyLimit", valueBoolean=q["step_therapy"]),
            ext("StepTherapyLimitNewStartsOnly", valueBoolean=q["step_therapy_new_starts_only"]),
            ext("QuantityLimit", valueBoolean=True),
            ext("AdditionalCoverageInformation", valueMarkdown=" ".join(info)),
        ]
        entries.append({
            "resourceType": "Basic", "id": f"{f['id']}-quorvanta", "meta": meta("FormularyItem"), "extension": exts,
            "code": {"coding": [{"system": f"{USDF}/CodeSystem/usdf-InsuranceItemTypeCS", "code": "formulary-item"}]},
            "subject": {"reference": f"MedicationKnowledge/{drug['id']}"},
        })
    doc = {
        "_notice": "FICTITIOUS. FHIR formulary resources for plans and a drug that do not exist. Generated from payer/plans.json by scripts/render.py; do not edit by hand.",
        "generated_from": "payer/plans.json",
        "conformance": "Shaped after the HL7 US Drug Formulary implementation guide STU2 (Formulary, FormularyItem, FormularyDrug) and not validated against it. The drug is coded with a pack-local code system and its NDCs because an invented drug has no RxNorm code, which the FormularyDrug profile requires. A formulary that excludes QUORVANTA has no FormularyItem. Unwrap the bundle field before loading it into a FHIR server.",
        "bundle": {"resourceType": "Bundle", "id": "quorvanta-formularies", "type": "collection", "timestamp": stamp,
                   "entry": [{"fullUrl": f"urn:ardenquay:{r['resourceType']}/{r['id']}", "resource": r} for r in entries]},
    }
    path = SRC / "payer/formulary-fhir.json"
    path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n")
    print(f"wrote {path.relative_to(SRC.parent)}")


if __name__ == "__main__":
    render_program_terms()
    render_product_identifiers()
    render_formulary_fhir()
