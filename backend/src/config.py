import os
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class SearchAPI(Enum):
    PERPLEXITY = "perplexity"
    TAVILY = "tavily"
    DUCKDUCKGO = "duckduckgo"
    SEARXNG = "searxng"
    ADVANCED = "advanced"


class Configuration(BaseModel):
    """深度研究助手的配置项。"""

    max_web_research_loops: int = Field(
        default=3,
        title="研究深度",
        description="要执行的研究迭代次数",
    )
    local_llm: str = Field(
        default="llama3.2",
        title="本地模型名称",
        description="本地托管大模型名称（Ollama/LMStudio）",
    )
    llm_provider: str = Field(
        default="ollama",
        title="大模型提供方",
        description="提供方标识（ollama、lmstudio 或 custom）",
    )
    search_api: SearchAPI = Field(
        default=SearchAPI.DUCKDUCKGO,
        title="搜索 API",
        description="要使用的网络搜索 API",
    )
    enable_notes: bool = Field(
        default=True,
        title="启用笔记",
        description="是否将任务进度保存到笔记存储",
    )
    notes_workspace: str = Field(
        default="./notes",
        title="笔记工作区",
        description="笔记存储写入任务笔记的目录",
    )
    fetch_full_page: bool = Field(
        default=True,
        title="抓取完整页面",
        description="是否在搜索结果中包含完整页面内容",
    )
    ollama_base_url: str = Field(
        default="http://localhost:11434",
        title="Ollama 基础 URL",
        description="Ollama API 基础地址（不含 /v1 后缀）",
    )
    lmstudio_base_url: str = Field(
        default="http://localhost:1234/v1",
        title="LMStudio 基础 URL",
        description="LMStudio OpenAI 兼容 API 基础地址",
    )
    strip_thinking_tokens: bool = Field(
        default=True,
        title="移除思考标签",
        description="是否从模型响应中移除 <think> 标签内容",
    )
    use_tool_calling: bool = Field(
        default=False,
        title="使用工具调用",
        description="是否使用工具调用而不是 JSON 模式生成结构化输出",
    )
    llm_api_key: Optional[str] = Field(
        default=None,
        title="大模型 API Key",
        description="使用自定义 OpenAI 兼容服务时的可选 API Key",
    )
    llm_base_url: Optional[str] = Field(
        default=None,
        title="大模型基础 URL",
        description="使用自定义 OpenAI 兼容服务时的可选基础地址",
    )
    llm_model_id: Optional[str] = Field(
        default=None,
        title="大模型 ID",
        description="使用自定义 OpenAI 兼容服务时的可选模型标识",
    )
    database_url: Optional[str] = Field(
        default=None,
        title="数据库 URL",
        description="为未来 Postgres + pgvector 预留的数据库连接字符串",
    )
    rag_enabled: bool = Field(
        default=False,
        title="启用 RAG",
        description="为未来启用检索增强生成预留的开关",
    )
    rag_top_k: int = Field(
        default=5,
        title="RAG 检索片段数",
        description="每个任务最多注入的文档库片段数量",
    )
    rag_context_max_chars: int = Field(
        default=6000,
        title="RAG 上下文长度上限",
        description="每个任务最多注入的文档库上下文字符数",
    )
    rag_min_score: float = Field(
        default=0.1,
        title="RAG 最低匹配分",
        description="低于该分数的文档片段不会进入任务上下文",
    )
    embedding_model: Optional[str] = Field(
        default=None,
        title="嵌入模型",
        description="为未来向量索引预留的嵌入模型标识",
    )
    vector_namespace: str = Field(
        default="deep_research",
        title="向量命名空间",
        description="为未来研究历史和上传文档预留的向量命名空间",
    )

    @classmethod
    def from_env(cls, overrides: Optional[dict[str, Any]] = None) -> "Configuration":
        """根据环境变量和覆盖项创建配置对象。"""

        raw_values: dict[str, Any] = {}

        # 按字段名从环境变量读取配置值
        for field_name in cls.model_fields.keys():
            env_key = field_name.upper()
            if env_key in os.environ:
                raw_values[field_name] = os.environ[env_key]

        # 显式环境变量名称的补充映射
        env_aliases = {
            "local_llm": os.getenv("LOCAL_LLM"),
            "llm_provider": os.getenv("LLM_PROVIDER"),
            "llm_api_key": os.getenv("LLM_API_KEY"),
            "llm_model_id": os.getenv("LLM_MODEL_ID"),
            "llm_base_url": os.getenv("LLM_BASE_URL"),
            "lmstudio_base_url": os.getenv("LMSTUDIO_BASE_URL"),
            "ollama_base_url": os.getenv("OLLAMA_BASE_URL"),
            "max_web_research_loops": os.getenv("MAX_WEB_RESEARCH_LOOPS"),
            "fetch_full_page": os.getenv("FETCH_FULL_PAGE"),
            "strip_thinking_tokens": os.getenv("STRIP_THINKING_TOKENS"),
            "use_tool_calling": os.getenv("USE_TOOL_CALLING"),
            "search_api": os.getenv("SEARCH_API"),
            "enable_notes": os.getenv("ENABLE_NOTES"),
            "notes_workspace": os.getenv("NOTES_WORKSPACE"),
            "database_url": os.getenv("DATABASE_URL"),
            "rag_enabled": os.getenv("RAG_ENABLED"),
            "rag_top_k": os.getenv("RAG_TOP_K"),
            "rag_context_max_chars": os.getenv("RAG_CONTEXT_MAX_CHARS"),
            "rag_min_score": os.getenv("RAG_MIN_SCORE"),
            "embedding_model": os.getenv("EMBEDDING_MODEL"),
            "vector_namespace": os.getenv("VECTOR_NAMESPACE"),
        }

        for key, value in env_aliases.items():
            if value is not None:
                raw_values.setdefault(key, value)

        if overrides:
            for key, value in overrides.items():
                if value is not None:
                    raw_values[key] = value

        return cls(**raw_values)

    def sanitized_ollama_url(self) -> str:
        """确保 Ollama 基础地址包含 OpenAI 客户端需要的 /v1 后缀。"""

        base = self.ollama_base_url.rstrip("/")
        if not base.endswith("/v1"):
            base = f"{base}/v1"
        return base

    def resolved_model(self) -> Optional[str]:
        """尽力解析当前应使用的模型标识。"""

        return self.llm_model_id or self.local_llm

