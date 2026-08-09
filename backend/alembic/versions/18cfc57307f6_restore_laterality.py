"""Restore the laterality annotations dropped by an importer defect.

docs/ontology-defect-report-2026-07-30.md §3,
docs/superpowers/plans/2026-07-30-ontology-data-quality.md Task 4, and
docs/adr/0003-ga4gh-conformance-debt.md Amendment 1 (D5 -- this restoration
is authorized as journalled, reversible data recovery, not GA4GH
conformance work).

``extractors.py`` (before correction) matched laterality cell values against
four bare tokens (``bilateral``, ``unilateral``, ``left``, ``right``) while
the source stores compound text (``unilateral left``, ``unilateral
unspecified``, ...). Only ``bilateral`` ever occurred bare, so every
compound value was silently dropped while the phenotype feature itself was
still written -- leaving 408 raw source rows' worth of laterality
information indistinguishable from "never stated".

Source resolution (``scripts/build_laterality_fixture.py``, run against
``HNF1B_DataCuration.xlsx``, sha256
``0fcc5362148085ea0c55b682836c8f4ecef2b5be7f88a9038409f94d8a5061ec``):
939 source rows resolve to 864 individuals; 73 individuals have more than
one source row. Grouping by (individual_id, phenotype_column) and requiring
agreement across an individual's rows (plan Task 4 Step 1) yields **1140**
resolved assertions, not the raw 1205 (=797+408) row tally: 18
(individual_id, column) keys had disagreeing repeated rows and are written
to ``migration/data/laterality_conflicts_2026-07-30.csv`` for curator
review rather than resolved automatically. The 1140 resolved rows are
committed at ``migration/data/laterality_2026-07-30.csv`` (de-identified per
ADR 0003: ``individual_id, phenotype_column, hpo_id, laterality_value``
only -- never ``ReviewBy`` or any other clinical column).

Matched against the live corpus (verified before writing this revision):
every one of the 1140 resolved rows finds exactly one existing
``phenotypicFeatures`` entry (by ``phenopacket-<individual_id>`` and
``hpo_id``) -- 763 already carry the correct ``Bilateral`` modifier (a
no-op) and 377 have empty ``modifiers`` and are backfilled. Zero
disagreements, zero unmatched rows. This yields new modifier totals:
``Unilateral`` 377 (160 unspecified + 113 with ``Left`` + 104 with
``Right``), ``Bilateral`` unchanged at 771. Total new modifier entries:
377 + 113 + 104 = 594.

Uniform, term-agnostic parsing (LATERALITY POLICY, plan controller note
2026-07-30): ``HP:0000122`` "Unilateral renal agenesis" admits
``{Unilateral, Left, Right}`` and rejects only ``Bilateral`` -- an earlier
side-only draft was overturned because the source carries 20
"unilateral unspecified" values on that term, and dropping them would
recreate the very indistinguishability this migration repairs. The parser
below therefore has no per-term special case.

Frozen parsing logic
---------------------

``_parse_laterality`` below is a byte-for-byte frozen copy of
``migration.phenopackets.laterality.parse_laterality`` (Task 1), not an
import of it: per this plan's global constraint, a migration must be a
frozen snapshot of its own intent, and importing a migration-package module
would let a later edit to that module silently change what this
already-applied revision does when replayed on a fresh database. Parity
between the two encodings is enforced by
``tests/test_laterality_backfill.py::test_frozen_parser_matches_the_shared_implementation``,
never by an import (mirroring the curation plan's Task 7 Step 3 correction
for the same class of dependency).

Scope and reversibility
------------------------

Same scope decision as ``efa98cccfa51``: only ``phenopackets.phenopacket``
(working copy) and ``phenopacket_revisions.content_jsonb`` at
``head_published_revision_id`` (public head) are rewritten; older revisions
are immutable history. Reuses ``ontology_migration_journal``
(``json_path='phenotypicFeatures'``) rather than creating a second journal
table. Downgrade restores each journalled row only after verifying its
current value still hashes to the recorded postimage -- a curator edit made
after this migration ran is left alone rather than clobbered, and
``restore_from_journal`` aborts (raises) rather than silently returning a
partial count if any row was left alone this way, naming which ones. A
global delete of the three unilateral modifier ids is explicitly not an
acceptable downgrade, because it would also delete post-migration curator
edits (ADR 0003 Amendment 1).

Re-running upgrade() safely, mirroring ``efa98cccfa51``'s equivalent fix:
``apply_restoration`` refuses if this revision already has journal rows
(``upgrade()`` no longer clears them unconditionally first). Against an
already-restored corpus, every backfilled feature takes the
``already_correct`` branch in ``_restore_and_journal`` -- ``changed`` stays
``False`` -- so a second, unguarded application would journal nothing while
an unconditional clear-first would have destroyed the first application's
594 preimage rows outright. ``restore_from_journal`` clears this revision's
own journal rows only once every one of them has been confirmed restored, so
the journal is non-empty exactly when the corpus is in the
post-``upgrade()`` state.

Revision ID: 18cfc57307f6
Revises: efa98cccfa51
Create Date: 2026-07-30 20:59:46.372380
"""

