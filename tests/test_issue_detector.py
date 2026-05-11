from src.core.issue_detector import is_issue
from src.parsers.fingerprint import FingerprintRow


def _row(**kwargs) -> FingerprintRow:
    defaults = dict(
        nama="X", no_staff="9001", dept="T",
        tanggal="2026-04-01", hari="Senin",
        tipe="Hari Kerja", jadwal="08.00 - 16.00",
        masuk="08.00", keluar="16.00",
        kerja_jam=8.0, lembur_jam=None,
        terlambat_menit=0, source_file="x",
    )
    defaults.update(kwargs)
    return FingerprintRow(**defaults)


def test_no_issue_when_both_filled():
    assert is_issue(_row()) is False


def test_issue_when_masuk_empty():
    assert is_issue(_row(masuk=None)) is True


def test_issue_when_keluar_empty():
    assert is_issue(_row(keluar=None)) is True


def test_issue_when_both_empty():
    assert is_issue(_row(masuk=None, keluar=None)) is True


def test_no_issue_on_istirahat_even_if_empty():
    assert is_issue(_row(tipe="Istirahat", masuk=None, keluar=None)) is False
