from src.core.overtime import (count_pending, detect_minutes,
                                format_duration, month_rows, summarize)
from src.db.attendance import upsert_attendance
from src.db.connection import get_connection
from src.db.employees import upsert_employee
from src.db.holidays import mark_holidays
from src.db.overtime import apply_status
from src.db.schema import init_db
from src.db.settings import set_setting


def _row(**kw):
    base = dict(tipe="Hari Kerja", masuk="09:00", keluar="19:30",
                schedule=("09.00", "17.00"), threshold_min=18 * 60,
                is_holiday=False)
    base.update(kw)
    return detect_minutes(**base)


def test_workday_above_threshold():
    assert _row() == 150


def test_workday_between_end_and_threshold_not_counted():
    assert _row(keluar="17:30") is None


def test_workday_at_threshold_not_counted():
    assert _row(keluar="18:00") is None


def test_holiday_full_duration_without_threshold():
    assert _row(tipe="Hari Libur", keluar="14:00", is_holiday=True) == 300


def test_holiday_requires_both_punches():
    assert _row(masuk=None, keluar="14:00", is_holiday=True) is None


def test_holiday_zero_or_negative_duration_skipped():
    assert _row(masuk="14:00", keluar="14:00", is_holiday=True) is None


def test_missing_punch_skipped():
    assert _row(keluar=None) is None


def test_non_workday_tipe_skipped_on_weekday():
    assert _row(tipe="Istirahat") is None


def test_format_duration():
    assert format_duration(150) == "2j 30m"
    assert format_duration(300) == "5j"
    assert format_duration(45) == "45m"
    assert format_duration(0) == "0m"


def _seed(conn):
    eid = upsert_employee(conn, no_staff="S1", nama="Agus", dept="Ops")

    def att(tanggal, masuk, keluar, tipe="Hari Kerja"):
        upsert_attendance(
            conn, employee_id=eid, tanggal=tanggal, hari=None, tipe=tipe,
            jadwal=None, masuk=masuk, keluar=keluar, kerja_jam=None,
            lembur_jam=None, terlambat_menit=0, has_issue=0,
            imported_from="t.xlsx")

    att("2026-10-01", "09:00", "19:30")            # Thu: 150
    att("2026-10-02", "09:00", "17:30")            # Fri: di bawah ambang
    att("2026-10-04", "09:00", "14:00")            # Sun: 300 (libur)
    att("2026-10-05", "09:00", "14:00")            # Mon: ditandai libur -> 300
    att("2026-10-06", None, "19:00")               # Tue: jam masuk kosong
    att("2026-10-07", "09:00", "19:00")            # Wed: 120
    mark_holidays(conn, ["2026-10-05"])
    return eid


def test_month_rows_and_aggregates(tmp_path):
    p = tmp_path / "o.db"
    init_db(p)
    with get_connection(p) as conn:
        eid = _seed(conn)
        apply_status(conn, employee_id=eid, tanggal="2026-10-01",
                     status="diterima", detected_minutes=150,
                     approved_minutes=120)
        apply_status(conn, employee_id=eid, tanggal="2026-10-07",
                     status="diajukan", detected_minutes=120)

        rows = month_rows(conn, "2026-10")
        by_date = {r.tanggal: r for r in rows}
        assert set(by_date) == {"2026-10-01", "2026-10-04",
                                "2026-10-05", "2026-10-07"}
        assert by_date["2026-10-01"].minutes == 150
        assert by_date["2026-10-01"].status == "diterima"
        assert by_date["2026-10-01"].approved_minutes == 120
        assert by_date["2026-10-04"].is_holiday is True
        assert by_date["2026-10-04"].minutes == 300
        assert by_date["2026-10-05"].is_holiday is True
        assert by_date["2026-10-07"].status == "diajukan"

        assert count_pending(conn, "2026-10") == 3  # 04, 05, 07

        s = summarize(rows)
        assert len(s) == 1
        assert s[0]["days"] == 4
        assert s[0]["detected"] == 150 + 300 + 300 + 120
        assert s[0]["approved"] == 120


