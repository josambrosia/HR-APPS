from src.parsers.fingerprint import FingerprintRow


def is_issue(row: FingerprintRow) -> bool:
    """An issue is a Hari Kerja with missing Masuk OR Keluar."""
    if row.tipe != "Hari Kerja":
        return False
    return row.masuk is None or row.keluar is None
