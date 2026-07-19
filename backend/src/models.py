"""深度研究工作流使用的状态模型。"""

import operator
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List

from typing_extensions import Annotated


@dataclass(kw_only=True)
class TodoItem:
    """单个待办任务项。"""

    id: int
    title: str
    intent: str
    query: str
    status: str = field(default="pending")
    summary: str | None = field(default=None)
    sources_summary: str | None = field(default=None)
    notices: list[str] = field(default_factory=list)
    note_id: str | None = field(default=None)
    note_path: str | None = field(default=None)
    stream_token: str | None = field(default=None)


@dataclass(kw_only=True)
class SummaryState:
    research_topic: str = field(default=None)  # 报告主题
    search_query: str = field(default=None)  # 已废弃的占位字段
    web_research_results: Annotated[list, operator.add] = field(default_factory=list)
    sources_gathered: Annotated[list, operator.add] = field(default_factory=list)
    research_loop_count: int = field(default=0)  # 研究循环次数
    running_summary: str = field(default=None)  # 兼容旧接口的总结字段
    todo_items: Annotated[list, operator.add] = field(default_factory=list)
    structured_report: str | None = field(default=None)
    report_note_id: str | None = field(default=None)
    report_note_path: str | None = field(default=None)
    current_task_index: int = field(default=0)
    current_task_id: int | None = field(default=None)
    current_context: str = field(default="")
    current_sources_summary: str = field(default="")
    current_search_result: dict | None = field(default=None)
    current_answer_text: str | None = field(default=None)
    current_search_backend: str | None = field(default=None)
    current_retrieval_context: str = field(default="")
    stream_events: list[dict] = field(default_factory=list)


@dataclass(kw_only=True)
class SummaryStateInput:
    research_topic: str = field(default=None)  # 报告主题


@dataclass(kw_only=True)
class SummaryStateOutput:
    running_summary: str = field(default=None)  # 向后兼容的文本
    report_markdown: str | None = field(default=None)
    todo_items: List[TodoItem] = field(default_factory=list)


@dataclass(kw_only=True)
class ResearchRun:
    """为持久化预留的研究运行元数据。"""

    id: str
    topic: str
    search_api: str
    owner_id: str = "local-dev"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(kw_only=True)
class ResearchTask:
    """为持久化预留的任务快照。"""

    run_id: str
    task_id: int
    title: str
    intent: str
    query: str
    status: str
    summary: str | None = None
    sources_summary: str | None = None
    note_id: str | None = None
    note_path: str | None = None


@dataclass(kw_only=True)
class ResearchSource:
    """为持久化预留的来源快照。"""

    run_id: str
    task_id: int
    title: str
    url: str
    content: str = ""


@dataclass(kw_only=True)
class ResearchReport:
    """为持久化预留的报告快照。"""

    run_id: str
    markdown: str
    note_id: str | None = None
    note_path: str | None = None


@dataclass(kw_only=True)
class ResearchToolCall:
    """一次可回放的工具调用事件。"""

    run_id: str
    event_id: int
    agent: str
    tool: str
    parameters: dict = field(default_factory=dict)
    result: str = ""
    task_id: int | None = None
    note_id: str | None = None
    step: int | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(kw_only=True)
class ResearchDocumentChunk:
    """上传文档切块后的检索片段。"""

    id: str
    document_id: str
    document_title: str
    chunk_index: int
    text: str
    metadata: dict = field(default_factory=dict)
    embedding: list[float] | None = None
    embedding_model: str | None = None
    embedded_at: datetime | None = None


@dataclass(kw_only=True)
class ResearchDocument:
    """上传到文档库的原始文本文件。"""

    id: str
    owner_id: str = "local-dev"
    filename: str
    content_type: str
    size_bytes: int
    raw_text: str = ""
    summary: str | None = None
    status: str = "ready"
    error_message: str | None = None
    processed_at: datetime | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    chunks: list[ResearchDocumentChunk] = field(default_factory=list)
