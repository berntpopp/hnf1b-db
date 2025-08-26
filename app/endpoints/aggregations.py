# File: app/endpoints/aggregations.py

from datetime import datetime

from fastapi import APIRouter

from app.database import db

router = APIRouter()


async def _aggregate_with_total(collection, group_field: str) -> dict:
    """Helper function to perform an aggregation.

    Returns both grouped counts and the total document count.

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
                    {"$sort": {"_id": 1}},
                ],
                "total_count": [{"$count": "total"}],
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
    Helper function that aggregates a collection by a given field.

    Sums the number of individuals carrying each variant. Each document is
    assumed to have an 'individual_ids' array; its size is computed and summed.

    Args:
        collection: The Motor collection (e.g. db.variants).
        group_field: The field to group by (e.g. "variant_type").

    Returns:
        A dictionary with:
          - "total_count": Sum of all individual counts across the collection.
          - "grouped_counts": List of documents with keys '_id' (group key) and 'count'.
    """
    pipeline = [
        {
            "$project": {
                group_field: 1,
                "individual_count": {"$size": {"$ifNull": ["$individual_ids", []]}},
            }
        },
        {
            "$facet": {
                "grouped_counts": [
                    {
                        "$group": {
                            "_id": f"${group_field}",
                            "count": {"$sum": "$individual_count"},
                        }
                    },
                    {"$sort": {"_id": 1}},
                ],
                "total_count": [
                    {"$group": {"_id": None, "total": {"$sum": "$individual_count"}}}
                ],
            }
        },
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
    Aggregate Individuals by a field from their newest report.

    Helper function to aggregate the Individuals collection by a specified field
    extracted from the newest (most recent) report in each individual's reports
    array.

    Args:
        collection: The Motor collection (e.g. db.individuals).
        report_field: The field within the newest report to group by
            (e.g. "age_onset", "cohort", or "family_history").

    Returns:
        A dictionary with:
          - "total_count": The total number of individuals (with at least one report).
          - "grouped_counts": A list of documents with keys:
              - "_id": The value of the specified report field.
              - "count": The number of individuals with that value in their
                newest report.
    """
    pipeline = [
        {"$match": {"reports": {"$exists": True, "$ne": []}}},
        {
            "$set": {
                "latest_report": {
                    "$reduce": {
                        "input": "$reports",
                        "initialValue": {"report_date": datetime(1970, 1, 1)},
                        "in": {
                            "$cond": [
                                {"$gt": ["$$this.report_date", "$$value.report_date"]},
                                "$$this",
                                "$$value",
                            ]
                        },
                    }
                }
            }
        },
    ]
    if report_field == "age_onset":
        pipeline.append(
            {
                "$set": {
                    "latest_report.age_onset": {
                        "$cond": [
                            {
                                "$eq": [
                                    {"$toLower": "$latest_report.age_onset"},
                                    "prenatal",
                                ]
                            },
                            "prenatal",
                            {
                                "$cond": [
                                    {
                                        "$eq": [
                                            {"$toLower": "$latest_report.age_onset"},
                                            "not reported",
                                        ]
                                    },
                                    "not reported",
                                    "postnatal",
                                ]
                            },
                        ]
                    }
                }
            }
        )
    pipeline.append(
        {
            "$facet": {
                "grouped_counts": [
                    {
                        "$group": {
                            "_id": f"$latest_report.{report_field}",
                            "count": {"$sum": 1},
                        }
                    },
                    {"$sort": {"_id": 1}},
                ],
                "total_count": [{"$count": "total"}],
            }
        }
    )
    result = await collection.aggregate(pipeline).to_list(length=1)
    if result:
        grouped_counts = result[0].get("grouped_counts", [])
        total_docs = result[0].get("total_count", [])
        total_count = total_docs[0]["total"] if total_docs else 0
        return {"total_count": total_count, "grouped_counts": grouped_counts}
    return {"total_count": 0, "grouped_counts": []}


async def _aggregate_variant_field(collection, field_name: str) -> dict:
    """
    Aggregate Individuals by a field within their variant object.

    Helper function to aggregate the Individuals collection by a specified field
    contained within the embedded 'variant' object.

    Args:
        collection: The Motor collection (e.g. db.individuals).
        field_name: The field inside the variant object to group by
            (e.g. "detection_method" or "segregation").

    Returns:
        A dictionary with:
          - "total_count": Total number of individuals that have a
            non-empty variant.
          - "grouped_counts": A list of documents with keys:
              - "_id": The value of the specified variant field.
              - "count": The number of individuals with that value.
    """
    pipeline = [
        {"$match": {"variant": {"$exists": True, "$ne": {}}}},
        {"$project": {"target": f"$variant.{field_name}"}},
        {
            "$facet": {
                "grouped_counts": [
                    {"$group": {"_id": "$target", "count": {"$sum": 1}}},
                    {"$sort": {"_id": 1}},
                ],
                "total_count": [{"$count": "total"}],
            }
        },
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
    Count individuals grouped by their 'Sex' field.

    Also returns the total number of individuals.

    Returns:
        A dictionary with:
          - "total_count": Total number of individuals.
          - "grouped_counts": List of documents with keys "_id" (sex)
            and "count".
    """
    return await _aggregate_with_total(db.individuals, "Sex")


@router.get("/variants/type-count", tags=["Aggregations"])
async def count_variants_by_type() -> dict:
    """
    Count variants grouped by their type.

    Groups by the 'variant_type' field and returns the total number of variants.

    Returns:
        A dictionary with:
          - "total_count": Total number of variants.
          - "grouped_counts": List of documents with keys "_id"
            (variant type) and "count".
    """
    return await _aggregate_with_total(db.variants, "variant_type")


@router.get("/publications/type-count", tags=["Aggregations"])
async def count_publications_by_type() -> dict:
    """
    Count publications grouped by their 'publication_type' field.

    Also returns the total number of publications.

    Returns:
        A dictionary with:
          - "total_count": Total number of publications.
          - "grouped_counts": List of documents with keys "_id"
            (publication type) and "count".
    """
    return await _aggregate_with_total(db.publications, "publication_type")


@router.get("/variants/newest-classification-verdict-count", tags=["Aggregations"])
async def count_variants_by_newest_verdict() -> dict:
    """
    Count variants grouped by the 'verdict' field of the newest classification.

    The newest classification is determined by the maximum 'classification_date'
    within the 'classifications' array.

    Returns:
        A dictionary with:
          - "total_count": Total number of variant documents.
          - "grouped_counts": List of documents with keys "_id" (verdict)
            and "count".
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
                                {
                                    "$gt": [
                                        "$$this.classification_date",
                                        "$$value.classification_date",
                                    ]
                                },
                                "$$this",
                                "$$value",
                            ]
                        },
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
                            "count": {"$sum": 1},
                        }
                    },
                    {"$sort": {"_id": 1}},
                ],
                "total_count": [{"$count": "total"}],
            }
        },
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
    Sum the total number of individuals for each variant type.

    Each variant document contains an 'individual_ids' array.
    This endpoint projects the size of that array, groups by 'variant_type',
    and sums the sizes.

    Returns:
        A dictionary with:
          - "total_count": The overall sum of individuals (summed across
            all variants).
          - "grouped_counts": A list of documents with keys:
              - "_id": The variant type.
              - "count": Sum of individuals carrying variants of that type.
    """
    return await _aggregate_individual_counts(db.variants, "variant_type")


@router.get("/individuals/age-onset-count", tags=["Aggregations"])
async def count_individuals_by_age_onset() -> dict:
    """
    Aggregate individuals by the 'age_onset' field of their newest report.

    For each individual, the newest report is selected based on the maximum
    'report_date'. Then, if the age_onset value (case-insensitive) is
    "prenatal" or "not reported", that value is preserved.
    Any other value (e.g. "8y", "7m", "postnatal") is normalized to "postnatal".

    Returns:
        A dictionary with:
          - "total_count": Total number of individuals with at least one
            report.
          - "grouped_counts": List of documents with keys:
              - "_id": The standardized age_onset value.
              - "count": The number of individuals with that age_onset.
    """
    return await _aggregate_latest_report_field(db.individuals, "age_onset")


@router.get("/individuals/cohort-count", tags=["Aggregations"])
async def count_individuals_by_cohort() -> dict:
    """
    Aggregate individuals by the 'cohort' field of their newest report.

    For each individual, the newest report is selected based on the maximum
    'report_date'. Then, individuals are grouped by the value of 'cohort' in
    that report.

    Returns:
        A dictionary with:
          - "total_count": Total number of individuals with at least one
            report.
          - "grouped_counts": List of documents with keys:
              - "_id": The cohort value.
              - "count": The number of individuals with that cohort.
    """
    return await _aggregate_latest_report_field(db.individuals, "cohort")


@router.get("/individuals/family-history-count", tags=["Aggregations"])
async def count_individuals_by_family_history() -> dict:
    """
    Aggregate individuals by the 'family_history' field of their newest report.

    For each individual, the newest report is selected based on the maximum
    'report_date'. Then, individuals are grouped by the value of
    'family_history' in that report.

    Returns:
        A dictionary with:
          - "total_count": Total number of individuals with at least one
            report.
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
              - "count": The number of individuals with that detection
                method.
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

    The pipeline converts the 'phenotypes' object in the newest report into an
    array, unwinds it, and then groups by phenotype_id and name.
    For each phenotype, counts for each 'described' category ("yes", "no", and
    "not reported") are accumulated and then grouped into a sub-object.
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
        {"$match": {"reports": {"$exists": True, "$ne": []}}},
        {
            "$set": {
                "latest_report": {
                    "$reduce": {
                        "input": "$reports",
                        "initialValue": {"report_date": datetime(1970, 1, 1)},
                        "in": {
                            "$cond": [
                                {"$gt": ["$$this.report_date", "$$value.report_date"]},
                                "$$this",
                                "$$value",
                            ]
                        },
                    }
                }
            }
        },
        {"$project": {"phenotypes": {"$objectToArray": "$latest_report.phenotypes"}}},
        {"$unwind": "$phenotypes"},
        {
            "$group": {
                "_id": {
                    "phenotype_id": "$phenotypes.v.phenotype_id",
                    "name": "$phenotypes.v.name",
                },
                "yes": {
                    "$sum": {
                        "$cond": [
                            {"$eq": [{"$toLower": "$phenotypes.v.described"}, "yes"]},
                            1,
                            0,
                        ]
                    }
                },
                "no": {
                    "$sum": {
                        "$cond": [
                            {"$eq": [{"$toLower": "$phenotypes.v.described"}, "no"]},
                            1,
                            0,
                        ]
                    }
                },
                "not_reported": {
                    "$sum": {
                        "$cond": [
                            {
                                "$eq": [
                                    {"$toLower": "$phenotypes.v.described"},
                                    "not reported",
                                ]
                            },
                            1,
                            0,
                        ]
                    }
                },
            }
        },
        {
            "$project": {
                "_id": 0,
                "phenotype_id": "$_id.phenotype_id",
                "name": "$_id.name",
                "counts": {
                    "yes": "$yes",
                    "no": "$no",
                    "not reported": "$not_reported",
                },
            }
        },
        {"$sort": {"counts.yes": -1}},
    ]
    results = await db.individuals.aggregate(pipeline).to_list(length=None)
    return {"results": results}


@router.get("/publications/cumulative-count", tags=["Aggregations"])
async def cumulative_publications() -> dict:
    """
    Compute cumulative publication counts in one-month intervals.

    Two facets are returned:
      - overall: Cumulative count of all publications over time.
      - byType: Cumulative count over time grouped by publication_type.

    Each facet uses $dateTrunc to group publication_date into month intervals, and
    $setWindowFields to compute a running total.

    Returns:
        A dictionary with keys:
          - "overall": List of documents with monthDate, monthlyCount, and
            cumulativeCount.
          - "byType": List of documents with monthDate, publication_type,
            monthlyCount, and cumulativeCount.
    """
    overall_pipeline = [
        {
            "$set": {
                "monthDate": {
                    "$dateTrunc": {"date": "$publication_date", "unit": "month"}
                }
            }
        },
        {"$group": {"_id": "$monthDate", "monthlyCount": {"$sum": 1}}},
        {"$sort": {"_id": 1}},
        {
            "$setWindowFields": {
                "sortBy": {"_id": 1},
                "output": {
                    "cumulativeCount": {
                        "$sum": "$monthlyCount",
                        "window": {"documents": ["unbounded", "current"]},
                    }
                },
            }
        },
        {
            "$project": {
                "_id": 0,
                "monthDate": "$_id",
                "monthlyCount": 1,
                "cumulativeCount": 1,
            }
        },
    ]

    by_type_pipeline = [
        {
            "$set": {
                "monthDate": {
                    "$dateTrunc": {"date": "$publication_date", "unit": "month"}
                }
            }
        },
        {
            "$group": {
                "_id": {
                    "monthDate": "$monthDate",
                    "publication_type": "$publication_type",
                },
                "monthlyCount": {"$sum": 1},
            }
        },
        {
            "$set": {
                "monthDate": "$_id.monthDate",
                "publication_type": "$_id.publication_type",
            }
        },
        {"$sort": {"monthDate": 1}},
        {
            "$setWindowFields": {
                "partitionBy": "$publication_type",
                "sortBy": {"monthDate": 1},
                "output": {
                    "cumulativeCount": {
                        "$sum": "$monthlyCount",
                        "window": {"documents": ["unbounded", "current"]},
                    }
                },
            }
        },
        {
            "$project": {
                "_id": 0,
                "monthDate": 1,
                "publication_type": 1,
                "monthlyCount": 1,
                "cumulativeCount": 1,
            }
        },
    ]

    facet_pipeline = [
        {"$facet": {"overall": overall_pipeline, "byType": by_type_pipeline}}
    ]
    result = await db.publications.aggregate(facet_pipeline).to_list(length=1)
    return result[0] if result else {"overall": [], "byType": []}


@router.get("/variants/small_variants", tags=["Aggregations"])
async def get_variant_small_variants() -> dict:
    """Retrieve variants of type SNV or indel and extract flag information.

    For each variant that matches variant_type in ['SNV', 'indel'], this
    endpoint extracts:
      - variant_id,
      - verdict from the newest (most recent) classification (based on
        classification_date),
      - transcript, c_dot, p_dot, and protein_position from the newest
        annotation (by annotation_date) among annotations with source 'vep',
      - individual_count: number of individuals carrying the variant (computed
        as the length of the individual_ids array),
      - cadd_score: the CADD score from the newest VEP annotation.

    Returns:
        A dictionary with a key "small_variants" containing an array of flag
        objects.
    """
    pipeline = [
        # 1. Filter for variants with type SNV or indel.
        {"$match": {"variant_type": {"$in": ["SNV", "indel"]}}},
        # 2. Determine the newest classification and filter annotations for
        # source "vep".
        {
            "$set": {
                "latest_classification": {
                    "$reduce": {
                        "input": "$classifications",
                        "initialValue": {"classification_date": datetime(1970, 1, 1)},
                        "in": {
                            "$cond": [
                                {
                                    "$gt": [
                                        "$$this.classification_date",
                                        "$$value.classification_date",
                                    ]
                                },
                                "$$this",
                                "$$value",
                            ]
                        },
                    }
                },
                "vep_annotations": {
                    "$filter": {
                        "input": "$annotations",
                        "as": "annotation",
                        "cond": {"$eq": ["$$annotation.source", "vep"]},
                    }
                },
            }
        },
        # 3. Determine the newest annotation among those with source "vep".
        {
            "$set": {
                "latest_vep_annotation": {
                    "$reduce": {
                        "input": "$vep_annotations",
                        "initialValue": {"annotation_date": datetime(1970, 1, 1)},
                        "in": {
                            "$cond": [
                                {
                                    "$gt": [
                                        "$$this.annotation_date",
                                        "$$value.annotation_date",
                                    ]
                                },
                                "$$this",
                                "$$value",
                            ]
                        },
                    }
                }
            }
        },
        # 4. Project the required fields along with the count of individuals
        # and the CADD score.
        {
            "$project": {
                "_id": 0,
                "variant_id": 1,
                "verdict": "$latest_classification.verdict",
                "transcript": "$latest_vep_annotation.transcript",
                "c_dot": "$latest_vep_annotation.c_dot",
                "p_dot": "$latest_vep_annotation.p_dot",
                "protein_position": "$latest_vep_annotation.protein_position",
                "individual_count": {"$size": {"$ifNull": ["$individual_ids", []]}},
                "cadd_score": "$latest_vep_annotation.cadd_phred",
            }
        },
    ]
    results = await db.variants.aggregate(pipeline).to_list(length=None)
    return {"small_variants": results}


@router.get("/summary", tags=["Aggregations"])
async def get_summary_stats() -> dict:
    """Retrieve summary statistics for main collections.

    For Individuals:
      - Count the total number of individuals.
      - Sum the total number of reports across all individuals.

    For Variants and Publications:
      - Count the total number of documents.

    Returns:
        A dictionary with:
            {
                "individuals": <int>,
                "total_reports": <int>,
                "variants": <int>,
                "publications": <int>
            }
    """
    # Get counts for each collection using count_documents.
    individuals_count = await db.individuals.count_documents({})
    variants_count = await db.variants.count_documents({})
    publications_count = await db.publications.count_documents({})

    # Compute total number of reports across all individuals.
    # For each document, if "reports" is missing, treat it as an empty list.
    pipeline = [
        {"$project": {"report_count": {"$size": {"$ifNull": ["$reports", []]}}}},
        {"$group": {"_id": None, "total_reports": {"$sum": "$report_count"}}},
    ]
    reports_result = await db.individuals.aggregate(pipeline).to_list(length=1)
    total_reports = reports_result[0]["total_reports"] if reports_result else 0

    return {
        "individuals": individuals_count,
        "total_reports": total_reports,
        "variants": variants_count,
        "publications": publications_count,
    }


@router.get("/variants/impact-group-count", tags=["Aggregations"])
async def count_variants_by_impact_group() -> dict:
    """Aggregate variants into impact groups.

    Groups are based on the newest VEP annotation's impact value and the newest
    classification's verdict. Grouping logic:
      - If impact == "MODERATE" => "nT"
      - If impact == "HIGH" => "T"
      - If impact == "LOW" and verdict == "LP/P" => "T"
      - If impact == "MODIFIER" and verdict == "LP/P" => "T"
      - If impact is null and verdict == "LP/P" => "T"
      - Else => "other"

    Returns:
        A dictionary with:
          - "total_count": Total number of variants processed.
          - "grouped_counts": A list of documents with keys "_id" (impact
            group) and "count".
    """
    pipeline = [
        # 1. Get the newest classification and filter annotations for source "vep"
        {
            "$set": {
                "latest_classification": {
                    "$reduce": {
                        "input": "$classifications",
                        "initialValue": {"classification_date": datetime(1970, 1, 1)},
                        "in": {
                            "$cond": [
                                {
                                    "$gt": [
                                        "$$this.classification_date",
                                        "$$value.classification_date",
                                    ]
                                },
                                "$$this",
                                "$$value",
                            ]
                        },
                    }
                },
                "vep_annotations": {
                    "$filter": {
                        "input": "$annotations",
                        "as": "annotation",
                        "cond": {"$eq": ["$$annotation.source", "vep"]},
                    }
                },
            }
        },
        # 2. Get the newest VEP annotation based on annotation_date
        {
            "$set": {
                "latest_vep_annotation": {
                    "$reduce": {
                        "input": "$vep_annotations",
                        "initialValue": {"annotation_date": datetime(1970, 1, 1)},
                        "in": {
                            "$cond": [
                                {
                                    "$gt": [
                                        "$$this.annotation_date",
                                        "$$value.annotation_date",
                                    ]
                                },
                                "$$this",
                                "$$value",
                            ]
                        },
                    }
                }
            }
        },
        # 3. Compute impact_groups according to the specified logic
        {
            "$set": {
                "impact_groups": {
                    "$switch": {
                        "branches": [
                            {
                                "case": {
                                    "$eq": ["$latest_vep_annotation.impact", "MODERATE"]
                                },
                                "then": "nT",
                            },
                            {
                                "case": {
                                    "$eq": ["$latest_vep_annotation.impact", "HIGH"]
                                },
                                "then": "T",
                            },
                            {
                                "case": {
                                    "$and": [
                                        {
                                            "$eq": [
                                                "$latest_vep_annotation.impact",
                                                "LOW",
                                            ]
                                        },
                                        {
                                            "$eq": [
                                                "$latest_classification.verdict",
                                                "LP/P",
                                            ]
                                        },
                                    ]
                                },
                                "then": "T",
                            },
                            {
                                "case": {
                                    "$and": [
                                        {
                                            "$eq": [
                                                "$latest_vep_annotation.impact",
                                                "MODIFIER",
                                            ]
                                        },
                                        {
                                            "$eq": [
                                                "$latest_classification.verdict",
                                                "LP/P",
                                            ]
                                        },
                                    ]
                                },
                                "then": "T",
                            },
                            {
                                "case": {
                                    "$and": [
                                        {
                                            "$eq": [
                                                "$latest_vep_annotation.impact",
                                                None,
                                            ]
                                        },
                                        {
                                            "$eq": [
                                                "$latest_classification.verdict",
                                                "LP/P",
                                            ]
                                        },
                                    ]
                                },
                                "then": "T",
                            },
                        ],
                        "default": "other",
                    }
                }
            }
        },
        # 4. Group by the computed impact_groups and count the documents
        {
            "$facet": {
                "grouped_counts": [
                    {"$group": {"_id": "$impact_groups", "count": {"$sum": 1}}},
                    {"$sort": {"_id": 1}},
                ],
                "total_count": [{"$count": "total"}],
            }
        },
    ]

    result = await db.variants.aggregate(pipeline).to_list(length=1)
    if result:
        grouped_counts = result[0].get("grouped_counts", [])
        total_docs = result[0].get("total_count", [])
        total_count = total_docs[0]["total"] if total_docs else 0
        return {"total_count": total_count, "grouped_counts": grouped_counts}
    return {"total_count": 0, "grouped_counts": []}


@router.get("/variants/effect-group-count", tags=["Aggregations"])
async def count_variants_by_effect_group() -> dict:
    """Aggregate variants into effect groups.

    Groups are based on the newest VEP annotation's effect and impact values,
    as well as the newest classification's verdict. The grouping logic is:
      - If effect == "transcript_ablation" => "17qDel"
      - If effect == "transcript_amplification" => "17qDup"
      - If impact == "MODERATE" => "nT"
      - If impact is null and verdict == "LP/P" => "T"
      - If impact == "LOW" and verdict == "LP/P" => "T"
      - If effect is in the list of severe effects => "T"
      - Else => "other"

    Returns:
        A dictionary with:
          - "total_count": The total number of variants processed.
          - "grouped_counts": A list of documents with keys "_id" (effect
            group) and "count".
    """
    pipeline = [
        # 1. Extract the newest classification and filter annotations for VEP.
        {
            "$set": {
                "latest_classification": {
                    "$reduce": {
                        "input": "$classifications",
                        "initialValue": {"classification_date": datetime(1970, 1, 1)},
                        "in": {
                            "$cond": [
                                {
                                    "$gt": [
                                        "$$this.classification_date",
                                        "$$value.classification_date",
                                    ]
                                },
                                "$$this",
                                "$$value",
                            ]
                        },
                    }
                },
                "vep_annotations": {
                    "$filter": {
                        "input": "$annotations",
                        "as": "annotation",
                        "cond": {"$eq": ["$$annotation.source", "vep"]},
                    }
                },
            }
        },
        # 2. Reduce the VEP annotations to the one with the most recent annotation_date.
        {
            "$set": {
                "latest_vep_annotation": {
                    "$reduce": {
                        "input": "$vep_annotations",
                        "initialValue": {"annotation_date": datetime(1970, 1, 1)},
                        "in": {
                            "$cond": [
                                {
                                    "$gt": [
                                        "$$this.annotation_date",
                                        "$$value.annotation_date",
                                    ]
                                },
                                "$$this",
                                "$$value",
                            ]
                        },
                    }
                }
            }
        },
        # 3. Compute effect_groups using the provided logic.
        {
            "$set": {
                "effect_groups": {
                    "$switch": {
                        "branches": [
                            {
                                "case": {
                                    "$eq": [
                                        "$latest_vep_annotation.effect",
                                        "transcript_ablation",
                                    ]
                                },
                                "then": "17qDel",
                            },
                            {
                                "case": {
                                    "$eq": [
                                        "$latest_vep_annotation.effect",
                                        "transcript_amplification",
                                    ]
                                },
                                "then": "17qDup",
                            },
                            {
                                "case": {
                                    "$eq": ["$latest_vep_annotation.impact", "MODERATE"]
                                },
                                "then": "nT",
                            },
                            {
                                "case": {
                                    "$and": [
                                        {
                                            "$eq": [
                                                "$latest_vep_annotation.impact",
                                                None,
                                            ]
                                        },
                                        {
                                            "$eq": [
                                                "$latest_classification.verdict",
                                                "LP/P",
                                            ]
                                        },
                                    ]
                                },
                                "then": "T",
                            },
                            {
                                "case": {
                                    "$and": [
                                        {
                                            "$eq": [
                                                "$latest_vep_annotation.impact",
                                                "LOW",
                                            ]
                                        },
                                        {
                                            "$eq": [
                                                "$latest_classification.verdict",
                                                "LP/P",
                                            ]
                                        },
                                    ]
                                },
                                "then": "T",
                            },
                            {
                                "case": {
                                    "$in": [
                                        "$latest_vep_annotation.effect",
                                        [
                                            "stop_gained",
                                            "start_lost",
                                            "stop_lost",
                                            "frameshift_variant",
                                            "splice_donor_variant",
                                            "splice_acceptor_variant",
                                            "splice_donor_5th_base_variant",
                                            "coding_sequence_variant",
                                        ],
                                    ]
                                },
                                "then": "T",
                            },
                        ],
                        "default": "other",
                    }
                }
            }
        },
        # 4. Group by the computed effect_groups and get the total document count.
        {
            "$facet": {
                "grouped_counts": [
                    {"$group": {"_id": "$effect_groups", "count": {"$sum": 1}}},
                    {"$sort": {"_id": 1}},
                ],
                "total_count": [{"$count": "total"}],
            }
        },
    ]

    result = await db.variants.aggregate(pipeline).to_list(length=1)
    if result:
        grouped_counts = result[0].get("grouped_counts", [])
        total_docs = result[0].get("total_count", [])
        total_count = total_docs[0]["total"] if total_docs else 0
        return {"total_count": total_count, "grouped_counts": grouped_counts}
    return {"total_count": 0, "grouped_counts": []}


@router.get("/individuals/phenotype-cohort-count", tags=["Aggregations"])
async def phenotype_cohort_counts() -> dict:
    """Classify individuals based on phenotypes from their newest report.

    For each individual (with at least one report), using the phenotypes from
    the newest report, classify the individual as follows:

      - MODY: Has "Maturity-onset diabetes of the young" (described == "yes").

      - CAKUT: Has any of these kidney-related phenotypes (described == "yes"):
          • "Multicystic kidney dysplasia",
          • "Unilateral renal agenesis",
          • "Renal hypoplasia",
          • "Abnormal renal morphology"
        OR has "Abnormality of the genital system" (described == "yes") AND
        also has any kidney-related phenotype.

      - any_kidney: Defined as the presence (described == "yes") of any of:
          "Chronic kidney disease",
          "Stage 1 chronic kidney disease",
          "Stage 2 chronic kidney disease",
          "Stage 3 chronic kidney disease",
          "Stage 4 chronic kidney disease",
          "Stage 5 chronic kidney disease",
          "Multicystic kidney dysplasia",
          "Renal hypoplasia",
          "Renal cyst",
          "Unilateral renal agenesis",
          "Abnormal renal morphology",
          "Renal cortical hyperechogenicity",
          "Multiple glomerular cysts",
          "Oligomeganephronia"

    Then, define mutually exclusive groups:
      - MODY_only: MODY true and CAKUT false.
      - CAKUT_only: CAKUT true and MODY false.
      - CAKUT_MODY: Both CAKUT and MODY are true.
      - Other: Neither MODY nor CAKUT.

    Finally, return cohort-level counts for each group.
    """
    pipeline = [
        # 1. Consider only individuals with at least one report.
        {"$match": {"reports": {"$exists": True, "$ne": []}}},
        # 2. Select the newest report based on report_date.
        {
            "$set": {
                "newest_report": {
                    "$reduce": {
                        "input": "$reports",
                        "initialValue": {"report_date": datetime(1970, 1, 1)},
                        "in": {
                            "$cond": [
                                {"$gt": ["$$this.report_date", "$$value.report_date"]},
                                "$$this",
                                "$$value",
                            ]
                        },
                    }
                }
            }
        },
        # 3. Convert the newest report's phenotypes object to an array.
        {
            "$set": {
                "phenotype_entries": {"$objectToArray": "$newest_report.phenotypes"}
            }
        },
        # 4. Compute any_kidney flag (true if any kidney-related phenotype is
        # present with described == "yes").
        {
            "$set": {
                "any_kidney": {
                    "$gt": [
                        {
                            "$size": {
                                "$filter": {
                                    "input": "$phenotype_entries",
                                    "as": "p",
                                    "cond": {
                                        "$and": [
                                            {
                                                "$in": [
                                                    "$$p.v.name",
                                                    [
                                                        "Chronic kidney disease",
                                                        "Stage 1 chronic kidney"
                                                        " disease",
                                                        "Stage 2 chronic kidney"
                                                        " disease",
                                                        "Stage 3 chronic kidney"
                                                        " disease",
                                                        "Stage 4 chronic kidney"
                                                        " disease",
                                                        "Stage 5 chronic kidney"
                                                        " disease",
                                                        "Multicystic kidney dysplasia",
                                                        "Renal hypoplasia",
                                                        "Renal cyst",
                                                        "Unilateral renal" " agenesis",
                                                        "Abnormal renal" " morphology",
                                                        "Renal cortical"
                                                        " hyperechogenicity",
                                                        "Multiple glomerular cysts",
                                                        "Oligomeganephronia",
                                                    ],
                                                ]
                                            },
                                            {
                                                "$eq": [
                                                    {"$toLower": "$$p.v.described"},
                                                    "yes",
                                                ]
                                            },
                                        ]
                                    },
                                }
                            }
                        },
                        0,
                    ]
                }
            }
        },
        # 5. Compute MODY flag (true if "Maturity-onset diabetes of the young"
        # is present with described == "yes").
        {
            "$set": {
                "MODY": {
                    "$gt": [
                        {
                            "$size": {
                                "$filter": {
                                    "input": "$phenotype_entries",
                                    "as": "p",
                                    "cond": {
                                        "$and": [
                                            {
                                                "$eq": [
                                                    "$$p.v.name",
                                                    "Maturity-onset diabetes"
                                                    " of the young",
                                                ]
                                            },
                                            {
                                                "$eq": [
                                                    {"$toLower": "$$p.v.described"},
                                                    "yes",
                                                ]
                                            },
                                        ]
                                    },
                                }
                            }
                        },
                        0,
                    ]
                }
            }
        },
        # 6. Compute CAKUT flag:
        #    Option A: One of these kidney-specific phenotypes is present with
        #    described == "yes".
        #    Option B: "Abnormality of the genital system" is present
        #    (described == "yes") AND any_kidney is true.
        {
            "$set": {
                "CAKUT": {
                    "$or": [
                        {
                            "$gt": [
                                {
                                    "$size": {
                                        "$filter": {
                                            "input": "$phenotype_entries",
                                            "as": "p",
                                            "cond": {
                                                "$and": [
                                                    {
                                                        "$in": [
                                                            "$$p.v.name",
                                                            [
                                                                "Multicystic kidney"
                                                                " dysplasia",
                                                                "Unilateral renal"
                                                                " agenesis",
                                                                "Renal hypoplasia",
                                                                "Abnormal renal"
                                                                " morphology",
                                                            ],
                                                        ]
                                                    },
                                                    {
                                                        "$eq": [
                                                            {
                                                                "$toLower": (
                                                                    "$$p.v.described"
                                                                )
                                                            },
                                                            "yes",
                                                        ]
                                                    },
                                                ]
                                            },
                                        }
                                    }
                                },
                                0,
                            ]
                        },
                        {
                            "$and": [
                                {
                                    "$gt": [
                                        {
                                            "$size": {
                                                "$filter": {
                                                    "input": "$phenotype_entries",
                                                    "as": "p",
                                                    "cond": {
                                                        "$and": [
                                                            {
                                                                "$eq": [
                                                                    "$$p.v.name",
                                                                    "Abnormality of the"
                                                                    " genital system",
                                                                ]
                                                            },
                                                            {
                                                                "$eq": [
                                                                    {
                                                                        "$toLower": (
                                                                            "$$p.v."
                                                                            "described"
                                                                        )
                                                                    },
                                                                    "yes",
                                                                ]
                                                            },
                                                        ]
                                                    },
                                                }
                                            }
                                        },
                                        0,
                                    ]
                                },
                                "$any_kidney",
                            ]
                        },
                    ]
                }
            }
        },
        # 7. Define mutually exclusive flags.
        {
            "$set": {
                "MODY_only": {"$and": ["$MODY", {"$eq": ["$CAKUT", False]}]},
                "CAKUT_only": {"$and": ["$CAKUT", {"$eq": ["$MODY", False]}]},
                "CAKUT_MODY": {"$and": ["$CAKUT", "$MODY"]},
                "Other": {
                    "$and": [{"$eq": ["$MODY", False]}, {"$eq": ["$CAKUT", False]}]
                },
            }
        },
        # 8. Group across all individuals to compute cohort-level counts.
        {
            "$group": {
                "_id": None,
                "total_count": {"$sum": 1},
                "MODY_only_count": {"$sum": {"$cond": ["$MODY_only", 1, 0]}},
                "CAKUT_only_count": {"$sum": {"$cond": ["$CAKUT_only", 1, 0]}},
                "CAKUT_MODY_count": {"$sum": {"$cond": ["$CAKUT_MODY", 1, 0]}},
                "Other_count": {"$sum": {"$cond": ["$Other", 1, 0]}},
            }
        },
        {
            "$project": {
                "_id": 0,
                "total_count": 1,
                "MODY_only_count": 1,
                "CAKUT_only_count": 1,
                "CAKUT_MODY_count": 1,
                "Other_count": 1,
            }
        },
    ]

    results = await db.individuals.aggregate(pipeline).to_list(length=1)
    if results:
        return results[0]
    return {
        "total_count": 0,
        "MODY_only_count": 0,
        "CAKUT_only_count": 0,
        "CAKUT_MODY_count": 0,
        "Other_count": 0,
    }
