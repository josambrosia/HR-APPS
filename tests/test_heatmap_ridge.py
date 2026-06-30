from src.core.heatmap import build_lateness_ridge, severity_color


def test_severity_color_ramp():
    assert severity_color(5, 12, 90) == "#10B981"    # on-time → green
    assert severity_color(30, 12, 90) == "#FBBF24"   # mild (< severe/2) → amber
    assert severity_color(70, 12, 90) == "#FB923C"   # moderate (< severe) → orange
    assert severity_color(120, 12, 90) == "#EF4444"  # severe (>= severe) → red


def test_build_lateness_ridge_marks_peaks_and_dinas():
    cells = {
        1: {"status": "hadir", "telat": 0},
        2: {"status": "sedang", "telat": 40},
        3: {"status": "parah", "telat": 120},
        4: {"status": "dinas", "telat": 30},   # excused → baseline dot, not a peak
        5: {"status": "libur", "telat": "—"},
    }
    days = [1, 2, 3, 4, 5]
    r = build_lateness_ridge(cells, days, tolerance=12, severe=90)
    assert {p["m"] for p in r["peaks"]} == {40, 120}   # only sedang/parah peak
    assert len(r["dinas"]) == 1                          # dinas → baseline dot
    assert len(r["segments"]) == len(days) - 1
    assert r["tol_y"] is not None
    cols = {p["m"]: p["color"] for p in r["peaks"]}
    assert cols[120] == "#EF4444" and cols[40] == "#FBBF24"


def test_build_lateness_ridge_handles_empty_cells():
    """Punctual / no-data employee: flat ridge, no peaks, no crash."""
    r = build_lateness_ridge({}, [1, 2, 3], tolerance=12, severe=90)
    assert r["peaks"] == [] and r["dinas"] == []
    assert r["fill"] and r["axis"]
