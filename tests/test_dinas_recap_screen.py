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
        upsert_employee(conn, no_staff="S3", nama="Cici", dept="HR")  # tanpa tugas
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
        # semua pegawai aktif tampil — Cici nol tetap muncul, di dasar
        assert [r["nama"] for r in s._month_rows] == ["Andi", "Budi", "Cici"]
        assert s._month_rows[-1]["total"] == 0
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
        assert [r["nama"] for r in s._month_rows] == ["Andi", "Budi", "Cici"]
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


def test_rows_stay_compact(tk_root, screen_mod):
    """Regresi v24: garis aksen ber-fill='y' membuat satu baris peringkat
    setinggi ~250px. Tinggi baris harus tetap kecil & pasti."""
    s = screen_mod.DinasRecapScreen(tk_root)
    try:
        s.update_idletasks()
        assert s._rank_pool, "papan peringkat kosong"
        for e in s._rank_pool:
            assert e["frame"].cget("height") == screen_mod._RANK_ROW_H
            assert e["frame"].cget("height") <= 40
    finally:
        s.destroy()


def test_span_change_reuses_widgets_and_skips_month_panel(tk_root, screen_mod):
    """Regresi performa: dulu satu pergantian rentang menghancurkan lalu
    membangun ulang ±660 widget di KEDUA panel (±9 detik pada 33 pegawai).

    Dua jaminan sekaligus, tanpa mengukur waktu (bebas flaky):
      1. panel bulan tidak tersentuh — rentang tak mempengaruhinya;
      2. baris peringkat dipakai ulang (objek widget sama, hanya isinya berubah).
    """
    s = screen_mod.DinasRecapScreen(tk_root)
    try:
        month_ids = [id(e["frame"]) for e in s._month_pool]
        month_names = [e["nama"].cget("text") for e in s._month_pool]
        rank_ids = [id(e["frame"]) for e in s._rank_pool]
        before_total = s._rank_pool[0]["tot"].cget("text")

        s._on_span("3 bln")

        assert [id(e["frame"]) for e in s._month_pool] == month_ids
        assert [e["nama"].cget("text") for e in s._month_pool] == month_names
        assert [id(e["frame"]) for e in s._rank_pool] == rank_ids
        # isinya memang diperbarui, bukan sekadar tidak berubah
        assert s._rank_pool[0]["tot"].cget("text") != before_total
    finally:
        s.destroy()


def test_pool_shrinks_without_leaving_stale_rows(tk_root, screen_mod, dbp):
    """Baris berlebih disembunyikan lewat grid_remove() — tidak boleh ada sisa
    baris lama yang masih tampak saat jumlah data menyusut."""
    from src.db.employees import upsert_employee
    s = screen_mod.DinasRecapScreen(tk_root)
    try:
        grown = len(s._month_pool)
        with get_connection(dbp) as conn:
            conn.execute("UPDATE employees SET active = 0 WHERE nama != 'Andi'")
        s.on_show()
        assert len(s._month_rows) == 1
        assert len(s._month_pool) == grown          # pool tidak menyusut...
        visible = [e for e in s._month_pool if e["frame"].winfo_manager()]
        assert len(visible) == 1                    # ...tapi yang tampil hanya 1
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
