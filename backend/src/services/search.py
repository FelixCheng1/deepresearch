"""搜索分发辅助函数，输出适合 LangChain 流程使用的标准化结果。"""

from __future__ import annotations

import logging
import os
from typing import Any, Tuple

import requests
from ddgs import DDGS
from tavily import TavilyClient

from config import Configuration
from utils import (
    deduplicate_and_format_sources,
    format_sources,
    get_config_value,
)

logger = logging.getLogger(__name__)

MAX_TOKENS_PER_SOURCE = 2000

SEARCH_ENGINE_LABELS = {
    "advanced": "智能降级",
    "duckduckgo": "DuckDuckGo",
    "tavily": "Tavily",
    "perplexity": "Perplexity",
    "searxng": "SearXNG",
}

SEARCH_ENGINE_DESCRIPTIONS = {
    "advanced": "优先使用 Tavily；不可用或请求失败时自动降级到 DuckDuckGo。",
    "duckduckgo": "无需 API 密钥的网页搜索。",
    "tavily": "面向 AI 研究的网页搜索，需要服务端配置 API 密钥。",
    "perplexity": "返回 AI 总结和引用，需要服务端配置 API 密钥。",
    "searxng": "连接服务端配置的自建 SearXNG 实例。",
}


def get_search_capabilities(config: Configuration) -> dict[str, Any]:
    """返回不包含密钥的搜索能力清单。"""

    available = {
        "advanced": True,
        "duckduckgo": True,
        "tavily": bool(os.getenv("TAVILY_API_KEY")),
        "perplexity": bool(os.getenv("PERPLEXITY_API_KEY")),
        "searxng": bool(os.getenv("SEARXNG_URL")),
    }
    engines = [
        {
            "id": engine,
            "label": SEARCH_ENGINE_LABELS[engine],
            "description": SEARCH_ENGINE_DESCRIPTIONS[engine],
        }
        for engine in ("advanced", "duckduckgo", "tavily", "perplexity", "searxng")
        if available[engine]
    ]
    default_engine = str(get_config_value(config.search_api))
    return {
        "default_engine": default_engine,
        "default_available": available.get(default_engine, False),
        "engines": engines,
    }


def dispatch_search(
    query: str,
    config: Configuration,
    loop_count: int,
) -> Tuple[dict[str, Any] | None, list[str], str | None, str]:
    """执行配置的搜索后端，并标准化响应载荷。"""

    requested_backend = str(get_config_value(config.search_api))
    primary_backend = requested_backend
    fallback_reason: str | None = None

    if requested_backend == "advanced":
        if os.getenv("TAVILY_API_KEY"):
            primary_backend = "tavily"
        else:
            primary_backend = "duckduckgo"
            fallback_reason = "Tavily 未配置 API 密钥"

    try:
        raw_response = _run_search_backend(query, primary_backend, config)
    except Exception as exc:
        logger.exception("Search backend %s failed: %s", primary_backend, exc)
        if primary_backend == "duckduckgo":
            raise
        fallback_reason = f"{SEARCH_ENGINE_LABELS.get(primary_backend, primary_backend)} 请求失败（{type(exc).__name__}）"
        raw_response = _duckduckgo_search(query)

    if isinstance(raw_response, str):
        notices = [raw_response]
        logger.warning("Search backend %s returned text notice: %s", primary_backend, raw_response)
        payload: dict[str, Any] = {
            "results": [],
            "backend": primary_backend,
            "answer": None,
            "notices": notices,
        }
    else:
        payload = raw_response
        notices = list(payload.get("notices") or [])

    if primary_backend != "duckduckgo" and not _has_usable_content(payload):
        fallback_reason = notices[0] if notices else f"{SEARCH_ENGINE_LABELS.get(primary_backend, primary_backend)} 未返回有效内容"
        payload = _duckduckgo_search(query)
        notices = list(payload.get("notices") or [])

    actual_backend = str(payload.get("backend") or primary_backend)
    if actual_backend != requested_backend and fallback_reason:
        notices.insert(
            0,
            f"搜索后端已从 {requested_backend} 降级为 {actual_backend}：{fallback_reason}",
        )
    payload["requested_backend"] = requested_backend
    payload["backend"] = actual_backend
    payload["fallback_reason"] = fallback_reason if actual_backend != requested_backend else None
    payload["notices"] = notices

    backend_label = actual_backend
    answer_text = payload.get("answer")
    results = payload.get("results", [])

    if notices:
        for notice in notices:
            logger.info("Search notice (%s): %s", backend_label, notice)

    logger.info(
        "Search backend=%s resolved_backend=%s answer=%s results=%s",
        requested_backend,
        backend_label,
        bool(answer_text),
        len(results),
    )

    return payload, notices, answer_text, backend_label


