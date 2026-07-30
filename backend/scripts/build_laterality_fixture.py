#!/usr/bin/env python3
r"""Build the de-identified laterality-restoration fixture from the source workbook.

docs/ontology-defect-report-2026-07-30.md §3 and
docs/superpowers/plans/2026-07-30-ontology-data-quality.md Task 4.

``extractors.py`` (before its correction) matched laterality cell values
against four bare tokens (``bilateral``, ``unilateral``, ``left``, ``right``)
while the source actually stores compound text (``unilateral left``,
``unilateral unspecified``, ...), so 408 correct, curated laterality
assertions were silently dropped -- the phenotype row itself was still
written, leaving a feature indistinguishable from one whose laterality was
never stated. This script re-derives what those 408 assertions were, from
the same workbook the original import read.

Resolving source rows to records
---------------------------------

The importer groups 939 sheet rows into 864 individuals (73 individuals have
more than one row) and deduplicates features by HPO id, so a raw per-row
tally of "797 bilateral" does **not** imply 797 stored ``Bilateral``
modifiers once records are resolved. This script emits **one resolved row
per (individual_id, phenotype_column)**:

* group source rows by ``individual_id``;
* for each of the six laterality-bearing phenotype columns, collect the
  distinct *laterality-asserting* values across that individual's rows
  (``parse_laterality`` decides what counts as an assertion -- "no", "not
  reported" and blank cells are not laterality information and do not count
  against agreement);
* if the individual's rows agree (zero or one distinct asserting value),
  emit the resolved value;
* if they disagree, emit **nothing** to the fixture -- the conflict is
  written to a separate conflicts CSV for curator resolution rather than
  silently picked one way or the other.

Per ADR 0003's PII constraint, the fixture and the workbook itself are never
committed. The fixture carries only ``individual_id, phenotype_column,
hpo_id, laterality_value`` -- never ``ReviewBy`` (institutional email
addresses), comments, or any other clinical column.

Usage::

    uv run --with openpyxl python scripts/build_laterality_fixture.py \\
        /path/to/HNF1B_DataCuration.xlsx \\
        --fixture-out migration/data/laterality_2026-07-30.csv \\
        --conflicts-out migration/data/laterality_conflicts_2026-07-30.csv
"""

from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import sys
from pathlib import Path
from typing import Any

# openpyxl is intentionally not a project dependency -- this script is a
# one-off, run via `uv run --with openpyxl`, per the task instructions.
import openpyxl

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from migration.phenopackets.laterality import parse_laterality  # noqa: E402

# phenotype_column -> hpo_id. Matches app/ontology/data/curation_vocabulary.csv
# (the committed, verified sheet vocabulary) and what the corpus actually
# stores today. Hardcoded here, not imported from HPOMapper's fallback
# dictionary: this script runs as part of Task 4, before Task 6 corrects
# that dictionary's own remaining wrong entries, and this script's own
# correctness must not depend on that later task's completion.
COLUMN_TO_HPO: dict[str, str] = {
    "Hyperechogenicity": "HP:0033132",
    "RenalCysts": "HP:0000107",
    "MulticysticDysplasticKidney": "HP:0000003",
    "RenalHypoplasia": "HP:0000089",
    "SolitaryKidney": "HP:0000122",
    "UrinaryTractMalformation": "HP:0000079",
}

FIXTURE_FIELDS = ["individual_id", "phenotype_column", "hpo_id", "laterality_value"]
CONFLICTS_FIELDS = [
    "individual_id",
    "phenotype_column",
    "hpo_id",
    "conflicting_values",
]


def _individual_id_key(raw: Any) -> str:
    """Normalise a sheet ``individual_id`` cell (often a float) to its record form.

    ``phenopackets.phenopacket_id`` for the curated corpus is ``phenopacket-<n>``
    and ``subject_id`` is ``str(n)``; the sheet stores ``individual_id`` as a
    float (e.g. ``106.0``) because every column in an ``openpyxl`` numeric
    read comes back as ``float``.
    """
    return str(int(raw))


def read_individual_rows(xlsx_path: Path) -> list[dict[str, Any]]:
    """Read every row of the ``Individuals`` sheet, keeping only the columns needed."""
    workbook = openpyxl.load_workbook(xlsx_path, read_only=True, data_only=True)
    worksheet = workbook["Individuals"]
    rows_iter = worksheet.iter_rows(values_only=True)
    header = next(rows_iter)
    col_index = {name: i for i, name in enumerate(header)}

    missing = [c for c in COLUMN_TO_HPO if c not in col_index]
    if "individual_id" not in col_index:
        missing.append("individual_id")
    if missing:
        raise SystemExit(f"Individuals sheet is missing expected column(s): {missing}")

    rows: list[dict[str, Any]] = []
    for row in rows_iter:
        individual_id = row[col_index["individual_id"]]
        if individual_id is None:
            continue
        record = {"individual_id": individual_id}
        for column in COLUMN_TO_HPO:
            record[column] = row[col_index[column]]
        rows.append(record)
    return rows


