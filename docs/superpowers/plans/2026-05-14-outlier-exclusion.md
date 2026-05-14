# Outlier / Pengecualian Exclusion Menu — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an "Outlier / Pengecualian" menu that lets the user exclude specific employees from Dashboard + Coaching analytics, with soft-revert (history-preserving) carry-forward semantics.

**Architecture:** New `outlier_exclusions` table stores exclusion ranges (`effective_from`/`effective_until` as "YYYY-MM"). A new `src/db/outlier.py` module owns all data access. Insight functions in `src/core/insights.py` and `list_coaching_for_week` in `src/db/coaching.py` filter out excluded employees per the analyzed month. A new `src/ui/screens/outlier.py` screen manages exclusions; `src/ui/app.py` wires the sidebar entry.

**Tech Stack:** Python 3.13 · SQLite · CustomTkinter · pytest

**Spec:** [2026-05-14-outlier-exclusion-design.md](../specs/2026-05-14-outlier-exclusion-design.md)

---

## File Structure

| File | Responsibility |
|---|---|
| `src/db/schema.py` (modify) | Add `outlier_exclusions` table to DDL |
| `src/db/outlier.py` (create) | All data access: query excluded IDs, toggle exclude/revert, roster, SQL-clause helper |
| `src/core/insights.py` (modify) | 7 insight functions filter excluded employees |
| `src/db/coaching.py` (modify) | `list_coaching_for_week` filters excluded employees |
| `src/ui/screens/outlier.py` (create) | The Outlier screen (matches approved mockup) |
| `src/ui/app.py` (modify) | Sidebar "EXCEPTIONAL CASE" group + `_show()` branch |
| `tests/test_outlier_db.py` (create) | Unit tests for `src/db/outlier.py` |
| `tests/test_insights.py` (modify) | Exclusion-filter tests for insight functions |
| `tests/test_coaching_db.py` (modify) | Exclusion-filter test for `list_coaching_for_week` |
| `tests/test_schema.py` (modify) | Assert `outlier_exclusions` table exists |

---

## Task 1: Schema — add `outlier_exclusions` table

**Files:**
- Modify: `src/db/schema.py`
- Test: `tests/test_schema.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_schema.py`:

```python
def test_outlier_exclusions_table_created(temp_db_path):
    """init_db creates the outlier_exclusions table."""
    from src.db.schema import init_db
    from src.db.connection import get_connection
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        row = conn.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name='outlier_exclusions'"
        ).fetchone()
    assert row is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `../../../.venv/Scripts/python.exe -m pytest tests/test_schema.py::test_outlier_exclusions_table_created -v`
Expected: FAIL — `assert None is not None`.

- [ ] **Step 3: Add the table to the DDL**

In `src/db/schema.py`, inside the `DDL` string, add this block immediately before the closing `"""` (after the `export_history` index):

```sql

CREATE TABLE IF NOT EXISTS outlier_exclusions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id     INTEGER NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
    effective_from  TEXT    NOT NULL,
    effective_until TEXT,
    created_at      TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_outlier_employee
    ON outlier_exclusions(employee_id);
```

- [ ] **Step 4: Run test to verify it passes**

Run: `../../../.venv/Scripts/python.exe -m pytest tests/test_schema.py -v`
Expected: all PASS including the new test.

- [ ] **Step 5: Commit**

```bash
git add src/db/schema.py tests/test_schema.py
git commit -m "feat(schema): add outlier_exclusions table"
```

---

## Task 2: `src/db/outlier.py` — `excluded_employee_ids` + `exclusion_sql`

**Files:**
- Create: `src/db/outlier.py`
- Create: `tests/test_outlier_db.py`

These two are the core read primitives: which employee IDs are excluded for a given month, and a helper to build a safe `NOT IN (...)` SQL fragment.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_outlier_db.py`:

```python
"""Tests for src/db/outlier.py — Outlier exclusion data access."""
from datetime import datetime, UTC

from src.db.schema import init_db
from src.db.connection import get_connection
from src.db.employees import upsert_employee


def _emp(conn, no, nama):
    return upsert_employee(conn, no_staff=no, nama=nama, dept="X")


def _insert_exclusion(conn, employee_id, effective_from, effective_until=None):
    """Direct insert helper for tests that need to seed exclusion rows."""
    conn.execute(
        "INSERT INTO outlier_exclusions "
        "(employee_id, effective_from, effective_until, created_at) "
        "VALUES (?, ?, ?, ?)",
        (employee_id, effective_from, effective_until,
         datetime.now(UTC).isoformat(timespec="seconds")),
    )


def test_excluded_employee_ids_empty_when_no_rows(temp_db_path):
    from src.db.outlier import excluded_employee_ids
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        assert excluded_employee_ids(conn, "2026-04") == set()


def test_excluded_employee_ids_active_ongoing(temp_db_path):
    """Row with effective_until NULL is excluded for effective_from onward."""
    from src.db.outlier import excluded_employee_ids
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        a = _emp(conn, "1", "A")
        _insert_exclusion(conn, a, "2026-04", None)
        assert excluded_employee_ids(conn, "2026-03") == set()    # before
        assert excluded_employee_ids(conn, "2026-04") == {a}      # at start
        assert excluded_employee_ids(conn, "2026-09") == {a}      # forward


def test_excluded_employee_ids_closed_range(temp_db_path):
    """Row with effective_until set excludes [from, until) — until is exclusive."""
    from src.db.outlier import excluded_employee_ids
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        a = _emp(conn, "1", "A")
        _insert_exclusion(conn, a, "2026-04", "2026-06")
        assert excluded_employee_ids(conn, "2026-03") == set()    # before from
        assert excluded_employee_ids(conn, "2026-04") == {a}      # at from
        assert excluded_employee_ids(conn, "2026-05") == {a}      # inside
        assert excluded_employee_ids(conn, "2026-06") == set()    # at until (exclusive)
        assert excluded_employee_ids(conn, "2026-07") == set()    # after


def test_exclusion_sql_empty_set_is_noop(temp_db_path):
    from src.db.outlier import exclusion_sql
    frag, params = exclusion_sql(set())
    assert frag == ""
    assert params == ()


def test_exclusion_sql_builds_not_in_clause():
    from src.db.outlier import exclusion_sql
    frag, params = exclusion_sql({3, 7})
    assert frag.strip().startswith("AND employee_id NOT IN (")
    assert frag.count("?") == 2
    assert set(params) == {3, 7}


def test_exclusion_sql_custom_column():
    from src.db.outlier import exclusion_sql
    frag, _ = exclusion_sql({1}, column="e.id")
    assert "e.id NOT IN (" in frag
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `../../../.venv/Scripts/python.exe -m pytest tests/test_outlier_db.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.db.outlier'`.

- [ ] **Step 3: Create `src/db/outlier.py` with the two functions**

```python
"""Data access for the Outlier / Pengecualian feature.

An employee is "excluded" from analytics for a given analysis-month M when
there is an outlier_exclusions row where:
    effective_from <= M AND (effective_until IS NULL OR M < effective_until)

