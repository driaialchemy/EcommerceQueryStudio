"""Streamlit dashboard for the governed Maven Fuzzy Factory analytics runtime."""

from __future__ import annotations

import sys
import os
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from src.audit.audit_logger import DEFAULT_AUDIT_PATH
from src.ingestion.load_csvs import DEFAULT_RAW_DIR, REQUIRED_CSVS, load_csvs_to_duckdb
from src.runtime.executor import DEFAULT_DB_PATH
from src.runtime.pipeline import answer_question
from src.semantic_layer.schema_registry import build_schema_registry
from src.templates.template_loader import get_template


DEFAULT_START_DATE = date(2012, 1, 1)
DEFAULT_END_DATE = date(2015, 12, 31)

TEMPLATE_OPTIONS: dict[str, dict[str, str]] = {
    "Conversion by channel": {
        "template_id": "conversion_by_channel",
        "question": "What is the conversion rate by channel?",
    },
    "Conversion by device": {
        "template_id": "conversion_by_device",
        "question": "What is the conversion rate by device type?",
    },
    "Revenue by campaign": {
        "template_id": "revenue_by_campaign",
        "question": "What is revenue by campaign?",
    },
    "Refund rate by product": {
        "template_id": "refund_rate_by_product",
        "question": "What is the refund rate by product?",
    },
    "Monthly revenue trend": {
        "template_id": "monthly_revenue_trend",
        "question": "What is the monthly revenue trend?",
    },
}

_TEMPLATE_LABELS_BY_ID = {
    option["template_id"]: label for label, option in TEMPLATE_OPTIONS.items()
}


def _fmt_count(value: Any) -> str:
    if pd.isna(value):
        return "0"
    return f"{float(value):,.0f}"


def _fmt_money(value: Any) -> str:
    if pd.isna(value):
        return "$0"
    return f"${float(value):,.0f}"


def _fmt_rate(value: Any) -> str:
    if pd.isna(value):
        return "0.00%"
    return f"{float(value) * 100:.2f}%"


def _build_parameters(start_date: date, end_date: date) -> dict[str, str]:
    return {"start_date": start_date.isoformat(), "end_date": end_date.isoformat()}


def _raw_file_status(raw_dir: Path = DEFAULT_RAW_DIR) -> pd.DataFrame:
    rows = []
    for filename in REQUIRED_CSVS:
        path = raw_dir / filename
        rows.append(
            {
                "file": filename,
                "present": path.exists(),
                "size_mb": round(path.stat().st_size / 1_000_000, 2) if path.exists() else 0,
            }
        )
    return pd.DataFrame(rows)


@st.cache_data(ttl=30)
def _schema_summary(db_path_text: str) -> pd.DataFrame:
    registry = build_schema_registry(Path(db_path_text))
    rows = []
    for table_name, entry in registry.items():
        rows.append(
            {
                "table": table_name,
                "grain": entry.get("grain", ""),
                "rows": entry.get("row_count", 0),
                "columns": len(entry.get("columns", [])),
            }
        )
    return pd.DataFrame(rows).sort_values("table").reset_index(drop=True)


def _response_frame(response: dict) -> pd.DataFrame:
    rows = response.get("rows") or []
    if not rows:
        return pd.DataFrame()
    frame = pd.DataFrame(rows)
    for column in frame.columns:
        if "date" in column.lower() or "month" in column.lower():
            frame[column] = pd.to_datetime(frame[column], errors="ignore")
    return frame


def _channel_label(frame: pd.DataFrame) -> pd.Series:
    source = frame.get("utm_source", pd.Series([""] * len(frame))).fillna("direct")
    campaign = frame.get("utm_campaign", pd.Series([""] * len(frame))).fillna("none")
    return source.astype(str) + " / " + campaign.astype(str)


