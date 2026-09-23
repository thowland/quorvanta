#!/usr/bin/env python3
"""Regenerate the pack's generated documents from their canonical sources.

Run from anywhere:  python3 scripts/render.py

Writes program-terms.md, product-identifiers.md, payer/formulary-fhir.json and
label/label-spl.xml. Edit the JSON (or label.md), then re-run this script;
never edit a generated file by hand.
"""

import json
import re
import uuid
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


LOINC = "2.16.840.1.113883.6.1"
NCI = "2.16.840.1.113883.3.26.1.1"
NDC_OID = "2.16.840.1.113883.6.69"
# A UUID-based OID (arc 2.25) for identifiers an invented product cannot have: UNIIs and the labeler's DUNS.
PACK_OID = "2.25." + str(uuid.uuid5(uuid.NAMESPACE_URL, "https://ardenquay.example/spl").int)
SPL_SECTIONS = {
    "1": ("34067-9", "INDICATIONS & USAGE SECTION"),
    "2": ("34068-7", "DOSAGE & ADMINISTRATION SECTION"),
    "3": ("43678-2", "DOSAGE FORMS & STRENGTHS SECTION"),
    "4": ("34070-3", "CONTRAINDICATIONS SECTION"),
    "5": ("43685-7", "WARNINGS AND PRECAUTIONS SECTION"),
    "6": ("34084-4", "ADVERSE REACTIONS SECTION"),
    "6.1": ("90374-0", "CLINICAL TRIALS EXPERIENCE SECTION"),
    "6.2": ("90375-7", "POSTMARKETING EXPERIENCE SECTION"),
    "7": ("34073-7", "DRUG INTERACTIONS SECTION"),
    "8": ("43684-0", "USE IN SPECIFIC POPULATIONS SECTION"),
    "8.1": ("42228-7", "PREGNANCY SECTION"),
    "8.2": ("77290-5", "LACTATION SECTION"),
    "8.4": ("34081-0", "PEDIATRIC USE SECTION"),
    "8.5": ("34082-8", "GERIATRIC USE SECTION"),
    "8.6": ("88828-9", "RENAL IMPAIRMENT SUBSECTION"),
    "11": ("34089-3", "DESCRIPTION SECTION"),
    "12": ("34090-1", "CLINICAL PHARMACOLOGY SECTION"),
    "12.1": ("43679-0", "MECHANISM OF ACTION SECTION"),
    "12.2": ("43681-6", "PHARMACODYNAMICS SECTION"),
    "12.3": ("43682-4", "PHARMACOKINETICS SECTION"),
    "14": ("34092-7", "CLINICAL STUDIES SECTION"),
    "16": ("34069-5", "HOW SUPPLIED SECTION"),
    "17": ("88436-1", "PATIENT COUNSELING INFORMATION"),
}
UNCLASSIFIED = ("42229-5", "SPL UNCLASSIFIED SECTION")
HIGHLIGHT_TARGET = {"Indication": "1", "Dosage and administration": "2", "Dosage form": "3", "Contraindications": "4",
                    "Warnings and precautions": "5", "Adverse reactions": "6", "Specific populations": "8"}


def ndc10(ndc11):
    """11-digit billing NDC (5-4-2) to the 10-digit form SPL requires; the pack pads the product code."""
    lab, prod, pkg = ndc11.split("-")
    assert len(prod) == 4 and prod[0] == "0", ndc11
    return f"{lab}-{prod[1:]}-{pkg}"


def xml_inline(s, links=False):
    s = s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    s = re.sub(r"\*\*(.+?)\*\*", r'<content styleCode="bold">\1</content>', s)
    s = re.sub(r"\*(.+?)\*", r'<content styleCode="italics">\1</content>', s)
    if links:
        s = re.sub(r"\((\d+(?:\.\d+)?)\)", lambda m: f'(<linkHtml href="#S{m.group(1).replace(".", "_")}">{m.group(1)}</linkHtml>)', s)
    return s


def xml_blocks(lines):
    """Paragraphs, bullet lists and captioned tables from a run of Markdown lines."""
    blocks, cur = [], []
    for line in lines + [""]:
        if line.strip():
            cur.append(line)
        elif cur:
            blocks.append(cur)
            cur = []
    out, caption = [], None
    for b in blocks:
        if b[0].startswith("|"):
            rows = [[c.strip() for c in r.strip().strip("|").split("|")] for r in b if not re.fullmatch(r"\|[\s\-|]+\|", r.strip())]
            head, body = rows[0], rows[1:]
            t = ["<table>"] + ([f"<caption>{xml_inline(caption)}</caption>"] if caption else [])
            t.append("<thead><tr>" + "".join(f"<th>{xml_inline(c)}</th>" for c in head) + "</tr></thead>")
            t.append("<tbody>" + "".join("<tr>" + "".join(f"<td>{xml_inline(c)}</td>" for c in r) + "</tr>" for r in body) + "</tbody>")
            out.append("".join(t) + "</table>")
            caption = None
        elif all(l.startswith("- ") for l in b):
            out.append('<list listType="unordered">' + "".join(f"<item>{xml_inline(l[2:])}</item>" for l in b) + "</list>")
        elif len(b) == 1 and re.fullmatch(r"\*\*Table .+\*\*", b[0]):
            caption = b[0].strip("*")
        else:
            out.append(f"<paragraph>{xml_inline(' '.join(b))}</paragraph>")
    return "".join(out)


