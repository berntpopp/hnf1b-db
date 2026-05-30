"""Embedding providers for the publication full-text RAG dense leg.

This module defines the embedding provider protocol used by the dense
retrieval leg, a deterministic pure-Python fake provider for CI and unit
tests, and a lazily-imported SentenceTransformer-backed provider for
production. Nothing here touches the database; persistence and backfill
live in separate modules.

The fake provider never requires ``numpy``, ``torch``, or
``sentence-transformers`` so the unit tests run in any environment, while
:func:`get_embedding_provider` quietly returns ``None`` when the optional
model stack is not installed.
"""

from __future__ import annotations

import asyncio
import hashlib
import importlib.util
import math
import random
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import Sequence


@runtime_checkable
class EmbeddingProvider(Protocol):
    """Protocol implemented by every embedding backend.

    Implementations turn text into fixed-length, L2-normalized float
    vectors suitable for cosine/inner-product similarity in the dense
    retrieval leg.
    """

    @property
    def dim(self) -> int:
        """Return the dimensionality of the produced vectors."""
        ...

    @property
    def model_name(self) -> str:
        """Return the identifier of the underlying embedding model."""
        ...

    async def embed(
        self, texts: Sequence[str], *, is_query: bool = False
    ) -> list[list[float]]:
        """Embed a batch of texts into L2-normalized float vectors.

        Args:
            texts: The texts to embed, in order.
            is_query: Whether the texts are search queries (some models
                apply a query-side prompt prefix); document passages use
                ``False``.

        Returns:
            One ``dim``-length float vector per input text, in input order.
        """
        ...


def hash_text(text: str) -> str:
    """Return the SHA-256 hex digest of ``text`` encoded as UTF-8.

    The digest is stored as ``embeddings.text_hash`` so that re-embedding
    can be skipped when a passage's text is unchanged.

    Args:
        text: The text to hash.

    Returns:
        The 64-character lowercase hexadecimal SHA-256 digest.
    """
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _l2_normalize(vector: list[float]) -> list[float]:
    """Return ``vector`` scaled to unit L2 norm.

    Args:
        vector: The raw float vector.

    Returns:
        The L2-normalized vector. An all-zero vector is returned unchanged
        to avoid division by zero.
    """
    norm = math.sqrt(sum(component * component for component in vector))
    if norm == 0.0:
        return vector
    return [component / norm for component in vector]


class FakeEmbeddingProvider:
    """Deterministic, dependency-free embedding provider for tests and CI.

    Each text is hashed with SHA-256 and the digest seeds a standard-library
    PRNG that fills a ``dim``-length vector, which is then L2-normalized. The
    same text always yields an identical vector and distinct texts almost
    always yield distinct vectors. The ``is_query`` flag is ignored because
    the fake model has no query-side prompt.
    """

    def __init__(self, dim: int = 384, model_name: str = "fake-deterministic") -> None:
        """Initialize the fake provider.

        Args:
            dim: Dimensionality of the produced vectors.
            model_name: Reported model identifier.
        """
        self._dim = dim
        self._model_name = model_name

    @property
    def dim(self) -> int:
        """Return the dimensionality of the produced vectors."""
        return self._dim

    @property
    def model_name(self) -> str:
        """Return the reported model identifier."""
        return self._model_name

    async def embed(
        self, texts: Sequence[str], *, is_query: bool = False
    ) -> list[list[float]]:
        """Deterministically embed ``texts`` into L2-normalized vectors.

        Args:
            texts: The texts to embed, in order.
            is_query: Ignored; the fake model has no query-side prompt.

        Returns:
            One ``dim``-length L2-normalized float vector per input text.
        """
        del is_query  # No query-side prompt for the deterministic fake.
        return [self._vector_for(text) for text in texts]

    def _vector_for(self, text: str) -> list[float]:
        """Build the deterministic L2-normalized vector for one text.

        Args:
            text: The text to embed.

        Returns:
            A ``dim``-length L2-normalized float vector seeded by
            ``sha256(text)``.
        """
        seed = int.from_bytes(hashlib.sha256(text.encode("utf-8")).digest(), "big")
        rng = random.Random(seed)
        raw = [rng.uniform(-1.0, 1.0) for _ in range(self._dim)]
        return _l2_normalize(raw)


