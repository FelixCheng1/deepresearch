"""通过 HTTP 暴露 DeepResearchAgent 的 FastAPI 入口。"""

from __future__ import annotations

import json
import sys
from email import policy
from email.parser import BytesParser
from typing import Any, Dict, Iterator, Optional

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from loguru import logger
from pydantic import BaseModel, Field

from config import Configuration, SearchAPI
from agent import DeepResearchAgent
from services.repository import ResearchRepository, create_research_repository

# 添加控制台日志处理程序
logger.add(
    sys.stderr,
    level="INFO",
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <4}</level> | <cyan>using_function:{function}</cyan> | <cyan>{file}:{line}</cyan> | <level>{message}</level>",
    colorize=True,
)


# 添加错误日志文件处理程序
logger.add(
    sink=sys.stderr,
    level="ERROR",
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <4}</level> | <cyan>using_function:{function}</cyan> | <cyan>{file}:{line}</cyan> | <level>{message}</level>",
    colorize=True,
)


class ResearchRequest(BaseModel):
    """触发研究任务的请求体。"""

    topic: str = Field(..., description="用户提供的研究主题")
    search_api: SearchAPI | None = Field(
        default=None,
        description="覆盖环境变量配置的默认搜索后端",
    )


class ResearchResponse(BaseModel):
    """包含生成报告和结构化任务的 HTTP 响应。"""

    report_markdown: str = Field(
        ..., description="包含分节内容的 Markdown 格式研究报告"
    )
    todo_items: list[dict[str, Any]] = Field(
        default_factory=list,
        description="包含总结和来源信息的结构化 TODO 项",
    )


def _mask_secret(value: Optional[str], visible: int = 4) -> str:
    """遮盖敏感令牌，同时保留首尾少量字符。"""
    if not value:
        return "unset"

    if len(value) <= visible * 2:
        return "*" * len(value)

    return f"{value[:visible]}...{value[-visible:]}"



async def _read_uploaded_file(request: Request) -> tuple[str, str, bytes]:
    """使用标准库解析单文件 multipart 上传，避免普通测试依赖 python-multipart。"""

    content_type = request.headers.get("content-type", "")
    body = await request.body()
    if not content_type.startswith("multipart/form-data"):
        raise HTTPException(status_code=400, detail="请使用 multipart/form-data 上传文档")

    raw_message = (
        f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n".encode("utf-8")
        + body
    )
    message = BytesParser(policy=policy.default).parsebytes(raw_message)
    for part in message.iter_parts():
        if part.get_content_disposition() != "form-data":
            continue
        filename = part.get_filename()
        if not filename:
            continue
        payload = part.get_payload(decode=True) or b""
        return filename, part.get_content_type(), payload

    raise HTTPException(status_code=400, detail="未找到上传文件")

def _build_config(payload: ResearchRequest) -> Configuration:
    overrides: Dict[str, Any] = {}

    if payload.search_api is not None:
        overrides["search_api"] = payload.search_api

    return Configuration.from_env(overrides=overrides)


