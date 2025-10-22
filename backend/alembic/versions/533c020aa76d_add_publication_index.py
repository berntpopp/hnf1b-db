"""add_publication_index

Revision ID: 533c020aa76d
Revises: 8d988c04336a
Create Date: 2025-10-22 17:09:02.525754

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "533c020aa76d"
down_revision: Union[str, Sequence[str], None] = "8d988c04336a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create GIN index for externalReferences queries."""
    # Create GIN index for fast containment queries on externalReferences
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_phenopackets_external_refs
        ON phenopackets
        USING GIN ((phenopacket->'metaData'->'externalReferences'));
    """)


def downgrade() -> None:
    """Drop GIN index for externalReferences queries."""
    op.execute("""
        DROP INDEX IF EXISTS idx_phenopackets_external_refs;
    """)
