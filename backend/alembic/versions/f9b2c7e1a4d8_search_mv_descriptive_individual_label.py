"""global_search_index: descriptive INDIVIDUAL labels (disease / key HPO)

Revision ID: f9b2c7e1a4d8
Revises: f3a9c1d4e7b2
Create Date: 2026-05-30 13:00:00.000000

The phenopacket branch of ``global_search_index`` previously set
``label = COALESCE(content_jsonb->'subject'->>'id', phenopacket_id)`` — a bare
identifier (often a numeric subject id like "581") that is useless to a human
or an LLM consuming ``/search/global`` (and the MCP ``hnf1b_search`` tool).

This migration rebuilds the MV changing **only** the phenopacket ``label`` to a
descriptive form::

    'Individual ' || <subject id or phenopacket id>
        || COALESCE(': ' || <first disease label>,
                    ': ' || <first non-excluded phenotypicFeature label>,
                    '')

The "first" element is resolved deterministically via ``WITH ORDINALITY
ORDER BY ordinality LIMIT 1`` (JSONB arrays preserve insertion order). An ASCII
``': '`` separator is used to avoid encoding edge cases.

Everything else is byte-for-byte identical to ``f3a9c1d4e7b2``: the gene /
domain / transcript / publication (static) branches, the variant branch, and
the phenopacket ``search_vector`` / ``type`` / ``subtype`` / ``extra_info``
(disease + non-excluded HPO labels remain FTS-indexed in the search_vector, so
recall is unchanged — this only improves the human/LLM-facing display label and
trigram matchability). All four indexes are recreated. ``downgrade()`` restores
the exact ``f3a9c1d4e7b2`` MV (bare-id phenopacket label) + indexes.
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f9b2c7e1a4d8"
down_revision: Union[str, Sequence[str], None] = "f3a9c1d4e7b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Shared public-filter fragment (I3 + I7 + I1) — qualified on ``p``.
# Verbatim from f3a9c1d4e7b2.
_PUBLIC_FILTER = (
    "p.deleted_at IS NULL"
    "\n          AND p.state = 'published'"
    "\n          AND p.head_published_revision_id IS NOT NULL"
)

# Synthetic-record exclusion (e2e fixtures must not surface in public search).
_NO_E2E = "p.phenopacket_id NOT LIKE 'e2e-%'"

DROP_GLOBAL_SEARCH_MV = "DROP MATERIALIZED VIEW IF EXISTS global_search_index;"

# Index set — verbatim from f3a9c1d4e7b2 (unique id index for CONCURRENTLY
# refresh, GIN on search_vector, trigram GIN on label, btree on type).
MV_INDEXES = [
    "CREATE UNIQUE INDEX idx_global_search_id ON global_search_index (id);",
    "CREATE INDEX idx_global_search_vector "
    "ON global_search_index USING GIN (search_vector);",
    "CREATE INDEX idx_global_search_label_trgm "
    "ON global_search_index USING GIN (label gin_trgm_ops);",
    "CREATE INDEX idx_global_search_type ON global_search_index (type);",
]

# Non-phenopacket/variant branches — verbatim from f3a9c1d4e7b2.
_STATIC_BRANCHES = """
-- Genes
SELECT
    'gene_' || id::text AS id,
    symbol AS label,
    'Gene'::text AS type,
    'Symbol'::text AS subtype,
    setweight(to_tsvector('simple', symbol), 'A') ||
    setweight(to_tsvector('english', COALESCE(name, '')), 'B') AS search_vector,
    name AS extra_info
FROM genes

UNION ALL

-- Protein domains
SELECT
    'domain_' || id::text AS id,
    name AS label,
    'Gene Feature'::text AS type,
    'Domain'::text AS subtype,
    to_tsvector('english', name) AS search_vector,
    short_name AS extra_info
FROM protein_domains

UNION ALL

-- Transcripts
SELECT
    'transcript_' || id::text AS id,
    transcript_id AS label,
    'Gene Feature'::text AS type,
    'Transcript'::text AS subtype,
    to_tsvector('simple', transcript_id) AS search_vector,
    NULL::text AS extra_info
FROM transcripts

UNION ALL

