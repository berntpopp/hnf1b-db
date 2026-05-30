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

# Mirrors the live /reference/genes/{symbol} shape: an internal row ``id``
# (UUID), ``created_at``/``updated_at`` timestamps, and a NESTED ``transcripts``
# block that duplicates the standalone /transcripts endpoint (the duplicate the
# scorecard flagged).
GENE_PAYLOAD = {
    "id": "a09c8191-b0d5-4828-af87-042ddd7de013",
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
    "source": "Ensembl REST API",
    "source_version": "GRCh38",
    "created_at": "2026-04-17T09:48:44.742052Z",
    "updated_at": "2026-05-30T08:45:48.940076Z",
    "transcripts": [
        {
            "id": "799a1ceb-38a3-4f81-a158-1c086e7ee07a",
            "transcript_id": "ENST00000372566",
            "is_canonical": True,
            "exon_count": 9,
            "created_at": "2026-05-30T08:45:48.940076Z",
            "updated_at": "2026-05-30T08:45:48.940076Z",
        }
    ],
}

# Each transcript carries an internal ``id`` (UUID), ``created_at``/``updated_at``
# timestamps, an ``exon_count`` scalar, and a full ``exons`` array (each exon also
# has its own UUID ``id``). The first transcript is intentionally duplicated to
# exercise dedupe-by-transcript_id.
_EXONS = [
    {
        "id": "213003b6-2b0c-4d1d-b123-354f18afa16b",
        "exon_number": 1,
        "chromosome": "17",
        "start": 36098063,
        "end": 36098372,
    },
    {
        "id": "833ce028-0309-4086-a53d-950cdcba5289",
        "exon_number": 2,
        "chromosome": "17",
        "start": 36099035,
        "end": 36099371,
    },
]

_TX_CANONICAL = {
    "id": "799a1ceb-38a3-4f81-a158-1c086e7ee07a",
    "transcript_id": "ENST00000372566",
    "protein_id": "NP_000449.3",
    "is_canonical": True,
    "exon_count": 2,
    "source": "RefSeq",
    "created_at": "2026-05-30T08:45:48.940076Z",
    "updated_at": "2026-05-30T08:45:48.940076Z",
    "exons": _EXONS,
}

TRANSCRIPTS_PAYLOAD = [
    _TX_CANONICAL,
    # Exact duplicate of the canonical transcript (same transcript_id) — the
    # service must collapse this to a single entry.
    dict(_TX_CANONICAL),
    {
        "id": "b1234567-0000-0000-0000-000000000000",
        "transcript_id": "ENST00000372567",
        "is_canonical": False,
        "exon_count": 0,
        "source": "RefSeq",
        "created_at": "2026-05-30T08:45:48.940076Z",
        "updated_at": "2026-05-30T08:45:48.940076Z",
        "exons": [],
    },
]

