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


def test_two_separate_boards_rank_by_their_own_metric(db):
    with get_connection(db) as conn:
        ctx = build_dinas_recap_context(conn, "2026-07", "year")
    d = ctx["dinas_rank"]
    assert d[0]["nama"] == "Andi" and d[0]["rank"] == 1 and d[0]["mark"] == "👑"
    assert d[0]["value"] == 3 and d[0]["bar_pct"] == 100   # 2 Juli + 1 Maret
    p = ctx["paparan_rank"]
    # Andi 1 paparan, Budi 1 — seri, dipecah nama
    assert [r["nama"] for r in p] == ["Andi", "Budi"]
    assert all(r["value"] == 1 for r in p)


def test_span_affects_boards_but_not_month_panel(db):
    with get_connection(db) as conn:
        year = build_dinas_recap_context(conn, "2026-07", "year")
        q3 = build_dinas_recap_context(conn, "2026-07", "3m")
    assert year["dinas_rank"][0]["value"] == 3    # termasuk Maret
    assert q3["dinas_rank"][0]["value"] == 2      # Mei–Juli saja
    assert year["month_totals"] == q3["month_totals"]


def test_boards_can_use_different_spans(db):
    with get_connection(db) as conn:
        ctx = build_dinas_recap_context(conn, "2026-07", "3m", paparan_span="year")
    assert ctx["span"] == "3m" and ctx["paparan_span"] == "year"
    assert ctx["dinas_rank"][0]["value"] == 2     # Mei–Juli
    assert ctx["span_label"] == "Mei – Juli 2026"
    assert ctx["paparan_span_label"] == "Januari – Desember 2026"


def test_paparan_span_defaults_to_main_span(db):
    with get_connection(db) as conn:
        ctx = build_dinas_recap_context(conn, "2026-07", "3m")
    assert ctx["paparan_span"] == "3m"


def test_excluded_employees_hidden_from_all_three_panels(db):
    from src.db.dinas_exclusions import set_excluded_ids
    with get_connection(db) as conn:
        andi = conn.execute(
            "SELECT id FROM employees WHERE nama = 'Andi'").fetchone()["id"]
        set_excluded_ids(conn, [andi])
    with get_connection(db) as conn:
        ctx = build_dinas_recap_context(conn, "2026-07", "year")
    assert "Andi" not in {r["nama"] for r in ctx["month_rows"]}
    assert "Andi" not in {r["nama"] for r in ctx["dinas_rank"]}
    assert "Andi" not in {r["nama"] for r in ctx["paparan_rank"]}
    assert ctx["excluded_count"] == 1
    # totals ikut menyusut — bukan sekadar barisnya yang disembunyikan
    assert ctx["month_totals"] == {"dinas": 0, "paparan": 1, "total": 1}


def test_span_label_present(db):
    with get_connection(db) as conn:
        ctx = build_dinas_recap_context(conn, "2026-07", "6m")
    assert ctx["span_label"] == "Februari – Juli 2026"
    assert ctx["span"] == "6m"


def test_all_zero_range_lists_everyone_without_crowning_anyone(db):
    """Rentang tanpa aktivitas: semua pegawai tetap tampil, tapi tak ada juara
    dan tak ada penanda 👑/💎."""
    with get_connection(db) as conn:
        ctx = build_dinas_recap_context(conn, "2030-01", "year")
    for board in ("dinas_rank", "paparan_rank"):
        rows = ctx[board]
        assert [r["nama"] for r in rows] == ["Andi", "Budi"]
        assert all(r["value"] == 0 for r in rows)
        assert all(r["mark"] == "" for r in rows)
        assert all(r["bar_pct"] == 0 for r in rows)
    assert ctx["dinas_champion"] is None
    assert ctx["paparan_champion"] is None
    assert ctx["month_totals"] == {"dinas": 0, "paparan": 0, "total": 0}


def test_render_html_contains_all_three_sections(db):
    from src.reports.dinas_recap_print import render_dinas_recap_html
    with get_connection(db) as conn:
        html = render_dinas_recap_html(conn, "2026-07", "year")
    assert "Rincian Bulan" in html
    assert "Papan Peringkat Dinas" in html
    assert "Papan Peringkat Paparan" in html
    assert "Juli 2026" in html
    assert "Januari – Desember 2026" in html
    assert "Andi" in html
    assert "HR Officer in Charge" in html


def test_render_html_shows_both_spans_when_they_differ(db):
    from src.reports.dinas_recap_print import render_dinas_recap_html
    with get_connection(db) as conn:
        html = render_dinas_recap_html(conn, "2026-07", "3m", paparan_span="year")
    assert "Mei – Juli 2026" in html
    assert "Januari – Desember 2026" in html
