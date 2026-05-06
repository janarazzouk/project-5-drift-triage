from app.agents.routing import build_action_decision
from app.agents.state import AgentState, append_message


def action_node(state: AgentState) -> AgentState:
    action_result = build_action_decision(state)

    recommended_action = action_result["recommended_action"]
    production_action_required = action_result["production_action_required"]
    queue_job_required = action_result["queue_job_required"]

    content = (
        f"Action decision completed. Recommended action={recommended_action}, "
        f"production_action_required={production_action_required}, "
        f"queue_job_required={queue_job_required}."
    )

    return {
        "action_result": action_result,
        "recommended_action": recommended_action,
        "production_action_required": production_action_required,
        "queue_job_required": queue_job_required,
        "current_step": "action_completed",
        "status": "running",
        "messages": append_message(
            state,
            role="agent",
            node_name="action",
            content=content,
            metadata=action_result,
        ),
    }