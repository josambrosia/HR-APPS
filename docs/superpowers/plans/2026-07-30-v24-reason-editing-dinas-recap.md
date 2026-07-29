# v24.0.0 — Edit Alasan + Rekap Dinas & Paparan — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Izinkan pengisian `reason_category` langsung dari editor absensi Heatmap (termasuk hari bersih & telat ringan), dan tambahkan layar "Rekap Dinas" (panel bulan + papan peringkat dengan rentang 3/6 bln/Tahun ini) yang bisa dicetak.

**Architecture:** Logika rentang & peringkat murni di `src/core/dinas_recap.py` (tanpa Tk/SQL). Query agregasi tunggal di `src/db/attendance.py` melayani kedua panel. Layar `src/ui/screens/dinas_recap.py` hanya merakit widget. Cetak lewat `src/reports/dinas_recap_print.py` + template Jinja2, mengikuti pola `heatmap_print` (render string → temp file → browser).

**Tech Stack:** Python 3.13, customtkinter, SQLite, Jinja2, pytest, PyInstaller, Inno Setup 6.

**Spec:** `docs/superpowers/specs/2026-07-30-reason-editing-dinas-paparan-recap-design.md`

---

## File Structure

| File | Tanggung jawab |
|------|----------------|
| `src/core/dinas_recap.py` (baru) | Resolusi rentang (`resolve_range`), label rentang, penomoran peringkat (`rank`), konstanta span. Murni — tanpa DB/Tk. |
| `src/db/attendance.py` (ubah) | `count_dinas_paparan_by_employee(conn, start, end)` — satu agregasi untuk kedua panel. |
| `src/ui/components/attendance_edit_dialog.py` (ubah) | Seksi "Alasan / Keterangan" kontekstual + simpan/hapus alasan. |
| `src/ui/screens/dinas_recap.py` (baru) | Layar 2 panel + segmented rentang + tombol Cetak. |
| `src/ui/app.py` (ubah) | Item nav "Rekap Dinas" + cabang `_create_screen`. |
| `src/reports/dinas_recap_print.py` (baru) | Bangun konteks cetak + render template. |
| `src/reports/templates/dinas_recap_print.html.j2` (baru) | Lembar cetak A4 potret. |
| `HR-Absensi.spec` (ubah) | Bundling template baru. |
| `src/config.py` (ubah) | `APP_VERSION` 24.0.0 + entri changelog. |

---

### Task 1: Core — resolusi rentang & peringkat

**Files:**
- Create: `src/core/dinas_recap.py`
- Test: `tests/test_dinas_recap_core.py`

- [ ] **Step 1: Tulis test yang gagal**

```python
# tests/test_dinas_recap_core.py
import pytest

from src.core.dinas_recap import (
    SPANS, DEFAULT_SPAN, resolve_range, span_label, rank)


def test_default_span_is_year():
    assert DEFAULT_SPAN == "year"
    assert [s[0] for s in SPANS] == ["3m", "6m", "year"]
    assert dict(SPANS)["year"] == "Tahun ini"


def test_year_span_is_full_calendar_year():
    assert resolve_range("2026-07", "year") == ("2026-01-01", "2026-12-31")
    assert resolve_range("2026-01", "year") == ("2026-01-01", "2026-12-31")


def test_3m_span_is_inclusive_backwards():
    # Juli 2026 -> Mei, Jun, Jul
    assert resolve_range("2026-07", "3m") == ("2026-05-01", "2026-07-31")


def test_6m_span_is_inclusive_backwards():
    # Juli 2026 -> Feb..Jul
    assert resolve_range("2026-07", "6m") == ("2026-02-01", "2026-07-31")


def test_span_crosses_year_boundary():
    # Februari 2026, 6 bulan -> September 2025 .. Februari 2026
    assert resolve_range("2026-02", "6m") == ("2025-09-01", "2026-02-28")
    # Januari 2026, 3 bulan -> November 2025 .. Januari 2026
    assert resolve_range("2026-01", "3m") == ("2025-11-01", "2026-01-31")


def test_end_day_follows_month_length():
    assert resolve_range("2026-02", "3m")[1] == "2026-02-28"
    assert resolve_range("2024-02", "3m")[1] == "2024-02-29"  # kabisat


def test_unknown_span_raises():
    with pytest.raises(KeyError):
        resolve_range("2026-07", "9m")


def test_span_label_same_year_omits_first_year():
    assert span_label("2026-07", "year") == "Januari – Desember 2026"
    assert span_label("2026-07", "3m") == "Mei – Juli 2026"


def test_span_label_cross_year_shows_both():
    assert span_label("2026-02", "6m") == "September 2025 – Februari 2026"


def test_rank_numbers_sequentially_and_copies():
    rows = [{"nama": "A", "total": 9}, {"nama": "B", "total": 4}]
    out = rank(rows)
    assert [r["rank"] for r in out] == [1, 2]
    assert "rank" not in rows[0]  # input tidak dimutasi


def test_rank_empty_list():
    assert rank([]) == []
```

- [ ] **Step 2: Jalankan test — pastikan gagal**

Run: `.venv/Scripts/python.exe -m pytest tests/test_dinas_recap_core.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.core.dinas_recap'`

- [ ] **Step 3: Implementasi minimal**

```python
# src/core/dinas_recap.py
"""Rentang & peringkat untuk layar Rekap Dinas — logika murni (tanpa DB/Tk).

Rentang papan peringkat: "Tahun ini" (Jan–Des tahun bulan terpilih, default)
atau 3/6 bulan terakhir yang dihitung MUNDUR dan INKLUSIF dari bulan terpilih.
Lihat docs/superpowers/specs/2026-07-30-reason-editing-dinas-paparan-recap-design.md.
"""
from calendar import monthrange
from typing import Dict, List, Tuple

from src.core.week_utils import MONTH_NAMES_ID

# (id, label) — urutan tampil pada segmented control.
SPANS: Tuple[Tuple[str, str], ...] = (
    ("3m", "3 bln"),
    ("6m", "6 bln"),
    ("year", "Tahun ini"),
)
DEFAULT_SPAN = "year"

# Berapa bulan mundur dari bulan terpilih (0 = bulan terpilih saja).
_MONTHS_BACK: Dict[str, int] = {"3m": 2, "6m": 5}


def resolve_range(year_month: str, span: str) -> Tuple[str, str]:
    """('YYYY-MM', span) -> (start_iso, end_iso), keduanya inklusif.

    span 'year' -> 1 Jan .. 31 Des tahun `year_month`.
    span '3m'/'6m' -> awal bulan (m-2 / m-5) .. akhir bulan terpilih.
    Melempar KeyError untuk span tak dikenal.
    """
    y, m = int(year_month[:4]), int(year_month[5:7])
    if span == "year":
        return f"{y:04d}-01-01", f"{y:04d}-12-31"
    back = _MONTHS_BACK[span]
    sy, sm = y, m - back
    while sm < 1:
        sm += 12
        sy -= 1
    last = monthrange(y, m)[1]
    return f"{sy:04d}-{sm:02d}-01", f"{y:04d}-{m:02d}-{last:02d}"


def span_label(year_month: str, span: str) -> str:
    """Label rentang untuk header layar & cetak, mis. 'Mei – Juli 2026'.
    Tahun awal ditulis hanya bila rentangnya melintasi tahun."""
    start, end = resolve_range(year_month, span)
    sy, sm = int(start[:4]), int(start[5:7])
    ey, em = int(end[:4]), int(end[5:7])
    if sy == ey:
        return f"{MONTH_NAMES_ID[sm]} – {MONTH_NAMES_ID[em]} {ey}"
    return f"{MONTH_NAMES_ID[sm]} {sy} – {MONTH_NAMES_ID[em]} {ey}"


def rank(rows: List[dict]) -> List[dict]:
    """Beri nomor peringkat 1..N pada baris yang SUDAH terurut dari SQL.
    Mengembalikan salinan dangkal — input tidak dimutasi."""
    return [{**r, "rank": i} for i, r in enumerate(rows, start=1)]
```

- [ ] **Step 4: Jalankan test — pastikan lulus**

Run: `.venv/Scripts/python.exe -m pytest tests/test_dinas_recap_core.py -q`
Expected: PASS (11 passed)

- [ ] **Step 5: Commit**

```bash
git add src/core/dinas_recap.py tests/test_dinas_recap_core.py
git commit -m "feat(v24): core rentang + peringkat Rekap Dinas (pure)"
```

---

### Task 2: DB — agregasi dinas & paparan per pegawai

**Files:**
- Modify: `src/db/attendance.py` (tambah fungsi di akhir file)
- Test: `tests/test_dinas_recap_db.py`

- [ ] **Step 1: Tulis test yang gagal**

