"""Runtime pipeline: routes a question, renders SQL, executes against DuckDB."""

from __future__ import annotations

from pathlib import Path

from src.runtime.executor import DEFAULT_DB_PATH, execute_sql
from src.runtime.router import route_question
from src.templates.template_loader import get_template, render_template_sql
from src.validation.validators import validate_result


def answer_question(
    question: str,
    parameters: dict | None = None,
    db_path: Path = DEFAULT_DB_PATH,
) -> dict:
    """Answer a supported analytics question end-to-end.

    Steps:
    1. Route the question to a template (or clarify/unsupported).
    2. Merge routed default parameters with caller-supplied parameters
       (caller parameters take precedence).
    3. Render SQL via the template loader.
    4. Execute against DuckDB.
    5. Return a structured response.

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
    """
    route = route_question(question)
    route_type = route["route_type"]

    if route_type == "clarify":
        return {
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

    if route_type == "unsupported":
        return {
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

    template_id = route["template_id"]
    merged_params = {**route["extracted_parameters"], **(parameters or {})}

    template = get_template(template_id)
    assumptions = template.get("assumptions", [])

    sql = render_template_sql(template_id, merged_params)
    rows = execute_sql(sql, db_path=db_path)

    validation = validate_result(template_id, rows, merged_params)

    return {
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
