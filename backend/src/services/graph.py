"""深度研究工作流的 LangGraph 状态机定义。"""

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
    graph.add_node("select_next_task", lambda payload: payload["agent"]._graph_select_next_task(payload))
    graph.add_node("prepare_task", lambda payload: payload["agent"]._graph_prepare_task(payload))
    graph.add_node("retrieve_documents", lambda payload: payload["agent"]._graph_retrieve_documents(payload))
    graph.add_node("search_web", lambda payload: payload["agent"]._graph_search_web(payload))
    graph.add_node("summarize_task", lambda payload: payload["agent"]._graph_summarize_task(payload))
    graph.add_node("persist_task", lambda payload: payload["agent"]._graph_persist_task(payload))
    graph.add_node("write_report", lambda payload: payload["agent"]._graph_write_report(payload))
    graph.add_node("persist_report", lambda payload: payload["agent"]._graph_persist_report(payload))

    graph.set_entry_point("plan_tasks")
    graph.add_edge("plan_tasks", "select_next_task")
    graph.add_edge("select_next_task", "prepare_task")
    graph.add_conditional_edges(
        "prepare_task",
        lambda payload: payload["agent"]._graph_should_retrieve(payload),
        {
            "retrieve_documents": "retrieve_documents",
            "search_web": "search_web",
        },
    )
    graph.add_edge("retrieve_documents", "search_web")
    graph.add_edge("search_web", "summarize_task")
    graph.add_edge("summarize_task", "persist_task")
    graph.add_conditional_edges(
        "persist_task",
        lambda payload: payload["agent"]._graph_should_continue(payload),
        {
            "select_next_task": "select_next_task",
            "write_report": "write_report",
        },
    )
    graph.add_edge("write_report", "persist_report")
    graph.add_edge("persist_report", END)

    return graph.compile()
