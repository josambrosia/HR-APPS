"""Layar Rekap Dinas Paparan: tiga panel, sort kolom, rentang per papan, cetak."""
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
        upsert_employee(conn, no_staff="S3", nama="Cici", dept="HR")  # tanpa tugas
        _row(conn, a, "2026-07-01", "tugas_lapangan")
        _row(conn, a, "2026-07-02", "tugas_lapangan")
        _row(conn, b, "2026-07-06", "tugas_paparan")
        _row(conn, b, "2026-07-07", "tugas_paparan")
        _row(conn, b, "2026-07-08", "tugas_paparan")
        _row(conn, a, "2026-03-02", "tugas_lapangan")   # luar 3 bln, dalam tahun
    return p


@pytest.fixture
def screen_mod(monkeypatch, dbp):
    from src.ui.screens import dinas_recap as M
    from src.ui.components import dinas_exclude_dialog as D
    monkeypatch.setattr(M, "DB_PATH", dbp)
    monkeypatch.setattr(D, "DB_PATH", dbp)
    return M


def test_screen_builds_three_panels(tk_root, screen_mod):
    s = screen_mod.DinasRecapScreen(tk_root)
    try:
        assert s._month == "2026-07"
        assert s._span == "year" and s._paparan_span == "year"
        # semua pegawai aktif tampil, termasuk yang nol
        assert [r["nama"] for r in s._month_rows] == ["Budi", "Andi", "Cici"]
        assert s._dinas_panel is not None and s._paparan_panel is not None
    finally:
        s.destroy()


def test_boards_rank_by_their_own_metric(tk_root, screen_mod):
    s = screen_mod.DinasRecapScreen(tk_root)
    try:
        din = [e["nama"].cget("text") for e in s._dinas_panel._pool[:2]]
        pap = [e["nama"].cget("text") for e in s._paparan_panel._pool[:2]]
        assert din[0].startswith("Andi")     # 3 dinas
        assert pap[0].startswith("Budi")     # 3 paparan
    finally:
        s.destroy()


def test_each_board_has_its_own_span(tk_root, screen_mod):
    s = screen_mod.DinasRecapScreen(tk_root)
    try:
        s._on_dinas_span("3 bln")
        assert s._span == "3m"
        assert s._paparan_span == "year"        # papan lain tak ikut berubah
        s._on_paparan_span("6 bln")
        assert s._span == "3m" and s._paparan_span == "6m"
    finally:
        s.destroy()


def test_span_change_leaves_other_panels_widgets_untouched(tk_root, screen_mod):
    """Regresi performa: satu papan berganti rentang tidak boleh membangun
    ulang panel bulan maupun papan satunya."""
    s = screen_mod.DinasRecapScreen(tk_root)
    try:
        month_ids = [id(e["frame"]) for e in s._month_pool]
        pap_ids = [id(e["frame"]) for e in s._paparan_panel._pool]
        s._on_dinas_span("3 bln")
        assert [id(e["frame"]) for e in s._month_pool] == month_ids
        assert [id(e["frame"]) for e in s._paparan_panel._pool] == pap_ids
    finally:
        s.destroy()


def test_clicking_column_sorts_and_toggles_direction(tk_root, screen_mod):
    s = screen_mod.DinasRecapScreen(tk_root)
    try:
        s._on_sort("dinas")
        assert s._sort_key == "dinas" and s._sort_desc is True
        assert s._month_pool[0]["nama"].cget("text") == "Andi"    # 2 dinas
        s._on_sort("dinas")                                        # klik lagi
        assert s._sort_desc is False
        # Budi & Cici sama-sama 0 dinas → seri dipecah nama, B sebelum C
        assert [e["nama"].cget("text") for e in s._month_pool[:3]] == \
            ["Budi", "Cici", "Andi"]
    finally:
        s.destroy()


def test_sorting_by_name_starts_ascending(tk_root, screen_mod):
    s = screen_mod.DinasRecapScreen(tk_root)
    try:
        s._on_sort("nama")
        assert s._sort_desc is False
        assert [e["nama"].cget("text") for e in s._month_pool[:3]] == \
            ["Andi", "Budi", "Cici"]
    finally:
        s.destroy()


