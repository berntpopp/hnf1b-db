"""Gene structure import module."""

from typing import List, Tuple

import requests

from app.database import get_db
from app.models import Gene


def fetch_gene_data(symbol: str, server_url: str) -> dict:
    """Fetch the expanded gene record for the given symbol from the specified server.

    Uses the Ensembl REST API to fetch gene data.
    """
    url = f"{server_url}/lookup/symbol/homo_sapiens/{symbol}?expand=1"
    headers = {"Content-Type": "application/json"}
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    data = response.json()
    return data


def extract_canonical_transcript_exons(gene_data: dict) -> Tuple[str, List[dict]]:
    """Extract canonical transcript and exons from gene data.

    Given a gene record (from the lookup endpoint), find the canonical transcript and
    return its id along with a list of its exons. Each exon is formatted as a dict with
    keys: exon_number, start, and stop.
    """
    transcripts = gene_data.get("Transcript", [])
    canonical_exons = []
    transcript_id = None

    for transcript in transcripts:
        if transcript.get("is_canonical") == 1:
            transcript_id = transcript.get("id")
            exons = transcript.get("Exon", [])
            canonical_exons = exons
            break

    if not canonical_exons and transcripts:
        transcript = transcripts[0]
        transcript_id = transcript.get("id")
        canonical_exons = transcript.get("Exon", [])

    formatted_exons = []
    canonical_exons.sort(key=lambda x: x.get("start", 0))

    for i, exon in enumerate(canonical_exons):
        formatted_exons.append(
            {
                "exon_number": i + 1,
                "start": exon.get("start"),
                "stop": exon.get("end"),
            }
        )

    return transcript_id, formatted_exons


def fetch_gene_structure_from_symbol(symbol: str = "HNF1B") -> dict:
    """Fetch gene structure for the given gene symbol from both GRCh38 and GRCh37.

    Returns a gene document that includes:
      - gene_symbol (display_name)
      - ensembl_gene_id
      - transcript (canonical transcript id)
      - exons (from GRCh38, as default)
      - hg38: { "exons": [...] }
      - hg19: { "exons": [...] }
    """
    server_hg38 = "https://rest.ensembl.org"
    gene_data_hg38 = fetch_gene_data(symbol, server_hg38)
    transcript_hg38, exons_hg38 = extract_canonical_transcript_exons(gene_data_hg38)

    server_hg19 = "https://grch37.rest.ensembl.org"
    gene_data_hg19 = fetch_gene_data(symbol, server_hg19)
    _, exons_hg19 = extract_canonical_transcript_exons(gene_data_hg19)

    gene_document = {
        "gene_symbol": gene_data_hg38.get("display_name", symbol),
        "ensembl_gene_id": gene_data_hg38.get("id"),
        "transcript": transcript_hg38,
        "exons": exons_hg38,
        "hg38": {"exons": exons_hg38},
        "hg19": {"exons": exons_hg19},
    }
    return gene_document


async def import_genes(test_mode: bool = False):
    """Import genomic structure for the HNF1B gene using the Ensembl lookup endpoint.

    The function fetches gene data for both GRCh38 and GRCh37 (hg19) and builds a gene
    document that includes exon coordinates from the canonical transcript.
    """
    print("[import_genes] Starting gene structure import...")

    if test_mode:
        await create_test_genes()
        return

    try:
        gene_document = fetch_gene_structure_from_symbol("HNF1B")
    except Exception as e:
        print(f"[import_genes] Error fetching gene structure from Ensembl: {e}")
        print("[import_genes] Falling back to test data...")
        await create_test_genes()
        return

    async for db_session in get_db():
        # Clear existing genes
        from sqlalchemy import text

        await db_session.execute(text("DELETE FROM genes"))

        # Create gene document
        gene_obj = Gene(
            gene_symbol=gene_document["gene_symbol"],
            ensembl_gene_id=gene_document["ensembl_gene_id"],
            transcript=gene_document["transcript"],
            exons=gene_document["exons"],
            hg38=gene_document["hg38"],
            hg19=gene_document["hg19"],
        )

        db_session.add(gene_obj)
        await db_session.commit()

        print(
            f"[import_genes] Successfully imported gene structure for {gene_document['gene_symbol']}"
        )
        break


async def create_test_genes():
    """Create test gene data for API testing."""
    print("[create_test_genes] Creating test gene structure data...")

    # Realistic HNF1B gene structure data
    test_exons_hg38 = [
        {"exon_number": 1, "start": 36080373, "stop": 36080544},
        {"exon_number": 2, "start": 36101028, "stop": 36101240},
        {"exon_number": 3, "start": 36104467, "stop": 36104663},
        {"exon_number": 4, "start": 36105936, "stop": 36106107},
        {"exon_number": 5, "start": 36106791, "stop": 36106961},
        {"exon_number": 6, "start": 36109424, "stop": 36109523},
        {"exon_number": 7, "start": 36113000, "stop": 36113136},
        {"exon_number": 8, "start": 36115487, "stop": 36115622},
        {"exon_number": 9, "start": 36116499, "stop": 36118143},
    ]

    test_exons_hg19 = [
        {"exon_number": 1, "start": 36047273, "stop": 36047444},
        {"exon_number": 2, "start": 36067928, "stop": 36068140},
        {"exon_number": 3, "start": 36071367, "stop": 36071563},
        {"exon_number": 4, "start": 36072836, "stop": 36073007},
        {"exon_number": 5, "start": 36073691, "stop": 36073861},
        {"exon_number": 6, "start": 36076324, "stop": 36076423},
        {"exon_number": 7, "start": 36079900, "stop": 36080036},
        {"exon_number": 8, "start": 36082387, "stop": 36082522},
        {"exon_number": 9, "start": 36083399, "stop": 36085043},
    ]

    async for db_session in get_db():
        # Clear existing genes
        from sqlalchemy import text

        await db_session.execute(text("DELETE FROM genes"))

        # Create test gene
        gene_obj = Gene(
            gene_symbol="HNF1B",
            ensembl_gene_id="ENSG00000275410",
            transcript="ENST00000257555",
            exons=test_exons_hg38,  # Default to hg38
            hg38={"exons": test_exons_hg38},
            hg19={"exons": test_exons_hg19},
        )

        db_session.add(gene_obj)
        await db_session.commit()

        print("[create_test_genes] Successfully created test gene structure")
        break
