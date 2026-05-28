"""global_search_index: searchable phenopacket_id + resolvable variant ids

Revision ID: b7c1f0a9d2e4
Revises: cf54db173db8
Create Date: 2026-05-29 01:30:00.000000

Rebuilds the ``global_search_index`` materialized view to fix two MCP/search
defects and add synthetic-record exclusion:

1. **Phenopacket branch** previously indexed only ``subject.id`` in the
   ``search_vector`` and ``label``, so a query for a literal ``phenopacket_id``
   (e.g. ``phenopacket-596``) matched nothing. The ``phenopacket_id`` is now
   folded into the ``search_vector`` so it is discoverable.

2. **Variant branch** previously emitted ``'var_' || md5(variant_label)`` as the
   row id — an opaque hash that the ``/phenopackets/.../by-variant`` and
   all-variants endpoints cannot resolve, severing the search → get_variant
   chain. It now emits ``'var_' || (variationDescriptor.id)`` — the resolvable
   GA4GH VRS / CNV descriptor id those endpoints key on — and de-duplicates by
   that descriptor id.

3. Both branches exclude synthetic ``e2e-%`` phenopackets so test fixtures
   never appear in ``/search/global`` results.

The gene / domain / transcript / publication branches are unchanged.
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b7c1f0a9d2e4"
down_revision: Union[str, Sequence[str], None] = "cf54db173db8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Shared public-filter fragment (I3 + I7 + I1) — qualified on ``p``.
_PUBLIC_FILTER = (
    "p.deleted_at IS NULL"
    "\n          AND p.state = 'published'"
    "\n          AND p.head_published_revision_id IS NOT NULL"
)

# Synthetic-record exclusion (e2e fixtures must not surface in public search).
_NO_E2E = "p.phenopacket_id NOT LIKE 'e2e-%'"

DROP_GLOBAL_SEARCH_MV = "DROP MATERIALIZED VIEW IF EXISTS global_search_index;"

MV_INDEXES = [
    "CREATE UNIQUE INDEX idx_global_search_id ON global_search_index (id);",
    "CREATE INDEX idx_global_search_vector "
    "ON global_search_index USING GIN (search_vector);",
    "CREATE INDEX idx_global_search_label_trgm "
    "ON global_search_index USING GIN (label gin_trgm_ops);",
    "CREATE INDEX idx_global_search_type ON global_search_index (type);",
]

# Non-phenopacket/variant branches, shared verbatim by both upgrade/downgrade.
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

# ---------------------------------------------------------------------------
# NEW MV — phenopacket_id searchable + resolvable variant descriptor ids.
# ---------------------------------------------------------------------------
CREATE_GLOBAL_SEARCH_MV_NEW = f"""
CREATE MATERIALIZED VIEW global_search_index AS
{_STATIC_BRANCHES}
UNION ALL

-- Phenopackets (head-published content; published-only; phenopacket_id searchable)
SELECT
    'pp_' || p.phenopacket_id AS id,
    COALESCE(r.content_jsonb->'subject'->>'id', p.phenopacket_id) AS label,
    'Phenopacket'::text AS type,
    'Individual'::text AS subtype,
    to_tsvector(
        'simple',
        p.phenopacket_id || ' '
            || COALESCE(r.content_jsonb->'subject'->>'id', '')
    ) AS search_vector,
    NULL::text AS extra_info
FROM phenopackets p
JOIN phenopacket_revisions r ON r.id = p.head_published_revision_id
WHERE {_PUBLIC_FILTER}
  AND {_NO_E2E}

UNION ALL

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

# ---------------------------------------------------------------------------
# Previous MV (cf54db173db8) — used by downgrade(): md5 ids, subject-only FTS.
# ---------------------------------------------------------------------------
CREATE_GLOBAL_SEARCH_MV_PREV = f"""
CREATE MATERIALIZED VIEW global_search_index AS
{_STATIC_BRANCHES}
UNION ALL

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


def _recreate_indexes() -> None:
    for stmt in MV_INDEXES:
        op.execute(stmt)


def upgrade() -> None:
    """Rebuild global_search_index: searchable phenopacket_id + resolvable variant ids."""
    op.execute(DROP_GLOBAL_SEARCH_MV)
    op.execute(CREATE_GLOBAL_SEARCH_MV_NEW)
    _recreate_indexes()


def downgrade() -> None:
    """Restore the cf54db173db8 MV (md5 variant ids, subject-only FTS)."""
    op.execute(DROP_GLOBAL_SEARCH_MV)
    op.execute(CREATE_GLOBAL_SEARCH_MV_PREV)
    _recreate_indexes()
