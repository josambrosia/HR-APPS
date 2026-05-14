# Issue Resolution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a "Tugas Belajar/Kuliah" reason category, a Batch Resolve popup, and derive-at-render Masuk/Terlambat corrections (with an adjustable penalty setting) to the HR Absensi issue-resolution flow.

**Architecture:** Three independent changes. (1) New reason category = two constant additions. (2) Derive-at-render correction = a pure `effective_attendance` helper consumed by the two Excel exporters; the DB columns are never mutated. (3) Batch Resolve = a new `CTkToplevel` modal that reuses the existing `set_reason` DB function. No schema changes, no import-flow changes.

**Tech Stack:** Python 3.13, SQLite (stdlib `sqlite3`), customtkinter (UI), openpyxl (Excel), pytest (tests).

---

## Codebase Notes (read before starting)

- **Spec:** `docs/superpowers/specs/2026-05-15-issue-resolution-design.md` — full design rationale.
- **Run all tests** (from the worktree root): `../../../.venv/Scripts/python.exe -m pytest -q`
- **Run one test:** `../../../.venv/Scripts/python.exe -m pytest tests/test_file.py::test_name -v`
- **Baseline:** 194 tests passing before this plan.
- **Test DB pattern:** `init_db(temp_db_path)` then `with get_connection(temp_db_path) as conn:`. The `temp_db_path` and `tk_root` (session-scoped, for UI) fixtures live in `tests/conftest.py`.
- **UI screen test pattern:** `monkeypatch.setattr(screen_mod, "DB_PATH", temp_db_path)`, construct with `tk_root`, `tk_root.update_idletasks()`, assert, `.destroy()`. See `tests/test_outlier_screen.py`.
- **`masuk` column format:** colon `HH:MM` (e.g. `08:15`). The `schedule_start` setting is dot format (`08.00`). The helper in Task 2 normalizes between them.
- **Reason categories** live in `src/config.py` `REASON_CATEGORIES` and `src/core/reason_mapper.py` `REASON_LABELS` — the two must stay key-synced (guarded by `test_reason_categories_and_labels_in_sync`).
- `COACHING_EXCLUDED = ("tugas_lapangan", "tugas_paparan", "terlambat_kerja")` in `src/config.py` — this IS the "work-justified-late" set.

---

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `src/config.py` | Modify | `REASON_CATEGORIES` +1; `DEFAULT_LUPA_PENALTY_MIN` constant |
| `src/core/reason_mapper.py` | Modify | `REASON_LABELS` +1; `effective_attendance` + 2 private format helpers |
| `src/db/settings.py` | Modify | `read_lupa_penalty_min(conn)` helper |
| `src/core/report_generator.py` | Modify | Feed an "effective row" through the monthly-report write loop |
| `src/core/weekly_export.py` | Modify | Add `reason_category` to SELECT; write effective Masuk/Terlambat |
| `src/ui/screens/settings.py` | Modify | "Penalti Lupa Absen Datang" row in the General tab |
| `src/ui/components/batch_resolve_dialog.py` | Create | Batch Resolve modal + 2 pure logic functions |
| `src/ui/screens/issues.py` | Modify | "+ Resolve Massal" header button + handler |
| `tests/test_reason_mapper.py` | Modify | 10-category test + `effective_attendance` tests |
| `tests/test_settings_repo.py` | Modify | `read_lupa_penalty_min` tests |
| `tests/test_report_generator.py` | Modify | Effective-value tests |
| `tests/test_weekly_export.py` | Modify | Effective-value tests |
| `tests/test_batch_resolve_dialog.py` | Create | Logic-function + construction-smoke tests |
| `tests/test_settings_screen.py` | Create | Settings screen smoke + penalty-save test |
| `tests/test_issues_screen.py` | Create | Issues screen smoke + button-wired test |

---

## Task 1: New reason category "Tugas Belajar/Kuliah"

**Files:**
- Modify: `src/config.py`
- Modify: `src/core/reason_mapper.py`
- Test: `tests/test_reason_mapper.py`

- [ ] **Step 1: Update the failing tests**

In `tests/test_reason_mapper.py`, rename `test_all_9_categories_present` to `test_all_10_categories_present` and add `tugas_belajar`:

```python
def test_all_10_categories_present():
    assert set(REASON_LABELS.keys()) == {
        "tugas_lapangan", "tugas_paparan", "izin_sakit", "cuti", "tugas_belajar",
        "terlambat_kerja", "terlambat_lain", "lupa_absen", "libur", "na",
    }
```

Add a new test next to `test_render_alasan_ijin_libur`:

```python
def test_render_alasan_ijin_tugas_belajar():
    assert render_alasan_ijin("tugas_belajar", None) == "Tugas Belajar/Kuliah"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `../../../.venv/Scripts/python.exe -m pytest tests/test_reason_mapper.py -v`
Expected: FAIL — `test_all_10_categories_present` (set mismatch), `test_render_alasan_ijin_tugas_belajar` (ValueError unknown category), and `test_reason_categories_and_labels_in_sync` still passes (neither constant changed yet).

- [ ] **Step 3: Add the category to `src/config.py`**

In `REASON_CATEGORIES`, add `"tugas_belajar"` after `"cuti"`:

```python
REASON_CATEGORIES = (
    "tugas_lapangan",
    "tugas_paparan",
    "izin_sakit",
    "cuti",
    "tugas_belajar",
    "terlambat_kerja",
    "terlambat_lain",
    "lupa_absen",
    "libur",
    "na",
)
```

- [ ] **Step 4: Add the label to `src/core/reason_mapper.py`**

In `REASON_LABELS`, add the entry after `"cuti"`:

```python
REASON_LABELS = {
    "tugas_lapangan":  "Tugas Lapangan",
    "tugas_paparan":   "Tugas Paparan",
    "izin_sakit":      "Izin Sakit",
    "cuti":            "Cuti",
    "tugas_belajar":   "Tugas Belajar/Kuliah",
    "terlambat_kerja": "Masuk Terlambat dengan Alasan Pekerjaan",
    "terlambat_lain":  "Terlambat dengan alasan",
    "lupa_absen":      "Lupa Absen",
    "libur":           "Libur",
    "na":              "NA / Belum ada kabar",
}
```

Do NOT add it to `REASON_NEEDS_DETAIL` and do NOT add a branch to `render_alasan_ijin` — it falls through to `return REASON_LABELS[category]`.

- [ ] **Step 5: Run tests to verify they pass**

Run: `../../../.venv/Scripts/python.exe -m pytest tests/test_reason_mapper.py -v`
Expected: PASS — all tests in the file.

- [ ] **Step 6: Commit**

```bash
git add src/config.py src/core/reason_mapper.py tests/test_reason_mapper.py
git commit -m "feat(reason): add Tugas Belajar/Kuliah reason category"
```

---

## Task 2: `effective_attendance` derive helper

**Files:**
- Modify: `src/core/reason_mapper.py`
- Test: `tests/test_reason_mapper.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_reason_mapper.py`. First update the import line at the top:

```python
from src.core.reason_mapper import render_alasan_ijin, REASON_LABELS, effective_attendance
```

Then add these tests at the end of the file:

```python
def _att_row(reason_category=None, masuk="09:40", keluar="16:00", terlambat_menit=100):
    return {
        "reason_category": reason_category, "masuk": masuk,
        "keluar": keluar, "terlambat_menit": terlambat_menit,
    }


