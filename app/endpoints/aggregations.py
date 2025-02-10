# File: app/endpoints/aggregations.py

from fastapi import APIRouter
from app.database import db

router = APIRouter()


@router.get("/individuals/sex-count", tags=["Aggregations"])
async def count_individuals_by_sex():
    """
    Count individuals grouped by their 'Sex' field.

    Returns:
        A list of documents, each containing the sex (or None) and the corresponding count.
    """
    pipeline = [
        {"$group": {"_id": "$Sex", "count": {"$sum": 1}}},
        {"$sort": {"_id": 1}}
    ]
    results = await db.individuals.aggregate(pipeline).to_list(length=None)
    return results


@router.get("/variants/type-count", tags=["Aggregations"])
async def count_variants_by_type():
    """
    Count variants grouped by their type, stored in 'variant_type'.

    Returns:
        A list of documents, each containing the variant type and the count.
    """
    pipeline = [
        {"$group": {"_id": "$variant_type", "count": {"$sum": 1}}},
        {"$sort": {"_id": 1}}
    ]
    results = await db.variants.aggregate(pipeline).to_list(length=None)
    return results


@router.get("/publications/type-count", tags=["Aggregations"])
async def count_publications_by_type():
    """
    Count publications grouped by their 'publication_type' field.

    Returns:
        A list of documents, each containing the publication type and the count.
    """
    pipeline = [
        {"$group": {"_id": "$publication_type", "count": {"$sum": 1}}},
        {"$sort": {"_id": 1}}
    ]
    results = await db.publications.aggregate(pipeline).to_list(length=None)
    return results
