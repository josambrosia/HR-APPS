"""Item 19 — kartu KPI Coaching diperbarui di tempat, tidak dihancurkan."""
import pytest

from src.db.schema import init_db
from src.db.connection import get_connection
from src.db.settings import set_setting
from src.db.employees import upsert_employee


@pytest.fixture
def dbp(tmp_path):
    p = tmp_path / "hr.db"
    init_db(p)
    with get_connection(p) as conn:
        set_setting(conn, "current_month", "2026-07")
        upsert_employee(conn, no_staff="S1", nama="Andi", dept="Ops")
        upsert_employee(conn, no_staff="S2", nama="Budi", dept="Sales")
    return p


def test_kartu_kpi_tidak_dibangun_ulang_saat_reload(tk_root, monkeypatch, dbp):
    """Regresi cacat: _render_stats() men-destroy() semua kartu tiap reload,
    jadi Total/Sudah/Belum/Coverage berkedip putih tiap toggle."""
    from src.ui.screens import coaching as M
    monkeypatch.setattr(M, "DB_PATH", dbp)
    s = M.CoachingScreen(tk_root)
    try:
        before = [id(c) for c in s._stats_cards]
        assert len(before) == 4
        s._reload()
        after = [id(c) for c in s._stats_cards]
        assert after == before, "kartu KPI dibangun ulang — kedipannya masih ada"
    finally:
        s.destroy()


def test_nilai_kartu_tetap_benar_setelah_reload(tk_root, monkeypatch, dbp):
    from src.ui.screens import coaching as M
    monkeypatch.setattr(M, "DB_PATH", dbp)
    s = M.CoachingScreen(tk_root)
    try:
        s._reload()
        total_card = s._stats_cards[0]
        # NOTE penyesuaian dari rencana: produksi tidak menyimpan baris hasil
        # query sebagai `self._rows` (rencana mengasumsikan atribut yang
        # tidak ada). `_reload()` memang mengisi `self._row_cache` (iid ->
        # row) untuk setiap baris yang dirender, jadi panjangnya persis
        # sama dengan Total yang dihitung `_render_stats` — dipakai di sini
        # sebagai sumber independen tanpa mengubah kode produksi.
        assert total_card._value_label.cget("text") == str(len(s._row_cache))
    finally:
        s.destroy()
