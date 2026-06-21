import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import agent as agent_module
import main as main_module
from config import Configuration
from services.repository import InMemoryResearchRepository
from helpers import make_notes_dir


class Response:
    def __init__(self, content: str) -> None:
        self.content = content


class FakeChatModel:
    def invoke(self, messages):
        system = messages[0].content
        if "研究规划专家" in system:
            return Response(
                '{"tasks":[{"title":"背景","intent":"了解背景","query":"topic background"}]}'
            )
        if "文档检索查询改写器" in system:
            return Response("topic background LangGraph RAG retrieval quality")
        if "报告撰写" in system:
            return Response("# 最终报告\n\n整合结论。")
        return Response("## 任务总结\n\n- 关键发现")

    def stream(self, messages):
        yield Response("## 任务总结\n\n")
        yield Response("- 关键发现")


class ToolCallOnlySummaryModel(FakeChatModel):
    def invoke(self, messages):
        system = messages[0].content
        if "研究规划专家" in system:
            return Response(
                '{"tasks":[{"title":"背景","intent":"了解背景","query":"topic background"}]}'
            )
        if "文档检索查询改写器" in system:
            return Response("topic background LangGraph RAG retrieval quality")
        if "报告撰写" in system:
            return Response("# 最终报告\n\n整合结论。")
        return Response(
            '```json\n[{"tool_call":{"type":"function","function":{"name":"note","arguments":"{}"}}}]\n```'
        )


def fake_search(query, config, loop_count):
    return (
        {
            "results": [
                {
                    "title": "Example",
                    "url": "https://example.com",
                    "content": "Example content",
                    "raw_content": "Example raw content",
                }
            ],
            "backend": "duckduckgo",
            "answer": None,
            "notices": [],
        },
        [],
        None,
        "duckduckgo",
    )


def empty_search(query, config, loop_count):
    return (
        {
            "results": [],
            "backend": "duckduckgo",
            "answer": None,
            "notices": [],
        },
        [],
        None,
        "duckduckgo",
    )


def test_agent_run_with_mock_llm_and_search(monkeypatch):
    monkeypatch.setattr(agent_module, "dispatch_search", fake_search)
    config = Configuration(enable_notes=True, notes_workspace=str(make_notes_dir()), rag_enabled=False)
    repo = InMemoryResearchRepository()
    deep_agent = agent_module.DeepResearchAgent(
        config=config,
        repository=repo,
        chat_model=FakeChatModel(),
    )

    result = deep_agent.run("topic")

    assert "最终报告" in result.report_markdown
    assert result.todo_items[0].status == "completed"
    assert repo.reports[deep_agent.run_id].markdown == result.report_markdown


def test_agent_stream_preserves_frontend_event_protocol(monkeypatch):
    monkeypatch.setattr(agent_module, "dispatch_search", fake_search)
    config = Configuration(enable_notes=True, notes_workspace=str(make_notes_dir()), rag_enabled=False)
    deep_agent = agent_module.DeepResearchAgent(config=config, chat_model=FakeChatModel())

    events = list(deep_agent.run_stream("topic"))
    event_types = [event["type"] for event in events]

    assert "todo_list" in event_types
    assert "sources" in event_types
    assert "task_summary_chunk" in event_types
    assert "task_status" in event_types
    assert "final_report" in event_types
    assert event_types[-1] == "done"


def test_agent_stream_emits_langgraph_workflow_nodes(monkeypatch):
    monkeypatch.setattr(agent_module, "dispatch_search", fake_search)
    config = Configuration(enable_notes=True, notes_workspace=str(make_notes_dir()), rag_enabled=False)
    deep_agent = agent_module.DeepResearchAgent(config=config, chat_model=FakeChatModel())

    events = list(deep_agent.run_stream("topic"))
    workflow_nodes = [
        event
        for event in events
        if event["type"] == "workflow_node" and event["status"] in {"completed", "skipped"}
    ]
    node_names = {event["node"] for event in workflow_nodes}

    assert "plan_tasks" in node_names
    assert "retrieve_documents" in node_names
    assert "search_web" in node_names
    assert "summarize_task" in node_names
    assert "write_report" in node_names
    assert any(
        event["node"] == "retrieve_documents" and event["status"] == "skipped"
        for event in workflow_nodes
    )


def test_agent_stream_emits_workflow_graph_topology(monkeypatch):
    monkeypatch.setattr(agent_module, "dispatch_search", fake_search)
    config = Configuration(enable_notes=True, notes_workspace=str(make_notes_dir()), rag_enabled=False)
    deep_agent = agent_module.DeepResearchAgent(config=config, chat_model=FakeChatModel())

    events = list(deep_agent.run_stream("topic"))
    graph_event = next(event for event in events if event["type"] == "workflow_graph")
    node_ids = {node["id"] for node in graph_event["nodes"]}
    edges = {(edge["from"], edge["to"]) for edge in graph_event["edges"]}

    assert "global:plan_tasks" in node_ids
    assert "global:dispatch_tasks" in node_ids
    assert "global:write_report" in node_ids
    assert "task:1:search_web" in node_ids
    assert ("global:dispatch_tasks", "task:1:prepare_task") in edges
    assert ("task:1:persist_task", "global:join_tasks") in edges


