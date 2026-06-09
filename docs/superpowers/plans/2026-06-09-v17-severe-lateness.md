# Severe Lateness Menu — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a "Severe Lateness" sidebar menu that surfaces work days where the employee clocked in AND out but was late ≥ a configurable threshold (default 60 min), with the same reason-resolution workflow as Issues.

**Architecture:** A structural clone of the Issues menu with a different detector query. Reuses the existing `reason_category` / `reason_detail` / `resolved_at` columns — **no schema change**. Resolution automatically flows into Coaching (via `COACHING_EXCLUDED`) and the monthly-report export (via the shared reason plumbing).

**Tech Stack:** Python 3.x, customtkinter (UI), SQLite, pytest. Spec: `docs/superpowers/specs/2026-06-09-v17-severe-lateness-design.md`.

**Baseline:** 296 tests passing on `v16` (`cfeb789`). Every task ends green.

---

## Reference signatures (verified against codebase — do not guess)

- `set_reason(conn, *, attendance_id, category, detail)` — keyword-only after `conn`.
- `unresolve_issue(conn, attendance_id)`.
- `upsert_employee(conn, no_staff="1", nama="ANDI", dept="X") -> int`.
- `upsert_attendance(conn, employee_id, tanggal, hari, tipe, jadwal, masuk, keluar, kerja_jam, lembur_jam, terlambat_menit, has_issue, imported_from)`.
- `get_setting(conn, key, default=...)`, `set_setting(conn, key, value)`.
- `REASON_NEEDS_DETAIL = {"tugas_lapangan","tugas_paparan","terlambat_kerja","terlambat_lain"}`.
- `insights.resolution_rate(conn, start, end)` is **has_issue=1 scoped** — DO NOT reuse for this menu.
- Test fixtures available: `temp_db_path`, `tk_root`, `monkeypatch`.
- Run the suite from worktree root: `../../../.venv/Scripts/python.exe -m pytest -q`.

---

### Task 0: Confirm green baseline

**Files:** none.

- [ ] **Step 1: Run the full suite**

Run: `../../../.venv/Scripts/python.exe -m pytest -q`
Expected: all pass (~296). If anything fails, STOP and report before proceeding.

---

### Task 1: Severe-lateness detector (pure predicate)

**Files:**
- Create: `src/core/severe_lateness_detector.py`
- Test: `tests/test_severe_lateness_detector.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_severe_lateness_detector.py
from src.core.severe_lateness_detector import is_severe_lateness


def _row(tipe="Hari Kerja", masuk="09:15", keluar="16:30", terlambat=75):
    return {"tipe": tipe, "masuk": masuk, "keluar": keluar, "terlambat_menit": terlambat}


def test_is_severe_at_boundary():
    assert is_severe_lateness(_row(terlambat=60), 60) is True
    assert is_severe_lateness(_row(terlambat=59), 60) is False


def test_is_severe_requires_both_punches():
    assert is_severe_lateness(_row(masuk=None), 60) is False
    assert is_severe_lateness(_row(keluar=None), 60) is False


def test_is_severe_hari_kerja_only():
    assert is_severe_lateness(_row(tipe="Hari Libur"), 60) is False


def test_is_severe_null_terlambat_not_severe():
    assert is_severe_lateness(_row(terlambat=None), 60) is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `../../../.venv/Scripts/python.exe -m pytest tests/test_severe_lateness_detector.py -q`
Expected: FAIL (ModuleNotFoundError: No module named 'src.core.severe_lateness_detector').

- [ ] **Step 3: Write minimal implementation**

```python
# src/core/severe_lateness_detector.py
"""Pure predicate: is a single attendance row a 'severe lateness' day?

A severe-lateness day is a Hari Kerja where BOTH punches are present and the
recorded lateness meets/exceeds the threshold. Distinct from an Issue (which
requires a MISSING punch), so the two sets never overlap.
"""


def is_severe_lateness(row, threshold_min: int) -> bool:
    """row supports row["tipe"], row["masuk"], row["keluar"],
    row["terlambat_menit"] (dict or sqlite3.Row)."""
    if row["tipe"] != "Hari Kerja":
        return False
    if not row["masuk"] or not row["keluar"]:
        return False
    late = row["terlambat_menit"] or 0
    return late >= threshold_min
```

- [ ] **Step 4: Run test to verify it passes**

Run: `../../../.venv/Scripts/python.exe -m pytest tests/test_severe_lateness_detector.py -q`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add src/core/severe_lateness_detector.py tests/test_severe_lateness_detector.py
git commit -m "feat(v17): severe-lateness detector predicate"
```

---

### Task 2: Config constants

**Files:**
- Modify: `src/config.py` (near `DEFAULT_LUPA_PENALTY_MIN` and `REASON_CATEGORIES`)
- Test: `tests/test_config_severe_lateness.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_config_severe_lateness.py
from src import config


def test_default_threshold_is_60():
    assert config.DEFAULT_SEVERE_LATENESS_THRESHOLD_MIN == 60


def test_severe_lateness_categories_subset():
    expected = ("tugas_lapangan", "tugas_paparan", "terlambat_kerja",
                "terlambat_lain", "izin_sakit", "cuti", "na")
    assert config.SEVERE_LATENESS_CATEGORIES == expected
    # every entry must be a valid global reason category
    for c in config.SEVERE_LATENESS_CATEGORIES:
        assert c in config.REASON_CATEGORIES
    # lupa/libur explicitly excluded
    for c in ("lupa_absen_datang", "lupa_absen_pulang", "libur"):
        assert c not in config.SEVERE_LATENESS_CATEGORIES
```

