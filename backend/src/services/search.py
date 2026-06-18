"""搜索分发辅助函数，输出适合 LangChain 流程使用的标准化结果。"""

from __future__ import annotations

import logging
import os
from typing import Any, Optional, Tuple

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


def dispatch_search(
    query: str,
    config: Configuration,
    loop_count: int,
) -> Tuple[dict[str, Any] | None, list[str], Optional[str], str]:
    """执行配置的搜索后端，并标准化响应载荷。"""

    search_api = get_config_value(config.search_api)

    try:
        raw_response = _run_search_backend(query, search_api, config)
    except Exception as exc:  # pragma: no cover - 防御性日志
        logger.exception("Search backend %s failed: %s", search_api, exc)
        raise

    if isinstance(raw_response, str):
        notices = [raw_response]
        logger.warning("Search backend %s returned text notice: %s", search_api, raw_response)
        payload: dict[str, Any] = {
            "results": [],
            "backend": search_api,
            "answer": None,
            "notices": notices,
        }
    else:
        payload = raw_response
        notices = list(payload.get("notices") or [])

    backend_label = str(payload.get("backend") or search_api)
    answer_text = payload.get("answer")
    results = payload.get("results", [])

    if notices:
        for notice in notices:
            logger.info("Search notice (%s): %s", backend_label, notice)

    logger.info(
        "Search backend=%s resolved_backend=%s answer=%s results=%s",
        search_api,
        backend_label,
        bool(answer_text),
        len(results),
    )

    return payload, notices, answer_text, backend_label


def _run_search_backend(query: str, search_api: str, config: Configuration) -> dict[str, Any] | str:
    if search_api == "duckduckgo":
        return _duckduckgo_search(query)
    if search_api == "tavily":
        return _tavily_search(query, config)
    if search_api == "searxng":
        return _searxng_search(query)
    if search_api == "perplexity":
        return _perplexity_search(query, config)
    if search_api == "advanced":
        try:
            return _tavily_search(query, config)
        except Exception as exc:
            logger.info("Advanced search falling back to DuckDuckGo: %s", exc)
            return _duckduckgo_search(query)
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
    base_url = os.getenv("SEARXNG_URL") or "http://localhost:8888"
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
    answer_text: Optional[str],
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