```python
# tests/test_dinas_recap_db.py
import pytest

from src.db.schema import init_db
from src.db.connection import get_connection
from src.db.employees import upsert_employee
from src.db.attendance import (
    save_manual_attendance, set_reason, count_dinas_paparan_by_employee)


def _row(conn, eid, tanggal, category):
    save_manual_attendance(
        conn, employee_id=eid, tanggal=tanggal, hari="Senin", tipe="Hari Kerja",
        jadwal=None, masuk="08:00", keluar="16:00", kerja_jam=8.0,
        lembur_jam=0.0, terlambat_menit=0, has_issue=0)
    rid = conn.execute(
        "SELECT id FROM attendance_records WHERE employee_id=? AND tanggal=?",
        (eid, tanggal)).fetchone()["id"]
    if category:
        set_reason(conn, attendance_id=rid, category=category, detail=None)


@pytest.fixture
def db(tmp_path):
    p = tmp_path / "hr.db"
    init_db(p)
    with get_connection(p) as conn:
        a = upsert_employee(conn, no_staff="S1", nama="Andi", dept="Ops")
        b = upsert_employee(conn, no_staff="S2", nama="Budi", dept="Sales")
        c = upsert_employee(conn, no_staff="S3", nama="Cici", dept="HR")
        # Andi: 2 dinas + 1 paparan = 3
        _row(conn, a, "2026-07-01", "tugas_lapangan")
        _row(conn, a, "2026-07-02", "tugas_lapangan")
        _row(conn, a, "2026-07-03", "tugas_paparan")
        # Budi: 3 paparan = 3 (seri dengan Andi; Andi menang via dinas lebih banyak)
        _row(conn, b, "2026-07-06", "tugas_paparan")
        _row(conn, b, "2026-07-07", "tugas_paparan")
        _row(conn, b, "2026-07-08", "tugas_paparan")
        # Cici: hanya belajar & tanpa alasan -> tidak masuk rekap
        _row(conn, c, "2026-07-06", "tugas_belajar")
        _row(conn, c, "2026-07-07", None)
        # Di luar rentang Juli
        _row(conn, a, "2026-06-30", "tugas_lapangan")
        _row(conn, a, "2026-08-01", "tugas_paparan")
    yield p


def test_counts_split_dinas_and_paparan(db):
    with get_connection(db) as conn:
        rows = count_dinas_paparan_by_employee(conn, "2026-07-01", "2026-07-31")
    by_name = {r["nama"]: r for r in rows}
    assert by_name["Andi"]["dinas"] == 2
    assert by_name["Andi"]["paparan"] == 1
    assert by_name["Andi"]["total"] == 3
    assert by_name["Budi"]["dinas"] == 0
    assert by_name["Budi"]["paparan"] == 3


def test_excludes_employees_without_dinas_or_paparan(db):
    with get_connection(db) as conn:
        rows = count_dinas_paparan_by_employee(conn, "2026-07-01", "2026-07-31")
    assert "Cici" not in {r["nama"] for r in rows}


def test_tugas_belajar_not_counted(db):
    with get_connection(db) as conn:
        rows = count_dinas_paparan_by_employee(conn, "2026-07-01", "2026-07-31")
    assert sum(r["total"] for r in rows) == 6  # 3 Andi + 3 Budi, belajar diabaikan


def test_date_bounds_are_inclusive_and_exclusive_outside(db):
    with get_connection(db) as conn:
        juli = count_dinas_paparan_by_employee(conn, "2026-07-01", "2026-07-31")
        juni = count_dinas_paparan_by_employee(conn, "2026-06-01", "2026-06-30")
    assert {r["nama"] for r in juli} == {"Andi", "Budi"}
    assert [(r["nama"], r["total"]) for r in juni] == [("Andi", 1)]


def test_order_total_desc_then_dinas_desc_then_nama(db):
    with get_connection(db) as conn:
        rows = count_dinas_paparan_by_employee(conn, "2026-07-01", "2026-07-31")
    # Andi & Budi sama-sama total 3; Andi punya dinas 2 -> di atas
    assert [r["nama"] for r in rows] == ["Andi", "Budi"]


def test_includes_dept_and_employee_id(db):
    with get_connection(db) as conn:
        rows = count_dinas_paparan_by_employee(conn, "2026-07-01", "2026-07-31")
    assert rows[0]["dept"] == "Ops"
    assert isinstance(rows[0]["employee_id"], int)


def test_empty_range_returns_empty_list(db):
    with get_connection(db) as conn:
        assert count_dinas_paparan_by_employee(conn, "2030-01-01", "2030-12-31") == []
```

- [ ] **Step 2: Jalankan test — pastikan gagal**

Run: `.venv/Scripts/python.exe -m pytest tests/test_dinas_recap_db.py -q`
Expected: FAIL — `ImportError: cannot import name 'count_dinas_paparan_by_employee'`

- [ ] **Step 3: Implementasi minimal**

Tambahkan di akhir `src/db/attendance.py`:

```python
# Kategori yang menyusun Rekap Dinas (spec §2 B1/B2). tugas_belajar sengaja
# TIDAK dihitung — rekap hanya memisah Dinas (lapangan) vs Paparan.
DINAS_CATEGORY = "tugas_lapangan"
PAPARAN_CATEGORY = "tugas_paparan"


def count_dinas_paparan_by_employee(conn: sqlite3.Connection, start: str, end: str) -> list[dict]:
    """Jumlah hari dinas & paparan per pegawai dalam [start, end] (inklusif).

    Hanya pegawai dengan minimal 1 dinas/paparan yang dikembalikan (spec D2).
    Urutan: total DESC, dinas DESC, nama ASC — deterministik untuk peringkat.

    Returns list[dict] dengan kunci:
      employee_id, nama, dept, dinas, paparan, total
    """
    rows = conn.execute(
        """
        SELECT e.id AS employee_id, e.nama, e.dept,
               SUM(CASE WHEN ar.reason_category = ? THEN 1 ELSE 0 END) AS dinas,
               SUM(CASE WHEN ar.reason_category = ? THEN 1 ELSE 0 END) AS paparan
          FROM attendance_records ar
          JOIN employees e ON ar.employee_id = e.id
         WHERE ar.tanggal BETWEEN ? AND ?
           AND ar.reason_category IN (?, ?)
         GROUP BY e.id
        HAVING (dinas + paparan) >= 1
         ORDER BY (dinas + paparan) DESC, dinas DESC, e.nama ASC
        """,
        (DINAS_CATEGORY, PAPARAN_CATEGORY, start, end,
         DINAS_CATEGORY, PAPARAN_CATEGORY),
    ).fetchall()
    return [
        {
            "employee_id": r["employee_id"],
            "nama": r["nama"],
            "dept": r["dept"] or "",
            "dinas": r["dinas"],
            "paparan": r["paparan"],
            "total": r["dinas"] + r["paparan"],
        }
        for r in rows
    ]
```

- [ ] **Step 4: Jalankan test — pastikan lulus**

Run: `.venv/Scripts/python.exe -m pytest tests/test_dinas_recap_db.py -q`
Expected: PASS (7 passed)

- [ ] **Step 5: Commit**

```bash
git add src/db/attendance.py tests/test_dinas_recap_db.py
git commit -m "feat(v24): agregasi dinas/paparan per pegawai"
```

---

### Task 3: Editor — seksi alasan kontekstual

**Files:**
- Modify: `src/ui/components/attendance_edit_dialog.py`
- Test: `tests/test_attendance_edit_reason.py`

- [ ] **Step 1: Tulis test yang gagal**