import csv
import json
from pathlib import Path
from typing import Any, Sequence, Union

from sqlalchemy import text
from sqlalchemy.engine import Connection

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "18cfc57307f6"
down_revision: Union[str, Sequence[str], None] = "efa98cccfa51"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_FIXTURE_PATH = (
    Path(__file__).resolve().parents[2]
    / "migration"
    / "data"
    / "laterality_2026-07-30.csv"
)

# --- frozen copy of migration.phenopackets.laterality.parse_laterality -----
# See module docstring "Frozen parsing logic". Keep in sync with
# migration/phenopackets/laterality.py by re-running the parity test, never
# by importing it.
_BILATERAL = {"id": "HP:0012832", "label": "Bilateral"}
_UNILATERAL = {"id": "HP:0012833", "label": "Unilateral"}
_LEFT = {"id": "HP:0012835", "label": "Left"}
_RIGHT = {"id": "HP:0012834", "label": "Right"}

_NON_LATERALITY = {
    "",
    "no",
    "none",
    "absent",
    "negative",
    "yes",
    "not reported",
    "not applicable",
    "unknown",
}


def _parse_laterality(value: Any) -> list[dict[str, str]]:
    """Frozen copy of ``laterality.parse_laterality`` -- see module docstring."""
    if value is None:
        return []

    text_value = str(value).strip().lower()
    if text_value in _NON_LATERALITY:
        return []

    has_bilateral = "bilateral" in text_value
    has_unilateral = "unilateral" in text_value

    if has_bilateral and has_unilateral:
        return []
    if has_bilateral:
        return [dict(_BILATERAL)]
    if not has_unilateral:
        return []

    modifiers = [dict(_UNILATERAL)]
    if "left" in text_value:
        modifiers.append(dict(_LEFT))
    elif "right" in text_value:
        modifiers.append(dict(_RIGHT))
    return modifiers


def load_fixture(path: Path = _FIXTURE_PATH) -> list[dict[str, str]]:
    """Read the committed, de-identified laterality fixture CSV."""
    with path.open(newline="", encoding="utf-8") as fh:
        lines = [line for line in fh if not line.startswith("#")]
    return list(csv.DictReader(lines))


def _target_modifiers_by_key(
    fixture_rows: list[dict[str, str]],
) -> dict[tuple[str, str], list[dict[str, str]]]:
    """Map ``(phenopacket_id, hpo_id) -> target modifiers`` from fixture rows."""
    targets: dict[tuple[str, str], list[dict[str, str]]] = {}
    for row in fixture_rows:
        phenopacket_id = f"phenopacket-{row['individual_id']}"
        key = (phenopacket_id, row["hpo_id"])
        targets[key] = _parse_laterality(row["laterality_value"])
    return targets


