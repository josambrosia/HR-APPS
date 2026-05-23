import pytest
from src.core.reason_mapper import render_alasan_ijin, REASON_LABELS, effective_attendance


def test_all_categories_present():
    """v15: split lupa_absen → lupa_absen_datang + lupa_absen_pulang.
    Both new + old (transitional) categories live in REASON_LABELS until
    legacy cleanup task drops `lupa_absen`.
    """
    assert set(REASON_LABELS.keys()) == {
        "tugas_lapangan", "tugas_paparan", "izin_sakit", "cuti", "tugas_belajar",
        "terlambat_kerja", "terlambat_lain",
        "lupa_absen",            # transitional — dropped in cleanup task
        "lupa_absen_datang",     # NEW
        "lupa_absen_pulang",     # NEW
        "libur", "na",
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


def _att_row(reason_category=None, masuk="09:40", keluar="16:00", terlambat_menit=100):
    return {
        "reason_category": reason_category, "masuk": masuk,
        "keluar": keluar, "terlambat_menit": terlambat_menit,
    }


def test_effective_attendance_work_justified_late_with_clock_in():
    # tugas_lapangan is the representative; spot-check that all COACHING_EXCLUDED
    # members share the same path
    for cat in ("tugas_lapangan", "tugas_paparan", "terlambat_kerja"):
        row = _att_row(reason_category=cat, masuk="09:40", terlambat_menit=100)
        eff = effective_attendance(row, schedule_start="08.00", lupa_penalty_min=15)
        assert eff == {"masuk": "08:00", "terlambat_menit": 0}, f"Failed for {cat}"


def test_effective_attendance_work_justified_late_no_badge():
    row = _att_row(reason_category="tugas_lapangan", masuk=None, keluar=None,
                   terlambat_menit=None)
    eff = effective_attendance(row, schedule_start="08.00", lupa_penalty_min=15)
    assert eff == {"masuk": None, "terlambat_menit": None}


def test_effective_attendance_forgot_clock_in():
    row = _att_row(reason_category="lupa_absen", masuk=None, keluar="16:05",
                   terlambat_menit=None)
    eff = effective_attendance(row, schedule_start="08.00", lupa_penalty_min=15)
    assert eff == {"masuk": "08:15", "terlambat_menit": 15}


def test_effective_attendance_forgot_clock_out_untouched():
    row = _att_row(reason_category="lupa_absen", masuk="08:05", keluar=None,
                   terlambat_menit=5)
    eff = effective_attendance(row, schedule_start="08.00", lupa_penalty_min=15)
    assert eff == {"masuk": "08:05", "terlambat_menit": 5}


def test_effective_attendance_other_category_untouched():
    row = _att_row(reason_category="izin_sakit", masuk="08:30", terlambat_menit=30)
    eff = effective_attendance(row, schedule_start="08.00", lupa_penalty_min=15)
    assert eff == {"masuk": "08:30", "terlambat_menit": 30}


def test_effective_attendance_no_reason_untouched():
    row = _att_row(reason_category=None, masuk="08:30", terlambat_menit=30)
    eff = effective_attendance(row, schedule_start="08.00", lupa_penalty_min=15)
    assert eff == {"masuk": "08:30", "terlambat_menit": 30}


def test_effective_attendance_custom_penalty():
    row = _att_row(reason_category="lupa_absen", masuk=None, keluar="16:00",
                   terlambat_menit=None)
    eff = effective_attendance(row, schedule_start="08.00", lupa_penalty_min=20)
    assert eff == {"masuk": "08:20", "terlambat_menit": 20}


def test_effective_attendance_lupa_datang_forgot_clock_in():
    """Lupa Absen Datang with masuk=NULL, keluar set: penalty applied."""
    row = _att_row(reason_category="lupa_absen_datang", masuk=None, keluar="16:05",
                   terlambat_menit=None)
    eff = effective_attendance(row, schedule_start="08.00", lupa_penalty_min=15)
    assert eff == {"masuk": "08:15", "terlambat_menit": 15}


def test_effective_attendance_lupa_datang_both_null():
    """Lupa Absen Datang with both masuk AND keluar NULL: penalty still applied
    because user explicitly labeled the row as 'datang missing'."""
    row = _att_row(reason_category="lupa_absen_datang", masuk=None, keluar=None,
                   terlambat_menit=None)
    eff = effective_attendance(row, schedule_start="08.00", lupa_penalty_min=15)
    assert eff == {"masuk": "08:15", "terlambat_menit": 15}


def test_effective_attendance_lupa_datang_zero_penalty():
    """Penalty=0 means karyawan dianggap masuk tepat pukul 08:00, no terlambat."""
    row = _att_row(reason_category="lupa_absen_datang", masuk=None, keluar="16:00",
                   terlambat_menit=None)
    eff = effective_attendance(row, schedule_start="08.00", lupa_penalty_min=0)
    assert eff == {"masuk": "08:00", "terlambat_menit": 0}


def test_effective_attendance_lupa_pulang_no_correction():
    """Lupa Absen Pulang: raw masuk preserved, no penalty applied to terlambat."""
    row = _att_row(reason_category="lupa_absen_pulang", masuk="08:05", keluar=None,
                   terlambat_menit=5)
    eff = effective_attendance(row, schedule_start="08.00", lupa_penalty_min=15)
    assert eff == {"masuk": "08:05", "terlambat_menit": 5}
