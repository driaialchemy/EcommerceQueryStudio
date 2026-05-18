"""Tests for Stage 6: runtime pipeline (router, executor, pipeline)."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.runtime.executor import execute_sql
from src.runtime.router import route_question
from src.runtime.pipeline import answer_question

_DB_PATH = Path("data/processed/maven_fuzzy_factory.duckdb")

# ---------------------------------------------------------------------------
# Router: supported templates
# ---------------------------------------------------------------------------


def test_route_conversion_by_channel():
    r = route_question("What is the conversion rate by channel?")
    assert r["route_type"] == "template"
    assert r["template_id"] == "conversion_by_channel"


def test_route_conversion_by_channel_via_source():
    r = route_question("Show me conversion rate by utm_source")
    assert r["route_type"] == "template"
    assert r["template_id"] == "conversion_by_channel"


def test_route_conversion_by_device():
    r = route_question("What is the conversion rate by device type?")
    assert r["route_type"] == "template"
    assert r["template_id"] == "conversion_by_device"


def test_route_revenue_by_campaign():
    r = route_question("Show revenue by campaign")
    assert r["route_type"] == "template"
    assert r["template_id"] == "revenue_by_campaign"


def test_route_refund_by_product():
    r = route_question("What is the refund rate by product?")
    assert r["route_type"] == "template"
    assert r["template_id"] == "refund_rate_by_product"


def test_route_refund_by_item():
    r = route_question("Show refund amounts per item")
    assert r["route_type"] == "template"
    assert r["template_id"] == "refund_rate_by_product"


def test_route_monthly_revenue_trend():
    r = route_question("Show monthly revenue trend")
    assert r["route_type"] == "template"
    assert r["template_id"] == "monthly_revenue_trend"


def test_route_monthly_revenue_keyword():
    r = route_question("What is the monthly revenue over time?")
    assert r["route_type"] == "template"
    assert r["template_id"] == "monthly_revenue_trend"


# ---------------------------------------------------------------------------
# Router: defaults
# ---------------------------------------------------------------------------


def test_route_injects_default_dates():
    r = route_question("Show conversion rate by channel")
    params = r["extracted_parameters"]
    assert params["start_date"] == "2012-01-01"
    assert params["end_date"] == "2015-12-31"


# ---------------------------------------------------------------------------
# Router: ambiguity and unsupported
# ---------------------------------------------------------------------------


def test_route_best_channel_returns_clarify():
    r = route_question("Which is the best channel?")
    assert r["route_type"] == "clarify"


def test_route_most_profitable_returns_clarify():
    r = route_question("What is the most profitable option?")
    assert r["route_type"] == "clarify"


def test_route_performance_without_metric_returns_clarify():
    r = route_question("What is the performance of my campaigns?")
    assert r["route_type"] == "clarify"


def test_route_unsupported_question():
    r = route_question("How many employees do we have?")
    assert r["route_type"] == "unsupported"
    assert r["template_id"] is None


def test_route_unsupported_returns_reason():
    r = route_question("What is the weather today?")
    assert r["route_type"] == "unsupported"
    assert len(r["reason"]) > 0


# ---------------------------------------------------------------------------
# Executor: safety checks
# ---------------------------------------------------------------------------


def test_executor_rejects_non_select_drop():
    with pytest.raises(ValueError, match="Only SELECT"):
        execute_sql("DROP TABLE orders", db_path=_DB_PATH if _DB_PATH.exists() else Path("nonexistent.duckdb"))


def test_executor_rejects_non_select_insert():
    with pytest.raises(ValueError, match="Only SELECT"):
        execute_sql("INSERT INTO orders VALUES (1)", db_path=_DB_PATH if _DB_PATH.exists() else Path("nonexistent.duckdb"))


def test_executor_rejects_non_select_update():
    with pytest.raises(ValueError, match="Only SELECT"):
        execute_sql("UPDATE orders SET price_usd = 0", db_path=_DB_PATH if _DB_PATH.exists() else Path("nonexistent.duckdb"))


def test_executor_missing_db_raises_file_not_found():
    with pytest.raises(FileNotFoundError, match="not found"):
        execute_sql("SELECT 1", db_path=Path("does_not_exist.duckdb"))


# ---------------------------------------------------------------------------
# Pipeline: non-executing paths
# ---------------------------------------------------------------------------


def test_pipeline_clarify_returns_clarify_status():
    result = answer_question("Which is the best channel?")
    assert result["status"] == "clarify"
    assert result["sql"] is None
    assert result["rows"] is None


def test_pipeline_unsupported_returns_unsupported_status():
    result = answer_question("How many employees do we have?")
    assert result["status"] == "unsupported"
    assert result["sql"] is None
    assert result["rows"] is None


def test_pipeline_clarify_does_not_execute_sql(monkeypatch):
    executed = []

    def _mock_execute(sql, db_path=None):
        executed.append(sql)
        return []

    monkeypatch.setattr("src.runtime.pipeline.execute_sql", _mock_execute)
    answer_question("Which is the best channel?")
    assert executed == [], "SQL must not be executed for clarify route"


def test_pipeline_unsupported_does_not_execute_sql(monkeypatch):
    executed = []

    def _mock_execute(sql, db_path=None):
        executed.append(sql)
        return []

    monkeypatch.setattr("src.runtime.pipeline.execute_sql", _mock_execute)
    answer_question("How many employees do we have?")
    assert executed == [], "SQL must not be executed for unsupported route"


def test_pipeline_clarify_validation_status_not_applicable():
    result = answer_question("Which is the best channel?")
    assert result["validation_status"] == "not_applicable"
    assert result["validation"] is None


def test_pipeline_unsupported_validation_status_not_applicable():
    result = answer_question("How many employees do we have?")
    assert result["validation_status"] == "not_applicable"
    assert result["validation"] is None


def test_pipeline_template_answer_includes_validation_status(monkeypatch):
    monkeypatch.setattr("src.runtime.pipeline.render_template_sql", lambda tid, params, **kw: "SELECT 1")
    monkeypatch.setattr("src.runtime.pipeline.execute_sql", lambda sql, db_path=None: [])
    result = answer_question("Show conversion rate by channel")
    assert result["validation_status"] in ("passed", "failed")


def test_pipeline_template_answer_includes_validation_object(monkeypatch):
    monkeypatch.setattr("src.runtime.pipeline.render_template_sql", lambda tid, params, **kw: "SELECT 1")
    monkeypatch.setattr("src.runtime.pipeline.execute_sql", lambda sql, db_path=None: [])
    result = answer_question("Show conversion rate by channel")
    assert isinstance(result["validation"], dict)
    assert "status" in result["validation"]
    assert "checks" in result["validation"]


# ---------------------------------------------------------------------------
# Pipeline: user parameters override defaults
# ---------------------------------------------------------------------------


def test_pipeline_user_params_override_defaults(monkeypatch):
    captured = {}

    def _mock_render(template_id, parameters, **kwargs):
        captured["parameters"] = parameters
        return "SELECT 1"

    def _mock_execute(sql, db_path=None):
        return []

    monkeypatch.setattr("src.runtime.pipeline.render_template_sql", _mock_render)
    monkeypatch.setattr("src.runtime.pipeline.execute_sql", _mock_execute)

    answer_question(
        "Show conversion rate by channel",
        parameters={"start_date": "2014-01-01", "end_date": "2014-12-31"},
    )
    assert captured["parameters"]["start_date"] == "2014-01-01"
    assert captured["parameters"]["end_date"] == "2014-12-31"


# ---------------------------------------------------------------------------
# Optional: live DuckDB execution test
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _DB_PATH.exists(), reason="DuckDB file not present")
def test_pipeline_executes_and_returns_rows_for_conversion_by_channel():
    result = answer_question("What is the conversion rate by channel?")
    assert result["status"] == "ok"
    assert result["template_id"] == "conversion_by_channel"
    assert isinstance(result["rows"], list)
    assert result["row_count"] == len(result["rows"])
    assert result["sql"] is not None
    assert "{start_date}" not in result["sql"]
    for row in result["rows"]:
        assert "sessions" in row
        assert "orders" in row
        assert row["sessions"] >= row["orders"] >= 0


@pytest.mark.skipif(not _DB_PATH.exists(), reason="DuckDB file not present")
def test_pipeline_executes_monthly_revenue_trend():
    result = answer_question("Show monthly revenue trend")
    assert result["status"] == "ok"
    assert result["template_id"] == "monthly_revenue_trend"
    assert isinstance(result["rows"], list)
    assert result["row_count"] > 0
