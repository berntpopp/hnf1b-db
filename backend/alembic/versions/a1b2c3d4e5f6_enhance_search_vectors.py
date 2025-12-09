"""enhance_search_vectors

Add HPO IDs, HGVS expressions, comments to phenopacket search.
Add authors to publication search.
Use 'simple' config for scientific notation.

Revision ID: a1b2c3d4e5f6
Revises: 9d4e5f6g7h8i
Create Date: 2025-12-09 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "9d4e5f6g7h8i"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Enhanced phenopacket search trigger with HPO IDs, HGVS, comments
ENHANCED_TRIGGER_FUNCTION = """
CREATE OR REPLACE FUNCTION phenopackets_search_vector_update()
RETURNS TRIGGER AS $$
DECLARE
    phenotype_labels text;
    phenotype_ids text;
    phenotype_comments text;
    disease_labels text;
    gene_symbols text;
    variant_labels text;
    variant_expressions text;
BEGIN
    -- Extract phenotype labels
    SELECT string_agg(value->'type'->>'label', ' ')
    INTO phenotype_labels
    FROM jsonb_array_elements(
        COALESCE(NEW.phenopacket->'phenotypicFeatures', '[]'::jsonb)
    );

    -- Extract HPO IDs (HP:XXXXXXX)
    SELECT string_agg(value->'type'->>'id', ' ')
    INTO phenotype_ids
    FROM jsonb_array_elements(
        COALESCE(NEW.phenopacket->'phenotypicFeatures', '[]'::jsonb)
    );

    -- Extract phenotype descriptions/comments
    SELECT string_agg(value->>'description', ' ')
    INTO phenotype_comments
    FROM jsonb_array_elements(
        COALESCE(NEW.phenopacket->'phenotypicFeatures', '[]'::jsonb)
    )
    WHERE value->>'description' IS NOT NULL;

    -- Extract disease labels
    SELECT string_agg(value->'term'->>'label', ' ')
    INTO disease_labels
    FROM jsonb_array_elements(
        COALESCE(NEW.phenopacket->'diseases', '[]'::jsonb)
    );

    -- Extract gene symbols and variant info from interpretations
    SELECT
        string_agg(DISTINCT
            gi.value->'variantInterpretation'->'variationDescriptor'->'geneContext'->>'symbol',
            ' '
        ),
        string_agg(DISTINCT
            gi.value->'variantInterpretation'->'variationDescriptor'->>'label',
            ' '
        )
    INTO gene_symbols, variant_labels
    FROM jsonb_array_elements(
        COALESCE(NEW.phenopacket->'interpretations', '[]'::jsonb)
    ) AS interp,
    LATERAL jsonb_array_elements(
        COALESCE(interp.value->'diagnosis'->'genomicInterpretations', '[]'::jsonb)
    ) AS gi;

    -- Extract all HGVS expressions from variants
    SELECT string_agg(expr.value->>'value', ' ')
    INTO variant_expressions
    FROM jsonb_array_elements(
        COALESCE(NEW.phenopacket->'interpretations', '[]'::jsonb)
    ) AS interp,
    LATERAL jsonb_array_elements(
        COALESCE(interp.value->'diagnosis'->'genomicInterpretations', '[]'::jsonb)
    ) AS gi,
    LATERAL jsonb_array_elements(
        COALESCE(
            gi.value->'variantInterpretation'->'variationDescriptor'->'expressions',
            '[]'::jsonb
        )
    ) AS expr;

    -- Build search vector using 'simple' for IDs/HGVS, 'english' for text
    NEW.search_vector :=
        setweight(to_tsvector('simple', COALESCE(NEW.phenopacket->'subject'->>'id', '')), 'A') ||
        setweight(to_tsvector('simple', COALESCE(phenotype_ids, '')), 'A') ||
        setweight(to_tsvector('english', COALESCE(phenotype_labels, '')), 'B') ||
        setweight(to_tsvector('english', COALESCE(phenotype_comments, '')), 'C') ||
        setweight(to_tsvector('english', COALESCE(disease_labels, '')), 'B') ||
        setweight(to_tsvector('simple', COALESCE(gene_symbols, '')), 'A') ||
        setweight(to_tsvector('simple', COALESCE(variant_labels, '')), 'A') ||
        setweight(to_tsvector('simple', COALESCE(variant_expressions, '')), 'A');

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
"""

# Drop MV command (separate for asyncpg)
DROP_GLOBAL_SEARCH_MV = "DROP MATERIALIZED VIEW IF EXISTS global_search_index;"

# Create global search MV with authors and enhanced variant search text
CREATE_GLOBAL_SEARCH_MV = """
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
    COALESCE(search_vector, to_tsvector('simple', COALESCE(subject_id, ''))) AS search_vector,
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
                    gi.value->'variantInterpretation'->'variationDescriptor'->'geneContext'->>'symbol',
                    'Unknown'
                ) || ':' || COALESCE(
                    (gi.value->'variantInterpretation'->'variationDescriptor'->'expressions'->0)->>'value',
                    'unknown'
                )
            ) AS variant_label,
            COALESCE(
                gi.value->'variantInterpretation'->'variationDescriptor'->>'moleculeContext',
                'genomic'
            ) AS molecule_context,
            -- Comprehensive search text including all HGVS expressions
            COALESCE(gi.value->'variantInterpretation'->'variationDescriptor'->>'label', '') || ' ' ||
            COALESCE(gi.value->'variantInterpretation'->'variationDescriptor'->'geneContext'->>'symbol', '') || ' ' ||
            COALESCE((
                SELECT string_agg(e->>'value', ' ')
                FROM jsonb_array_elements(
                    gi.value->'variantInterpretation'->'variationDescriptor'->'expressions'
                ) AS e
            ), '') AS search_text,
            gi.value->'variantInterpretation'->>'acmgPathogenicityClassification' AS pathogenicity
        FROM phenopackets p,
             LATERAL jsonb_array_elements(p.phenopacket->'interpretations') AS interp,
             LATERAL jsonb_array_elements(interp.value->'diagnosis'->'genomicInterpretations') AS gi
        WHERE p.deleted_at IS NULL
          AND gi.value->'variantInterpretation'->'variationDescriptor' IS NOT NULL
    ) AS raw_variants
    ORDER BY variant_label
) AS unique_variants;
"""

# Indexes for the materialized view
MV_INDEXES = [
    "CREATE UNIQUE INDEX idx_global_search_id ON global_search_index (id);",
    "CREATE INDEX idx_global_search_vector ON global_search_index USING GIN (search_vector);",
    "CREATE INDEX idx_global_search_label_trgm ON global_search_index USING GIN (label gin_trgm_ops);",
    "CREATE INDEX idx_global_search_type ON global_search_index (type);",
]


def upgrade() -> None:
    """Upgrade: Enhance search vectors for better biomedical search."""
    # 1. Update phenopacket trigger with enhanced extraction
    op.execute(ENHANCED_TRIGGER_FUNCTION)

    # 2. Repopulate all phenopacket search vectors
    op.execute(
        "UPDATE phenopackets SET phenopacket = phenopacket "
        "WHERE search_vector IS NOT NULL OR search_vector IS NULL"
    )

    # 3. Drop existing MV (separate statement for asyncpg)
    op.execute(DROP_GLOBAL_SEARCH_MV)

    # 4. Recreate global search MV with authors and enhanced variants
    op.execute(CREATE_GLOBAL_SEARCH_MV)

    # 5. Recreate indexes
    for idx_sql in MV_INDEXES:
        op.execute(idx_sql)


def downgrade() -> None:
    """Downgrade: Revert to previous search configuration."""
    # This would need the original trigger/MV definitions
    # For now, just drop and let previous migrations handle recreation
    op.execute("DROP MATERIALIZED VIEW IF EXISTS global_search_index;")
