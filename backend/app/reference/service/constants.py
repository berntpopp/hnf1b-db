"""Reference data constants (HNF1B domains, exons, Ensembl URLs).

Extracted during Wave 4 from the monolithic ``reference/service.py``.
"""

from __future__ import annotations

# Ensembl REST API settings
ENSEMBL_API_BASE = "https://rest.ensembl.org"
CHR17Q12_REGION = "17:36000000-39900000"
ENSEMBL_RATE_LIMIT_DELAY = 0.1  # 10 req/sec

# Valid biotypes to import (exclude pseudogenes)
VALID_BIOTYPES = ["protein_coding", "lncRNA", "miRNA", "snRNA", "snoRNA"]

# HNF1B protein domains from UniProt P35680 (verified 2025-01-17)
HNF1B_DOMAINS = [
    {
        "name": "Dimerization Domain",
        "short_name": "Dim",
        "start": 1,
        "end": 31,
        "function": "Mediates homodimer or heterodimer formation",
        "source": "UniProt",
        "uniprot_id": "P35680",
    },
    {
        "name": "POU-Specific Domain",
        "short_name": "POU-S",
        "start": 8,
        "end": 173,
        "function": "DNA binding (part 1)",
        "pfam_id": "PF00157",
        "interpro_id": "IPR000327",
        "source": "UniProt",
        "uniprot_id": "P35680",
    },
    {
        "name": "POU Homeodomain",
        "short_name": "POU-H",
        "start": 232,
        "end": 305,
        "function": "DNA binding (part 2)",
        "interpro_id": "IPR001356",
        "source": "UniProt",
        "uniprot_id": "P35680",
    },
    {
        "name": "Transactivation Domain",
        "short_name": "TAD",
        "start": 314,
        "end": 557,
        "function": "Transcriptional activation",
        "source": "UniProt",
        "uniprot_id": "P35680",
    },
]

# HNF1B exon data (fallback if chr17q12_genes.json not found)
HNF1B_EXONS = [
    {"number": 1, "start": 36098063, "end": 36098372},
    {"number": 2, "start": 36099035, "end": 36099371},
    {"number": 3, "start": 36102283, "end": 36102437},
    {"number": 4, "start": 36103407, "end": 36103619},
    {"number": 5, "start": 36104458, "end": 36104588},
    {"number": 6, "start": 36105361, "end": 36105505},
    {"number": 7, "start": 36106626, "end": 36106784},
    {"number": 8, "start": 36108060, "end": 36108311},
    {"number": 9, "start": 36111731, "end": 36112306},
]
