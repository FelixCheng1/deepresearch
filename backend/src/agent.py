"""协调深度研究工作流的编排器。"""

from __future__ import annotations

import logging
import queue
import re
import threading
from typing import Any, Iterator
from uuid import uuid4

from config import Configuration
from models import (
    ResearchReport,
    ResearchRun,
    ResearchSource,
    ResearchTask,
    SummaryState,
    SummaryStateOutput,
    TodoItem,
)
from services.graph import build_research_graph, build_task_graph, send_task
from services.llm import create_chat_model
from services.note_store import NoteStore
from services.planner import PlanningService
from services.repository import ResearchRepository, create_research_repository
from services.reporter import ReportingService
from services.retriever import DisabledRetriever, Retriever
from services.search import dispatch_search, prepare_research_context
from services.summarizer import SummarizationService
from services.tool_events import ToolCallTracker

logger = logging.getLogger(__name__)


WORKFLOW_LABELS = {
    "plan_tasks": "规划研究任务",
    "dispatch_tasks": "分发并行任务",
    "join_tasks": "汇总任务结果",
    "prepare_task": "准备任务",
    "retrieve_documents": "检索文档库",
    "search_web": "搜索网页资料",
    "summarize_task": "总结任务发现",
    "persist_task": "保存任务状态",
    "write_report": "撰写最终报告",
    "persist_report": "保存最终报告",
}


