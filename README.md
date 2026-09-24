<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/quorvanta-identity-package/logo-lockup-reverse.png">
    <img src="assets/quorvanta-identity-package/logo-lockup.png" width="480" alt="Quorvanta logo: an open circular Q in deep teal with an apricot diagonal tail, beside the Quorvanta wordmark and the generic name soriximel tavorate">
  </picture>
</p>

# QUORVANTA: a synthetic therapy for building, demonstrating and testing pharma commercial systems

> Everything here is invented. There is no QUORVANTA, no soriximel tavorate, no Brennick syndrome and no Arden Quay Biosciences, and none of the studies, figures, people, plans, pharmacies or patients exist. The pack contains no medical information and must not be used for any clinical purpose.

This repository holds a complete, internally consistent fictional product: an invented drug for an invented disease, marketed by an invented company, together with the regulatory, promotional, medical, access, patient-support, payer, supply-chain, safety and field-force material that a real specialty launch would generate around it. It exists so that anyone working on the software around a commercial product has something complete and unencumbered to develop against, hand to a vendor, put on a screen in a demonstration, and test with, without a real product anywhere in the picture.

## Why a fictional product is useful

The data that pharma commercial systems run on is hard to work with anywhere outside production, for three reasons.

- **Real product content carries its review burden wherever it goes.** Labels, claims, promotional pieces and medical information responses go through medical, legal and regulatory review (MLR) before anyone outside the company sees them, and every copy of that content inherits the obligation. Loading it into a development environment, sending it through an external language model or giving it to a partner all become questions for compliance.
- **Real patient and prescriber data is off limits.** Patient data is protected under HIPAA, and prescriber data is licensed. Any system built or shown on either carries privacy and contractual risk that a development or demonstration environment should not need.
- **Public synthetic data covers single functions.** Synthetic health records and claims files exist, as do conformance fixtures for standards such as FHIR and EPCIS. Each covers one function, with real drug codes and no product behind it. Nothing public follows one product from its label, through the claims and materials built on that label, into the support program, the payer transactions and the supply chain.

Those constraints bite long before anyone writes a test. Developers end up building against stubs and hand-typed fixtures that do not join up, so integration problems surface late, when the real data finally arrives. Vendor evaluations stall on data-sharing agreements, or go ahead on the vendor's own sample data, which shows their product at its best and tells you little about how it will handle yours. Demonstrations are given on redacted screens or placeholder content, and the reviewers spend the meeting asking about the gaps instead of the system.

Quorvanta is my answer to that. Because nothing in it is real, it can go into a public repository, a vendor sandbox, a continuous integration pipeline or an external model without an agreement or a review, and because the pieces agree with each other exactly, a system built or shown on it behaves the way it would on a real product.

## What is in the pack

The foundation is a fictitious prescribing information document (the label), written in the standard US structure and sections. Everything else is derived from it, and the numbers agree everywhere they appear. The layers built on it are:

| Area | What it contains |
| --- | --- |
| Claims and references | 105 claims with approved wording, each citing numbered findings in 28 fictitious references, with rules for which claims must travel together and which safety summary must accompany efficacy |
| Promotional and patient materials | A detail aid, a dosing card and an Important Safety Information block annotated claim by claim, plus direct-to-consumer claims mapped back to the HCP claims they derive from |
| Medical information | 18 standard response documents covering the questions the label leaves unanswered by design |
| Patient support | Program terms for the QuorvantaConnect hub, approved responses, letters, call scripts, an IVR flow and 29 synthetic case records with benefits, prior authorization, copay, bridge and foundation history |
| Payer | Plans, formularies (also as FHIR resources), coverage records and 223 claims, benefit checks, prior authorizations and appeals that reproduce every case's history |
| Supply chain | Serial-level EPCIS (GS1's standard for supply-chain events) history, Drug Supply Chain Security Act (DSCSA) transaction data, and pharmacy dispense (EDI 867) and inventory (EDI 852) feeds that reconcile with the events and with the cases |
| Safety | Drug Safety conventions and 22 adverse event reports arriving through every company channel |
| Field force | Territories, representatives, prescribers, approved emails and a call log checked against field compliance rules |
| Label as SPL | The label rendered as HL7 Structured Product Labeling XML, the format FDA receives |
| Disease and market | Unbranded disease education for HCPs and patients, a competitor landscape with no efficacy data, and press releases from topline results through approval and commercial availability |
| Generated population | Offices, HCPs, office staff, patients, labs and monitoring lab results at volume, for CRM, master-data and load testing |

`sources/README.md` is the detailed reference, covering each file, the cast, the claim schema, the timeline and the test patterns built into the data.

## Building against it

The pack is plain JSON, Markdown and XML with stable identifiers, and the records join across files the way production data does: a patient-support case names its prescriber, who appears in the field force's call log; its plan shipments have paid claims in the payer transactions; and a bottle shipped to it during the channel window can be followed by serial number back through the pharmacy's dispense feed and the EPCIS events to the lot it was made in. That makes it usable as seed data for a CRM, a hub platform, a data warehouse or a master-data service, where the joins are usually the first thing a stub gets wrong.

Where a standard format exists, the pack uses it. The formulary is published as FHIR resources, the label as SPL, the serialization history as EPCIS events and the pharmacy feeds in the shape of EDI 867 and 852 data, so parsers and integrations can be exercised without waiting on a trading partner. The few places where an invented drug cannot meet a standard (it has no RxNorm code, for instance) are documented where they occur.

For content systems, the claims library carries what a modular content or claims-management tool needs to model: approved wording, the findings that substantiate each claim, the claims that must travel together, and the safety summary that must accompany any efficacy statement. The promotional pieces are annotated claim by claim, so an authoring or assembly tool has real structure to work from.

For volume, `scripts/generate_population.py` builds offices, HCPs, office staff, patients, labs and lab results at whatever scale a CRM or load test needs. It is reproducible from its seed, can build one entity type at a time, and tags planted data-quality problems in each record so that a cleansing or matching pipeline has known errors to find.

## Demonstrating with it

A demonstration needs a story as well as data, and the pack has one. The product moves from topline results through approval to commercial availability, with press releases at each step. The patient-support cases have histories that can be walked through on screen, from enrolment and benefits verification through prior authorization and appeal, copay support and bridge supply to shipments that can be traced to a serialized bottle. Representatives have territories, call histories and approved emails, and the medical information responses answer the questions a prescriber would ask. All of it can be recorded, screenshotted and shared publicly without an NDA (non-disclosure agreement) around the data.

### Visual identity

The product has a visual identity for demonstrations, interface mock-ups and training material. A plausible brand keeps reviewers' attention on the behaviour being shown, where placeholder styling tends to draw comments that have nothing to do with the system. The mark is an open circular Q in deep teal crossed by an apricot diagonal, set beside the wordmark with the generic name beneath it, on an ivory ground.

<p align="center">
  <img src="assets/quorvanta-identity-package/identity-board.png" width="860" alt="Quorvanta identity board: the logo lockup, the standalone Q symbol, a reversed logo on deep teal, the five-colour palette, and mock-ups of a carton, a brand card reading 'A little more possibility.' and a poster, over the footer 'An imaginary therapy for an imaginary condition.'">
</p>

`assets/quorvanta-identity-package/` holds the logo in a light version and a reverse version for dark backgrounds, the identity board, the brand guide and the prompts used to generate the images. The images are generated raster concept art, so small lettering and mock-up copy can vary between them. Where they disagree, the brand guide's spelling, colour values and copy are authoritative; the board, for example, labels ink as #243633, where the guide gives #243638. The logo should be redrawn as vector artwork before any print use. The guide's copy rules match the pack's own: the brand line is "A little more possibility.", and no identity material may carry clinical statistics or therapeutic promises, which can come only from the approved claims.

## Testing with it

Commercial systems tend to fail at the joins between these pieces. A chatbot paraphrases an approved claim until it no longer says what the label says; a patient-support assistant answers a Medicare patient with copay-program language written for the commercially insured. A test can only catch those failures if the pieces agree exactly, so that a wrong answer is objectively wrong, and the pack adds labelled test material on top of that agreement.

There are questions an HCP might ask a chatbot, with the claims a correct answer must use; multi-turn patient-support conversations with the expected handling at each turn, including when identity verification must happen before any case detail is disclosed; and adverse event reports, each with the correct intake assessment. Every expected answer is drawn verbatim from approved text, so it can be checked mechanically. Alongside these are sets of candidate answers labelled pass or fail, each failing answer naming its faults from a taxonomy of 51 fault types covering the ways fluent output goes wrong in regulated settings, such as attributing a predecessor drug's trial result to the new product, dropping the comparator from a relative risk figure, filling a silence in the label with plausible advice, predicting a prior authorization outcome, or starting a safety reporting clock at the wrong receipt. A system can be scored against the expected answers, and a judge model can be calibrated against the labelled sets.

The data also contains documented traps, planted on purpose, which must not be fixed:
- a withdrawn claim;
- references that are not approved for promotional use;
- a figure that appears only in a press release;
- label silences on topics such as missed doses and pediatric use;
- a lot number that was never manufactured;
- a representative who forwarded an adverse event late.

Keep `sources/test-design/` out of anything the system under test, or a judge model, can see. It holds the answer keys, and a model that has read them is no longer being tested. With that boundary in place, the same material scores a guardrailed HCP chatbot, an agentic patient-services assistant, a claims review tool, a hub's benefits and prior authorization logic, or a safety intake workflow end to end.

## Getting started

The pack needs Python 3; only the population generator needs a third-party library.

```bash
git clone https://github.com/thowland/quorvanta.git && cd quorvanta
git config core.hooksPath scripts/git-hooks      # run the validator before every commit
python3 scripts/validate.py                      # check every cross-reference, figure and fiction marker
```

From there, pick the layer that matches the system you are working on and read its section in `sources/README.md`, then load the content that system would hold in production: the claims library and references for an HCP assistant or content tool, for example, the program terms, cases and payer transactions for a hub platform, or the field force, prescribers and population for a CRM. If you are testing, put the matching scenarios in `sources/test-design/` through the system and score its output against the expected answers, calibrating any judge model against the labelled pass and fail sets before trusting its scores.

To generate a larger population, install the pinned dependency and run the generator:

```bash
python3 -m venv .venv && .venv/bin/pip install -r scripts/requirements.txt
.venv/bin/python scripts/generate_population.py --list
.venv/bin/python scripts/generate_population.py --entity hcps --count hcps=1000
```

## Keeping it consistent

Several files are generated from others, and the validator will fail if they drift:
- the Structured Product Labeling rendering and the FHIR formulary come from `scripts/render.py`;
- the supply-chain data comes from `scripts/build_channel.py`;
- the population comes from `scripts/generate_population.py`.

When a figure changes, it changes in the label first and then everywhere it is repeated. `CLAUDE.md` records the rules that keep the pack coherent for anyone editing it with an AI coding assistant, and they apply equally to anyone editing by hand.

The fiction is also enforced mechanically:
- telephone numbers are in the reserved 555-01xx range;
- web domains end in `.example`;
- NDCs use an unassigned labeler code, and GS1 identifiers use prefixes that are never issued;
- NPIs and CLIA numbers use ranges that are never assigned;
- every file carries a notice that its contents are invented.

## Limits worth knowing

- **No medical information.** The pack imitates the structure and language of real labeling and program material closely, but its content has been through no review of any kind. It must not be read as medical information.
- **Standards conformance.** The FHIR and SPL files follow the published structures but break a few requirements on purpose. An invented drug has no RxNorm code, no UNII substance code and no DUNS number, and each exception is documented where it occurs.
- **Name clearance.** The invented names have not yet been cleared against real trademarks, companies or products. `scripts/names-to-check.csv` lists them for that work, and `BACKLOG.md` tracks it with the other release tasks.
- **Public answer keys.** Because the answer keys are public, they will eventually reach the training data of language models. Anyone relying on the pack for evaluation should keep a set of scenarios of their own that has never been published.

## Extending it

`BACKLOG.md` lists the planned additions:
- speaker programs and Open Payments reporting;
- market prescription volumes;
- a mock lot recall traced through the serialization data;
- a periodic safety report;
- filled letters and forms for document-extraction testing;
- complete patient journeys for the generated population.

New population entity types are single modules under `scripts/population/entities/`, and the validator checks them from their own file headers. Contributions should keep the validator passing and should never introduce a real drug, company, product, plan, pharmacy or person.

## Licence

The content under `sources/` and the identity package under `assets/` are licensed under Creative Commons Attribution-ShareAlike 4.0 International (CC BY-SA 4.0), and the tooling under `scripts/` under the GNU General Public License v3.0. See `LICENSE` and `LICENSES/`. LOINC codes used in the pack are covered by the notice in `LICENSE`.