```python
# tests/test_attendance_edit_reason.py
"""Seksi 'Alasan / Keterangan' di editor absensi: opsi kontekstual + simpan."""
import pytest


@pytest.fixture(scope="module")
def root():
    ctk = pytest.importorskip("customtkinter")
    try:
        r = ctk.CTk()
    except Exception as exc:  # pragma: no cover - headless CI
        pytest.skip(f"no Tk display: {exc}")
    r.withdraw()
    yield r
    try:
        r.destroy()
    except Exception:
        pass


def _setup(tmp_path, monkeypatch):
    from src.ui.components import attendance_edit_dialog as D
    from src.db.schema import init_db
    from src.db.connection import get_connection
    from src.db.employees import upsert_employee
    dbp = tmp_path / "hr.db"
    init_db(dbp)
    with get_connection(dbp) as c:
        eid = upsert_employee(c, no_staff="S1", nama="Budi")
    monkeypatch.setattr(D, "DB_PATH", dbp)
    return D, dbp, eid


def _dlg(D, root, eid, tanggal="2026-07-06"):
    return D.AttendanceEditDialog(
        root, employee_id=eid, nama="Budi", tanggal=tanggal,
        on_saved=lambda: None, on_deleted=lambda: None)


def test_late_reasons_hidden_when_not_late(tmp_path, monkeypatch, root):
    from src.core.reason_mapper import REASON_LABELS
    D, _dbp, eid = _setup(tmp_path, monkeypatch)
    dlg = _dlg(D, root, eid)
    try:
        dlg._masuk.insert(0, "08:00")   # tepat waktu
        dlg._keluar.insert(0, "16:00")
        dlg._recompute_preview()
        values = dlg._reason_menu.cget("values")
        assert REASON_LABELS["tugas_paparan"] in values
        assert REASON_LABELS["izin_sakit"] in values
        assert REASON_LABELS["terlambat_kerja"] not in values
        assert REASON_LABELS["terlambat_lain"] not in values
    finally:
        dlg.destroy()


def test_late_reasons_appear_when_late(tmp_path, monkeypatch, root):
    from src.core.reason_mapper import REASON_LABELS
    D, _dbp, eid = _setup(tmp_path, monkeypatch)
    dlg = _dlg(D, root, eid)
    try:
        dlg._masuk.insert(0, "08:20")   # telat 20 mnt (di bawah ambang severe)
        dlg._keluar.insert(0, "16:00")
        dlg._recompute_preview()
        values = dlg._reason_menu.cget("values")
        assert REASON_LABELS["terlambat_kerja"] in values
        assert REASON_LABELS["terlambat_lain"] in values
    finally:
        dlg.destroy()


def test_lupa_absen_and_libur_never_offered(tmp_path, monkeypatch, root):
    from src.core.reason_mapper import REASON_LABELS
    D, _dbp, eid = _setup(tmp_path, monkeypatch)
    dlg = _dlg(D, root, eid)
    try:
        dlg._masuk.insert(0, "09:30")
        dlg._recompute_preview()
        values = dlg._reason_menu.cget("values")
        for cat in ("lupa_absen_datang", "lupa_absen_pulang", "libur", "na"):
            assert REASON_LABELS[cat] not in values
    finally:
        dlg.destroy()


def test_detail_field_visible_only_for_categories_needing_detail(tmp_path, monkeypatch, root):
    from src.core.reason_mapper import REASON_LABELS
    D, _dbp, eid = _setup(tmp_path, monkeypatch)
    dlg = _dlg(D, root, eid)
    try:
        dlg._reason_var.set(REASON_LABELS["tugas_paparan"])
        dlg._on_reason_change()
        assert dlg._detail.winfo_manager() != ""      # tampil
        dlg._reason_var.set(REASON_LABELS["cuti"])
        dlg._on_reason_change()
        assert dlg._detail.winfo_manager() == ""      # sembunyi
    finally:
        dlg.destroy()


def test_save_writes_reason_and_detail(tmp_path, monkeypatch, root):
    from src.core.reason_mapper import REASON_LABELS
    from src.db.connection import get_connection
    from src.db.attendance import get_attendance
    D, dbp, eid = _setup(tmp_path, monkeypatch)
    dlg = _dlg(D, root, eid)
    dlg._masuk.insert(0, "08:00")
    dlg._keluar.insert(0, "16:00")
    dlg._recompute_preview()
    dlg._reason_var.set(REASON_LABELS["tugas_paparan"])
    dlg._on_reason_change()
    dlg._detail.insert(0, "Kantor Pusat")
    dlg._save()
    with get_connection(dbp) as c:
        row = get_attendance(c, employee_id=eid, tanggal="2026-07-06")
    assert row["reason_category"] == "tugas_paparan"
    assert row["reason_detail"] == "Kantor Pusat"
    assert row["resolved_at"] is not None
    assert row["has_issue"] == 0          # hari bersih tetap bukan issue


def test_clearing_reason_unresolves_row(tmp_path, monkeypatch, root):
    from src.db.connection import get_connection
    from src.db.attendance import get_attendance, set_reason
    D, dbp, eid = _setup(tmp_path, monkeypatch)
    # baris sudah punya alasan sebelumnya
    with get_connection(dbp) as c:
        from src.db.attendance import save_manual_attendance
        save_manual_attendance(
            c, employee_id=eid, tanggal="2026-07-07", hari="Selasa",
            tipe="Hari Kerja", jadwal=None, masuk="08:00", keluar="16:00",
            kerja_jam=8.0, lembur_jam=0.0, terlambat_menit=0, has_issue=0)
        rid = c.execute("SELECT id FROM attendance_records WHERE employee_id=? AND tanggal=?",
                        (eid, "2026-07-07")).fetchone()["id"]
        set_reason(c, attendance_id=rid, category="tugas_lapangan", detail="Site A")
    dlg = _dlg(D, root, eid, tanggal="2026-07-07")
    dlg._reason_var.set(D.NO_REASON)
    dlg._on_reason_change()
    dlg._save()
    with get_connection(dbp) as c:
        row = get_attendance(c, employee_id=eid, tanggal="2026-07-07")
    assert row["reason_category"] is None
    assert row["reason_detail"] is None
    assert row["resolved_at"] is None


def test_existing_reason_preloaded(tmp_path, monkeypatch, root):
    from src.core.reason_mapper import REASON_LABELS
    from src.db.connection import get_connection
    from src.db.attendance import save_manual_attendance, set_reason
    D, dbp, eid = _setup(tmp_path, monkeypatch)
    with get_connection(dbp) as c:
        save_manual_attendance(
            c, employee_id=eid, tanggal="2026-07-08", hari="Rabu",
            tipe="Hari Kerja", jadwal=None, masuk="08:00", keluar="16:00",
            kerja_jam=8.0, lembur_jam=0.0, terlambat_menit=0, has_issue=0)
        rid = c.execute("SELECT id FROM attendance_records WHERE employee_id=? AND tanggal=?",
                        (eid, "2026-07-08")).fetchone()["id"]
        set_reason(c, attendance_id=rid, category="tugas_lapangan", detail="Site B")
    dlg = _dlg(D, root, eid, tanggal="2026-07-08")
    try:
        assert dlg._reason_var.get() == REASON_LABELS["tugas_lapangan"]
        assert dlg._detail.get() == "Site B"
    finally:
        dlg.destroy()
```

- [ ] **Step 2: Jalankan test — pastikan gagal**

Run: `.venv/Scripts/python.exe -m pytest tests/test_attendance_edit_reason.py -q`
Expected: FAIL — `AttributeError: 'AttendanceEditDialog' object has no attribute '_reason_menu'`

- [ ] **Step 3a: Tambah import & konstanta**

Di `src/ui/components/attendance_edit_dialog.py`, ubah baris import DB:

```python
from src.db.attendance import (
    get_attendance, save_manual_attendance, delete_attendance,
    set_reason, unresolve_issue)
```

Tambahkan import mapper tepat di bawah `from src.core.attendance_calc import ...`:

```python
from src.core.reason_mapper import REASON_LABELS, REASON_NEEDS_DETAIL
```

Tambahkan konstanta di bawah `_TIPE_OPTIONS`:

```python
# Alasan yang selalu tersedia di editor (spec A1) — hari apa pun, termasuk
# hari bersih (punch lengkap & tepat waktu).
_BASE_REASONS = ("tugas_lapangan", "tugas_paparan", "tugas_belajar",
                 "izin_sakit", "cuti")
# Alasan pembenar keterlambatan — HANYA muncul saat baris memang telat (A2).
_LATE_REASONS = ("terlambat_kerja", "terlambat_lain")
NO_REASON = "— (tidak ada)"
```

- [ ] **Step 3b: Simpan state alasan awal di `__init__`**

Di `__init__`, tepat setelah blok `with get_connection(DB_PATH) as conn:` (setelah `self._existing = ...`), tambahkan:

```python
        ex0 = self._existing or {}
        self._reason_cat = ex0.get("reason_category")   # id kategori terpilih
```

- [ ] **Step 3c: Bangun seksi alasan**

Di `_build()`, tepat SETELAH blok "Auto box" (setelah baris
`self._lembur_lbl = self._metric(grid, 1, 1, "Lembur", "—")`) dan SEBELUM
komentar `# Override (collapsible)`, sisipkan:

```python
        # Alasan / keterangan — opsi kontekstual (lihat _refresh_reason_options)
        self._reason_box = ctk.CTkFrame(self, fg_color="transparent")
        self._reason_box.pack(fill="x", padx=SPACE_LG, pady=(SPACE_MD, 0))
        ctk.CTkLabel(self._reason_box, text="ALASAN / KETERANGAN", font=FONT_LABEL,
                     text_color=COLOR_TEXT_MUTED, anchor="w").pack(fill="x", pady=(0, 2))
        self._reason_var = ctk.StringVar(
            value=REASON_LABELS.get(self._reason_cat, NO_REASON))
        self._reason_menu = ctk.CTkOptionMenu(
            self._reason_box, values=[NO_REASON], variable=self._reason_var,
            command=lambda _v: self._on_reason_change(),
            fg_color=COLOR_SURFACE_HIGH, button_color=COLOR_ACCENT,
            button_hover_color=COLOR_ACCENT_HOVER, text_color=COLOR_TEXT,
            font=FONT_BODY)
        self._reason_menu.pack(fill="x")
        self._detail = self._entry(self._reason_box, ex.get("reason_detail") or "")
```

- [ ] **Step 3d: Tambahkan method perilaku**

Sisipkan method berikut di bagian `# ---------- behavior ----------`, tepat
SEBELUM `def _toggle_override(self):`:

```python
    def _selected_reason_id(self):
        """Label terpilih -> id kategori, atau None bila '— (tidak ada)'."""
        label = self._reason_var.get()
        for cat, lbl in REASON_LABELS.items():
            if lbl == label:
                return cat
        return None

    def _refresh_reason_options(self, terlambat):
        """Susun ulang daftar opsi alasan sesuai konteks baris.

        Alasan telat hanya ditawarkan saat baris memang telat (>0 menit).
        Kategori yang sedang terpilih selalu dipertahankan di daftar agar
        nilai lama tidak hilang diam-diam saat jam diedit."""
        cats = list(_BASE_REASONS)
        if terlambat > 0:
            cats += list(_LATE_REASONS)
        cur = self._selected_reason_id()
        if cur and cur not in cats:
            cats.append(cur)
        self._reason_menu.configure(
            values=[NO_REASON] + [REASON_LABELS[c] for c in cats])

    def _on_reason_change(self):
        """Tampilkan field detail hanya untuk kategori yang membutuhkannya."""
        cat = self._selected_reason_id()
        if cat in REASON_NEEDS_DETAIL:
            if self._detail.winfo_manager() == "":
                self._detail.pack(fill="x", pady=(SPACE_XS, 0))
        else:
            self._detail.pack_forget()
        try:
            self.update_idletasks()
            self.geometry(f"{DIALOG_W}x{self.winfo_reqheight()}")
        except Exception:
            pass
```

- [ ] **Step 3e: Sambungkan ke recompute**

Di `_recompute_preview`, tepat sebelum `return d`, tambahkan:

```python
        if hasattr(self, "_reason_menu"):
            self._refresh_reason_options(d["terlambat_menit"])
```

Dan di akhir `_build()`, ganti baris terakhir `self._recompute_preview()` menjadi:

```python
        self._recompute_preview()
        self._on_reason_change()
```

- [ ] **Step 3f: Simpan alasan di `_save`**

Di `_save()`, ganti blok `with get_connection(DB_PATH) as conn:` menjadi:

```python
        cat = self._selected_reason_id()
        detail = self._detail.get().strip() or None
        with get_connection(DB_PATH) as conn:
            save_manual_attendance(
                conn, employee_id=self._eid, tanggal=self._tanggal,
                hari=hari_name(self._tanggal), tipe=self._tipe_var.get(),
                jadwal=self._jadwal.get().strip() or None,
                masuk=masuk, keluar=keluar, kerja_jam=kerja, lembur_jam=lembur,
                terlambat_menit=terlambat, has_issue=calc["has_issue"])
            # Alasan disimpan terpisah: save_manual_attendance sengaja
            # mempertahankan reason_* (aturan kepemilikan v23).
            row = get_attendance(conn, employee_id=self._eid, tanggal=self._tanggal)
            if row is not None:
                if cat is None:
                    unresolve_issue(conn, attendance_id=row["id"])
                else:
                    set_reason(conn, attendance_id=row["id"],
                               category=cat, detail=detail)
```

- [ ] **Step 4: Jalankan test — pastikan lulus**

Run: `.venv/Scripts/python.exe -m pytest tests/test_attendance_edit_reason.py tests/test_attendance_edit_dialog.py -q`
Expected: PASS (9 passed) — test v23 yang lama tetap hijau.

- [ ] **Step 5: Commit**

```bash
git add src/ui/components/attendance_edit_dialog.py tests/test_attendance_edit_reason.py
git commit -m "feat(v24): editor absensi bisa set alasan (kontekstual)"
```

---

### Task 4: Konteks cetak (dipakai layar & printer)

**Files:**
- Create: `src/reports/dinas_recap_print.py`
- Test: `tests/test_dinas_recap_context.py`

- [ ] **Step 1: Tulis test yang gagal**

```python
# tests/test_dinas_recap_context.py
import pytest

from src.db.schema import init_db
from src.db.connection import get_connection
from src.db.employees import upsert_employee
from src.db.attendance import save_manual_attendance, set_reason
from src.reports.dinas_recap_print import build_dinas_recap_context


def _row(conn, eid, tanggal, category):
    save_manual_attendance(
        conn, employee_id=eid, tanggal=tanggal, hari="Senin", tipe="Hari Kerja",
        jadwal=None, masuk="08:00", keluar="16:00", kerja_jam=8.0,
        lembur_jam=0.0, terlambat_menit=0, has_issue=0)
    rid = conn.execute(
        "SELECT id FROM attendance_records WHERE employee_id=? AND tanggal=?",
        (eid, tanggal)).fetchone()["id"]
    set_reason(conn, attendance_id=rid, category=category, detail=None)


@pytest.fixture
def db(tmp_path):
    p = tmp_path / "hr.db"
    init_db(p)
    with get_connection(p) as conn:
        a = upsert_employee(conn, no_staff="S1", nama="Andi", dept="Ops")
        b = upsert_employee(conn, no_staff="S2", nama="Budi", dept="Sales")
        _row(conn, a, "2026-07-01", "tugas_lapangan")
        _row(conn, a, "2026-07-02", "tugas_lapangan")
        _row(conn, a, "2026-07-03", "tugas_paparan")
        _row(conn, b, "2026-07-06", "tugas_paparan")
        _row(conn, a, "2026-03-02", "tugas_lapangan")   # di luar 3 bln, dalam tahun
    yield p


def test_month_panel_and_totals(db):
    with get_connection(db) as conn:
        ctx = build_dinas_recap_context(conn, "2026-07", "year")
    assert ctx["month_label"] == "Juli 2026"
    assert [r["nama"] for r in ctx["month_rows"]] == ["Andi", "Budi"]
    assert ctx["month_totals"] == {"dinas": 2, "paparan": 2, "total": 4}


def test_rank_rows_have_rank_marks_and_bars(db):
    with get_connection(db) as conn:
        ctx = build_dinas_recap_context(conn, "2026-07", "year")
    r = ctx["rank_rows"]
    assert r[0]["nama"] == "Andi" and r[0]["rank"] == 1 and r[0]["mark"] == "👑"
    assert r[1]["nama"] == "Budi" and r[1]["rank"] == 2 and r[1]["mark"] == "💎"
    assert r[0]["bar_pct"] == 100                 # pemuncak
    assert r[1]["bar_pct"] == 25                  # 1 dari 4
    assert r[0]["dinas_pct"] + r[0]["paparan_pct"] == 100


def test_span_affects_rank_rows_but_not_month_panel(db):
    with get_connection(db) as conn:
        year = build_dinas_recap_context(conn, "2026-07", "year")
        q3 = build_dinas_recap_context(conn, "2026-07", "3m")
    assert year["rank_rows"][0]["total"] == 4     # termasuk Maret
    assert q3["rank_rows"][0]["total"] == 3       # Mei–Juli saja
    assert year["month_totals"] == q3["month_totals"]


def test_span_label_present(db):
    with get_connection(db) as conn:
        ctx = build_dinas_recap_context(conn, "2026-07", "6m")
    assert ctx["span_label"] == "Februari – Juli 2026"
    assert ctx["span"] == "6m"


def test_champion_none_when_empty(db):
    with get_connection(db) as conn:
        ctx = build_dinas_recap_context(conn, "2030-01", "year")
    assert ctx["rank_rows"] == []
    assert ctx["champion"] is None
    assert ctx["month_totals"] == {"dinas": 0, "paparan": 0, "total": 0}


def test_render_html_contains_both_sections(db):
    from src.reports.dinas_recap_print import render_dinas_recap_html
    with get_connection(db) as conn:
        html = render_dinas_recap_html(conn, "2026-07", "year")
    assert "Rekap Dinas" in html
    assert "Juli 2026" in html
    assert "Januari – Desember 2026" in html
    assert "Andi" in html
    assert "HR Officer in Charge" in html
```

- [ ] **Step 2: Jalankan test — pastikan gagal**

Run: `.venv/Scripts/python.exe -m pytest tests/test_dinas_recap_context.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.reports.dinas_recap_print'`

- [ ] **Step 3: Implementasi**

```python
# src/reports/dinas_recap_print.py
"""Konteks + render HTML cetak untuk layar Rekap Dinas.

Server-free, mengikuti pola heatmap_print: fungsi mengembalikan STRING HTML;
pemanggil menulis ke temp file lalu membukanya di browser (Ctrl-P / Save PDF).
Konteksnya juga dipakai layar in-app supaya angka di layar & cetak identik.
"""
from datetime import datetime

from src.core.dinas_recap import rank, resolve_range, span_label
from src.core.week_utils import MONTH_NAMES_ID, full_month_range
from src.db.attendance import count_dinas_paparan_by_employee
from src.db.settings import get_setting
from src.reports.html_renderer import _build_env

TEMPLATE_FILE = "dinas_recap_print.html.j2"


def _month_label(year_month: str) -> str:
    y, m = int(year_month[:4]), int(year_month[5:7])
    return f"{MONTH_NAMES_ID[m]} {y}"


def build_dinas_recap_context(conn, year_month: str, span: str) -> dict:
    """Konteks render untuk kedua panel.

    Panel kiri selalu bulan `year_month`; panel kanan mengikuti `span`.
    Baris peringkat dilengkapi rank, mark (👑/💎), dan persentase bar:
      bar_pct      — panjang bar relatif terhadap pemuncak
      dinas_pct    — porsi dinas DI DALAM bar (dinas+paparan = 100)
      paparan_pct  — sisanya
    """
    m_start, m_end = full_month_range(year_month)
    month_rows = count_dinas_paparan_by_employee(conn, m_start, m_end)
    month_totals = {
        "dinas": sum(r["dinas"] for r in month_rows),
        "paparan": sum(r["paparan"] for r in month_rows),
        "total": sum(r["total"] for r in month_rows),
    }

    r_start, r_end = resolve_range(year_month, span)
    rank_rows = rank(count_dinas_paparan_by_employee(conn, r_start, r_end))
    top = rank_rows[0]["total"] if rank_rows else 0
    for r in rank_rows:
        r["bar_pct"] = round(r["total"] / top * 100) if top else 0
        r["dinas_pct"] = round(r["dinas"] / r["total"] * 100) if r["total"] else 0
        r["paparan_pct"] = 100 - r["dinas_pct"] if r["total"] else 0
        r["mark"] = "👑" if r["rank"] == 1 else ("💎" if r["rank"] in (2, 3) else "")

    return {
        "month": year_month,
        "month_label": _month_label(year_month),
        "month_rows": month_rows,
        "month_totals": month_totals,
        "span": span,
        "span_label": span_label(year_month, span),
        "rank_rows": rank_rows,
        "champion": rank_rows[0] if rank_rows else None,
        "generated_at": datetime.now().strftime("%d %b %Y"),
    }


def render_dinas_recap_html(conn, year_month: str, span: str) -> str:
    """Render lembar cetak Rekap Dinas menjadi string HTML."""
    ctx = build_dinas_recap_context(conn, year_month, span)
    ctx["hr_officer_name"] = get_setting(conn, "hr_officer_name", default="")
    return _build_env().get_template(TEMPLATE_FILE).render(**ctx)
```

- [ ] **Step 4: Buat template cetak**

Create `src/reports/templates/dinas_recap_print.html.j2`:

```html
<!DOCTYPE html>
<html lang="id">
<head>
<meta charset="utf-8">
<title>Rekap Dinas &amp; Paparan — {{ month_label }}</title>
<style>
  @page { size: A4 portrait; margin: 14mm 13mm; }
  * { box-sizing: border-box; }
  body { margin:0; font-family:"Segoe UI",-apple-system,sans-serif; color:#171717;
         -webkit-print-color-adjust:exact; print-color-adjust:exact; }
  .kicker { font-family:Consolas,monospace; font-size:9pt; letter-spacing:2px;
            color:#EC4899; font-weight:700; margin-bottom:4px; }
  h1 { font-family:"Space Grotesk","Segoe UI",sans-serif; font-size:22pt;
       font-weight:700; letter-spacing:-.5px; line-height:1.05; margin:0; }
  .head { display:flex; justify-content:space-between; align-items:flex-start; }
  .meta { text-align:right; font-family:Consolas,monospace; font-size:8.5pt;
          color:#888; line-height:1.7; }
  .chip { display:inline-block; background:#F5F3FF; color:#7C3AED; border-radius:5px;
          padding:2px 9px; font-weight:700; margin-bottom:4px; }
  .rule { display:flex; height:4px; border-radius:2px; overflow:hidden; margin:14px 0 16px; }
  .rule i { display:block; height:100%; }
  .cards { display:flex; gap:10px; margin-bottom:18px; }
  .card { flex:1; border:1px solid #eee; border-radius:9px; padding:10px 12px; }
  .card.champ { border-color:#EC489933; background:#FDF2F8; }
  .card .cap { font-family:Consolas,monospace; font-size:8pt; letter-spacing:1px; font-weight:700; }
  .card .val { font-family:"Space Grotesk","Segoe UI",sans-serif; font-size:20pt; font-weight:700; }
  h2 { font-family:"Space Grotesk","Segoe UI",sans-serif; font-size:12pt; margin:0;
       font-weight:700; letter-spacing:.3px; }
  .sec { display:flex; align-items:center; justify-content:space-between; margin:0 0 8px; }
  .sec .left { display:flex; align-items:center; gap:7px; }
  .sec .bar { width:5px; height:15px; background:#EC4899; border-radius:2px; display:inline-block; }
  .sec .note { font-family:Consolas,monospace; font-size:8.5pt; color:#999; }
  table { width:100%; border-collapse:collapse; font-size:10pt; }
  thead th { text-align:left; color:#555; font-size:8pt; text-transform:uppercase;
             letter-spacing:.5px; background:#fafafa; padding:6px 8px; font-weight:600; }
  tbody td { padding:6px 8px; border-bottom:1px solid #f0f0f0; }
  tfoot td { padding:8px; font-weight:700; border-top:2px solid #333; }
  .num { text-align:right; font-family:Consolas,monospace; font-variant-numeric:tabular-nums; }
  .teal { color:#0D9488; } .violet { color:#7C3AED; } .zero { color:#bbb; }
  .rank { margin-top:2px; }
  .rrow { display:flex; align-items:center; gap:11px; margin-bottom:9px;
          page-break-inside:avoid; }
  .rno { width:20px; text-align:center; font-family:"Space Grotesk","Segoe UI",sans-serif;
         font-weight:700; font-size:12pt; }
  .rbody { flex:1; }
  .rline { display:flex; justify-content:space-between; font-size:10pt; margin-bottom:3px; }
  .rbar { height:7px; background:#f1f1f1; border-radius:4px; overflow:hidden; display:flex; }
  .rbar i { display:block; height:100%; }
  .legend { font-family:Consolas,monospace; font-size:8.5pt; color:#aaa;
            margin-top:8px; text-align:right; }
  .sign { margin-top:34px; display:flex; justify-content:space-between;
          font-size:10pt; page-break-inside:avoid; }
  .sign .who { text-align:center; }
  .sign .line { border-top:1.5px solid #171717; padding-top:4px; min-width:190px;
                font-weight:600; margin-top:48px; }
  .tip { margin-top:18px; border-top:1px dashed #ddd; padding-top:7px;
         font-family:Consolas,monospace; font-size:7.5pt; color:#bbb; }
  .empty { color:#999; font-style:italic; padding:14px 0; }
</style>
</head>
<body>

  <div class="head">
    <div>
      <div class="kicker">LAPORAN KEHADIRAN</div>
      <h1>Rekap Dinas<br>&amp; Paparan</h1>
    </div>
    <div class="meta">
      <div class="chip">{{ month_label|upper }}</div>
      <div>Dicetak {{ generated_at }}</div>
      <div>Josaphat Tech Solution</div>
    </div>
  </div>
  <div class="rule">
    <i style="width:62%;background:#EC4899"></i>
    <i style="width:22%;background:#0D9488"></i>
    <i style="width:16%;background:#7C3AED"></i>
  </div>

  <div class="cards">
    <div class="card">
      <div class="cap teal">TOTAL DINAS</div>
      <div class="val teal">{{ month_totals.dinas }}</div>
    </div>
    <div class="card">
      <div class="cap violet">TOTAL PAPARAN</div>
      <div class="val violet">{{ month_totals.paparan }}</div>
    </div>
    <div class="card champ">
      <div class="cap" style="color:#EC4899">
        {% if champion %}JUARA · {{ champion.nama|upper }}{% else %}JUARA{% endif %}
      </div>
      <div class="val">
        {% if champion %}{{ champion.total }}{% else %}—{% endif %}
      </div>
    </div>
  </div>

  <div class="sec">
    <div class="left"><span class="bar"></span><h2>Bulan Terpilih — {{ month_label }}</h2></div>
  </div>
  {% if month_rows %}
  <table>
    <thead>
      <tr>
        <th>Nama</th><th>Dept</th>
        <th class="num teal">Dinas</th><th class="num violet">Paparan</th><th class="num">Total</th>
      </tr>
    </thead>
    <tbody>
      {% for r in month_rows %}
      <tr>
        <td>{{ r.nama }}</td><td style="color:#888">{{ r.dept }}</td>
        <td class="num {% if r.dinas %}teal{% else %}zero{% endif %}">{{ r.dinas }}</td>
        <td class="num {% if r.paparan %}violet{% else %}zero{% endif %}">{{ r.paparan }}</td>
        <td class="num"><b>{{ r.total }}</b></td>
      </tr>
      {% endfor %}
    </tbody>
    <tfoot>
      <tr>
        <td colspan="2">TOTAL</td>
        <td class="num teal">{{ month_totals.dinas }}</td>
        <td class="num violet">{{ month_totals.paparan }}</td>
        <td class="num">{{ month_totals.total }}</td>
      </tr>
    </tfoot>
  </table>
  {% else %}
  <div class="empty">Belum ada dinas atau paparan pada bulan ini.</div>
  {% endif %}

  <div class="sec" style="margin-top:22px">
    <div class="left"><span class="bar"></span><h2>Papan Peringkat</h2></div>
    <span class="note">{{ span_label }} · Dinas + Paparan</span>
  </div>
  {% if rank_rows %}
  <div class="rank">
    {% for r in rank_rows %}
    <div class="rrow">
      <span class="rno" style="color:{% if r.rank == 1 %}#EC4899{% elif r.rank == 2 %}#F472B6{% elif r.rank == 3 %}#F9A8D4{% else %}#aaa{% endif %}">{{ r.rank }}</span>
      <div class="rbody">
        <div class="rline">
          <span>{{ r.nama }} {{ r.mark }}</span>
          <span class="num"><span class="teal">{{ r.dinas }}</span> · <span class="violet">{{ r.paparan }}</span> · <b>{{ r.total }}</b></span>
        </div>
        <div class="rbar" style="width:{{ r.bar_pct }}%">
          <i style="width:{{ r.dinas_pct }}%;background:#0D9488"></i>
          <i style="width:{{ r.paparan_pct }}%;background:#7C3AED"></i>
        </div>
      </div>
    </div>
    {% endfor %}
  </div>
  <div class="legend"><span class="teal">■</span> dinas &nbsp; <span class="violet">■</span> paparan</div>
  {% else %}
  <div class="empty">Belum ada data pada rentang ini.</div>
  {% endif %}

  <div class="sign">
    <div style="align-self:flex-end;font-family:Consolas,monospace;font-size:8pt;color:#ccc">
      HR Absensi
    </div>
    <div class="who">
      <div style="color:#666">Mengetahui,</div>
      <div class="line">{{ hr_officer_name or "HR Officer in Charge" }}</div>
    </div>
  </div>

  <div class="tip">
    Tip cetak: aktifkan "Background graphics" dan matikan "Headers and footers"
    di dialog cetak browser.
  </div>

</body>
</html>
```

- [ ] **Step 5: Daftarkan template ke PyInstaller**

Di `HR-Absensi.spec`, tambahkan setelah baris `employee_report.html.j2`:

```python
        ('src/reports/templates/dinas_recap_print.html.j2', 'src/reports/templates'),
```

- [ ] **Step 6: Jalankan test — pastikan lulus**

Run: `.venv/Scripts/python.exe -m pytest tests/test_dinas_recap_context.py -q`
Expected: PASS (6 passed)

- [ ] **Step 7: Commit**

```bash
git add src/reports/dinas_recap_print.py src/reports/templates/dinas_recap_print.html.j2 HR-Absensi.spec tests/test_dinas_recap_context.py
git commit -m "feat(v24): konteks + template cetak Rekap Dinas"
```

---

### Task 5: Layar Rekap Dinas

**Files:**
- Create: `src/ui/screens/dinas_recap.py`
- Test: `tests/test_dinas_recap_screen.py`

- [ ] **Step 1: Tulis test yang gagal**

