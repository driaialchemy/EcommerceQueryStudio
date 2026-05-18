"""Programmatic result validators for template-backed query results."""

from __future__ import annotations

import math


def _is_numeric(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _fields_matching(row: dict, *keywords: str, exclude: tuple[str, ...] = ()) -> list[str]:
    """Return field names whose lowercased name contains ALL keywords and none of exclude."""
    result = []
    for k in row:
        lk = k.lower()
        if all(kw in lk for kw in keywords) and not any(ex in lk for ex in exclude):
            result.append(k)
    return result


def _check_general(rows: list[dict]) -> list[dict]:
    checks = []

    if not isinstance(rows, list):
        return [{"check_name": "rows_is_list", "status": "failed", "message": "rows must be a list"}]

    checks.append({"check_name": "rows_is_list", "status": "passed", "message": "rows is a list"})
    checks.append({"check_name": "row_count_non_negative", "status": "passed", "message": f"row_count={len(rows)} >= 0"})

    for i, row in enumerate(rows):
        if not isinstance(row, dict):
            checks.append({"check_name": "rows_are_dicts", "status": "failed", "message": f"row[{i}] is not a dict"})
            return checks

    checks.append({"check_name": "rows_are_dicts", "status": "passed", "message": "all rows are dicts"})

    nan_inf_ok = True
    for i, row in enumerate(rows):
        for k, v in row.items():
            if _is_numeric(v):
                if math.isnan(v):
                    checks.append({"check_name": "no_nan_values", "status": "failed", "message": f"row[{i}].{k} is NaN"})
                    nan_inf_ok = False
                elif math.isinf(v):
                    checks.append({"check_name": "no_infinite_values", "status": "failed", "message": f"row[{i}].{k} is infinite"})
                    nan_inf_ok = False

    if nan_inf_ok:
        checks.append({"check_name": "no_nan_or_infinite_values", "status": "passed", "message": "no NaN or infinite numeric values"})

    return checks


def _check_conversion(rows: list[dict]) -> list[dict]:
    checks = []
    rate_ok = True
    session_ok = True
    order_ok = True
    exceed_ok = True

    for i, row in enumerate(rows):
        rate_fields = _fields_matching(row, "rate") + _fields_matching(row, "cvr") + _fields_matching(row, "conversion")
        rate_fields = list(dict.fromkeys(rate_fields))
        for f in rate_fields:
            v = row[f]
            if _is_numeric(v) and not (0.0 <= v <= 1.0):
                checks.append({"check_name": "conversion_rate_range", "status": "failed", "message": f"row[{i}].{f}={v} not in [0,1]"})
                rate_ok = False

        session_fields = _fields_matching(row, "session")
        for f in session_fields:
            v = row[f]
            if _is_numeric(v) and v < 0:
                checks.append({"check_name": "session_count_non_negative", "status": "failed", "message": f"row[{i}].{f}={v} < 0"})
                session_ok = False

        order_fields = _fields_matching(row, "order")
        for f in order_fields:
            v = row[f]
            if _is_numeric(v) and v < 0:
                checks.append({"check_name": "order_count_non_negative", "status": "failed", "message": f"row[{i}].{f}={v} < 0"})
                order_ok = False

        # orders must not exceed sessions in same row
        for sf in session_fields:
            for of in order_fields:
                sv, ov = row.get(sf), row.get(of)
                if _is_numeric(sv) and _is_numeric(ov) and ov > sv:
                    checks.append({"check_name": "orders_not_exceed_sessions", "status": "failed", "message": f"row[{i}]: {of}={ov} > {sf}={sv}"})
                    exceed_ok = False

    if rate_ok:
        checks.append({"check_name": "conversion_rate_range", "status": "passed", "message": "all conversion-rate values in [0,1]"})
    if session_ok:
        checks.append({"check_name": "session_count_non_negative", "status": "passed", "message": "all session counts >= 0"})
    if order_ok:
        checks.append({"check_name": "order_count_non_negative", "status": "passed", "message": "all order counts >= 0"})
    if exceed_ok:
        checks.append({"check_name": "orders_not_exceed_sessions", "status": "passed", "message": "orders do not exceed sessions"})

    return checks


def _check_revenue_by_campaign(rows: list[dict]) -> list[dict]:
    checks = []
    revenue_ok = True
    order_ok = True

    for i, row in enumerate(rows):
        rev_fields = _fields_matching(row, "revenue") + _fields_matching(row, "sales")
        rev_fields = list(dict.fromkeys(rev_fields))
        for f in rev_fields:
            v = row[f]
            if _is_numeric(v) and v < 0:
                checks.append({"check_name": "revenue_non_negative", "status": "failed", "message": f"row[{i}].{f}={v} < 0"})
                revenue_ok = False

        order_fields = _fields_matching(row, "order")
        for f in order_fields:
            v = row[f]
            if _is_numeric(v) and v < 0:
                checks.append({"check_name": "order_count_non_negative", "status": "failed", "message": f"row[{i}].{f}={v} < 0"})
                order_ok = False

    if revenue_ok:
        checks.append({"check_name": "revenue_non_negative", "status": "passed", "message": "all revenue values >= 0"})
    if order_ok:
        checks.append({"check_name": "order_count_non_negative", "status": "passed", "message": "all order counts >= 0"})

    return checks


def _check_refund_rate_by_product(rows: list[dict]) -> list[dict]:
    checks = []
    rate_ok = True
    refund_count_ok = True
    item_order_ok = True
    exceed_ok = True

    for i, row in enumerate(rows):
        rate_fields = _fields_matching(row, "refund", "rate")
        for f in rate_fields:
            v = row[f]
            if _is_numeric(v) and not (0.0 <= v <= 1.0):
                checks.append({"check_name": "refund_rate_range", "status": "failed", "message": f"row[{i}].{f}={v} not in [0,1]"})
                rate_ok = False

        refund_count_fields = _fields_matching(row, "refund", exclude=("rate", "amount"))
        for f in refund_count_fields:
            v = row[f]
            if _is_numeric(v) and v < 0:
                checks.append({"check_name": "refund_count_non_negative", "status": "failed", "message": f"row[{i}].{f}={v} < 0"})
                refund_count_ok = False

        item_fields = _fields_matching(row, "item") + _fields_matching(row, "order")
        item_fields = list(dict.fromkeys(item_fields))
        for f in item_fields:
            v = row[f]
            if _is_numeric(v) and v < 0:
                checks.append({"check_name": "item_order_count_non_negative", "status": "failed", "message": f"row[{i}].{f}={v} < 0"})
                item_order_ok = False

        # refund counts must not exceed item/order counts
        for rf in refund_count_fields:
            for itf in item_fields:
                rv, iv = row.get(rf), row.get(itf)
                if _is_numeric(rv) and _is_numeric(iv) and rv > iv:
                    checks.append({"check_name": "refund_not_exceed_items", "status": "failed", "message": f"row[{i}]: {rf}={rv} > {itf}={iv}"})
                    exceed_ok = False

    if rate_ok:
        checks.append({"check_name": "refund_rate_range", "status": "passed", "message": "all refund-rate values in [0,1]"})
    if refund_count_ok:
        checks.append({"check_name": "refund_count_non_negative", "status": "passed", "message": "all refund counts >= 0"})
    if item_order_ok:
        checks.append({"check_name": "item_order_count_non_negative", "status": "passed", "message": "all item/order counts >= 0"})
    if exceed_ok:
        checks.append({"check_name": "refund_not_exceed_items", "status": "passed", "message": "refund counts do not exceed item/order counts"})

    return checks


def _check_monthly_revenue_trend(rows: list[dict]) -> list[dict]:
    checks = []
    revenue_ok = True
    date_ok = True

    for i, row in enumerate(rows):
        rev_fields = _fields_matching(row, "revenue") + _fields_matching(row, "sales")
        rev_fields = list(dict.fromkeys(rev_fields))
        for f in rev_fields:
            v = row[f]
            if _is_numeric(v) and v < 0:
                checks.append({"check_name": "revenue_non_negative", "status": "failed", "message": f"row[{i}].{f}={v} < 0"})
                revenue_ok = False

        date_fields = _fields_matching(row, "date") + _fields_matching(row, "month") + _fields_matching(row, "time")
        date_fields = list(dict.fromkeys(date_fields))
        for f in date_fields:
            if row[f] is None:
                checks.append({"check_name": "date_fields_not_null", "status": "failed", "message": f"row[{i}].{f} is null"})
                date_ok = False

    if revenue_ok:
        checks.append({"check_name": "revenue_non_negative", "status": "passed", "message": "all revenue values >= 0"})
    if date_ok:
        checks.append({"check_name": "date_fields_not_null", "status": "passed", "message": "all date/month/time fields are non-null"})

    return checks


_TEMPLATE_CHECKERS = {
    "conversion_by_channel": _check_conversion,
    "conversion_by_device": _check_conversion,
    "revenue_by_campaign": _check_revenue_by_campaign,
    "refund_rate_by_product": _check_refund_rate_by_product,
    "monthly_revenue_trend": _check_monthly_revenue_trend,
}


def validate_result(
    template_id: str,
    rows: list[dict],
    parameters: dict | None = None,
) -> dict:
    """Validate query result rows against general and template-specific rules."""
    general_checks = _check_general(rows)

    # If general checks failed at the structural level, stop early
    structural_failed = any(
        c["status"] == "failed" and c["check_name"] in ("rows_is_list", "rows_are_dicts")
        for c in general_checks
    )

    specific_checks: list[dict] = []
    if not structural_failed:
        checker = _TEMPLATE_CHECKERS.get(template_id)
        if checker:
            specific_checks = checker(rows)

    all_checks = general_checks + specific_checks
    overall = "passed" if all(c["status"] == "passed" for c in all_checks) else "failed"

    return {
        "status": overall,
        "template_id": template_id,
        "checks": all_checks,
    }
