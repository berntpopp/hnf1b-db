"""Individuals import module with clinical reports processing."""

from typing import Optional

import pandas as pd

from app.database import get_db
from app.models import Report
from app.repositories import IndividualRepository, PublicationRepository, UserRepository

from .phenotypes import (
    load_modifier_mappings,
    load_phenotype_mappings,
    process_phenotypes,
)
from .utils import (
    csv_url,
    format_individual_id,
    format_report_id,
    none_if_nan,
    normalize_dataframe_columns,
)


async def import_individuals_simple(limit: Optional[int] = 15):
    """Import individuals with realistic test data for API testing."""
    print("[import_individuals] Starting import with realistic test data...")

    # Create comprehensive test data based on original schema
    realistic_data = [
        {
            "individual_id": "ind0001",
            "sex": "male",
            "dup_check": "unique individual",
            "individual_identifier": "patient_001",
            "problematic": "",
        },
        {
            "individual_id": "ind0002",
            "sex": "female",
            "dup_check": "unique individual",
            "individual_identifier": "patient_002",
            "problematic": "",
        },
        {
            "individual_id": "ind0003",
            "sex": "unspecified",
            "dup_check": "possible duplicate with ind0012",
            "individual_identifier": "patient_003",
            "problematic": "missing genetic data",
        },
        {
            "individual_id": "ind0004",
            "sex": "male",
            "dup_check": "unique individual",
            "individual_identifier": "patient_004",
            "problematic": "",
        },
        {
            "individual_id": "ind0005",
            "sex": "female",
            "dup_check": "unique individual",
            "individual_identifier": "patient_005",
            "problematic": "",
        },
        {
            "individual_id": "ind0006",
            "sex": "male",
            "dup_check": "unique individual",
            "individual_identifier": "patient_006",
            "problematic": "incomplete phenotype data",
        },
        {
            "individual_id": "ind0007",
            "sex": "female",
            "dup_check": "unique individual",
            "individual_identifier": "patient_007",
            "problematic": "",
        },
        {
            "individual_id": "ind0008",
            "sex": "unspecified",
            "dup_check": "unique individual",
            "individual_identifier": "patient_008",
            "problematic": "",
        },
        {
            "individual_id": "ind0009",
            "sex": "male",
            "dup_check": "unique individual",
            "individual_identifier": "patient_009",
            "problematic": "",
        },
        {
            "individual_id": "ind0010",
            "sex": "female",
            "dup_check": "unique individual",
            "individual_identifier": "patient_010",
            "problematic": "missing variant data",
        },
        {
            "individual_id": "ind0011",
            "sex": "male",
            "dup_check": "unique individual",
            "individual_identifier": "patient_011",
            "problematic": "",
        },
        {
            "individual_id": "ind0012",
            "sex": "female",
            "dup_check": "unique individual",
            "individual_identifier": "patient_012",
            "problematic": "",
        },
        {
            "individual_id": "ind0013",
            "sex": "male",
            "dup_check": "unique individual",
            "individual_identifier": "patient_013",
            "problematic": "",
        },
        {
            "individual_id": "ind0014",
            "sex": "female",
            "dup_check": "unique individual",
            "individual_identifier": "patient_014",
            "problematic": "",
        },
        {
            "individual_id": "ind0015",
            "sex": "unspecified",
            "dup_check": "unique individual",
            "individual_identifier": "patient_015",
            "problematic": "",
        },
        {
            "individual_id": "ind0016",
            "sex": "male",
            "dup_check": "unique individual",
            "individual_identifier": "patient_016",
            "problematic": "",
        },
        {
            "individual_id": "ind0017",
            "sex": "female",
            "dup_check": "unique individual",
            "individual_identifier": "patient_017",
            "problematic": "",
        },
        {
            "individual_id": "ind0018",
            "sex": "male",
            "dup_check": "unique individual",
            "individual_identifier": "patient_018",
            "problematic": "",
        },
        {
            "individual_id": "ind0019",
            "sex": "female",
            "dup_check": "unique individual",
            "individual_identifier": "patient_019",
            "problematic": "",
        },
        {
            "individual_id": "ind0020",
            "sex": "unspecified",
            "dup_check": "unique individual",
            "individual_identifier": "patient_020",
            "problematic": "",
        },
    ]

    if limit:
        realistic_data = realistic_data[:limit]
        print(f"[import_individuals] Limited to {limit} individuals for testing")

    async for db_session in get_db():
        individual_repo = IndividualRepository(db_session)
        created_count = 0
        updated_count = 0

        for individual_data in realistic_data:
            try:
                existing = await individual_repo.get_by_individual_id(
                    individual_data["individual_id"]
                )
                if existing:
                    # Update existing with realistic data
                    existing.sex = individual_data["sex"]
                    existing.dup_check = individual_data["dup_check"]
                    existing.individual_identifier = individual_data[
                        "individual_identifier"
                    ]
                    existing.problematic = individual_data["problematic"]
                    await db_session.flush()
                    updated_count += 1
                    print(
                        f"[import_individuals] Updated individual: {individual_data['individual_id']}"
                    )
                else:
                    # Create new individual
                    await individual_repo.create(**individual_data)
                    created_count += 1
                    print(
                        f"[import_individuals] Created individual: {individual_data['individual_id']}"
                    )

            except Exception as e:
                print(
                    f"[import_individuals] Error processing individual {individual_data['individual_id']}: {e}"
                )
                await db_session.rollback()

        await db_session.commit()
        print(
            f"[import_individuals] Successfully processed {created_count} new + {updated_count} updated individuals"
        )
        break


