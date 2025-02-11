# File: app/endpoints/aggregations.py

from fastapi import APIRouter
from app.database import db

router = APIRouter()


async def _aggregate_with_total(collection, group_field: str) -> dict:
    """
    Helper function to perform an aggregation that returns both grouped counts and the total document count.
    
    Args:
        collection: The Motor collection (e.g. db.individuals).
        group_field: The field to group by (e.g. "Sex" for individuals).
        
    Returns:
        A dictionary with keys:
          - "total_count": The total number of documents.
          - "grouped_counts": A list of grouped results (each with _id and count).
    """
    pipeline = [
        {
            "$facet": {
                "grouped_counts": [
                    {"$group": {"_id": f"${group_field}", "count": {"$sum": 1}}},
                    {"$sort": {"_id": 1}}
                ],
                "total_count": [
                    {"$count": "total"}
                ]
            }
        }
    ]
    result = await collection.aggregate(pipeline).to_list(length=1)
    if result:
        grouped_counts = result[0].get("grouped_counts", [])
        total_docs = result[0].get("total_count", [])
        total_count = total_docs[0]["total"] if total_docs else 0
        return {"total_count": total_count, "grouped_counts": grouped_counts}
    return {"total_count": 0, "grouped_counts": []}


@router.get("/individuals/sex-count", tags=["Aggregations"])
async def count_individuals_by_sex() -> dict:
    """
    Count individuals grouped by their 'Sex' field, along with the total number of individuals.
    
    Returns:
        A dictionary with:
          - "total_count": Total number of individuals.
          - "grouped_counts": List of documents with keys "_id" (sex) and "count".
    """
    return await _aggregate_with_total(db.individuals, "Sex")


@router.get("/variants/type-count", tags=["Aggregations"])
async def count_variants_by_type() -> dict:
    """
    Count variants grouped by their type (stored in 'variant_type'),
    along with the total number of variants.
    
    Returns:
        A dictionary with:
          - "total_count": Total number of variants.
          - "grouped_counts": List of documents with keys "_id" (variant type) and "count".
    """
    return await _aggregate_with_total(db.variants, "variant_type")


@router.get("/publications/type-count", tags=["Aggregations"])
async def count_publications_by_type() -> dict:
    """
    Count publications grouped by their 'publication_type' field,
    along with the total number of publications.
    
    Returns:
        A dictionary with:
          - "total_count": Total number of publications.
          - "grouped_counts": List of documents with keys "_id" (publication type) and "count".
    """
    return await _aggregate_with_total(db.publications, "publication_type")
