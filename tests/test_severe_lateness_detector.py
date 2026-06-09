# tests/test_severe_lateness_detector.py
from src.core.severe_lateness_detector import is_severe_lateness


def _row(tipe="Hari Kerja", masuk="09:15", keluar="16:30", terlambat=75):
    return {"tipe": tipe, "masuk": masuk, "keluar": keluar, "terlambat_menit": terlambat}


def test_is_severe_at_boundary():
    assert is_severe_lateness(_row(terlambat=60), 60) is True
    assert is_severe_lateness(_row(terlambat=59), 60) is False


def test_is_severe_requires_both_punches():
    assert is_severe_lateness(_row(masuk=None), 60) is False
    assert is_severe_lateness(_row(keluar=None), 60) is False


def test_is_severe_hari_kerja_only():
    assert is_severe_lateness(_row(tipe="Hari Libur"), 60) is False


def test_is_severe_null_terlambat_not_severe():
    assert is_severe_lateness(_row(terlambat=None), 60) is False
