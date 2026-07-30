"""Correct five wrong ontology terms stored in the corpus.

docs/ontology-defect-report-2026-07-30.md T2-T5 and
docs/superpowers/plans/2026-07-30-ontology-data-quality.md Task 3.

Corrects, in both authoritative copies of every affected record:

* T2/T3 -- ``MONDO:0011593`` ("seizures, benign familial infantile, 2") and
  ``MONDO:0010953`` ("Fanconi anemia complementation group E") collapse to
  ``MONDO:0007669`` ("renal cysts and diabetes syndrome" / RCAD -- the actual
  HNF1B disease). A record holding both collapses to one entry.
* T4 -- ``HP:0034199`` ("Late first trimester onset") is replaced by
  ``HP:0003577`` / "Congenital onset", the term the source's own
  ``Phenotype_modifier`` sheet lists "Prenatal onset" as a synonym of.
* T5 -- ``HP:0003674`` keeps its id (the abstract "Onset" parent -- HPO has no
  discrete postnatal-onset term) but its label is corrected to "Onset"; the
  stored label "Postnatal onset" claimed a specificity the id does not carry.

Scope decision (plan Task 3 Step 2): only each record's *working copy*
(``phenopackets.phenopacket``) and its *head-published revision*
(``phenopacket_revisions.content_jsonb`` at ``head_published_revision_id``)
are rewritten. Older revision rows are immutable history and are correct as
history; they are deliberately left untouched. ``app/ontology/conformance``'s
A3 scope matches this decision -- it only ever reads working copies and head
revisions, never the full revision history, so a corrected term does not
turn A3 permanently red the moment history legitimately disagrees with it.

Path scope -- larger than the plan's Task 3 Step 4 text.
--------------------------------------------------------

Step 4, as written, names two locations: ``diseases[].onset.ontologyClass``
and ``subject.timeAtLastEncounter.ontologyClass``. Proving the SQL against
the live database (per the controller's instruction, in a rolled-back
transaction) surfaced three more locations carrying the same two wrong ids,
found by a recursive walk of every stored document rather than by guessing
paths one at a time:

  interpretations[].diagnosis.disease.id       440   MONDO:0011593 only
  phenotypicFeatures[].onset.ontologyClass.id  976   HP:0034199 / HP:0003674
  phenotypicFeatures[].onset.age.ontologyClass.id
                                                275   HP:0034199 / HP:0003674 (a
                                                      second, independent copy
                                                      of the onset id nested
                                                      under the feature's
                                                      ``onset.age`` key -- 10
                                                      features hold two
                                                      *disagreeing* onset ids
                                                      between the two
                                                      locations, so each is
                                                      corrected from its own
                                                      stored value, never
                                                      copied from its sibling)

``interpretations[].diagnosis.disease`` traces to the same
``AgeParser.parse_age()`` call site as ``diseases[].onset`` and
``subject.timeAtLastEncounter``
(``migration/phenopackets/extractors.py``/``builder_simple.py``): one
``AgeOnset`` cell is parsed once per source row and stamped onto every
phenotypic feature built from that row, so the defect's true footprint is
every onset location the importer writes, not only the two the original
audit sampled. Leaving the other three unfixed would also leave
``app.ontology.conformance.ONTOLOGY_PATHS`` (which already lists
``phenotypicFeatures[].onset.ontologyClass`` and
``interpretations[].diagnosis.disease``) permanently red on this corpus, and
the Task 5 preflight script would never exit zero. A validated exhaustive
substring scan of every stored document confirms zero remaining occurrences
of ``HP:0034199``, ``MONDO:0011593`` or ``MONDO:0010953`` in either copy
after this migration, at any path.

``app/ontology/conformance.ONTOLOGY_PATHS`` is extended in this same commit
to add ``phenotypicFeatures[].onset.age.ontologyClass`` -- the one location
above it did not already enumerate -- so Task 5's preflight coverage matches
what this migration actually touches.

Reversibility
-------------

The disease-array collapse destroys which record held which term (two
entries dedupe to one), so downgrade cannot be a name-based inverse remap.
This revision creates ``ontology_migration_journal`` and writes one row per
(table, row, top-level json key) touched, with the pre-correction value of
that *whole* top-level key (``diseases`` / ``subject`` / ``interpretations``
/ ``phenotypicFeatures``) as ``preimage`` and a hash of the corrected value
as ``postimage_sha``. Downgrade restores each journalled row only after
verifying the row's current value still hashes to its recorded
``postimage_sha`` -- so a curator edit made after this migration is left
alone rather than silently clobbered. Restoring the diseases key must always
happen last on downgrade, from ``diseases`` journal rows, and NOT be
re-derived by inverting the id map, since the id map alone cannot know which
of the two collapsed entries -- if any -- a given record originally had.

The journal *table* is retained after downgrade, deliberately: it is
infrastructure in the same permanent-raw-SQL-table family as
``hpo_terms_lookup``, not schema this revision owns end-to-end, and Task 4's
migration reuses it. Dropping it on downgrade would also destroy the audit
trail of any later migration's journal rows. This revision's own *rows* in
it, however, are deleted once ``restore_from_journal`` finishes restoring
every one of them -- see "Re-running upgrade() safely" below for why.

``restore_from_journal`` also aborts (raises) rather than silently returning
a partial count if any journalled row was skipped -- see its docstring.

Re-running upgrade() safely
----------------------------

``apply_corrections`` used to be paired with an unconditional
``DELETE FROM ontology_migration_journal WHERE revision = :revision`` in
``upgrade()``, to make a downgrade -> upgrade cycle re-journal cleanly. That
is correct for downgrade -> upgrade, but not for upgrade -> upgrade: calling
``upgrade()`` a second time without an intervening ``downgrade()`` (e.g.
``alembic stamp`` to an earlier revision then ``upgrade``, or a backup
restored against a stale ``alembic_version``) would delete the *first*
upgrade's journal rows -- the only record of the true pre-correction preimage
-- and re-run the correction against already-corrected data. Most
corrections are no-ops the second time (their ``EXISTS`` candidates are
already gone), so most of the original journal is destroyed with nothing
re-journalled in its place; the ``onset_abstract`` (``HP:0003674``) branch
additionally re-matches on id even though only its label changed the first
time, so some rows get re-journalled carrying an *already-corrected* value as
their recorded "preimage" -- silently wrong, not just silently missing.

``apply_corrections`` therefore refuses (raises ``RuntimeError``) if this
revision already has any journal rows when it is called, instead of
clearing them. ``restore_from_journal`` is the only thing that clears this
revision's journal rows now, and only after confirming every one of them
restored cleanly (see its own docstring) -- so the journal is non-empty
exactly when the corpus is in the post-``upgrade()`` state, and empty
exactly when it is safe to ``upgrade()`` again.

``ontology_migration_journal`` is registered in ``alembic/env.py``'s
``include_object`` and in
``tests/test_alembic_env_autogenerate.py::_RAW_SQL_TABLES`` in this same
commit.

Every id/label literal below is redeclared inline rather than imported from
application code: a migration file is a frozen snapshot of what it did, and
must not silently change behaviour if some other module is edited later.

Revision ID: efa98cccfa51
Revises: d4e8b1f60a27
Create Date: 2026-07-30 20:43:01.041075
"""

