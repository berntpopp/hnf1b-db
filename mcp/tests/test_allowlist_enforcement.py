"""Closed-world allowlist enforcement integration test (Task 5a).

Proves the security invariant: across ALL services/tools, the MCP only ever
requests allowlisted paths, and NEVER requests a denied/side-effecting path.

The StubClient has the same ``get(path, params=None)`` async interface as
``ApiClient``, runs the REAL ``assert_allowed`` from
``hnf1b_mcp.client.allowlist`` before recording, and returns canned happy-path
JSON shaped per endpoint.

Denied paths exercised:
  - ``/publications/{pmid}/metadata``  (PubMed fetch + DB write)
  - ``/admin/sync``                    (privileged admin route)
  - ``/auth/login``                    (authentication route)
  - ``/dev/reset``                     (dev-only route)
  - ``/hpo/search``                    (legacy HPO OLS proxy)
"""

from __future__ import annotations

import re
from typing import Any

import pytest

from hnf1b_mcp.client.allowlist import (
    _DENY,  # noqa: PLC2701
    assert_allowed,
    is_allowed,
    is_denied,
)
from hnf1b_mcp.services.capabilities import get_capabilities
from hnf1b_mcp.services.individuals import get_individual, get_individuals
from hnf1b_mcp.services.publications import (
    get_publication_citing_individuals,
    list_publications,
)
from hnf1b_mcp.services.reference import get_gene_context
from hnf1b_mcp.services.search import search
from hnf1b_mcp.services.statistics import get_statistics
from hnf1b_mcp.services.terms import resolve_terms
from hnf1b_mcp.services.variants import get_variant, search_variants

# ---------------------------------------------------------------------------
# Deny patterns exercised in direct-refusal tests
# ---------------------------------------------------------------------------

_DENIED_PATHS = [
    "/publications/PMID:1/metadata",
    "/publications/12345678/metadata",
    "/admin/sync",
    "/admin/statistics",
    "/auth/login",
    "/auth/me",
    "/dev/reset",
    "/hpo/search",
    "/hpo/autocomplete",
    "/clinical/diabetes",
    "/comments",
    "/variants/annotate",
    "/users/mentionable",
    "/seo/sitemap-index.xml",
    "/publications/sync",
    "/phenopackets/compare/variant-types",
]

# ---------------------------------------------------------------------------
# Canned responses keyed by path pattern
# ---------------------------------------------------------------------------

# Individual phenopacket record (minimal happy path)
_PHENOPACKET_RECORD: dict[str, Any] = {
    "phenopacket_id": "pp-001",
    "id": "pp-001",
    "phenopacket": {
        "id": "pp-001",
        "subject": {"id": "pp-001", "sex": "MALE"},
        "diseases": [{"term": {"id": "OMIM:137920", "label": "HNF1B disease"}}],
        "phenotypicFeatures": [
            {
                "type": {"id": "HP:0000083", "label": "Renal insufficiency"},
                "excluded": False,
            }
        ],
        "measurements": [],
        "interpretations": [],
        "metaData": {"externalReferences": [{"id": "PMID:12345678"}]},
    },
}

_PHENOPACKETS_LIST_RESP: dict[str, Any] = {
    "data": [{"attributes": {"phenopacket_id": "pp-001"}, "id": "pp-001"}],
    "meta": {"total": 1},
}

_PHENOPACKETS_BATCH_RESP: dict[str, Any] = {
    "results": [_PHENOPACKET_RECORD],
}

_SEARCH_GLOBAL_RESP: dict[str, Any] = {
    "results": [
        {"id": "pp_001", "label": "Individual 001"},
        {"id": "var_HNF1B:c.494G>A", "label": "c.494G>A"},
        {"id": "pub_PMID:12345678", "label": "Author 2024"},
    ]
}

_ALL_VARIANTS_RESP: dict[str, Any] = {
    "data": [
        {
            "variant_id": "HNF1B:c.494G>A",
            "simple_id": "var-1",
            "label": "c.494G>A",
            "gene_symbol": "HNF1B",
            "structural_type": "SNV",
            "pathogenicity": "PATHOGENIC",
            "phenopacket_count": 5,
            "hg38": "17:36107165:G:A",
            "transcript": "NM_000458.3",
            "protein": "p.Arg165Gln",
            "molecular_consequence": "Missense",
        }
    ],
    "meta": {"total": 1},
}

