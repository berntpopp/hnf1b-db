"""Correct HP:0033133 -> HP:0033132 for renal cortical hyperechogenicity.

The source curation spreadsheet paired the wrong HPO id with the right term
name: its ``Phenotype`` sheet lists category ``Hyperechogenicity`` as
``HP:0033133`` / "Renal cortical hyperechogenicity" / "Increased echogenecity of
the kidney cortex."

Per HPO (version 2026-06-23):

    HP:0033132  Renal cortical hyperechogenicity   <- what was meant
    HP:0033133  Renal cortical hypoechogeneity     <- what was stored

Hyper- and hypo-echogenicity are opposite findings, and renal cortical
hyperechogenicity is the classic HNF1B ultrasound feature. Every affected
record therefore asserts the inverse of what its publication reported.

The error was concealed rather than exposed by later cleanup: stored labels
read "Renal cortical hypoechogeneity", i.e. they were normalised to agree with
the wrong id. Label normalisation against an incorrect id launders a
contradiction into a consistent falsehood, which is why nothing flagged it.

Scope (measured before writing this revision):

    phenopackets.phenopacket              460 features
    phenopacket_revisions.content_jsonb   460 features
    hpo_terms_lookup                        1 row (id wrong, label right)

Both copies are rewritten because ``phenopacket_revisions.content_jsonb`` at
``head_published_revision_id`` is what public reads and global search serve
(``app/phenopackets/repositories/visibility.py:80``); fixing only the working
copy would leave the wrong term in every public response.

This revision deliberately does NOT touch the four other stored-vs-lookup label
differences (HP:0012622, HP:0002910, HP:0000708, HP:0012443). Those are HPO
renames where the *stored* label is current and ``hpo_terms_lookup`` is stale;
normalising them toward the lookup table would regress them.

Revision ID: d4e8b1f60a27
Revises: f9b2c7e1a4d8
"""

from sqlalchemy import text

from alembic import op

revision = "d4e8b1f60a27"
down_revision = "f9b2c7e1a4d8"
branch_labels = None
depends_on = None

WRONG_ID = "HP:0033133"
WRONG_LABEL = "Renal cortical hypoechogeneity"
RIGHT_ID = "HP:0033132"
RIGHT_LABEL = "Renal cortical hyperechogenicity"

# Rewrite phenotypicFeatures[].type in place, preserving element order and every
# sibling key (excluded, evidence, onset, modifiers). jsonb_agg over
# jsonb_array_elements WITH ORDINALITY keeps ordering deterministic.
#
# Two details that are easy to get wrong:
#
#   * The strip is parenthesised: ``((type) - 'id' - 'label') || build_object(...)``.
#     Written the other way round, ``build_object(...) || (type) - 'id' - 'label'``
#     parses as ``(build || type) - 'id' - 'label'`` and deletes the very keys it
#     is supposed to set, silently emptying every type object.
#   * The predicate uses EXISTS rather than ``@> :probe::jsonb``. A ``::`` cast
#     immediately after a bind parameter is a syntax error under asyncpg.
#   * ``jsonb_build_object`` takes ``"any"``, so asyncpg cannot infer the type of a
#     bare bind parameter and fails with IndeterminateDatatypeError. Both values
#     are wrapped in an explicit ``cast(... as text)``.
_REWRITE = """
UPDATE {table} AS t
SET {column} = jsonb_set(
        t.{column},
        '{{phenotypicFeatures}}',
        (
            SELECT jsonb_agg(
                       CASE
                           WHEN elem->'type'->>'id' = :from_id
                           THEN jsonb_set(
                                    elem,
                                    '{{type}}',
                                    ((elem->'type') - 'id' - 'label')
                                       || jsonb_build_object(
                                              'id', cast(:to_id as text),
                                              'label', cast(:to_label as text)
                                          )
                                )
                           ELSE elem
                       END
                       ORDER BY ord
                   )
            FROM jsonb_array_elements(t.{column}->'phenotypicFeatures')
                 WITH ORDINALITY AS a(elem, ord)
        )
    )
WHERE EXISTS (
    SELECT 1
    FROM jsonb_array_elements(t.{column}->'phenotypicFeatures') AS e
    WHERE e->'type'->>'id' = :from_id
)
"""


def _retarget(from_id: str, to_id: str, to_label: str) -> None:
    """Point every feature at ``from_id`` to ``to_id``, in both stored copies."""
    conn = op.get_bind()
    for table, column in (
        ("phenopackets", "phenopacket"),
        ("phenopacket_revisions", "content_jsonb"),
    ):
        conn.execute(
            text(_REWRITE.format(table=table, column=column)),
            {"from_id": from_id, "to_id": to_id, "to_label": to_label},
        )

    # Set id AND label together. Setting only the id leaves the row carrying
    # whatever label HPO ingestion last wrote, which is how the original
    # mismatched pair (wrong id + right label) arose and stayed invisible.
    conn.execute(
        text(
            "UPDATE hpo_terms_lookup SET hpo_id = :to_id, label = :to_label "
            "WHERE hpo_id IN (:from_id, :to_id)"
        ),
        {"from_id": from_id, "to_id": to_id, "to_label": to_label},
    )


def upgrade() -> None:
    # The lookup row pairs the wrong id with the right label, which is precisely
    # what hid the error in the UI: the create page rendered
    # "Renal cortical hyperechogenicity  HP:0033133" and looked correct.
    _retarget(WRONG_ID, RIGHT_ID, RIGHT_LABEL)


def downgrade() -> None:
    _retarget(RIGHT_ID, WRONG_ID, WRONG_LABEL)