import json
from typing import Sequence, Union

from sqlalchemy import text
from sqlalchemy.engine import Connection

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "efa98cccfa51"
down_revision: Union[str, Sequence[str], None] = "d4e8b1f60a27"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# --- correction constants (redeclared inline; see module docstring) ---
MONDO_WRONG_1 = "MONDO:0011593"  # seizures, benign familial infantile, 2
MONDO_WRONG_2 = "MONDO:0010953"  # Fanconi anemia complementation group E
MONDO_RIGHT_ID = "MONDO:0007669"
MONDO_RIGHT_LABEL = "renal cysts and diabetes syndrome"

ONSET_WRONG_PRENATAL = "HP:0034199"  # actually "Late first trimester onset"
ONSET_CONGENITAL_ID = "HP:0003577"
ONSET_CONGENITAL_LABEL = "Congenital onset"
ONSET_ABSTRACT_ID = "HP:0003674"  # id is correct and unchanged
ONSET_ABSTRACT_LABEL = "Onset"  # label is corrected from "Postnatal onset"

# IF NOT EXISTS: the journal table is retained on downgrade (see module
# docstring), so a downgrade -> upgrade cycle must not fail trying to
# recreate a table that is still there.
_JOURNAL_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS ontology_migration_journal (
    id             bigserial PRIMARY KEY,
    revision       text NOT NULL,
    table_name     text NOT NULL,
    row_id         text NOT NULL,
    json_path      text NOT NULL,
    preimage       jsonb NOT NULL,
    postimage_sha  text NOT NULL
)
"""
_JOURNAL_INDEX_SQL = (
    "CREATE INDEX IF NOT EXISTS ix_omj_lookup ON ontology_migration_journal "
    "(revision, table_name, row_id)"
)

# restore_from_journal() runs this once every journalled row for this
# revision has been confirmed restored, so a later upgrade() finds an empty
# journal and apply_corrections()'s own guard (see its docstring) lets it
# proceed. NOT run by upgrade() itself -- see module docstring "Re-running
# upgrade() safely" for why clearing here unconditionally, before
# re-applying, silently destroyed the only record of the true preimage on a
# second, unguarded upgrade().
_CLEAR_OWN_JOURNAL_ROWS_SQL = (
    "DELETE FROM ontology_migration_journal WHERE revision = :revision"
)

_JOURNAL_INSERT_SQL = """
INSERT INTO ontology_migration_journal
    (revision, table_name, row_id, json_path, preimage, postimage_sha)
