# File: app/endpoints/aggregations.py

from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends
from sqlalchemy import and_, desc, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Individual, Publication, Report, Variant, VariantAnnotation, VariantClassification

router = APIRouter()


async def _aggregate_with_total(
    db: AsyncSession, model, group_field: str
) -> Dict[str, Any]:
    """
    Helper function to perform an aggregation that returns both grouped counts and total count.
    
    Args:
        db: Database session
        model: SQLAlchemy model class
        group_field: The field to group by
        
    Returns:
        A dictionary with total_count and grouped_counts
    """
    # Get total count
    total_result = await db.execute(select(func.count()).select_from(model))
    total_count = total_result.scalar() or 0
    
    # Get grouped counts
    field_attr = getattr(model, group_field)
    grouped_result = await db.execute(
        select(field_attr.label("_id"), func.count().label("count"))
        .group_by(field_attr)
        .order_by(field_attr)
    )
    
    grouped_counts = [
        {"_id": row._id, "count": row.count} for row in grouped_result.fetchall()
    ]
    
    return {"total_count": total_count, "grouped_counts": grouped_counts}


async def _aggregate_latest_report_field(
    db: AsyncSession, report_field: str
) -> Dict[str, Any]:
    """
    Helper function to aggregate individuals by a field from their latest report.
    
    Args:
        db: Database session
        report_field: Field from the report to group by
        
    Returns:
        Dictionary with total_count and grouped_counts
    """
    # Subquery to get the latest report for each individual
    latest_report_subq = (
        select(
            Report.individual_id,
            Report.id.label("report_id"),
            getattr(Report, report_field).label("field_value"),
            func.row_number()
            .over(
                partition_by=Report.individual_id,
                order_by=desc(Report.report_date)
            )
            .label("rn"),
        )
        .subquery()
    )
    
    # Get individuals with their latest report field value
    latest_reports = (
        select(latest_report_subq.c.field_value)
        .where(latest_report_subq.c.rn == 1)
    )
    
    # Apply age_onset normalization if needed
    if report_field == "age_onset":
        latest_reports = select(
            func.case(
                (func.lower(latest_report_subq.c.field_value) == "prenatal", "prenatal"),
                (func.lower(latest_report_subq.c.field_value) == "not reported", "not reported"),
                else_="postnatal"
            ).label("field_value")
        ).select_from(latest_report_subq).where(latest_report_subq.c.rn == 1)
    
    # Get total count
    total_result = await db.execute(
        select(func.count()).select_from(latest_reports.subquery())
    )
    total_count = total_result.scalar() or 0
    
    # Get grouped counts
    grouped_query = (
        select(
            latest_reports.subquery().c.field_value.label("_id"),
            func.count().label("count")
        )
        .group_by(latest_reports.subquery().c.field_value)
        .order_by(latest_reports.subquery().c.field_value)
    )
    
    grouped_result = await db.execute(grouped_query)
    grouped_counts = [
        {"_id": row._id, "count": row.count} for row in grouped_result.fetchall()
    ]
    
    return {"total_count": total_count, "grouped_counts": grouped_counts}


