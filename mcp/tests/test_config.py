from hnf1b_mcp.config import Settings


def test_defaults(monkeypatch):
    monkeypatch.delenv("HNF1B_MCP_API_BASE_URL", raising=False)
    s = Settings()
    assert s.api_base_url.endswith("/api/v2")
    assert s.protocol_version == "2025-11-25"
    assert s.default_response_mode == "compact"
    assert s.mode_char_budgets["compact"] == 12000
    assert "claude.ai" in " ".join(s.allowed_origins) or s.allowed_origins == ["*"]


def test_env_override(monkeypatch):
    monkeypatch.setenv("HNF1B_MCP_API_BASE_URL", "http://hnf1b_api:8000/api/v2")
    assert Settings().api_base_url == "http://hnf1b_api:8000/api/v2"


def test_allowed_origins_csv_env(monkeypatch):
    monkeypatch.setenv(
        "HNF1B_MCP_ALLOWED_ORIGINS", "https://claude.ai,https://claude.com"
    )
    s = Settings()
    assert s.allowed_origins == ["https://claude.ai", "https://claude.com"]


def test_allowed_origins_csv_with_spaces(monkeypatch):
    monkeypatch.setenv("HNF1B_MCP_ALLOWED_ORIGINS", " https://a.test , https://b.test ")
    assert Settings().allowed_origins == ["https://a.test", "https://b.test"]
