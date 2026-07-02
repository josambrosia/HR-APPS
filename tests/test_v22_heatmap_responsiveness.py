# tests/test_v22_heatmap_responsiveness.py
"""v22 heatmap responsiveness: search debounce + match-set skip, trailing-edge
resize throttle + width-bucket skip, sort no-op skip, and the cached-screen
on_show() refresh contract (fresh data, preserved query/sort/scroll)."""
import time
from types import SimpleNamespace

import src.ui.screens.heatmap as mod
from src.db.schema import init_db
from src.db.connection import get_connection
from src.db.employees import upsert_employee
from src.db.attendance import upsert_attendance
from src.db.settings import set_setting


def _seed(p):
    """Two employees in Mei 2026: ANDI (slightly late once) + BUDI (on time)."""
    init_db(p)
    with get_connection(p) as conn:
        set_setting(conn, "current_month", "2026-05")
        a = upsert_employee(conn, no_staff="1", nama="ANDI", dept="IT")
        b = upsert_employee(conn, no_staff="2", nama="BUDI", dept="HR")
        upsert_attendance(conn, employee_id=a, tanggal="2026-05-04", hari="Senin",
                          tipe="Hari Kerja", jadwal="", masuk="08:05", keluar="16:30",
                          kerja_jam=None, lembur_jam=None, terlambat_menit=5,
                          has_issue=0, imported_from="W")
        upsert_attendance(conn, employee_id=b, tanggal="2026-05-04", hari="Senin",
                          tipe="Hari Kerja", jadwal="", masuk="07:58", keluar="16:10",
                          kerja_jam=None, lembur_jam=None, terlambat_menit=0,
                          has_issue=0, imported_from="W")
    return a, b


def _screen(monkeypatch, tk_root, p):
    monkeypatch.setattr(mod, "DB_PATH", p)
    s = mod.HeatmapScreen(tk_root)
    tk_root.update_idletasks()
    return s


def _count_repaints(monkeypatch, s):
    """Wrap the real _repaint so tests can count how often it actually runs."""
    calls = {"n": 0}
    real = s._repaint

    def counting():
        calls["n"] += 1
        real()

    monkeypatch.setattr(s, "_repaint", counting)
    return calls


def _pump(tk_root, ms):
    """Drive the Tk event loop for ~ms wall-clock so after() timers fire."""
    deadline = time.monotonic() + ms / 1000.0
    while time.monotonic() < deadline:
        tk_root.update()
        time.sleep(0.01)


# ---------- search debounce ----------

def test_search_debounce_coalesces_keystrokes(tmp_path, monkeypatch, tk_root):
    p = tmp_path / "h.db"
    _seed(p)
    s = _screen(monkeypatch, tk_root, p)
    assert s._search._debounce_ms == 200    # screen opts into the debounce
    calls = _count_repaints(monkeypatch, s)
    entry = s._search._entry
    for ch in "AND":                        # three rapid keystrokes
        entry.insert("end", ch)
        s._search._on_key_release()
    assert calls["n"] == 0                  # nothing repaints per keystroke
    _pump(tk_root, 400)                     # let the 200 ms debounce elapse
    assert calls["n"] == 1                  # ...then exactly one repaint
    assert [e["nama"] for e in s._visible_employees] == ["ANDI"]
    s.destroy()


def test_search_same_match_set_skips_repaint(tmp_path, monkeypatch, tk_root):
    p = tmp_path / "h.db"
    _seed(p)
    s = _screen(monkeypatch, tk_root, p)
    s._search.set("AN")                     # matches ANDI only
    assert [e["nama"] for e in s._visible_employees] == ["ANDI"]
    calls = _count_repaints(monkeypatch, s)
    s._search.set("ANDI")                   # same match set -> repaint skipped
    assert calls["n"] == 0
    s._search.set("")                       # back to everyone -> one repaint
    assert calls["n"] == 1
    s.destroy()


# ---------- resize throttle ----------

def test_resize_throttle_coalesces_configure_events(tmp_path, monkeypatch, tk_root):
    p = tmp_path / "h.db"
    _seed(p)
    s = _screen(monkeypatch, tk_root, p)
    calls = _count_repaints(monkeypatch, s)
    for w in (700, 760, 820, 900):          # a drag: four widths in one burst
        s._on_canvas_configure(SimpleNamespace(width=w))
    assert calls["n"] == 0                  # trailing edge: silent mid-drag
    _pump(tk_root, 300)
    assert calls["n"] == 1                  # one reflow after the size settles
    assert s._last_w == 900                 # ...at the final width
    s.destroy()