def _show_metric_strip(template_id: str, frame: pd.DataFrame) -> None:
    if frame.empty:
        st.info("No rows returned for the selected question and date range.")
        return

    cols = st.columns(4)

    if template_id in {"conversion_by_channel", "conversion_by_device"}:
        sessions = frame["sessions"].sum()
        orders = frame["orders"].sum()
        conversion = orders / sessions if sessions else 0
        top_row = frame.sort_values("conversion_rate", ascending=False).iloc[0]
        top_label = top_row.get("device_type", None)
        if top_label is None:
            top_label = "top channel"
        cols[0].metric("Sessions", _fmt_count(sessions))
        cols[1].metric("Orders", _fmt_count(orders))
        cols[2].metric("Overall conversion", _fmt_rate(conversion))
        cols[3].metric(str(top_label), _fmt_rate(top_row["conversion_rate"]))
        return

    if template_id in {"revenue_by_campaign", "monthly_revenue_trend"}:
        orders = frame["orders"].sum()
        revenue = frame["gross_order_revenue"].sum()
        aov = revenue / orders if orders else 0
        cols[0].metric("Orders", _fmt_count(orders))
        cols[1].metric("Gross revenue", _fmt_money(revenue))
        cols[2].metric("Average order value", _fmt_money(aov))
        cols[3].metric("Rows", _fmt_count(len(frame)))
        return

    if template_id == "refund_rate_by_product":
        items = frame["items_sold"].sum()
        refunds = frame["refunded_items"].sum()
        refund_amount = frame["refund_amount"].sum()
        refund_rate = refunds / items if items else 0
        cols[0].metric("Items sold", _fmt_count(items))
        cols[1].metric("Refunded items", _fmt_count(refunds))
        cols[2].metric("Refund rate", _fmt_rate(refund_rate))
        cols[3].metric("Refund amount", _fmt_money(refund_amount))


def _show_chart(template_id: str, frame: pd.DataFrame) -> None:
    if frame.empty:
        return

    if template_id == "conversion_by_channel":
        chart = frame.copy()
        chart["channel"] = _channel_label(chart)
        chart["conversion_pct"] = chart["conversion_rate"] * 100
        chart = chart.sort_values("sessions", ascending=False).head(15)
        st.bar_chart(chart, x="channel", y="conversion_pct", width="stretch")
        return

    if template_id == "conversion_by_device":
        chart = frame.copy()
        chart["conversion_pct"] = chart["conversion_rate"] * 100
        st.bar_chart(chart, x="device_type", y="conversion_pct", width="stretch")
        return

    if template_id == "revenue_by_campaign":
        chart = frame.copy()
        chart["campaign"] = _channel_label(chart)
        chart = chart.sort_values("gross_order_revenue", ascending=False).head(15)
        st.bar_chart(chart, x="campaign", y="gross_order_revenue", width="stretch")
        return

    if template_id == "refund_rate_by_product":
        chart = frame.copy()
        chart["refund_pct"] = chart["refund_rate"] * 100
        st.bar_chart(chart, x="product_name", y="refund_pct", width="stretch")
        return

    if template_id == "monthly_revenue_trend":
        chart = frame.copy()
        chart["month"] = pd.to_datetime(chart["month"], errors="coerce")
        left, right = st.columns(2)
        with left:
            st.line_chart(chart, x="month", y="gross_order_revenue", width="stretch")
        with right:
            st.line_chart(chart, x="month", y="orders", width="stretch")


def _show_governance(response: dict) -> None:
    explanation = response.get("explanation") or {}
    validation = response.get("validation") or {}

    status_cols = st.columns(4)
    status_cols[0].metric("Status", str(response.get("status", "unknown")))
    status_cols[1].metric("Template", str(response.get("template_id") or "none"))
    status_cols[2].metric("Validation", str(response.get("validation_status", "unknown")))
    status_cols[3].metric("Rows", _fmt_count(response.get("row_count") or 0))

    st.write(explanation.get("summary", ""))
    st.write(explanation.get("method", ""))

    checks = validation.get("checks") or []
    if checks:
        st.dataframe(pd.DataFrame(checks), width="stretch", hide_index=True)

    with st.expander("Assumptions"):
        assumptions = response.get("assumptions") or []
        if assumptions:
            for assumption in assumptions:
                st.write(f"- {assumption}")
        else:
            st.write("No template assumptions were returned.")

    with st.expander("Rendered SQL"):
        st.code(response.get("sql") or "No SQL was executed.", language="sql")

    with st.expander("Audit"):
        if response.get("audit_logged"):
            st.write(f"Logged to `{response.get('audit_path')}`")
        else:
            st.warning(response.get("audit_error") or "Audit event was not written.")


def _run_analysis(question: str, parameters: dict[str, str]) -> dict:
    return answer_question(
        question=question,
        parameters=parameters,
        db_path=DEFAULT_DB_PATH,
        audit_path=DEFAULT_AUDIT_PATH,
    )


