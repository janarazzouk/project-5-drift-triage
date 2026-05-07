import streamlit as st

from ui.api import ApiClient
from ui.components import (
    dataframe,
    extract_list,
    flatten_approval_row,
    flatten_job_row,
    hero,
    json_expander,
    kpi_card,
    safe_get,
    section,
    show_api_error,
)


def render_overview_page(client: ApiClient) -> None:
    hero(
        "System Overview",
        "A simple control center for drift, agent decisions, approvals, queue jobs, and model safety.",
    )

    agent_health = client.health_agent()
    model_health = client.health_model_service()
    queue = client.get_queue_status()
    pending_approvals = client.get_pending_approvals()
    registry = client.get_registry()

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        kpi_card(
            "Agent",
            "Healthy" if agent_health.ok else "Down",
            "LangGraph investigation service",
        )

    with col2:
        kpi_card(
            "Model Service",
            "Healthy" if model_health.ok else "Down",
            "Prediction, drift, registry, promotion",
        )

    queue_data = queue.data if queue.ok and isinstance(queue.data, dict) else {}
    with col3:
        kpi_card(
            "Queue Pending",
            queue_data.get("pending_count", "—"),
            f"Processing: {queue_data.get('processing_count', '—')}",
        )

    approvals = extract_list(pending_approvals.data, "approvals") if pending_approvals.ok else []
    with col4:
        kpi_card(
            "Pending Approvals",
            len(approvals),
            "Human-in-the-loop actions",
        )

    st.divider()

    col_left, col_right = st.columns([1.2, 1])

    with col_left:
        section(
            "What needs attention?",
            "Pending approvals and blocked/failed jobs appear here first.",
        )

        if approvals:
            st.dataframe(
                dataframe([flatten_approval_row(item) for item in approvals]),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.success("No pending approvals right now.")

        if queue.ok:
            jobs = extract_list(queue.data, "tracked_jobs")
            failed_jobs = [
                job for job in jobs if str(job.get("status")).lower() in {"failed", "dlq"}
            ]

            if failed_jobs:
                st.warning("Some jobs need attention.")
                st.dataframe(
                    dataframe([flatten_job_row(job) for job in failed_jobs]),
                    use_container_width=True,
                    hide_index=True,
                )
            else:
                st.info("No failed or DLQ jobs in the latest queue view.")
        else:
            show_api_error("Queue status unavailable", queue.error, queue.data)

    with col_right:
        section(
            "Current Registry Snapshot",
            "The currently served model and registry state from the model service.",
        )

        if registry.ok:
            model_name = safe_get(registry.data, "model_name", default="—")
            model_version = safe_get(registry.data, "model_version", default="—")
            stage = safe_get(registry.data, "stage", default=safe_get(registry.data, "environment", default="—"))
            threshold = safe_get(registry.data, "selected_threshold", default="—")

            k1, k2 = st.columns(2)
            with k1:
                kpi_card("Model", model_name, "Registry model name")
            with k2:
                kpi_card("Version", model_version, f"Stage: {stage}")

            kpi_card("Operating Threshold", threshold, "Used for class prediction")
            json_expander("Raw registry response", registry.data)
        else:
            show_api_error("Registry unavailable", registry.error, registry.data)

    st.divider()

    section(
        "Latest Queue Activity",
        "Recent replay, retrain, and rollback jobs.",
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