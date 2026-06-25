"""Migration test for the multi-table dataset model (c3d4e5f6a7b8): a legacy single-CSV
data_sources row must back-fill to one dataset_tables child (parquet_path preserved), gain a
parquet:/// uri and type='parquet'; downgrade must reverse cleanly."""
import sqlite3
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config

from data_analysis_agent.tools.table_naming import sql_table_name

_REPO = Path(__file__).resolve().parents[3]
_PREV = "b8e1f0a2c3d4"  # revision before the dataset migration


def _cfg(db_path: Path) -> Config:
    cfg = Config(str(_REPO / "alembic.ini"))
    cfg.set_main_option("script_location", str(_REPO / "alembic"))
    return cfg


@pytest.fixture
def at_prev_revision(tmp_path, monkeypatch):
    db_path = tmp_path / "mig.db"
    monkeypatch.setenv("DATAANALYSIS_DATABASE_URL", f"sqlite:///{db_path}")
    cfg = _cfg(db_path)
    command.upgrade(cfg, _PREV)
    return cfg, db_path


def test_backfill_legacy_row_to_dataset_and_table(at_prev_revision):
    cfg, db_path = at_prev_revision
    # Seed a legacy single-CSV dataset row (schema at b8e1f0a2c3d4 has no uri column).
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO data_sources (id, name, type, parquet_path, row_count, column_names_json, "
        "schema_json, tool_description, capability_description, created_at) "
        "VALUES ('ds1', 'Sales Report.csv', 'csv', '/data/parquet/ds1.parquet', 3, "
        "'[\"region\",\"sales\"]', '[]', 'tool desc', 'cap desc', '2026-01-01 00:00:00')"
    )
    conn.commit()
    conn.close()

    command.upgrade(cfg, "head")  # applies c3d4e5f6a7b8

    conn = sqlite3.connect(db_path)
    ds = dict(zip(["type", "uri"], conn.execute("SELECT type, uri FROM data_sources WHERE id='ds1'").fetchone()))
    assert ds["type"] == "parquet"
    assert ds["uri"] == "parquet:///Sales%20Report.csv"

    rows = conn.execute(
        "SELECT dataset_id, table_name, parquet_path, capability_description FROM dataset_tables WHERE dataset_id='ds1'"
    ).fetchall()
    conn.close()
    assert len(rows) == 1
    dataset_id, table_name, parquet_path, cap = rows[0]
    assert dataset_id == "ds1"
    assert table_name == sql_table_name("Sales Report.csv")  # 'sales_report'
    assert parquet_path == "/data/parquet/ds1.parquet"  # preserved, no file move
    assert cap == "cap desc"


def test_downgrade_reverses(at_prev_revision):
    cfg, db_path = at_prev_revision
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO data_sources (id, name, type, parquet_path, created_at) "
        "VALUES ('ds2', 'x.csv', 'csv', '/p/ds2.parquet', '2026-01-01 00:00:00')"
    )
    conn.commit()
    conn.close()

    command.upgrade(cfg, "head")
    command.downgrade(cfg, _PREV)

    conn = sqlite3.connect(db_path)
    tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")]
    ds_cols = [r[1] for r in conn.execute("PRAGMA table_info(data_sources)")]
    dtype = conn.execute("SELECT type FROM data_sources WHERE id='ds2'").fetchone()[0]
    conn.close()
    assert "dataset_tables" not in tables
    assert "uri" not in ds_cols
    assert dtype == "csv"  # restored
