"""populate_curated_hpo_terms_for_hnf1b

Revision ID: b1e70338f190
Revises: f74b2759f2a9
Create Date: 2025-11-14 22:26:44.767241

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'b1e70338f190'
down_revision: Union[str, Sequence[str], None] = 'f74b2759f2a9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Populate hpo_terms_lookup with curated minimal dataset for HNF1B phenotyping.

    These 37 terms are the minimal recommended phenotypes extracted from the
    HPOMapper used in the Google Sheets migration. They represent the core
    clinical features that should be assessed in HNF1B patients.
    """
    # Clear any existing data (table should be empty anyway)
    op.execute("TRUNCATE TABLE hpo_terms_lookup")

    # Insert curated HPO terms from HPOMapper (migration/phenopackets/hpo_mapper.py)
    # These terms are grouped by organ system for clarity
    op.execute("""
        INSERT INTO hpo_terms_lookup (hpo_id, label, phenopacket_count) VALUES
        -- Kidney phenotypes (most common in HNF1B)
        ('HP:0000107', 'Renal cyst', 0),
        ('HP:0000083', 'Renal insufficiency', 0),
        ('HP:0012622', 'Chronic kidney disease', 0),
        ('HP:0012623', 'Stage 1 chronic kidney disease', 0),
        ('HP:0012624', 'Stage 2 chronic kidney disease', 0),
        ('HP:0012625', 'Stage 3 chronic kidney disease', 0),
        ('HP:0012626', 'Stage 4 chronic kidney disease', 0),
        ('HP:0003774', 'Stage 5 chronic kidney disease', 0),
        ('HP:0000089', 'Renal hypoplasia', 0),
        ('HP:0004729', 'Solitary functioning kidney', 0),
        ('HP:0000003', 'Multicystic kidney dysplasia', 0),
        ('HP:0010935', 'Increased echogenicity of kidneys', 0),
        ('HP:0000079', 'Abnormality of the urinary system', 0),
        ('HP:0010945', 'Fetal renal anomaly', 0),
        ('HP:0100611', 'Multiple glomerular cysts', 0),
        ('HP:0004719', 'Oligomeganephronia', 0),
        -- Metabolic phenotypes
        ('HP:0002917', 'Hypomagnesemia', 0),
        ('HP:0002149', 'Hyperuricemia', 0),
        ('HP:0001997', 'Gout', 0),
        ('HP:0002900', 'Hypokalemia', 0),
        ('HP:0000843', 'Hyperparathyroidism', 0),
        -- Diabetes/Pancreas
        ('HP:0004904', 'Maturity-onset diabetes of the young', 0),
        ('HP:0100575', 'Pancreatic hypoplasia', 0),
        ('HP:0001738', 'Exocrine pancreatic insufficiency', 0),
        -- Liver
        ('HP:0031865', 'Abnormal liver physiology', 0),
        ('HP:0002910', 'Elevated hepatic transaminase', 0),
        -- Genital
        ('HP:0000078', 'Abnormality of the genital system', 0),
        -- Developmental
        ('HP:0012759', 'Neurodevelopmental abnormality', 0),
        ('HP:0000708', 'Behavioral abnormality', 0),
        ('HP:0001999', 'Abnormal facial shape', 0),
        ('HP:0004322', 'Short stature', 0),
        ('HP:0001622', 'Premature birth', 0),
        -- Neurological
        ('HP:0012443', 'Abnormality of brain morphology', 0),
        ('HP:0001250', 'Seizures', 0),
        -- Other systems
        ('HP:0000478', 'Abnormality of the eye', 0),
        ('HP:0001627', 'Abnormal heart morphology', 0),
        ('HP:0033127', 'Abnormality of the musculoskeletal system', 0)
    """)


def downgrade() -> None:
    """Remove curated HPO terms from lookup table."""
    op.execute("TRUNCATE TABLE hpo_terms_lookup")
