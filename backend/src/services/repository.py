"""研究数据的持久化边界。

默认实现刻意保持为内存存储，让图工作流先拥有稳定的存储接口，
同时不在第一阶段引入数据库依赖。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from models import ResearchReport, ResearchRun, ResearchSource, ResearchTask


class ResearchRepository(Protocol):
    """为未来数据库持久化预留的研究数据存储协议。"""

    def save_run(self, run: ResearchRun) -> None:
        """保存一次研究运行的元数据。"""

    def save_task(self, task: ResearchTask) -> None:
        """保存任务快照。"""

    def save_source(self, source: ResearchSource) -> None:
        """保存来源快照。"""

    def save_report(self, report: ResearchReport) -> None:
        """保存报告快照。"""


@dataclass
class InMemoryResearchRepository:
    """在接入 Postgres + pgvector 前使用的简单内存仓库。"""

    runs: dict[str, ResearchRun] = field(default_factory=dict)
    tasks: dict[tuple[str, int], ResearchTask] = field(default_factory=dict)
    sources: list[ResearchSource] = field(default_factory=list)
    reports: dict[str, ResearchReport] = field(default_factory=dict)

    def save_run(self, run: ResearchRun) -> None:
        self.runs[run.id] = run

    def save_task(self, task: ResearchTask) -> None:
        self.tasks[(task.run_id, task.task_id)] = task

    def save_source(self, source: ResearchSource) -> None:
        self.sources.append(source)

    def save_report(self, report: ResearchReport) -> None:
        self.reports[report.run_id] = report
