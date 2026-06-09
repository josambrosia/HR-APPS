from src import config

def test_default_late_tolerance():
    assert config.DEFAULT_LATE_TOLERANCE_MIN == 12

def test_heatmap_dinas_reasons():
    assert config.HEATMAP_DINAS_REASONS == (
        "tugas_lapangan", "tugas_paparan", "tugas_belajar", "terlambat_kerja")
    for r in config.HEATMAP_DINAS_REASONS:
        assert r in config.REASON_CATEGORIES

def test_coaching_excluded_unchanged():
    # Heatmap green group is broader than coaching; coaching set stays 3.
    assert config.COACHING_EXCLUDED == ("tugas_lapangan", "tugas_paparan", "terlambat_kerja")
