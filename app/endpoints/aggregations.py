# File: app/endpoints/aggregations.py

from datetime import datetime
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
        A dictionary with:
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


async def _aggregate_individual_counts(collection, group_field: str) -> dict:
    """
    Helper function that aggregates a collection by a given field while summing the number
    of individuals carrying each variant. Each document is assumed to have an 'individual_ids'
    array; its size is computed and summed.
    
    Args:
        collection: The Motor collection (e.g. db.variants).
        group_field: The field to group by (e.g. "variant_type").
        
    Returns:
        A dictionary with:
          - "total_count": Sum of all individual counts across the collection.
          - "grouped_counts": List of documents with keys '_id' (group key) and 'individual_total'.
    """
    pipeline = [
        {
            "$project": {
                group_field: 1,
                "individual_count": {"$size": {"$ifNull": ["$individual_ids", []]}}
            }
        },
        {
            "$facet": {
                "grouped_counts": [
                    {
                        "$group": {
                            "_id": f"${group_field}",
                            "individual_total": {"$sum": "$individual_count"}
                        }
                    },
                    {"$sort": {"_id": 1}}
                ],
                "total_count": [
                    {
                        "$group": {
                            "_id": None,
                            "total": {"$sum": "$individual_count"}
                        }
                    }
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


async def _aggregate_latest_report_field(collection, report_field: str) -> dict:
    """
    Helper function to aggregate the Individuals collection by a specified field extracted
    from the newest (most recent) report in each individual's reports array.
    
    Args:
        collection: The Motor collection (e.g. db.individuals).
        report_field: The field within the newest report to group by (e.g. "age_onset", "cohort", or "family_history").
        
    Returns:
        A dictionary with:
          - "total_count": The total number of individuals (with at least one report).
          - "grouped_counts": A list of documents with keys:
              - "_id": The value of the specified report field.
              - "count": The number of individuals with that value in their newest report.
    """
    pipeline = [
        { "$match": { "reports": { "$exists": True, "$ne": [] } } },
        { "$set": {
              "latest_report": {
                  "$reduce": {
                      "input": "$reports",
                      "initialValue": {"report_date": datetime(1970, 1, 1)},
                      "in": {
                          "$cond": [
                              { "$gt": ["$$this.report_date", "$$value.report_date"] },
                              "$$this",
                              "$$value"
                          ]
                      }
                  }
              }
          }
        }
    ]
    if report_field == "age_onset":
        pipeline.append({
            "$set": {
                "latest_report.age_onset": {
                    "$cond": [
                        { "$eq": [ { "$toLower": "$latest_report.age_onset" }, "prenatal" ] },
                        "prenatal",
                        { "$cond": [
                            { "$eq": [ { "$toLower": "$latest_report.age_onset" }, "not reported" ] },
                            "not reported",
                            "postnatal"
                        ] }
                    ]
                }
            }
        })
    pipeline.append({
        "$facet": {
            "grouped_counts": [
                { "$group": { "_id": f"$latest_report.{report_field}", "count": { "$sum": 1 } } },
                { "$sort": { "_id": 1 } }
            ],
            "total_count": [
                { "$count": "total" }
            ]
        }
    })
    result = await collection.aggregate(pipeline).to_list(length=1)
    if result:
        grouped_counts = result[0].get("grouped_counts", [])
        total_docs = result[0].get("total_count", [])
        total_count = total_docs[0]["total"] if total_docs else 0
        return {"total_count": total_count, "grouped_counts": grouped_counts}
    return {"total_count": 0, "grouped_counts": []}


async def _aggregate_variant_field(collection, field_name: str) -> dict:
    """
    Helper function to aggregate the Individuals collection by a specified field
    contained within the embedded 'variant' object.
    
    Args:
        collection: The Motor collection (e.g. db.individuals).
        field_name: The field inside the variant object to group by (e.g. "detection_method" or "segregation").
        
    Returns:
        A dictionary with:
          - "total_count": Total number of individuals that have a non-empty variant.
          - "grouped_counts": A list of documents with keys:
              - "_id": The value of the specified variant field.
              - "count": The number of individuals with that value.
    """
    pipeline = [
        { "$match": { "variant": { "$exists": True, "$ne": {} } } },
        { "$project": { "target": f"$variant.{field_name}" } },
        { "$facet": {
            "grouped_counts": [
                { "$group": { "_id": "$target", "count": { "$sum": 1 } } },
                { "$sort": { "_id": 1 } }
            ],
            "total_count": [
                { "$count": "total" }
            ]
        } }
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


@router.get("/variants/newest-classification-verdict-count", tags=["Aggregations"])
async def count_variants_by_newest_verdict() -> dict:
    """
    Count variants grouped by the 'verdict' field of the newest (most recent) classification object.
    
    The newest classification is determined by the maximum 'classification_date' within the 'classifications' array.
    
    Returns:
        A dictionary with:
          - "total_count": Total number of variant documents.
          - "grouped_counts": List of documents with keys "_id" (verdict) and "count".
    """
    pipeline = [
        {
            "$set": {
                "latest_classification": {
                    "$reduce": {
                        "input": "$classifications",
                        "initialValue": {"classification_date": datetime(1970, 1, 1)},
                        "in": {
                            "$cond": [
                                {"$gt": ["$$this.classification_date", "$$value.classification_date"]},
                                "$$this",
                                "$$value"
                            ]
                        }
                    }
                }
            }
        },
        {
            "$facet": {
                "grouped_counts": [
                    {
                        "$group": {
                            "_id": "$latest_classification.verdict",
                            "count": {"$sum": 1}
                        }
                    },
                    {"$sort": {"_id": 1}}
                ],
                "total_count": [
                    {"$count": "total"}
                ]
            }
        }
    ]
    result = await db.variants.aggregate(pipeline).to_list(length=1)
    if result:
        grouped_counts = result[0].get("grouped_counts", [])
        total_docs = result[0].get("total_count", [])
        total_count = total_docs[0]["total"] if total_docs else 0
        return {"total_count": total_count, "grouped_counts": grouped_counts}
    return {"total_count": 0, "grouped_counts": []}


@router.get("/variants/individual-count-by-type", tags=["Aggregations"])
async def count_individuals_by_variant_type() -> dict:
    """
    For each variant type, sum the total number of individuals carrying that variant.
    
    Each variant document contains an 'individual_ids' array.
    This endpoint projects the size of that array, groups by 'variant_type', and sums the sizes.
    
    Returns:
        A dictionary with:
          - "total_count": The overall sum of individuals (summed across all variants).
          - "grouped_counts": A list of documents with keys:
              - "_id": The variant type.
              - "individual_total": Sum of individuals carrying variants of that type.
    """
    return await _aggregate_individual_counts(db.variants, "variant_type")


@router.get("/individuals/age-onset-count", tags=["Aggregations"])
async def count_individuals_by_age_onset() -> dict:
    """
    Aggregate individuals by the 'age_onset' field of their newest report.
    
    For each individual, the newest report is selected based on the maximum 'report_date'.
    Then, if the age_onset value (case-insensitive) is "prenatal" or "not reported", that value is preserved.
    Any other value (e.g. "8y", "7m", "postnatal") is normalized to "postnatal".
    
    Returns:
        A dictionary with:
          - "total_count": Total number of individuals with at least one report.
          - "grouped_counts": List of documents with keys:
              - "_id": The standardized age_onset value.
              - "count": The number of individuals with that age_onset.
    """
    return await _aggregate_latest_report_field(db.individuals, "age_onset")


@router.get("/individuals/cohort-count", tags=["Aggregations"])
async def count_individuals_by_cohort() -> dict:
    """
    Aggregate individuals by the 'cohort' field of their newest report.
    
    For each individual, the newest report is selected based on the maximum 'report_date'.
    Then, individuals are grouped by the value of 'cohort' in that report.
    
    Returns:
        A dictionary with:
          - "total_count": Total number of individuals with at least one report.
          - "grouped_counts": List of documents with keys:
              - "_id": The cohort value.
              - "count": The number of individuals with that cohort.
    """
    return await _aggregate_latest_report_field(db.individuals, "cohort")


@router.get("/individuals/family-history-count", tags=["Aggregations"])
async def count_individuals_by_family_history() -> dict:
    """
    Aggregate individuals by the 'family_history' field of their newest report.
    
    For each individual, the newest report is selected based on the maximum 'report_date'.
    Then, individuals are grouped by the value of 'family_history' in that report.
    
    Returns:
        A dictionary with:
          - "total_count": Total number of individuals with at least one report.
          - "grouped_counts": List of documents with keys:
              - "_id": The family_history value.
              - "count": The number of individuals with that family_history.
    """
    return await _aggregate_latest_report_field(db.individuals, "family_history")


@router.get("/individuals/detection-method-count", tags=["Aggregations"])
async def count_individuals_by_detection_method() -> dict:
    """
    Aggregate individuals by the 'detection_method' field found in their variant object.
    
    Only individuals with a non-empty variant object are considered.
    
    Returns:
        A dictionary with:
          - "total_count": Total number of individuals with variant data.
          - "grouped_counts": List of documents with keys:
              - "_id": The detection method.
              - "count": The number of individuals with that detection method.
    """
    return await _aggregate_variant_field(db.individuals, "detection_method")


@router.get("/individuals/segregation-count", tags=["Aggregations"])
async def count_individuals_by_segregation() -> dict:
    """
    Aggregate individuals by the 'segregation' field found in their variant object.
    
    Only individuals with a non-empty variant object are considered.
    
    Returns:
        A dictionary with:
          - "total_count": Total number of individuals with variant data.
          - "grouped_counts": List of documents with keys:
              - "_id": The segregation value.
              - "count": The number of individuals with that segregation.
    """
    return await _aggregate_variant_field(db.individuals, "segregation")


@router.get("/individuals/phenotype-described-count", tags=["Aggregations"])
async def count_phenotypes_by_described() -> dict:
    """
    Aggregate the phenotypes from the newest report (review) of each individual.
    
    The pipeline converts the 'phenotypes' object in the newest report into an array,
    unwinds it, and then groups by phenotype_id and name.
    For each phenotype, counts for each 'described' category ("yes", "no", and "not reported")
    are accumulated and then grouped into a sub-object.
    Finally, the results are sorted in descending order by the "yes" count.
    
    Returns:
        A dictionary with a key "results" containing a list of documents.
        Each document has:
          - phenotype_id: The phenotype identifier.
          - name: The phenotype name.
          - counts: An object with keys:
              - "yes": Count of individuals with described "yes".
              - "no": Count of individuals with described "no".
              - "not reported": Count of individuals with described "not reported".
    """
    pipeline = [
        { "$match": { "reports": { "$exists": True, "$ne": [] } } },
        { "$set": {
              "latest_report": {
                  "$reduce": {
                      "input": "$reports",
                      "initialValue": { "report_date": datetime(1970, 1, 1) },
                      "in": {
                          "$cond": [
                              { "$gt": ["$$this.report_date", "$$value.report_date"] },
                              "$$this",
                              "$$value"
                          ]
                      }
                  }
              }
          }
        },
        { "$project": {
              "phenotypes": { "$objectToArray": "$latest_report.phenotypes" }
          }
        },
        { "$unwind": "$phenotypes" },
        { "$group": {
              "_id": {
                  "phenotype_id": "$phenotypes.v.phenotype_id",
                  "name": "$phenotypes.v.name"
              },
              "yes": {
                  "$sum": {
                      "$cond": [
                          { "$eq": [ { "$toLower": "$phenotypes.v.described" }, "yes" ] },
                          1,
                          0
                      ]
                  }
              },
              "no": {
                  "$sum": {
                      "$cond": [
                          { "$eq": [ { "$toLower": "$phenotypes.v.described" }, "no" ] },
                          1,
                          0
                      ]
                  }
              },
              "not_reported": {
                  "$sum": {
                      "$cond": [
                          { "$eq": [ { "$toLower": "$phenotypes.v.described" }, "not reported" ] },
                          1,
                          0
                      ]
                  }
              }
          }
        },
        { "$project": {
              "_id": 0,
              "phenotype_id": "$_id.phenotype_id",
              "name": "$_id.name",
              "counts": {
                  "yes": "$yes",
                  "no": "$no",
                  "not reported": "$not_reported"
              }
          }
        },
        { "$sort": { "counts.yes": -1 } }
    ]
    results = await db.individuals.aggregate(pipeline).to_list(length=None)
    return {"results": results}


@router.get("/publications/cumulative-count", tags=["Aggregations"])
async def cumulative_publications() -> dict:
    """
    Aggregate the publications collection to compute cumulative counts in one-month intervals.
    
    Two facets are returned:
      - overall: Cumulative count of all publications over time.
      - byType: Cumulative count over time grouped by publication_type.
    
    Each facet uses $dateTrunc to group publication_date into month intervals, and
    $setWindowFields to compute a running total.
    
    Returns:
        A dictionary with keys:
          - "overall": List of documents with monthDate, monthlyCount, and cumulativeCount.
          - "byType": List of documents with monthDate, publication_type, monthlyCount, and cumulativeCount.
    """
    overall_pipeline = [
        { "$set": { "monthDate": { "$dateTrunc": { "date": "$publication_date", "unit": "month" } } } },
        { "$group": { "_id": "$monthDate", "monthlyCount": { "$sum": 1 } } },
        { "$sort": { "_id": 1 } },
        { "$setWindowFields": {
            "sortBy": { "_id": 1 },
            "output": {
                "cumulativeCount": {
                    "$sum": "$monthlyCount",
                    "window": { "documents": [ "unbounded", "current" ] }
                }
            }
        } },
        { "$project": { "_id": 0, "monthDate": "$_id", "monthlyCount": 1, "cumulativeCount": 1 } }
    ]

    by_type_pipeline = [
        { "$set": { "monthDate": { "$dateTrunc": { "date": "$publication_date", "unit": "month" } } } },
        { "$group": {
            "_id": { "monthDate": "$monthDate", "publication_type": "$publication_type" },
            "monthlyCount": { "$sum": 1 }
        } },
        { "$set": {
            "monthDate": "$_id.monthDate",
            "publication_type": "$_id.publication_type"
        } },
        { "$sort": { "monthDate": 1 } },
        { "$setWindowFields": {
            "partitionBy": "$publication_type",
            "sortBy": { "monthDate": 1 },
            "output": {
                "cumulativeCount": {
                    "$sum": "$monthlyCount",
                    "window": { "documents": [ "unbounded", "current" ] }
                }
            }
        } },
        { "$project": { "_id": 0, "monthDate": 1, "publication_type": 1, "monthlyCount": 1, "cumulativeCount": 1 } }
    ]

    facet_pipeline = [
        {
            "$facet": {
                "overall": overall_pipeline,
                "byType": by_type_pipeline
            }
        }
    ]
    result = await db.publications.aggregate(facet_pipeline).to_list(length=1)
    return result[0] if result else {"overall": [], "byType": []}
