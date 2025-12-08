#!/usr/bin/env python3
"""Helper functions for docker-entrypoint.sh.

This module provides database query functions that are called from the
entrypoint script, avoiding complex shell escaping for SQL queries.
"""

import asyncio
import sys

from sqlalchemy import text

from app.database import async_session_maker


async def count_phenopackets() -> int:
    """Count total phenopackets in database."""
    async with async_session_maker() as session:
        result = await session.execute(
            text("SELECT COUNT(*) FROM phenopackets WHERE deleted_at IS NULL")
        )
        return result.scalar() or 0


async def count_publication_metadata() -> int:
    """Count cached publication metadata entries."""
    async with async_session_maker() as session:
        result = await session.execute(
            text("SELECT COUNT(*) FROM publication_metadata")
        )
        return result.scalar() or 0


async def count_unique_pmids() -> int:
    """Count unique PMIDs referenced in phenopackets."""
    async with async_session_maker() as session:
        result = await session.execute(
            text("""
                SELECT COUNT(DISTINCT REPLACE(ext_ref->>'id', 'PMID:', ''))
                FROM phenopackets,
                     jsonb_array_elements(
                         phenopacket->'metaData'->'externalReferences'
                     ) as ext_ref
                WHERE ext_ref->>'id' LIKE 'PMID:%'
                  AND deleted_at IS NULL
            """)
        )
        return result.scalar() or 0


async def count_variant_annotations() -> int:
    """Count cached variant annotations."""
    async with async_session_maker() as session:
        result = await session.execute(
            text("SELECT COUNT(*) FROM variant_annotations")
        )
        return result.scalar() or 0


async def count_unique_variants() -> int:
    """Count unique VCF variants in phenopackets."""
    async with async_session_maker() as session:
        result = await session.execute(
            text("""
                SELECT COUNT(DISTINCT expr->>'value')
                FROM phenopackets,
                     jsonb_array_elements(
                         phenopacket->'interpretations'
                     ) as interp,
                     jsonb_array_elements(
                         interp->'diagnosis'->'genomicInterpretations'
                     ) as gi,
                     jsonb_array_elements(
                         gi->'variantInterpretation'
                           ->'variationDescriptor'->'expressions'
                     ) as expr
                WHERE expr->>'syntax' = 'vcf'
                  AND deleted_at IS NULL
            """)
        )
        return result.scalar() or 0


async def count_chr17q12_genes() -> int:
    """Count genes in chr17q12 region."""
    async with async_session_maker() as session:
        result = await session.execute(
            text("""
                SELECT COUNT(*)
                FROM genes
                WHERE chromosome = '17'
                  AND start_position >= 36000000
                  AND end_position <= 39900000
            """)
        )
        return result.scalar() or 0


async def count_genomes(assembly_name: str = "GRCh38") -> int:
    """Count genomes with given assembly name."""
    async with async_session_maker() as session:
        result = await session.execute(
            text("SELECT COUNT(*) FROM genomes WHERE assembly_name = :name"),
            {"name": assembly_name},
        )
        return result.scalar() or 0


COMMANDS = {
    "phenopackets": count_phenopackets,
    "publication_metadata": count_publication_metadata,
    "pmids": count_unique_pmids,
    "variant_annotations": count_variant_annotations,
    "variants": count_unique_variants,
    "chr17q12_genes": count_chr17q12_genes,
    "genomes": count_genomes,
}


def main():
    """CLI entry point."""
    if len(sys.argv) < 2:
        print("Usage: python -m scripts.entrypoint_helpers <command>", file=sys.stderr)
        print(f"Commands: {', '.join(COMMANDS.keys())}", file=sys.stderr)
        sys.exit(1)

    command = sys.argv[1]
    if command not in COMMANDS:
        print(f"Unknown command: {command}", file=sys.stderr)
        print(f"Available: {', '.join(COMMANDS.keys())}", file=sys.stderr)
        sys.exit(1)

    try:
        result = asyncio.run(COMMANDS[command]())
        print(result)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        print("0")  # Default to 0 on error


if __name__ == "__main__":
    main()