def main() -> None:
    st.set_page_config(
        page_title="Maven Fuzzy Factory Analytics",
        page_icon=None,
        layout="wide",
    )

    st.title("Maven Fuzzy Factory Analytics")

    db_exists = DEFAULT_DB_PATH.exists()
    raw_status = _raw_file_status()
    raw_complete = bool(raw_status["present"].all())

    status_left, status_mid, status_right = st.columns(3)
    status_left.metric("DuckDB", "Ready" if db_exists else "Missing")
    status_mid.metric("Raw CSVs", "Complete" if raw_complete else "Incomplete")
    status_right.metric("Approved Templates", _fmt_count(len(TEMPLATE_OPTIONS)))

    if not db_exists and raw_complete:
        if st.button("Build DuckDB", type="primary"):
            with st.spinner("Loading CSVs into DuckDB..."):
                load_csvs_to_duckdb(raw_dir=DEFAULT_RAW_DIR, db_path=DEFAULT_DB_PATH)
                _schema_summary.clear()
            st.rerun()

    with st.expander("Data Status", expanded=not db_exists):
        st.dataframe(raw_status, width="stretch", hide_index=True)
        if db_exists:
            try:
                st.dataframe(
                    _schema_summary(str(DEFAULT_DB_PATH)),
                    width="stretch",
                    hide_index=True,
                )
            except Exception as exc:  # noqa: BLE001
                st.warning(f"Schema summary unavailable: {exc}")

    st.divider()

    control_left, control_right = st.columns([1, 2])
    with control_left:
        mode = st.radio(
            "Question mode",
            ["Guided template", "Custom governed question"],
            horizontal=False,
        )
        selected_label = st.selectbox("Template", list(TEMPLATE_OPTIONS.keys()))
        start_date = st.date_input("Start date", DEFAULT_START_DATE)
        end_date = st.date_input("End date exclusive", DEFAULT_END_DATE)
        run_clicked = st.button("Run Analysis", type="primary", width="stretch")

    option = TEMPLATE_OPTIONS[selected_label]
    guided_question = option["question"]

    with control_right:
        if mode == "Custom governed question":
            question = st.text_area("Question", guided_question, height=104)
        else:
            question = guided_question
            st.text_area("Question", question, height=104, disabled=True)

        template = get_template(option["template_id"])
        st.caption(template["business_question"])
        st.write(template["description"])

    if "last_response" not in st.session_state and db_exists:
        try:
            st.session_state["last_response"] = _run_analysis(
                guided_question,
                _build_parameters(start_date, end_date),
            )
        except Exception as exc:  # noqa: BLE001
            st.session_state["last_response"] = {"status": "error", "reason": str(exc)}

    if run_clicked:
        if not db_exists:
            st.error("DuckDB database is missing.")
        elif start_date >= end_date:
            st.error("Start date must be before end date.")
        else:
            with st.spinner("Running governed analytics pipeline..."):
                try:
                    st.session_state["last_response"] = _run_analysis(
                        question,
                        _build_parameters(start_date, end_date),
                    )
                except Exception as exc:  # noqa: BLE001
                    st.session_state["last_response"] = {
                        "status": "error",
                        "route_type": "error",
                        "template_id": None,
                        "parameters": _build_parameters(start_date, end_date),
                        "sql": None,
                        "row_count": None,
                        "rows": None,
                        "assumptions": [],
                        "validation_status": "error",
                        "validation": None,
                        "reason": str(exc),
                        "explanation": {"summary": str(exc), "method": "Execution failed."},
                        "audit_logged": False,
                    }

    response = st.session_state.get("last_response")
    if not response:
        return

    st.divider()

    if response.get("status") != "ok":
        st.warning(response.get("reason") or response.get("explanation", {}).get("summary", "No result."))
        _show_governance(response)
        return

    frame = _response_frame(response)
    template_id = str(response.get("template_id"))

    st.subheader(_TEMPLATE_LABELS_BY_ID.get(template_id, "Analysis Result"))
    _show_metric_strip(template_id, frame)
    _show_chart(template_id, frame)

    st.subheader("Results")
    st.dataframe(frame, width="stretch", hide_index=True)

    st.subheader("Governance")
    _show_governance(response)


if __name__ == "__main__":
    main()
