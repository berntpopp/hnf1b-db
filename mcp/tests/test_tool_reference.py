"""Tests for the hnf1b_get_gene_context tool registration and behavior."""

from __future__ import annotations

import httpx
import pytest
import respx
from fastmcp import FastMCP

from hnf1b_mcp.client.api_client import ApiClient
from hnf1b_mcp.tools.reference import register

BASE = "http://api.test/api/v2"

# ---------------------------------------------------------------------------
# Shared fixture data (mirrors test_reference.py payloads)
# ---------------------------------------------------------------------------

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
    "created_at": "2026-04-17T09:48:44.742052Z",
    "updated_at": "2026-05-30T08:45:48.940076Z",
    "transcripts": [{"id": "799a1ceb", "transcript_id": "ENST00000372566"}],
}

TRANSCRIPTS_PAYLOAD = [
    {
        "id": "799a1ceb-38a3-4f81-a158-1c086e7ee07a",
        "transcript_id": "ENST00000372566",
        "is_canonical": True,
        "exon_count": 1,
        "created_at": "2026-05-30T08:45:48.940076Z",
        "updated_at": "2026-05-30T08:45:48.940076Z",
        "exons": [
            {
                "id": "213003b6-2b0c-4d1d-b123-354f18afa16b",
                "exon_number": 1,
                "chromosome": "17",
                "start": 36098063,
                "end": 36098372,
            }
        ],
    },
    {
        "id": "b1234567-0000-0000-0000-000000000000",
        "transcript_id": "ENST00000372567",
        "is_canonical": False,
        "exon_count": 0,
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


def _mock_all(symbol: str = "HNF1B") -> None:
    """Register respx mocks for the three reference endpoints."""
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
# Registration tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_registers_with_readonly_hint() -> None:
    """Tool is registered with readOnlyHint=True and openWorldHint=False."""
    mcp = FastMCP("test")
    register(mcp, None)
    tools = await mcp.list_tools()
    t = next(t for t in tools if t.name == "hnf1b_get_gene_context")
    assert t.annotations.readOnlyHint is True
    assert t.annotations.openWorldHint is False


@pytest.mark.asyncio
async def test_registers_with_client_none() -> None:
    """register() must not raise when client=None."""
    mcp = FastMCP("test")
    register(mcp, None)
    tools = await mcp.list_tools()
    names = [t.name for t in tools]
    assert "hnf1b_get_gene_context" in names


# ---------------------------------------------------------------------------
# Happy-path tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_happy_path_full_structured_content() -> None:
    """Happy path: all three endpoints mocked, structured_content contains expected keys."""
    _mock_all()
    client = ApiClient(base_url=BASE)
    try:
        mcp = FastMCP("test")
        register(mcp, client)
        r = await mcp.call_tool("hnf1b_get_gene_context", {})
        sc = r.structured_content

        # data_class must be the EXTERNAL_REF value
        assert sc["data_class"] == "external_reference_identifier"

        # meta block must be present
        assert "meta" in sc
        assert "response_mode" in sc["meta"]

        # gene block
        assert sc["gene"]["symbol"] == "HNF1B"
        assert sc["gene"]["ensembl_id"] == "ENSG00000275410"
        assert sc["gene"]["chromosome"] == "17"

        # uri
        assert sc["uri"] == "hnf1b://gene/HNF1B"

        # transcripts and domains
        assert "transcripts" in sc
        assert len(sc["transcripts"]) == 2
        assert sc["transcripts"][0]["transcript_id"] == "ENST00000372566"

        assert "domains" in sc
        assert len(sc["domains"]) == 2
        assert sc["domains"][0]["name"] == "Dimerisation domain"
    finally:
        await client.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_happy_path_gene_only() -> None:
    """With include_transcripts=False and include_domains=False only gene + uri returned."""
    respx.get(f"{BASE}/reference/genes/HNF1B").mock(
        return_value=httpx.Response(200, json=GENE_PAYLOAD)
    )
    client = ApiClient(base_url=BASE)
    try:
        mcp = FastMCP("test")
        register(mcp, client)
        r = await mcp.call_tool(
            "hnf1b_get_gene_context",
            {"include_transcripts": False, "include_domains": False},
        )
        sc = r.structured_content

        assert sc["data_class"] == "external_reference_identifier"
        assert "meta" in sc
        assert sc["gene"]["symbol"] == "HNF1B"
        assert sc["uri"] == "hnf1b://gene/HNF1B"
        assert "transcripts" not in sc
        assert "domains" not in sc
    finally:
        await client.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_custom_gene_symbol_reflected_in_uri() -> None:
    """gene_symbol param is forwarded to the service and reflected in uri."""
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
    client = ApiClient(base_url=BASE)
    try:
        mcp = FastMCP("test")
        register(mcp, client)
        r = await mcp.call_tool(
            "hnf1b_get_gene_context",
            {"gene_symbol": symbol},
        )
        sc = r.structured_content

        assert sc["uri"] == f"hnf1b://gene/{symbol}"
        assert sc["gene"]["symbol"] == symbol
        assert sc["data_class"] == "external_reference_identifier"
    finally:
        await client.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_response_mode_reflected_in_meta() -> None:
    """response_mode argument is echoed in the meta block."""
    _mock_all()
    client = ApiClient(base_url=BASE)
    try:
        mcp = FastMCP("test")
        register(mcp, client)
        r = await mcp.call_tool(
            "hnf1b_get_gene_context",
            {"response_mode": "full"},
        )
        sc = r.structured_content
        assert sc["meta"]["response_mode"] == "full"
    finally:
        await client.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_tool_default_strips_noise_and_gates_exons() -> None:
    """Default compact call: no UUIDs/timestamps, no exon array, exon_count kept."""
    _mock_all()
    client = ApiClient(base_url=BASE)
    try:
        mcp = FastMCP("test")
        register(mcp, client)
        r = await mcp.call_tool("hnf1b_get_gene_context", {})
        sc = r.structured_content

        assert "id" not in sc["gene"]
        assert "created_at" not in sc["gene"]
        assert "transcripts" not in sc["gene"]  # nested duplicate gone
        canonical = sc["transcripts"][0]
        assert "id" not in canonical
        assert "exons" not in canonical
        assert canonical["exon_count"] == 1
    finally:
        await client.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_tool_include_exons_true_returns_exon_array() -> None:
    """include_exons=True surfaces the full per-transcript exon array."""
    _mock_all()
    client = ApiClient(base_url=BASE)
    try:
        mcp = FastMCP("test")
        register(mcp, client)
        r = await mcp.call_tool(
            "hnf1b_get_gene_context",
            {"include_exons": True, "response_mode": "full"},
        )
        sc = r.structured_content
        assert "exons" in sc["transcripts"][0]
        assert sc["transcripts"][0]["exons"][0]["exon_number"] == 1
    finally:
        await client.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_get_gene_context_not_found_returns_rich_error_envelope() -> None:
    """A 404 gene fetch surfaces a rich not_found (field + gene symbol echoed)."""
    respx.get(f"{BASE}/reference/genes/NOPE").mock(return_value=httpx.Response(404))
    client = ApiClient(base_url=BASE)
    try:
        mcp = FastMCP("test")
        register(mcp, client)
        r = await mcp.call_tool(
            "hnf1b_get_gene_context",
            {"gene_symbol": "NOPE"},
        )
        sc = r.structured_content
        assert sc.get("is_error") is True
        assert sc["error"]["code"] == "not_found"
        assert sc["error"]["field"] == "gene_symbol"
        assert "NOPE" in sc["error"]["message"]
    finally:
        await client.aclose()
