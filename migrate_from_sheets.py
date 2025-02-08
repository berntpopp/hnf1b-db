# migrate_from_sheets.py
import asyncio
import math
import re
import pandas as pd
from app.database import db
from app.config import settings
from app.models import User, Individual, Publication, Report, Variant

# The spreadsheet ID (extracted from your URL)
SPREADSHEET_ID = "1jE4-HmyAh1FUK6Ph7AuHt2UDVW2mTINTWXBtAWqhVSw"

# GIDs for each sheet:
GID_REVIEWERS = "1321366018"      # Reviewers sheet
GID_INDIVIDUALS = "0"             # Individuals sheet
GID_PUBLICATIONS = "1670256162"   # Publications sheet

# ---------------------------------------------------
# Helper: Convert NA values to None.
def none_if_nan(v):
    try:
        if isinstance(v, float) and math.isnan(v):
            return None
    except Exception:
        pass
    if isinstance(v, str) and v.strip().upper() == "NA":
        return None
    return v

# ---------------------------------------------------
def csv_url(spreadsheet_id: str, gid: str) -> str:
    url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/export?format=csv&gid={gid}"
    print(f"[csv_url] Built URL: {url}")
    return url

# ---------------------------------------------------
def import_users():
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
    db.users.delete_many({})
    if validated_users:
        db.users.insert_many(validated_users)
    print(f"[import_users] Imported {len(validated_users)} users.")

# ---------------------------------------------------
def import_individuals():
    print("[import_individuals] Starting import of individuals.")
    url = csv_url(SPREADSHEET_ID, GID_INDIVIDUALS)
    print(f"[import_individuals] Fetching individuals from URL: {url}")
    individuals_df = pd.read_csv(url)
    print(f"[import_individuals] Raw columns: {individuals_df.columns.tolist()}")

    individuals_df = individuals_df.dropna(how="all")
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
    db.individuals.delete_many({})
    if validated_individuals:
        db.individuals.insert_many(validated_individuals)
    print(f"[import_individuals] Imported {len(validated_individuals)} individuals.")

# ---------------------------------------------------
def import_publications():
    print("[import_publications] Starting import of publications.")
    url = csv_url(SPREADSHEET_ID, GID_PUBLICATIONS)
    print(f"[import_publications] Fetching publications from URL: {url}")
    publications_df = pd.read_csv(url)
    print(f"[import_publications] Raw columns: {publications_df.columns.tolist()}")

    publications_df = publications_df.dropna(how="all")
    print(f"[import_publications] Normalized columns: {publications_df.columns.tolist()}")

    # Build a mapping from reviewer email to user_id.
    user_mapping = {}
    for user_doc in db.users.find({}, {"email": 1, "user_id": 1}):
        email = user_doc["email"].strip().lower()
        user_mapping[email] = user_doc["user_id"]
    print(f"[import_publications] User mapping: {user_mapping}")

    validated_publications = []
    for idx, row in publications_df.iterrows():
        try:
            # Convert legacy "Assigne" (if present) from email to user_id.
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
    db.publications.delete_many({})
    if validated_publications:
        db.publications.insert_many(validated_publications)
    print(f"[import_publications] Imported {len(validated_publications)} publications.")

