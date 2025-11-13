"""add cursor pagination index on phenopackets

Revision ID: 72e990f17d42
Revises: 131bded2e26e
Create Date: 2025-11-10 13:42:56.300519

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "72e990f17d42"
down_revision: Union[str, Sequence[str], None] = "131bded2e26e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: Add composite index for cursor pagination."""
    # Create composite index on (created_at DESC, id DESC) for efficient cursor pagination
    # This index optimizes range queries like:
    # WHERE created_at < ? OR (created_at = ? AND id < ?)
    # Used by cursor pagination for stable, deterministic ordering
    op.create_index(
        "idx_phenopackets_cursor_pagination",
        "phenopackets",
        [sa.text("created_at DESC"), sa.text("id DESC")],
        unique=False,
        postgresql_using="btree",
    )


def downgrade() -> None:
    """Downgrade schema: Remove cursor pagination index."""
    op.drop_index("idx_phenopackets_cursor_pagination", table_name="phenopackets")
