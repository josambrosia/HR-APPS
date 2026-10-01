"""v26: badge item nav Lembur (Open + Diajukan bulan aktif)."""
from src.db.attendance import upsert_attendance
from src.db.connection import get_connection
from src.db.employees import upsert_employee
from src.db.schema import init_db
from src.db.settings import set_setting


class _Badge:
    def __init__(self):
        self.text = None

    def configure(self, **kw):
        if "text" in kw:
            self.text = kw["text"]


class _Item:
    def __init__(self, badge):
        self._badge = badge


class _Dummy:
    def __init__(self, item):
        self._nav_items = {"Overtime": item}


def test_badge_counts_pending(tmp_path, monkeypatch):
    import src.ui.app as app_mod
    p = tmp_path / "a.db"
    init_db(p)
    with get_connection(p) as conn:
        set_setting(conn, "current_month", "2026-10")
        e = upsert_employee(conn, no_staff="1", nama="Agus")
        upsert_attendance(
            conn, employee_id=e, tanggal="2026-10-01", hari=None,
            tipe="Hari Kerja", jadwal=None, masuk="09:00", keluar="19:30",
            kerja_jam=None, lembur_jam=None, terlambat_menit=0,
            has_issue=0, imported_from="t")
    monkeypatch.setattr("src.config.DB_PATH", p)
    badge = _Badge()
    dummy = _Dummy(_Item(badge))
    app_mod.HRApp._refresh_overtime_badge(dummy)
    assert badge.text == "1"


def test_badge_empty_when_zero(tmp_path, monkeypatch):
    import src.ui.app as app_mod
    p = tmp_path / "a.db"
    init_db(p)
    with get_connection(p) as conn:
        set_setting(conn, "current_month", "2026-10")
    monkeypatch.setattr("src.config.DB_PATH", p)
    badge = _Badge()
    dummy = _Dummy(_Item(badge))
    app_mod.HRApp._refresh_overtime_badge(dummy)
    assert badge.text == ""
