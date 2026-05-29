"""fix POU-Specific protein domain start boundary (8 -> 90)

Revision ID: c8d2a3f1e0b5
Revises: b7c1f0a9d2e4
Create Date: 2026-05-29 02:10:00.000000

The HNF1B "POU-Specific Domain" was seeded with start=8, conflating the
upstream dimerization region. UniProt P35680 places the POU-specific domain at
aa 90–173, which is also what the survival-analysis domain table uses. This
data migration aligns the already-seeded ``protein_domains`` row so
``get_gene_context`` and the survival metadata agree (single boundary).
"""

from typing import Sequence, Union

from alembic import op

revision: str = "c8d2a3f1e0b5"
down_revision: Union[str, Sequence[str], None] = "b7c1f0a9d2e4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Correct the POU-Specific domain start from 8 to 90 (UniProt P35680)."""
    op.execute(
        'UPDATE protein_domains SET "start" = 90 '
        "WHERE name = 'POU-Specific Domain' AND \"start\" = 8;"
    )


def downgrade() -> None:
    """Restore the previous start=8 value."""
    op.execute(
        'UPDATE protein_domains SET "start" = 8 '
        "WHERE name = 'POU-Specific Domain' AND \"start\" = 90;"
    )
