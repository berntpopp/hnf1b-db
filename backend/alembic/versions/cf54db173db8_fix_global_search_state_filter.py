"""fix global search state filter

Revision ID: cf54db173db8
Revises: 20260415_0005
Create Date: 2026-05-28 22:18:20.287045

Wave A — public-API content/draft leak fix (THE key deliverable).

The ``global_search_index`` materialized view (defined in revision
``a1b2c3d4e5f6``) had two visibility leaks:

1. Its phenopacket and variant branches filtered only on
   ``deleted_at IS NULL`` — so ``draft`` / ``in_review`` / ``approved`` /
   ``archived`` records (and their variants) leaked to anonymous callers via
   ``/search/global`` and ``/search/autocomplete``.
2. Both branches sourced JSONB from ``p.phenopacket`` (the working copy),
   which holds the unpublished clone-to-draft edit mid-edit — leaking
   unpublished curator edits.

This migration rebuilds the MV so that the phenopacket and variant branches:
  - join the head-published revision
    (``phenopacket_revisions r JOIN phenopackets p ON r.id =
    p.head_published_revision_id``) and read content from ``r.content_jsonb``,
    never ``p.phenopacket``; and
  - apply the full public filter (I3 + I7 + I1):
    ``p.deleted_at IS NULL AND p.state = 'published'
    AND p.head_published_revision_id IS NOT NULL``.

Non-phenopacket branches (genes, domains, transcripts, publications) are
unchanged. The unique index ``idx_global_search_id`` on ``(id)`` is recreated
(required for CONCURRENTLY refresh).
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "cf54db173db8"
down_revision: Union[str, Sequence[str], None] = "20260415_0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ---------------------------------------------------------------------------
# Shared public-filter fragment (I3 + I7 + I1) — qualified on ``p``.
# ---------------------------------------------------------------------------
_PUBLIC_FILTER = (
    "p.deleted_at IS NULL"
    "\n          AND p.state = 'published'"
    "\n          AND p.head_published_revision_id IS NOT NULL"
)

DROP_GLOBAL_SEARCH_MV = "DROP MATERIALIZED VIEW IF EXISTS global_search_index;"

MV_INDEXES = [
    "CREATE UNIQUE INDEX idx_global_search_id ON global_search_index (id);",
    "CREATE INDEX idx_global_search_vector "
    "ON global_search_index USING GIN (search_vector);",
    "CREATE INDEX idx_global_search_label_trgm "
    "ON global_search_index USING GIN (label gin_trgm_ops);",
    "CREATE INDEX idx_global_search_type ON global_search_index (type);",
]

# ---------------------------------------------------------------------------
# Fixed MV: published-only, head-published content (Wave A).
# ---------------------------------------------------------------------------
CREATE_GLOBAL_SEARCH_MV_FIXED = f"""
CREATE MATERIALIZED VIEW global_search_index AS
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

UNION ALL

-- Phenopackets (head-published content; published-only)
SELECT
    'pp_' || p.phenopacket_id AS id,
    COALESCE(r.content_jsonb->'subject'->>'id', p.phenopacket_id) AS label,
    'Phenopacket'::text AS type,
    'Individual'::text AS subtype,
    to_tsvector(
        'simple', COALESCE(r.content_jsonb->'subject'->>'id', '')
    ) AS search_vector,
    NULL::text AS extra_info
FROM phenopackets p
JOIN phenopacket_revisions r ON r.id = p.head_published_revision_id
WHERE {_PUBLIC_FILTER}

UNION ALL

-- Variants (deduplicated; head-published content; published-only)
SELECT * FROM (
    SELECT DISTINCT ON (variant_label)
        'var_' || md5(variant_label) AS id,
        variant_label AS label,
        'Variant'::text AS type,
        molecule_context AS subtype,
        to_tsvector('simple', search_text) AS search_vector,
        pathogenicity AS extra_info
    FROM (
        SELECT
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
            -- Comprehensive search text including all HGVS expressions
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
          AND gi.value->'variantInterpretation'->'variationDescriptor' IS NOT NULL
    ) AS raw_variants
    ORDER BY variant_label
) AS unique_variants;
"""

# ---------------------------------------------------------------------------
# Original leaky MV (from a1b2c3d4e5f6) — used by downgrade().
# ---------------------------------------------------------------------------
CREATE_GLOBAL_SEARCH_MV_LEGACY = """
CREATE MATERIALIZED VIEW global_search_index AS
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

UNION ALL

-- Phenopackets
SELECT
    'pp_' || phenopacket_id AS id,
    subject_id AS label,
    'Phenopacket'::text AS type,
    'Individual'::text AS subtype,
    COALESCE(
        search_vector, to_tsvector('simple', COALESCE(subject_id, ''))
    ) AS search_vector,
    NULL::text AS extra_info
FROM phenopackets
WHERE deleted_at IS NULL

UNION ALL

-- Variants (deduplicated)
SELECT * FROM (
    SELECT DISTINCT ON (variant_label)
        'var_' || md5(variant_label) AS id,
        variant_label AS label,
        'Variant'::text AS type,
        molecule_context AS subtype,
        to_tsvector('simple', search_text) AS search_vector,
        pathogenicity AS extra_info
    FROM (
        SELECT
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
        FROM phenopackets p,
             LATERAL jsonb_array_elements(p.phenopacket->'interpretations') AS interp,
             LATERAL jsonb_array_elements(
                 interp.value->'diagnosis'->'genomicInterpretations') AS gi
        WHERE p.deleted_at IS NULL
          AND gi.value->'variantInterpretation'->'variationDescriptor' IS NOT NULL
    ) AS raw_variants
    ORDER BY variant_label
) AS unique_variants;
"""


def _recreate_indexes() -> None:
    for stmt in MV_INDEXES:
        op.execute(stmt)


def upgrade() -> None:
    """Rebuild global_search_index: published-only + head-published content."""
    op.execute(DROP_GLOBAL_SEARCH_MV)
    op.execute(CREATE_GLOBAL_SEARCH_MV_FIXED)
    _recreate_indexes()


def downgrade() -> None:
    """Restore the original leaky MV definition from a1b2c3d4e5f6."""
    op.execute(DROP_GLOBAL_SEARCH_MV)
    op.execute(CREATE_GLOBAL_SEARCH_MV_LEGACY)
    _recreate_indexes()
