import pytest
from src.core.reason_mapper import render_alasan_ijin, REASON_LABELS


def test_all_8_categories_present():
    assert set(REASON_LABELS.keys()) == {
        "tugas_lapangan", "tugas_paparan", "izin_sakit", "cuti",
        "terlambat_kerja", "terlambat_lain", "lupa_absen", "na",
    }


def test_render_with_detail():
    assert render_alasan_ijin("tugas_lapangan", "Sragen") == "Tugas Lapangan di Sragen"
    assert render_alasan_ijin("tugas_paparan", "PT FAFIFU") == "Tugas Paparan di PT FAFIFU"
    assert render_alasan_ijin("terlambat_kerja", "meeting client") == \
        "Masuk Terlambat dengan Alasan Pekerjaan: meeting client"
    assert render_alasan_ijin("terlambat_lain", "bertemu dokter") == \
        "Terlambat dengan alasan: bertemu dokter"


def test_render_without_detail():
    assert render_alasan_ijin("izin_sakit", None) == "Izin Sakit"
    assert render_alasan_ijin("cuti", None) == "Cuti"
    assert render_alasan_ijin("lupa_absen", None) == "Lupa Absen"
    assert render_alasan_ijin("na", None) == "NA / Belum ada kabar"


def test_render_unknown_category_raises():
    with pytest.raises(ValueError):
        render_alasan_ijin("invalid_cat", None)
