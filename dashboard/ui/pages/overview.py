import streamlit as st

from ui.api import ApiClient
from ui.components import (
    dataframe,
    extract_list,
    flatten_approval_row,
    flatten_job_row,
    hero,
    kpi_card,
    section,
    show_api_error,
)


def render_overview_page(client: ApiClient) -> None:
    hero(
        "System Overview",
        "A simple control center for drift, agent decisions, human approvals, and worker jobs.",
    )

    agent_health = client.health_agent()
    model_health = client.health_model_service()
    queue = client.get_queue_status()
    pending_approvals = client.get_pending_approvals()

    queue_data = queue.data if queue.ok and isinstance(queue.data, dict) else {}
    approvals = extract_list(pending_approvals.data, "approvals") if pending_approvals.ok else []

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        kpi_card(
            "Agent",
            "Healthy" if agent_health.ok else "Down",
            "Investigation service",
        )

    with col2:
        kpi_card(
            "Model Service",
            "Healthy" if model_health.ok else "Down",
            "Prediction and drift service",
        )

    with col3:
        kpi_card(
            "Queue Pending",
            queue_data.get("pending_count", "—"),
            f"Processing: {queue_data.get('processing_count', '—')}",
        )

    with col4:
        kpi_card(
            "Pending Approvals",
            len(approvals),
            "Human actions waiting",
        )

    st.divider()

    col_left, col_right = st.columns([1.1, 1])

    with col_left:
        section(
            "Pending Human Actions",
            "Approvals that need a person before the system can continue.",
        )

        if approvals:
            st.dataframe(
                dataframe([flatten_approval_row(item) for item in approvals]),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.success("No pending approvals right now.")

    with col_right:
        section(
            "Queue Health",
            "Current Redis queue and worker status.",
        )

        if queue.ok:
            k1, k2, k3 = st.columns(3)
            with k1:
                kpi_card("Pending", queue_data.get("pending_count", "—"))
            with k2:
                kpi_card("Processing", queue_data.get("processing_count", "—"))
            with k3:
                kpi_card("DLQ", queue_data.get("dlq_count", "—"))
        else:
            show_api_error("Queue status unavailable", queue.error, queue.data)

    st.divider()

    section(
        "Latest Jobs",
        "Recent replay, retrain, and rollback worker jobs.",
    )

    if queue.ok:
        jobs = extract_list(queue.data, "tracked_jobs")
        st.dataframe(
            dataframe([flatten_job_row(job) for job in jobs[:10]]),
            use_container_width=True,
            hide_index=True,
        )
    else:
        show_api_error("Queue status unavailable", queue.error, queue.data)