Months are "YYYY-MM" strings; string comparison works because the format
is zero-padded and lexicographic order matches chronological order.
"""
import sqlite3
from datetime import datetime, UTC
from typing import List


def excluded_employee_ids(conn: sqlite3.Connection, year_month: str) -> set:
    """Set of employee_id excluded from analytics for the given month.

    `year_month` is "YYYY-MM". Used by the insights layer and the Coaching
    data layer to drop Outlier employees from aggregations.
    """
    rows = conn.execute(
        """
        SELECT DISTINCT employee_id
          FROM outlier_exclusions
         WHERE effective_from <= ?
           AND (effective_until IS NULL OR ? < effective_until)
        """,
        (year_month, year_month),
    ).fetchall()
    return {r[0] for r in rows}


def exclusion_sql(excluded: set, column: str = "employee_id") -> tuple:
    """Build an ' AND <column> NOT IN (?,?,...)' SQL fragment + params tuple.

    Returns ('', ()) when `excluded` is empty so callers can splice it in
    unconditionally without producing invalid `NOT IN ()` SQL.
    """
    if not excluded:
        return "", ()
    placeholders = ",".join("?" for _ in excluded)
    return f" AND {column} NOT IN ({placeholders})", tuple(excluded)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `../../../.venv/Scripts/python.exe -m pytest tests/test_outlier_db.py -v`
Expected: 6 PASS.

- [ ] **Step 5: Commit**

```bash
git add src/db/outlier.py tests/test_outlier_db.py
git commit -m "feat(db): outlier excluded_employee_ids + exclusion_sql helper"
```

---

## Task 3: `src/db/outlier.py` — `exclude_employee` + `revert_employee`

**Files:**
- Modify: `src/db/outlier.py`
- Modify: `tests/test_outlier_db.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_outlier_db.py`:

```python
def _active_rows(conn, employee_id):
    return conn.execute(
        "SELECT effective_from, effective_until FROM outlier_exclusions "
        "WHERE employee_id = ? ORDER BY id",
        (employee_id,),
    ).fetchall()


def test_exclude_employee_creates_active_row(temp_db_path):
    from src.db.outlier import exclude_employee, excluded_employee_ids
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        a = _emp(conn, "1", "A")
        exclude_employee(conn, a, "2026-04")
        rows = _active_rows(conn, a)
        assert len(rows) == 1
        assert rows[0]["effective_from"] == "2026-04"
        assert rows[0]["effective_until"] is None
        assert excluded_employee_ids(conn, "2026-04") == {a}


def test_exclude_employee_noop_if_already_active(temp_db_path):
    """Excluding someone who already has an active row does nothing."""
    from src.db.outlier import exclude_employee
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        a = _emp(conn, "1", "A")
        exclude_employee(conn, a, "2026-04")
        exclude_employee(conn, a, "2026-05")  # already active — no-op
        assert len(_active_rows(conn, a)) == 1


def test_revert_employee_same_month_deletes_row(temp_db_path):
    """Revert in the same month as exclude removes the row entirely."""
    from src.db.outlier import exclude_employee, revert_employee
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        a = _emp(conn, "1", "A")
        exclude_employee(conn, a, "2026-04")
        revert_employee(conn, a, "2026-04")
        assert _active_rows(conn, a) == []


def test_revert_employee_past_month_sets_effective_until(temp_db_path):
    """Revert in a later month closes the range at the active month."""
    from src.db.outlier import (
        exclude_employee, revert_employee, excluded_employee_ids,
    )
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        a = _emp(conn, "1", "A")
        exclude_employee(conn, a, "2026-04")
        revert_employee(conn, a, "2026-06")
        rows = _active_rows(conn, a)
        assert len(rows) == 1
        assert rows[0]["effective_from"] == "2026-04"
        assert rows[0]["effective_until"] == "2026-06"
        # April + May stay excluded, June onward counted again
        assert excluded_employee_ids(conn, "2026-05") == {a}
        assert excluded_employee_ids(conn, "2026-06") == set()


def test_revert_employee_noop_if_not_excluded(temp_db_path):
    from src.db.outlier import revert_employee
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        a = _emp(conn, "1", "A")
        revert_employee(conn, a, "2026-04")  # nothing to revert — no error
        assert _active_rows(conn, a) == []


def test_re_exclude_after_revert_creates_new_row(temp_db_path):
    from src.db.outlier import exclude_employee, revert_employee
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        a = _emp(conn, "1", "A")
        exclude_employee(conn, a, "2026-04")
        revert_employee(conn, a, "2026-06")
        exclude_employee(conn, a, "2026-08")
        rows = _active_rows(conn, a)
        assert len(rows) == 2
        assert rows[1]["effective_from"] == "2026-08"
        assert rows[1]["effective_until"] is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `../../../.venv/Scripts/python.exe -m pytest tests/test_outlier_db.py -k "exclude_employee or revert_employee or re_exclude" -v`
Expected: FAIL — `ImportError: cannot import name 'exclude_employee'`.

- [ ] **Step 3: Add the two functions to `src/db/outlier.py`**

Append:

```python
def _active_row(conn: sqlite3.Connection, employee_id: int):
    """Return the single active (effective_until IS NULL) row for an
    employee, or None. Invariant: at most one active row per employee.
    """
    return conn.execute(
        "SELECT id, effective_from FROM outlier_exclusions "
        "WHERE employee_id = ? AND effective_until IS NULL",
        (employee_id,),
    ).fetchone()


def exclude_employee(
    conn: sqlite3.Connection, employee_id: int, active_month: str
) -> None:
    """Exclude an employee starting from `active_month` ("YYYY-MM").

    No-op if the employee already has an active exclusion row.
    """
    if _active_row(conn, employee_id) is not None:
        return
    conn.execute(
        "INSERT INTO outlier_exclusions "
        "(employee_id, effective_from, effective_until, created_at) "
        "VALUES (?, ?, NULL, ?)",
        (employee_id, active_month,
         datetime.now(UTC).isoformat(timespec="seconds")),
    )


def revert_employee(
    conn: sqlite3.Connection, employee_id: int, active_month: str
) -> None:
    """Stop excluding an employee, effective from `active_month` onward.

    Soft revert (history-preserving):
      - if the active row started in `active_month` → DELETE it (empty range)
      - otherwise → set effective_until = active_month (past months stay excluded)
      - no active row → no-op
    """
    row = _active_row(conn, employee_id)
    if row is None:
        return
    if row["effective_from"] == active_month:
        conn.execute(
            "DELETE FROM outlier_exclusions WHERE id = ?", (row["id"],)
        )
    else:
        conn.execute(
            "UPDATE outlier_exclusions SET effective_until = ? WHERE id = ?",
            (active_month, row["id"]),
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `../../../.venv/Scripts/python.exe -m pytest tests/test_outlier_db.py -v`
Expected: all PASS (12 total now).

- [ ] **Step 5: Commit**

```bash
git add src/db/outlier.py tests/test_outlier_db.py
git commit -m "feat(db): outlier exclude_employee + revert_employee (soft revert)"
```

---

## Task 4: `src/db/outlier.py` — `revert_all`, `list_active_exclusions`, `month_roster`

**Files:**
- Modify: `src/db/outlier.py`
- Modify: `tests/test_outlier_db.py`

These three feed the Outlier screen UI.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_outlier_db.py`:

```python
def _att(conn, emp_id, tanggal):
    from src.db.attendance import upsert_attendance
    upsert_attendance(
        conn, employee_id=emp_id, tanggal=tanggal, hari="Senin",
        tipe="Hari Kerja", jadwal="08.00 - 16.00",
        masuk="08.05", keluar="16.00", kerja_jam=8.0,
        lembur_jam=None, terlambat_menit=5, has_issue=0,
        imported_from="W1.xls",
    )


def test_revert_all_closes_every_active_row(temp_db_path):
    from src.db.outlier import exclude_employee, revert_all, excluded_employee_ids
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        a = _emp(conn, "1", "A")
        b = _emp(conn, "2", "B")
        exclude_employee(conn, a, "2026-04")
        exclude_employee(conn, b, "2026-04")
        count = revert_all(conn, "2026-06")
        assert count == 2
        assert excluded_employee_ids(conn, "2026-06") == set()


def test_revert_all_returns_zero_when_nothing_active(temp_db_path):
    from src.db.outlier import revert_all
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        assert revert_all(conn, "2026-04") == 0


def test_list_active_exclusions_returns_employee_detail(temp_db_path):
    from src.db.outlier import exclude_employee, list_active_exclusions
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        a = _emp(conn, "1", "ALICE")
        _emp(conn, "2", "BOB")  # not excluded
        exclude_employee(conn, a, "2026-04")
        rows = list_active_exclusions(conn)
        assert len(rows) == 1
        assert rows[0]["employee_id"] == a
        assert rows[0]["nama"] == "ALICE"
        assert rows[0]["effective_from"] == "2026-04"


def test_month_roster_lists_employees_with_attendance_in_month(temp_db_path):
    from src.db.outlier import month_roster
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        a = _emp(conn, "1", "ALICE")
        b = _emp(conn, "2", "BOB")
        _emp(conn, "3", "CAROL")  # no attendance — should not appear
        _att(conn, a, "2026-04-01")
        _att(conn, b, "2026-04-02")
        _att(conn, a, "2026-05-01")  # also in May
        roster = month_roster(conn, "2026-04")
        names = [r["nama"] for r in roster]
        assert names == ["ALICE", "BOB"]  # sorted by nama, CAROL absent
        may = month_roster(conn, "2026-05")
        assert [r["nama"] for r in may] == ["ALICE"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `../../../.venv/Scripts/python.exe -m pytest tests/test_outlier_db.py -k "revert_all or list_active or month_roster" -v`
Expected: FAIL — `ImportError: cannot import name 'revert_all'`.

- [ ] **Step 3: Add the three functions to `src/db/outlier.py`**

Append:

```python
def revert_all(conn: sqlite3.Connection, active_month: str) -> int:
    """Revert every currently-active exclusion. Returns count reverted."""
    active = conn.execute(
        "SELECT employee_id FROM outlier_exclusions WHERE effective_until IS NULL"
    ).fetchall()
    for r in active:
        revert_employee(conn, r["employee_id"], active_month)
    return len(active)


def list_active_exclusions(conn: sqlite3.Connection) -> List[dict]:
    """All currently-active exclusions joined with employee detail.

    Each dict: employee_id, nama, dept, effective_from. Sorted by nama.
    Feeds the "Dikecualikan" section of the Outlier screen.
    """
    rows = conn.execute(
        """
        SELECT ox.employee_id, e.nama, e.dept, ox.effective_from
          FROM outlier_exclusions ox
          JOIN employees e ON ox.employee_id = e.id
         WHERE ox.effective_until IS NULL
         ORDER BY e.nama ASC
        """
    ).fetchall()
    return [
        {
            "employee_id": r["employee_id"],
            "nama": r["nama"],
            "dept": r["dept"] or "",
            "effective_from": r["effective_from"],
        }
        for r in rows
    ]


def month_roster(conn: sqlite3.Connection, year_month: str) -> List[dict]:
    """Employees who have an attendance record in the given month.

    Each dict: id, nama, dept. Sorted by nama. Feeds the Outlier screen list.
    """
    rows = conn.execute(
        """
        SELECT DISTINCT e.id, e.nama, e.dept
          FROM attendance_records ar
          JOIN employees e ON ar.employee_id = e.id
         WHERE substr(ar.tanggal, 1, 7) = ?
         ORDER BY e.nama ASC
        """,
        (year_month,),
    ).fetchall()
    return [
        {"id": r["id"], "nama": r["nama"], "dept": r["dept"] or ""}
        for r in rows
    ]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `../../../.venv/Scripts/python.exe -m pytest tests/test_outlier_db.py -v`
Expected: all PASS (16 total now).

- [ ] **Step 5: Commit**

```bash
git add src/db/outlier.py tests/test_outlier_db.py
git commit -m "feat(db): outlier revert_all + list_active_exclusions + month_roster"
```

---

## Task 5: `insights.py` — filter `terlambat_ranking`

**Files:**
- Modify: `src/core/insights.py`
- Modify: `tests/test_insights.py`

`terlambat_ranking` is per-employee aggregation, so excluded employees can be dropped Python-side from the result rows. `top_n_terlambat` and `coaching_flag` derive from it — they inherit the filter automatically.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_insights.py`:

```python
def test_terlambat_ranking_drops_excluded_employees(temp_db_path):
    """Employees excluded via the Outlier menu are absent from the ranking."""
    from src.db.outlier import exclude_employee
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        a = _add_emp(conn, "1", "ANDI")
        b = _add_emp(conn, "2", "BUDI")
        _add_att(conn, a, "2026-04-01", "Senin", "08.50", "16.00", 50)
        _add_att(conn, b, "2026-04-01", "Senin", "08.40", "16.00", 40)
        exclude_employee(conn, a, "2026-04")  # ANDI excluded from April onward

        names = [r["nama"] for r in terlambat_ranking(conn, "2026-04-01", "2026-04-30")]
        assert "ANDI" not in names
        assert "BUDI" in names


def test_terlambat_ranking_exclusion_cascades_to_coaching_flag(temp_db_path):
    """coaching_flag derives from terlambat_ranking — excluded emp drop too."""
    from src.db.outlier import exclude_employee
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        a = _add_emp(conn, "1", "ANDI")
        _add_att(conn, a, "2026-04-01", "Senin", "09.40", "16.00", 100)  # over threshold
        exclude_employee(conn, a, "2026-04")
        flagged = coaching_flag(conn, "2026-04-01", "2026-04-30", threshold=75)
        assert [r["nama"] for r in flagged] == []


def test_terlambat_ranking_exclusion_respects_month(temp_db_path):
    """Exclusion effective from April does not affect March analysis."""
    from src.db.outlier import exclude_employee
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        a = _add_emp(conn, "1", "ANDI")
        _add_att(conn, a, "2026-03-02", "Senin", "08.50", "16.00", 50)
        _add_att(conn, a, "2026-04-01", "Rabu", "08.50", "16.00", 50)
        exclude_employee(conn, a, "2026-04")
        mar = [r["nama"] for r in terlambat_ranking(conn, "2026-03-01", "2026-03-31")]
        apr = [r["nama"] for r in terlambat_ranking(conn, "2026-04-01", "2026-04-30")]
        assert "ANDI" in mar   # March unaffected
        assert "ANDI" not in apr  # April excluded
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `../../../.venv/Scripts/python.exe -m pytest tests/test_insights.py -k "excluded or exclusion" -v`
Expected: FAIL — `ANDI` still present in ranking.

- [ ] **Step 3: Add the filter to `terlambat_ranking`**

In `src/core/insights.py`, add the import at the top (after the existing `from src.config import COACHING_EXCLUDED`):

```python
from src.db.outlier import excluded_employee_ids, exclusion_sql
```

Then in `terlambat_ranking`, find this line:

```python
    rows = conn.execute(sql, params).fetchall()
```

and insert immediately after it:

```python
    # Drop employees excluded via the Outlier menu for this period's month
    excluded = excluded_employee_ids(conn, start[:7])
    if excluded:
        rows = [r for r in rows if r["id"] not in excluded]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `../../../.venv/Scripts/python.exe -m pytest tests/test_insights.py -v`
Expected: all PASS — new exclusion tests pass, all pre-existing tests still pass (no regression — when there are no exclusions, `excluded` is empty and the filter is a no-op).

- [ ] **Step 5: Commit**

```bash
git add src/core/insights.py tests/test_insights.py
git commit -m "feat(insights): filter excluded employees from terlambat_ranking"
```

---

## Task 6: `insights.py` — filter `karyawan_teladan` + `karyawan_teladan_top_n`

**Files:**
- Modify: `src/core/insights.py`
- Modify: `tests/test_insights.py`

These query with `GROUP BY e.id` then `LIMIT` — filtering must happen in SQL (`AND e.id NOT IN (...)`) before grouping, not after.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_insights.py`:

```python
def test_karyawan_teladan_excludes_outlier(temp_db_path):
    """An excluded employee cannot win Teladan even with a perfect record."""
    from src.db.outlier import exclude_employee
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        a = _add_emp(conn, "1", "PERFECT")
        b = _add_emp(conn, "2", "OKAY")
        # PERFECT: 3 clean days (best score)
        for d in ("2026-04-01", "2026-04-02", "2026-04-03"):
            _add_att(conn, a, d, "Senin", "07.55", "16.00", 0)
        # OKAY: 3 slightly-late days
        for d in ("2026-04-01", "2026-04-02", "2026-04-03"):
            _add_att(conn, b, d, "Senin", "08.10", "16.00", 10)
        exclude_employee(conn, a, "2026-04")

        winner = karyawan_teladan(conn, "2026-04-01", "2026-04-30")
        assert winner["nama"] == "OKAY"  # PERFECT excluded

        top = karyawan_teladan_top_n(conn, "2026-04-01", "2026-04-30", n=None)
        assert "PERFECT" not in [r["nama"] for r in top]


def test_karyawan_teladan_no_exclusion_unchanged(temp_db_path):
    """With no exclusions, Teladan behaves exactly as before."""
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        a = _add_emp(conn, "1", "PERFECT")
        for d in ("2026-04-01", "2026-04-02", "2026-04-03"):
            _add_att(conn, a, d, "Senin", "07.55", "16.00", 0)
        winner = karyawan_teladan(conn, "2026-04-01", "2026-04-30")
        assert winner["nama"] == "PERFECT"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `../../../.venv/Scripts/python.exe -m pytest tests/test_insights.py -k "teladan_excludes" -v`
Expected: FAIL — `winner["nama"]` is `"PERFECT"`, expected `"OKAY"`.

- [ ] **Step 3: Add the filter to both functions**

In `src/core/insights.py`, modify `karyawan_teladan`. Find:

```python
    placeholders = ",".join("?" for _ in COACHING_EXCLUDED)
    sql = f"""
        SELECT e.id, e.nama, e.dept,
