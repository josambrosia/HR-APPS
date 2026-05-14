# Hari Libur Menu + Export Mingguan Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Hari Libur menu (mark dates as holidays — auto-resolve issues, drop from recap, hybrid `holidays`-table + `tipe`-stamp data model) and an Export Mingguan feature that restructures the Export screen into Export vs Generate modes.

**Architecture:** Holidays are stored in a new `holidays` table (durable source of truth) AND stamped onto `attendance_records.tipe='Hari Libur'` (denormalisation so queries/exports see it directly); `restamp_holidays` re-applies the stamp after each fingerprint import. Insight/coaching layers exclude holiday rows via the existing `tipe='Hari Kerja'` filter pattern. The Export screen gains a mode toggle: Export (fill imported template, unchanged) vs Generate (build from DB — Bulanan + the new Mingguan).

**Tech Stack:** Python 3.13, SQLite (`sqlite3`), customtkinter, openpyxl, pytest. Run tests from the worktree root with `../../../.venv/Scripts/python.exe -m pytest`.

**Spec:** `docs/superpowers/specs/2026-05-14-hari-libur-and-weekly-export-design.md`
**Baseline:** 160 tests passing at v11 (`e383c35`). Target after this plan: ~195-205.

---

## File Structure

**Create:**
- `src/db/holidays.py` — holidays data access: read queries + `mark_holidays` / `unmark_holidays` / `restamp_holidays`
- `src/core/weekly_export.py` — normalised weekly `.xlsx` generator
- `src/ui/screens/holiday.py` — Hari Libur screen (pola B: multi-select + Terapkan)
- `tests/test_holidays_db.py` — unit tests for `holidays.py`
- `tests/test_weekly_export.py` — unit tests for `weekly_export.py`
- `tests/test_holiday_screen.py` — smoke test for `holiday.py`

**Modify:**
- `src/db/schema.py` — `holidays` table + `export_history.kind` column in DDL + `_migrate()` for existing DBs
- `src/config.py` — `"libur"` in `REASON_CATEGORIES`
- `src/core/reason_mapper.py` — `"libur"` in `REASON_LABELS`
- `src/core/insights.py` — `AND tipe='Hari Kerja'` in `terlambat_ranking`, `ranking_departemen`, `resolution_rate`
- `src/db/coaching.py` — `AND ar.tipe='Hari Kerja'` in `list_coaching_for_week`
- `src/core/report_generator.py` — holiday rows in `_write_data_row` + skip totals; `IJIN_CATEGORIES` excludes `"libur"`
- `src/core/report_filler.py` — skip holiday rows
- `src/ui/screens/import_screen.py` — call `restamp_holidays` after import upsert
- `src/db/export_history.py` — `kind` param on `record_export` + `list_recent_exports`
- `src/ui/app.py` — Hari Libur nav item + `_show` branch + sidebar tightening
- `src/ui/screens/export.py` — mode toggle (Export / Generate), Generate mode (Bulanan + Mingguan)
- `src/ui/screens/active_month.py` — remove the per-card Generate button
- `tests/test_schema.py`, `tests/test_insights.py`, `tests/test_coaching_db.py`, `tests/test_report_generator.py`, `tests/test_report_filler_dry_run.py`, `tests/test_export_history.py`, `tests/test_reason_mapper.py` — add coverage

---

## Task 1: Schema — `holidays` table + `export_history.kind` + migration

**Files:**
- Modify: `src/db/schema.py`
- Test: `tests/test_schema.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_schema.py`:

```python
def test_holidays_table_created(temp_db_path):
    """init_db creates the holidays table."""
    init_db(temp_db_path)
    with sqlite3.connect(temp_db_path) as conn:
        row = conn.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name='holidays'"
        ).fetchone()
    assert row is not None


def test_export_history_has_kind_column(temp_db_path):
    """export_history has the kind column after init_db (new DB)."""
    init_db(temp_db_path)
    with sqlite3.connect(temp_db_path) as conn:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(export_history)")}
    assert "kind" in cols


def test_migrate_adds_kind_to_legacy_export_history(temp_db_path):
    """A pre-existing export_history WITHOUT kind gets the column added."""
    with sqlite3.connect(temp_db_path) as conn:
        conn.execute(
            """
            CREATE TABLE export_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                out_path TEXT NOT NULL, template TEXT NOT NULL,
                year_month TEXT NOT NULL, filled INTEGER NOT NULL,
                na INTEGER NOT NULL, not_found INTEGER NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.commit()
    init_db(temp_db_path)  # must migrate in place without error
    with sqlite3.connect(temp_db_path) as conn:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(export_history)")}
    assert "kind" in cols
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `../../../.venv/Scripts/python.exe -m pytest tests/test_schema.py -v`
Expected: 3 new tests FAIL (no `holidays` table, no `kind` column).

- [ ] **Step 3: Add the `holidays` table + `kind` column to DDL**

In `src/db/schema.py`, inside the `DDL` string, after the `outlier_exclusions` block, add:

```sql

CREATE TABLE IF NOT EXISTS holidays (
    tanggal    TEXT PRIMARY KEY,
    created_at TEXT NOT NULL
);
```

And in the same `DDL` string, change the `export_history` table definition to include `kind`:

```sql
CREATE TABLE IF NOT EXISTS export_history (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    out_path    TEXT NOT NULL,
    template    TEXT NOT NULL,
    year_month  TEXT NOT NULL,
    filled      INTEGER NOT NULL,
    na          INTEGER NOT NULL,
    not_found   INTEGER NOT NULL,
    kind        TEXT NOT NULL DEFAULT 'fill',
    created_at  TEXT NOT NULL
);
```

- [ ] **Step 4: Add `_migrate()` and call it from `init_db`**

In `src/db/schema.py`, add this function above `init_db`:

```python
def _migrate(conn: sqlite3.Connection) -> None:
    """Idempotent column additions for pre-existing databases.

    CREATE TABLE IF NOT EXISTS only creates missing tables — it does NOT
    add columns to a table that already exists. For an existing data/hr.db
    the export_history.kind column must be added via ALTER TABLE.
    """
    cols = {row[1] for row in conn.execute("PRAGMA table_info(export_history)")}
    if "kind" not in cols:
        conn.execute(
            "ALTER TABLE export_history "
            "ADD COLUMN kind TEXT NOT NULL DEFAULT 'fill'"
        )
```

In `init_db`, call `_migrate(conn)` right after `conn.executescript(DDL)`:

```python
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(DDL)
        _migrate(conn)
        for key, value in DEFAULT_SETTINGS.items():
            ...
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `../../../.venv/Scripts/python.exe -m pytest tests/test_schema.py -v`
Expected: all PASS (7 total: 4 original + 3 new).

- [ ] **Step 6: Commit**

```bash
git add src/db/schema.py tests/test_schema.py
git commit -m "feat(db): holidays table + export_history.kind column + migration"
```

---

## Task 2: `holidays.py` — read queries

**Files:**
- Create: `src/db/holidays.py`
- Test: `tests/test_holidays_db.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_holidays_db.py`:

```python
"""Tests for src/db/holidays.py — Hari Libur data access."""
from datetime import datetime, UTC

from src.db.schema import init_db
from src.db.connection import get_connection
from src.db.employees import upsert_employee
from src.db.attendance import upsert_attendance


def _emp(conn, no, nama):
    return upsert_employee(conn, no_staff=no, nama=nama, dept="X")


def _att(conn, emp_id, tanggal, *, tipe="Hari Kerja", masuk="08.05",
         keluar="16.00", has_issue=0, reason_category=None):
    upsert_attendance(
        conn, employee_id=emp_id, tanggal=tanggal, hari="Senin",
        tipe=tipe, jadwal="08.00 - 16.00",
        masuk=masuk, keluar=keluar, kerja_jam=8.0,
        lembur_jam=None, terlambat_menit=5, has_issue=has_issue,
        imported_from="W1.xls",
    )
    if reason_category is not None:
        conn.execute(
            "UPDATE attendance_records SET reason_category=? "
            "WHERE employee_id=? AND tanggal=?",
            (reason_category, emp_id, tanggal),
        )


def _mark_direct(conn, tanggal):
    """Seed a holidays row directly (no stamping) for read-query tests."""
    conn.execute(
        "INSERT OR IGNORE INTO holidays (tanggal, created_at) VALUES (?, ?)",
        (tanggal, datetime.now(UTC).isoformat(timespec="seconds")),
    )


def test_list_holidays_empty(temp_db_path):
    from src.db.holidays import list_holidays
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        assert list_holidays(conn) == []


def test_list_holidays_sorted(temp_db_path):
    from src.db.holidays import list_holidays
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        _mark_direct(conn, "2026-04-17")
        _mark_direct(conn, "2026-04-03")
        assert list_holidays(conn) == ["2026-04-03", "2026-04-17"]


def test_holiday_dates_in_month_filters_by_month(temp_db_path):
    from src.db.holidays import holiday_dates_in_month
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        _mark_direct(conn, "2026-04-03")
        _mark_direct(conn, "2026-05-01")
        assert holiday_dates_in_month(conn, "2026-04") == {"2026-04-03"}
        assert holiday_dates_in_month(conn, "2026-05") == {"2026-05-01"}


def test_workday_roster_lists_workdays_with_flags(temp_db_path):
    from src.db.holidays import workday_roster
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        a = _emp(conn, "1", "ANDI")
        _att(conn, a, "2026-04-01", has_issue=1)                       # open issue
        _att(conn, a, "2026-04-03", tipe="Hari Libur",
             reason_category="libur", has_issue=1)                     # already holiday
        _att(conn, a, "2026-04-05", tipe="Istirahat")                  # weekend — excluded
        _mark_direct(conn, "2026-04-03")
        roster = workday_roster(conn, "2026-04")
        assert [r["tanggal"] for r in roster] == ["2026-04-01", "2026-04-03"]
        by_date = {r["tanggal"]: r for r in roster}
        assert by_date["2026-04-01"]["is_holiday"] is False
        assert by_date["2026-04-01"]["issue_count"] == 1   # open issue
        assert by_date["2026-04-03"]["is_holiday"] is True
        assert by_date["2026-04-03"]["issue_count"] == 1   # libur-resolved
        assert by_date["2026-04-01"]["hari"] == "Senin"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `../../../.venv/Scripts/python.exe -m pytest tests/test_holidays_db.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.db.holidays'`.

- [ ] **Step 3: Create `src/db/holidays.py` with the read queries**

