import pandas as pd
import streamlit as st

from ui.api import ApiClient
from ui.components import (
    extract_list,
    flatten_approval_row,
    hero,
    kpi_card,
    pill,
    section,
    show_api_error,
)


def render_human_approvals_page(client: ApiClient) -> None:
    hero(
        "Human Approval Inbox",
        "Approve or reject retrain, rollback, and Production promotion requests.",
    )

    pending_result = client.get_pending_approvals()

    if not pending_result.ok:
        show_api_error("Could not load pending approvals", pending_result.error, pending_result.data)
        return

    approvals = extract_list(pending_result.data, "approvals")

    c1, c2, c3 = st.columns(3)
    with c1:
        kpi_card("Pending Approvals", len(approvals), "Waiting for human action")
    with c2:
        retrain_count = len([a for a in approvals if a.get("requested_action") == "retrain"])
        kpi_card("Retrain Requests", retrain_count, "Creates candidate model")
    with c3:
        promotion_count = len([a for a in approvals if a.get("requested_action") == "promote_to_production"])
        kpi_card("Promotion Requests", promotion_count, "Checklist still decides")

    st.divider()

    if not approvals:
        st.success("No approvals pending.")
    else:
        section(
            "Pending Actions",
            "Each card explains the action and lets a human approve or reject it.",
        )

        for approval in approvals:
            _approval_card(client, approval)

    st.divider()

    section("Approval History", "Recent approvals and rejections.")
    history = client.get_all_approvals()

    if history.ok:
        history_items = extract_list(history.data, "approvals")
        st.dataframe(
            pd.DataFrame([flatten_approval_row(item) for item in history_items]),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("Approval history endpoint is unavailable. Pending approvals still work.")


def _approval_card(client: ApiClient, approval: dict) -> None:
    approval_id = approval.get("id")
    action = approval.get("requested_action")
    target = approval.get("target_environment")
    model_name = approval.get("model_name")
    model_version = approval.get("model_version")
    investigation_id = approval.get("investigation_id")
    reason = approval.get("reason", "No reason provided.")

    st.markdown(
        f"""
        <div class="approval-card">
            <div style="display:flex; justify-content:space-between; gap:1rem; align-items:center;">
                <div>
                    <div style="font-size:1.1rem; font-weight:850;">{action}</div>
                    <div class="muted small">Approval ID: {approval_id}</div>
                </div>
                <div>{pill(approval.get("status"))}</div>
            </div>
            <hr style="border:none; border-top:1px solid #E2E8F0; margin:0.8rem 0;" />
            <b>Model:</b> {model_name}<br/>
            <b>Version:</b> {model_version}<br/>
            <b>Target:</b> {target}<br/>
            <b>Investigation:</b> {investigation_id}<br/><br/>
            <span class="muted">{reason}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if action == "retrain":
        st.info(
            "This queues a Redis retrain job. It creates a candidate model, not a Production model."
        )
    elif action == "promote_to_production":
        st.warning(
            "This asks the model service to run the promotion checklist. "
            "The checklist can still block promotion."
        )
    elif action == "rollback_production":
        st.error(
            "This action can affect Production. Approve only if rollback is intended."
        )

    col1, col2 = st.columns(2)

    with col1:
        with st.form(f"approve_{approval_id}"):
            approved_by = st.text_input(
                "Approved by",
                value="janarazzouk",
                key=f"approved_by_{approval_id}",
            )
            note = st.text_area("Approval note", value="", key=f"note_{approval_id}")
            submitted = st.form_submit_button("Approve", use_container_width=True)

            if submitted:
                result = client.approve(approval_id, approved_by, note)

                if result.ok:
                    message = result.data.get("message") if isinstance(result.data, dict) else "Approval submitted."
                    st.success(message)
                    st.rerun()
                else:
                    show_api_error("Approval failed", result.error, result.data)

    with col2:
        with st.form(f"reject_{approval_id}"):
            rejected_by = st.text_input(
                "Rejected by",
                value="janarazzouk",
                key=f"rejected_by_{approval_id}",
            )
            rejection_reason = st.text_area(
                "Rejection reason",
                value="Not approved for this demo.",
                key=f"reject_reason_{approval_id}",
            )
            submitted = st.form_submit_button("Reject", use_container_width=True)

            if submitted:
                result = client.reject(approval_id, rejected_by, rejection_reason)

                if result.ok:
                    st.success("Approval rejected.")
                    st.rerun()
                else:
                    show_api_error("Rejection failed", result.error, result.data)