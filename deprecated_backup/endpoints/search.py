# File: app/endpoints/search.py
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import (
    Gene,
    Individual,
    Protein,
    Publication,
    Variant,
    VariantAnnotation,
    VariantClassification,
)

router = APIRouter()


async def search_individuals(
    db: AsyncSession, query: str, reduce_doc: bool = True
) -> List[Dict[str, Any]]:
    """Search individuals by individual_id, sex, identifier, etc."""
    search_query = select(Individual).where(
        or_(
            Individual.individual_id.ilike(f"%{query}%"),
            Individual.sex.ilike(f"%{query}%"),
            Individual.individual_identifier.ilike(f"%{query}%"),
            Individual.dup_check.ilike(f"%{query}%"),
        )
    )

    result = await db.execute(search_query)
    individuals = result.scalars().all()

    results = []
    for individual in individuals:
        if reduce_doc:
            # Minimal response
            item = {
                "_id": str(individual.id),
                "individual_id": individual.individual_id,
                "collection": "individuals",
                "matched_fields": {
                    "individual_id": individual.individual_id,
                    "sex": individual.sex,
                    "individual_identifier": individual.individual_identifier,
                },
            }
        else:
            # Full response
            item = {
                "_id": str(individual.id),
                "individual_id": individual.individual_id,
                "collection": "individuals",
                "sex": individual.sex,
                "individual_doi": individual.individual_doi,
                "dup_check": individual.dup_check,
                "individual_identifier": individual.individual_identifier,
                "problematic": individual.problematic,
                "created_at": individual.created_at.isoformat()
                if individual.created_at
                else None,
            }
        results.append(item)

    return results


async def search_variants(
    db: AsyncSession, query: str, reduce_doc: bool = True
) -> List[Dict[str, Any]]:
    """Search variants by variant_id, genomic coordinates, annotations, etc."""
    # Search in variants and related annotations/classifications
    variant_query = select(Variant).where(
        or_(
            Variant.variant_id.ilike(f"%{query}%"),
            Variant.variant_type.ilike(f"%{query}%"),
            Variant.hg19.ilike(f"%{query}%"),
            Variant.hg38.ilike(f"%{query}%"),
        )
    )

    # Also search in annotations
    annotation_query = (
        select(Variant)
        .join(VariantAnnotation)
        .where(
            or_(
                VariantAnnotation.transcript.ilike(f"%{query}%"),
                VariantAnnotation.c_dot.ilike(f"%{query}%"),
                VariantAnnotation.p_dot.ilike(f"%{query}%"),
                VariantAnnotation.impact.ilike(f"%{query}%"),
                VariantAnnotation.effect.ilike(f"%{query}%"),
            )
        )
    )

    # Also search in classifications
    classification_query = (
        select(Variant)
        .join(VariantClassification)
        .where(
            or_(
                VariantClassification.verdict.ilike(f"%{query}%"),
                VariantClassification.criteria.ilike(f"%{query}%"),
                VariantClassification.system.ilike(f"%{query}%"),
            )
        )
    )

    # Combine all variant searches
    all_variants = set()

    for search_query in [variant_query, annotation_query, classification_query]:
        try:
            result = await db.execute(search_query)
            variants = result.scalars().all()
            all_variants.update(variants)
        except Exception:
            # Skip if join fails
            continue

    results = []
    for variant in all_variants:
        if reduce_doc:
            # Minimal response
            item = {
                "_id": str(variant.id),
                "variant_id": variant.variant_id,
                "collection": "variants",
                "matched_fields": {
                    "variant_id": variant.variant_id,
                    "variant_type": variant.variant_type,
                    "hg19": variant.hg19,
                    "hg38": variant.hg38,
                },
            }
        else:
            # Full response
            item = {
                "_id": str(variant.id),
                "variant_id": variant.variant_id,
                "collection": "variants",
                "variant_type": variant.variant_type,
                "hg19": variant.hg19,
                "hg38": variant.hg38,
                "hg19_info": variant.hg19_info,
                "hg38_info": variant.hg38_info,
                "is_current": variant.is_current,
                "created_at": variant.created_at.isoformat()
                if variant.created_at
                else None,
            }
        results.append(item)

    return results


async def search_publications(
    db: AsyncSession, query: str, reduce_doc: bool = True
) -> List[Dict[str, Any]]:
    """Search publications by publication_id, DOI, PMID, title, etc."""
    # Build search conditions
    search_conditions = [
        Publication.publication_id.ilike(f"%{query}%"),
        Publication.doi.ilike(f"%{query}%"),
        Publication.title.ilike(f"%{query}%"),
        Publication.abstract.ilike(f"%{query}%"),
        Publication.journal.ilike(f"%{query}%"),
        Publication.publication_alias.ilike(f"%{query}%"),
    ]

    # Add PMID search if query is numeric
    try:
        pmid_value = int(query)
        search_conditions.append(Publication.pmid == pmid_value)
    except ValueError:
        # Query is not numeric, skip PMID search
        pass

    search_query = select(Publication).where(or_(*search_conditions))

    result = await db.execute(search_query)
    publications = result.scalars().all()

    results = []
    for publication in publications:
        if reduce_doc:
            # Minimal response
            item = {
                "_id": str(publication.id),
                "publication_id": publication.publication_id,
                "collection": "publications",
                "matched_fields": {
                    "publication_id": publication.publication_id,
                    "doi": publication.doi,
                    "pmid": publication.pmid,
                    "title": publication.title,
                },
            }
        else:
            # Full response
            item = {
                "_id": str(publication.id),
                "publication_id": publication.publication_id,
                "collection": "publications",
                "publication_type": publication.publication_type,
                "title": publication.title,
                "abstract": publication.abstract,
                "doi": publication.doi,
                "pmid": publication.pmid,
                "journal": publication.journal,
                "publication_alias": publication.publication_alias,
                "created_at": publication.created_at.isoformat()
                if publication.created_at
                else None,
            }
        results.append(item)

    return results


