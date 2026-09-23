#!/usr/bin/env python3
"""Build the channel and serialization data from the case records.

Run from anywhere:  python3 scripts/build_channel.py

Writes sources/channel/{trading-partners,shipments,epcis-events,dispense-867,
inventory-852}.json. Every case shipment in the window becomes a dispense;
anonymous patients add the rest of each pharmacy's volume from a fixed seed,
so the output is the same on every run. Re-run after changing case shipments,
payer claims or the lot register, then run scripts/validate.py.
"""

import hashlib
import json
import random
from datetime import date, timedelta
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "sources"
START, END = date(2026, 7, 1), date(2026, 9, 22)
rng = random.Random(20260922)


def load(rel):
    return json.loads((SRC / rel).read_text())


def check_digit(body):
    total = sum(int(d) * (3 if i % 2 == 0 else 1) for i, d in enumerate(reversed(body)))
    return str((10 - total % 10) % 10)


def gln(prefix, ref):
    body = prefix + ref
    return body + check_digit(body)


def sgln(prefix, ref):
    return f"urn:epc:id:sgln:{prefix}.{ref}.0"


def pgln(prefix, ref):
    return f"urn:epc:id:pgln:{prefix}.{ref}"


product = load("product/product-identifiers.json")
packages = {p["id"]: p for p in product["packages"]}
lots = {l["lot"]: l for l in product["lots"]}
cases = load("test-design/ps-cases.json")["cases"]
network = {p["id"]: p for p in load("access/specialty-pharmacy-network.json")["pharmacies"]}
hcps = load("crm/field-force.json")["hcps"]
hcp_by_id = {h["id"]: h for h in hcps}
tx = load("payer/transactions.json")
coverages = {c["id"]: c for c in tx["coverages"]}
plans = {p["id"]: p for p in load("payer/plans.json")["plans"]}

AQ = "0300000"            # Arden Quay: the GS1 company prefix inside the product GTINs
ITEM_REF = {"PKG-120": "019001", "PKG-STARTER": "019002"}  # indicator digit + item reference

parties = [
    {"id": "TP-AQB", "name": "Arden Quay Biosciences, Inc.", "role": "manufacturer_of_record", "prefix": AQ,
     "locations": [{"id": "LOC-AQB-HQ", "name": "Headquarters, Waltham, MA", "ref": "00001", "tz": "-04:00"}]},
    {"id": "TP-PKG", "name": "Hollins Vale Packaging (contract packager)", "role": "contract_packager", "prefix": "0200010",
     "locations": [{"id": "LOC-PKG", "name": "Packaging site, Greenfield, IN", "ref": "00001", "tz": "-04:00"}]},
    {"id": "TP-3PL", "name": "Pellwood Logistics (third-party logistics provider)", "role": "3pl", "prefix": "0200011",
     "locations": [{"id": "LOC-3PL", "name": "Distribution center, Memphis, TN", "ref": "00001", "tz": "-05:00"}]},
]
SP_TZ = {"SP-01": "-04:00", "SP-02": "-04:00", "SP-03": "-05:00", "SP-04": "-04:00", "SP-05": "-05:00"}
for n, sp in enumerate(sorted(network), 1):
    p = network[sp]
    parties.append({"id": f"TP-{sp}", "name": p["name"], "role": "dispenser", "pharmacy_id": sp,
                    "ncpdp": p["ncpdp"].split()[0], "prefix": f"020000{n}",
                    "locations": [{"id": f"LOC-{sp}", "name": f"{p['name']} dispensing site", "ref": "00001", "tz": SP_TZ[sp]}]})
for p in parties:
    p["pgln"] = pgln(p["prefix"], "00000")
    p["gln"] = gln(p["prefix"], "00000")
    for l in p["locations"]:
        l["gln"] = gln(p["prefix"], l["ref"])
        l["sgln"] = sgln(p["prefix"], l["ref"])
party = {p["id"]: p for p in parties}
sp_party = {p["pharmacy_id"]: p for p in parties if p["role"] == "dispenser"}
loc = lambda pid: party[pid]["locations"][0]


def serial_for(lot_id, n):
    h = hashlib.sha256(f"{lot_id}:{n}".encode()).hexdigest().upper()
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    v = int(h, 16)
    out = ""
    for _ in range(12):
        v, r = divmod(v, len(alphabet))
        out += alphabet[r]
    return out


