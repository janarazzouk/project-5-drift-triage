import pandas as pd
import streamlit as st

from ui.api import ApiClient
from ui.components import (
    extract_list,
    hero,
    kpi_card,
    render_pill,
    safe_get,
    section,
    show_api_error,
)


def render_drift_monitor_page(client: ApiClient) -> None:
    hero(
        "Drift Monitor",
        "Track drift severity, changed features, and output drift without exposing raw JSON.",
    )

    latest_drift = client.get_latest_drift()

    drift_data = None
    source = "model service"

    if latest_drift.ok and isinstance(latest_drift.data, dict):
        drift_data = latest_drift.data
    else:
        investigations = client.list_investigations()

        if investigations.ok:
            items = extract_list(investigations.data, "investigations")
            recent = items[0] if items else None

            if recent:
                investigation_id = recent.get("id") or recent.get("investigation_id")
                detail = client.get_investigation(investigation_id)

                if detail.ok:
                    drift_data = safe_get(detail.data, "state_json", "drift_report") or safe_get(
                        detail.data,
                        "drift_report",
                    )
                    source = "latest investigation"

    if not drift_data:
        show_api_error(
            "No drift report available",
            latest_drift.error,
            latest_drift.data,
        )
        st.info("Run a drift check or trigger a demo drift event from the Demo Controls page.")
        return

    severity = drift_data.get("severity") or drift_data.get("new_severity") or "unknown"
    overall_score = drift_data.get("overall_score", "—")
    sample_size = drift_data.get("sample_size", "—")
    min_required = drift_data.get("min_required_samples", "—")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        kpi_card("Severity", severity, f"Source: {source}")
    with col2:
        kpi_card("Overall Score", overall_score, "Higher means stronger drift")
    with col3:
        kpi_card("Sample Size", sample_size, "Recent prediction window")
    with col4:
        kpi_card("Minimum Required", min_required, "Reliability threshold")

    render_pill(severity)

    st.divider()

    section(
        "Feature Drift",
        "Features that changed compared with the reference training distribution.",
    )

    features = drift_data.get("features") or []

    if features:
        rows = []

        for feature in features:
            rows.append(
                {
                    "feature": feature.get("feature"),
                    "type": feature.get("kind"),
                    "score": feature.get("score"),
                    "severity": feature.get("severity"),
                    "reason": safe_get(feature, "details", "reason", default=""),
                }
            )

        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.info("No individual feature drift entries were returned.")

    output_drift = drift_data.get("output_drift")

    if output_drift:
        section("Output Drift", "Summary only.")
        output_rows = [
            {
                "type": output_drift.get("kind"),
                "score": output_drift.get("score"),
                "severity": output_drift.get("severity"),
            }
        ]
        st.dataframe(pd.DataFrame(output_rows), use_container_width=True, hide_index=True)