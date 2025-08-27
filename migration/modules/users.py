"""User/reviewer import module."""

import pandas as pd

from app.database import get_db
from app.repositories import UserRepository

from .utils import csv_url, normalize_dataframe_columns


async def import_users(
    spreadsheet_id: str, gid_reviewers: str, skip_duplicates: bool = True
):
    """Import user/reviewer data from Google Sheets into PostgreSQL."""
    print("[import_users] Starting import of reviewers/users...")

    url = csv_url(spreadsheet_id, gid_reviewers)
    df = pd.read_csv(url)
    df = df.dropna(how="all")
    df = normalize_dataframe_columns(df)

    print(f"[import_users] Processing {len(df)} users...")

    # Get database session and repository
    async for db_session in get_db():
        user_repo = UserRepository(db_session)
        created_count = 0

        for idx, row in df.iterrows():
            user_data = {
                "user_id": int(row["user_id"])
                if pd.notna(row.get("user_id"))
                else idx + 1,
                "user_name": str(row.get("user_name", "")).strip(),
                "password": "changeme",  # Default password
                "email": str(row.get("email", "")).strip(),
                "user_role": str(row.get("role", "reviewer")).strip(),
                "first_name": str(row.get("first_name", "")).strip(),
                "family_name": str(row.get("family_name", "")).strip(),
                "orcid": str(row.get("orcid", "")).strip()
                if row.get("orcid")
                else None,
            }

            # Skip empty rows
            if not user_data["user_name"] and not user_data["email"]:
                continue

            try:
                # Check if user exists first
                if skip_duplicates:
                    existing = await user_repo.get_by_email(user_data["email"])
                    if existing:
                        print(
                            f"[import_users] Skipping existing user: "
                            f"{user_data['user_name']}"
                        )
                        continue

                await user_repo.create(**user_data)
                created_count += 1
                print(f"[import_users] Created user: {user_data['user_name']}")

            except Exception as e:
                if "duplicate key" in str(e) and skip_duplicates:
                    print(
                        f"[import_users] Skipping duplicate user: "
                        f"{user_data['user_name']}"
                    )
                    await db_session.rollback()
                else:
                    print(
                        f"[import_users] Error creating user "
                        f"{user_data.get('user_name')}: {e}"
                    )
                    await db_session.rollback()

        await db_session.commit()
        print(f"[import_users] Successfully imported {created_count} new users")
        break  # Exit after first (and only) iteration
