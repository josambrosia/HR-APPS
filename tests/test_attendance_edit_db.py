from src.db.schema import init_db
from src.db.connection import get_connection
from src.db.employees import upsert_employee
from src.db.attendance import (
    upsert_attendance, get_attendance, save_manual_attendance,
    delete_attendance, manual_rows_for_import,
)


def _emp(conn):
    return upsert_employee(conn, no_staff="S1", nama="Budi", dept="Prod")


def test_save_manual_sets_flag_and_preserves_reason(tmp_path):
    db = tmp_path / "hr.db"
    init_db(db)
    with get_connection(db) as c:
        eid = _emp(c)
        upsert_attendance(
            c, employee_id=eid, tanggal="2026-05-06", hari="Rabu",
            tipe="Hari Kerja", jadwal="", masuk="08:00", keluar=None,
            kerja_jam=0.0, lembur_jam=0.0, terlambat_menit=0, has_issue=1,
            imported_from="f.xls")
        c.execute("UPDATE attendance_records SET reason_category='izin_sakit' "
                  "WHERE employee_id=? AND tanggal=?", (eid, "2026-05-06"))
    with get_connection(db) as c:
        eid = _emp(c)
        save_manual_attendance(
            c, employee_id=eid, tanggal="2026-05-06", hari="Rabu",
            tipe="Hari Kerja", jadwal="", masuk="08:00", keluar="16:05",
            kerja_jam=8.1, lembur_jam=0.1, terlambat_menit=0, has_issue=0,
            now="2026-07-16T10:00:00")
    with get_connection(db) as c:
        row = get_attendance(c, employee_id=_emp(c), tanggal="2026-05-06")
    assert row["keluar"] == "16:05"
    assert row["has_issue"] == 0
    assert row["manual_edited_at"] == "2026-07-16T10:00:00"
    assert row["reason_category"] == "izin_sakit"          # preserved


def test_import_upsert_clears_manual_flag(tmp_path):
    db = tmp_path / "hr.db"
    init_db(db)
    with get_connection(db) as c:
        eid = _emp(c)
        save_manual_attendance(
            c, employee_id=eid, tanggal="2026-05-06", hari="Rabu",
            tipe="Hari Kerja", jadwal="", masuk="08:00", keluar="16:05",
            kerja_jam=8.1, lembur_jam=0.1, terlambat_menit=0, has_issue=0,
            now="2026-07-16T10:00:00")
    with get_connection(db) as c:
        eid = _emp(c)
        upsert_attendance(
            c, employee_id=eid, tanggal="2026-05-06", hari="Rabu",
            tipe="Hari Kerja", jadwal="", masuk="08:00", keluar=None,
            kerja_jam=0.0, lembur_jam=0.0, terlambat_menit=0, has_issue=1,
            imported_from="f2.xls")
    with get_connection(db) as c:
        row = get_attendance(c, employee_id=_emp(c), tanggal="2026-05-06")
    assert row["manual_edited_at"] is None                 # import overwrite clears flag


def test_delete_attendance(tmp_path):
    db = tmp_path / "hr.db"
    init_db(db)
    with get_connection(db) as c:
        eid = _emp(c)
        save_manual_attendance(
            c, employee_id=eid, tanggal="2026-05-06", hari="Rabu",
            tipe="Hari Kerja", jadwal="", masuk="08:00", keluar="16:00",
            kerja_jam=8.0, lembur_jam=0.0, terlambat_menit=0, has_issue=0)
        delete_attendance(c, employee_id=eid, tanggal="2026-05-06")
        assert get_attendance(c, employee_id=eid, tanggal="2026-05-06") is None


def test_manual_rows_for_import_only_returns_flagged(tmp_path):
    db = tmp_path / "hr.db"
    init_db(db)
    with get_connection(db) as c:
        eid = _emp(c)
        # one manual-edited row, one plain imported row
        save_manual_attendance(
            c, employee_id=eid, tanggal="2026-05-06", hari="Rabu",
            tipe="Hari Kerja", jadwal="", masuk="08:00", keluar="16:05",
            kerja_jam=8.1, lembur_jam=0.1, terlambat_menit=0, has_issue=0)
        upsert_attendance(
            c, employee_id=eid, tanggal="2026-05-07", hari="Kamis",
            tipe="Hari Kerja", jadwal="", masuk="08:00", keluar="16:00",
            kerja_jam=8.0, lembur_jam=0.0, terlambat_menit=0, has_issue=0,
            imported_from="f.xls")
    with get_connection(db) as c:
        got = manual_rows_for_import(c, ["S1"], "2026-05-01", "2026-05-31")
    assert set(got.keys()) == {("S1", "2026-05-06")}
    assert got[("S1", "2026-05-06")]["nama"] == "Budi"
    assert got[("S1", "2026-05-06")]["keluar"] == "16:05"
