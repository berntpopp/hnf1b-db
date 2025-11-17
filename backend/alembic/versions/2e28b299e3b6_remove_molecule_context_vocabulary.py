"""remove_molecule_context_vocabulary

Revision ID: 2e28b299e3b6
Revises: 88b3a0c19a89
Create Date: 2025-11-14 23:06:52.636302

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '2e28b299e3b6'
down_revision: Union[str, Sequence[str], None] = '88b3a0c19a89'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Remove molecule_context_values table.

    moleculeContext is annotation-derived (from VEP/VRS), not user-selectable.
    It's determined by the variant representation format (genomic/transcript/protein)
    and should not be a controlled vocabulary for user input.
    """
    op.execute("DROP TABLE IF EXISTS molecule_context_values")


def downgrade() -> None:
    """Restore molecule_context_values table if needed."""
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
