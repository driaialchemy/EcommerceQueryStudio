"""Tests for src/templates/template_loader.py — Stage 5."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
import yaml

from src.templates.template_loader import (
    DEFAULT_SQL_TEMPLATE_DIR,
    DEFAULT_TEMPLATE_REGISTRY_PATH,
    get_template,
    get_template_sql,
    list_templates,
    load_template_registry,
    render_template_sql,
    validate_all_template_contracts,
    validate_template_contract,
    validate_template_parameters,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

MVP_TEMPLATE_IDS = [
    "conversion_by_channel",
    "conversion_by_device",
    "revenue_by_campaign",
    "refund_rate_by_product",
    "monthly_revenue_trend",
]

_MINIMAL_TEMPLATE = {
    "template_id": "test_tmpl",
    "version": "1.0",
    "owner": "analytics",
    "business_question": "A question?",
    "description": "A description.",
    "sql_file": "test_tmpl.sql",
    "supported_metrics": ["sessions"],
    "required_tables": ["website_sessions"],
    "default_dimensions": ["utm_source"],
    "allowed_dimensions": ["utm_source"],
    "allowed_filters": ["start_date", "end_date"],
    "time_grains": ["month"],
    "parameters": [
        {"name": "start_date", "required": True, "type": "date"},
        {"name": "end_date", "required": True, "type": "date"},
    ],
    "required_join_paths": [],
    "validation_rules": ["Rule one."],
    "assumptions": ["Assumption one."],
    "fallback_behavior": "Return empty result.",
    "status": "approved",
}


def _make_registry_yaml(templates: list[dict]) -> str:
    return yaml.dump({"version": "1", "templates": templates})


def _make_sql(placeholders: list[str]) -> str:
    conditions = " AND ".join(f"col >= '{{{p}}}'" for p in placeholders)
    return f"SELECT 1 WHERE {conditions}"


# ---------------------------------------------------------------------------
# Registry loading
# ---------------------------------------------------------------------------


def test_load_template_registry_returns_dict():
    registry = load_template_registry()
    assert isinstance(registry, dict)
    assert len(registry) >= 5


def test_list_templates_returns_all_mvp_ids():
    ids = list_templates()
    for tid in MVP_TEMPLATE_IDS:
        assert tid in ids


def test_list_templates_is_sorted():
    ids = list_templates()
    assert ids == sorted(ids)


# ---------------------------------------------------------------------------
# get_template
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("template_id", MVP_TEMPLATE_IDS)
def test_get_template_returns_contract(template_id):
    tmpl = get_template(template_id)
    assert tmpl["template_id"] == template_id
    assert tmpl["status"] == "approved"


def test_get_template_unknown_raises_key_error():
    with pytest.raises(KeyError, match="Unknown template_id"):
        get_template("nonexistent_template")


# ---------------------------------------------------------------------------
# validate_template_contract
# ---------------------------------------------------------------------------


def test_validate_template_contract_passes_for_minimal():
    validate_template_contract(_MINIMAL_TEMPLATE)


def test_validate_template_contract_fails_on_missing_field():
    bad = {k: v for k, v in _MINIMAL_TEMPLATE.items() if k != "owner"}
    with pytest.raises(ValueError, match="missing required contract fields"):
        validate_template_contract(bad)


def test_validate_all_template_contracts_passes_for_real_registry():
    validate_all_template_contracts()  # must not raise


# ---------------------------------------------------------------------------
# get_template_sql
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("template_id", MVP_TEMPLATE_IDS)
def test_get_template_sql_loads_file(template_id):
    sql = get_template_sql(template_id)
    assert isinstance(sql, str)
    assert len(sql) > 0


def test_get_template_sql_missing_file_raises(tmp_path):
    registry_yaml = tmp_path / "registry.yaml"
    sql_dir = tmp_path / "sql"
    sql_dir.mkdir()

    tmpl = dict(_MINIMAL_TEMPLATE, template_id="no_file_tmpl", sql_file="missing.sql")
    registry_yaml.write_text(_make_registry_yaml([tmpl]), encoding="utf-8")

    with pytest.raises(FileNotFoundError, match="no_file_tmpl"):
        get_template_sql("no_file_tmpl", registry_path=registry_yaml, sql_dir=sql_dir)


# ---------------------------------------------------------------------------
# validate_template_parameters
# ---------------------------------------------------------------------------


def test_validate_parameters_passes_with_valid_dates():
    validate_template_parameters(
        _MINIMAL_TEMPLATE, {"start_date": "2023-01-01", "end_date": "2023-12-31"}
    )


def test_validate_parameters_catches_missing_required():
    with pytest.raises(ValueError, match="missing required parameters"):
        validate_template_parameters(_MINIMAL_TEMPLATE, {"start_date": "2023-01-01"})


def test_validate_parameters_catches_unknown_parameter():
    with pytest.raises(ValueError, match="does not accept parameters"):
        validate_template_parameters(
            _MINIMAL_TEMPLATE,
            {
                "start_date": "2023-01-01",
                "end_date": "2023-12-31",
                "injected_fragment": "DROP TABLE orders",
            },
        )


def test_validate_parameters_rejects_bad_date_format():
    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        validate_template_parameters(
            _MINIMAL_TEMPLATE,
            {"start_date": "01/01/2023", "end_date": "2023-12-31"},
        )


def test_validate_parameters_rejects_partial_date():
    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        validate_template_parameters(
            _MINIMAL_TEMPLATE,
            {"start_date": "2023-1-1", "end_date": "2023-12-31"},
        )


def test_validate_parameters_enum_valid(tmp_path):
    tmpl = dict(
        _MINIMAL_TEMPLATE,
        parameters=[
            {"name": "start_date", "required": True, "type": "date"},
            {"name": "end_date", "required": True, "type": "date"},
            {
                "name": "device_type",
                "required": False,
                "type": "enum",
                "allowed_values": ["desktop", "mobile", "tablet"],
            },
        ],
    )
    validate_template_parameters(
        tmpl, {"start_date": "2023-01-01", "end_date": "2023-12-31", "device_type": "mobile"}
    )


def test_validate_parameters_enum_invalid(tmp_path):
    tmpl = dict(
        _MINIMAL_TEMPLATE,
        parameters=[
            {"name": "start_date", "required": True, "type": "date"},
            {"name": "end_date", "required": True, "type": "date"},
            {
                "name": "device_type",
                "required": False,
                "type": "enum",
                "allowed_values": ["desktop", "mobile", "tablet"],
            },
        ],
    )
    with pytest.raises(ValueError, match="must be one of"):
        validate_template_parameters(
            tmpl,
            {
                "start_date": "2023-01-01",
                "end_date": "2023-12-31",
                "device_type": "fridge",
            },
        )


# ---------------------------------------------------------------------------
# render_template_sql
# ---------------------------------------------------------------------------


def test_render_template_sql_substitutes_placeholders(tmp_path):
    registry_yaml = tmp_path / "registry.yaml"
    sql_dir = tmp_path / "sql"
    sql_dir.mkdir()

    tmpl = dict(_MINIMAL_TEMPLATE)
    registry_yaml.write_text(_make_registry_yaml([tmpl]), encoding="utf-8")
    (sql_dir / "test_tmpl.sql").write_text(
        "SELECT 1 WHERE dt >= '{start_date}' AND dt < '{end_date}'",
        encoding="utf-8",
    )

    rendered = render_template_sql(
        "test_tmpl",
        {"start_date": "2023-01-01", "end_date": "2023-12-31"},
        registry_path=registry_yaml,
        sql_dir=sql_dir,
    )
    assert "2023-01-01" in rendered
    assert "2023-12-31" in rendered
    assert "{start_date}" not in rendered
    assert "{end_date}" not in rendered


def test_render_template_sql_rejects_unknown_parameter(tmp_path):
    registry_yaml = tmp_path / "registry.yaml"
    sql_dir = tmp_path / "sql"
    sql_dir.mkdir()

    tmpl = dict(_MINIMAL_TEMPLATE)
    registry_yaml.write_text(_make_registry_yaml([tmpl]), encoding="utf-8")
    (sql_dir / "test_tmpl.sql").write_text(
        "SELECT 1 WHERE dt >= '{start_date}' AND dt < '{end_date}'",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="does not accept parameters"):
        render_template_sql(
            "test_tmpl",
            {
                "start_date": "2023-01-01",
                "end_date": "2023-12-31",
                "evil": "DROP TABLE orders",
            },
            registry_path=registry_yaml,
            sql_dir=sql_dir,
        )


# ---------------------------------------------------------------------------
# Structural contract checks on real templates
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("template_id", ["conversion_by_channel", "conversion_by_device"])
def test_conversion_templates_declare_left_join(template_id):
    tmpl = get_template(template_id)
    join_paths = " ".join(tmpl.get("required_join_paths", []))
    assert "LEFT JOIN" in join_paths.upper(), (
        f"{template_id} must declare a LEFT JOIN path in required_join_paths"
    )


def test_refund_rate_uses_order_items_and_refunds():
    tmpl = get_template("refund_rate_by_product")
    assert "order_items" in tmpl["required_tables"]
    assert "order_item_refunds" in tmpl["required_tables"]


def test_refund_rate_join_paths_include_left_join_to_refunds():
    tmpl = get_template("refund_rate_by_product")
    joined = " ".join(tmpl.get("required_join_paths", []))
    assert "order_item_refunds" in joined
    assert "LEFT JOIN" in joined.upper()


@pytest.mark.parametrize("template_id", MVP_TEMPLATE_IDS)
def test_no_mvp_template_uses_website_pageviews(template_id):
    tmpl = get_template(template_id)
    assert "website_pageviews" not in tmpl.get("required_tables", [])


@pytest.mark.parametrize("template_id", MVP_TEMPLATE_IDS)
def test_no_mvp_sql_references_website_pageviews(template_id):
    sql = get_template_sql(template_id).lower()
    assert "website_pageviews" not in sql


@pytest.mark.parametrize("template_id", MVP_TEMPLATE_IDS)
def test_all_mvp_templates_have_approved_status(template_id):
    assert get_template(template_id)["status"] == "approved"


@pytest.mark.parametrize("template_id", MVP_TEMPLATE_IDS)
def test_all_mvp_sql_contains_date_placeholders(template_id):
    sql = get_template_sql(template_id)
    assert "{start_date}" in sql
    assert "{end_date}" in sql


# ---------------------------------------------------------------------------
# Optional: live DuckDB smoke test
# ---------------------------------------------------------------------------

_DB_PATH = Path("data/processed/maven_fuzzy_factory.duckdb")


@pytest.mark.skipif(not _DB_PATH.exists(), reason="DuckDB file not present")
def test_render_and_execute_conversion_by_channel_against_duckdb():
    import duckdb

    rendered = render_template_sql(
        "conversion_by_channel",
        {"start_date": "2012-01-01", "end_date": "2015-01-01"},
    )

    con = duckdb.connect(str(_DB_PATH), read_only=True)
    result = con.execute(rendered).fetchall()
    con.close()

    assert isinstance(result, list)
    # Each row: (utm_source, utm_campaign, sessions, orders, conversion_rate)
    for row in result:
        assert len(row) == 5
        sessions = row[2]
        orders = row[3]
        assert sessions >= orders >= 0
