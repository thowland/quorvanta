# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

This is not software. It is a synthetic test dataset: an invented drug (QUORVANTA, soriximel tavorate), an invented disease (Brennick syndrome), an invented company (Arden Quay Biosciences), and the regulatory, promotional, medical, access, patient and press documents around them. The data is used to test a guardrailed HCP chatbot and a patient-services assistant for the support program (QuorvantaConnect) without touching a real product. It also serves as a test bed for adverse event intake, payer and benefits processing, and CRM and field-force compliance. The pack is being prepared for public release on GitHub under CC BY-SA 4.0 (content in `sources/` and the identity package in `assets/`) and GPL-3.0 (scripts). There is no build step; the tooling is in `scripts/` (see Commands). `sources/README.md` is the authoritative description of the pack, covering files, cast, test patterns, claim schema, timeline and fault types.

## Non-negotiable invariants

- **Nothing real.** No real drug, brand, company, product or software vendor names anywhere, including in README prose about where the pack came from. The pack was originally modeled on a real label; all traces of that were deliberately removed and must not come back.
- **Fiction markers:**
  - Phone numbers use the reserved `1-800-555-01xx` range; synthetic patients use `(xxx) 555-01xx`.
  - Web and email domains use `.example`.
  - DOIs use the `10.5555` prefix.
  - NCPDP ids use a `99-` prefix.
  - NDCs use the unassigned labeler `00000`; GTIN-14 check digits must be correct.
  - Prescriber NPIs are 10 digits beginning with `9`, with a correct check digit (Luhn over the `80840` prefix). The core cast uses `90`, the generated population `91`.
  - Lab CLIA numbers are `99D` plus seven digits.
  - Pharmacy BINs begin with `000`.
  - Every local phone number, `(xxx) nnn-nnnn`, is `555-01xx`.
  - GS1: the manufacturer's company prefix is `0300000`, the one inside the GTINs. Every other trading partner uses `0200001` to `0200011`, in the restricted-circulation range; GLN and SSCC check digits must be correct.
  - Event coding uses the pack's own `AET-*` terms. Never add MedDRA codes or NCPDP code values; both are licensed.
  - Every JSON file carries a top-level `_notice` field.
  - Every Markdown document opens with a "Everything here is invented" blockquote.
  - Keep all of these markers in any new file.
- **Numbers must agree everywhere.** A figure lives first in `sources/label/label.md` and reappears in claims, references, promo pieces, SRDs, patient materials and press releases. Arm sizes sum to study totals, the pooled safety population equals the two twice-daily arms, and relative reductions follow from the stated rates. When changing a number, grep every file for it.
- **Deliberate traps are features, not bugs.** Do not "fix" them:
  - the withdrawn claim `EFF-013`;
  - the three references marked `not_approved_for_promotional_use` (REF-019 to REF-021);
  - findings that support no claim (`REF-003.7`, `REF-011.7`);
  - the 6.2% GI discontinuation figure that appears only in the press release;
  - the label silences listed in `known-gaps.json`;
  - the unnamed open-label reference arm in CASTLEREAGH: never identify it with a competitor;
  - the patient-services limits in `test-design/ps-known-gaps.json`. For example, the Foundation income limit is only a percentage with no dollar table, and there is no approved price and no approved way to extend bridge supply;
  - `CALL-0029`'s late adverse event forward (declared as `CF-03`), and the other intake traps in `ae-intake.json`: hepatic failure is unlisted because label 5.5 says no case progressed to it, and lot `QS26G099` is not in the register;
  - no price anywhere in `payer/`: claims carry patient amounts only;
  - the FHIR formulary's pack-local drug code (FHIR requires RxNorm, which an invented drug cannot have), and the SPL's pack-local ingredient and labeler ids (no UNII or DUNS);
  - the channel traps: the damaged bottle at SP-03, expired lot QV24H009 destroyed at SP-05, and case QC-26-00118's allocated bottle.

## How the pieces connect

The chain of support runs **label → references → claims → materials**:

- `claims/claims-library.json`: each claim cites finding ids in `claims/references.json` (e.g. `REF-002.2`) through `reference.citations`. It may list other claims in `requires`; those must accompany it. `qualifiers.data_source` is `DMT`, `QUORVANTA` or `class`. The DMT bridging attribution is the pack's central test pattern. `rules.isi_claims` defines the safety summary that must accompany any efficacy claim.
- `promotional/promo-materials.json`: each unit lists the claim ids that support it. The three `promo-*.md` files are readable renderings of the same units and must stay in sync with the JSON.
- `patient/dtc-claims.json`: each consumer claim maps to HCP claim ids via `derives_from`.
- `test-design/known-gaps.json`: each gap names the SRD in `medical-information/srds.json` that answers it (`srd_id`, which may be null). Each SRD points back to its gap via `gap_id`. This file is the answer key. Keep it out of anything that would be fed to a generator or judge model.
- Access claims (`ACC-*`) cite REF-022 (program terms) and REF-023 (distribution notice), which mirror `access/specialty-pharmacy-network.json` and the commercial-availability press release.

The patient-services chain runs **program terms → responses → letters, scripts and statuses**:

- `patient-services/program-terms.json` holds numbered provisions (`PGM-COPAY.3`). It is the full text behind REF-022, whose `location` must carry the same version and effective date.
- `patient-services/ps-responses.json` responses cite provisions or DTC claim ids.
  - Responses with `{{placeholders}}` are `verified_only` and are filled from a case record.
  - Computed fields are `copay.remaining`, `bridge.days_remaining`, `<domain>.status_text` (taken from `case-statuses.json`) and `last_shipment`.
- `bi-letters.md`, `ivr-call-flow.md` and `agent-scripts.md` tag each line with `PSR-*`, `ps_*` fixed messages, `ESC-*`, `CMP-*` or `VER`.
- `test-design/ps-cases.json` must obey the program rules the validator encodes:
  - the copay program is for commercial insurance with no government program, capped at $16,000;
  - bridge supply is capped at 60 days, and `days_dispensed` must equal the sum of bridge shipments;
  - capsules = days × 2 for the starting dose and days × 4 for the maintenance dose;
  - bridge and Foundation product ships from SP-04;
  - plan-mandated pharmacies must be honored.
- Add a new case by editing the JSON directly and checking its arithmetic.

**Unbranded disease content** (`disease/`): `disease-facts.json` holds DIS-* facts, each citing approved findings (REF-024 to REF-028).
- Both disease pieces must be the exact approved wording of the facts they tag: the `text` field in the HCP overview, `patient_text` in the patient piece.
- Neither piece may mention the product, its ingredients, the predecessor or QuorvantaConnect (`forbidden_terms`).
- Never join a disease fact to a product claim to imply a benefit (HF-16).

**Product identifiers** (`product/product-identifiers.json`): two packages, the bottle of 120 (`PKG-120`) and the 30-day starter bottle of 92 (`PKG-STARTER`), with NDCs, GTINs, bottle label text and a lot register.
- Lots are `QV`/`QS` + 2-digit year + month letter + 3-digit sequence, and expire at the end of the 24th month after manufacture.
- Every case shipment names its package and, once shipped, its lot. The lot must exist, match the package, be made before shipping, and outlast the supply.
- A first fill is one starter bottle (28 starting-dose capsules plus 64 maintenance capsules); later fills are bottles of 120. QUORVANTA is dispensed only in the original container, so partial fills are not possible.
- The Markdown is generated: edit the JSON and run `scripts/render.py`.

**Adverse event intake** (`safety/`, `test-design/scenarios/ae-intake.json`, `ae-assessments.json`):
- `safety-reference.json` defines the event terms (listed only with label sections), seriousness criteria, special situations, day 0, the 15-day rule and the business calendar.
- Each report's `expected` assessment must follow from its own receipts and events. The validator recomputes case type, seriousness, listedness, reportability, day 0, due date and late forwarding.
- Field receipts must match the call log: the same call date, and a forward date equal to Drug Safety's receipt.

