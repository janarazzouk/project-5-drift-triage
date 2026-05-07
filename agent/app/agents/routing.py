from typing import Any

from app.agents.state import AgentState


SEVERITY_ORDER = {
    "insufficient_data": 0,
    "normal": 1,
    "warning": 2,
    "critical": 3,
}


def choose_next_node(state: AgentState) -> str:
    current_step = state.get("current_step", "created")

    if current_step in {"created", "webhook_received"}:
        return "triage"

    if current_step == "triage_completed":
        return "action"

    if current_step == "action_completed":
        if state.get("production_action_required"):
            return "approval"

        return "comms"

    if current_step == "approval_required":
        return "comms"

    if current_step == "comms_completed":
        return "completion"

    if current_step in {
        "agent_decision_completed",
        "waiting_for_job",
        "waiting_for_approval",
        "completed",
        "failed",
    }:
        return "end"

    return "completion"


def extract_drifted_features(
    drift_report: dict[str, Any],
    *,
    min_severity: str = "warning",
) -> list[str]:
    min_rank = SEVERITY_ORDER.get(min_severity, 2)
    drifted_features = []

    for feature_result in drift_report.get("features", []):
        severity = feature_result.get("severity", "normal")
        severity_rank = SEVERITY_ORDER.get(severity, 0)

        if severity_rank >= min_rank:
            feature_name = feature_result.get("feature")

            if feature_name:
                drifted_features.append(feature_name)

    return drifted_features


def get_output_drift_severity(
    drift_report: dict[str, Any],
) -> str | None:
    output_drift = drift_report.get("output_drift")

    if not output_drift:
        return None

    return output_drift.get("severity")


def get_primary_issue(
    drift_report: dict[str, Any],
) -> str:
    drifted_features = extract_drifted_features(drift_report)
    output_drift_severity = get_output_drift_severity(drift_report)

    if drifted_features and output_drift_severity in {"warning", "critical"}:
        return "feature_and_output_drift"

    if drifted_features:
        return "feature_drift"

    if output_drift_severity in {"warning", "critical"}:
        return "output_drift"

    return "no_strong_drift_signal"


def build_triage_decision(state: AgentState) -> dict[str, Any]:
    severity = state.get("severity") or state.get("new_severity") or "normal"
    drift_report = state.get("drift_report") or {}

    drifted_features = extract_drifted_features(drift_report)
    output_drift_severity = get_output_drift_severity(drift_report)
    primary_issue = get_primary_issue(drift_report)

    if severity == "critical":
        risk_level = "high"
    elif severity == "warning":
        risk_level = "medium"
    elif severity == "insufficient_data":
        risk_level = "unknown"
    else:
        risk_level = "low"

    if severity == "insufficient_data":
        explanation = (
            "The platform does not have enough recent predictions to make a reliable "
            "drift decision yet."
        )
    elif severity == "normal":
        explanation = (
            "The latest drift check is normal. No immediate model action is required."
        )
    elif severity == "warning":
        explanation = (
            "Warning-level drift was detected. A replay test should verify whether "
            "the model service still behaves as expected."
        )
    else:
        explanation = (
            "Critical drift was detected. The model may be unsafe for Production, "
            "so a stronger action may be required."
        )

    return {
        "severity": severity,
        "risk_level": risk_level,
        "primary_issue": primary_issue,
        "explanation": explanation,
        "drifted_features": drifted_features,
        "output_drift_severity": output_drift_severity,
    }


def build_action_decision(state: AgentState) -> dict[str, Any]:
    severity = state.get("severity") or state.get("new_severity") or "normal"
    previous_severity = state.get("previous_severity")
    triage_result = state.get("triage_result") or {}
    output_drift_severity = triage_result.get("output_drift_severity")

    if severity == "insufficient_data":
        return {
            "recommended_action": "monitor",
            "production_action_required": False,
            "queue_job_required": False,
            "target_environment": None,
            "reason": (
                "There is not enough drift data yet. Keep collecting predictions "
                "before dispatching replay, retrain, or rollback tools."
            ),
        }

    if severity == "normal":
        if previous_severity and previous_severity != "normal":
            return {
                "recommended_action": "resolve",
                "production_action_required": False,
                "queue_job_required": False,
                "target_environment": None,
                "reason": (
                    "Drift severity recovered to normal. Resolve the investigation "
                    "without touching Production."
                ),
            }

        return {
            "recommended_action": "monitor",
            "production_action_required": False,
            "queue_job_required": False,
            "target_environment": None,
            "reason": "Drift is normal. Continue monitoring.",
        }

    if severity == "warning":
        return {
            "recommended_action": "replay_test",
            "production_action_required": False,
            "queue_job_required": True,
            "target_environment": None,
            "reason": (
                "Warning drift should first dispatch a replay test to confirm that "
                "the serving path, preprocessing, and model artifacts are still stable."
            ),
        }

    if severity == "critical":
        if previous_severity == "warning" or output_drift_severity == "critical":
            return {
                "recommended_action": "rollback_production",
                "production_action_required": True,
                "queue_job_required": False,
                "target_environment": "production",
                "reason": (
                    "Critical drift after a warning state or critical output drift can "
                    "indicate Production risk. Request human approval before rollback."
                ),
            }

        return {
            "recommended_action": "retrain",
            "production_action_required": True,
            "queue_job_required": False,
            "target_environment": "candidate",
            "reason": (
                "Critical feature drift was detected. Retraining can create a new "
                "candidate model and consume training resources, so it requires human "
                "approval before the Redis retrain job is queued."
            ),
        }

    return {
        "recommended_action": "monitor",
        "production_action_required": False,
        "queue_job_required": False,
        "target_environment": None,
        "reason": "No matching route was found. Defaulting to monitor.",
    }


def build_summary(state: AgentState) -> str:
    investigation_id = state.get("investigation_id", "unknown")
    severity = state.get("severity", "unknown")
    previous_severity = state.get("previous_severity", "unknown")
    model_name = state.get("model_name", "unknown")
    model_version = state.get("model_version") or "unknown"

    triage_result = state.get("triage_result") or {}
    action_result = state.get("action_result") or {}

    recommended_action = action_result.get("recommended_action", "monitor")
    action_reason = action_result.get("reason", "No reason provided.")
    primary_issue = triage_result.get("primary_issue", "unknown")
    drifted_features = triage_result.get("drifted_features") or []

    feature_text = (
        ", ".join(drifted_features)
        if drifted_features
        else "no individual warning/critical feature listed"
    )

    if action_result.get("production_action_required"):
        next_step = "waiting for human approval in the dashboard"
    elif action_result.get("queue_job_required"):
        next_step = "dispatching a Redis background job"
    elif recommended_action == "resolve":
        next_step = "resolving the investigation"
    else:
        next_step = "continuing to monitor"

    return (
        f"Investigation {investigation_id}: drift severity changed from "
        f"{previous_severity} to {severity} for model {model_name} "
        f"version {model_version}. Primary issue: {primary_issue}. "
        f"Drifted features: {feature_text}. Recommended action: "
        f"{recommended_action}. Reason: {action_reason} Next step: {next_step}."
    )