def sgtin(pkg, serial):
    return f"urn:epc:id:sgtin:{AQ}.{ITEM_REF[pkg]}.{serial}"


def lot_for(pkg, d):
    """Lot for an anonymous dispense: the one made two months before the dispense month. Case shipments keep their own lots."""
    y, m = d.year, d.month - 2
    if m < 1:
        y, m = y - 1, m + 12
    return next(l["lot"] for l in product["lots"] if l["package"] == pkg and l["manufactured"][:7] == f"{y}-{m:02d}")


# ---- dispenses ------------------------------------------------------------------
paid_pharmacy = {}
for t in tx["transactions"]:
    if t["type"] == "claim" and t["result"] == "paid" and coverages[t["coverage_id"]]["order"] == "primary":
        paid_pharmacy[(t["case_id"], t["date"])] = (t["pharmacy_id"], plans[coverages[t["coverage_id"]]["plan_id"]]["type"])

D = []            # dispenses
held = []         # bottles allocated to a patient but not yet shipped (still on hand)
for c in cases:
    seen = set()
    for s in c["shipments"]:
        d = date.fromisoformat(s["date"])
        key = (s["date"], s["package"])
        if not START <= d <= END or key in seen or s["lot"] is None:
            continue
        seen.add(key)
        if s["source"] == "plan":
            if s["status"] not in ("SHIP_SHIPPED", "SHIP_DELIVERED"):
                held.append({"pharmacy_id": c["pharmacy"]["id"], "package": s["package"], "lot": s["lot"], "date": s["date"], "case_id": c["case_id"]})
                continue
            sp, payer = paid_pharmacy[(c["case_id"], s["date"])]
        else:
            sp, payer = "SP-04", "bridge" if s["source"] == "bridge" else "foundation"
        D.append({"pharmacy_id": sp, "date": s["date"], "package": s["package"], "lot": s["lot"],
                  "hub_case_id": c["case_id"], "patient_token": None, "prescriber": c["prescriber_id"],
                  "payer_type": payer, "source": s["source"]})

ANON = {"SP-01": 30, "SP-02": 18, "SP-03": 10, "SP-04": 4, "SP-05": 4}
PAYERS = {"SP-01": ["commercial"] * 6 + ["medicare"] * 2 + ["medicaid", "tricare"],
          "SP-02": ["commercial"] * 3 + ["medicare"], "SP-03": ["commercial"],
          "SP-04": ["commercial", "foundation"], "SP-05": ["commercial"]}
prescribers = [h["id"] for h in hcps if h["specialty"] == "Neurology"]
token = 0
for sp, n in ANON.items():
    for _ in range(n):
        token += 1
        pt = f"PT-{hashlib.sha256(f'pt{token}'.encode()).hexdigest()[:8].upper()}"
        payer = rng.choice(PAYERS[sp])
        prescriber = rng.choice(prescribers)
        new = rng.random() < 0.2
        d = START + timedelta(days=rng.randrange(0, 30 if not new else 70))
        first = True
        while d <= END:
            pkg = "PKG-STARTER" if new and first else "PKG-120"
            D.append({"pharmacy_id": sp, "date": str(d), "package": pkg, "lot": lot_for(pkg, d), "hub_case_id": None,
                      "patient_token": pt, "prescriber": prescriber, "payer_type": payer,
                      "source": "pap" if payer == "foundation" else "plan"})
            first = False
            d += timedelta(days=30)

D.sort(key=lambda x: (x["pharmacy_id"], x["date"], x["hub_case_id"] or "~", x["patient_token"] or ""))

# ---- stock needed per pharmacy and lot ---------------------------------------------
need = {}
for x in D + held:
    k = (x["pharmacy_id"], x["package"], x["lot"])
    need.setdefault(k, []).append(x["date"])
BUFFER = 1
DAMAGED = ("SP-03", "PKG-120", "QV26G032")      # one bottle damaged in transit on receipt
EXPIRED = ("SP-05", "PKG-120", "QV24H009", 2)   # slow stock that expires in the window

serial_counter = {}
lot_serials = {}   # lot -> list of (serial, pharmacy)