```python
"""Data access for the Hari Libur feature.

Holidays are date-keyed (company-wide). The `holidays` table is the durable
source of truth; attendance_records.tipe is stamped 'Hari Libur' as a
denormalisation so weekly export & other queries see it directly. The stamp
is re-applied after every import via restamp_holidays().
"""
import sqlite3
from datetime import datetime, UTC
from typing import List


def list_holidays(conn: sqlite3.Connection) -> List[str]:
    """All holiday dates ('YYYY-MM-DD'), ascending."""
    rows = conn.execute(
        "SELECT tanggal FROM holidays ORDER BY tanggal ASC"
    ).fetchall()
    return [r[0] for r in rows]


def holiday_dates_in_month(conn: sqlite3.Connection, year_month: str) -> set:
    """Set of holiday dates within the given 'YYYY-MM' month."""
    rows = conn.execute(
        "SELECT tanggal FROM holidays WHERE substr(tanggal, 1, 7) = ?",
        (year_month,),
    ).fetchall()
    return {r[0] for r in rows}


def workday_roster(conn: sqlite3.Connection, year_month: str) -> List[dict]:
    """Dates in the month with attendance records of tipe Hari Kerja/Hari Libur.

    Each dict: {tanggal, hari, is_holiday, issue_count}.
      - is_holiday: date is present in the holidays table
      - issue_count: if NOT holiday -> count of OPEN issues (has_issue=1 AND
        reason_category IS NULL) -> preview "will be auto-resolved".
        If holiday -> count of reason_category='libur' rows -> preview
        "will be re-opened" on revert.
    Sorted ascending by date. Istirahat (weekend) rows are excluded —
    marking those as holiday is meaningless.
    """
    rows = conn.execute(
        """
        SELECT
            ar.tanggal,
            MIN(ar.hari) AS hari,
            MAX(CASE WHEN h.tanggal IS NOT NULL THEN 1 ELSE 0 END) AS is_holiday,
            SUM(CASE
                WHEN h.tanggal IS NULL
                     AND ar.has_issue = 1 AND ar.reason_category IS NULL
                THEN 1
                WHEN h.tanggal IS NOT NULL
                     AND ar.reason_category = 'libur'
                THEN 1
                ELSE 0
            END) AS issue_count
          FROM attendance_records ar
          LEFT JOIN holidays h ON h.tanggal = ar.tanggal
         WHERE substr(ar.tanggal, 1, 7) = ?
           AND ar.tipe IN ('Hari Kerja', 'Hari Libur')
         GROUP BY ar.tanggal
         ORDER BY ar.tanggal ASC
        """,
        (year_month,),
    ).fetchall()
    return [
        {
            "tanggal": r["tanggal"],
            "hari": r["hari"] or "",
            "is_holiday": bool(r["is_holiday"]),
            "issue_count": r["issue_count"] or 0,
        }
        for r in rows
    ]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `../../../.venv/Scripts/python.exe -m pytest tests/test_holidays_db.py -v`
Expected: 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/db/holidays.py tests/test_holidays_db.py
git commit -m "feat(db): holidays.py read queries (list, month, workday_roster)"
```

---

## Task 3: `holidays.py` — `mark_holidays` / `unmark_holidays` / `restamp_holidays`

**Files:**
- Modify: `src/db/holidays.py`
- Test: `tests/test_holidays_db.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_holidays_db.py`:

```python
def _row(conn, emp_id, tanggal):
    return conn.execute(
        "SELECT tipe, reason_category, resolved_at FROM attendance_records "
        "WHERE employee_id=? AND tanggal=?", (emp_id, tanggal),
    ).fetchone()


def test_mark_holidays_stamps_tipe_and_inserts_row(temp_db_path):
    from src.db.holidays import mark_holidays, list_holidays
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        a = _emp(conn, "1", "ANDI")
        _att(conn, a, "2026-04-03")
        result = mark_holidays(conn, ["2026-04-03"])
        assert list_holidays(conn) == ["2026-04-03"]
        assert _row(conn, a, "2026-04-03")["tipe"] == "Hari Libur"
        assert result["dates_marked"] == 1


def test_mark_holidays_auto_resolves_only_open_issues(temp_db_path):
    from src.db.holidays import mark_holidays
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        a = _emp(conn, "1", "OPEN")
        b = _emp(conn, "2", "MANUAL")
        _att(conn, a, "2026-04-03", has_issue=1)                          # open
        _att(conn, b, "2026-04-03", has_issue=1, reason_category="izin_sakit")
        result = mark_holidays(conn, ["2026-04-03"])
        assert result["issues_resolved"] == 1                             # only the open one
        assert _row(conn, a, "2026-04-03")["reason_category"] == "libur"
        assert _row(conn, b, "2026-04-03")["reason_category"] == "izin_sakit"


def test_mark_holidays_idempotent(temp_db_path):
    from src.db.holidays import mark_holidays, list_holidays
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        a = _emp(conn, "1", "ANDI")
        _att(conn, a, "2026-04-03", has_issue=1)
        mark_holidays(conn, ["2026-04-03"])
        mark_holidays(conn, ["2026-04-03"])  # second call — no dup, no error
        assert list_holidays(conn) == ["2026-04-03"]


def test_unmark_holidays_restores_tipe_and_reopens_libur_issues(temp_db_path):
    from src.db.holidays import mark_holidays, unmark_holidays, list_holidays
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        a = _emp(conn, "1", "ANDI")
        _att(conn, a, "2026-04-03", has_issue=1)
        mark_holidays(conn, ["2026-04-03"])
        result = unmark_holidays(conn, ["2026-04-03"])
        assert list_holidays(conn) == []
        row = _row(conn, a, "2026-04-03")
        assert row["tipe"] == "Hari Kerja"
        assert row["reason_category"] is None
        assert result["issues_reopened"] == 1


def test_unmark_holidays_leaves_manually_resolved_issues(temp_db_path):
    from src.db.holidays import mark_holidays, unmark_holidays
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        b = _emp(conn, "2", "MANUAL")
        _att(conn, b, "2026-04-03", has_issue=1, reason_category="izin_sakit")
        mark_holidays(conn, ["2026-04-03"])
        unmark_holidays(conn, ["2026-04-03"])
        assert _row(conn, b, "2026-04-03")["reason_category"] == "izin_sakit"


def test_restamp_holidays_reapplies_after_simulated_reimport(temp_db_path):
    from src.db.holidays import mark_holidays, restamp_holidays
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        a = _emp(conn, "1", "ANDI")
        _att(conn, a, "2026-04-03", has_issue=1)
        mark_holidays(conn, ["2026-04-03"])
        # simulate re-import: upsert overwrites tipe back to 'Hari Kerja'
        _att(conn, a, "2026-04-03", has_issue=1)
        assert _row(conn, a, "2026-04-03")["tipe"] == "Hari Kerja"   # lost
        # a NEW employee imported later with an open issue on the holiday date
        c = _emp(conn, "2", "LATE")
        _att(conn, c, "2026-04-03", has_issue=1)
        restamp_holidays(conn)
        assert _row(conn, a, "2026-04-03")["tipe"] == "Hari Libur"   # restored
        assert _row(conn, c, "2026-04-03")["tipe"] == "Hari Libur"
        assert _row(conn, c, "2026-04-03")["reason_category"] == "libur"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `../../../.venv/Scripts/python.exe -m pytest tests/test_holidays_db.py -v`
Expected: 6 new tests FAIL with `ImportError: cannot import name 'mark_holidays'`.

- [ ] **Step 3: Add the write functions to `src/db/holidays.py`**

Append to `src/db/holidays.py`:

```python
def mark_holidays(conn: sqlite3.Connection, dates: list) -> dict:
    """Mark the given dates ('YYYY-MM-DD') as holidays.

    For each date: insert into holidays, stamp attendance_records.tipe to
    'Hari Libur', auto-resolve OPEN issues (reason_category IS NULL) with
    reason_category='libur'. Idempotent — already-holiday dates re-stamp
    harmlessly. Returns {'dates_marked', 'issues_resolved'}.
    """
    now = datetime.now(UTC).isoformat(timespec="seconds")
    issues_resolved = 0
    for d in dates:
        conn.execute(
            "INSERT OR IGNORE INTO holidays (tanggal, created_at) VALUES (?, ?)",
            (d, now),
        )
        conn.execute(
            "UPDATE attendance_records SET tipe='Hari Libur' "
            "WHERE tanggal=? AND tipe='Hari Kerja'",
            (d,),
        )
        cur = conn.execute(
            "UPDATE attendance_records "
            "SET reason_category='libur', reason_detail=NULL, resolved_at=? "
            "WHERE tanggal=? AND has_issue=1 AND reason_category IS NULL",
            (now, d),
        )
        issues_resolved += cur.rowcount
    return {"dates_marked": len(dates), "issues_resolved": issues_resolved}


def unmark_holidays(conn: sqlite3.Connection, dates: list) -> dict:
    """Remove holiday status from the given dates.

    For each date: delete from holidays, restore attendance_records.tipe to
    'Hari Kerja', re-open ONLY issues this feature resolved
    (reason_category='libur'). Manual resolutions are left untouched.
    Returns {'dates_unmarked', 'issues_reopened'}.
    """
    issues_reopened = 0
    for d in dates:
        conn.execute("DELETE FROM holidays WHERE tanggal=?", (d,))
        conn.execute(
            "UPDATE attendance_records SET tipe='Hari Kerja' "
            "WHERE tanggal=? AND tipe='Hari Libur'",
            (d,),
        )
        cur = conn.execute(
            "UPDATE attendance_records "
            "SET reason_category=NULL, reason_detail=NULL, resolved_at=NULL "
            "WHERE tanggal=? AND reason_category='libur'",
            (d,),
        )
        issues_reopened += cur.rowcount
    return {"dates_unmarked": len(dates), "issues_reopened": issues_reopened}


def restamp_holidays(conn: sqlite3.Connection) -> None:
    """Re-apply holiday stamping for every date in the holidays table.

    Called after a fingerprint import: upsert_attendance overwrites
    attendance_records.tipe back to 'Hari Kerja', so this re-stamps
    'Hari Libur' and re-resolves any newly-imported OPEN issues on
    holiday dates. Makes import idempotent w.r.t. holiday status.
    """
    dates = [r[0] for r in conn.execute("SELECT tanggal FROM holidays")]
    if dates:
        mark_holidays(conn, dates)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `../../../.venv/Scripts/python.exe -m pytest tests/test_holidays_db.py -v`
Expected: all 10 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/db/holidays.py tests/test_holidays_db.py
git commit -m "feat(db): holidays.py mark/unmark/restamp with auto-resolve"
```

---

## Task 4: `"libur"` reason category

**Files:**
- Modify: `src/config.py`, `src/core/reason_mapper.py`
- Test: `tests/test_reason_mapper.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_reason_mapper.py`:

```python
def test_render_alasan_ijin_libur():
    from src.core.reason_mapper import render_alasan_ijin
    assert render_alasan_ijin("libur", None) == "Libur"


def test_libur_in_reason_categories():
    from src.config import REASON_CATEGORIES
    assert "libur" in REASON_CATEGORIES
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `../../../.venv/Scripts/python.exe -m pytest tests/test_reason_mapper.py -v`
Expected: 2 new tests FAIL (`"libur"` not a known category / not in tuple).

- [ ] **Step 3: Add `"libur"` to config + reason_mapper**

In `src/config.py`, add `"libur"` to `REASON_CATEGORIES` (before `"na"`):

```python
REASON_CATEGORIES = (
    "tugas_lapangan",
    "tugas_paparan",
    "izin_sakit",
    "cuti",
    "terlambat_kerja",
    "terlambat_lain",
    "lupa_absen",
    "libur",
    "na",
)
```

In `src/core/reason_mapper.py`, add `"libur"` to `REASON_LABELS` (before `"na"`):

```python
    "lupa_absen":      "Lupa Absen",
    "libur":           "Libur",
    "na":              "NA / Belum ada kabar",
```

