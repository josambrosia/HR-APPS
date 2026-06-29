from src.core.heatmap import STATUS_COLORS


def test_libur_nodata_na_all_distinct():
    libur = STATUS_COLORS["libur"]
    nodata = STATUS_COLORS["nodata"]
    na = STATUS_COLORS["na"]
    assert libur != nodata
    assert libur != na
    assert nodata != na


def test_libur_is_slate():
    assert STATUS_COLORS["libur"] == "#39414F"
