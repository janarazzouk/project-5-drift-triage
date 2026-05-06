from app.agents.routing import choose_next_node
from app.agents.state import AgentState, append_message


def supervisor_node(state: AgentState) -> AgentState:
    next_node = choose_next_node(state)

    return {
        "next_node": next_node,
        "status": state.get("status", "running"),
        "messages": append_message(
            state,
            role="agent",
            node_name="supervisor",
            content=f"Supervisor routed the investigation to: {next_node}.",
            metadata={
                "current_step": state.get("current_step"),
                "next_node": next_node,
            },
        ),
    }


def route_from_supervisor(state: AgentState) -> str:
    return state.get("next_node") or "end"