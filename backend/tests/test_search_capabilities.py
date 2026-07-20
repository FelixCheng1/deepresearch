import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import main as main_module
from config import Configuration, SearchAPI
from services import search


def _result(backend: str) -> dict:
    return {
        "results": [
            {
                "title": "Example",
                "url": "https://example.com",
                "content": "content",
                "raw_content": "content",
            }
        ],
        "backend": backend,
        "answer": None,
        "notices": [],
    }


def test_capabilities_only_include_configured_engines(monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "configured")
    monkeypatch.delenv("PERPLEXITY_API_KEY", raising=False)
    monkeypatch.delenv("SEARXNG_URL", raising=False)

    capabilities = search.get_search_capabilities(
        Configuration(search_api=SearchAPI.TAVILY)
    )

    assert capabilities["default_engine"] == "tavily"
    assert capabilities["default_available"] is True
    assert [item["id"] for item in capabilities["engines"]] == [
        "advanced",
        "duckduckgo",
        "tavily",
    ]
    assert "configured" not in str(capabilities)


def test_advanced_records_missing_tavily_fallback(monkeypatch):
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    monkeypatch.setattr(search, "_duckduckgo_search", lambda query: _result("duckduckgo"))

    payload, notices, _, backend = search.dispatch_search(
        "topic",
        Configuration(search_api=SearchAPI.ADVANCED),
        0,
    )

    assert backend == "duckduckgo"
    assert payload["requested_backend"] == "advanced"
    assert payload["fallback_reason"] == "Tavily 未配置 API 密钥"
    assert "advanced 降级为 duckduckgo" in notices[0]


def test_remote_backend_failure_falls_back_without_exposing_error_detail(monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "configured")

    def failed_backend(query, backend, config):
        raise RuntimeError("secret provider response")

    monkeypatch.setattr(search, "_run_search_backend", failed_backend)
    monkeypatch.setattr(search, "_duckduckgo_search", lambda query: _result("duckduckgo"))

    payload, _, _, backend = search.dispatch_search(
        "topic",
        Configuration(search_api=SearchAPI.TAVILY),
        0,
    )

    assert backend == "duckduckgo"
    assert payload["requested_backend"] == "tavily"
    assert payload["fallback_reason"] == "Tavily 请求失败（RuntimeError）"
    assert "secret provider response" not in str(payload)


def test_successful_backend_has_no_fallback_reason(monkeypatch):
    monkeypatch.setattr(
        search,
        "_run_search_backend",
        lambda query, backend, config: _result("tavily"),
    )

    payload, notices, _, backend = search.dispatch_search(
        "topic",
        Configuration(search_api=SearchAPI.TAVILY),
        0,
    )

    assert backend == "tavily"
    assert notices == []
    assert payload["fallback_reason"] is None


def test_capabilities_endpoint_returns_safe_authenticated_contract(monkeypatch):
    from fastapi.testclient import TestClient

    monkeypatch.setenv("AUTH_REQUIRED", "false")
    monkeypatch.setenv("SEARCH_API", "tavily")
    monkeypatch.setenv("TAVILY_API_KEY", "configured")
    monkeypatch.delenv("PERPLEXITY_API_KEY", raising=False)
    monkeypatch.delenv("SEARXNG_URL", raising=False)

    response = TestClient(main_module.create_app()).get("/capabilities")

    assert response.status_code == 200
    assert response.json()["search"]["default_engine"] == "tavily"
    assert [item["id"] for item in response.json()["search"]["engines"]] == [
        "advanced",
        "duckduckgo",
        "tavily",
    ]
    assert "configured" not in response.text
