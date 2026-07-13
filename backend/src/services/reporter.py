"""将任务结果整合为最终报告的服务。"""

from __future__ import annotations

from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from config import Configuration
from models import SummaryState
from prompts import report_writer_instructions
from services.llm import message_content
from services.text_processing import strip_tool_calls
from utils import strip_thinking_tokens


class ReportingService:
    """生成最终结构化报告。"""

    def __init__(self, chat_model: Any, config: Configuration) -> None:
        self._chat_model = chat_model
        self._config = config

    def generate_report(self, state: SummaryState) -> str:
        """基于已完成任务生成结构化报告。"""

        tasks_block = []
        for task in state.todo_items:
            summary_block = task.summary or "暂无可用信息"
            sources_block = task.sources_summary or "暂无来源"
            tasks_block.append(
                f"### 任务 {task.id}: {task.title}\n"
                f"- 任务目标：{task.intent}\n"
                f"- 检索查询：{task.query}\n"
                f"- 执行状态：{task.status}\n"
                f"- 任务总结：\n{summary_block}\n"
                f"- 来源概览：\n{sources_block}\n"
            )

        prompt = (
            f"研究主题：{state.research_topic}\n"
            f"任务概览：\n{''.join(tasks_block)}\n"
            "请只基于以上任务概览生成面向用户的 Markdown 最终报告。不要输出工具调用、JSON 工具参数或代码块。"
        )

        response = message_content(
            self._chat_model.invoke(
                [
                    SystemMessage(content=report_writer_instructions.strip()),
                    HumanMessage(content=prompt),
                ]
            )
        )

        report_text = response.strip()
        if self._config.strip_thinking_tokens:
            report_text = strip_thinking_tokens(report_text)

        report_text = strip_tool_calls(report_text).strip()

        return report_text or "报告生成失败，请检查输入。"

