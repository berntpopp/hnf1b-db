"""Summary statistics endpoint for phenopackets aggregations.

Provides lightweight statistics for the home page dashboard.
"""

from typing import Dict

from .common import (
    APIRouter,
    AsyncSession,
    Depends,
    Optional,
    Phenopacket,
    User,
    datetime,
    func,
    get_current_user_optional,
    get_db,
    log_aggregation_access,
    select,
    text,
    timezone,
)

router = APIRouter()


@router.get("/summary", response_model=Dict[str, int])
async def get_summary_statistics(
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Get lightweight summary statistics for home page.

    Returns:
        Dictionary with counts:
        - total_phenopackets: Total number of phenopackets
        - with_variants: Phenopackets containing interpretations
        - distinct_hpo_terms: Number of unique HPO terms used
        - distinct_publications: Number of unique publication references
        - distinct_variants: Number of unique genetic variants
        - male: Number of male subjects
        - female: Number of female subjects
        - unknown_sex: Number of subjects with unknown sex
    """
    # Log access for authenticated users only
    if current_user:
        log_aggregation_access(
            user_id=current_user.id,
            endpoint="/aggregate/summary",
            timestamp=datetime.now(timezone.utc),
        )

    # 1. Total phenopackets
    total_result = await db.execute(select(func.count()).select_from(Phenopacket))
    total_phenopackets = total_result.scalar()

    # 2. With variants (interpretations exist)
    with_variants_result = await db.execute(
        text(
            """
            SELECT COUNT(*)
            FROM phenopackets
            WHERE jsonb_array_length(phenopacket->'interpretations') > 0
        """
        )
    )
    with_variants = with_variants_result.scalar()

    # 3. Distinct HPO terms
    distinct_hpo_result = await db.execute(
        text(
            """
            SELECT COUNT(DISTINCT feature->'type'->>'id')
            FROM phenopackets,
                 jsonb_array_elements(phenopacket->'phenotypicFeatures') as feature
            WHERE feature->'type'->>'id' IS NOT NULL
        """
        )
    )
    distinct_hpo_terms = distinct_hpo_result.scalar() or 0

    # 4. Distinct sources (publications and internal cohort data)
    distinct_publications_result = await db.execute(
        text(
            """
            SELECT COUNT(DISTINCT ext_ref->>'id')
            FROM phenopackets,
                 jsonb_array_elements(
                     phenopacket->'metaData'->'externalReferences'
                 ) as ext_ref
            WHERE ext_ref->>'id' IS NOT NULL
        """
        )
    )
    distinct_publications = distinct_publications_result.scalar() or 0

    # 5. Distinct variants (unique variants by VRS ID across all phenopackets)
    # Count by variationDescriptor.id (VRS identifier) which uniquely identifies
    # each variant. This correctly counts CNVs with different boundaries as
    # separate variants
    # per GA4GH VRS 2.0 specification: https://vrs.ga4gh.org/en/2.0.0-ballot.2024-11/
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
            WHERE vd_lateral.vd IS NOT NULL
              AND vd_lateral.vd->>'id' IS NOT NULL
              AND p.deleted_at IS NULL
        """
        )
    )
    distinct_variants = distinct_variants_result.scalar() or 0

    # 6. Sex distribution
    sex_distribution_result = await db.execute(
        text(
            """
            SELECT
                subject_sex,
                COUNT(*) as count
            FROM phenopackets
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
        "distinct_variants": distinct_variants,
        "male": male,
        "female": female,
        "unknown_sex": unknown_sex,
    }
