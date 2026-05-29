"""publication full-text RAG: abstracts, passages, embeddings

Adds the storage substrate for publication abstracts, license-gated
open-access full-text passages, and optional pgvector semantic embeddings,
plus the lexical FTS index used for hybrid retrieval.

Requires the ``vector`` extension (the DB image is switched to
``pgvector/pgvector:pg15`` in the same change). ``tsvector`` is core
PostgreSQL and needs no extension.

Revision ID: e7a1b9c3d2f4
Revises: d4e9c1a2b3f5
Create Date: 2026-05-29

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e7a1b9c3d2f4"
down_revision: Union[str, Sequence[str], None] = "d4e9c1a2b3f5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the full-text RAG schema."""
    # pgvector extension (idempotent). The default postgres superuser in dev,
    # CI, and the pgvector image can run CREATE EXTENSION.
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # --- extend publication_metadata ---------------------------------------
    op.execute("ALTER TABLE publication_metadata ADD COLUMN IF NOT EXISTS pmcid VARCHAR(20)")
    op.execute(
        "ALTER TABLE publication_metadata "
        "ADD COLUMN IF NOT EXISTS coverage VARCHAR(20) NOT NULL DEFAULT 'title_only'"
    )
    op.execute("ALTER TABLE publication_metadata ADD COLUMN IF NOT EXISTS license VARCHAR(50)")
    op.execute(
        "ALTER TABLE publication_metadata "
        "ADD COLUMN IF NOT EXISTS fulltext_fetched_at TIMESTAMPTZ"
    )
    op.execute(
        "ALTER TABLE publication_metadata "
        "ADD CONSTRAINT valid_coverage "
        "CHECK (coverage IN ('full_text', 'abstract_only', 'title_only'))"
    )
    op.execute(
        "COMMENT ON COLUMN publication_metadata.coverage IS "
        "'Retrieval tier: full_text | abstract_only | title_only';"
    )

    # --- publication_fulltext (retrieval-ready passages) -------------------
    op.execute("""
        CREATE TABLE publication_fulltext (
            pmid          VARCHAR(20)  NOT NULL
                          REFERENCES publication_metadata(pmid) ON DELETE CASCADE,
            passage_id    VARCHAR(120) NOT NULL,
            section       VARCHAR(40)  NOT NULL,
            seq           INTEGER      NOT NULL,
            text          TEXT         NOT NULL,
            char_count    INTEGER      NOT NULL,
            token_count   INTEGER      NOT NULL,
            source        VARCHAR(40)  NOT NULL,
            fetched_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
            search_vector tsvector GENERATED ALWAYS AS (
                to_tsvector('english', coalesce(section, '') || ' ' || coalesce(text, ''))
            ) STORED,
            CONSTRAINT pk_publication_fulltext PRIMARY KEY (pmid, passage_id)
        );
    """)
    op.execute(
        "CREATE INDEX idx_publication_fulltext_search "
        "ON publication_fulltext USING GIN (search_vector);"
    )
    op.execute(
        "CREATE INDEX idx_publication_fulltext_pmid_section "
        "ON publication_fulltext (pmid, section);"
    )
    op.execute(
        "COMMENT ON TABLE publication_fulltext IS "
        "'License-gated open-access passages for hybrid (lexical+semantic) RAG. "
        "References section is never stored.';"
    )

    # --- publication_fulltext_embeddings (optional semantic index) ---------
    op.execute("""
        CREATE TABLE publication_fulltext_embeddings (
            passage_id  VARCHAR(120) NOT NULL,
            pmid        VARCHAR(20)  NOT NULL,
            model_name  VARCHAR(80)  NOT NULL DEFAULT 'BAAI/bge-small-en-v1.5',
            embedding   vector(384)  NOT NULL,
            text_hash   VARCHAR(64)  NOT NULL,
            created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
            CONSTRAINT pk_publication_fulltext_embeddings
                PRIMARY KEY (passage_id, model_name),
            CONSTRAINT fk_publication_fulltext_embeddings
                FOREIGN KEY (pmid, passage_id)
                REFERENCES publication_fulltext(pmid, passage_id) ON DELETE CASCADE
        );
    """)
    # HNSW (cosine) index. Cheap on an empty table; the corpus is small (low
    # thousands of passages) so building up-front is negligible.
    op.execute(
        "CREATE INDEX idx_publication_fulltext_embeddings_hnsw "
        "ON publication_fulltext_embeddings "
        "USING hnsw (embedding vector_cosine_ops);"
    )


def downgrade() -> None:
    """Drop the full-text RAG schema (leaves the vector extension in place)."""
    op.execute("DROP TABLE IF EXISTS publication_fulltext_embeddings;")
    op.execute("DROP TABLE IF EXISTS publication_fulltext;")
    op.execute("ALTER TABLE publication_metadata DROP CONSTRAINT IF EXISTS valid_coverage;")
    op.execute("ALTER TABLE publication_metadata DROP COLUMN IF EXISTS fulltext_fetched_at;")
    op.execute("ALTER TABLE publication_metadata DROP COLUMN IF EXISTS license;")
    op.execute("ALTER TABLE publication_metadata DROP COLUMN IF EXISTS coverage;")
    op.execute("ALTER TABLE publication_metadata DROP COLUMN IF EXISTS pmcid;")
