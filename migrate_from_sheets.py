# migrate_from_sheets.py
import asyncio
import math
import re
import pandas as pd
from dateutil import parser as date_parser  # requires: pip install python-dateutil
from app.database import db
from app.config import settings
from app.models import User, Individual, Publication, Report, Variant

# The spreadsheet ID (extracted from your URL)
SPREADSHEET_ID = "1jE4-HmyAh1FUK6Ph7AuHt2UDVW2mTINTWXBtAWqhVSw"

# GIDs for each sheet:
GID_REVIEWERS = "1321366018"      # Reviewers sheet
GID_INDIVIDUALS = "0"             # Individuals sheet
GID_PUBLICATIONS = "1670256162"   # Publications sheet

# GIDs for additional mapping sheets:
PHENOTYPE_GID = "1119329208"       # Phenotype sheet
MODIFIER_GID   = "1741928801"       # Phenotype Modifier sheet

# ---------------------------------------------------
# Helper: Convert NA (or NaN) values to None.
def none_if_nan(v):
    if pd.isna(v):
        return None
    if isinstance(v, str) and v.strip().upper() == "NA":
        return None
    return v

# ---------------------------------------------------
def csv_url(spreadsheet_id: str, gid: str) -> str:
    url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/export?format=csv&gid={gid}"
    print(f"[csv_url] Built URL: {url}")
    return url

# ---------------------------------------------------
async def load_phenotype_mappings():
    """
    Load the phenotype mapping from the Phenotype sheet.
    Returns a dict mapping phenotype_category (lowercase) to a dict
    with keys "phenotype_id" and "name".
    """
    url = csv_url(SPREADSHEET_ID, PHENOTYPE_GID)
    df = pd.read_csv(url)
    df.columns = [col.strip() for col in df.columns if isinstance(col, str)]
    mapping = {}
    # For each row, use the 'phenotype_category' (lowercase) as key.
    for idx, row in df.iterrows():
        cat = str(row["phenotype_category"]).strip().lower()
        # If there are multiple rows for the same category, you may choose the first one.
        if cat not in mapping:
            mapping[cat] = {
                "phenotype_id": row["phenotype_id"],
                "name": row["phenotype_name"]
            }
    print(f"[load_phenotype_mappings] Loaded phenotype mapping for {len(mapping)} categories.")
    return mapping

# ---------------------------------------------------
async def load_modifier_mappings():
    """
    Load the phenotype modifier mapping from the Modifier sheet.
    Returns a dict mapping standardized modifier strings (lowercase)
    and their synonyms to a dict with keys "modifier_id" and "name".
    """
    url = csv_url(SPREADSHEET_ID, MODIFIER_GID)
    df = pd.read_csv(url)
    df.columns = [col.strip() for col in df.columns if isinstance(col, str)]
    mapping = {}
    for idx, row in df.iterrows():
        key = str(row["modifier_name"]).strip().lower()
        mapping[key] = {"modifier_id": row["modifier_id"], "name": row["modifier_name"].strip()}
        # If there are synonyms (comma-separated), add them as keys as well.
        if pd.notna(row.get("modifier_synonyms")):
            synonyms = row["modifier_synonyms"].split(",")
            for syn in synonyms:
                mapping[syn.strip().lower()] = {"modifier_id": row["modifier_id"], "name": row["modifier_name"].strip()}
    print(f"[load_modifier_mappings] Loaded modifier mapping for {len(mapping)} keys.")
    return mapping

