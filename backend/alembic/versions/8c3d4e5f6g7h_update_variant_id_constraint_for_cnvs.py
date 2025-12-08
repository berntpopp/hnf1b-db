"""update_variant_id_constraint_for_cnvs

Revision ID: 8c3d4e5f6g7h
Revises: 7b2a3c4d5e6f
Create Date: 2025-12-08

Update the valid_variant_id constraint to support CNV/structural variant formats:
- SNVs/indels: CHR-POS-REF-ALT (e.g., 17-36459258-A-G)
- CNVs symbolic: CHR-POS-REF-<TYPE> (e.g., 17-36459258-A-<DEL>)
- CNVs region: CHR-START-END-TYPE (e.g., 17-36459258-37832869-DEL)
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8c3d4e5f6g7h"
down_revision: Union[str, Sequence[str], None] = "7b2a3c4d5e6f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Update valid_variant_id constraint to support CNV formats."""
    # Drop the old constraint
    op.execute("""
        ALTER TABLE variant_annotations
        DROP CONSTRAINT IF EXISTS valid_variant_id;
    """)

    # Add the new constraint that supports CNV formats
    # Three valid formats:
    # 1. SNVs/indels: CHR-POS-REF-ALT (e.g., 17-36459258-A-G)
    # 2. CNVs symbolic: CHR-POS-REF-<TYPE> (e.g., 17-36459258-A-<DEL>)
    # 3. CNVs region: CHR-START-END-TYPE (e.g., 17-36459258-37832869-DEL)
    op.execute("""
        ALTER TABLE variant_annotations
        ADD CONSTRAINT valid_variant_id CHECK (
            -- SNVs and small indels (e.g., 17-36459258-A-G)
            variant_id ~ '^[0-9XYM]+-[0-9]+-[ACGT]+-[ACGT]+$'
            OR
            -- CNVs with symbolic alleles (e.g., 17-36459258-A-<DEL>)
            variant_id ~ '^[0-9XYM]+-[0-9]+-[ACGT]+-<(DEL|DUP|INS|INV|CNV)>$'
            OR
            -- CNVs in region format (e.g., 17-36459258-37832869-DEL)
            variant_id ~ '^[0-9XYM]+-[0-9]+-[0-9]+-(DEL|DUP|INS|INV|CNV)$'
        );
    """)

    # Update column comment to document all supported formats
    op.execute("""
        COMMENT ON COLUMN variant_annotations.variant_id IS
        'Unique variant identifier. Supported formats:\n'
        '- SNV/indel: CHR-POS-REF-ALT (e.g., 17-36459258-A-G)\n'
        '- CNV symbolic: CHR-POS-REF-<TYPE> (e.g., 17-36459258-A-<DEL>)\n'
        '- CNV region: CHR-START-END-TYPE (e.g., 17-36459258-37832869-DEL)';
    """)


def downgrade() -> None:
    """Restore the original valid_variant_id constraint (SNV-only)."""
    op.execute("""
        ALTER TABLE variant_annotations
        DROP CONSTRAINT IF EXISTS valid_variant_id;
    """)

    op.execute("""
        ALTER TABLE variant_annotations
        ADD CONSTRAINT valid_variant_id CHECK (
            variant_id ~ '^[0-9XYM]+-[0-9]+-[ACGT]+-[ACGT]+$'
        );
    """)

    op.execute("""
        COMMENT ON COLUMN variant_annotations.variant_id IS
        'Unique variant identifier in VCF format: CHR-POS-REF-ALT (e.g., 17-36459258-A-G)';
    """)
