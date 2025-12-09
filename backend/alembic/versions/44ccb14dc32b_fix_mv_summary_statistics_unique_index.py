"""fix_mv_summary_statistics_unique_index

Revision ID: 44ccb14dc32b
Revises: a1b2c3d4e5f6
Create Date: 2025-12-09 09:15:30.964093

Fixes #162: The mv_summary_statistics materialized view cannot be refreshed
concurrently because it uses an expression-based unique index ((1)).

PostgreSQL requires unique indexes on actual columns for CONCURRENTLY refresh.
This migration:
1. Drops the existing mv_summary_statistics view
2. Recreates it with an explicit `id` column (always 1 for singleton)
3. Creates a unique index on the `id` column
4. Updates the refresh function

Reference: https://www.postgresql.org/docs/current/sql-refreshmaterializedview.html
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "44ccb14dc32b"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Recreate mv_summary_statistics with proper unique index on id column."""
    # Drop existing materialized view (CASCADE drops the index too)
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_summary_statistics CASCADE")

    # Recreate with explicit id column for proper unique indexing
    op.execute(
        """
        CREATE MATERIALIZED VIEW mv_summary_statistics AS
        SELECT
            1 AS id,
            COUNT(*) as total_phenopackets,
            COUNT(*) FILTER (
                WHERE jsonb_array_length(
                    COALESCE(phenopacket->'interpretations', '[]'::jsonb)
                ) > 0
            ) as with_variants,
            COUNT(*) FILTER (
                WHERE jsonb_array_length(
                    COALESCE(phenopacket->'phenotypicFeatures', '[]'::jsonb)
                ) > 0
            ) as with_features,
            COUNT(*) FILTER (
                WHERE jsonb_array_length(
                    COALESCE(phenopacket->'diseases', '[]'::jsonb)
                ) > 0
            ) as with_diseases,
            COUNT(DISTINCT phenopacket->'subject'->>'id') as unique_subjects,
            NOW() as refreshed_at
        FROM phenopackets
        WHERE deleted_at IS NULL
        """
    )

    # Create unique index on actual column (not expression)
    # This enables REFRESH MATERIALIZED VIEW CONCURRENTLY
    op.execute(
        """
        CREATE UNIQUE INDEX ix_mv_summary_statistics_id
        ON mv_summary_statistics (id)
        """
    )

    # Recreate the refresh function (unchanged, but ensures it works)
    op.execute(
        """
        CREATE OR REPLACE FUNCTION refresh_all_aggregation_views()
        RETURNS void AS $$
        BEGIN
            REFRESH MATERIALIZED VIEW CONCURRENTLY mv_feature_aggregation;
            REFRESH MATERIALIZED VIEW CONCURRENTLY mv_disease_aggregation;
            REFRESH MATERIALIZED VIEW CONCURRENTLY mv_sex_distribution;
            REFRESH MATERIALIZED VIEW CONCURRENTLY mv_summary_statistics;
        END;
        $$ LANGUAGE plpgsql;
        """
    )


def downgrade() -> None:
    """Restore original mv_summary_statistics with expression-based index.

    Note: The downgraded version cannot use REFRESH CONCURRENTLY.
    """
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_summary_statistics CASCADE")

    # Recreate without id column (original schema)
    op.execute(
        """
        CREATE MATERIALIZED VIEW mv_summary_statistics AS
        SELECT
            COUNT(*) as total_phenopackets,
            COUNT(*) FILTER (
                WHERE jsonb_array_length(
                    COALESCE(phenopacket->'interpretations', '[]'::jsonb)
                ) > 0
            ) as with_variants,
            COUNT(*) FILTER (
                WHERE jsonb_array_length(
                    COALESCE(phenopacket->'phenotypicFeatures', '[]'::jsonb)
                ) > 0
            ) as with_features,
            COUNT(*) FILTER (
                WHERE jsonb_array_length(
                    COALESCE(phenopacket->'diseases', '[]'::jsonb)
                ) > 0
            ) as with_diseases,
            COUNT(DISTINCT phenopacket->'subject'->>'id') as unique_subjects,
            NOW() as refreshed_at
        FROM phenopackets
        WHERE deleted_at IS NULL
        """
    )

    # Restore original expression-based index (non-concurrent compatible)
    op.execute(
        """
        CREATE UNIQUE INDEX ix_mv_summary_statistics_singleton
        ON mv_summary_statistics ((1))
        """
    )

    # Recreate refresh function
    op.execute(
        """
        CREATE OR REPLACE FUNCTION refresh_all_aggregation_views()
        RETURNS void AS $$
        BEGIN
            REFRESH MATERIALIZED VIEW CONCURRENTLY mv_feature_aggregation;
            REFRESH MATERIALIZED VIEW CONCURRENTLY mv_disease_aggregation;
            REFRESH MATERIALIZED VIEW CONCURRENTLY mv_sex_distribution;
            REFRESH MATERIALIZED VIEW CONCURRENTLY mv_summary_statistics;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
