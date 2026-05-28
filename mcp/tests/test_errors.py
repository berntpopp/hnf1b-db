import pytest

from hnf1b_mcp.services.errors import ERROR_CODES, McpToolError


def test_codes_present():
    assert ERROR_CODES == {"invalid_input", "not_found", "ambiguous_query", "temporarily_unavailable"}

def test_envelope():
    e = McpToolError("invalid_input", "bad query", argument="query")
    env = e.to_envelope()
    assert env["error"]["code"] == "invalid_input"
    assert env["error"]["argument"] == "query"
    assert env["error"]["message"] == "bad query"

def test_rejects_unknown_code():
    with pytest.raises(ValueError):
        McpToolError("kaboom", "x")

def test_ambiguous_choices():
    e = McpToolError("ambiguous_query", "many", choices=["A", "B"])
    assert e.to_envelope()["error"]["choices"] == ["A", "B"]
