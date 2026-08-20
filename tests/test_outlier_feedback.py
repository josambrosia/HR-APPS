"""Item 16 — exclude/revert di Outlier akhirnya mengonfirmasi dirinya."""
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
    return p


def test_exclude_memunculkan_konfirmasi(tk_root, monkeypatch, dbp):
    """Regresi cacat: sebelumnya tombol ini tidak memberi umpan balik apa pun,
    jadi pada roster panjang ia terasa rusak."""
    from src.ui.screens import outlier as M
    monkeypatch.setattr(M, "DB_PATH", dbp)
    shown = []
    monkeypatch.setattr(M, "show_success_toast",
                        lambda *a, **k: shown.append(a))
    s = M.OutlierScreen(tk_root)
    try:
        with get_connection(dbp) as conn:
            eid = conn.execute("SELECT id FROM employees WHERE nama='Andi'").fetchone()["id"]
        s._on_exclude(eid)
        assert shown, "exclude tidak mengonfirmasi apa pun"
    finally:
        s.destroy()


def test_revert_all_juga_mengonfirmasi(tk_root, monkeypatch, dbp):
    from src.ui.screens import outlier as M
    monkeypatch.setattr(M, "DB_PATH", dbp)
    shown = []
    monkeypatch.setattr(M, "show_success_toast", lambda *a, **k: shown.append(a))
    s = M.OutlierScreen(tk_root)
    try:
        s._on_revert_all()
        assert shown
    finally:
        s.destroy()
