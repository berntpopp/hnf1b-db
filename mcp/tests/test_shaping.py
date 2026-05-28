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


def test_build_meta_echoes_mode():
    m = build_meta(response_mode="compact", effective_chars=123, dropped=None)
    assert m["response_mode"] == "compact"
    assert m["effective_chars"] == 123
