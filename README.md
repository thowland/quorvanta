<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/quorvanta-identity-package/logo-lockup-reverse.png">
    <img src="assets/quorvanta-identity-package/logo-lockup.png" width="480" alt="Quorvanta logo: an open circular Q in deep teal with an apricot diagonal tail, beside the Quorvanta wordmark and the generic name soriximel tavorate">
  </picture>
</p>

# QUORVANTA: a synthetic therapy for testing pharma commercial systems

> Everything here is invented. There is no QUORVANTA, no soriximel tavorate, no Brennick syndrome and no Arden Quay Biosciences, and none of the studies, figures, people, plans, pharmacies or patients exist. The pack contains no medical information and must not be used for any clinical purpose.

This repository holds a complete, internally consistent fictional product. It has an invented drug for an invented disease, marketed by an invented company, together with the regulatory, promotional, medical, access, patient-support, payer, supply-chain, safety and field-force material that would surround a real specialty launch. It exists so that software touching that material can be built and tested without using a real product.

## Why a fictional product is useful

Most of the systems a pharmaceutical company runs around a commercial product are hard to test honestly. The difficulty comes from the data they depend on.

- **Real product content carries obligations.** Labels, claims, promotional pieces and medical information responses have to go through medical, legal and regulatory review (MLR) before anyone outside the company sees them. Test data built from real content therefore inherits that review burden, and a test that exposes a guardrail failure against real content can itself become a reportable problem.
- **Real patient and prescriber data is off limits.** Patient data is protected under HIPAA, and prescriber data is licensed. A support-program or CRM test built on either carries privacy and contractual risk that no test environment should need.
- **Public synthetic data covers single functions.** Synthetic health records and claims files exist, as do conformance fixtures for standards such as FHIR and EPCIS. Each covers one function, with real drug codes and no product behind it. Nothing public follows one product from its label, through the claims and materials built on that label, into the support program, the payer transactions and the supply chain.

The last point is the one that matters most for testing. Commercial systems tend to fail at the joins between these pieces. A chatbot paraphrases an approved claim until it no longer says what the label says. A patient-support assistant answers a Medicare patient with copay-program language that was written for the commercially insured and does not apply to them. A test bed can only exercise those failures if the pieces agree with each other exactly, so that a wrong answer is objectively wrong. This pack is built so that they do.

## What is in the pack

The foundation is a fictitious prescribing information document (the label), written in the standard US structure and sections. Everything else is derived from it, and the numbers agree everywhere they appear. The layers built on it are:

| Area | What it contains |
| --- | --- |
| Claims and references | 105 claims with approved wording, each citing numbered findings in 28 fictitious references, with rules for which claims must travel together and which safety summary must accompany efficacy |
| Promotional and patient materials | A detail aid, a dosing card and an Important Safety Information block annotated claim by claim, plus direct-to-consumer claims mapped back to the HCP claims they derive from |
| Medical information | 18 standard response documents covering the questions the label leaves unanswered by design |
| Patient support | Program terms for the QuorvantaConnect hub, approved responses, letters, call scripts, an IVR flow and 29 synthetic case records with benefits, prior authorization, copay, bridge and foundation history |
| Payer | Plans, formularies (also as FHIR resources), coverage records and 223 claims, benefit checks, prior authorizations and appeals that reproduce every case's history |
| Supply chain | Serial-level EPCIS (GS1's standard for supply-chain events) history, Drug Supply Chain Security Act (DSCSA) transaction data, and pharmacy dispense and inventory feeds that reconcile with the events and with the cases |
| Safety | Drug Safety conventions and 22 adverse event reports arriving through every company channel |
| Field force | Territories, representatives, prescribers, approved emails and a call log checked against field compliance rules |
| Label as SPL | The label rendered as HL7 Structured Product Labeling XML, the format FDA receives |
| Generated population | Offices, HCPs, office staff, patients, labs and monitoring lab results at volume, for CRM, master-data and load testing |

`sources/README.md` is the detailed reference, covering each file, the cast, the claim schema, the timeline and the test patterns built into the data.

## How the testing works

The pack includes labelled test material, which is what separates it from sample data. There are questions an HCP might ask a chatbot, with the claims a correct answer must use. There are multi-turn patient-support conversations with the expected handling at each turn, including when identity verification must happen before any case detail is disclosed. There are also adverse event reports, each with the correct intake assessment.

Alongside these are sets of candidate answers labelled pass or fail. Each failing answer names the faults that make it fail, drawn from a taxonomy of 51 fault types. The faults describe the ways fluent output goes wrong in regulated settings:
- attributing a predecessor drug's trial result to the new product;
- dropping the comparator from a relative risk figure;
- filling a silence in the label with plausible advice;
- predicting a prior authorization outcome;
- starting a safety reporting clock at the wrong receipt.

A system under test can be scored against the expected answers, and a judge model can be calibrated against the labelled ones.

The data also contains traps, planted on purpose. They are documented, and they must not be fixed:
- a withdrawn claim;
- references that are not approved for promotional use;
- a figure that appears only in a press release;
- label silences on topics such as missed doses and pediatric use;
- a lot number that was never manufactured;
- a representative who forwarded an adverse event late.

Each gives a test something to catch.

## Who might use it

The pack was first built to test a guardrailed HCP chatbot and a patient-services assistant. The same material serves any team building or buying software in this space. A few examples:

- **AI assistants.** Test the model's behaviour directly, since every correct answer is verbatim approved text that can be checked mechanically.
- **Claims and promotional review tools.** Test claim substantiation and fair-balance checks against a library whose support is fully traceable.
- **Hub and access platforms.** Exercise benefits verification, prior authorization, copay and bridge logic against cases whose arithmetic is known to be right.
- **Safety systems.** Test adverse event intake and case processing against reports whose seriousness, expectedness and due dates are already worked out.
- **Commercial data and supply-chain teams.** Load prescriber, payer, dispense, inventory and serialization data that joins up across files, with planted data-quality problems tagged for scoring.
- **Vendor evaluations and demonstrations.** Show a system working end to end without an NDA (non-disclosure agreement) around the data.

## Visual identity

The product has a visual identity for use in demonstrations, interface mock-ups and training material. A plausible brand keeps reviewers' attention on the behaviour being shown, where placeholder styling tends to draw comments that have nothing to do with the system under test. The mark is an open circular Q in deep teal crossed by an apricot diagonal, set beside the wordmark with the generic name beneath it, on an ivory ground.

<p align="center">
  <img src="assets/quorvanta-identity-package/identity-board.png" width="860" alt="Quorvanta identity board: the logo lockup, the standalone Q symbol, a reversed logo on deep teal, the five-colour palette, and mock-ups of a carton, a brand card reading 'A little more possibility.' and a poster, over the footer 'An imaginary therapy for an imaginary condition.'">
</p>

`assets/quorvanta-identity-package/` holds the logo in a light version and a reverse version for dark backgrounds, the identity board, the brand guide and the prompts used to generate the images. The images are generated raster concept art, so small lettering and mock-up copy can vary between them. Where they disagree, the brand guide's spelling, colour values and copy are authoritative; the board, for example, labels ink as #243633, where the guide gives #243638. The logo should be redrawn as vector artwork before any print use. The guide's copy rules match the pack's own: the brand line is "A little more possibility.", and no identity material may carry clinical statistics or therapeutic promises, which can come only from the approved claims.

## Getting started

The pack is plain JSON, Markdown and XML under `sources/`, with Python tooling under `scripts/`. It needs Python 3; only the population generator needs a third-party library.

```bash
git clone <this repository> && cd <repository>
git config core.hooksPath scripts/git-hooks      # run the validator before every commit
python3 scripts/validate.py                      # check every cross-reference, figure and fiction marker
```

The general approach is:

1. **Choose the layer.** Pick the part of the pack that matches the system you are testing, and read its section in `sources/README.md`.
2. **Load the content.** Give your system the content it would have in production: the claims library and references for an HCP assistant, for example, or the program terms and approved responses for a patient-services assistant.
3. **Run the scenarios.** Put the matching inbound scenarios or conversations through your system, and score its output against the expected answers in `sources/test-design/`.
4. **Calibrate any judge.** If you use a judge model, calibrate it against the labelled pass and fail sets before trusting its scores.

Keep `sources/test-design/` out of anything a generator or judge model can see. It holds the answer keys, and a model that has read them is no longer being tested.

To generate a larger population, install the pinned dependency and run the generator. It is reproducible from its seed and can build one entity type at a time:

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
