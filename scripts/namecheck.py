#!/usr/bin/env python3
"""Exact-phrase web search for each name in names-to-check.csv.

Run from anywhere:
    python3 scripts/namecheck.py                  # search every name without a status
    python3 scripts/namecheck.py --limit 90       # stay inside a daily quota
    python3 scripts/namecheck.py --recheck        # search again even where a status is set
    python3 scripts/namecheck.py --dry-run        # show what would be searched

For each row it reads the name from column C, searches for it in double quotes,
and writes column J (status) and column K (notes):

    available   no result contains the exact phrase
    in use      at least one result contains the exact phrase in its title or snippet
    N/A         not searched: nonproprietary (generic) names, which cannot be
                trademarked, and kind "reference" rows, which name a real product

The notes column gets the date, time and timezone of the lookup. The evidence
for each search (query, reported hit count, top links) is appended to
namecheck-log.jsonl, so an 'in use' can be checked by hand.

Backends (--backend), each needing its own credentials in the environment:
    google   Google Custom Search JSON API: GOOGLE_API_KEY and GOOGLE_CSE_ID (a
             Programmable Search Engine set to search the entire web). Google has
             closed this API to new customers and ends it on 2027-01-01.
    serpapi  Google results through SerpApi: SERPAPI_API_KEY.
    brave    Brave Search API: BRAVE_SEARCH_API_KEY.

The CSV is saved after every lookup, so a run stopped by a quota or an error can
be resumed. Standard library only.
"""

import argparse
import csv
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NAME, KIND, STATUS, NOTES = 2, 1, 9, 10          # columns C, B, J and K
EXPECTED = {KIND: "kind", NAME: "name", STATUS: "status", NOTES: "notes"}
NOT_SEARCHED = {"nonproprietary", "reference"}


class QuotaExceeded(Exception):
    pass