`render_alasan_ijin("libur", None)` falls through to `return REASON_LABELS[category]` → `"Libur"`. Do NOT add `"libur"` to `REASON_NEEDS_DETAIL`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `../../../.venv/Scripts/python.exe -m pytest tests/test_reason_mapper.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add src/config.py src/core/reason_mapper.py tests/test_reason_mapper.py
git commit -m "feat(core): add 'libur' reason category"
```

---

## Task 5: `insights.py` — exclude holiday rows from recap

**Files:**
- Modify: `src/core/insights.py`
- Test: `tests/test_insights.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_insights.py` (the file already has `_add_emp` / `_add_att` helpers):

```python
def test_terlambat_ranking_excludes_holiday_dates(temp_db_path):
    from src.db.holidays import mark_holidays
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        a = _add_emp(conn, "1", "ANDI")
        _add_att(conn, a, "2026-04-01", "Senin", "08.50", "16.00", 50)
        _add_att(conn, a, "2026-04-03", "Jumat", "09.00", "16.00", 60)
        base = terlambat_ranking(conn, "2026-04-01", "2026-04-30")
        assert base[0]["total_terlambat"] == 110          # baseline: both days
        mark_holidays(conn, ["2026-04-03"])
        after = terlambat_ranking(conn, "2026-04-01", "2026-04-30")
        assert after[0]["total_terlambat"] == 50          # holiday's 60 dropped


def test_ranking_departemen_excludes_holiday_dates(temp_db_path):
    from src.db.holidays import mark_holidays
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        a = _add_emp(conn, "1", "ANDI")
        _add_att(conn, a, "2026-04-01", "Senin", "08.50", "16.00", 50)
        _add_att(conn, a, "2026-04-03", "Jumat", "09.00", "16.00", 60)
        mark_holidays(conn, ["2026-04-03"])
        rows = ranking_departemen(conn, "2026-04-01", "2026-04-30")
        assert rows[0]["total_terlambat"] == 50           # only April 1 counts


def test_resolution_rate_excludes_holiday_dates(temp_db_path):
    from src.db.holidays import mark_holidays
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        a = _add_emp(conn, "1", "ANDI")
        _add_att(conn, a, "2026-04-01", "Senin", None, None, 0, has_issue=1)
        _add_att(conn, a, "2026-04-03", "Jumat", None, None, 0, has_issue=1)
        mark_holidays(conn, ["2026-04-03"])               # resolves Apr-3 as 'libur'
        rate = resolution_rate(conn, "2026-04-01", "2026-04-30")
        assert rate["total"] == 1                         # holiday row excluded
        assert rate["resolved"] == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `../../../.venv/Scripts/python.exe -m pytest tests/test_insights.py -k holiday -v`
Expected: 3 tests FAIL (holiday rows still counted).

- [ ] **Step 3: Add `tipe='Hari Kerja'` filters in `src/core/insights.py`**

In `terlambat_ranking`, change the WHERE line:

```python
         WHERE ar.tanggal BETWEEN ? AND ?
           AND ar.tipe = 'Hari Kerja'
         GROUP BY e.id
```

In `ranking_departemen`, change the WHERE line:

```python
         WHERE ar.tanggal BETWEEN ? AND ?
               AND e.dept IS NOT NULL
               AND ar.tipe = 'Hari Kerja'{exc_frag}
```

In `resolution_rate`, change the WHERE line:

```python
         WHERE has_issue = 1 AND tanggal BETWEEN ? AND ?
           AND tipe = 'Hari Kerja'
```

The other insight functions (`karyawan_teladan`, `karyawan_teladan_top_n`, `hari_paling_rawan`, `avg_minutes_per_late_event`, `pola_jam_masuk`) already filter `tipe = 'Hari Kerja'` — no change needed. `top_n_terlambat` and `coaching_flag` derive from `terlambat_ranking` — they inherit the fix.

- [ ] **Step 4: Run tests to verify they pass**

Run: `../../../.venv/Scripts/python.exe -m pytest tests/test_insights.py -v`
Expected: all PASS (existing tests unaffected — they use only `tipe='Hari Kerja'` rows; 3 new tests pass).

- [ ] **Step 5: Commit**

```bash
git add src/core/insights.py tests/test_insights.py
git commit -m "feat(insights): exclude Hari Libur rows from recap aggregations"
```

---

## Task 6: `coaching.py` — exclude holiday rows from `list_coaching_for_week`

**Files:**
- Modify: `src/db/coaching.py`
- Test: `tests/test_coaching_db.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_coaching_db.py` (file already has `_conn`, `_add_employee`, `_add_late_attendance` helpers):

```python
def test_list_coaching_for_week_excludes_holiday_dates():
    """Lateness on a holiday date does not push an employee over threshold."""
    from src.db.holidays import mark_holidays
    conn = _conn()
    emp = _add_employee(conn)
    # 50 min on a normal day + 50 min on a day that becomes a holiday
    _add_late_attendance(conn, emp, "2026-04-06", 50)
    _add_late_attendance(conn, emp, "2026-04-08", 50)
    # baseline: 100 total > 75 threshold -> employee appears
    base = list_coaching_for_week(
        conn, week_start="2026-04-06", week_end="2026-04-12", threshold_minutes=75,
    )
    assert len(base) == 1
    # mark April 8 holiday -> only 50 left -> below threshold -> not flagged
    mark_holidays(conn, ["2026-04-08"])
    after = list_coaching_for_week(
        conn, week_start="2026-04-06", week_end="2026-04-12", threshold_minutes=75,
    )
    assert after == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `../../../.venv/Scripts/python.exe -m pytest tests/test_coaching_db.py -k holiday -v`
Expected: FAIL (employee still flagged — holiday lateness still counted).

- [ ] **Step 3: Add `tipe='Hari Kerja'` filter in `src/db/coaching.py`**

In `list_coaching_for_week`, inside the `terlambat` CTE, change the WHERE line:

```python
              FROM attendance_records ar
             WHERE ar.tanggal BETWEEN ? AND ?
               AND ar.tipe = 'Hari Kerja'{exc_frag}
             GROUP BY ar.employee_id
```

- [ ] **Step 4: Run test to verify it passes**

Run: `../../../.venv/Scripts/python.exe -m pytest tests/test_coaching_db.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add src/db/coaching.py tests/test_coaching_db.py
git commit -m "feat(coaching): exclude Hari Libur rows from list_coaching_for_week"
```

---

## Task 7: `report_generator.py` — holiday rows in monthly report

**Files:**
- Modify: `src/core/report_generator.py`
- Test: `tests/test_report_generator.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_report_generator.py`:

```python
def test_generate_monthly_report_holiday_row(tmp_path):
    """Holiday row: G='Libur', E='Hari Kerja', count columns blank, and it
    does not contribute to Total Personal."""
    import sqlite3
    from src.db.holidays import mark_holidays
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(DDL)
    a = upsert_employee(conn, no_staff="1", nama="ANDI", dept="X")
    upsert_attendance(
        conn, employee_id=a, tanggal="2026-04-01", hari="Senin",
        tipe="Hari Kerja", jadwal="08.00 - 16.00", masuk="08:30",
        keluar="16:00", kerja_jam=7.5, lembur_jam=None,
        terlambat_menit=30, has_issue=0, imported_from="t.xls",
    )
    upsert_attendance(
        conn, employee_id=a, tanggal="2026-04-03", hari="Jumat",
        tipe="Hari Kerja", jadwal="08.00 - 16.00", masuk="09:00",
        keluar="16:00", kerja_jam=7.0, lembur_jam=None,
        terlambat_menit=60, has_issue=0, imported_from="t.xls",
    )
    mark_holidays(conn, ["2026-04-03"])
    out = tmp_path / "out.xlsx"
    generate_monthly_report(conn, year_month="2026-04", out_path=out)
    ws = load_workbook(out).active

    holiday_row = total_row = None
    for r in range(3, ws.max_row + 1):
        c = ws.cell(row=r, column=3).value
        if c is not None and str(c).startswith("2026-04-03"):
            holiday_row = r
        if ws.cell(row=r, column=1).value == "Total Personal:":
            total_row = r
    assert holiday_row is not None and total_row is not None
    assert ws.cell(row=holiday_row, column=5).value == "Hari Kerja"   # E Tipe
    assert ws.cell(row=holiday_row, column=7).value == "Libur"        # G Masuk
    assert ws.cell(row=holiday_row, column=8).value in (None, "")     # H Keluar
    assert ws.cell(row=holiday_row, column=12).value in (None, "")    # L Terlambat
    assert ws.cell(row=total_row, column=12).value == 30             # only April 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `../../../.venv/Scripts/python.exe -m pytest tests/test_report_generator.py -k holiday -v`
Expected: FAIL (holiday row written as a normal row; total includes 60).

- [ ] **Step 3: Exclude `"libur"` from `IJIN_CATEGORIES`**

In `src/core/report_generator.py`, change the `IJIN_CATEGORIES` line:

```python
# All reason categories except "na" (unknown) and "libur" (a company holiday,
# not a personal ijin) — neither should add to the monthly Ijin column.
IJIN_CATEGORIES = tuple(c for c in REASON_CATEGORIES if c not in ("na", "libur"))
```

- [ ] **Step 4: Add the holiday-row branch in `_write_data_row`**

In `src/core/report_generator.py`, at the start of `_write_data_row` (after the `tanggal_val` conversion block, before `has_issue = db_row.get("has_issue") == 1`), insert:

```python
    is_holiday = db_row.get("tipe") == "Hari Libur"
    if is_holiday:
        # Holiday row: marker "Libur" in column G only; Tipe shown as
        # "Hari Kerja" (matches the reference Laporan Bulanan April); all
        # count columns + Alasan Ijin left blank.
        values = [
            db_row["nama"],              # A Nama
            db_row.get("dept") or "",     # B Dept
            tanggal_val,                 # C Tanggal
            db_row.get("hari") or "",     # D Hari
            "Hari Kerja",                # E Tipe (override)
            db_row.get("jadwal") or "",   # F Jadwal
            "Libur",                     # G Masuk -> marker
            "",                          # H Keluar
            "", "", "", "", "", "", "", "",  # I-P counts blank
            "",                          # Q Alasan Ijin blank
        ]
        for col, val in enumerate(values, start=1):
            ws.cell(row=row_num, column=col, value=val)
        _apply_row_styles(ws, row_num, styles)
        return
```

- [ ] **Step 5: Skip holiday rows in the totals loop**

In `src/core/report_generator.py`, in `generate_monthly_report`, change the per-record loop body:

```python
        for r in emp_records:
            is_holiday = r.get("tipe") == "Hari Libur"
            derived = compute_derived(r)
            _write_data_row(ws, current_row, r, derived, data_styles)
            if not is_holiday:
                _accumulate_total(total, r, derived)
                if r.get("has_issue") == 1 and not r.get("reason_category"):
                    na_count += 1
            rows_generated += 1
            current_row += 1
