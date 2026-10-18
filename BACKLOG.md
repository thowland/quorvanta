# Backlog

Ideas for extending the QUORVANTA pack. Nothing here is part of the dataset. Items are roughly in the order they would pay off, and most extend a thread that already exists, so the validator can check the new data against it.

## Generated population: new entity types

Each of these is one module in `scripts/population/entities/`. The validator checks them from each file's header.

| Item | What it adds | Notes |
| --- | --- | --- |
| Market prescription volume | Weekly new and total prescriptions by prescriber for QUORVANTA and the six fictional competitors, as volumes only. | Competitor names may appear only in `landscape/` and `test-design/`; this needs a decision on where the file lives. |
| Payers at volume | More employers and plans, and formulary positions over time. | Must stay consistent with `payer/plans.json`. |

## Scenarios built on existing data

- **Periodic safety report.** Aggregate the adverse event intake cases into a periodic report, and render individual cases on the public FDA MedWatch 3500A fields.
- **Outreach scenarios.** The second phase of the engagement work in `engagement/`:
  - an EF-* fault family for outreach (texting without consent or after STOP, a never-start text after the first fill, the copay text to a government-insured patient, a missed side-effect reply, and so on), each with a failing example;
  - labeled inbound text replies, including side-effect mentions that must be forwarded to Drug Safety the same day and linked into `ae-intake.json`, medical questions, and replies from someone other than the patient;
  - labeled campaign-audience and next-best-action decisions for a set of patients, with the expected suppressions.

## Documents

Filled benefits letters and Start Forms, plan approval and denial letters, appeal letters, Foundation decisions and fax cover sheets, some made to look scanned or faxed, would support document-AI and OCR testing, where almost no public pharma data exists. Committing the PDFs would bloat the repository, so the design commits only a JSON manifest listing each document with its template, source record and the fields an extraction tool should return. A script renders the PDFs locally from the manifest into an ignored folder, which keeps the repository small and the expected fields under validation.

## Master data management

The population already carries master-data problems with an answer key: duplicate HCPs (same NPI, name variant), moved and deactivated prescribers, retired prescribers still targeted, duplicate and closed offices, departed and multi-office staff, and patients who are duplicates or share a name, or a name and date of birth. A matching or cleansing tool can be scored against those flags. What is missing is the MDM layer itself:

- **Several sources per person.** Each HCP or patient comes from one generated file. Real MDM reconciles the same person arriving from several systems, each with its own ids and its own variations. For HCPs that would be the CRM, the Start Form's prescriber section, the 867 dispense feed's prescriber NPI, the email platform and portal registrations; for patients, the hub, the specialty pharmacy and the texting platform.
- **Golden records and crosswalks.** A master file mapping every source record to its master id, kept in `test-design/` as the answer key for match-and-merge.
- **Survivorship rules.** A rules file, in the style of `engagement/campaign-rules.json`, saying which source wins for address, phone, specialty and consent and how conflicts are settled, so the validator can recompute every golden record.
- **The core cast inside the population.** The four core case managers are on the generated staff roster, and two generated patients are deliberate namesakes of hub-case patients, but the 30 core prescribers and the hub cases themselves still never appear in the generated files, so nothing yet has to resolve a hub case against a population patient.
- **Identity in the outreach data.** Texts are keyed on the population patient id. Shared household phone numbers and a reassigned number, where consent belongs to the previous owner, would give consent resolution something to catch.

The work is roughly the size of the engagement layer: source feeds with realistic variation (nicknames, suffixes, address formats, stale specialties, phone formats), the master file and crosswalk, the survivorship rules and their validator checks, and the outreach tie-ins.

## Complete patient journeys

Turn some generated patients into full journeys: enrollment, benefits check, prior authorization, shipments, claims, EPCIS and 867 records, then persistence and discontinuation. Discontinuation reasons would match the label's rates. This is the largest item, because every generated patient then has to pass the payer and channel checks. `scripts/build_channel.py` and the payer data would need to accept generated patients as well as the hand-built cases.

## Deferred on purpose

- **Pricing and gross-to-net.** List price, rebates, chargebacks, Medicaid rebates and 340B. The pack has no approved price (PGAP-09 in `sources/test-design/ps-known-gaps.json`), so adding one reverses a design decision.
- **Other languages and markets.** The pack is US English; the only Spanish-language hub case is QC-26-00114 in `sources/test-design/ps-cases.json`, though the outreach texts and some generated patients are in Spanish.
- **Free-text corpora.** Contact-center transcripts, community posts and market-research verbatims. They would need LLM generation, labels, and the same fiction and denylist checks as everything else.
