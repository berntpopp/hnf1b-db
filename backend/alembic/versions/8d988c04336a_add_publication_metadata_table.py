"""add_publication_metadata_table

Revision ID: 8d988c04336a
Revises: 002_jsonb_indexes
Create Date: 2025-10-22 14:53:20.005022

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8d988c04336a'
down_revision: Union[str, Sequence[str], None] = '002_jsonb_indexes'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create publication_metadata table for PubMed caching."""
    # Create publication_metadata table
    op.execute("""
        CREATE TABLE publication_metadata (
            pmid VARCHAR(20) PRIMARY KEY,
            title TEXT NOT NULL,
            authors JSONB NOT NULL,
            journal VARCHAR(255),
            year INTEGER,
            doi VARCHAR(100),
            abstract TEXT,
            data_source VARCHAR(50) DEFAULT 'PubMed',
            fetched_by VARCHAR(100),
            fetched_at TIMESTAMP DEFAULT NOW(),
            api_version VARCHAR(20),
            CONSTRAINT valid_pmid CHECK (pmid LIKE 'PMID:%')
        );
    """)

    # Index for cache lookups by fetched_at
    op.execute("""
        CREATE INDEX idx_publication_metadata_fetched_at
        ON publication_metadata (fetched_at);
    """)

    # Add documentation comments
    op.execute("""
        COMMENT ON TABLE publication_metadata IS
        'Cache for PubMed publication metadata. Data is public domain scientific literature.';
    """)

    op.execute("""
        COMMENT ON COLUMN publication_metadata.authors IS
        'JSONB array of author objects [{name, affiliation}] to preserve order';
    """)


def downgrade() -> None:
    """Drop publication_metadata table."""
    op.drop_table('publication_metadata')
