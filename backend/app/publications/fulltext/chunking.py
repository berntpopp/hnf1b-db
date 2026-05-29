"""Section-bounded token-window chunking with character-offset recovery.

This is a pure module: it performs no I/O and depends only on the stdlib plus
the shared data contracts in :mod:`app.publications.fulltext.types`.

Chunking windows a single section's token stream into overlapping groups and
recovers each chunk's text as the *exact* original substring (via character
offsets), so capitalization, punctuation, and whitespace are preserved and the
text is never re-detokenized. The real BGE tokenizer is used only when the
optional ``tokenizers`` / ``transformers`` libraries are importable; otherwise
a deterministic regex tokenizer is used. Because the corpus is small and lexical
full-text search dominates retrieval, the regex fallback is fully sufficient.
"""

from __future__ import annotations

import re
from typing import Protocol

from app.publications.fulltext.types import Chunk

#: Token pattern: a run of word characters, or a single non-word, non-space
#: character (so punctuation becomes its own token).
_TOKEN_RE = re.compile(r"\w+|[^\w\s]")

#: HuggingFace model id whose fast tokenizer is preferred when available.
_BGE_MODEL_ID = "BAAI/bge-small-en-v1.5"


class TokenCounter(Protocol):
    """A tokenizer that reports character offsets for each token."""

    def offsets(self, text: str) -> list[tuple[int, int]]:
        """Return token character spans in order.

        Args:
            text: The text to tokenize.

        Returns:
            One ``(start_char, end_char)`` tuple per token, in order, such that
            ``text[start_char:end_char]`` is the token's surface form.
        """
        ...


class _RegexTokenizer:
    """Deterministic, dependency-free tokenizer using a fixed regex.

    Tokens are runs of word characters or single punctuation characters, with
    whitespace acting purely as a separator. Offsets index directly into the
    input string so the original substring can be recovered exactly.
    """

    def offsets(self, text: str) -> list[tuple[int, int]]:
        """Return token character spans for ``text``.

        Args:
            text: The text to tokenize.

        Returns:
            One ``(start_char, end_char)`` span per matched token, in order.
        """
        return [(m.start(), m.end()) for m in _TOKEN_RE.finditer(text)]


class _BgeTokenizer:
    """Wraps a HuggingFace fast tokenizer and exposes character offsets.

    The wrapped tokenizer must produce offset mappings (only fast tokenizers
    do). Special tokens, which carry empty ``(0, 0)`` spans, are dropped so the
    reported offsets always index real characters in the input.
    """

    def __init__(self, tokenizer: object) -> None:
        """Store the underlying fast tokenizer.

        Args:
            tokenizer: A loaded HuggingFace fast tokenizer instance.
        """
        self._tokenizer = tokenizer

    def offsets(self, text: str) -> list[tuple[int, int]]:
        """Return token character spans for ``text``.

        Args:
            text: The text to tokenize.

        Returns:
            One ``(start_char, end_char)`` span per content token, in order,
            with special tokens (empty spans) removed.
        """
        encoding = self._tokenizer(  # type: ignore[operator]
            text,
            add_special_tokens=False,
            return_offsets_mapping=True,
        )
        mapping = encoding["offset_mapping"]
        return [(int(start), int(end)) for start, end in mapping if end > start]


def get_tokenizer() -> TokenCounter:
    """Return the active tokenizer, preferring BGE when its libs are present.

    Attempts to lazily import ``transformers`` and build a fast tokenizer that
    yields character offsets. Any failure (missing optional dependency, no
    offset support, or load error) falls back to the deterministic regex
    tokenizer, which is sufficient for the small lexical-FTS-dominated corpus.

    Returns:
        A :class:`TokenCounter` implementation.
    """
    try:  # pragma: no cover - exercised only when optional libs are installed
        from transformers import AutoTokenizer  # noqa: PLC0415

        tokenizer = AutoTokenizer.from_pretrained(_BGE_MODEL_ID, use_fast=True)
        if not getattr(tokenizer, "is_fast", False):
            return _RegexTokenizer()
        probe = _BgeTokenizer(tokenizer)
        # Verify offsets are usable before committing to the BGE path.
        probe.offsets("probe")
        return probe
    except Exception:  # pragma: no cover - defensive fallback
        return _RegexTokenizer()


def chunk_section(
    section: str,
    text: str,
    *,
    max_tokens: int = 510,
    overlap_tokens: int = 50,
    tokenizer: TokenCounter | None = None,
) -> list[Chunk]:
    """Window one section's tokens into overlapping, offset-recovered chunks.

    The token offsets are grouped into consecutive windows of at most
    ``max_tokens`` tokens, advancing by ``step = max_tokens - overlap_tokens``
    tokens so that adjacent windows share ``overlap_tokens`` tokens. Each
    chunk's text is recovered as ``text[first_token_start:last_token_end]``,
    i.e. the exact original substring, never re-detokenized. The section
    boundary is never crossed because the input is a single section.

    Args:
        section: Canonical section label propagated onto every chunk.
        text: The section's raw text (capitalization/punctuation preserved).
        max_tokens: Maximum tokens per chunk window. Must be at least 1.
        overlap_tokens: Tokens shared between consecutive windows. Must be
            non-negative and strictly less than ``max_tokens`` (so the step is
            at least 1).
        tokenizer: Tokenizer to use; defaults to :func:`get_tokenizer`.

    Returns:
        Chunks in document order with ``idx`` incrementing from 0. Empty or
        whitespace-only ``text`` yields an empty list; text with at most
        ``max_tokens`` tokens yields exactly one chunk.

    Raises:
        ValueError: If ``max_tokens`` is below 1, ``overlap_tokens`` is
            negative, or the resulting step is below 1.
    """
    if max_tokens < 1:
        raise ValueError("max_tokens must be >= 1")
    if overlap_tokens < 0:
        raise ValueError("overlap_tokens must be >= 0")
    step = max_tokens - overlap_tokens
    if step < 1:
        raise ValueError("step (max_tokens - overlap_tokens) must be >= 1")

    if not text.strip():
        return []

    active = tokenizer if tokenizer is not None else get_tokenizer()
    spans = active.offsets(text)
    if not spans:
        return []

    chunks: list[Chunk] = []
    idx = 0
    for start in range(0, len(spans), step):
        window = spans[start : start + max_tokens]
        if not window:
            break
        first_start = window[0][0]
        last_end = window[-1][1]
        substring = text[first_start:last_end]
        chunks.append(
            Chunk(
                section=section,
                idx=idx,
                text=substring,
                char_count=len(substring),
                token_count=len(window),
            )
        )
        idx += 1
        # The final window has been emitted once it reaches the last token.
        if start + max_tokens >= len(spans):
            break

    return chunks
