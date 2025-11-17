"""add_deleted_at_for_soft_delete

Revision ID: 30848634d515
Revises: db5aee5fe183
Create Date: 2025-11-16 20:43:16.180402

Adds soft delete support to phenopackets table:
- deleted_at: Timestamp when record was soft-deleted (NULL if not deleted)
- deleted_by: Username who performed the soft delete

This enables audit-preserving deletion where records remain in database
but are filtered from queries. Critical for research data integrity.

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '30848634d515'
down_revision: Union[str, Sequence[str], None] = 'db5aee5fe183'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add deleted_at column for soft delete timestamp
    op.add_column(
        'phenopackets',
        sa.Column(
            'deleted_at',
            sa.DateTime(timezone=True),
            nullable=True,
            comment='Timestamp when record was soft-deleted (NULL if active)'
        )
    )

    # Add deleted_by column to track who performed the deletion
    op.add_column(
        'phenopackets',
        sa.Column(
            'deleted_by',
            sa.String(100),
            nullable=True,
            comment='Username who performed the soft delete'
        )
    )

    # Add index for efficient filtering of non-deleted records
    op.create_index(
        'ix_phenopackets_deleted_at',
        'phenopackets',
        ['deleted_at'],
        postgresql_where=sa.text('deleted_at IS NULL')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_phenopackets_deleted_at', table_name='phenopackets')
    op.drop_column('phenopackets', 'deleted_by')
    op.drop_column('phenopackets', 'deleted_at')