```

(the block inside `karyawan_teladan`) and change it so the `WHERE` clause includes the exclusion fragment. Replace the whole function body from `placeholders = ...` down to `return conn.execute(sql, params).fetchone()` with:

```python
    placeholders = ",".join("?" for _ in COACHING_EXCLUDED)
    excluded = excluded_employee_ids(conn, start[:7])
    exc_frag, exc_params = exclusion_sql(excluded, column="e.id")
    sql = f"""
        SELECT e.id, e.nama, e.dept,
               SUM(CASE WHEN ar.reason_category IN ({placeholders}) THEN 0
                        WHEN ar.masuk IS NULL THEN 0
                        ELSE COALESCE(ar.terlambat_menit, 0) END)
                 + SUM(CASE WHEN ar.tipe='Hari Kerja' AND ar.masuk IS NULL AND ar.keluar IS NULL
                            THEN 60 ELSE 0 END)
                 + SUM(CASE WHEN ar.has_issue = 1 THEN 30 ELSE 0 END) AS score,
               COUNT(*) AS hari_kerja
          FROM attendance_records ar
          JOIN employees e ON ar.employee_id = e.id
         WHERE ar.tanggal BETWEEN ? AND ?
               AND ar.tipe = 'Hari Kerja'{exc_frag}
         GROUP BY e.id
         HAVING hari_kerja >= 3
         ORDER BY score ASC, e.nama ASC
         LIMIT 1
    """
    params = (*COACHING_EXCLUDED, start, end, *exc_params)
    return conn.execute(sql, params).fetchone()
