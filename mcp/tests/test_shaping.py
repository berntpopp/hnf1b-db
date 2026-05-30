from hnf1b_mcp.services.shaping import apply_budget, build_meta, resolve_mode


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
