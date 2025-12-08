"""add_5part_cnv_format

Revision ID: 9d4e5f6g7h8i
Revises: 8c3d4e5f6g7h
Create Date: 2025-12-08

Add support for 5-part CNV format with END position:
- CNVs with END: CHR-POS-END-REF-<TYPE> (e.g., 17-37733556-37733821-C-<DEL>)

Per VCF 4.3 specification, symbolic alleles (structural variants) should include
the END position to uniquely identify variants with the same start but different
end coordinates.
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9d4e5f6g7h8i"
down_revision: Union[str, Sequence[str], None] = "8c3d4e5f6g7h"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Update valid_variant_id constraint to support 5-part CNV format."""
    # Drop the old constraint
    op.execute("""
        ALTER TABLE variant_annotations
        DROP CONSTRAINT IF EXISTS valid_variant_id;
    """)

    # Add the new constraint that supports all CNV formats including 5-part
    # Five valid formats:
    # 1. SNVs/indels: CHR-POS-REF-ALT (e.g., 17-36459258-A-G)
    # 2. CNVs symbolic 4-part: CHR-POS-REF-<TYPE> (e.g., 17-36459258-A-<DEL>)
    # 3. CNVs with END 5-part: CHR-POS-END-REF-<TYPE> (e.g., 17-37733556-37733821-C-<DEL>)
    # 4. CNVs region: CHR-START-END-TYPE (e.g., 17-36459258-37832869-DEL)
    # 5. Internal CNV: var:GENE:CHROM:START-END:TYPE (e.g., var:HNF1B:17:36459258-37832869:DEL)
    op.execute("""
        ALTER TABLE variant_annotations
        ADD CONSTRAINT valid_variant_id CHECK (
            -- SNVs and small indels (e.g., 17-36459258-A-G)
            variant_id ~ '^[0-9XYM]+-[0-9]+-[ACGT]+-[ACGT]+$'
            OR
            -- CNVs with symbolic alleles 4-part (e.g., 17-36459258-A-<DEL>)
            variant_id ~ '^[0-9XYM]+-[0-9]+-[ACGT]+-<(DEL|DUP|INS|INV|CNV)>$'
            OR
            -- CNVs with END position 5-part (e.g., 17-37733556-37733821-C-<DEL>)
            -- Per VCF 4.3 spec: symbolic alleles need END for unique identification
            variant_id ~ '^[0-9XYM]+-[0-9]+-[0-9]+-[ACGT]+-<(DEL|DUP|INS|INV|CNV)>$'
            OR
            -- CNVs in region format (e.g., 17-36459258-37832869-DEL)
            variant_id ~ '^[0-9XYM]+-[0-9]+-[0-9]+-(DEL|DUP|INS|INV|CNV)$'
            OR
            -- Internal CNV format (e.g., var:HNF1B:17:36459258-37832869:DEL)
            variant_id ~ '^var:[A-Za-z0-9]+:[0-9XYM]+:[0-9]+-[0-9]+:(DEL|DUP|INS|INV|CNV)$'
        );
    """)

    # Update column comment to document all supported formats
    op.execute("""
        COMMENT ON COLUMN variant_annotations.variant_id IS
        'Unique variant identifier. Supported formats:\n'
        '- SNV/indel: CHR-POS-REF-ALT (e.g., 17-36459258-A-G)\n'
        '- CNV symbolic 4-part: CHR-POS-REF-<TYPE> (e.g., 17-36459258-A-<DEL>)\n'
        '- CNV with END 5-part: CHR-POS-END-REF-<TYPE> (e.g., 17-37733556-37733821-C-<DEL>)\n'
        '- CNV region: CHR-START-END-TYPE (e.g., 17-36459258-37832869-DEL)';
    """)


def downgrade() -> None:
    """Restore the previous constraint without 5-part CNV format."""
    op.execute("""
        ALTER TABLE variant_annotations
        DROP CONSTRAINT IF EXISTS valid_variant_id;
    """)

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

    op.execute("""
        COMMENT ON COLUMN variant_annotations.variant_id IS
        'Unique variant identifier. Supported formats:\n'
        '- SNV/indel: CHR-POS-REF-ALT (e.g., 17-36459258-A-G)\n'
        '- CNV symbolic: CHR-POS-REF-<TYPE> (e.g., 17-36459258-A-<DEL>)\n'
        '- CNV region: CHR-START-END-TYPE (e.g., 17-36459258-37832869-DEL)';
    """)
