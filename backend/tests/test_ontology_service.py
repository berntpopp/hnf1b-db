from __future__ import annotations

import threading

import pytest

from app.services.ontology_service import (
    HybridOntologyService,
    OntologySource,
    OntologyTerm,
)


@pytest.fixture
def ontology_service(monkeypatch, tmp_path) -> HybridOntologyService:
    monkeypatch.setenv("USE_ONTOLOGY_APIS", "true")
    monkeypatch.setenv("ONTOLOGY_API_TIMEOUT", "1")
    monkeypatch.setenv("ONTOLOGY_CACHE_TTL_HOURS", "24")

    service = HybridOntologyService()
    service.file_cache.cache_dir = tmp_path
    service._memory_cache.clear()
    return service


@pytest.mark.asyncio
async def test_get_term_async_returns_cached_term_without_api_fetch(
    ontology_service: HybridOntologyService, monkeypatch
):
    term_id = "HP:0000083"
    cached_term = OntologyTerm(
        id=term_id,
        label="Cached renal insufficiency",
        source=OntologySource.LOCAL_CACHE,
    )

    monkeypatch.setattr(ontology_service.file_cache, "get", lambda _: cached_term)

    def fail_fetch(term_id: str):
        raise AssertionError(f"unexpected API fetch for {term_id}")

    monkeypatch.setattr(ontology_service, "_fetch_from_apis", fail_fetch)

    term = await ontology_service.get_term_async(term_id)

    assert term == cached_term


@pytest.mark.asyncio
async def test_get_term_async_uses_api_fallback_before_local_and_populates_caches(
    ontology_service: HybridOntologyService, monkeypatch
):
    term_id = "HP:9991234"
    api_term = OntologyTerm(
        id=term_id,
        label="Mock API term",
        description="Fetched from mocked API",
        source=OntologySource.HPO_API,
    )
    loop_thread_id = threading.get_ident()
    cache_set_thread_id = None

    monkeypatch.setattr(ontology_service.local_provider, "get_term", lambda _: None)
    monkeypatch.setattr(ontology_service, "_fetch_from_apis", lambda _: api_term)

    def fake_cache_set(requested_term_id: str, requested_term: OntologyTerm):
        nonlocal cache_set_thread_id
        cache_set_thread_id = threading.get_ident()
        assert requested_term_id == term_id
        assert requested_term == api_term

    monkeypatch.setattr(ontology_service.file_cache, "set", fake_cache_set)

    term = await ontology_service.get_term_async(term_id)

    assert term == api_term
    assert ontology_service._memory_cache[term_id] == api_term
    assert cache_set_thread_id is not None
    assert cache_set_thread_id != loop_thread_id


@pytest.mark.asyncio
async def test_get_term_async_checks_api_before_local_when_cache_misses(
    ontology_service: HybridOntologyService, monkeypatch
):
    term_id = "HP:1234567"
    api_term = OntologyTerm(
        id=term_id,
        label="Fetched from API",
        source=OntologySource.HPO_API,
    )
    local_term = OntologyTerm(
        id=term_id,
        label="Local fallback term",
        source=OntologySource.LOCAL_HARDCODED,
    )

    monkeypatch.setattr(ontology_service.file_cache, "get", lambda _: None)
    monkeypatch.setattr(
        ontology_service.local_provider, "get_term", lambda _: local_term
    )
    monkeypatch.setattr(ontology_service, "_fetch_from_apis", lambda _: api_term)

    term = await ontology_service.get_term_async(term_id)

    assert term == api_term


@pytest.mark.asyncio
async def test_get_term_async_moves_file_cache_io_off_event_loop(
    ontology_service: HybridOntologyService, monkeypatch
):
    term_id = "HP:7777777"
    cached_term = OntologyTerm(
        id=term_id,
        label="Cached off-loop term",
        source=OntologySource.LOCAL_CACHE,
    )
    loop_thread_id = None
    cache_get_thread_id = None

    async def capture_loop_thread():
        import threading

        return threading.get_ident()

    def fake_cache_get(requested_term_id: str):
        nonlocal cache_get_thread_id
        cache_get_thread_id = threading.get_ident()
        assert requested_term_id == term_id
        return cached_term

    monkeypatch.setattr(ontology_service.file_cache, "get", fake_cache_get)

    loop_thread_id = await capture_loop_thread()
    term = await ontology_service.get_term_async(term_id)

    assert term == cached_term
    assert cache_get_thread_id is not None
    assert cache_get_thread_id != loop_thread_id


@pytest.mark.asyncio
async def test_get_term_async_preserves_file_cache_behavior(
    ontology_service: HybridOntologyService, monkeypatch, tmp_path
):
    term_id = "HP:5555555"
    api_term = OntologyTerm(
        id=term_id,
        label="Persisted cached term",
        source=OntologySource.HPO_API,
    )

    monkeypatch.setattr(ontology_service.local_provider, "get_term", lambda _: None)
    monkeypatch.setattr(ontology_service, "_fetch_from_apis", lambda _: api_term)

    fetched_term = await ontology_service.get_term_async(term_id)
    ontology_service._memory_cache.clear()
    monkeypatch.setattr(ontology_service, "_fetch_from_apis", lambda _: None)

    cached_term = await ontology_service.get_term_async(term_id)

    assert fetched_term == api_term
    assert cached_term is not None
    assert cached_term.label == api_term.label
    assert cached_term.source == OntologySource.HPO_API
