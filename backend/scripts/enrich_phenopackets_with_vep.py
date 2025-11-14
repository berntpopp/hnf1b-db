#!/usr/bin/env python3
"""Enrich existing phenopackets with VEP annotations.

This script:
1. Fetches all phenopackets with variants
2. Annotates each variant using the VEP API
3. Adds VEP data to phenopacket extensions (schema-compliant)
4. Updates database with enriched phenopackets

Usage:
    # Dry run (shows what would be annotated without making changes)
    python scripts/enrich_phenopackets_with_vep.py --dry-run

    # Annotate first 10 phenopackets (testing)
    python scripts/enrich_phenopackets_with_vep.py --limit 10

    # Annotate all phenopackets
    python scripts/enrich_phenopackets_with_vep.py

    # Force re-annotation of already annotated variants
    python scripts/enrich_phenopackets_with_vep.py --force

Requirements:
    - Database running (make hybrid-up)
    - Valid backend/.env with DATABASE_URL
    - Internet connection (for VEP API calls)
"""

import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text

from app.database import get_db
from app.phenopackets.validation.variant_validator import VariantValidator


def extract_vcf_from_phenopacket(pk_data: Dict[str, Any]) -> Optional[str]:
    """Extract VCF string from phenopacket variant.

    Supports both expression-based format (current schema) and vcf_record format.

    Args:
        pk_data: Phenopacket data dictionary

    Returns:
        VCF string (e.g., "17-36459258-A-G") or None if not found
    """
    try:
        interpretations = pk_data.get("interpretations", [])
        if not interpretations:
            return None

        genomic_interps = (
            interpretations[0]
            .get("diagnosis", {})
            .get("genomicInterpretations", [])
        )
        if not genomic_interps:
            return None

        variation_descriptor = (
            genomic_interps[0]
            .get("variantInterpretation", {})
            .get("variationDescriptor", {})
        )

        # Try to get VCF from expressions array (new format)
        expressions = variation_descriptor.get("expressions", [])
        for expr in expressions:
            if expr.get("syntax") == "vcf":
                vcf_value = expr.get("value", "")
                # Clean up VCF value (chr17-37744882-C-T)
                # Remove "chr" prefix if present
                vcf_cleaned = vcf_value.replace("chr", "")
                # Skip large structural variants (<DEL>, <DUP>, etc.)
                if "<" in vcf_cleaned or ">" in vcf_cleaned:
                    return None
                return vcf_cleaned

        # Fallback: try vcf_record format (if it exists)
        vcf_record = variation_descriptor.get("vcf_record")
        if vcf_record:
            chr_val = vcf_record.get("chr", "").replace("chr", "")
            pos = vcf_record.get("pos")
            ref = vcf_record.get("ref")
            alt = vcf_record.get("alt")

            if all([chr_val, pos, ref, alt]):
                return f"{chr_val}-{pos}-{ref}-{alt}"

        return None

    except (KeyError, IndexError, AttributeError):
        return None


def add_vep_to_phenopacket(
    pk_data: Dict[str, Any], vep_data: Dict[str, Any]
) -> Dict[str, Any]:
    """Add VEP annotation to phenopacket using schema-compliant extensions field.

    This follows GA4GH Phenopackets v2 VariationDescriptor schema.
    The extensions field is explicitly designed for "resource-specific
    Extensions needed to describe the variation."

    Args:
        pk_data: Phenopacket data dictionary
        vep_data: VEP annotation data from VariantValidator

    Returns:
        Updated phenopacket data
    """
    try:
        # Navigate to variation descriptor
        variant_desc = (
            pk_data["interpretations"][0]["diagnosis"]["genomicInterpretations"][0][
                "variantInterpretation"
            ]["variationDescriptor"]
        )

        # Initialize extensions array if doesn't exist
        if "extensions" not in variant_desc:
            variant_desc["extensions"] = []

        # Remove old VEP extension if exists (allow re-annotation)
        variant_desc["extensions"] = [
            ext
            for ext in variant_desc["extensions"]
            if ext.get("name") != "vep_annotation"
        ]

        # Add new VEP extension (schema-compliant structure)
        variant_desc["extensions"].append(
            {
                "name": "vep_annotation",  # Extension identifier
                "value": {
                    # Core VEP fields
                    "most_severe_consequence": vep_data.get("most_severe_consequence"),
                    "impact": vep_data.get("impact"),
                    "gene_symbol": vep_data.get("gene_symbol"),
                    # Pathogenicity scores
                    "cadd_score": vep_data.get("cadd_score"),
                    "polyphen_prediction": vep_data.get("polyphen_prediction"),
                    "polyphen_score": vep_data.get("polyphen_score"),
                    "sift_prediction": vep_data.get("sift_prediction"),
                    "sift_score": vep_data.get("sift_score"),
                    # Population frequency
                    "gnomad_af": vep_data.get("gnomad_af"),
                    "gnomad_af_nfe": vep_data.get("gnomad_af_nfe"),
                    # Metadata
                    "annotated_at": datetime.now().isoformat(),
                    "vep_version": vep_data.get("vep_version", "112"),
                    "assembly": vep_data.get("assembly", "GRCh38"),
                },
            }
        )

        return pk_data

    except (KeyError, IndexError) as e:
        print(f"    ⚠️  Error adding VEP to phenopacket: {e}")
        return pk_data


