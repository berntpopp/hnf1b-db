"""global_search_index: phenopacket branch searchable by phenotype/disease text

Revision ID: f3a9c1d4e7b2
Revises: e7a1b9c3d2f4
Create Date: 2026-05-30 11:00:00.000000

Folds disease term labels and non-excluded phenotypicFeatures labels into the
phenopacket branch ``search_vector`` so ``/search/global`` (and the MCP
``hnf1b_search`` tool that consumes it) returns individuals for free-text
clinical queries like "renal cysts" or "diabetes".

The gene / domain / transcript / publication (static) branches and the
variant branch are byte-for-byte identical to the definition installed by
b7c1f0a9d2e4 (which is still the live definition at e7a1b9c3d2f4 — no
intermediate migration altered the MV). Only the phenopacket branch changes:
``upgrade()`` enriches its ``search_vector`` and ``downgrade()`` restores the
phenotype-blind (phenopacket_id + subject.id) branch exactly as it stood at
e7a1b9c3d2f4.
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f3a9c1d4e7b2"
down_revision: Union[str, Sequence[str], None] = "e7a1b9c3d2f4"
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

# Non-phenopacket/variant branches — identical to b7c1f0a9d2e4 (the live
# definition at e7a1b9c3d2f4). Shared verbatim by both upgrade/downgrade.
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

# Variant branch — identical to b7c1f0a9d2e4 (resolvable descriptor ids;
# deduplicated by descriptor_id; published-only; e2e excluded).
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

# Phenopacket branch — ENRICHED. phenopacket_id + subject.id stay weight 'A'
# (verbatim from b7c1f0a9d2e4); disease term labels join at weight 'B' and
# non-excluded phenotypicFeatures labels at weight 'C'.
_PHENO_BRANCH_NEW = f"""
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

# Phenopacket branch — PREVIOUS (phenotype-blind), for downgrade(). This is the
# exact branch installed by b7c1f0a9d2e4 and still live at e7a1b9c3d2f4:
# phenopacket_id + subject.id only, single 'simple' to_tsvector (no weights).
_PHENO_BRANCH_PREV = f"""
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
"""

# Branch order matches the live MV (b7c1f0a9d2e4): static, phenopacket, variant.
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
    """Rebuild global_search_index with a phenotype/disease-searchable phenopacket branch."""
    op.execute(DROP_GLOBAL_SEARCH_MV)
    op.execute(CREATE_MV_NEW)
    _recreate_indexes()


def downgrade() -> None:
    """Restore the e7a1b9c3d2f4 phenotype-blind phenopacket branch (== b7c1f0a9d2e4)."""
    op.execute(DROP_GLOBAL_SEARCH_MV)
    op.execute(CREATE_MV_PREV)
    _recreate_indexes()
