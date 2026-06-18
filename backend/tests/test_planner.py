import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from config import Configuration
from models import SummaryState
from services.planner import PlanningService


class Response:
    def __init__(self, content: str) -> None:
        self.content = content


class FakeModel:
    def __init__(self, content: str) -> None:
        self.content = content

    def invoke(self, messages):
        return Response(self.content)


def test_planner_parses_json_with_extra_text():
    model = FakeModel('before {"tasks":[{"title":"背景","intent":"了解背景","query":"topic background"}]} after')
    service = PlanningService(model, Configuration(enable_notes=False))

    tasks = service.plan_todo_list(SummaryState(research_topic="topic"))

    assert len(tasks) == 1
    assert tasks[0].title == "背景"
    assert tasks[0].intent == "了解背景"
    assert tasks[0].query == "topic background"


def test_planner_empty_payload_returns_no_tasks():
    service = PlanningService(FakeModel('{"tasks": []}'), Configuration(enable_notes=False))

    assert service.plan_todo_list(SummaryState(research_topic="topic")) == []


def test_fallback_tasks_create_multi_task_research_plan():
    tasks = PlanningService.create_fallback_tasks(SummaryState(research_topic="LangGraph 多智能体"))

    assert len(tasks) == 4
    assert [task.id for task in tasks] == [1, 2, 3, 4]
    assert [task.title for task in tasks] == [
        "基础背景梳理",
        "技术机制分析",
        "应用案例调研",
        "风险挑战评估",
    ]
    assert all("LangGraph 多智能体" in task.query for task in tasks)