@router.get("/individuals/sex-count", tags=["Aggregations"])
async def count_individuals_by_sex(
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Count individuals grouped by their 'Sex' field."""
    return await _aggregate_with_total(db, Individual, "sex")


@router.get("/variants/type-count", tags=["Aggregations"])
async def count_variants_by_type(
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Count variants grouped by their type."""
    return await _aggregate_with_total(db, Variant, "variant_type")


@router.get("/publications/type-count", tags=["Aggregations"])
async def count_publications_by_type(
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Count publications grouped by their 'publication_type' field."""
    return await _aggregate_with_total(db, Publication, "publication_type")


@router.get("/variants/newest-classification-verdict-count", tags=["Aggregations"])
async def count_variants_by_newest_verdict(
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Count variants grouped by the 'verdict' field of the newest classification."""
    # Subquery to get the latest classification for each variant
    latest_classification_subq = (
        select(
            VariantClassification.variant_id,
            VariantClassification.verdict,
            func.row_number()
            .over(
                partition_by=VariantClassification.variant_id,
                order_by=desc(VariantClassification.classification_date)
            )
            .label("rn"),
        )
        .subquery()
    )
    
    # Get verdicts from latest classifications
    latest_verdicts = (
        select(latest_classification_subq.c.verdict)
        .where(latest_classification_subq.c.rn == 1)
    )
    
    # Total count
    total_result = await db.execute(
        select(func.count()).select_from(latest_verdicts.subquery())
    )
    total_count = total_result.scalar() or 0
    
    # Grouped counts
    grouped_result = await db.execute(
        select(
            latest_verdicts.subquery().c.verdict.label("_id"),
            func.count().label("count")
        )
        .group_by(latest_verdicts.subquery().c.verdict)
        .order_by(latest_verdicts.subquery().c.verdict)
    )
    
    grouped_counts = [
        {"_id": row._id, "count": row.count} for row in grouped_result.fetchall()
    ]
    
    return {"total_count": total_count, "grouped_counts": grouped_counts}


@router.get("/variants/individual-count-by-type", tags=["Aggregations"])
async def count_individuals_by_variant_type(
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Sum the total number of individuals for each variant type."""
    # Use raw SQL for complex aggregation with individual_variants join
    query = text("""
        SELECT 
            v.variant_type as _id,
            COUNT(DISTINCT iv.individual_id) as count
        FROM variants v
        JOIN individual_variants iv ON v.id = iv.variant_id
        WHERE v.variant_type IS NOT NULL
        GROUP BY v.variant_type
        ORDER BY v.variant_type
    """)
    
    grouped_result = await db.execute(query)
    grouped_counts = [
        {"_id": row._id, "count": row.count} for row in grouped_result.fetchall()
    ]
    
    # Total count
    total_query = text("""
        SELECT COUNT(DISTINCT iv.individual_id) as total
        FROM variants v
        JOIN individual_variants iv ON v.id = iv.variant_id
        WHERE v.variant_type IS NOT NULL
    """)
    
    total_result = await db.execute(total_query)
    total_count = total_result.scalar() or 0
    
    return {"total_count": total_count, "grouped_counts": grouped_counts}


@router.get("/individuals/age-onset-count", tags=["Aggregations"])
async def count_individuals_by_age_onset(
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Aggregate individuals by the 'age_onset' field of their newest report."""
    return await _aggregate_latest_report_field(db, "age_onset")


@router.get("/individuals/cohort-count", tags=["Aggregations"])
async def count_individuals_by_cohort(
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Aggregate individuals by the 'cohort' field of their newest report."""
    return await _aggregate_latest_report_field(db, "cohort")


@router.get("/individuals/family-history-count", tags=["Aggregations"])
async def count_individuals_by_family_history(
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Aggregate individuals by the 'family_history' field of their newest report."""
    return await _aggregate_latest_report_field(db, "family_history")


@router.get("/individuals/detection-method-count", tags=["Aggregations"])
async def count_individuals_by_detection_method(
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Aggregate individuals by the detection_method field."""
    # Use raw SQL to join with individual_variants
    query = text("""
        SELECT 
            iv.detection_method as _id,
            COUNT(DISTINCT i.id) as count
        FROM individuals i
        JOIN individual_variants iv ON i.id = iv.individual_id
        WHERE iv.detection_method IS NOT NULL
        GROUP BY iv.detection_method
        ORDER BY iv.detection_method
    """)
    
    grouped_result = await db.execute(query)
    grouped_counts = [
        {"_id": row._id, "count": row.count} for row in grouped_result.fetchall()
    ]
    
    # Total count
    total_query = text("""
        SELECT COUNT(DISTINCT i.id) as total
        FROM individuals i
        JOIN individual_variants iv ON i.id = iv.individual_id
        WHERE iv.detection_method IS NOT NULL
    """)
    
    total_result = await db.execute(total_query)
    total_count = total_result.scalar() or 0
    
    return {"total_count": total_count, "grouped_counts": grouped_counts}


@router.get("/individuals/segregation-count", tags=["Aggregations"])
async def count_individuals_by_segregation(
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Aggregate individuals by the segregation field."""
    # Use raw SQL to join with individual_variants
    query = text("""
        SELECT 
            iv.segregation as _id,
            COUNT(DISTINCT i.id) as count
        FROM individuals i
        JOIN individual_variants iv ON i.id = iv.individual_id
        WHERE iv.segregation IS NOT NULL
        GROUP BY iv.segregation
        ORDER BY iv.segregation
    """)
    
    grouped_result = await db.execute(query)
    grouped_counts = [
        {"_id": row._id, "count": row.count} for row in grouped_result.fetchall()
    ]
    
    # Total count
    total_query = text("""
        SELECT COUNT(DISTINCT i.id) as total
        FROM individuals i
        JOIN individual_variants iv ON i.id = iv.individual_id
        WHERE iv.segregation IS NOT NULL
    """)
    
    total_result = await db.execute(total_query)
    total_count = total_result.scalar() or 0
    
    return {"total_count": total_count, "grouped_counts": grouped_counts}


@router.get("/individuals/phenotype-described-count", tags=["Aggregations"])
async def count_phenotypes_by_described(
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Aggregate the phenotypes from the newest report of each individual."""
    # Use raw SQL for complex JSONB operations
    query = text("""
        WITH latest_reports AS (
            SELECT DISTINCT ON (r.individual_id)
                r.individual_id,
                r.phenotypes
            FROM reports r
            WHERE r.phenotypes IS NOT NULL
            ORDER BY r.individual_id, r.report_date DESC
        ),
        phenotype_data AS (
            SELECT 
                phenotype_key,
                phenotype_value->>'name' as name,
                phenotype_value->>'described' as described
            FROM latest_reports lr,
                 jsonb_each(lr.phenotypes) AS p(phenotype_key, phenotype_value)
            WHERE phenotype_value IS NOT NULL
        )
        SELECT 
            phenotype_key as phenotype_id,
            name,
            jsonb_build_object(
                'yes', COUNT(*) FILTER (WHERE described = 'yes'),
                'no', COUNT(*) FILTER (WHERE described = 'no'),
                'not reported', COUNT(*) FILTER (WHERE described = 'not reported')
            ) as counts
        FROM phenotype_data
        GROUP BY phenotype_key, name
        ORDER BY COUNT(*) FILTER (WHERE described = 'yes') DESC
    """)
    
    result = await db.execute(query)
    results = [
        {
            "phenotype_id": row.phenotype_id,
            "name": row.name,
            "counts": row.counts
        }
        for row in result.fetchall()
    ]
    
    return {"results": results}


@router.get("/publications/cumulative-count", tags=["Aggregations"])
async def cumulative_publications(
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Compute cumulative publication counts in one-month intervals."""
    # Overall cumulative count
    overall_query = text("""
        WITH monthly_counts AS (
            SELECT 
                date_trunc('month', publication_date) as month_date,
                COUNT(*) as monthly_count
            FROM publications
            WHERE publication_date IS NOT NULL
            GROUP BY date_trunc('month', publication_date)
            ORDER BY month_date
        )
        SELECT 
            month_date as monthDate,
            monthly_count as monthlyCount,
            SUM(monthly_count) OVER (ORDER BY month_date) as cumulativeCount
        FROM monthly_counts
        ORDER BY month_date
    """)
    
    overall_result = await db.execute(overall_query)
    overall = [
        {
            "monthDate": row.monthDate.isoformat() if row.monthDate else None,
            "monthlyCount": row.monthlyCount,
            "cumulativeCount": row.cumulativeCount
        }
        for row in overall_result.fetchall()
    ]
    
    # By type cumulative count
    by_type_query = text("""
        WITH monthly_counts_by_type AS (
            SELECT 
                date_trunc('month', publication_date) as month_date,
                publication_type,
                COUNT(*) as monthly_count
            FROM publications
            WHERE publication_date IS NOT NULL
            GROUP BY date_trunc('month', publication_date), publication_type
            ORDER BY publication_type, month_date
        )
        SELECT 
            month_date as monthDate,
            publication_type,
            monthly_count as monthlyCount,
            SUM(monthly_count) OVER (
                PARTITION BY publication_type 
                ORDER BY month_date
            ) as cumulativeCount
        FROM monthly_counts_by_type
        ORDER BY publication_type, month_date
    """)
    
    by_type_result = await db.execute(by_type_query)
    by_type = [
        {
            "monthDate": row.monthDate.isoformat() if row.monthDate else None,
            "publication_type": row.publication_type,
            "monthlyCount": row.monthlyCount,
            "cumulativeCount": row.cumulativeCount
        }
        for row in by_type_result.fetchall()
    ]
    
    return {"overall": overall, "byType": by_type}


@router.get("/variants/small_variants", tags=["Aggregations"])
async def get_variant_small_variants(
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Retrieve variants of type SNV or indel and extract information."""
    query = text("""
        WITH latest_classifications AS (
            SELECT DISTINCT ON (variant_id)
                variant_id,
                verdict
            FROM variant_classifications
            ORDER BY variant_id, classification_date DESC
        ),
        latest_vep_annotations AS (
            SELECT DISTINCT ON (variant_id)
                variant_id,
                transcript,
                c_dot,
                p_dot
            FROM variant_annotations
            WHERE source = 'vep'
            ORDER BY variant_id, annotation_date DESC
        ),
        individual_counts AS (
            SELECT 
                variant_id,
                COUNT(DISTINCT individual_id) as individual_count
            FROM individual_variants
            GROUP BY variant_id
        )
        SELECT 
            v.variant_id,
            lc.verdict,
            lva.transcript,
            lva.c_dot,
            lva.p_dot,
            COALESCE(ic.individual_count, 0) as individual_count
        FROM variants v
        LEFT JOIN latest_classifications lc ON v.id = lc.variant_id
        LEFT JOIN latest_vep_annotations lva ON v.id = lva.variant_id
        LEFT JOIN individual_counts ic ON v.id = ic.variant_id
        WHERE v.variant_type IN ('SNV', 'indel')
        ORDER BY v.variant_id
    """)
    
    result = await db.execute(query)
    small_variants = [
        {
            "variant_id": row.variant_id,
            "verdict": row.verdict,
            "transcript": row.transcript,
            "c_dot": row.c_dot,
            "p_dot": row.p_dot,
            "individual_count": row.individual_count
        }
        for row in result.fetchall()
    ]
    
    return {"small_variants": small_variants}


@router.get("/summary", tags=["Aggregations"])
async def get_summary_stats(
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Retrieve summary statistics for main collections."""
    # Count individuals
    individuals_result = await db.execute(select(func.count()).select_from(Individual))
    individuals_count = individuals_result.scalar() or 0
    
    # Count total reports
    reports_result = await db.execute(select(func.count()).select_from(Report))
    total_reports = reports_result.scalar() or 0
    
    # Count variants
    variants_result = await db.execute(select(func.count()).select_from(Variant))
    variants_count = variants_result.scalar() or 0
    
    # Count publications
    publications_result = await db.execute(select(func.count()).select_from(Publication))
    publications_count = publications_result.scalar() or 0
    
    return {
        "individuals": individuals_count,
        "total_reports": total_reports,
        "variants": variants_count,
        "publications": publications_count
    }


@router.get("/variants/impact-group-count", tags=["Aggregations"])
async def count_variants_by_impact_group(
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Aggregate variants into impact groups."""
    query = text("""
        WITH latest_classifications AS (
            SELECT DISTINCT ON (variant_id)
                variant_id,
                verdict
            FROM variant_classifications
            ORDER BY variant_id, classification_date DESC
        ),
        latest_vep_annotations AS (
            SELECT DISTINCT ON (variant_id)
                variant_id,
                impact
            FROM variant_annotations
            WHERE source = 'vep'
            ORDER BY variant_id, annotation_date DESC
        )
        SELECT 
            CASE 
                WHEN lva.impact = 'MODERATE' THEN 'nT'
                WHEN lva.impact = 'HIGH' THEN 'T'
                WHEN lva.impact = 'LOW' AND lc.verdict = 'LP/P' THEN 'T'
                WHEN lva.impact = 'MODIFIER' AND lc.verdict = 'LP/P' THEN 'T'
                WHEN lva.impact IS NULL AND lc.verdict = 'LP/P' THEN 'T'
                ELSE 'other'
            END as _id,
            COUNT(*) as count
        FROM variants v
        LEFT JOIN latest_classifications lc ON v.id = lc.variant_id
        LEFT JOIN latest_vep_annotations lva ON v.id = lva.variant_id
        GROUP BY 1
        ORDER BY 1
    """)
    
    result = await db.execute(query)
    grouped_counts = [
        {"_id": row._id, "count": row.count} for row in result.fetchall()
    ]
    
    total_count = sum(item["count"] for item in grouped_counts)
    
    return {"total_count": total_count, "grouped_counts": grouped_counts}


@router.get("/variants/effect-group-count", tags=["Aggregations"])
async def count_variants_by_effect_group(
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Aggregate variants into effect groups."""
    query = text("""
        WITH latest_classifications AS (
            SELECT DISTINCT ON (variant_id)
                variant_id,
                verdict
            FROM variant_classifications
            ORDER BY variant_id, classification_date DESC
        ),
        latest_vep_annotations AS (
            SELECT DISTINCT ON (variant_id)
                variant_id,
                impact,
                effect
            FROM variant_annotations
            WHERE source = 'vep'
            ORDER BY variant_id, annotation_date DESC
        )
        SELECT 
            CASE 
                WHEN lva.effect = 'transcript_ablation' THEN '17qDel'
                WHEN lva.effect = 'transcript_amplification' THEN '17qDup'
                WHEN lva.impact = 'MODERATE' THEN 'nT'
                WHEN lva.impact IS NULL AND lc.verdict = 'LP/P' THEN 'T'
                WHEN lva.impact = 'LOW' AND lc.verdict = 'LP/P' THEN 'T'
                WHEN lva.effect IN (
                    'stop_gained', 'frameshift_variant', 'stop_lost', 
                    'start_lost', 'splice_acceptor_variant', 
                    'splice_donor_variant'
                ) THEN 'T'
                ELSE 'other'
            END as _id,
            COUNT(*) as count
        FROM variants v
        LEFT JOIN latest_classifications lc ON v.id = lc.variant_id
        LEFT JOIN latest_vep_annotations lva ON v.id = lva.variant_id
        GROUP BY 1
        ORDER BY 1
    """)
    
    result = await db.execute(query)
    grouped_counts = [
        {"_id": row._id, "count": row.count} for row in result.fetchall()
    ]
    
    total_count = sum(item["count"] for item in grouped_counts)
    
    return {"total_count": total_count, "grouped_counts": grouped_counts}


@router.get("/individuals/phenotype-cohort-count", tags=["Aggregations"])
async def phenotype_cohort_counts(
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Classify individuals based on phenotypes from their newest report."""
    query = text("""
        WITH latest_reports AS (
            SELECT DISTINCT ON (r.individual_id)
                r.individual_id,
                r.phenotypes
            FROM reports r
            WHERE r.phenotypes IS NOT NULL
            ORDER BY r.individual_id, r.report_date DESC
        ),
        individual_phenotypes AS (
            SELECT 
                individual_id,
                CASE 
                    WHEN phenotypes ? 'HP:0000002' AND phenotypes->'HP:0000002'->>'described' = 'yes' THEN 'Abnormal'
                    ELSE 'Normal'
                END as phenotype_category
            FROM latest_reports
        )
        SELECT 
            phenotype_category as _id,
            COUNT(*) as count
        FROM individual_phenotypes
        GROUP BY phenotype_category
        ORDER BY phenotype_category
    """)
    
    result = await db.execute(query)
    grouped_counts = [
        {"_id": row._id, "count": row.count} for row in result.fetchall()
    ]
    
    total_count = sum(item["count"] for item in grouped_counts)
    
    return {"total_count": total_count, "grouped_counts": grouped_counts}