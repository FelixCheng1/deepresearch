"""协调深度研究工作流的编排器。"""

from __future__ import annotations

import logging
import re
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


WORKFLOW_LABELS = {
    "plan_tasks": "规划研究任务",
    "select_next_task": "选择下一个任务",
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
        self.repository = repository or InMemoryResearchRepository()
        self.retriever = retriever or DisabledRetriever(self.config)
        self._tool_tracker = ToolCallTracker(
            self.config.notes_workspace if self.config.enable_notes else None
        )
        self.run_id = uuid4().hex
        self._streaming = False

        self.planner = PlanningService(self.llm, self.config)
        self.summarizer = SummarizationService(lambda: self.llm, self.config)
        self.reporting = ReportingService(self.llm, self.config)
        self.graph = build_research_graph()

    # ------------------------------------------------------------------
    # 公共接口
    # ------------------------------------------------------------------
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
        """执行同一套 LangGraph 工作流，并逐步产出 SSE 事件。"""

        state = SummaryState(research_topic=topic)
        self._streaming = True
        self._emit_event(state, {"type": "status", "message": "初始化研究流程"})

        try:
            for chunk in self.graph.stream({"agent": self, "state": state}):
                state = self._state_from_graph_chunk(chunk, state)
                yield from self._pop_stream_events(state)
        except Exception as exc:
            logger.exception("Streaming research failed")
            yield from self._pop_stream_events(state)
            yield {"type": "error", "detail": str(exc)}
            return
        finally:
            self._streaming = False

        yield from self._pop_stream_events(state)
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
        self._workflow(state, "plan_tasks", "completed", detail=f"生成 {len(state.todo_items)} 个任务")
        return {"state": state}

    def _graph_select_next_task(self, payload: dict[str, Any]) -> dict[str, SummaryState]:
        state = payload["state"]
        self._workflow(state, "select_next_task", "in_progress")
        task = self._current_task(state)
        if task is None:
            self._workflow(state, "select_next_task", "skipped", detail="没有待执行任务")
            return {"state": state}

        state.current_task_id = task.id
        state.current_context = ""
        state.current_sources_summary = ""
        state.current_search_result = None
        state.current_answer_text = None
        state.current_search_backend = None
        state.current_retrieval_context = ""
        self._workflow(
            state,
            "select_next_task",
            "completed",
            task=task,
            detail=f"当前任务：{task.title}",
        )
        return {"state": state}

    def _graph_prepare_task(self, payload: dict[str, Any]) -> dict[str, SummaryState]:
        state = payload["state"]
        task = self._current_task(state)
        if task is None:
            return {"state": state}

        self._workflow(state, "prepare_task", "in_progress", task=task)
        task.status = "in_progress"
        self._emit_event(
            state,
            {
                "type": "task_status",
                "task_id": task.id,
                "status": "in_progress",
                "title": task.title,
                "intent": task.intent,
                "query": task.query,
                "note_id": task.note_id,
                "note_path": task.note_path,
                "step": self._step_for_task(state, task),
                "stream_token": task.stream_token,
            },
        )
        self._workflow(state, "prepare_task", "completed", task=task)
        return {"state": state}

    def _graph_should_retrieve(self, payload: dict[str, Any]) -> str:
        state = payload["state"]
        task = self._current_task(state)
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

    def _graph_retrieve_documents(self, payload: dict[str, Any]) -> dict[str, SummaryState]:
        state = payload["state"]
        task = self._current_task(state)
        if task is None:
            return {"state": state}

        self._workflow(state, "retrieve_documents", "in_progress", task=task)
        chunks = self.retriever.retrieve(task.query)
        if chunks:
            state.current_retrieval_context = "\n\n".join(chunk.text for chunk in chunks)
            detail = f"找到 {len(chunks)} 个文档片段"
            status = "completed"
        else:
            state.current_retrieval_context = ""
            detail = "未找到可用文档片段"
            status = "skipped"
        self._workflow(state, "retrieve_documents", status, task=task, detail=detail)
        return {"state": state}

    def _graph_search_web(self, payload: dict[str, Any]) -> dict[str, SummaryState]:
        state = payload["state"]
        task = self._current_task(state)
        if task is None:
            return {"state": state}

        self._workflow(state, "search_web", "in_progress", task=task)
        search_result, notices, answer_text, backend = dispatch_search(
            task.query,
            self.config,
            state.research_loop_count,
        )
        task.notices = notices
        state.current_search_result = search_result
        state.current_answer_text = answer_text
        state.current_search_backend = backend

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
            return {"state": state}

        sources_summary, context = prepare_research_context(
            search_result,
            answer_text,
            self.config,
        )
        if state.current_retrieval_context:
            context = f"历史/文档检索上下文：\n{state.current_retrieval_context}\n\n{context}"

        task.sources_summary = sources_summary
        state.current_sources_summary = sources_summary
        state.current_context = context
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
        return {"state": state}

    def _graph_summarize_task(self, payload: dict[str, Any]) -> dict[str, SummaryState]:
        state = payload["state"]
        task = self._current_task(state)
        if task is None:
            return {"state": state}

        if task.status == "skipped":
            task.summary = "暂无可用信息"
            self._workflow(state, "summarize_task", "skipped", task=task, detail="任务已跳过")
            return {"state": state}

        self._workflow(state, "summarize_task", "in_progress", task=task)
        if self._streaming:
            summary_stream, summary_getter = self.summarizer.stream_task_summary(
                state,
                task,
                state.current_context,
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
            summary_text = self.summarizer.summarize_task(state, task, state.current_context)

        task.summary = summary_text.strip() if summary_text else "暂无可用信息"
        task.status = "completed"
        self._workflow(state, "summarize_task", "completed", task=task)
        return {"state": state}

    def _graph_persist_task(self, payload: dict[str, Any]) -> dict[str, SummaryState]:
        state = payload["state"]
        task = self._current_task(state)
        if task is None:
            return {"state": state}

        self._workflow(state, "persist_task", "in_progress", task=task)
        self._update_task_note(task)
        self.repository.save_task(self._task_snapshot(task))
        self._emit_events(state, self._drain_tool_events(state, step=self._step_for_task(state, task)))
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
                "note_id": task.note_id,
                "note_path": task.note_path,
                "step": self._step_for_task(state, task),
                "stream_token": task.stream_token,
            },
        )
        self._workflow(state, "persist_task", "completed", task=task)
        state.current_task_index += 1
        return {"state": state}

    def _graph_should_continue(self, payload: dict[str, Any]) -> str:
        state = payload["state"]
        if state.current_task_index < len(state.todo_items):
            return "select_next_task"
        return "write_report"

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
        event: dict[str, Any] = {
            "type": "workflow_node",
            "node": node,
            "status": status,
            "label": WORKFLOW_LABELS.get(node, node),
        }
        if task is not None:
            event["task_id"] = task.id
            event["step"] = self._step_for_task(state, task)
            event["stream_token"] = task.stream_token
        if detail:
            event["detail"] = detail
        self._emit_event(state, event)

    def _emit_event(self, state: SummaryState, event: dict[str, Any]) -> None:
        state.stream_events.append(event)

    def _emit_events(self, state: SummaryState, events: list[dict[str, Any]]) -> None:
        for event in events:
            self._emit_event(state, event)

    def _pop_stream_events(self, state: SummaryState) -> Iterator[dict[str, Any]]:
        while state.stream_events:
            yield state.stream_events.pop(0)

    def _state_from_graph_chunk(self, chunk: dict[str, Any], fallback: SummaryState) -> SummaryState:
        for value in chunk.values():
            if isinstance(value, dict) and isinstance(value.get("state"), SummaryState):
                return value["state"]
        return fallback

    def _current_task(self, state: SummaryState) -> TodoItem | None:
        if state.current_task_index < 0 or state.current_task_index >= len(state.todo_items):
            return None
        return state.todo_items[state.current_task_index]

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
