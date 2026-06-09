import urllib.request

from src.db.schema import init_db
from src.db.connection import get_connection
from src.db.employees import upsert_employee
from src.db.attendance import upsert_attendance
import src.web.heatmap_server as hs


def test_server_serves_heatmap(temp_db_path, monkeypatch):
    monkeypatch.setattr(hs, "DB_PATH", temp_db_path)
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        a = upsert_employee(conn, no_staff="1", nama="ANDI", dept="IT")
        upsert_attendance(conn, employee_id=a, tanggal="2026-05-04", hari="Senin",
                          tipe="Hari Kerja", jadwal="", masuk="09:15", keluar="16:30",
                          kerja_jam=None, lembur_jam=None, terlambat_menit=75,
                          has_issue=0, imported_from="W")
    base = hs.ensure_started()
    assert base.startswith("http://127.0.0.1:")
    assert hs.ensure_started() == base  # idempotent
    html = urllib.request.urlopen(base + "/heatmap?month=2026-05", timeout=5).read().decode()
    assert "ANDI" in html and "Heatmap" in html
    pr = urllib.request.urlopen(
        base + "/heatmap/print?month=2026-05&scope=matrix", timeout=5).read().decode()
    assert pr and "ANDI" in pr
