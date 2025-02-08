# migrate_from_sheets.py
import asyncio
import pandas as pd
from app.database import db
from app.config import settings
from app.models import User, Individual, Publication  # Import our models

# The spreadsheet ID (extracted from your URL)
SPREADSHEET_ID = "1jE4-HmyAh1FUK6Ph7AuHt2UDVW2mTINTWXBtAWqhVSw"

# Replace these with the actual gid values for each sheet:
GID_REVIEWERS = "1321366018"      # For example, the "Reviewers" sheet
GID_INDIVIDUALS = "0"             # For example, the "Individuals" sheet
GID_PUBLICATIONS = "1670256162"   # For example, the "Publications" sheet

def csv_url(spreadsheet_id: str, gid: str) -> str:
    """
    Build the CSV export URL for a given spreadsheet ID and sheet gid.
    """
    url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/export?format=csv&gid={gid}"
    print(f"[csv_url] Built URL: {url}")
    return url

def import_users():
    print("[import_users] Starting import of reviewers/users.")
    url = csv_url(SPREADSHEET_ID, GID_REVIEWERS)
    print(f"[import_users] Fetching reviewers from URL: {url}")
    reviewers_df = pd.read_csv(url)
    print(f"[import_users] Raw columns: {reviewers_df.columns.tolist()}")
    
    reviewers_df = reviewers_df.dropna(how="all")
    # Normalize column names by stripping any surrounding whitespace.
    reviewers_df.columns = [col.strip() for col in reviewers_df.columns if isinstance(col, str)]
    print(f"[import_users] Normalized columns: {reviewers_df.columns.tolist()}")
    
    # Define expected columns for user data.
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
            # Use exclude_none=True so that if _id is None it is removed
            user = User(**row)
            validated_users.append(user.dict(by_alias=True, exclude_none=True))
        except Exception as e:
            print(f"[import_users] Validation error in row {idx}: {e}\nRow data: {row}")
    
    print(f"[import_users] Inserting {len(validated_users)} valid users into database...")
    # Delete all old entries first.
    db.users.delete_many({})
    if validated_users:
        db.users.insert_many(validated_users)
    print(f"[import_users] Imported {len(validated_users)} users.")

def import_individuals():
    print("[import_individuals] Starting import of individuals.")
    url = csv_url(SPREADSHEET_ID, GID_INDIVIDUALS)
    print(f"[import_individuals] Fetching individuals from URL: {url}")
    individuals_df = pd.read_csv(url)
    print(f"[import_individuals] Raw columns: {individuals_df.columns.tolist()}")
    
    individuals_df = individuals_df.dropna(how="all")
    # Rename column "Sex" to "sex" if it exists.
    if "Sex" in individuals_df.columns:
        individuals_df = individuals_df.rename(columns={"Sex": "sex"})
    print(f"[import_individuals] Normalized columns: {individuals_df.columns.tolist()}")
    
    validated_individuals = []
    for idx, row in individuals_df.iterrows():
        try:
            indiv = Individual(**row)
            validated_individuals.append(indiv.dict(by_alias=True, exclude_none=True))
        except Exception as e:
            print(f"[import_individuals] Validation error in row {idx}: {e}\nRow data: {row}")
    
    print(f"[import_individuals] Inserting {len(validated_individuals)} valid individuals into database...")
    db.individuals.delete_many({})
    if validated_individuals:
        db.individuals.insert_many(validated_individuals)
    print(f"[import_individuals] Imported {len(validated_individuals)} individuals.")

def import_publications():
    print("[import_publications] Starting import of publications.")
    url = csv_url(SPREADSHEET_ID, GID_PUBLICATIONS)
    print(f"[import_publications] Fetching publications from URL: {url}")
    publications_df = pd.read_csv(url)
    print(f"[import_publications] Raw columns: {publications_df.columns.tolist()}")
    
    publications_df = publications_df.dropna(how="all")
    print(f"[import_publications] Normalized columns: {publications_df.columns.tolist()}")
    
    validated_publications = []
    for idx, row in publications_df.iterrows():
        try:
            pub = Publication(**row)
            validated_publications.append(pub.dict(by_alias=True, exclude_none=True))
        except Exception as e:
            print(f"[import_publications] Validation error in row {idx}: {e}\nRow data: {row}")
    
    print(f"[import_publications] Inserting {len(validated_publications)} valid publications into database...")
    db.publications.delete_many({})
    if validated_publications:
        db.publications.insert_many(validated_publications)
    print(f"[import_publications] Imported {len(validated_publications)} publications.")

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
    print("[main] Migration process complete.")

if __name__ == "__main__":
    asyncio.run(main())