async def search_genes(
    db: AsyncSession, query: str, reduce_doc: bool = True
) -> List[Dict[str, Any]]:
    """Search genes by gene_symbol, ensembl_gene_id, transcript, etc."""
    search_query = select(Gene).where(
        or_(
            Gene.gene_symbol.ilike(f"%{query}%"),
            Gene.ensembl_gene_id.ilike(f"%{query}%"),
            Gene.transcript.ilike(f"%{query}%"),
        )
    )

    result = await db.execute(search_query)
    genes = result.scalars().all()

    results = []
    for gene in genes:
        if reduce_doc:
            # Minimal response
            item = {
                "_id": str(gene.id),
                "gene_symbol": gene.gene_symbol,
                "collection": "genes",
                "matched_fields": {
                    "gene_symbol": gene.gene_symbol,
                    "ensembl_gene_id": gene.ensembl_gene_id,
                    "transcript": gene.transcript,
                },
            }
        else:
            # Full response
            item = {
                "_id": str(gene.id),
                "gene_symbol": gene.gene_symbol,
                "collection": "genes",
                "ensembl_gene_id": gene.ensembl_gene_id,
                "transcript": gene.transcript,
                "exons": gene.exons,
                "hg38": gene.hg38,
                "hg19": gene.hg19,
                "created_at": gene.created_at.isoformat() if gene.created_at else None,
            }
        results.append(item)

    return results


async def search_proteins(
    db: AsyncSession, query: str, reduce_doc: bool = True
) -> List[Dict[str, Any]]:
    """Search proteins by gene, transcript, protein, etc."""
    search_query = select(Protein).where(
        or_(
            Protein.gene.ilike(f"%{query}%"),
            Protein.transcript.ilike(f"%{query}%"),
            Protein.protein.ilike(f"%{query}%"),
        )
    )

    result = await db.execute(search_query)
    proteins = result.scalars().all()

    results = []
    for protein in proteins:
        if reduce_doc:
            # Minimal response
            item = {
                "_id": str(protein.id),
                "gene": protein.gene,
                "collection": "proteins",
                "matched_fields": {
                    "gene": protein.gene,
                    "transcript": protein.transcript,
                    "protein": protein.protein,
                },
            }
        else:
            # Full response
            item = {
                "_id": str(protein.id),
                "gene": protein.gene,
                "collection": "proteins",
                "transcript": protein.transcript,
                "protein": protein.protein,
                "features": protein.features,
                "created_at": protein.created_at.isoformat()
                if protein.created_at
                else None,
            }
        results.append(item)

    return results


@router.get(
    "/",
    response_model=Dict[str, Any],
    summary="Search across Individuals, Variants, Publications, Genes, and Proteins",
)
async def search_documents(
    request: Request,
    db: AsyncSession = Depends(get_db),
    q: str = Query(..., description="Search query string"),
    collection: Optional[str] = Query(
        None,
        description=(
            "Optional: Limit search to a specific collection. Allowed values: "
            "'individuals', 'variants', 'publications', 'genes', or 'proteins'."
        ),
    ),
    reduce_doc: bool = Query(
        True,
        description=(
            "If true, only return minimal info for each matching document: "
            "the _id, the identifier field (individual_id, variant_id, or "
            "publication_id), "
            "and a dictionary of matched field values."
        ),
    ),
) -> Dict[str, Any]:
    """Cross-collection search functionality.

    Searches across individuals, variants, publications, genes, and proteins.
    """
    try:
        results = []

        # Validate collection parameter
        valid_collections = [
            "individuals",
            "variants",
            "publications",
            "genes",
            "proteins",
        ]
        if collection and collection not in valid_collections:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Invalid collection '{collection}'. "
                    f"Must be one of: {', '.join(valid_collections)}"
                ),
            )

        # Search in specific collection or all collections
        if not collection or collection == "individuals":
            individuals_results = await search_individuals(db, q, reduce_doc)
            results.extend(individuals_results)

        if not collection or collection == "variants":
            variants_results = await search_variants(db, q, reduce_doc)
            results.extend(variants_results)

        if not collection or collection == "publications":
            publications_results = await search_publications(db, q, reduce_doc)
            results.extend(publications_results)

        if not collection or collection == "genes":
            genes_results = await search_genes(db, q, reduce_doc)
            results.extend(genes_results)

        if not collection or collection == "proteins":
            proteins_results = await search_proteins(db, q, reduce_doc)
            results.extend(proteins_results)

        # Build response
        response = {
            "query": q,
            "collection": collection or "all",
            "reduce_doc": reduce_doc,
            "total_results": len(results),
            "results": results,
        }

        # Add collection-specific counts
        if not collection:
            counts = {}
            for result in results:
                coll = result.get("collection", "unknown")
                counts[coll] = counts.get(coll, 0) + 1
            response["counts_by_collection"] = counts

        return response

    except HTTPException:
        raise
    except Exception as e:
        print(f"Search error: {e}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")