def create_app() -> FastAPI:
    app = FastAPI(title="LangGraph Deep Researcher")
    memory_config = Configuration.from_env()
    memory_repository: ResearchRepository = create_research_repository(memory_config)

    def get_repository(config: Configuration) -> ResearchRepository:
        if config.database_url:
            return create_research_repository(config)
        return memory_repository

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.on_event("startup")
    def log_startup_configuration() -> None:
        config = Configuration.from_env()

        if config.llm_provider == "ollama":
            base_url = config.sanitized_ollama_url()
        elif config.llm_provider == "lmstudio":
            base_url = config.lmstudio_base_url
        else:
            base_url = config.llm_base_url or "unset"

        logger.info(
            "DeepResearch configuration loaded: provider={} model={} base_url={} search_api={} "
            "max_loops={} fetch_full_page={} tool_calling={} strip_thinking={} api_key={}",
            config.llm_provider,
            config.resolved_model() or "unset",
            base_url,
            (config.search_api.value if isinstance(config.search_api, SearchAPI) else config.search_api),
            config.max_web_research_loops,
            config.fetch_full_page,
            config.use_tool_calling,
            config.strip_thinking_tokens,
            _mask_secret(config.llm_api_key),
        )

    @app.get("/healthz")
    def health_check() -> Dict[str, str]:
        return {"status": "ok"}

    @app.get("/research/runs")
    def list_research_runs(limit: int = 20) -> Dict[str, Any]:
        """列出最近的研究历史。"""

        config = Configuration.from_env()
        repository = get_repository(config)
        return {"runs": repository.list_runs(limit=limit)}

    @app.get("/research/runs/{run_id}")
    def get_research_run(run_id: str) -> Dict[str, Any]:
        """读取一次研究运行的完整快照。"""

        config = Configuration.from_env()
        repository = get_repository(config)
        run = repository.get_run(run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="未找到研究历史")
        return run

    @app.post("/documents/upload")
    async def upload_document(request: Request) -> Dict[str, Any]:
        """上传 .txt 或 .md 文档并写入文本切块。"""

        filename, content_type, raw_bytes = await _read_uploaded_file(request)
        suffix = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if suffix not in {"txt", "md"}:
            raise HTTPException(status_code=400, detail="仅支持 .txt 和 .md 文档")

        if not raw_bytes:
            raise HTTPException(status_code=400, detail="上传文件为空")
        try:
            raw_text = raw_bytes.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise HTTPException(status_code=400, detail="文档必须使用 UTF-8 文本编码") from exc
        if not raw_text.strip():
            raise HTTPException(status_code=400, detail="文档没有可检索文本")

        config = Configuration.from_env()
        repository = get_repository(config)
        document = repository.save_document(
            filename=filename,
            content_type=content_type or ("text/markdown" if suffix == "md" else "text/plain"),
            raw_text=raw_text,
            size_bytes=len(raw_bytes),
        )
        return {
            "document": {
                "id": document.id,
                "filename": document.filename,
                "content_type": document.content_type,
                "size_bytes": document.size_bytes,
                "summary": document.summary,
                "created_at": document.created_at.isoformat(),
                "chunk_count": len(document.chunks),
            }
        }

    @app.get("/documents")
    def list_documents(limit: int = 50) -> Dict[str, Any]:
        """列出已上传文档。"""

        config = Configuration.from_env()
        repository = get_repository(config)
        return {"documents": repository.list_documents(limit=limit)}

    @app.get("/documents/{document_id}")
    def get_document(document_id: str) -> Dict[str, Any]:
        """读取单个文档及其切块。"""

        config = Configuration.from_env()
        repository = get_repository(config)
        document = repository.get_document(document_id)
        if document is None:
            raise HTTPException(status_code=404, detail="未找到文档")
        return document

    @app.delete("/documents/{document_id}")
    def delete_document(document_id: str) -> Dict[str, Any]:
        """删除单个文档及其切块。"""

        config = Configuration.from_env()
        repository = get_repository(config)
        if not repository.delete_document(document_id):
            raise HTTPException(status_code=404, detail="未找到文档")
        return {"deleted": True, "document_id": document_id}

    @app.post("/research", response_model=ResearchResponse)
    def run_research(payload: ResearchRequest) -> ResearchResponse:
        try:
            config = _build_config(payload)
            agent = DeepResearchAgent(config=config, repository=get_repository(config))
            result = agent.run(payload.topic)
        except ValueError as exc:  # 通常来自不受支持的配置
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:  # pragma: no cover - 防御性保护
            raise HTTPException(status_code=500, detail="研究失败") from exc

        todo_payload = [
            {
                "id": item.id,
                "title": item.title,
                "intent": item.intent,
                "query": item.query,
                "status": item.status,
                "summary": item.summary,
                "sources_summary": item.sources_summary,
                "note_id": item.note_id,
                "note_path": item.note_path,
            }
            for item in result.todo_items
        ]

        return ResearchResponse(
            report_markdown=(result.report_markdown or result.running_summary or ""),
            todo_items=todo_payload,
        )

    @app.post("/research/stream")
    def stream_research(payload: ResearchRequest) -> StreamingResponse:
        try:
            config = _build_config(payload)
            agent = DeepResearchAgent(config=config, repository=get_repository(config))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        def event_iterator() -> Iterator[str]:
            try:
                for event in agent.run_stream(payload.topic):
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
            except Exception as exc:  # pragma: no cover - 防御性保护
                logger.exception("Streaming research failed")
                error_payload = {"type": "error", "detail": str(exc)}
                yield f"data: {json.dumps(error_payload, ensure_ascii=False)}\n\n"

        return StreamingResponse(
            event_iterator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            },
        )

    return app


app = create_app()


if __name__ == "__main__":
    import os

    import uvicorn

    # Windows 下 reload 会启动子进程并重新导入 LangGraph，直接运行脚本时默认关闭更稳。
    reload_enabled = os.getenv("UVICORN_RELOAD", "").lower() in {"1", "true", "yes"}

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=reload_enabled,
        log_level="info"
    )