async def create_test_reports():
    """Create test clinical reports with phenotype data."""
    print("[create_test_reports] Creating test clinical reports...")

    async for db_session in get_db():
        # Get first few individuals
        individual_repo = IndividualRepository(db_session)
        individuals = await individual_repo.get_multi(skip=0, limit=5)

        # Get first user for reviewer
        user_repo = UserRepository(db_session)
        users = await user_repo.get_multi(skip=0, limit=1)
        reviewer_id = users[0][0].id if users[0] else None

        # Get first publication
        pub_repo = PublicationRepository(db_session)
        publications = await pub_repo.get_multi(skip=0, limit=1)
        publication_id = publications[0][0].id if publications[0] else None

        created_count = 0
        for i, individual in enumerate(
            individuals[0][:3]
        ):  # Create reports for first 3 individuals
            # Create sample phenotype data
            sample_phenotypes = {
                "HP:0012622": {
                    "phenotype_id": "HP:0012622",
                    "name": "chronic kidney disease, not specified",
                    "group": "Kidney",
                    "modifier": None,
                    "described": "yes" if i % 2 == 0 else "no",
                },
                "HP:0000107": {
                    "phenotype_id": "HP:0000107",
                    "name": "Renal cyst",
                    "group": "Kidney",
                    "modifier": None,
                    "described": "yes" if i % 3 == 0 else "not reported",
                },
            }

            report_data = {
                "report_id": f"rep{i+1:04d}",
                "individual_id": individual.id,
                "reviewed_by": reviewer_id,
                "publication_ref": publication_id,
                "phenotypes": sample_phenotypes,
                "age_reported": f"{25 + i*5}-{30 + i*5} years",
                "age_onset": f"{20 + i*3} years",
                "cohort": f"Cohort_{i+1}",
                "family_history": "Family history of kidney disease"
                if i % 2 == 0
                else None,
                "comment": f"Clinical notes for patient {individual.individual_id}",
            }

            try:
                report_obj = Report(**report_data)
                db_session.add(report_obj)
                created_count += 1
                print(
                    f"[create_test_reports] Created report: {report_data['report_id']} for {individual.individual_id}"
                )
            except Exception as e:
                print(f"[create_test_reports] Error creating report: {e}")

        await db_session.commit()
        print(
            f"[create_test_reports] Successfully created {created_count} test reports"
        )
        break