class DeepResearchAgent:
    """使用 LangGraph 编排 TODO 驱动的研究工作流。"""

    def __init__(
        self,
        config: Configuration | None = None,
        *,
        repository: ResearchRepository | None = None,
        retriever: Retriever | None = None,
        chat_model: Any | None = None,
    ) -> None:
        """使用配置和共享工具初始化编排器。"""

        self.config = config or Configuration.from_env()
        self.llm = chat_model or create_chat_model(self.config)

        self.note_store = (
            NoteStore(workspace=self.config.notes_workspace)
            if self.config.enable_notes
            else None
        )
        self.repository = repository or create_research_repository(self.config)
        self.retriever = retriever or DisabledRetriever(self.config)
        self._tool_tracker = ToolCallTracker(
            self.config.notes_workspace if self.config.enable_notes else None
        )
        self.run_id = uuid4().hex
        self._streaming = False
        self._event_queue: queue.Queue[dict[str, Any]] | None = None
        self._shared_lock = threading.Lock()
        self.max_parallel_tasks = 3

        self.planner = PlanningService(self.llm, self.config)
        self.summarizer = SummarizationService(lambda: self.llm, self.config)
        self.reporting = ReportingService(self.llm, self.config)
        self.task_graph = build_task_graph()
        self.graph = build_research_graph()

    # ------------------------------------------------------------------
    # 公共接口
    # ------------------------------------------------------------------
    def run(self, topic: str) -> SummaryStateOutput:
        """执行研究工作流并返回最终报告。"""

        state = SummaryState(research_topic=topic)
        result = self.graph.invoke({"agent": self, "state": state, "task_cursor": 0, "task_results": []})
        state = result["state"]

        return SummaryStateOutput(
            running_summary=state.running_summary,
            report_markdown=state.structured_report,
            todo_items=state.todo_items,
        )

    def run_stream(self, topic: str) -> Iterator[dict[str, Any]]:
        """执行同一套 LangGraph 工作流，并逐步产出 SSE 事件。"""

        state = SummaryState(research_topic=topic)
        self._streaming = True
        self._event_queue = queue.Queue()
        self._emit_event(state, {"type": "status", "message": "初始化研究流程"})

        error_holder: dict[str, Exception] = {}

        def run_graph() -> None:
            try:
                self.graph.invoke(
                    {"agent": self, "state": state, "task_cursor": 0, "task_results": []}
                )
            except Exception as exc:  # pragma: no cover - 外层会把异常转成 SSE
                logger.exception("Streaming research failed")
                error_holder["error"] = exc

        worker = threading.Thread(target=run_graph, name="research-langgraph-stream", daemon=True)
        worker.start()

        try:
            while worker.is_alive() or (self._event_queue and not self._event_queue.empty()):
                try:
                    yield self._event_queue.get(timeout=0.1)
                except queue.Empty:
                    continue

            if "error" in error_holder:
                yield {"type": "error", "detail": str(error_holder["error"])}
                return
        finally:
            worker.join(timeout=0.2)
            self._streaming = False
            self._event_queue = None

        yield {"type": "done"}

    # ------------------------------------------------------------------
    # LangGraph 节点实现
    # ------------------------------------------------------------------
    def _graph_plan_tasks(self, payload: dict[str, Any]) -> dict[str, SummaryState]:
        state = payload["state"]
        self._workflow(state, "plan_tasks", "in_progress")

        state.todo_items = self.planner.plan_todo_list(state)
        self._emit_events(state, self._drain_tool_events(state, step=0))

        if not state.todo_items:
            logger.info("No TODO items generated; falling back to default task list")
            state.todo_items = self.planner.create_fallback_tasks(state)
        elif len(state.todo_items) < 3:
            logger.info("Planner produced too few tasks; supplementing fallback tasks")
            existing_titles = {task.title for task in state.todo_items}
            supplemental = self.planner.create_fallback_tasks(
                state,
                start_id=len(state.todo_items) + 1,
                count=4 - len(state.todo_items),
                existing_titles=existing_titles,
            )
            state.todo_items.extend(supplemental)

        self.repository.save_run(
            ResearchRun(
                id=self.run_id,
                topic=state.research_topic or "",
                search_api=str(self.config.search_api.value),
            )
        )

        for index, task in enumerate(state.todo_items, start=1):
            task.stream_token = f"task_{task.id}"
            self._ensure_task_note(task)
            self.repository.save_task(self._task_snapshot(task))

        self._emit_event(
            state,
            {
                "type": "todo_list",
                "tasks": [self._serialize_task(task) for task in state.todo_items],
                "step": 0,
            },
        )
        self._emit_event(state, self._workflow_graph_event(state))
        self._workflow(state, "plan_tasks", "completed", detail=f"生成 {len(state.todo_items)} 个任务")
        return {"state": state, "task_cursor": 0, "task_results": []}

    def _graph_dispatch_tasks(self, payload: dict[str, Any]) -> dict[str, Any]:
        state = payload["state"]
        cursor = int(payload.get("task_cursor") or 0)
        remaining = max(0, len(state.todo_items) - cursor)
        batch_size = min(self.max_parallel_tasks, remaining)
        if batch_size:
            detail = f"并行分发 {batch_size} 个任务"
            self._workflow(state, "dispatch_tasks", "in_progress", detail=detail)
            self._workflow(state, "dispatch_tasks", "completed", detail=detail)
        else:
            detail = "没有待分发任务"
            self._workflow(state, "dispatch_tasks", "skipped", detail=detail)
        return {}

    def _graph_route_task_batch(self, payload: dict[str, Any]) -> list[Any] | str:
        state = payload["state"]
        cursor = int(payload.get("task_cursor") or 0)
        batch = state.todo_items[cursor : cursor + self.max_parallel_tasks]
        if not batch:
            return "join_tasks"

        return [
            send_task(
                "run_task",
                {
                    "agent": self,
                    "state": state,
                    "task": task,
                    "task_index": cursor + offset,
                },
            )
            for offset, task in enumerate(batch)
        ]

    def _graph_run_task(self, payload: dict[str, Any]) -> dict[str, list[TodoItem]]:
        state = payload["state"]
        task = payload["task"]
        try:
            result = self.task_graph.invoke(payload)
            task = result.get("task", task)
        except Exception as exc:
            logger.exception("Task %s failed", task.id)
            task.status = "skipped"
            task.summary = f"任务执行失败：{exc}"
            self._workflow(state, "persist_task", "failed", task=task, detail=str(exc))
            self._emit_task_status(state, task)
        return {"task_results": [task]}

    def _graph_join_tasks(self, payload: dict[str, Any]) -> dict[str, Any]:
        state = payload["state"]
        results = payload.get("task_results") or []
        if results:
            by_id = {task.id: task for task in results}
            state.todo_items = [by_id.get(task.id, task) for task in state.todo_items]

        unique_done = {task.id for task in results}
        cursor = min(len(unique_done), len(state.todo_items))
        detail = f"已汇总 {cursor} / {len(state.todo_items)} 个任务"
        self._workflow(state, "join_tasks", "completed", detail=detail)
        return {"state": state, "task_cursor": cursor}

    def _graph_after_join(self, payload: dict[str, Any]) -> str:
        state = payload["state"]
        cursor = int(payload.get("task_cursor") or 0)
        if cursor < len(state.todo_items):
            return "dispatch_tasks"
        return "write_report"

    def _task_prepare_task(self, payload: dict[str, Any]) -> dict[str, Any]:
        state = payload["state"]
        task = payload["task"]

        self._workflow(state, "prepare_task", "in_progress", task=task)
        task.status = "in_progress"
        self._emit_task_status(state, task)
        self._workflow(state, "prepare_task", "completed", task=task)
        return {"task": task}

    def _task_should_retrieve(self, payload: dict[str, Any]) -> str:
        state = payload["state"]
        task = payload["task"]
        if not self.config.rag_enabled:
            self._workflow(
                state,
                "retrieve_documents",
                "skipped",
                task=task,
                detail="RAG 未启用，跳过文档库检索",
            )
            return "search_web"
        return "retrieve_documents"

    def _task_retrieve_documents(self, payload: dict[str, Any]) -> dict[str, Any]:
        state = payload["state"]
        task = payload["task"]

        self._workflow(state, "retrieve_documents", "in_progress", task=task)
        chunks = self.retriever.retrieve(task.query)
        if chunks:
            retrieval_context = "\n\n".join(chunk.text for chunk in chunks)
            detail = f"找到 {len(chunks)} 个文档片段"
            status = "completed"
        else:
            retrieval_context = ""
            detail = "未找到可用文档片段"
            status = "skipped"
        self._workflow(state, "retrieve_documents", status, task=task, detail=detail)
        return {"retrieval_context": retrieval_context}

    def _task_search_web(self, payload: dict[str, Any]) -> dict[str, Any]:
        state = payload["state"]
        task = payload["task"]

        self._workflow(state, "search_web", "in_progress", task=task)
        search_result, notices, answer_text, backend = dispatch_search(
            task.query,
            self.config,
            self._step_for_task(state, task) - 1,
        )
        task.notices = notices

        for notice in notices:
            if notice:
                self._emit_event(
                    state,
                    {
                        "type": "status",
                        "message": notice,
                        "task_id": task.id,
                        "step": self._step_for_task(state, task),
                    },
                )

        if not search_result or not search_result.get("results"):
            task.status = "skipped"
            self._workflow(state, "search_web", "skipped", task=task, detail="没有获得搜索结果")
            return {"task": task, "search_context": ""}

        sources_summary, context = prepare_research_context(
            search_result,
            answer_text,
            self.config,
        )
        retrieval_context = payload.get("retrieval_context") or ""
        if retrieval_context:
            context = f"历史/文档检索上下文：\n{retrieval_context}\n\n{context}"

        task.sources_summary = sources_summary
        with self._shared_lock:
            state.web_research_results.append(context)
            state.sources_gathered.append(sources_summary)
            state.research_loop_count += 1
            self._save_sources(task, search_result)

        self._emit_event(
            state,
            {
                "type": "sources",
                "task_id": task.id,
                "latest_sources": sources_summary,
                "raw_context": context,
                "step": self._step_for_task(state, task),
                "backend": backend,
                "note_id": task.note_id,
                "note_path": task.note_path,
                "stream_token": task.stream_token,
            },
        )
        self._workflow(state, "search_web", "completed", task=task, detail=f"使用 {backend} 完成搜索")
        return {"task": task, "search_context": context}

    def _task_summarize_task(self, payload: dict[str, Any]) -> dict[str, Any]:
        state = payload["state"]
        task = payload["task"]

        if task.status == "skipped":
            task.summary = "暂无可用信息"
            self._workflow(state, "summarize_task", "skipped", task=task, detail="任务已跳过")
            return {"task": task}

        self._workflow(state, "summarize_task", "in_progress", task=task)
        context = payload.get("search_context") or ""
        if self._streaming:
            summary_stream, summary_getter = self.summarizer.stream_task_summary(
                state,
                task,
                context,
            )
            for chunk in summary_stream:
                if chunk:
                    self._emit_event(
                        state,
                        {
                            "type": "task_summary_chunk",
                            "task_id": task.id,
                            "content": chunk,
                            "note_id": task.note_id,
                            "step": self._step_for_task(state, task),
                            "stream_token": task.stream_token,
                        },
                    )
            summary_text = summary_getter()
        else:
            summary_text = self.summarizer.summarize_task(state, task, context)

        task.summary = summary_text.strip() if summary_text else "暂无可用信息"
        task.status = "completed"
        self._workflow(state, "summarize_task", "completed", task=task)
        return {"task": task}

    def _task_persist_task(self, payload: dict[str, Any]) -> dict[str, Any]:
        state = payload["state"]
        task = payload["task"]

        self._workflow(state, "persist_task", "in_progress", task=task)
        with self._shared_lock:
            self._update_task_note(task)
            self.repository.save_task(self._task_snapshot(task))
            self._emit_events(state, self._drain_tool_events(state, step=self._step_for_task(state, task)))
        self._emit_task_status(state, task)
        self._workflow(state, "persist_task", "completed", task=task)
        return {"task": task}

    def _graph_write_report(self, payload: dict[str, Any]) -> dict[str, SummaryState]:
        state = payload["state"]
        self._workflow(state, "write_report", "in_progress")
        report = self.reporting.generate_report(state)
        self._emit_events(state, self._drain_tool_events(state, step=len(state.todo_items) + 1))
        state.structured_report = report
        state.running_summary = report
        self._workflow(state, "write_report", "completed")
        return {"state": state}

    def _graph_persist_report(self, payload: dict[str, Any]) -> dict[str, SummaryState]:
        state = payload["state"]
        self._workflow(state, "persist_report", "in_progress")
        note_event = self._persist_final_report(state, state.structured_report or "")
        self._emit_events(state, self._drain_tool_events(state, step=len(state.todo_items) + 1))
        if note_event:
            self._emit_event(state, note_event)

        if state.structured_report:
            self.repository.save_report(
                ResearchReport(
                    run_id=self.run_id,
                    markdown=state.structured_report,
                    note_id=state.report_note_id,
                    note_path=state.report_note_path,
                )
            )

        self._emit_event(
            state,
            {
                "type": "final_report",
                "report": state.structured_report or "",
                "note_id": state.report_note_id,
                "note_path": state.report_note_path,
            },
        )
        self._workflow(state, "persist_report", "completed")
        return {"state": state}

    # ------------------------------------------------------------------
    # 事件与状态辅助方法
    # ------------------------------------------------------------------
    def _workflow(
        self,
        state: SummaryState,
        node: str,
        status: str,
        *,
        task: TodoItem | None = None,
        detail: str | None = None,
    ) -> None:
        node_id = self._workflow_node_id(node, task)
        event: dict[str, Any] = {
            "type": "workflow_node",
            "node_id": node_id,
            "node": node,
            "scope": "task" if task is not None else "global",
            "status": status,
            "label": WORKFLOW_LABELS.get(node, node),
            "depends_on": self._workflow_depends_on(node, task),
        }
        if task is not None:
            event["task_id"] = task.id
            event["step"] = self._step_for_task(state, task)
            event["stream_token"] = task.stream_token
        if detail:
            event["detail"] = detail
        self._emit_event(state, event)

    def _emit_event(self, state: SummaryState, event: dict[str, Any]) -> None:
        if self._streaming and self._event_queue is not None:
            self._event_queue.put(event)
            return
        state.stream_events.append(event)

    def _emit_events(self, state: SummaryState, events: list[dict[str, Any]]) -> None:
        for event in events:
            self._emit_event(state, event)

    def _emit_task_status(self, state: SummaryState, task: TodoItem) -> None:
        """统一输出前端兼容的任务状态事件。"""

        self._emit_event(
            state,
            {
                "type": "task_status",
                "task_id": task.id,
                "status": task.status,
                "summary": task.summary,
                "sources_summary": task.sources_summary,
                "title": task.title,
                "intent": task.intent,
                "query": task.query,
                "note_id": task.note_id,
                "note_path": task.note_path,
                "step": self._step_for_task(state, task),
                "stream_token": task.stream_token,
            },
        )

    def _workflow_node_id(self, node: str, task: TodoItem | None = None) -> str:
        if task is None:
            return f"global:{node}"
        return f"task:{task.id}:{node}"

    def _workflow_depends_on(self, node: str, task: TodoItem | None = None) -> list[str]:
        if task is None:
            mapping = {
                "dispatch_tasks": ["global:plan_tasks"],
                "join_tasks": [f"task:{item.id}:persist_task" for item in getattr(self, "_last_tasks", [])],
                "write_report": ["global:join_tasks"],
                "persist_report": ["global:write_report"],
            }
            return mapping.get(node, [])

        mapping = {
            "prepare_task": ["global:dispatch_tasks"],
            "retrieve_documents": [self._workflow_node_id("prepare_task", task)],
            "search_web": [
                self._workflow_node_id("prepare_task", task),
                self._workflow_node_id("retrieve_documents", task),
            ],
            "summarize_task": [self._workflow_node_id("search_web", task)],
            "persist_task": [self._workflow_node_id("summarize_task", task)],
        }
        return mapping.get(node, [])

    def _workflow_graph_event(self, state: SummaryState) -> dict[str, Any]:
        """生成前端绘制 DAG/泳道图所需的拓扑。"""

        self._last_tasks = list(state.todo_items)
        nodes: list[dict[str, Any]] = [
            self._workflow_graph_node("global:plan_tasks", "plan_tasks", "规划研究任务", "global"),
            self._workflow_graph_node("global:dispatch_tasks", "dispatch_tasks", "分发并行任务", "global"),
            self._workflow_graph_node("global:join_tasks", "join_tasks", "汇总任务结果", "global"),
            self._workflow_graph_node("global:write_report", "write_report", "撰写最终报告", "global"),
            self._workflow_graph_node("global:persist_report", "persist_report", "保存最终报告", "global"),
        ]
        edges: list[dict[str, str]] = [
            {"from": "global:plan_tasks", "to": "global:dispatch_tasks"},
            {"from": "global:join_tasks", "to": "global:write_report"},
            {"from": "global:write_report", "to": "global:persist_report"},
        ]

        for task in state.todo_items:
            task_nodes = [
                ("prepare_task", "准备任务"),
                ("retrieve_documents", "检索文档库"),
                ("search_web", "搜索网页资料"),
                ("summarize_task", "总结任务发现"),
                ("persist_task", "保存任务状态"),
            ]
            for node, label in task_nodes:
                nodes.append(
                    self._workflow_graph_node(
                        self._workflow_node_id(node, task),
                        node,
                        label,
                        "task",
                        task=task,
                    )
                )

            first = self._workflow_node_id("prepare_task", task)
            nodes_for_edges = [self._workflow_node_id(node, task) for node, _ in task_nodes]
            edges.append({"from": "global:dispatch_tasks", "to": first})
            for source, target in zip(nodes_for_edges, nodes_for_edges[1:]):
                edges.append({"from": source, "to": target})
            edges.append({"from": nodes_for_edges[-1], "to": "global:join_tasks"})

        return {"type": "workflow_graph", "nodes": nodes, "edges": edges}

    def _workflow_graph_node(
        self,
        node_id: str,
        node: str,
        label: str,
        scope: str,
        *,
        task: TodoItem | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "id": node_id,
            "node": node,
            "label": label,
            "scope": scope,
            "status": "pending",
        }
        if task is not None:
            payload["task_id"] = task.id
            payload["task_title"] = task.title
        return payload

    def _step_for_task(self, state: SummaryState, task: TodoItem) -> int:
        try:
            return state.todo_items.index(task) + 1
        except ValueError:
            return task.id

    def _drain_tool_events(
        self,
        state: SummaryState,
        *,
        step: int | None = None,
    ) -> list[dict[str, Any]]:
        """代理到共享的工具调用追踪器。"""

        return self._tool_tracker.drain(state, step=step)

    @property
    def _tool_call_events(self) -> list[dict[str, Any]]:
        """为兼容旧集成暴露已记录的工具事件。"""

        return self._tool_tracker.as_dicts()

    def _serialize_task(self, task: TodoItem) -> dict[str, Any]:
        """将任务 dataclass 转成前端可序列化字典。"""

        return {
            "id": task.id,
            "title": task.title,
            "intent": task.intent,
            "query": task.query,
            "status": task.status,
            "summary": task.summary,
            "sources_summary": task.sources_summary,
            "note_id": task.note_id,
            "note_path": task.note_path,
            "stream_token": task.stream_token,
        }

    # ------------------------------------------------------------------
    # 持久化辅助方法
    # ------------------------------------------------------------------
    def _ensure_task_note(self, task: TodoItem) -> None:
        if not self.note_store or task.note_id:
            return

        payload = {
            "action": "create",
            "task_id": task.id,
            "title": f"任务 {task.id}: {task.title}",
            "note_type": "task_state",
            "tags": ["deep_research", f"task_{task.id}"],
            "content": f"任务目标：{task.intent}\n\n检索查询：{task.query}",
        }
        result = self.note_store.run(payload)
        note_id = self._extract_note_id_from_text(result)
        if note_id:
            task.note_id = note_id
            task.note_path = self.note_store.path_for(note_id)
        self._record_note_call("研究规划专家", payload, result)

    def _update_task_note(self, task: TodoItem) -> None:
        if not self.note_store:
            return
        if not task.note_id:
            self._ensure_task_note(task)
        if not task.note_id:
            return

        payload = {
            "action": "update",
            "note_id": task.note_id,
            "task_id": task.id,
            "title": f"任务 {task.id}: {task.title}",
            "note_type": "task_state",
            "tags": ["deep_research", f"task_{task.id}"],
            "content": (
                f"任务目标：{task.intent}\n\n"
                f"检索查询：{task.query}\n\n"
                f"执行状态：{task.status}\n\n"
                f"来源概览：\n{task.sources_summary or '暂无来源'}\n\n"
                f"任务总结：\n{task.summary or '暂无可用信息'}"
            ),
        }
        result = self.note_store.run(payload)
        self._record_note_call("任务总结专家", payload, result)

    def _record_note_call(self, agent_name: str, payload: dict[str, Any], result: str) -> None:
        self._tool_tracker.record(
            {
                "agent_name": agent_name,
                "tool_name": "note",
                "raw_parameters": str(payload),
                "parsed_parameters": payload,
                "result": result,
            }
        )

    def _task_snapshot(self, task: TodoItem) -> ResearchTask:
        return ResearchTask(
            run_id=self.run_id,
            task_id=task.id,
            title=task.title,
            intent=task.intent,
            query=task.query,
            status=task.status,
            note_id=task.note_id,
            note_path=task.note_path,
        )

    def _save_sources(self, task: TodoItem, search_result: dict[str, Any] | None) -> None:
        if not search_result:
            return
        for item in search_result.get("results", []):
            url = str(item.get("url") or "")
            if not url:
                continue
            self.repository.save_source(
                ResearchSource(
                    run_id=self.run_id,
                    task_id=task.id,
                    title=str(item.get("title") or url),
                    url=url,
                    content=str(item.get("content") or item.get("raw_content") or ""),
                )
            )

    def _persist_final_report(self, state: SummaryState, report: str) -> dict[str, Any] | None:
        if not self.note_store or not report or not report.strip():
            return None

        note_title = f"研究报告：{state.research_topic}".strip() or "研究报告"
        tags = ["deep_research", "report"]
        content = report.strip()
        note_id = self._find_existing_report_note_id(state)

        if note_id:
            update_payload = {
                "action": "update",
                "note_id": note_id,
                "title": note_title,
                "note_type": "conclusion",
                "tags": tags,
                "content": content,
            }
            response = self.note_store.run(update_payload)
            self._record_note_call("报告撰写专家", update_payload, response)
            if response.startswith("❌"):
                note_id = None

        if not note_id:
            create_payload = {
                "action": "create",
                "title": note_title,
                "note_type": "conclusion",
                "tags": tags,
                "content": content,
            }
            response = self.note_store.run(create_payload)
            self._record_note_call("报告撰写专家", create_payload, response)
            note_id = self._extract_note_id_from_text(response)

        if not note_id:
            return None

        state.report_note_id = note_id
        if self.config.notes_workspace:
            state.report_note_path = self.note_store.path_for(note_id)

        payload = {
            "type": "report_note",
            "note_id": note_id,
            "title": note_title,
            "content": content,
        }
        if state.report_note_path:
            payload["note_path"] = state.report_note_path
        return payload

    def _find_existing_report_note_id(self, state: SummaryState) -> str | None:
        if state.report_note_id:
            return state.report_note_id

        for event in reversed(self._tool_tracker.as_dicts()):
            if event.get("tool") != "note":
                continue

            parameters = event.get("parsed_parameters") or {}
            if not isinstance(parameters, dict):
                continue

            action = parameters.get("action")
            if action not in {"create", "update"}:
                continue

            note_type = parameters.get("note_type")
            if note_type != "conclusion":
                title = parameters.get("title")
                if not (isinstance(title, str) and title.startswith("研究报告")):
                    continue

            note_id = parameters.get("note_id")
            if not note_id:
                note_id = self._tool_tracker._extract_note_id(event.get("result", ""))  # type: ignore[attr-defined]

            if note_id:
                return note_id

        return None

    @staticmethod
    def _extract_note_id_from_text(response: str) -> str | None:
        if not response:
            return None

        match = re.search(r"ID:\s*([^\n]+)", response)
        if not match:
            return None

        return match.group(1).strip()


def run_deep_research(topic: str, config: Configuration | None = None) -> SummaryStateOutput:
    """与类接口等价的便捷调用函数。"""

    agent = DeepResearchAgent(config=config)
    return agent.run(topic)

