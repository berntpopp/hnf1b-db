"""Reference genome data module.

Provides SQLAlchemy models, Pydantic schemas, and API endpoints for:
- Reference genomes (GRCh37, GRCh38, T2T-CHM13)
- Genes (HNF1B and chr17q12 region)
- Transcripts (RefSeq isoforms)
- Protein domains (UniProt/Pfam/InterPro)
- Exons (genomic coordinates)
"""

from app.reference.models import (
    Exon,
    Gene,
    ProteinDomain,
    ReferenceGenome,
    Transcript,
)

__all__ = [
    "ReferenceGenome",
    "Gene",
    "Transcript",
    "Exon",
    "ProteinDomain",
]