# ---------------------------------------------------
async def import_users():
    print("[import_users] Starting import of reviewers/users.")
    url = csv_url(SPREADSHEET_ID, GID_REVIEWERS)
    print(f"[import_users] Fetching reviewers from URL: {url}")
    reviewers_df = pd.read_csv(url)
    print(f"[import_users] Raw columns: {reviewers_df.columns.tolist()}")

    reviewers_df = reviewers_df.dropna(how="all")
    reviewers_df.columns = [col.strip() for col in reviewers_df.columns if isinstance(col, str)]
    print(f"[import_users] Normalized columns: {reviewers_df.columns.tolist()}")

    expected_columns = [
        'user_id', 'user_name', 'password', 'email',
        'user_role', 'first_name', 'family_name', 'orcid'
    ]
    missing = [col for col in expected_columns if col not in reviewers_df.columns]
    if missing:
        raise KeyError(f"[import_users] Missing expected columns in Reviewers sheet: {missing}\n"
                       f"Normalized columns are: {reviewers_df.columns.tolist()}")

    users_df = reviewers_df[expected_columns].sort_values('user_id')
    validated_users = []
    for idx, row in users_df.iterrows():
        try:
            user = User(**row)
            validated_users.append(user.dict(by_alias=True, exclude_none=True))
        except Exception as e:
            print(f"[import_users] Validation error in row {idx}: {e}")
    print(f"[import_users] Inserting {len(validated_users)} valid users into database...")
    await db.users.delete_many({})
    if validated_users:
        await db.users.insert_many(validated_users)
    print(f"[import_users] Imported {len(validated_users)} users.")

# ---------------------------------------------------
async def import_individuals():
    print("[import_individuals] Starting import of individuals.")
    url = csv_url(SPREADSHEET_ID, GID_INDIVIDUALS)
    print(f"[import_individuals] Fetching individuals from URL: {url}")
    individuals_df = pd.read_csv(url)
    print(f"[import_individuals] Raw columns: {individuals_df.columns.tolist()}")

    individuals_df = individuals_df.dropna(how="all")
    # Limit to only the required columns:
    required_columns = [
        'individual_id', 'DupCheck', 'IndividualIdentifier', 
        'Problematic', 'Cohort', 'Sex', 'AgeOnset', 'AgeReported'
    ]
    individuals_df = individuals_df[required_columns]
    # Rename "Sex" to "sex" so it matches our model.
    if "Sex" in individuals_df.columns:
        individuals_df = individuals_df.rename(columns={"Sex": "sex"})
    print(f"[import_individuals] Normalized columns: {individuals_df.columns.tolist()}")

    validated_individuals = []
    for idx, row in individuals_df.iterrows():
        try:
            indiv = Individual(**row)
            validated_individuals.append(indiv.dict(by_alias=True, exclude_none=True))
        except Exception as e:
            print(f"[import_individuals] Validation error in row {idx}: {e}")
    print(f"[import_individuals] Inserting {len(validated_individuals)} valid individuals into database...")
    await db.individuals.delete_many({})
    if validated_individuals:
        await db.individuals.insert_many(validated_individuals)
    print(f"[import_individuals] Imported {len(validated_individuals)} individuals.")

# ---------------------------------------------------
async def import_publications():
    print("[import_publications] Starting import of publications.")
    url = csv_url(SPREADSHEET_ID, GID_PUBLICATIONS)
    print(f"[import_publications] Fetching publications from URL: {url}")
    publications_df = pd.read_csv(url)
    print(f"[import_publications] Raw columns: {publications_df.columns.tolist()}")

    publications_df = publications_df.dropna(how="all")
    print(f"[import_publications] Normalized columns: {publications_df.columns.tolist()}")

    # Build a mapping from reviewer email to user_id.
    user_mapping = {}
    user_docs = await db.users.find({}, {"email": 1, "user_id": 1}).to_list(length=None)
    for user_doc in user_docs:
        email = user_doc["email"].strip().lower()
        user_mapping[email] = user_doc["user_id"]
    print(f"[import_publications] User mapping: {user_mapping}")

    validated_publications = []
    for idx, row in publications_df.iterrows():
        try:
            if "Assigne" in row:
                assignee_email = row["Assigne"]
                if pd.notna(assignee_email):
                    row["assignee"] = user_mapping.get(assignee_email.strip().lower())
                row = row.drop(labels=["Assigne"])
            pub = Publication(**row)
            validated_publications.append(pub.dict(by_alias=True, exclude_none=True))
        except Exception as e:
            print(f"[import_publications] Validation error in row {idx}: {e}")
    print(f"[import_publications] Inserting {len(validated_publications)} valid publications into database...")
    await db.publications.delete_many({})
    if validated_publications:
        await db.publications.insert_many(validated_publications)
    print(f"[import_publications] Imported {len(validated_publications)} publications.")

