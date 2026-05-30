from __future__ import annotations

from pathlib import Path

import pytest

from app.publications.fulltext.embeddings import (
    EmbeddingProvider,
    FakeEmbeddingProvider,
    SentenceTransformerEmbeddingProvider,
    get_embedding_provider,
    hash_text,
)

FIX = Path(__file__).parent / "fixtures" / "publications"


async def test_fake_provider_shape_and_determinism():
    provider = FakeEmbeddingProvider(dim=384)
    assert provider.dim == 384
    assert provider.model_name == "fake-deterministic"

    vectors = await provider.embed(["a", "b", "a"])
    assert len(vectors) == 3
    assert all(len(v) == 384 for v in vectors)

    # Same text -> identical vector.
    assert vectors[0] == vectors[2]
    # Different text -> different vector.
    assert vectors[0] != vectors[1]


async def test_fake_provider_l2_normalized():
    provider = FakeEmbeddingProvider(dim=384)
    vectors = await provider.embed(["hello world", "another passage"])
    for vec in vectors:
        sum_sq = sum(component * component for component in vec)
        assert abs(sum_sq - 1.0) < 1e-6


async def test_fake_provider_is_query_ignored():
    provider = FakeEmbeddingProvider(dim=64)
    as_doc = await provider.embed(["query text"], is_query=False)
    as_query = await provider.embed(["query text"], is_query=True)
    assert as_doc == as_query


async def test_fake_provider_custom_dim():
    provider = FakeEmbeddingProvider(dim=16, model_name="tiny-fake")
    assert provider.dim == 16
    assert provider.model_name == "tiny-fake"
    vectors = await provider.embed(["x"])
    assert len(vectors[0]) == 16
    assert abs(sum(c * c for c in vectors[0]) - 1.0) < 1e-6


async def test_fake_provider_empty_batch():
    provider = FakeEmbeddingProvider(dim=384)
    assert await provider.embed([]) == []


async def test_fake_provider_is_embedding_provider():
    # Runtime-checkable protocol conformance.
    assert isinstance(FakeEmbeddingProvider(), EmbeddingProvider)


def test_hash_text_deterministic_and_hex_length():
    digest = hash_text("HNF1B full text passage")
    assert len(digest) == 64
    assert all(ch in "0123456789abcdef" for ch in digest)
    assert digest == hash_text("HNF1B full text passage")
    assert digest != hash_text("different text")


def test_hash_text_on_fixture_content():
    # Exercise the hash on real recorded fixture bytes (text-decoded).
    raw = (FIX / "europepmc_core_32574212.json").read_text(encoding="utf-8")
    digest = hash_text(raw)
    assert len(digest) == 64
    assert digest == hash_text(raw)


def test_get_embedding_provider_returns_none_without_sentence_transformers():
    # sentence-transformers is intentionally absent in this environment.
    provider = get_embedding_provider()
    assert provider is None


def test_sentence_transformer_provider_raises_clear_error_when_missing():
    with pytest.raises(RuntimeError, match="sentence-transformers is not installed"):
        SentenceTransformerEmbeddingProvider(
            model_name="BAAI/bge-small-en-v1.5",
            query_prefix="prefix: ",
        )