def new_serials(lot_id, count, sp):
    out = []
    for _ in range(count):
        n = serial_counter.get(lot_id, 0) + 1
        serial_counter[lot_id] = n
        s = serial_for(lot_id, n)
        out.append(s)
        lot_serials.setdefault(lot_id, []).append((s, sp))
    return out


# Each pharmacy receives each month's lot in one shipment, four days before the lot's first dispense.
orders = {}
for (sp, pkg, lot_id), dates in sorted(need.items()):
    first = min(date.fromisoformat(d) for d in dates)
    recv = first - timedelta(days=4)
    qty = len(dates) + BUFFER + (1 if (sp, pkg, lot_id) == DAMAGED else 0)
    orders.setdefault((sp, recv), []).append({"package": pkg, "lot": lot_id, "quantity": qty})
orders.setdefault(("SP-05", date(2024, 11, 18)), []).append({"package": EXPIRED[1], "lot": EXPIRED[2], "quantity": EXPIRED[3]})

# ---- EPCIS events -----------------------------------------------------------------
E = []


def when(d, hh, tz):
    return {"eventTime": f"{d}T{hh}:00{tz}", "eventTimeZoneOffset": tz}


def bt(kind, owner_gln, ident):
    return {"type": kind, "bizTransaction": f"urn:epcglobal:cbv:bt:{owner_gln}:{ident}"}


sscc_counter = {}


def sscc(prefix):
    n = sscc_counter.get(prefix, 0) + 1
    sscc_counter[prefix] = n
    ref = f"0{n:09d}"                      # extension digit 0 + 9-digit serial reference
    digits = ref[0] + prefix + ref[1:]
    return f"urn:epc:id:sscc:{prefix}.{ref}", digits + check_digit(digits)


serials_by_line = {}
shipments = []
pkg_loc, tpl_loc = loc("TP-PKG"), loc("TP-3PL")
aq = party["TP-AQB"]
by_lot = {}
for (sp, recv), lines in sorted(orders.items(), key=lambda kv: kv[0][1]):
    for line in lines:
        line["serials"] = new_serials(line["lot"], line["quantity"], sp)
        by_lot.setdefault(line["lot"], []).append((sp, recv, line))

# Packager: commission each lot's serials, pack, ship to the 3PL, which receives and unpacks.
for lot_id, uses in sorted(by_lot.items()):
    lot = lots[lot_id]
    pkg = lot["package"]
    made = date.fromisoformat(lot["manufactured"])
    epcs = [sgtin(pkg, s) for _, _, line in uses for s in line["serials"]]
    c_day, s_day, r_day = made + timedelta(days=5), made + timedelta(days=7), made + timedelta(days=9)
    E.append({"type": "ObjectEvent", **when(c_day, "09:00", pkg_loc["tz"]), "epcList": epcs, "action": "ADD",
              "bizStep": "commissioning", "disposition": "active",
              "readPoint": {"id": pkg_loc["sgln"]}, "bizLocation": {"id": pkg_loc["sgln"]},
              "ilmd": {"cbvmda:lotNumber": lot_id, "cbvmda:itemExpirationDate": lot["expiry"]}})
    pallet, pallet_digits = sscc(party["TP-PKG"]["prefix"])
    E.append({"type": "AggregationEvent", **when(c_day, "11:00", pkg_loc["tz"]), "parentID": pallet, "childEPCs": epcs,
              "action": "ADD", "bizStep": "packing", "disposition": "in_progress",
              "readPoint": {"id": pkg_loc["sgln"]}, "bizLocation": {"id": pkg_loc["sgln"]}})
    move = f"TRF-{lot_id}"
    E.append({"type": "ObjectEvent", **when(s_day, "15:00", pkg_loc["tz"]), "epcList": [pallet], "action": "OBSERVE",
              "bizStep": "shipping", "disposition": "in_transit", "readPoint": {"id": pkg_loc["sgln"]},
              "bizTransactionList": [bt("desadv", party["TP-PKG"]["gln"], move)],
              "sourceList": [{"type": "owning_party", "source": aq["pgln"]}, {"type": "location", "source": pkg_loc["sgln"]}],
              "destinationList": [{"type": "owning_party", "destination": aq["pgln"]}, {"type": "location", "destination": tpl_loc["sgln"]}]})
    E.append({"type": "ObjectEvent", **when(r_day, "10:00", tpl_loc["tz"]), "epcList": [pallet], "action": "OBSERVE",
              "bizStep": "receiving", "disposition": "in_progress", "readPoint": {"id": tpl_loc["sgln"]}, "bizLocation": {"id": tpl_loc["sgln"]},
              "bizTransactionList": [bt("desadv", party["TP-PKG"]["gln"], move)],
              "sourceList": [{"type": "owning_party", "source": aq["pgln"]}, {"type": "location", "source": pkg_loc["sgln"]}],
              "destinationList": [{"type": "owning_party", "destination": aq["pgln"]}, {"type": "location", "destination": tpl_loc["sgln"]}]})
    E.append({"type": "AggregationEvent", **when(r_day, "10:30", tpl_loc["tz"]), "parentID": pallet, "childEPCs": epcs,
              "action": "DELETE", "bizStep": "unpacking", "disposition": "in_progress",
              "readPoint": {"id": tpl_loc["sgln"]}, "bizLocation": {"id": tpl_loc["sgln"]}})
    shipments.append({"id": f"SHP-{len(shipments) + 1:04d}", "kind": "internal_transfer", "reference": move,
                      "from": "LOC-PKG", "to": "LOC-3PL", "owner_before": "TP-AQB", "owner_after": "TP-AQB",
                      "shipped": str(s_day), "received": str(r_day), "sscc": pallet_digits,
                      "lines": [{"ndc": packages[pkg]["ndc"], "gtin": packages[pkg]["gtin"], "lot": lot_id,
                                 "expiry": lot["expiry"], "quantity": len(epcs)}]})

