"""深度研究工作流的 LangGraph 定义。"""

from __future__ import annotations

from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

from models import SummaryState


class ResearchGraphState(TypedDict):
    """在 LangGraph 节点之间传递的运行时状态。"""

    agent: Any
    state: SummaryState


def build_research_graph():
    """构建并编译研究工作流图。"""

    graph = StateGraph(ResearchGraphState)
    graph.add_node("plan_tasks", lambda payload: payload["agent"]._graph_plan_tasks(payload))
    graph.add_node("execute_tasks", lambda payload: payload["agent"]._graph_execute_tasks(payload))
    graph.add_node("generate_report", lambda payload: payload["agent"]._graph_generate_report(payload))
    graph.add_node("persist_report", lambda payload: payload["agent"]._graph_persist_report(payload))

    graph.set_entry_point("plan_tasks")
    graph.add_edge("plan_tasks", "execute_tasks")
    graph.add_edge("execute_tasks", "generate_report")
    graph.add_edge("generate_report", "persist_report")
    graph.add_edge("persist_report", END)

    return graph.compile()