```

Then modify `karyawan_teladan_top_n`. Replace its body from `placeholders = ...` down to the final `return conn.execute(sql, params).fetchall()` with:

```python
    placeholders = ",".join("?" for _ in COACHING_EXCLUDED)
    excluded = excluded_employee_ids(conn, start[:7])
    exc_frag, exc_params = exclusion_sql(excluded, column="e.id")
    limit_clause = "" if n is None else "LIMIT ?"
    sql = f"""
        SELECT e.id, e.nama, e.dept,
               SUM(CASE WHEN ar.reason_category IN ({placeholders}) THEN 0
                        WHEN ar.masuk IS NULL THEN 0
                        ELSE COALESCE(ar.terlambat_menit, 0) END)
                 + SUM(CASE WHEN ar.tipe='Hari Kerja' AND ar.masuk IS NULL AND ar.keluar IS NULL
                            THEN 60 ELSE 0 END)
                 + SUM(CASE WHEN ar.has_issue = 1 THEN 30 ELSE 0 END) AS score,
               COUNT(*) AS hari_kerja
          FROM attendance_records ar
          JOIN employees e ON ar.employee_id = e.id
         WHERE ar.tanggal BETWEEN ? AND ?
               AND ar.tipe = 'Hari Kerja'{exc_frag}
         GROUP BY e.id
         HAVING hari_kerja >= 3
         ORDER BY score ASC, e.nama ASC
         {limit_clause}
    """
    if n is None:
        params = (*COACHING_EXCLUDED, start, end, *exc_params)
    else:
        params = (*COACHING_EXCLUDED, start, end, *exc_params, n)
    return conn.execute(sql, params).fetchall()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `../../../.venv/Scripts/python.exe -m pytest tests/test_insights.py -v`
Expected: all PASS, no regression.

- [ ] **Step 5: Commit**

```bash
git add src/core/insights.py tests/test_insights.py
git commit -m "feat(insights): filter excluded employees from karyawan_teladan + top_n"
```

---

## Task 7: `insights.py` — filter `ranking_departemen`, `hari_paling_rawan`, `avg_minutes_per_late_event`, `pola_jam_masuk`

**Files:**
- Modify: `src/core/insights.py`
- Modify: `tests/test_insights.py`

