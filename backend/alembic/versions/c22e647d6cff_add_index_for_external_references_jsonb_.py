"""add index for external references jsonb queries

Revision ID: c22e647d6cff
Revises: 93b3e6984a6c
Create Date: 2025-11-13 16:01:18.091957

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c22e647d6cff"
down_revision: Union[str, Sequence[str], None] = "93b3e6984a6c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add GIN index for external references JSONB queries.

    This index optimizes queries that search for publications in
    phenopacket metadata (e.g., /by-publication/{pmid} endpoint).

    Note: Uses standard CREATE INDEX (not CONCURRENTLY) because
    CONCURRENTLY cannot run inside Alembic's transaction block.
    For production deployments with large tables, consider running
    this migration manually with CONCURRENTLY outside a transaction.
    """
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_phenopackets_external_references
        ON phenopackets USING GIN ((phenopacket->'metaData'->'externalReferences'))
        """
    )


def downgrade() -> None:
    """Remove GIN index for external references."""
    op.execute("DROP INDEX IF EXISTS idx_phenopackets_external_references")
