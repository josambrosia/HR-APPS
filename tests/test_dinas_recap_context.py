import pytest

from src.db.schema import init_db
from src.db.connection import get_connection
from src.db.employees import upsert_employee
from src.db.attendance import save_manual_attendance, set_reason
from src.reports.dinas_recap_print import build_dinas_recap_context


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
def db(tmp_path):
    p = tmp_path / "hr.db"
    init_db(p)
    with get_connection(p) as conn:
        a = upsert_employee(conn, no_staff="S1", nama="Andi", dept="Ops")
        b = upsert_employee(conn, no_staff="S2", nama="Budi", dept="Sales")
        _row(conn, a, "2026-07-01", "tugas_lapangan")
        _row(conn, a, "2026-07-02", "tugas_lapangan")
        _row(conn, a, "2026-07-03", "tugas_paparan")
        _row(conn, b, "2026-07-06", "tugas_paparan")
        _row(conn, a, "2026-03-02", "tugas_lapangan")   # di luar 3 bln, dalam tahun
    yield p


def test_month_panel_and_totals(db):
    with get_connection(db) as conn:
        ctx = build_dinas_recap_context(conn, "2026-07", "year")
    assert ctx["month_label"] == "Juli 2026"
    assert [r["nama"] for r in ctx["month_rows"]] == ["Andi", "Budi"]
    assert ctx["month_totals"] == {"dinas": 2, "paparan": 2, "total": 4}


def test_rank_rows_have_rank_marks_and_bars(db):
    with get_connection(db) as conn:
        ctx = build_dinas_recap_context(conn, "2026-07", "year")
    r = ctx["rank_rows"]
    assert r[0]["nama"] == "Andi" and r[0]["rank"] == 1 and r[0]["mark"] == "👑"
    assert r[1]["nama"] == "Budi" and r[1]["rank"] == 2 and r[1]["mark"] == "💎"
    assert r[0]["bar_pct"] == 100                 # pemuncak
    assert r[1]["bar_pct"] == 25                  # 1 dari 4
    assert r[0]["dinas_pct"] + r[0]["paparan_pct"] == 100


def test_span_affects_rank_rows_but_not_month_panel(db):
    with get_connection(db) as conn:
        year = build_dinas_recap_context(conn, "2026-07", "year")
        q3 = build_dinas_recap_context(conn, "2026-07", "3m")
    assert year["rank_rows"][0]["total"] == 4     # termasuk Maret
    assert q3["rank_rows"][0]["total"] == 3       # Mei–Juli saja
    assert year["month_totals"] == q3["month_totals"]


def test_span_label_present(db):
    with get_connection(db) as conn:
        ctx = build_dinas_recap_context(conn, "2026-07", "6m")
    assert ctx["span_label"] == "Februari – Juli 2026"
    assert ctx["span"] == "6m"


def test_champion_none_when_empty(db):
    with get_connection(db) as conn:
        ctx = build_dinas_recap_context(conn, "2030-01", "year")
    assert ctx["rank_rows"] == []
    assert ctx["champion"] is None
    assert ctx["month_totals"] == {"dinas": 0, "paparan": 0, "total": 0}


def test_render_html_contains_both_sections(db):
    from src.reports.dinas_recap_print import render_dinas_recap_html
    with get_connection(db) as conn:
        html = render_dinas_recap_html(conn, "2026-07", "year")
    assert "Rekap Dinas" in html
    assert "Juli 2026" in html
    assert "Januari – Desember 2026" in html
    assert "Andi" in html
    assert "HR Officer in Charge" in html
