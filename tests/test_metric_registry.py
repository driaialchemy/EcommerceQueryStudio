"""Tests for the semantic metric registry."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
import yaml

from src.semantic_layer.metric_registry import (
    DEFAULT_METRICS_PATH,
    get_metric,
    get_metrics_by_grain,
    get_metrics_by_table,
    list_metrics,
    load_metric_contracts,
    validate_all_metric_contracts,
    validate_metric_contract,
)

MVP_METRICS = [
    "sessions",
    "orders",
    "items_sold",
    "gross_order_revenue",
    "gross_item_revenue",
    "gross_profit",
    "refund_amount",
    "net_revenue_after_refunds",
    "conversion_rate",
    "revenue_per_session",
    "profit_per_session",
    "refund_rate",
    "average_order_value",
    "items_per_order",
]


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------


def test_load_metric_contracts_returns_dict():
    contracts = load_metric_contracts(DEFAULT_METRICS_PATH)
    assert isinstance(contracts, dict)
    assert len(contracts) >= len(MVP_METRICS)


def test_all_mvp_metrics_exist():
    contracts = load_metric_contracts(DEFAULT_METRICS_PATH)
    for mid in MVP_METRICS:
        assert mid in contracts, f"Missing MVP metric: {mid}"


# ---------------------------------------------------------------------------
# get_metric / list_metrics
# ---------------------------------------------------------------------------


def test_get_metric_returns_single_metric():
    m = get_metric("sessions")
    assert m["metric_id"] == "sessions"
    assert "business_definition" in m


def test_get_metric_raises_for_unknown():
    with pytest.raises(KeyError, match="Unknown metric"):
        get_metric("nonexistent_metric_xyz")


def test_list_metrics_returns_sorted_ids():
    ids = list_metrics()
    assert sorted(ids) == ids
    for mid in MVP_METRICS:
        assert mid in ids


# ---------------------------------------------------------------------------
# Validation — real file
# ---------------------------------------------------------------------------


def test_validate_all_metric_contracts_passes():
    validate_all_metric_contracts(DEFAULT_METRICS_PATH)


# ---------------------------------------------------------------------------
# Validation — contract failures
# ---------------------------------------------------------------------------


def _write_yaml(tmp_path: Path, metrics: list[dict]) -> Path:
    p = tmp_path / "metrics.yaml"
    p.write_text(yaml.dump({"version": "1", "metrics": metrics}), encoding="utf-8")
    return p


def _minimal_metric(**overrides) -> dict:
    base = {
        "metric_id": "test_metric",
        "version": "1.0",
        "owner": "test",
        "business_definition": "A test metric.",
        "grain": "order",
        "status": "approved",
        "base_table": "orders",
        "required_tables": ["orders"],
        "validation_rules": ["A rule."],
        "assumptions": ["An assumption."],
    }
    base.update(overrides)
    return base


def test_missing_required_field_fails(tmp_path):
    metric = _minimal_metric()
    del metric["owner"]
    path = _write_yaml(tmp_path, [metric])
    with pytest.raises(ValueError, match="missing required fields"):
        validate_all_metric_contracts(path)


def test_empty_required_tables_fails(tmp_path):
    metric = _minimal_metric(required_tables=[])
    path = _write_yaml(tmp_path, [metric])
    with pytest.raises(ValueError, match="required_tables must be a non-empty list"):
        validate_all_metric_contracts(path)


def test_empty_validation_rules_fails(tmp_path):
    metric = _minimal_metric(validation_rules=[])
    path = _write_yaml(tmp_path, [metric])
    with pytest.raises(ValueError, match="validation_rules must be a non-empty list"):
        validate_all_metric_contracts(path)


def test_no_base_table_or_components_fails(tmp_path):
    metric = _minimal_metric()
    del metric["base_table"]
    path = _write_yaml(tmp_path, [metric])
    with pytest.raises(ValueError, match="must have either base_table or components"):
        validate_all_metric_contracts(path)


def test_composed_metric_without_components_list_fails(tmp_path):
    metric = _minimal_metric()
    del metric["base_table"]
    metric["components"] = "not_a_list"
    path = _write_yaml(tmp_path, [metric])
    with pytest.raises(ValueError, match="components must be a list"):
        validate_all_metric_contracts(path)


def test_cross_table_without_join_paths_or_alignment_fails(tmp_path):
    metric = _minimal_metric(
        required_tables=["orders", "order_items"],
    )
    path = _write_yaml(tmp_path, [metric])
    with pytest.raises(ValueError, match="cross-table metric requires join_paths or alignment_rules"):
        validate_all_metric_contracts(path)


def test_approved_metric_without_assumptions_fails(tmp_path):
    metric = _minimal_metric()
    del metric["assumptions"]
    path = _write_yaml(tmp_path, [metric])
    with pytest.raises(ValueError, match="approved metrics must include assumptions"):
        validate_all_metric_contracts(path)


# ---------------------------------------------------------------------------
# get_metrics_by_table / get_metrics_by_grain
# ---------------------------------------------------------------------------


def test_get_metrics_by_table_website_sessions():
    results = get_metrics_by_table("website_sessions")
    ids = [m["metric_id"] for m in results]
    assert "sessions" in ids
    assert "conversion_rate" in ids


def test_get_metrics_by_table_order_items():
    results = get_metrics_by_table("order_items")
    ids = [m["metric_id"] for m in results]
    assert "gross_item_revenue" in ids
    assert "gross_profit" in ids
    assert "items_sold" in ids


def test_get_metrics_by_grain_session():
    results = get_metrics_by_grain("session")
    ids = [m["metric_id"] for m in results]
    assert "sessions" in ids
    assert "conversion_rate" in ids
    assert "revenue_per_session" in ids


def test_get_metrics_by_grain_order():
    results = get_metrics_by_grain("order")
    ids = [m["metric_id"] for m in results]
    assert "orders" in ids
    assert "average_order_value" in ids


# ---------------------------------------------------------------------------
# Business-rule spot checks
# ---------------------------------------------------------------------------


def test_conversion_rate_requires_left_join():
    m = get_metric("conversion_rate")
    join_text = " ".join(m.get("join_paths", []) + m.get("alignment_rules", []) + m.get("assumptions", []))
    assert "LEFT JOIN" in join_text, "conversion_rate must require LEFT JOIN"


def test_conversion_rate_denominator_is_all_sessions():
    m = get_metric("conversion_rate")
    all_text = str(m)
    assert "website_sessions" in all_text
    assert "DISTINCT" in all_text


def test_net_revenue_has_refund_attribution_assumption():
    m = get_metric("net_revenue_after_refunds")
    assumption_text = " ".join(m.get("assumptions", []) + m.get("alignment_rules", []))
    assert "refund" in assumption_text.lower() and "attribution" in assumption_text.lower()


def test_gross_item_revenue_and_gross_order_revenue_are_distinct():
    gi = get_metric("gross_item_revenue")
    go = get_metric("gross_order_revenue")
    assert gi["base_table"] != go["base_table"]
    assert gi["base_table"] == "order_items"
    assert go["base_table"] == "orders"


def test_sessions_base_table_is_website_sessions():
    m = get_metric("sessions")
    assert m["base_table"] == "website_sessions"


def test_refund_amount_uses_order_item_refunds():
    m = get_metric("refund_amount")
    assert "order_item_refunds" in m["required_tables"]


def test_gross_profit_uses_order_items():
    m = get_metric("gross_profit")
    assert m["base_table"] == "order_items"
    assert "cogs_usd" in m["measure"]