class SentenceTransformerEmbeddingProvider:
    """SentenceTransformer-backed provider, imported lazily.

    ``sentence-transformers`` (and its ``torch`` stack) are heavyweight and
    optional, so the import happens in :meth:`__init__`. A missing dependency
    raises a clear :class:`RuntimeError` rather than a bare ``ImportError``.
    """

    def __init__(
        self,
        *,
        model_name: str,
        query_prefix: str,
        batch_size: int = 32,
        dim: int = 384,
    ) -> None:
        """Load the underlying SentenceTransformer model.

        Args:
            model_name: The SentenceTransformer model identifier to load.
            query_prefix: Prefix prepended to query texts when
                ``is_query`` is true.
            batch_size: Encoding batch size passed to ``model.encode``.
            dim: Reported embedding dimensionality.

        Raises:
            RuntimeError: If ``sentence-transformers`` is not installed.
        """
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:  # pragma: no cover - optional dependency
            msg = (
                "sentence-transformers is not installed; install the optional "
                "embedding stack to use SentenceTransformerEmbeddingProvider."
            )
            raise RuntimeError(msg) from exc

        self._model = SentenceTransformer(model_name)
        self._model_name = model_name
        self._query_prefix = query_prefix
        self._batch_size = batch_size
        self._dim = dim

    @property
    def dim(self) -> int:
        """Return the reported embedding dimensionality."""
        return self._dim

    @property
    def model_name(self) -> str:
        """Return the underlying model identifier."""
        return self._model_name

    async def embed(
        self, texts: Sequence[str], *, is_query: bool = False
    ) -> list[list[float]]:
        """Embed ``texts`` using the SentenceTransformer model off-thread.

        Args:
            texts: The texts to embed, in order.
            is_query: When true, each text is prefixed with the configured
                ``query_prefix`` before encoding.

        Returns:
            One L2-normalized float vector per input text, in input order.
        """
        prepared = (
            [f"{self._query_prefix}{text}" for text in texts]
            if is_query
            else list(texts)
        )
        return await asyncio.to_thread(self._encode, prepared)

    def _encode(self, texts: list[str]) -> list[list[float]]:
        """Run the blocking ``model.encode`` call and coerce to lists.

        Args:
            texts: The (already query-prefixed) texts to encode.

        Returns:
            The encoded, L2-normalized vectors as plain Python float lists.
        """
        encoded = self._model.encode(
            texts,
            normalize_embeddings=True,
            batch_size=self._batch_size,
        )
        return [[float(value) for value in vector] for vector in encoded]


def get_embedding_provider(
    *,
    model_name: str = "BAAI/bge-small-en-v1.5",
    query_prefix: str = ("Represent this sentence for searching relevant passages: "),
    batch_size: int = 32,
    dim: int = 384,
) -> EmbeddingProvider | None:
    """Return a real embedding provider, or ``None`` if unavailable.

    The optional ``sentence-transformers`` package is probed with
    :func:`importlib.util.find_spec` so the heavy ``torch`` stack is not
    imported just to test availability.

    Args:
        model_name: The SentenceTransformer model identifier to load.
        query_prefix: Prefix prepended to query texts when embedding queries.
        batch_size: Encoding batch size.
        dim: Reported embedding dimensionality.

    Returns:
        A :class:`SentenceTransformerEmbeddingProvider` when
        ``sentence-transformers`` is importable, otherwise ``None``.
    """
    if importlib.util.find_spec("sentence_transformers") is None:
        return None
    return SentenceTransformerEmbeddingProvider(
        model_name=model_name,
        query_prefix=query_prefix,
        batch_size=batch_size,
        dim=dim,
    )
