# tests/test_config_severe_lateness.py
from src import config


def test_default_threshold_is_60():
    assert config.DEFAULT_SEVERE_LATENESS_THRESHOLD_MIN == 60


def test_severe_lateness_categories_subset():
    expected = ("tugas_lapangan", "tugas_paparan", "terlambat_kerja",
                "terlambat_lain", "izin_sakit", "cuti", "na")
    assert config.SEVERE_LATENESS_CATEGORIES == expected
    # every entry must be a valid global reason category
    for c in config.SEVERE_LATENESS_CATEGORIES:
        assert c in config.REASON_CATEGORIES
    # lupa/libur explicitly excluded
    for c in ("lupa_absen_datang", "lupa_absen_pulang", "libur"):
        assert c not in config.SEVERE_LATENESS_CATEGORIES
