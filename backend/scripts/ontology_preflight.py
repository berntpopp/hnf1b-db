#!/usr/bin/env python3
"""Whole-corpus ontology preflight report.

docs/superpowers/plans/2026-07-30-ontology-data-quality.md Task 5.

The arithmetic that cannot live in pytest: ``conftest.py``'s autouse
``_isolate_database_between_tests`` truncates ``phenopackets`` and
``phenopacket_revisions`` after every test, so any assertion of real corpus
counts inside the test suite either passes vacuously or fails with zero.
This script connects to a real database and reports, **without modifying
anything**:

* every ``(id, label)`` pair at each path in
  ``app.ontology.conformance.ONTOLOGY_PATHS``, checked with A3
  (``check_label``);
* disease entry count, distinct disease term ids, array-length distribution;
* onset distribution across ``diseases[].onset.ontologyClass`` and
  ``subject.timeAtLastEncounter.ontologyClass``;
* modifier totals by label (``phenotypicFeatures[].modifiers[]``);
* working-copy vs. head-published-revision divergence per record.

Scope matches Task 3's decision: the JSONB-path sweep (A3) walks working
copies and head-published revisions only, never full revision history --
older revisions legitimately hold pre-correction values, and treating them
as violations would make A3 permanently red the moment any term is ever
corrected.

Exits non-zero if any A3 violation is found. Output is deterministic (sorted
throughout, no timestamps in the body) so two runs can be meaningfully
``diff``'d -- the intended before/after deployment record for Tasks 3-4:

    uv run python scripts/ontology_preflight.py > /tmp/preflight-before.txt
    # ... apply the ontology-correction migrations ...
    uv run python scripts/ontology_preflight.py > /tmp/preflight-after.txt
    diff /tmp/preflight-before.txt /tmp/preflight-after.txt

Usage:
    uv run python scripts/ontology_preflight.py
    DATABASE_URL=postgresql+asyncpg://... uv run python scripts/ontology_preflight.py
"""

from __future__ import annotations

import asyncio
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Iterator

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

from app.database import async_session_maker  # noqa: E402
from app.ontology.conformance import ONTOLOGY_PATHS, check_label  # noqa: E402

_HPO_LOOKUP_PATH = "hpo_terms_lookup.hpo_id"

# Onset identifiers live in FOUR independent paths, not two. Task 3's
# migration corrected 10 `phenotypicFeatures[].onset.age.ontologyClass`
# values that *disagreed* with their sibling
# `phenotypicFeatures[].onset.ontologyClass` value on the same feature and
# were fixed independently rather than derived from one another -- so a
# corrupted feature-onset at either nested path can exist without the other
# noticing. Enumerated explicitly here (not sourced from `ONTOLOGY_PATHS`,
# which also carries non-onset paths) so `test_onset_report_covers_all_four_`
# `required_paths` fails loudly if a path is ever silently dropped from this
# report, rather than passing vacuously because it merely iterated whatever
# `ONTOLOGY_PATHS` happened to contain.
_ONSET_PATHS: list[str] = [
    "diseases[].onset.ontologyClass",
    "subject.timeAtLastEncounter.ontologyClass",
    "phenotypicFeatures[].onset.ontologyClass",
    "phenotypicFeatures[].onset.age.ontologyClass",
]


def _iter_path_values(doc: dict[str, Any], path: str) -> Iterator[Any]:
    """Walk ``doc`` along an ``ONTOLOGY_PATHS``-style dotted/bracketed path.

    A segment ending in ``[]`` means "this key holds an array; iterate its
    elements and continue the remaining path from each element". Every
    ``ONTOLOGY_PATHS`` entry other than ``hpo_terms_lookup.hpo_id`` (handled
    separately -- it names a SQL table/column, not a JSONB path) resolves to
    either a single ``{id, label}`` object or, for a path ending in ``[]``
    (e.g. ``phenotypicFeatures[].modifiers[]``), each array element itself.
    """

    def walk(node: Any, segments: list[str]) -> Iterator[Any]:
        if node is None:
            return
        if not segments:
            yield node
            return
        segment = segments[0]
        rest = segments[1:]
        is_array = segment.endswith("[]")
        key = segment[:-2] if is_array else segment
        if not isinstance(node, dict):
            return
        value = node.get(key)
        if is_array:
            if isinstance(value, list):
                for item in value:
                    yield from walk(item, rest)
        else:
            yield from walk(value, rest)

    yield from walk(doc, path.split("."))


async def _fetch_working_and_head(
    session: AsyncSession,
) -> list[tuple[str, dict[str, Any], dict[str, Any] | None]]:
    """Return one ``(id, working_copy, head_revision)`` tuple per phenopacket."""
    result = await session.execute(
        text(
            "SELECT p.phenopacket_id, p.phenopacket, r.content_jsonb "
            "FROM phenopackets p "
            "LEFT JOIN phenopacket_revisions r ON p.head_published_revision_id = r.id "
            "ORDER BY p.phenopacket_id"
        )
    )
    return [(row[0], row[1], row[2]) for row in result.fetchall()]


async def _fetch_hpo_terms_lookup(
    session: AsyncSession,
) -> list[tuple[str, str]]:
    result = await session.execute(
        text("SELECT hpo_id, label FROM hpo_terms_lookup ORDER BY hpo_id")
    )
    return [(row[0], row[1]) for row in result.fetchall()]


