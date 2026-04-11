"""Reference data service sub-package.

Split from the old 722-LOC flat module during Wave 4. The public
import path is unchanged::

    from app.reference.service import (
        initialize_reference_data,
        sync_chr17q12_genes,
        get_reference_data_status,
        SyncResult,
        ReferenceDataStatus,
    )

Submodules:

- ``constants``        — HNF1B domain + exon data, Ensembl URLs
- ``types``            — ``SyncResult`` / ``ReferenceDataStatus`` dataclasses
- ``hnf1b_importer``   — HNF1B bootstrap (gene, transcript, exons, domains)
- ``ensembl_sync``     — chr17q12 region sync from the Ensembl REST API
- ``status``           — ``get_reference_data_status`` query
"""

from .constants import (
    CHR17Q12_REGION,
    ENSEMBL_API_BASE,
    ENSEMBL_RATE_LIMIT_DELAY,
    HNF1B_DOMAINS,
    HNF1B_EXONS,
    VALID_BIOTYPES,
)
from .ensembl_sync import (
    fetch_genes_from_ensembl,
    parse_gene_from_ensembl,
    sync_chr17q12_genes,
)
from .hnf1b_importer import (
    get_gene_by_symbol,
    get_genome_by_name,
    get_or_create_grch38_genome,
    import_hnf1b_domains,
    import_hnf1b_exons,
    import_hnf1b_gene,
    import_hnf1b_transcript,
    initialize_reference_data,
)
from .status import get_reference_data_status
from .types import ReferenceDataStatus, SyncResult

__all__ = [
    # Types
    "SyncResult",
    "ReferenceDataStatus",
    # Constants
    "HNF1B_DOMAINS",
    "HNF1B_EXONS",
    "ENSEMBL_API_BASE",
    "CHR17Q12_REGION",
    "ENSEMBL_RATE_LIMIT_DELAY",
    "VALID_BIOTYPES",
    # HNF1B importer
    "initialize_reference_data",
    "get_or_create_grch38_genome",
    "get_genome_by_name",
    "get_gene_by_symbol",
    "import_hnf1b_gene",
    "import_hnf1b_transcript",
    "import_hnf1b_exons",
    "import_hnf1b_domains",
    # Ensembl sync
    "fetch_genes_from_ensembl",
    "parse_gene_from_ensembl",
    "sync_chr17q12_genes",
    # Status
    "get_reference_data_status",
]