def _has_usable_content(payload: dict[str, Any]) -> bool:
    return bool(payload.get("results") or payload.get("answer"))


def _run_search_backend(query: str, search_api: str, config: Configuration) -> dict[str, Any] | str:
    if search_api == "duckduckgo":
        return _duckduckgo_search(query)
    if search_api == "tavily":
        return _tavily_search(query, config)
    if search_api == "searxng":
        return _searxng_search(query)
    if search_api == "perplexity":
        return _perplexity_search(query, config)
    return {
        "results": [],
        "backend": search_api,
        "answer": None,
        "notices": [f"不支持的搜索后端：{search_api}"],
    }


def _duckduckgo_search(query: str) -> dict[str, Any]:
    rows = list(DDGS().text(query, max_results=5))
    results = [
        {
            "title": item.get("title") or item.get("href") or "",
            "url": item.get("href") or item.get("url") or "",
            "content": item.get("body") or "",
            "raw_content": item.get("body") or "",
        }
        for item in rows
    ]
    return {"results": results, "backend": "duckduckgo", "answer": None, "notices": []}


def _tavily_search(query: str, config: Configuration) -> dict[str, Any]:
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        return {
            "results": [],
            "backend": "tavily",
            "answer": None,
            "notices": ["未配置 TAVILY_API_KEY"],
        }

    client = TavilyClient(api_key=api_key)
    response = client.search(
        query=query,
        max_results=5,
        include_raw_content=config.fetch_full_page,
        include_answer=True,
    )
    results = [
        {
            "title": item.get("title") or item.get("url") or "",
            "url": item.get("url") or "",
            "content": item.get("content") or "",
            "raw_content": item.get("raw_content") or item.get("content") or "",
        }
        for item in response.get("results", [])
    ]
    return {
        "results": results,
        "backend": "tavily",
        "answer": response.get("answer"),
        "notices": [],
    }


def _searxng_search(query: str) -> dict[str, Any]:
    base_url = os.getenv("SEARXNG_URL")
    if not base_url:
        return {
            "results": [],
            "backend": "searxng",
            "answer": None,
            "notices": ["未配置 SEARXNG_URL"],
        }
    response = requests.get(
        f"{base_url.rstrip('/')}/search",
        params={"q": query, "format": "json"},
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    results = [
        {
            "title": item.get("title") or item.get("url") or "",
            "url": item.get("url") or "",
            "content": item.get("content") or "",
            "raw_content": item.get("content") or "",
        }
        for item in payload.get("results", [])[:5]
    ]
    return {"results": results, "backend": "searxng", "answer": None, "notices": []}


def _perplexity_search(query: str, config: Configuration) -> dict[str, Any]:
    api_key = os.getenv("PERPLEXITY_API_KEY")
    if not api_key:
        return {
            "results": [],
            "backend": "perplexity",
            "answer": None,
            "notices": ["未配置 PERPLEXITY_API_KEY"],
        }

    response = requests.post(
        "https://api.perplexity.ai/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": os.getenv("PERPLEXITY_MODEL", "sonar"),
            "messages": [{"role": "user", "content": query}],
        },
        timeout=60,
    )
    response.raise_for_status()
    payload = response.json()
    answer = payload.get("choices", [{}])[0].get("message", {}).get("content")
    citations = payload.get("citations") or []
    results = [
        {
            "title": str(citation),
            "url": str(citation),
            "content": answer or "",
            "raw_content": answer or "",
        }
        for citation in citations[:5]
    ]
    return {"results": results, "backend": "perplexity", "answer": answer, "notices": []}


def prepare_research_context(
    search_result: dict[str, Any] | None,
    answer_text: str | None,
    config: Configuration,
) -> tuple[str, str]:
    """为下游模型构建结构化上下文和来源摘要。"""

    sources_summary = format_sources(search_result)
    context = deduplicate_and_format_sources(
        search_result or {"results": []},
        max_tokens_per_source=MAX_TOKENS_PER_SOURCE,
        fetch_full_page=config.fetch_full_page,
    )

    if answer_text:
        context = f"AI直接答案：\n{answer_text}\n\n{context}"

    return sources_summary, context
