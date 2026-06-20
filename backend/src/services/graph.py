"""深度研究工作流的 LangGraph 图定义。"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, StateGraph
from langgraph.types import Send

from models import SummaryState, TodoItem


class ResearchGraphState(TypedDict, total=False):
    """父图在规划、并行任务和报告阶段传递的状态。"""

    agent: Any
    state: SummaryState
    task_cursor: int
    task_results: Annotated[list[TodoItem], operator.add]


class TaskGraphState(TypedDict, total=False):
    """单个任务子图的局部状态。"""

    agent: Any
    state: SummaryState
    task: TodoItem
    task_index: int
    retrieval_context: str
    search_context: str


def build_task_graph():
    """构建单个研究任务的子图。"""

    graph = StateGraph(TaskGraphState)

    graph.add_node("prepare_task", lambda payload: payload["agent"]._task_prepare_task(payload))
    graph.add_node(
        "retrieve_documents",
        lambda payload: payload["agent"]._task_retrieve_documents(payload),
    )
    graph.add_node("search_web", lambda payload: payload["agent"]._task_search_web(payload))
    graph.add_node("summarize_task", lambda payload: payload["agent"]._task_summarize_task(payload))
    graph.add_node("persist_task", lambda payload: payload["agent"]._task_persist_task(payload))

    graph.set_entry_point("prepare_task")
    graph.add_conditional_edges(
        "prepare_task",
        lambda payload: payload["agent"]._task_should_retrieve(payload),
        {
            "retrieve_documents": "retrieve_documents",
            "search_web": "search_web",
        },
    )
    graph.add_edge("retrieve_documents", "search_web")
    graph.add_edge("search_web", "summarize_task")
    graph.add_edge("summarize_task", "persist_task")
    graph.add_edge("persist_task", END)

    return graph.compile()


def build_research_graph():
    """构建并编译父级研究工作流图。"""

    graph = StateGraph(ResearchGraphState)

    graph.add_node("plan_tasks", lambda payload: payload["agent"]._graph_plan_tasks(payload))
    graph.add_node(
        "dispatch_tasks",
        lambda payload: payload["agent"]._graph_dispatch_tasks(payload),
    )
    graph.add_node("run_task", lambda payload: payload["agent"]._graph_run_task(payload))
    graph.add_node("join_tasks", lambda payload: payload["agent"]._graph_join_tasks(payload))
    graph.add_node("write_report", lambda payload: payload["agent"]._graph_write_report(payload))
    graph.add_node("persist_report", lambda payload: payload["agent"]._graph_persist_report(payload))

    graph.set_entry_point("plan_tasks")
    graph.add_edge("plan_tasks", "dispatch_tasks")
    graph.add_conditional_edges(
        "dispatch_tasks",
        lambda payload: payload["agent"]._graph_route_task_batch(payload),
        {
            "run_task": "run_task",
            "join_tasks": "join_tasks",
        },
    )
    graph.add_edge("run_task", "join_tasks")
    graph.add_conditional_edges(
        "join_tasks",
        lambda payload: payload["agent"]._graph_after_join(payload),
        {
            "dispatch_tasks": "dispatch_tasks",
            "write_report": "write_report",
        },
    )
    graph.add_edge("write_report", "persist_report")
    graph.add_edge("persist_report", END)

    return graph.compile()


def send_task(node: str, payload: dict[str, Any]) -> Send:
    """为父图创建任务分发指令。"""

    return Send(node, payload)