- [ ] **Step 2: Run test to verify it fails**

Run: `../../../.venv/Scripts/python.exe -m pytest tests/test_config_severe_lateness.py -q`
Expected: FAIL (AttributeError: module 'src.config' has no attribute 'DEFAULT_SEVERE_LATENESS_THRESHOLD_MIN').

- [ ] **Step 3: Write minimal implementation**

In `src/config.py`, add next to `DEFAULT_LUPA_PENALTY_MIN`:

```python
DEFAULT_SEVERE_LATENESS_THRESHOLD_MIN = 60
```

And after the `REASON_CATEGORIES` tuple, add:

```python
# Reason categories shown in the Severe Lateness resolve panel — a subset of
# REASON_CATEGORIES relevant when BOTH punches are present (so lupa_absen_* and
# libur are excluded). terlambat_kerja is in COACHING_EXCLUDED (justified late →
# dropped from coaching); terlambat_lain is not (stays counted, just annotated).
SEVERE_LATENESS_CATEGORIES = (
    "tugas_lapangan",
    "tugas_paparan",
    "terlambat_kerja",
    "terlambat_lain",
    "izin_sakit",
    "cuti",
    "na",
)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `../../../.venv/Scripts/python.exe -m pytest tests/test_config_severe_lateness.py -q`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add src/config.py tests/test_config_severe_lateness.py
git commit -m "feat(v17): severe-lateness config constants"
```

---

### Task 3: Default setting in schema

**Files:**
- Modify: `src/db/schema.py` (`DEFAULT_SETTINGS` dict)
- Test: `tests/test_schema_severe_lateness_setting.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_schema_severe_lateness_setting.py
from src.db.schema import init_db
from src.db.connection import get_connection
from src.db.settings import get_setting


def test_severe_lateness_default_seeded(temp_db_path):
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        assert get_setting(conn, "severe_lateness_threshold_min") == "60"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `../../../.venv/Scripts/python.exe -m pytest tests/test_schema_severe_lateness_setting.py -q`
Expected: FAIL (assert None == "60").

- [ ] **Step 3: Write minimal implementation**

In `src/db/schema.py`, add to the `DEFAULT_SETTINGS` dict:

```python
    "severe_lateness_threshold_min": "60",
```

(The existing `init_db` loop inserts every `DEFAULT_SETTINGS` key with
`INSERT ... ON CONFLICT(key) DO NOTHING`, so existing DBs pick up the default on
next startup. No `_migrate()` entry needed — brand-new key.)

- [ ] **Step 4: Run test to verify it passes**

Run: `../../../.venv/Scripts/python.exe -m pytest tests/test_schema_severe_lateness_setting.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/db/schema.py tests/test_schema_severe_lateness_setting.py
git commit -m "feat(v17): seed severe_lateness_threshold_min default setting"
```

---

### Task 4: Settings read helper

**Files:**
- Modify: `src/db/settings.py`
- Test: `tests/test_settings_read_severe_lateness.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_settings_read_severe_lateness.py
from src.db.schema import init_db
from src.db.connection import get_connection
from src.db.settings import set_setting, read_severe_lateness_threshold


def test_reads_int_value(temp_db_path):
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        set_setting(conn, "severe_lateness_threshold_min", "90")
        assert read_severe_lateness_threshold(conn) == 90


def test_fallback_on_invalid(temp_db_path):
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        set_setting(conn, "severe_lateness_threshold_min", "not-a-number")
        assert read_severe_lateness_threshold(conn) == 60


def test_fallback_on_missing(temp_db_path):
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        conn.execute("DELETE FROM settings WHERE key='severe_lateness_threshold_min'")
        assert read_severe_lateness_threshold(conn) == 60
```

- [ ] **Step 2: Run test to verify it fails**

Run: `../../../.venv/Scripts/python.exe -m pytest tests/test_settings_read_severe_lateness.py -q`
Expected: FAIL (ImportError: cannot import name 'read_severe_lateness_threshold').

- [ ] **Step 3: Write minimal implementation**

In `src/db/settings.py`, add the import near the top (with the other config imports):

```python
from src.config import DEFAULT_SEVERE_LATENESS_THRESHOLD_MIN
```

and the helper (mirror `read_lupa_penalty_min`):

```python
def read_severe_lateness_threshold(conn) -> int:
    """Read severe_lateness_threshold_min as int; fall back to the default on
    missing or non-integer values."""
    raw = get_setting(conn, "severe_lateness_threshold_min",
                      default=str(DEFAULT_SEVERE_LATENESS_THRESHOLD_MIN))
    try:
        return int(raw)
    except (TypeError, ValueError):
        return DEFAULT_SEVERE_LATENESS_THRESHOLD_MIN
```

- [ ] **Step 4: Run test to verify it passes**

Run: `../../../.venv/Scripts/python.exe -m pytest tests/test_settings_read_severe_lateness.py -q`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add src/db/settings.py tests/test_settings_read_severe_lateness.py
git commit -m "feat(v17): read_severe_lateness_threshold helper"
```

---