def _restore_and_journal(
    conn: Connection,
    revision_id: str,
    *,
    table: str,
    column: str,
    id_column: str,
    id_expr: str,
    phenopacket_id_expr: str,
    join_clause: str,
    targets: dict[tuple[str, str], list[dict[str, str]]],
) -> dict[str, int]:
    """Backfill laterality modifiers for one table, journalling every changed row.

    For each row whose ``phenopacket_id`` appears in ``targets``: for every
    ``phenotypicFeatures`` entry whose ``type.id`` matches a fixture key,
    compare its current ``modifiers`` against the fixture's resolved value:

    * empty modifiers -> backfilled (written);
    * modifiers already equal (as an id set) to the target -> left alone,
      counted as already-correct;
    * modifiers present and different -> left alone, counted as a
      disagreement and reported, never overwritten.

    Fixture keys with no matching record, or no matching feature within a
    matching record, are counted as unmatched.
    """
    wanted_phenopacket_ids = sorted({pid for pid, _ in targets})
    if not wanted_phenopacket_ids:
        return {
            "backfilled": 0,
            "already_correct": 0,
            "disagreement": 0,
            "unmatched": 0,
        }

    rows = conn.execute(
        text(
            f"SELECT {id_expr} AS row_id, {phenopacket_id_expr} AS phenopacket_id, "
            f"t.{column}->'phenotypicFeatures' AS features "
            f"FROM {table} AS t {join_clause} "
            f"WHERE {phenopacket_id_expr} = ANY(:ids)"
        ),
        {"ids": wanted_phenopacket_ids},
    ).fetchall()

    seen_keys: set[tuple[str, str]] = set()
    backfilled = 0
    already_correct = 0
    disagreement = 0
    disagreement_details: list[str] = []

    for row in rows:
        features = row.features or []
        changed = False
        new_features = []
        for feature in features:
            hpo_id = (feature.get("type") or {}).get("id")
            key = (row.phenopacket_id, hpo_id)
            target = targets.get(key)
            if target is None:
                new_features.append(feature)
                continue

            seen_keys.add(key)
            existing = feature.get("modifiers") or []
            existing_ids = {m["id"] for m in existing}
            target_ids = {m["id"] for m in target}

            if not existing_ids:
                backfilled += 1
                changed = True
                new_feature = dict(feature)
                new_feature["modifiers"] = [dict(m) for m in target]
                new_features.append(new_feature)
            elif existing_ids == target_ids:
                already_correct += 1
                new_features.append(feature)
            else:
                disagreement += 1
                disagreement_details.append(
                    f"{row.phenopacket_id} {hpo_id}: stored {sorted(existing_ids)} "
                    f"!= source {sorted(target_ids)}"
                )
                new_features.append(feature)

        if changed:
            preimage = features
            postimage = new_features
            # postimage_sha MUST be computed by Postgres's own `::text` cast
            # of the JUST-WRITTEN jsonb value, via RETURNING -- not by
            # hashing Python's json.dumps() serialization, which does not
            # byte-for-byte match jsonb's own text representation (key
            # ordering / whitespace differ) and would make every downgrade
            # verification fail with a false mismatch.
            postimage_sha = conn.execute(
                text(
                    f"UPDATE {table} AS t SET {column} = jsonb_set("
                    f"t.{column}, '{{phenotypicFeatures}}', cast(:features as jsonb)) "
                    f"WHERE t.{id_column} = :row_id "
                    f"RETURNING md5((t.{column} -> 'phenotypicFeatures')::text)"
                ),
                {"features": json.dumps(postimage), "row_id": row.row_id},
            ).scalar_one()
            conn.execute(
                text(
                    "INSERT INTO ontology_migration_journal "
                    "(revision, table_name, row_id, json_path, preimage, postimage_sha) "
                    "VALUES (:revision, :table_name, :row_id, 'phenotypicFeatures', "
                    "cast(:preimage as jsonb), :postimage_sha)"
                ),
                {
                    "revision": revision_id,
                    "table_name": table,
                    "row_id": str(row.row_id),
                    "preimage": json.dumps(preimage),
                    "postimage_sha": postimage_sha,
                },
            )

    unmatched = len(set(targets) - seen_keys)
    if disagreement_details:
        # Surfaced via exception context / logs, never silently dropped --
        # printed so `alembic upgrade` output records exactly what a
        # curator needs to review.
        print(  # noqa: T201 -- deliberate migration-time visibility
            f"ontology laterality restore ({table}): {disagreement} disagreement(s):\n"
            + "\n".join(disagreement_details)
        )

    return {
        "backfilled": backfilled,
        "already_correct": already_correct,
        "disagreement": disagreement,
        "unmatched": unmatched,
    }


