import streamlit as st


def inject_global_styles() -> None:
    st.markdown(
        """
        <style>
        :root {
            --bg: #F8FAFC;
            --card: #FFFFFF;
            --border: #E2E8F0;
            --text: #0F172A;
            --muted: #64748B;
            --blue: #2563EB;
            --green: #16A34A;
            --yellow: #D97706;
            --red: #DC2626;
            --purple: #7C3AED;
        }

        .block-container {
            padding-top: 1.6rem;
            padding-bottom: 3rem;
        }

        .sidebar-title {
            display: flex;
            gap: 0.75rem;
            align-items: center;
            padding: 0.75rem 0.25rem 1.2rem 0.25rem;
        }

        .sidebar-logo {
            width: 42px;
            height: 42px;
            border-radius: 14px;
            background: linear-gradient(135deg, #2563EB, #7C3AED);
            color: white;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.4rem;
        }

        .sidebar-name {
            font-weight: 800;
            font-size: 1.05rem;
            color: #0F172A;
            line-height: 1.1;
        }

        .sidebar-subtitle {
            color: #64748B;
            font-size: 0.78rem;
        }

        .hero {
            padding: 1.35rem 1.5rem;
            border-radius: 24px;
            background: linear-gradient(135deg, #EFF6FF, #F5F3FF);
            border: 1px solid #DBEAFE;
            margin-bottom: 1.2rem;
        }

        .hero-title {
            font-size: 2rem;
            font-weight: 850;
            color: #0F172A;
            margin-bottom: 0.25rem;
        }

        .hero-subtitle {
            color: #475569;
            font-size: 1rem;
        }

        .kpi-card {
            background: white;
            border: 1px solid #E2E8F0;
            border-radius: 22px;
            padding: 1rem 1.1rem;
            box-shadow: 0 10px 30px rgba(15, 23, 42, 0.04);
            min-height: 118px;
        }

        .kpi-label {
            color: #64748B;
            font-size: 0.82rem;
            font-weight: 650;
            margin-bottom: 0.55rem;
        }

        .kpi-value {
            font-size: 1.65rem;
            font-weight: 850;
            color: #0F172A;
            line-height: 1.1;
        }

        .kpi-help {
            color: #64748B;
            font-size: 0.78rem;
            margin-top: 0.45rem;
        }

        .soft-card {
            background: white;
            border: 1px solid #E2E8F0;
            border-radius: 22px;
            padding: 1rem 1.1rem;
            box-shadow: 0 10px 30px rgba(15, 23, 42, 0.04);
            margin-bottom: 1rem;
        }

        .section-title {
            font-size: 1.35rem;
            font-weight: 800;
            color: #0F172A;
            margin-top: 0.25rem;
            margin-bottom: 0.2rem;
        }

        .section-subtitle {
            color: #64748B;
            margin-bottom: 1rem;
        }

        .pill {
            display: inline-flex;
            align-items: center;
            gap: 0.35rem;
            border-radius: 999px;
            padding: 0.22rem 0.65rem;
            font-size: 0.78rem;
            font-weight: 750;
            border: 1px solid transparent;
        }

        .pill-green {
            background: #DCFCE7;
            color: #166534;
            border-color: #BBF7D0;
        }

        .pill-yellow {
            background: #FEF3C7;
            color: #92400E;
            border-color: #FDE68A;
        }

        .pill-red {
            background: #FEE2E2;
            color: #991B1B;
            border-color: #FECACA;
        }

        .pill-blue {
            background: #DBEAFE;
            color: #1D4ED8;
            border-color: #BFDBFE;
        }

        .pill-purple {
            background: #EDE9FE;
            color: #6D28D9;
            border-color: #DDD6FE;
        }

        .pill-gray {
            background: #F1F5F9;
            color: #475569;
            border-color: #E2E8F0;
        }

        .approval-card {
            border: 1px solid #E2E8F0;
            border-radius: 24px;
            background: #FFFFFF;
            padding: 1.1rem;
            margin-bottom: 1rem;
            box-shadow: 0 10px 30px rgba(15, 23, 42, 0.04);
        }

        .muted {
            color: #64748B;
        }

        .small {
            font-size: 0.86rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )