#!/usr/bin/env python3
"""Main migration orchestrator script for importing all data from Google Sheets
to PostgreSQL.
"""

import asyncio
import os
import sys

from dotenv import load_dotenv

# Add parent directory to path to import app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


from migration.modules.genes import import_genes
from migration.modules.genomics import load_genomic_files
from migration.modules.individuals import import_individuals
from migration.modules.proteins import import_proteins
from migration.modules.publications import import_publications
from migration.modules.users import import_users
from migration.modules.variants import import_variants

# Load environment variables
load_dotenv()

# Configuration - Working spreadsheet from original script
SPREADSHEET_ID = "1jE4-HmyAh1FUK6Ph7AuHt2UDVW2mTINTWXBtAWqhVSw"
GID_REVIEWERS = "1321366018"
GID_PUBLICATIONS = "1670256162"
GID_INDIVIDUALS = "0"
GID_PHENOTYPES = "934433647"
GID_MODIFIERS = "1350764936"


async def main(test_mode: bool = False):
    """Main migration orchestrator - runs all import phases."""
    print("=" * 60)
    print("Starting PostgreSQL Migration from Google Sheets")
    if test_mode:
        print("*** TEST MODE - Limited data import ***")
    print("=" * 60)

    try:
        # Phase 1: Import users/reviewers
        print("\n--- Phase 1: Importing Users ---")
        await import_users(SPREADSHEET_ID, GID_REVIEWERS, skip_duplicates=True)

        # Phase 2: Import publications with PubMed enrichment
        print("\n--- Phase 2: Importing Publications ---")
        pub_limit = 10 if test_mode else None
        await import_publications(
            SPREADSHEET_ID, GID_PUBLICATIONS, limit=pub_limit, skip_duplicates=True
        )

        # Phase 3: Import individuals and clinical reports
        print("\n--- Phase 3: Importing Individuals ---")
        ind_limit = 20 if test_mode else None
        await import_individuals(
            SPREADSHEET_ID, GID_INDIVIDUALS, limit=ind_limit, skip_duplicates=True
        )

        # Phase 4: Import protein structure data
        print("\n--- Phase 4: Importing Proteins ---")
        await import_proteins(SPREADSHEET_ID, test_mode=test_mode)

        # Phase 5: Import gene structure data
        print("\n--- Phase 5: Importing Genes ---")
        await import_genes(test_mode=test_mode)

        # Phase 6: Import variants with genomic annotations
        print("\n--- Phase 6: Importing Variants ---")
        await import_variants(SPREADSHEET_ID, GID_INDIVIDUALS, skip_duplicates=True)

        genomic_data = await load_genomic_files()
        if "error" not in genomic_data:
            print(
                "[main] Genomic files loaded successfully - full variant import logic can be added later"
            )
        else:
            print(
                f"[main] Warning: Could not load genomic files: {genomic_data['error']}"
            )

        print("\n" + "=" * 60)
        print("Migration completed successfully!")
        print("=" * 60)

    except Exception as e:
        print(f"\n[ERROR] Migration failed: {e}")
        raise


if __name__ == "__main__":
    import sys

    # Check for test mode flag
    test_mode = "--test" in sys.argv
    asyncio.run(main(test_mode=test_mode))
