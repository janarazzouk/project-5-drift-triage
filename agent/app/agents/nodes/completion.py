from app.agents.state import AgentState, append_message


def completion_node(state: AgentState) -> AgentState:
    recommended_action = state.get("recommended_action")
    production_action_required = bool(state.get("production_action_required"))
    queue_job_required = bool(state.get("queue_job_required"))

    if production_action_required:
        status = "running"
        result_message = (
            "Agent decision completed. The service layer will create a human approval "
            "request before any Production action is executed."
        )
    elif queue_job_required:
        status = "running"
        result_message = (
            "Agent decision completed. The service layer will enqueue the selected "
            "background job in Redis."
        )
    elif recommended_action in {"monitor", "resolve", None}:
        status = "resolved"
        result_message = "Agent decision completed. No Production action or queue job is required."
    else:
        status = "running"
        result_message = "Agent decision completed."

    result = {
        "recommended_action": recommended_action,
        "production_action_required": production_action_required,
        "queue_job_required": queue_job_required,
        "summary": state.get("summary"),
    }

    return {
        "status": status,
        "current_step": "agent_decision_completed",
        "result": result,
        "messages": append_message(
            state,
            role="agent",
            node_name="completion",
            content=result_message,
            metadata=result,
        ),
    }