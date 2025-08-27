"""Variants import module with genomic annotations."""

from typing import Dict, Optional

import pandas as pd

from app.database import get_db
from app.models import (
    IndividualVariant,
    Variant,
    VariantAnnotation,
    VariantClassification,
)
from app.repositories import IndividualRepository

from .genomics import load_genomic_files
from .utils import (
    csv_url,
    format_individual_id,
    format_variant_id,
    none_if_nan,
    normalize_dataframe_columns,
    parse_date,
)


async def import_variants(
    spreadsheet_id: str,
    gid_individuals: str,
    limit: Optional[int] = None,
    skip_duplicates: bool = True,
):
    """Import variants from Google Sheets using the original logic."""
    print("[import_variants] Starting import of variants...")

    # Get the individuals sheet to extract variant data
    url = csv_url(spreadsheet_id, gid_individuals)
    print(f"[import_variants] Reading from URL: {url}")

    try:
        df = pd.read_csv(url)
        df = df.dropna(how="all")
        df = normalize_dataframe_columns(df)
        print(
            f"[import_variants] Found {len(df)} rows with "
            f"columns: {df.columns.tolist()}"
        )

        # Load genomic annotation files
        print("[import_variants] Loading genomic annotation files...")
        genomic_data = await load_genomic_files()
        annotation_map = genomic_data.get("annotation_map", {})
        cnv_annotation_map = genomic_data.get("cnv_annotation_map", {})

        # Extract unique variants from the sheet
        print("[import_variants] Extracting unique variants...")
        unique_variants = extract_unique_variants(df)
        print(f"[import_variants] Found {len(unique_variants)} unique variants")

        if limit:
            # Limit variants for testing
            limited_variants = dict(list(unique_variants.items())[:limit])
            unique_variants = limited_variants
            print(f"[import_variants] Limited to first {limit} variants for testing")

        # Import to database
        async for db_session in get_db():
            individual_repo = IndividualRepository(db_session)

            # Get individual mappings
            individuals = await individual_repo.get_multi(skip=0, limit=2000)
            individual_mapping = {ind.individual_id: ind.id for ind in individuals[0]}

            # Clear existing variants if not skipping duplicates
            if not skip_duplicates:
                from sqlalchemy import text

                await db_session.execute(
                    text(
                        "DELETE FROM individual_variants WHERE variant_id IN "
                        "(SELECT id FROM variants WHERE variant_id LIKE 'var%')"
                    )
                )
                await db_session.execute(
                    text(
                        "DELETE FROM variant_annotations WHERE variant_id IN "
                        "(SELECT id FROM variants WHERE variant_id LIKE 'var%')"
                    )
                )
                await db_session.execute(
                    text(
                        "DELETE FROM variant_classifications WHERE variant_id IN "
                        "(SELECT id FROM variants WHERE variant_id LIKE 'var%')"
                    )
                )
                await db_session.execute(
                    text("DELETE FROM variants WHERE variant_id LIKE 'var%'")
                )

            created_count = 0
            variant_id_counter = 1

            for variant_key, variant_info in unique_variants.items():
                try:
                    # Create variant ID
                    variant_id = format_variant_id(variant_id_counter)

                    # Check if variant already exists
                    if skip_duplicates:
                        from sqlalchemy import text

                        check_sql = text(
                            "SELECT id FROM variants WHERE variant_id = :variant_id "
                            "LIMIT 1"
                        )
                        result = await db_session.execute(
                            check_sql, {"variant_id": variant_id}
                        )
                        if result.scalar():
                            print(
                                f"[import_variants] Skipping existing variant: "
                                f"{variant_id}"
                            )
                            variant_id_counter += 1
                            continue

                    # Create variant
                    variant_data = variant_info["variant_data"]
                    variant_data["variant_id"] = variant_id
                    variant_data["is_current"] = True

                    variant_obj = Variant(**variant_data)
                    db_session.add(variant_obj)
                    await db_session.flush()  # Get the ID

                    # Add genomic annotations if available
                    hg38_key = variant_data.get("hg38")
                    if hg38_key:
                        if hg38_key in annotation_map:
                            annotation_data = annotation_map[hg38_key].copy()
                            annotation_data["variant_id"] = variant_obj.id
                            annotation_obj = VariantAnnotation(**annotation_data)
                            db_session.add(annotation_obj)
                        elif (
                            ("<DEL>" in hg38_key) or ("<DUP>" in hg38_key)
                        ) and hg38_key in cnv_annotation_map:
                            annotation_data = cnv_annotation_map[hg38_key].copy()
                            annotation_data["variant_id"] = variant_obj.id
                            annotation_obj = VariantAnnotation(**annotation_data)
                            db_session.add(annotation_obj)

                    # Add classifications
                    for classification_data in variant_info.get("classifications", []):
                        if classification_data.get(
                            "verdict"
                        ):  # Only add if has verdict
                            classification_data_copy = classification_data.copy()
                            classification_data_copy["variant_id"] = variant_obj.id
                            classification_obj = VariantClassification(
                                **classification_data_copy
                            )
                            db_session.add(classification_obj)

                    # Create individual-variant associations
                    for individual_id in variant_info.get("individual_ids", []):
                        if individual_id in individual_mapping:
                            individual_uuid = individual_mapping[individual_id]

                            # Get detection method and segregation for this individual
                            det_info = variant_info.get(
                                "individual_variant_info", {}
                            ).get(individual_id, {})

                            association_data = {
                                "variant_id": variant_obj.id,
                                "individual_id": individual_uuid,
                                "detection_method": det_info.get("detection_method")
                                or "Unknown",
                                "segregation": det_info.get("segregation"),
                                "is_current": True,
                            }

                            association_obj = IndividualVariant(**association_data)
                            db_session.add(association_obj)

                    created_count += 1
                    variant_id_counter += 1
                    print(f"[import_variants] Created variant: {variant_id}")

                except Exception as e:
                    print(
                        f"[import_variants] Error processing variant {variant_key}: {e}"
                    )
                    continue

            await db_session.commit()
            print(f"[import_variants] Successfully imported {created_count} variants")
            break

    except Exception as e:
        print(f"[import_variants] Error accessing Google Sheets: {e}")
        raise


