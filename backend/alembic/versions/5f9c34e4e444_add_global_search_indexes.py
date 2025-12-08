"""add_global_search_indexes

Revision ID: 5f9c34e4e444
Revises: a7b8c9d0e1f2
Create Date: 2025-12-07 15:20:12.516765

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "5f9c34e4e444"
down_revision: Union[str, Sequence[str], None] = "a7b8c9d0e1f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Enable pg_trgm extension for fuzzy matching
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    # 2. Add search_vector to publication_metadata (Generated Column)
    # Using raw SQL because SQLAlchemy generic types for TSVECTOR are tricky in Alembic
    op.execute("""
        ALTER TABLE publication_metadata
        ADD COLUMN IF NOT EXISTS search_vector tsvector
        GENERATED ALWAYS AS (
            setweight(to_tsvector('english', COALESCE(title, '')), 'A') ||
            setweight(to_tsvector('english', COALESCE(journal, '')), 'B')
        ) STORED
    """)

    # 3. Create index on publication search_vector
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_publication_search_vector
        ON publication_metadata USING GIN (search_vector)
    """)

    # 4. Add Trigram indexes for Genes (Symbol, Name) and Protein Domains (Name)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_genes_symbol_trgm
        ON genes USING GIN (symbol gin_trgm_ops)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_genes_name_trgm
        ON genes USING GIN (name gin_trgm_ops)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_protein_domains_name_trgm
        ON protein_domains USING GIN (name gin_trgm_ops)
    """)

    # 5. Create Global Search Materialized View
    # Aggregates searchable text from all major entities
    op.execute("""
        CREATE MATERIALIZED VIEW IF NOT EXISTS global_search_index AS
        SELECT
            id::text AS id,
            symbol AS label,
            'Gene' AS type,
            'Symbol' AS subtype,
            setweight(to_tsvector('english', symbol), 'A') ||
            setweight(to_tsvector('english', name), 'B') AS search_vector,
            NULL::text AS extra_info
        FROM genes
        UNION ALL
        SELECT
            id::text AS id,
            name AS label,
            'Gene Feature' AS type,
            'Domain' AS subtype,
            to_tsvector('english', name) AS search_vector,
            short_name AS extra_info
        FROM protein_domains
        UNION ALL
        SELECT
            id::text AS id,
            transcript_id AS label,
            'Gene Feature' AS type,
            'Transcript' AS subtype,
            to_tsvector('simple', transcript_id) AS search_vector,
            NULL::text AS extra_info
        FROM transcripts
        UNION ALL
        SELECT
            pmid AS id,
            title AS label,
            'Publication' AS type,
            'Article' AS subtype,
            search_vector,
            journal AS extra_info
        FROM publication_metadata
        UNION ALL
        SELECT
            phenopacket_id AS id,
            subject_id AS label,
            'Phenopacket' AS type,
            'Individual' AS subtype,
            search_vector,
            NULL::text AS extra_info
        FROM phenopackets
    """)

    # 6. Index the Materialized View for fast autocomplete and full-text search
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_global_search_vector
        ON global_search_index USING GIN (search_vector)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_global_search_label_trgm
        ON global_search_index USING GIN (label gin_trgm_ops)
    """)


def downgrade() -> None:
    op.execute("DROP MATERIALIZED VIEW IF EXISTS global_search_index")
    op.execute("DROP INDEX IF EXISTS idx_protein_domains_name_trgm")
    op.execute("DROP INDEX IF EXISTS idx_genes_name_trgm")
    op.execute("DROP INDEX IF EXISTS idx_genes_symbol_trgm")
    op.execute("DROP INDEX IF EXISTS idx_publication_search_vector")
    op.execute("ALTER TABLE publication_metadata DROP COLUMN IF EXISTS search_vector")