### Task 5: DB query layer

**Files:**
- Modify: `src/db/attendance.py`
- Test: `tests/test_attendance_severe_lateness.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_attendance_severe_lateness.py
from src.db.schema import init_db
from src.db.connection import get_connection
from src.db.employees import upsert_employee
from src.db.attendance import (
    upsert_attendance, set_reason,
    list_severe_lateness_for_period, count_severe_lateness_for_period,
)

START, END = "2026-05-01", "2026-05-31"


def _seed(conn):
    a = upsert_employee(conn, no_staff="1", nama="BUDI", dept="IT")
    b = upsert_employee(conn, no_staff="2", nama="ANI", dept="HR")
    # BUDI: 75 min late, both punches -> severe
    upsert_attendance(conn, employee_id=a, tanggal="2026-05-04", hari="Senin",
                      tipe="Hari Kerja", jadwal="08.00 - 16.00",
                      masuk="09:15", keluar="16:30", kerja_jam=None,
                      lembur_jam=None, terlambat_menit=75, has_issue=0,
                      imported_from="W1.xls")
    # ANI: 30 min late -> below threshold 60
    upsert_attendance(conn, employee_id=b, tanggal="2026-05-05", hari="Selasa",
                      tipe="Hari Kerja", jadwal="08.00 - 16.00",
                      masuk="08:30", keluar="16:05", kerja_jam=None,
                      lembur_jam=None, terlambat_menit=30, has_issue=0,
                      imported_from="W1.xls")
    # BUDI: 120 min late but MISSING keluar -> this is an Issue, not severe-late
    upsert_attendance(conn, employee_id=a, tanggal="2026-05-06", hari="Rabu",
                      tipe="Hari Kerja", jadwal="08.00 - 16.00",
                      masuk="10:00", keluar=None, kerja_jam=None,
                      lembur_jam=None, terlambat_menit=120, has_issue=1,
                      imported_from="W1.xls")
    return a, b


def test_list_filters_by_threshold(temp_db_path):
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        _seed(conn)
        rows = list_severe_lateness_for_period(conn, START, END, 60)
        names = [r["nama"] for r in rows]
        assert names == ["BUDI"]  # only the 75-min, both-punches row


def test_list_excludes_missing_punch_rows(temp_db_path):
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        _seed(conn)
        rows = list_severe_lateness_for_period(conn, START, END, 60)
        for r in rows:
            assert r["masuk"] and r["keluar"]


def test_list_open_vs_resolved_split(temp_db_path):
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        a, _ = _seed(conn)
        # resolve BUDI's severe row
        row = list_severe_lateness_for_period(conn, START, END, 60)[0]
        set_reason(conn, attendance_id=row["id"], category="terlambat_lain",
                   detail="macet")
        assert list_severe_lateness_for_period(conn, START, END, 60, resolved=False) == []
        resolved = list_severe_lateness_for_period(conn, START, END, 60, resolved=True)
        assert len(resolved) == 1


def test_count_open_resolved_na_total(temp_db_path):
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        _seed(conn)
        c = count_severe_lateness_for_period(conn, START, END, 60)
        assert c == {"open": 1, "resolved": 0, "na": 0, "total": 1}
        row = list_severe_lateness_for_period(conn, START, END, 60)[0]
        set_reason(conn, attendance_id=row["id"], category="na", detail=None)
        c2 = count_severe_lateness_for_period(conn, START, END, 60)
        assert c2 == {"open": 0, "resolved": 0, "na": 1, "total": 1}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `../../../.venv/Scripts/python.exe -m pytest tests/test_attendance_severe_lateness.py -q`
Expected: FAIL (ImportError on list_severe_lateness_for_period).

- [ ] **Step 3: Write minimal implementation**

In `src/db/attendance.py`, add:

```python
def list_severe_lateness_for_period(conn, start, end, threshold_min, resolved=None):
    """Hari Kerja rows with both punches present and terlambat_menit >=
    threshold_min, in [start, end]. resolved=False -> reason_category IS NULL;
    True -> IS NOT NULL; None -> both. Joined with employees, sorted by name/date."""
    sql = """
        SELECT ar.*, e.nama, e.dept, e.no_staff
          FROM attendance_records ar
          JOIN employees e ON ar.employee_id = e.id
         WHERE ar.tipe = 'Hari Kerja'
           AND ar.masuk IS NOT NULL
           AND ar.keluar IS NOT NULL
           AND ar.terlambat_menit >= ?
           AND ar.tanggal BETWEEN ? AND ?
    """
    params = [threshold_min, start, end]
    if resolved is True:
        sql += " AND ar.reason_category IS NOT NULL"
    elif resolved is False:
        sql += " AND ar.reason_category IS NULL"
    sql += " ORDER BY e.nama ASC, ar.tanggal ASC"
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def count_severe_lateness_for_period(conn, start, end, threshold_min):
    """Returns {open, resolved, na, total} over the threshold-filtered set.
    resolved = reason set AND != 'na'; na = reason == 'na'; open = reason NULL."""
    row = conn.execute(
        """
        SELECT
          SUM(CASE WHEN reason_category IS NULL THEN 1 ELSE 0 END) AS open,
          SUM(CASE WHEN reason_category IS NOT NULL AND reason_category != 'na'
                   THEN 1 ELSE 0 END) AS resolved,
          SUM(CASE WHEN reason_category = 'na' THEN 1 ELSE 0 END) AS na,
          COUNT(*) AS total
          FROM attendance_records
         WHERE tipe = 'Hari Kerja'
           AND masuk IS NOT NULL AND keluar IS NOT NULL
           AND terlambat_menit >= ?
           AND tanggal BETWEEN ? AND ?
        """,
        (threshold_min, start, end),
    ).fetchone()
    return {
        "open": row["open"] or 0,
        "resolved": row["resolved"] or 0,
        "na": row["na"] or 0,
        "total": row["total"] or 0,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `../../../.venv/Scripts/python.exe -m pytest tests/test_attendance_severe_lateness.py -q`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add src/db/attendance.py tests/test_attendance_severe_lateness.py
git commit -m "feat(v17): list_/count_severe_lateness_for_period queries"
```

---

### Task 6: Settings UI row + validation

**Files:**
- Modify: `src/ui/screens/settings.py` (`_build_general`, `_save`)
- Test: `tests/test_settings_screen_severe_lateness.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_settings_screen_severe_lateness.py
import src.ui.screens.settings as mod
from src.db.schema import init_db
from src.db.connection import get_connection
from src.db.settings import get_setting


def test_settings_saves_severe_threshold(temp_db_path, monkeypatch, tk_root):
    monkeypatch.setattr(mod, "DB_PATH", temp_db_path)
    init_db(temp_db_path)
    screen = mod.SettingsScreen(tk_root)
    tk_root.update_idletasks()
    assert hasattr(screen, "severe_var"), "severe_var entry must exist"
    screen.severe_var.set("90")
    screen._save()
    tk_root.update_idletasks()
    with get_connection(temp_db_path) as conn:
        assert get_setting(conn, "severe_lateness_threshold_min") == "90"
    screen.destroy()


def test_settings_rejects_out_of_range(temp_db_path, monkeypatch, tk_root):
    monkeypatch.setattr(mod, "DB_PATH", temp_db_path)
    # silence the modal warning during the test
    monkeypatch.setattr(mod.messagebox, "showwarning", lambda *a, **k: None)
    init_db(temp_db_path)
    screen = mod.SettingsScreen(tk_root)
    tk_root.update_idletasks()
    screen.severe_var.set("0")   # below min 1 -> rejected, nothing saved
    screen._save()
    with get_connection(temp_db_path) as conn:
        assert get_setting(conn, "severe_lateness_threshold_min") == "60"
    screen.destroy()
```

(If the SettingsScreen class name differs, match the real one — confirm in `src/ui/screens/settings.py`.)

- [ ] **Step 2: Run test to verify it fails**

Run: `../../../.venv/Scripts/python.exe -m pytest tests/test_settings_screen_severe_lateness.py -q`
Expected: FAIL (no attribute `severe_var`).

- [ ] **Step 3: Write minimal implementation**

In `_build_general`, after reading the other settings, also read the severe threshold:

```python
            severe = get_setting(conn, "severe_lateness_threshold_min", default="60")
```

After the `row4` (Penalti Lupa Absen) block, add a new row mirroring it:

```python
        row5 = ctk.CTkFrame(
            parent, fg_color=COLOR_SURFACE,
            border_width=1, border_color=COLOR_BORDER,
            corner_radius=RADIUS_MD,
        )
        row5.pack(fill="x", pady=SPACE_SM)
        ctk.CTkLabel(
            row5, text="Severe Lateness Threshold (menit):",
            font=FONT_BODY, text_color=COLOR_TEXT,
        ).pack(side="left", padx=SPACE_MD, pady=SPACE_SM + 2)
        self.severe_var = ctk.StringVar(value=severe)
        ctk.CTkEntry(
            row5, textvariable=self.severe_var, width=80,
            fg_color=COLOR_SURFACE_HIGH,
            border_width=1, border_color=COLOR_BORDER,
            text_color=COLOR_TEXT,
            font=FONT_BODY,
            placeholder_text_color=COLOR_TEXT_MUTED,
        ).pack(side="left")
```

In `_save`, AFTER the existing lupa-penalty validation block (which already
`return`s on failure) and BEFORE the `with get_connection(...)` block, add a
second validation that also returns on failure:

```python
        # Validate Severe Lateness threshold: integer in [1, 999]
        raw_sev = self.severe_var.get().strip()
        try:
            severe = int(raw_sev)
        except ValueError:
            messagebox.showwarning(
                "Threshold tidak valid",
                f"'{raw_sev}' bukan angka. Threshold harus bilangan bulat "
                f"antara 1 dan 999.")
            return
        if severe < 1 or severe > 999:
            messagebox.showwarning(
                "Threshold di luar rentang",
                f"{severe} di luar rentang. Threshold harus antara 1 dan 999 menit.")
            return
```

Then inside the existing `with get_connection(...)` block, add the save:

```python
            set_setting(conn, "severe_lateness_threshold_min", str(severe))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `../../../.venv/Scripts/python.exe -m pytest tests/test_settings_screen_severe_lateness.py -q`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add src/ui/screens/settings.py tests/test_settings_screen_severe_lateness.py
git commit -m "feat(v17): Severe Lateness threshold setting UI + validation"
```

---

### Task 7: Export fill path picks up resolved severe-lateness rows

**Files:**
- Modify: `src/core/report_filler.py` (the `has_issue` gate, ~lines 79-89)
- Test: `tests/test_report_filler_severe_lateness.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_report_filler_severe_lateness.py
from pathlib import Path
from openpyxl import Workbook
from src.db.schema import init_db
from src.db.connection import get_connection
from src.db.employees import upsert_employee
from src.db.attendance import upsert_attendance, set_reason
from src.core.report_filler import fill_monthly_report, ALASAN_IJIN_COL


def _make_template(tmp_path, nama, tanggal_str):
    wb = Workbook()
    ws = wb.active
    # rows 1-2 are headers; data starts row 3. Col 1 = nama, col 3 = tanggal.
    ws.cell(row=3, column=1, value=nama)
    ws.cell(row=3, column=3, value=tanggal_str)
    p = tmp_path / "tpl.xlsx"
    wb.save(p)
    return p


def test_resolved_severe_lateness_writes_alasan(tmp_path, temp_db_path):
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        a = upsert_employee(conn, no_staff="1", nama="BUDI", dept="IT")
        upsert_attendance(conn, employee_id=a, tanggal="2026-05-04", hari="Senin",
                          tipe="Hari Kerja", jadwal="08.00 - 16.00",
                          masuk="09:15", keluar="16:30", kerja_jam=None,
                          lembur_jam=None, terlambat_menit=75, has_issue=0,
                          imported_from="W1.xls")
        rid = conn.execute("SELECT id FROM attendance_records").fetchone()["id"]
        set_reason(conn, attendance_id=rid, category="terlambat_lain", detail="macet")
        tpl = _make_template(tmp_path, "BUDI", "04/05/2026")
        out, summary = fill_monthly_report(tpl, conn, out_dir=tmp_path)
    from openpyxl import load_workbook
    ws = load_workbook(out).active
    val = ws.cell(row=3, column=ALASAN_IJIN_COL).value
    assert val and "Terlambat" in val
    assert summary.filled_count == 1


def test_unresolved_issue_still_writes_na(tmp_path, temp_db_path):
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        a = upsert_employee(conn, no_staff="1", nama="ANI", dept="HR")
        upsert_attendance(conn, employee_id=a, tanggal="2026-05-05", hari="Selasa",
                          tipe="Hari Kerja", jadwal="08.00 - 16.00",
                          masuk=None, keluar="16:00", kerja_jam=None,
                          lembur_jam=None, terlambat_menit=None, has_issue=1,
                          imported_from="W1.xls")
        tpl = _make_template(tmp_path, "ANI", "05/05/2026")
        out, summary = fill_monthly_report(tpl, conn, out_dir=tmp_path)
    from openpyxl import load_workbook
    ws = load_workbook(out).active
    assert ws.cell(row=3, column=ALASAN_IJIN_COL).value == "NA / Belum ada kabar"
    assert summary.na_count == 1


def test_unresolved_non_issue_row_skipped(tmp_path, temp_db_path):
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        a = upsert_employee(conn, no_staff="1", nama="CITRA", dept="Fin")
        upsert_attendance(conn, employee_id=a, tanggal="2026-05-06", hari="Rabu",
                          tipe="Hari Kerja", jadwal="08.00 - 16.00",
                          masuk="09:10", keluar="17:00", kerja_jam=None,
                          lembur_jam=None, terlambat_menit=70, has_issue=0,
                          imported_from="W1.xls")
        tpl = _make_template(tmp_path, "CITRA", "06/05/2026")
        out, summary = fill_monthly_report(tpl, conn, out_dir=tmp_path)
    from openpyxl import load_workbook
    ws = load_workbook(out).active
    assert ws.cell(row=3, column=ALASAN_IJIN_COL).value in (None, "")
    assert summary.filled_count == 0 and summary.na_count == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `../../../.venv/Scripts/python.exe -m pytest tests/test_report_filler_severe_lateness.py -q`
Expected: FAIL — `test_resolved_severe_lateness_writes_alasan` fails (the current `has_issue != 1` gate skips the row, so Alasan is empty / filled_count 0).

- [ ] **Step 3: Write minimal implementation**

In `src/core/report_filler.py`, replace the gate + write block (currently):

```python
        if row["tipe"] == "Hari Libur":
            continue  # holiday row — skip; do not write Alasan Ijin
        if row["has_issue"] != 1:
            continue  # skip non-issue rows entirely

        if row["reason_category"]:
            text = render_alasan_ijin(row["reason_category"], row["reason_detail"])
            summary.filled_count += 1
        else:
            text = "NA / Belum ada kabar"
            summary.na_count += 1
```

with the reason→elif-has_issue→else ladder (mirrors `report_generator`):

```python
        if row["tipe"] == "Hari Libur":
            continue  # holiday row — skip; do not write Alasan Ijin

        if row["reason_category"]:
            text = render_alasan_ijin(row["reason_category"], row["reason_detail"])
            summary.filled_count += 1
        elif row["has_issue"] == 1:
            text = "NA / Belum ada kabar"
            summary.na_count += 1
        else:
            continue  # non-issue, unresolved → no Alasan
```

- [ ] **Step 4: Run test to verify it passes**

Run: `../../../.venv/Scripts/python.exe -m pytest tests/test_report_filler_severe_lateness.py -q`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add src/core/report_filler.py tests/test_report_filler_severe_lateness.py
git commit -m "feat(v17): fill export writes Alasan for any resolved row (keeps NA)"
```

---

### Task 8: Generalize batch resolve dialog with a lister callable

**Files:**
- Modify: `src/ui/components/batch_resolve_dialog.py` (`__init__` + the hardcoded `list_issues_for_period` call)
- Modify: `src/ui/screens/issues.py` (pass the explicit Issues lister — optional if default covers it)
- Test: `tests/test_batch_resolve_lister.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_batch_resolve_lister.py
import inspect
from src.ui.components.batch_resolve_dialog import BatchResolveDialog


def test_init_accepts_lister_fn():
    sig = inspect.signature(BatchResolveDialog.__init__)
    assert "lister_fn" in sig.parameters, "BatchResolveDialog must accept lister_fn"
    assert sig.parameters["lister_fn"].default is None
```

(Confirm the real class name `BatchResolveDialog` in the module; match it.)

- [ ] **Step 2: Run test to verify it fails**

Run: `../../../.venv/Scripts/python.exe -m pytest tests/test_batch_resolve_lister.py -q`
Expected: FAIL (lister_fn not in parameters).

- [ ] **Step 3: Write minimal implementation**

In `batch_resolve_dialog.py`:
- Add `lister_fn=None` to `__init__`'s signature.
- Store it: `self._lister_fn = lister_fn or (lambda c, s, e: list_issues_for_period(c, s, e, resolved=False))`.
- Replace the hardcoded `list_issues_for_period(conn, period_start, period_end, resolved=False)` call with `self._lister_fn(conn, period_start, period_end)`.

(Keep the `from src.db.attendance import list_issues_for_period` import for the
default lambda.)

- [ ] **Step 4: Run test to verify it passes**

Run: `../../../.venv/Scripts/python.exe -m pytest tests/test_batch_resolve_lister.py -q`
Expected: PASS.

- [ ] **Step 5: Run the full suite (guard the Issues batch flow)**

Run: `../../../.venv/Scripts/python.exe -m pytest -q`
Expected: still green — the default lister keeps Issues behavior identical.

- [ ] **Step 6: Commit**

```bash
git add src/ui/components/batch_resolve_dialog.py tests/test_batch_resolve_lister.py
git commit -m "feat(v17): batch resolve dialog accepts injected lister_fn"
```

---

### Task 9: Severe Lateness screen (clone of Issues + Telat column)

**Files:**
- Create: `src/ui/screens/severe_lateness.py`
- Test: `tests/test_severe_lateness_screen.py`

**Approach:** Copy `src/ui/screens/issues.py` verbatim into
`severe_lateness.py`, then apply these precise deltas. Do NOT rewrite from
scratch — preserve all the v16 search / Ctrl+F / click-outside / Enter-submit /
period-state machinery exactly.

Deltas to apply after copying:
1. Rename the class `IssuesScreen` → `SevereLatenessScreen`.
2. Imports: add `from src.db.attendance import list_severe_lateness_for_period, count_severe_lateness_for_period`; add `from src.db.settings import read_severe_lateness_threshold`; add `from src.config import SEVERE_LATENESS_CATEGORIES`. Keep `set_reason`, `unresolve_issue`.
3. In `__init__`, read the threshold once: `self._threshold = read_severe_lateness_threshold(conn)` (inside the existing settings-read connection block).
4. Title label text → `"Severe Lateness"`.
5. The reason combobox values → built from `SEVERE_LATENESS_CATEGORIES` (mapped through `REASON_LABELS`) instead of the full `REASON_CATEGORIES`.
6. `_make_tree` column list: insert `"terlambat"` after `"keluar"`:
   - `cols = ["nama", "dept", "tanggal", "hari", "masuk", "keluar", "terlambat"]`
   - when `show_reason`: append `"alasan"` AFTER `terlambat`.
   - widths: add `"terlambat": 80`. labels: add `"terlambat": "Telat (mnt)"`.
7. Row rendering (`_render_rows` / wherever `values=(...)` is built): insert
   `row["terlambat_menit"]` in the matching position (after `keluar`, before
   `alasan`). Use `row["terlambat_menit"] if row["terlambat_menit"] is not None else "—"`.
8. Data source: replace every `list_issues_for_period(conn, start, end, ...)`
   call with `list_severe_lateness_for_period(conn, start, end, self._threshold, ...)`.
9. KPI counts: replace `count_issues_for_period(conn, start, end)` with
   `count_severe_lateness_for_period(conn, start, end, self._threshold)`.
10. **Resolution-rate KPI:** replace the `resolution_rate(conn, start, end)` call
    with a local computation from the count dict:
    `total = c["total"]; rate = round(c["resolved"] / total * 100) if total else 0`.
    Remove the `from src.core.insights import resolution_rate` import if it is no
    longer used.
11. Batch resolve: pass the severe lister to the dialog —
    `BatchResolveDialog(..., lister_fn=lambda conn, s, e: list_severe_lateness_for_period(conn, s, e, self._threshold, resolved=False))`.
12. Keep `_on_batch_resolve`, search, Ctrl+F (`winfo_toplevel().bind_all`),
    click-outside, Enter-submit, `_on_destroy_cleanup`, `period_state` wiring
    byte-for-byte (only the data calls change).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_severe_lateness_screen.py
import customtkinter as ctk
from src.db.schema import init_db
from src.db.connection import get_connection
from src.db.employees import upsert_employee
from src.db.attendance import upsert_attendance
from src.db.settings import set_setting


def _seed(conn):
    a = upsert_employee(conn, no_staff="1", nama="BUDI", dept="IT")
    b = upsert_employee(conn, no_staff="2", nama="ANI", dept="HR")
    for eid, late in ((a, 75), (b, 90)):
        upsert_attendance(conn, employee_id=eid, tanggal="2026-05-04", hari="Senin",
                          tipe="Hari Kerja", jadwal="08.00 - 16.00",
                          masuk="09:15", keluar="16:30", kerja_jam=None,
                          lembur_jam=None, terlambat_menit=late, has_issue=0,
                          imported_from="W1.xls")
    set_setting(conn, "current_month", "2026-05")


def test_screen_constructs_with_batch_resolve(temp_db_path, monkeypatch, tk_root):
    import src.ui.screens.severe_lateness as mod
    monkeypatch.setattr(mod, "DB_PATH", temp_db_path)
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        _seed(conn)
    screen = mod.SevereLatenessScreen(tk_root)
    tk_root.update_idletasks()
    assert hasattr(screen, "_on_batch_resolve")
    screen.destroy()


def test_screen_binds_ctrl_f(temp_db_path, monkeypatch, tk_root):
    import src.ui.screens.severe_lateness as mod
    monkeypatch.setattr(mod, "DB_PATH", temp_db_path)
    init_db(temp_db_path)
    screen = mod.SevereLatenessScreen(tk_root)
    tk_root.update_idletasks()
    assert screen.bind("<Control-f>") != ""
    screen.destroy()


def test_screen_filter_reduces_rows(temp_db_path, monkeypatch, tk_root):
    import src.ui.screens.severe_lateness as mod
    monkeypatch.setattr(mod, "DB_PATH", temp_db_path)
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        _seed(conn)
    screen = mod.SevereLatenessScreen(tk_root)
    tk_root.update_idletasks()
    assert len(screen.open_tree.get_children()) == 2
    screen._apply_filter("budi")
    tk_root.update_idletasks()
    assert len(screen.open_tree.get_children()) == 1
    screen._apply_filter("")
    tk_root.update_idletasks()
    assert len(screen.open_tree.get_children()) == 2
    screen.destroy()


def test_screen_reads_and_writes_period_state(temp_db_path, monkeypatch, tk_root):
    from src.core.session_state import period_state
    import src.ui.screens.severe_lateness as mod
    monkeypatch.setattr(mod, "DB_PATH", temp_db_path)
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        set_setting(conn, "current_month", "2026-05")
    period_state.set("minggu_2")
    screen = mod.SevereLatenessScreen(tk_root)
    tk_root.update_idletasks()
    assert screen.nav.active == "minggu_2"
    screen._on_period_change("minggu_3")
    tk_root.update_idletasks()
    assert period_state.get() == "minggu_3"
    screen.destroy()
```

(Match attribute names — `open_tree`, `nav`, `_apply_filter`, `_on_period_change`,
`_on_batch_resolve` — to whatever the copied Issues code uses. If Issues uses a
different week-state accessor than `period_state`, mirror it.)

- [ ] **Step 2: Run test to verify it fails**

Run: `../../../.venv/Scripts/python.exe -m pytest tests/test_severe_lateness_screen.py -q`
Expected: FAIL (ModuleNotFoundError on src.ui.screens.severe_lateness).

- [ ] **Step 3: Implement the screen** (copy issues.py → apply the 12 deltas above).

- [ ] **Step 4: Run test to verify it passes**

Run: `../../../.venv/Scripts/python.exe -m pytest tests/test_severe_lateness_screen.py -q`
Expected: PASS (4 passed). Then run the FULL suite to ensure no regression:
`../../../.venv/Scripts/python.exe -m pytest -q`

- [ ] **Step 5: Commit**

```bash
git add src/ui/screens/severe_lateness.py tests/test_severe_lateness_screen.py
git commit -m "feat(v17): SevereLatenessScreen (Issues clone + Telat column)"
```

---

### Task 10: Sidebar entry + router wiring

**Files:**
- Modify: `src/ui/app.py` (nav_groups WORKFLOW group + `_show` router)
- Test: `tests/test_app_severe_lateness_nav.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_app_severe_lateness_nav.py
import src.ui.app as app_mod


def test_workflow_group_has_severe_lateness_below_issues():
    # Locate the nav_groups definition by constructing the structure the app uses.
    # The app exposes nav via a module-level builder or the App instance; assert the
    # WORKFLOW group contains SevereLateness directly after Issues.
    src = open(app_mod.__file__, encoding="utf-8").read()
    assert '"SevereLateness"' in src or "'SevereLateness'" in src
    # ordering: Issues appears before SevereLateness, which appears before WhatsApp
    i_issues = src.index("Issues")
    i_severe = src.index("SevereLateness")
    i_wa = src.index("WhatsAppAssistant")
    assert i_issues < i_severe < i_wa
```

(This is a lightweight structural guard. If `app.py` defines nav_groups in an
importable function, prefer asserting on that structure instead of reading source.)

- [ ] **Step 2: Run test to verify it fails**

Run: `../../../.venv/Scripts/python.exe -m pytest tests/test_app_severe_lateness_nav.py -q`
Expected: FAIL (SevereLateness not present).

- [ ] **Step 3: Write minimal implementation**

In `app.py` `nav_groups`, insert between Issues and WhatsApp Assistant:

```python
            ("◷", "Severe Lateness", "SevereLateness"),
```

In `_show()`, add a branch mirroring the Issues handler (lazy import + instantiate
+ grid). Example (match the real pattern in the file):

```python
        elif screen_key == "SevereLateness":
            if "SevereLateness" not in self._screens:
                from src.ui.screens.severe_lateness import SevereLatenessScreen
                self._screens["SevereLateness"] = SevereLatenessScreen(self.content)
                self._screens["SevereLateness"].grid(row=0, column=0, sticky="nsew")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `../../../.venv/Scripts/python.exe -m pytest tests/test_app_severe_lateness_nav.py -q`
Expected: PASS. Then full suite: `../../../.venv/Scripts/python.exe -m pytest -q`.

- [ ] **Step 5: Commit**

```bash
git add src/ui/app.py tests/test_app_severe_lateness_nav.py
git commit -m "feat(v17): sidebar entry + router for Severe Lateness"
```

---

### Task 11: Changelog + version bump

**Files:**
- Modify: `src/config.py` (`APP_VERSION`, `APP_BUILD_DATE`, `APP_CHANGELOG`)
- Test: `tests/test_changelog_v17.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_changelog_v17.py
from src import config


def test_version_is_v17():
    assert config.APP_VERSION == "17.0.0"


def test_changelog_has_v17_entry_on_top():
    top = config.APP_CHANGELOG[0]
    assert top["version"] == "17.0.0"
    kinds = [k for k, _ in top["changes"]]
    assert "feat" in kinds
    assert any("Severe Lateness" in desc for _, desc in top["changes"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `../../../.venv/Scripts/python.exe -m pytest tests/test_changelog_v17.py -q`
Expected: FAIL (APP_VERSION still 16.1.1).

- [ ] **Step 3: Write minimal implementation**

In `src/config.py`: set `APP_VERSION = "17.0.0"`, `APP_BUILD_DATE = "2026-06-09"`,
and prepend to `APP_CHANGELOG`:

```python
    {
        "version": "17.0.0",
        "date": "2026-06-09",
        "changes": [
            ("feat", "Menu baru 'Severe Lateness': mendeteksi keterlambatan harian "
                     "di atas ambang (default 60 menit) walau jam masuk & keluar "
                     "lengkap; resolusi alasan sama seperti Issues."),
            ("feat", "Pengaturan baru 'Severe Lateness Threshold (menit)' di "
                     "Settings → Umum (default 60, rentang 1–999)."),
        ],
    },
```

- [ ] **Step 4: Run test to verify it passes**

Run: `../../../.venv/Scripts/python.exe -m pytest tests/test_changelog_v17.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/config.py tests/test_changelog_v17.py
git commit -m "chore(v17): bump APP_VERSION 17.0.0 + changelog entry"
```

---

### Task 12: Full green + manual smoke handoff

**Files:** none.

- [ ] **Step 1: Run the full suite**

Run: `../../../.venv/Scripts/python.exe -m pytest -q`
Expected: all pass (296 baseline + the new tests).

- [ ] **Step 2: Hand off the smoke-test guide to the user**

Provide a manual smoke checklist (app launches; Severe Lateness menu visible
below Issues with the ◷ icon; rows appear for late-but-present days; resolve via
right panel persists; batch resolve works; threshold setting changes the list;
resolved reason appears in the filled monthly export; Coaching tally drops when a
day is marked Tugas Lapangan). **Do not build/rotate/push until the user confirms
smoke + authorizes** (framework rules 1–2; NO auto-push).

---

## Release (AFTER smoke + explicit user authorization)

Per CLAUDE.md framework rules 1–2 (not part of the TDD task loop):
1. Build installer: `../../../.venv/Scripts/python.exe -m tools.build_installer`
2. Rotate prod `.exe` (2-level `.bak`/`.bak.old`); never touch `data/hr.db`.
3. Copy to `Installers/HR-Absensi-Setup-v17.0.0.exe`.
4. Smoke the installed build (icon renders monochrome; menu works).
5. Push `v17` + advance `latest` (`git push origin v17:latest`) — **only with explicit authorization**.
6. Update `memory/version_state.md`.

---

## Self-review notes

- **Spec coverage:** §2 detection → T1/T5; §4 settings → T2/T3/T4/T6; §5 DB → T5;
  §6 screen → T9; §7 sidebar → T10; §8 categories → T2 (used in T9); §9 export →
  T7 (generator unchanged, per spec); §10 batch → T8; §11 changelog → T11; §12
  tests → distributed per task. All sections covered.
- **Type consistency:** `is_severe_lateness(row, threshold_min)`,
  `list_severe_lateness_for_period(conn, start, end, threshold_min, resolved=None)`,
  `count_severe_lateness_for_period(conn, start, end, threshold_min)`,
  `read_severe_lateness_threshold(conn)`, `severe_var`, `self._threshold` — names
  consistent across tasks.
- **No placeholders:** every code step shows complete code or a precise,
  unambiguous delta (T9 is a copy-then-delta because reproducing 500 lines would
  be error-prone; the deltas are exhaustive).
```
