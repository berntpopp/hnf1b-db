"""add comment_mentions table

Revision ID: 483990d7e28f
Revises: e5ed3805d054
Create Date: 2026-04-14 19:02:35.056874

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "483990d7e28f"
down_revision: Union[str, Sequence[str], None] = "e5ed3805d054"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create comment_mentions join table (D.2 §5.1 B3)."""
    op.execute("""
        CREATE TABLE comment_mentions (
          comment_id   BIGINT NOT NULL REFERENCES comments(id) ON DELETE CASCADE,
          user_id      BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
          PRIMARY KEY (comment_id, user_id)
        );
    """)
    op.execute("""
        CREATE INDEX ix_comment_mentions_user ON comment_mentions (user_id);
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS comment_mentions;")
