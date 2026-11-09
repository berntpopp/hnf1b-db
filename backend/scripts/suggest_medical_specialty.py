#!/usr/bin/env python3
"""Suggest ``medical_specialty`` for publications (curation aid, issue #11).

Reads the publications sheet export (CSV with ``PMID`` and ``medical_specialty``
columns) or a list of PMIDs, fetches journal + first/last author affiliations
from PubMed and the journal's MeSH headings from the NLM Catalog, and writes a
suggestions CSV for curators. Nothing is written to the sheet or the database.

Usage:
    # Suggest for every row whose medical_specialty is still empty
    python scripts/suggest_medical_specialty.py --csv publications.csv -o out.csv
    # Measure agreement with the rows curators already labelled
    python scripts/suggest_medical_specialty.py --csv publications.csv --evaluate
    # Ad-hoc PMIDs
    python scripts/suggest_medical_specialty.py --pmids 20378641 16249435

The sheet export URL is
``https://docs.google.com/spreadsheets/d/<SHEET_ID>/export?format=csv&gid=<GID>``
and may be passed directly to ``--csv``.
"""

import argparse
import asyncio
import csv
import io
import sys
from pathlib import Path

# Add backend to path so ``app`` imports resolve when run as a script.
sys.path.insert(0, str(Path(__file__).parent.parent))

import aiohttp

from app.core.config import settings
from app.publications.specialty import evaluate, fetch_specialty_suggestions


def _labels(cell: str) -> set[str]:
    return {s.strip().lower() for s in cell.split(",") if s.strip()}


async def _read_rows(source: str, session: aiohttp.ClientSession) -> list[dict]:
    if source.startswith(("http://", "https://")):
        async with session.get(source) as response:
            response.raise_for_status()
            text = await response.text()
    else:
        text = Path(source).read_text(encoding="utf-8")
    return list(csv.DictReader(io.StringIO(text)))


async def main(args: argparse.Namespace) -> int:
    """Run the suggester and write or evaluate its output."""
    apis = settings.external_apis
    async with aiohttp.ClientSession() as session:
        if args.csv:
            rows = await _read_rows(args.csv, session)
            gold = {
                r["PMID"].strip(): _labels(r.get("medical_specialty") or "")
                for r in rows
                if r.get("PMID", "").strip().isdigit()
            }
        else:
            gold = {p.replace("PMID:", ""): set() for p in args.pmids}
        if args.evaluate:
            targets = [p for p, g in gold.items() if g]
        elif args.all or not args.csv:
            targets = list(gold)
        else:
            targets = [p for p, g in gold.items() if not g]
        suggestions = await fetch_specialty_suggestions(
            targets,
            session=session,
            base_url=apis.efetch.base_url,
            api_key=settings.PUBMED_API_KEY,
            batch_size=apis.efetch.batch_size,
            timeout=apis.efetch.timeout_seconds,
        )

    missing = [p for p in targets if p not in suggestions]
    if missing:
        print(f"PubMed returned no record for: {', '.join(missing)}", file=sys.stderr)

    if args.evaluate:
        pairs = [(suggestions[p], gold[p]) for p in targets if p in suggestions]
        for key, value in evaluate(pairs).items():
            print(
                f"{key:>9}: {value:.3f}"
                if isinstance(value, float)
                else f"{key:>9}: {value}"
            )
        return 0

    out = (
        open(args.output, "w", newline="", encoding="utf-8")
        if args.output
        else sys.stdout
    )
    writer = csv.writer(out)
    writer.writerow(
        ["PMID", "suggested_medical_specialty", "scores", "evidence", "current"]
    )
    for pmid in targets:
        s = suggestions.get(pmid)
        if s is None:
            continue
        writer.writerow(
            [
                pmid,
                ", ".join(s.ranked),
                "; ".join(f"{k}={s.scores[k]}" for k in s.ranked),
                "; ".join(f"{k}<-{'+'.join(s.evidence[k])}" for k in s.ranked),
                ", ".join(sorted(gold.get(pmid, set()))),
            ]
        )
    if args.output:
        out.close()
        print(
            f"Wrote {len(targets) - len(missing)} suggestions to {args.output}",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--csv", help="Publications sheet CSV path or export URL")
    source.add_argument("--pmids", nargs="+", help="PMIDs to classify")
    parser.add_argument(
        "--all", action="store_true", help="Also suggest for labelled rows"
    )
    parser.add_argument(
        "--evaluate", action="store_true", help="Score against labelled rows"
    )
    parser.add_argument("-o", "--output", help="Write CSV here instead of stdout")
    sys.exit(asyncio.run(main(parser.parse_args())))
