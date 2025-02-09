import asyncio
import math
import re
import pandas as pd
from dateutil import parser as date_parser  # requires: pip install python-dateutil
from app.database import db
from app.config import settings
from app.models import User, Individual, Publication, Report, Variant

SPREADSHEET_ID = "1jE4-HmyAh1FUK6Ph7AuHt2UDVW2mTINTWXBtAWqhVSw"

# GIDs for each sheet:
GID_REVIEWERS = "1321366018"      # Reviewers sheet
GID_INDIVIDUALS = "0"             # Individuals sheet (contains both individual and report data)
GID_PUBLICATIONS = "1670256162"   # Publications sheet

# GIDs for additional mapping sheets:
PHENOTYPE_GID = "1119329208"       # Phenotype sheet
MODIFIER_GID   = "1741928801"      # Modifier sheet

# ---------------------------------------------------
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
    Returns a dict mapping the lowercased phenotype category to a dict with keys:
      "phenotype_id" and "name".
    """
    url = csv_url(SPREADSHEET_ID, PHENOTYPE_GID)
    df = pd.read_csv(url)
    df.columns = [col.strip() for col in df.columns if isinstance(col, str)]
    mapping = {}
    for idx, row in df.iterrows():
        key = str(row["phenotype_category"]).strip().lower()
        mapping[key] = {
            "phenotype_id": row["phenotype_id"],
            "name": row["phenotype_name"]
        }
    print(f"[load_phenotype_mappings] Loaded mapping for {len(mapping)} phenotype categories.")
    return mapping

# ---------------------------------------------------
async def load_modifier_mappings():
    """
    Load the modifier mapping from the Modifier sheet.
    Returns a dict mapping standardized modifier strings (and their synonyms) to a dict with keys:
      "modifier_id" and "name".
    """
    url = csv_url(SPREADSHEET_ID, MODIFIER_GID)
    df = pd.read_csv(url)
    df.columns = [col.strip() for col in df.columns if isinstance(col, str)]
    mapping = {}
    for idx, row in df.iterrows():
        key = str(row["modifier_name"]).strip().lower()
        mapping[key] = {"modifier_id": row["modifier_id"], "name": row["modifier_name"].strip()}
        if pd.notna(row.get("modifier_synonyms")):
            synonyms = row["modifier_synonyms"].split(",")
            for syn in synonyms:
                mapping[syn.strip().lower()] = {"modifier_id": row["modifier_id"], "name": row["modifier_name"].strip()}
    print(f"[load_modifier_mappings] Loaded mapping for {len(mapping)} modifier keys.")
    return mapping

# ---------------------------------------------------
async def import_users():
    print("[import_users] Starting import of reviewers/users.")
    url = csv_url(SPREADSHEET_ID, GID_REVIEWERS)
    reviewers_df = pd.read_csv(url)
    reviewers_df = reviewers_df.dropna(how="all")
    reviewers_df.columns = [col.strip() for col in reviewers_df.columns if isinstance(col, str)]
    expected_columns = [
        'user_id', 'user_name', 'password', 'email',
        'user_role', 'first_name', 'family_name', 'orcid'
    ]
    missing = [col for col in expected_columns if col not in reviewers_df.columns]
    if missing:
        raise KeyError(f"[import_users] Missing expected columns in Reviewers sheet: {missing}")
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
async def import_individuals_with_reports():
    print("[import_individuals] Starting import of individuals with embedded reports.")
    url = csv_url(SPREADSHEET_ID, GID_INDIVIDUALS)
    df = pd.read_csv(url)
    df = df.dropna(how="all")
    df.columns = [col.strip() for col in df.columns if isinstance(col, str)]
    print(f"[import_individuals] Normalized columns: {df.columns.tolist()}")

    # Base individual columns from the sheet.
    base_cols = [
        'individual_id', 'DupCheck', 'IndividualIdentifier', 
        'Problematic', 'Cohort', 'Sex', 'AgeOnset', 'AgeReported'
    ]
    # Rename "Sex" to "sex"
    if "Sex" in df.columns:
        df = df.rename(columns={"Sex": "sex"})

    # Report-specific columns: we assume that if a row has a report_id, it holds report info.
    # (For this example we use only 'report_id' and 'ReviewBy')
    report_cols = ['report_id', 'ReviewBy']

    # Define phenotype columns to integrate.
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

    # Build a mapping from reviewer email to user_id.
    user_mapping = {}
    user_docs = await db.users.find({}, {"email": 1, "user_id": 1}).to_list(length=None)
    for user_doc in user_docs:
        email = user_doc["email"].strip().lower()
        user_mapping[email] = user_doc["user_id"]

    # Load external phenotype and modifier mappings.
    phenotype_mapping = await load_phenotype_mappings()
    modifier_mapping = await load_modifier_mappings()

    # Group rows by individual_id.
    grouped = df.groupby('individual_id')
    validated_individuals = []
    for indiv_id, group in grouped:
        base_data = group.iloc[0][base_cols].to_dict()
        reports = []
        for idx, row in group.iterrows():
            if pd.notna(row.get('report_id')):
                report_data = {'report_id': row['report_id']}
                review_by_email = row.get('ReviewBy')
                if pd.notna(review_by_email):
                    report_data['reviewed_by'] = user_mapping.get(review_by_email.strip().lower())
                else:
                    report_data['reviewed_by'] = None

                # Build phenotypes as a dictionary mapping standardized HPO term to phenotype data.
                phenotypes_obj = {}
                for col in phenotype_cols:
                    # Always include an entry for each phenotype column.
                    raw_val = row.get(col, "")
                    reported_val = str(raw_val).strip() if pd.notna(raw_val) else ""
                    # Use the lowercased column name as key to lookup standardized info.
                    pheno_key = col.strip().lower()
                    std_info = phenotype_mapping.get(pheno_key, {"phenotype_id": col, "name": col})
                    mod_key = reported_val.lower()
                    mod_info = modifier_mapping.get(mod_key) if mod_key else None
                    modifier_std = mod_info["name"] if mod_info else reported_val
                    # If reported value is empty, "no", or "not reported", set described=False.
                    described = False if reported_val in ["", "no", "not reported"] else True
                    phenotypes_obj[std_info["phenotype_id"]] = {
                        "phenotype_id": std_info["phenotype_id"],
                        "name": std_info["name"],
                        "modifier": modifier_std,
                        "modifier_id": mod_info["modifier_id"] if mod_info else None,
                        "described": described
                    }
                report_data['phenotypes'] = phenotypes_obj
                reports.append(report_data)
        base_data['reports'] = reports
        try:
            indiv = Individual(**base_data)
            validated_individuals.append(indiv.dict(by_alias=True, exclude_none=True))
        except Exception as e:
            print(f"[import_individuals] Validation error for individual {indiv_id}: {e}")
    print(f"[import_individuals] Inserting {len(validated_individuals)} valid individuals with embedded reports into database...")
    await db.individuals.delete_many({})
    if validated_individuals:
        await db.individuals.insert_many(validated_individuals)
    print(f"[import_individuals] Imported {len(validated_individuals)} individuals with embedded reports.")

# ---------------------------------------------------
async def import_publications():
    print("[import_publications] Starting import of publications.")
    url = csv_url(SPREADSHEET_ID, GID_PUBLICATIONS)
    publications_df = pd.read_csv(url)
    publications_df = publications_df.dropna(how="all")
    publications_df.columns = [col.strip() for col in publications_df.columns if isinstance(col, str)]
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
            from app.models import Publication  # ensure Publication model is imported
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
async def import_variants():
    print("[import_variants] Starting import of variants.")
    # Load the entire individuals sheet to extract variant data.
    url = csv_url(SPREADSHEET_ID, GID_INDIVIDUALS)
    df = pd.read_csv(url)
    df = df.dropna(how="all")
    df.columns = [col.strip() for col in df.columns if isinstance(col, str)]
    print(f"[import_variants] Normalized columns: {df.columns.tolist()}")

    # We assume the following columns are used for variant uniqueness:
    variant_key_cols = ['VariantType', 'VariantReported', 'ID', 'hg19_INFO', 'hg19', 'hg38_INFO', 'hg38', 'Varsome']
    # We'll also capture detection_method and segregation per individual.
    unique_variants = {}  # key -> dict with variant data and list of individual_ids
    individual_variant_info = {}  # individual_id -> dict with detection_method and segregation

    for idx, row in df.iterrows():
        # Only process rows with a VariantType.
        if pd.notna(row.get('VariantType')):
            # Build a key based on the variant columns.
            key_parts = []
            for col in variant_key_cols:
                val = none_if_nan(row.get(col))
                key_parts.append(str(val).strip() if val is not None else "")
            variant_key = "|".join(key_parts)
            individual_id = row['individual_id']
            # Record detection_method and segregation for this individual.
            det_method = none_if_nan(row.get('DetecionMethod'))
            seg = none_if_nan(row.get('Segregation'))
            individual_variant_info[individual_id] = {
                "detection_method": det_method,
                "segregation": seg
            }
            # If this variant key already exists, add this individual_id.
            if variant_key in unique_variants:
                if individual_id not in unique_variants[variant_key]['individual_ids']:
                    unique_variants[variant_key]['individual_ids'].append(individual_id)
            else:
                # Build variant data.
                variant_data = {
                    'variant_type': row.get('VariantType'),
                    'variant_reported': row.get('VariantReported'),
                    'ID': none_if_nan(row.get('ID')),
                    'hg19_INFO': none_if_nan(row.get('hg19_INFO')),
                    'hg19': none_if_nan(row.get('hg19')),
                    'hg38_INFO': none_if_nan(row.get('hg38_INFO')),
                    'hg38': none_if_nan(row.get('hg38')),
                    'varsome': none_if_nan(row.get('Varsome'))
                }
                # Process Varsome: try to extract transcript, c_dot, p_dot if possible.
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
                unique_variants[variant_key] = {
                    "variant_data": variant_data,
                    "individual_ids": [individual_id]
                }

    print(f"[import_variants] Found {len(unique_variants)} unique variants.")

    # Now assign sequential variant_id values and prepare Variant documents.
    validated_variants = []
    variant_id_counter = 1
    variant_key_to_id = {}
    for key, info in unique_variants.items():
        variant_doc = info["variant_data"]
        variant_doc['variant_id'] = variant_id_counter
        variant_doc['individual_ids'] = info["individual_ids"]
        from app.models import Variant  # ensure Variant model is imported
        try:
            var = Variant(**variant_doc)
            validated_variants.append(var.dict(by_alias=True, exclude_none=True))
            variant_key_to_id[key] = variant_id_counter
            variant_id_counter += 1
        except Exception as e:
            print(f"[import_variants] Validation error for variant key {key}: {e}")

    print(f"[import_variants] Inserting {len(validated_variants)} unique variants into database...")
    await db.variants.delete_many({})
    if validated_variants:
        await db.variants.insert_many(validated_variants)
    print(f"[import_variants] Imported {len(validated_variants)} variants.")

    # ---------------------------------------------------
    # Now update individuals: add a 'variant' field in each individual document
    # based on the individual_variant_info mapping and variant_key_to_id.
    print("[import_variants] Updating individuals with variant references...")
    individuals_cursor = db.individuals.find({})
    async for indiv_doc in individuals_cursor:
        indiv_id = indiv_doc.get("individual_id")
        # Look up the variant key(s) for this individual.
        # Here we scan through unique_variants to find a key that contains this individual.
        found_variant_id = None
        for key, info in unique_variants.items():
            if indiv_id in info["individual_ids"]:
                found_variant_id = variant_key_to_id.get(key)
                break
        if found_variant_id is not None:
            # Get detection_method and segregation info from individual_variant_info.
            det_seg = individual_variant_info.get(indiv_id, {})
            variant_ref = {
                "variant_id": found_variant_id,
                "detection_method": det_seg.get("detection_method"),
                "segregation": det_seg.get("segregation")
            }
            await db.individuals.update_one(
                {"_id": indiv_doc["_id"]},
                {"$set": {"variant": variant_ref}}
            )
    print("[import_variants] Updated individuals with variant references.")

# ---------------------------------------------------
async def main():
    print("[main] Starting migration process...")
    try:
        await import_users()
    except Exception as e:
        print(f"[main] Error during import_users: {e}")
    try:
        await import_individuals_with_reports()
    except Exception as e:
        print(f"[main] Error during import_individuals_with_reports: {e}")
    try:
        await import_publications()
    except Exception as e:
        print(f"[main] Error during import_publications: {e}")
    try:
        await import_variants()
    except Exception as e:
        print(f"[main] Error during import_variants: {e}")
    print("[main] Migration process complete.")

if __name__ == "__main__":
    asyncio.run(main())