# 3PL to pharmacy: one shipment per order, one case (SSCC) per package line.
STATEMENT = ("The seller attests that it is authorized, received the product from an authorized party, and has complied with the applicable transaction information, history and statement requirements. Fictitious; no product or party here exists.")
for (sp, recv), lines in sorted(orders.items(), key=lambda kv: (kv[0][1], kv[0][0])):
    sp_p, sp_l = sp_party[sp], loc(sp_party[sp]["id"])
    ship = recv - timedelta(days=1)
    po = f"PO-{sp.replace('-', '')}-{ship:%y%m%d}"
    inv = f"INV-{sp.replace('-', '')}-{ship:%y%m%d}"
    cases_out = []
    for line in lines:
        epcs = [sgtin(line["package"], s) for s in line["serials"]]
        box, box_digits = sscc(party["TP-3PL"]["prefix"])
        cases_out.append((box, box_digits, line, epcs))
        E.append({"type": "AggregationEvent", **when(ship, "11:00", tpl_loc["tz"]), "parentID": box, "childEPCs": epcs,
                  "action": "ADD", "bizStep": "packing", "disposition": "in_progress",
                  "readPoint": {"id": tpl_loc["sgln"]}, "bizLocation": {"id": tpl_loc["sgln"]}})
    txns = [bt("po", sp_p["gln"], po), bt("inv", aq["gln"], inv)]
    src = [{"type": "owning_party", "source": aq["pgln"]}, {"type": "location", "source": tpl_loc["sgln"]}]
    dst = [{"type": "owning_party", "destination": sp_p["pgln"]}, {"type": "location", "destination": sp_l["sgln"]}]
    E.append({"type": "ObjectEvent", **when(ship, "15:00", tpl_loc["tz"]), "epcList": [c[0] for c in cases_out], "action": "OBSERVE",
              "bizStep": "shipping", "disposition": "in_transit", "readPoint": {"id": tpl_loc["sgln"]},
              "bizTransactionList": txns, "sourceList": src, "destinationList": dst})
    E.append({"type": "ObjectEvent", **when(recv, "10:00", sp_l["tz"]), "epcList": [c[0] for c in cases_out], "action": "OBSERVE",
              "bizStep": "receiving", "disposition": "in_progress", "readPoint": {"id": sp_l["sgln"]}, "bizLocation": {"id": sp_l["sgln"]},
              "bizTransactionList": txns, "sourceList": src, "destinationList": dst})
    for box, _, line, epcs in cases_out:
        E.append({"type": "AggregationEvent", **when(recv, "10:30", sp_l["tz"]), "parentID": box, "childEPCs": epcs,
                  "action": "DELETE", "bizStep": "unpacking", "disposition": "in_progress",
                  "readPoint": {"id": sp_l["sgln"]}, "bizLocation": {"id": sp_l["sgln"]}})
        if (sp, line["package"], line["lot"]) == DAMAGED:
            bad = epcs[-1]
            E.append({"type": "ObjectEvent", **when(recv, "10:45", sp_l["tz"]), "epcList": [bad], "action": "OBSERVE",
                      "bizStep": "inspecting", "disposition": "damaged", "readPoint": {"id": sp_l["sgln"]}, "bizLocation": {"id": sp_l["sgln"]}})
            E.append({"type": "ObjectEvent", **when(recv + timedelta(days=7), "14:00", sp_l["tz"]), "epcList": [bad], "action": "DELETE",
                      "bizStep": "destroying", "disposition": "destroyed", "readPoint": {"id": sp_l["sgln"]}, "bizLocation": {"id": sp_l["sgln"]}})
        if (sp, line["package"], line["lot"]) == EXPIRED[:3]:
            exp = date.fromisoformat(lots[line["lot"]]["expiry"]) + timedelta(days=1)
            E.append({"type": "ObjectEvent", **when(exp, "08:30", sp_l["tz"]), "epcList": epcs, "action": "OBSERVE",
                      "bizStep": "holding", "disposition": "expired", "readPoint": {"id": sp_l["sgln"]}, "bizLocation": {"id": sp_l["sgln"]}})
            E.append({"type": "ObjectEvent", **when(date(2026, 9, 15), "14:00", sp_l["tz"]), "epcList": epcs, "action": "DELETE",
                      "bizStep": "destroying", "disposition": "destroyed", "readPoint": {"id": sp_l["sgln"]}, "bizLocation": {"id": sp_l["sgln"]}})
    shipments.append({
        "id": f"SHP-{len(shipments) + 1:04d}", "kind": "sale", "reference": po, "invoice": inv,
        "from": "LOC-3PL", "to": f"LOC-{sp}", "owner_before": "TP-AQB", "owner_after": f"TP-{sp}",
        "shipped": str(ship), "received": str(recv),
        "lines": [{"sscc": d, "ndc": packages[l["package"]]["ndc"], "gtin": packages[l["package"]]["gtin"], "lot": l["lot"],
                   "expiry": lots[l["lot"]]["expiry"], "quantity": l["quantity"]} for _, d, l, _ in cases_out],
        "dscsa": {
            "transaction_information": {
                "product": "QUORVANTA (soriximel tavorate) delayed-release capsules, 190 mg",
                "seller": {"name": aq["name"], "gln": aq["gln"]}, "buyer": {"name": sp_p["name"], "gln": sp_p["gln"]},
                "transaction_date": str(ship), "shipment_date": str(ship)},
            "transaction_statement": STATEMENT,
            "transaction_history": "Direct purchase from the manufacturer of record; no intermediate owners.",
        },
    })