def test_changed_flag_after_attendance_edit(tmp_path):
    p = tmp_path / "o.db"
    init_db(p)
    with get_connection(p) as conn:
        eid = _seed(conn)
        apply_status(conn, employee_id=eid, tanggal="2026-10-01",
                     status="diterima", detected_minutes=150,
                     approved_minutes=150)
        upsert_attendance(
            conn, employee_id=eid, tanggal="2026-10-01", hari=None,
            tipe="Hari Kerja", jadwal=None, masuk="09:00", keluar="20:00",
            kerja_jam=None, lembur_jam=None, terlambat_menit=0, has_issue=0,
            imported_from="edit")
        row = [r for r in month_rows(conn, "2026-10")
               if r.tanggal == "2026-10-01"][0]
        assert row.minutes == 180
        assert row.changed is True


def test_decision_row_survives_when_no_longer_qualifying(tmp_path):
    p = tmp_path / "o.db"
    init_db(p)
    with get_connection(p) as conn:
        eid = _seed(conn)
        apply_status(conn, employee_id=eid, tanggal="2026-10-01",
                     status="diterima", detected_minutes=150,
                     approved_minutes=150)
        upsert_attendance(
            conn, employee_id=eid, tanggal="2026-10-01", hari=None,
            tipe="Hari Kerja", jadwal=None, masuk="09:00", keluar="17:10",
            kerja_jam=None, lembur_jam=None, terlambat_menit=0, has_issue=0,
            imported_from="edit")
        row = [r for r in month_rows(conn, "2026-10")
               if r.tanggal == "2026-10-01"][0]
        assert row.qualifies is False
        assert row.minutes == 0
        assert row.status == "diterima"
        assert row.changed is True


def test_custom_threshold_setting(tmp_path):
    p = tmp_path / "o.db"
    init_db(p)
    with get_connection(p) as conn:
        set_setting(conn, "overtime_threshold", "19.00")
        _seed(conn)
        rows = month_rows(conn, "2026-10")
        by_date = {r.tanggal: r for r in rows}
        # keluar 19:00 <= ambang 19:00 -> 10-07 tidak lolos; 19:30 pada
        # 10-01 tetap lolos; baris libur tidak terpengaruh ambang.
        assert set(by_date) == {"2026-10-01", "2026-10-04", "2026-10-05"}
        assert by_date["2026-10-01"].minutes == 150


def test_orphan_decision_survives_without_attendance_row(tmp_path):
    """Keputusan tetap tampil walau baris absensinya hilang (bug v26)."""
    from src.db.attendance import delete_attendance
    p = tmp_path / "o.db"
    init_db(p)
    with get_connection(p) as conn:
        eid = _seed(conn)
        apply_status(conn, employee_id=eid, tanggal="2026-10-01",
                     status="diterima", detected_minutes=150,
                     approved_minutes=120)
        delete_attendance(conn, employee_id=eid, tanggal="2026-10-01")
        rows = month_rows(conn, "2026-10")
        by_date = {r.tanggal: r for r in rows}
        assert "2026-10-01" in by_date, "keputusan yatim hilang dari daftar"
        orphan = by_date["2026-10-01"]
        assert orphan.missing_data is True
        assert orphan.qualifies is False
        assert orphan.minutes == 0
        assert orphan.status == "diterima"
        assert orphan.approved_minutes == 120
        assert orphan.detected_at_decision == 150
        # urutan tetap kronologis
        assert [r.tanggal for r in rows] == sorted(r.tanggal for r in rows)
        # ikut terhitung badge (belum final)
        assert count_pending(conn, "2026-10") == 3


def test_orphan_diajukan_counted_as_pending(tmp_path):
    from src.db.attendance import delete_attendance
    p = tmp_path / "o.db"
    init_db(p)
    with get_connection(p) as conn:
        eid = _seed(conn)
        apply_status(conn, employee_id=eid, tanggal="2026-10-01",
                     status="diajukan", detected_minutes=150)
        delete_attendance(conn, employee_id=eid, tanggal="2026-10-01")
        rows = month_rows(conn, "2026-10")
        orphan = [r for r in rows if r.tanggal == "2026-10-01"][0]
        assert orphan.status == "diajukan"
        assert count_pending(conn, "2026-10") == 4
