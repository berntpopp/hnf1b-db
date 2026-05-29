"""Tests for hnf1b_mcp.services.reference – get_gene_context."""

from __future__ import annotations

import httpx
import pytest
import respx

from hnf1b_mcp.client.api_client import ApiClient
from hnf1b_mcp.services.reference import get_gene_context

BASE = "http://api.test/api/v2"

# ---------------------------------------------------------------------------
# Shared fixture data
# ---------------------------------------------------------------------------

GENE_PAYLOAD = {
    "symbol": "HNF1B",
    "name": "HNF1 homeobox B",
    "chromosome": "17",
    "start": 37685262,
    "end": 37732497,
    "strand": "+",
    "ensembl_id": "ENSG00000275410",
    "ncbi_gene_id": "6928",
    "hgnc_id": "HGNC:11617",
    "omim_id": "189907",
    "transcripts": ["ENST00000372566"],
}

TRANSCRIPTS_PAYLOAD = [
    {
        "transcript_id": "ENST00000372566",
        "biotype": "protein_coding",
        "length": 2672,
    },
    {
        "transcript_id": "ENST00000372567",
        "biotype": "protein_coding",
        "length": 1500,
    },
]

DOMAINS_PAYLOAD = {
    "gene": "HNF1B",
    "protein": "HNF-1-beta",
    "uniprot": "P35680",
    "length": 557,
    "domains": [
        {
            "name": "Dimerisation domain",
            "short_name": "DIM",
            "start": 1,
            "end": 32,
            "pfam_id": "PF04812",
            "interpro_id": "IPR006701",
            "uniprot_id": "P35680",
            "function": "Homodimerisation and heterodimerisation with HNF1A",
        },
        {
            "name": "POU-specific domain",
            "short_name": "POUs",
            "start": 88,
            "end": 172,
            "pfam_id": "PF00157",
            "interpro_id": "IPR013116",
            "uniprot_id": "P35680",
            "function": "DNA binding",
        },
    ],
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_all(symbol: str = "HNF1B") -> None:
    """Register respx mocks for the three HNF1B endpoints."""
    respx.get(f"{BASE}/reference/genes/{symbol}").mock(
        return_value=httpx.Response(200, json=GENE_PAYLOAD)
    )
    respx.get(f"{BASE}/reference/genes/{symbol}/transcripts").mock(
        return_value=httpx.Response(200, json=TRANSCRIPTS_PAYLOAD)
    )
    respx.get(f"{BASE}/reference/genes/{symbol}/domains").mock(
        return_value=httpx.Response(200, json=DOMAINS_PAYLOAD)
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_full_context_shape() -> None:
    """All three endpoints are called; result contains expected keys/values."""
    _mock_all()
    c = ApiClient(base_url=BASE)
    result = await get_gene_context(c)
    await c.aclose()

    # gene block
    assert result["gene"]["symbol"] == "HNF1B"
    assert result["gene"]["chromosome"] == "17"
    assert result["gene"]["ensembl_id"] == "ENSG00000275410"
    assert result["gene"]["ncbi_gene_id"] == "6928"
    assert result["gene"]["hgnc_id"] == "HGNC:11617"
    assert result["gene"]["omim_id"] == "189907"

    # transcripts
    assert "transcripts" in result
    assert len(result["transcripts"]) == 2
    assert result["transcripts"][0]["transcript_id"] == "ENST00000372566"

    # domains
    assert "domains" in result
    assert len(result["domains"]) == 2
    assert result["domains"][0]["name"] == "Dimerisation domain"
    assert result["domains"][1]["pfam_id"] == "PF00157"

    # URI
    assert result["uri"] == "hnf1b://gene/HNF1B"


@pytest.mark.asyncio
@respx.mock
async def test_uri_reflects_gene_symbol() -> None:
    """Uri uses the gene_symbol argument, not a hardcoded string."""
    symbol = "HNF1A"
    respx.get(f"{BASE}/reference/genes/{symbol}").mock(
        return_value=httpx.Response(200, json={**GENE_PAYLOAD, "symbol": symbol})
    )
    respx.get(f"{BASE}/reference/genes/{symbol}/transcripts").mock(
        return_value=httpx.Response(200, json=TRANSCRIPTS_PAYLOAD)
    )
    respx.get(f"{BASE}/reference/genes/{symbol}/domains").mock(
        return_value=httpx.Response(200, json=DOMAINS_PAYLOAD)
    )
    c = ApiClient(base_url=BASE)
    result = await get_gene_context(c, gene_symbol=symbol)
    await c.aclose()

    assert result["uri"] == f"hnf1b://gene/{symbol}"
    assert result["gene"]["symbol"] == symbol


@pytest.mark.asyncio
@respx.mock
async def test_include_domains_false_omits_domains_key() -> None:
    """When include_domains=False, 'domains' key must not appear in the result."""
    # Only the gene and transcripts endpoints should be called.
    respx.get(f"{BASE}/reference/genes/HNF1B").mock(
        return_value=httpx.Response(200, json=GENE_PAYLOAD)
    )
    respx.get(f"{BASE}/reference/genes/HNF1B/transcripts").mock(
        return_value=httpx.Response(200, json=TRANSCRIPTS_PAYLOAD)
    )
    # Deliberately do NOT register a mock for domains so that any call to it
    # raises a ConnectionError from respx – which would fail the test.

    c = ApiClient(base_url=BASE)
    result = await get_gene_context(c, include_domains=False)
    await c.aclose()

    assert "domains" not in result
    assert "transcripts" in result
    assert result["gene"]["symbol"] == "HNF1B"


@pytest.mark.asyncio
@respx.mock
async def test_include_transcripts_false_omits_transcripts_key() -> None:
    """When include_transcripts=False, 'transcripts' key must not appear."""
    respx.get(f"{BASE}/reference/genes/HNF1B").mock(
        return_value=httpx.Response(200, json=GENE_PAYLOAD)
    )
    respx.get(f"{BASE}/reference/genes/HNF1B/domains").mock(
        return_value=httpx.Response(200, json=DOMAINS_PAYLOAD)
    )

    c = ApiClient(base_url=BASE)
    result = await get_gene_context(c, include_transcripts=False)
    await c.aclose()

    assert "transcripts" not in result
    assert "domains" in result


@pytest.mark.asyncio
@respx.mock
async def test_genome_build_passed_as_query_param() -> None:
    """genome_build is forwarded as a query param to all relevant endpoints."""
    build = "GRCh37"

    respx.get(f"{BASE}/reference/genes/HNF1B").mock(
        return_value=httpx.Response(200, json=GENE_PAYLOAD)
    )
    respx.get(f"{BASE}/reference/genes/HNF1B/transcripts").mock(
        return_value=httpx.Response(200, json=TRANSCRIPTS_PAYLOAD)
    )
    respx.get(f"{BASE}/reference/genes/HNF1B/domains").mock(
        return_value=httpx.Response(200, json=DOMAINS_PAYLOAD)
    )

    c = ApiClient(base_url=BASE)
    result = await get_gene_context(c, genome_build=build)
    await c.aclose()

    # Verify the gene endpoint received the genome_build param
    gene_request = respx.calls[0].request
    assert "genome_build=GRCh37" in str(gene_request.url)
    assert result["uri"] == "hnf1b://gene/HNF1B"


@pytest.mark.asyncio
@respx.mock
async def test_both_flags_false_returns_gene_only() -> None:
    """When both include_transcripts and include_domains are False, only gene block returned."""
    respx.get(f"{BASE}/reference/genes/HNF1B").mock(
        return_value=httpx.Response(200, json=GENE_PAYLOAD)
    )

    c = ApiClient(base_url=BASE)
    result = await get_gene_context(c, include_transcripts=False, include_domains=False)
    await c.aclose()

    assert "transcripts" not in result
    assert "domains" not in result
    assert result["gene"]["symbol"] == "HNF1B"
    assert result["uri"] == "hnf1b://gene/HNF1B"


@pytest.mark.asyncio
@respx.mock
async def test_unseeded_reference_data_is_disclosed() -> None:
    """Empty transcripts/domains + null xrefs surface a data-status note."""
    symbol = "HNF1B"
    respx.get(f"{BASE}/reference/genes/{symbol}").mock(
        return_value=httpx.Response(
            200,
            json={
                "symbol": symbol,
                "name": "HNF1 homeobox B",
                "chromosome": "17",
                "hgnc_id": None,
                "ncbi_gene_id": None,
                "omim_id": None,
                "transcripts": [],
            },
        )
    )
    respx.get(f"{BASE}/reference/genes/{symbol}/transcripts").mock(
        return_value=httpx.Response(200, json=[])
    )
    respx.get(f"{BASE}/reference/genes/{symbol}/domains").mock(
        return_value=httpx.Response(200, json={"domains": []})
    )
    c = ApiClient(base_url=BASE)
    result = await get_gene_context(c)
    await c.aclose()

    assert "reference_data_status" in result
    note = result["reference_data_status"]
    assert "transcripts" in note and "domains" in note and "cross_references" in note
    # The note must NOT claim none exist — it must point at seeding.
    assert "unseeded" in note