```python
# tests/test_dinas_recap_screen.py
"""Layar Rekap Dinas: dua panel, segmented rentang, cetak."""
import pytest

from src.db.schema import init_db
from src.db.connection import get_connection
from src.db.employees import upsert_employee
from src.db.attendance import save_manual_attendance, set_reason
from src.db.settings import set_setting


def _row(conn, eid, tanggal, category):
    save_manual_attendance(
        conn, employee_id=eid, tanggal=tanggal, hari="Senin", tipe="Hari Kerja",
        jadwal=None, masuk="08:00", keluar="16:00", kerja_jam=8.0,
        lembur_jam=0.0, terlambat_menit=0, has_issue=0)
    rid = conn.execute(
        "SELECT id FROM attendance_records WHERE employee_id=? AND tanggal=?",
        (eid, tanggal)).fetchone()["id"]
    set_reason(conn, attendance_id=rid, category=category, detail=None)


@pytest.fixture
def dbp(tmp_path):
    p = tmp_path / "hr.db"
    init_db(p)
    with get_connection(p) as conn:
        set_setting(conn, "current_month", "2026-07")
        a = upsert_employee(conn, no_staff="S1", nama="Andi", dept="Ops")
        b = upsert_employee(conn, no_staff="S2", nama="Budi", dept="Sales")
        _row(conn, a, "2026-07-01", "tugas_lapangan")
        _row(conn, a, "2026-07-02", "tugas_paparan")
        _row(conn, b, "2026-07-06", "tugas_paparan")
        _row(conn, a, "2026-03-02", "tugas_lapangan")   # luar 3 bln, dalam tahun
    return p


@pytest.fixture
def screen_mod(monkeypatch, dbp):
    from src.ui.screens import dinas_recap as M
    monkeypatch.setattr(M, "DB_PATH", dbp)
    return M


def test_screen_builds_and_loads_both_panels(tk_root, screen_mod):
    s = screen_mod.DinasRecapScreen(tk_root)
    try:
        assert s._month == "2026-07"
        assert s._span == "year"
        assert [r["nama"] for r in s._month_rows] == ["Andi", "Budi"]
        assert s._rank_rows[0]["nama"] == "Andi"
        assert s._rank_rows[0]["rank"] == 1
    finally:
        s.destroy()


def test_changing_span_reloads_leaderboard_only(tk_root, screen_mod):
    s = screen_mod.DinasRecapScreen(tk_root)
    try:
        assert s._rank_rows[0]["total"] == 3      # year: Mar + Jul
        s._on_span("3 bln")
        assert s._span == "3m"
        assert s._rank_rows[0]["total"] == 2      # Mei–Jul saja
        assert [r["nama"] for r in s._month_rows] == ["Andi", "Budi"]
    finally:
        s.destroy()


def test_on_show_follows_active_month(tk_root, screen_mod, dbp):
    s = screen_mod.DinasRecapScreen(tk_root)
    try:
        with get_connection(dbp) as conn:
            set_setting(conn, "current_month", "2026-03")
        s.on_show()
        assert s._month == "2026-03"
        assert [r["nama"] for r in s._month_rows] == ["Andi"]
    finally:
        s.destroy()


def test_empty_state_does_not_crash(tk_root, monkeypatch, tmp_path):
    from src.ui.screens import dinas_recap as M
    p = tmp_path / "empty.db"
    init_db(p)
    with get_connection(p) as conn:
        set_setting(conn, "current_month", "2026-07")
    monkeypatch.setattr(M, "DB_PATH", p)
    s = M.DinasRecapScreen(tk_root)
    try:
        assert s._month_rows == []
        assert s._rank_rows == []
    finally:
        s.destroy()


def test_print_writes_html_and_opens_browser(tk_root, screen_mod, monkeypatch):
    opened = []
    monkeypatch.setattr(screen_mod, "open_html_in_browser",
                        lambda p: opened.append(p) or (True, "Test"))
    s = screen_mod.DinasRecapScreen(tk_root)
    try:
        s._do_print()
        assert len(opened) == 1
        html = opened[0].read_text(encoding="utf-8")
        assert "Rekap Dinas" in html
        assert "Andi" in html
    finally:
        s.destroy()
```

- [ ] **Step 2: Jalankan test — pastikan gagal**

Run: `.venv/Scripts/python.exe -m pytest tests/test_dinas_recap_screen.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.ui.screens.dinas_recap'`

- [ ] **Step 3: Implementasi**

