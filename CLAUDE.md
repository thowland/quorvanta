# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

This is not software. It is a synthetic test dataset: an invented drug (QUORVANTA, soriximel tavorate), an invented disease (Brennick syndrome), an invented company (Arden Quay Biosciences), and the regulatory, promotional, medical, access, patient and press documents around them. The data is used to test a guardrailed HCP chatbot without touching a real product. There is no build step; the only tooling is the validator in `scripts/` (see Commands). `sources/README.md` is the authoritative description of the pack, covering files, cast, test patterns, claim schema, timeline and fault types.

## Non-negotiable invariants

- **Nothing real.** No real drug, brand, company, product or software vendor names anywhere, including in README prose about where the pack came from. The pack was originally modelled on a real label; all traces of that were deliberately removed and must not come back.
- **Fiction markers:**
  - Phone numbers use the reserved `1-800-555-01xx` range.
  - Web and email domains use `.example`.
  - DOIs use the `10.5555` prefix.
  - NCPDP ids use a `99-` prefix.
  - Every JSON file carries a top-level `_notice` field.
  - Every Markdown document opens with a "Everything here is invented" blockquote.
  - Keep all of these markers in any new file.
- **Numbers must agree everywhere.** A figure lives first in `sources/label/label.md` and reappears in claims, references, promo pieces, SRDs, patient materials and press releases. Arm sizes sum to study totals, the pooled safety population equals the two twice-daily arms, and relative reductions follow from the stated rates. When changing a number, grep every file for it.
- **Deliberate traps are features, not bugs.** Do not "fix" them:
  - the withdrawn claim `EFF-013`;
  - the three references marked `not_approved_for_promotional_use` (REF-019 to REF-021);
  - findings that support no claim (`REF-003.7`, `REF-011.7`);
  - the 6.2% GI discontinuation figure that appears only in the press release;
  - the label silences listed in `known-gaps.json`.

## How the pieces connect

The chain of support runs **label → references → claims → materials**:

- `claims/claims-library.json`: each claim cites finding ids in `claims/references.json` (e.g. `REF-002.2`) through `reference.citations`. It may list other claims in `requires`; those must accompany it. `qualifiers.data_source` is `DMT`, `QUORVANTA` or `class`. The DMT bridging attribution is the pack's central test pattern. `rules.isi_claims` defines the safety summary that must accompany any efficacy claim.
- `promotional/promo-materials.json`: each unit lists the claim ids that support it. The three `promo-*.md` files are readable renderings of the same units and must stay in sync with the JSON.
- `patient/dtc-claims.json`: each consumer claim maps to HCP claim ids via `derives_from`.
- `test-design/known-gaps.json`: each gap names the SRD in `medical-information/srds.json` that answers it (`srd_id`, which may be null). Each SRD points back to its gap via `gap_id`. This file is the answer key. Keep it out of anything that would be fed to a generator or judge model.
- Access claims (`ACC-*`) cite REF-022 (program terms) and REF-023 (distribution notice), which mirror `access/specialty-pharmacy-network.json` and the commercial-availability press release.

Several documents exist as a JSON/Markdown pair (`references`, `srds`, `start-form`, promo pieces). The JSON is canonical; update the Markdown to match. Paths stored inside JSON files (e.g. `product.label`, `references_file`) are relative to `sources/`.

## Commands

```bash
python3 scripts/validate.py                            # all integrity checks; exits non-zero on failure
python3 scripts/validate.py --denylist ~/real-names.txt  # also reject real brand/company names
```

Run the validator after any edit. It checks:
- JSON parses and carries `_notice`, and every Markdown file has a fiction notice;
- citations, `requires` and `derives_from` ids resolve, and no approved claim cites a non-approved reference;
- promo and DTC materials use only approved claims, and promo unit text appears verbatim in its Markdown rendering;
- gap↔SRD links run both ways, and each JSON/Markdown pair is in sync;
- the counts in `sources/README.md` still match the data;
- phones, DOIs and domains use the fiction ranges.

The denylist file must live outside the repo, since listing real names inside the pack would defeat the purpose. The only real numbers allowed are FDA MedWatch and US Poison Control (`ALLOWED_PHONES` in the script).

A pre-commit hook (`scripts/git-hooks/pre-commit`) runs the validator against the staged snapshot and blocks the commit on failure. It picks up a denylist from `$QUORVANTA_DENYLIST` when set. Each fresh clone must enable it once with `git config core.hooksPath scripts/git-hooks`. The main branch is `master`.

`scripts/` is for tooling that operates on the pack. Nothing under `scripts/` is part of the dataset.
