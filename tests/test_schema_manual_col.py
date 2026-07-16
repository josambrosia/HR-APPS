import sqlite3

from src.db.schema import init_db


def _cols(db):
    conn = sqlite3.connect(db)
    try:
        return {r[1] for r in conn.execute("PRAGMA table_info(attendance_records)")}
    finally:
        conn.close()


def test_manual_edited_at_present_on_fresh_db(tmp_path):
    db = tmp_path / "hr.db"
    init_db(db)
    assert "manual_edited_at" in _cols(db)


def test_manual_edited_at_added_to_legacy_db(tmp_path):
    db = tmp_path / "hr.db"
    # Simulate a pre-existing DB WITHOUT the column.
    conn = sqlite3.connect(db)
    # Realistic pre-v23 attendance_records: has reason_* (touched by the v15
    # migration) but NOT manual_edited_at (the column v23 must ALTER-add).
    conn.executescript(
        """
        CREATE TABLE employees(id INTEGER PRIMARY KEY, no_staff TEXT UNIQUE, nama TEXT);
        CREATE TABLE attendance_records(
            id INTEGER PRIMARY KEY, employee_id INTEGER, tanggal TEXT,
            masuk TEXT, keluar TEXT, has_issue INTEGER,
            reason_category TEXT, reason_detail TEXT, resolved_at TEXT,
            UNIQUE(employee_id, tanggal));
        """
    )
    conn.commit()
    conn.close()

    assert "manual_edited_at" not in _cols(db)
    init_db(db)                       # must ALTER-add the column idempotently
    assert "manual_edited_at" in _cols(db)

    init_db(db)                       # second run is a no-op (no crash)
    assert "manual_edited_at" in _cols(db)
