from app.agents.routing import build_triage_decision
from app.agents.state import AgentState, append_message


def triage_node(state: AgentState) -> AgentState:
    triage_result = build_triage_decision(state)

    content = (
        f"Triage completed. Severity={triage_result['severity']}, "
        f"risk_level={triage_result['risk_level']}, "
        f"primary_issue={triage_result['primary_issue']}."
    )

    return {
        "triage_result": triage_result,
        "current_step": "triage_completed",
        "status": "running",
        "messages": append_message(
            state,
            role="agent",
            node_name="triage",
            content=content,
            metadata=triage_result,
        ),
    }