Four aggregate-across-employees functions — exclusion MUST happen in the SQL `WHERE` (before `SUM`/`COUNT`/`GROUP BY`), otherwise totals/averages/distributions are wrong.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_insights.py`:

```python
def test_ranking_departemen_excludes_outlier_from_dept_totals(temp_db_path):
    from src.db.outlier import exclude_employee
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        a = _add_emp(conn, "1", "ANDI")
        b = _add_emp(conn, "2", "BUDI")
        _add_att(conn, a, "2026-04-01", "Senin", "09.40", "16.00", 100)
        _add_att(conn, b, "2026-04-01", "Senin", "08.40", "16.00", 40)
        exclude_employee(conn, a, "2026-04")
        rows = ranking_departemen(conn, "2026-04-01", "2026-04-30")
        # Both are dept "X"; only BUDI's 40 should count
        total = sum(r["total_terlambat"] for r in rows)
        assert total == 40


def test_hari_paling_rawan_excludes_outlier(temp_db_path):
    from src.db.outlier import exclude_employee
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        a = _add_emp(conn, "1", "ANDI")
        b = _add_emp(conn, "2", "BUDI")
        _add_att(conn, a, "2026-04-06", "Senin", "08.50", "16.00", 50)
        _add_att(conn, b, "2026-04-06", "Senin", "08.40", "16.00", 40)
        exclude_employee(conn, a, "2026-04")
        rows = hari_paling_rawan(conn, "2026-04-01", "2026-04-30")
        senin = next(r for r in rows if r["hari"] == "Senin")
        assert senin["terlambat_count"] == 1  # only BUDI


def test_avg_minutes_per_late_event_excludes_outlier(temp_db_path):
    from src.db.outlier import exclude_employee
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        a = _add_emp(conn, "1", "ANDI")
        b = _add_emp(conn, "2", "BUDI")
        _add_att(conn, a, "2026-04-01", "Senin", "09.40", "16.00", 100)
        _add_att(conn, b, "2026-04-01", "Senin", "08.20", "16.00", 20)
        exclude_employee(conn, a, "2026-04")
        # Only BUDI's single 20-min event counts → avg 20.0
        assert avg_minutes_per_late_event(conn, "2026-04-01", "2026-04-30") == 20.0


def test_pola_jam_masuk_excludes_outlier(temp_db_path):
    from src.db.outlier import exclude_employee
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        a = _add_emp(conn, "1", "ANDI")
        b = _add_emp(conn, "2", "BUDI")
        _add_att(conn, a, "2026-04-01", "Senin", "08.00", "16.00", 0)
        _add_att(conn, b, "2026-04-01", "Senin", "08.00", "16.00", 0)
        exclude_employee(conn, a, "2026-04")
        rows = pola_jam_masuk(conn, "2026-04-01", "2026-04-30")
        counts = {r["band"]: r["count"] for r in rows}
        assert sum(counts.values()) == 1  # only BUDI's session
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `../../../.venv/Scripts/python.exe -m pytest tests/test_insights.py -k "departemen_excludes or rawan_excludes or per_late_event_excludes or jam_masuk_excludes" -v`
Expected: FAIL — totals/counts still include ANDI.

- [ ] **Step 3: Add filters to all four functions**

In `src/core/insights.py`:

**3a — `ranking_departemen`:** replace its body from `placeholders = ...` down to `return conn.execute(sql, params).fetchall()` with:

```python
    placeholders = ",".join("?" for _ in COACHING_EXCLUDED)
    excluded = excluded_employee_ids(conn, start[:7])
    exc_frag, exc_params = exclusion_sql(excluded, column="e.id")
    sql = f"""
        SELECT e.dept,
               SUM(CASE WHEN ar.reason_category IN ({placeholders}) THEN 0
                        WHEN ar.masuk IS NULL THEN 0
                        ELSE COALESCE(ar.terlambat_menit, 0) END) AS total_terlambat,
               SUM(CASE WHEN ar.has_issue = 1 THEN 1 ELSE 0 END) AS issue_count,
               COUNT(CASE WHEN ar.masuk IS NOT NULL
                          AND ar.terlambat_menit > 0
                          AND (ar.reason_category IS NULL
                               OR ar.reason_category NOT IN ({placeholders}))
                          THEN 1 END) AS hari_telat,
               COUNT(DISTINCT e.id) AS pegawai_count
          FROM attendance_records ar
          JOIN employees e ON ar.employee_id = e.id
         WHERE ar.tanggal BETWEEN ? AND ?
               AND e.dept IS NOT NULL{exc_frag}
         GROUP BY e.dept
         ORDER BY total_terlambat DESC, e.dept ASC
    """
    params = (*COACHING_EXCLUDED, *COACHING_EXCLUDED, start, end, *exc_params)
    return conn.execute(sql, params).fetchall()
```

**3b — `hari_paling_rawan`:** replace its body from `sql = """` down to `return conn.execute(sql, (start, end)).fetchall()` with:

```python
    excluded = excluded_employee_ids(conn, start[:7])
    exc_frag, exc_params = exclusion_sql(excluded, column="employee_id")
    sql = f"""
        SELECT hari,
               SUM(CASE WHEN masuk IS NOT NULL AND terlambat_menit > 0 THEN 1 ELSE 0 END) AS terlambat_count,
               SUM(CASE WHEN has_issue = 1 THEN 1 ELSE 0 END) AS issue_count,
               COUNT(*) AS total_rows
          FROM attendance_records
         WHERE tipe = 'Hari Kerja'
           AND tanggal BETWEEN ? AND ?
           AND hari IS NOT NULL{exc_frag}
         GROUP BY hari
         ORDER BY terlambat_count DESC, hari ASC
    """
    return conn.execute(sql, (start, end, *exc_params)).fetchall()
```

**3c — `avg_minutes_per_late_event`:** replace its body from `row = conn.execute(` down to `return float(total) / cnt if cnt else 0.0` with:

```python
    excluded = excluded_employee_ids(conn, period_start[:7])
    exc_frag, exc_params = exclusion_sql(excluded, column="employee_id")
    row = conn.execute(
        f"""
        SELECT COALESCE(SUM(terlambat_menit), 0) AS total,
               COUNT(*) AS cnt
          FROM attendance_records
         WHERE tanggal BETWEEN ? AND ?
           AND tipe = 'Hari Kerja'
           AND terlambat_menit IS NOT NULL
           AND terlambat_menit > 0{exc_frag}
        """,
        (period_start, period_end, *exc_params),
    ).fetchone()
    total, cnt = row[0], row[1]
    return float(total) / cnt if cnt else 0.0
```

**3d — `pola_jam_masuk`:** replace the `rows = conn.execute(...)` block with:

```python
    excluded = excluded_employee_ids(conn, period_start[:7])
    exc_frag, exc_params = exclusion_sql(excluded, column="employee_id")
    rows = conn.execute(
        f"""
        SELECT masuk
          FROM attendance_records
         WHERE tanggal BETWEEN ? AND ?
           AND tipe = 'Hari Kerja'
           AND masuk IS NOT NULL{exc_frag}
        """,
        (period_start, period_end, *exc_params),
    ).fetchall()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `../../../.venv/Scripts/python.exe -m pytest tests/test_insights.py -v`
Expected: all PASS, no regression.

- [ ] **Step 5: Commit**

```bash
git add src/core/insights.py tests/test_insights.py
git commit -m "feat(insights): filter excluded employees from dept/rawan/avg/pola insights"
```

---

## Task 8: `src/db/coaching.py` — filter `list_coaching_for_week`

**Files:**
- Modify: `src/db/coaching.py`
- Modify: `tests/test_coaching_db.py`

The Coaching screen goes through `list_coaching_for_week`, NOT `coaching_flag`, so it needs its own filter. The exclusion month is derived from `week_start[:7]`.

- [ ] **Step 1: Read the existing coaching test file for its helper pattern**

Run: `head -40 tests/test_coaching_db.py`
Note the `_add_emp` / attendance-insert helpers used there so the new test matches local conventions. (If the file uses different helper names than shown below, adapt the test accordingly — behaviour must stay identical.)

- [ ] **Step 2: Write the failing test**

Append to `tests/test_coaching_db.py`:

```python
def test_list_coaching_for_week_excludes_outlier(temp_db_path):
    """An employee excluded via the Outlier menu does not appear in the
    Coaching list, even when over the lateness threshold."""
    from src.db.schema import init_db
    from src.db.connection import get_connection
    from src.db.employees import upsert_employee
    from src.db.attendance import upsert_attendance
    from src.db.outlier import exclude_employee
    from src.db.coaching import list_coaching_for_week

    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        a = upsert_employee(conn, no_staff="1", nama="ANDI", dept="X")
        b = upsert_employee(conn, no_staff="2", nama="BUDI", dept="X")
        for emp in (a, b):
            upsert_attendance(
                conn, employee_id=emp, tanggal="2026-04-06", hari="Senin",
                tipe="Hari Kerja", jadwal="08.00 - 16.00",
                masuk="09.40", keluar="16.00", kerja_jam=6.0,
                lembur_jam=None, terlambat_menit=100, has_issue=0,
                imported_from="W1.xls",
            )
        exclude_employee(conn, a, "2026-04")  # ANDI excluded

        rows = list_coaching_for_week(
            conn, week_start="2026-04-06", week_end="2026-04-12",
            threshold_minutes=75,
        )
        names = [r["nama"] for r in rows]
        assert "ANDI" not in names
        assert "BUDI" in names
```

- [ ] **Step 3: Run test to verify it fails**

Run: `../../../.venv/Scripts/python.exe -m pytest tests/test_coaching_db.py -k "excludes_outlier" -v`
Expected: FAIL — `"ANDI"` still in `names`.

- [ ] **Step 4: Add the filter to `list_coaching_for_week`**

In `src/db/coaching.py`, add the import near the top (after `from src.config import COACHING_EXCLUDED`):

```python
from src.db.outlier import excluded_employee_ids, exclusion_sql
```

Then in `list_coaching_for_week`, replace the block from `placeholders = ...` through the `return conn.execute(sql, params).fetchall()` with:

```python
    placeholders = ",".join("?" for _ in COACHING_EXCLUDED)
    excluded = excluded_employee_ids(conn, week_start[:7])
    exc_frag, exc_params = exclusion_sql(excluded, column="ar.employee_id")
    sql = f"""
        WITH terlambat AS (
            SELECT
                ar.employee_id,
                SUM(CASE
                    WHEN ar.reason_category IN ({placeholders}) THEN 0
                    WHEN ar.masuk IS NULL THEN 0
                    ELSE COALESCE(ar.terlambat_menit, 0)
                END) AS total_terlambat
              FROM attendance_records ar
             WHERE ar.tanggal BETWEEN ? AND ?{exc_frag}
             GROUP BY ar.employee_id
        )
        SELECT
            t.employee_id,
            e.nama,
            e.dept,
            e.no_staff,
            t.total_terlambat,
            ? AS week_start,
            cs.coached_at,
            CASE WHEN cs.id IS NOT NULL THEN 1 ELSE 0 END AS is_coached
          FROM terlambat t
          JOIN employees e ON t.employee_id = e.id
          LEFT JOIN coaching_sessions cs
                 ON cs.employee_id = t.employee_id
                AND cs.week_start = ?
         WHERE t.total_terlambat > ?
         ORDER BY t.total_terlambat DESC, e.nama ASC
    """
    params = (
        *COACHING_EXCLUDED, week_start, week_end, *exc_params,
        week_start, week_start, threshold_minutes,
    )
    return conn.execute(sql, params).fetchall()
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `../../../.venv/Scripts/python.exe -m pytest tests/test_coaching_db.py -v`
Expected: all PASS, no regression.

- [ ] **Step 6: Commit**

```bash
git add src/db/coaching.py tests/test_coaching_db.py
git commit -m "feat(coaching): filter excluded employees from list_coaching_for_week"
```

---

## Task 9: `src/ui/screens/outlier.py` — the Outlier screen

**Files:**
- Create: `src/ui/screens/outlier.py`
- Test: `tests/test_outlier_screen.py` (create)

Matches the approved mockup: header + active-month badge, info bar, search box, "Dikecualikan" section, "Disertakan" section, "Revert Semua" footer. UI rendering can't be deeply unit-tested; a construct-smoke-test guards against import/wiring errors.

- [ ] **Step 1: Write the failing smoke test**

Create `tests/test_outlier_screen.py`:

```python
"""Smoke test for the Outlier screen — verifies it constructs without error
against a temp DB with sample data. Deep UI behaviour is covered by the
src/db/outlier.py unit tests."""
import customtkinter as ctk

from src.db.schema import init_db
from src.db.connection import get_connection
from src.db.employees import upsert_employee
from src.db.attendance import upsert_attendance
from src.db.settings import set_setting
from src.db.outlier import exclude_employee


def test_outlier_screen_constructs(temp_db_path, monkeypatch):
    # Point the screen module's DB_PATH at the temp DB
    import src.ui.screens.outlier as outlier_mod
    monkeypatch.setattr(outlier_mod, "DB_PATH", temp_db_path)

    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        a = upsert_employee(conn, no_staff="1", nama="ANDI", dept="X")
        b = upsert_employee(conn, no_staff="2", nama="BUDI", dept="X")
        for emp in (a, b):
            upsert_attendance(
                conn, employee_id=emp, tanggal="2026-04-01", hari="Senin",
                tipe="Hari Kerja", jadwal="08.00 - 16.00",
                masuk="08.05", keluar="16.00", kerja_jam=8.0,
                lembur_jam=None, terlambat_menit=5, has_issue=0,
                imported_from="W1.xls",
            )
        set_setting(conn, "current_month", "2026-04")
        exclude_employee(conn, a, "2026-04")
        conn.commit()

    root = ctk.CTk()
    root.withdraw()
    try:
        screen = outlier_mod.OutlierScreen(root)
        root.update_idletasks()
        assert screen is not None
    finally:
        root.destroy()


def test_outlier_screen_constructs_with_no_active_month(temp_db_path, monkeypatch):
    """Empty state — no current_month set — must not crash."""
    import src.ui.screens.outlier as outlier_mod
    monkeypatch.setattr(outlier_mod, "DB_PATH", temp_db_path)
    init_db(temp_db_path)

    root = ctk.CTk()
    root.withdraw()
    try:
        screen = outlier_mod.OutlierScreen(root)
        root.update_idletasks()
        assert screen is not None
    finally:
        root.destroy()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `../../../.venv/Scripts/python.exe -m pytest tests/test_outlier_screen.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.ui.screens.outlier'`.

- [ ] **Step 3: Create `src/ui/screens/outlier.py`**