DOMAINS_PAYLOAD = {
    "gene": "HNF1B",
    "protein": "HNF-1-beta",
    "uniprot": "P35680",
    "length": 557,
    "domains": [
        {
            "id": "c675793b-165a-4b25-97f0-b05733c0c591",
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
            "id": "fbecabf9-1f6e-4178-a869-cb83db52f32d",
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


# ---------------------------------------------------------------------------
# Token-discipline: noise stripping, transcript dedupe, exon gating
# ---------------------------------------------------------------------------

_NOISE_KEYS = {"id", "created_at", "updated_at"}


@pytest.mark.asyncio
@respx.mock
@pytest.mark.parametrize("mode", ["compact", "standard"])
async def test_llm_modes_strip_internal_noise(mode: str) -> None:
    """compact/standard carry NO UUIDs and NO created_at/updated_at anywhere."""
    _mock_all()
    c = ApiClient(base_url=BASE)
    result = await get_gene_context(c, response_mode=mode)
    await c.aclose()

    gene = result["gene"]
    assert _NOISE_KEYS.isdisjoint(gene), f"gene still leaks {_NOISE_KEYS & set(gene)}"
    # The nested transcripts block that duplicated the standalone list is gone.
    assert "transcripts" not in gene

    for tx in result["transcripts"]:
        assert _NOISE_KEYS.isdisjoint(tx), f"transcript leaks {_NOISE_KEYS & set(tx)}"
    for dom in result["domains"]:
        assert _NOISE_KEYS.isdisjoint(dom), f"domain leaks {_NOISE_KEYS & set(dom)}"

    # The genuinely useful fields survive.
    assert gene["symbol"] == "HNF1B"
    assert gene["ensembl_id"] == "ENSG00000275410"
    assert result["transcripts"][0]["transcript_id"] == "ENST00000372566"
    assert result["domains"][0]["name"] == "Dimerisation domain"


@pytest.mark.asyncio
@respx.mock
async def test_transcripts_are_deduplicated() -> None:
    """A payload with a duplicated transcript collapses to one entry per id."""
    _mock_all()
    c = ApiClient(base_url=BASE)
    result = await get_gene_context(c, response_mode="standard")
    await c.aclose()

    # Source had 3 rows (2 share ENST00000372566) -> 2 distinct accessions.
    ids = [tx["transcript_id"] for tx in result["transcripts"]]
    assert ids == ["ENST00000372566", "ENST00000372567"]
    assert len(ids) == len(set(ids))


@pytest.mark.asyncio
@respx.mock
async def test_default_omits_exons_keeps_exon_count() -> None:
    """Default (include_exons=False) drops the exon array but keeps exon_count."""
    _mock_all()
    c = ApiClient(base_url=BASE)
    result = await get_gene_context(c, response_mode="standard")
    await c.aclose()

    canonical = result["transcripts"][0]
    assert canonical["transcript_id"] == "ENST00000372566"
    assert "exons" not in canonical
    assert canonical["exon_count"] == 2


@pytest.mark.asyncio
@respx.mock
async def test_include_exons_true_returns_exon_array() -> None:
    """include_exons=True restores the full per-transcript exon array."""
    _mock_all()
    c = ApiClient(base_url=BASE)
    result = await get_gene_context(c, include_exons=True, response_mode="full")
    await c.aclose()

    canonical = result["transcripts"][0]
    assert "exons" in canonical
    assert [e["exon_number"] for e in canonical["exons"]] == [1, 2]


@pytest.mark.asyncio
@respx.mock
async def test_full_mode_preserves_provenance() -> None:
    """Full mode keeps the internal id/created_at/updated_at provenance fields."""
    _mock_all()
    c = ApiClient(base_url=BASE)
    result = await get_gene_context(c, response_mode="full")
    await c.aclose()

    gene = result["gene"]
    assert gene["id"] == "a09c8191-b0d5-4828-af87-042ddd7de013"
    assert "created_at" in gene
    assert "updated_at" in gene
    # transcripts still carry provenance in full mode.
    assert "created_at" in result["transcripts"][0]
    # but dedupe still applies in every mode.
    ids = [tx["transcript_id"] for tx in result["transcripts"]]
    assert len(ids) == len(set(ids))


@pytest.mark.asyncio
@respx.mock
async def test_compact_token_cut_vs_baseline() -> None:
    """Stripping noise + gating exons yields a materially smaller compact payload."""
    import json as _json

    _mock_all()
    c = ApiClient(base_url=BASE)
    compact = await get_gene_context(c, response_mode="compact")
    full = await get_gene_context(c, include_exons=True, response_mode="full")
    await c.aclose()

    compact_chars = len(_json.dumps(compact, default=str))
    full_chars = len(_json.dumps(full, default=str))
    # The summarized compact payload is well under the provenance/exon-rich full
    # payload — the scorecard wanted a 30-40% cut on this tool.
    assert compact_chars < full_chars * 0.7
