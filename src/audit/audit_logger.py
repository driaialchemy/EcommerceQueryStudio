"""Deterministic audit logger for the governed analytics runtime."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_AUDIT_PATH = Path("data/audit/runtime_audit_log.jsonl")

_SQL_PREVIEW_MAX = 300


def build_audit_event(question: str, response: dict) -> dict:
    """Build a structured audit event from a pipeline response."""
    validation = response.get("validation")
    if validation and isinstance(validation.get("checks"), list):
        checks = validation["checks"]
        passed = sum(1 for c in checks if c.get("status") == "passed")
        failed = sum(1 for c in checks if c.get("status") == "failed")
        validation_summary = {"passed": passed, "failed": failed}
    else:
        validation_summary = None

    sql = response.get("sql")
    if sql:
        sql_hash = hashlib.sha256(sql.encode()).hexdigest()
        sql_preview = sql[:_SQL_PREVIEW_MAX]
    else:
        sql_hash = None
        sql_preview = None

    return {
        "question": question,
        "status": response.get("status"),
        "route_type": response.get("route_type"),
        "template_id": response.get("template_id"),
        "parameters": response.get("parameters", {}),
        "row_count": response.get("row_count"),
        "validation_status": response.get("validation_status"),
        "validation_summary": validation_summary,
        "assumptions": response.get("assumptions", []),
        "sql_hash": sql_hash,
        "sql_preview": sql_preview,
    }


def write_audit_event(
    event: dict,
    audit_path: Path = DEFAULT_AUDIT_PATH,
) -> dict:
    """Append one JSON audit event to the JSONL audit file and return it."""
    audit_path = Path(audit_path)
    audit_path.parent.mkdir(parents=True, exist_ok=True)

    if "timestamp" not in event:
        event = {**event, "timestamp": datetime.now(timezone.utc).isoformat()}

    with audit_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event) + "\n")

    return event