_RESTORE_FROM_JOURNAL_SQL = """
UPDATE {table} AS t
SET {column} = jsonb_set(t.{column}, ARRAY['phenotypicFeatures'], j.preimage)
FROM ontology_migration_journal j
WHERE j.revision = :revision
  AND j.table_name = '{table}'
  AND j.json_path = 'phenotypicFeatures'
  AND j.row_id = t.{id_column}::text
  AND md5((t.{column} -> 'phenotypicFeatures')::text) = j.postimage_sha
RETURNING t.{id_column}
"""


_JOURNAL_ROW_COUNT_FOR_REVISION_SQL = (
    "SELECT count(*) FROM ontology_migration_journal WHERE revision = :revision"
)


def apply_restoration(
    conn: Connection,
    revision_id: str,
    fixture_rows: list[dict[str, str]] | None = None,
) -> dict[str, dict[str, int]]:
    """Apply the laterality backfill to both stored copies. Returns per-table counts.

    ``fixture_rows`` defaults to the committed CSV (``load_fixture()``); the
    parameter exists so ``tests/test_laterality_backfill.py`` can inject a
    seeded, synthetic fixture instead of depending on the real corpus.

    Refuses (raises ``RuntimeError``) if ``revision_id`` already has journal
    rows -- see module docstring "Re-running upgrade() safely". Against an
    already-restored corpus every feature takes the ``already_correct``
    branch and nothing gets (re-)journalled, so an unguarded second
    application combined with an unconditional clear-first would destroy the
    first application's 594 preimage rows with nothing to replace them.
    """
    existing = conn.execute(
        text(_JOURNAL_ROW_COUNT_FOR_REVISION_SQL), {"revision": revision_id}
    ).scalar_one()
    if existing:
        raise RuntimeError(
            f"Refusing to apply 18cfc57307f6's laterality restoration: "
            f"ontology_migration_journal already has {existing} row(s) for "
            f"revision {revision_id!r}. This means upgrade() already ran and "
            f"was never followed by a successful downgrade() (which clears "
            f"its own journal rows once every one of them restores cleanly) "
            f"-- applying the restoration again would journal nothing for "
            f"already-backfilled features while the true original preimage "
            f"remains only in the existing journal rows. Run downgrade() "
            f"first, or clear this revision's rows from "
            f"ontology_migration_journal deliberately if you are certain "
            f"they are stale."
        )

    if fixture_rows is None:
        fixture_rows = load_fixture()
    targets = _target_modifiers_by_key(fixture_rows)

    working = _restore_and_journal(
        conn,
        revision_id,
        table="phenopackets",
        column="phenopacket",
        id_column="id",
        id_expr="t.id",
        phenopacket_id_expr="t.phenopacket_id",
        join_clause="",
        targets=targets,
    )
    head = _restore_and_journal(
        conn,
        revision_id,
        table="phenopacket_revisions",
        column="content_jsonb",
        id_column="id",
        # The SELECT always aliases the primary FROM table as `t` -- see
        # _restore_and_journal's query template -- so this must reference
        # `t.id` (the revision row), not `r.id`.
        id_expr="t.id",
        phenopacket_id_expr="p.phenopacket_id",
        join_clause="JOIN phenopackets p ON p.head_published_revision_id = t.id",
        targets=targets,
    )

    total_seen = (
        working["backfilled"] + working["already_correct"] + working["disagreement"]
    )
    total_seen += working["unmatched"]
    if total_seen != len(fixture_rows):
        raise RuntimeError(
            f"Laterality restoration join is lossy: accounted for {total_seen} of "
            f"{len(fixture_rows)} fixture rows on phenopackets (working copy)."
        )

    return {"phenopackets": working, "phenopacket_revisions": head}