def test_resize_same_width_bucket_skips_reflow(tmp_path, monkeypatch, tk_root):
    p = tmp_path / "h.db"
    _seed(p)
    s = _screen(monkeypatch, tk_root, p)
    calls = _count_repaints(monkeypatch, s)
    s._on_canvas_configure(SimpleNamespace(width=900))
    _pump(tk_root, 300)
    assert calls["n"] == 1
    s._on_canvas_configure(SimpleNamespace(width=904))   # inside the ±8 bucket
    _pump(tk_root, 300)
    assert calls["n"] == 1                  # same bucket -> no second reflow
    s.destroy()


# ---------- sort ----------

def test_sort_same_key_skips_repaint(tmp_path, monkeypatch, tk_root):
    p = tmp_path / "h.db"
    _seed(p)
    s = _screen(monkeypatch, tk_root, p)
    calls = _count_repaints(monkeypatch, s)
    s._on_sort("Nama (A–Z)")                # already the active key -> no-op
    assert calls["n"] == 0
    s._on_sort("Paling sering telat")       # real change -> one repaint
    assert calls["n"] == 1
    s.destroy()


# ---------- on_show ----------

def test_on_show_refreshes_data_and_preserves_query(tmp_path, monkeypatch, tk_root):
    p = tmp_path / "h.db"
    a, _b = _seed(p)
    s = _screen(monkeypatch, tk_root, p)
    s._search.set("ANDI")
    tk_root.update_idletasks()
    assert [e["nama"] for e in s._visible_employees] == ["ANDI"]
    assert s._visible_employees[0]["needs_attention"] is False
    # Data changes while the screen is hidden: ANDI gains a severe-late day.
    with get_connection(p) as conn:
        upsert_attendance(conn, employee_id=a, tanggal="2026-05-05", hari="Selasa",
                          tipe="Hari Kerja", jadwal="", masuk="09:15", keluar="16:30",
                          kerja_jam=None, lembur_jam=None, terlambat_menit=75,
                          has_issue=0, imported_from="W")
    calls = _count_repaints(monkeypatch, s)
    s.on_show()
    tk_root.update_idletasks()
    assert calls["n"] == 1                             # exactly one repaint
    assert s._search.get() == "ANDI"                   # query survives in the widget
    assert [e["nama"] for e in s._visible_employees] == ["ANDI"]  # ...and re-applies
    assert s._visible_employees[0]["needs_attention"] is True    # fresh data painted
    s.destroy()


def test_on_show_picks_up_new_employee_and_keeps_sort(tmp_path, monkeypatch, tk_root):
    p = tmp_path / "h.db"
    _seed(p)
    s = _screen(monkeypatch, tk_root, p)
    s._on_sort("Kehadiran terendah")
    with get_connection(p) as conn:
        c = upsert_employee(conn, no_staff="3", nama="CITRA", dept="GA")
        upsert_attendance(conn, employee_id=c, tanggal="2026-05-06", hari="Rabu",
                          tipe="Hari Kerja", jadwal="", masuk="08:00", keluar="16:05",
                          kerja_jam=None, lembur_jam=None, terlambat_menit=0,
                          has_issue=0, imported_from="W")
    s.on_show()
    tk_root.update_idletasks()
    assert s._sortkey == "kehadiran"                   # sort selection survives
    assert "CITRA" in [e["nama"] for e in s._visible_employees]
    s.destroy()


def test_on_show_follows_changed_current_month(tmp_path, monkeypatch, tk_root):
    p = tmp_path / "h.db"
    _seed(p)
    s = _screen(monkeypatch, tk_root, p)
    assert s._month == "2026-05"
    with get_connection(p) as conn:
        set_setting(conn, "current_month", "2026-06")  # e.g. a new import landed
    s.on_show()
    tk_root.update_idletasks()
    assert s._month == "2026-06"
    assert "Juni" in s._month_lbl.cget("text")
    s.destroy()


def test_on_show_handles_empty_db(temp_db_path, monkeypatch, tk_root):
    init_db(temp_db_path)                   # no attendance, no current_month
    monkeypatch.setattr(mod, "DB_PATH", temp_db_path)
    s = mod.HeatmapScreen(tk_root)
    tk_root.update_idletasks()
    s.on_show()                             # idempotent: same empty state as __init__
    tk_root.update_idletasks()
    texts = [s._canvas.itemcget(i, "text") for i in s._canvas.find_all()
             if s._canvas.type(i) == "text"]
    assert any("Belum ada data" in t for t in texts)
    s.destroy()
