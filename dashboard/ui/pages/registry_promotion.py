import pandas as pd
import streamlit as st

from ui.api import ApiClient
from ui.components import (
    clean_checklist_rows,
    hero,
    kpi_card,
    section,
    show_api_error,
)


def render_registry_promotion_page(client: ApiClient) -> None:
    hero(
        "Registry & Promotion",
        "See the current model version and the Production safety checklist.",
    )

    registry = client.get_registry()
    checklist = client.get_promotion_checklist()

    col_left, col_right = st.columns([0.8, 1.2])

    with col_left:
        section("Registry", "Current served model version.")

        if registry.ok:
            data = registry.data if isinstance(registry.data, dict) else {}
            version = data.get("model_version", "—")
            kpi_card("Current Version", version, "Served by model service")
        else:
            show_api_error("Registry unavailable", registry.error, registry.data)

    with col_right:
        section("Promotion Checklist", "Programmatic gate before Production.")

        if checklist.ok:
            data = checklist.data if isinstance(checklist.data, dict) else {}
            passed = data.get("passed", "—")
            checks = data.get("checks") or []

            kpi_card("Checklist Passed", passed, "All checks must pass for promotion")

            if checks:
                st.dataframe(
                    pd.DataFrame(clean_checklist_rows(checks)),
                    use_container_width=True,
                    hide_index=True,
                )
        else:
            show_api_error("Promotion checklist unavailable", checklist.error, checklist.data)