# Dispensing: each dispense takes the next serial of its lot held at that pharmacy.
stock = {}
for (sp, recv), lines in orders.items():
    for line in lines:
        bad = 1 if (sp, line["package"], line["lot"]) == DAMAGED else 0
        good = line["serials"][:-1] if bad else line["serials"]
        if (sp, line["package"], line["lot"]) != EXPIRED[:3]:
            stock.setdefault((sp, line["lot"]), []).extend(good)
records = []
for n, x in enumerate(sorted(D, key=lambda x: (x["date"], x["pharmacy_id"])), 1):
    s = stock[(x["pharmacy_id"], x["lot"])].pop(0)
    sp_l = loc(sp_party[x["pharmacy_id"]]["id"])
    d = x["date"]
    epc = sgtin(x["package"], s)
    E.append({"type": "ObjectEvent", **when(d, "14:00", sp_l["tz"]), "epcList": [epc], "action": "OBSERVE",
              "bizStep": "dispensing", "disposition": "dispensed", "readPoint": {"id": sp_l["sgln"]}, "bizLocation": {"id": sp_l["sgln"]}})
    p = hcp_by_id[x["prescriber"]]
    new = x["package"] == "PKG-STARTER"
    records.append({
        "record_id": f"867-{n:05d}", "pharmacy_id": x["pharmacy_id"], "ncpdp": network[x["pharmacy_id"]]["ncpdp"].split()[0],
        "dispense_date": d, "ndc": packages[x["package"]]["ndc"], "quantity": 1, "unit": "bottle",
        "capsules": packages[x["package"]]["capsules"], "days_supply": 30, "lot": x["lot"], "serial": s,
        "fill_type": "new" if new else "refill", "patient_token": x["patient_token"], "hub_case_id": x["hub_case_id"],
        "prescriber_npi": p["npi"], "ship_to_state": p["state"] if x["hub_case_id"] is None else next(c for c in cases if c["case_id"] == x["hub_case_id"])["patient"]["state"],
        "payer_type": x["payer_type"], "source": x["source"],
    })

