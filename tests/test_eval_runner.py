"""Tests for the question-bank eval harness (Stage 9)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from src.evals.eval_runner import load_question_bank, run_eval_case, run_question_bank

_BANK_PATH = Path(__file__).parent.parent / "src" / "evals" / "question_bank.yaml"

# ---------------------------------------------------------------------------
# load_question_bank
# ---------------------------------------------------------------------------


def test_load_question_bank_returns_list():
    cases = load_question_bank(_BANK_PATH)
    assert isinstance(cases, list)
    assert len(cases) > 0


def test_question_bank_has_required_keys():
    cases = load_question_bank(_BANK_PATH)
    required = {"id", "question", "expected_status", "expected_route_type", "should_execute_sql"}
    for case in cases:
        missing = required - set(case.keys())
        assert not missing, f"Case {case.get('id')} missing keys: {missing}"


def test_question_bank_contains_supported_cases():
    cases = load_question_bank(_BANK_PATH)
    supported = [c for c in cases if c["expected_route_type"] == "template"]
    assert len(supported) >= 5, "Expected at least 5 supported (template) cases"


def test_question_bank_contains_clarify_cases():
    cases = load_question_bank(_BANK_PATH)
    clarify = [c for c in cases if c["expected_route_type"] == "clarify"]
    assert len(clarify) >= 3, "Expected at least 3 clarify cases"


def test_question_bank_contains_unsupported_cases():
    cases = load_question_bank(_BANK_PATH)
    unsupported = [c for c in cases if c["expected_route_type"] == "unsupported"]
    assert len(unsupported) >= 4, "Expected at least 4 unsupported cases"


# ---------------------------------------------------------------------------
# run_eval_case — clarify and unsupported (no DuckDB required)
# ---------------------------------------------------------------------------


def _get_case_by_id(case_id: str) -> dict:
    cases = load_question_bank(_BANK_PATH)
    for c in cases:
        if c["id"] == case_id:
            return c
    raise KeyError(f"Case {case_id!r} not found in question bank")


def test_run_eval_case_clarify_passes_without_duckdb(tmp_path):
    case = _get_case_by_id("clarify_best_channel")
    result = run_eval_case(case, db_path=tmp_path / "nonexistent.duckdb")
    assert result["status"] == "passed", f"Checks: {result['checks']}"
    assert result["response_summary"]["status"] == "clarify"
    assert result["response_summary"]["route_type"] == "clarify"


def test_run_eval_case_unsupported_passes_without_duckdb(tmp_path):
    case = _get_case_by_id("unsupported_customer_lifetime_value")
    result = run_eval_case(case, db_path=tmp_path / "nonexistent.duckdb")
    assert result["status"] == "passed", f"Checks: {result['checks']}"
    assert result["response_summary"]["status"] == "unsupported"


# ---------------------------------------------------------------------------
# run_eval_case — supported (skip when DuckDB missing)
# ---------------------------------------------------------------------------


def test_run_eval_case_skips_supported_when_db_missing(tmp_path):
    case = _get_case_by_id("supported_conversion_by_channel")
    result = run_eval_case(case, db_path=tmp_path / "nonexistent.duckdb")
    assert result["status"] == "skipped"
    assert all(c["status"] == "skipped" for c in result["checks"])


# ---------------------------------------------------------------------------
# run_question_bank aggregate output
# ---------------------------------------------------------------------------


def test_run_question_bank_returns_aggregate_keys(tmp_path):
    output = run_question_bank(_BANK_PATH, db_path=tmp_path / "nonexistent.duckdb")
    assert "total_cases" in output
    assert "passed" in output
    assert "failed" in output
    assert "skipped" in output
    assert "results" in output
    assert output["total_cases"] == output["passed"] + output["failed"] + output["skipped"]
    assert output["total_cases"] == len(output["results"])


def test_run_question_bank_passes_clarify_unsupported_without_db(tmp_path):
    output = run_question_bank(_BANK_PATH, db_path=tmp_path / "nonexistent.duckdb")
    assert output["passed"] >= 7, (
        f"Expected at least 7 passing cases (3 clarify + 4 unsupported), got {output['passed']}"
    )


# ---------------------------------------------------------------------------
# Failed expectation produces a failed result
# ---------------------------------------------------------------------------


def test_run_eval_case_failed_expectation(tmp_path):
    """A case with a wrong expected_status should produce a failed result."""
    bad_case = {
        "id": "test_bad_expectation",
        "question": "What is the best channel?",
        "expected_status": "ok",          # wrong — router returns "clarify"
        "expected_route_type": "clarify",
        "expected_template_id": None,
        "should_execute_sql": False,
        "expected_validation_status": None,
    }
    result = run_eval_case(bad_case, db_path=tmp_path / "nonexistent.duckdb")
    assert result["status"] == "failed"
    status_check = next(c for c in result["checks"] if c["check_name"] == "response_status")
    assert status_check["status"] == "failed"
    assert status_check["actual"] == "clarify"
    assert status_check["expected"] == "ok"


# ---------------------------------------------------------------------------
# response_summary completeness
# ---------------------------------------------------------------------------


def test_response_summary_has_all_required_fields(tmp_path):
    case = _get_case_by_id("clarify_best_channel")
    result = run_eval_case(case, db_path=tmp_path / "nonexistent.duckdb")
    summary = result["response_summary"]
    for field in ("status", "route_type", "template_id", "validation_status", "row_count"):
        assert field in summary, f"response_summary missing field: {field}"