# ---------------------------------------------------
async def import_reports():
    print("[import_reports] Starting import of reports.")
    # For now, we omit any date fields.
    url = csv_url(SPREADSHEET_ID, GID_INDIVIDUALS)
    print(f"[import_reports] Fetching report data from URL: {url}")
    df = pd.read_csv(url)
    print(f"[import_reports] Raw columns: {df.columns.tolist()}")
    df = df.dropna(how="all")
    df.columns = [col.strip() for col in df.columns if isinstance(col, str)]
    print(f"[import_reports] Normalized columns: {df.columns.tolist()}")

    # Build a mapping from reviewer email to user_id.
    user_mapping = {}
    user_docs = await db.users.find({}, {"email": 1, "user_id": 1}).to_list(length=None)
    for user_doc in user_docs:
        email = user_doc["email"].strip().lower()
        user_mapping[email] = user_doc["user_id"]
    print(f"[import_reports] User mapping: {user_mapping}")

    # Load phenotype and modifier mappings.
    phenotype_mapping = await load_phenotype_mappings()
    modifier_mapping = await load_modifier_mappings()

    # Define the list of phenotype columns to integrate.
    phenotype_cols = [
        'RenalInsufficancy', 'Hyperechogenicity', 'RenalCysts', 'MulticysticDysplasticKidney',
        'KidneyBiopsy', 'RenalHypoplasia', 'SolitaryKidney', 'UrinaryTractMalformation',
        'GenitalTractAbnormality', 'AntenatalRenalAbnormalities', 'Hypomagnesemia',
        'Hypokalemia', 'Hyperuricemia', 'Gout', 'MODY', 'PancreaticHypoplasia',
        'ExocrinePancreaticInsufficiency', 'Hyperparathyroidism', 'NeurodevelopmentalDisorder',
        'MentalDisease', 'Seizures', 'BrainAbnormality', 'PrematureBirth',
        'CongenitalCardiacAnomalies', 'EyeAbnormality', 'ShortStature',
        'MusculoskeletalFeatures', 'DysmorphicFeatures', 'ElevatedHepaticTransaminase',
        'AbnormalLiverPhysiology'
    ]

    validated_reports = []
    if 'report_id' not in df.columns:
        print("[import_reports] No 'report_id' column found; skipping report import.")
    else:
        report_rows = df[df['report_id'].notna()]
        for idx, row in report_rows.iterrows():
            try:
                report_data = {
                    'report_id': row['report_id'],
                    'individual_id': row['individual_id']
                    # Date fields are omitted for now.
                }
                review_by_email = row.get('ReviewBy')
                if pd.notna(review_by_email):
                    report_data['reviewed_by'] = user_mapping.get(review_by_email.strip().lower())
                else:
                    report_data['reviewed_by'] = None
                
                # Build phenotypes as an array of objects.
                phenotypes_list = []
                for col in phenotype_cols:
                    if col in df.columns:
                        raw_val = row.get(col)
                        # Convert value to a string (or empty if missing)
                        reported_val = str(raw_val).strip() if pd.notna(raw_val) else ""
                        # Lookup standardized phenotype info by using the column name (lowercased)
                        pheno_key = col.strip().lower()
                        std_info = phenotype_mapping.get(pheno_key, {"phenotype_id": col, "name": col})
                        # Determine modifier using the reported value.
                        mod_key = reported_val.lower() if reported_val != "" else ""
                        mod_info = modifier_mapping.get(mod_key) if mod_key != "" else None
                        modifier_std = mod_info["name"] if mod_info else reported_val
                        # Set described flag: if reported value is non‑empty and not "no"/"not reported", then True.
                        described = False if reported_val in ["", "no", "not reported"] else True
                        pheno_obj = {
                            "phenotype_id": std_info["phenotype_id"],
                            "name": std_info["name"],
                            "modifier": modifier_std,
                            "modifier_id": mod_info["modifier_id"] if mod_info else None,
                            "described": described
                        }
                        phenotypes_list.append(pheno_obj)
                report_data['phenotypes'] = phenotypes_list
                rep = Report(**report_data)
                validated_reports.append(rep.dict(by_alias=True, exclude_none=True))
            except Exception as e:
                print(f"[import_reports] Validation error in row {idx}: {e}")
    print(f"[import_reports] Inserting {len(validated_reports)} valid reports into database...")
    await db.reports.delete_many({})
    if validated_reports:
        await db.reports.insert_many(validated_reports)
    print(f"[import_reports] Imported {len(validated_reports)} reports.")