VALUES (:revision, :table_name, :row_id, :json_path, cast(:preimage as jsonb), :postimage_sha)
"""


# ---------------------------------------------------------------------------
# Correction 1: diseases[] -- MONDO collapse + onset remap + dedupe.
# ---------------------------------------------------------------------------
# Combines the term collapse and the onset remap into one pass over the
# array so a record needing both is journalled once, not twice. Dedup keeps
# the first occurrence by ordinality (`jsonb_agg(DISTINCT e ORDER BY ord)` is
# invalid PostgreSQL -- the ORDER BY expression is not the DISTINCT
# argument), matching plan Task 3 Step 3.
_DISEASES_WORKING_SQL = """
WITH candidates AS (
    SELECT t.id, t.phenopacket->'diseases' AS preimage
    FROM phenopackets t
    WHERE EXISTS (
        SELECT 1 FROM jsonb_array_elements(t.phenopacket->'diseases') d
        WHERE d->'term'->>'id' IN (:mondo_1, :mondo_2)
           OR d->'onset'->'ontologyClass'->>'id' IN (:onset_wrong, :onset_abstract)
    )
),
updated AS (
    UPDATE phenopackets AS t
    SET phenopacket = jsonb_set(t.phenopacket, '{diseases}', (
        SELECT jsonb_agg(e ORDER BY ord)
        FROM (
            SELECT DISTINCT ON (e) e, ord
            FROM (
                SELECT
                    CASE
                        WHEN mapped_term->'onset'->'ontologyClass'->>'id' = :onset_wrong
                        THEN jsonb_set(mapped_term, '{onset,ontologyClass}',
                                 jsonb_build_object('id', cast(:congenital_id as text),
                                                     'label', cast(:congenital_label as text)))
                        WHEN mapped_term->'onset'->'ontologyClass'->>'id' = :onset_abstract
                        THEN jsonb_set(mapped_term, '{onset,ontologyClass}',
                                 jsonb_build_object('id', cast(:onset_abstract as text),
                                                     'label', cast(:onset_abstract_label as text)))
                        ELSE mapped_term
                    END AS e, ord
                FROM (
                    SELECT
                        CASE
                            WHEN d->'term'->>'id' IN (:mondo_1, :mondo_2)
                            THEN jsonb_set(d, '{term}',
                                     jsonb_build_object('id', cast(:mondo_right_id as text),
                                                         'label', cast(:mondo_right_label as text)))
                            ELSE d
                        END AS mapped_term, ord
                    FROM jsonb_array_elements(t.phenopacket->'diseases') WITH ORDINALITY AS a(d, ord)
                ) step1
            ) step2
            ORDER BY e, ord
        ) deduped
    ))
    FROM candidates c
    WHERE t.id = c.id
    RETURNING t.id, t.phenopacket->'diseases' AS postimage
)
SELECT c.id::text AS row_id, c.preimage, md5(u.postimage::text) AS postimage_sha
FROM candidates c JOIN updated u ON u.id = c.id
"""

_DISEASES_HEAD_SQL = """
WITH candidates AS (
    SELECT r.id AS rid, r.content_jsonb->'diseases' AS preimage
    FROM phenopacket_revisions r
    JOIN phenopackets p ON p.head_published_revision_id = r.id
    WHERE EXISTS (
        SELECT 1 FROM jsonb_array_elements(r.content_jsonb->'diseases') d
        WHERE d->'term'->>'id' IN (:mondo_1, :mondo_2)
           OR d->'onset'->'ontologyClass'->>'id' IN (:onset_wrong, :onset_abstract)
    )
),
updated AS (
    UPDATE phenopacket_revisions AS r
    SET content_jsonb = jsonb_set(r.content_jsonb, '{diseases}', (
        SELECT jsonb_agg(e ORDER BY ord)
        FROM (
            SELECT DISTINCT ON (e) e, ord
            FROM (
                SELECT
                    CASE
                        WHEN mapped_term->'onset'->'ontologyClass'->>'id' = :onset_wrong
                        THEN jsonb_set(mapped_term, '{onset,ontologyClass}',
                                 jsonb_build_object('id', cast(:congenital_id as text),
                                                     'label', cast(:congenital_label as text)))
                        WHEN mapped_term->'onset'->'ontologyClass'->>'id' = :onset_abstract
                        THEN jsonb_set(mapped_term, '{onset,ontologyClass}',
                                 jsonb_build_object('id', cast(:onset_abstract as text),
                                                     'label', cast(:onset_abstract_label as text)))
                        ELSE mapped_term
                    END AS e, ord
                FROM (
                    SELECT
                        CASE
                            WHEN d->'term'->>'id' IN (:mondo_1, :mondo_2)
                            THEN jsonb_set(d, '{term}',
                                     jsonb_build_object('id', cast(:mondo_right_id as text),
                                                         'label', cast(:mondo_right_label as text)))
                            ELSE d
                        END AS mapped_term, ord
                    FROM jsonb_array_elements(r.content_jsonb->'diseases') WITH ORDINALITY AS a(d, ord)
                ) step1
            ) step2
            ORDER BY e, ord
        ) deduped
    ))
    FROM candidates c
    WHERE r.id = c.rid
    RETURNING r.id, r.content_jsonb->'diseases' AS postimage
)
SELECT c.rid::text AS row_id, c.preimage, md5(u.postimage::text) AS postimage_sha
FROM candidates c JOIN updated u ON u.id = c.rid
"""


# ---------------------------------------------------------------------------
# Correction 2: subject.timeAtLastEncounter.ontologyClass -- scalar, not an
# array. A plain jsonb_set on the fixed path (plan amendment hazard #2).
# ---------------------------------------------------------------------------
_SUBJECT_WORKING_SQL = """
WITH candidates AS (
    SELECT t.id, t.phenopacket->'subject' AS preimage
    FROM phenopackets t
    WHERE t.phenopacket #>> '{subject,timeAtLastEncounter,ontologyClass,id}'
          IN (:onset_wrong, :onset_abstract)
),
updated AS (
    UPDATE phenopackets AS t
    SET phenopacket = CASE
        WHEN t.phenopacket #>> '{subject,timeAtLastEncounter,ontologyClass,id}' = :onset_wrong
        THEN jsonb_set(t.phenopacket, '{subject,timeAtLastEncounter,ontologyClass}',
                 jsonb_build_object('id', cast(:congenital_id as text), 'label', cast(:congenital_label as text)))
        WHEN t.phenopacket #>> '{subject,timeAtLastEncounter,ontologyClass,id}' = :onset_abstract
        THEN jsonb_set(t.phenopacket, '{subject,timeAtLastEncounter,ontologyClass}',
                 jsonb_build_object('id', cast(:onset_abstract as text), 'label', cast(:onset_abstract_label as text)))
        ELSE t.phenopacket
    END
    FROM candidates c
    WHERE t.id = c.id
    RETURNING t.id, t.phenopacket->'subject' AS postimage
)
SELECT c.id::text AS row_id, c.preimage, md5(u.postimage::text) AS postimage_sha
FROM candidates c JOIN updated u ON u.id = c.id
"""

_SUBJECT_HEAD_SQL = """
WITH candidates AS (
    SELECT r.id AS rid, r.content_jsonb->'subject' AS preimage
    FROM phenopacket_revisions r
    JOIN phenopackets p ON p.head_published_revision_id = r.id
    WHERE r.content_jsonb #>> '{subject,timeAtLastEncounter,ontologyClass,id}'
          IN (:onset_wrong, :onset_abstract)
),
updated AS (
    UPDATE phenopacket_revisions AS r
    SET content_jsonb = CASE
        WHEN r.content_jsonb #>> '{subject,timeAtLastEncounter,ontologyClass,id}' = :onset_wrong
        THEN jsonb_set(r.content_jsonb, '{subject,timeAtLastEncounter,ontologyClass}',
                 jsonb_build_object('id', cast(:congenital_id as text), 'label', cast(:congenital_label as text)))
        WHEN r.content_jsonb #>> '{subject,timeAtLastEncounter,ontologyClass,id}' = :onset_abstract
        THEN jsonb_set(r.content_jsonb, '{subject,timeAtLastEncounter,ontologyClass}',
                 jsonb_build_object('id', cast(:onset_abstract as text), 'label', cast(:onset_abstract_label as text)))
        ELSE r.content_jsonb
    END
    FROM candidates c
    WHERE r.id = c.rid
    RETURNING r.id, r.content_jsonb->'subject' AS postimage
)
SELECT c.rid::text AS row_id, c.preimage, md5(u.postimage::text) AS postimage_sha
FROM candidates c JOIN updated u ON u.id = c.rid
"""


# ---------------------------------------------------------------------------
# Correction 3: phenotypicFeatures[].onset -- both the bare
# `.ontologyClass` location and the independent, sometimes-disagreeing copy
# nested under `.age.ontologyClass` (see module docstring). One pass over
# the array, both sub-locations fixed from their own stored value.
# ---------------------------------------------------------------------------
_FEATURES_ONSET_WORKING_SQL = """
WITH candidates AS (
    SELECT t.id, t.phenopacket->'phenotypicFeatures' AS preimage
    FROM phenopackets t
    WHERE EXISTS (
        SELECT 1 FROM jsonb_array_elements(t.phenopacket->'phenotypicFeatures') f
        WHERE f->'onset'->'ontologyClass'->>'id' IN (:onset_wrong, :onset_abstract)
           OR f->'onset'->'age'->'ontologyClass'->>'id' IN (:onset_wrong, :onset_abstract)
    )
),
updated AS (
    UPDATE phenopackets AS t
    SET phenopacket = jsonb_set(t.phenopacket, '{phenotypicFeatures}', (
        SELECT jsonb_agg(g ORDER BY ord)
        FROM (
            SELECT
                CASE
                    WHEN step1->'onset'->'age'->'ontologyClass'->>'id' = :onset_wrong
                    THEN jsonb_set(step1, '{onset,age,ontologyClass}',
                             jsonb_build_object('id', cast(:congenital_id as text), 'label', cast(:congenital_label as text)))
                    WHEN step1->'onset'->'age'->'ontologyClass'->>'id' = :onset_abstract
                    THEN jsonb_set(step1, '{onset,age,ontologyClass}',
                             jsonb_build_object('id', cast(:onset_abstract as text), 'label', cast(:onset_abstract_label as text)))
                    ELSE step1
                END AS g, ord
            FROM (
                SELECT
                    CASE
                        WHEN f->'onset'->'ontologyClass'->>'id' = :onset_wrong
                        THEN jsonb_set(f, '{onset,ontologyClass}',
                                 jsonb_build_object('id', cast(:congenital_id as text), 'label', cast(:congenital_label as text)))
                        WHEN f->'onset'->'ontologyClass'->>'id' = :onset_abstract
                        THEN jsonb_set(f, '{onset,ontologyClass}',
                                 jsonb_build_object('id', cast(:onset_abstract as text), 'label', cast(:onset_abstract_label as text)))
                        ELSE f
                    END AS step1, ord
                FROM jsonb_array_elements(t.phenopacket->'phenotypicFeatures') WITH ORDINALITY AS a(f, ord)
            ) inner1
        ) inner2
    ))
    FROM candidates c
    WHERE t.id = c.id
    RETURNING t.id, t.phenopacket->'phenotypicFeatures' AS postimage
)
SELECT c.id::text AS row_id, c.preimage, md5(u.postimage::text) AS postimage_sha
FROM candidates c JOIN updated u ON u.id = c.id
"""

_FEATURES_ONSET_HEAD_SQL = """
WITH candidates AS (
    SELECT r.id AS rid, r.content_jsonb->'phenotypicFeatures' AS preimage
    FROM phenopacket_revisions r
    JOIN phenopackets p ON p.head_published_revision_id = r.id
    WHERE EXISTS (
        SELECT 1 FROM jsonb_array_elements(r.content_jsonb->'phenotypicFeatures') f
        WHERE f->'onset'->'ontologyClass'->>'id' IN (:onset_wrong, :onset_abstract)
           OR f->'onset'->'age'->'ontologyClass'->>'id' IN (:onset_wrong, :onset_abstract)
    )
),
updated AS (
    UPDATE phenopacket_revisions AS r
    SET content_jsonb = jsonb_set(r.content_jsonb, '{phenotypicFeatures}', (
        SELECT jsonb_agg(g ORDER BY ord)
        FROM (
            SELECT
                CASE
                    WHEN step1->'onset'->'age'->'ontologyClass'->>'id' = :onset_wrong
                    THEN jsonb_set(step1, '{onset,age,ontologyClass}',
                             jsonb_build_object('id', cast(:congenital_id as text), 'label', cast(:congenital_label as text)))
                    WHEN step1->'onset'->'age'->'ontologyClass'->>'id' = :onset_abstract
                    THEN jsonb_set(step1, '{onset,age,ontologyClass}',
                             jsonb_build_object('id', cast(:onset_abstract as text), 'label', cast(:onset_abstract_label as text)))
                    ELSE step1
                END AS g, ord
            FROM (
                SELECT
                    CASE
                        WHEN f->'onset'->'ontologyClass'->>'id' = :onset_wrong
                        THEN jsonb_set(f, '{onset,ontologyClass}',
                                 jsonb_build_object('id', cast(:congenital_id as text), 'label', cast(:congenital_label as text)))
                        WHEN f->'onset'->'ontologyClass'->>'id' = :onset_abstract
                        THEN jsonb_set(f, '{onset,ontologyClass}',
                                 jsonb_build_object('id', cast(:onset_abstract as text), 'label', cast(:onset_abstract_label as text)))
                        ELSE f
                    END AS step1, ord
                FROM jsonb_array_elements(r.content_jsonb->'phenotypicFeatures') WITH ORDINALITY AS a(f, ord)
            ) inner1
        ) inner2
    ))
    FROM candidates c
    WHERE r.id = c.rid
    RETURNING r.id, r.content_jsonb->'phenotypicFeatures' AS postimage
)
SELECT c.rid::text AS row_id, c.preimage, md5(u.postimage::text) AS postimage_sha
FROM candidates c JOIN updated u ON u.id = c.rid
"""


# ---------------------------------------------------------------------------
# Correction 4: interpretations[].diagnosis.disease -- flat {id,label}, no
# onset, no dedup: every stored value is MONDO:0011593.
# ---------------------------------------------------------------------------
_INTERPRETATIONS_WORKING_SQL = """
WITH candidates AS (
    SELECT t.id, t.phenopacket->'interpretations' AS preimage
    FROM phenopackets t
    WHERE EXISTS (
        SELECT 1 FROM jsonb_array_elements(t.phenopacket->'interpretations') i
        WHERE i->'diagnosis'->'disease'->>'id' IN (:mondo_1, :mondo_2)
    )
),
updated AS (
    UPDATE phenopackets AS t
    SET phenopacket = jsonb_set(t.phenopacket, '{interpretations}', (
        SELECT jsonb_agg(
                   CASE
                       WHEN i->'diagnosis'->'disease'->>'id' IN (:mondo_1, :mondo_2)
                       THEN jsonb_set(i, '{diagnosis,disease}',
                                jsonb_build_object('id', cast(:mondo_right_id as text), 'label', cast(:mondo_right_label as text)))
                       ELSE i
                   END
                   ORDER BY ord
               )
        FROM jsonb_array_elements(t.phenopacket->'interpretations') WITH ORDINALITY AS a(i, ord)
    ))
    FROM candidates c
    WHERE t.id = c.id
    RETURNING t.id, t.phenopacket->'interpretations' AS postimage
)
SELECT c.id::text AS row_id, c.preimage, md5(u.postimage::text) AS postimage_sha
FROM candidates c JOIN updated u ON u.id = c.id
"""

_INTERPRETATIONS_HEAD_SQL = """
WITH candidates AS (
    SELECT r.id AS rid, r.content_jsonb->'interpretations' AS preimage
    FROM phenopacket_revisions r
    JOIN phenopackets p ON p.head_published_revision_id = r.id
    WHERE EXISTS (
        SELECT 1 FROM jsonb_array_elements(r.content_jsonb->'interpretations') i
        WHERE i->'diagnosis'->'disease'->>'id' IN (:mondo_1, :mondo_2)
    )
),
updated AS (
    UPDATE phenopacket_revisions AS r
    SET content_jsonb = jsonb_set(r.content_jsonb, '{interpretations}', (
        SELECT jsonb_agg(
                   CASE
                       WHEN i->'diagnosis'->'disease'->>'id' IN (:mondo_1, :mondo_2)
                       THEN jsonb_set(i, '{diagnosis,disease}',
                                jsonb_build_object('id', cast(:mondo_right_id as text), 'label', cast(:mondo_right_label as text)))
                       ELSE i
                   END
                   ORDER BY ord
               )
        FROM jsonb_array_elements(r.content_jsonb->'interpretations') WITH ORDINALITY AS a(i, ord)
    ))
    FROM candidates c
    WHERE r.id = c.rid
    RETURNING r.id, r.content_jsonb->'interpretations' AS postimage
)
SELECT c.rid::text AS row_id, c.preimage, md5(u.postimage::text) AS postimage_sha
FROM candidates c JOIN updated u ON u.id = c.rid
"""


_PARAMS = {
    "mondo_1": MONDO_WRONG_1,
    "mondo_2": MONDO_WRONG_2,
    "mondo_right_id": MONDO_RIGHT_ID,
    "mondo_right_label": MONDO_RIGHT_LABEL,
    "onset_wrong": ONSET_WRONG_PRENATAL,
    "congenital_id": ONSET_CONGENITAL_ID,
    "congenital_label": ONSET_CONGENITAL_LABEL,
    "onset_abstract": ONSET_ABSTRACT_ID,
    "onset_abstract_label": ONSET_ABSTRACT_LABEL,
}

# (json_path / journal label, working-copy SQL, head-revision SQL)
_CORRECTIONS: list[tuple[str, str, str]] = [
    ("diseases", _DISEASES_WORKING_SQL, _DISEASES_HEAD_SQL),
    ("subject", _SUBJECT_WORKING_SQL, _SUBJECT_HEAD_SQL),
    ("phenotypicFeatures", _FEATURES_ONSET_WORKING_SQL, _FEATURES_ONSET_HEAD_SQL),
    ("interpretations", _INTERPRETATIONS_WORKING_SQL, _INTERPRETATIONS_HEAD_SQL),
]


_JOURNAL_ROW_COUNT_FOR_REVISION_SQL = (
    "SELECT count(*) FROM ontology_migration_journal WHERE revision = :revision"
)


def apply_corrections(conn: Connection, revision_id: str) -> dict[str, int]:
    """Apply all five term corrections to both stored copies, journalling each row.

    Returns a ``{json_path: rows_touched}`` count per correction, summed over
    both tables, for callers (tests, this module's ``upgrade``) to assert
    against.

    Refuses (raises ``RuntimeError``) if ``revision_id`` already has journal
    rows -- see module docstring "Re-running upgrade() safely". A second,
    unguarded application would destroy the first application's journalled
    preimages (most corrections are no-ops the second time and would
    silently drop out of a naive clear-and-reapply) and, for the
    ``onset_abstract`` id-based branch specifically, re-journal an
    already-corrected value as if it were the original preimage.
    """
    existing = conn.execute(
        text(_JOURNAL_ROW_COUNT_FOR_REVISION_SQL), {"revision": revision_id}
    ).scalar_one()
    if existing:
        raise RuntimeError(
            f"Refusing to apply efa98cccfa51's corrections: "
            f"ontology_migration_journal already has {existing} row(s) for "
            f"revision {revision_id!r}. This means upgrade() already ran and "
            f"was never followed by a successful downgrade() (which clears "
            f"its own journal rows once every one of them restores cleanly) "
            f"-- applying the corrections again would destroy or corrupt the "
            f"existing journal rather than reflect the true original "
            f"preimage. Run downgrade() first, or clear this revision's rows "
            f"from ontology_migration_journal deliberately if you are certain "
            f"they are stale."
        )

    counts: dict[str, int] = {}
    for json_path, working_sql, head_sql in _CORRECTIONS:
        touched = 0
        for table_name, sql in (
            ("phenopackets", working_sql),
            ("phenopacket_revisions", head_sql),
        ):
            rows = conn.execute(text(sql), _PARAMS).fetchall()
            for row in rows:
                conn.execute(
                    text(_JOURNAL_INSERT_SQL),
                    {
                        "revision": revision_id,
                        "table_name": table_name,
                        "row_id": row.row_id,
                        "json_path": json_path,
                        "preimage": json.dumps(row.preimage),
                        "postimage_sha": row.postimage_sha,
                    },
                )
                touched += 1
        counts[json_path] = touched
    return counts


_RESTORE_WORKING_SQL = """
UPDATE phenopackets AS t
SET phenopacket = jsonb_set(t.phenopacket, ARRAY[j.json_path], j.preimage)
FROM ontology_migration_journal j
WHERE j.revision = :revision
  AND j.table_name = 'phenopackets'
  AND j.row_id = t.id::text
  AND j.json_path = :json_path
  AND md5((t.phenopacket -> j.json_path)::text) = j.postimage_sha
RETURNING t.id
"""

_RESTORE_HEAD_SQL = """
UPDATE phenopacket_revisions AS r
SET content_jsonb = jsonb_set(r.content_jsonb, ARRAY[j.json_path], j.preimage)
FROM ontology_migration_journal j
WHERE j.revision = :revision
  AND j.table_name = 'phenopacket_revisions'
  AND j.row_id = r.id::text
  AND j.json_path = :json_path
  AND md5((r.content_jsonb -> j.json_path)::text) = j.postimage_sha
RETURNING r.id
"""


_JOURNAL_ROW_IDS_SQL = """
SELECT row_id FROM ontology_migration_journal
WHERE revision = :revision AND table_name = :table_name AND json_path = :json_path
"""


def restore_from_journal(conn: Connection, revision_id: str) -> dict[str, int]:
    """Restore every journalled row for ``revision_id``, verifying postimage_sha first.

    A row whose current value no longer hashes to the recorded
    ``postimage_sha`` (a curator edited it after this migration ran) is left
    alone rather than clobbered -- see module docstring. Restores
    ``phenotypicFeatures`` and ``interpretations`` before ``diseases``, since
    the disease-array collapse is the one correction that destroys
    information the id map alone cannot re-derive; order does not matter for
    correctness here (each json_path is a disjoint top-level key) but keeps
    the more information-losing correction visually last.

    Aborts (raises ``RuntimeError``) instead of returning a partial count if
    any journalled row could not be restored -- i.e. its current value no
    longer hashes to the recorded postimage (edited after this migration
    ran), or the row no longer exists. A silent partial downgrade would leave
    those rows migrated while Alembic still records the schema version as
    moved backward, and this function's own end-of-run journal clear (below)
    would then discard the only record of their true preimage on the very
    next successful ``upgrade()``, making it permanently unreachable.

    On full success -- every journalled row for ``revision_id`` restored --
    this revision's own rows are deleted from ``ontology_migration_journal``
    (the table itself is retained; see module docstring "Re-running
    upgrade() safely"), so a subsequent ``upgrade()`` finds an empty journal
    and is allowed to re-apply cleanly.
    """
    counts: dict[str, int] = {}
    for json_path, _working_sql, _head_sql in reversed(_CORRECTIONS):
        touched = 0
        skipped: list[str] = []
        for table_name, sql in (
            ("phenopackets", _RESTORE_WORKING_SQL),
            ("phenopacket_revisions", _RESTORE_HEAD_SQL),
        ):
            expected_row_ids = {
                row.row_id
                for row in conn.execute(
                    text(_JOURNAL_ROW_IDS_SQL),
                    {
                        "revision": revision_id,
                        "table_name": table_name,
                        "json_path": json_path,
                    },
                ).fetchall()
            }
            restored_rows = conn.execute(
                text(sql), {"revision": revision_id, "json_path": json_path}
            ).fetchall()
            restored_row_ids = {str(row[0]) for row in restored_rows}
            touched += len(restored_row_ids)
            skipped.extend(
                f"{table_name}:{row_id}"
                for row_id in sorted(expected_row_ids - restored_row_ids)
            )
        if skipped:
            raise RuntimeError(
                f"Refusing to downgrade efa98cccfa51: {len(skipped)} "
                f"journalled row(s) for json_path={json_path!r} (revision "
                f"{revision_id!r}) were skipped because their current value "
                f"no longer hashes to the recorded postimage (edited after "
                f"this migration ran), or the row no longer exists: "
                f"{skipped}. Downgrading anyway would leave these rows "
                f"migrated while Alembic records the schema version as moved "
                f"backward, and a later re-upgrade would clear the journal, "
                f"making their original preimage permanently unreachable. "
                f"Resolve the divergence manually before downgrading past "
                f"this revision."
            )
        counts[json_path] = touched

    conn.execute(text(_CLEAR_OWN_JOURNAL_ROWS_SQL), {"revision": revision_id})
    return counts


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(text(_JOURNAL_TABLE_SQL))
    conn.execute(text(_JOURNAL_INDEX_SQL))
    # No unconditional clear here -- apply_corrections() refuses if this
    # revision's journal is non-empty. See module docstring "Re-running
    # upgrade() safely".
    apply_corrections(conn, revision)


def downgrade() -> None:
    conn = op.get_bind()
    restore_from_journal(conn, revision)
    # The journal table itself is retained -- see module docstring.
