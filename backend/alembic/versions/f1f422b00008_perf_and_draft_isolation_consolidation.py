"""Consolidated migration: JSONB GIN indexes, MV rebuild for draft isolation, and RAG/FK indexes.

Addresses:
- #521 (PERF-02): GIN indexes on phenopacket_revisions(content_jsonb) (published),
  dropping duplicate and dead snake_case indexes on phenopackets.
- #526 (DATA-04): Update 4 aggregation MVs to query phenopacket_revisions at head_published_revision_id.
- #532 (PERF-05): Wire aggregation MVs with published-head revisions and refresh helper.
- #542 (PERF-06): Add missing B-tree FK indexes and RAG embedding indexes.

Revision ID: f1f422b00008
Revises: f0f422b00007
Create Date: 2026-10-19
"""

from __future__ import annotations

from alembic import op

revision = "f1f422b00008"
down_revision = "f0f422b00007"
branch_labels = None
depends_on = None

_PUBLIC_REVISION_FILTER = """
    p.deleted_at IS NULL
    AND p.state = 'published'
    AND p.head_published_revision_id IS NOT NULL
    AND r.state = 'published'
    AND p.phenopacket_id NOT LIKE 'e2e-%'
"""

_LEGACY_PUBLIC_FILTER = """
    deleted_at IS NULL
    AND state = 'published'
    AND head_published_revision_id IS NOT NULL
"""


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. #521: Drop duplicate & dead snake_case indexes on phenopackets
    # ------------------------------------------------------------------
    op.execute("DROP INDEX IF EXISTS idx_phenopacket_diseases;")
    op.execute("DROP INDEX IF EXISTS idx_phenopacket_interpretations;")
    op.execute("DROP INDEX IF EXISTS idx_phenopackets_external_refs;")
    op.execute("DROP INDEX IF EXISTS idx_phenopacket_features;")
    op.execute("DROP INDEX IF EXISTS idx_phenopacket_hpo_terms;")
    op.execute("DROP INDEX IF EXISTS idx_phenopacket_variant_labels;")
    op.execute("DROP INDEX IF EXISTS idx_phenopacket_medical_actions;")

    # ------------------------------------------------------------------
    # 2. #521: Partial GIN indexes on phenopacket_revisions(content_jsonb)
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_phenopacket_revisions_features_gin
        ON phenopacket_revisions USING gin ((content_jsonb->'phenotypicFeatures'))
        WHERE state = 'published';
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_phenopacket_revisions_interpretations_gin
        ON phenopacket_revisions USING gin ((content_jsonb->'interpretations'))
        WHERE state = 'published';
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_phenopacket_revisions_diseases_gin
        ON phenopacket_revisions USING gin ((content_jsonb->'diseases'))
        WHERE state = 'published';
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_phenopacket_revisions_external_refs_gin
        ON phenopacket_revisions USING gin (((content_jsonb->'metaData'->'externalReferences')))
        WHERE state = 'published';
        """
    )

    # ------------------------------------------------------------------
    # 3. #542: Missing B-tree FK indexes and RAG embedding indexes
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_phenopacket_revisions_parent_revision_id
        ON phenopacket_revisions USING btree (parent_revision_id);
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_phenopacket_revisions_actor_id
        ON phenopacket_revisions USING btree (actor_id);
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_phenopackets_head_published_revision_id
        ON phenopackets USING btree (head_published_revision_id);
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_phenopackets_editing_revision_id
        ON phenopackets USING btree (editing_revision_id);
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_publication_fulltext_embeddings_model_pmid_passage
        ON publication_fulltext_embeddings USING btree (model_name, pmid, passage_id);
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_publication_fulltext_embeddings_hnsw
        ON publication_fulltext_embeddings USING hnsw (embedding vector_cosine_ops);
        """
    )

    # ------------------------------------------------------------------
    # 4. #526 & #532: Rebuild 4 Materialized Views to query phenopacket_revisions
    # ------------------------------------------------------------------
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_feature_aggregation CASCADE;")
    op.execute(
        f"""
        CREATE MATERIALIZED VIEW mv_feature_aggregation AS
        WITH total_phenopackets AS (
            SELECT COUNT(*) as total
            FROM phenopackets p
            WHERE p.deleted_at IS NULL
              AND p.state = 'published'
              AND p.head_published_revision_id IS NOT NULL
              AND p.phenopacket_id NOT LIKE 'e2e-%'
        ),
        feature_counts AS (
            SELECT
                feature->'type'->>'id' as hpo_id,
                MIN(feature->'type'->>'label') as label,
                SUM(CASE WHEN NOT COALESCE((feature->>'excluded')::boolean, false)
                    THEN 1 ELSE 0 END) as present_count,
                SUM(CASE WHEN COALESCE((feature->>'excluded')::boolean, false)
                    THEN 1 ELSE 0 END) as absent_count
            FROM
                phenopackets p
                JOIN phenopacket_revisions r ON r.id = p.head_published_revision_id,
                jsonb_array_elements(r.content_jsonb->'phenotypicFeatures') as feature
            WHERE
                {_PUBLIC_REVISION_FILTER}
            GROUP BY
                feature->'type'->>'id'
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
        ORDER BY fc.present_count DESC;
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX ix_mv_feature_aggregation_hpo_id_label
        ON mv_feature_aggregation (hpo_id, label);
        """
    )
    op.execute(
        """
        CREATE INDEX ix_mv_feature_aggregation_present_count
        ON mv_feature_aggregation (present_count DESC);
        """
    )

    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_disease_aggregation CASCADE;")
    op.execute(
        f"""
        CREATE MATERIALIZED VIEW mv_disease_aggregation AS
        WITH disease_counts AS (
            SELECT
                disease->'term'->>'id' as disease_id,
                disease->'term'->>'label' as label,
                COUNT(*) as count
            FROM
                phenopackets p
                JOIN phenopacket_revisions r ON r.id = p.head_published_revision_id,
                jsonb_array_elements(r.content_jsonb->'diseases') as disease
            WHERE
                {_PUBLIC_REVISION_FILTER}
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
        ORDER BY dc.count DESC;
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX ix_mv_disease_aggregation_disease_id_label
        ON mv_disease_aggregation (disease_id, label);
        """
    )

    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_sex_distribution CASCADE;")
    op.execute(
        f"""
        CREATE MATERIALIZED VIEW mv_sex_distribution AS
        SELECT
            COALESCE(r.content_jsonb->'subject'->>'sex', p.subject_sex, 'Unknown') as sex,
            COUNT(*) as count,
            ROUND((COUNT(*)::numeric / NULLIF(SUM(COUNT(*)) OVER (), 0)) * 100, 2) as percentage,
            NOW() as refreshed_at
        FROM
            phenopackets p
            JOIN phenopacket_revisions r ON r.id = p.head_published_revision_id
        WHERE
            {_PUBLIC_REVISION_FILTER}
        GROUP BY
            COALESCE(r.content_jsonb->'subject'->>'sex', p.subject_sex, 'Unknown')
        ORDER BY
            count DESC;
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX ix_mv_sex_distribution_sex
        ON mv_sex_distribution (sex);
        """
    )

    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_summary_statistics CASCADE;")
    op.execute(
        f"""
        CREATE MATERIALIZED VIEW mv_summary_statistics AS
        SELECT
            COUNT(*) as total_phenopackets,
            COUNT(*) FILTER (
                WHERE jsonb_array_length(
                    COALESCE(r.content_jsonb->'interpretations', '[]'::jsonb)
                ) > 0
            ) as with_variants,
            COUNT(*) FILTER (
                WHERE jsonb_array_length(
                    COALESCE(r.content_jsonb->'phenotypicFeatures', '[]'::jsonb)
                ) > 0
            ) as with_features,
            COUNT(*) FILTER (
                WHERE jsonb_array_length(
                    COALESCE(r.content_jsonb->'diseases', '[]'::jsonb)
                ) > 0
            ) as with_diseases,
            COUNT(DISTINCT r.content_jsonb->'subject'->>'id') as unique_subjects,
            NOW() as refreshed_at
        FROM
            phenopackets p
            JOIN phenopacket_revisions r ON r.id = p.head_published_revision_id
        WHERE
            {_PUBLIC_REVISION_FILTER};
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX ix_mv_summary_statistics_singleton
        ON mv_summary_statistics ((1));
        """
    )

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

    op.execute("ANALYZE phenopackets;")
    op.execute("ANALYZE phenopacket_revisions;")


