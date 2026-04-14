"""add comment_edits table

Revision ID: e5ed3805d054
Revises: 531a38c865bd
Create Date: 2026-04-14 19:02:04.741887

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e5ed3805d054"
down_revision: Union[str, Sequence[str], None] = "531a38c865bd"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create comment_edits append-only log (D.2 §5.1 B2)."""
    op.execute("""
        CREATE TABLE comment_edits (
          id           BIGSERIAL PRIMARY KEY,
          comment_id   BIGINT NOT NULL REFERENCES comments(id) ON DELETE CASCADE,
          editor_id    BIGINT NOT NULL REFERENCES users(id),
          prev_body    TEXT NOT NULL,
          edited_at    TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)
    op.execute("""
        CREATE INDEX ix_comment_edits_comment
          ON comment_edits (comment_id, edited_at DESC);
    """)
    op.execute("""
        COMMENT ON TABLE comment_edits IS
        'Append-only history of comment body edits. Service layer enforces immutability (C1).';
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS comment_edits;")
