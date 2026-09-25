# Backlog

Ideas for extending the QUORVANTA pack, with open decisions and release tasks. Nothing here is part of the dataset. Items are roughly in the order they would pay off, and most extend a thread that already exists, so the validator can check the new data against it.

## Release tasks

These are needed before the repository is public.

- **Denylist.** Assemble a real-names list outside the repository and run `python3 scripts/validate.py --denylist <file>`. Set `$QUORVANTA_DENYLIST` so the pre-commit hook uses it.
- **Label decisions.** Two points need a decision (see sources/README.md, "Machine-readable label"):
  - whether to add the MedWatch line to the adverse reactions highlight;
  - whether section 16 should print 10-digit NDCs, which would also change claim SUP-004.

## Generated population: new entity types

Each of these is one module in `scripts/population/entities/`. The validator checks them from each file's header.

| Item | What it adds | Notes |
| --- | --- | --- |
| Speaker programs and Open Payments | Speakers, programs, venues, attendees, meals and honoraria, reported as federal Open Payments (Sunshine Act) data. Tests spend caps, sign-in rules, repeat attendance and state restrictions. | Promotional talks may use only approved claims and slides; attendees come from `population/hcps.json`. |
| QuorvantaConnect staff | Case managers, nurses and supervisors, with queues and schedules. | The core cases already name case managers. |
| Medical information requests at volume | Unsolicited questions from generated HCPs, each routed to the SRD that answers it, or to the fallback. | Operational metrics such as turnaround and repeat askers. |
| Market prescription volume | Weekly new and total prescriptions by prescriber for QUORVANTA and the six fictional competitors, as volumes only. | Competitor names may appear only in `landscape/` and `test-design/`; this needs a decision on where the file lives. |
| Payers at volume | More employers and plans, and formulary positions over time. | Must stay consistent with `payer/plans.json`. |

## Scenarios built on existing data

- **Mock recall.** Recall one lot. Find every pharmacy and patient that received it from `channel/epcis-events.json` and `dispense-867.json`, then add QuorvantaConnect outreach, letters and a patient-services script, with the expected answer set for the trace.
- **Periodic safety report.** Aggregate the adverse event intake cases into a periodic report, and render individual cases on the public FDA MedWatch 3500A fields.
- **Lab-driven scenarios.** Use `population/lab-results.json` patterns as triggers. Examples:
  - a nurse-line call about prolonged lymphopenia;
  - an HCP question about starting in low counts (GAP-08);
  - an adverse event report for the liver-injury signal;
  - blood-test reminders for overdue counts (PGM-NURSE.3).
- **Outreach scenarios.** The second phase of the engagement work in `engagement/`:
  - an EF-* fault family for outreach (texting without consent or after STOP, a never-start text after the first fill, the copay text to a government-insured patient, a missed side-effect reply, and so on), each with a failing example;
  - labeled inbound text replies, including side-effect mentions that must be forwarded to Drug Safety the same day and linked into `ae-intake.json`, medical questions, and replies from someone other than the patient;
  - labeled campaign-audience and next-best-action decisions for a set of patients, with the expected suppressions.
- **Label history.** A v1.1 safety update with retired claims, to test bots answering from superseded content.
- **Adversarial prompts.** Prompt-injection and jailbreak attempts against the HCP bot and patient-services guardrails.

## Documents

Planned for later. The concern is repository size, so the design generates documents on demand rather than committing them:

- **Content.** Filled benefits letters and Start Forms, plan approval and denial letters, appeal letters, Foundation decisions and fax cover sheets, some made to look scanned or faxed.
- **What gets committed.** A committed manifest (JSON) lists each document with its template, source record and the fields an extraction tool should return. A script renders the PDFs locally from the manifest into an ignored folder, so the repository stays small and the expected fields stay under validation.
- **Why.** It targets document-AI and OCR testing, where almost no public pharma data exists.

## Complete patient journeys

Turn some generated patients into full journeys: enrollment, benefits check, prior authorization, shipments, claims, EPCIS and 867 records, then persistence and discontinuation. Discontinuation reasons would match the label's rates. This is the largest item, because every generated patient then has to pass the payer and channel checks. `scripts/build_channel.py` and the payer data would need to accept generated patients as well as the hand-built cases.

## Deferred on purpose

- **Pricing and gross-to-net.** List price, rebates, chargebacks, Medicaid rebates and 340B. The pack has no approved price (PGAP-09), so adding one reverses a design decision.
- **Other languages and markets.** The pack is US English; the only Spanish-language case is QC-26-00114.
- **Free-text corpora.** Contact-center transcripts, community posts and market-research verbatims. They would need LLM generation, labels, and the same fiction and denylist checks as everything else.
