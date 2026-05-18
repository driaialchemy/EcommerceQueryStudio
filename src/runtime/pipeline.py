"""Runtime pipeline: routes a question, renders SQL, executes against DuckDB."""

from __future__ import annotations

from pathlib import Path

from src.audit.audit_logger import DEFAULT_AUDIT_PATH, build_audit_event, write_audit_event
from src.explanation.explainer import explain_answer
from src.runtime.executor import DEFAULT_DB_PATH, execute_sql
from src.runtime.router import route_question
from src.templates.template_loader import get_template, render_template_sql
from src.validation.validators import validate_result


def _attach_audit(response: dict, question: str, audit_path: Path) -> dict:
    """Write audit event and attach audit fields to response in-place."""
    try:
        event = build_audit_event(question, response)
        write_audit_event(event, audit_path=audit_path)
        response["audit_logged"] = True
        response["audit_path"] = str(audit_path)
    except Exception as exc:  # noqa: BLE001
        response["audit_logged"] = False
        response["audit_error"] = str(exc)
    return response


def answer_question(
    question: str,
    parameters: dict | None = None,
    db_path: Path = DEFAULT_DB_PATH,
    audit_path: Path = DEFAULT_AUDIT_PATH,
) -> dict:
    """Answer a supported analytics question end-to-end.

    Steps:
    1. Route the question to a template (or clarify/unsupported).
    2. Merge routed default parameters with caller-supplied parameters
       (caller parameters take precedence).
    3. Render SQL via the template loader.
    4. Execute against DuckDB.
    5. Explain the answer deterministically.
    6. Write an audit event.
    7. Return a structured response.

    Returns a dict with keys:
        status: "ok" | "clarify" | "unsupported" | "error"
        route_type: str
        template_id: str | None
        parameters: dict
        sql: str | None
        row_count: int | None
        rows: list[dict] | None
        assumptions: list[str]
        validation_status: str
        reason: str | None
        explanation: dict
        audit_logged: bool
        audit_path: str  (present when audit_logged is True)
        audit_error: str  (present when audit_logged is False)
    """
    route = route_question(question)
    route_type = route["route_type"]

    if route_type == "clarify":
        response = {
            "status": "clarify",
            "route_type": route_type,
            "template_id": None,
            "parameters": {},
            "sql": None,
            "row_count": None,
            "rows": None,
            "assumptions": [],
            "validation_status": "not_applicable",
            "validation": None,
            "reason": route["reason"],
        }
        response["explanation"] = explain_answer(response)
        return _attach_audit(response, question, audit_path)

    if route_type == "unsupported":
        response = {
            "status": "unsupported",
            "route_type": route_type,
            "template_id": None,
            "parameters": {},
            "sql": None,
            "row_count": None,
            "rows": None,
            "assumptions": [],
            "validation_status": "not_applicable",
            "validation": None,
            "reason": route["reason"],
        }
        response["explanation"] = explain_answer(response)
        return _attach_audit(response, question, audit_path)

    template_id = route["template_id"]
    merged_params = {**route["extracted_parameters"], **(parameters or {})}

    template = get_template(template_id)
    assumptions = template.get("assumptions", [])

    sql = render_template_sql(template_id, merged_params)
    rows = execute_sql(sql, db_path=db_path)

    validation = validate_result(template_id, rows, merged_params)

    response = {
        "status": "ok",
        "route_type": route_type,
        "template_id": template_id,
        "parameters": merged_params,
        "sql": sql,
        "row_count": len(rows),
        "rows": rows,
        "assumptions": assumptions,
        "validation_status": validation["status"],
        "validation": validation,
        "reason": route["reason"],
    }
    response["explanation"] = explain_answer(response)
    return _attach_audit(response, question, audit_path)