def test_effective_attendance_work_justified_late_with_clock_in():
    row = _att_row(reason_category="tugas_lapangan", masuk="09:40", terlambat_menit=100)
    eff = effective_attendance(row, schedule_start="08.00", lupa_penalty_min=15)
    assert eff == {"masuk": "08:00", "terlambat_menit": 0}


def test_effective_attendance_work_justified_late_no_badge():
    row = _att_row(reason_category="tugas_lapangan", masuk=None, keluar=None,
                   terlambat_menit=None)
    eff = effective_attendance(row, schedule_start="08.00", lupa_penalty_min=15)
    assert eff == {"masuk": None, "terlambat_menit": None}


def test_effective_attendance_forgot_clock_in():
    row = _att_row(reason_category="lupa_absen", masuk=None, keluar="16:05",
                   terlambat_menit=None)
    eff = effective_attendance(row, schedule_start="08.00", lupa_penalty_min=15)
    assert eff == {"masuk": "08:15", "terlambat_menit": 15}


def test_effective_attendance_forgot_clock_out_untouched():
    row = _att_row(reason_category="lupa_absen", masuk="08:05", keluar=None,
                   terlambat_menit=5)
    eff = effective_attendance(row, schedule_start="08.00", lupa_penalty_min=15)
    assert eff == {"masuk": "08:05", "terlambat_menit": 5}


def test_effective_attendance_other_category_untouched():
    row = _att_row(reason_category="izin_sakit", masuk="08:30", terlambat_menit=30)
    eff = effective_attendance(row, schedule_start="08.00", lupa_penalty_min=15)
    assert eff == {"masuk": "08:30", "terlambat_menit": 30}


def test_effective_attendance_no_reason_untouched():
    row = _att_row(reason_category=None, masuk="08:30", terlambat_menit=30)
    eff = effective_attendance(row, schedule_start="08.00", lupa_penalty_min=15)
    assert eff == {"masuk": "08:30", "terlambat_menit": 30}


def test_effective_attendance_custom_penalty():
    row = _att_row(reason_category="lupa_absen", masuk=None, keluar="16:00",
                   terlambat_menit=None)
    eff = effective_attendance(row, schedule_start="08.00", lupa_penalty_min=20)
    assert eff == {"masuk": "08:20", "terlambat_menit": 20}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `../../../.venv/Scripts/python.exe -m pytest tests/test_reason_mapper.py -v`
Expected: FAIL — `ImportError: cannot import name 'effective_attendance'`.

- [ ] **Step 3: Implement the helper in `src/core/reason_mapper.py`**

Add the config import at the top of the file (after `from typing import Optional`):

```python
from src.config import COACHING_EXCLUDED
```

Add at the end of the file:

```python
def _schedule_start_minutes(schedule_start: str) -> int:
    """Parse the schedule_start setting ('08.00' dot-format) to
    minutes-from-midnight. Falls back to 480 (08:00) on malformed input."""
    try:
        h, m = schedule_start.replace(":", ".").split(".")
        return int(h) * 60 + int(m)
    except (ValueError, AttributeError):
        return 8 * 60


def _minutes_to_hhmm(total_min: int) -> str:
    """480 -> '08:00', 495 -> '08:15'. Colon format, to match the masuk column."""
    h, m = divmod(total_min, 60)
    return f"{h:02d}:{m:02d}"


def effective_attendance(row, *, schedule_start: str, lupa_penalty_min: int) -> dict:
    """Compute the 'effective' Masuk & Terlambat for one attendance row,
    derived from reason_category. Does NOT touch the DB — used at export
    render time so the raw fingerprint columns stay intact.

    `row` must support row["reason_category"], row["masuk"], row["keluar"],
    row["terlambat_menit"] (works for both dict and sqlite3.Row).

    Returns {"masuk": str | None, "terlambat_menit": int | None}.

    Rules:
      - reason_category in COACHING_EXCLUDED (work-justified-late) AND raw
        masuk is set (a real late clock-in) -> masuk = schedule_start,
        terlambat_menit = 0.
      - reason_category in COACHING_EXCLUDED AND raw masuk is NULL (a no-badge
        field day) -> no correction; stays a justified absence.
      - reason_category == 'lupa_absen' AND masuk is NULL AND keluar is set
        (forgot to clock IN) -> terlambat_menit = lupa_penalty_min,
        masuk = schedule_start + lupa_penalty_min.
      - everything else (incl. lupa_absen forgot-OUT, other categories,
        no reason) -> raw values unchanged.
    """
    cat = row["reason_category"]
    masuk = row["masuk"]
    keluar = row["keluar"]
    terlambat = row["terlambat_menit"]

    if cat in COACHING_EXCLUDED:
        if masuk is not None:
            return {
                "masuk": _minutes_to_hhmm(_schedule_start_minutes(schedule_start)),
                "terlambat_menit": 0,
            }
        return {"masuk": masuk, "terlambat_menit": terlambat}

    if cat == "lupa_absen" and masuk is None and keluar is not None:
        return {
            "masuk": _minutes_to_hhmm(
                _schedule_start_minutes(schedule_start) + lupa_penalty_min),
            "terlambat_menit": lupa_penalty_min,
        }

    return {"masuk": masuk, "terlambat_menit": terlambat}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `../../../.venv/Scripts/python.exe -m pytest tests/test_reason_mapper.py -v`
Expected: PASS — all tests in the file.

- [ ] **Step 5: Commit**

```bash
git add src/core/reason_mapper.py tests/test_reason_mapper.py
git commit -m "feat(reason): effective_attendance helper for derive-at-render corrections"
```

---

## Task 3: Penalty setting + `read_lupa_penalty_min` helper

**Files:**
- Modify: `src/config.py`
- Modify: `src/db/settings.py`
- Test: `tests/test_settings_repo.py`

- [ ] **Step 1: Write the failing tests**

In `tests/test_settings_repo.py`, update the import line:

```python
from src.db.settings import get_setting, set_setting, read_lupa_penalty_min
```

Add these tests at the end of the file:

```python
def test_read_lupa_penalty_min_default(temp_db_path):
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        assert read_lupa_penalty_min(conn) == 15


def test_read_lupa_penalty_min_custom(temp_db_path):
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        set_setting(conn, "lupa_absen_datang_penalty_min", "20")
        assert read_lupa_penalty_min(conn) == 20


def test_read_lupa_penalty_min_malformed_falls_back(temp_db_path):
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        set_setting(conn, "lupa_absen_datang_penalty_min", "abc")
        assert read_lupa_penalty_min(conn) == 15
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `../../../.venv/Scripts/python.exe -m pytest tests/test_settings_repo.py -v`
Expected: FAIL — `ImportError: cannot import name 'read_lupa_penalty_min'`.

