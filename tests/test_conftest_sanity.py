def test_fixtures_exist(synthetic_fingerprint_xls, synthetic_monthly_xlsx, temp_db_path):
    assert synthetic_fingerprint_xls.exists()
    assert synthetic_monthly_xlsx.exists()
    assert not temp_db_path.exists()  # db not created yet