allocations = []
for h in held:
    s = stock[(h["pharmacy_id"], h["lot"])].pop(0)
    allocations.append({**h, "serial": s, "note": "Allocated to the patient's delayed shipment; still on hand at the pharmacy."})


E.sort(key=lambda e: (e["eventTime"][:10], e["eventTime"][11:16]))

# ---- 852 inventory -----------------------------------------------------------------
periods = [(date(2026, 7, 1), date(2026, 7, 31)), (date(2026, 8, 1), date(2026, 8, 31)), (date(2026, 9, 1), END)]
where = {}      # serial epc -> (pharmacy, date in, date out, reason out)
for e in E:
    day = e["eventTime"][:10]
    if e["type"] == "AggregationEvent" and e["bizStep"] == "unpacking":
        spid = next((sp for sp, pp in sp_party.items() if loc(pp["id"])["sgln"] == e["bizLocation"]["id"]), None)
        if spid:
            for c in e["childEPCs"]:
                where[c] = [spid, day, None, None]
    if e["type"] == "ObjectEvent" and e["bizStep"] in ("dispensing", "destroying"):
        for c in e["epcList"]:
            where[c][2], where[c][3] = day, e["bizStep"]
reports = []
for sp in sorted(sp_party):
    for pid, pkg in packages.items():
        mine = {k: v for k, v in where.items() if v[0] == sp and f".{ITEM_REF[pid]}." in k}
        for a, b in periods:
            a_s, b_s = str(a), str(b)
            on = lambda day: sum(1 for v in mine.values() if v[1] < day and (v[2] is None or v[2] >= day))
            opening = on(a_s)
            received = sum(1 for v in mine.values() if a_s <= v[1] <= b_s)
            dispensed = sum(1 for v in mine.values() if v[3] == "dispensing" and a_s <= v[2] <= b_s)
            destroyed = [v for v in mine.values() if v[3] == "destroying" and a_s <= v[2] <= b_s]
            closing = opening + received - dispensed - len(destroyed)
            end_day = str(b + timedelta(days=1))
            lots_on = {}
            for k, v in mine.items():
                if v[1] < end_day and (v[2] is None or v[2] >= end_day):
                    lot_id = next(l for l, ss in lot_serials.items() if k.rsplit(".", 1)[1] in {s for s, _ in ss})
                    lots_on[lot_id] = lots_on.get(lot_id, 0) + 1
            if not (opening or received or dispensed or destroyed):
                continue
            adj = []
            if destroyed:
                reason = "expired" if pid == "PKG-120" and sp == EXPIRED[0] else "damaged"
                adj.append({"reason": reason, "quantity": -len(destroyed)})
            reports.append({"pharmacy_id": sp, "ncpdp": network[sp]["ncpdp"].split()[0], "gln": sp_party[sp]["gln"],
                            "ndc": pkg["ndc"], "period_start": a_s, "period_end": b_s, "opening_on_hand": opening,
                            "received": received, "dispensed": dispensed, "adjustments": adj, "closing_on_hand": closing,
                            "lots_on_hand": [{"lot": k, "quantity": v} for k, v in sorted(lots_on.items())]})
            assert closing == sum(lots_on.values()), (sp, pid, a_s)

