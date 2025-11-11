"""add_fulltext_search_to_phenopackets

Revision ID: 8baf0de6a441
Revises: 72e990f17d42
Create Date: 2025-11-10 15:38:08.691308

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8baf0de6a441"
down_revision: Union[str, Sequence[str], None] = "72e990f17d42"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: Add full-text search to phenopackets and HPO lookup table."""
    # 1. Add search_vector column (will be populated by trigger)
    op.execute("""
        ALTER TABLE phenopackets
        ADD COLUMN search_vector tsvector
    """)

    # 2. Create function to update search_vector from JSONB
    op.execute("""
        CREATE OR REPLACE FUNCTION phenopackets_search_vector_update()
        RETURNS TRIGGER AS $$
        DECLARE
            phenotype_labels text;
            disease_labels text;
            gene_symbols text;
        BEGIN
            -- Extract phenotype labels
            SELECT string_agg(value->'type'->>'label', ' ')
            INTO phenotype_labels
            FROM jsonb_array_elements(NEW.phenopacket->'phenotypic_features');

            -- Extract disease labels
            SELECT string_agg(value->'term'->>'label', ' ')
            INTO disease_labels
            FROM jsonb_array_elements(NEW.phenopacket->'diseases');

            -- Extract gene symbols
            SELECT string_agg(
                gi.value->'variant_interpretation'->'variation_descriptor'->'gene_context'->>'symbol', ' ')
            INTO gene_symbols
            FROM jsonb_array_elements(NEW.phenopacket->'interpretations') AS interp,
                 jsonb_array_elements(interp.value->'diagnosis'->'genomic_interpretations') AS gi;

            -- Build search vector
            NEW.search_vector :=
                to_tsvector('english', COALESCE(NEW.phenopacket->'subject'->>'id', '')) ||
                to_tsvector('english', COALESCE(phenotype_labels, '')) ||
                to_tsvector('english', COALESCE(disease_labels, '')) ||
                to_tsvector('english', COALESCE(gene_symbols, ''));

            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    # 3. Create trigger to auto-update search_vector
    op.execute("""
        CREATE TRIGGER phenopackets_search_vector_trigger
        BEFORE INSERT OR UPDATE ON phenopackets
        FOR EACH ROW
        EXECUTE FUNCTION phenopackets_search_vector_update()
    """)

    # 4. Populate search_vector for existing records
    op.execute("""
        UPDATE phenopackets
        SET phenopacket = phenopacket
        WHERE search_vector IS NULL
    """)

    # 5. Create GIN index on search_vector for fast full-text queries
    op.execute("""
        CREATE INDEX idx_phenopackets_fulltext_search
        ON phenopackets USING GIN (search_vector)
    """)

    # 3. Create HPO terms lookup table for autocomplete
    op.execute("""
        CREATE TABLE hpo_terms_lookup (
            hpo_id VARCHAR(20) PRIMARY KEY,
            label TEXT NOT NULL,
            phenopacket_count INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)

    # 4. Create trigram index for fuzzy HPO term search
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute("""
        CREATE INDEX idx_hpo_lookup_label_trgm
        ON hpo_terms_lookup USING GIN (label gin_trgm_ops)
    """)

    # 5. Populate HPO lookup table from existing phenopackets
    op.execute("""
        INSERT INTO hpo_terms_lookup (hpo_id, label, phenopacket_count)
        SELECT DISTINCT
            pf.value->'type'->>'id' AS hpo_id,
            pf.value->'type'->>'label' AS label,
            COUNT(DISTINCT p.id) AS phenopacket_count
        FROM phenopackets p,
             jsonb_array_elements(p.phenopacket->'phenotypic_features') AS pf
        WHERE pf.value->'type'->>'id' IS NOT NULL
          AND pf.value->'type'->>'id' LIKE 'HP:%'
        GROUP BY hpo_id, label
        ORDER BY phenopacket_count DESC
    """)


def downgrade() -> None:
    """Downgrade schema: Remove full-text search and HPO lookup table."""
    # Drop HPO lookup table and indexes
    op.execute("DROP INDEX IF EXISTS idx_hpo_lookup_label_trgm")
    op.execute("DROP TABLE IF EXISTS hpo_terms_lookup")

    # Drop full-text search infrastructure
    op.execute(
        "DROP TRIGGER IF EXISTS phenopackets_search_vector_trigger ON phenopackets"
    )
    op.execute("DROP FUNCTION IF EXISTS phenopackets_search_vector_update()")
    op.execute("DROP INDEX IF EXISTS idx_phenopackets_fulltext_search")
    op.execute("ALTER TABLE phenopackets DROP COLUMN IF EXISTS search_vector")
