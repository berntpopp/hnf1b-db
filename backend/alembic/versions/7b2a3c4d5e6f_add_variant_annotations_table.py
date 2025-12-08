"""add_variant_annotations_table

Revision ID: 7b2a3c4d5e6f
Revises: 6a1b2c3d4e5f
Create Date: 2025-12-08

Permanent storage for VEP variant annotations.
Similar pattern to publication_metadata - fetch once, store forever.
Indexed by unique variant ID (VCF format) to avoid redundant API calls.
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7b2a3c4d5e6f"
down_revision: Union[str, Sequence[str], None] = "6a1b2c3d4e5f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create variant_annotations table for VEP caching."""
    # Create variant_annotations table
    op.execute("""
        CREATE TABLE variant_annotations (
            variant_id VARCHAR(100) PRIMARY KEY,
            annotation JSONB NOT NULL,
            most_severe_consequence VARCHAR(100),
            impact VARCHAR(20),
            gene_symbol VARCHAR(50),
            gene_id VARCHAR(50),
            transcript_id VARCHAR(50),
            cadd_score NUMERIC(6,2),
            gnomad_af NUMERIC(12,10),
            gnomad_af_nfe NUMERIC(12,10),
            polyphen_prediction VARCHAR(50),
            polyphen_score NUMERIC(5,3),
            sift_prediction VARCHAR(50),
            sift_score NUMERIC(5,3),
            hgvsc TEXT,
            hgvsp TEXT,
            assembly VARCHAR(20) DEFAULT 'GRCh38',
            data_source VARCHAR(50) DEFAULT 'Ensembl VEP',
            vep_version VARCHAR(20),
            fetched_by VARCHAR(100),
            fetched_at TIMESTAMP DEFAULT NOW(),
            CONSTRAINT valid_variant_id CHECK (
                variant_id ~ '^[0-9XYM]+-[0-9]+-[ACGT]+-[ACGT]+$'
            ),
            CONSTRAINT valid_impact CHECK (
                impact IS NULL OR impact IN ('HIGH', 'MODERATE', 'LOW', 'MODIFIER')
            )
        );
    """)

    # Index for cache lookups
    op.execute("""
        CREATE INDEX idx_variant_annotations_fetched_at
        ON variant_annotations (fetched_at);
    """)

    # Index for gene-based queries
    op.execute("""
        CREATE INDEX idx_variant_annotations_gene_symbol
        ON variant_annotations (gene_symbol);
    """)

    # Index for impact-based queries
    op.execute("""
        CREATE INDEX idx_variant_annotations_impact
        ON variant_annotations (impact);
    """)

    # Index for consequence-based queries
    op.execute("""
        CREATE INDEX idx_variant_annotations_consequence
        ON variant_annotations (most_severe_consequence);
    """)

    # GIN index for full JSONB annotation searches
    op.execute("""
        CREATE INDEX idx_variant_annotations_annotation_gin
        ON variant_annotations USING GIN (annotation);
    """)

    # Add documentation comments
    op.execute("""
        COMMENT ON TABLE variant_annotations IS
        'Permanent cache for Ensembl VEP variant annotations. '
        'Indexed by unique variant ID (VCF format) to avoid redundant API calls. '
        'Similar architecture to publication_metadata table.';
    """)

    op.execute("""
        COMMENT ON COLUMN variant_annotations.variant_id IS
        'Unique variant identifier in VCF format: CHR-POS-REF-ALT (e.g., 17-36459258-A-G)';
    """)

    op.execute("""
        COMMENT ON COLUMN variant_annotations.annotation IS
        'Full VEP API response stored as JSONB for detailed access';
    """)

    op.execute("""
        COMMENT ON COLUMN variant_annotations.cadd_score IS
        'CADD Phred score for variant pathogenicity prediction';
    """)

    op.execute("""
        COMMENT ON COLUMN variant_annotations.gnomad_af IS
        'gnomAD global allele frequency';
    """)


def downgrade() -> None:
    """Drop variant_annotations table."""
    op.drop_table("variant_annotations")
