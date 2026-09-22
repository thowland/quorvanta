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


if __name__ == "__main__":
    render_program_terms()