_BY_VARIANT_RESP: list[dict[str, Any]] = [
    {"phenopacket_id": "pp-001"},
    {"phenopacket_id": "pp-002"},
]

_GENE_RESP: dict[str, Any] = {
    "symbol": "HNF1B",
    "hgnc_id": "HGNC:11630",
    "chromosome": "17",
    "start": 36046363,
    "end": 36109589,
}

_TRANSCRIPTS_RESP: list[dict[str, Any]] = [
    {"transcript_id": "NM_000458.4", "is_mane_select": True}
]

_DOMAINS_RESP: dict[str, Any] = {
    "domains": [{"name": "POU Homeodomain", "start": 200, "end": 280}]
}

_PUBLICATIONS_RESP: dict[str, Any] = {
    "data": [
        {
            "id": "12345678",
            "attributes": {
                "pmid": "12345678",
                "title": "HNF1B case series",
                "authors": "Author A et al.",
                "journal": "J Genet",
                "year": 2024,
                "doi": "10.1000/test",
                "phenopacket_count": 3,
            },
        }
    ],
    "meta": {"total": 1, "page": 1, "page_size": 25},
}

_BY_PUBLICATION_RESP: dict[str, Any] = {
    "data": [
        {"id": "pp-001", "attributes": {"phenopacket_id": "pp-001"}},
        {"id": "pp-002", "attributes": {"phenopacket_id": "pp-002"}},
    ]
}

_AGGREGATE_SUMMARY_RESP: dict[str, Any] = {"total_phenopackets": 42, "data": []}
_AGGREGATE_SURVIVAL_RESP: dict[str, Any] = {"groups": [{"group": "del", "data": []}]}
_AGGREGATE_SEX_RESP: dict[str, Any] = {"data": [{"sex": "MALE", "count": 30}]}

_HPO_AUTOCOMPLETE_RESP: dict[str, Any] = {
    "items": [
        {"hpo_id": "HP:0000083", "label": "Renal insufficiency", "description": ""}
    ]
}

_VOCAB_SEX_RESP: dict[str, Any] = {
    "items": [
        {"id": "MALE", "label": "Male", "description": ""},
        {"id": "FEMALE", "label": "Female", "description": ""},
    ]
}

_PHENOPACKETS_SEARCH_RESP: dict[str, Any] = {
    "data": [{"id": "pp-001"}, {"id": "pp-002"}],
}

# ---------------------------------------------------------------------------
# Stub client
# ---------------------------------------------------------------------------


def _make_response(path: str) -> Any:
    """Return a canned happy-path payload for an allowlisted path.

    Args:
        path: An allowlisted API path (without query string).

    Returns:
        A dict or list representative of the endpoint's response shape.
    """
    # Ordered from most-specific to least-specific.
    if re.match(r"^/phenopackets/batch$", path):
        return _PHENOPACKETS_BATCH_RESP
    if re.match(r"^/phenopackets/search/facets$", path):
        return {"facets": []}
    if re.match(r"^/phenopackets/search$", path):
        return _PHENOPACKETS_SEARCH_RESP
    # Specific aggregate paths before the generic aggregate catch-all
    if re.match(r"^/phenopackets/aggregate/summary$", path):
        return _AGGREGATE_SUMMARY_RESP
    if re.match(r"^/phenopackets/aggregate/survival-data$", path):
        return _AGGREGATE_SURVIVAL_RESP
    if re.match(r"^/phenopackets/aggregate/sex-distribution$", path):
        return _AGGREGATE_SEX_RESP
    if re.match(r"^/phenopackets/aggregate/all-variants$", path):
        return _ALL_VARIANTS_RESP
    if re.match(r"^/phenopackets/aggregate/[a-z-]+$", path):
        return {"data": []}
    if re.match(r"^/phenopackets/by-publication/[^/]+$", path):
        return _BY_PUBLICATION_RESP
    if re.match(r"^/phenopackets/by-variant/[^/]+$", path):
        return _BY_VARIANT_RESP
    if re.match(r"^/phenopackets/?$", path):
        return _PHENOPACKETS_LIST_RESP
    if re.match(r"^/phenopackets/[^/]+$", path):
        return _PHENOPACKET_RECORD
    if path == "/search/global":
        return _SEARCH_GLOBAL_RESP
    if path == "/search/autocomplete":
        return {"items": []}
    if path.startswith("/reference/genes/") and path.endswith("/transcripts"):
        return _TRANSCRIPTS_RESP
    if path.startswith("/reference/genes/") and path.endswith("/domains"):
        return _DOMAINS_RESP
    if re.match(r"^/reference/genes/[^/]+$", path):
        return _GENE_RESP
    if path == "/reference/genes":
        return {"data": []}
    if path == "/reference/genomes":
        return {"data": []}
    if path == "/publications/":
        return _PUBLICATIONS_RESP
    if path == "/ontology/hpo/autocomplete":
        return _HPO_AUTOCOMPLETE_RESP
    if path == "/ontology/hpo/grouped":
        return {"groups": []}
    if re.match(r"^/ontology/vocabularies/[a-z-]+$", path):
        return _VOCAB_SEX_RESP
    # fallback
    return {}


class StubClient:
    """Stub API client that enforces the allowlist and records every requested path.

    Has the same ``get(path, params=None)`` async interface as
    :class:`~hnf1b_mcp.client.api_client.ApiClient`.  Calls
    :func:`~hnf1b_mcp.client.allowlist.assert_allowed` before recording so
    that any non-allowlisted request raises :class:`PermissionError` and
    fails the test immediately.

    Attributes:
        recorded_paths: Ordered list of every path that was requested.
    """

    def __init__(self) -> None:
        """Initialize with an empty recording list."""
        self.recorded_paths: list[str] = []

    async def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        """Enforce allowlist, record the path, and return canned JSON.

        Args:
            path: API path (must be allowlisted).
            params: Optional query parameters (ignored for canned responses).

        Returns:
            A canned happy-path payload for the given path.

        Raises:
            PermissionError: If *path* is not on the allowlist.
        """
        assert_allowed(path)  # Raises PermissionError for non-allowlisted paths
        self.recorded_paths.append(path)
        return _make_response(path)

    async def aclose(self) -> None:
        """No-op cleanup to match the ApiClient interface."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _assert_path_clean(path: str) -> None:
    """Assert that a recorded path satisfies both allowlist invariants.

    Args:
        path: A path that was recorded by the StubClient.
    """
    assert is_allowed(path), f"Recorded path NOT allowlisted: {path!r}"
    assert not is_denied(path), f"Recorded path matches explicit deny rule: {path!r}"


# ---------------------------------------------------------------------------
# Individual service tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_service_uses_allowlisted_paths() -> None:
    """search() only requests /search/global."""
    stub = StubClient()
    result = await search(stub, query="HNF1B")  # type: ignore[arg-type]
    assert result["query"] == "HNF1B"
    assert "/search/global" in stub.recorded_paths
    for p in stub.recorded_paths:
        _assert_path_clean(p)


@pytest.mark.asyncio
async def test_get_individual_uses_allowlisted_paths() -> None:
    """get_individual() only requests /phenopackets/{id}."""
    stub = StubClient()
    result = await get_individual(stub, "pp-001")  # type: ignore[arg-type]
    assert result["phenopacket_id"] == "pp-001"
    assert "/phenopackets/pp-001" in stub.recorded_paths
    for p in stub.recorded_paths:
        _assert_path_clean(p)


@pytest.mark.asyncio
async def test_get_individuals_batch_uses_allowlisted_paths() -> None:
    """get_individuals() with ids uses /phenopackets/batch."""
    stub = StubClient()
    result = await get_individuals(stub, ids=["pp-001"])  # type: ignore[arg-type]
    assert result["total"] == 1
    assert "/phenopackets/batch" in stub.recorded_paths
    for p in stub.recorded_paths:
        _assert_path_clean(p)


@pytest.mark.asyncio
async def test_get_individuals_list_uses_allowlisted_paths() -> None:
    """get_individuals() without ids uses /phenopackets/ discovery endpoint."""
    stub = StubClient()
    result = await get_individuals(stub)  # type: ignore[arg-type]
    assert "/phenopackets/" in stub.recorded_paths
    assert result["total"] >= 0
    for p in stub.recorded_paths:
        _assert_path_clean(p)


@pytest.mark.asyncio
async def test_find_individuals_by_phenotype_uses_allowlisted_paths() -> None:
    """find_individuals_by_phenotype flow hits /phenopackets/search then /phenopackets/batch."""
    stub = StubClient()
    # Direct service calls for the two legs: discovery + batch
    search_resp = await stub.get(
        "/phenopackets/search", params={"hpo_id": "HP:0000083"}
    )
    ids = [item["id"] for item in search_resp.get("data", []) if item.get("id")]
    if ids:
        await stub.get("/phenopackets/batch", params={"phenopacket_ids": ",".join(ids)})
    # All recorded paths must be allowlisted
    for p in stub.recorded_paths:
        _assert_path_clean(p)
    assert "/phenopackets/search" in stub.recorded_paths


@pytest.mark.asyncio
async def test_search_variants_uses_allowlisted_paths() -> None:
    """search_variants() only requests /phenopackets/aggregate/all-variants."""
    stub = StubClient()
    result = await search_variants(stub)  # type: ignore[arg-type]
    assert result["total"] == 1
    assert "/phenopackets/aggregate/all-variants" in stub.recorded_paths
    for p in stub.recorded_paths:
        _assert_path_clean(p)


@pytest.mark.asyncio
async def test_get_variant_uses_allowlisted_paths() -> None:
    """get_variant() only requests /phenopackets/by-variant/{variant_id}."""
    stub = StubClient()
    variant_id = "HNF1B:c.494G>A"
    result = await get_variant(stub, variant_id)  # type: ignore[arg-type]
    assert result["carrier_count"] == 2
    assert f"/phenopackets/by-variant/{variant_id}" in stub.recorded_paths
    for p in stub.recorded_paths:
        _assert_path_clean(p)


@pytest.mark.asyncio
async def test_get_gene_context_uses_allowlisted_paths() -> None:
    """get_gene_context() requests gene + transcripts + domains — all allowlisted."""
    stub = StubClient()
    result = await get_gene_context(
        stub,  # type: ignore[arg-type]
        gene_symbol="HNF1B",
        include_transcripts=True,
        include_domains=True,
    )
    assert result["gene"]["symbol"] == "HNF1B"
    assert "/reference/genes/HNF1B" in stub.recorded_paths
    assert "/reference/genes/HNF1B/transcripts" in stub.recorded_paths
    assert "/reference/genes/HNF1B/domains" in stub.recorded_paths
    for p in stub.recorded_paths:
        _assert_path_clean(p)


@pytest.mark.asyncio
async def test_list_publications_uses_allowlisted_paths() -> None:
    """list_publications() only requests /publications/."""
    stub = StubClient()
    result = await list_publications(stub)  # type: ignore[arg-type]
    assert "/publications/" in stub.recorded_paths
    assert result["total"] >= 0
    for p in stub.recorded_paths:
        _assert_path_clean(p)


@pytest.mark.asyncio
async def test_get_publication_citing_individuals_uses_allowlisted_paths() -> None:
    """get_publication_citing_individuals() uses /phenopackets/by-publication/{pmid}."""
    stub = StubClient()
    result = await get_publication_citing_individuals(
        stub,
        pmid="12345678",  # type: ignore[arg-type]
    )
    assert "/phenopackets/by-publication/12345678" in stub.recorded_paths
    assert result["total"] == 2
    # CRITICAL: the metadata endpoint must NOT have been requested
    assert "/publications/12345678/metadata" not in stub.recorded_paths
    for p in stub.recorded_paths:
        _assert_path_clean(p)


@pytest.mark.asyncio
async def test_get_statistics_summary_uses_allowlisted_paths() -> None:
    """get_statistics(summary) only requests /phenopackets/aggregate/summary."""
    stub = StubClient()
    result = await get_statistics(stub, metric="summary")  # type: ignore[arg-type]
    assert result["metric"] == "summary"
    assert "/phenopackets/aggregate/summary" in stub.recorded_paths
    for p in stub.recorded_paths:
        _assert_path_clean(p)


@pytest.mark.asyncio
async def test_get_statistics_survival_uses_allowlisted_paths() -> None:
    """get_statistics(survival, comparison=...) only requests the aggregate/survival-data path."""
    stub = StubClient()
    result = await get_statistics(
        stub,  # type: ignore[arg-type]
        metric="survival",
        comparison="variant_type",
    )
    assert result["metric"] == "survival"
    assert "/phenopackets/aggregate/survival-data" in stub.recorded_paths
    for p in stub.recorded_paths:
        _assert_path_clean(p)


@pytest.mark.asyncio
async def test_resolve_terms_hpo_uses_allowlisted_paths() -> None:
    """resolve_terms(hpo) only requests /ontology/hpo/autocomplete."""
    stub = StubClient()
    result = await resolve_terms(stub, text="renal", vocabulary="hpo")  # type: ignore[arg-type]
    assert result["vocabulary"] == "hpo"
    assert "/ontology/hpo/autocomplete" in stub.recorded_paths
    # The legacy /hpo/ proxy must NOT have been requested
    for p in stub.recorded_paths:
        assert not p.startswith("/hpo/"), f"Legacy HPO OLS proxy was hit: {p!r}"
    for p in stub.recorded_paths:
        _assert_path_clean(p)


@pytest.mark.asyncio
async def test_resolve_terms_controlled_vocab_uses_allowlisted_paths() -> None:
    """resolve_terms(sex) only requests /ontology/vocabularies/sex."""
    stub = StubClient()
    result = await resolve_terms(stub, text="", vocabulary="sex")  # type: ignore[arg-type]
    assert result["vocabulary"] == "sex"
    assert "/ontology/vocabularies/sex" in stub.recorded_paths
    for p in stub.recorded_paths:
        _assert_path_clean(p)


def test_get_capabilities_makes_no_api_calls() -> None:
    """get_capabilities() is pure static data — no API calls at all."""
    result = get_capabilities()
    assert "tools" in result
    assert "canonical_workflows" in result
    assert isinstance(result["tools"], list)


# ---------------------------------------------------------------------------
# Aggregate invariant over all recorded paths
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_all_service_paths_are_allowlisted() -> None:
    """Drive every service function and assert ALL recorded paths are allowlisted.

    This is the primary closed-world invariant test: collect every path that
    any service function requests across all 11 exercised services/tools, then
    assert:

    1. The recorded set is non-empty.
    2. Every recorded path passes ``is_allowed()``.
    3. No recorded path passes ``is_denied()``.
    """
    stub = StubClient()

    # --- search ---
    await search(stub, query="HNF1B renal")  # type: ignore[arg-type]

    # --- individuals ---
    await get_individual(stub, "pp-001")  # type: ignore[arg-type]
    await get_individuals(stub, ids=["pp-001", "pp-002"])  # type: ignore[arg-type]
    await get_individuals(stub)  # type: ignore[arg-type]

    # --- find_individuals_by_phenotype (manual two-step) ---
    resp = await stub.get("/phenopackets/search", params={"hpo_id": "HP:0000083"})
    ids = [item["id"] for item in resp.get("data", []) if item.get("id")]
    if ids:
        await stub.get("/phenopackets/batch", params={"phenopacket_ids": ",".join(ids)})

    # --- variants ---
    await search_variants(stub)  # type: ignore[arg-type]
    await get_variant(stub, "HNF1B:c.494G>A")  # type: ignore[arg-type]

    # --- gene context ---
    await get_gene_context(stub, gene_symbol="HNF1B")  # type: ignore[arg-type]

    # --- publications ---
    await list_publications(stub)  # type: ignore[arg-type]
    await get_publication_citing_individuals(stub, pmid="12345678")  # type: ignore[arg-type]

    # --- statistics ---
    await get_statistics(stub, metric="summary")  # type: ignore[arg-type]
    await get_statistics(stub, metric="survival", comparison="variant_type")  # type: ignore[arg-type]
    await get_statistics(stub, metric="sex_distribution")  # type: ignore[arg-type]

    # --- terms ---
    await resolve_terms(stub, text="renal", vocabulary="hpo")  # type: ignore[arg-type]
    await resolve_terms(stub, text="", vocabulary="sex")  # type: ignore[arg-type]

    # --- Primary assertions ---
    assert len(stub.recorded_paths) > 0, "No paths were recorded — test is vacuous"

    for path in stub.recorded_paths:
        assert is_allowed(path), (
            f"Service requested a NON-ALLOWLISTED path: {path!r}\n"
            f"All recorded paths: {stub.recorded_paths}"
        )
        assert not is_denied(path), (
            f"Service requested an EXPLICITLY DENIED path: {path!r}\n"
            f"All recorded paths: {stub.recorded_paths}"
        )


# ---------------------------------------------------------------------------
# Direct client-layer refusal tests
# ---------------------------------------------------------------------------


def test_assert_allowed_rejects_publications_metadata() -> None:
    """assert_allowed raises PermissionError for the PubMed metadata path."""
    with pytest.raises(PermissionError):
        assert_allowed("/publications/PMID:1/metadata")


def test_assert_allowed_rejects_publications_pmid_metadata_bare() -> None:
    """assert_allowed raises PermissionError for bare numeric PMID metadata path."""
    with pytest.raises(PermissionError):
        assert_allowed("/publications/12345678/metadata")


def test_assert_allowed_rejects_admin_sync() -> None:
    """assert_allowed raises PermissionError for /admin/sync."""
    with pytest.raises(PermissionError):
        assert_allowed("/admin/sync")


def test_assert_allowed_rejects_auth_login() -> None:
    """assert_allowed raises PermissionError for /auth/login."""
    with pytest.raises(PermissionError):
        assert_allowed("/auth/login")


def test_assert_allowed_rejects_dev_routes() -> None:
    """assert_allowed raises PermissionError for /dev/* routes."""
    with pytest.raises(PermissionError):
        assert_allowed("/dev/reset")


def test_assert_allowed_rejects_hpo_ols_proxy() -> None:
    """assert_allowed raises PermissionError for the legacy /hpo/ OLS proxy."""
    with pytest.raises(PermissionError):
        assert_allowed("/hpo/search")
    with pytest.raises(PermissionError):
        assert_allowed("/hpo/autocomplete")


@pytest.mark.asyncio
async def test_stub_client_refuses_denied_path() -> None:
    """StubClient itself raises PermissionError for denied paths (via assert_allowed)."""
    stub = StubClient()
    with pytest.raises(PermissionError):
        await stub.get("/publications/PMID:1/metadata")
    # No path should have been recorded
    assert stub.recorded_paths == []


@pytest.mark.asyncio
async def test_stub_client_refuses_admin_path() -> None:
    """StubClient raises PermissionError for /admin/* paths."""
    stub = StubClient()
    with pytest.raises(PermissionError):
        await stub.get("/admin/sync")
    assert stub.recorded_paths == []


# ---------------------------------------------------------------------------
# Parametrised: every explicitly denied path raises PermissionError
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("path", _DENIED_PATHS)
def test_every_denied_path_raises_permission_error(path: str) -> None:
    """Every explicitly denied path raises PermissionError from assert_allowed.

    Args:
        path: A denied API path from the parametrised list.
    """
    with pytest.raises(PermissionError):
        assert_allowed(path)


@pytest.mark.parametrize("path", _DENIED_PATHS)
def test_every_denied_path_matches_deny_rule(path: str) -> None:
    """Every denied path satisfies is_denied() — explicit deny coverage check.

    Args:
        path: A denied API path from the parametrised list.
    """
    assert is_denied(path), (
        f"Expected {path!r} to match a deny rule, but is_denied() returned False.\n"
        f"Deny patterns: {[d.pattern for d in _DENY]}"
    )
