# tests/test_heatmap_cell_status.py
from src.core.heatmap import cell_status, STATUS_COLORS, STATUS_CODES, STATUS_LABELS

def row(**kw):
    base = dict(tipe="Hari Kerja", masuk="08:00", keluar="16:00",
                terlambat_menit=0, reason_category=None)
    base.update(kw); return base

def cs(r, **kw):
    opts = dict(tolerance=12, severe=60, is_weekend=False, is_holiday=False)
    opts.update(kw); return cell_status(r, **opts)

def test_libur_weekend_holiday():
    assert cs(None, is_weekend=True) == "libur"
    assert cs(None, is_holiday=True) == "libur"
    assert cs(row(tipe="Hari Libur")) == "libur"

def test_nodata():
    assert cs(None) == "nodata"           # working day, no row

def test_lateness_tiers():
    assert cs(row(terlambat_menit=12)) == "hadir"
    assert cs(row(terlambat_menit=13)) == "sedang"
    assert cs(row(terlambat_menit=59)) == "sedang"
    assert cs(row(terlambat_menit=60)) == "parah"
    assert cs(row(terlambat_menit=None)) == "hadir"   # NULL -> 0

def test_reason_overrides_lateness():
    assert cs(row(terlambat_menit=90, reason_category="terlambat_kerja")) == "dinas"
    assert cs(row(reason_category="tugas_belajar")) == "dinas"
    assert cs(row(reason_category="izin_sakit")) == "sakit"
    assert cs(row(reason_category="cuti")) == "cuti"
    assert cs(row(masuk=None, reason_category="lupa_absen_pulang")) == "lupa"
    assert cs(row(masuk=None, reason_category="na")) == "na"

def test_terlambat_lain_falls_through():
    # not a leave reason -> shown by lateness magnitude
    assert cs(row(terlambat_menit=30, reason_category="terlambat_lain")) == "sedang"
    assert cs(row(terlambat_menit=80, reason_category="terlambat_lain")) == "parah"

def test_absen_tanpa_alasan():
    assert cs(row(masuk=None, reason_category=None)) == "mangkir"

def test_dicts_cover_all_statuses():
    for k in ("hadir","dinas","sedang","parah","sakit","cuti","lupa","mangkir","na","libur","nodata"):
        assert k in STATUS_COLORS and k in STATUS_CODES and k in STATUS_LABELS
