"""Tests for Stage 8: audit_logger."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from src.audit.audit_logger import (
    DEFAULT_AUDIT_PATH,
    build_audit_event,
    write_audit_event,
)

# ---------------------------------------------------------------------------
# write_audit_event
# ---------------------------------------------------------------------------


def test_write_creates_parent_directory(tmp_path):
    audit_path = tmp_path / "audit" / "subdir" / "log.jsonl"
    write_audit_event({"question": "q"}, audit_path=audit_path)
    assert audit_path.parent.exists()


def test_write_appends_one_json_line(tmp_path):
    audit_path = tmp_path / "log.jsonl"
    write_audit_event({"question": "q1"}, audit_path=audit_path)
    write_audit_event({"question": "q2"}, audit_path=audit_path)
    lines = audit_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["question"] == "q1"
    assert json.loads(lines[1])["question"] == "q2"


def test_write_adds_timestamp_when_missing(tmp_path):
    audit_path = tmp_path / "log.jsonl"
    returned = write_audit_event({"question": "q"}, audit_path=audit_path)
    assert "timestamp" in returned
    line = audit_path.read_text(encoding="utf-8").strip()
    assert "timestamp" in json.loads(line)


def test_write_preserves_existing_timestamp(tmp_path):
    audit_path = tmp_path / "log.jsonl"
    event = {"question": "q", "timestamp": "2024-01-01T00:00:00+00:00"}
    returned = write_audit_event(event, audit_path=audit_path)
    assert returned["timestamp"] == "2024-01-01T00:00:00+00:00"


def test_write_returns_final_event(tmp_path):
    audit_path = tmp_path / "log.jsonl"
    returned = write_audit_event({"question": "q", "status": "ok"}, audit_path=audit_path)
    assert returned["status"] == "ok"


# ---------------------------------------------------------------------------
# build_audit_event
# ---------------------------------------------------------------------------

_BASE_RESPONSE = {
    "status": "ok",
    "route_type": "template",
    "template_id": "conversion_by_channel",
    "parameters": {"start_date": "2012-01-01", "end_date": "2015-12-31"},
    "sql": "SELECT 1",
    "row_count": 5,
    "rows": [{"sessions": 100, "orders": 10}],
    "assumptions": ["date range defaults"],
    "validation_status": "passed",
    "validation": {
        "status": "passed",
        "checks": [
            {"check_name": "rows_is_list", "status": "passed", "message": "ok"},
            {"check_name": "row_count_non_negative", "status": "passed", "message": "ok"},
            {"check_name": "no_nan_or_infinite_values", "status": "failed", "message": "err"},
        ],
    },
}


def test_build_includes_required_fields():
    event = build_audit_event("Show conversion by channel", _BASE_RESPONSE)
    for field in (
        "question", "status", "route_type", "template_id",
        "parameters", "row_count", "validation_status",
        "validation_summary", "assumptions", "sql_hash", "sql_preview",
    ):
        assert field in event, f"Missing field: {field}"


def test_build_hashes_sql():
    event = build_audit_event("q", _BASE_RESPONSE)
    expected = hashlib.sha256("SELECT 1".encode()).hexdigest()
    assert event["sql_hash"] == expected


def test_build_does_not_store_full_sql():
    long_sql = "SELECT " + "x," * 200 + "1 FROM t"
    response = {**_BASE_RESPONSE, "sql": long_sql}
    event = build_audit_event("q", response)
    assert "sql" not in event or event.get("sql") is None  # no raw sql key
    assert "sql_hash" in event
    assert event["sql_hash"] == hashlib.sha256(long_sql.encode()).hexdigest()


def test_sql_preview_truncated_to_300():
    long_sql = "SELECT " + "a" * 400
    response = {**_BASE_RESPONSE, "sql": long_sql}
    event = build_audit_event("q", response)
    assert len(event["sql_preview"]) <= 300


def test_validation_summary_counts_passed_and_failed():
    event = build_audit_event("q", _BASE_RESPONSE)
    summary = event["validation_summary"]
    assert summary["passed"] == 2
    assert summary["failed"] == 1


def test_build_clarify_response_sql_fields_null():
    clarify_response = {
        "status": "clarify",
        "route_type": "clarify",
        "template_id": None,
        "parameters": {},
        "sql": None,
        "row_count": None,
        "assumptions": [],
        "validation_status": "not_applicable",
        "validation": None,
    }
    event = build_audit_event("Which is best?", clarify_response)
    assert event["sql_hash"] is None
    assert event["sql_preview"] is None


def test_build_unsupported_response_sql_fields_null():
    unsupported_response = {
        "status": "unsupported",
        "route_type": "unsupported",
        "template_id": None,
        "parameters": {},
        "sql": None,
        "row_count": None,
        "assumptions": [],
        "validation_status": "not_applicable",
        "validation": None,
    }
    event = build_audit_event("How many employees?", unsupported_response)
    assert event["sql_hash"] is None
    assert event["sql_preview"] is None
