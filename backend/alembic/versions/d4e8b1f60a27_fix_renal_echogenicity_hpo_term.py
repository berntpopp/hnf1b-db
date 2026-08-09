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
    phenopacket_revisions.content_jsonb   460 features (head-published only)
    hpo_terms_lookup                        1 row (id wrong, label right)

``phenopacket_revisions.content_jsonb`` at ``head_published_revision_id`` is
what public reads and global search serve
(``app/phenopackets/repositories/visibility.py:80``); fixing only the working
copy would leave the wrong term in every public response. The
``phenopacket_revisions`` write is therefore scoped by a join to
``phenopackets.head_published_revision_id`` -- older revision rows are
immutable history and are deliberately not rewritten, matching the scope
decision later migrations in this series (``efa98cccfa51``, ``18cfc57307f6``)
make explicitly.

This revision deliberately does NOT touch the four other stored-vs-lookup label
differences (HP:0012622, HP:0002910, HP:0000708, HP:0012443). Those are HPO
renames where the *stored* label is current and ``hpo_terms_lookup`` is stale;
normalising them toward the lookup table would regress them.

``hpo_terms_lookup`` metadata beyond id/label
----------------------------------------------

``hpo_terms_lookup`` also carries ``category``/``description``/``synonyms``,
populated once from the curation sheet
(``0bd1567a483c_add_phenotype_metadata_to_hpo_lookup.py``) and later
overwritten by an authoritative-HPO repopulation keyed on ``hpo_id`` -- while
the row's id was still the wrong ``HP:0033133``, so that repopulation (quite
correctly, given the id it was told to trust) wrote HP:0033133's own true
metadata: category ``Hypoechogenicity``, description "Decreased echogenicity
of the kidney cortex." Retargeting only ``hpo_id``/``label`` therefore leaves
the row self-contradictory after this migration: id and label say
*hyper*echogenicity, category and description still say *hypo*. This
correction sets all three together, from two independently cross-checked
sources that agree: the original curation-sheet seed row (``category
'Hyperechogenicity'``, ``description 'Increased echogenecity of the kidney
cortex.'``, no synonyms) and the pinned ``app/ontology/data/
ontology_snapshot.json`` (``HP:0033132.definition ==`` the same description,
``.synonyms == []``). The values are redeclared inline rather than read from
either source at migration run time -- see "Every id/label literal below" in
``efa98cccfa51``'s docstring for why a migration must be a frozen snapshot of
its own intent.

Reversibility
-------------

There is no journal table at this revision (``efa98cccfa51`` creates
``ontology_migration_journal`` one revision later), so an exact,
journal-verified reversal is not available here. An unconditional inverse
remap would be a live data-destroying footgun: ``HP:0033132`` (Renal cortical
hyperechogenicity) and ``HP:0033133`` (Renal cortical hypoechogeneity) are
opposite ultrasound findings, so blindly rewriting every row currently
carrying the correct id back to the wrong one would also invert any record
that legitimately came to carry ``HP:0033132`` after this migration ran --
including new imports and curator edits -- silently re-introducing the exact
clinical contradiction this migration exists to remove.

Instead, ``downgrade()`` reuses the same head-scoped rewrite as ``upgrade()``
and additionally refuses (raises) unless the number of rows it would touch,
in both ``phenopackets`` and ``phenopacket_revisions``, exactly matches the
number this revision's ``upgrade()`` touched when it was written (measured
above: 460 and 460). Any divergence -- a new or edited record now carrying
``HP:0033132``, or the correction already having been reverted by hand --
aborts the migration rather than silently reverting data outside what
``upgrade()`` actually changed. This keeps ``make db-reset``
(``alembic downgrade base`` followed by ``alembic upgrade head``) working
against a corpus that still matches this migration's original scope, while
refusing outright the moment it does not.

Revision ID: d4e8b1f60a27
Revises: f9b2c7e1a4d8
"""

from sqlalchemy import text
from sqlalchemy.engine import Connection

from alembic import op

revision = "d4e8b1f60a27"
down_revision = "f9b2c7e1a4d8"
branch_labels = None
depends_on = None

WRONG_ID = "HP:0033133"
WRONG_LABEL = "Renal cortical hypoechogeneity"
RIGHT_ID = "HP:0033132"
RIGHT_LABEL = "Renal cortical hyperechogenicity"

# hpo_terms_lookup metadata for the RIGHT_ID side -- see module docstring
# "hpo_terms_lookup metadata beyond id/label". Cross-checked against both the
# original curation-sheet seed row and the pinned ontology snapshot; do not
# read either source at migration run time (frozen-snapshot principle).
RIGHT_CATEGORY = "Hyperechogenicity"
RIGHT_DESCRIPTION = "Increased echogenecity of the kidney cortex."
RIGHT_SYNONYMS = "No synonyms found for this term."

# Number of rows this revision's upgrade() touched, measured against the live
# corpus before this revision was written (see module docstring "Scope").
# downgrade() refuses unless the corpus still matches this exactly -- see
# module docstring "Reversibility".
_EXPECTED_UPGRADE_ROWCOUNTS = {
    "phenopackets": 460,
    "phenopacket_revisions": 460,
}

# Table-specific FROM/WHERE fragments for _REWRITE below. phenopackets is the
# working copy and is rewritten unscoped (every row is "current").
# phenopacket_revisions is scoped to each record's head-published revision
# only -- older revisions are immutable history (see module docstring "Scope").
_TABLE_SCOPE = {
    "phenopackets": {"extra_from": "", "extra_where": ""},
    "phenopacket_revisions": {
        "extra_from": "FROM phenopackets p",
        "extra_where": "p.head_published_revision_id = t.id AND ",
    },
}

# Rewrite phenotypicFeatures[].type in place, preserving element order and every
# sibling key (excluded, evidence, onset, modifiers). jsonb_agg over
# jsonb_array_elements WITH ORDINALITY keeps ordering deterministic.
#
# Three details that are easy to get wrong:
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
#   * ``{extra_from}``/``{extra_where}`` scope the ``phenopacket_revisions``
#     write to each record's head-published revision (see ``_TABLE_SCOPE``);
#     for ``phenopackets`` both are empty and the clause is unchanged.
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
{extra_from}
WHERE {extra_where}EXISTS (
    SELECT 1
    FROM jsonb_array_elements(t.{column}->'phenotypicFeatures') AS e
    WHERE e->'type'->>'id' = :from_id
)
"""


