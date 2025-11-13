"""fix_search_vector_trigger_camelcase

Revision ID: f74b2759f2a9
Revises: c22e647d6cff
Create Date: 2025-11-13 17:50:33.014490

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'f74b2759f2a9'
down_revision: Union[str, Sequence[str], None] = 'c22e647d6cff'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Fix search_vector trigger to use correct camelCase field names.

    The original migration 8baf0de6a441 used snake_case field names
    (phenotypic_features, variant_interpretation, etc.) instead of
    camelCase names required by GA4GH Phenopackets v2 schema.

    This caused search_vector to remain NULL/empty, breaking full-text
    search and HPO autocomplete functionality.
    """
    # 1. Drop existing trigger and function
    op.execute("""
        DROP TRIGGER IF EXISTS phenopackets_search_vector_trigger ON phenopackets
    """)
    op.execute("""
        DROP FUNCTION IF EXISTS phenopackets_search_vector_update()
    """)

    # 2. Recreate function with correct camelCase field names
    op.execute("""
        CREATE OR REPLACE FUNCTION phenopackets_search_vector_update()
        RETURNS TRIGGER AS $$
        DECLARE
            phenotype_labels text;
            disease_labels text;
            gene_symbols text;
        BEGIN
            -- Extract phenotype labels (FIXED: phenotypicFeatures not phenotypic_features)
            SELECT string_agg(value->'type'->>'label', ' ')
            INTO phenotype_labels
            FROM jsonb_array_elements(NEW.phenopacket->'phenotypicFeatures');

            -- Extract disease labels (correct - diseases is not camelCase in schema)
            SELECT string_agg(value->'term'->>'label', ' ')
            INTO disease_labels
            FROM jsonb_array_elements(NEW.phenopacket->'diseases');

            -- Extract gene symbols (FIXED: variantInterpretation, variationDescriptor, geneContext, genomicInterpretations)
            SELECT string_agg(
                gi.value->'variantInterpretation'->'variationDescriptor'->'geneContext'->>'symbol', ' ')
            INTO gene_symbols
            FROM jsonb_array_elements(NEW.phenopacket->'interpretations') AS interp,
                 jsonb_array_elements(interp.value->'diagnosis'->'genomicInterpretations') AS gi;

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

    # 3. Recreate trigger
    op.execute("""
        CREATE TRIGGER phenopackets_search_vector_trigger
        BEFORE INSERT OR UPDATE ON phenopackets
        FOR EACH ROW
        EXECUTE FUNCTION phenopackets_search_vector_update()
    """)

    # 4. Repopulate search_vector for all existing phenopackets
    op.execute("""
        UPDATE phenopackets
        SET phenopacket = phenopacket
        WHERE search_vector IS NULL OR search_vector = ''::tsvector
    """)


def downgrade() -> None:
    """Revert to original (buggy) snake_case version.

    Note: This downgrade is provided for rollback purposes but will
    reintroduce the bug where search_vector remains NULL/empty.
    """
    # Drop corrected trigger and function
    op.execute("""
        DROP TRIGGER IF EXISTS phenopackets_search_vector_trigger ON phenopackets
    """)
    op.execute("""
        DROP FUNCTION IF EXISTS phenopackets_search_vector_update()
    """)

    # Recreate with original buggy snake_case field names
    op.execute("""
        CREATE OR REPLACE FUNCTION phenopackets_search_vector_update()
        RETURNS TRIGGER AS $$
        DECLARE
            phenotype_labels text;
            disease_labels text;
            gene_symbols text;
        BEGIN
            -- Extract phenotype labels (BUGGY: phenotypic_features)
            SELECT string_agg(value->'type'->>'label', ' ')
            INTO phenotype_labels
            FROM jsonb_array_elements(NEW.phenopacket->'phenotypic_features');

            -- Extract disease labels
            SELECT string_agg(value->'term'->>'label', ' ')
            INTO disease_labels
            FROM jsonb_array_elements(NEW.phenopacket->'diseases');

            -- Extract gene symbols (BUGGY: variant_interpretation, etc.)
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

    # Recreate trigger
    op.execute("""
        CREATE TRIGGER phenopackets_search_vector_trigger
        BEFORE INSERT OR UPDATE ON phenopackets
        FOR EACH ROW
        EXECUTE FUNCTION phenopackets_search_vector_update()
    """)
