"""Layar Rekap Dinas: dua panel, segmented rentang, cetak."""
import pytest

from src.db.schema import init_db
from src.db.connection import get_connection
from src.db.employees import upsert_employee
from src.db.attendance import save_manual_attendance, set_reason
from src.db.settings import set_setting


def _row(conn, eid, tanggal, category):
    save_manual_attendance(
        conn, employee_id=eid, tanggal=tanggal, hari="Senin", tipe="Hari Kerja",
        jadwal=None, masuk="08:00", keluar="16:00", kerja_jam=8.0,
        lembur_jam=0.0, terlambat_menit=0, has_issue=0)
    rid = conn.execute(
        "SELECT id FROM attendance_records WHERE employee_id=? AND tanggal=?",
        (eid, tanggal)).fetchone()["id"]
    set_reason(conn, attendance_id=rid, category=category, detail=None)


@pytest.fixture
def dbp(tmp_path):
    p = tmp_path / "hr.db"
    init_db(p)
    with get_connection(p) as conn:
        set_setting(conn, "current_month", "2026-07")
        a = upsert_employee(conn, no_staff="S1", nama="Andi", dept="Ops")
        b = upsert_employee(conn, no_staff="S2", nama="Budi", dept="Sales")
        _row(conn, a, "2026-07-01", "tugas_lapangan")
        _row(conn, a, "2026-07-02", "tugas_paparan")
        _row(conn, b, "2026-07-06", "tugas_paparan")
        _row(conn, a, "2026-03-02", "tugas_lapangan")   # luar 3 bln, dalam tahun
    return p


@pytest.fixture
def screen_mod(monkeypatch, dbp):
    from src.ui.screens import dinas_recap as M
    monkeypatch.setattr(M, "DB_PATH", dbp)
    return M


def test_screen_builds_and_loads_both_panels(tk_root, screen_mod):
    s = screen_mod.DinasRecapScreen(tk_root)
    try:
        assert s._month == "2026-07"
        assert s._span == "year"
        assert [r["nama"] for r in s._month_rows] == ["Andi", "Budi"]
        assert s._rank_rows[0]["nama"] == "Andi"
        assert s._rank_rows[0]["rank"] == 1
    finally:
        s.destroy()


def test_changing_span_reloads_leaderboard_only(tk_root, screen_mod):
    s = screen_mod.DinasRecapScreen(tk_root)
    try:
        assert s._rank_rows[0]["total"] == 3      # year: Mar + Jul
        s._on_span("3 bln")
        assert s._span == "3m"
        assert s._rank_rows[0]["total"] == 2      # Mei–Jul saja
        assert [r["nama"] for r in s._month_rows] == ["Andi", "Budi"]
    finally:
        s.destroy()


def test_on_show_follows_active_month(tk_root, screen_mod, dbp):
    s = screen_mod.DinasRecapScreen(tk_root)
    try:
        with get_connection(dbp) as conn:
            set_setting(conn, "current_month", "2026-03")
        s.on_show()
        assert s._month == "2026-03"
        assert [r["nama"] for r in s._month_rows] == ["Andi"]
    finally:
        s.destroy()


def test_empty_state_does_not_crash(tk_root, monkeypatch, tmp_path):
    from src.ui.screens import dinas_recap as M
    p = tmp_path / "empty.db"
    init_db(p)
    with get_connection(p) as conn:
        set_setting(conn, "current_month", "2026-07")
    monkeypatch.setattr(M, "DB_PATH", p)
    s = M.DinasRecapScreen(tk_root)
    try:
        assert s._month_rows == []
        assert s._rank_rows == []
    finally:
        s.destroy()


def test_print_writes_html_and_opens_browser(tk_root, screen_mod, monkeypatch):
    opened = []
    monkeypatch.setattr(screen_mod, "open_html_in_browser",
                        lambda p: opened.append(p) or (True, "Test"))
    s = screen_mod.DinasRecapScreen(tk_root)
    try:
        s._do_print()
        assert len(opened) == 1
        html = opened[0].read_text(encoding="utf-8")
        assert "Rekap Dinas" in html
        assert "Andi" in html
    finally:
        s.destroy()
