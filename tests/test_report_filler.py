from openpyxl import load_workbook
from src.db.schema import init_db
from src.db.connection import get_connection
from src.db.employees import upsert_employee
from src.db.attendance import upsert_attendance, set_reason
from src.core.report_filler import fill_monthly_report


def _seed(conn):
    emp_id = upsert_employee(conn, no_staff="9001", nama="BUDI", dept="TEST")
    # Day 2: lupa keluar — user inputs "lupa_absen_pulang"
    upsert_attendance(conn, employee_id=emp_id, tanggal="2026-04-02",
                      hari="Selasa", tipe="Hari Kerja", jadwal="08.00 - 16.00",
                      masuk="08.10", keluar=None, kerja_jam=None,
                      lembur_jam=None, terlambat_menit=10,
                      has_issue=1, imported_from="W1.xls")
    rec = conn.execute(
        "SELECT id FROM attendance_records WHERE tanggal='2026-04-02'"
    ).fetchone()
    set_reason(conn, attendance_id=rec["id"], category="lupa_absen_pulang", detail=None)
    # Day 3: tidak masuk — left as NA
    upsert_attendance(conn, employee_id=emp_id, tanggal="2026-04-03",
                      hari="Rabu", tipe="Hari Kerja", jadwal="08.00 - 16.00",
                      masuk=None, keluar=None, kerja_jam=None,
                      lembur_jam=None, terlambat_menit=None,
                      has_issue=1, imported_from="W1.xls")


def test_fill_writes_alasan_ijin_to_correct_rows(synthetic_monthly_xlsx, temp_db_path):
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        _seed(conn)
        out_path, summary = fill_monthly_report(synthetic_monthly_xlsx, conn)

    assert out_path.exists()
    assert out_path.name.endswith("[filled].xlsx")
    assert out_path != synthetic_monthly_xlsx  # original untouched

    wb = load_workbook(out_path)
    ws = wb.active
    # Row 3: BUDI 2026-04-01 (no issue, no reason → no alasan written)
    # Row 4: BUDI 2026-04-02 (lupa_absen_pulang → "Lupa Absen Pulang")
    # Row 5: BUDI 2026-04-03 (no reason → "NA / Belum ada kabar")
    assert ws.cell(row=3, column=17).value in (None, "")
    assert ws.cell(row=4, column=17).value == "Lupa Absen Pulang"
    assert ws.cell(row=5, column=17).value == "NA / Belum ada kabar"


def test_fill_returns_summary(synthetic_monthly_xlsx, temp_db_path):
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        _seed(conn)
        out_path, summary = fill_monthly_report(synthetic_monthly_xlsx, conn)
    assert summary.filled_count == 1
    assert summary.na_count == 1
