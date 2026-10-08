"""v26: layar Lembur — daftar, filter, aksi massal, on_show."""
import pytest

from src.db.attendance import upsert_attendance
from src.db.connection import get_connection
from src.db.employees import upsert_employee
from src.db.overtime import apply_status, get_decision
from src.db.schema import init_db
from src.db.settings import set_setting


def _att(conn, eid, tanggal, masuk, keluar):
    upsert_attendance(
        conn, employee_id=eid, tanggal=tanggal, hari=None, tipe="Hari Kerja",
        jadwal=None, masuk=masuk, keluar=keluar, kerja_jam=None,
        lembur_jam=None, terlambat_menit=0, has_issue=0, imported_from="t")


def _seed(p):
    init_db(p)
    with get_connection(p) as conn:
        a = upsert_employee(conn, no_staff="1", nama="Agus", dept="Ops")
        b = upsert_employee(conn, no_staff="2", nama="Budi", dept="Gudang")
        set_setting(conn, "current_month", "2026-10")
        _att(conn, a, "2026-10-01", "09:00", "19:30")   # 150 open
        _att(conn, b, "2026-10-02", "09:00", "19:00")   # 120
        apply_status(conn, employee_id=b, tanggal="2026-10-02",
                     status="diterima", detected_minutes=120,
                     approved_minutes=90)
    return a, b


def _screen(monkeypatch, tk_root, p):
    import src.ui.screens.overtime as mod
    monkeypatch.setattr(mod, "DB_PATH", p)
    s = mod.OvertimeScreen(tk_root)
    tk_root.update_idletasks()
    return s


def test_constructs_and_lists_rows(tmp_path, monkeypatch, tk_root):
    p = tmp_path / "o.db"
    _seed(p)
    s = _screen(monkeypatch, tk_root, p)
    try:
        assert len(s.tree.get_children()) == 2
        assert len(s.sum_tree.get_children()) == 2
        assert s._kpi_orang._value_label.cget("text") == "2"
        assert s._kpi_detected._value_label.cget("text") == "4j 30m"
        assert s._kpi_approved._value_label.cget("text") == "1j 30m"
        assert s._kpi_pending._value_label.cget("text") == "1"
    finally:
        s.destroy()


def test_filter_and_search(tmp_path, monkeypatch, tk_root):
    p = tmp_path / "o.db"
    _seed(p)
    s = _screen(monkeypatch, tk_root, p)
    try:
        s._filter = "diterima"
        s._render_table()
        assert len(s.tree.get_children()) == 1
        s._filter = "all"
        s._search.set("Agus")
        s._render_table()
        assert len(s.tree.get_children()) == 1
        s._search.clear()
        s._render_table()
        assert len(s.tree.get_children()) == 2
    finally:
        s.destroy()


def test_batch_ajukan_writes_decision(tmp_path, monkeypatch, tk_root):
    import src.ui.screens.overtime as mod
    p = tmp_path / "o.db"
    _seed(p)
    monkeypatch.setattr(mod, "show_success_toast", lambda *a, **k: None)
    s = _screen(monkeypatch, tk_root, p)
    try:
        open_iid = [iid for iid, r in s._row_by_iid.items()
                    if r.status == "open"][0]
        s._toggle_check(open_iid)
        assert s._batch_bar.winfo_manager() != ""
        s._apply_batch("diajukan")
        with get_connection(p) as conn:
            eid = int(open_iid.split("|")[0])
            d = get_decision(conn, eid, "2026-10-01")
        assert d["status"] == "diajukan"
    finally:
        s.destroy()


def test_batch_skips_ineligible(tmp_path, monkeypatch, tk_root):
    import src.ui.screens.overtime as mod
    p = tmp_path / "o.db"
    _seed(p)
    monkeypatch.setattr(mod, "show_success_toast", lambda *a, **k: None)
    s = _screen(monkeypatch, tk_root, p)
    try:
        done_iid = [iid for iid, r in s._row_by_iid.items()
                    if r.status == "diterima"][0]
        s._toggle_check(done_iid)
        s._apply_batch("diajukan")   # hanya Open yang boleh diajukan
        with get_connection(p) as conn:
            eid = int(done_iid.split("|")[0])
            d = get_decision(conn, eid, "2026-10-02")
        assert d["status"] == "diterima"
    finally:
        s.destroy()


def test_on_show_reloads_after_external_change(tmp_path, monkeypatch, tk_root):
    p = tmp_path / "o.db"
    a, _b = _seed(p)
    s = _screen(monkeypatch, tk_root, p)
    try:
        assert len(s.tree.get_children()) == 2
        with get_connection(p) as conn:
            _att(conn, a, "2026-10-05", "09:00", "19:00")
        s.on_show()
        assert len(s.tree.get_children()) == 3
    finally:
        s.destroy()


def test_no_active_month_shows_empty(tmp_path, monkeypatch, tk_root):
    import src.ui.screens.overtime as mod
    p = tmp_path / "o.db"
    init_db(p)
    s = _screen(monkeypatch, tk_root, p)
    try:
        assert s._month == ""
        assert len(s.tree.get_children()) == 0
    finally:
        s.destroy()


def test_orphan_decision_visible_in_its_tab(tmp_path, monkeypatch, tk_root):
    """Keputusan yang baris absensinya hilang tetap tampil di tab statusnya."""
    from src.db.attendance import delete_attendance
    p = tmp_path / "o.db"
    a, _b = _seed(p)
    with get_connection(p) as conn:
        apply_status(conn, employee_id=a, tanggal="2026-10-01",
                     status="diajukan", detected_minutes=150)
        delete_attendance(conn, employee_id=a, tanggal="2026-10-01")
    s = _screen(monkeypatch, tk_root, p)
    try:
        assert len(s.tree.get_children()) == 2   # 10-02 + yatim 10-01
        s._filter = "diajukan"
        s._render_table()
        iids = s.tree.get_children()
        assert len(iids) == 1
        vals = s.tree.item(iids[0], "values")
        assert vals[1].endswith("⚠")
        assert vals[6] == "—"                    # jam lembur tidak diketahui
        assert vals[8] == "Diajukan"
    finally:
        s.destroy()
