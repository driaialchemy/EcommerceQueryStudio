"""Schema and data dictionary registry for Maven Fuzzy Factory."""

from __future__ import annotations

from pathlib import Path

import duckdb

DEFAULT_DB_PATH = Path("data/processed/maven_fuzzy_factory.duckdb")

EXPECTED_TABLES = [
    "maven_fuzzy_factory_data_dictionary",
    "website_sessions",
    "website_pageviews",
    "orders",
    "order_items",
    "order_item_refunds",
    "products",
]

_TABLE_GRAINS: dict[str, str] = {
    "maven_fuzzy_factory_data_dictionary": "one row per table field",
    "website_sessions": "one row per website session",
    "website_pageviews": "one row per pageview",
    "orders": "one row per completed order",
    "order_items": "one row per purchased item",
    "order_item_refunds": "one row per refunded order item",
    "products": "one row per product",
}

# Join keys expressed as {table: [list of "table.col = other_table.col" strings]}
_ALLOWED_JOIN_KEYS: dict[str, list[str]] = {
    "website_sessions": [
        "website_sessions.website_session_id = website_pageviews.website_session_id",
        "website_sessions.website_session_id = orders.website_session_id",
    ],
    "website_pageviews": [
        "website_sessions.website_session_id = website_pageviews.website_session_id",
    ],
    "orders": [
        "website_sessions.website_session_id = orders.website_session_id",
        "orders.order_id = order_items.order_id",
        "products.product_id = orders.primary_product_id",
    ],
    "order_items": [
        "orders.order_id = order_items.order_id",
        "order_items.order_item_id = order_item_refunds.order_item_id",
        "products.product_id = order_items.product_id",
    ],
    "order_item_refunds": [
        "order_items.order_item_id = order_item_refunds.order_item_id",
    ],
    "products": [
        "products.product_id = orders.primary_product_id",
        "products.product_id = order_items.product_id",
    ],
    "maven_fuzzy_factory_data_dictionary": [],
}


def connect_db(db_path: Path = DEFAULT_DB_PATH) -> duckdb.DuckDBPyConnection:
    if not db_path.exists():
        raise FileNotFoundError(f"DuckDB database not found: {db_path}")
    return duckdb.connect(str(db_path))


def list_tables(db_path: Path = DEFAULT_DB_PATH) -> list[str]:
    with connect_db(db_path) as con:
        rows = con.execute("SHOW TABLES").fetchall()
    return [row[0] for row in rows]


def get_table_columns(
    table_name: str, db_path: Path = DEFAULT_DB_PATH
) -> list[dict]:
    with connect_db(db_path) as con:
        rows = con.execute(f"DESCRIBE {table_name}").fetchall()
    return [{"column_name": row[0], "column_type": row[1]} for row in rows]


def load_data_dictionary(db_path: Path = DEFAULT_DB_PATH) -> list[dict]:
    with connect_db(db_path) as con:
        cols = [
            desc[0]
            for desc in con.execute(
                "DESCRIBE maven_fuzzy_factory_data_dictionary"
            ).fetchall()
        ]
        rows = con.execute(
            "SELECT * FROM maven_fuzzy_factory_data_dictionary"
        ).fetchall()
    return [dict(zip(cols, row)) for row in rows]


def validate_expected_tables(db_path: Path = DEFAULT_DB_PATH) -> None:
    found = set(list_tables(db_path))
    missing = [t for t in EXPECTED_TABLES if t not in found]
    if missing:
        raise ValueError(
            f"Expected tables missing from {db_path}: {missing}"
        )


def build_schema_registry(db_path: Path = DEFAULT_DB_PATH) -> dict:
    validate_expected_tables(db_path)

    dd_rows = load_data_dictionary(db_path)
    # Index data-dictionary entries by (table_name, field_name) — key names vary,
    # so detect the relevant columns from the first row.
    dd_by_table: dict[str, list[dict]] = {}
    if dd_rows:
        sample = dd_rows[0]
        table_col = next(
            (k for k in sample if "table" in k.lower()), None
        )
        for entry in dd_rows:
            tname = entry.get(table_col, "") if table_col else ""
            dd_by_table.setdefault(tname, []).append(entry)

    registry: dict[str, dict] = {}
    with connect_db(db_path) as con:
        for table in EXPECTED_TABLES:
            columns = get_table_columns(table, db_path)
            row_count: int = con.execute(
                f"SELECT COUNT(*) FROM {table}"
            ).fetchone()[0]

            entry: dict = {
                "table_name": table,
                "grain": _TABLE_GRAINS.get(table, "unknown"),
                "row_count": row_count,
                "columns": columns,
                "allowed_join_keys": _ALLOWED_JOIN_KEYS.get(table, []),
            }

            if table in dd_by_table:
                entry["dictionary_fields"] = dd_by_table[table]

            registry[table] = entry

    return registry