# ---- write -------------------------------------------------------------------------
NOTE = "FICTITIOUS. {}"
out = SRC / "channel"
out.mkdir(exist_ok=True)
docs = {
    "trading-partners.json": {
        "_notice": NOTE.format("Trading partners and locations in a supply chain that does not exist. The manufacturer's GS1 company prefix 0300000 is the one inside the product GTINs (03 plus the unassigned NDC labeler 00000). Every other party uses a prefix from 0200001 to 0200011, in the GS1 range reserved for restricted circulation, which is never issued as a company prefix."),
        "partners_version": "1.0.0", "as_of": str(END),
        "usage": "GLNs are 13 digits with a GS1 check digit; sgln and pgln are their EPC URIs. Arden Quay owns the product until a network pharmacy receives it; the packager and the 3PL never own it. Generated by scripts/build_channel.py.",
        "epc_formats": {
            "sgtin": f"urn:epc:id:sgtin:{AQ}.<indicator and item reference>.<serial>; item reference 019001 for PKG-120 and 019002 for PKG-STARTER",
            "sscc": "18 digits: extension digit, company prefix, serial reference, check digit; EPC urn:epc:id:sscc:<prefix>.<extension and serial reference>",
            "serial": product["formats"]["serial"],
        },
        "parties": parties,
    },
    "shipments.json": {
        "_notice": NOTE.format("Product movements and DSCSA transaction data for a product that does not exist, between parties that do not exist. There are no prices."),
        "shipments_version": "1.0.0", "as_of": str(END),
        "usage": "internal_transfer moves product from the packager to the 3PL without a change of owner; sale moves it from the 3PL to a pharmacy, which becomes the owner on receipt and gets DSCSA transaction information, history and statement. Line quantities are bottles. Every serial in a line appears in the matching EPCIS packing event. Generated by scripts/build_channel.py.",
        "shipments": shipments,
    },
    "epcis-events.json": {
        "_notice": NOTE.format("EPCIS events for serial numbers of a product that does not exist. Unwrap the document field before loading it into an EPCIS repository."),
        "events_version": "1.0.0", "as_of": str(END),
        "usage": "The full serial-level history of every bottle that was at a network pharmacy between 2026-07-01 and 2026-09-22: commissioning at the packager (with lot and expiry), packing, shipping and receiving to the 3PL, packing and shipping to a pharmacy, receiving and unpacking there, then dispensing, damage or expiry and destruction. Generated by scripts/build_channel.py.",
        "document": {"@context": ["https://ref.gs1.org/standards/epcis/2.0.0/epcis-context.jsonld"],
                     "type": "EPCISDocument", "schemaVersion": "2.0", "creationDate": f"{END}T18:00:00-04:00",
                     "epcisBody": {"eventList": E}},
    },
    "dispense-867.json": {
        "_notice": NOTE.format("Pharmacy dispense (sales-out) data for patients and a product that do not exist. Patient tokens and hub case ids are synthetic."),
        "feed_version": "1.0.0", "period": {"start": str(START), "end": str(END)},
        "usage": "One record per bottle dispensed by a network pharmacy, the data a limited-distribution manufacturer receives in an 867 product transfer and resale report. Records with a hub_case_id are the case shipments in test-design/ps-cases.json; the rest are anonymous patients. The layout is the pack's own and carries no X12 syntax. Generated by scripts/build_channel.py.",
        "held_allocations": allocations,
        "records": records,
    },
    "inventory-852.json": {
        "_notice": NOTE.format("Pharmacy inventory reports for a product that does not exist."),
        "feed_version": "1.0.0", "period": {"start": str(START), "end": str(END)},
        "usage": "Monthly inventory by pharmacy and NDC, the data carried in an 852 product activity report: opening_on_hand + received - dispensed + adjustments = closing_on_hand, in bottles, and lots_on_hand totals closing_on_hand. Every figure can be recomputed from epcis-events.json. September runs to the pack's as_of date. The layout is the pack's own and carries no X12 syntax. Generated by scripts/build_channel.py.",
        "reports": reports,
    },
}
for name, doc in docs.items():
    (out / name).write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n")
    print(f"wrote sources/channel/{name}")
print(len(E), "events;", len(records), "dispenses;", len(shipments), "shipments;", len(reports), "852 rows;", sum(serial_counter.values()), "serials")
