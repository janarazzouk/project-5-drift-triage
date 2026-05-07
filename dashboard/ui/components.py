from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st


def hero(title: str, subtitle: str) -> None:
    st.markdown(
        f"""
        <div class="hero">
            <div class="hero-title">{title}</div>
            <div class="hero-subtitle">{subtitle}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def section(title: str, subtitle: str | None = None) -> None:
    st.markdown(f'<div class="section-title">{title}</div>', unsafe_allow_html=True)
    if subtitle:
        st.markdown(f'<div class="section-subtitle">{subtitle}</div>', unsafe_allow_html=True)


def kpi_card(label: str, value: Any, help_text: str = "") -> None:
    st.markdown(
        f"""
        <div class="kpi-card">
            <div class="kpi-label">{label}</div>
            <div class="kpi-value">{value}</div>
            <div class="kpi-help">{help_text}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def pill(value: Any) -> str:
    text = str(value or "unknown")
    normalized = text.lower()

    if normalized in {"healthy", "ok", "normal", "completed", "resolved", "approved", "passed", "true"}:
        color = "green"
    elif normalized in {"warning", "pending", "waiting_for_approval", "waiting_for_job", "queued"}:
        color = "yellow"
    elif normalized in {"critical", "failed", "blocked", "promotion_blocked", "rejected", "dlq", "false"}:
        color = "red"
    elif normalized in {"running", "processing", "in_progress"}:
        color = "blue"
    elif normalized in {"candidate", "promote_to_production", "retrain"}:
        color = "purple"
    else:
        color = "gray"

    return f'<span class="pill pill-{color}">{text}</span>'


def render_pill(value: Any) -> None:
    st.markdown(pill(value), unsafe_allow_html=True)


def json_expander(title: str, data: Any, expanded: bool = False) -> None:
    with st.expander(title, expanded=expanded):
        st.json(data)


def show_api_error(label: str, error: str | None, data: Any = None) -> None:
    st.warning(f"{label}: {error or 'No data returned.'}")
    if data is not None:
        json_expander("Response details", data)


def extract_list(data: Any, key: str) -> list[dict[str, Any]]:
    if isinstance(data, list):
        return data

    if isinstance(data, dict):
        value = data.get(key)
        if isinstance(value, list):
            return value

        for fallback in ["items", "results", "records", "tracked_jobs", "approvals", "investigations", "jobs"]:
            value = data.get(fallback)
            if isinstance(value, list):
                return value

    return []


def safe_get(data: Any, *keys: str, default: Any = None) -> Any:
    current = data

    for key in keys:
        if not isinstance(current, dict):
            return default

        current = current.get(key)

    return current if current is not None else default


def dataframe(items: list[dict[str, Any]], columns: list[str] | None = None) -> pd.DataFrame:
    if not items:
        return pd.DataFrame(columns=columns or [])

    rows = []

    for item in items:
        if columns:
            rows.append({column: item.get(column) for column in columns})
        else:
            rows.append(item)

    return pd.DataFrame(rows)


def flatten_job_row(job: dict[str, Any]) -> dict[str, Any]:
    result = job.get("result_json") or {}

    return {
        "job_id": job.get("job_id"),
        "type": job.get("job_type"),
        "status": job.get("status"),
        "investigation_id": job.get("investigation_id"),
        "attempts": job.get("attempts"),
        "model_version": result.get("model_version"),
        "completed": result.get("completed"),
        "created_at": job.get("created_at"),
        "finished_at": job.get("finished_at"),
    }


def flatten_investigation_row(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": item.get("id") or item.get("investigation_id"),
        "severity": item.get("severity"),
        "status": item.get("status"),
        "current_step": item.get("current_step"),
        "recommended_action": item.get("recommended_action"),
        "model_version": item.get("model_version"),
        "updated_at": item.get("updated_at"),
    }


def flatten_approval_row(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": item.get("id"),
        "action": item.get("requested_action"),
        "target": item.get("target_environment"),
        "status": item.get("status"),
        "model_version": item.get("model_version"),
        "investigation_id": item.get("investigation_id"),
        "created_at": item.get("created_at"),
    }