"""Experimental structure endpoints: mmCIF download and per-residue DNA distances."""

import pytest
from httpx import AsyncClient

from app.reference.structure import STRUCTURE_FILE, residue_dna_distances


def test_distances_match_ngl_reference_values() -> None:
    """Values agree with the NGL-based calculator the frontend used before."""
    distances = residue_dna_distances()

    # NGL (float32 coordinates) gave 26.81423, 4.99190, 5.96581 for these.
    assert distances[90] == pytest.approx(26.814, abs=1e-3)
    assert distances[303] == pytest.approx(4.992, abs=1e-3)
    assert distances[150] == pytest.approx(5.966, abs=1e-3)
    # Resolved: 90-187 and 231-310 (the linker 188-230 is not in the crystal).
    assert set(distances) == set(range(90, 188)) | set(range(231, 311))


@pytest.mark.asyncio
async def test_dna_distances_endpoint(async_client: AsyncClient) -> None:
    response = await async_client.get(
        "/api/v2/reference/genes/hnf1b/structure/dna-distances"
    )

    assert response.status_code == 200
    assert response.headers["cache-control"] == "public, max-age=86400"
    body = response.json()
    assert body["gene"] == "HNF1B"
    assert body["pdb_id"] == "2H8R"
    assert len(body["residues"]) == 178
    assert body["residues"][0] == {"residue": 90, "distance": 26.814}


@pytest.mark.asyncio
async def test_structure_download(async_client: AsyncClient) -> None:
    response = await async_client.get("/api/v2/reference/genes/HNF1B/structure")

    assert response.status_code == 200
    assert response.headers["content-type"] == "chemical/x-mmcif"
    assert response.content == STRUCTURE_FILE.read_bytes()


@pytest.mark.asyncio
@pytest.mark.parametrize("suffix", ["", "/dna-distances"])
async def test_unknown_gene_is_404(async_client: AsyncClient, suffix: str) -> None:
    response = await async_client.get(f"/api/v2/reference/genes/TP53/structure{suffix}")

    assert response.status_code == 404
