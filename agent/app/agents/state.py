from typing import Any, Literal, TypedDict


DriftSeverity = Literal[
    "insufficient_data",
    "normal",
    "warning",
    "critical",
]


AgentStatus = Literal[
    "open",
    "running",
    "waiting_for_job",
    "waiting_for_approval",
    "resolved",
    "failed",
]


class AgentMessage(TypedDict, total=False):
    role: str
    node_name: str
    content: str
    metadata: dict[str, Any]


class TriageResult(TypedDict, total=False):
    severity: str
    risk_level: str
    primary_issue: str
    explanation: str
    drifted_features: list[str]
    output_drift_severity: str | None


class ActionResult(TypedDict, total=False):
    recommended_action: str
    production_action_required: bool
    queue_job_required: bool
    reason: str


class AgentState(TypedDict, total=False):
    investigation_id: str
    event_id: str

    model_name: str
    model_version: str | None

    previous_severity: str
    new_severity: str
    severity: str

    overall_score: float
    sample_size: int
    min_required_samples: int

    drift_report: dict[str, Any]
    metadata: dict[str, Any]

    status: str
    current_step: str
    next_node: str | None

    triage_result: TriageResult
    action_result: ActionResult

    recommended_action: str | None
    production_action_required: bool
    queue_job_required: bool

    approval_id: str | None
    approval_status: str | None

    queued_job_ids: list[str]

    summary: str | None
    result: dict[str, Any] | None

    messages: list[AgentMessage]


def append_message(
    state: AgentState,
    *,
    role: str,
    node_name: str,
    content: str,
    metadata: dict[str, Any] | None = None,
) -> list[AgentMessage]:
    messages = list(state.get("messages") or [])

    messages.append(
        {
            "role": role,
            "node_name": node_name,
            "content": content,
            "metadata": metadata or {},
        }
    )

    return messages