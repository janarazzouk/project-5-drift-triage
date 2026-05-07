import streamlit as st

from ui.api import ApiClient
from ui.config import load_dashboard_config
from ui.pages.demo_controls import render_demo_controls_page
from ui.pages.drift_monitor import render_drift_monitor_page
from ui.pages.human_approvals import render_human_approvals_page
from ui.pages.investigations import render_investigations_page
from ui.pages.overview import render_overview_page
from ui.pages.queue_jobs import render_queue_jobs_page
from ui.pages.registry_promotion import render_registry_promotion_page
from ui.styles import inject_global_styles


st.set_page_config(
    page_title="Drift Triage Co-pilot",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)


def main() -> None:
    inject_global_styles()

    config = load_dashboard_config()
    client = ApiClient(config)

    st.sidebar.markdown(
        """
        <div class="sidebar-title">
            <div class="sidebar-logo">🛡️</div>
            <div>
                <div class="sidebar-name">Drift Triage</div>
                <div class="sidebar-subtitle">Co-pilot Dashboard</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    page = st.sidebar.radio(
        "Navigation",
        [
            "Overview",
            "Drift Monitor",
            "Investigations",
            "Human Approvals",
            "Queue & Jobs",
            "Registry & Promotion",
            "Demo Controls",
        ],
        label_visibility="collapsed",
    )

    st.sidebar.divider()

    if st.sidebar.button("Refresh dashboard", use_container_width=True):
        st.rerun()

    st.sidebar.caption("Connected services")
    st.sidebar.code(
        f"Agent: {config.agent_api_url}\nModel: {config.model_service_api_url}",
        language="text",
    )

    if page == "Overview":
        render_overview_page(client)
    elif page == "Drift Monitor":
        render_drift_monitor_page(client)
    elif page == "Investigations":
        render_investigations_page(client)
    elif page == "Human Approvals":
        render_human_approvals_page(client)
    elif page == "Queue & Jobs":
        render_queue_jobs_page(client)
    elif page == "Registry & Promotion":
        render_registry_promotion_page(client)
    elif page == "Demo Controls":
        render_demo_controls_page(client)


if __name__ == "__main__":
    main()