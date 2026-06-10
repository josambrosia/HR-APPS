# tests/test_heatmap_helpers.py
from src.core.heatmap import pct_band_color, needs_attention, sort_employees


def test_pct_band_color():
    assert pct_band_color(100) == "#10B981"
    assert pct_band_color(90) == "#10B981"
    assert pct_band_color(89) == "#FBBF24"
    assert pct_band_color(75) == "#FBBF24"
    assert pct_band_color(74) == "#EC4899"
    assert pct_band_color(0) == "#EC4899"


def test_needs_attention():
    assert needs_attention({"X": 1, "TB": 0}) is True
    assert needs_attention({"X": 0, "TB": 2}) is True
    assert needs_attention({"X": 0, "TB": 0}) is False


def _emp(nama, x, pct, td, tt):
    return {"nama": nama, "summary": {"X": x},
            "sorotan": {"pct_hadir": pct, "telat_days": td, "telat_total": tt}}


def test_sort_employees():
    emps = [_emp("Budi", 0, 100, 1, 10), _emp("Andi", 2, 80, 3, 50),
            _emp("Citra", 0, 90, 0, 0)]
    assert [e["nama"] for e in sort_employees(emps, "nama")] == ["Andi", "Budi", "Citra"]
    assert [e["nama"] for e in sort_employees(emps, "kehadiran")] == ["Andi", "Citra", "Budi"]
    assert [e["nama"] for e in sort_employees(emps, "telat")] == ["Andi", "Budi", "Citra"]
    assert [e["nama"] for e in sort_employees(emps, "absen")] == ["Andi", "Budi", "Citra"]