class Report:
    """Accumulates deterministic, diff-friendly output lines."""

    def __init__(self) -> None:
        """Start with an empty, unviolated report."""
        self.lines: list[str] = []
        self.violation_count = 0

    def header(self, title: str) -> None:
        """Append a section header."""
        self.lines.append("")
        self.lines.append(f"=== {title} ===")

    def line(self, text_line: str) -> None:
        """Append one line of report body."""
        self.lines.append(text_line)

    def render(self) -> str:
        """Render the accumulated report as a single trailing-newline string."""
        return "\n".join(self.lines) + "\n"


async def run_preflight() -> Report:
    """Build the full deterministic report by querying the corpus once."""
    report = Report()
    async with async_session_maker() as session:
        records = await _fetch_working_and_head(session)
        hpo_lookup_rows = await _fetch_hpo_terms_lookup(session)

    # --- Section 1: A3 conformance sweep over every ONTOLOGY_PATHS entry ---
    report.header("A3 conformance sweep (ONTOLOGY_PATHS)")
    violations: Counter[tuple[str, str, str]] = Counter()  # (path, id, label) -> count
    pairs_checked = 0

    for path in ONTOLOGY_PATHS:
        if path == _HPO_LOOKUP_PATH:
            for hpo_id, label in hpo_lookup_rows:
                pairs_checked += 1
                if check_label(hpo_id, label) is not None:
                    violations[(path, hpo_id, label)] += 1
            continue

        for _phenopacket_id, working_copy, head_revision in records:
            for scope_doc in (working_copy, head_revision):
                if scope_doc is None:
                    continue
                for value in _iter_path_values(scope_doc, path):
                    if not isinstance(value, dict):
                        continue
                    term_id = value.get("id")
                    label = value.get("label")
                    if term_id is None or label is None:
                        continue
                    pairs_checked += 1
                    if check_label(term_id, label) is not None:
                        violations[(path, term_id, label)] += 1

    report.line(f"pairs checked: {pairs_checked}")
    report.line(f"distinct violating (path, id, label) triples: {len(violations)}")
    for (path, term_id, label), count in sorted(violations.items()):
        report.line(f"  VIOLATION  {path}  {term_id!r}  {label!r}  (x{count})")
    report.violation_count = len(violations)

    # --- Section 2: disease entry shape ---
    report.header("Disease entries (working copy)")
    disease_entry_count = 0
    disease_term_ids: Counter[str] = Counter()
    array_lengths: Counter[int] = Counter()
    for _phenopacket_id, working_copy, _head in records:
        diseases = working_copy.get("diseases")
        if not isinstance(diseases, list):
            continue
        array_lengths[len(diseases)] += 1
        for disease in diseases:
            disease_entry_count += 1
            term_id = (disease.get("term") or {}).get("id")
            if term_id:
                disease_term_ids[term_id] += 1
    report.line(f"disease entries: {disease_entry_count}")
    report.line(f"distinct disease term ids: {sorted(disease_term_ids)}")
    for term_id, count in sorted(disease_term_ids.items()):
        report.line(f"  term {term_id}: {count}")
    report.line("array-length distribution:")
    for length, count in sorted(array_lengths.items()):
        report.line(f"  length {length}: {count} records")

    # --- Section 3: onset distribution across all four onset paths ---
    # All four are reported independently -- see _ONSET_PATHS's comment for
    # why the two phenotypicFeatures[] onset paths can disagree with each
    # other and must not be conflated into one count.
    report.header("Onset distribution (all four onset paths)")
    for path in _ONSET_PATHS:
        onset_counts: Counter[tuple[str | None, str | None]] = Counter()
        pairs_at_path = 0
        for _phenopacket_id, working_copy, _head in records:
            for value in _iter_path_values(working_copy, path):
                if not isinstance(value, dict):
                    continue
                onset_counts[(value.get("id"), value.get("label"))] += 1
                pairs_at_path += 1

        report.line(f"{path}:  ({pairs_at_path} occurrences)")
        for (term_id, label), count in sorted(
            onset_counts.items(), key=lambda kv: (kv[0][0] or "", kv[0][1] or "")
        ):
            report.line(f"  {term_id!r}  {label!r}: {count}")

    # --- Section 4: modifier totals ---
    report.header("phenotypicFeatures[].modifiers[] totals (working copy)")
    modifier_totals: Counter[tuple[str, str]] = Counter()
    for _phenopacket_id, working_copy, _head in records:
        for feature in working_copy.get("phenotypicFeatures") or []:
            for modifier in feature.get("modifiers") or []:
                modifier_totals[(modifier.get("id"), modifier.get("label"))] += 1
    for (term_id, label), count in sorted(modifier_totals.items()):
        report.line(f"  {term_id!r}  {label!r}: {count}")

    # --- Section 5: working copy vs. head-published-revision divergence ---
    report.header("Working copy vs. head-published-revision divergence")
    no_head = 0
    diverging: list[str] = []
    for phenopacket_id, working_copy, head_revision in records:
        if head_revision is None:
            no_head += 1
            continue
        if working_copy != head_revision:
            diverging.append(phenopacket_id)
    report.line(f"records total: {len(records)}")
    report.line(f"records with no head-published revision: {no_head}")
    report.line(f"records where working copy != head revision: {len(diverging)}")
    for phenopacket_id in sorted(diverging):
        report.line(f"  diverges: {phenopacket_id}")

    return report


def main() -> int:
    """CLI entry point: print the report, exit non-zero on any A3 violation."""
    report = asyncio.run(run_preflight())
    sys.stdout.write(report.render())
    return 1 if report.violation_count else 0


if __name__ == "__main__":
    raise SystemExit(main())