```python
"""Outlier / Pengecualian screen — manage which employees are excluded
from Dashboard & Coaching analytics for the active month onward.

See spec: docs/superpowers/specs/2026-05-14-outlier-exclusion-design.md
"""
import customtkinter as ctk

from src.config import DB_PATH
from src.core.report_generator import month_label
from src.db.connection import get_connection
from src.db.settings import get_setting
from src.db.outlier import (
    month_roster, list_active_exclusions,
    exclude_employee, revert_employee, revert_all,
)
from src.ui.theme import (
    COLOR_BG, COLOR_SURFACE, COLOR_SURFACE_HIGH,
    COLOR_BORDER, COLOR_BORDER_STRONG,
    COLOR_ACCENT, COLOR_ACCENT_HOVER,
    COLOR_INFO, COLOR_SECONDARY,
    COLOR_TEXT, COLOR_TEXT_DIM, COLOR_TEXT_MUTED,
    FONT_DISPLAY, FONT_SUBHEAD, FONT_BODY, FONT_BODY_BOLD,
    FONT_SMALL, FONT_LABEL, FONT_MONO_SMALL,
    SPACE_XS, SPACE_SM, SPACE_MD, SPACE_LG,
    RADIUS_SM, RADIUS_MD,
)

# Violet-tinted treatment for excluded rows (matches approved mockup)
_EXCLUDED_BG = "#160E1C"
_EXCLUDED_BORDER = "#3A2348"


class OutlierScreen(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        with get_connection(DB_PATH) as conn:
            self._month = get_setting(conn, "current_month") or ""

        self._build_header()
        self._build_scroll()
        self._render()

    # ── layout scaffold ──────────────────────────────────────────
    def _build_header(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", pady=(0, SPACE_MD))
        left = ctk.CTkFrame(header, fg_color="transparent")
        left.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(
            left, text="Outlier — Pengecualian",
            font=FONT_DISPLAY, text_color=COLOR_TEXT,
        ).pack(anchor="w")
        ctk.CTkLabel(
            left,
            text="Kecualikan karyawan tertentu dari analisis Dashboard & Coaching",
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
                badge, text="BULAN AKTIF", font=FONT_LABEL,
                text_color="#5FB8C8",
            ).pack(anchor="e", padx=SPACE_MD, pady=(SPACE_XS, 0))
            ctk.CTkLabel(
                badge, text=month_label(self._month),
                font=FONT_BODY_BOLD, text_color=COLOR_INFO,
            ).pack(anchor="e", padx=SPACE_MD, pady=(0, SPACE_XS))

    def _build_scroll(self):
        self.scroll = ctk.CTkScrollableFrame(self, fg_color=COLOR_BG)
        self.scroll.grid(row=1, column=0, sticky="nsew")

    # ── render ───────────────────────────────────────────────────
    def _render(self):
        for child in self.scroll.winfo_children():
            child.destroy()

        if not self._month:
            self._render_empty(
                "Belum ada bulan aktif.",
                "Pilih bulan di menu Active Month dulu.",
            )
            return

        with get_connection(DB_PATH) as conn:
            roster = month_roster(conn, self._month)
            active = list_active_exclusions(conn)

        if not roster:
            self._render_empty(
                "Belum ada data untuk bulan aktif.",
                "Import fingerprint dulu via menu Import.",
            )
            return

        excluded_ids = {a["employee_id"] for a in active}
        active_by_id = {a["employee_id"]: a for a in active}
        excluded_rows = [r for r in roster if r["id"] in excluded_ids]
        included_rows = [r for r in roster if r["id"] not in excluded_ids]

        self._render_infobar(len(excluded_rows), len(roster))

        if excluded_rows:
            self._render_section_label(
                f"Dikecualikan", len(excluded_rows), excluded=True,
            )
            for r in excluded_rows:
                self._render_row(
                    r, excluded=True,
                    since=active_by_id[r["id"]]["effective_from"],
                )

        self._render_section_label(
            "Disertakan dalam analisis", len(included_rows), excluded=False,
        )
        for r in included_rows:
            self._render_row(r, excluded=False, since=None)

        if excluded_rows:
            self._render_footer(len(excluded_rows))

    def _render_empty(self, title: str, hint: str):
        box = ctk.CTkFrame(
            self.scroll, fg_color=COLOR_SURFACE,
            border_width=1, border_color=COLOR_BORDER,
            corner_radius=RADIUS_MD,
        )
        box.pack(fill="x", pady=SPACE_SM, padx=SPACE_XS)
        ctk.CTkLabel(
            box, text=title, font=FONT_SUBHEAD, text_color=COLOR_TEXT,
        ).pack(anchor="w", padx=SPACE_LG, pady=(SPACE_LG, SPACE_XS))
        ctk.CTkLabel(
            box, text=hint, font=FONT_SMALL, text_color=COLOR_TEXT_DIM,
        ).pack(anchor="w", padx=SPACE_LG, pady=(0, SPACE_LG))

    def _render_infobar(self, excluded_count: int, total: int):
        bar = ctk.CTkFrame(
            self.scroll, fg_color=COLOR_SURFACE,
            border_width=1, border_color=COLOR_BORDER,
            corner_radius=RADIUS_MD,
        )
        bar.pack(fill="x", pady=(SPACE_XS, SPACE_MD), padx=SPACE_XS)
        msg = (
            f"{excluded_count} dari {total} karyawan dikecualikan dari "
            f"analisis bulan ini. Pengecualian hanya memengaruhi angka "
            f"Dashboard & Coaching — issue mereka tetap terbuka dan harus "
            f"di-resolve seperti biasa."
        )
        ctk.CTkLabel(
            bar, text=msg, font=FONT_SMALL, text_color=COLOR_TEXT_DIM,
            wraplength=720, justify="left", anchor="w",
        ).pack(anchor="w", fill="x", padx=SPACE_MD, pady=SPACE_SM)

    def _render_section_label(self, text: str, count: int, excluded: bool):
        row = ctk.CTkFrame(self.scroll, fg_color="transparent")
        row.pack(fill="x", padx=SPACE_XS, pady=(SPACE_MD, SPACE_XS))
        ctk.CTkLabel(
            row, text=text.upper(), font=FONT_LABEL,
            text_color=COLOR_SECONDARY if excluded else COLOR_TEXT_MUTED,
        ).pack(side="left")
        ctk.CTkLabel(
            row, text=f"  {count}", font=FONT_LABEL,
            text_color=COLOR_TEXT_MUTED,
        ).pack(side="left")

    def _render_row(self, emp: dict, excluded: bool, since):
        card = ctk.CTkFrame(
            self.scroll,
            fg_color=_EXCLUDED_BG if excluded else COLOR_SURFACE,
            border_width=1,
            border_color=_EXCLUDED_BORDER if excluded else COLOR_BORDER,
            corner_radius=RADIUS_MD,
        )
        card.pack(fill="x", pady=2, padx=SPACE_XS)

        ctk.CTkLabel(
            card, text=emp["nama"][:1].upper(),
            font=FONT_BODY_BOLD,
            text_color=COLOR_SECONDARY if excluded else COLOR_TEXT_MUTED,
            fg_color=COLOR_SURFACE_HIGH, corner_radius=RADIUS_SM,
            width=30, height=30,
        ).pack(side="left", padx=(SPACE_MD, SPACE_SM), pady=SPACE_SM)

        info = ctk.CTkFrame(card, fg_color="transparent")
        info.pack(side="left", fill="x", expand=True, pady=SPACE_SM)
        ctk.CTkLabel(
            info, text=emp["nama"], font=FONT_BODY_BOLD,
            text_color=COLOR_TEXT,
        ).pack(anchor="w")
        meta = emp["dept"] or "-"
        if excluded and since:
            meta = f"{meta} · sejak {month_label(since)}"
        ctk.CTkLabel(
            info, text=meta, font=FONT_MONO_SMALL,
            text_color=COLOR_TEXT_MUTED,
        ).pack(anchor="w")

        if excluded:
            ctk.CTkButton(
                card, text="↩ Sertakan kembali", width=150, height=30,
                fg_color="transparent",
                border_width=1, border_color=COLOR_SECONDARY,
                text_color=COLOR_SECONDARY, hover_color=COLOR_SURFACE_HIGH,
                font=FONT_SMALL,
                command=lambda eid=emp["id"]: self._on_revert(eid),
            ).pack(side="right", padx=SPACE_MD, pady=SPACE_SM)
        else:
            ctk.CTkButton(
                card, text="Kecualikan", width=110, height=30,
                fg_color="transparent",
                border_width=1, border_color=COLOR_BORDER_STRONG,
                text_color=COLOR_TEXT_DIM, hover_color=COLOR_SURFACE_HIGH,
                font=FONT_SMALL,
                command=lambda eid=emp["id"]: self._on_exclude(eid),
            ).pack(side="right", padx=SPACE_MD, pady=SPACE_SM)

    def _render_footer(self, excluded_count: int):
        footer = ctk.CTkFrame(self.scroll, fg_color="transparent")
        footer.pack(fill="x", pady=(SPACE_MD, SPACE_SM), padx=SPACE_XS)
        ctk.CTkButton(
            footer, text=f"↩ Revert Semua ({excluded_count})",
            width=170, height=34,
            fg_color="transparent",
            border_width=1, border_color=COLOR_BORDER,
            text_color=COLOR_TEXT_MUTED, hover_color=COLOR_SURFACE_HIGH,
            font=FONT_SMALL,
            command=self._on_revert_all,
        ).pack(side="right")

    # ── actions ──────────────────────────────────────────────────
    def _on_exclude(self, employee_id: int):
        with get_connection(DB_PATH) as conn:
            exclude_employee(conn, employee_id, self._month)
            conn.commit()
        self._render()

    def _on_revert(self, employee_id: int):
        with get_connection(DB_PATH) as conn:
            revert_employee(conn, employee_id, self._month)
            conn.commit()
        self._render()

    def _on_revert_all(self):
        with get_connection(DB_PATH) as conn:
            revert_all(conn, self._month)
            conn.commit()
        self._render()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `../../../.venv/Scripts/python.exe -m pytest tests/test_outlier_screen.py -v`
Expected: 2 PASS.

If a test fails because `month_label` rejects an unexpected input, check the actual signature of `month_label` in `src/core/report_generator.py` and adapt the call sites (it is already used by `active_month.py` with `"YYYY-MM"` strings, so `month_label("2026-04")` is known-good).

- [ ] **Step 5: Commit**

```bash
git add src/ui/screens/outlier.py tests/test_outlier_screen.py
git commit -m "feat(ui): Outlier screen — manage employee exclusions"
```

---

## Task 10: `src/ui/app.py` — sidebar entry + screen routing

**Files:**
- Modify: `src/ui/app.py`

- [ ] **Step 1: Add the sidebar group**

In `src/ui/app.py`, find the `nav_groups` list (around line 140). Insert a new group **between** the `"WORKFLOW"` group and the `"SYSTEM"` group:

```python
            ("WORKFLOW", [
                ("🚩", "Issues", "Issues"),
                ("💬", "WhatsApp Assistant", "WhatsAppAssistant"),
                ("🎯", "Coaching", "Coaching"),
            ]),
            ("EXCEPTIONAL CASE", [
                ("🔸", "Outlier", "Outlier"),
            ]),
            ("SYSTEM", [
                ("⚙", "Settings", "Settings"),
            ]),
