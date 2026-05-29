from __future__ import annotations

import math

import pytest

from app.publications.fulltext.chunking import (
    _RegexTokenizer,
    chunk_section,
    get_tokenizer,
)
from app.publications.fulltext.types import Chunk

TOK = _RegexTokenizer()


def _expected_window_count(n_tokens: int, max_tokens: int, step: int) -> int:
    if n_tokens <= max_tokens:
        return 1
    return 1 + math.ceil((n_tokens - max_tokens) / step)


@pytest.mark.parametrize("text", ["", "   ", "\n\t  \n"])
def test_empty_or_whitespace_returns_empty(text: str) -> None:
    assert chunk_section("intro", text, tokenizer=TOK) == []


def test_short_text_single_chunk_exact_slice() -> None:
    text = "Short methods paragraph, with caps."
    chunks = chunk_section("methods", text, max_tokens=510, overlap_tokens=50, tokenizer=TOK)
    assert len(chunks) == 1
    chunk = chunks[0]
    assert isinstance(chunk, Chunk)
    assert chunk.idx == 0
    assert chunk.section == "methods"
    # Offset recovery: first token start .. last token end == whole trimmed slice.
    offsets = TOK.offsets(text)
    assert chunk.text == text[offsets[0][0] : offsets[-1][1]]
    assert chunk.text == "Short methods paragraph, with caps."
    assert chunk.char_count == len(chunk.text)
    assert chunk.token_count == len(offsets)
    assert chunk.token_count <= 510


def test_text_with_exactly_max_tokens_single_chunk() -> None:
    text = " ".join(f"w{i}" for i in range(10))
    chunks = chunk_section("results", text, max_tokens=10, overlap_tokens=2, tokenizer=TOK)
    assert len(chunks) == 1
    assert chunks[0].token_count == 10


def test_long_text_windowing_overlap_and_offset_recovery() -> None:
    n = 100
    words = [f"w{i}" for i in range(n)]
    text = " ".join(words)
    max_tokens = 10
    overlap_tokens = 2
    step = max_tokens - overlap_tokens  # 8

    chunks = chunk_section(
        "discussion",
        text,
        max_tokens=max_tokens,
        overlap_tokens=overlap_tokens,
        tokenizer=TOK,
    )

    # Windowing formula: ceil((n - max) / step) + 1 windows.
    assert len(chunks) == _expected_window_count(n, max_tokens, step)

    spans = TOK.offsets(text)
    assert len(spans) == n  # one token per "wI" word (no punctuation)

    covered: set[int] = set()
    for i, chunk in enumerate(chunks):
        # Section label propagated and idx increments 0,1,2,...
        assert chunk.section == "discussion"
        assert chunk.idx == i
        # Each chunk respects the token budget.
        assert chunk.token_count <= max_tokens
        # Offset recovery: every chunk.text is an EXACT substring of the original.
        assert chunk.text in text
        assert chunk.char_count == len(chunk.text)
        # The recovered text equals the slice of the matching token window.
        window_start = i * step
        window = spans[window_start : window_start + max_tokens]
        assert chunk.token_count == len(window)
        assert chunk.text == text[window[0][0] : window[-1][1]]
        covered.update(range(window_start, window_start + chunk.token_count))

    # Consecutive chunks overlap by exactly overlap_tokens tokens (token based).
    for a_idx in range(len(chunks) - 1):
        a = chunks[a_idx]
        b = chunks[a_idx + 1]
        a_tokens = set(range(a_idx * step, a_idx * step + a.token_count))
        b_tokens = set(range((a_idx + 1) * step, (a_idx + 1) * step + b.token_count))
        shared = a_tokens & b_tokens
        assert len(shared) == overlap_tokens
        # The shared tokens are the suffix of A and the prefix of B; verify the
        # overlapping text region matches between the two recovered substrings.
        overlap_text_a = text[spans[(a_idx + 1) * step][0] : spans[a_idx * step + a.token_count - 1][1]]
        assert overlap_text_a in a.text
        assert overlap_text_a in b.text

    # Union of all chunk windows covers every token 0..n-1.
    assert covered == set(range(n))


def test_punctuation_and_case_preserved() -> None:
    text = "HNF1B, the Hepatocyte Nuclear Factor-1B; causes RCAD! (Renal Cysts)."
    chunks = chunk_section("abstract", text, max_tokens=510, overlap_tokens=50, tokenizer=TOK)
    assert len(chunks) == 1
    recovered = chunks[0].text
    # Caps survive.
    assert "HNF1B" in recovered
    assert "Hepatocyte Nuclear Factor-1B" in recovered
    # Punctuation survives.
    assert "," in recovered
    assert ";" in recovered
    assert "!" in recovered
    assert "(Renal Cysts)." in recovered
    # The recovered text is the exact slice from first to last token.
    offsets = TOK.offsets(text)
    assert recovered == text[offsets[0][0] : offsets[-1][1]]
    assert recovered == text  # no leading/trailing whitespace to trim here


def test_leading_trailing_whitespace_trimmed_to_token_span() -> None:
    text = "   leading and trailing spaces   "
    chunks = chunk_section("intro", text, max_tokens=510, overlap_tokens=50, tokenizer=TOK)
    assert len(chunks) == 1
    # Recovered slice starts at first token, ends at last token (no padding ws).
    assert chunks[0].text == "leading and trailing spaces"


def test_overlap_zero_is_contiguous_no_shared_tokens() -> None:
    n = 25
    text = " ".join(f"w{i}" for i in range(n))
    chunks = chunk_section("results", text, max_tokens=10, overlap_tokens=0, tokenizer=TOK)
    # step == max_tokens == 10 -> ceil(25/10) windows = 3.
    assert len(chunks) == 3
    assert [c.token_count for c in chunks] == [10, 10, 5]


def test_invalid_parameters_raise() -> None:
    with pytest.raises(ValueError):
        chunk_section("intro", "w0 w1", max_tokens=0, overlap_tokens=0, tokenizer=TOK)
    with pytest.raises(ValueError):
        chunk_section("intro", "w0 w1", max_tokens=5, overlap_tokens=-1, tokenizer=TOK)
    with pytest.raises(ValueError):
        # overlap == max_tokens -> step 0 -> invalid.
        chunk_section("intro", "w0 w1", max_tokens=5, overlap_tokens=5, tokenizer=TOK)


def test_get_tokenizer_returns_regex_fallback_offsets() -> None:
    tok = get_tokenizer()
    spans = tok.offsets("Alpha, beta.")
    text = "Alpha, beta."
    surfaces = [text[s:e] for s, e in spans]
    assert surfaces == ["Alpha", ",", "beta", "."]


def test_default_tokenizer_used_when_none_passed() -> None:
    # Sanity: chunk_section works end-to-end with the default tokenizer.
    chunks = chunk_section("title", "HNF1B gene")
    assert len(chunks) == 1
    assert chunks[0].text == "HNF1B gene"
    assert chunks[0].section == "title"
