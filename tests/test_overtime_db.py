from src.db.connection import get_connection
from src.db.employees import upsert_employee
from src.db.overtime import apply_status, get_decision, set_note_approved
from src.db.schema import init_db


def _emp(conn):
    return upsert_employee(conn, no_staff="S1", nama="Agus", dept="Ops")


def test_status_lifecycle(tmp_path):
    p = tmp_path / "o.db"
    init_db(p)
    with get_connection(p) as conn:
        eid = _emp(conn)
        apply_status(conn, employee_id=eid, tanggal="2026-10-01",
                     status="diajukan", detected_minutes=150)
        d = get_decision(conn, eid, "2026-10-01")
        assert d["status"] == "diajukan"
        assert d["submitted_at"]
        assert d["decided_at"] is None
        assert d["detected_minutes_at_decision"] == 150

        apply_status(conn, employee_id=eid, tanggal="2026-10-01",
                     status="diterima", detected_minutes=150,
                     approved_minutes=120, note="disetujui 2 jam")
        d = get_decision(conn, eid, "2026-10-01")
        assert d["status"] == "diterima"
        assert d["approved_minutes"] == 120
        assert d["note"] == "disetujui 2 jam"
        assert d["decided_at"]
        assert d["submitted_at"]  # dipertahankan dari aksi sebelumnya


def test_status_change_preserves_note_when_none(tmp_path):
    p = tmp_path / "o.db"
    init_db(p)
    with get_connection(p) as conn:
        eid = _emp(conn)
        apply_status(conn, employee_id=eid, tanggal="2026-10-01",
                     status="diterima", detected_minutes=150,
                     approved_minutes=150, note="ok")
        apply_status(conn, employee_id=eid, tanggal="2026-10-01",
                     status="tidak_diterima", detected_minutes=150)
        d = get_decision(conn, eid, "2026-10-01")
        assert d["note"] == "ok"


def test_revert_to_open_deletes_row(tmp_path):
    p = tmp_path / "o.db"
    init_db(p)
    with get_connection(p) as conn:
        eid = _emp(conn)
        apply_status(conn, employee_id=eid, tanggal="2026-10-01",
                     status="diajukan", detected_minutes=150)
        apply_status(conn, employee_id=eid, tanggal="2026-10-01",
                     status="open", detected_minutes=150)
        assert get_decision(conn, eid, "2026-10-01") is None


def test_set_note_approved_noop_when_open(tmp_path):
    p = tmp_path / "o.db"
    init_db(p)
    with get_connection(p) as conn:
        eid = _emp(conn)
        set_note_approved(conn, employee_id=eid, tanggal="2026-10-01",
                          note="cek", approved_minutes=None)
        assert get_decision(conn, eid, "2026-10-01") is None


def test_set_note_approved_updates_existing(tmp_path):
    p = tmp_path / "o.db"
    init_db(p)
    with get_connection(p) as conn:
        eid = _emp(conn)
        apply_status(conn, employee_id=eid, tanggal="2026-10-01",
                     status="diterima", detected_minutes=150,
                     approved_minutes=150)
        set_note_approved(conn, employee_id=eid, tanggal="2026-10-01",
                          note="koreksi 2,5 jam", approved_minutes=150)
        d = get_decision(conn, eid, "2026-10-01")
        assert d["note"] == "koreksi 2,5 jam"
        assert d["approved_minutes"] == 150


def test_unknown_status_rejected(tmp_path):
    p = tmp_path / "o.db"
    init_db(p)
    with get_connection(p) as conn:
        eid = _emp(conn)
        try:
            apply_status(conn, employee_id=eid, tanggal="2026-10-01",
                         status="disetujui", detected_minutes=150)
        except ValueError:
            pass
        else:
            raise AssertionError("status tidak dikenal harus ditolak")
