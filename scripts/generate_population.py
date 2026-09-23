#!/usr/bin/env python3
"""Generate the synthetic population: offices, HCPs, office staff, patients.

Needs Faker (scripts/requirements.txt), unlike the rest of the tooling:

    python3 -m venv .venv && .venv/bin/pip install -r scripts/requirements.txt
    .venv/bin/python scripts/generate_population.py                      # every entity, default counts
    .venv/bin/python scripts/generate_population.py --entity hcps        # one entity; its inputs must exist
    .venv/bin/python scripts/generate_population.py --entity patients --with-deps
    .venv/bin/python scripts/generate_population.py --count hcps=1000 --count patients=800
    .venv/bin/python scripts/generate_population.py --entity lab-results --count lab-results=200   # patients monitored
    .venv/bin/python scripts/generate_population.py --list

Output goes to sources/population/<entity>.json. The same seed and Faker
version always give the same records. Run scripts/validate.py afterwards.
Entity types live in scripts/population/entities/; see population/core.py for
how to add one.
"""

import argparse
import importlib
import pkgutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

try:
    import faker
except ImportError:
    sys.exit("Faker is not installed. Run: python3 -m venv .venv && .venv/bin/pip install -r scripts/requirements.txt")

from population import core, entities  # noqa: E402

for mod in pkgutil.iter_modules(entities.__path__):
    importlib.import_module(f"population.entities.{mod.name}")


def order(names):
    """The chosen entities, each after the entities it requires."""
    done, out = set(), []

    def visit(n, chain=()):
        if n in chain:
            sys.exit(f"circular requirement: {' -> '.join(chain + (n,))}")
        if n in done or n not in names:
            return
        for r in core.REGISTRY[n].requires:
            visit(r, chain + (n,))
        done.add(n)
        out.append(n)
    for n in sorted(names):
        visit(n)
    return out


def with_deps(names):
    out, stack = set(), list(names)
    while stack:
        n = stack.pop()
        if n not in out:
            out.add(n)
            stack.extend(core.REGISTRY[n].requires)
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--entity", action="append", choices=sorted(core.REGISTRY), metavar="NAME",
                        help="entity to generate; repeat for several (default: all)")
    parser.add_argument("--count", action="append", default=[], metavar="NAME=N", help="override an entity's default count")
    parser.add_argument("--seed", type=int, default=20260922, help="random seed (default 20260922)")
    parser.add_argument("--with-deps", action="store_true", help="also regenerate the entities the chosen ones require")
    parser.add_argument("--list", action="store_true", help="list entity types and exit")
    args = parser.parse_args()

    if args.list:
        for name, e in sorted(core.REGISTRY.items()):
            req = ", ".join(e.requires) or "nothing"
            print(f"{name:16} default {e.default_count:>5} {e.count_means:<20} ids {e.id_prefix}-NNNNN  requires {req}")
        return

    counts = {}
    for item in args.count:
        name, _, n = item.partition("=")
        if name not in core.REGISTRY or not n.isdigit() or int(n) < 1:
            parser.error(f"--count expects NAME=N with a known entity and N >= 1, got {item!r}")
        counts[name] = int(n)

    chosen = set(args.entity or core.REGISTRY)
    if args.with_deps:
        chosen = with_deps(chosen)
    ctx = core.Context(args.seed, faker.Faker)
    for name in order(chosen):
        e = core.REGISTRY[name]
        records = e.generate(ctx, counts.get(name, e.default_count))
        ctx.set_records(name, records)
        path = core.write(e, records, ctx, faker.VERSION)
        print(f"wrote {path.relative_to(core.ROOT)} ({len(records)} records)")

    stale = sorted(n for n, e in core.REGISTRY.items()
                   if n not in chosen and e.path.exists() and set(e.requires) & chosen)
    if stale:
        print(f"note: {', '.join(stale)} reference regenerated entities; regenerate them too, "
              f"or run scripts/validate.py to see what no longer resolves")


if __name__ == "__main__":
    main()
