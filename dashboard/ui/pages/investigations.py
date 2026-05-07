import pandas as pd
import streamlit as st

from ui.api import ApiClient
from ui.components import (
    clean_checklist_rows,
    clean_metric_rows,
    extract_list,
    flatten_approval_row,
    flatten_investigation_row,
    flatten_job_row,
    hero,
    kpi_card,
    pill,
    safe_get,
    section,
    show_api_error,
)


def render_investigations_page(client: ApiClient) -> None:
    hero(
        "Investigations",
        "Follow each agent investigation from drift alert to final outcome.",
    )

    investigations_result = client.list_investigations()

    if not investigations_result.ok:
        show_api_error(
            "Could not load investigations",
            investigations_result.error,
            investigations_result.data,
        )

        investigation_id = st.text_input("Enter investigation ID manually")
        if investigation_id:
            _render_investigation_detail(client, investigation_id)
        return

    investigations = extract_list(investigations_result.data, "investigations")

    if not investigations:
        st.info("No investigations found yet.")
        return

    rows = [flatten_investigation_row(item) for item in investigations]

    section("All Investigations", "Open, resolved, and failed agent investigations.")
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    investigation_options = [row["id"] for row in rows if row.get("id")]

    selected_id = st.selectbox(
        "Select an investigation",
        investigation_options,
        index=0,
    )

    if selected_id:
        _render_investigation_detail(client, selected_id)


def _render_investigation_detail(client: ApiClient, investigation_id: str) -> None:
    st.divider()

    detail = client.get_investigation_summary(investigation_id)

    if not detail.ok:
        detail = client.get_investigation(investigation_id)

    if not detail.ok:
        show_api_error("Could not load investigation", detail.error, detail.data)
        return

    data = detail.data
    investigation = data.get("investigation", data) if isinstance(data, dict) else {}

    status = investigation.get("status")
    current_step = investigation.get("current_step")
    recommended_action = investigation.get("recommended_action")
    severity = investigation.get("severity")
    summary = investigation.get("summary", "No summary available.")

    section(
        f"Investigation {investigation_id}",
        "Readable summary of the agent decision and final outcome.",
    )

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        kpi_card("Severity", severity or "—", "Drift severity")
    with c2:
        kpi_card("Status", status or "—", "Investigation state")
    with c3:
        kpi_card("Current Step", current_step or "—", "Workflow step")
    with c4:
        kpi_card("Action", recommended_action or "—", "Current recommendation")

    st.markdown(
        f"""
        <div class="soft-card">
            <b>Summary</b><br/>
            <span class="muted">{summary}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    state = investigation.get("state_json") or {}
    candidate = state.get("candidate_model") or {}
    promotion_result = state.get("promotion_result") or investigation.get("result_json") or {}

    if candidate:
        section("Candidate Model", "Created by retraining.")
        c1, c2, c3 = st.columns(3)
        with c1:
            kpi_card("Candidate Version", candidate.get("model_version", "—"), "MLflow version")
        with c2:
            kpi_card("Threshold", candidate.get("selected_threshold", "—"), "Operating threshold")
        with c3:
            kpi_card("Run ID", candidate.get("mlflow_run_id", "—"), "MLflow run")

        metrics = candidate.get("test_metrics") or {}
        if metrics:
            st.dataframe(
                pd.DataFrame(clean_metric_rows(metrics)),
                use_container_width=True,
                hide_index=True,
            )

    if promotion_result:
        section("Promotion Result", "Whether the candidate reached Production.")
        promoted = promotion_result.get("promoted")
        message = promotion_result.get("message", "No promotion message.")

        st.markdown(f"{pill(promoted)} {message}", unsafe_allow_html=True)

        checks = safe_get(promotion_result, "checklist", "checks", default=[])
        if checks:
            st.dataframe(
                pd.DataFrame(clean_checklist_rows(checks)),
                use_container_width=True,
                hide_index=True,
            )

    approvals = extract_list(data, "approvals")
    jobs = extract_list(data, "jobs")

    if approvals:
        section("Approvals")
        st.dataframe(
            pd.DataFrame([flatten_approval_row(item) for item in approvals]),
            use_container_width=True,
            hide_index=True,
        )

    if jobs:
        section("Jobs")
        st.dataframe(
            pd.DataFrame([flatten_job_row(item) for item in jobs]),
            use_container_width=True,
            hide_index=True,
        )