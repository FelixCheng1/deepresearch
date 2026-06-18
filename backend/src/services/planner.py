"""负责将研究主题转换为可执行任务的服务。"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, List, Optional

from langchain_core.messages import HumanMessage, SystemMessage

from models import SummaryState, TodoItem
from config import Configuration
from prompts import get_current_date, todo_planner_instructions, todo_planner_system_prompt
from services.llm import message_content
from utils import strip_thinking_tokens

logger = logging.getLogger(__name__)

TOOL_CALL_PATTERN = re.compile(
    r"\[TOOL_CALL:(?P<tool>[^:]+):(?P<body>[^\]]+)\]",
    re.IGNORECASE,
)

class PlanningService:
    """调用规划模型生成结构化 TODO 项。"""

    def __init__(self, chat_model: Any, config: Configuration) -> None:
        self._chat_model = chat_model
        self._config = config

    def plan_todo_list(self, state: SummaryState) -> List[TodoItem]:
        """要求规划模型将主题拆解为可执行任务。"""

        prompt = todo_planner_instructions.format(
            current_date=get_current_date(),
            research_topic=state.research_topic,
        )

        response = message_content(
            self._chat_model.invoke(
                [
                    SystemMessage(content=todo_planner_system_prompt.strip()),
                    HumanMessage(content=prompt),
                ]
            )
        )

        logger.info("Planner raw output (truncated): %s", response[:500])

        tasks_payload = self._extract_tasks(response)
        todo_items: List[TodoItem] = []

        for idx, item in enumerate(tasks_payload, start=1):
            title = str(item.get("title") or f"任务{idx}").strip()
            intent = str(item.get("intent") or "聚焦主题的关键问题").strip()
            query = str(item.get("query") or state.research_topic).strip()

            if not query:
                query = state.research_topic

            task = TodoItem(
                id=idx,
                title=title,
                intent=intent,
                query=query,
            )
            todo_items.append(task)

        state.todo_items = todo_items

        titles = [task.title for task in todo_items]
        logger.info("Planner produced %d tasks: %s", len(todo_items), titles)
        return todo_items

    @staticmethod
    def create_fallback_task(state: SummaryState) -> TodoItem:
        """规划失败时创建兼容旧调用的单个兜底任务。"""

        return PlanningService.create_fallback_tasks(state, start_id=1, count=1)[0]

    @staticmethod
    def create_fallback_tasks(
        state: SummaryState,
        *,
        start_id: int = 1,
        count: int = 4,
        existing_titles: set[str] | None = None,
    ) -> List[TodoItem]:
        """规划失败或任务过少时创建多任务兜底清单。"""

        topic = (state.research_topic or "").strip()
        base_query = topic or "研究主题"
        templates = [
            (
                "基础背景梳理",
                "收集主题的核心背景、最新动态与关键概念，建立后续分析上下文。",
                f"{base_query} 最新进展 背景",
            ),
            (
                "技术机制分析",
                "分析主题背后的核心原理、技术架构与关键组成部分。",
                f"{base_query} 原理 架构 关键技术",
            ),
            (
                "应用案例调研",
                "调研主题在真实场景中的应用案例、实践路径与代表性成果。",
                f"{base_query} 应用案例 实践",
            ),
            (
                "风险挑战评估",
                "识别主题当前的局限、风险、争议点与未来发展趋势。",
                f"{base_query} 局限 挑战 趋势",
            ),
        ]

        skipped = existing_titles or set()
        tasks: List[TodoItem] = []
        next_id = start_id
        for title, intent, query in templates:
            if title in skipped:
                continue
            tasks.append(TodoItem(id=next_id, title=title, intent=intent, query=query))
            next_id += 1
            if len(tasks) >= count:
                break
        return tasks

    # ------------------------------------------------------------------
    # 解析辅助方法
    # ------------------------------------------------------------------
    def _extract_tasks(self, raw_response: str) -> List[dict[str, Any]]:
        """将规划输出解析为任务字典列表。"""

        text = raw_response.strip()
        if self._config.strip_thinking_tokens:
            text = strip_thinking_tokens(text)

        json_payload = self._extract_json_payload(text)
        tasks: List[dict[str, Any]] = []

        if isinstance(json_payload, dict):
            candidate = json_payload.get("tasks")
            if isinstance(candidate, list):
                for item in candidate:
                    if isinstance(item, dict):
                        tasks.append(item)
        elif isinstance(json_payload, list):
            for item in json_payload:
                if isinstance(item, dict):
                    tasks.append(item)

        if not tasks:
            tool_payload = self._extract_tool_payload(text)
            if tool_payload and isinstance(tool_payload.get("tasks"), list):
                for item in tool_payload["tasks"]:
                    if isinstance(item, dict):
                        tasks.append(item)

        return tasks

    def _extract_json_payload(self, text: str) -> Optional[dict[str, Any] | list]:
        """尝试从文本中定位并解析 JSON 对象或数组。"""

        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            candidate = text[start : end + 1]
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                pass

        start = text.find("[")
        end = text.rfind("]")
        if start != -1 and end != -1 and end > start:
            candidate = text[start : end + 1]
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                return None

        return None

    def _extract_tool_payload(self, text: str) -> Optional[dict[str, Any]]:
        """解析输出中的第一个 TOOL_CALL 表达式。"""

        match = TOOL_CALL_PATTERN.search(text)
        if not match:
            return None

        body = match.group("body")

        try:
            payload = json.loads(body)
            if isinstance(payload, dict):
                return payload
        except json.JSONDecodeError:
            pass

        parts = [segment.strip() for segment in body.split(",") if segment.strip()]
        payload: dict[str, Any] = {}
        for part in parts:
            if "=" not in part:
                continue
            key, value = part.split("=", 1)
            payload[key.strip()] = value.strip().strip('"').strip("'")

        return payload or None