**Payer** (`payer/`): `plans.json` holds processors, formularies and plans; `transactions.json` holds coverages and transactions per case. The transactions must reproduce each case:
- one paid primary claim per plan shipment that has left the pharmacy, and none for bridge or Foundation shipments;
- copay claims follow the $16,000 cap and sum to `copay.used_ytd`;
- the last benefit check date equals `bv.completed_on`;
- the case's `pa` fields and status follow from the requests, decisions and appeals;
- prior authorization needs follow the formulary: `none`, `new_starts` (a starter bottle first, with no earlier shipment) or `all`, unless an approval is on file.
- `formulary-fhir.json` is generated: edit `plans.json` and run `scripts/render.py`.

**Field force** (`crm/`):
- Prescribers link to cases both ways (`hcps[].case_ids` and each case's `prescriber_id`).
- Every call must obey the field rules FR-01 to FR-08 or declare the breach in `deviations` as a CF-* fault; the validator recomputes the deviations.
- A passing approved email equals its template body, which is approved claim text plus the ISI claims.

**Engagement** (`engagement/`, and `refills`, `sms-messages`, `campaign-memberships`, `hcp-emails` and `portal-sessions` in `population/`):
- `campaign-rules.json` holds the consents, keywords, time zones and rules ENG-01 to ENG-13; `approved-messages.json` the only texts a patient may receive, each in English and Spanish; `campaigns.json` the step schedules.
- Texts never name QUORVANTA, the condition, a dose, a symptom or case details, and no campaign asks a patient to start, continue or restart treatment.
- The validator recomputes every due text, membership and exit from the patient, their fills and the inbound keywords, independently of `scripts/population/engagement.py`, which the generator uses. A text that breaks a rule must carry that rule's flag; change the rules or generator, never the logs.
- `case-outreach.json` is the hand-built equivalent for eight core cases, June to September 2026, with each case's opt-in state at the log start. Edit it only with its arithmetic checked by the validator.
- Free text in generated logs is always benign; side-effect replies belong in labeled scenarios.

**Channel** (`channel/`) is generated by `scripts/build_channel.py` from the cases, payer claims, lot register and CRM data. Re-run it after changing any of those.
- Every serial's EPCIS history must be well formed: commissioned once with its lot and expiry, then packed, shipped, received and unpacked, and dispensed or destroyed at most once. A bottle may not be dispensed from a lot that expires before its 30-day supply is used.
- Each 867 record matches one dispensing event. The case shipments in the window match the case records, and plan shipments match the pharmacy on the paid claim.
- Every 852 row can be recomputed from the events.
- No price appears anywhere.

**SPL** (`label/label-spl.xml`) is generated from `label/label.md` and `product/product-identifiers.json` by `scripts/render.py`. Any edit to the label must be followed by a render.

**Population** (`population/`) is generated by `scripts/generate_population.py` (Faker, pinned in `scripts/requirements.txt`, installed in `.venv`). Never edit it by hand; change the entity module and regenerate.
- One module per entity type lives in `scripts/population/entities/`. The fiction-safe name, phone, email and NPI helpers are in `scripts/population/core.py`; use them in new entities rather than raw Faker calls, because Faker's defaults produce real-looking phones, domains and names.
- The validator is driven by each file's header (`id_prefix`, `references`, `must_match`, `quality_flags`), so a new entity type needs no validator change. Keep `scripts/validate.py` standard-library only.
- Population records never carry scenarios or answer keys, and never reuse a core cast name or NPI.
- `patterns` (clinical or business situations) and `quality_flags` (data problems) are separate. The validator re-derives the lab-results patterns and eGFR from the values, so change the generator, not the output.
- Deferred ideas and release tasks live in `BACKLOG.md`.

**Competitors** (`landscape/competitors.json`) are context only, with no efficacy data. Their names may appear only in `landscape/`, `test-design/` and the README; the validator enforces this.

**Scenarios** (`test-design/scenarios/`):
- `fault-types.json` defines the fault ids (HF-* for the HCP bot, PF-* for patient services, SF-* for adverse event intake, CF-* for field records), and every fault needs at least one failing example in a labeled set.
- A passing HCP response must meet all of these:
  - contain its cited claims, disease facts and fixed messages word for word;
  - match its inbound scenario's claim set, which is already closed over `requires`;
  - have `isi_appended` set when it uses an efficacy claim.
- A passing patient-services reply must equal its fixed messages followed by its responses, filled from the case by `fill()` in `validate.py`.
- In conversations, case-specific responses may appear only after a turn where verification succeeds. Verification succeeds only if the user's turn contains the case's last name, the formatted date of birth, and the ZIP code or case number, and the caller is entitled.
- When adding scenarios, build the passing answers from the source texts rather than typing them; paraphrases fail the checks.

Real public services the fiction keeps on purpose: 911, 988, FDA MedWatch, Poison Control, Medicare, Medicaid, TRICARE, the VA, Extra Help and the Federal Poverty Guidelines. Never add a real pharmacy, insurer, PBM or charity name, including in example questions.

Several documents exist as a JSON/Markdown pair (`references`, `srds`, `start-form`, promo pieces). The JSON is canonical; update the Markdown to match. `patient-services/program-terms.md` is fully generated: edit the JSON and run `scripts/render.py`. Paths stored inside JSON files (e.g. `product.label`, `references_file`) are relative to `sources/`.

## Commands

```bash
python3 scripts/validate.py                            # all integrity checks; exits non-zero on failure
python3 scripts/validate.py --denylist ~/real-names.txt  # also reject real brand/company names
python3 scripts/render.py                              # regenerate program-terms.md, product-identifiers.md, payer/formulary-fhir.json and label/label-spl.xml
python3 scripts/build_channel.py                       # regenerate channel/ from the cases, claims, lots and CRM
.venv/bin/python scripts/generate_population.py        # regenerate population/ (needs Faker; see sources/README.md)
python3 scripts/extract_names.py                       # refresh scripts/names-to-check.csv, the invented names needing clearance
python3 scripts/namecheck.py --limit 90                # exact-phrase web search per name; needs search API credentials (see its docstring)
```

Run the validator after any edit. It checks:
- JSON parses and carries `_notice`, and every Markdown file has a fiction notice;
- citations, `requires` and `derives_from` ids resolve, and no approved claim cites a non-approved reference;
- promo and DTC materials use only approved claims, and promo unit text appears verbatim in its Markdown rendering;
- gap↔SRD links run both ways, and each JSON/Markdown pair is in sync;
- the counts in `sources/README.md` still match the data;
- phones, DOIs and domains use the fiction ranges;
- product identifiers: NDC and GTIN formats, lot format and expiry, and case shipments against the lot register and packages;
- disease pieces match their facts and stay unbranded; competitor names stay in landscape/ and test-design/;
- scenarios: ids resolve, correct answers are verbatim and complete, verification order holds, every fault type has a failing example;
- patient services: provision, response, status and tag references resolve; placeholders resolve against the cases; the case records obey the program rules; and the README's patient-services counts match;
- safety: event terms against label sections, and every intake report's expected assessment recomputed from its receipts and events;
- field force: NPIs, territories, prescriber-case links, template bodies, and each call's field rules against its declared deviations;
- channel: GLNs and prefixes, each serial's EPCIS history, 867 records against events and cases, 852 rows recomputed from events, no prices;
- population: ids, declared references and must_match fields, flag legends, 91-prefixed NPIs, .example emails, adult patients unless flagged, and plan names;
- SPL: identical to a fresh render, section codes and highlight placement, and 10-digit NDCs;
- payer: BIN range, plans and coverages, claims against shipments, copay arithmetic, benefit-check and PA history against the cases, and the FHIR bundle against `plans.json`.

The denylist file must live outside the repo, since listing real names inside the pack would defeat the purpose. The only real numbers allowed are FDA MedWatch and US Poison Control (`ALLOWED_PHONES` in the script). The only real domains allowed are the HL7 and GS1 canonical hosts that FHIR and EPCIS require (`ALLOWED_HOSTS`).

A pre-commit hook (`scripts/git-hooks/pre-commit`) runs the validator against the staged snapshot and blocks the commit on failure. It picks up a denylist from `$QUORVANTA_DENYLIST` when set. Each fresh clone must enable it once with `git config core.hooksPath scripts/git-hooks`. The main branch is `master`.

`scripts/` is for tooling that operates on the pack. Nothing under `scripts/` is part of the dataset.