def test_active_sort_header_shows_direction_arrow(tk_root, screen_mod):
    s = screen_mod.DinasRecapScreen(tk_root)
    try:
        s._on_sort("paparan")
        lbl, _cap = s._sort_headers["paparan"]
        assert "▼" in lbl.cget("text")
        s._on_sort("paparan")
        assert "▲" in lbl.cget("text")
        other, _ = s._sort_headers["dinas"]
        assert other.cget("text") == "DIN"       # kolom lain bersih
    finally:
        s.destroy()


def test_header_columns_line_up_with_data_columns(tk_root, screen_mod):
    """Regresi: pack(side='right') menumpuk terbalik, sehingga judul sempat
    terbaca TOT|PAP|DIN di atas angka yang urutannya DIN|PAP|TOT."""
    s = screen_mod.DinasRecapScreen(tk_root)
    try:
        s.update_idletasks()

        def order(widgets):
            return [w for w in sorted(widgets, key=lambda w: w.winfo_x())]

        hdr_lbls = [lbl for key, (lbl, _c) in s._sort_headers.items()
                    if key != "nama"]
        hdr_caps = [w.cget("text").split()[0] for w in order(hdr_lbls)]
        assert hdr_caps == ["DIN", "PAP", "TOT"]

        e = s._month_pool[0]
        data_x = order([e["din"], e["pap"], e["tot"]])
        assert [w.cget("text") for w in data_x] == [
            e["din"].cget("text"), e["pap"].cget("text"), e["tot"].cget("text")]
        # judul dan angka benar-benar sekolom
        for lbl, cell in zip(order(hdr_lbls), data_x):
            assert abs(lbl.winfo_x() - cell.winfo_x()) <= 2
    finally:
        s.destroy()


def test_excluded_employee_disappears_from_all_panels(tk_root, screen_mod, dbp):
    from src.db.dinas_exclusions import set_excluded_ids
    s = screen_mod.DinasRecapScreen(tk_root)
    try:
        with get_connection(dbp) as conn:
            andi = conn.execute(
                "SELECT id FROM employees WHERE nama='Andi'").fetchone()["id"]
            set_excluded_ids(conn, [andi])
        s._load()
        assert "Andi" not in {r["nama"] for r in s._month_rows}
        visible_din = [e["nama"].cget("text") for e in s._dinas_panel._pool
                       if e["frame"].winfo_manager()]
        assert not any(t.startswith("Andi") for t in visible_din)
    finally:
        s.destroy()


def test_on_show_follows_active_month(tk_root, screen_mod, dbp):
    s = screen_mod.DinasRecapScreen(tk_root)
    try:
        with get_connection(dbp) as conn:
            set_setting(conn, "current_month", "2026-03")
        s.on_show()
        assert s._month == "2026-03"
        totals = {r["nama"]: r["total"] for r in s._month_rows}
        assert totals == {"Andi": 1, "Budi": 0, "Cici": 0}
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
    finally:
        s.destroy()


def test_rows_stay_compact(tk_root, screen_mod):
    """Regresi v24: garis aksen ber-fill='y' membuat satu baris peringkat
    setinggi ~250px. Tinggi baris harus tetap kecil & pasti."""
    s = screen_mod.DinasRecapScreen(tk_root)
    try:
        s.update_idletasks()
        assert s._dinas_panel._pool, "papan dinas kosong"
        for e in s._dinas_panel._pool:
            assert e["frame"].cget("height") == screen_mod._RANK_ROW_H
    finally:
        s.destroy()


def test_print_uses_both_active_spans(tk_root, screen_mod, monkeypatch):
    opened = []
    monkeypatch.setattr(screen_mod, "open_html_in_browser",
                        lambda p: opened.append(p) or (True, "Test"))
    s = screen_mod.DinasRecapScreen(tk_root)
    try:
        s._on_dinas_span("3 bln")
        s._do_print()
        assert len(opened) == 1
        html = opened[0].read_text(encoding="utf-8")
        assert "Papan Peringkat Dinas" in html
        assert "Papan Peringkat Paparan" in html
        assert "Mei – Juli 2026" in html            # rentang dinas
        assert "Januari – Desember 2026" in html    # rentang paparan
    finally:
        s.destroy()
