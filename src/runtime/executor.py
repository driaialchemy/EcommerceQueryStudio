"""DuckDB executor for governed SQL templates."""

from __future__ import annotations

from pathlib import Path

import duckdb

DEFAULT_DB_PATH = Path("data/processed/maven_fuzzy_factory.duckdb")


def execute_sql(sql: str, db_path: Path = DEFAULT_DB_PATH) -> list[dict]:
    """Execute a read-only SELECT query against DuckDB and return rows as list[dict].

    Raises:
        FileNotFoundError: DuckDB file is missing.
        ValueError: SQL is not a SELECT statement.
    """
    if not db_path.exists():
        raise FileNotFoundError(
            f"DuckDB database not found at '{db_path}'. "
            "Run the ingestion step first to create it."
        )

    # Strip leading SQL line comments before checking statement type
    non_comment = "\n".join(
        line for line in sql.splitlines() if not line.strip().startswith("--")
    ).strip()
    if not non_comment.upper().startswith("SELECT"):
        raise ValueError(
            f"Only SELECT queries are permitted. Received statement starting with: "
            f"'{sql.strip()[:60]}'"
        )

    con = duckdb.connect(str(db_path), read_only=True)
    try:
        cursor = con.execute(sql)
        columns = [desc[0] for desc in cursor.description]
        rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
    finally:
        con.close()

    return rows