```python
# src/ui/screens/dinas_recap.py
"""Layar Rekap Dinas & Paparan — dua panel.

Kiri: tabel bulan aktif (Dinas / Paparan / Total + grand total).
Kanan: papan peringkat dengan rentang bisa diatur (3 bln / 6 bln / Tahun ini,
default Tahun ini) — garis aksen magenta memudar per peringkat, penanda 👑/💎,
bar bertumpuk teal (dinas) + ungu (paparan), kolom angka sejajar.
Cetak merender dinas_recap_print.html.j2 ke temp file lalu membukanya di
browser (Ctrl-P / Save PDF), mengikuti rentang yang aktif di layar.
Lihat docs/superpowers/specs/2026-07-30-reason-editing-dinas-paparan-recap-design.md.
"""
import os
import tempfile
from datetime import date
from pathlib import Path

import customtkinter as ctk

from src.config import DB_PATH
from src.core.dinas_recap import SPANS, DEFAULT_SPAN
from src.db.connection import get_connection
from src.db.settings import get_setting
from src.reports.dinas_recap_print import (
    build_dinas_recap_context, render_dinas_recap_html)
from src.ui.browser_launcher import open_html_in_browser
from src.ui.theme import (
    COLOR_SURFACE, COLOR_SURFACE_HIGH, COLOR_BORDER,
    COLOR_ACCENT, COLOR_ACCENT_HOVER, COLOR_SECONDARY,
    COLOR_TEXT, COLOR_TEXT_DIM, COLOR_TEXT_MUTED, COLOR_TEXT_DISABLED,
    FONT_DISPLAY, FONT_BODY, FONT_BODY_BOLD, FONT_SMALL, FONT_LABEL,
    FONT_MONO_DATA, FONT_MONO_SMALL,
    SPACE_XS, SPACE_SM, SPACE_MD, SPACE_LG, SPACE_XL, RADIUS_MD,
)

_TEAL = "#0D9488"          # Dinas — sama dengan STATUS_COLORS['dinas'] di core.heatmap
_BAR_TRACK = "#1F1F1F"
_BAR_H = 6
# Warna angka peringkat: magenta memudar sesuai tier, abu untuk sisanya.
_RANK_COLORS = {1: COLOR_ACCENT, 2: COLOR_ACCENT_HOVER, 3: "#F9A8D4"}
_RANK_ACCENTS = {1: COLOR_ACCENT, 2: "#8E2C58", 3: "#5A1E3A"}
_ACCENT_REST = "#2F2F2F"
_LABEL_TO_SPAN = {label: sid for sid, label in SPANS}


class DinasRecapScreen(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self._month = self._read_active_month()
        self._span = DEFAULT_SPAN
        self._month_rows = []
        self._rank_rows = []
        self._month_totals = {"dinas": 0, "paparan": 0, "total": 0}
        self._span_label = ""

        self._build_header()
        self._build_body()
        self._load()

    # ---------- data ----------
    def _read_active_month(self) -> str:
        with get_connection(DB_PATH) as conn:
            m = get_setting(conn, "current_month", default="")
        return m or date.today().strftime("%Y-%m")

    def _load(self):
        """Baca ulang kedua panel dari DB dan render. Idempoten."""
        with get_connection(DB_PATH) as conn:
            ctx = build_dinas_recap_context(conn, self._month, self._span)
        self._month_rows = ctx["month_rows"]
        self._month_totals = ctx["month_totals"]
        self._rank_rows = ctx["rank_rows"]
        self._span_label = ctx["span_label"]
        self._month_title.configure(text=f"◆ BULAN TERPILIH · {ctx['month_label'].upper()}")
        self._month_count.configure(text=f"{len(self._month_rows)} pegawai")
        self._span_lbl.configure(text=self._span_label)
        self._render_month()
        self._render_rank()

    def on_show(self) -> None:
        """Kontrak shell: dipanggil tiap layar cache ditampilkan lagi.
        Mengikuti current_month bila berubah saat layar tersembunyi; pilihan
        rentang pengguna dipertahankan."""
        m = self._read_active_month()
        if m != self._month:
            self._month = m
        self._load()

    # ---------- build ----------
    def _build_header(self):
        head = ctk.CTkFrame(self, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew", padx=SPACE_XL, pady=(SPACE_LG, SPACE_SM))
        ctk.CTkLabel(head, text="Rekap Dinas & Paparan", font=FONT_DISPLAY,
                     text_color=COLOR_TEXT).pack(side="left")
        ctk.CTkButton(
            head, text="🖨️  Cetak", command=self._do_print, width=104,
            fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER,
            text_color="#0A0A0A", font=FONT_BODY_BOLD, corner_radius=RADIUS_MD,
        ).pack(side="right")

    def _panel(self, parent, col):
        box = ctk.CTkFrame(parent, fg_color=COLOR_SURFACE, border_width=1,
                           border_color=COLOR_BORDER, corner_radius=RADIUS_MD)
        box.grid(row=0, column=col, sticky="nsew",
                 padx=(0, SPACE_SM) if col == 0 else (SPACE_SM, 0))
        box.grid_columnconfigure(0, weight=1)
        box.grid_rowconfigure(1, weight=1)
        return box

    def _build_body(self):
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.grid(row=1, column=0, sticky="nsew", padx=SPACE_XL, pady=(0, SPACE_LG))
        body.grid_columnconfigure(0, weight=11, uniform="p")
        body.grid_columnconfigure(1, weight=9, uniform="p")
        body.grid_rowconfigure(0, weight=1)

        # ---- panel kiri: bulan terpilih ----
        left = self._panel(body, 0)
        lhead = ctk.CTkFrame(left, fg_color="transparent")
        lhead.grid(row=0, column=0, sticky="ew", padx=SPACE_MD, pady=(SPACE_SM, SPACE_XS))
        self._month_title = ctk.CTkLabel(lhead, text="", font=FONT_MONO_SMALL,
                                         text_color=COLOR_TEXT_DIM)
        self._month_title.pack(side="left")
        self._month_count = ctk.CTkLabel(lhead, text="", font=FONT_MONO_SMALL,
                                         text_color=COLOR_TEXT_DISABLED)
        self._month_count.pack(side="right")
        self._month_list = ctk.CTkScrollableFrame(left, fg_color="transparent")
        self._month_list.grid(row=1, column=0, sticky="nsew", padx=SPACE_SM, pady=(0, SPACE_SM))
        self._month_list.grid_columnconfigure(0, weight=1)

        # ---- panel kanan: papan peringkat ----
        right = self._panel(body, 1)
        rhead = ctk.CTkFrame(right, fg_color="transparent")
        rhead.grid(row=0, column=0, sticky="ew", padx=SPACE_MD, pady=(SPACE_SM, SPACE_XS))
        ctk.CTkLabel(rhead, text="🏆 PAPAN PERINGKAT", font=FONT_MONO_SMALL,
                     text_color=COLOR_TEXT_DIM).pack(side="left")
        self._span_ctl = ctk.CTkSegmentedButton(
            rhead, values=[label for _sid, label in SPANS],
            command=self._on_span,
            fg_color=COLOR_SURFACE_HIGH, selected_color=COLOR_ACCENT,
            selected_hover_color=COLOR_ACCENT_HOVER, unselected_color=COLOR_SURFACE_HIGH,
            unselected_hover_color=COLOR_BORDER, text_color=COLOR_TEXT,
            font=FONT_SMALL, corner_radius=RADIUS_MD)
        self._span_ctl.set(dict(SPANS)[DEFAULT_SPAN])
        self._span_ctl.pack(side="right")
        self._span_lbl = ctk.CTkLabel(right, text="", font=FONT_MONO_SMALL,
                                      text_color=COLOR_TEXT_DISABLED, anchor="w")
        self._span_lbl.grid(row=2, column=0, sticky="ew", padx=SPACE_MD, pady=(0, SPACE_SM))
        self._rank_list = ctk.CTkScrollableFrame(right, fg_color="transparent")
        self._rank_list.grid(row=1, column=0, sticky="nsew", padx=SPACE_SM, pady=(0, SPACE_XS))
        self._rank_list.grid_columnconfigure(0, weight=1)

    # ---------- render ----------
    @staticmethod
    def _clear(frame):
        for w in frame.winfo_children():
            w.destroy()

    def _num(self, parent, text, color, width):
        return ctk.CTkLabel(parent, text=str(text), font=FONT_MONO_DATA,
                            text_color=color, width=width, anchor="e")

    def _render_month(self):
        self._clear(self._month_list)
        if not self._month_rows:
            ctk.CTkLabel(self._month_list, text="Belum ada dinas atau paparan bulan ini.",
                         font=FONT_SMALL, text_color=COLOR_TEXT_MUTED).pack(pady=SPACE_LG)
            return
        hdr = ctk.CTkFrame(self._month_list, fg_color="transparent")
        hdr.pack(fill="x", pady=(0, SPACE_XS))
        ctk.CTkLabel(hdr, text="NAMA", font=FONT_LABEL, text_color=COLOR_TEXT_DISABLED,
                     anchor="w").pack(side="left", fill="x", expand=True)
        for cap, col in (("DIN", _TEAL), ("PAP", COLOR_SECONDARY), ("TOT", COLOR_TEXT_DIM)):
            ctk.CTkLabel(hdr, text=cap, font=FONT_LABEL, text_color=col,
                         width=38, anchor="e").pack(side="left")
        for r in self._month_rows:
            row = ctk.CTkFrame(self._month_list, fg_color="transparent")
            row.pack(fill="x", pady=1)
            name = ctk.CTkFrame(row, fg_color="transparent")
            name.pack(side="left", fill="x", expand=True)
            ctk.CTkLabel(name, text=r["nama"], font=FONT_BODY,
                         text_color=COLOR_TEXT, anchor="w").pack(anchor="w")
            if r["dept"]:
                ctk.CTkLabel(name, text=r["dept"], font=FONT_MONO_SMALL,
                             text_color=COLOR_TEXT_DISABLED, anchor="w").pack(anchor="w")
            self._num(row, r["dinas"], _TEAL if r["dinas"] else COLOR_TEXT_DISABLED, 38).pack(side="left")
            self._num(row, r["paparan"], COLOR_SECONDARY if r["paparan"] else COLOR_TEXT_DISABLED, 38).pack(side="left")
            self._num(row, r["total"], COLOR_TEXT, 38).pack(side="left")
        sep = ctk.CTkFrame(self._month_list, fg_color=COLOR_BORDER, height=1)
        sep.pack(fill="x", pady=(SPACE_XS, SPACE_XS))
        tot = ctk.CTkFrame(self._month_list, fg_color="transparent")
        tot.pack(fill="x")
        ctk.CTkLabel(tot, text="TOTAL", font=FONT_BODY_BOLD, text_color=COLOR_TEXT,
                     anchor="w").pack(side="left", fill="x", expand=True)
        self._num(tot, self._month_totals["dinas"], _TEAL, 38).pack(side="left")
        self._num(tot, self._month_totals["paparan"], COLOR_SECONDARY, 38).pack(side="left")
        self._num(tot, self._month_totals["total"], COLOR_TEXT, 38).pack(side="left")

    def _render_rank(self):
        self._clear(self._rank_list)
        if not self._rank_rows:
            ctk.CTkLabel(self._rank_list, text="Belum ada data pada rentang ini.",
                         font=FONT_SMALL, text_color=COLOR_TEXT_MUTED).pack(pady=SPACE_LG)
            return
        for r in self._rank_rows:
            accent = _RANK_ACCENTS.get(r["rank"], _ACCENT_REST)
            wrap = ctk.CTkFrame(self._rank_list, fg_color="transparent")
            wrap.pack(fill="x", pady=3)
            # garis aksen tier di kiri (pilihan desain user — lihat spec §4.4)
            ctk.CTkFrame(wrap, fg_color=accent, width=3, corner_radius=2).pack(
                side="left", fill="y", padx=(0, SPACE_SM))
            ctk.CTkLabel(wrap, text=str(r["rank"]), font=FONT_BODY_BOLD, width=18,
                         text_color=_RANK_COLORS.get(r["rank"], COLOR_TEXT_MUTED)).pack(side="left")
            body = ctk.CTkFrame(wrap, fg_color="transparent")
            body.pack(side="left", fill="x", expand=True, padx=(SPACE_XS, 0))
            line = ctk.CTkFrame(body, fg_color="transparent")
            line.pack(fill="x")
            label = f"{r['nama']} {r['mark']}".strip()
            ctk.CTkLabel(line, text=label, font=FONT_BODY, text_color=COLOR_TEXT,
                         anchor="w").pack(side="left", fill="x", expand=True)
            self._num(line, r["total"], COLOR_TEXT, 34).pack(side="right")
            self._num(line, r["paparan"], COLOR_SECONDARY, 30).pack(side="right")
            self._num(line, r["dinas"], _TEAL, 30).pack(side="right")
            self._bar(body, r)

    def _bar(self, parent, r):
        """Bar bertumpuk: panjang ∝ total relatif pemuncak, isi = komposisi."""
        track = ctk.CTkFrame(parent, fg_color=_BAR_TRACK, height=_BAR_H,
                             corner_radius=3)
        track.pack(fill="x", pady=(3, 0))
        track.pack_propagate(False)
        fill = ctk.CTkFrame(track, fg_color="transparent")
        fill.place(relx=0, rely=0, relwidth=max(r["bar_pct"], 1) / 100, relheight=1)
        if r["dinas_pct"]:
            ctk.CTkFrame(fill, fg_color=_TEAL, corner_radius=3).place(
                relx=0, rely=0, relwidth=r["dinas_pct"] / 100, relheight=1)
        if r["paparan_pct"]:
            ctk.CTkFrame(fill, fg_color=COLOR_SECONDARY, corner_radius=3).place(
                relx=r["dinas_pct"] / 100, rely=0,
                relwidth=r["paparan_pct"] / 100, relheight=1)

    # ---------- events ----------
    def _on_span(self, label):
        self._span = _LABEL_TO_SPAN.get(label, DEFAULT_SPAN)
        self._load()

    def _do_print(self):
        with get_connection(DB_PATH) as conn:
            html = render_dinas_recap_html(conn, self._month, self._span)
        fd, path = tempfile.mkstemp(suffix=".html", prefix="rekap_dinas_")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(html)
        open_html_in_browser(Path(path))
```

- [ ] **Step 4: Jalankan test — pastikan lulus**

Run: `.venv/Scripts/python.exe -m pytest tests/test_dinas_recap_screen.py -q`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add src/ui/screens/dinas_recap.py tests/test_dinas_recap_screen.py
git commit -m "feat(v24): layar Rekap Dinas (dua panel + rentang + cetak)"
```

---

### Task 6: Wiring navigasi sidebar

**Files:**
- Modify: `src/ui/app.py`
- Test: `tests/test_app_dinas_recap_nav.py`

- [ ] **Step 1: Tulis test yang gagal**

```python
# tests/test_app_dinas_recap_nav.py
"""Item nav 'Rekap Dinas' terdaftar dan membuat layar yang benar."""