def build_spl():
    """HL7 SPL (FDA R5) XML for label/label.md, with product data from product-identifiers.json."""
    md = (SRC / "label/label.md").read_text().splitlines()
    product = json.loads((SRC / "product/product-identifiers.json").read_text())
    gid = lambda key: str(uuid.uuid5(uuid.NAMESPACE_URL, f"https://ardenquay.example/spl/{key}"))
    version = re.search(r"Label version (\d+)\.(\d+)", "\n".join(md))
    eff = "20260901"

    highlights, sections, footer = {}, [], []
    mode, last = None, None
    for line in md[1:]:
        if line.startswith(">"):
            continue
        if line.strip() == "---":
            mode = "footer" if mode == "section" else mode
            continue
        if line.startswith("## HIGHLIGHTS"):
            mode = "highlights"
            continue
        m = re.match(r"^(##|###) (\d+(?:\.\d+)?) (.+)$", line)
        if m:
            mode = "section"
            sections.append({"num": m.group(2), "title": f"{m.group(2)} {m.group(3)}", "lines": []})
            continue
        if mode == "highlights" and line.strip():
            h = re.match(r"^\*\*(.+?)\.\*\* (.+)$", line)
            if h:
                last = HIGHLIGHT_TARGET[h.group(1)]
                highlights.setdefault(last, []).append(h.group(2))
            else:
                highlights[last].append(line)
        elif mode == "section":
            sections[-1]["lines"].append(line)
        elif mode == "footer" and line.strip():
            footer.append(line)
    sections[-1]["lines"] += [""] + footer

    def section_xml(sec, children):
        code, name = SPL_SECTIONS.get(sec["num"], UNCLASSIFIED)
        sid = "S" + sec["num"].replace(".", "_")
        parts = [f'<component><section ID="{sid}"><id root="{gid(sid)}"/>',
                 f'<code code="{code}" codeSystem="{LOINC}" displayName="{xml_inline(name)}"/>',
                 f"<title>{xml_inline(sec['title'])}</title>",
                 f"<text>{xml_blocks(sec['lines'])}</text>" if any(l.strip() for l in sec["lines"]) else "",
                 f'<effectiveTime value="{eff}"/>']
        if sec["num"] in highlights:
            paras = "".join(f"<paragraph>{xml_inline(p, links=True)}</paragraph>" for p in highlights[sec["num"]])
            parts.append(f"<excerpt><highlight><text>{paras}</text></highlight></excerpt>")
        parts += children + ["</section></component>"]
        return "".join(parts)

    body = []
    majors = [s for s in sections if "." not in s["num"]]
    for major in majors:
        kids = [section_xml(s, []) for s in sections if s["num"].startswith(major["num"] + ".")]
        body.append(section_xml(major, kids))

    desc = next(" ".join(s["lines"]) for s in sections if s["num"] == "11")
    inactive = []
    for group in re.findall(r"(?:Inactive ingredients|Capsule shell): ([^.]+)\.", desc):
        inactive += [x.strip() for x in re.split(r", | and ", group) if x.strip()]
    sub = lambda name: f'<code code="{re.sub("[^A-Z0-9]+", "-", name.upper()).strip("-")}" codeSystem="{PACK_OID}"/><name>{xml_inline(name.upper())}</name>'
    pr = product["product"]
    pkgs = product["packages"]
    first_ndc = ndc10(pkgs[0]["ndc"])
    ingredients = [
        '<ingredient classCode="ACTIB"><quantity><numerator value="190" unit="mg"/><denominator value="1" unit="1"/></quantity>'
        f"<ingredientSubstance>{sub(pr['generic'])}<activeMoiety><activeMoiety>{sub('monomethyl tavorate')}</activeMoiety></activeMoiety></ingredientSubstance></ingredient>"
    ] + [f'<ingredient classCode="IACT"><ingredientSubstance>{sub(n)}</ingredientSubstance></ingredient>' for n in inactive]
    contents = [
        f'<asContent><quantity><numerator value="{p["capsules"]}" unit="1"/><denominator value="1" unit="1"/></quantity>'
        f'<containerPackagedProduct><code code="{ndc10(p["ndc"])}" codeSystem="{NDC_OID}"/>'
        f'<formCode code="C43169" codeSystem="{NCI}" displayName="BOTTLE"/></containerPackagedProduct>'
        f'<subjectOf><marketingAct><code code="C53292" codeSystem="{NCI}"/><statusCode code="active"/>'
        f'<effectiveTime><low value="{p["introduced"].replace("-", "")}"/></effectiveTime></marketingAct></subjectOf></asContent>'
        for p in pkgs]
    product_section = (
        f'<component><section><id root="{gid("product-data")}"/>'
        f'<code code="48780-1" codeSystem="{LOINC}" displayName="SPL PRODUCT DATA ELEMENTS SECTION"/>'
        f'<title>SPL product data elements</title><text/><effectiveTime value="{eff}"/>'
        f'<subject><manufacturedProduct><manufacturedProduct>'
        f'<code code="{first_ndc.rsplit("-", 1)[0]}" codeSystem="{NDC_OID}"/><name>{pr["brand"]}</name>'
        f'<formCode code="C42902" codeSystem="{NCI}" displayName="CAPSULE, DELAYED RELEASE"/>'
        f'<asEntityWithGeneric><genericMedicine><name>{pr["generic"]}</name></genericMedicine></asEntityWithGeneric>'
        + "".join(ingredients) + "".join(contents) +
        "</manufacturedProduct>"
        f'<subjectOf><approval><id extension="NDA000000" root="2.16.840.1.113883.3.150"/>'
        f'<code code="C73594" codeSystem="{NCI}" displayName="NDA"/>'
        f'<author><territorialAuthority><territory><code code="USA" codeSystem="1.0.3166.1.2.3"/></territory></territorialAuthority></author></approval></subjectOf>'
        f'<subjectOf><marketingAct><code code="C53292" codeSystem="{NCI}"/><statusCode code="active"/>'
        f'<effectiveTime><low value="{pkgs[0]["introduced"].replace("-", "")}"/></effectiveTime></marketingAct></subjectOf>'
        f'<consumedIn><substanceAdministration><routeCode code="C38288" codeSystem="{NCI}" displayName="ORAL"/></substanceAdministration></consumedIn>'
        "</manufacturedProduct></subject></section></component>")
    panels = [
        f'<component><section><id root="{gid("panel-" + p["id"])}"/>'
        f'<code code="51945-4" codeSystem="{LOINC}" displayName="PACKAGE LABEL.PRINCIPAL DISPLAY PANEL"/>'
        f'<title>PRINCIPAL DISPLAY PANEL: {xml_inline(p["name"])}</title><text>'
        + "".join(f"<paragraph>{xml_inline(l)}</paragraph>" for l in product["bottle_label_text"][p["id"]])
        + f'</text><effectiveTime value="{eff}"/></section></component>'
        for p in pkgs]
    title = ("These highlights do not include all the information needed to use QUORVANTA safely and effectively. "
             "See full prescribing information for QUORVANTA.<br/>"
             "QUORVANTA (soriximel tavorate) delayed-release capsules, for oral use<br/>"
             "Initial U.S. Approval: 2024<br/>"
             "FICTITIOUS PRESCRIBING INFORMATION. Everything in this document is invented.")
    doc = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        "<!-- FICTITIOUS. Everything in this document is invented: QUORVANTA, soriximel tavorate, Brennick syndrome and "
        "Arden Quay Biosciences do not exist, and the document contains no medical information. Generated from "
        "label/label.md and product/product-identifiers.json by scripts/render.py; do not edit by hand. "
        "Ingredient codes and the labeler id use a pack-local OID because an invented product has no UNII and no DUNS. -->\n"
        '<document xmlns="urn:hl7-org:v3">'
        f'<id root="{gid("document-v" + version.group(1) + "." + version.group(2))}"/>'
        f'<code code="34391-3" codeSystem="{LOINC}" displayName="HUMAN PRESCRIPTION DRUG LABEL"/>'
        f"<title>{title}</title>"
        f'<effectiveTime value="{eff}"/><setId root="{gid("set")}"/><versionNumber value="{version.group(1)}"/>'
        f'<author><time/><assignedEntity><representedOrganization><id extension="AQB" root="{PACK_OID}"/>'
        f"<name>{pr['labeler']}</name></representedOrganization></assignedEntity></author>"
        "<component><structuredBody>" + product_section + "".join(body) + "".join(panels) +
        "</structuredBody></component></document>\n")
    return doc


def render_spl():
    path = SRC / "label/label-spl.xml"
    path.write_text(build_spl())
    print(f"wrote {path.relative_to(SRC.parent)}")


if __name__ == "__main__":
    render_program_terms()
    render_product_identifiers()
    render_formulary_fhir()
    render_spl()