def fetch(url, headers=None):
    req = urllib.request.Request(url, headers={"User-Agent": "quorvanta-namecheck/1.0", **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        if e.code == 429 or (e.code == 403 and re.search(r"quota|limit|rateLimit", body, re.I)):
            raise QuotaExceeded(f"HTTP {e.code}: {body[:200]}")
        raise RuntimeError(f"HTTP {e.code}: {body[:300]}")


def env(name):
    value = os.environ.get(name)
    if not value:
        sys.exit(f"{name} is not set; see the docstring at the top of scripts/namecheck.py")
    return value


def google(query):
    params = {"key": env("GOOGLE_API_KEY"), "cx": env("GOOGLE_CSE_ID"), "q": query, "num": 10}
    data = fetch("https://www.googleapis.com/customsearch/v1?" + urllib.parse.urlencode(params))
    items = [{"title": i.get("title", ""), "snippet": i.get("snippet", ""), "link": i.get("link", "")} for i in data.get("items", [])]
    return int(data.get("searchInformation", {}).get("totalResults", 0) or 0), items


def serpapi(query):
    params = {"engine": "google", "q": query, "num": 10, "api_key": env("SERPAPI_API_KEY")}
    data = fetch("https://serpapi.com/search.json?" + urllib.parse.urlencode(params))
    if "error" in data and "hasn't returned any results" not in data["error"]:
        if re.search(r"run out|limit", data["error"], re.I):
            raise QuotaExceeded(data["error"])
        raise RuntimeError(data["error"])
    items = [{"title": i.get("title", ""), "snippet": i.get("snippet", ""), "link": i.get("link", "")} for i in data.get("organic_results", [])]
    return int(data.get("search_information", {}).get("total_results", len(items)) or 0), items


def brave(query):
    data = fetch("https://api.search.brave.com/res/v1/web/search?" + urllib.parse.urlencode({"q": query, "count": 20}),
                 {"Accept": "application/json", "X-Subscription-Token": env("BRAVE_SEARCH_API_KEY")})
    items = [{"title": i.get("title", ""), "snippet": re.sub(r"<[^>]+>", "", i.get("description", "")), "link": i.get("url", "")}
             for i in data.get("web", {}).get("results", [])]
    return len(items), items


BACKENDS = {"google": google, "serpapi": serpapi, "brave": brave}


def contains_phrase(name, item):
    """True if the exact phrase appears, as whole words, in the result's title or snippet."""
    text = re.sub(r"\s+", " ", f"{item['title']} {item['snippet']}")
    return re.search(rf"(?<![\w-]){re.escape(name)}(?![\w-])", text, re.I) is not None


def stamp():
    now = datetime.now().astimezone()
    offset = now.strftime("%z")
    return now.strftime("%Y-%m-%d %H:%M:%S %Z") + f" (UTC{offset[:3]}:{offset[3:]})"


def save(path, rows):
    tmp = path.with_suffix(".tmp")
    with tmp.open("w", newline="") as f:
        csv.writer(f).writerows(rows)
    tmp.replace(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--file", default=str(ROOT / "names-to-check.csv"), help="CSV to update (default names-to-check.csv)")
    parser.add_argument("--log", default=str(ROOT / "namecheck-log.jsonl"), help="evidence log (default namecheck-log.jsonl)")
    parser.add_argument("--backend", choices=sorted(BACKENDS), default="google")
    parser.add_argument("--limit", type=int, help="search at most this many names in this run")
    parser.add_argument("--recheck", action="store_true", help="search names that already have a status")
    parser.add_argument("--delay", type=float, default=1.0, help="seconds between searches (default 1)")
    parser.add_argument("--dry-run", action="store_true", help="list the searches without running them or writing anything")
    args = parser.parse_args()

    path = Path(args.file)
    with path.open(newline="") as f:
        rows = list(csv.reader(f))
    header = rows[0]
    for col, want in EXPECTED.items():
        if len(header) <= col or header[col] != want:
            sys.exit(f"column {chr(65 + col)} should be '{want}' but is '{header[col] if len(header) > col else ''}'; "
                     f"regenerate the file with scripts/extract_names.py")

    search = BACKENDS[args.backend]
    counts, searched, errors = {}, 0, 0
    log = None if args.dry_run else Path(args.log).open("a")
    try:
        for row in rows[1:]:
            name, kind = row[NAME], row[KIND]
            if row[STATUS] and not args.recheck:
                continue
            if kind in NOT_SEARCHED:
                status = "N/A"
                if args.dry_run:
                    print(f"N/A        {name}  ({kind}; not searched)")
                    continue
                row[STATUS], row[NOTES] = status, stamp()
                save(path, rows)
                counts[status] = counts.get(status, 0) + 1
                continue
            if args.limit is not None and searched >= args.limit:
                continue            # keep going only to mark N/A rows, which cost no search
            query = f'"{name}"'
            if args.dry_run:
                print(f"search     {query}")
                searched += 1
                continue
            try:
                total, items = search(query)
            except QuotaExceeded as e:
                print(f"stopped: quota reached ({e}). Progress is saved; run again later to continue.")
                break
            except (RuntimeError, urllib.error.URLError) as e:
                errors += 1
                print(f"error on {query}: {e}")
                if errors >= 3:
                    print("stopped after 3 errors. Progress is saved.")
                    break
                continue
            errors = 0
            matches = [i for i in items if contains_phrase(name, i)]
            status = "in use" if matches else "available"
            when = stamp()
            row[STATUS], row[NOTES] = status, when
            save(path, rows)
            log.write(json.dumps({"name": name, "query": query, "backend": args.backend, "checked": when, "status": status,
                                  "reported_results": total, "exact_matches": len(matches),
                                  "top": [i["link"] for i in (matches or items)[:5]]}) + "\n")
            log.flush()
            counts[status] = counts.get(status, 0) + 1
            searched += 1
            print(f"{status:10} {name}")
            time.sleep(args.delay)
    finally:
        if log:
            log.close()
    remaining = sum(1 for r in rows[1:] if not r[STATUS])
    if not args.dry_run:
        print(f"\n{', '.join(f'{v} {k}' for k, v in sorted(counts.items())) or 'nothing updated'}; {remaining} names still unchecked")
    else:
        print(f"\n{searched} searches would run with --backend {args.backend}")


if __name__ == "__main__":
    main()
