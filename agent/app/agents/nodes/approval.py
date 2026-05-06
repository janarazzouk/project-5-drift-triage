from app.agents.state import AgentState, append_message


def approval_node(state: AgentState) -> AgentState:
    recommended_action = state.get("recommended_action") or "unknown"

    if not state.get("production_action_required"):
        return {
            "approval_status": "not_required",
            "current_step": "approval_not_required",
            "messages": append_message(
                state,
                role="agent",
                node_name="approval",
                content="Approval node checked the action. Human approval is not required.",
                metadata={
                    "recommended_action": recommended_action,
                    "production_action_required": False,
                },
            ),
        }

    return {
        "approval_status": "required",
        "current_step": "approval_required",
        "status": "running",
        "messages": append_message(
            state,
            role="agent",
            node_name="approval",
            content=(
                f"Human approval is required before executing Production action: "
                f"{recommended_action}."
            ),
            metadata={
                "recommended_action": recommended_action,
                "production_action_required": True,
            },
        ),
    }