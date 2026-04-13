"""Rebuild aggregation materialized views to filter on state='published'.

Revision ID: 20260412_0004
Revises: 20260412_0003
Create Date: 2026-04-12

Wave 7 D.1 — filter-centralization sweep (Task 14).

The original MV definitions (revision a7b8c9d0e1f2) filtered only on
``deleted_at IS NULL``.  After the state-machine migration the public
invariants require three conditions (I3 + I7 + I1):

    deleted_at IS NULL
    AND state = 'published'
    AND head_published_revision_id IS NOT NULL

This migration drops and recreates all four aggregation MVs with the
full public filter so that:
  - draft / archived / soft-deleted records are excluded from all
    aggregation data visible to anonymous users.
  - The unique indexes are preserved so CONCURRENTLY refresh still works.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "20260412_0004"
down_revision: Union[str, Sequence[str], None] = "20260412_0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# ---------------------------------------------------------------------------
# Shared public-filter fragment (I3 + I7 + I1)
# ---------------------------------------------------------------------------
_PUBLIC_FILTER = (
    "deleted_at IS NULL"
    "\n              AND state = 'published'"
    "\n              AND head_published_revision_id IS NOT NULL"
)


def upgrade() -> None:
    """Recreate all aggregation MVs with the full public-state filter."""
    # ------------------------------------------------------------------
    # 1. mv_feature_aggregation
    # ------------------------------------------------------------------
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_feature_aggregation CASCADE")
    op.execute(
        f"""
        CREATE MATERIALIZED VIEW mv_feature_aggregation AS
        WITH total_phenopackets AS (
            SELECT COUNT(*) as total
            FROM phenopackets
            WHERE {_PUBLIC_FILTER}
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
                {_PUBLIC_FILTER}
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
    op.execute(
        """
        CREATE UNIQUE INDEX ix_mv_feature_aggregation_hpo_id_label
        ON mv_feature_aggregation (hpo_id, label)
        """
    )
    op.execute(
        """
        CREATE INDEX ix_mv_feature_aggregation_present_count
        ON mv_feature_aggregation (present_count DESC)
        """
    )

    # ------------------------------------------------------------------
    # 2. mv_disease_aggregation
    # ------------------------------------------------------------------
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_disease_aggregation CASCADE")
    op.execute(
        f"""
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
                {_PUBLIC_FILTER}
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
    op.execute(
        """
        CREATE UNIQUE INDEX ix_mv_disease_aggregation_disease_id_label
        ON mv_disease_aggregation (disease_id, label)
        """
    )

    # ------------------------------------------------------------------
    # 3. mv_sex_distribution
    # ------------------------------------------------------------------
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_sex_distribution CASCADE")
    op.execute(
        f"""
        CREATE MATERIALIZED VIEW mv_sex_distribution AS
        SELECT
            subject_sex as sex,
            COUNT(*) as count,
            ROUND((COUNT(*)::numeric / NULLIF(SUM(COUNT(*)) OVER (), 0)) * 100, 2)
                as percentage,
            NOW() as refreshed_at
        FROM phenopackets
        WHERE {_PUBLIC_FILTER}
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

    # ------------------------------------------------------------------
    # 4. mv_summary_statistics
    # ------------------------------------------------------------------
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_summary_statistics CASCADE")
    op.execute(
        f"""
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
        WHERE {_PUBLIC_FILTER}
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX ix_mv_summary_statistics_singleton
        ON mv_summary_statistics ((1))
        """
    )

    # ------------------------------------------------------------------
    # 5. Recreate the refresh helper so it stays consistent
    # ------------------------------------------------------------------
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
    """Restore the original MV definitions (deleted_at IS NULL only)."""
    # ------------------------------------------------------------------
    # 1. mv_feature_aggregation (original)
    # ------------------------------------------------------------------
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_feature_aggregation CASCADE")
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
    op.execute(
        """
        CREATE UNIQUE INDEX ix_mv_feature_aggregation_hpo_id_label
        ON mv_feature_aggregation (hpo_id, label)
        """
    )
    op.execute(
        """
        CREATE INDEX ix_mv_feature_aggregation_present_count
        ON mv_feature_aggregation (present_count DESC)
        """
    )

    # ------------------------------------------------------------------
    # 2. mv_disease_aggregation (original)
    # ------------------------------------------------------------------
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_disease_aggregation CASCADE")
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
    op.execute(
        """
        CREATE UNIQUE INDEX ix_mv_disease_aggregation_disease_id_label
        ON mv_disease_aggregation (disease_id, label)
        """
    )

    # ------------------------------------------------------------------
    # 3. mv_sex_distribution (original)
    # ------------------------------------------------------------------
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_sex_distribution CASCADE")
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

    # ------------------------------------------------------------------
    # 4. mv_summary_statistics (original)
    # ------------------------------------------------------------------
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_summary_statistics CASCADE")
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
    op.execute(
        """
        CREATE UNIQUE INDEX ix_mv_summary_statistics_singleton
        ON mv_summary_statistics ((1))
        """
    )

    # Restore helper function
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
