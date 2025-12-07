"""add_variants_to_global_search

Revision ID: 6a1b2c3d4e5f
Revises: 5f9c34e4e444
Create Date: 2025-12-07 16:00:00.000000

Adds variants to global_search_index materialized view and creates
unique index for CONCURRENTLY refresh support.
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "6a1b2c3d4e5f"
down_revision: Union[str, Sequence[str], None] = "5f9c34e4e444"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add variants to global_search_index and create unique index for CONCURRENTLY."""
    # Drop existing indexes first
    op.execute("DROP INDEX IF EXISTS idx_global_search_vector")
    op.execute("DROP INDEX IF EXISTS idx_global_search_label_trgm")

    # Drop and recreate MV with variants included
    op.execute("DROP MATERIALIZED VIEW IF EXISTS global_search_index")

    # Create enhanced MV with variants
    op.execute("""
        CREATE MATERIALIZED VIEW global_search_index AS
        -- Genes
        SELECT
            'gene_' || id::text AS id,
            symbol AS label,
            'Gene' AS type,
            'Symbol' AS subtype,
            setweight(to_tsvector('english', symbol), 'A') ||
            setweight(to_tsvector('english', COALESCE(name, '')), 'B') AS search_vector,
            name AS extra_info
        FROM genes

        UNION ALL

        -- Protein Domains
        SELECT
            'domain_' || id::text AS id,
            name AS label,
            'Gene Feature' AS type,
            'Domain' AS subtype,
            to_tsvector('english', name) AS search_vector,
            short_name AS extra_info
        FROM protein_domains

        UNION ALL

        -- Transcripts
        SELECT
            'transcript_' || id::text AS id,
            transcript_id AS label,
            'Gene Feature' AS type,
            'Transcript' AS subtype,
            to_tsvector('simple', transcript_id) AS search_vector,
            NULL::text AS extra_info
        FROM transcripts

        UNION ALL

        -- Publications
        SELECT
            'pub_' || pmid AS id,
            title AS label,
            'Publication' AS type,
            'Article' AS subtype,
            COALESCE(search_vector, to_tsvector('english', COALESCE(title, ''))) AS search_vector,
            journal AS extra_info
        FROM publication_metadata
        WHERE title IS NOT NULL

        UNION ALL

        -- Phenopackets (individuals)
        SELECT
            'pp_' || phenopacket_id AS id,
            subject_id AS label,
            'Phenopacket' AS type,
            'Individual' AS subtype,
            COALESCE(search_vector, to_tsvector('english', COALESCE(subject_id, ''))) AS search_vector,
            NULL::text AS extra_info
        FROM phenopackets
        WHERE deleted_at IS NULL

        UNION ALL

        -- Unique Variants extracted from phenopackets (deduplicated by label)
        SELECT
            id, label, type, subtype, search_vector, extra_info
        FROM (
            SELECT DISTINCT ON (variant_label)
                'var_' || md5(variant_label) AS id,
                variant_label AS label,
                'Variant' AS type,
                molecule_context AS subtype,
                to_tsvector('english', search_text) AS search_vector,
                pathogenicity AS extra_info
            FROM (
                SELECT
                    COALESCE(
                        gi.value->'variantInterpretation'->'variationDescriptor'->>'label',
                        COALESCE(gi.value->'variantInterpretation'->'variationDescriptor'->'geneContext'->>'symbol', 'Unknown')
                        || ':' ||
                        COALESCE(gi.value->'variantInterpretation'->'variationDescriptor'->'expressions'->0->>'value', 'unknown')
                    ) AS variant_label,
                    COALESCE(
                        gi.value->'variantInterpretation'->'variationDescriptor'->>'moleculeContext',
                        'genomic'
                    ) AS molecule_context,
                    COALESCE(gi.value->'variantInterpretation'->'variationDescriptor'->>'label', '') || ' ' ||
                    COALESCE(gi.value->'variantInterpretation'->'variationDescriptor'->'geneContext'->>'symbol', '') || ' ' ||
                    COALESCE(gi.value->'variantInterpretation'->'variationDescriptor'->'expressions'->0->>'value', '') AS search_text,
                    gi.value->'variantInterpretation'->>'acmgPathogenicityClassification' AS pathogenicity
                FROM phenopackets p,
                    jsonb_array_elements(p.phenopacket->'interpretations') AS interp,
                    jsonb_array_elements(interp.value->'diagnosis'->'genomicInterpretations') AS gi
                WHERE p.deleted_at IS NULL
                  AND gi.value->'variantInterpretation'->'variationDescriptor' IS NOT NULL
            ) AS raw_variants
            ORDER BY variant_label
        ) AS unique_variants
    """)

    # Create unique index on id for CONCURRENTLY refresh support
    op.execute("""
        CREATE UNIQUE INDEX idx_global_search_id
        ON global_search_index (id)
    """)

    # Create GIN index for full-text search
    op.execute("""
        CREATE INDEX idx_global_search_vector
        ON global_search_index USING GIN (search_vector)
    """)

    # Create trigram index for autocomplete
    op.execute("""
        CREATE INDEX idx_global_search_label_trgm
        ON global_search_index USING GIN (label gin_trgm_ops)
    """)

    # Create index on type for filtered queries
    op.execute("""
        CREATE INDEX idx_global_search_type
        ON global_search_index (type)
    """)


def downgrade() -> None:
    """Revert to original global_search_index without variants."""
    # Drop enhanced MV
    op.execute("DROP INDEX IF EXISTS idx_global_search_type")
    op.execute("DROP INDEX IF EXISTS idx_global_search_label_trgm")
    op.execute("DROP INDEX IF EXISTS idx_global_search_vector")
    op.execute("DROP INDEX IF EXISTS idx_global_search_id")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS global_search_index")

    # Recreate original MV without variants (from previous migration)
    op.execute("""
        CREATE MATERIALIZED VIEW global_search_index AS
        SELECT
            id::text AS id,
            symbol AS label,
            'Gene' AS type,
            'Symbol' AS subtype,
            setweight(to_tsvector('english', symbol), 'A') ||
            setweight(to_tsvector('english', name), 'B') AS search_vector,
            NULL::text AS extra_info
        FROM genes
        UNION ALL
        SELECT
            id::text AS id,
            name AS label,
            'Gene Feature' AS type,
            'Domain' AS subtype,
            to_tsvector('english', name) AS search_vector,
            short_name AS extra_info
        FROM protein_domains
        UNION ALL
        SELECT
            id::text AS id,
            transcript_id AS label,
            'Gene Feature' AS type,
            'Transcript' AS subtype,
            to_tsvector('simple', transcript_id) AS search_vector,
            NULL::text AS extra_info
        FROM transcripts
        UNION ALL
        SELECT
            pmid AS id,
            title AS label,
            'Publication' AS type,
            'Article' AS subtype,
            search_vector,
            journal AS extra_info
        FROM publication_metadata
        UNION ALL
        SELECT
            phenopacket_id AS id,
            subject_id AS label,
            'Phenopacket' AS type,
            'Individual' AS subtype,
            search_vector,
            NULL::text AS extra_info
        FROM phenopackets
    """)

    op.execute("""
        CREATE INDEX idx_global_search_vector
        ON global_search_index USING GIN (search_vector)
    """)
    op.execute("""
        CREATE INDEX idx_global_search_label_trgm
        ON global_search_index USING GIN (label gin_trgm_ops)
    """)
