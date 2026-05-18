"""Tests for CSV → DuckDB ingestion."""

import pytest
import duckdb
from pathlib import Path

from src.ingestion.load_csvs import (
    REQUIRED_CSVS,
    get_table_name,
    validate_required_csvs,
    load_csvs_to_duckdb,
)

TINY_CSV = "id,name\n1,foo\n2,bar\n"


def _write_all_csvs(raw_dir: Path, content: str = TINY_CSV) -> None:
    raw_dir.mkdir(parents=True, exist_ok=True)
    for csv_file in REQUIRED_CSVS:
        (raw_dir / csv_file).write_text(content)


def test_get_table_name():
    assert get_table_name("website_sessions.csv") == "website_sessions"
    assert get_table_name("orders.csv") == "orders"


def test_validate_missing_csvs_raises(tmp_path):
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    with pytest.raises(FileNotFoundError, match="Missing required CSVs"):
        validate_required_csvs(raw_dir)


def test_validate_all_present_passes(tmp_path):
    raw_dir = tmp_path / "raw"
    _write_all_csvs(raw_dir)
    validate_required_csvs(raw_dir)  # should not raise


def test_load_creates_duckdb_file(tmp_path):
    raw_dir = tmp_path / "raw"
    db_path = tmp_path / "processed" / "test.duckdb"
    _write_all_csvs(raw_dir)
    load_csvs_to_duckdb(raw_dir=raw_dir, db_path=db_path)
    assert db_path.exists()


def test_load_creates_expected_tables(tmp_path):
    raw_dir = tmp_path / "raw"
    db_path = tmp_path / "processed" / "test.duckdb"
    _write_all_csvs(raw_dir)
    load_csvs_to_duckdb(raw_dir=raw_dir, db_path=db_path)

    with duckdb.connect(str(db_path)) as con:
        tables = {row[0] for row in con.execute("SHOW TABLES").fetchall()}

    expected = {get_table_name(f) for f in REQUIRED_CSVS}
    assert expected.issubset(tables)


def test_load_returns_row_counts(tmp_path):
    raw_dir = tmp_path / "raw"
    db_path = tmp_path / "processed" / "test.duckdb"
    _write_all_csvs(raw_dir, content=TINY_CSV)
    counts = load_csvs_to_duckdb(raw_dir=raw_dir, db_path=db_path)

    assert set(counts.keys()) == {get_table_name(f) for f in REQUIRED_CSVS}
    for table, count in counts.items():
        assert count == 2, f"{table} expected 2 rows, got {count}"


def test_load_partial_csvs_raises(tmp_path):
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    (raw_dir / "orders.csv").write_text(TINY_CSV)
    with pytest.raises(FileNotFoundError):
        load_csvs_to_duckdb(raw_dir=raw_dir, db_path=tmp_path / "test.duckdb")
