"""Semantic metric registry for Maven Fuzzy Factory governed analytics."""

from __future__ import annotations

from pathlib import Path

import yaml

DEFAULT_METRICS_PATH = Path("src/semantic_layer/metrics.yaml")

_REQUIRED_FIELDS = {
    "metric_id",
    "version",
    "owner",
    "business_definition",
    "grain",
    "status",
    "required_tables",
    "validation_rules",
}


def load_metric_contracts(metrics_path: Path = DEFAULT_METRICS_PATH) -> dict:
    """Load all metric contracts from YAML, keyed by metric_id."""
    with metrics_path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    return {m["metric_id"]: m for m in data["metrics"]}


def get_metric(metric_id: str, metrics_path: Path = DEFAULT_METRICS_PATH) -> dict:
    """Return one metric contract by ID. Raises KeyError if not found."""
    contracts = load_metric_contracts(metrics_path)
    if metric_id not in contracts:
        raise KeyError(f"Unknown metric: '{metric_id}'. Available: {sorted(contracts)}")
    return contracts[metric_id]


def list_metrics(metrics_path: Path = DEFAULT_METRICS_PATH) -> list[str]:
    """Return a sorted list of all metric IDs."""
    return sorted(load_metric_contracts(metrics_path).keys())


def validate_metric_contract(metric: dict) -> None:
    """Raise ValueError with a descriptive message if a metric contract is invalid."""
    mid = metric.get("metric_id", "<unknown>")

    missing = _REQUIRED_FIELDS - metric.keys()
    if missing:
        raise ValueError(f"Metric '{mid}' is missing required fields: {sorted(missing)}")

    if not isinstance(metric["required_tables"], list) or not metric["required_tables"]:
        raise ValueError(f"Metric '{mid}': required_tables must be a non-empty list.")

    if not isinstance(metric["validation_rules"], list) or not metric["validation_rules"]:
        raise ValueError(f"Metric '{mid}': validation_rules must be a non-empty list.")

    has_base_table = "base_table" in metric
    has_components = "components" in metric
    if not has_base_table and not has_components:
        raise ValueError(f"Metric '{mid}': must have either base_table or components.")

    if has_components and not isinstance(metric["components"], list):
        raise ValueError(f"Metric '{mid}': components must be a list.")

    is_cross_table = len(metric["required_tables"]) > 1
    has_join_paths = bool(metric.get("join_paths"))
    has_alignment = bool(metric.get("alignment_rules"))
    if is_cross_table and not has_join_paths and not has_alignment:
        raise ValueError(
            f"Metric '{mid}': cross-table metric requires join_paths or alignment_rules."
        )

    if metric.get("status") == "approved" and "assumptions" not in metric:
        raise ValueError(f"Metric '{mid}': approved metrics must include assumptions.")


def validate_all_metric_contracts(metrics_path: Path = DEFAULT_METRICS_PATH) -> None:
    """Validate all metric contracts in the YAML file. Raises ValueError on first failure."""
    for metric in load_metric_contracts(metrics_path).values():
        validate_metric_contract(metric)


def get_metrics_by_table(
    table_name: str, metrics_path: Path = DEFAULT_METRICS_PATH
) -> list[dict]:
    """Return all metrics whose required_tables includes table_name."""
    return [
        m
        for m in load_metric_contracts(metrics_path).values()
        if table_name in m.get("required_tables", [])
    ]


def get_metrics_by_grain(
    grain: str, metrics_path: Path = DEFAULT_METRICS_PATH
) -> list[dict]:
    """Return all metrics with the given grain."""
    return [
        m
        for m in load_metric_contracts(metrics_path).values()
        if m.get("grain") == grain
    ]
