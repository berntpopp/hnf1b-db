"""add_revision_column_for_optimistic_locking

Revision ID: db5aee5fe183
Revises: fff51e479b02
Create Date: 2025-11-16 19:35:13.572324

Changes:
- Add revision column (Integer, default 1) to phenopackets table
- This is the revision counter for optimistic locking
- Keep 'version' as String for GA4GH schema version

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "db5aee5fe183"
down_revision: Union[str, Sequence[str], None] = "fff51e479b02"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add revision column for optimistic locking
    op.add_column(
        "phenopackets",
        sa.Column(
            "revision",
            sa.Integer,
            nullable=False,
            server_default="1",
            comment="Revision counter for optimistic locking",
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("phenopackets", "revision")