def test_agent_stream_starts_multiple_tasks_before_first_completion(monkeypatch):
    def slow_search(query, config, loop_count):
        time.sleep(0.05)
        return fake_search(query, config, loop_count)

    monkeypatch.setattr(agent_module, "dispatch_search", slow_search)
    config = Configuration(enable_notes=True, notes_workspace=str(make_notes_dir()), rag_enabled=False)
    deep_agent = agent_module.DeepResearchAgent(config=config, chat_model=FakeChatModel())

    events = list(deep_agent.run_stream("topic"))
    started_before_completion = set()
    for event in events:
        if event["type"] == "task_status" and event.get("status") == "completed":
            break
        if event["type"] == "task_status" and event.get("status") == "in_progress":
            started_before_completion.add(event["task_id"])

    assert len(started_before_completion) > 1


def test_rag_disabled_marks_each_task_retrieval_skipped(monkeypatch):
    monkeypatch.setattr(agent_module, "dispatch_search", fake_search)
    config = Configuration(enable_notes=True, notes_workspace=str(make_notes_dir()), rag_enabled=False)
    deep_agent = agent_module.DeepResearchAgent(config=config, chat_model=FakeChatModel())

    events = list(deep_agent.run_stream("topic"))
    todo_event = next(event for event in events if event["type"] == "todo_list")
    skipped_retrievals = {
        event["task_id"]
        for event in events
        if event["type"] == "workflow_node"
        and event["node"] == "retrieve_documents"
        and event["status"] == "skipped"
    }

    assert skipped_retrievals == {task["id"] for task in todo_event["tasks"]}


def test_agent_stream_continues_when_search_has_no_results(monkeypatch):
    monkeypatch.setattr(agent_module, "dispatch_search", empty_search)
    config = Configuration(enable_notes=True, notes_workspace=str(make_notes_dir()), rag_enabled=False)
    deep_agent = agent_module.DeepResearchAgent(config=config, chat_model=FakeChatModel())

    events = list(deep_agent.run_stream("topic"))
    event_types = [event["type"] for event in events]
    task_statuses = [
        event
        for event in events
        if event["type"] == "task_status" and event.get("status") == "skipped"
    ]

    assert task_statuses
    assert "final_report" in event_types
    assert event_types[-1] == "done"


def test_agent_supplements_too_short_task_plan(monkeypatch):
    monkeypatch.setattr(agent_module, "dispatch_search", fake_search)

    class OneTaskModel(FakeChatModel):
        def invoke(self, messages):
            system = messages[0].content
            if "研究规划专家" in system:
                return Response(
                    '{"tasks":[{"title":"背景","intent":"了解背景","query":"topic background"}]}'
                )
            return super().invoke(messages)

    config = Configuration(enable_notes=True, notes_workspace=str(make_notes_dir()), rag_enabled=False)
    deep_agent = agent_module.DeepResearchAgent(config=config, chat_model=OneTaskModel())

    events = list(deep_agent.run_stream("topic"))
    todo_event = next(event for event in events if event["type"] == "todo_list")

    assert len(todo_event["tasks"]) == 4
    assert todo_event["tasks"][0]["title"] == "背景"
    assert todo_event["tasks"][1]["title"] == "基础背景梳理"


def test_tool_call_only_summary_falls_back_to_empty_message(monkeypatch):
    monkeypatch.setattr(agent_module, "dispatch_search", fake_search)
    config = Configuration(enable_notes=True, notes_workspace=str(make_notes_dir()), rag_enabled=False)
    deep_agent = agent_module.DeepResearchAgent(config=config, chat_model=ToolCallOnlySummaryModel())

    result = deep_agent.run("topic")

    assert result.todo_items[0].summary == "暂无可用信息"
    assert "tool_call" not in result.todo_items[0].summary


def test_fastapi_research_endpoint_with_mock_agent(monkeypatch):
    class FakeAgent:
        def __init__(self, config, **kwargs):
            pass

        def run(self, topic):
            task = agent_module.TodoItem(
                id=1,
                title="背景",
                intent="了解背景",
                query=topic,
                status="completed",
                summary="summary",
                sources_summary="sources",
            )
            return agent_module.SummaryStateOutput(
                running_summary="report",
                report_markdown="report",
                todo_items=[task],
            )

    monkeypatch.setattr(main_module, "DeepResearchAgent", FakeAgent)
    app = main_module.create_app()

    from fastapi.testclient import TestClient

    response = TestClient(app).post("/research", json={"topic": "topic"})

    assert response.status_code == 200
    assert response.json()["report_markdown"] == "report"


def test_fastapi_research_runs_endpoints(monkeypatch):
    repo = InMemoryResearchRepository()
    repo.save_run(agent_module.ResearchRun(id="run-api", topic="topic", search_api="duckduckgo"))
    repo.save_report(agent_module.ResearchReport(run_id="run-api", markdown="# 报告"))

    monkeypatch.setattr(main_module, "create_research_repository", lambda config: repo)
    app = main_module.create_app()

    from fastapi.testclient import TestClient

    client = TestClient(app)
    list_response = client.get("/research/runs")
    detail_response = client.get("/research/runs/run-api")
    missing_response = client.get("/research/runs/missing")

    assert list_response.status_code == 200
    assert list_response.json()["runs"][0]["id"] == "run-api"
    assert detail_response.status_code == 200
    assert detail_response.json()["report"]["markdown"] == "# 报告"
    assert missing_response.status_code == 404
