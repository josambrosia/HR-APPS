import pytest
from src.core.reason_mapper import render_alasan_ijin, REASON_LABELS


def test_all_10_categories_present():
    assert set(REASON_LABELS.keys()) == {
        "tugas_lapangan", "tugas_paparan", "izin_sakit", "cuti", "tugas_belajar",
        "terlambat_kerja", "terlambat_lain", "lupa_absen", "libur", "na",
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


def test_render_alasan_ijin_libur():
    assert render_alasan_ijin("libur", None) == "Libur"


def test_render_alasan_ijin_tugas_belajar():
    assert render_alasan_ijin("tugas_belajar", None) == "Tugas Belajar/Kuliah"


def test_libur_in_reason_categories():
    from src.config import REASON_CATEGORIES
    assert "libur" in REASON_CATEGORIES


def test_reason_categories_and_labels_in_sync():
    """REASON_CATEGORIES (config) and REASON_LABELS (reason_mapper) must
    have identical key sets — a key in one but not the other is a latent
    runtime ValueError in render_alasan_ijin."""
    from src.config import REASON_CATEGORIES
    assert set(REASON_CATEGORIES) == set(REASON_LABELS.keys())
