"""Deterministic question-bank evaluation harness."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from src.runtime.pipeline import answer_question

_DEFAULT_BANK_PATH = Path(__file__).parent / "question_bank.yaml"
_DEFAULT_DB_PATH = Path(__file__).parent.parent.parent / "data" / "processed" / "maven_fuzzy_factory.duckdb"


def load_question_bank(path: Path | str | None = None) -> list[dict]:
    """Load and return eval cases from the question bank YAML."""
    bank_path = Path(path) if path is not None else _DEFAULT_BANK_PATH
    with open(bank_path, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    return data["eval_cases"]


def _check(check_name: str, expected: Any, actual: Any, message: str = "") -> dict:
    status = "passed" if actual == expected else "failed"
    return {
        "check_name": check_name,
        "status": status,
        "expected": expected,
        "actual": actual,
        "message": message or (
            f"Expected {expected!r}, got {actual!r}" if status == "failed" else "ok"
        ),
    }


def _skipped_check(check_name: str, reason: str, expected: Any = None) -> dict:
    return {
        "check_name": check_name,
        "status": "skipped",
        "expected": expected,
        "actual": None,
        "message": reason,
    }


def run_eval_case(case: dict, db_path: Path | str | None = None) -> dict:
    """Run a single eval case and return a structured result dict."""
    case_id = case["id"]
    question = case["question"]
    should_execute_sql = case["should_execute_sql"]
    expected_status = case["expected_status"]
    expected_route_type = case["expected_route_type"]
    expected_template_id = case.get("expected_template_id")
    expected_validation_status = case.get("expected_validation_status")

    resolved_db_path = Path(db_path) if db_path is not None else _DEFAULT_DB_PATH
    db_missing = should_execute_sql and not resolved_db_path.exists()

    if db_missing:
        response_summary = {
            "status": None,
            "route_type": None,
            "template_id": None,
            "validation_status": None,
            "row_count": None,
        }
        skip_reason = f"DuckDB file not found at {resolved_db_path}; skipping SQL execution case."
        return {
            "id": case_id,
            "question": question,
            "status": "skipped",
            "checks": [_skipped_check("all_checks", skip_reason)],
            "response_summary": response_summary,
        }

    try:
        response = answer_question(question, db_path=resolved_db_path)
    except Exception as exc:  # noqa: BLE001
        response_summary = {
            "status": "error",
            "route_type": None,
            "template_id": None,
            "validation_status": None,
            "row_count": None,
        }
        return {
            "id": case_id,
            "question": question,
            "status": "failed",
            "checks": [
                {
                    "check_name": "pipeline_execution",
                    "status": "failed",
                    "expected": None,
                    "actual": None,
                    "message": f"Pipeline raised exception: {exc}",
                }
            ],
            "response_summary": response_summary,
        }

    actual_status = response.get("status")
    actual_route_type = response.get("route_type")
    actual_template_id = response.get("template_id")
    actual_validation_status = response.get("validation_status")
    actual_row_count = response.get("row_count")
    actual_sql = response.get("sql")

    checks = []
    checks.append(_check("response_status", expected_status, actual_status))
    checks.append(_check("route_type", expected_route_type, actual_route_type))
    checks.append(_check("template_id", expected_template_id, actual_template_id))

    if should_execute_sql:
        has_sql = actual_sql is not None and actual_sql != ""
        has_rows = actual_row_count is not None
        sql_executed = has_sql and has_rows
        checks.append(_check(
            "sql_executed",
            True,
            sql_executed,
            "Expected SQL to be executed with rows returned." if not sql_executed else "ok",
        ))
    else:
        has_sql_output = actual_sql is not None and actual_sql != ""
        checks.append(_check(
            "sql_not_executed",
            False,
            has_sql_output,
            "Expected no SQL output for non-executable case." if has_sql_output else "ok",
        ))

    if expected_validation_status is not None:
        checks.append(_check("validation_status", expected_validation_status, actual_validation_status))

    all_passed = all(c["status"] == "passed" for c in checks)
    any_failed = any(c["status"] == "failed" for c in checks)
    overall = "passed" if all_passed else ("failed" if any_failed else "skipped")

    return {
        "id": case_id,
        "question": question,
        "status": overall,
        "checks": checks,
        "response_summary": {
            "status": actual_status,
            "route_type": actual_route_type,
            "template_id": actual_template_id,
            "validation_status": actual_validation_status,
            "row_count": actual_row_count,
        },
    }


def run_question_bank(
    question_bank_path: Path | str | None = None,
    db_path: Path | str | None = None,
) -> dict:
    """Run all cases in the question bank and return aggregate results."""
    cases = load_question_bank(question_bank_path)
    results = [run_eval_case(case, db_path=db_path) for case in cases]

    passed = sum(1 for r in results if r["status"] == "passed")
    failed = sum(1 for r in results if r["status"] == "failed")
    skipped = sum(1 for r in results if r["status"] == "skipped")

    return {
        "total_cases": len(results),
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
        "results": results,
    }
