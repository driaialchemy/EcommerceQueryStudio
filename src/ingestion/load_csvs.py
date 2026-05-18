"""Load Maven Fuzzy Factory CSVs into DuckDB."""

from __future__ import annotations

import argparse
from pathlib import Path

import duckdb

REQUIRED_CSVS = [
    "maven_fuzzy_factory_data_dictionary.csv",
    "website_sessions.csv",
    "website_pageviews.csv",
    "orders.csv",
    "order_items.csv",
    "order_item_refunds.csv",
    "products.csv",
]

DEFAULT_RAW_DIR = Path("data/raw")
DEFAULT_DB_PATH = Path("data/processed/maven_fuzzy_factory.duckdb")


def get_table_name(csv_filename: str) -> str:
    return Path(csv_filename).stem


def validate_required_csvs(raw_dir: Path) -> None:
    missing = [f for f in REQUIRED_CSVS if not (raw_dir / f).exists()]
    if missing:
        raise FileNotFoundError(f"Missing required CSVs in {raw_dir}: {missing}")


def load_csvs_to_duckdb(
    raw_dir: Path = DEFAULT_RAW_DIR,
    db_path: Path = DEFAULT_DB_PATH,
) -> dict[str, int]:
    validate_required_csvs(raw_dir)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    counts: dict[str, int] = {}
    with duckdb.connect(str(db_path)) as con:
        for csv_file in REQUIRED_CSVS:
            table = get_table_name(csv_file)
            csv_path = raw_dir / csv_file
            con.execute(
                f"CREATE OR REPLACE TABLE {table} AS SELECT * FROM read_csv_auto('{csv_path.as_posix()}')"
            )
            counts[table] = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]

    return counts


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Load CSVs into DuckDB")
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR)
    parser.add_argument("--db-path", type=Path, default=DEFAULT_DB_PATH)
    args = parser.parse_args()

    row_counts = load_csvs_to_duckdb(raw_dir=args.raw_dir, db_path=args.db_path)
    for table, count in row_counts.items():
        print(f"  {table}: {count:,} rows")
