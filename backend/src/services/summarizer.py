"""任务总结工具。"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import Tuple

from langchain_core.messages import HumanMessage, SystemMessage

from config import Configuration
from models import SummaryState, TodoItem
from prompts import task_summarizer_instructions
from services.llm import message_content
from services.text_processing import strip_tool_calls
from utils import strip_thinking_tokens


class SummarizationService:
    """处理同步和流式任务总结。"""

    def __init__(
        self,
        summarizer_factory: Callable[[], object],
        config: Configuration,
    ) -> None:
        self._agent_factory = summarizer_factory
        self._config = config

    def summarize_task(self, state: SummaryState, task: TodoItem, context: str) -> str:
        """使用总结模型生成指定任务的总结。"""

        prompt = self._build_prompt(state, task, context)

        agent = self._agent_factory()
        response = message_content(
            agent.invoke(
                [
                    SystemMessage(content=task_summarizer_instructions.strip()),
                    HumanMessage(content=prompt),
                ]
            )
        )

        summary_text = response.strip()
        if self._config.strip_thinking_tokens:
            summary_text = strip_thinking_tokens(summary_text)

        summary_text = strip_tool_calls(summary_text).strip()

        return summary_text or "暂无可用信息"

    def stream_task_summary(
        self, state: SummaryState, task: TodoItem, context: str
    ) -> Tuple[Iterator[str], Callable[[], str]]:
        """流式生成任务总结文本，同时收集完整输出。"""

        prompt = self._build_prompt(state, task, context)
        remove_thinking = self._config.strip_thinking_tokens
        raw_buffer = ""
        visible_output = ""
        emit_index = 0
        agent = self._agent_factory()
        messages = [
            SystemMessage(content=task_summarizer_instructions.strip()),
            HumanMessage(content=prompt),
        ]

        def flush_visible() -> Iterator[str]:
            nonlocal emit_index, raw_buffer
            while True:
                start = raw_buffer.find("<think>", emit_index)
                if start == -1:
                    if emit_index < len(raw_buffer):
                        segment = raw_buffer[emit_index:]
                        emit_index = len(raw_buffer)
                        if segment:
                            yield segment
                    break

                if start > emit_index:
                    segment = raw_buffer[emit_index:start]
                    emit_index = start
                    if segment:
                        yield segment

                end = raw_buffer.find("</think>", start)
                if end == -1:
                    break
                emit_index = end + len("</think>")

        def generator() -> Iterator[str]:
            nonlocal raw_buffer, visible_output, emit_index
            try:
                for chunk in agent.stream(messages):
                    chunk_text = message_content(chunk)
                    raw_buffer += chunk_text
                    if remove_thinking:
                        for segment in flush_visible():
                            visible_output += segment
                            if segment:
                                yield segment
                    else:
                        visible_output += chunk_text
                        if chunk_text:
                            yield chunk_text
            finally:
                if remove_thinking:
                    for segment in flush_visible():
                        visible_output += segment
                        if segment:
                            yield segment

        def get_summary() -> str:
            if remove_thinking:
                cleaned = strip_thinking_tokens(visible_output)
            else:
                cleaned = visible_output

            return strip_tool_calls(cleaned).strip()

        return generator(), get_summary

    def _build_prompt(self, state: SummaryState, task: TodoItem, context: str) -> str:
        """构造同步和流式模式共用的总结提示词。"""

        return (
            f"任务主题：{state.research_topic}\n"
            f"任务名称：{task.title}\n"
            f"任务目标：{task.intent}\n"
            f"检索查询：{task.query}\n"
            f"任务上下文：\n{context}\n"
            "请只返回面向用户的 Markdown 任务总结。不要输出工具调用、JSON 工具参数或代码块。"
        )
