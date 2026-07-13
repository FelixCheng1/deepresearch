"""通过 HTTP 暴露 DeepResearchAgent 的 FastAPI 入口。"""

from __future__ import annotations

import json
import os
import sys
from contextlib import asynccontextmanager
from email import policy
from email.parser import BytesParser
from typing import Any, Dict, Iterator

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from loguru import logger
from pydantic import BaseModel, Field

from agent import DeepResearchAgent
from config import Configuration, SearchAPI
from services.document_worker import start_document_worker
from services.repository import ResearchRepository, create_research_repository

load_dotenv()

# 添加控制台日志处理程序
logger.add(
    sys.stderr,
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
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


def _mask_secret(value: str | None, visible: int = 4) -> str:
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
        f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n".encode()
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
    app_config = Configuration.from_env()
    memory_repository: ResearchRepository = create_research_repository(app_config)

    def get_repository(config: Configuration) -> ResearchRepository:
        if config.database_url:
            return create_research_repository(config)
        return memory_repository

    @asynccontextmanager
    async def lifespan(app: FastAPI):
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
        stop_event, worker = start_document_worker(
            config=config,
            repository_factory=get_repository,
        )
        app.state.document_worker_stop = stop_event
        app.state.document_worker = worker
        try:
            yield
        finally:
            stop_event.set()
            worker.join(timeout=2)

    app = FastAPI(title="LangGraph Deep Researcher", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=app_config.cors_origin_list(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
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
        """上传文档并后台解析、切块入库。"""

        filename, content_type, raw_bytes = await _read_uploaded_file(request)
        suffix = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if suffix not in {"txt", "md", "pdf", "docx"}:
            raise HTTPException(status_code=400, detail="仅支持 .txt、.md、.pdf 和 .docx 文档")

        if not raw_bytes:
            raise HTTPException(status_code=400, detail="上传文件为空")

        config = Configuration.from_env()
        repository = get_repository(config)
        document = repository.create_pending_document(
            filename=filename,
            content_type=content_type or "application/octet-stream",
            size_bytes=len(raw_bytes),
        )
        repository.enqueue_document_job(document.id, raw_bytes)
        return {
            "document": {
                "id": document.id,
                "filename": document.filename,
                "content_type": document.content_type,
                "size_bytes": document.size_bytes,
                "summary": document.summary,
                "status": document.status,
                "error_message": document.error_message,
                "processed_at": document.processed_at.isoformat() if document.processed_at else None,
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


    @app.post("/documents/{document_id}/retry")
    def retry_document(document_id: str) -> Dict[str, Any]:
        config = Configuration.from_env()
        repository = get_repository(config)
        document = repository.get_document(document_id)
        if document is None:
            raise HTTPException(status_code=404, detail="未找到文档")
        if document.get("status") != "failed":
            raise HTTPException(status_code=400, detail="仅失败文档可以重试")
        job = repository.retry_failed_document(document_id)
        if job is None:
            raise HTTPException(status_code=400, detail="文档缺少可重试的上传内容")
        refreshed = repository.get_document(document_id)
        return {"document": refreshed, "job": {key: value for key, value in job.items() if key != "payload"}}

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
    import uvicorn

    config = Configuration.from_env()
    # Windows 下 reload 会启动子进程并重新导入 LangGraph，直接运行脚本时默认关闭更稳。
    reload_enabled = os.getenv("UVICORN_RELOAD", "").lower() in {"1", "true", "yes"}

    uvicorn.run(
        "main:app",
        host=config.host,
        port=config.port,
        reload=reload_enabled,
        log_level=config.log_level.lower(),
    )
