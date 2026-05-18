"""Tests for Stage 7: programmatic result validators."""

from __future__ import annotations

import math

import pytest

from src.validation.validators import validate_result


def _passed(result: dict) -> bool:
    return result["status"] == "passed"


def _failed(result: dict) -> bool:
    return result["status"] == "failed"


def _check_failed(result: dict, check_name: str) -> bool:
    return any(c["check_name"] == check_name and c["status"] == "failed" for c in result["checks"])


# ---------------------------------------------------------------------------
# General checks
# ---------------------------------------------------------------------------


def test_rows_not_list_fails():
    result = validate_result("conversion_by_channel", "not a list")
    assert _failed(result)
    assert _check_failed(result, "rows_is_list")


def test_row_not_dict_fails():
    result = validate_result("conversion_by_channel", [["a", "b"]])
    assert _failed(result)
    assert _check_failed(result, "rows_are_dicts")


def test_nan_value_fails():
    rows = [{"sessions": 100, "orders": 10, "conversion_rate": math.nan}]
    result = validate_result("conversion_by_channel", rows)
    assert _failed(result)
    assert _check_failed(result, "no_nan_values")


def test_infinite_value_fails():
    rows = [{"sessions": 100, "orders": 10, "conversion_rate": math.inf}]
    result = validate_result("conversion_by_channel", rows)
    assert _failed(result)
    assert _check_failed(result, "no_infinite_values")


def test_empty_rows_passes_general():
    result = validate_result("conversion_by_channel", [])
    assert _passed(result)


# ---------------------------------------------------------------------------
# conversion_by_channel
# ---------------------------------------------------------------------------


def test_conversion_by_channel_valid_passes():
    rows = [
        {"utm_source": "gsearch", "utm_campaign": "nonbrand", "sessions": 200, "orders": 40, "conversion_rate": 0.20},
        {"utm_source": "bsearch", "utm_campaign": "brand", "sessions": 100, "orders": 10, "conversion_rate": 0.10},
    ]
    result = validate_result("conversion_by_channel", rows)
    assert _passed(result)


def test_conversion_rate_above_1_fails():
    rows = [{"sessions": 100, "orders": 50, "conversion_rate": 1.5}]
    result = validate_result("conversion_by_channel", rows)
    assert _failed(result)
    assert _check_failed(result, "conversion_rate_range")


def test_orders_exceed_sessions_fails():
    rows = [{"sessions": 50, "orders": 80, "conversion_rate": 0.5}]
    result = validate_result("conversion_by_channel", rows)
    assert _failed(result)
    assert _check_failed(result, "orders_not_exceed_sessions")


def test_conversion_by_device_valid_passes():
    rows = [{"device_type": "desktop", "sessions": 500, "orders": 100, "conversion_rate": 0.20}]
    result = validate_result("conversion_by_device", rows)
    assert _passed(result)


def test_conversion_by_device_rate_below_0_fails():
    rows = [{"device_type": "mobile", "sessions": 100, "orders": 5, "conversion_rate": -0.05}]
    result = validate_result("conversion_by_device", rows)
    assert _failed(result)
    assert _check_failed(result, "conversion_rate_range")


# ---------------------------------------------------------------------------
# revenue_by_campaign
# ---------------------------------------------------------------------------


def test_revenue_by_campaign_valid_passes():
    rows = [
        {"utm_source": "gsearch", "utm_campaign": "nonbrand", "orders": 50, "gross_order_revenue": 2500.0, "average_order_value": 50.0},
    ]
    result = validate_result("revenue_by_campaign", rows)
    assert _passed(result)


def test_revenue_negative_fails():
    rows = [{"utm_source": "gsearch", "orders": 10, "gross_order_revenue": -100.0}]
    result = validate_result("revenue_by_campaign", rows)
    assert _failed(result)
    assert _check_failed(result, "revenue_non_negative")


def test_revenue_by_campaign_empty_rows_passes():
    result = validate_result("revenue_by_campaign", [])
    assert _passed(result)


# ---------------------------------------------------------------------------
# refund_rate_by_product
# ---------------------------------------------------------------------------


def test_refund_rate_by_product_valid_passes():
    rows = [
        {"product_id": 1, "product_name": "Teddy Bear", "items_sold": 100, "refunded_items": 5, "refund_rate": 0.05, "refund_amount": 49.95},
    ]
    result = validate_result("refund_rate_by_product", rows)
    assert _passed(result)


def test_refund_rate_above_1_fails():
    rows = [{"product_id": 1, "product_name": "Bear", "items_sold": 100, "refunded_items": 10, "refund_rate": 1.5}]
    result = validate_result("refund_rate_by_product", rows)
    assert _failed(result)
    assert _check_failed(result, "refund_rate_range")


def test_refund_count_exceeds_items_fails():
    rows = [{"product_id": 1, "product_name": "Bear", "items_sold": 10, "refunded_items": 15, "refund_rate": 0.5}]
    result = validate_result("refund_rate_by_product", rows)
    assert _failed(result)
    assert _check_failed(result, "refund_not_exceed_items")


# ---------------------------------------------------------------------------
# monthly_revenue_trend
# ---------------------------------------------------------------------------


def test_monthly_revenue_trend_valid_passes():
    rows = [
        {"month": "2014-01-01", "orders": 200, "gross_order_revenue": 10000.0, "average_order_value": 50.0},
        {"month": "2014-02-01", "orders": 180, "gross_order_revenue": 9000.0, "average_order_value": 50.0},
    ]
    result = validate_result("monthly_revenue_trend", rows)
    assert _passed(result)


def test_monthly_revenue_negative_fails():
    rows = [{"month": "2014-01-01", "orders": 100, "gross_order_revenue": -500.0}]
    result = validate_result("monthly_revenue_trend", rows)
    assert _failed(result)
    assert _check_failed(result, "revenue_non_negative")


def test_monthly_revenue_trend_empty_passes():
    result = validate_result("monthly_revenue_trend", [])
    assert _passed(result)
