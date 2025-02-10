# File: migrate_from_sheets.py
import asyncio
import math
import re
import pandas as pd
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
def normalize_dataframe_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Strip whitespace from DataFrame column names."""
    df.columns = [col.strip() for col in df.columns if isinstance(col, str)]
    return df

# ---------------------------------------------------
async def load_phenotype_mappings():
    url = csv_url(SPREADSHEET_ID, PHENOTYPE_GID)
    df = pd.read_csv(url)
    df = normalize_dataframe_columns(df)
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
    url = csv_url(SPREADSHEET_ID, MODIFIER_GID)
    df = pd.read_csv(url)
    df = normalize_dataframe_columns(df)
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
    reviewers_df = normalize_dataframe_columns(reviewers_df)
    expected_columns = ['user_id', 'user_name', 'password', 'email',
                        'user_role', 'first_name', 'family_name', 'orcid']
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
async def import_publications():
    print("[import_publications] Starting import of publications.")
    url = csv_url(SPREADSHEET_ID, GID_PUBLICATIONS)
    publications_df = pd.read_csv(url)
    publications_df = publications_df.dropna(how="all")
    publications_df = normalize_dataframe_columns(publications_df)
    user_mapping = {}
    user_docs = await db.users.find({}, {"email": 1}).to_list(length=None)
    for user_doc in user_docs:
        email = user_doc["email"].strip().lower()
        user_mapping[email] = user_doc["_id"]
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
async def import_individuals_with_reports():
    print("[import_individuals] Starting import of individuals with embedded reports.")
    url = csv_url(SPREADSHEET_ID, GID_INDIVIDUALS)
    df = pd.read_csv(url)
    df = df.dropna(how="all")
    df = normalize_dataframe_columns(df)
    print(f"[import_individuals] Normalized columns: {df.columns.tolist()}")

    # Build base_cols list; include "Publication" only if it exists (case sensitive)
    base_cols = ['individual_id', 'DupCheck', 'IndividualIdentifier', 'Problematic', 'Cohort', 'Sex', 'AgeOnset', 'AgeReported']
    if "Publication" in df.columns:
        base_cols.append("Publication")

    # Build publication mapping: keys are the lowercased publication_alias from publications
    pub_docs = await db.publications.find({}, {"publication_alias": 1}).to_list(length=None)
    publication_mapping = {
        doc["publication_alias"].strip().lower(): doc["_id"]
        for doc in pub_docs if "publication_alias" in doc
    }
    print(f"[import_individuals] Loaded publication mapping for {len(publication_mapping)} publications.")

    # Build user mapping from reviewers: key = lowercased email, value = _id of the user document
    user_docs = await db.users.find({}, {"email": 1}).to_list(length=None)
    user_mapping = {}
    for user_doc in user_docs:
        email = user_doc["email"].strip().lower()
        user_mapping[email] = user_doc["_id"]

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

    phenotype_mapping = await load_phenotype_mappings()
    modifier_mapping = await load_modifier_mappings()

    grouped = df.groupby('individual_id')
    validated_individuals = []
    for indiv_id, group in grouped:
        base_data = group.iloc[0][base_cols].to_dict()
        # Save and remove the base Publication value (if available) from base_data
        base_publication_alias = base_data.pop('Publication', None)
        reports = []
        for idx, row in group.iterrows():
            if pd.notna(row.get('report_id')):
                report_data = {'report_id': row['report_id']}
                # Link the reviewing user: lookup the ReviewBy column (using email) to get the user _id.
                review_by_email = row.get('ReviewBy')
                if pd.notna(review_by_email):
                    report_data['reviewed_by'] = user_mapping.get(review_by_email.strip().lower())
                else:
                    report_data['reviewed_by'] = None
                phenotypes_obj = {}
                for col in phenotype_cols:
                    raw_val = row.get(col, "")
                    reported_val = str(raw_val).strip() if pd.notna(raw_val) else ""
                    pheno_key = col.strip().lower()
                    std_info = phenotype_mapping.get(pheno_key, {"phenotype_id": col, "name": col})
                    mod_key = reported_val.lower()
                    mod_info = modifier_mapping.get(mod_key) if mod_key else None
                    modifier_std = mod_info["name"] if mod_info else reported_val
                    described = False if reported_val in ["", "no", "not reported"] else True
                    phenotypes_obj[std_info["phenotype_id"]] = {
                        "phenotype_id": std_info["phenotype_id"],
                        "name": std_info["name"],
                        "modifier": modifier_std,
                        "modifier_id": mod_info["modifier_id"] if mod_info else None,
                        "described": described
                    }
                report_data['phenotypes'] = phenotypes_obj

                # Link the publication: get the Publication column from the current row,
                # if missing, fallback to the base publication value.
                pub_alias = row.get('Publication')
                if not pd.notna(pub_alias) and base_publication_alias:
                    pub_alias = base_publication_alias
                if pd.notna(pub_alias):
                    pub_alias_lower = str(pub_alias).strip().lower()
                    pub_obj_id = publication_mapping.get(pub_alias_lower)
                    if pub_obj_id:
                        report_data["publication_ref"] = pub_obj_id
                    else:
                        print(f"[import_individuals] Warning: Publication alias '{pub_alias}' not found for individual {indiv_id}.")
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
async def import_variants():
    print("[import_variants] Starting import of variants.")
    url = csv_url(SPREADSHEET_ID, GID_INDIVIDUALS)
    df = pd.read_csv(url)
    df = df.dropna(how="all")
    df = normalize_dataframe_columns(df)
    print(f"[import_variants] Normalized columns: {df.columns.tolist()}")

    variant_key_cols = ['VariantType', 'VariantReported', 'ID', 'hg19_INFO', 'hg19', 'hg38_INFO', 'hg38', 'Varsome']
    unique_variants = {}
    individual_variant_info = {}

    for idx, row in df.iterrows():
        if pd.notna(row.get('VariantType')):
            key_parts = []
            for col in variant_key_cols:
                val = none_if_nan(row.get(col))
                key_parts.append(str(val).strip() if val is not None else "")
            variant_key = "|".join(key_parts)
            sp_indiv_id = row['individual_id']
            det_method = none_if_nan(row.get('DetecionMethod'))
            seg = none_if_nan(row.get('Segregation'))
            individual_variant_info[sp_indiv_id] = {
                "detection_method": det_method,
                "segregation": seg
            }
            if variant_key in unique_variants:
                if sp_indiv_id not in unique_variants[variant_key]['individual_ids']:
                    unique_variants[variant_key]['individual_ids'].append(sp_indiv_id)
            else:
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
                    "individual_ids": [sp_indiv_id]
                }
    print(f"[import_variants] Found {len(unique_variants)} unique variants.")

    spid_to_objid = {}
    async for doc in db.individuals.find({}, {"individual_id": 1}):
        spid = doc.get("individual_id")
        if spid is not None:
            spid_to_objid[spid] = doc["_id"]

    variant_docs_to_insert = []
    variant_id_counter = 1
    for key, info in unique_variants.items():
        variant_doc = info["variant_data"]
        variant_doc['variant_id'] = variant_id_counter
        objid_list = []
        for spid in info["individual_ids"]:
            if spid in spid_to_objid:
                objid_list.append(spid_to_objid[spid])
        variant_doc['individual_ids'] = objid_list
        variant_docs_to_insert.append(variant_doc)
        variant_id_counter += 1

    print(f"[import_variants] Inserting {len(variant_docs_to_insert)} unique variants into database...")
    await db.variants.delete_many({})
    inserted_result = await db.variants.insert_many(variant_docs_to_insert)
    inserted_ids = inserted_result.inserted_ids
    variant_key_to_objid = {}
    for i, key in enumerate(unique_variants.keys()):
        variant_key_to_objid[key] = inserted_ids[i]
    print(f"[import_variants] Inserted {len(variant_docs_to_insert)} unique variants into database.")

    print("[import_variants] Updating individuals with variant references...")
    async for indiv_doc in db.individuals.find({}):
        sp_indiv_id = indiv_doc.get("individual_id")
        found_variant_objid = None
        for key, info in unique_variants.items():
            if sp_indiv_id in info["individual_ids"]:
                found_variant_objid = variant_key_to_objid.get(key)
                break
        if found_variant_objid is not None:
            det_seg = individual_variant_info.get(sp_indiv_id, {})
            variant_ref = {
                "variant_ref": found_variant_objid,
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
        await import_publications()
    except Exception as e:
        print(f"[main] Error during import_publications: {e}")
    try:
        await import_individuals_with_reports()
    except Exception as e:
        print(f"[main] Error during import_individuals_with_reports: {e}")
    try:
        await import_variants()
    except Exception as e:
        print(f"[main] Error during import_variants: {e}")
    print("[main] Migration process complete.")

if __name__ == "__main__":
    asyncio.run(main())
