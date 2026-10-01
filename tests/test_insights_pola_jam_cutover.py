import sqlite3

from src.core.insights import band_labels, pola_jam_masuk
from src.db.attendance import upsert_attendance
from src.db.connection import get_connection
from src.db.employees import upsert_employee
from src.db.schema import init_db


def test_band_labels_shift_with_start():
    labels = band_labels(9 * 60)
    assert labels[0][0] == "<08:45"
    assert labels[2] == ("09:00", "ontime")
    assert labels[7][0] == ">10:00"


def _legacy_db(p):
    with sqlite3.connect(p) as conn:
        conn.execute("CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT)")
        conn.execute("INSERT INTO settings VALUES ('schedule_start','08.00')")
        conn.execute("INSERT INTO settings VALUES ('schedule_end','16.00')")
        conn.commit()
    init_db(p)


def _att(conn, eid, tanggal, masuk):
    upsert_attendance(
        conn, employee_id=eid, tanggal=tanggal, hari=None, tipe="Hari Kerja",
        jadwal=None, masuk=masuk, keluar="16:00", kerja_jam=8.0,
        lembur_jam=0.0, terlambat_menit=0, has_issue=0, imported_from="t")


def test_pola_jam_cutover_uses_per_date_schedule(tmp_path):
    """September melintasi cutoff: baris 10 Sep dinilai relatif 08.00,
    baris 15 Sep relatif 09.00; label memakai jadwal akhir periode."""
    p = tmp_path / "i.db"
    _legacy_db(p)
    with get_connection(p) as conn:
        a = upsert_employee(conn, no_staff="1", nama="A")
        b = upsert_employee(conn, no_staff="2", nama="B")
        c = upsert_employee(conn, no_staff="3", nama="C")
        _att(conn, a, "2026-09-10", "08:00")   # rel 08.00 -> ontime (index 2)
        _att(conn, b, "2026-09-15", "08:00")   # rel 09.00 -> <08:45 (index 0)
        _att(conn, c, "2026-09-15", "09:00")   # rel 09.00 -> ontime (index 2)
        rows = pola_jam_masuk(conn, "2026-09-01", "2026-09-30")
    counts = {r["band"]: r["count"] for r in rows}
    assert counts["<08:45"] == 1
    assert counts["09:00"] == 2
    assert sum(counts.values()) == 3


def test_pola_jam_new_schedule_labels(tmp_path):
    p = tmp_path / "i.db"
    init_db(p)
    with get_connection(p) as conn:
        a = upsert_employee(conn, no_staff="1", nama="A")
        _att(conn, a, "2026-10-01", "09:00")
        rows = pola_jam_masuk(conn, "2026-10-01", "2026-10-31")
    counts = {r["band"]: r["count"] for r in rows}
    assert counts["09:00"] == 1