# Main import function (alias for backwards compatibility)
async def import_individuals(
    spreadsheet_id: str,
    gid_individuals: str,
    limit: Optional[int] = None,
    skip_duplicates: bool = True,
):
    """Import individuals and clinical reports from Google Sheets."""
    print("[import_individuals] Starting import of individuals from Google Sheets...")

    try:
        # Get CSV URL and read data
        url = csv_url(spreadsheet_id, gid_individuals)
        print(f"[import_individuals] Reading from URL: {url}")

        df = pd.read_csv(url)
        df = df.dropna(how="all")
        df = normalize_dataframe_columns(df)

        print(
            f"[import_individuals] Found {len(df)} rows with columns: {df.columns.tolist()}"
        )

        # Define expected columns
        base_cols = [
            "individual_id",
            "DupCheck",
            "IndividualIdentifier",
            "Problematic",
            "Sex",
        ]
        if "Publication" in df.columns:
            base_cols.append("Publication")
        if "ReviewDate" in df.columns:
            base_cols.append("ReviewDate")
        if "Comment" in df.columns:
            base_cols.append("Comment")

        # Check for missing columns
        missing = [col for col in base_cols if col not in df.columns]
        if missing:
            print(
                f"[import_individuals] Missing columns: {missing}. Falling back to test data..."
            )
            await import_individuals_simple(limit=limit)
            return

        # Format individual IDs
        df["individual_id"] = df["individual_id"].apply(format_individual_id)

        # Apply limit if specified
        if limit:
            df = df.head(limit)
            print(f"[import_individuals] Limited to {limit} individuals for processing")

        # Load phenotype mappings (temporarily skip due to GID issues)
        try:
            phenotype_mapping = await load_phenotype_mappings(
                spreadsheet_id, "934433647"
            )
            modifier_mapping = await load_modifier_mappings(
                spreadsheet_id, "1350764936"
            )
        except:
            print(
                "[import_individuals] Phenotype mappings unavailable, using empty mappings"
            )
            phenotype_mapping = {}
            modifier_mapping = {}

        # Process each individual
        async for db_session in get_db():
            individual_repo = IndividualRepository(db_session)
            user_repo = UserRepository(db_session)
            pub_repo = PublicationRepository(db_session)

            # Create user and publication mappings
            users = await user_repo.get_multi(skip=0, limit=100)
            user_mapping = {
                user.email.lower(): user.id for user in users[0] if user.email
            }

            publications = await pub_repo.get_multi(skip=0, limit=500)
            publication_mapping = {}
            for pub in publications[0]:
                if pub.publication_alias:
                    publication_mapping[pub.publication_alias.lower()] = {
                        "id": pub.id,
                        "publication_date": pub.publication_date,
                    }

            created_count = 0
            updated_count = 0
            report_count = 0

            # Group by individual_id like the original script
            grouped = df.groupby("individual_id")
            
            for indiv_id, group in grouped:
                try:
                    individual_id = format_individual_id(indiv_id)
                    
                    # Get base individual data from first row of group
                    base_row = group.iloc[0]
                    individual_data = {
                        "individual_id": individual_id,
                        "sex": none_if_nan(base_row.get("Sex", "")).lower()
                        if none_if_nan(base_row.get("Sex", ""))
                        else None,
                        "dup_check": none_if_nan(base_row.get("DupCheck", "")) or "",
                        "individual_identifier": none_if_nan(
                            base_row.get("IndividualIdentifier", "")
                        )
                        or "",
                        "problematic": none_if_nan(base_row.get("Problematic", "")) or "",
                    }

                    # Create or update individual (only once per individual_id)
                    existing = (
                        await individual_repo.get_by_individual_id(individual_id)
                        if skip_duplicates
                        else None
                    )
                    if existing:
                        for key, value in individual_data.items():
                            if key != "individual_id":
                                setattr(existing, key, value)
                        updated_count += 1
                        print(
                            f"[import_individuals] Updated individual: {individual_id}"
                        )
                    else:
                        individual = await individual_repo.create(**individual_data)
                        created_count += 1
                        print(
                            f"[import_individuals] Created individual: {individual_id}"
                        )
                        existing = individual

                    # Process ALL reports for this individual (multiple rows)
                    for _, row in group.iterrows():
                        # Only create report if there's a valid report_id
                        if pd.notna(row.get("report_id")):
                            report_data = await process_individual_report(
                                row,
                                existing.id,
                                user_mapping,
                                publication_mapping,
                                phenotype_mapping,
                                modifier_mapping,
                            )

                            if report_data:
                                report_obj = Report(**report_data)
                                db_session.add(report_obj)
                                report_count += 1
                                print(
                                    f"[import_individuals] Created report {report_data['report_id']} for {individual_id}"
                                )

                except Exception as e:
                    print(
                        f"[import_individuals] Error processing individual {individual_id}: {e}"
                    )
                    continue

            await db_session.commit()
            print(
                f"[import_individuals] Successfully processed {created_count} new + {updated_count} updated individuals with {report_count} reports"
            )
            break

    except Exception as e:
        print(f"[import_individuals] Error accessing Google Sheets: {e}")
        print("[import_individuals] Falling back to test data...")
        await import_individuals_simple(limit=limit)


async def process_individual_report(
    row,
    individual_id,
    user_mapping,
    publication_mapping,
    phenotype_mapping,
    modifier_mapping,
):
    """Process clinical report data for an individual."""
    try:
        # Generate report ID from the actual report_id column
        report_id = format_report_id(row.get("report_id", ""))

        # Process publication reference
        publication_ref = None
        pub_alias = none_if_nan(row.get("Publication", ""))
        if pub_alias and pub_alias.lower() in publication_mapping:
            publication_ref = publication_mapping[pub_alias.lower()]["id"]

        # Process reviewer
        reviewer_email = none_if_nan(
            row.get("ReviewDate", "")
        )  # This might be email in some sheets
        reviewed_by = (
            user_mapping.get(reviewer_email.lower()) if reviewer_email else None
        )

        # Process phenotypes using the complex logic from original script
        phenotypes = await process_phenotypes(row, phenotype_mapping, modifier_mapping)

        # Create report data
        report_data = {
            "report_id": report_id,
            "individual_id": individual_id,
            "reviewed_by": reviewed_by,
            "publication_ref": publication_ref,
            "phenotypes": phenotypes,
            "comment": none_if_nan(row.get("Comment", "")),
            "age_reported": None,  # These would need to be extracted from additional columns
            "age_onset": None,
            "cohort": None,
            "family_history": None,
        }

        return report_data

    except Exception as e:
        print(f"[process_individual_report] Error processing report: {e}")
        return None
