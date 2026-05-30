from hnf1b_mcp.services.shaping import (
    DEFAULT_SAMPLE_SIZE,
    apply_budget,
    build_meta,
    resolve_mode,
    sample_with_signal,
)


def test_resolve_mode_default():
    assert resolve_mode(None) == "compact"
    assert resolve_mode("full") == "full"


def test_resolve_mode_invalid():
    import pytest

    from hnf1b_mcp.services.errors import McpToolError

    with pytest.raises(McpToolError):
        resolve_mode("gigantic")


def test_apply_budget_trims_lists():
    payload = {"items": [{"x": i} for i in range(1000)]}
    shaped, dropped = apply_budget(payload, max_chars=200, list_keys=["items"])
    assert dropped["dropped_records"] > 0
    assert len(shaped["items"]) < 1000


def test_apply_budget_keep_min_never_empties_a_match():
    # A single item already exceeds the budget; keep_min=1 must retain it (with a
    # truncation signal) rather than pop the list to empty.
    payload = {"items": [{"text": "x" * 5000}, {"text": "y" * 5000}]}
    shaped, dropped = apply_budget(
        payload, max_chars=100, list_keys=["items"], keep_min=1
    )
    assert len(shaped["items"]) == 1  # the top item survives
    assert dropped["dropped_records"] == 1


def test_apply_budget_keep_min_default_zero_can_empty():
    # Default keep_min=0 preserves the prior unbounded-trim behaviour.
    payload = {"items": [{"text": "x" * 5000}]}
    shaped, dropped = apply_budget(payload, max_chars=100, list_keys=["items"])
    assert shaped["items"] == []
    assert dropped["dropped_records"] == 1


def test_build_meta_echoes_mode():
    m = build_meta(response_mode="compact", effective_chars=123, dropped=None)
    assert m["response_mode"] == "compact"
    assert m["effective_chars"] == 123


# ---------------------------------------------------------------------------
# sample_with_signal — the shared sample/signal helper
# ---------------------------------------------------------------------------

_NOTE = "first {sample} of {total}; recover via include_x=true"


def test_sample_with_signal_returns_whole_when_fits():
    # A list at or below the sample size is returned WHOLE with an EMPTY signal,
    # so the caller never emits a spurious truncation flag.
    items = [f"x{i}" for i in range(5)]
    sampled, signal = sample_with_signal(
        items, total=5, key_prefix="x", note=_NOTE, sample_size=10
    )
    assert sampled == items
    assert signal == {}


def test_sample_with_signal_boundary_exactly_sample_size_no_signal():
    # len == sample_size: whole list, no signal (inclusive boundary).
    items = [f"x{i}" for i in range(10)]
    sampled, signal = sample_with_signal(
        items, total=10, key_prefix="x", note=_NOTE, sample_size=10
    )
    assert sampled == items
    assert len(sampled) == 10
    assert signal == {}


def test_sample_with_signal_boundary_one_over_sample_size_flagged():
    # len == sample_size + 1: sampled down to sample_size with a full signal.
    items = [f"x{i}" for i in range(11)]
    sampled, signal = sample_with_signal(
        items, total=11, key_prefix="x", note=_NOTE, sample_size=10
    )
    assert len(sampled) == 10
    assert sampled == items[:10]
    assert signal["x_total"] == 11
    assert signal["x_returned"] == 10
    assert signal["x_truncated"] is True
    assert signal["x_note"] == "first 10 of 11; recover via include_x=true"


def test_sample_with_signal_prefixed_keys():
    # The signal keys are derived from key_prefix.
    items = list(range(50))
    _, signal = sample_with_signal(
        items, total=50, key_prefix="citing_individuals", note=_NOTE
    )
    assert set(signal) == {
        "citing_individuals_total",
        "citing_individuals_returned",
        "citing_individuals_truncated",
        "citing_individuals_note",
    }


def test_sample_with_signal_total_may_exceed_len():
    # total is authoritative even when the fetched list was itself bounded.
    items = [f"x{i}" for i in range(20)]
    sampled, signal = sample_with_signal(
        items, total=379, key_prefix="carriers", note=_NOTE
    )
    assert len(sampled) == DEFAULT_SAMPLE_SIZE
    assert signal["carriers_total"] == 379
    assert signal["carriers_returned"] == DEFAULT_SAMPLE_SIZE


def test_default_sample_size_is_ten():
    assert DEFAULT_SAMPLE_SIZE == 10