def test_nav_item_registered_in_insight_group():
    import inspect
    import src.ui.app as app_mod
    src = inspect.getsource(app_mod.HRApp._build_sidebar)
    assert '"Rekap Dinas", "DinasRecap"' in src
    # harus berada di grup INSIGHT (muncul sebelum label DATA MANAGEMENT)
    assert src.index("Rekap Dinas") < src.index("DATA MANAGEMENT")


def test_create_screen_returns_dinas_recap(tk_root, monkeypatch, tmp_path):
    from src.db.schema import init_db
    from src.db.connection import get_connection
    from src.db.settings import set_setting
    import src.ui.screens.dinas_recap as screen_mod
    from src.ui.screens.dinas_recap import DinasRecapScreen

    p = tmp_path / "hr.db"
    init_db(p)
    with get_connection(p) as conn:
        set_setting(conn, "current_month", "2026-07")
    monkeypatch.setattr(screen_mod, "DB_PATH", p)

    import src.ui.app as app_mod
    dummy = type("D", (), {"content": tk_root})()
    screen = app_mod.HRApp._create_screen(dummy, "DinasRecap")
    try:
        assert isinstance(screen, DinasRecapScreen)
    finally:
        screen.destroy()
```

- [ ] **Step 2: Jalankan test — pastikan gagal**

Run: `.venv/Scripts/python.exe -m pytest tests/test_app_dinas_recap_nav.py -q`
Expected: FAIL — `AssertionError` (nav belum ada) dan `_create_screen`
mengembalikan frame placeholder, bukan `DinasRecapScreen`.

- [ ] **Step 3: Implementasi**

Di `src/ui/app.py`, dalam `nav_groups`, grup `"INSIGHT"`, tambahkan setelah item Heatmap:

```python
                ("▤", "Rekap Dinas", "DinasRecap"),
```

Sehingga grup INSIGHT menjadi:

```python
            ("INSIGHT", [
                ("📊", "Dashboard", "Dashboard"),
                ("⊞", "Heatmap", "Heatmap"),
                ("▤", "Rekap Dinas", "DinasRecap"),
            ]),
```

Di `_create_screen`, tambahkan cabang setelah cabang `"Heatmap"`:

```python
        elif name == "DinasRecap":
            from src.ui.screens.dinas_recap import DinasRecapScreen
            return DinasRecapScreen(self.content)
```

- [ ] **Step 4: Jalankan test — pastikan lulus**

Run: `.venv/Scripts/python.exe -m pytest tests/test_app_dinas_recap_nav.py -q`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add src/ui/app.py tests/test_app_dinas_recap_nav.py
git commit -m "feat(v24): nav sidebar Rekap Dinas"
```

---

### Task 7: Versi + changelog

**Files:**
- Modify: `src/config.py`
- Create: `tests/test_changelog_v24_0_0.py`
- Modify: `tests/test_changelog_v23_0_0.py`

- [ ] **Step 1: Tulis test yang gagal**

```python
# tests/test_changelog_v24_0_0.py
from src import config


def test_version_is_v24_0_0():
    assert config.APP_VERSION == "24.0.0"
    assert config.APP_BUILD_DATE == "2026-07-30"


def test_changelog_top_is_v24_0_0():
    top = config.APP_CHANGELOG[0]
    assert top["version"] == "24.0.0"
    assert top["date"] == "2026-07-30"
    kinds = {k for k, _ in top["changes"]}
    assert "feat" in kinds
    blob = " ".join(d for _, d in top["changes"]).lower()
    assert "alasan" in blob
    assert "rekap" in blob
    assert "dinas" in blob
    assert "paparan" in blob
```

Ubah `tests/test_changelog_v23_0_0.py` menjadi gaya retensi:

```python
from src import config


def test_changelog_retains_v23_0_0_entry():
    """v23.0.0 bukan lagi versi terkini, tapi entri changelog-nya harus tetap
    ada (dialog About menampilkan riwayat penuh)."""
    entry = next((e for e in config.APP_CHANGELOG if e["version"] == "23.0.0"), None)
    assert entry is not None
    assert entry["date"] == "2026-07-16"
    kinds = {k for k, _ in entry["changes"]}
    assert "feat" in kinds
    blob = " ".join(d for _, d in entry["changes"]).lower()
    assert "edit data" in blob
    assert "backup" in blob
    assert "konflik" in blob or "konfirmasi" in blob
```

- [ ] **Step 2: Jalankan test — pastikan gagal**

Run: `.venv/Scripts/python.exe -m pytest tests/test_changelog_v24_0_0.py -q`
Expected: FAIL — `assert '23.0.0' == '24.0.0'`

- [ ] **Step 3: Implementasi**

Di `src/config.py`, ubah:

```python
APP_VERSION = "24.0.0"
APP_BUILD_DATE = "2026-07-30"  # YYYY-MM-DD; bumped manually with APP_VERSION on release
```

dan sisipkan entri baru di paling atas `APP_CHANGELOG`:

```python
    {
        "version": "24.0.0",
        "date": "2026-07-30",
        "changes": [
            ("feat", "Alasan bisa diisi langsung dari jendela Edit Data di "
                     "Heatmap — termasuk untuk hari yang absensinya sudah "
                     "lengkap dan tepat waktu. Contoh: karyawan hadir pagi "
                     "lalu berangkat tugas paparan/lapangan kini bisa ditandai "
                     "tanpa lewat menu Issues."),
            ("feat", "Pilihan alasan menyesuaikan kondisi baris: Tugas "
                     "Lapangan, Tugas Paparan, Tugas Belajar, Izin Sakit, dan "
                     "Cuti selalu tersedia; alasan keterlambatan hanya muncul "
                     "bila hari itu memang tercatat telat — sehingga telat "
                     "ringan pun kini bisa diberi alasan."),
            ("feat", "Menu baru \"Rekap Dinas\": jumlah Dinas, Paparan, dan "
                     "totalnya per karyawan untuk bulan aktif, ditemani papan "
                     "peringkat sepanjang periode (Tahun ini, atau 3/6 bulan "
                     "terakhir) lengkap dengan grafik komposisi dinas vs "
                     "paparan. Bisa dicetak jadi PDF."),
        ],
    },
```

- [ ] **Step 4: Jalankan test — pastikan lulus**

Run: `.venv/Scripts/python.exe -m pytest tests/test_changelog_v24_0_0.py tests/test_changelog_v23_0_0.py -q`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add src/config.py tests/test_changelog_v24_0_0.py tests/test_changelog_v23_0_0.py
git commit -m "chore(release): APP_VERSION 24.0.0 + changelog"
```

---

### Task 8: Suite penuh + bundle rilis

**Files:** tidak ada perubahan kode — verifikasi & artefak.

- [ ] **Step 1: Jalankan seluruh suite**

Run: `.venv/Scripts/python.exe -m pytest -q`
Expected: PASS — seluruh test hijau (±600 tests, ±2 menit). Perbaiki regresi
sebelum lanjut; JANGAN build dengan suite merah.

- [ ] **Step 2: Pastikan .exe produksi tidak sedang berjalan**

Run: `tasklist | grep -i HR-Absensi || echo "not running"`
Expected: `not running`. Bila berjalan, TANYA user dulu sebelum menutupnya.

- [ ] **Step 3: Catat md5 DB produksi (baseline keamanan data)**

Run: `md5sum "dist/HR-Absensi/data/hr.db"`
Expected: satu hash — catat; harus IDENTIK di Step 7.

- [ ] **Step 4: Build installer**

Run (Git Bash, Inno Setup tidak ada di PATH default):
```bash
PATH="/c/Program Files (x86)/Inno Setup 6:$PATH" .venv/Scripts/python.exe -m tools.build_installer
```
Expected: PyInstaller sukses → ISCC sukses → `installer/Output/HR-Absensi-Setup-v24.0.0.exe` ada.

- [ ] **Step 5: Rotasi .exe produksi (pola 2-level)**

`data/` TIDAK PERNAH dipindah. Urutan: `.bak` → `.bak.old`, exe lama → `.bak`,
build baru → produksi.

- [ ] **Step 6: Salin installer ke titik ambil**

Run: `cp installer/Output/HR-Absensi-Setup-v24.0.0.exe "Installers/HR-Absensi-Setup-v24.0.0.exe"`
Expected: file ada di `Installers/`.

- [ ] **Step 7: Verifikasi DB produksi tidak tersentuh**

Run: `md5sum "dist/HR-Absensi/data/hr.db"`
Expected: hash IDENTIK dengan Step 3.

- [ ] **Step 8: Smoke test**

Jalankan `dist/HR-Absensi/HR-Absensi.exe`, pastikan app hidup > 8 detik dan
dashboard tampil; buka menu **Rekap Dinas** dan pastikan dua panel muncul.
Tutup app.

- [ ] **Step 9: Commit artefak & catatan rilis**

```bash
git add -A
git commit -m "build(v24): installer + rotasi produksi v24.0.0"
```

- [ ] **Step 10: BERHENTI — minta otorisasi push**

`git push` MEMBUTUHKAN izin eksplisit user (workflow_rules Rule 1). Laporkan
hasil build + smoke, lalu tanyakan apakah boleh push `v24.0.0` dan memajukan
`latest`. Jangan push tanpa jawaban.

---

## Catatan pelaksanaan

- Jalankan seluruh perintah dari root proyek `D:\Gawe\Project X\HR App`.
- Interpreter: `.venv/Scripts/python.exe`.
- JANGAN menulis ke `data/hr.db` produksi (`dist/HR-Absensi/data/hr.db`).
- Test Tk memakai fixture `tk_root` sesi-tunggal dari `tests/conftest.py` —
  jangan membuat `ctk.CTk()` baru di test layar (root ganda per proses tidak
  stabil di Windows).
