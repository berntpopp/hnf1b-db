"""add comments table

Revision ID: 531a38c865bd
Revises: 20260412_0004
Create Date: 2026-04-14 19:01:37.712136

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '531a38c865bd'
down_revision: Union[str, Sequence[str], None] = '20260412_0004'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create comments table (Wave 7 D.2 spec §5.1 migration B1)."""
    op.execute("""
        CREATE TABLE comments (
          id              BIGSERIAL PRIMARY KEY,
          record_type     TEXT NOT NULL,
          record_id       UUID NOT NULL,
          author_id       BIGINT NOT NULL REFERENCES users(id),
          body_markdown   TEXT NOT NULL
            CHECK (char_length(body_markdown) BETWEEN 1 AND 10000),
          resolved_at     TIMESTAMPTZ NULL,
          resolved_by_id  BIGINT NULL REFERENCES users(id),
          created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
          updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
          deleted_at      TIMESTAMPTZ NULL,
          deleted_by_id   BIGINT NULL REFERENCES users(id),
          CONSTRAINT chk_resolved_consistency
            CHECK ((resolved_at IS NULL) = (resolved_by_id IS NULL)),
          CONSTRAINT chk_deleted_consistency
            CHECK ((deleted_at IS NULL) = (deleted_by_id IS NULL))
        );
    """)
    op.execute("""
        CREATE INDEX ix_comments_record
          ON comments (record_type, record_id, created_at ASC)
          WHERE deleted_at IS NULL;
    """)
    op.execute("""
        CREATE INDEX ix_comments_author ON comments (author_id);
    """)
    op.execute("""
        CREATE INDEX ix_comments_unresolved
          ON comments (record_type, record_id)
          WHERE resolved_at IS NULL AND deleted_at IS NULL;
    """)
    op.execute("""
        COMMENT ON TABLE comments IS
        'Curation-layer comments on domain records. Generic by (record_type, record_id).';
    """)


def downgrade() -> None:
    """Drop comments table."""
    op.execute("DROP TABLE IF EXISTS comments;")
