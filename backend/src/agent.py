"""协调深度研究工作流的编排器。"""

from __future__ import annotations

import logging
import re
from queue import Empty, Queue
from threading import Lock, Thread
from typing import Any, Callable, Iterator
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
from services.graph import build_research_graph
from services.llm import create_chat_model
from services.note_store import NoteStore
from services.planner import PlanningService
from services.repository import InMemoryResearchRepository, ResearchRepository
from services.reporter import ReportingService
from services.retriever import DisabledRetriever, Retriever
from services.search import dispatch_search, prepare_research_context
from services.summarizer import SummarizationService
from services.tool_events import ToolCallTracker

logger = logging.getLogger(__name__)


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
        self.repository = repository or InMemoryResearchRepository()
        self.retriever = retriever or DisabledRetriever(self.config)

        self._tool_tracker = ToolCallTracker(
            self.config.notes_workspace if self.config.enable_notes else None
        )
        self._tool_event_sink_enabled = False
        self._state_lock = Lock()
        self.run_id = uuid4().hex

        self.planner = PlanningService(self.llm, self.config)
        self.summarizer = SummarizationService(lambda: self.llm, self.config)
        self.reporting = ReportingService(self.llm, self.config)
        self.graph = build_research_graph()

    # ------------------------------------------------------------------
    # 公共接口
    # ------------------------------------------------------------------
    def _set_tool_event_sink(self, sink: Callable[[dict[str, Any]], None] | None) -> None:
        """启用或停用即时工具事件回调。"""
        self._tool_event_sink_enabled = sink is not None
        self._tool_tracker.set_event_sink(sink)

    def run(self, topic: str) -> SummaryStateOutput:
        """执行研究工作流并返回最终报告。"""
        state = SummaryState(research_topic=topic)
        result = self.graph.invoke({"agent": self, "state": state})
        state = result["state"]

        return SummaryStateOutput(
            running_summary=state.running_summary,
            report_markdown=state.structured_report,
            todo_items=state.todo_items,
        )

    def run_stream(self, topic: str) -> Iterator[dict[str, Any]]:
        """执行研究工作流，并逐步产出进度事件。"""
        state = SummaryState(research_topic=topic)
        logger.debug("Starting streaming research: topic=%s", topic)
        yield {"type": "status", "message": "初始化研究流程"}

        self._plan_tasks(state)
        for event in self._drain_tool_events(state, step=0):
            yield event

        channel_map: dict[int, dict[str, Any]] = {}
        for index, task in enumerate(state.todo_items, start=1):
            token = f"task_{task.id}"
            task.stream_token = token
            channel_map[task.id] = {"step": index, "token": token}

        yield {
            "type": "todo_list",
            "tasks": [self._serialize_task(t) for t in state.todo_items],
            "step": 0,
        }

        event_queue: Queue[dict[str, Any]] = Queue()

        def enqueue(
            event: dict[str, Any],
            *,
            task: TodoItem | None = None,
            step_override: int | None = None,
        ) -> None:
            payload = dict(event)
            target_task_id = payload.get("task_id")
            if task is not None:
                target_task_id = task.id
                payload["task_id"] = task.id

            channel = channel_map.get(target_task_id) if target_task_id is not None else None
            if channel:
                payload.setdefault("step", channel["step"])
                payload["stream_token"] = channel["token"]
            if step_override is not None:
                payload["step"] = step_override
            event_queue.put(payload)

        def tool_event_sink(event: dict[str, Any]) -> None:
            enqueue(event)

        self._set_tool_event_sink(tool_event_sink)

        threads: list[Thread] = []

        def worker(task: TodoItem, step: int) -> None:
            try:
                enqueue(
                    {
                        "type": "task_status",
                        "task_id": task.id,
                        "status": "in_progress",
                        "title": task.title,
                        "intent": task.intent,
                        "note_id": task.note_id,
                        "note_path": task.note_path,
                    },
                    task=task,
                )

                for event in self._execute_task(state, task, emit_stream=True, step=step):
                    enqueue(event, task=task)
            except Exception as exc:  # pragma: no cover - 防御性保护
                logger.exception("Task execution failed", exc_info=exc)
                enqueue(
                    {
                        "type": "task_status",
                        "task_id": task.id,
                        "status": "failed",
                        "detail": str(exc),
                        "title": task.title,
                        "intent": task.intent,
                        "note_id": task.note_id,
                        "note_path": task.note_path,
                    },
                    task=task,
                )
            finally:
                enqueue({"type": "__task_done__", "task_id": task.id})

        for task in state.todo_items:
            step = channel_map.get(task.id, {}).get("step", 0)
            thread = Thread(target=worker, args=(task, step), daemon=True)
            threads.append(thread)
            thread.start()

        active_workers = len(state.todo_items)
        finished_workers = 0

        try:
            while finished_workers < active_workers:
                event = event_queue.get()
                if event.get("type") == "__task_done__":
                    finished_workers += 1
                    continue
                yield event

            while True:
                try:
                    event = event_queue.get_nowait()
                except Empty:
                    break
                if event.get("type") != "__task_done__":
                    yield event
        finally:
            self._set_tool_event_sink(None)
            for thread in threads:
                thread.join()

        report = self.reporting.generate_report(state)
        final_step = len(state.todo_items) + 1
        for event in self._drain_tool_events(state, step=final_step):
            yield event
        state.structured_report = report
        state.running_summary = report

        note_event = self._persist_final_report(state, report)
        if note_event:
            yield note_event
        self.repository.save_report(
            ResearchReport(
                run_id=self.run_id,
                markdown=report,
                note_id=state.report_note_id,
                note_path=state.report_note_path,
            )
        )

        yield {
            "type": "final_report",
            "report": report,
            "note_id": state.report_note_id,
            "note_path": state.report_note_path,
        }
        yield {"type": "done"}

    # ------------------------------------------------------------------
    # LangGraph 节点实现
    # ------------------------------------------------------------------
    def _graph_plan_tasks(self, payload: dict[str, Any]) -> dict[str, SummaryState]:
        state = payload["state"]
        self._plan_tasks(state)
        return {"state": state}

    def _graph_execute_tasks(self, payload: dict[str, Any]) -> dict[str, SummaryState]:
        state = payload["state"]
        for task in state.todo_items:
            for _ in self._execute_task(state, task, emit_stream=False):
                pass
        return {"state": state}

    def _graph_generate_report(self, payload: dict[str, Any]) -> dict[str, SummaryState]:
        state = payload["state"]
        report = self.reporting.generate_report(state)
        self._drain_tool_events(state)
        state.structured_report = report
        state.running_summary = report
        return {"state": state}

    def _graph_persist_report(self, payload: dict[str, Any]) -> dict[str, SummaryState]:
        state = payload["state"]
        self._persist_final_report(state, state.structured_report or "")
        if state.structured_report:
            self.repository.save_report(
                ResearchReport(
                    run_id=self.run_id,
                    markdown=state.structured_report,
                    note_id=state.report_note_id,
                    note_path=state.report_note_path,
                )
            )
        return {"state": state}

    # ------------------------------------------------------------------
    # 执行辅助方法
    # ------------------------------------------------------------------
    def _plan_tasks(self, state: SummaryState) -> None:
        state.todo_items = self.planner.plan_todo_list(state)
        self._drain_tool_events(state)

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

        for task in state.todo_items:
            self._ensure_task_note(task)
            self.repository.save_task(self._task_snapshot(task))

    def _execute_task(
        self,
        state: SummaryState,
        task: TodoItem,
        *,
        emit_stream: bool,
        step: int | None = None,
    ) -> Iterator[dict[str, Any]]:
        """为单个任务执行搜索和总结。"""
        task.status = "in_progress"

        search_result, notices, answer_text, backend = dispatch_search(
            task.query,
            self.config,
            state.research_loop_count,
        )
        task.notices = notices

        if emit_stream:
            for event in self._drain_tool_events(state, step=step):
                yield event
        else:
            self._drain_tool_events(state)

        if notices and emit_stream:
            for notice in notices:
                if notice:
                    yield {
                        "type": "status",
                        "message": notice,
                        "task_id": task.id,
                        "step": step,
                    }

        if not search_result or not search_result.get("results"):
            task.status = "skipped"
            if emit_stream:
                for event in self._drain_tool_events(state, step=step):
                    yield event
                yield {
                    "type": "task_status",
                    "task_id": task.id,
                    "status": "skipped",
                    "title": task.title,
                    "intent": task.intent,
                    "note_id": task.note_id,
                    "note_path": task.note_path,
                    "step": step,
                }
            else:
                self._drain_tool_events(state)
            return
        else:
            if not emit_stream:
                self._drain_tool_events(state)

        sources_summary, context = prepare_research_context(
            search_result,
            answer_text,
            self.config,
        )
        retrieval_chunks = self.retriever.retrieve(task.query)
        if retrieval_chunks:
            rag_context = "\n\n".join(chunk.text for chunk in retrieval_chunks)
            context = f"历史/文档检索上下文：\n{rag_context}\n\n{context}"

        task.sources_summary = sources_summary

        with self._state_lock:
            state.web_research_results.append(context)
            state.sources_gathered.append(sources_summary)
            state.research_loop_count += 1
            self._save_sources(task, search_result)

        summary_text: str | None = None

        if emit_stream:
            for event in self._drain_tool_events(state, step=step):
                yield event
            yield {
                "type": "sources",
                "task_id": task.id,
                "latest_sources": sources_summary,
                "raw_context": context,
                "step": step,
                "backend": backend,
                "note_id": task.note_id,
                "note_path": task.note_path,
            }

            summary_stream, summary_getter = self.summarizer.stream_task_summary(state, task, context)
            try:
                for event in self._drain_tool_events(state, step=step):
                    yield event
                for chunk in summary_stream:
                    if chunk:
                        yield {
                            "type": "task_summary_chunk",
                            "task_id": task.id,
                            "content": chunk,
                            "note_id": task.note_id,
                            "step": step,
                        }
                    for event in self._drain_tool_events(state, step=step):
                        yield event
            finally:
                summary_text = summary_getter()
        else:
            summary_text = self.summarizer.summarize_task(state, task, context)
            self._drain_tool_events(state)

        task.summary = summary_text.strip() if summary_text else "暂无可用信息"
        task.status = "completed"
        self._update_task_note(task)
        self.repository.save_task(self._task_snapshot(task))

        if emit_stream:
            for event in self._drain_tool_events(state, step=step):
                yield event
            yield {
                "type": "task_status",
                "task_id": task.id,
                "status": "completed",
                "summary": task.summary,
                "sources_summary": task.sources_summary,
                "note_id": task.note_id,
                "note_path": task.note_path,
                "step": step,
            }
        else:
            self._drain_tool_events(state)

    def _drain_tool_events(
        self,
        state: SummaryState,
        *,
        step: int | None = None,
    ) -> list[dict[str, Any]]:
        """代理到共享的工具调用追踪器。"""
        events = self._tool_tracker.drain(state, step=step)
        if self._tool_event_sink_enabled:
            return []
        return events

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
