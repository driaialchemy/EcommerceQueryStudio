"""Tests for schema_registry."""

from __future__ import annotations

import pytest
import duckdb

from src.semantic_layer.schema_registry import (
    DEFAULT_DB_PATH,
    EXPECTED_TABLES,
    build_schema_registry,
    connect_db,
    get_table_columns,
    list_tables,
    load_data_dictionary,
    validate_expected_tables,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_db(tmp_path, tables: list[str] | None = None) -> "Path":
    from pathlib import Path

    db_path = tmp_path / "test.duckdb"
    tables = tables or EXPECTED_TABLES
    with duckdb.connect(str(db_path)) as con:
        for table in tables:
            if table == "maven_fuzzy_factory_data_dictionary":
                con.execute(
                    f"CREATE TABLE {table} (table_name VARCHAR, field_name VARCHAR, description VARCHAR)"
                )
                con.execute(
                    f"INSERT INTO {table} VALUES ('website_sessions', 'website_session_id', 'PK')"
                )
            else:
                con.execute(
                    f"CREATE TABLE {table} (id INTEGER, name VARCHAR)"
                )
                con.execute(f"INSERT INTO {table} VALUES (1, 'test')")
    return db_path


# ---------------------------------------------------------------------------
# connect_db
# ---------------------------------------------------------------------------

def test_connect_db_missing_file_raises(tmp_path):
    missing = tmp_path / "no_such.duckdb"
    with pytest.raises(FileNotFoundError, match="not found"):
        connect_db(missing)


# ---------------------------------------------------------------------------
# list_tables / validate_expected_tables
# ---------------------------------------------------------------------------

def test_list_tables_returns_created_tables(tmp_path):
    db = _make_db(tmp_path)
    tables = list_tables(db)
    assert set(EXPECTED_TABLES).issubset(set(tables))


def test_validate_expected_tables_passes(tmp_path):
    db = _make_db(tmp_path)
    validate_expected_tables(db)  # should not raise


def test_validate_expected_tables_fails_when_missing(tmp_path):
    db = _make_db(tmp_path, tables=["products"])
    with pytest.raises(ValueError, match="missing"):
        validate_expected_tables(db)


# ---------------------------------------------------------------------------
# get_table_columns
# ---------------------------------------------------------------------------

def test_get_table_columns_returns_names_and_types(tmp_path):
    db = _make_db(tmp_path)
    cols = get_table_columns("products", db)
    assert isinstance(cols, list)
    assert len(cols) == 2
    col_names = [c["column_name"] for c in cols]
    assert "id" in col_names
    assert "name" in col_names
    for col in cols:
        assert "column_type" in col


# ---------------------------------------------------------------------------
# load_data_dictionary
# ---------------------------------------------------------------------------

def test_load_data_dictionary_returns_rows(tmp_path):
    db = _make_db(tmp_path)
    rows = load_data_dictionary(db)
    assert len(rows) >= 1
    assert "table_name" in rows[0]


# ---------------------------------------------------------------------------
# build_schema_registry
# ---------------------------------------------------------------------------

def test_build_schema_registry_includes_expected_keys(tmp_path):
    db = _make_db(tmp_path)
    reg = build_schema_registry(db)
    for table in EXPECTED_TABLES:
        assert table in reg
        entry = reg[table]
        assert "table_name" in entry
        assert "columns" in entry
        assert "grain" in entry
        assert "row_count" in entry
        assert "allowed_join_keys" in entry


def test_build_schema_registry_includes_grain(tmp_path):
    db = _make_db(tmp_path)
    reg = build_schema_registry(db)
    assert reg["website_sessions"]["grain"] == "one row per website session"
    assert reg["orders"]["grain"] == "one row per completed order"
    assert reg["products"]["grain"] == "one row per product"


def test_build_schema_registry_includes_row_count(tmp_path):
    db = _make_db(tmp_path)
    reg = build_schema_registry(db)
    # Each non-dict table has exactly 1 row inserted
    assert reg["products"]["row_count"] == 1
    assert reg["orders"]["row_count"] == 1
    assert reg["maven_fuzzy_factory_data_dictionary"]["row_count"] == 1


def test_build_schema_registry_includes_join_keys(tmp_path):
    db = _make_db(tmp_path)
    reg = build_schema_registry(db)
    ws_joins = reg["website_sessions"]["allowed_join_keys"]
    assert any("website_pageviews" in k for k in ws_joins)
    assert any("orders" in k for k in ws_joins)
    # data dictionary has no join keys
    assert reg["maven_fuzzy_factory_data_dictionary"]["allowed_join_keys"] == []


def test_build_schema_registry_includes_dictionary_fields(tmp_path):
    db = _make_db(tmp_path)
    reg = build_schema_registry(db)
    # The data dict row has table_name='website_sessions'
    assert "dictionary_fields" in reg["website_sessions"]