def downgrade() -> None:
    # ------------------------------------------------------------------
    # 1. Restore legacy MVs (reading phenopackets.phenopacket)
    # ------------------------------------------------------------------
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_feature_aggregation CASCADE;")
    op.execute(
        f"""
        CREATE MATERIALIZED VIEW mv_feature_aggregation AS
        WITH total_phenopackets AS (
            SELECT COUNT(*) as total
            FROM phenopackets
            WHERE {_LEGACY_PUBLIC_FILTER}
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
                {_LEGACY_PUBLIC_FILTER}
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
        ORDER BY fc.present_count DESC;
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX ix_mv_feature_aggregation_hpo_id_label
        ON mv_feature_aggregation (hpo_id, label);
        """
    )
    op.execute(
        """
        CREATE INDEX ix_mv_feature_aggregation_present_count
        ON mv_feature_aggregation (present_count DESC);
        """
    )

    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_disease_aggregation CASCADE;")
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
                {_LEGACY_PUBLIC_FILTER}
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
        ORDER BY dc.count DESC;
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX ix_mv_disease_aggregation_disease_id_label
        ON mv_disease_aggregation (disease_id, label);
        """
    )

    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_sex_distribution CASCADE;")
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
        WHERE {_LEGACY_PUBLIC_FILTER}
        GROUP BY subject_sex
        ORDER BY count DESC;
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX ix_mv_sex_distribution_sex
        ON mv_sex_distribution (sex);
        """
    )

    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_summary_statistics CASCADE;")
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
        WHERE {_LEGACY_PUBLIC_FILTER};
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX ix_mv_summary_statistics_singleton
        ON mv_summary_statistics ((1));
        """
    )

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

    # ------------------------------------------------------------------
    # 2. Drop new indexes
    # ------------------------------------------------------------------
    op.execute("DROP INDEX IF EXISTS idx_publication_fulltext_embeddings_hnsw;")
    op.execute(
        "DROP INDEX IF EXISTS idx_publication_fulltext_embeddings_model_pmid_passage;"
    )
    op.execute("DROP INDEX IF EXISTS idx_phenopackets_editing_revision_id;")
    op.execute("DROP INDEX IF EXISTS idx_phenopackets_head_published_revision_id;")
    op.execute("DROP INDEX IF EXISTS idx_phenopacket_revisions_actor_id;")
    op.execute("DROP INDEX IF EXISTS idx_phenopacket_revisions_parent_revision_id;")

    op.execute("DROP INDEX IF EXISTS idx_phenopacket_revisions_external_refs_gin;")
    op.execute("DROP INDEX IF EXISTS idx_phenopacket_revisions_diseases_gin;")
    op.execute("DROP INDEX IF EXISTS idx_phenopacket_revisions_interpretations_gin;")
    op.execute("DROP INDEX IF EXISTS idx_phenopacket_revisions_features_gin;")

    # ------------------------------------------------------------------
    # 3. Restore duplicate and snake_case indexes on phenopackets
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_phenopacket_diseases
        ON phenopackets USING gin (((phenopacket -> 'diseases')));
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_phenopacket_interpretations
        ON phenopackets USING gin (((phenopacket -> 'interpretations')));
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_phenopackets_external_refs
        ON phenopackets USING gin (((phenopacket -> 'metaData' -> 'externalReferences')));
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_phenopacket_features
        ON phenopackets USING gin (((phenopacket -> 'phenotypic_features')));
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_phenopacket_hpo_terms
        ON phenopackets USING gin (jsonb_path_query_array(phenopacket, '$.phenotypic_features[*].type.id'));
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_phenopacket_variant_labels
        ON phenopackets USING gin (
            jsonb_path_query_array(
                phenopacket,
                '$.interpretations[*].diagnosis.genomic_interpretations[*].variant_interpretation.variation_descriptor.label'
            )
        );
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_phenopacket_medical_actions
        ON phenopackets USING gin (((phenopacket -> 'medical_actions')));
        """
    )