# ---------------------------------------------------
def import_reports():
    print("[import_reports] Starting import of reports.")
    # Assume report data is in the Individuals sheet.
    url = csv_url(SPREADSHEET_ID, GID_INDIVIDUALS)
    print(f"[import_reports] Fetching report data from URL: {url}")
    df = pd.read_csv(url)
    print(f"[import_reports] Raw columns: {df.columns.tolist()}")
    df = df.dropna(how="all")
    df.columns = [col.strip() for col in df.columns if isinstance(col, str)]
    print(f"[import_reports] Normalized columns: {df.columns.tolist()}")

    # Build a mapping from reviewer email to user_id.
    user_mapping = {}
    for user_doc in db.users.find({}, {"email": 1, "user_id": 1}):
        email = user_doc["email"].strip().lower()
        user_mapping[email] = user_doc["user_id"]
    print(f"[import_reports] User mapping: {user_mapping}")

    validated_reports = []
    if 'report_id' not in df.columns:
        print("[import_reports] No 'report_id' column found; skipping report import.")
    else:
        report_rows = df[df['report_id'].notna()]
        for idx, row in report_rows.iterrows():
            try:
                report_data = {}
                report_data['report_id'] = row['report_id']
                report_data['individual_id'] = row['individual_id']
                report_data['report_review_date'] = row.get('ReviewDate')
                report_data['report_date'] = row.get('ReportDate', row.get('ReviewDate'))
                review_by_email = row.get('ReviewBy')
                if pd.notna(review_by_email):
                    report_data['reviewed_by'] = user_mapping.get(review_by_email.strip().lower())
                else:
                    report_data['reviewed_by'] = None
                # Assume phenotype information is stored in a column named "Phenotypes"
                phenotypes_str = row.get('Phenotypes')
                phenotypes_list = []
                if pd.notna(phenotypes_str):
                    for entry in phenotypes_str.split(';'):
                        parts = entry.split('|')
                        if len(parts) >= 2:
                            pheno = {
                                "phenotype_id": parts[0].strip(),
                                "name": parts[1].strip(),
                                "modifier": parts[2].strip() if len(parts) > 2 else None,
                                "described": parts[3].strip().lower() == "true" if len(parts) > 3 else False
                            }
                            phenotypes_list.append(pheno)
                report_data['phenotypes'] = phenotypes_list
                rep = Report(**report_data)
                validated_reports.append(rep.dict(by_alias=True, exclude_none=True))
            except Exception as e:
                print(f"[import_reports] Validation error in row {idx}: {e}")
    
    print(f"[import_reports] Inserting {len(validated_reports)} valid reports into database...")
    db.reports.delete_many({})
    if validated_reports:
        db.reports.insert_many(validated_reports)
    print(f"[import_reports] Imported {len(validated_reports)} reports.")

# ---------------------------------------------------
def import_variants():
    print("[import_variants] Starting import of variants.")
    # Assume variant data is in the Individuals sheet.
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
                variant_data = {}
                variant_data['variant_id'] = variant_id_counter
                variant_id_counter += 1
                variant_data['individual_id'] = row['individual_id']
                variant_data['is_current'] = True  # Mark as current by default
                variant_data['variant_type'] = row.get('VariantType')
                variant_data['variant_reported'] = row.get('VariantReported')
                # Convert problematic fields: use none_if_nan to clean NaN values.
                variant_data['ID'] = none_if_nan(row.get('ID'))
                variant_data['hg19_INFO'] = none_if_nan(row.get('hg19_INFO'))
                variant_data['hg19'] = none_if_nan(row.get('hg19'))
                variant_data['hg38_INFO'] = none_if_nan(row.get('hg38_INFO'))
                variant_data['hg38'] = none_if_nan(row.get('hg38'))

                # Parse the Varsome field into transcript, c_dot, and p_dot.
                varsome_val = row.get('Varsome')
                if pd.notna(varsome_val) and str(varsome_val).strip().upper() != "NA":
                    # Expected format: "HNF1B(NM_000458.4):c.406C>G (p.Gln136Glu)"
                    pattern = r"^[^(]+\(([^)]+)\):([^ ]+)\s+(\(p\..+\))"
                    m = re.match(pattern, str(varsome_val))
                    if m:
                        variant_data['transcript'] = m.group(1)
                        variant_data['c_dot'] = m.group(2)
                        variant_data['p_dot'] = m.group(3)
                    else:
                        # Fallback: assign the raw string to transcript only.
                        variant_data['transcript'] = str(varsome_val)
                # Else, leave transcript, c_dot, p_dot as None.

                variant_data['detection_method'] = none_if_nan(row.get('DetecionMethod'))
                variant_data['segregation'] = none_if_nan(row.get('Segregation'))
                
                var = Variant(**variant_data)
                validated_variants.append(var.dict(by_alias=True, exclude_none=True))
            except Exception as e:
                print(f"[import_variants] Validation error in row {idx}: {e}")
    
    print(f"[import_variants] Inserting {len(validated_variants)} valid variants into database...")
    db.variants.delete_many({})
    if validated_variants:
        db.variants.insert_many(validated_variants)
    print(f"[import_variants] Imported {len(validated_variants)} variants.")

# ---------------------------------------------------
async def main():
    print("[main] Starting migration process...")
    try:
        import_users()
    except Exception as e:
        print(f"[main] Error during import_users: {e}")
    try:
        import_individuals()
    except Exception as e:
        print(f"[main] Error during import_individuals: {e}")
    try:
        import_publications()
    except Exception as e:
        print(f"[main] Error during import_publications: {e}")
    try:
        import_reports()
    except Exception as e:
        print(f"[main] Error during import_reports: {e}")
    try:
        import_variants()
    except Exception as e:
        print(f"[main] Error during import_variants: {e}")
    print("[main] Migration process complete.")

if __name__ == "__main__":
    asyncio.run(main())
