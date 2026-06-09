from src.db.schema import init_db
from src.db.connection import get_connection
from src.db.employees import upsert_employee
from src.db.attendance import upsert_attendance
from src.db.holidays import mark_holidays
from src.db.outlier import exclude_employee
from src.core.heatmap import build_heatmap_context


def _seed(conn):
    a = upsert_employee(conn, no_staff="1", nama="ANDI", dept="IT")
    b = upsert_employee(conn, no_staff="2", nama="BUDI", dept="HR")
    upsert_attendance(conn, employee_id=a, tanggal="2026-05-04", hari="Senin",
                      tipe="Hari Kerja", jadwal="", masuk="09:15", keluar="16:30",
                      kerja_jam=None, lembur_jam=None, terlambat_menit=75,
                      has_issue=0, imported_from="W")
    return a, b


def test_context_shape_and_status(temp_db_path):
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        a, b = _seed(conn)
        ctx = build_heatmap_context(conn, "2026-05", exclude_outliers=False)
    assert ctx["month_label"] == "Mei 2026"
    assert ctx["prev_month"] == "2026-04" and ctx["next_month"] == "2026-06"
    assert ctx["is_empty"] is False
    names = [e["nama"] for e in ctx["employees"]]
    assert names == ["ANDI", "BUDI"]              # active, A-Z
    andi = ctx["employees"][0]
    assert andi["cells"][4]["status"] == "parah"  # 75 min late >= 60
    assert andi["cells"][4]["code"] == "TB"
    # a day with no row, weekday -> nodata; a weekend -> libur
    assert andi["cells"][1]["status"] in ("nodata", "libur")
    assert andi["hk"] == 1                          # only the one attended day


def test_context_excludes_outlier(temp_db_path):
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        a, b = _seed(conn)
        exclude_employee(conn, b, "2026-05")
        ctx = build_heatmap_context(conn, "2026-05", exclude_outliers=True)
    assert [e["nama"] for e in ctx["employees"]] == ["ANDI"]


def test_context_empty_month(temp_db_path):
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        ctx = build_heatmap_context(conn, "2026-05", exclude_outliers=False)
    assert ctx["is_empty"] is True
