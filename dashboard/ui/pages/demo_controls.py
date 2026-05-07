from datetime import datetime, timezone

import streamlit as st

from ui.api import ApiClient, now_utc_iso
from ui.components import hero, section, show_api_error


def render_demo_controls_page(client: ApiClient) -> None:
    hero(
        "Demo Controls",
        "Trigger realistic drift events without typing curl commands during your presentation.",
    )

    st.warning(
        "Use this page for local demos only. It sends synthetic drift webhooks to the agent."
    )

    section(
        "Critical Feature Drift → Retrain Approval",
        "This starts the main demo flow: drift, investigation, retrain approval, queue job, candidate model, promotion approval.",
    )

    model_version = st.text_input("Current model version", value="6")
    event_suffix = st.text_input(
        "Unique event suffix",
        value=datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S"),
    )

    event_id = f"dashboard_demo_retrain_{event_suffix}"

    payload = _critical_retrain_payload(
        event_id=event_id,
        model_version=model_version,
    )

    _json_expander("Payload preview", payload)

    if st.button("Trigger critical retrain demo", use_container_width=True):
        result = client.send_drift_webhook(
            payload=payload,
            idempotency_key=event_id,
        )

        if result.ok:
            st.success("Critical drift webhook sent.")
            _json_expander("Agent response", result.data, expanded=True)
        else:
            show_api_error("Failed to send webhook", result.error, result.data)

    st.divider()

    section(
        "Warning Drift → Replay Test",
        "Use this to show the lighter path: warning drift dispatches a replay test.",
    )

    warning_event_id = f"dashboard_demo_warning_{event_suffix}"
    warning_payload = _warning_replay_payload(
        event_id=warning_event_id,
        model_version=model_version,
    )

    _json_expander("Warning payload preview", warning_payload)

    if st.button("Trigger warning replay demo", use_container_width=True):
        result = client.send_drift_webhook(
            payload=warning_payload,
            idempotency_key=warning_event_id,
        )

        if result.ok:
            st.success("Warning drift webhook sent.")
            _json_expander("Agent response", result.data, expanded=True)
        else:
            show_api_error("Failed to send webhook", result.error, result.data)

    st.divider()

    section(
        "Critical Output Drift → Rollback Approval",
        "Use this to show the rollback approval path.",
    )

    rollback_event_id = f"dashboard_demo_rollback_{event_suffix}"
    rollback_payload = _critical_rollback_payload(
        event_id=rollback_event_id,
        model_version=model_version,
    )

    _json_expander("Rollback payload preview", rollback_payload)

    if st.button("Trigger rollback approval demo", use_container_width=True):
        result = client.send_drift_webhook(
            payload=rollback_payload,
            idempotency_key=rollback_event_id,
        )

        if result.ok:
            st.success("Critical output drift webhook sent.")
            _json_expander("Agent response", result.data, expanded=True)
        else:
            show_api_error("Failed to send webhook", result.error, result.data)


def _json_expander(title: str, data, expanded: bool = False) -> None:
    with st.expander(title, expanded=expanded):
        st.json(data)


def _base_payload(
    *,
    event_id: str,
    model_version: str,
    previous_severity: str,
    new_severity: str,
    overall_score: float,
    triggered_by: str,
) -> dict:
    return {
        "contract_version": "v1",
        "event_type": "drift.severity_changed",
        "event_id": event_id,
        "created_at": now_utc_iso(),
        "source_service": "model_service",
        "model_name": "drift-triage-bank-marketing-classifier",
        "model_version": model_version,
        "previous_severity": previous_severity,
        "new_severity": new_severity,
        "overall_score": overall_score,
        "sample_size": 320,
        "min_required_samples": 30,
        "metadata": {
            "triggered_by": triggered_by,
        },
    }


def _critical_retrain_payload(
    *,
    event_id: str,
    model_version: str,
) -> dict:
    payload = _base_payload(
        event_id=event_id,
        model_version=model_version,
        previous_severity="normal",
        new_severity="critical",
        overall_score=0.88,
        triggered_by="dashboard_critical_retrain_demo",
    )

    payload["drift_report"] = {
        "sample_size": 320,
        "min_required_samples": 30,
        "severity": "critical",
        "overall_score": 0.88,
        "features": [
            {
                "feature": "campaign",
                "kind": "numeric",
                "score": 0.88,
                "severity": "critical",
                "details": {
                    "reason": "Dashboard demo: critical numeric feature drift"
                },
            },
            {
                "feature": "month",
                "kind": "categorical",
                "score": 0.55,
                "severity": "warning",
                "details": {
                    "reason": "Dashboard demo: warning categorical drift"
                },
            },
        ],
        "output_drift": {
            "kind": "prediction_rate",
            "score": 0.10,
            "severity": "normal",
        },
    }

    return payload


def _warning_replay_payload(
    *,
    event_id: str,
    model_version: str,
) -> dict:
    payload = _base_payload(
        event_id=event_id,
        model_version=model_version,
        previous_severity="normal",
        new_severity="warning",
        overall_score=0.22,
        triggered_by="dashboard_warning_replay_demo",
    )

    payload["drift_report"] = {
        "sample_size": 200,
        "min_required_samples": 30,
        "severity": "warning",
        "overall_score": 0.22,
        "features": [
            {
                "feature": "euribor3m",
                "kind": "numeric",
                "score": 0.22,
                "severity": "warning",
                "details": {
                    "reason": "Dashboard demo: warning drift should run replay test"
                },
            }
        ],
        "output_drift": {
            "kind": "prediction_rate",
            "score": 0.08,
            "severity": "normal",
        },
    }

    return payload


def _critical_rollback_payload(
    *,
    event_id: str,
    model_version: str,
) -> dict:
    payload = _base_payload(
        event_id=event_id,
        model_version=model_version,
        previous_severity="warning",
        new_severity="critical",
        overall_score=0.91,
        triggered_by="dashboard_critical_rollback_demo",
    )

    payload["drift_report"] = {
        "sample_size": 320,
        "min_required_samples": 30,
        "severity": "critical",
        "overall_score": 0.91,
        "features": [
            {
                "feature": "euribor3m",
                "kind": "numeric",
                "score": 0.72,
                "severity": "critical",
                "details": {
                    "reason": "Dashboard demo: critical drift after warning"
                },
            }
        ],
        "output_drift": {
            "kind": "output_probability",
            "score": 0.41,
            "severity": "critical",
        },
    }

    return payload