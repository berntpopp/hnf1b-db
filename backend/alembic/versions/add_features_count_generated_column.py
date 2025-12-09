"""add_features_count_generated_column

Revision ID: 5c8d7e9f0a1b
Revises: 48c7a668d614
Create Date: 2025-12-09

Adds PostgreSQL generated columns for server-side sorting:
- features_count: Count of phenotypic features (JSONB array length)
- has_variant: Boolean indicating if phenopacket has genomic interpretations

These columns enable server-side sorting on computed values that were
previously only available client-side.
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "5c8d7e9f0a1b"
down_revision: Union[str, Sequence[str], None] = "48c7a668d614"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add generated columns for server-side sorting.

    PostgreSQL generated columns are computed from expressions and stored
    automatically, staying in sync with the source JSONB data.
    """
    # Add features_count as a GENERATED ALWAYS column
    # This counts the phenotypicFeatures array length
    op.execute("""
        ALTER TABLE phenopackets
        ADD COLUMN IF NOT EXISTS features_count INTEGER
        GENERATED ALWAYS AS (
            jsonb_array_length(
                COALESCE(phenopacket->'phenotypicFeatures', '[]'::jsonb)
            )
        ) STORED;
    """)

    # Add has_variant as a GENERATED ALWAYS column
    # This checks if interpretations array has any elements
    op.execute("""
        ALTER TABLE phenopackets
        ADD COLUMN IF NOT EXISTS has_variant BOOLEAN
        GENERATED ALWAYS AS (
            jsonb_array_length(
                COALESCE(phenopacket->'interpretations', '[]'::jsonb)
            ) > 0
        ) STORED;
    """)

    # Add indexes for efficient sorting
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_phenopackets_features_count
        ON phenopackets(features_count DESC);
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_phenopackets_has_variant
        ON phenopackets(has_variant);
    """)


def downgrade() -> None:
    """Remove generated columns and their indexes."""
    op.execute("DROP INDEX IF EXISTS idx_phenopackets_has_variant;")
    op.execute("DROP INDEX IF EXISTS idx_phenopackets_features_count;")
    op.execute("ALTER TABLE phenopackets DROP COLUMN IF EXISTS has_variant;")
    op.execute("ALTER TABLE phenopackets DROP COLUMN IF EXISTS features_count;")
