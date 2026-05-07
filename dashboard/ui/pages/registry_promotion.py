import pandas as pd
import streamlit as st

from ui.api import ApiClient
from ui.components import (
    extract_list,
    hero,
    json_expander,
    kpi_card,
    safe_get,
    section,
    show_api_error,
)


def render_registry_promotion_page(client: ApiClient) -> None:
    hero(
        "Registry & Promotion",
        "Understand which model is active and why a candidate can or cannot reach Production.",
    )

    registry = client.get_registry()
    checklist = client.get_promotion_checklist()

    col_left, col_right = st.columns([1, 1])

    with col_left:
        section("Registry State", "Current model state from the model service.")

        if registry.ok:
            data = registry.data if isinstance(registry.data, dict) else {}

            c1, c2 = st.columns(2)
            with c1:
                kpi_card("Model Name", data.get("model_name", "—"), "Registry model")
            with c2:
                kpi_card("Version", data.get("model_version", "—"), "Current version")

            c3, c4 = st.columns(2)
            with c3:
                kpi_card("Stage", data.get("stage", data.get("environment", "—")), "Lifecycle stage")
            with c4:
                kpi_card("Threshold", data.get("selected_threshold", "—"), "Operating threshold")

            json_expander("Raw registry response", registry.data)
        else:
            show_api_error("Registry unavailable", registry.error, registry.data)

    with col_right:
        section("Promotion Checklist", "Programmatic gate before Production.")

        if checklist.ok:
            data = checklist.data if isinstance(checklist.data, dict) else {}
            passed = data.get("passed", "—")
            checks = data.get("checks") or []

            kpi_card("Checklist Passed", passed, "All checks must pass for Production promotion")

            if checks:
                st.dataframe(pd.DataFrame(checks), use_container_width=True, hide_index=True)

            json_expander("Raw checklist response", checklist.data)
        else:
            show_api_error("Promotion checklist unavailable", checklist.error, checklist.data)

    st.divider()

    section(
        "Latest Candidate From Investigations",
        "Useful after an approved retrain creates a candidate model.",
    )

    investigations = client.list_investigations()

    if not investigations.ok:
        st.info("Could not load investigations to find a recent candidate model.")
        return

    items = extract_list(investigations.data, "investigations")

    selected_candidate = None
    selected_investigation_id = None

    for item in items:
        investigation_id = item.get("id") or item.get("investigation_id")
        if not investigation_id:
            continue

        detail = client.get_investigation(investigation_id)
        if not detail.ok:
            continue

        candidate = safe_get(detail.data, "state_json", "candidate_model")
        if candidate:
            selected_candidate = candidate
            selected_investigation_id = investigation_id
            break

    if not selected_candidate:
        st.info("No candidate model found in recent investigations.")
        return

    c1, c2, c3 = st.columns(3)
    with c1:
        kpi_card("Candidate Version", selected_candidate.get("model_version", "—"), "From latest retrain")
    with c2:
        kpi_card("Investigation", selected_investigation_id, "Source investigation")
    with c3:
        kpi_card("Threshold", selected_candidate.get("selected_threshold", "—"), "Candidate threshold")

    metrics = selected_candidate.get("test_metrics") or {}

    if metrics:
        required = {
            "accuracy": "0.70",
            "precision": "0.20",
            "recall": "0.75",
            "f1": "0.35",
            "auc": "0.80",
        }

        rows = []

        for metric, value in metrics.items():
            rows.append(
                {
                    "metric": metric,
                    "candidate": value,
                    "required_for_demo": required.get(metric, "—"),
                }
            )

        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

        recall = metrics.get("recall")
        if recall is not None and recall < 0.75:
            st.error(
                f"Candidate recall is {recall:.4f}, which is below the required 0.75. "
                "Promotion should be blocked by the checklist."
            )

    json_expander("Raw candidate model", selected_candidate)