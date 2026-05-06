from app.agents.routing import build_summary
from app.agents.state import AgentState, append_message


def comms_node(state: AgentState) -> AgentState:
    summary = build_summary(state)

    return {
        "summary": summary,
        "current_step": "comms_completed",
        "status": "running",
        "messages": append_message(
            state,
            role="agent",
            node_name="comms",
            content=summary,
            metadata={
                "recommended_action": state.get("recommended_action"),
                "production_action_required": state.get("production_action_required"),
                "queue_job_required": state.get("queue_job_required"),
            },
        ),
    }