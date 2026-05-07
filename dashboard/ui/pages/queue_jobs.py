import pandas as pd
import streamlit as st

from ui.api import ApiClient
from ui.components import (
    extract_list,
    flatten_job_row,
    hero,
    json_expander,
    kpi_card,
    section,
    show_api_error,
)


def render_queue_jobs_page(client: ApiClient) -> None:
    hero(
        "Queue & Jobs",
        "Monitor Redis queue depth, DLQ, worker jobs, retries, and tool results.",
    )

    result = client.get_queue_status()

    if not result.ok:
        show_api_error("Could not load queue status", result.error, result.data)
        return

    data = result.data if isinstance(result.data, dict) else {}
    jobs = extract_list(data, "tracked_jobs")

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        kpi_card("Pending", data.get("pending_count", "—"), data.get("queue_name", "queue"))
    with c2:
        kpi_card("Processing", data.get("processing_count", "—"), "Worker currently handling")
    with c3:
        kpi_card("DLQ", data.get("dlq_count", "—"), "Dead-letter queue")
    with c4:
        kpi_card("Tracked Jobs", len(jobs), "Recent DB-tracked jobs")

    st.divider()

    section("Recent Jobs", "Replay tests, retrains, rollbacks, and failures.")
    st.dataframe(
        pd.DataFrame([flatten_job_row(job) for job in jobs]),
        use_container_width=True,
        hide_index=True,
    )

    if not jobs:
        st.info("No jobs found.")
        return

    job_ids = [job.get("job_id") for job in jobs if job.get("job_id")]
    selected_job_id = st.selectbox("Inspect job", job_ids)

    selected_job = next((job for job in jobs if job.get("job_id") == selected_job_id), None)

    if selected_job:
        st.divider()

        section(f"Job {selected_job_id}", "Payload, result, and worker logs.")

        result_json = selected_job.get("result_json") or {}

        c1, c2, c3 = st.columns(3)
        with c1:
            kpi_card("Type", selected_job.get("job_type", "—"), "Tool type")
        with c2:
            kpi_card("Status", selected_job.get("status", "—"), "Queue state")
        with c3:
            kpi_card("Attempts", selected_job.get("attempts", "—"), f"Max: {selected_job.get('max_attempts', '—')}")

        if selected_job.get("error_message"):
            st.error(selected_job["error_message"])

        if result_json:
            c1, c2, c3 = st.columns(3)
            with c1:
                kpi_card("Completed", result_json.get("completed", "—"), "Worker result")
            with c2:
                kpi_card("Model Version", result_json.get("model_version", "—"), "Retrain output")
            with c3:
                kpi_card("MLflow Run", result_json.get("mlflow_run_id", "—"), "Run ID")

            metrics = result_json.get("test_metrics") or {}
            if metrics:
                st.dataframe(
                    pd.DataFrame(
                        [{"metric": key, "value": value} for key, value in metrics.items()]
                    ),
                    use_container_width=True,
                    hide_index=True,
                )

            stdout = result_json.get("stdout_tail")
            stderr = result_json.get("stderr_tail")

            if stdout:
                with st.expander("stdout tail"):
                    st.code(stdout, language="text")

            if stderr:
                with st.expander("stderr tail"):
                    st.code(stderr, language="text")

        json_expander("Raw job payload", selected_job.get("payload_json"))
        json_expander("Raw job result", selected_job.get("result_json"))
        json_expander("Raw job record", selected_job)