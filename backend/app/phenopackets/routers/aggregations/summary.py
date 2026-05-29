"""Summary statistics endpoint for phenopackets aggregations.

Provides lightweight statistics for the home page dashboard.
"""

from typing import Dict

from app.phenopackets.repositories.visibility import public_filter

from .common import (
    APIRouter,
    AsyncSession,
    Depends,
    Phenopacket,
    func,
    get_db,
    select,
    text,
)
from .sql_fragments.ctes import synthetic_exclusion

router = APIRouter()


@router.get("/summary", response_model=Dict[str, int])
async def get_summary_statistics(db: AsyncSession = Depends(get_db)):
    """Get lightweight summary statistics for home page.

    Returns:
        Dictionary with counts:
        - total_phenopackets: Total number of phenopackets
        - with_variants: Phenopackets containing interpretations
        - distinct_hpo_terms: Number of unique HPO terms used
        - distinct_publications: Unique PMID-prefixed publication references only
          (matches GET /publications/.total)
        - distinct_sources: Unique external references of ANY kind (PMIDs plus
          internal/non-PMID cohort sources); >= distinct_publications
        - distinct_variants: Number of unique genetic variants
        - male: Number of male subjects
        - female: Number of female subjects
        - unknown_sex: Number of subjects with unknown sex

    All counts exclude synthetic e2e-* fixtures.
    """
    # All summary queries apply the public visibility filter (I3 + I7):
    # deleted_at IS NULL, state='published', head_published_revision_id IS NOT NULL

    # Synthetic-record exclusion (defense-in-depth): e2e-* fixtures must never
    # inflate cohort aggregates. The single-record read keeps them; aggregates
    # do not. Derived from the shared synthetic_exclusion() helper (no inline
    # drift); the unqualified form matches these alias-less FROM phenopackets
    # subqueries.
    _NO_E2E = f"AND {synthetic_exclusion('')}"

    # 1. Total phenopackets (published only, excluding synthetic fixtures)
    total_result = await db.execute(
        public_filter(select(func.count()).select_from(Phenopacket)).where(
            Phenopacket.phenopacket_id.not_like("e2e-%")
        )
    )
    total_phenopackets = total_result.scalar()

    # 2. With variants (interpretations exist) — published only
    with_variants_result = await db.execute(
        text(
            f"""
            SELECT COUNT(*)
            FROM phenopackets
            WHERE deleted_at IS NULL
              AND state = 'published'
              AND head_published_revision_id IS NOT NULL
              {_NO_E2E}
              AND jsonb_array_length(phenopacket->'interpretations') > 0
        """
        )
    )
    with_variants = with_variants_result.scalar()

    # 3. Distinct HPO terms — published only
    distinct_hpo_result = await db.execute(
        text(
            f"""
            SELECT COUNT(DISTINCT feature->'type'->>'id')
            FROM phenopackets,
                 jsonb_array_elements(phenopacket->'phenotypicFeatures') as feature
            WHERE deleted_at IS NULL
              AND state = 'published'
              AND head_published_revision_id IS NOT NULL
              {_NO_E2E}
              AND feature->'type'->>'id' IS NOT NULL
        """
        )
    )
    distinct_hpo_terms = distinct_hpo_result.scalar() or 0

    # 4a. Distinct PUBLICATIONS — PMID-prefixed external references only.
    # This matches GET /publications/.total (which also counts PMID-only),
    # so the two surfaces agree and the field name is honest.
    distinct_publications_result = await db.execute(
        text(
            f"""
            SELECT COUNT(DISTINCT ext_ref->>'id')
            FROM phenopackets,
                 jsonb_array_elements(
                     phenopacket->'metaData'->'externalReferences'
                 ) as ext_ref
            WHERE deleted_at IS NULL
              AND state = 'published'
              AND head_published_revision_id IS NOT NULL
              {_NO_E2E}
              AND ext_ref->>'id' LIKE 'PMID:%'
        """
        )
    )
    distinct_publications = distinct_publications_result.scalar() or 0

    # 4b. Distinct SOURCES — all external references (PMIDs + internal cohort
    # references). Reported separately so the broader figure is still available
    # without being mislabeled as a publication count.
    distinct_sources_result = await db.execute(
        text(
            f"""
            SELECT COUNT(DISTINCT ext_ref->>'id')
            FROM phenopackets,
                 jsonb_array_elements(
                     phenopacket->'metaData'->'externalReferences'
                 ) as ext_ref
            WHERE deleted_at IS NULL
              AND state = 'published'
              AND head_published_revision_id IS NOT NULL
              {_NO_E2E}
              AND ext_ref->>'id' IS NOT NULL
        """
        )
    )
    distinct_sources = distinct_sources_result.scalar() or 0

    # 5. Distinct variants (unique variants by VRS ID across all phenopackets)
    # Count by variationDescriptor.id (VRS identifier) which uniquely identifies
    # each variant. This correctly counts CNVs with different boundaries as
    # separate variants
    # per GA4GH VRS 2.0 specification: https://vrs.ga4gh.org/en/2.0.0-ballot.2024-11/
    # Published only.
    distinct_variants_result = await db.execute(
        text(
            """
            SELECT COUNT(DISTINCT vd->>'id')
            FROM phenopackets p,
                 jsonb_array_elements(p.phenopacket->'interpretations') as interp,
                 jsonb_array_elements(
                    interp->'diagnosis'->'genomicInterpretations'
                ) as gi,
                 LATERAL (
                     SELECT gi->'variantInterpretation'->'variationDescriptor' as vd
                 ) vd_lateral
            WHERE p.deleted_at IS NULL
              AND p.state = 'published'
              AND p.head_published_revision_id IS NOT NULL
              AND p.phenopacket_id NOT LIKE 'e2e-%'
              AND vd_lateral.vd IS NOT NULL
              AND vd_lateral.vd->>'id' IS NOT NULL
        """
        )
    )
    distinct_variants = distinct_variants_result.scalar() or 0

    # 6. Sex distribution — published only
    sex_distribution_result = await db.execute(
        text(
            """
            SELECT
                subject_sex,
                COUNT(*) as count
            FROM phenopackets
            WHERE deleted_at IS NULL
              AND state = 'published'
              AND head_published_revision_id IS NOT NULL
              AND phenopacket_id NOT LIKE 'e2e-%'
            GROUP BY subject_sex
        """
        )
    )
    sex_rows = sex_distribution_result.fetchall()

    # Parse sex distribution
    male = 0
    female = 0
    unknown_sex = 0
    for row in sex_rows:
        if row.subject_sex == "MALE":
            male = int(row._mapping["count"])
        elif row.subject_sex == "FEMALE":
            female = int(row._mapping["count"])
        else:
            unknown_sex += int(row._mapping["count"])

    return {
        "total_phenopackets": total_phenopackets,
        "with_variants": with_variants,
        "distinct_hpo_terms": distinct_hpo_terms,
        "distinct_publications": distinct_publications,
        "distinct_sources": distinct_sources,
        "distinct_variants": distinct_variants,
        "male": male,
        "female": female,
        "unknown_sex": unknown_sex,
    }