def _retarget(
    conn: Connection,
    from_id: str,
    to_id: str,
    to_label: str,
    *,
    guard_rowcounts: dict[str, int] | None = None,
) -> None:
    """Point every feature at ``from_id`` to ``to_id``, in both stored copies.

    ``phenopacket_revisions`` is scoped to each record's
    ``head_published_revision_id`` only -- see ``_TABLE_SCOPE`` and the
    module docstring "Scope".

    ``guard_rowcounts``, when given (``downgrade()`` only), is compared
    against each UPDATE's actual matched-row count (``result.rowcount``); a
    mismatch raises ``RuntimeError`` instead of proceeding -- see the module
    docstring "Reversibility" for why an unconditional inverse remap is not
    safe at this revision.
    """
    for table, column in (
        ("phenopackets", "phenopacket"),
        ("phenopacket_revisions", "content_jsonb"),
    ):
        scope = _TABLE_SCOPE[table]
        result = conn.execute(
            text(_REWRITE.format(table=table, column=column, **scope)),
            {"from_id": from_id, "to_id": to_id, "to_label": to_label},
        )
        if guard_rowcounts is not None:
            expected = guard_rowcounts[table]
            if result.rowcount != expected:
                raise RuntimeError(
                    f"Refusing to downgrade d4e8b1f60a27: expected to revert "
                    f"exactly {expected} row(s) in {table!r} (the count this "
                    f"revision's upgrade() touched), but the current corpus "
                    f"has {result.rowcount} row(s) matching {from_id!r}. This "
                    f"means the corpus has changed since upgrade() ran -- a "
                    f"new or curator-edited record now carries {from_id!r}, "
                    f"or the correction was already reverted -- and an "
                    f"unconditional inverse remap would silently re-invert a "
                    f"clinical finding (HP:0033132 'Renal cortical "
                    f"hyperechogenicity' -> HP:0033133 'Renal cortical "
                    f"hypoechogeneity', the opposite ultrasound finding) for "
                    f"rows this migration never touched. Restore from backup "
                    f"instead of downgrading past this revision."
                )

    # Set id, label AND metadata together. Setting only the id leaves the row
    # carrying whatever label/category/description HPO ingestion or an
    # authoritative repopulation last wrote for the OLD id, which is how both
    # the original mismatched pair (wrong id + right label) and the
    # id/label-vs-category/description contradiction arose and stayed
    # invisible -- see module docstring "hpo_terms_lookup metadata beyond
    # id/label". The metadata columns are only meaningful for the RIGHT_ID
    # side (upgrade); on downgrade they are harmless no-ops since the row
    # keeps id/label WRONG_ID/WRONG_LABEL either way -- deliberately not
    # reverted, since WRONG_ID's own true metadata is not this migration's
    # concern and category/description staying "correct for hyperechogenicity"
    # under a temporarily-wrong id is strictly less harmful than the
    # self-contradiction this migration exists to fix.
    conn.execute(
        text(
            "UPDATE hpo_terms_lookup SET hpo_id = :to_id, label = :to_label, "
            "category = :category, description = :description, "
            "synonyms = :synonyms "
            "WHERE hpo_id IN (:from_id, :to_id)"
        ),
        {
            "from_id": from_id,
            "to_id": to_id,
            "to_label": to_label,
            "category": RIGHT_CATEGORY,
            "description": RIGHT_DESCRIPTION,
            "synonyms": RIGHT_SYNONYMS,
        },
    )


def upgrade() -> None:
    # The lookup row pairs the wrong id with the right label, which is precisely
    # what hid the error in the UI: the create page rendered
    # "Renal cortical hyperechogenicity  HP:0033133" and looked correct.
    conn = op.get_bind()
    _retarget(conn, WRONG_ID, RIGHT_ID, RIGHT_LABEL)


def downgrade() -> None:
    """Reverse the correction -- refuses unless the corpus still matches exactly what upgrade() touched.

    See module docstring "Reversibility": there is no journal at this
    revision, so this cannot verify individual rows the way
    ``efa98cccfa51``/``18cfc57307f6`` do. Instead it checks the aggregate
    row count against what upgrade() touched (``_EXPECTED_UPGRADE_ROWCOUNTS``)
    and refuses outright on any mismatch, rather than silently re-inverting a
    clinical finding for rows outside upgrade()'s original scope.
    """
    conn = op.get_bind()
    _retarget(
        conn,
        RIGHT_ID,
        WRONG_ID,
        WRONG_LABEL,
        guard_rowcounts=_EXPECTED_UPGRADE_ROWCOUNTS,
    )
