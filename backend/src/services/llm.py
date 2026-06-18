"""LangChain 聊天模型工厂。"""

from __future__ import annotations

from langchain_openai import ChatOpenAI

from config import Configuration


def create_chat_model(config: Configuration) -> ChatOpenAI:
    """根据应用配置创建 OpenAI 兼容的聊天模型。"""

    provider = (config.llm_provider or "").strip().lower()
    base_url = config.llm_base_url
    api_key = config.llm_api_key

    if provider == "ollama":
        base_url = config.sanitized_ollama_url()
        api_key = api_key or "ollama"
    elif provider == "lmstudio":
        base_url = config.lmstudio_base_url
        api_key = api_key or "lmstudio"

    return ChatOpenAI(
        model=config.resolved_model() or "gpt-4o-mini",
        api_key=api_key or "not-needed",
        base_url=base_url,
        temperature=0,
    )


def message_content(response: object) -> str:
    """从 LangChain 消息式响应中提取文本内容。"""

    content = getattr(response, "content", response)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                value = item.get("text") or item.get("content")
                if value:
                    parts.append(str(value))
        return "".join(parts)
    return str(content or "")