```

- [ ] **Step 6: Run test to verify it passes**

Run: `../../../.venv/Scripts/python.exe -m pytest tests/test_report_generator.py -v`
Expected: all PASS (existing tests unaffected).

- [ ] **Step 7: Commit**

```bash
git add src/core/report_generator.py tests/test_report_generator.py
git commit -m "feat(core): render Hari Libur rows in monthly report generator"
```

---

## Task 8: `report_filler.py` — skip holiday rows

**Files:**
- Modify: `src/core/report_filler.py`
- Test: `tests/test_report_filler_dry_run.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_report_filler_dry_run.py`:

```python
def test_fill_skips_holiday_rows(synthetic_monthly_xlsx, tmp_path):
    """A row whose DB tipe is 'Hari Libur' is skipped — column Q not written."""
    import sqlite3
    from src.db.schema import DDL
    from src.db.employees import upsert_employee
    from src.db.attendance import upsert_attendance
    from src.db.holidays import mark_holidays
    from src.core.report_filler import fill_monthly_report
    from openpyxl import load_workbook

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(DDL)
    budi = upsert_employee(conn, no_staff="9001", nama="BUDI", dept="TEST")
    upsert_attendance(
        conn, employee_id=budi, tanggal="2026-04-03", hari="Rabu",
        tipe="Hari Kerja", jadwal="08.00 - 16.00", masuk=None, keluar=None,
        kerja_jam=None, lembur_jam=None, terlambat_menit=None, has_issue=1,
        imported_from="t.xls",
    )
    mark_holidays(conn, ["2026-04-03"])
    out_path, _summary = fill_monthly_report(
        synthetic_monthly_xlsx, conn, dry_run=False, out_dir=tmp_path,
    )
    ws = load_workbook(out_path).active
    # synthetic_monthly_xlsx row 5 = BUDI 2026-04-03; column Q (17) stays blank
    assert ws.cell(row=5, column=17).value in (None, "")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `../../../.venv/Scripts/python.exe -m pytest tests/test_report_filler_dry_run.py -k holiday -v`
Expected: FAIL (column Q gets `"Libur"` written because the row matches and has `reason_category='libur'`).

- [ ] **Step 3: Skip holiday rows in `fill_monthly_report`**

In `src/core/report_filler.py`, add `ar.tipe` to the SELECT:

```python
        row = conn.execute(
            """
            SELECT ar.has_issue, ar.reason_category, ar.reason_detail, ar.tipe
              FROM attendance_records ar
              JOIN employees e ON ar.employee_id = e.id
             WHERE e.nama = ? COLLATE NOCASE AND ar.tanggal = ?
            """,
            (nama, tanggal),
        ).fetchone()
```

Then, right after the `if row is None:` block, add the holiday skip:

```python
        if row is None:
            summary.not_found_count += 1
            continue
        if row["tipe"] == "Hari Libur":
            continue  # holiday row — skip; do not write Alasan Ijin
        if row["has_issue"] != 1:
            continue  # skip non-issue rows entirely
```

- [ ] **Step 4: Run test to verify it passes**

Run: `../../../.venv/Scripts/python.exe -m pytest tests/test_report_filler_dry_run.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add src/core/report_filler.py tests/test_report_filler_dry_run.py
git commit -m "feat(core): skip Hari Libur rows in report_filler"
```

---

## Task 9: Import re-stamp wiring

**Files:**
- Modify: `src/ui/screens/import_screen.py`

This is a one-line UI wiring change. `restamp_holidays` is fully unit-tested in Task 3; verification here is the full regression suite + manual smoke.

- [ ] **Step 1: Add the import**

In `src/ui/screens/import_screen.py`, near the other `src.db` imports (after line 11 `from src.db.attendance import ...`), add:

```python
from src.db.holidays import restamp_holidays
```

- [ ] **Step 2: Call `restamp_holidays` after the import upsert loop**

In `_on_confirm`, inside the `with cm as progress, get_connection(DB_PATH) as conn:` block, after the `if mode_month:` block (i.e. after `set_setting(conn, "current_month", mode_month)`), still inside the `with` block, add at 12-space indentation:

```python
            if mode_month:
                set_setting(conn, "current_month", mode_month)

            # Re-stamp holiday status: upsert_attendance overwrites tipe back
            # to 'Hari Kerja', so re-apply 'Hari Libur' + auto-resolve for
            # dates in the holidays table (see Hari Libur design spec).
            restamp_holidays(conn)
```

- [ ] **Step 3: Run the full suite to confirm nothing regressed**

Run: `../../../.venv/Scripts/python.exe -m pytest -q`
Expected: same count as after Task 8, all PASS.

- [ ] **Step 4: Commit**

```bash
git add src/ui/screens/import_screen.py
git commit -m "feat(import): re-stamp holidays after fingerprint import"
```

---

## Task 10: `weekly_export.py` — normalised weekly export generator

**Files:**
- Create: `src/core/weekly_export.py`
- Test: `tests/test_weekly_export.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_weekly_export.py`:

```python
"""Tests for src/core/weekly_export.py — normalised weekly export."""
import sqlite3

from openpyxl import load_workbook

from src.db.schema import DDL
from src.db.employees import upsert_employee
from src.db.attendance import upsert_attendance
from src.db.holidays import mark_holidays
from src.core.weekly_export import generate_weekly_export, HEADERS


def _conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(DDL)
    return conn


def _att(conn, emp_id, tanggal, hari):
    upsert_attendance(
        conn, employee_id=emp_id, tanggal=tanggal, hari=hari,
        tipe="Hari Kerja", jadwal="08.00 - 16.00",
        masuk="08:05", keluar="16:00", kerja_jam=8.0,
        lembur_jam=None, terlambat_menit=5, has_issue=0,
        imported_from="W1.xls",
    )


def test_weekly_export_has_header_and_12_columns(tmp_path):
    conn = _conn()
    a = upsert_employee(conn, no_staff="1", nama="ANDI", dept="X")
    _att(conn, a, "2026-04-07", "Selasa")
    out = tmp_path / "weekly.xlsx"
    generate_weekly_export(conn, "2026-04-06", "2026-04-12", out)
    ws = load_workbook(out).active
    assert [c.value for c in ws[1]] == HEADERS
    assert len(HEADERS) == 12


def test_weekly_export_filters_date_range(tmp_path):
    conn = _conn()
    a = upsert_employee(conn, no_staff="1", nama="ANDI", dept="X")
    _att(conn, a, "2026-04-07", "Selasa")   # inside
    _att(conn, a, "2026-04-20", "Senin")    # outside
    out = tmp_path / "weekly.xlsx"
    summary = generate_weekly_export(conn, "2026-04-06", "2026-04-12", out)
    assert summary.rows == 1
    ws = load_workbook(out).active
    assert ws.cell(row=2, column=4).value == "2026-04-07"   # D Tanggal


def test_weekly_export_holiday_row_tipe_and_blank_counts(tmp_path):
    conn = _conn()
    a = upsert_employee(conn, no_staff="1", nama="ANDI", dept="X")
    _att(conn, a, "2026-04-09", "Kamis")
    mark_holidays(conn, ["2026-04-09"])
    out = tmp_path / "weekly.xlsx"
    generate_weekly_export(conn, "2026-04-06", "2026-04-12", out)
    ws = load_workbook(out).active
    assert ws.cell(row=2, column=6).value == "Hari Libur"      # F Tipe
    assert ws.cell(row=2, column=7).value == "08.00 - 16.00"   # G Jadwal kept
    assert ws.cell(row=2, column=8).value in (None, "")        # H Masuk blank
    assert ws.cell(row=2, column=12).value in (None, "")       # L Terlambat blank


def test_weekly_export_sorted_by_nama_then_tanggal(tmp_path):
    conn = _conn()
    a = upsert_employee(conn, no_staff="1", nama="ZARA", dept="X")
    b = upsert_employee(conn, no_staff="2", nama="ANDI", dept="X")
    _att(conn, a, "2026-04-07", "Selasa")
    _att(conn, b, "2026-04-08", "Rabu")
    _att(conn, b, "2026-04-07", "Selasa")
    out = tmp_path / "weekly.xlsx"
    generate_weekly_export(conn, "2026-04-06", "2026-04-12", out)
    ws = load_workbook(out).active
    assert [ws.cell(row=r, column=1).value for r in range(2, 5)] == \
        ["ANDI", "ANDI", "ZARA"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `../../../.venv/Scripts/python.exe -m pytest tests/test_weekly_export.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.core.weekly_export'`.

- [ ] **Step 3: Create `src/core/weekly_export.py`**

```python
"""Generate a normalised weekly attendance export (.xlsx) from the DB.

Mirrors the fingerprint structure, cleaned: 12 columns, one row per
attendance record in the date range. Column F (Tipe) shows 'Hari Libur'
for dates marked via the Hari Libur menu (tipe is already stamped in the DB).
"""
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font

HEADERS = [
    "Nama", "No. Staff", "Dept", "Tanggal", "Hari", "Tipe",
    "Jadwal", "Masuk", "Keluar", "Kerja", "Lembur", "Terlambat",
]
_COL_WIDTHS = [22, 10, 16, 12, 9, 12, 14, 9, 9, 8, 8, 10]


@dataclass
class WeeklyExportSummary:
    rows: int
    employees: int


def generate_weekly_export(
    conn: sqlite3.Connection,
    period_start: str,
    period_end: str,
    out_path: Path,
) -> WeeklyExportSummary:
    """Write a normalised weekly export for [period_start, period_end].

    Holiday rows (tipe='Hari Libur'): column F shows 'Hari Libur', the count
    columns (Masuk/Keluar/Kerja/Lembur/Terlambat) are left blank, Jadwal kept.
    """
    rows = conn.execute(
        """
        SELECT e.nama, e.no_staff, e.dept,
               ar.tanggal, ar.hari, ar.tipe, ar.jadwal,
               ar.masuk, ar.keluar, ar.kerja_jam, ar.lembur_jam,
               ar.terlambat_menit
          FROM attendance_records ar
          JOIN employees e ON ar.employee_id = e.id
         WHERE ar.tanggal BETWEEN ? AND ?
         ORDER BY e.nama ASC, ar.tanggal ASC
        """,
        (period_start, period_end),
    ).fetchall()

    wb = Workbook()
    ws = wb.active
    ws.title = "Mingguan"
    ws.append(HEADERS)
    for col_idx, width in enumerate(_COL_WIDTHS, start=1):
        ws.column_dimensions[
            ws.cell(row=1, column=col_idx).column_letter
        ].width = width
    for cell in ws[1]:
        cell.font = Font(bold=True)

    employees = set()
    for r in rows:
        employees.add(r["nama"])
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

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out_path)
    return WeeklyExportSummary(rows=len(rows), employees=len(employees))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `../../../.venv/Scripts/python.exe -m pytest tests/test_weekly_export.py -v`
Expected: 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/core/weekly_export.py tests/test_weekly_export.py
git commit -m "feat(core): weekly_export.py — normalised weekly xlsx generator"
```

---

## Task 11: `export_history.py` — `kind` parameter

**Files:**
- Modify: `src/db/export_history.py`
- Test: `tests/test_export_history.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_export_history.py`:

```python
def test_record_export_with_kind(empty_db):
    with get_connection(empty_db) as conn:
        export_id = record_export(
            conn, out_path="/tmp/Laporan Mingguan.xlsx", template="-",
            year_month="2026-04", filled=120, na=0, not_found=0,
            kind="generate_mingguan",
        )
    with get_connection(empty_db) as conn:
        row = conn.execute(
            "SELECT kind FROM export_history WHERE id = ?", (export_id,)
        ).fetchone()
    assert row["kind"] == "generate_mingguan"


def test_record_export_kind_defaults_to_fill(empty_db):
    with get_connection(empty_db) as conn:
        export_id = record_export(
            conn, out_path="/a.xlsx", template="/t.xlsx",
            year_month="2026-04", filled=1, na=0, not_found=0,
        )
        row = conn.execute(
            "SELECT kind FROM export_history WHERE id = ?", (export_id,)
        ).fetchone()
    assert row["kind"] == "fill"


def test_list_recent_exports_includes_kind(empty_db):
    with get_connection(empty_db) as conn:
        record_export(
            conn, out_path="/a.xlsx", template="-", year_month="2026-04",
            filled=1, na=0, not_found=0, kind="generate_bulanan",
        )
        rows = list_recent_exports(conn)
    assert rows[0]["kind"] == "generate_bulanan"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `../../../.venv/Scripts/python.exe -m pytest tests/test_export_history.py -k kind -v`
Expected: FAIL (`record_export` has no `kind` parameter).

- [ ] **Step 3: Add the `kind` parameter**

In `src/db/export_history.py`, change `record_export`'s signature and INSERT:

```python
def record_export(
    conn: sqlite3.Connection,
    *,
    out_path: str,
    template: str,
    year_month: str,
    filled: int,
    na: int,
    not_found: int,
    kind: str = "fill",
    created_at: str | None = None,
) -> int:
    """Insert a row for a completed export. Returns the new row id.

    kind: 'fill' (Export mode), 'generate_bulanan', or 'generate_mingguan'.
    ...
    """
    from datetime import datetime, timezone
    if created_at is None:
        created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    cur = conn.execute(
        """
        INSERT INTO export_history
            (out_path, template, year_month, filled, na, not_found, kind, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (out_path, template, year_month, filled, na, not_found, kind, created_at),
    )
    return cur.lastrowid
```

And add `kind` to `list_recent_exports`'s SELECT:

```python
        SELECT id, out_path, template, year_month, filled, na, not_found,
               kind, created_at
        FROM export_history
        ORDER BY created_at DESC, id DESC
        LIMIT ?
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `../../../.venv/Scripts/python.exe -m pytest tests/test_export_history.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add src/db/export_history.py tests/test_export_history.py
git commit -m "feat(db): export_history.record_export accepts kind"
```

---

## Task 12: Hari Libur screen — `src/ui/screens/holiday.py`

**Files:**
- Create: `src/ui/screens/holiday.py`
- Test: `tests/test_holiday_screen.py`

- [ ] **Step 1: Write the failing smoke tests**

Create `tests/test_holiday_screen.py`:

```python
"""Smoke test for the Hari Libur screen — constructs without error against
a temp DB. Deep behaviour is covered by tests/test_holidays_db.py."""
import pytest
import customtkinter as ctk

from src.db.schema import init_db
from src.db.connection import get_connection
from src.db.employees import upsert_employee
from src.db.attendance import upsert_attendance
from src.db.settings import set_setting
from src.db.holidays import mark_holidays


@pytest.fixture(scope="module")
def tk_root():
    root = ctk.CTk()
    root.withdraw()
    yield root
    root.destroy()


def test_holiday_screen_constructs(temp_db_path, monkeypatch, tk_root):
    import src.ui.screens.holiday as holiday_mod
    monkeypatch.setattr(holiday_mod, "DB_PATH", temp_db_path)
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        a = upsert_employee(conn, no_staff="1", nama="ANDI", dept="X")
        upsert_attendance(
            conn, employee_id=a, tanggal="2026-04-01", hari="Senin",
            tipe="Hari Kerja", jadwal="08.00 - 16.00", masuk="08.05",
            keluar="16.00", kerja_jam=8.0, lembur_jam=None,
            terlambat_menit=5, has_issue=0, imported_from="W1.xls",
        )
        upsert_attendance(
            conn, employee_id=a, tanggal="2026-04-03", hari="Jumat",
            tipe="Hari Kerja", jadwal="08.00 - 16.00", masuk=None,
            keluar=None, kerja_jam=None, lembur_jam=None,
            terlambat_menit=None, has_issue=1, imported_from="W1.xls",
        )
        set_setting(conn, "current_month", "2026-04")
        mark_holidays(conn, ["2026-04-03"])
        conn.commit()
    screen = holiday_mod.HolidayScreen(tk_root)
    tk_root.update_idletasks()
    assert screen is not None
    screen.destroy()


def test_holiday_screen_constructs_no_active_month(temp_db_path, monkeypatch, tk_root):
    import src.ui.screens.holiday as holiday_mod
    monkeypatch.setattr(holiday_mod, "DB_PATH", temp_db_path)
    init_db(temp_db_path)
    screen = holiday_mod.HolidayScreen(tk_root)
    tk_root.update_idletasks()
    assert screen is not None
    screen.destroy()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `../../../.venv/Scripts/python.exe -m pytest tests/test_holiday_screen.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.ui.screens.holiday'`.

- [ ] **Step 3: Create `src/ui/screens/holiday.py`**

```python
"""Hari Libur screen — mark dates in the active month as holidays.

Pola B: multi-select checkboxes + impact preview + Terapkan button.
See spec: docs/superpowers/specs/2026-05-14-hari-libur-and-weekly-export-design.md
"""
import customtkinter as ctk

from src.config import DB_PATH
from src.core.report_generator import month_label
from src.db.connection import get_connection
from src.db.settings import get_setting
from src.db.holidays import workday_roster, mark_holidays, unmark_holidays
from src.ui.components.toast import show_success_toast
from src.ui.theme import (
    COLOR_BG, COLOR_SURFACE,
    COLOR_BORDER,
    COLOR_ACCENT, COLOR_ACCENT_HOVER, COLOR_INFO, COLOR_SECONDARY,
    COLOR_TEXT, COLOR_TEXT_DIM, COLOR_TEXT_MUTED,
    FONT_DISPLAY, FONT_SUBHEAD, FONT_BODY, FONT_BODY_BOLD,
    FONT_SMALL, FONT_LABEL,
    SPACE_XS, SPACE_SM, SPACE_MD, SPACE_LG,
    RADIUS_SM, RADIUS_MD,
)

_MONTH_ID = {
    1: "Januari", 2: "Februari", 3: "Maret", 4: "April", 5: "Mei", 6: "Juni",
    7: "Juli", 8: "Agustus", 9: "September", 10: "Oktober",
    11: "November", 12: "Desember",
}

# Violet-tinted treatment for already-holiday rows (matches Outlier screen)
_HOLIDAY_BG = "#160E1C"
_HOLIDAY_BORDER = "#3A2348"


def _format_tanggal(iso: str, hari: str) -> str:
    """'2026-04-03', 'Jumat' -> 'Jumat, 3 April 2026'."""
    y, m, d = iso.split("-")
    label = f"{int(d)} {_MONTH_ID[int(m)]} {y}"
    return f"{hari}, {label}" if hari else label


class HolidayScreen(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        with get_connection(DB_PATH) as conn:
            self._month = get_setting(conn, "current_month") or ""

        # tanggal -> {"var": BooleanVar, "was_holiday": bool, "issue_count": int}
        self._rows: dict = {}

        self._build_header()
        self._build_scroll()
        self._build_footer()
        self._render()

    def _build_header(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", pady=(0, SPACE_MD))
        left = ctk.CTkFrame(header, fg_color="transparent")
        left.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(
            left, text="Hari Libur", font=FONT_DISPLAY, text_color=COLOR_TEXT,
        ).pack(anchor="w")
        ctk.CTkLabel(
            left,
            text="Tandai tanggal sebagai hari libur - tidak dihitung sebagai hari kerja",
            font=FONT_SMALL, text_color=COLOR_TEXT_DIM,
        ).pack(anchor="w", pady=(2, 0))
        if self._month:
            badge = ctk.CTkFrame(
                header, fg_color="#08222B",
                border_width=1, border_color="#12454F",
                corner_radius=RADIUS_SM,
            )
            badge.pack(side="right")
            ctk.CTkLabel(
                badge, text="BULAN AKTIF", font=FONT_LABEL, text_color="#5FB8C8",
            ).pack(anchor="e", padx=SPACE_MD, pady=(SPACE_XS, 0))
            ctk.CTkLabel(
                badge, text=month_label(self._month),
                font=FONT_BODY_BOLD, text_color=COLOR_INFO,
            ).pack(anchor="e", padx=SPACE_MD, pady=(0, SPACE_XS))

    def _build_scroll(self):
        self.scroll = ctk.CTkScrollableFrame(self, fg_color=COLOR_BG)
        self.scroll.grid(row=1, column=0, sticky="nsew")

    def _build_footer(self):
        self.footer = ctk.CTkFrame(self, fg_color="transparent")
        self.footer.grid(row=2, column=0, sticky="ew", pady=(SPACE_MD, 0))
        self._preview_label = ctk.CTkLabel(
            self.footer, text="", font=FONT_SMALL,
            text_color=COLOR_TEXT_DIM, anchor="w", justify="left",
        )
        self._preview_label.pack(side="left", fill="x", expand=True)
        self._apply_btn = ctk.CTkButton(
            self.footer, text="Terapkan Perubahan", width=180, height=34,
            fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER,
            text_color=COLOR_BG, font=FONT_BODY_BOLD,
            command=self._on_apply, state="disabled",
        )
        self._apply_btn.pack(side="right")

    def _render(self):
        for child in self.scroll.winfo_children():
            child.destroy()
        self._rows.clear()

        if not self._month:
            self._render_empty(
                "Belum ada bulan aktif.",
                "Pilih bulan di menu Active Month dulu.",
            )
            self.footer.grid_remove()
            return

        with get_connection(DB_PATH) as conn:
            roster = workday_roster(conn, self._month)

        if not roster:
            self._render_empty(
                "Belum ada data untuk bulan aktif.",
                "Import fingerprint dulu via menu Import.",
            )
            self.footer.grid_remove()
            return

        self.footer.grid()
        marked = sum(1 for r in roster if r["is_holiday"])
        self._render_infobar(marked)
        for r in roster:
            self._render_row(r)
        self._update_preview()

    def _render_empty(self, title: str, hint: str):
        box = ctk.CTkFrame(
            self.scroll, fg_color=COLOR_SURFACE,
            border_width=1, border_color=COLOR_BORDER, corner_radius=RADIUS_MD,
        )
        box.pack(fill="x", pady=SPACE_SM, padx=SPACE_XS)
        ctk.CTkLabel(box, text=title, font=FONT_SUBHEAD, text_color=COLOR_TEXT).pack(
            anchor="w", padx=SPACE_LG, pady=(SPACE_LG, SPACE_XS))
        ctk.CTkLabel(box, text=hint, font=FONT_SMALL, text_color=COLOR_TEXT_DIM).pack(
            anchor="w", padx=SPACE_LG, pady=(0, SPACE_LG))

    def _render_infobar(self, marked_count: int):
        bar = ctk.CTkFrame(
            self.scroll, fg_color=COLOR_SURFACE,
            border_width=1, border_color=COLOR_BORDER, corner_radius=RADIUS_MD,
        )
        bar.pack(fill="x", pady=(SPACE_XS, SPACE_MD), padx=SPACE_XS)
        msg = (
            f"{marked_count} hari libur ditandai bulan ini. Hari libur tidak "
            f"dihitung sebagai hari kerja - issue karyawan di tanggal itu "
            f"otomatis ter-resolve & keluar dari recap Dashboard + cetak."
        )
        ctk.CTkLabel(
            bar, text=msg, font=FONT_SMALL, text_color=COLOR_TEXT_DIM,
            wraplength=720, justify="left", anchor="w",
        ).pack(anchor="w", fill="x", padx=SPACE_MD, pady=SPACE_SM)

    def _render_row(self, r: dict):
        tanggal = r["tanggal"]
        is_holiday = r["is_holiday"]
        card = ctk.CTkFrame(
            self.scroll,
            fg_color=_HOLIDAY_BG if is_holiday else COLOR_SURFACE,
            border_width=1,
            border_color=_HOLIDAY_BORDER if is_holiday else COLOR_BORDER,
            corner_radius=RADIUS_MD,
        )
        card.pack(fill="x", pady=2, padx=SPACE_XS)

        var = ctk.BooleanVar(value=is_holiday)
        chk = ctk.CTkCheckBox(
            card, text="", width=24, variable=var,
            command=self._update_preview,
            fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER,
        )
        chk.pack(side="left", padx=(SPACE_MD, SPACE_SM), pady=SPACE_SM)

        ctk.CTkLabel(
            card, text=_format_tanggal(tanggal, r["hari"]),
            font=FONT_BODY, text_color=COLOR_TEXT, anchor="w",
        ).pack(side="left", fill="x", expand=True, pady=SPACE_SM)

        if is_holiday:
            ctk.CTkLabel(
                card, text="SUDAH LIBUR", font=FONT_LABEL,
                text_color=COLOR_SECONDARY,
            ).pack(side="right", padx=SPACE_MD, pady=SPACE_SM)

        self._rows[tanggal] = {
            "var": var,
            "was_holiday": is_holiday,
            "issue_count": r["issue_count"],
        }

    def _compute_diff(self):
        """Return (to_mark, to_unmark) date lists from current checkbox state."""
        to_mark, to_unmark = [], []
        for tanggal, st in self._rows.items():
            checked = st["var"].get()
            if checked and not st["was_holiday"]:
                to_mark.append(tanggal)
            elif not checked and st["was_holiday"]:
                to_unmark.append(tanggal)
        return to_mark, to_unmark

    def _update_preview(self):
        to_mark, to_unmark = self._compute_diff()
        parts = []
        if to_mark:
            issues = sum(self._rows[d]["issue_count"] for d in to_mark)
            parts.append(
                f"{len(to_mark)} tanggal jadi libur - {issues} issue akan ter-resolve"
            )
        if to_unmark:
            issues = sum(self._rows[d]["issue_count"] for d in to_unmark)
            parts.append(
                f"{len(to_unmark)} tanggal dibuka kembali - {issues} issue dibuka lagi"
            )
        if parts:
            self._preview_label.configure(text="   |   ".join(parts))
            self._apply_btn.configure(state="normal")
        else:
            self._preview_label.configure(text="Belum ada perubahan.")
            self._apply_btn.configure(state="disabled")

    def _on_apply(self):
        to_mark, to_unmark = self._compute_diff()
        if not to_mark and not to_unmark:
            return
        with get_connection(DB_PATH) as conn:
            if to_mark:
                mark_holidays(conn, to_mark)
            if to_unmark:
                unmark_holidays(conn, to_unmark)
            conn.commit()
        show_success_toast(
            self.winfo_toplevel(),
            title="Hari Libur Diperbarui",
            message=(
                f"{len(to_mark)} tanggal ditandai libur, "
                f"{len(to_unmark)} dibuka kembali."
            ),
        )
        self._render()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `../../../.venv/Scripts/python.exe -m pytest tests/test_holiday_screen.py -v`
Expected: 2 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/ui/screens/holiday.py tests/test_holiday_screen.py
git commit -m "feat(ui): Hari Libur screen — multi-select date marking"
```

---

## Task 13: `app.py` — sidebar wiring + tightening (opsi A)

**Files:**
- Modify: `src/ui/app.py`

Pure UI wiring + layout. Verified by full-suite regression + manual smoke (no isolated unit test — `HRApp` is the Tk root and cannot be re-instantiated across tests).

- [ ] **Step 1: Add the Hari Libur nav item**

In `src/ui/app.py`, in `_build_sidebar`, in the `nav_groups` list, change the `EXCEPTIONAL CASE` group to:

```python
            ("EXCEPTIONAL CASE", [
                ("🔸", "Outlier", "Outlier"),
                ("🌴", "Hari Libur", "Holiday"),
            ]),
```

- [ ] **Step 2: Add the `_show` branch**

In `_show`, after the `elif name == "Outlier":` block, add:

```python
        elif name == "Holiday":
            from src.ui.screens.holiday import HolidayScreen
            HolidayScreen(self.content).grid(row=0, column=0, sticky="nsew")
```

- [ ] **Step 3: Tighten nav item height**

In `_build_nav_item`, change the frame height:

```python
        frame = ctk.CTkFrame(self.sidebar, fg_color="transparent", height=32)
```

- [ ] **Step 4: Tighten section-label padding**

In `_build_sidebar`, in the `for group_label, items in nav_groups:` loop, change the section label's `.pack(...)`:

```python
            ctk.CTkLabel(
                self.sidebar,
                text=group_label,
                font=FONT_LABEL,
                text_color=COLOR_TEXT_DISABLED,
                anchor="w",
            ).pack(fill="x", padx=SPACE_LG, pady=(SPACE_XS, 2))
```

- [ ] **Step 5: Compact the footer to 2 lines**

In `_build_sidebar`, replace the footer block (from `footer = ctk.CTkFrame(...)` through the tagline `ctk.CTkLabel(...).pack(fill="x")`) with:

```python
        footer = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        footer.pack(side="bottom", fill="x", padx=8, pady=(SPACE_SM, 10))

        sep = ctk.CTkFrame(footer, fg_color=COLOR_BORDER, height=1)
        sep.pack(fill="x", pady=(0, SPACE_SM))

        # Brand — single horizontal row: "Josaphat Tech" white + "Solution" magenta
        brand_row = ctk.CTkFrame(footer, fg_color="transparent")
        brand_row.pack(fill="x")
        ctk.CTkLabel(
            brand_row, text=brand_line1, font=(FONT_FAMILY, 12, "bold"),
            text_color=COLOR_TEXT,
        ).pack(side="left")
        if brand_line2:
            ctk.CTkLabel(
                brand_row, text=f" {brand_line2}",
                font=(FONT_FAMILY, 12, "bold"), text_color=COLOR_ACCENT,
            ).pack(side="left")

        # Version + tagline — single mono line
        ctk.CTkLabel(
            footer,
            text=f"v{APP_VERSION} · {APP_TAGLINE.rstrip('.').lower()}",
            font=("Consolas", 8), text_color=COLOR_TEXT_DIM, anchor="w",
        ).pack(fill="x", pady=(2, 0))
```

(The `brand_line1` / `brand_line2` / `APP_VERSION` / `APP_TAGLINE` variables are already computed just above the original footer block — keep that part.)

- [ ] **Step 6: Run the full suite to confirm nothing regressed**

Run: `../../../.venv/Scripts/python.exe -m pytest -q`
Expected: same count as after Task 12, all PASS.

- [ ] **Step 7: Manual smoke**

Launch the app (`../../../.venv/Scripts/python.exe -m src.main` from the worktree root). Confirm: sidebar shows 🌴 Hari Libur under EXCEPTIONAL CASE; clicking it opens the screen; all menus visible without clipping at the maximized window size.

- [ ] **Step 8: Commit**

```bash
git add src/ui/app.py
git commit -m "feat(ui): wire Hari Libur into sidebar + tighten layout (opsi A)"
```

---

## Task 14: `export.py` — mode toggle + Export mode + Generate>Bulanan

**Files:**
- Modify: `src/ui/screens/export.py`
- Test: `tests/test_export_screen.py` (create)

This restructures `ExportScreen` so two persistent panels (`_export_panel`, `_generate_panel`) are built once and shown/hidden via pack — no destroy/rebuild, so the Export-mode file selection survives mode switches. Generate mode in this task supports **Bulanan** (moved from Active Month). Mingguan is added in Task 15.

- [ ] **Step 1: Write the failing smoke test**

Create `tests/test_export_screen.py`:

```python
"""Smoke test for the restructured Export screen."""
import pytest
import customtkinter as ctk

from src.db.schema import init_db
from src.db.connection import get_connection
from src.db.employees import upsert_employee
from src.db.attendance import upsert_attendance
from src.db.settings import set_setting


@pytest.fixture(scope="module")
def tk_root():
    root = ctk.CTk()
    root.withdraw()
    yield root
    root.destroy()


def test_export_screen_constructs_with_modes(temp_db_path, monkeypatch, tk_root):
    import src.ui.screens.export as export_mod
    monkeypatch.setattr(export_mod, "DB_PATH", temp_db_path)
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        a = upsert_employee(conn, no_staff="1", nama="ANDI", dept="X")
        upsert_attendance(
            conn, employee_id=a, tanggal="2026-04-01", hari="Senin",
            tipe="Hari Kerja", jadwal="08.00 - 16.00", masuk="08.05",
            keluar="16.00", kerja_jam=8.0, lembur_jam=None,
            terlambat_menit=5, has_issue=0, imported_from="W1.xls",
        )
        set_setting(conn, "current_month", "2026-04")
        conn.commit()
    screen = export_mod.ExportScreen(tk_root)
    tk_root.update_idletasks()
    # both modes switchable without error
    screen._show_mode("generate")
    tk_root.update_idletasks()
    screen._show_mode("export")
    tk_root.update_idletasks()
    assert screen is not None
    screen.destroy()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `../../../.venv/Scripts/python.exe -m pytest tests/test_export_screen.py -v`
Expected: FAIL with `AttributeError: 'ExportScreen' object has no attribute '_show_mode'`.

- [ ] **Step 3: Add imports**

In `src/ui/screens/export.py`, add to the imports near the top (alongside the existing `src.core` / `src.db` imports):

```python
from src.core.report_generator import generate_monthly_report, month_label
from src.db.attendance import list_months_with_stats
from src.ui.components.toast import show_success_toast
```

- [ ] **Step 4: Replace `__init__` and `_build` with the mode shell**

In `src/ui/screens/export.py`, change `__init__` to:

```python
    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        self._selected: Path | None = None
        self._filename_mismatch = False
        self._detected_ym: str | None = None
        self._mode = "export"
        self._build_shell()
```

Rename the existing `_build` method to `_build_export_mode` and give it a `parent` parameter:

```python
    def _build_export_mode(self, parent):
```

Inside `_build_export_mode`, **delete** the header label block (the first `ctk.CTkLabel(self, text="Export Laporan Bulanan", ...)` — the header now lives in `_build_shell`). Then change every widget that was parented to `self` so it is parented to `parent` instead:
- `self.banner = ctk.CTkFrame(self, ...)` → `ctk.CTkFrame(parent, ...)`
- `self.save_dest_frame = self._build_save_destination()` → `self._build_save_destination(parent)`
- `self.picker_zone = self._build_picker_zone()` → `self._build_picker_zone(parent)`
- `self.chip_frame = ctk.CTkFrame(self, ...)` → `ctk.CTkFrame(parent, ...)`
- `self.preview_frame = ctk.CTkFrame(self, ...)` → `ctk.CTkFrame(parent, ...)`
- `self.result_frame = ctk.CTkFrame(self, ...)` → `ctk.CTkFrame(parent, ...)`
- `self.history_frame = ctk.CTkFrame(self, ...)` → `ctk.CTkFrame(parent, ...)`

Update the two helper methods to take `parent`:
- `def _build_picker_zone(self):` → `def _build_picker_zone(self, parent):`, and inside it `zone = ctk.CTkFrame(self, ...)` → `ctk.CTkFrame(parent, ...)`
- `def _build_save_destination(self):` → `def _build_save_destination(self, parent):`, and inside it `frame = ctk.CTkFrame(self, ...)` → `ctk.CTkFrame(parent, ...)`

In `_show_chip`, the line `self.chip_frame.pack(fill="x", pady=(0, SPACE_MD), before=self.preview_frame)` stays as-is (both are children of `parent` now — `before=` still works).

Then add the new shell methods:

```python
    def _build_shell(self):
        ctk.CTkLabel(
            self, text="Export", font=FONT_DISPLAY, text_color=COLOR_TEXT,
        ).pack(anchor="w", pady=(0, SPACE_MD))

        toggle = ctk.CTkFrame(self, fg_color="transparent")
        toggle.pack(anchor="w", pady=(0, SPACE_XS))
        self._mode_btns = {}
        for mode, label in (("export", "📤 Export"), ("generate", "⚙ Generate")):
            btn = ctk.CTkButton(
                toggle, text=label, width=150, height=32,
                command=lambda m=mode: self._show_mode(m),
                font=FONT_BODY_BOLD,
            )
            btn.pack(side="left", padx=(0, SPACE_XS))
            self._mode_btns[mode] = btn

        ctk.CTkLabel(
            self,
            text="Export = isi template dari atasan · Generate = buat file dari database",
            font=FONT_MONO_SMALL, text_color=COLOR_TEXT_MUTED,
        ).pack(anchor="w", pady=(0, SPACE_MD))

        self._export_panel = ctk.CTkFrame(self, fg_color="transparent")
        self._generate_panel = ctk.CTkFrame(self, fg_color="transparent")
        self._build_export_mode(self._export_panel)
        self._build_generate_mode(self._generate_panel)
        self._show_mode("export")

    def _show_mode(self, mode):
        self._mode = mode
        for m, btn in self._mode_btns.items():
            if m == mode:
                btn.configure(
                    fg_color=COLOR_ACCENT, text_color=COLOR_BG,
                    hover_color=COLOR_ACCENT_HOVER,
                )
            else:
                btn.configure(
                    fg_color=COLOR_SURFACE, text_color=COLOR_TEXT_DIM,
                    hover_color=COLOR_SURFACE_HIGH,
                )
        self._export_panel.pack_forget()
        self._generate_panel.pack_forget()
        panel = self._export_panel if mode == "export" else self._generate_panel
        panel.pack(fill="both", expand=True)

    def _build_generate_mode(self, parent):
        """Generate mode — build a report from the database. Bulanan only;
        Mingguan is added in Task 15."""
        ctk.CTkLabel(
            parent,
            text="Buat file laporan dari database - tidak perlu template",
            font=FONT_SMALL, text_color=COLOR_TEXT_DIM,
        ).pack(anchor="w", pady=(0, SPACE_MD))

        ctk.CTkLabel(
            parent, text="PILIH BULAN", font=FONT_LABEL,
            text_color=COLOR_TEXT_MUTED,
        ).pack(anchor="w", padx=SPACE_XS)

        with get_connection(DB_PATH) as conn:
            months = [r["year_month"] for r in list_months_with_stats(conn)]
            active = get_setting(conn, "current_month") or ""

        if not months:
            ctk.CTkLabel(
                parent, text="(belum ada data bulan - import fingerprint dulu)",
                font=FONT_BODY, text_color=COLOR_TEXT_MUTED,
            ).pack(anchor="w", padx=SPACE_XS, pady=SPACE_SM)
            return

        labels = [month_label(m) for m in months]
        self._gen_month_map = dict(zip(labels, months))
        default_label = month_label(active) if active in months else labels[0]
        self._gen_month_var = ctk.StringVar(value=default_label)
        ctk.CTkOptionMenu(
            parent, values=labels, variable=self._gen_month_var, width=280,
            font=FONT_BODY, fg_color=COLOR_SURFACE_HIGH,
            button_color=COLOR_BORDER, button_hover_color=COLOR_BORDER_STRONG,
            text_color=COLOR_TEXT,
        ).pack(anchor="w", padx=SPACE_XS, pady=(SPACE_XS, SPACE_MD))

        ctk.CTkButton(
            parent, text="⚙ Generate Laporan Bulanan", height=36,
            fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER,
            text_color=COLOR_BG, font=FONT_BODY_BOLD,
            command=self._on_generate_bulanan,
        ).pack(anchor="w", padx=SPACE_XS)

    def _on_generate_bulanan(self):
        year_month = self._gen_month_map[self._gen_month_var.get()]
        default_name = f"Laporan Bulanan {month_label(year_month)} [Auto Filled].xlsx"
        out_path = filedialog.asksaveasfilename(
            defaultextension=".xlsx", initialfile=default_name,
            filetypes=[("Excel files", "*.xlsx")],
            title=f"Simpan Laporan {month_label(year_month)}",
        )
        if not out_path:
            return
        try:
            with get_connection(DB_PATH) as conn:
                summary = generate_monthly_report(
                    conn, year_month=year_month, out_path=Path(out_path),
                )
                record_export(
                    conn, out_path=str(out_path), template="-",
                    year_month=year_month, filled=summary.rows_generated,
                    na=summary.na_count, not_found=0, kind="generate_bulanan",
                )
        except Exception as e:
            messagebox.showerror(
                "Error generate laporan", f"Tidak bisa generate file:\n{e}",
            )
            return
        show_success_toast(
            self.winfo_toplevel(), title="Laporan Berhasil Dibuat",
            message=(
                f"Laporan Bulanan {month_label(year_month)} disimpan.\n"
                f"{summary.rows_generated} baris · {summary.na_count} NA"
            ),
        )
```

- [ ] **Step 5: Run test to verify it passes**

Run: `../../../.venv/Scripts/python.exe -m pytest tests/test_export_screen.py -v`
Expected: PASS.

- [ ] **Step 6: Run the full suite + manual smoke**

Run: `../../../.venv/Scripts/python.exe -m pytest -q` — same count as Task 13, all PASS.
Manual: launch app → Export screen → toggle Export/Generate; in Export mode pick a template (old flow works); in Generate mode pick a month + Generate Laporan Bulanan.

- [ ] **Step 7: Commit**

```bash
git add src/ui/screens/export.py tests/test_export_screen.py
git commit -m "feat(ui): Export screen mode toggle + Generate Bulanan"
```

---

## Task 15: `export.py` — Generate>Mingguan sub-mode

**Files:**
- Modify: `src/ui/screens/export.py`
- Test: `tests/test_export_screen.py`

Adds a `Bulanan | Mingguan` sub-toggle to Generate mode. The Bulanan UI from Task 14 moves into `_build_gen_bulanan`; `_build_gen_mingguan` is new.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_export_screen.py`:

```python
def test_export_screen_generate_has_mingguan_submode(temp_db_path, monkeypatch, tk_root):
    import src.ui.screens.export as export_mod
    monkeypatch.setattr(export_mod, "DB_PATH", temp_db_path)
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        a = upsert_employee(conn, no_staff="1", nama="ANDI", dept="X")
        upsert_attendance(
            conn, employee_id=a, tanggal="2026-04-07", hari="Selasa",
            tipe="Hari Kerja", jadwal="08.00 - 16.00", masuk="08.05",
            keluar="16.00", kerja_jam=8.0, lembur_jam=None,
            terlambat_menit=5, has_issue=0, imported_from="W1.xls",
        )
        set_setting(conn, "current_month", "2026-04")
        conn.commit()
    screen = export_mod.ExportScreen(tk_root)
    screen._show_mode("generate")
    screen._show_gen_sub("mingguan")
    tk_root.update_idletasks()
    screen._show_gen_sub("bulanan")
    tk_root.update_idletasks()
    assert screen is not None
    screen.destroy()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `../../../.venv/Scripts/python.exe -m pytest tests/test_export_screen.py -k mingguan -v`
Expected: FAIL with `AttributeError: 'ExportScreen' object has no attribute '_show_gen_sub'`.

- [ ] **Step 3: Add imports**

In `src/ui/screens/export.py`, add:

```python
from src.core.week_utils import weeks_in_month
from src.core.weekly_export import generate_weekly_export
```

- [ ] **Step 4: Restructure `_build_generate_mode` with a sub-toggle**

Replace the `_build_generate_mode` method (from Task 14) with:

```python
    def _build_generate_mode(self, parent):
        """Generate mode — build a report from the database. Sub-modes:
        Bulanan (whole month) and Mingguan (one week)."""
        ctk.CTkLabel(
            parent,
            text="Buat file laporan dari database - tidak perlu template",
            font=FONT_SMALL, text_color=COLOR_TEXT_DIM,
        ).pack(anchor="w", pady=(0, SPACE_MD))

        sub = ctk.CTkFrame(parent, fg_color="transparent")
        sub.pack(anchor="w", pady=(0, SPACE_MD))
        self._gen_sub = "bulanan"
        self._gen_sub_btns = {}
        for sub_mode, label in (("bulanan", "Bulanan"), ("mingguan", "Mingguan")):
            b = ctk.CTkButton(
                sub, text=label, width=120, height=30,
                command=lambda s=sub_mode: self._show_gen_sub(s),
                font=FONT_BODY_BOLD,
            )
            b.pack(side="left", padx=(0, SPACE_XS))
            self._gen_sub_btns[sub_mode] = b

        self._gen_bulanan_panel = ctk.CTkFrame(parent, fg_color="transparent")
        self._gen_mingguan_panel = ctk.CTkFrame(parent, fg_color="transparent")
        self._build_gen_bulanan(self._gen_bulanan_panel)
        self._build_gen_mingguan(self._gen_mingguan_panel)
        self._show_gen_sub("bulanan")

    def _show_gen_sub(self, sub_mode):
        self._gen_sub = sub_mode
        for s, btn in self._gen_sub_btns.items():
            if s == sub_mode:
                btn.configure(
                    fg_color=COLOR_ACCENT, text_color=COLOR_BG,
                    hover_color=COLOR_ACCENT_HOVER,
                )
            else:
                btn.configure(
                    fg_color=COLOR_SURFACE, text_color=COLOR_TEXT_DIM,
                    hover_color=COLOR_SURFACE_HIGH,
                )
        self._gen_bulanan_panel.pack_forget()
        self._gen_mingguan_panel.pack_forget()
        panel = (
            self._gen_bulanan_panel if sub_mode == "bulanan"
            else self._gen_mingguan_panel
        )
        panel.pack(fill="both", expand=True)

    def _build_gen_bulanan(self, parent):
        ctk.CTkLabel(
            parent, text="PILIH BULAN", font=FONT_LABEL,
            text_color=COLOR_TEXT_MUTED,
        ).pack(anchor="w", padx=SPACE_XS)

        with get_connection(DB_PATH) as conn:
            months = [r["year_month"] for r in list_months_with_stats(conn)]
            active = get_setting(conn, "current_month") or ""

        if not months:
            ctk.CTkLabel(
                parent, text="(belum ada data bulan - import fingerprint dulu)",
                font=FONT_BODY, text_color=COLOR_TEXT_MUTED,
            ).pack(anchor="w", padx=SPACE_XS, pady=SPACE_SM)
            return

        labels = [month_label(m) for m in months]
        self._gen_month_map = dict(zip(labels, months))
        default_label = month_label(active) if active in months else labels[0]
        self._gen_month_var = ctk.StringVar(value=default_label)
        ctk.CTkOptionMenu(
            parent, values=labels, variable=self._gen_month_var, width=280,
            font=FONT_BODY, fg_color=COLOR_SURFACE_HIGH,
            button_color=COLOR_BORDER, button_hover_color=COLOR_BORDER_STRONG,
            text_color=COLOR_TEXT,
        ).pack(anchor="w", padx=SPACE_XS, pady=(SPACE_XS, SPACE_MD))

        ctk.CTkButton(
            parent, text="⚙ Generate Laporan Bulanan", height=36,
            fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER,
            text_color=COLOR_BG, font=FONT_BODY_BOLD,
            command=self._on_generate_bulanan,
        ).pack(anchor="w", padx=SPACE_XS)

    def _build_gen_mingguan(self, parent):
        with get_connection(DB_PATH) as conn:
            active = get_setting(conn, "current_month") or ""

        if not active:
            ctk.CTkLabel(
                parent, text="(belum ada bulan aktif - pilih di Active Month dulu)",
                font=FONT_BODY, text_color=COLOR_TEXT_MUTED,
            ).pack(anchor="w", padx=SPACE_XS, pady=SPACE_SM)
            return

        self._mingguan_weeks = list(weeks_in_month(active))
        if not self._mingguan_weeks:
            ctk.CTkLabel(
                parent, text="(tidak ada minggu di bulan aktif)",
                font=FONT_BODY, text_color=COLOR_TEXT_MUTED,
            ).pack(anchor="w", padx=SPACE_XS, pady=SPACE_SM)
            return

        ctk.CTkLabel(
            parent, text=f"PILIH MINGGU - {month_label(active)}",
            font=FONT_LABEL, text_color=COLOR_TEXT_MUTED,
        ).pack(anchor="w", padx=SPACE_XS)

        week_row = ctk.CTkFrame(parent, fg_color="transparent")
        week_row.pack(anchor="w", padx=SPACE_XS, pady=(SPACE_XS, SPACE_MD))
        self._mingguan_week_btns = {}
        for (n, start, end) in self._mingguan_weeks:
            b = ctk.CTkButton(
                week_row, text=f"Minggu {n}", width=95, height=30,
                command=lambda w=(n, start, end): self._on_select_week(w),
                font=FONT_BODY,
            )
            b.pack(side="left", padx=(0, SPACE_XS))
            self._mingguan_week_btns[n] = b
        self._on_select_week(self._mingguan_weeks[0])

        ctk.CTkButton(
            parent, text="⚙ Generate Laporan Mingguan", height=36,
            fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER,
            text_color=COLOR_BG, font=FONT_BODY_BOLD,
            command=self._on_generate_mingguan,
        ).pack(anchor="w", padx=SPACE_XS)

    def _on_select_week(self, week):
        self._mingguan_sel = week
        n_sel = week[0]
        for n, btn in self._mingguan_week_btns.items():
            if n == n_sel:
                btn.configure(fg_color=COLOR_ACCENT, text_color=COLOR_BG)
            else:
                btn.configure(fg_color=COLOR_SURFACE, text_color=COLOR_TEXT_DIM)

    def _on_generate_mingguan(self):
        n, start, end = self._mingguan_sel
        default_name = f"Laporan Mingguan {start} sd {end}.xlsx"
        out_path = filedialog.asksaveasfilename(
            defaultextension=".xlsx", initialfile=default_name,
            filetypes=[("Excel files", "*.xlsx")],
            title=f"Simpan Laporan Mingguan (Minggu {n})",
        )
        if not out_path:
            return
        try:
            with get_connection(DB_PATH) as conn:
                summary = generate_weekly_export(conn, start, end, Path(out_path))
                record_export(
                    conn, out_path=str(out_path), template="-",
                    year_month=start[:7], filled=summary.rows, na=0,
                    not_found=0, kind="generate_mingguan",
                )
        except Exception as e:
            messagebox.showerror(
                "Error generate mingguan", f"Tidak bisa generate file:\n{e}",
            )
            return
        show_success_toast(
            self.winfo_toplevel(), title="Laporan Mingguan Dibuat",
            message=(
                f"Minggu {n} ({start} sd {end}) disimpan.\n"
                f"{summary.rows} baris · {summary.employees} pegawai"
            ),
        )
```

Note: `_on_generate_bulanan` from Task 14 is unchanged and stays in the class.

- [ ] **Step 5: Run tests to verify they pass**

Run: `../../../.venv/Scripts/python.exe -m pytest tests/test_export_screen.py -v`
Expected: all PASS.

- [ ] **Step 6: Manual smoke**

Launch app → Export → Generate → Mingguan → pick a week → Generate Laporan Mingguan → confirm a 12-column `.xlsx` is produced with column F = Tipe.

- [ ] **Step 7: Commit**

```bash
git add src/ui/screens/export.py tests/test_export_screen.py
git commit -m "feat(ui): Export screen Generate>Mingguan sub-mode"
```

---

## Task 16: `active_month.py` — remove the per-card Generate button

**Files:**
- Modify: `src/ui/screens/active_month.py`

Generate now lives in the Export screen (Task 14/15). Active Month returns to being purely a month picker.

- [ ] **Step 1: Remove the Generate button from `_render_card`**

In `src/ui/screens/active_month.py`, in `_render_card`, delete the entire `# Generate button: cyan secondary (both states)` block — the `ctk.CTkButton(btn_row, text="Generate", ...)` call (8 lines, including its `.pack(...)`).

- [ ] **Step 2: Remove the `_on_generate` method**

Delete the entire `_on_generate` method (the `def _on_generate(self, year_month: str):` block, ~33 lines, through the closing `)` of its `show_success_toast` call).

- [ ] **Step 3: Remove now-unused imports**

At the top of `src/ui/screens/active_month.py`, remove imports that were only used by `_on_generate`:
- `from pathlib import Path` — remove
- `from tkinter import filedialog, messagebox` — remove
- `from src.ui.components.toast import show_success_toast` — remove
- Change `from src.core.report_generator import (generate_monthly_report, month_label,)` to just `from src.core.report_generator import month_label` (`month_label` is still used by `_render_card`)

- [ ] **Step 4: Run the full suite to confirm nothing regressed**

Run: `../../../.venv/Scripts/python.exe -m pytest -q`
Expected: same count as Task 15, all PASS.

- [ ] **Step 5: Manual smoke**

Launch app → Active Month → confirm cards show only "✓ Pilih" / "✓ Sedang Aktif" (no Generate button), and picking a month still works.

- [ ] **Step 6: Commit**

```bash
git add src/ui/screens/active_month.py
git commit -m "refactor(ui): remove Generate button from Active Month (moved to Export)"
```

---

## Task 17: Full verification + build

**Files:** none (verification + build only)

- [ ] **Step 1: Run the full test suite**

Run: `../../../.venv/Scripts/python.exe -m pytest -q`
Expected: all PASS, count ≈ 195-205 (160 baseline + ~35-45 new). If any fail, fix before continuing.

- [ ] **Step 2: Manual smoke checklist**

Launch app (`../../../.venv/Scripts/python.exe -m src.main`). Verify:
- Sidebar: 🌴 Hari Libur under EXCEPTIONAL CASE; everything fits at maximized size.
- Hari Libur screen: check 2 dates → preview shows "N tanggal jadi libur - M issue akan ter-resolve" → Terapkan → toast.
- Dashboard: the marked dates' lateness is gone from the recap; print (Cetak) reflects it.
- Coaching: employees whose lateness was only on holiday dates drop off the list.
- Issues: issues on the holiday dates moved to the Resolved view (reason "Libur").
- Hari Libur screen again: uncheck a date → Terapkan → it reopens.
- Export screen: toggle Export/Generate; Export mode old flow still works; Generate → Bulanan → produces a report; Generate → Mingguan → pick a week → produces a 12-column file with F=Tipe and holiday rows showing "Hari Libur".
- Active Month: no Generate button on cards.
- Re-import a fingerprint file covering a holiday date → confirm the holiday status survives (date still excluded from recap).

- [ ] **Step 3: Build the .exe**

First confirm no running instance will block the build output in the worktree:

Run: `tasklist | grep HR-Absensi || echo "not running"`

Then build (from the worktree root):

Run: `../../../.venv/Scripts/pyinstaller.exe HR-Absensi.spec --clean --noconfirm`
Expected: build succeeds, output in the worktree's `dist/HR-Absensi/`.

- [ ] **Step 4: Report completion**

Report the final test count and build result. Do NOT deploy/rotate the `.exe` into the main project's `dist/` and do NOT push — both are separate, user-authorized steps (workflow rules: NO auto-push; deploy with rotation only on explicit "deploy" instruction).

---

## Self-Review

**Spec coverage** — every spec section maps to a task:
- §3 Data model (holidays table + hybrid) → Tasks 1, 2, 3
- §4.1 schema + migration → Task 1
- §4.2 holidays.py → Tasks 2, 3
- §4.3 "libur" reason category → Task 4
- §4.4 holiday.py screen → Task 12
- §4.5 import re-stamp → Task 9
- §5 recap exclusion (insights + coaching) → Tasks 5, 6
- §6.1 report_generator holiday rows → Task 7
- §6.2 report_filler skip → Task 8
- §7 Export screen restructure → Tasks 14, 15
- §8 weekly_export.py → Task 10
- §9.1 active_month.py → Task 16
- §9.2 export_history kind → Task 11
- §9.3 schema kind column → Task 1
- §10 sidebar opsi A → Task 13
- §14 testing + build → Task 17

**Placeholder scan** — no TBD/TODO/"implement later". UI Tasks 9, 13, 16 use full-suite regression + manual smoke instead of isolated unit tests; this is an explicit, justified strategy (one-line wiring / Tk-root layout / pure deletion), not a placeholder — the underlying logic they exercise is unit-tested in Tasks 3, 12, 7/10/11.

**Type consistency** — `mark_holidays`/`unmark_holidays` return `{"dates_marked"/"dates_unmarked", "issues_resolved"/"issues_reopened"}`; `workday_roster` rows use keys `tanggal/hari/is_holiday/issue_count` consistently across Tasks 2, 3, 12. `generate_weekly_export` returns `WeeklyExportSummary(rows, employees)` — used as `summary.rows` / `summary.employees` in Tasks 10, 15. `record_export(..., kind=...)` signature in Task 11 matches the call sites in Tasks 14, 15. `generate_monthly_report` returns `GenerateSummary(rows_generated, na_count, employees_count)` — used as `summary.rows_generated` / `summary.na_count` in Task 14.
