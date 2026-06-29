from src import config

def test_default_late_tolerance():
    assert config.DEFAULT_LATE_TOLERANCE_MIN == 12

def test_heatmap_dinas_reasons():
    # v21: terlambat_lain joins the Dinas group so the heatmap matches the
    # legend label "Dinas (…/terlambat dengan alasan)".
    assert config.HEATMAP_DINAS_REASONS == (
        "tugas_lapangan", "tugas_paparan", "tugas_belajar",
        "terlambat_kerja", "terlambat_lain")
    for r in config.HEATMAP_DINAS_REASONS:
        assert r in config.REASON_CATEGORIES

def test_coaching_excluded_includes_justified_late():
    # v21: terlambat_lain ("Terlambat dengan alasan") is lateness-justified too,
    # so its minutes are zeroed and it is dropped from coaching.
    assert config.COACHING_EXCLUDED == (
        "tugas_lapangan", "tugas_paparan", "terlambat_kerja", "terlambat_lain")
