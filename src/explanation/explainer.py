"""Deterministic answer explanation layer — no LLM calls."""

from __future__ import annotations


def _validation_summary_text(response: dict) -> str:
    validation = response.get("validation")
    if not validation or not isinstance(validation.get("checks"), list):
        return "not_applicable"
    checks = validation["checks"]
    passed = sum(1 for c in checks if c.get("status") == "passed")
    failed = sum(1 for c in checks if c.get("status") == "failed")
    return f"{passed} check(s) passed, {failed} check(s) failed"


def explain_answer(response: dict) -> dict:
    """Return a deterministic explanation dict for a pipeline response."""
    status = response.get("status")
    assumptions = list(response.get("assumptions") or [])

    if status == "ok":
        template_id = response.get("template_id", "unknown")
        row_count = response.get("row_count", 0)
        return {
            "summary": (
                f"Query executed using governed template '{template_id}' "
                f"and returned {row_count} row(s)."
            ),
            "assumptions": assumptions,
            "method": (
                "The answer was produced using a governed SQL template "
                "executed against DuckDB. No free-form SQL was generated."
            ),
            "validation_summary": _validation_summary_text(response),
            "limitations": [
                "Stage 8 explanations are deterministic and do not interpret "
                "business meaning beyond validated query output."
            ],
        }

    if status == "clarify":
        return {
            "summary": "The question needs clarification before execution.",
            "assumptions": assumptions,
            "method": "No SQL was executed.",
            "validation_summary": "not_applicable",
            "limitations": [
                "Ambiguous business terms require a specific metric before "
                "a governed template can be selected and executed."
            ],
        }

    # unsupported (and any unexpected status)
    return {
        "summary": (
            "The question is unsupported by the current governed template set."
        ),
        "assumptions": assumptions,
        "method": "No SQL was executed.",
        "validation_summary": "not_applicable",
        "limitations": [
            "The system only answers supported template-backed business questions. "
            "Free-form or unrecognised questions are not executed."
        ],
    }