_JOURNAL_ROW_IDS_SQL = """
SELECT row_id FROM ontology_migration_journal
WHERE revision = :revision AND table_name = :table_name
  AND json_path = 'phenotypicFeatures'
"""


def restore_from_journal(conn: Connection, revision_id: str) -> dict[str, int]:
    """Restore every laterality journal row for ``revision_id``, both tables.

    Aborts (raises ``RuntimeError``) instead of returning a partial count if
    any journalled row could not be restored -- its current value no longer
    hashes to the recorded postimage (edited after this migration ran), or
    the row no longer exists. A silent partial downgrade would leave those
    rows migrated while Alembic still records the schema version as moved
    backward, and this function's own end-of-run journal clear (below) would
    then discard the only record of their true preimage on the very next
    successful ``upgrade()``, making it permanently unreachable.

    On full success this revision's own rows are deleted from
    ``ontology_migration_journal`` (the table itself is retained), so a
    subsequent ``upgrade()`` finds an empty journal and
    ``apply_restoration()``'s own guard lets it proceed -- see module
    docstring "Re-running upgrade() safely".
    """
    counts = {}
    skipped: list[str] = []
    for table, id_column in (("phenopackets", "id"), ("phenopacket_revisions", "id")):
        expected_row_ids = {
            row.row_id
            for row in conn.execute(
                text(_JOURNAL_ROW_IDS_SQL),
                {"revision": revision_id, "table_name": table},
            ).fetchall()
        }
        sql = _RESTORE_FROM_JOURNAL_SQL.format(
            table=table, column=_column_for(table), id_column=id_column
        )
        rows = conn.execute(text(sql), {"revision": revision_id}).fetchall()
        restored_row_ids = {str(row[0]) for row in rows}
        counts[table] = len(restored_row_ids)
        skipped.extend(
            f"{table}:{row_id}"
            for row_id in sorted(expected_row_ids - restored_row_ids)
        )

    if skipped:
        raise RuntimeError(
            f"Refusing to downgrade 18cfc57307f6: {len(skipped)} journalled "
            f"row(s) (revision {revision_id!r}) were skipped because their "
            f"current value no longer hashes to the recorded postimage "
            f"(edited after this migration ran), or the row no longer "
            f"exists: {skipped}. Downgrading anyway would leave these rows "
            f"migrated while Alembic records the schema version as moved "
            f"backward, and a later re-upgrade would clear the journal, "
            f"making their original preimage permanently unreachable. "
            f"Resolve the divergence manually before downgrading past this "
            f"revision."
        )

    conn.execute(text(_CLEAR_OWN_JOURNAL_ROWS_SQL), {"revision": revision_id})
    return counts


def _column_for(table: str) -> str:
    return "phenopacket" if table == "phenopackets" else "content_jsonb"


_CLEAR_OWN_JOURNAL_ROWS_SQL = (
    "DELETE FROM ontology_migration_journal "
    "WHERE revision = :revision AND json_path = 'phenotypicFeatures'"
)


def upgrade() -> None:
    conn = op.get_bind()
    # No unconditional clear here -- apply_restoration() refuses if this
    # revision's journal is non-empty. See module docstring "Re-running
    # upgrade() safely" (this used to unconditionally clear first, which
    # silently destroyed the journal on a second, unguarded upgrade()).
    apply_restoration(conn, revision)


def downgrade() -> None:
    conn = op.get_bind()
    restore_from_journal(conn, revision)
