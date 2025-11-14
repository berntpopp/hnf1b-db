"""add_phenopacket_controlled_vocabularies

Revision ID: 88b3a0c19a89
Revises: 0bd1567a483c
Create Date: 2025-11-14 22:48:25.918831

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '88b3a0c19a89'
down_revision: Union[str, Sequence[str], None] = '0bd1567a483c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create controlled vocabulary lookup tables for GA4GH Phenopackets v2 standard.

    These tables provide API-driven dropdown values to ensure frontend never
    hardcodes backend functionality (per user requirement).

    Tables created:
    - sex_values: Subject sex values
    - interpretation_status_values: ACMG variant classification
    - progress_status_values: Case interpretation progress
    - molecule_context_values: Variant molecular context
    - allelic_state_values: GENO ontology zygosity terms
    - evidence_code_values: ECO ontology evidence codes
    """
    # Create sex_values table
    op.execute("""
        CREATE TABLE IF NOT EXISTS sex_values (
            value VARCHAR(20) PRIMARY KEY,
            label VARCHAR(100) NOT NULL,
            description TEXT,
            sort_order INTEGER NOT NULL
        )
    """)

    op.execute("""
        INSERT INTO sex_values (value, label, description, sort_order) VALUES
        ('MALE', 'Male', 'Genetic or phenotypic male', 1),
        ('FEMALE', 'Female', 'Genetic or phenotypic female', 2),
        ('OTHER_SEX', 'Other', 'Indeterminate or other sex', 3),
        ('UNKNOWN_SEX', 'Unknown', 'Sex not determined or not recorded', 4)
    """)

    # Create interpretation_status_values table (ACMG classification)
    op.execute("""
        CREATE TABLE IF NOT EXISTS interpretation_status_values (
            value VARCHAR(50) PRIMARY KEY,
            label VARCHAR(100) NOT NULL,
            description TEXT,
            category VARCHAR(20) NOT NULL,
            sort_order INTEGER NOT NULL
        )
    """)

    op.execute("""
        INSERT INTO interpretation_status_values (value, label, description, category, sort_order) VALUES
        ('PATHOGENIC', 'Pathogenic', 'Sufficient evidence of pathogenicity (ACMG)', 'pathogenic', 1),
        ('LIKELY_PATHOGENIC', 'Likely pathogenic', 'High confidence of pathogenicity (ACMG)', 'pathogenic', 2),
        ('UNCERTAIN_SIGNIFICANCE', 'Uncertain significance', 'Insufficient evidence (ACMG VUS)', 'uncertain', 3),
        ('LIKELY_BENIGN', 'Likely benign', 'High confidence of benign impact (ACMG)', 'benign', 4),
        ('BENIGN', 'Benign', 'Sufficient evidence of benign impact (ACMG)', 'benign', 5),
        ('CAUSATIVE', 'Causative', 'Variant is causative of phenotype', 'pathogenic', 6),
        ('CONTRIBUTORY', 'Contributory', 'Variant contributes to phenotype', 'pathogenic', 7),
        ('CANDIDATE', 'Candidate', 'Variant is a candidate for causation', 'uncertain', 8),
        ('REJECTED', 'Rejected', 'Variant ruled out as causative', 'benign', 9)
    """)

    # Create progress_status_values table
    op.execute("""
        CREATE TABLE IF NOT EXISTS progress_status_values (
            value VARCHAR(20) PRIMARY KEY,
            label VARCHAR(100) NOT NULL,
            description TEXT,
            sort_order INTEGER NOT NULL
        )
    """)

    op.execute("""
        INSERT INTO progress_status_values (value, label, description, sort_order) VALUES
        ('COMPLETED', 'Completed', 'Interpretation completed', 1),
        ('SOLVED', 'Solved', 'Case solved with causal variant identified', 2),
        ('UNSOLVED', 'Unsolved', 'Case remains unsolved after investigation', 3),
        ('IN_PROGRESS', 'In progress', 'Interpretation currently underway', 4),
        ('UNKNOWN', 'Unknown', 'Progress status not determined', 5)
    """)

    # Create molecule_context_values table
    op.execute("""
        CREATE TABLE IF NOT EXISTS molecule_context_values (
            value VARCHAR(20) PRIMARY KEY,
            label VARCHAR(100) NOT NULL,
            description TEXT,
            sort_order INTEGER NOT NULL
        )
    """)

    op.execute("""
        INSERT INTO molecule_context_values (value, label, description, sort_order) VALUES
        ('genomic', 'Genomic', 'Variant represented at genomic DNA level', 1),
        ('transcript', 'Transcript', 'Variant represented at transcript (cDNA) level', 2),
        ('protein', 'Protein', 'Variant represented at protein level', 3)
    """)

    # Create allelic_state_values table (GENO ontology)
    op.execute("""
        CREATE TABLE IF NOT EXISTS allelic_state_values (
            id VARCHAR(20) PRIMARY KEY,
            label VARCHAR(100) NOT NULL,
            description TEXT,
            sort_order INTEGER NOT NULL
        )
    """)

    op.execute("""
        INSERT INTO allelic_state_values (id, label, description, sort_order) VALUES
        ('GENO:0000135', 'heterozygous', 'Having one variant allele and one reference allele', 1),
        ('GENO:0000136', 'homozygous', 'Having two identical variant alleles', 2),
        ('GENO:0000134', 'hemizygous', 'Having a single allele at a locus (e.g., X-linked in males)', 3),
        ('GENO:0000402', 'compound heterozygous', 'Having two different variant alleles at the same locus', 4)
    """)

    # Create evidence_code_values table (ECO ontology)
    op.execute("""
        CREATE TABLE IF NOT EXISTS evidence_code_values (
            id VARCHAR(20) PRIMARY KEY,
            label VARCHAR(200) NOT NULL,
            description TEXT,
            category VARCHAR(50),
            sort_order INTEGER NOT NULL
        )
    """)

    op.execute("""
        INSERT INTO evidence_code_values (id, label, description, category, sort_order) VALUES
        ('ECO:0000033', 'author statement', 'Evidence from published author statement', 'literature', 1),
        ('ECO:0000218', 'clinical study', 'Evidence from clinical research study', 'clinical', 2),
        ('ECO:0000362', 'computational evidence', 'Evidence from computational analysis or prediction', 'computational', 3),
        ('ECO:0000205', 'curator inference', 'Evidence from expert curator assessment', 'curation', 4),
        ('ECO:0000006', 'experimental evidence', 'Evidence from laboratory experimental work', 'experimental', 5),
        ('ECO:0000501', 'evidence from database', 'Evidence from curated database record', 'database', 6)
    """)


def downgrade() -> None:
    """Drop controlled vocabulary lookup tables."""
    op.execute("DROP TABLE IF EXISTS evidence_code_values")
    op.execute("DROP TABLE IF EXISTS allelic_state_values")
    op.execute("DROP TABLE IF EXISTS molecule_context_values")
    op.execute("DROP TABLE IF EXISTS progress_status_values")
    op.execute("DROP TABLE IF EXISTS interpretation_status_values")
    op.execute("DROP TABLE IF EXISTS sex_values")