def has_vep_annotation(pk_data: Dict[str, Any]) -> bool:
    """Check if phenopacket already has VEP annotation.

    Args:
        pk_data: Phenopacket data dictionary

    Returns:
        True if VEP annotation exists
    """
    try:
        variant_desc = (
            pk_data["interpretations"][0]["diagnosis"]["genomicInterpretations"][0][
                "variantInterpretation"
            ]["variationDescriptor"]
        )
        extensions = variant_desc.get("extensions", [])
        return any(ext.get("name") == "vep_annotation" for ext in extensions)
    except (KeyError, IndexError):
        return False


async def main(dry_run: bool = False, limit: Optional[int] = None, force: bool = False):
    """Enrich all phenopackets with VEP annotations.

    Args:
        dry_run: If True, show what would be done without making changes
        limit: Maximum number of phenopackets to process (for testing)
        force: If True, re-annotate even if VEP annotation exists
    """
    validator = VariantValidator()

    enriched_count = 0
    failed_count = 0
    skipped_count = 0
    already_annotated = 0

    print("=" * 80)
    print("VEP Phenopacket Enrichment Script")
    print("=" * 80)
    print(f"Mode: {'DRY RUN' if dry_run else 'LIVE UPDATE'}")
    print(f"Force re-annotation: {force}")
    print(f"Limit: {limit if limit else 'No limit (all phenopackets)'}")
    print("=" * 80)
    print()

    async for db in get_db():
        # Get all phenopackets with variants
        query = """
            SELECT id, phenopacket
            FROM phenopackets
            WHERE phenopacket @> '{"interpretations": [{}]}'
            ORDER BY id
        """
        if limit:
            query += f" LIMIT {limit}"

        result = await db.execute(text(query))
        phenopackets = result.fetchall()

        print(f"Found {len(phenopackets)} phenopackets with interpretations")
        print()

        for pk_id, pk_data in phenopackets:
            # Parse JSONB to dict if needed
            if isinstance(pk_data, str):
                pk_data = json.loads(pk_data)

            # Extract variant VCF
            variant_vcf = extract_vcf_from_phenopacket(pk_data)

            if not variant_vcf:
                print(f"⏭️  {pk_id}: No variant found, skipping")
                skipped_count += 1
                continue

            # Check if already annotated
            if has_vep_annotation(pk_data) and not force:
                print(
                    f"✓  {pk_id}: Already annotated, skipping "
                    f"(use --force to re-annotate)"
                )
                already_annotated += 1
                continue

            # Annotate with VEP
            try:
                print(f"🔄 {pk_id}: Annotating {variant_vcf}...", end=" ", flush=True)

                if dry_run:
                    print("(DRY RUN - would annotate)")
                    enriched_count += 1
                    continue

                annotation = await validator.annotate_variant_with_vep(variant_vcf)

                # Handle case where annotation fails
                if annotation is None:
                    print("❌ Failed: No annotation returned")
                    failed_count += 1
                    continue

                # Add annotation to phenopacket
                pk_data_updated = add_vep_to_phenopacket(pk_data, annotation)

                # Update database
                await db.execute(
                    text(
                        """
                    UPDATE phenopackets
                    SET phenopacket = :phenopacket, updated_at = NOW()
                    WHERE id = :id
                """
                    ),
                    {"id": pk_id, "phenopacket": json.dumps(pk_data_updated)},
                )

                consequence = annotation.get("most_severe_consequence", "N/A")
                impact = annotation.get("impact", "N/A")
                cadd = annotation.get("cadd_score", "N/A")
                print(f"✅ {consequence} ({impact}) CADD: {cadd}")
                enriched_count += 1

                # Small delay to respect rate limits
                # (15 req/sec = ~67ms between requests)
                await asyncio.sleep(0.1)

            except Exception as e:
                print(f"❌ Failed: {str(e)[:100]}")
                failed_count += 1

        if not dry_run:
            await db.commit()
            print()
            print("💾 Changes committed to database")

        break

    print()
    print("=" * 80)
    print("ENRICHMENT SUMMARY")
    print("=" * 80)
    print(f"✅ Enriched: {enriched_count}")
    print(f"✓  Already annotated: {already_annotated}")
    print(f"⏭️  Skipped (no variant): {skipped_count}")
    print(f"❌ Failed: {failed_count}")
    print("=" * 80)

    if dry_run:
        print()
        print("ℹ️  This was a DRY RUN - no changes were made to the database")
        print("   Run without --dry-run to apply changes")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Enrich phenopackets with VEP annotations"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Maximum number of phenopackets to process (for testing)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-annotate even if VEP annotation already exists",
    )

    args = parser.parse_args()

    try:
        asyncio.run(main(dry_run=args.dry_run, limit=args.limit, force=args.force))
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
