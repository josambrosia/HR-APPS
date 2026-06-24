# tests/test_heatmap_screen.py
import os
import src.ui.screens.heatmap as mod
from src.db.schema import init_db
from src.db.employees import upsert_employee
from src.db.attendance import upsert_attendance
from src.db.connection import get_connection


def _seed_two(p):
    init_db(p)
    with get_connection(p) as conn:
        a = upsert_employee(conn, no_staff="1", nama="ANDI", dept="IT")
        b = upsert_employee(conn, no_staff="2", nama="BUDI", dept="HR")
        # ANDI: a severe-late day (75') -> needs_attention + lower pct
        upsert_attendance(conn, employee_id=a, tanggal="2026-05-04", hari="Senin",
                          tipe="Hari Kerja", jadwal="", masuk="09:15", keluar="16:30",
                          kerja_jam=None, lembur_jam=None, terlambat_menit=75,
                          has_issue=0, imported_from="W")
        # BUDI: several on-time days -> higher pct
        for tgl, hari in (("2026-05-04", "Senin"), ("2026-05-05", "Selasa"),
                          ("2026-05-06", "Rabu"), ("2026-05-07", "Kamis")):
            upsert_attendance(conn, employee_id=b, tanggal=tgl, hari=hari,
                              tipe="Hari Kerja", jadwal="", masuk="08:03", keluar="16:10",
                              kerja_jam=None, lembur_jam=None, terlambat_menit=3,
                              has_issue=0, imported_from="W")
    return a, b


def _screen(monkeypatch, tk_root, p):
    monkeypatch.setattr(mod, "DB_PATH", p)
    with get_connection(p) as conn:
        from src.db.settings import set_setting
        set_setting(conn, "current_month", "2026-05")
    s = mod.HeatmapScreen(tk_root)
    tk_root.update_idletasks()
    return s


def test_constructs_and_paints_cells(tmp_path, monkeypatch, tk_root):
    p = tmp_path / "h.db"
    _seed_two(p)
    s = _screen(monkeypatch, tk_root, p)
    # 31 days in May x 2 employees = 62 day-cell rectangles
    assert len(s._canvas.find_withtag("cellrect")) == 62
    s.destroy()


def test_search_filters(tmp_path, monkeypatch, tk_root):
    p = tmp_path / "h.db"
    _seed_two(p)
    s = _screen(monkeypatch, tk_root, p)
    s._search.set("ANDI")
    tk_root.update_idletasks()
    assert [e["nama"] for e in s._visible_employees] == ["ANDI"]
    s._search.set("ZZZ")
    tk_root.update_idletasks()
    assert s._visible_employees == []
    s.destroy()


def test_sort_by_attendance(tmp_path, monkeypatch, tk_root):
    p = tmp_path / "h.db"
    _seed_two(p)
    s = _screen(monkeypatch, tk_root, p)
    s._on_sort("Kehadiran terendah")
    tk_root.update_idletasks()
    # ANDI (1 attended day) has the lower % than BUDI (4) -> first
    assert s._visible_employees[0]["nama"] == "ANDI"
    s.destroy()


def test_click_detail_and_print(tmp_path, monkeypatch, tk_root):
    p = tmp_path / "h.db"
    _seed_two(p)
    s = _screen(monkeypatch, tk_root, p)
    s._show_detail({"date": 4, "label": "Terlambat Berat", "masuk": "09:15",
                    "keluar": "16:30", "telat": 75, "alasan": "—"})
    assert "Terlambat Berat" in s._detail_var.get()
    captured = {}
    monkeypatch.setattr(mod, "open_html_in_browser", lambda path: captured.setdefault("p", path))
    s._do_print("full", "inc")
    assert os.path.exists(captured["p"])
    with open(captured["p"], encoding="utf-8") as f:
        assert "Mei 2026" in f.read()
    s.destroy()


def test_heatmap_uses_searchbar_shortcuts_helper(temp_db_path, monkeypatch, tk_root):
    import src.ui.screens.heatmap as mod
    monkeypatch.setattr(mod, "DB_PATH", temp_db_path)
    init_db(temp_db_path)
    screen = mod.HeatmapScreen(tk_root)
    tk_root.update_idletasks()
    assert getattr(screen._search, "_click_bind_id", None) is not None
    assert not hasattr(screen, "_on_click_outside_search")
    screen.destroy()


def test_heatmap_destroy_cleans_up_search_bindings(temp_db_path, monkeypatch, tk_root):
    """Heatmap's own <Destroy> (tooltip) binding must NOT clobber the
    SearchBar's <Destroy> cleanup — both run, so search bindings don't leak."""
    import src.ui.screens.heatmap as mod
    monkeypatch.setattr(mod, "DB_PATH", temp_db_path)
    init_db(temp_db_path)
    screen = mod.HeatmapScreen(tk_root)
    tk_root.update_idletasks()
    search = screen._search
    assert search._click_bind_id is not None
    screen.destroy()
    tk_root.update_idletasks()
    assert search._click_bind_id is None