def extract_unique_variants(df: pd.DataFrame) -> Dict:
    """Extract unique variants from the individuals dataframe using original logic."""
    variant_key_cols = ["VariantType", "hg19_INFO", "hg19", "hg38_INFO", "hg38"]
    unique_variants = {}

    classification_cols = [
        "verdict_classification",
        "criteria_classification",
        "comment_classification",
        "system_classification",
        "date_classification",
    ]

    for _, row in df.iterrows():
        if pd.notna(row.get("VariantType")):
            # Create variant key from genomic coordinates
            key_parts = []
            for col in variant_key_cols:
                val = none_if_nan(row.get(col))
                key_parts.append(str(val).strip() if val is not None else "")
            variant_key = "|".join(key_parts)

            if variant_key not in unique_variants:
                # Create new variant entry
                variant_data = {
                    "variant_type": none_if_nan(row.get("VariantType")),
                    "hg19": none_if_nan(row.get("hg19")),
                    "hg38": none_if_nan(row.get("hg38")),
                    "hg19_info": none_if_nan(row.get("hg19_INFO")),
                    "hg38_info": none_if_nan(row.get("hg38_INFO")),
                }

                unique_variants[variant_key] = {
                    "variant_data": variant_data,
                    "individual_ids": [],
                    "classifications": [],
                    "individual_variant_info": {},
                }

            # Add individual to this variant
            individual_id = format_individual_id(row.get("individual_id"))
            if (
                individual_id
                and individual_id not in unique_variants[variant_key]["individual_ids"]
            ):
                unique_variants[variant_key]["individual_ids"].append(individual_id)

                # Store individual-specific variant info
                det_method = none_if_nan(
                    row.get("DetecionMethod") or row.get("DetectionMethod")
                )
                segregation = none_if_nan(row.get("Segregation"))

                unique_variants[variant_key]["individual_variant_info"][
                    individual_id
                ] = {"detection_method": det_method, "segregation": segregation}

            # Add classification if present
            if any(
                col in row and pd.notna(row.get(col)) for col in classification_cols
            ):
                classification = {
                    "verdict": none_if_nan(row.get("verdict_classification")),
                    "criteria": none_if_nan(row.get("criteria_classification")),
                    "comment": none_if_nan(row.get("comment_classification")),
                    "system": none_if_nan(row.get("system_classification")) or "ACMG",
                    "classification_date": parse_date(row.get("date_classification")),
                }

                # Avoid duplicate classifications
                if (
                    classification
                    not in unique_variants[variant_key]["classifications"]
                ):
                    unique_variants[variant_key]["classifications"].append(
                        classification
                    )

    return unique_variants
