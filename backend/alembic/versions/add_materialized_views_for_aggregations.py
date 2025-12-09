"""add_materialized_views_for_aggregations

Revision ID: a7b8c9d0e1f2
Revises: 62362ff6f580
Create Date: 2025-12-06 22:30:00.000000

Creates PostgreSQL materialized views for optimizing expensive JSONB aggregation queries.
These views pre-compute statistics that are frequently accessed but rarely updated.

Materialized Views:
- mv_feature_aggregation: HPO term counts (present/absent/not_reported)
- mv_disease_aggregation: Disease distribution
- mv_sex_distribution: Sex distribution statistics
- mv_summary_statistics: Overall phenopacket statistics

Refresh Strategy:
- Use REFRESH MATERIALIZED VIEW CONCURRENTLY after data imports
- Views are refreshed via application code or scheduled jobs
- CONCURRENTLY allows reads during refresh (requires UNIQUE index)

Performance Impact:
- Aggregation queries: O(n) JSONB scan -> O(1) indexed lookup
- Expected speedup: 10-100x for large datasets

Deployment Notes:
- DOWNTIME WARNING: Creating materialized views involves full table scans.
  For large datasets (1000+ phenopackets), this may take several seconds.
  Consider running during maintenance windows for production deployments.
- Initial creation is NOT concurrent (CREATE MATERIALIZED VIEW cannot be concurrent).
  Only subsequent REFRESH operations can use CONCURRENTLY with the UNIQUE indexes.
- If the migration fails mid-way, the downgrade() function will clean up all views.
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a7b8c9d0e1f2"
down_revision: Union[str, Sequence[str], None] = "62362ff6f580"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create materialized views for aggregation optimization."""
    # 1. Feature Aggregation Materialized View
    # Pre-computes HPO term statistics including present/absent/not_reported counts
    op.execute(
        """
        CREATE MATERIALIZED VIEW mv_feature_aggregation AS
        WITH total_phenopackets AS (
            SELECT COUNT(*) as total FROM phenopackets WHERE deleted_at IS NULL
        ),
        feature_counts AS (
            SELECT
                feature->'type'->>'id' as hpo_id,
                feature->'type'->>'label' as label,
                SUM(CASE WHEN NOT COALESCE((feature->>'excluded')::boolean, false)
                    THEN 1 ELSE 0 END) as present_count,
                SUM(CASE WHEN COALESCE((feature->>'excluded')::boolean, false)
                    THEN 1 ELSE 0 END) as absent_count
            FROM
                phenopackets,
                jsonb_array_elements(phenopacket->'phenotypicFeatures') as feature
            WHERE
                deleted_at IS NULL
            GROUP BY
                feature->'type'->>'id',
                feature->'type'->>'label'
        )
        SELECT
            fc.hpo_id,
            fc.label,
            fc.present_count::integer,
            fc.absent_count::integer,
            (tp.total - fc.present_count - fc.absent_count)::integer as not_reported_count,
            tp.total::integer as total_phenopackets,
            CASE WHEN tp.total > 0
                THEN ROUND((fc.present_count::numeric / tp.total) * 100, 2)
                ELSE 0
            END as present_percentage,
            NOW() as refreshed_at
        FROM feature_counts fc, total_phenopackets tp
        ORDER BY fc.present_count DESC
        """
    )

    # Create unique index for CONCURRENTLY refresh
    # Note: Cannot use CONCURRENTLY in migration transaction, but can use CONCURRENTLY later
    # Using composite key (hpo_id, label) because same HPO ID can have different label text
    op.execute(
        """
        CREATE UNIQUE INDEX ix_mv_feature_aggregation_hpo_id_label
        ON mv_feature_aggregation (hpo_id, label)
        """
    )

    # Create additional indexes for common queries
    op.execute(
        """
        CREATE INDEX ix_mv_feature_aggregation_present_count
        ON mv_feature_aggregation (present_count DESC)
        """
    )

    # 2. Disease Aggregation Materialized View
    op.execute(
        """
        CREATE MATERIALIZED VIEW mv_disease_aggregation AS
        WITH disease_counts AS (
            SELECT
                disease->'term'->>'id' as disease_id,
                disease->'term'->>'label' as label,
                COUNT(*) as count
            FROM
                phenopackets,
                jsonb_array_elements(phenopacket->'diseases') as disease
            WHERE
                deleted_at IS NULL
            GROUP BY
                disease->'term'->>'id',
                disease->'term'->>'label'
        ),
        total_diseases AS (
            SELECT SUM(count) as total FROM disease_counts
        )
        SELECT
            dc.disease_id,
            dc.label,
            dc.count::integer,
            CASE WHEN td.total > 0
                THEN ROUND((dc.count::numeric / td.total) * 100, 2)
                ELSE 0
            END as percentage,
            NOW() as refreshed_at
        FROM disease_counts dc, total_diseases td
        ORDER BY dc.count DESC
        """
    )

    # Using composite key (disease_id, label) because same disease ID can have different label text
    op.execute(
        """
        CREATE UNIQUE INDEX ix_mv_disease_aggregation_disease_id_label
        ON mv_disease_aggregation (disease_id, label)
        """
    )

    # 3. Sex Distribution Materialized View
    op.execute(
        """
        CREATE MATERIALIZED VIEW mv_sex_distribution AS
        SELECT
            subject_sex as sex,
            COUNT(*) as count,
            ROUND((COUNT(*)::numeric / NULLIF(SUM(COUNT(*)) OVER (), 0)) * 100, 2)
                as percentage,
            NOW() as refreshed_at
        FROM phenopackets
        WHERE deleted_at IS NULL
        GROUP BY subject_sex
        ORDER BY count DESC
        """
    )

    op.execute(
        """
        CREATE UNIQUE INDEX ix_mv_sex_distribution_sex
        ON mv_sex_distribution (sex)
        """
    )

    # 4. Summary Statistics Materialized View
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

    # Summary stats has a single row, use dummy unique index
    op.execute(
        """
        CREATE UNIQUE INDEX ix_mv_summary_statistics_singleton
        ON mv_summary_statistics ((1))
        """
    )

    # 5. Create helper function to refresh all materialized views
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

    # Add comment explaining the refresh strategy
    op.execute(
        """
        COMMENT ON MATERIALIZED VIEW mv_feature_aggregation IS
        'Pre-computed HPO term statistics. Refresh after data imports with: '
        'SELECT refresh_all_aggregation_views();'
        """
    )


def downgrade() -> None:
    """Drop materialized views and helper function."""
    op.execute("DROP FUNCTION IF EXISTS refresh_all_aggregation_views()")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_summary_statistics CASCADE")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_sex_distribution CASCADE")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_disease_aggregation CASCADE")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_feature_aggregation CASCADE")
