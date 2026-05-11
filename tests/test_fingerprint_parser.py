from src.parsers.fingerprint import parse_fingerprint_file, FingerprintRow


def test_parse_returns_normalized_rows(synthetic_fingerprint_xls):
    rows = parse_fingerprint_file(synthetic_fingerprint_xls)
    # Synthetic fixture has 5 data rows after filtering Total Personal:
    # BUDI Mon, BUDI Tue, BUDI Wed, BUDI Sat (Istirahat), ANI Mon
    assert len(rows) == 5


def test_parse_filters_total_personal(synthetic_fingerprint_xls):
    rows = parse_fingerprint_file(synthetic_fingerprint_xls)
    for r in rows:
        assert "Total" not in (r.nama or "")


def test_parse_decimal_fields_normalized(synthetic_fingerprint_xls):
    rows = parse_fingerprint_file(synthetic_fingerprint_xls)
    # Find BUDI Mon row
    budi_mon = [r for r in rows if r.nama == "BUDI" and r.tanggal == "2026-04-01"][0]
    assert budi_mon.kerja_jam == 7.9
    assert budi_mon.terlambat_menit == 5
    assert budi_mon.masuk == "08:05"
    assert budi_mon.keluar == "16:30"


def test_parse_marks_issue_when_keluar_empty(synthetic_fingerprint_xls):
    rows = parse_fingerprint_file(synthetic_fingerprint_xls)
    budi_tue = [r for r in rows if r.nama == "BUDI" and r.tanggal == "2026-04-02"][0]
    assert budi_tue.masuk == "08:10"
    assert budi_tue.keluar is None
    # has_issue is computed by detector, not parser. Parser only normalizes.


def test_parse_extracts_no_staff_and_dept(synthetic_fingerprint_xls):
    rows = parse_fingerprint_file(synthetic_fingerprint_xls)
    budi = [r for r in rows if r.nama == "BUDI"][0]
    assert budi.no_staff == "9001"
    assert budi.dept == "TEST"