```

- [ ] **Step 2: Add the screen routing branch**

In `src/ui/app.py`, find the `_show()` method's `if/elif` chain (around line 397). Add a branch — place it right before the `elif name == "Settings":` branch:

```python
        elif name == "Outlier":
            from src.ui.screens.outlier import OutlierScreen
            OutlierScreen(self.content).grid(row=0, column=0, sticky="nsew")
        elif name == "Settings":
```

- [ ] **Step 3: Verify the app imports and the full suite still passes**

Run: `../../../.venv/Scripts/python.exe -c "import src.ui.app; print('app import OK')"`
Expected: `app import OK`

Run: `../../../.venv/Scripts/python.exe -m pytest -q`
Expected: all PASS (~149+).

- [ ] **Step 4: Commit**

```bash
git add src/ui/app.py
git commit -m "feat(ui): wire Outlier screen into sidebar (EXCEPTIONAL CASE group)"
```

---

## Task 11: Full verification + manual smoke

**Files:** none (verification only)

- [ ] **Step 1: Run the full test suite**

Run: `../../../.venv/Scripts/python.exe -m pytest -q`
Expected: all PASS. Count should be **131 baseline + 29 new ≈ 160** (16 in test_outlier_db [6+6+4]; 9 in test_insights [3+2+4]; 1 in test_coaching_db; 1 in test_schema; 2 in test_outlier_screen). Exact number may vary slightly — the requirement is **zero failures**.

If any pre-existing test fails, investigate — the exclusion filter is a no-op when there are no exclusion rows, so existing tests must be unaffected.

- [ ] **Step 2: Launch the app and smoke-test the feature**

Run: `../../../.venv/Scripts/python.exe -m src.main`

Verify:
- Sidebar shows new "EXCEPTIONAL CASE" group with "Outlier" item, positioned above "SYSTEM"
- Click Outlier → screen loads, shows active-month badge, info bar, employee list
- Click "Kecualikan" on an employee → they move to the "Dikecualikan" section with a violet card + "sejak [month]"
- Go to Dashboard → that employee is gone from Top 5 / Ranking / Coaching panels / counts
- Go to Coaching screen → that employee is gone from the Butuh Coaching list
- Back to Outlier → click "↩ Sertakan kembali" → employee returns to "Disertakan"
- Dashboard counts go back up
- Issues screen → the employee's issues are still listed (unaffected)

Close the app.

- [ ] **Step 3: Confirm clean working tree + commit chain**

Run: `git status` — expected: nothing to commit.
Run: `git log --oneline origin/v10..HEAD` — expected: the spec + plan commits plus the 10 task commits.

- [ ] **Step 4: Hand off**

Implementation complete. Do NOT push or build .exe here — those are user-authorized steps handled separately. Report completion with the final test count.

---

## Out of Scope (reaffirmed from spec)

- "Alasan" field per exclusion — not built
- Print transparency note — not built
- Per-month independent exclusion — using carry-forward
- Issues / WhatsApp / Report Generator behaviour — untouched
- Bulk multi-select exclude — only per-row + "Revert Semua"

---

## Reference

- **Spec:** [2026-05-14-outlier-exclusion-design.md](../specs/2026-05-14-outlier-exclusion-design.md)
- **UI mockup (approved):** `.superpowers/brainstorm/696-1778743382/content/01-outlier-screen.html`
- **Theme tokens:** `src/ui/theme.py`
- **Screen pattern reference:** `src/ui/screens/active_month.py` (reads `current_month`, scrollable card list, `_on_pick` navigation)