def resolve(
    rows: list[dict[str, Any]],
) -> tuple[list[dict[str, str]], list[dict[str, str]], dict[str, int]]:
    """Group rows by individual and resolve laterality per plan Task 4 Step 1."""
    by_individual: dict[Any, list[dict[str, Any]]] = collections.defaultdict(list)
    for row in rows:
        by_individual[row["individual_id"]].append(row)

    fixture_rows: list[dict[str, str]] = []
    conflict_rows: list[dict[str, str]] = []
    agreements = 0
    conflicts = 0
    no_assertion = 0

    for individual_id in sorted(by_individual, key=lambda v: int(v)):
        individual_rows = by_individual[individual_id]
        pp_individual_id = _individual_id_key(individual_id)
        for column, hpo_id in COLUMN_TO_HPO.items():
            values: set[str] = set()
            for source_row in individual_rows:
                raw_value = source_row[column]
                if parse_laterality(raw_value):
                    values.add(str(raw_value).strip().lower())

            if not values:
                no_assertion += 1
                continue

            if len(values) == 1:
                agreements += 1
                fixture_rows.append(
                    {
                        "individual_id": pp_individual_id,
                        "phenotype_column": column,
                        "hpo_id": hpo_id,
                        "laterality_value": next(iter(values)),
                    }
                )
            else:
                conflicts += 1
                conflict_rows.append(
                    {
                        "individual_id": pp_individual_id,
                        "phenotype_column": column,
                        "hpo_id": hpo_id,
                        "conflicting_values": "|".join(sorted(values)),
                    }
                )

    summary = {
        "source_rows": len(rows),
        "unique_individuals": len(by_individual),
        "unique_keys_with_assertion": agreements + conflicts,
        "agreements": agreements,
        "conflicts": conflicts,
        "no_assertion": no_assertion,
    }
    return fixture_rows, conflict_rows, summary


def _write_csv(
    path: Path, fields: list[str], rows: list[dict[str, str]], header_comment: str
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        fh.write(header_comment)
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point: read the workbook, resolve laterality, write both CSVs."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workbook", type=Path, help="Path to HNF1B_DataCuration.xlsx")
    parser.add_argument(
        "--fixture-out",
        type=Path,
        default=Path("migration/data/laterality_2026-07-30.csv"),
    )
    parser.add_argument(
        "--conflicts-out",
        type=Path,
        default=Path("migration/data/laterality_conflicts_2026-07-30.csv"),
    )
    args = parser.parse_args(argv)

    workbook_sha256 = hashlib.sha256(args.workbook.read_bytes()).hexdigest()

    rows = read_individual_rows(args.workbook)
    fixture_rows, conflict_rows, summary = resolve(rows)

    print("Resolution summary:")
    for key, value in summary.items():
        print(f"  {key:28s} {value}")
    print(f"  {'fixture rows emitted':28s} {len(fixture_rows)}")
    print(f"  {'conflict rows emitted':28s} {len(conflict_rows)}")

    header_comment = (
        f"# Source: HNF1B_DataCuration.xlsx sha256={workbook_sha256}\n"
        "# Live source: Google Sheet 1jE4-HmyAh1FUK6Ph7AuHt2UDVW2mTINTWXBtAWqhVSw\n"
        "# Built by scripts/build_laterality_fixture.py -- see that script's\n"
        "# docstring for the row-resolution rules. De-identified per ADR 0003:\n"
        "# individual_id, phenotype_column, hpo_id, laterality_value only.\n"
    )
    _write_csv(args.fixture_out, FIXTURE_FIELDS, fixture_rows, header_comment)

    conflicts_comment = (
        f"# Source: HNF1B_DataCuration.xlsx sha256={workbook_sha256}\n"
        "# Individuals whose repeated sheet rows disagree on a laterality\n"
        "# column's value. Not restored automatically; needs curator review.\n"
    )
    _write_csv(args.conflicts_out, CONFLICTS_FIELDS, conflict_rows, conflicts_comment)

    print(f"Wrote {args.fixture_out} ({len(fixture_rows)} rows)")
    print(f"Wrote {args.conflicts_out} ({len(conflict_rows)} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
