import pytest

from src.db.schema import init_db
from src.db.connection import get_connection
from src.db.employees import upsert_employee
from src.db.attendance import (
    save_manual_attendance, set_reason, count_dinas_paparan_by_employee)


def _row(conn, eid, tanggal, category):
    save_manual_attendance(
        conn, employee_id=eid, tanggal=tanggal, hari="Senin", tipe="Hari Kerja",
        jadwal=None, masuk="08:00", keluar="16:00", kerja_jam=8.0,
        lembur_jam=0.0, terlambat_menit=0, has_issue=0)
    rid = conn.execute(
        "SELECT id FROM attendance_records WHERE employee_id=? AND tanggal=?",
        (eid, tanggal)).fetchone()["id"]
    if category:
        set_reason(conn, attendance_id=rid, category=category, detail=None)


@pytest.fixture
def db(tmp_path):
    p = tmp_path / "hr.db"
    init_db(p)
    with get_connection(p) as conn:
        a = upsert_employee(conn, no_staff="S1", nama="Andi", dept="Ops")
        b = upsert_employee(conn, no_staff="S2", nama="Budi", dept="Sales")
        c = upsert_employee(conn, no_staff="S3", nama="Cici", dept="HR")
        # Andi: 2 dinas + 1 paparan = 3
        _row(conn, a, "2026-07-01", "tugas_lapangan")
        _row(conn, a, "2026-07-02", "tugas_lapangan")
        _row(conn, a, "2026-07-03", "tugas_paparan")
        # Budi: 3 paparan = 3 (seri dengan Andi; Andi menang via dinas lebih banyak)
        _row(conn, b, "2026-07-06", "tugas_paparan")
        _row(conn, b, "2026-07-07", "tugas_paparan")
        _row(conn, b, "2026-07-08", "tugas_paparan")
        # Cici: hanya belajar & tanpa alasan -> tidak masuk rekap
        _row(conn, c, "2026-07-06", "tugas_belajar")
        _row(conn, c, "2026-07-07", None)
        # Di luar rentang Juli
        _row(conn, a, "2026-06-30", "tugas_lapangan")
        _row(conn, a, "2026-08-01", "tugas_paparan")
    yield p


def test_counts_split_dinas_and_paparan(db):
    with get_connection(db) as conn:
        rows = count_dinas_paparan_by_employee(conn, "2026-07-01", "2026-07-31")
    by_name = {r["nama"]: r for r in rows}
    assert by_name["Andi"]["dinas"] == 2
    assert by_name["Andi"]["paparan"] == 1
    assert by_name["Andi"]["total"] == 3
    assert by_name["Budi"]["dinas"] == 0
    assert by_name["Budi"]["paparan"] == 3


def test_includes_all_active_employees_even_with_zero(db):
    """Semua pegawai aktif tampil, termasuk yang nol dinas & nol paparan."""
    with get_connection(db) as conn:
        rows = count_dinas_paparan_by_employee(conn, "2026-07-01", "2026-07-31")
    by_name = {r["nama"]: r for r in rows}
    assert set(by_name) == {"Andi", "Budi", "Cici"}
    assert by_name["Cici"]["dinas"] == 0
    assert by_name["Cici"]["paparan"] == 0
    assert by_name["Cici"]["total"] == 0


def test_tugas_belajar_not_counted(db):
    with get_connection(db) as conn:
        rows = count_dinas_paparan_by_employee(conn, "2026-07-01", "2026-07-31")
    assert sum(r["total"] for r in rows) == 6  # 3 Andi + 3 Budi, belajar diabaikan


def test_date_bounds_are_inclusive_and_exclusive_outside(db):
    with get_connection(db) as conn:
        juni = count_dinas_paparan_by_employee(conn, "2026-06-01", "2026-06-30")
    totals = {r["nama"]: r["total"] for r in juni}
    # hanya baris 30 Juni milik Andi yang masuk rentang Juni
    assert totals == {"Andi": 1, "Budi": 0, "Cici": 0}


def test_order_total_desc_then_dinas_desc_then_nama(db):
    with get_connection(db) as conn:
        rows = count_dinas_paparan_by_employee(conn, "2026-07-01", "2026-07-31")
    # Andi & Budi sama-sama total 3; Andi punya dinas 2 -> di atas.
    # Cici (0) turun ke dasar.
    assert [r["nama"] for r in rows] == ["Andi", "Budi", "Cici"]


def test_includes_dept_and_employee_id(db):
    with get_connection(db) as conn:
        rows = count_dinas_paparan_by_employee(conn, "2026-07-01", "2026-07-31")
    assert rows[0]["dept"] == "Ops"
    assert isinstance(rows[0]["employee_id"], int)


def test_range_without_activity_still_lists_everyone_at_zero(db):
    with get_connection(db) as conn:
        rows = count_dinas_paparan_by_employee(conn, "2030-01-01", "2030-12-31")
    assert [r["nama"] for r in rows] == ["Andi", "Budi", "Cici"]
    assert all(r["total"] == 0 for r in rows)


def test_no_employees_returns_empty_list(tmp_path):
    p = tmp_path / "empty.db"
    init_db(p)
    with get_connection(p) as conn:
        assert count_dinas_paparan_by_employee(conn, "2026-01-01", "2026-12-31") == []


def test_inactive_employee_excluded(db):
    with get_connection(db) as conn:
        conn.execute("UPDATE employees SET active = 0 WHERE nama = 'Cici'")
        rows = count_dinas_paparan_by_employee(conn, "2026-07-01", "2026-07-31")
    assert "Cici" not in {r["nama"] for r in rows}
