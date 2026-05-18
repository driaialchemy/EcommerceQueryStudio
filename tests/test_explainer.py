"""Tests for Stage 8: explainer."""

from __future__ import annotations

from src.explanation.explainer import explain_answer

_OK_RESPONSE = {
    "status": "ok",
    "route_type": "template",
    "template_id": "conversion_by_channel",
    "parameters": {"start_date": "2012-01-01", "end_date": "2015-12-31"},
    "sql": "SELECT 1",
    "row_count": 7,
    "assumptions": ["date range defaults"],
    "validation_status": "passed",
    "validation": {
        "status": "passed",
        "checks": [
            {"check_name": "rows_is_list", "status": "passed", "message": "ok"},
            {"check_name": "row_count_non_negative", "status": "passed", "message": "ok"},
            {"check_name": "bad_check", "status": "failed", "message": "err"},
        ],
    },
}

_CLARIFY_RESPONSE = {
    "status": "clarify",
    "route_type": "clarify",
    "template_id": None,
    "parameters": {},
    "sql": None,
    "row_count": None,
    "assumptions": [],
    "validation_status": "not_applicable",
    "validation": None,
    "reason": "ambiguous",
}

_UNSUPPORTED_RESPONSE = {
    "status": "unsupported",
    "route_type": "unsupported",
    "template_id": None,
    "parameters": {},
    "sql": None,
    "row_count": None,
    "assumptions": [],
    "validation_status": "not_applicable",
    "validation": None,
    "reason": "no template",
}


# ---------------------------------------------------------------------------
# Structure checks
# ---------------------------------------------------------------------------


def test_explain_returns_required_keys_for_ok():
    result = explain_answer(_OK_RESPONSE)
    for key in ("summary", "assumptions", "method", "validation_summary", "limitations"):
        assert key in result


def test_explain_returns_required_keys_for_clarify():
    result = explain_answer(_CLARIFY_RESPONSE)
    for key in ("summary", "assumptions", "method", "validation_summary", "limitations"):
        assert key in result


def test_explain_returns_required_keys_for_unsupported():
    result = explain_answer(_UNSUPPORTED_RESPONSE)
    for key in ("summary", "assumptions", "method", "validation_summary", "limitations"):
        assert key in result


# ---------------------------------------------------------------------------
# OK response
# ---------------------------------------------------------------------------


def test_explain_ok_summary_mentions_template_id():
    result = explain_answer(_OK_RESPONSE)
    assert "conversion_by_channel" in result["summary"]


def test_explain_ok_summary_mentions_row_count():
    result = explain_answer(_OK_RESPONSE)
    assert "7" in result["summary"]


def test_explain_ok_method_mentions_sql_template():
    result = explain_answer(_OK_RESPONSE)
    assert "template" in result["method"].lower()


def test_explain_ok_method_mentions_duckdb():
    result = explain_answer(_OK_RESPONSE)
    assert "duckdb" in result["method"].lower()


def test_explain_ok_assumptions_copied():
    result = explain_answer(_OK_RESPONSE)
    assert result["assumptions"] == ["date range defaults"]


def test_explain_ok_validation_summary_counts():
    result = explain_answer(_OK_RESPONSE)
    assert "2" in result["validation_summary"]
    assert "1" in result["validation_summary"]


def test_explain_ok_limitations_mention_deterministic():
    result = explain_answer(_OK_RESPONSE)
    assert any("deterministic" in lim.lower() for lim in result["limitations"])


# ---------------------------------------------------------------------------
# Clarify response
# ---------------------------------------------------------------------------


def test_explain_clarify_summary_mentions_clarification():
    result = explain_answer(_CLARIFY_RESPONSE)
    assert "clarif" in result["summary"].lower()


def test_explain_clarify_method_no_sql():
    result = explain_answer(_CLARIFY_RESPONSE)
    assert "no sql" in result["method"].lower()


def test_explain_clarify_validation_summary_not_applicable():
    result = explain_answer(_CLARIFY_RESPONSE)
    assert result["validation_summary"] == "not_applicable"


def test_explain_clarify_limitations_mention_ambiguous():
    result = explain_answer(_CLARIFY_RESPONSE)
    assert any("ambig" in lim.lower() or "metric" in lim.lower() for lim in result["limitations"])


# ---------------------------------------------------------------------------
# Unsupported response
# ---------------------------------------------------------------------------


def test_explain_unsupported_summary_mentions_unsupported():
    result = explain_answer(_UNSUPPORTED_RESPONSE)
    assert "unsupported" in result["summary"].lower()


def test_explain_unsupported_method_no_sql():
    result = explain_answer(_UNSUPPORTED_RESPONSE)
    assert "no sql" in result["method"].lower()


def test_explain_unsupported_validation_summary_not_applicable():
    result = explain_answer(_UNSUPPORTED_RESPONSE)
    assert result["validation_summary"] == "not_applicable"


def test_explain_unsupported_limitations_mention_template():
    result = explain_answer(_UNSUPPORTED_RESPONSE)
    assert any("template" in lim.lower() for lim in result["limitations"])
