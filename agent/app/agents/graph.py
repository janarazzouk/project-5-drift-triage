from typing import Any

from langgraph.graph import END, START, StateGraph

from app.agents.nodes import (
    action_node,
    approval_node,
    comms_node,
    completion_node,
    triage_node,
)
from app.agents.state import AgentState
from app.agents.supervisor import route_from_supervisor, supervisor_node
from app.core.config import Settings
from app.services.checkpoint_service import CheckpointService


def build_investigation_graph(
    *,
    checkpoint_service: CheckpointService | None = None,
):
    graph_builder = StateGraph(AgentState)

    graph_builder.add_node("supervisor", supervisor_node)
    graph_builder.add_node("triage", triage_node)
    graph_builder.add_node("action", action_node)
    graph_builder.add_node("approval", approval_node)
    graph_builder.add_node("comms", comms_node)
    graph_builder.add_node("completion", completion_node)

    graph_builder.add_edge(START, "supervisor")

    graph_builder.add_conditional_edges(
        "supervisor",
        route_from_supervisor,
        {
            "triage": "triage",
            "action": "action",
            "approval": "approval",
            "comms": "comms",
            "completion": "completion",
            "end": END,
        },
    )

    graph_builder.add_edge("triage", "supervisor")
    graph_builder.add_edge("action", "supervisor")
    graph_builder.add_edge("approval", "supervisor")
    graph_builder.add_edge("comms", "supervisor")
    graph_builder.add_edge("completion", "supervisor")

    checkpointer = None

    if checkpoint_service is not None:
        checkpointer = checkpoint_service.get_checkpointer()

    return graph_builder.compile(checkpointer=checkpointer)


def prepare_initial_state(initial_state: dict[str, Any]) -> AgentState:
    state = dict(initial_state)

    state.setdefault("status", "running")
    state.setdefault("current_step", "created")
    state.setdefault("queued_job_ids", [])
    state.setdefault("messages", [])
    state.setdefault("production_action_required", False)
    state.setdefault("queue_job_required", False)
    state.setdefault("approval_id", None)
    state.setdefault("approval_status", None)
    state.setdefault("summary", None)
    state.setdefault("result", None)

    if "severity" not in state:
        state["severity"] = state.get("new_severity", "normal")

    return state


def run_investigation_graph(
    *,
    settings: Settings,
    checkpoint_service: CheckpointService,
    initial_state: dict[str, Any],
    graph_thread_id: str,
) -> dict[str, Any]:
    graph = build_investigation_graph(
        checkpoint_service=checkpoint_service,
    )

    state = prepare_initial_state(initial_state)

    config = checkpoint_service.build_config(graph_thread_id)

    final_state = graph.invoke(
        state,
        config=config,
    )

    return dict(final_state)