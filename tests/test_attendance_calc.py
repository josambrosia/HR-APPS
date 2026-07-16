from src.core.attendance_calc import recompute, to_minutes
from src.core.week_utils import hari_name


def R(**kw):
    base = dict(tipe="Hari Kerja", masuk=None, keluar=None,
                schedule_start="08.00", schedule_end="16.00")
    base.update(kw)
    return recompute(**base)


def test_to_minutes_accepts_colon_and_dot():
    assert to_minutes("08:15") == 495
    assert to_minutes("08.00") == 480
    assert to_minutes("") is None
    assert to_minutes("xx") is None
    assert to_minutes("25:00") is None       # out of range
    assert to_minutes(None) is None


def test_missing_keluar_is_issue():
    assert R(masuk="08:00", keluar=None)["has_issue"] == 1


def test_missing_masuk_is_issue():
    assert R(masuk=None, keluar="16:00")["has_issue"] == 1


def test_full_day_no_issue_late_zero_work_eight():
    assert R(masuk="08:00", keluar="16:00") == {
        "has_issue": 0, "terlambat_menit": 0, "kerja_jam": 8.0, "lembur_jam": 0.0}


def test_late_and_overtime():
    r = R(masuk="08:20", keluar="16:30")
    assert r["terlambat_menit"] == 20
    assert r["lembur_jam"] == 0.5
    assert r["kerja_jam"] == 8.2
    assert r["has_issue"] == 0


def test_early_arrival_not_negative_late():
    assert R(masuk="07:30", keluar="16:00")["terlambat_menit"] == 0


def test_libur_type_never_issue_or_late():
    r = R(tipe="Hari Libur", masuk=None, keluar=None)
    assert r["has_issue"] == 0
    assert r["terlambat_menit"] == 0


def test_overnight_clamped_to_zero():
    assert R(masuk="16:00", keluar="08:00")["kerja_jam"] == 0.0


def test_hari_name_indonesia():
    assert hari_name("2026-05-06") == "Rabu"    # Wednesday
    assert hari_name("2026-05-09") == "Sabtu"   # Saturday
