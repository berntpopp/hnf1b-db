"""add_change_patch_and_summary_to_audit

Revision ID: fff51e479b02
Revises: 2e28b299e3b6
Create Date: 2025-11-16 19:02:07.763762

"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'fff51e479b02'
down_revision: Union[str, Sequence[str], None] = '2e28b299e3b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add change_patch column for JSON Patch (RFC 6902) format
    op.add_column(
        'phenopacket_audit',
        sa.Column('change_patch', JSONB, nullable=True)
    )

    # Add change_summary column for human-readable summary
    op.add_column(
        'phenopacket_audit',
        sa.Column('change_summary', sa.Text, nullable=True)
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('phenopacket_audit', 'change_summary')
    op.drop_column('phenopacket_audit', 'change_patch')
