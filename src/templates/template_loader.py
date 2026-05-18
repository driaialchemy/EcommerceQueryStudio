"""SQL template registry loader and renderer for governed ecommerce analytics."""

from __future__ import annotations

import re
from pathlib import Path

import yaml

DEFAULT_TEMPLATE_REGISTRY_PATH = Path("src/templates/template_registry.yaml")
DEFAULT_SQL_TEMPLATE_DIR = Path("src/templates/sql_templates")

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_PLACEHOLDER_RE = re.compile(r"\{(\w+)\}")

_REQUIRED_CONTRACT_FIELDS = {
    "template_id",
    "version",
    "owner",
    "business_question",
    "description",
    "sql_file",
    "supported_metrics",
    "required_tables",
    "default_dimensions",
    "allowed_dimensions",
    "allowed_filters",
    "time_grains",
    "parameters",
    "required_join_paths",
    "validation_rules",
    "assumptions",
    "fallback_behavior",
    "status",
}


def load_template_registry(
    registry_path: Path = DEFAULT_TEMPLATE_REGISTRY_PATH,
) -> dict:
    """Load all template contracts from YAML, keyed by template_id."""
    with registry_path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    return {t["template_id"]: t for t in data["templates"]}


def list_templates(
    registry_path: Path = DEFAULT_TEMPLATE_REGISTRY_PATH,
) -> list[str]:
    """Return a sorted list of all registered template IDs."""
    return sorted(load_template_registry(registry_path).keys())


def get_template(
    template_id: str,
    registry_path: Path = DEFAULT_TEMPLATE_REGISTRY_PATH,
) -> dict:
    """Retrieve a single template contract by ID.

    Raises KeyError for unknown template_id.
    """
    registry = load_template_registry(registry_path)
    if template_id not in registry:
        raise KeyError(
            f"Unknown template_id '{template_id}'. "
            f"Available templates: {sorted(registry.keys())}"
        )
    return registry[template_id]


def validate_template_contract(template: dict) -> None:
    """Validate that a template dict contains all required contract fields.

    Raises ValueError listing any missing fields.
    """
    missing = _REQUIRED_CONTRACT_FIELDS - set(template.keys())
    if missing:
        tid = template.get("template_id", "<unknown>")
        raise ValueError(
            f"Template '{tid}' is missing required contract fields: {sorted(missing)}"
        )


def validate_all_template_contracts(
    registry_path: Path = DEFAULT_TEMPLATE_REGISTRY_PATH,
) -> None:
    """Validate every template in the registry.

    Raises ValueError on the first contract that fails validation.
    """
    registry = load_template_registry(registry_path)
    for template in registry.values():
        validate_template_contract(template)


def get_template_sql(
    template_id: str,
    registry_path: Path = DEFAULT_TEMPLATE_REGISTRY_PATH,
    sql_dir: Path = DEFAULT_SQL_TEMPLATE_DIR,
) -> str:
    """Load the raw SQL string for a template.

    Raises FileNotFoundError if the SQL file declared in the contract is absent.
    """
    template = get_template(template_id, registry_path)
    sql_file = sql_dir / template["sql_file"]
    if not sql_file.exists():
        raise FileNotFoundError(
            f"SQL file for template '{template_id}' not found: {sql_file}"
        )
    return sql_file.read_text(encoding="utf-8")


def validate_template_parameters(template: dict, parameters: dict) -> None:
    """Validate a parameter dict against a template's declared parameter contract.

    Checks:
    - All required parameters are present.
    - No unknown parameters are supplied.
    - Date parameters match YYYY-MM-DD format.
    - Enum parameters match declared allowed_values.

    Raises ValueError with a descriptive message on the first violation.
    """
    declared = {p["name"]: p for p in template.get("parameters", [])}
    template_id = template.get("template_id", "<unknown>")

    missing = [
        name
        for name, spec in declared.items()
        if spec.get("required", False) and name not in parameters
    ]
    if missing:
        raise ValueError(
            f"Template '{template_id}' is missing required parameters: {missing}"
        )

    unknown = [k for k in parameters if k not in declared]
    if unknown:
        raise ValueError(
            f"Template '{template_id}' does not accept parameters: {unknown}. "
            f"Declared parameters: {sorted(declared.keys())}"
        )

    for name, value in parameters.items():
        spec = declared[name]
        param_type = spec.get("type", "string")

        if param_type == "date":
            if not _DATE_RE.match(str(value)):
                raise ValueError(
                    f"Parameter '{name}' in template '{template_id}' must be a date "
                    f"in YYYY-MM-DD format. Got: '{value}'"
                )

        if param_type == "enum":
            allowed = spec.get("allowed_values", [])
            if value not in allowed:
                raise ValueError(
                    f"Parameter '{name}' in template '{template_id}' must be one of "
                    f"{allowed}. Got: '{value}'"
                )


def render_template_sql(
    template_id: str,
    parameters: dict,
    registry_path: Path = DEFAULT_TEMPLATE_REGISTRY_PATH,
    sql_dir: Path = DEFAULT_SQL_TEMPLATE_DIR,
) -> str:
    """Render a governed SQL template by substituting validated named parameters.

    Parameters are validated against the template contract before substitution.
    Only declared parameters are accepted; SQL fragments are never permitted.

    Raises:
        KeyError:  unknown template_id.
        ValueError: parameter validation failure or unresolved SQL placeholder.
        FileNotFoundError: SQL file missing.
    """
    template = get_template(template_id, registry_path)
    validate_template_parameters(template, parameters)
    sql = get_template_sql(template_id, registry_path, sql_dir)
    return _safe_substitute(sql, parameters)


def _safe_substitute(sql: str, params: dict) -> str:
    """Replace {name} placeholders in SQL using only the supplied params dict.

    Raises ValueError if the SQL contains a placeholder that has no corresponding
    value in params (which would indicate a required param was missing from the SQL
    contract or the SQL file is inconsistent with the registry).
    """
    def _replace(match: re.Match) -> str:
        key = match.group(1)
        if key not in params:
            raise ValueError(
                f"SQL template contains placeholder '{{{key}}}' but no value was "
                f"provided for it. Check that the SQL file and template contract are "
                f"consistent."
            )
        return str(params[key])

    return _PLACEHOLDER_RE.sub(_replace, sql)