# ---------------------------------------------------
async def import_variants():
    print("[import_variants] Starting import of variants.")
    url = csv_url(SPREADSHEET_ID, GID_INDIVIDUALS)
    print(f"[import_variants] Fetching variant data from URL: {url}")
    df = pd.read_csv(url)
    print(f"[import_variants] Raw columns: {df.columns.tolist()}")
    df = df.dropna(how="all")
    df.columns = [col.strip() for col in df.columns if isinstance(col, str)]
    print(f"[import_variants] Normalized columns: {df.columns.tolist()}")

    validated_variants = []
    if 'VariantType' not in df.columns:
        print("[import_variants] No 'VariantType' column found; skipping variant import.")
    else:
        variant_rows = df[df['VariantType'].notna()]
        variant_id_counter = 1
        for idx, row in variant_rows.iterrows():
            try:
                variant_data = {
                    'variant_id': variant_id_counter,
                    'individual_id': row['individual_id'],
                    'is_current': True,
                    'variant_type': row.get('VariantType'),
                    'variant_reported': row.get('VariantReported'),
                    'ID': none_if_nan(row.get('ID')),
                    'hg19_INFO': none_if_nan(row.get('hg19_INFO')),
                    'hg19': none_if_nan(row.get('hg19')),
                    'hg38_INFO': none_if_nan(row.get('hg38_INFO')),
                    'hg38': none_if_nan(row.get('hg38'))
                }
                # Process Varsome: if present and not "NA", attempt to parse into transcript, c_dot, and p_dot.
                varsome_val = none_if_nan(row.get('Varsome'))
                if pd.notna(varsome_val):
                    variant_data['varsome'] = str(varsome_val)
                    pattern = r"^[^(]+\(([^)]+)\):([^ ]+)\s+(\(p\..+\))"
                    m = re.match(pattern, str(varsome_val))
                    if m:
                        variant_data['transcript'] = m.group(1)
                        variant_data['c_dot'] = m.group(2)
                        variant_data['p_dot'] = m.group(3)
                    else:
                        variant_data['transcript'] = str(varsome_val)
                variant_data['detection_method'] = none_if_nan(row.get('DetecionMethod'))
                variant_data['segregation'] = none_if_nan(row.get('Segregation'))
                
                var = Variant(**variant_data)
                validated_variants.append(var.dict(by_alias=True, exclude_none=True))
                variant_id_counter += 1
            except Exception as e:
                print(f"[import_variants] Validation error in row {idx}: {e}")
    print(f"[import_variants] Inserting {len(validated_variants)} valid variants into database...")
    await db.variants.delete_many({})
    if validated_variants:
        await db.variants.insert_many(validated_variants)
    print(f"[import_variants] Imported {len(validated_variants)} variants.")

# ---------------------------------------------------
async def main():
    print("[main] Starting migration process...")
    try:
        await import_users()
    except Exception as e:
        print(f"[main] Error during import_users: {e}")
    try:
        await import_individuals()
    except Exception as e:
        print(f"[main] Error during import_individuals: {e}")
    try:
        await import_publications()
    except Exception as e:
        print(f"[main] Error during import_publications: {e}")
    try:
        await import_reports()
    except Exception as e:
        print(f"[main] Error during import_reports: {e}")
    try:
        await import_variants()
    except Exception as e:
        print(f"[main] Error during import_variants: {e}")
    print("[main] Migration process complete.")

if __name__ == "__main__":
    asyncio.run(main())