- [ ] **Step 3: Add the constant to `src/config.py`**

In the `# Defaults` block, after `DEFAULT_COACHING_THRESHOLD_MINUTES = 75`:

```python
DEFAULT_LUPA_PENALTY_MIN = 15
```

- [ ] **Step 4: Add `read_lupa_penalty_min` to `src/db/settings.py`**

Add the import at the top (after `from typing import Optional`):

```python
from src.config import DEFAULT_LUPA_PENALTY_MIN
```

Add at the end of the file:

```python
def read_lupa_penalty_min(conn: sqlite3.Connection) -> int:
    """Read the configurable 'forgot to clock in' lateness penalty (minutes).

    Stored under the 'lupa_absen_datang_penalty_min' settings key as a string.
    Falls back to DEFAULT_LUPA_PENALTY_MIN on a missing or non-integer value.
    """
    raw = get_setting(conn, "lupa_absen_datang_penalty_min",
                      default=str(DEFAULT_LUPA_PENALTY_MIN))
    try:
        return int(raw)
    except (ValueError, TypeError):
        return DEFAULT_LUPA_PENALTY_MIN
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `../../../.venv/Scripts/python.exe -m pytest tests/test_settings_repo.py -v`
Expected: PASS — all tests in the file.

- [ ] **Step 6: Commit**

```bash
git add src/config.py src/db/settings.py tests/test_settings_repo.py
git commit -m "feat(settings): lupa-absen-datang penalty setting + read helper"
```

---

## Task 4: Apply effective values in the monthly report

**Files:**
- Modify: `src/core/report_generator.py`
- Test: `tests/test_report_generator.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_report_generator.py` (the file already imports `upsert_employee`, `upsert_attendance`, `set_reason`, `generate_monthly_report`, `load_workbook`, and has the `_conn()` helper):

```python
def test_generate_applies_effective_masuk_for_work_justified_late(tmp_path):
    """A tugas_lapangan-resolved late row exports Masuk=08:00, Terlambat=0."""
    conn = _conn()
    emp = upsert_employee(conn, no_staff="1", nama="ANDI", dept="X")
    upsert_attendance(
        conn, employee_id=emp, tanggal="2026-04-01", hari="Rabu",
        tipe="Hari Kerja", jadwal="08.00 - 16.00", masuk="09:40",
        keluar="16:00", kerja_jam=6.5, lembur_jam=None,
        terlambat_menit=100, has_issue=1, imported_from="t.xls",
    )
    rid = conn.execute("SELECT id FROM attendance_records").fetchone()["id"]
    set_reason(conn, attendance_id=rid, category="tugas_lapangan", detail="Sragen")
    out = tmp_path / "out.xlsx"
    generate_monthly_report(conn, year_month="2026-04", out_path=out)
    ws = load_workbook(out).active
    assert ws.cell(row=3, column=7).value == "08:00"   # G Masuk -> effective
    assert ws.cell(row=3, column=12).value == 0        # L Terlambat -> 0


def test_generate_applies_effective_for_forgot_clock_in(tmp_path):
    """A lupa_absen forgot-IN row exports Masuk=08:15, Terlambat=15, and
    stops counting as a 'lupa' day (column O blank)."""
    conn = _conn()
    emp = upsert_employee(conn, no_staff="1", nama="ANDI", dept="X")
    upsert_attendance(
        conn, employee_id=emp, tanggal="2026-04-01", hari="Rabu",
        tipe="Hari Kerja", jadwal="08.00 - 16.00", masuk=None,
        keluar="16:05", kerja_jam=None, lembur_jam=None,
        terlambat_menit=None, has_issue=1, imported_from="t.xls",
    )
    rid = conn.execute("SELECT id FROM attendance_records").fetchone()["id"]
    set_reason(conn, attendance_id=rid, category="lupa_absen", detail=None)
    out = tmp_path / "out.xlsx"
    generate_monthly_report(conn, year_month="2026-04", out_path=out)
    ws = load_workbook(out).active
    assert ws.cell(row=3, column=7).value == "08:15"      # G Masuk -> effective
    assert ws.cell(row=3, column=12).value == 15          # L Terlambat -> penalty
    assert ws.cell(row=3, column=15).value in (None, "")  # O Lupa -> no longer lupa


def test_generate_no_badge_work_justified_stays_absent(tmp_path):
    """tugas_lapangan with masuk AND keluar NULL: no correction, stays absent."""
    conn = _conn()
    emp = upsert_employee(conn, no_staff="1", nama="ANDI", dept="X")
    upsert_attendance(
        conn, employee_id=emp, tanggal="2026-04-01", hari="Rabu",
        tipe="Hari Kerja", jadwal="08.00 - 16.00", masuk=None,
        keluar=None, kerja_jam=None, lembur_jam=None,
        terlambat_menit=None, has_issue=1, imported_from="t.xls",
    )
    rid = conn.execute("SELECT id FROM attendance_records").fetchone()["id"]
    set_reason(conn, attendance_id=rid, category="tugas_lapangan", detail="Sragen")
    out = tmp_path / "out.xlsx"
    generate_monthly_report(conn, year_month="2026-04", out_path=out)
    ws = load_workbook(out).active
    assert ws.cell(row=3, column=7).value in (None, "")   # G Masuk stays blank
    assert ws.cell(row=3, column=14).value == 1           # N Absen -> still absent
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `../../../.venv/Scripts/python.exe -m pytest tests/test_report_generator.py -v`
Expected: FAIL — the three new tests (raw values written: G=`09:40`/blank, L=`100`/blank).

- [ ] **Step 3: Add imports to `src/core/report_generator.py`**

The file currently has `from src.config import TEMPLATE_LAPORAN_BULANAN, REASON_CATEGORIES` and `from src.core.reason_mapper import render_alasan_ijin`. Change them to:

```python
from src.config import TEMPLATE_LAPORAN_BULANAN, REASON_CATEGORIES, DEFAULT_SCHEDULE_START
from src.core.reason_mapper import render_alasan_ijin, effective_attendance
from src.db.settings import get_setting, read_lupa_penalty_min
```

- [ ] **Step 4: Read settings + use the effective row in `generate_monthly_report`**

In `generate_monthly_report`, immediately after `wb = load_workbook(TEMPLATE_LAPORAN_BULANAN)` and `ws = wb.active`, add:

```python
    schedule_start = get_setting(conn, "schedule_start", default=DEFAULT_SCHEDULE_START)
    lupa_penalty = read_lupa_penalty_min(conn)
```

Then change the per-row loop. The current loop body is:

```python
        for r in emp_records:
            is_holiday = r.get("tipe") == "Hari Libur"
            derived = {} if is_holiday else compute_derived(r)
            _write_data_row(ws, current_row, r, derived, data_styles, is_holiday=is_holiday)
            if not is_holiday:
                _accumulate_total(total, r, derived)
                if r.get("has_issue") == 1 and not r.get("reason_category"):
                    na_count += 1
            rows_generated += 1
            current_row += 1
```

Replace it with:

```python
        for r in emp_records:
            is_holiday = r.get("tipe") == "Hari Libur"
            if not is_holiday:
                eff = effective_attendance(
                    r, schedule_start=schedule_start, lupa_penalty_min=lupa_penalty)
                r = {**r, "masuk": eff["masuk"],
                     "terlambat_menit": eff["terlambat_menit"]}
            derived = {} if is_holiday else compute_derived(r)
            _write_data_row(ws, current_row, r, derived, data_styles, is_holiday=is_holiday)
            if not is_holiday:
                _accumulate_total(total, r, derived)
                if r.get("has_issue") == 1 and not r.get("reason_category"):
                    na_count += 1
            rows_generated += 1
            current_row += 1
```

(The rebound `r` is a dict copy with `masuk`/`terlambat_menit` overridden; `reason_category` and all other keys are preserved, so the `na_count` check and `compute_derived`'s `ijin_hari` still work.)

- [ ] **Step 5: Run tests to verify they pass**

Run: `../../../.venv/Scripts/python.exe -m pytest tests/test_report_generator.py -v`
Expected: PASS — all tests in the file (the 3 new + all pre-existing).

- [ ] **Step 6: Commit**

```bash
git add src/core/report_generator.py tests/test_report_generator.py
git commit -m "feat(report): apply effective Masuk/Terlambat in monthly report"
```

---

## Task 5: Apply effective values in the weekly export

**Files:**
- Modify: `src/core/weekly_export.py`
- Test: `tests/test_weekly_export.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_weekly_export.py` (file already imports `upsert_employee`, `upsert_attendance`, `generate_weekly_export`, `load_workbook`, has `_conn()`):

```python
def test_weekly_export_effective_masuk_work_justified_late(tmp_path):
    from src.db.attendance import set_reason
    conn = _conn()
    a = upsert_employee(conn, no_staff="1", nama="ANDI", dept="X")
    upsert_attendance(
        conn, employee_id=a, tanggal="2026-04-07", hari="Selasa",
        tipe="Hari Kerja", jadwal="08.00 - 16.00", masuk="09:40",
        keluar="16:00", kerja_jam=6.5, lembur_jam=None,
        terlambat_menit=100, has_issue=1, imported_from="W1.xls",
    )
    rid = conn.execute("SELECT id FROM attendance_records").fetchone()["id"]
    set_reason(conn, attendance_id=rid, category="tugas_paparan", detail="PT X")
    out = tmp_path / "weekly.xlsx"
    generate_weekly_export(conn, "2026-04-06", "2026-04-12", out)
    ws = load_workbook(out).active
    assert ws.cell(row=2, column=8).value == "08:00"   # H Masuk -> effective
    assert ws.cell(row=2, column=12).value == 0        # L Terlambat -> 0


def test_weekly_export_effective_forgot_clock_in(tmp_path):
    from src.db.attendance import set_reason
    conn = _conn()
    a = upsert_employee(conn, no_staff="1", nama="ANDI", dept="X")
    upsert_attendance(
        conn, employee_id=a, tanggal="2026-04-07", hari="Selasa",
        tipe="Hari Kerja", jadwal="08.00 - 16.00", masuk=None,
        keluar="16:05", kerja_jam=None, lembur_jam=None,
        terlambat_menit=None, has_issue=1, imported_from="W1.xls",
    )
    rid = conn.execute("SELECT id FROM attendance_records").fetchone()["id"]
    set_reason(conn, attendance_id=rid, category="lupa_absen", detail=None)
    out = tmp_path / "weekly.xlsx"
    generate_weekly_export(conn, "2026-04-06", "2026-04-12", out)
    ws = load_workbook(out).active
    assert ws.cell(row=2, column=8).value == "08:15"   # H Masuk -> effective
    assert ws.cell(row=2, column=12).value == 15       # L Terlambat -> penalty
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `../../../.venv/Scripts/python.exe -m pytest tests/test_weekly_export.py -v`
Expected: FAIL — the two new tests (raw values written).

- [ ] **Step 3: Add imports + reason_category to the SELECT in `src/core/weekly_export.py`**

After the existing imports (`from openpyxl.styles import Font`), add:

```python
from src.config import DEFAULT_SCHEDULE_START
from src.core.reason_mapper import effective_attendance
from src.db.settings import get_setting, read_lupa_penalty_min
```

In `generate_weekly_export`, change the SELECT to add `ar.reason_category`:

```python
    rows = conn.execute(
        """
        SELECT e.nama, e.no_staff, e.dept,
               ar.tanggal, ar.hari, ar.tipe, ar.jadwal,
               ar.masuk, ar.keluar, ar.kerja_jam, ar.lembur_jam,
               ar.terlambat_menit, ar.reason_category
          FROM attendance_records ar
          JOIN employees e ON ar.employee_id = e.id
         WHERE ar.tanggal BETWEEN ? AND ?
         ORDER BY e.nama ASC, ar.tanggal ASC
        """,
        (period_start, period_end),
    ).fetchall()
```

- [ ] **Step 4: Read settings + write effective values in the row loop**

Immediately after the `rows = conn.execute(...).fetchall()` block, add:

```python
    schedule_start = get_setting(conn, "schedule_start", default=DEFAULT_SCHEDULE_START)
    lupa_penalty = read_lupa_penalty_min(conn)
```

The current row loop body is:

```python
    for r in rows:
        employees.add(r["no_staff"])
        is_holiday = r["tipe"] == "Hari Libur"
        ws.append([
            r["nama"],
            r["no_staff"] or "",
            r["dept"] or "",
            r["tanggal"],
            r["hari"] or "",
            r["tipe"] or "",
            r["jadwal"] or "",
            "" if is_holiday else (r["masuk"] or ""),
            "" if is_holiday else (r["keluar"] or ""),
            "" if is_holiday else (
                r["kerja_jam"] if r["kerja_jam"] is not None else ""),
            "" if is_holiday else (
                r["lembur_jam"] if r["lembur_jam"] is not None else ""),
            "" if is_holiday else (
                r["terlambat_menit"] if r["terlambat_menit"] is not None else ""),
        ])
```

Replace it with:

```python
    for r in rows:
        employees.add(r["no_staff"])
        is_holiday = r["tipe"] == "Hari Libur"
        if is_holiday:
            eff_masuk, eff_terlambat = None, None
        else:
            eff = effective_attendance(
                r, schedule_start=schedule_start, lupa_penalty_min=lupa_penalty)
            eff_masuk = eff["masuk"]
            eff_terlambat = eff["terlambat_menit"]
        ws.append([
            r["nama"],
            r["no_staff"] or "",
            r["dept"] or "",
            r["tanggal"],
            r["hari"] or "",
            r["tipe"] or "",
            r["jadwal"] or "",
            "" if is_holiday else (eff_masuk or ""),
            "" if is_holiday else (r["keluar"] or ""),
            "" if is_holiday else (
                r["kerja_jam"] if r["kerja_jam"] is not None else ""),
            "" if is_holiday else (
                r["lembur_jam"] if r["lembur_jam"] is not None else ""),
            "" if is_holiday else (
                eff_terlambat if eff_terlambat is not None else ""),
        ])
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `../../../.venv/Scripts/python.exe -m pytest tests/test_weekly_export.py -v`
Expected: PASS — all tests in the file (2 new + all pre-existing, including the holiday-row test).

- [ ] **Step 6: Commit**

```bash
git add src/core/weekly_export.py tests/test_weekly_export.py
git commit -m "feat(export): apply effective Masuk/Terlambat in weekly export"
```

---

## Task 6: "Penalti Lupa Absen Datang" row in Settings

**Files:**
- Modify: `src/ui/screens/settings.py`
- Test: `tests/test_settings_screen.py` (create)

- [ ] **Step 1: Write the failing test**

Create `tests/test_settings_screen.py`:

```python
"""Smoke + behaviour test for the Settings screen."""
from src.db.schema import init_db
from src.db.connection import get_connection
from src.db.settings import get_setting


def test_settings_screen_constructs(temp_db_path, monkeypatch, tk_root):
    import src.ui.screens.settings as settings_mod
    monkeypatch.setattr(settings_mod, "DB_PATH", temp_db_path)
    init_db(temp_db_path)
    screen = settings_mod.SettingsScreen(tk_root)
    tk_root.update_idletasks()
    assert screen is not None
    screen.destroy()


def test_settings_screen_saves_lupa_penalty(temp_db_path, monkeypatch, tk_root):
    import src.ui.screens.settings as settings_mod
    monkeypatch.setattr(settings_mod, "DB_PATH", temp_db_path)
    monkeypatch.setattr(settings_mod.messagebox, "showinfo", lambda *a, **k: None)
    init_db(temp_db_path)
    screen = settings_mod.SettingsScreen(tk_root)
    tk_root.update_idletasks()
    screen.lupa_penalty_var.set("25")
    screen._save()
    with get_connection(temp_db_path) as conn:
        assert get_setting(conn, "lupa_absen_datang_penalty_min") == "25"
    screen.destroy()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `../../../.venv/Scripts/python.exe -m pytest tests/test_settings_screen.py -v`
Expected: FAIL — `test_settings_screen_saves_lupa_penalty` (`AttributeError: 'SettingsScreen' object has no attribute 'lupa_penalty_var'`). `test_settings_screen_constructs` may already pass.

- [ ] **Step 3: Read the setting in `_build_general`**

In `src/ui/screens/settings.py`, `_build_general` opens with a settings read block. Add the penalty read:

```python
        with get_connection(DB_PATH) as conn:
            current_month = get_setting(conn, "current_month", default="")
            sched_start = get_setting(conn, "schedule_start", default="08.00")
            sched_end = get_setting(conn, "schedule_end", default="16.00")
            threshold = get_setting(conn, "coaching_threshold_min", default="75")
            lupa_penalty = get_setting(conn, "lupa_absen_datang_penalty_min",
                                       default="15")
```

- [ ] **Step 4: Add the penalty row after `row3`**

In `_build_general`, after the `row3` block (the "Jadwal Kerja:" display frame) and BEFORE the "Simpan Pengaturan" `CTkButton`, insert:

```python
        row4 = ctk.CTkFrame(
            parent, fg_color=COLOR_SURFACE,
            border_width=1, border_color=COLOR_BORDER,
            corner_radius=RADIUS_MD,
        )
        row4.pack(fill="x", pady=SPACE_SM)
        ctk.CTkLabel(
            row4, text="Penalti Lupa Absen Datang (menit):",
            font=FONT_BODY, text_color=COLOR_TEXT,
        ).pack(side="left", padx=SPACE_MD, pady=SPACE_SM + 2)
        self.lupa_penalty_var = ctk.StringVar(value=lupa_penalty)
        ctk.CTkEntry(
            row4, textvariable=self.lupa_penalty_var, width=80,
            fg_color=COLOR_SURFACE_HIGH,
            border_width=1, border_color=COLOR_BORDER,
            text_color=COLOR_TEXT,
            font=FONT_BODY,
            placeholder_text_color=COLOR_TEXT_MUTED,
        ).pack(side="left")
```

- [ ] **Step 5: Persist the setting in `_save`**

Change `_save` to also write the penalty:

```python
    def _save(self):
        with get_connection(DB_PATH) as conn:
            set_setting(conn, "current_month", self.month_var.get().strip())
            set_setting(conn, "coaching_threshold_min", self.thr_var.get().strip())
            set_setting(conn, "lupa_absen_datang_penalty_min",
                        self.lupa_penalty_var.get().strip())
        messagebox.showinfo("Tersimpan", "Pengaturan disimpan.")
```

- [ ] **Step 6: Run the test to verify it passes**

Run: `../../../.venv/Scripts/python.exe -m pytest tests/test_settings_screen.py -v`
Expected: PASS — both tests.

- [ ] **Step 7: Commit**

```bash
git add src/ui/screens/settings.py tests/test_settings_screen.py
git commit -m "feat(ui): Penalti Lupa Absen Datang row in Settings"
```

---

## Task 7: Batch Resolve dialog component

**Files:**
- Create: `src/ui/components/batch_resolve_dialog.py`
- Test: `tests/test_batch_resolve_dialog.py` (create)

- [ ] **Step 1: Write the failing tests**

Create `tests/test_batch_resolve_dialog.py`:

```python
"""Tests for the Batch Resolve dialog — pure logic + construction smoke."""
from src.db.schema import init_db
from src.db.connection import get_connection
from src.db.employees import upsert_employee
from src.db.attendance import upsert_attendance, list_issues_for_period
from src.ui.components.batch_resolve_dialog import (
    group_open_issues_by_employee, apply_batch_resolve, BatchResolveDialog,
)


def _issue(conn, emp_id, tanggal, hari):
    upsert_attendance(
        conn, employee_id=emp_id, tanggal=tanggal, hari=hari,
        tipe="Hari Kerja", jadwal="08.00 - 16.00",
        masuk=None, keluar="16:00", kerja_jam=None,
        lembur_jam=None, terlambat_menit=None,
        has_issue=1, imported_from="W1.xls",
    )


def test_group_open_issues_by_employee(temp_db_path):
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        a = upsert_employee(conn, no_staff="1", nama="ZARA", dept="X")
        b = upsert_employee(conn, no_staff="2", nama="ANDI", dept="Y")
        _issue(conn, a, "2026-04-07", "Selasa")
        _issue(conn, b, "2026-04-07", "Selasa")
        _issue(conn, b, "2026-04-08", "Rabu")
        rows = list_issues_for_period(conn, "2026-04-01", "2026-04-30",
                                      resolved=False)
        groups = group_open_issues_by_employee(rows)
    assert [g["nama"] for g in groups] == ["ANDI", "ZARA"]   # sorted by nama
    andi = groups[0]
    assert len(andi["issues"]) == 2
    assert {i["tanggal"] for i in andi["issues"]} == {"2026-04-07", "2026-04-08"}
    assert all("attendance_id" in i for i in andi["issues"])


def test_apply_batch_resolve_sets_reason_on_all(temp_db_path):
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        a = upsert_employee(conn, no_staff="1", nama="ANDI", dept="X")
        _issue(conn, a, "2026-04-07", "Selasa")
        _issue(conn, a, "2026-04-08", "Rabu")
        ids = [r["id"] for r in conn.execute(
            "SELECT id FROM attendance_records").fetchall()]
        n = apply_batch_resolve(conn, ids, "tugas_lapangan", "Sragen")
        assert n == 2
        rows = conn.execute(
            "SELECT reason_category, reason_detail FROM attendance_records"
        ).fetchall()
    assert all(r["reason_category"] == "tugas_lapangan" for r in rows)
    assert all(r["reason_detail"] == "Sragen" for r in rows)


def test_batch_resolve_dialog_constructs(temp_db_path, monkeypatch, tk_root):
    import src.ui.components.batch_resolve_dialog as mod
    monkeypatch.setattr(mod, "DB_PATH", temp_db_path)
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        a = upsert_employee(conn, no_staff="1", nama="ANDI", dept="X")
        _issue(conn, a, "2026-04-07", "Selasa")
        conn.commit()
    dlg = mod.BatchResolveDialog(
        tk_root, period_start="2026-04-01", period_end="2026-04-30",
        on_done=lambda: None)
    tk_root.update_idletasks()
    assert dlg is not None
    dlg.destroy()


def test_batch_resolve_dialog_constructs_with_no_issues(temp_db_path, monkeypatch, tk_root):
    """No open issues — empty state, must not crash."""
    import src.ui.components.batch_resolve_dialog as mod
    monkeypatch.setattr(mod, "DB_PATH", temp_db_path)
    init_db(temp_db_path)
    dlg = mod.BatchResolveDialog(
        tk_root, period_start="2026-04-01", period_end="2026-04-30",
        on_done=lambda: None)
    tk_root.update_idletasks()
    assert dlg is not None
    dlg.destroy()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `../../../.venv/Scripts/python.exe -m pytest tests/test_batch_resolve_dialog.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.ui.components.batch_resolve_dialog'`.

- [ ] **Step 3: Create `src/ui/components/batch_resolve_dialog.py`**

```python
"""Modal dialog — resolve multiple open issues for one employee at once.

Pick an employee, check the dates with open issues (default all checked),
choose one reason category (+ optional detail), and apply it to every
checked date via the existing set_reason DB function.
"""
from typing import Callable, Optional

import customtkinter as ctk
from tkinter import messagebox

from src.config import DB_PATH
from src.db.connection import get_connection
from src.db.attendance import set_reason, list_issues_for_period
from src.core.reason_mapper import REASON_LABELS, REASON_NEEDS_DETAIL
from src.ui.theme import (
    COLOR_BG, COLOR_SURFACE, COLOR_SURFACE_HIGH,
    COLOR_BORDER,
    COLOR_ACCENT, COLOR_ACCENT_HOVER,
    COLOR_INFO,
    COLOR_TEXT, COLOR_TEXT_DIM, COLOR_TEXT_MUTED,
    FONT_HEADING, FONT_BODY, FONT_BODY_BOLD, FONT_SMALL, FONT_LABEL,
    SPACE_XS, SPACE_SM, SPACE_MD, SPACE_LG, SPACE_XL,
    RADIUS_MD,
)

DIALOG_W = 520
DIALOG_H = 600
_SCREEN_BUFFER = 100

_MONTH_ID = {
    1: "Januari", 2: "Februari", 3: "Maret", 4: "April", 5: "Mei", 6: "Juni",
    7: "Juli", 8: "Agustus", 9: "September", 10: "Oktober",
    11: "November", 12: "Desember",
}


def _format_tanggal(iso: str, hari: Optional[str]) -> str:
    """'2026-04-06', 'Senin' -> 'Senin, 6 April 2026'."""
    try:
        y, m, d = iso.split("-")
        label = f"{int(d)} {_MONTH_ID[int(m)]} {y}"
    except (ValueError, KeyError):
        return iso
    return f"{hari}, {label}" if hari else label


def group_open_issues_by_employee(issue_rows) -> list:
    """Group open-issue rows (from list_issues_for_period(resolved=False))
    by employee. Returns a list of dicts sorted by nama:
      {employee_id, nama, dept, no_staff,
       issues: [{attendance_id, tanggal, hari, masuk, keluar}, ...]}
    """
    by_emp = {}
    for r in issue_rows:
        eid = r["employee_id"]
        if eid not in by_emp:
            by_emp[eid] = {
                "employee_id": eid,
                "nama": r["nama"],
                "dept": r["dept"],
                "no_staff": r["no_staff"],
                "issues": [],
            }
        by_emp[eid]["issues"].append({
            "attendance_id": r["id"],
            "tanggal": r["tanggal"],
            "hari": r["hari"],
            "masuk": r["masuk"],
            "keluar": r["keluar"],
        })
    return sorted(by_emp.values(), key=lambda e: e["nama"])


def apply_batch_resolve(conn, attendance_ids: list, category: str,
                        detail: Optional[str]) -> int:
    """Resolve each attendance_id with the given category + detail via
    set_reason. Returns the count resolved. Caller commits."""
    for aid in attendance_ids:
        set_reason(conn, attendance_id=aid, category=category, detail=detail)
    return len(attendance_ids)


class BatchResolveDialog(ctk.CTkToplevel):
    """Modal — resolve many open issues for one employee in one action."""

    def __init__(self, parent, *, period_start: str, period_end: str,
                 on_done: Callable[[], None]):
        super().__init__(parent)
        self.title("Resolve Massal")
        self.resizable(False, False)
        self.configure(fg_color=COLOR_BG)
        self.transient(parent)

        sh = self.winfo_screenheight()
        sw = self.winfo_screenwidth()
        h = min(DIALOG_H, sh - _SCREEN_BUFFER)
        w = DIALOG_W
        x = (sw - w) // 2
        y = (sh - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")

        self._on_done = on_done

        with get_connection(DB_PATH) as conn:
            rows = list_issues_for_period(
                conn, period_start, period_end, resolved=False)
        self._groups = group_open_issues_by_employee(rows)
        self._by_label = {
            f"{g['nama']} ({g['dept'] or '-'}) — {len(g['issues'])} issue terbuka": g
            for g in self._groups
        }

        self._date_vars: dict = {}
        self._label_to_key = {v: k for k, v in REASON_LABELS.items()}

        self._build()

        self.after(50, lambda: (self.grab_set(), self.focus_set()))
        self.bind("<Escape>", lambda _e: self._on_cancel())
        self.protocol("WM_DELETE_WINDOW", self._on_cancel)

    def _build(self):
        ctk.CTkLabel(
            self, text="Resolve Massal",
            font=FONT_HEADING, text_color=COLOR_TEXT,
        ).pack(anchor="w", padx=SPACE_XL, pady=(SPACE_LG, SPACE_XS))
        ctk.CTkLabel(
            self, text="Selesaikan beberapa issue sekaligus untuk satu karyawan.",
            font=FONT_BODY, text_color=COLOR_TEXT_DIM,
        ).pack(anchor="w", padx=SPACE_XL, pady=(0, SPACE_MD))

        if not self._groups:
            ctk.CTkLabel(
                self, text="Tidak ada issue terbuka di periode ini.",
                font=FONT_BODY, text_color=COLOR_TEXT_MUTED,
            ).pack(pady=60, padx=SPACE_XL)
            ctk.CTkButton(
                self, text="Tutup", command=self._on_cancel,
                fg_color="transparent", border_width=1, border_color=COLOR_INFO,
                text_color=COLOR_INFO, hover_color=COLOR_SURFACE_HIGH,
                width=160, height=40, font=FONT_BODY_BOLD, corner_radius=RADIUS_MD,
            ).pack(side="bottom", pady=(0, SPACE_LG))
            return

        ctk.CTkLabel(self, text="KARYAWAN", font=FONT_LABEL,
                     text_color=COLOR_TEXT_MUTED).pack(
            anchor="w", padx=SPACE_XL, pady=(0, SPACE_XS))
        self._emp_var = ctk.StringVar(value="")
        ctk.CTkComboBox(
            self, values=list(self._by_label.keys()),
            variable=self._emp_var, width=DIALOG_W - 2 * SPACE_XL,
            command=self._on_employee_change,
            fg_color=COLOR_SURFACE_HIGH, button_color=COLOR_ACCENT,
            button_hover_color=COLOR_ACCENT_HOVER, border_color=COLOR_BORDER,
            text_color=COLOR_TEXT, font=FONT_BODY,
        ).pack(anchor="w", padx=SPACE_XL, pady=(0, SPACE_MD))

        ctk.CTkLabel(self, text="TANGGAL DENGAN ISSUE TERBUKA", font=FONT_LABEL,
                     text_color=COLOR_TEXT_MUTED).pack(
            anchor="w", padx=SPACE_XL, pady=(0, SPACE_XS))
        self._dates_scroll = ctk.CTkScrollableFrame(
            self, fg_color=COLOR_SURFACE, height=160)
        self._dates_scroll.pack(fill="x", padx=SPACE_XL, pady=(0, SPACE_MD))

        ctk.CTkLabel(self, text="KATEGORI ALASAN", font=FONT_LABEL,
                     text_color=COLOR_TEXT_MUTED).pack(
            anchor="w", padx=SPACE_XL, pady=(0, SPACE_XS))
        self._cat_var = ctk.StringVar(value="")
        ctk.CTkComboBox(
            self, values=list(REASON_LABELS.values()),
            variable=self._cat_var, width=DIALOG_W - 2 * SPACE_XL,
            command=self._on_cat_change,
            fg_color=COLOR_SURFACE_HIGH, button_color=COLOR_ACCENT,
            button_hover_color=COLOR_ACCENT_HOVER, border_color=COLOR_BORDER,
            text_color=COLOR_TEXT, font=FONT_BODY,
        ).pack(anchor="w", padx=SPACE_XL, pady=(0, SPACE_XS))

        self._detail_label = ctk.CTkLabel(
            self, text="Detail:", font=FONT_SMALL, text_color=COLOR_TEXT_MUTED)
        self._detail_entry = ctk.CTkEntry(
            self, width=DIALOG_W - 2 * SPACE_XL,
            fg_color=COLOR_SURFACE_HIGH, border_width=1,
            border_color=COLOR_BORDER, text_color=COLOR_TEXT, font=FONT_BODY)

        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(fill="x", padx=SPACE_XL, pady=(SPACE_LG, SPACE_LG),
                     side="bottom")
        self._submit_btn = ctk.CTkButton(
            btn_row, text="Resolve", command=self._on_submit,
            fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER,
            text_color=COLOR_BG, width=200, height=40, font=FONT_BODY_BOLD,
            corner_radius=RADIUS_MD)
        self._submit_btn.pack(side="right")
        ctk.CTkButton(
            btn_row, text="Batal", command=self._on_cancel,
            fg_color="transparent", hover_color=COLOR_SURFACE_HIGH,
            border_width=1, border_color=COLOR_INFO, text_color=COLOR_INFO,
            width=120, height=40, font=FONT_BODY_BOLD, corner_radius=RADIUS_MD,
        ).pack(side="right", padx=(0, SPACE_MD))
        self._preview = ctk.CTkLabel(
            btn_row, text="0 tanggal dipilih", font=FONT_SMALL,
            text_color=COLOR_TEXT_DIM)
        self._preview.pack(side="left")

    def _on_employee_change(self, _label):
        for w in self._dates_scroll.winfo_children():
            w.destroy()
        self._date_vars = {}
        group = self._by_label.get(self._emp_var.get())
        if not group:
            return
        for iss in group["issues"]:
            var = ctk.BooleanVar(value=True)   # default all checked
            self._date_vars[iss["attendance_id"]] = var
            row = ctk.CTkFrame(self._dates_scroll, fg_color=COLOR_SURFACE_HIGH,
                               corner_radius=RADIUS_MD)
            row.pack(fill="x", pady=2, padx=2)
            ctk.CTkCheckBox(
                row, text="", width=24, variable=var,
                command=self._update_preview,
                fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER,
            ).pack(side="left", padx=(SPACE_SM, SPACE_XS), pady=SPACE_XS)
            info = (f"{_format_tanggal(iss['tanggal'], iss['hari'])}    "
                    f"masuk {iss['masuk'] or '—'} · keluar {iss['keluar'] or '—'}")
            ctk.CTkLabel(row, text=info, font=FONT_SMALL, text_color=COLOR_TEXT,
                         anchor="w").pack(side="left", fill="x", expand=True,
                                          pady=SPACE_XS)
        self._update_preview()

    def _on_cat_change(self, _label):
        key = self._label_to_key.get(self._cat_var.get(), "")
        self._detail_label.pack_forget()
        self._detail_entry.pack_forget()
        if key in REASON_NEEDS_DETAIL:
            self._detail_label.pack(anchor="w", padx=SPACE_XL)
            self._detail_entry.pack(anchor="w", padx=SPACE_XL, pady=(SPACE_XS, 0))

    def _checked_ids(self) -> list:
        return [aid for aid, var in self._date_vars.items() if var.get()]

    def _update_preview(self):
        n = len(self._checked_ids())
        self._preview.configure(text=f"{n} tanggal dipilih")
        self._submit_btn.configure(text=f"Resolve {n} Issue" if n else "Resolve")

    def _on_submit(self):
        ids = self._checked_ids()
        if not ids:
            messagebox.showwarning("Pilih tanggal",
                                   "Belum ada tanggal yang dipilih.")
            return
        cat = self._label_to_key.get(self._cat_var.get(), "")
        if cat not in REASON_LABELS:
            messagebox.showwarning("Pilih kategori",
                                   "Belum memilih kategori alasan.")
            return
        detail = (self._detail_entry.get().strip()
                  if cat in REASON_NEEDS_DETAIL else None) or None
        with get_connection(DB_PATH) as conn:
            apply_batch_resolve(conn, ids, cat, detail)
        try:
            self.grab_release()
        except Exception:
            pass
        self.destroy()
        self._on_done()

    def _on_cancel(self):
        try:
            self.grab_release()
        except Exception:
            pass
        self.destroy()
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `../../../.venv/Scripts/python.exe -m pytest tests/test_batch_resolve_dialog.py -v`
Expected: PASS — all four tests. If a UI test errors on the `after(50, ...)` callback firing post-destroy, change `tk_root.update_idletasks()` to `tk_root.update()` in that test — but try as-written first.

- [ ] **Step 5: Commit**

```bash
git add src/ui/components/batch_resolve_dialog.py tests/test_batch_resolve_dialog.py
git commit -m "feat(ui): Batch Resolve dialog component"
```

---

## Task 8: Wire "+ Resolve Massal" into the Issues screen

**Files:**
- Modify: `src/ui/screens/issues.py`
- Test: `tests/test_issues_screen.py` (create)

- [ ] **Step 1: Write the failing test**

Create `tests/test_issues_screen.py`:

```python
"""Smoke test for the Issues screen — constructs + Batch Resolve wired."""
from src.db.schema import init_db
from src.db.connection import get_connection
from src.db.employees import upsert_employee
from src.db.attendance import upsert_attendance
from src.db.settings import set_setting


def test_issues_screen_constructs_with_batch_resolve(temp_db_path, monkeypatch, tk_root):
    import src.ui.screens.issues as issues_mod
    monkeypatch.setattr(issues_mod, "DB_PATH", temp_db_path)
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        a = upsert_employee(conn, no_staff="1", nama="ANDI", dept="X")
        upsert_attendance(
            conn, employee_id=a, tanggal="2026-04-01", hari="Senin",
            tipe="Hari Kerja", jadwal="08.00 - 16.00",
            masuk=None, keluar="16:00", kerja_jam=None,
            lembur_jam=None, terlambat_menit=None,
            has_issue=1, imported_from="W1.xls",
        )
        set_setting(conn, "current_month", "2026-04")
        conn.commit()
    screen = issues_mod.IssuesScreen(tk_root)
    tk_root.update_idletasks()
    assert screen is not None
    assert hasattr(screen, "_on_batch_resolve")
    screen.destroy()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `../../../.venv/Scripts/python.exe -m pytest tests/test_issues_screen.py -v`
Expected: FAIL — `AssertionError` on `hasattr(screen, "_on_batch_resolve")`.

- [ ] **Step 3: Add the header button in `_build_header`**

In `src/ui/screens/issues.py`, `_build_header` currently ends with `self.nav.pack(side="left")`. Add the button right after that line:

```python
        self.nav.pack(side="left")
        ctk.CTkButton(
            header, text="+ Resolve Massal", command=self._on_batch_resolve,
            fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER,
            text_color=COLOR_BG, font=FONT_BODY_BOLD, width=160,
        ).pack(side="right")
```

(`COLOR_ACCENT`, `COLOR_ACCENT_HOVER`, `COLOR_BG`, `FONT_BODY_BOLD` are already imported in this file.)

- [ ] **Step 4: Add the `_on_batch_resolve` handler**

Add this method to `IssuesScreen`, immediately after `_on_period_change`:

```python
    def _on_batch_resolve(self):
        from src.ui.components.batch_resolve_dialog import BatchResolveDialog
        start, end = self._active_range()
        BatchResolveDialog(
            self.winfo_toplevel(),
            period_start=start, period_end=end,
            on_done=self._reload,
        )
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `../../../.venv/Scripts/python.exe -m pytest tests/test_issues_screen.py -v`
Expected: PASS.

- [ ] **Step 6: Run the full suite**

Run: `../../../.venv/Scripts/python.exe -m pytest -q`
Expected: PASS — 194 baseline + new tests (~30+), no regressions.

- [ ] **Step 7: Commit**

```bash
git add src/ui/screens/issues.py tests/test_issues_screen.py
git commit -m "feat(ui): wire + Resolve Massal button into Issues screen"
```

---

## Manual Smoke Test (after all tasks)

Cannot be automated — needs a human at the desktop app:

1. **New category:** Issues screen → resolve an open issue → "Tugas Belajar/Kuliah" appears in the category combo → resolve → it moves to RESOLVED, shows "Tugas Belajar/Kuliah". Generate the monthly report → that row has `Ijin = 1`.
2. **Batch Resolve:** Issues screen → "+ Resolve Massal" (top-right) → pick an employee with several open issues → dates default all-checked → pick "Tugas Lapangan" + a detail → "Resolve N Issue" → all those dates move to RESOLVED.
3. **Lateness logic:** resolve a late row as "Tugas Lapangan" → Generate monthly report → that row shows Masuk `08:00`, Terlambat `0`. Resolve a forgot-clock-in row (has keluar, no masuk) as "Lupa Absen" → report shows Masuk `08:15`, Terlambat `15`, not counted as Lupa.
4. **Setting:** Settings → General → change "Penalti Lupa Absen Datang" to `20` → Save → re-generate → forgot-in rows now show `08:20` / `20`.

---

## Self-Review

**Spec coverage** (against `2026-05-15-issue-resolution-design.md`):
- §3–4 new category "Tugas Belajar/Kuliah" → Task 1. ✓
- §9 `effective_attendance` helper + format normalization → Task 2. ✓
- §10.3 penalty setting (`DEFAULT_LUPA_PENALTY_MIN`, `read_lupa_penalty_min`) → Task 3; Settings UI row → Task 6. ✓
- §10.1 report_generator effective row → Task 4. ✓
- §10.2 weekly_export effective values + `reason_category` in SELECT → Task 5. ✓
- §5–6 Batch Resolve dialog (`group_open_issues_by_employee`, `apply_batch_resolve`, `BatchResolveDialog`) → Task 7; Issues screen wiring → Task 8. ✓
- §11 insights/coaching unchanged → no task needed (verified: nothing touches `src/core/insights.py` or coaching). ✓
- §13 edge cases → covered by tests: no-badge work-justified (Task 4), forgot-OUT untouched (Task 2), other categories untouched (Task 2), malformed penalty (Task 3), no-issues dialog state (Task 7). ✓

**Placeholder scan:** No TBD/TODO; every code step has complete code. ✓

**Type consistency:** `effective_attendance` returns `{"masuk", "terlambat_menit"}` — consumed identically in Tasks 4 & 5. `group_open_issues_by_employee` dict shape (`employee_id, nama, dept, no_staff, issues`) — consumed by `BatchResolveDialog._build`/`_on_employee_change`. `apply_batch_resolve(conn, ids, category, detail)` signature — consistent in Task 7's test and `_on_submit`. `read_lupa_penalty_min(conn)` — consistent in Tasks 3, 4, 5. ✓

**Task ordering:** Task 3 (setting infra) precedes Tasks 4 & 5 (consumers that call `read_lupa_penalty_min`). Task 2 (`effective_attendance`) precedes Tasks 4 & 5. Task 7 (dialog) precedes Task 8 (wiring). ✓
