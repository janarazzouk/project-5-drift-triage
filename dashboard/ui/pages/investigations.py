import pandas as pd
import streamlit as st

from ui.api import ApiClient
from ui.components import (
    extract_list,
    flatten_investigation_row,
    hero,
    json_expander,
    kpi_card,
    pill,
    safe_get,
    section,
    show_api_error,
)


def render_investigations_page(client: ApiClient) -> None:
    hero(
        "Investigations",
        "Follow the agent story from drift alert to decision, approval, job result, and final outcome.",
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

    investigation_options = [
        row["id"] for row in rows if row.get("id")
    ]

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
        "Readable summary first, raw technical state in expanders below.",
    )

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        kpi_card("Severity", severity or "—", "Drift severity")
    with c2:
        kpi_card("Status", status or "—", "Investigation state")
    with c3:
        kpi_card("Current Step", current_step or "—", "Agent workflow step")
    with c4:
        kpi_card("Recommended Action", recommended_action or "—", "Agent decision")

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
            kpi_card("Candidate Version", candidate.get("model_version", "—"), "MLflow model version")
        with c2:
            kpi_card("Threshold", candidate.get("selected_threshold", "—"), "Operating threshold")
        with c3:
            kpi_card("MLflow Run", candidate.get("mlflow_run_id", "—"), "Training run")

        metrics = candidate.get("test_metrics") or {}
        if metrics:
            st.dataframe(
                pd.DataFrame(
                    [
                        {"metric": key, "value": value}
                        for key, value in metrics.items()
                    ]
                ),
                use_container_width=True,
                hide_index=True,
            )

    if promotion_result:
        section("Promotion Result", "Whether the candidate reached Production.")
        promoted = promotion_result.get("promoted")
        message = promotion_result.get("message", "No promotion message.")
        st.markdown(f"{pill(promoted)} {message}", unsafe_allow_html=True)

        checklist = safe_get(promotion_result, "checklist", "checks", default=[])
        if checklist:
            st.dataframe(pd.DataFrame(checklist), use_container_width=True, hide_index=True)

    messages = extract_list(data, "messages")
    if messages:
        section("Timeline", "Agent messages, approvals, tool results, and final outcome.")
        for message in messages:
            role = message.get("role")
            node = message.get("node_name")
            content = message.get("content")
            created_at = message.get("created_at")
            st.markdown(
                f"""
                <div class="soft-card">
                    <b>{node}</b> · <span class="muted">{role}</span> · <span class="muted">{created_at}</span><br/>
                    {content}
                </div>
                """,
                unsafe_allow_html=True,
            )

    jobs = extract_list(data, "jobs")
    approvals = extract_list(data, "approvals")

    if approvals:
        section("Approvals")
        st.dataframe(pd.DataFrame(approvals), use_container_width=True, hide_index=True)

    if jobs:
        section("Jobs")
        st.dataframe(pd.DataFrame(jobs), use_container_width=True, hide_index=True)

    json_expander("Raw investigation summary", data)