#!/usr/bin/env python3
"""Test script to verify CNV parser handles deletions correctly."""

import pandas as pd

from migration.vrs.cnv_parser import CNVParser


def test_cnv_parser():
    """Test the CNV parser with real data from Google Sheets."""
    print("Testing CNV Parser with real deletion data\n")
    print("=" * 60)

    # Test cases from actual Google Sheets data
    test_cases = [
        {
            "name": "Case 1: Standard deletion",
            "hg38": "chr17-36459258-T-<DEL>",
            "hg38_INFO": "IMPRECISE;SVTYPE=DEL;END=37832869;SVLEN=-1373610",
            "VariantType": "Deletion",
            "VariantReported": "1.5 Mb deletion including HNF1β",
        },
        {
            "name": "Case 2: Larger deletion",
            "hg38": "chr17-36466613-T-<DEL>",
            "hg38_INFO": "IMPRECISE;SVTYPE=DEL;END=39698363;SVLEN=-3231750",
            "VariantType": "Deletion",
            "VariantReported": "1.5Mb deletion within chromosome 17q12 (34,822,460-36,375,192, GRCh37/hg19)",
        },
        {
            "name": "Case 3: Duplication",
            "hg38": "chr17-36459258-T-<DUP>",
            "hg38_INFO": "IMPRECISE;SVTYPE=DUP;END=37832869;SVLEN=1373610",
            "VariantType": "Duplication",
            "VariantReported": "17q12 duplication",
        },
    ]

    for i, test_case in enumerate(test_cases, 1):
        print(f"\n{test_case['name']}")
        print("-" * 40)

        # Parse coordinates
        coords = CNVParser.parse_hg38_coordinates(
            test_case["hg38"], test_case["hg38_INFO"]
        )

        if coords:
            chromosome, start, end, variant_type = coords
            print("✓ Parsed coordinates:")
            print(f"  Chromosome: {chromosome}")
            print(f"  Start: {start:,}")
            print(f"  End: {end:,}")
            print(f"  Type: {variant_type}")
            print(
                f"  Size: {(end - start + 1):,} bp ({round((end - start + 1) / 1_000_000, 2)} Mb)"
            )

            # Create GA4GH notation
            ga4gh_notation = CNVParser.create_ga4gh_cnv_notation(
                chromosome, start, end, variant_type
            )
            print(f"\n✓ GA4GH Notation: {ga4gh_notation}")

            # Get dbVar ID
            dbvar_id = CNVParser.get_dbvar_id(variant_type)
            if dbvar_id:
                print(f"✓ dbVar ID: {dbvar_id}")

            # Create full phenopacket variant
            variant = CNVParser.create_phenopacket_cnv_variant(
                test_case["hg38"],
                test_case["hg38_INFO"],
                test_case["VariantType"],
                test_case["VariantReported"],
            )

            if variant:
                print("\n✓ Phenopacket variant created:")
                print(f"  ID: {variant['id']}")
                print(f"  Label: {variant['label']}")
                print(f"  Structural Type: {variant['structuralType']['label']}")
                print(f"  Expressions: {len(variant['expressions'])} formats")
                for expr in variant["expressions"]:
                    print(
                        f"    - {expr['syntax']}: {expr['value'][:50]}..."
                        if len(expr["value"]) > 50
                        else f"    - {expr['syntax']}: {expr['value']}"
                    )

                if variant.get("extensions"):
                    print(f"  Extensions: {len(variant['extensions'])} items")
                    for ext in variant["extensions"]:
                        if ext["name"] == "coordinates":
                            print(
                                f"    - Coordinates: chr{ext['value']['chromosome']}:{ext['value']['start']}-{ext['value']['end']}"
                            )
                        elif ext["name"] == "copy_number":
                            print(
                                f"    - Copy number: {ext['value']['absolute_copy_number']}"
                            )
                        elif ext["name"] == "external_reference":
                            print(f"    - External ref: {ext['value']['id']}")
        else:
            print("✗ Failed to parse coordinates")


def test_google_sheets_integration():
    """Test with actual data from Google Sheets."""
    print("\n\n" + "=" * 60)
    print("Testing with actual Google Sheets data")
    print("=" * 60)

    try:
        # Load actual data
        SPREADSHEET_ID = "1jE4-HmyAh1FUK6Ph7AuHt2UDVW2mTINTWXBtAWqhVSw"
        GID_INDIVIDUALS = "0"
        url = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/export?format=csv&gid={GID_INDIVIDUALS}"

        print("Loading data from Google Sheets...")
        df = pd.read_csv(url)

        # Filter for deletions and duplications
        cnv_df = df[
            df["VariantType"].str.contains("delet|dup", case=False, na=False)
        ].head(5)

        print(f"Found {len(cnv_df)} CNVs to test\n")

        success_count = 0
        for idx, row in cnv_df.iterrows():
            individual = row["IndividualIdentifier"]
            variant_type = row["VariantType"]
            hg38 = row["hg38"]
            hg38_info = row["hg38_INFO"]

            if pd.notna(hg38) and pd.notna(hg38_info):
                print(f"\nIndividual: {individual}")
                print(f"Variant Type: {variant_type}")

                # Parse using CNVParser
                coords = CNVParser.parse_hg38_coordinates(str(hg38), str(hg38_info))
                if coords:
                    chromosome, start, end, var_type = coords
                    ga4gh = CNVParser.create_ga4gh_cnv_notation(
                        chromosome, start, end, var_type
                    )
                    print(f"  ✓ GA4GH notation: {ga4gh}")
                    success_count += 1
                else:
                    print("  ✗ Failed to parse")

        print(f"\n\nSummary: Successfully parsed {success_count}/{len(cnv_df)} CNVs")

    except Exception as e:
        print(f"Error loading Google Sheets data: {e}")


if __name__ == "__main__":
    test_cnv_parser()
    test_google_sheets_integration()
