"""Tests for export_history repo functions."""
import pytest
from src.db.connection import get_connection
from src.db.schema import init_db
from src.db.export_history import record_export, list_recent_exports


@pytest.fixture
def empty_db(tmp_path):
    db_path = tmp_path / "test.db"
    init_db(db_path)
    return db_path


def test_record_export_inserts_row(empty_db):
    with get_connection(empty_db) as conn:
        export_id = record_export(
            conn,
            out_path="/tmp/Laporan April [filled].xlsx",
            template="/tmp/Laporan April.xlsx",
            year_month="2026-04",
            filled=130,
            na=12,
            not_found=0,
        )
    assert export_id > 0

    with get_connection(empty_db) as conn:
        row = conn.execute(
            "SELECT * FROM export_history WHERE id = ?", (export_id,)
        ).fetchone()
    assert row["out_path"] == "/tmp/Laporan April [filled].xlsx"
    assert row["year_month"] == "2026-04"
    assert row["filled"] == 130
    assert row["na"] == 12
    assert row["not_found"] == 0
    assert row["created_at"] is not None


def test_list_recent_exports_empty(empty_db):
    with get_connection(empty_db) as conn:
        rows = list_recent_exports(conn)
    assert rows == []


def test_list_recent_exports_orders_newest_first(empty_db):
    with get_connection(empty_db) as conn:
        # Insert 3 rows; SQLite created_at uses second-resolution so
        # we depend on id DESC tie-break for same-second inserts.
        id1 = record_export(conn, out_path="/a.xlsx", template="/t.xlsx", year_month="2026-01", filled=1, na=0, not_found=0)
        id2 = record_export(conn, out_path="/b.xlsx", template="/t.xlsx", year_month="2026-02", filled=2, na=0, not_found=0)
        id3 = record_export(conn, out_path="/c.xlsx", template="/t.xlsx", year_month="2026-03", filled=3, na=0, not_found=0)
        rows = list_recent_exports(conn)
    assert len(rows) == 3
    assert rows[0]["id"] == id3
    assert rows[1]["id"] == id2
    assert rows[2]["id"] == id1


def test_list_recent_exports_respects_limit(empty_db):
    with get_connection(empty_db) as conn:
        for i in range(10):
            record_export(conn, out_path=f"/f{i}.xlsx", template="/t.xlsx", year_month="2026-04", filled=i, na=0, not_found=0)
        rows = list_recent_exports(conn, limit=3)
    assert len(rows) == 3


def test_record_export_created_at_is_iso_utc(empty_db):
    """Stored created_at must be ISO-8601 UTC (matches imported_at convention)."""
    with get_connection(empty_db) as conn:
        export_id = record_export(
            conn, out_path="/a.xlsx", template="/t.xlsx",
            year_month="2026-04", filled=1, na=0, not_found=0,
        )
        row = conn.execute(
            "SELECT created_at FROM export_history WHERE id = ?", (export_id,)
        ).fetchone()
    # ISO format example: "2026-05-15T08:19:47+00:00"
    assert "T" in row["created_at"]
    assert "+00:00" in row["created_at"] or row["created_at"].endswith("Z")