-- Publications with authors
SELECT
    'pub_' || pmid AS id,
    title AS label,
    'Publication'::text AS type,
    'Article'::text AS subtype,
    setweight(to_tsvector('english', COALESCE(title, '')), 'A') ||
    setweight(to_tsvector('simple', COALESCE(
        (SELECT string_agg(a->>'name', ' ') FROM jsonb_array_elements(authors) AS a),
        ''
    )), 'B') ||
    setweight(to_tsvector('english', COALESCE(journal, '')), 'C') AS search_vector,
    journal AS extra_info
FROM publication_metadata
WHERE title IS NOT NULL
"""

# Variant branch — verbatim from f3a9c1d4e7b2.
_VARIANT_BRANCH = f"""
-- Variants (deduplicated by resolvable VRS/CNV descriptor id; published-only)
SELECT * FROM (
    SELECT DISTINCT ON (descriptor_id)
        'var_' || descriptor_id AS id,
        variant_label AS label,
        'Variant'::text AS type,
        molecule_context AS subtype,
        to_tsvector('simple', search_text) AS search_vector,
        pathogenicity AS extra_info
    FROM (
        SELECT
            gi.value->'variantInterpretation'->'variationDescriptor'->>'id'
                AS descriptor_id,
            COALESCE(
                gi.value->'variantInterpretation'->'variationDescriptor'->>'label',
                COALESCE(
                    gi.value->'variantInterpretation'->'variationDescriptor'
                        ->'geneContext'->>'symbol',
                    'Unknown'
                ) || ':' || COALESCE(
                    (gi.value->'variantInterpretation'->'variationDescriptor'
                        ->'expressions'->0)->>'value',
                    'unknown'
                )
            ) AS variant_label,
            COALESCE(
                gi.value->'variantInterpretation'->'variationDescriptor'
                    ->>'moleculeContext',
                'genomic'
            ) AS molecule_context,
            COALESCE(
                gi.value->'variantInterpretation'->'variationDescriptor'->>'label', ''
            ) || ' ' ||
            COALESCE(
                gi.value->'variantInterpretation'->'variationDescriptor'
                    ->'geneContext'->>'symbol', ''
            ) || ' ' ||
            COALESCE((
                SELECT string_agg(e->>'value', ' ')
                FROM jsonb_array_elements(
                    gi.value->'variantInterpretation'->'variationDescriptor'
                        ->'expressions'
                ) AS e
            ), '') AS search_text,
            gi.value->'variantInterpretation'
                ->>'acmgPathogenicityClassification' AS pathogenicity
        FROM phenopackets p
        JOIN phenopacket_revisions r ON r.id = p.head_published_revision_id,
             LATERAL jsonb_array_elements(
                 r.content_jsonb->'interpretations') AS interp,
             LATERAL jsonb_array_elements(
                 interp.value->'diagnosis'->'genomicInterpretations') AS gi
        WHERE {_PUBLIC_FILTER}
          AND {_NO_E2E}
          AND gi.value->'variantInterpretation'->'variationDescriptor'->>'id'
              IS NOT NULL
    ) AS raw_variants
    ORDER BY descriptor_id, variant_label
) AS unique_variants;
"""

# Phenopacket branch — DESCRIPTIVE label (this migration). The search_vector,
# type, subtype and extra_info are byte-for-byte identical to f3a9c1d4e7b2; the
# ONLY change is the ``label`` expression:
#   'Individual ' || <subject id or phenopacket id>
#       || COALESCE(': ' || <first disease label>,
#                   ': ' || <first non-excluded HPO label>, '')
# The "first" element is deterministic via WITH ORDINALITY ORDER BY ordinality.
_PHENO_BRANCH_NEW = f"""
-- Phenopackets (descriptive INDIVIDUAL label; phenotype/disease searchable)
SELECT
    'pp_' || p.phenopacket_id AS id,
    'Individual '
        || COALESCE(r.content_jsonb->'subject'->>'id', p.phenopacket_id)
        || COALESCE(
            ': ' || (
                SELECT d.elem->'term'->>'label'
                FROM jsonb_array_elements(r.content_jsonb->'diseases')
                    WITH ORDINALITY AS d(elem, ordinality)
                WHERE d.elem->'term'->>'label' IS NOT NULL
                ORDER BY d.ordinality
                LIMIT 1
            ),
            ': ' || (
                SELECT pf.elem->'type'->>'label'
                FROM jsonb_array_elements(r.content_jsonb->'phenotypicFeatures')
                    WITH ORDINALITY AS pf(elem, ordinality)
                WHERE COALESCE((pf.elem->>'excluded')::boolean, false) = false
                  AND pf.elem->'type'->>'label' IS NOT NULL
                ORDER BY pf.ordinality
                LIMIT 1
            ),
            ''
        ) AS label,
    'Phenopacket'::text AS type,
    'Individual'::text AS subtype,
    setweight(to_tsvector(
        'simple',
        p.phenopacket_id || ' '
            || COALESCE(r.content_jsonb->'subject'->>'id', '')
    ), 'A') ||
    setweight(to_tsvector('english', COALESCE((
        SELECT string_agg(DISTINCT d->'term'->>'label', ' ')
        FROM jsonb_array_elements(r.content_jsonb->'diseases') AS d
    ), '')), 'B') ||
    setweight(to_tsvector('english', COALESCE((
        SELECT string_agg(DISTINCT pf->'type'->>'label', ' ')
        FROM jsonb_array_elements(r.content_jsonb->'phenotypicFeatures') AS pf
        WHERE COALESCE((pf->>'excluded')::boolean, false) = false
    ), '')), 'C') AS search_vector,
    NULL::text AS extra_info
