from app.agents.state import AgentState, append_message


def approval_node(state: AgentState) -> AgentState:
    recommended_action = state.get("recommended_action") or "unknown"
    action_result = state.get("action_result") or {}
    target_environment = action_result.get("target_environment") or "production"

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
                    "target_environment": target_environment,
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
                f"Human approval is required before executing action "
                f"'{recommended_action}' for target environment "
                f"'{target_environment}'."
            ),
            metadata={
                "recommended_action": recommended_action,
                "production_action_required": True,
                "target_environment": target_environment,
            },
        ),
    }