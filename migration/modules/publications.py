"""Publications import module with PubMed enrichment."""

from typing import Optional

import pandas as pd

from app.database import get_db
from app.repositories import PublicationRepository

from .apis import update_publication_with_pubmed
from .utils import (
    csv_url,
    format_publication_id,
    normalize_dataframe_columns,
    parse_date,
)


async def import_publications(
    spreadsheet_id: str,
    gid_publications: str,
    limit: Optional[int] = None,
    skip_duplicates: bool = True,
):
    """Import publications from Google Sheets with optional PubMed enrichment."""
    print("[import_publications] Starting import of publications...")

    url = csv_url(spreadsheet_id, gid_publications)
    df = pd.read_csv(url)
    df = df.dropna(how="all")
    df = normalize_dataframe_columns(df)

    # Format publication_id
    if "publication_id" in df.columns:
        df["publication_id"] = df["publication_id"].apply(format_publication_id)

    # Rename Comment column if present
    if "Comment" in df.columns:
        df.rename(columns={"Comment": "comment"}, inplace=True)

    if limit:
        df = df.head(limit)
        print(
            f"[import_publications] Limited to first {limit} publications for testing"
        )

    print(f"[import_publications] Processing {len(df)} publications...")

    # Get database session and repository
    async for db_session in get_db():
        pub_repo = PublicationRepository(db_session)
        created_count = 0

        for idx, row in df.iterrows():
            # Handle PMID properly - convert to integer or None
            pmid_val = row.get("PMID")
            if pd.isna(pmid_val) or str(pmid_val).strip().lower() in ["nan", ""]:
                pmid_val = None
            else:
                try:
                    # Convert float to int if it's a valid number
                    pmid_val = int(float(pmid_val))
                except (ValueError, TypeError):
                    pmid_val = None

            pub_data = {
                "publication_id": row.get("publication_id", f"pub{idx+1:04d}"),
                "publication_type": str(row.get("publication_type", "")).strip()
                or None,
                "title": str(row.get("title", "")).strip(),
                "abstract": str(row.get("abstract", "")).strip() or None,
                "doi": str(row.get("DOI", "")).strip() or None,
                "pmid": pmid_val,
                "journal": str(row.get("journal", "")).strip() or None,
                "publication_alias": str(row.get("publication_alias", "")).strip()
                or None,
                "publication_date": parse_date(row.get("publication_date")),
                "keywords": [],
                "medical_specialty": [],
                "comment": str(row.get("comment", "")).strip() or None,
            }

            # Skip empty publications
            if not pub_data["title"] and not pub_data["pmid"]:
                continue

            try:
                # Check for existing publication
                if skip_duplicates and pub_data["publication_id"]:
                    existing = await pub_repo.get_by_publication_id(
                        pub_data["publication_id"]
                    )
                    if existing:
                        print(
                            f"[import_publications] Skipping existing publication: "
                            f"{pub_data['publication_id']}"
                        )
                        continue

                # Enrich with PubMed data if PMID exists
                # (but only for limited imports to save time)
                if pub_data["pmid"] and (not limit or limit <= 20):
                    print(
                        f"[import_publications] Enriching publication "
                        f"{pub_data['publication_id']} with PubMed data..."
                    )
                    pub_data = update_publication_with_pubmed(pub_data)

                await pub_repo.create(**pub_data)
                created_count += 1
                print(
                    f"[import_publications] Created publication: "
                    f"{pub_data['publication_id']}"
                )

            except Exception as e:
                if "duplicate key" in str(e) and skip_duplicates:
                    print(
                        f"[import_publications] Skipping duplicate publication: "
                        f"{pub_data['publication_id']}"
                    )
                    await db_session.rollback()
                else:
                    print(
                        f"[import_publications] Error creating publication "
                        f"{pub_data.get('publication_id')}: {e}"
                    )
                    await db_session.rollback()

        await db_session.commit()
        print(
            f"[import_publications] Successfully imported {created_count} new "
            f"publications"
        )
        break