FROM phenopackets p
JOIN phenopacket_revisions r ON r.id = p.head_published_revision_id
WHERE {_PUBLIC_FILTER}
  AND {_NO_E2E}
"""

# Phenopacket branch — PREVIOUS (bare-id label), for downgrade(). Byte-for-byte
# identical to the f3a9c1d4e7b2 phenopacket branch.
_PHENO_BRANCH_PREV = f"""
-- Phenopackets (phenotype/disease text searchable; published-only)
SELECT
    'pp_' || p.phenopacket_id AS id,
    COALESCE(r.content_jsonb->'subject'->>'id', p.phenopacket_id) AS label,
    'Phenopacket'::text AS type,
    'Individual'::text AS subtype,
    setweight(to_tsvector(
        'simple',
        p.phenopacket_id || ' '
            || COALESCE(r.content_jsonb->'subject'->>'id', '')
    ), 'A') ||
    setweight(to_tsvector('english', COALESCE((
        SELECT string_agg(DISTINCT d->'term'->>'label', ' ')
        FROM jsonb_array_elements(r.content_jsonb->'diseases') AS d
    ), '')), 'B') ||
    setweight(to_tsvector('english', COALESCE((
        SELECT string_agg(DISTINCT pf->'type'->>'label', ' ')
        FROM jsonb_array_elements(r.content_jsonb->'phenotypicFeatures') AS pf
        WHERE COALESCE((pf->>'excluded')::boolean, false) = false
    ), '')), 'C') AS search_vector,
    NULL::text AS extra_info
FROM phenopackets p
JOIN phenopacket_revisions r ON r.id = p.head_published_revision_id
WHERE {_PUBLIC_FILTER}
  AND {_NO_E2E}
"""

# Branch order matches f3a9c1d4e7b2: static, phenopacket, variant.
CREATE_MV_NEW = (
    "CREATE MATERIALIZED VIEW global_search_index AS\n"
    f"{_STATIC_BRANCHES}\nUNION ALL\n{_PHENO_BRANCH_NEW}\nUNION ALL\n{_VARIANT_BRANCH}"
)
CREATE_MV_PREV = (
    "CREATE MATERIALIZED VIEW global_search_index AS\n"
    f"{_STATIC_BRANCHES}\nUNION ALL\n{_PHENO_BRANCH_PREV}\nUNION ALL\n{_VARIANT_BRANCH}"
)


def _recreate_indexes() -> None:
    for stmt in MV_INDEXES:
        op.execute(stmt)


def upgrade() -> None:
    """Rebuild global_search_index with descriptive INDIVIDUAL labels."""
    op.execute(DROP_GLOBAL_SEARCH_MV)
    op.execute(CREATE_MV_NEW)
    _recreate_indexes()
    op.execute("REFRESH MATERIALIZED VIEW global_search_index;")


def downgrade() -> None:
    """Restore the f3a9c1d4e7b2 bare-id phenopacket label MV + indexes."""
    op.execute(DROP_GLOBAL_SEARCH_MV)
    op.execute(CREATE_MV_PREV)
    _recreate_indexes()
    op.execute("REFRESH MATERIALIZED VIEW global_search_index;")
