# Coaching Menu + Issues Unresolve Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Coaching screen (sidebar item #7) with weekly-only WeekNavBar, KPI cards, status-tinted Treeview with inline toggle, and optional-notes right panel; add "Batalkan Resolve" button to Issues right panel for resolved rows.

**Architecture:** New `coaching_sessions` table tracks per-employee per-week coaching status (existence = Sudah, absence = Belum). New `src/db/coaching.py` module with 5 functions. New `src/ui/screens/coaching.py` mirrors Issues pattern (table left, panel right). WeekNavBar gets `include_all=False` parameter. Issues screen gets a conditional `unresolve` button + new `unresolve_issue()` DB function.

**Tech Stack:** Python 3.13, customtkinter, ttk.Treeview (with tag-based row tinting), SQLite, pytest.

---

## Source Spec

[docs/superpowers/specs/2026-05-12-coaching-menu-and-unresolve-design.md](../specs/2026-05-12-coaching-menu-and-unresolve-design.md) — approved 2026-05-12.

---

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `src/db/schema.py` | Modify (DDL string) | Add `coaching_sessions` CREATE TABLE |
| `src/db/coaching.py` | Create | 5 CRUD/query functions for coaching_sessions |
| `src/db/attendance.py` | Modify (append) | Add `unresolve_issue` function |
| `src/ui/components/week_nav.py` | Modify | Add `include_all: bool = True` parameter |
| `src/ui/screens/coaching.py` | Create | CoachingScreen UI |
| `src/ui/screens/issues.py` | Modify | Add conditional "Batalkan Resolve" button + handler |
| `src/ui/app.py` | Modify | Register "🎯 Coaching" sidebar item + _show branch |
| `tests/test_coaching_db.py` | Create | 8 tests for coaching DB layer |
| `tests/test_unresolve_issue.py` | Create | 3 tests for unresolve_issue |

---

## Test Strategy

- **TDD on DB layer** (Tasks 1, 5): write failing test → minimal impl → green → commit
- **No new UI tests** — UI verified via manual smoke (consistent with project precedent)
- **Regression baseline:** 86 passing now. Target after this plan: 86 + 11 = **~97 passing**
- **pytest command from worktree root:** `../../../.venv/Scripts/python.exe -m pytest -q`

---

## Task 1: DB Schema + Coaching Module (TDD)

**Files:**
- Modify: `src/db/schema.py` (add 1 table to DDL)
- Create: `src/db/coaching.py`
- Create: `tests/test_coaching_db.py`

### Step 1: Add `coaching_sessions` to DDL

In `src/db/schema.py`, find the existing DDL string (lines 4-42). Add this CREATE TABLE statement at the end of the DDL string, before the closing `"""`:

```sql

CREATE TABLE IF NOT EXISTS coaching_sessions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id INTEGER NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
    week_start  TEXT    NOT NULL,
    coached_at  TEXT    NOT NULL,
    notes       TEXT,
    UNIQUE (employee_id, week_start)
);

CREATE INDEX IF NOT EXISTS idx_coaching_week ON coaching_sessions(week_start);
```

The final DDL string section should end with:
```python
CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS coaching_sessions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id INTEGER NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
    week_start  TEXT    NOT NULL,
    coached_at  TEXT    NOT NULL,
    notes       TEXT,
    UNIQUE (employee_id, week_start)
);

CREATE INDEX IF NOT EXISTS idx_coaching_week ON coaching_sessions(week_start);
"""
```

### Step 2: Write failing tests

Create `tests/test_coaching_db.py` with EXACTLY this content:

```python
"""Tests for src/db/coaching.py — coaching session CRUD + list query."""
import sqlite3

from src.db.schema import DDL
from src.db.employees import upsert_employee
from src.db.attendance import upsert_attendance, set_reason
from src.db.coaching import (
    mark_coached, unmark_coached, get_coaching_notes,
    update_notes, list_coaching_for_week,
)


def _conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(DDL)
    return conn


def _add_employee(conn, no_staff="E001", nama="ANDIKA", dept="ARGA DIRGA"):
    return upsert_employee(conn, no_staff=no_staff, nama=nama, dept=dept, phone=None)


def _add_late_attendance(conn, emp_id, tanggal, terlambat_menit):
    """Add a Hari Kerja attendance with masuk set (so terlambat counts)."""
    upsert_attendance(
        conn, employee_id=emp_id, tanggal=tanggal,
        hari="Senin", tipe="Hari Kerja", jadwal="08.00 - 16.00",
        masuk="08:15", keluar="16:00",
        kerja_jam=7.75, lembur_jam=0.0, terlambat_menit=terlambat_menit,
        has_issue=0, imported_from="test.xls",
    )


# ────────────────────────────────────────── CRUD


def test_mark_coached_inserts_row():
    conn = _conn()
    emp_id = _add_employee(conn)
    mark_coached(conn, employee_id=emp_id, week_start="2026-04-06")
    row = conn.execute(
        "SELECT * FROM coaching_sessions WHERE employee_id=? AND week_start=?",
        (emp_id, "2026-04-06"),
    ).fetchone()
    assert row is not None
    assert row["coached_at"] is not None
    assert row["notes"] is None


def test_mark_coached_idempotent_upserts_notes():
    conn = _conn()
    emp_id = _add_employee(conn)
    mark_coached(conn, employee_id=emp_id, week_start="2026-04-06", notes="first")
    mark_coached(conn, employee_id=emp_id, week_start="2026-04-06", notes="second")
    row = conn.execute(
        "SELECT notes FROM coaching_sessions WHERE employee_id=? AND week_start=?",
        (emp_id, "2026-04-06"),
    ).fetchone()
    assert row["notes"] == "second"
    # Still only one row
    count = conn.execute(
        "SELECT COUNT(*) c FROM coaching_sessions"
    ).fetchone()["c"]
    assert count == 1


def test_unmark_coached_deletes_row():
    conn = _conn()
    emp_id = _add_employee(conn)
    mark_coached(conn, employee_id=emp_id, week_start="2026-04-06")
    unmark_coached(conn, employee_id=emp_id, week_start="2026-04-06")
    row = conn.execute(
        "SELECT * FROM coaching_sessions WHERE employee_id=? AND week_start=?",
        (emp_id, "2026-04-06"),
    ).fetchone()
    assert row is None


def test_get_coaching_notes_returns_none_when_no_session():
    conn = _conn()
    emp_id = _add_employee(conn)
    result = get_coaching_notes(conn, employee_id=emp_id, week_start="2026-04-06")
    assert result is None


def test_update_notes_updates_existing_session():
    conn = _conn()
    emp_id = _add_employee(conn)
    mark_coached(conn, employee_id=emp_id, week_start="2026-04-06")
    update_notes(conn, employee_id=emp_id, week_start="2026-04-06", notes="discussed plan")
    result = get_coaching_notes(conn, employee_id=emp_id, week_start="2026-04-06")
    assert result == "discussed plan"


# ────────────────────────────────────────── list_coaching_for_week


def test_list_coaching_returns_over_threshold_pegawai():
    conn = _conn()
    emp1 = _add_employee(conn, no_staff="E001", nama="ANDIKA")
    emp2 = _add_employee(conn, no_staff="E002", nama="YASMIN")
    # ANDIKA: 80 mnt total (over 75)
    _add_late_attendance(conn, emp1, "2026-04-06", 50)
    _add_late_attendance(conn, emp1, "2026-04-07", 30)
    # YASMIN: 60 mnt total (under 75)
    _add_late_attendance(conn, emp2, "2026-04-06", 60)

    rows = [dict(r) for r in list_coaching_for_week(
        conn, week_start="2026-04-06", week_end="2026-04-12",
        threshold_minutes=75,
    )]
    assert len(rows) == 1
    assert rows[0]["nama"] == "ANDIKA"
    assert rows[0]["total_terlambat"] == 80
    assert rows[0]["is_coached"] == 0


def test_list_coaching_flags_is_coached_correctly():
    conn = _conn()
    emp_id = _add_employee(conn)
    _add_late_attendance(conn, emp_id, "2026-04-06", 100)
    mark_coached(conn, employee_id=emp_id, week_start="2026-04-06")

    rows = [dict(r) for r in list_coaching_for_week(
        conn, week_start="2026-04-06", week_end="2026-04-12",
        threshold_minutes=75,
    )]
    assert len(rows) == 1
    assert rows[0]["is_coached"] == 1
    assert rows[0]["coached_at"] is not None


def test_list_coaching_excludes_work_justified_lateness():
    conn = _conn()
    emp_id = _add_employee(conn)
    _add_late_attendance(conn, emp_id, "2026-04-06", 100)  # would be over threshold
    # But it's actually tugas_lapangan, so excluded
    row_id = conn.execute(
        "SELECT id FROM attendance_records WHERE tanggal='2026-04-06'"
    ).fetchone()["id"]
    set_reason(conn, attendance_id=row_id, category="tugas_lapangan",
               detail="kunjungan klien")

    rows = [dict(r) for r in list_coaching_for_week(
        conn, week_start="2026-04-06", week_end="2026-04-12",
        threshold_minutes=75,
    )]
    assert rows == []  # excluded — not over threshold once work-justified removed
```

### Step 3: Run tests to verify they fail

```
../../../.venv/Scripts/python.exe -m pytest tests/test_coaching_db.py -v
```

Expected: **all 8 tests fail** with `ImportError: cannot import name 'mark_coached' from 'src.db.coaching'`.

### Step 4: Implement `src/db/coaching.py`

Create file `src/db/coaching.py` with EXACTLY this content:

```python
"""Coaching session CRUD + list query for the Coaching screen.

A coaching session row exists when an employee has been marked as coached for
a given week. Absence of a row = "Belum coached". Notes are optional.
"""
import sqlite3
from datetime import datetime, UTC
from typing import Optional


def mark_coached(
    conn: sqlite3.Connection,
    *,
    employee_id: int,
    week_start: str,
    notes: Optional[str] = None,
) -> None:
    """Insert or update a coaching session (UPSERT). Idempotent.

    coached_at is always set to now() on insert. On conflict (same employee
    + same week), only notes is overwritten — coached_at preserved.
    """
    now = datetime.now(UTC).isoformat(timespec="seconds")
    conn.execute(
        """
        INSERT INTO coaching_sessions (employee_id, week_start, coached_at, notes)
        VALUES (?, ?, ?, ?)
        ON CONFLICT (employee_id, week_start) DO UPDATE SET
            notes = excluded.notes
        """,
        (employee_id, week_start, now, notes),
    )


def unmark_coached(
    conn: sqlite3.Connection,
    *,
    employee_id: int,
    week_start: str,
) -> None:
    """Delete a coaching session — toggles Sudah back to Belum."""
    conn.execute(
        "DELETE FROM coaching_sessions WHERE employee_id = ? AND week_start = ?",
        (employee_id, week_start),
    )


def get_coaching_notes(
    conn: sqlite3.Connection,
    *,
    employee_id: int,
    week_start: str,
) -> Optional[str]:
    """Return notes for the session, or None if no session exists."""
    row = conn.execute(
        "SELECT notes FROM coaching_sessions WHERE employee_id = ? AND week_start = ?",
        (employee_id, week_start),
    ).fetchone()
    return row["notes"] if row else None


def update_notes(
    conn: sqlite3.Connection,
    *,
    employee_id: int,
    week_start: str,
    notes: Optional[str],
) -> None:
    """Update notes on an existing session (no-op if session doesn't exist)."""
    conn.execute(
        """
        UPDATE coaching_sessions
           SET notes = ?
         WHERE employee_id = ? AND week_start = ?
        """,
        (notes, employee_id, week_start),
    )


def list_coaching_for_week(
    conn: sqlite3.Connection,
    *,
    week_start: str,
    week_end: str,
    threshold_minutes: int = 75,
):
    """Return pegawai over the lateness threshold in given week, with status.

    Lateness aggregation mirrors src/core/insights.py:
      - Requires masuk IS NOT NULL (employee must have clocked in)
      - Excludes work-justified categories (tugas_lapangan, tugas_paparan, terlambat_kerja)

    LEFT JOIN with coaching_sessions to flag is_coached.

    Returns sqlite3.Row with columns:
      - employee_id, nama, dept, no_staff
      - total_terlambat (int, minutes)
      - week_start (echo)
      - coached_at (str ISO datetime, or NULL)
      - is_coached (1 or 0)
    """
    return conn.execute(
        """
        WITH terlambat AS (
            SELECT
                ar.employee_id,
                SUM(CASE
                    WHEN ar.reason_category IN ('tugas_lapangan', 'tugas_paparan', 'terlambat_kerja')
                        THEN 0
                    WHEN ar.masuk IS NULL THEN 0
                    ELSE COALESCE(ar.terlambat_menit, 0)
                END) AS total_terlambat
              FROM attendance_records ar
             WHERE ar.tanggal BETWEEN ? AND ?
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
        """,
        (week_start, week_end, week_start, week_start, threshold_minutes),
    ).fetchall()
```

### Step 5: Run tests to verify they pass

```
../../../.venv/Scripts/python.exe -m pytest tests/test_coaching_db.py -v
```

Expected: **8 passed**.

### Step 6: Run full pytest

```
../../../.venv/Scripts/python.exe -m pytest -q
```

Expected: **94 passed** (86 baseline + 8 new).

### Step 7: Commit Task 1

```bash
git add src/db/schema.py src/db/coaching.py tests/test_coaching_db.py
git commit -m "$(cat <<'EOF'
feat(db): coaching_sessions table + coaching CRUD module

- schema.py DDL adds CREATE TABLE coaching_sessions (idempotent IF NOT EXISTS)
- src/db/coaching.py: 5 functions
  * mark_coached (UPSERT)
  * unmark_coached (DELETE)
  * get_coaching_notes (SELECT notes)
  * update_notes (UPDATE notes)
  * list_coaching_for_week (over-threshold + LEFT JOIN sessions)
- 8 unit tests covering CRUD + list edge cases (over-threshold,
  is_coached flag, work-justified exclusion)

Part 1 of 7 in Coaching + Unresolve feature.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: WeekNavBar `include_all` Parameter

**Files:**
- Modify: `src/ui/components/week_nav.py`

### Step 1: Add `include_all` parameter

In `src/ui/components/week_nav.py`, locate the `__init__` method (lines 24-43). Replace it with:

```python
    def __init__(
        self,
        parent,
        current_month: str,
        on_change: Callable[[str], None],
        initial: str = "semua",
        include_all: bool = True,
    ):
        super().__init__(parent, fg_color="transparent")
        self._on_change = on_change
        self._buttons: Dict[str, ctk.CTkButton] = {}
        self._active = initial

        if include_all:
            self._make_pill("semua", "Semua")
        if current_month:
            for num, start, end in weeks_in_month(current_month):
                s_day = start.split("-")[2]
                e_day = end.split("-")[2]
                self._make_pill(f"minggu_{num}", f"Minggu {num} ({s_day}-{e_day})")

        # If the requested initial isn't actually rendered (e.g., "semua" with
        # include_all=False), fall back to the first available pill.
        if self._active not in self._buttons and self._buttons:
            self._active = next(iter(self._buttons.keys()))

        self._refresh_styles()
```

### Step 2: Sanity check — existing consumers unchanged

```
../../../.venv/Scripts/python.exe -c "from src.ui.components.week_nav import WeekNavBar; print('OK')"
../../../.venv/Scripts/python.exe -m pytest -q
```

Expected: `OK` then **94 passed** (no regression — existing callers don't pass `include_all`, so default `True` preserves behavior).

### Step 3: Commit Task 2

```bash
git add src/ui/components/week_nav.py
git commit -m "$(cat <<'EOF'
feat(ui): WeekNavBar include_all parameter for weekly-only screens

Adds include_all: bool = True parameter. When False, the "Semua" pill is
not rendered (useful for screens where monthly aggregation is meaningless,
like the upcoming Coaching screen). Falls back gracefully to first
available week pill if initial="semua" but include_all=False.

Existing callers (Dashboard, Issues) unaffected — default True preserves
current behavior.

Part 2 of 7 in Coaching + Unresolve feature.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Coaching Screen UI

**Files:**
- Create: `src/ui/screens/coaching.py`

### Step 1: Create CoachingScreen module

Create `src/ui/screens/coaching.py` with EXACTLY this content:

```python
"""Coaching screen — weekly view of pegawai over lateness threshold with
one-click toggle to mark coached and optional notes panel."""
from tkinter import ttk
import customtkinter as ctk

from src.config import DB_PATH
from src.core.week_utils import weeks_in_month
from src.db.attendance import upsert_attendance  # unused? remove if not
from src.db.coaching import (
    list_coaching_for_week, mark_coached, unmark_coached,
    get_coaching_notes, update_notes,
)
from src.db.connection import get_connection
from src.db.settings import get_setting
from src.ui.components.kpi_card import KPICard
from src.ui.components.week_nav import WeekNavBar
from src.ui.theme import (
    FONT_FAMILY, COLOR_OK, COLOR_WARN, COLOR_ACCENT, COLOR_ERR,
    COLOR_PANEL, COLOR_TEXT, COLOR_TEXT_DIM,
)


class CoachingScreen(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        self.grid_columnconfigure(0, weight=2)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(2, weight=1)

        with get_connection(DB_PATH) as conn:
            self._current_month = get_setting(conn, "current_month") or ""
            threshold_raw = get_setting(conn, "coaching_threshold_min") or "75"
            try:
                self._threshold = int(threshold_raw)
            except ValueError:
                self._threshold = 75

        self.selected_row = None  # dict from _row_cache when row is selected
        self._row_cache = {}      # iid -> row dict

        self._setup_treeview_style()
        self._build_header()
        self._build_stats()
        self._build_table_and_panel()
        self._reload()

    def _setup_treeview_style(self):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure(
            "Coaching.Treeview",
            background=COLOR_PANEL, fieldbackground=COLOR_PANEL,
            foreground=COLOR_TEXT, rowheight=28, borderwidth=0,
        )
        style.configure(
            "Coaching.Treeview.Heading",
            background="#2C1B47", foreground=COLOR_TEXT_DIM,
            relief="flat", font=(FONT_FAMILY, 10, "bold"),
        )
        style.map(
            "Coaching.Treeview",
            background=[("selected", COLOR_ACCENT)],
            foreground=[("selected", "#1E104E")],
        )

    def _build_header(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 12))
        ctk.CTkLabel(header, text="🎯 Coaching",
                     font=(FONT_FAMILY, 24, "bold"),
                     text_color=COLOR_TEXT).pack(side="left", padx=(0, 16))
        self.nav = WeekNavBar(
            header, current_month=self._current_month,
            on_change=self._on_period_change, initial="minggu_1",
            include_all=False,
        )
        self.nav.pack(side="left")

    def _on_period_change(self, _key):
        self._reload()

    def _build_stats(self):
        self.stats = ctk.CTkFrame(self, fg_color="transparent")
        self.stats.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 12))
        for i in range(4):
            self.stats.grid_columnconfigure(i, weight=1)
        self._stats_cards = []

    def _render_stats(self, rows):
        for c in self._stats_cards:
            c.destroy()
        self._stats_cards = []

        total = len(rows)
        sudah = sum(1 for r in rows if r["is_coached"])
        belum = total - sudah
        if total > 0:
            coverage = f"{round(sudah / total * 100)}%"
        else:
            coverage = "—"

        cards = [
            ("Total", str(total), COLOR_ACCENT),
            ("Sudah", str(sudah), COLOR_OK),
            ("Belum", str(belum), COLOR_WARN),
            ("Coverage", coverage, COLOR_OK if total == 0 or sudah == total else COLOR_TEXT),
        ]
        for i, (label, val, color) in enumerate(cards):
            c = KPICard(self.stats, label, val, value_color=color)
            c.grid(row=0, column=i, padx=4, sticky="ew")
            self._stats_cards.append(c)

    def _build_table_and_panel(self):
        left = ctk.CTkFrame(self, fg_color="transparent")
        left.grid(row=2, column=0, sticky="nsew", padx=(0, 12))
        left.grid_columnconfigure(0, weight=1)
        left.grid_rowconfigure(0, weight=1)

        cols = ["nama", "dept", "terlambat", "status", "aksi"]
        widths = {"nama": 130, "dept": 100, "terlambat": 90, "status": 110, "aksi": 110}
        labels = {"nama": "Nama", "dept": "Dept", "terlambat": "Terlambat",
                  "status": "Status", "aksi": "Aksi"}

        self.tree = ttk.Treeview(
            left, columns=cols, show="headings",
            style="Coaching.Treeview", selectmode="browse", height=12,
        )
        for c in cols:
            self.tree.heading(c, text=labels[c])
            self.tree.column(c, width=widths[c], anchor="w")
        # Tag-based row tinting
        self.tree.tag_configure("belum", background="#3F2A2C", foreground=COLOR_TEXT)
        self.tree.tag_configure("sudah", background="#2A3F30", foreground=COLOR_TEXT)
        self.tree.grid(row=0, column=0, sticky="nsew")
        self.tree.bind("<Button-1>", self._on_tree_click)
        self.tree.bind("<<TreeviewSelect>>", self._on_select)

        right = ctk.CTkFrame(self, fg_color=COLOR_PANEL, corner_radius=8)
        right.grid(row=2, column=1, sticky="nsew")
        self.right = right
        self._build_panel_empty()

    def _build_panel_empty(self):
        for w in self.right.winfo_children():
            w.destroy()
        ctk.CTkLabel(
            self.right,
            text="Pilih baris untuk lihat detail\natau klik kolom Aksi untuk\nubah status coaching.",
            justify="center",
            font=(FONT_FAMILY, 12), text_color=COLOR_TEXT_DIM
        ).pack(pady=80, padx=16)

    def _active_range(self):
        """Return (start, end, num) for the currently selected week pill."""
        key = self.nav.active
        try:
            num = int(key.split("_")[1])
        except (IndexError, ValueError):
            num = 1
        if not self._current_month:
            return None, None, num
        for n, start, end in weeks_in_month(self._current_month):
            if n == num:
                return start, end, num
        return None, None, num

    def _reload(self):
        start, end, _num = self._active_range()
        self._row_cache = {}
        for item in self.tree.get_children():
            self.tree.delete(item)

        if not start:
            self._render_stats([])
            return

        with get_connection(DB_PATH) as conn:
            raw_rows = list_coaching_for_week(
                conn, week_start=start, week_end=end,
                threshold_minutes=self._threshold,
            )
        rows = [dict(r) for r in raw_rows]
        self._render_stats(rows)

        for r in rows:
            iid = str(r["employee_id"])
            self._row_cache[iid] = r
            is_coached = bool(r["is_coached"])
            status_text = "✓ Sudah" if is_coached else "○ Belum"
            aksi_text = "⊖ Batalkan" if is_coached else "⊕ Tandai"
            tag = "sudah" if is_coached else "belum"
            self.tree.insert(
                "", "end", iid=iid,
                values=(
                    r["nama"], r["dept"] or "-",
                    f"{r['total_terlambat']} mnt",
                    status_text, aksi_text,
                ),
                tags=(tag,),
            )

    def _on_tree_click(self, event):
        region = self.tree.identify_region(event.x, event.y)
        column = self.tree.identify_column(event.x)
        row_iid = self.tree.identify_row(event.y)
        if region != "cell" or not row_iid:
            return
        # Aksi column is the 5th column → "#5"
        if column == "#5":
            self._toggle_row(row_iid)
            return "break"  # prevent selection event

    def _toggle_row(self, iid: str):
        row = self._row_cache.get(iid)
        if not row:
            return
        start, _end, _num = self._active_range()
        if not start:
            return
        with get_connection(DB_PATH) as conn:
            if row["is_coached"]:
                unmark_coached(conn, employee_id=row["employee_id"], week_start=start)
            else:
                mark_coached(conn, employee_id=row["employee_id"], week_start=start)
        self._reload()
        # Re-select to keep panel in sync if the row is still visible
        if iid in self.tree.get_children():
            self.tree.selection_set(iid)

    def _on_select(self, _evt):
        sel = self.tree.selection()
        if not sel:
            return
        iid = sel[0]
        row = self._row_cache.get(iid)
        if row:
            self.selected_row = row
            self._build_panel_for(row)

    def _build_panel_for(self, row):
        for w in self.right.winfo_children():
            w.destroy()

        start, end, num = self._active_range()
        info_lines = [
            f"{row['nama']} ({row['dept'] or '-'})",
            f"Minggu {num} ({start} → {end})",
            f"Total terlambat: {row['total_terlambat']} mnt",
        ]
        ctk.CTkLabel(self.right, text="\n".join(info_lines), justify="left",
                     font=(FONT_FAMILY, 12), text_color=COLOR_TEXT
                     ).pack(anchor="w", padx=16, pady=(16, 12))

        is_coached = bool(row["is_coached"])
        status_color = COLOR_OK if is_coached else COLOR_WARN
        status_lines = ["Status: " + ("✓ Sudah Coaching" if is_coached else "○ Belum Coaching")]
        if is_coached and row.get("coached_at"):
            status_lines.append(f"Tercatat: {row['coached_at']}")
        ctk.CTkLabel(self.right, text="\n".join(status_lines), justify="left",
                     font=(FONT_FAMILY, 11), text_color=status_color
                     ).pack(anchor="w", padx=16, pady=(0, 12))

        ctk.CTkLabel(self.right, text="Catatan (opsional):",
                     font=(FONT_FAMILY, 11), text_color=COLOR_TEXT_DIM
                     ).pack(anchor="w", padx=16)

        notes_box = ctk.CTkTextbox(self.right, width=300, height=110)
        notes_box.pack(anchor="w", padx=16, pady=(4, 8))

        if is_coached:
            existing = ""
            with get_connection(DB_PATH) as conn:
                existing = get_coaching_notes(
                    conn, employee_id=row["employee_id"], week_start=start,
                ) or ""
            notes_box.insert("1.0", existing)
            save_btn = ctk.CTkButton(
                self.right, text="Simpan Catatan",
                fg_color=COLOR_OK, text_color="#1E104E", width=300,
                command=lambda: self._on_save_notes(row, notes_box.get("1.0", "end").strip()),
            )
            save_btn.pack(anchor="w", padx=16, pady=8)
        else:
            notes_box.insert("1.0", "(Tandai Sudah Coaching dulu untuk simpan catatan)")
            notes_box.configure(state="disabled")

    def _on_save_notes(self, row, text: str):
        start, _end, _num = self._active_range()
        if not start:
            return
        notes_value = text if text else None
        with get_connection(DB_PATH) as conn:
            update_notes(
                conn, employee_id=row["employee_id"], week_start=start,
                notes=notes_value,
            )
        # Refresh: keep selection same row so panel updates
        self._reload()
        iid = str(row["employee_id"])
        if iid in self.tree.get_children():
            self.tree.selection_set(iid)
```

### Step 2: Clean up unused import

Look at the imports at the top of the file. `upsert_attendance` is imported but unused — remove it. The cleaned imports block should be:

```python
from src.config import DB_PATH
from src.core.week_utils import weeks_in_month
from src.db.coaching import (
    list_coaching_for_week, mark_coached, unmark_coached,
    get_coaching_notes, update_notes,
)
from src.db.connection import get_connection
from src.db.settings import get_setting
from src.ui.components.kpi_card import KPICard
from src.ui.components.week_nav import WeekNavBar
from src.ui.theme import (
    FONT_FAMILY, COLOR_OK, COLOR_WARN, COLOR_ACCENT,
    COLOR_PANEL, COLOR_TEXT, COLOR_TEXT_DIM,
)
```

(Remove `COLOR_ERR` too if it's unused. Verify with grep before removing.)

### Step 3: Sanity import check

```
../../../.venv/Scripts/python.exe -c "from src.ui.screens.coaching import CoachingScreen; print('OK')"
```

Expected: `OK`.

If `ImportError` on `KPICard` or any theme constant: verify exact name in source file, adjust.

### Step 4: Run pytest — regression

```
../../../.venv/Scripts/python.exe -m pytest -q
```

Expected: **94 passed**.

### Step 5: Commit Task 3

```bash
git add src/ui/screens/coaching.py
git commit -m "$(cat <<'EOF'
feat(ui): CoachingScreen — weekly coaching tracker with one-click toggle

New screen mirrors Issues layout:
- WeekNavBar (no Semua, weekly only) pills M1..M5
- 4 KPI cards: Total/Sudah/Belum/Coverage%
- ttk.Treeview with tag-based row tinting (warm for Belum, cool for Sudah)
- Click on AKSI column toggles status (no confirm, instant)
- Click on row body opens right panel with status info + optional notes
- Notes editable only for Sudah rows; Belum shows grayed-out hint

Part 3 of 7 in Coaching + Unresolve feature.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Sidebar Registration for Coaching

**Files:**
- Modify: `src/ui/app.py`

### Step 1: Add Coaching to sidebar nav_items

In `src/ui/app.py`, locate the `nav_items` list (currently has 7 entries after Task 5 of previous feature). Insert "🎯 Coaching" between "Riwayat Bulan" and "Settings":

Current:
```python
        nav_items = [
            ("📊 Dashboard", "Dashboard"),
            ("📥 Import", "Import"),
            ("⚠ Issues", "Issues"),
            ("📋 Summary", "Summary"),
            ("📤 Export", "Export"),
            ("🗓 Riwayat Bulan", "Months"),
            ("⚙ Settings", "Settings"),
        ]
```

Replace with:
```python
        nav_items = [
            ("📊 Dashboard", "Dashboard"),
            ("📥 Import", "Import"),
            ("⚠ Issues", "Issues"),
            ("📋 Summary", "Summary"),
            ("📤 Export", "Export"),
            ("🗓 Riwayat Bulan", "Months"),
            ("🎯 Coaching", "Coaching"),
            ("⚙ Settings", "Settings"),
        ]
```

### Step 2: Add Coaching branch to `_show()`

In `_show()` method, locate the existing branches. Insert `elif name == "Coaching":` between `Months` and `Settings`:

Current relevant section:
```python
        elif name == "Months":
            from src.ui.screens.months import MonthsScreen
            MonthsScreen(self.content).grid(row=0, column=0, sticky="nsew")
        elif name == "Settings":
            from src.ui.screens.settings import SettingsScreen
            SettingsScreen(self.content).grid(row=0, column=0, sticky="nsew")
```

Replace with:
```python
        elif name == "Months":
            from src.ui.screens.months import MonthsScreen
            MonthsScreen(self.content).grid(row=0, column=0, sticky="nsew")
        elif name == "Coaching":
            from src.ui.screens.coaching import CoachingScreen
            CoachingScreen(self.content).grid(row=0, column=0, sticky="nsew")
        elif name == "Settings":
            from src.ui.screens.settings import SettingsScreen
            SettingsScreen(self.content).grid(row=0, column=0, sticky="nsew")
```

### Step 3: Sanity check

```
../../../.venv/Scripts/python.exe -c "from src.ui.app import HRApp; from src.ui.screens.coaching import CoachingScreen; print('OK')"
../../../.venv/Scripts/python.exe -m pytest -q
```

Expected: `OK` then **94 passed**.

### Step 4: Commit Task 4

```bash
git add src/ui/app.py
git commit -m "$(cat <<'EOF'
feat(ui): register 🎯 Coaching sidebar menu

Sidebar grows from 7 to 8 items: Coaching inserted between Riwayat Bulan
and Settings (key: "Coaching"). HRApp._show() handles the new branch.

Part 4 of 7 in Coaching + Unresolve feature.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: `unresolve_issue` DB Function (TDD)

**Files:**
- Modify: `src/db/attendance.py` (append 1 function)
- Create: `tests/test_unresolve_issue.py`

### Step 1: Write failing tests

Create `tests/test_unresolve_issue.py` with EXACTLY this content:

```python
"""Tests for unresolve_issue — clears reason fields to revert to Open."""
import sqlite3

from src.db.schema import DDL
from src.db.employees import upsert_employee
from src.db.attendance import upsert_attendance, set_reason, unresolve_issue


def _conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(DDL)
    return conn


def _add_resolved_issue(conn):
    """Create one employee with one resolved issue. Returns attendance_id."""
    emp_id = upsert_employee(conn, no_staff="E001", nama="ANDIKA",
                              dept="ARGA", phone=None)
    upsert_attendance(
        conn, employee_id=emp_id, tanggal="2026-04-01",
        hari="Rabu", tipe="Hari Kerja", jadwal="08.00 - 16.00",
        masuk=None, keluar=None,
        kerja_jam=None, lembur_jam=None, terlambat_menit=None,
        has_issue=1, imported_from="test.xls",
    )
    row_id = conn.execute(
        "SELECT id FROM attendance_records WHERE tanggal='2026-04-01'"
    ).fetchone()["id"]
    set_reason(conn, attendance_id=row_id,
               category="izin_sakit", detail=None)
    return row_id


def test_unresolve_clears_three_fields():
    conn = _conn()
    att_id = _add_resolved_issue(conn)
    unresolve_issue(conn, attendance_id=att_id)
    row = conn.execute(
        "SELECT reason_category, reason_detail, resolved_at "
        "FROM attendance_records WHERE id=?", (att_id,)
    ).fetchone()
    assert row["reason_category"] is None
    assert row["reason_detail"] is None
    assert row["resolved_at"] is None


def test_unresolve_does_not_touch_other_rows():
    conn = _conn()
    att_id_1 = _add_resolved_issue(conn)
    # Add a second resolved row
    upsert_attendance(
        conn, employee_id=1, tanggal="2026-04-02",
        hari="Kamis", tipe="Hari Kerja", jadwal="08.00 - 16.00",
        masuk=None, keluar=None,
        kerja_jam=None, lembur_jam=None, terlambat_menit=None,
        has_issue=1, imported_from="test.xls",
    )
    att_id_2 = conn.execute(
        "SELECT id FROM attendance_records WHERE tanggal='2026-04-02'"
    ).fetchone()["id"]
    set_reason(conn, attendance_id=att_id_2, category="cuti", detail=None)

    unresolve_issue(conn, attendance_id=att_id_1)

    row2 = conn.execute(
        "SELECT reason_category FROM attendance_records WHERE id=?", (att_id_2,)
    ).fetchone()
    assert row2["reason_category"] == "cuti"  # untouched


def test_unresolve_idempotent_on_already_null():
    conn = _conn()
    att_id = _add_resolved_issue(conn)
    unresolve_issue(conn, attendance_id=att_id)
    # Second call should no-op (fields already NULL)
    unresolve_issue(conn, attendance_id=att_id)
    row = conn.execute(
        "SELECT reason_category, reason_detail, resolved_at "
        "FROM attendance_records WHERE id=?", (att_id,)
    ).fetchone()
    assert row["reason_category"] is None
    assert row["reason_detail"] is None
    assert row["resolved_at"] is None
```

### Step 2: Run tests to verify they fail

```
../../../.venv/Scripts/python.exe -m pytest tests/test_unresolve_issue.py -v
```

Expected: **3 errors** with `ImportError: cannot import name 'unresolve_issue' from 'src.db.attendance'`.

### Step 3: Implement `unresolve_issue`

In `src/db/attendance.py`, append at the END of the file (after `list_months_with_stats`):

```python
def unresolve_issue(conn: sqlite3.Connection, *, attendance_id: int) -> None:
    """Clear resolve state on an attendance row.

    Sets reason_category, reason_detail, resolved_at all to NULL. The row
    becomes "Open" again. Used by the Issues 'Batalkan Resolve' button.
    """
    conn.execute(
        """
        UPDATE attendance_records
           SET reason_category = NULL,
               reason_detail = NULL,
               resolved_at = NULL
         WHERE id = ?
        """,
        (attendance_id,),
    )
```

### Step 4: Run tests to verify they pass

```
../../../.venv/Scripts/python.exe -m pytest tests/test_unresolve_issue.py -v
```

Expected: **3 passed**.

### Step 5: Full pytest

```
../../../.venv/Scripts/python.exe -m pytest -q
```

Expected: **97 passed** (94 + 3 new).

### Step 6: Commit Task 5

```bash
git add src/db/attendance.py tests/test_unresolve_issue.py
git commit -m "$(cat <<'EOF'
feat(db): unresolve_issue function — revert Resolved → Open

Clears reason_category, reason_detail, resolved_at all to NULL. Powers
the upcoming 'Batalkan Resolve' button in Issues right panel.

3 tests cover: field clearing, scope isolation, idempotency.

Part 5 of 7 in Coaching + Unresolve feature.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: Issues "Batalkan Resolve" Button

**Files:**
- Modify: `src/ui/screens/issues.py`

### Step 1: Import unresolve_issue

In `src/ui/screens/issues.py`, locate the existing import:

```python
from src.db.attendance import (
    set_reason, list_issues_for_period, count_issues_for_period,
)
```

Replace with:
```python
from src.db.attendance import (
    set_reason, list_issues_for_period, count_issues_for_period,
    unresolve_issue,
)
```

Also verify `COLOR_ERR` is in the theme import at the top of the file. If not, add it:
```python
from src.ui.theme import (
    FONT_FAMILY, COLOR_OK, COLOR_WARN, COLOR_ERR, COLOR_ACCENT,
    COLOR_PANEL, COLOR_PANEL_OPEN, COLOR_PANEL_RESOLVED,
    COLOR_TEXT, COLOR_TEXT_DIM,
)
```

### Step 2: Conditionally show "Batalkan Resolve" button in `_build_panel_for`

In `_build_panel_for(self, row_data)` (around line 182-226), after the existing `self.save_btn` definition and before the `_lay_out_form` call at line 226, add the unresolve button definition:

Current (around lines 219-226):
```python
        # Save button — keep a reference so we can repack it below detail when shown
        self.save_btn = ctk.CTkButton(
            self.right, text="Simpan", command=self._on_save,
            fg_color=COLOR_OK, text_color="#1E104E", width=300,
        )

        # Initial layout (Save below the optional detail)
        self._lay_out_form(initial_cat=current)
```

Replace with:
```python
        # Save button — keep a reference so we can repack it below detail when shown
        self.save_btn = ctk.CTkButton(
            self.right, text="Simpan", command=self._on_save,
            fg_color=COLOR_OK, text_color="#1E104E", width=300,
        )

        # Unresolve button — only shown when row is currently resolved
        # (reason_category is not None). Lay out below Save in _lay_out_form.
        self.unresolve_btn = ctk.CTkButton(
            self.right, text="↶ Batalkan Resolve", command=self._on_unresolve,
            fg_color=COLOR_ERR, text_color="#1E104E", width=300,
        )
        self._row_is_resolved = current is not None

        # Initial layout (Save below the optional detail)
        self._lay_out_form(initial_cat=current)
```

### Step 3: Update `_lay_out_form` to handle unresolve button

Find the existing `_lay_out_form` method (around lines 228-241):

```python
    def _lay_out_form(self, initial_cat: str | None):
        """(Re)pack detail widgets and Save button in correct order.

        Order:  cat_combo  ->  (detail_label  ->  detail_entry)?  ->  save_btn
        """
        # Always re-pack from the bottom so Save lands last
        self.detail_label.pack_forget()
        self.detail_entry.pack_forget()
        self.save_btn.pack_forget()

        if initial_cat and initial_cat in REASON_NEEDS_DETAIL:
            self.detail_label.pack(anchor="w", padx=16)
            self.detail_entry.pack(anchor="w", padx=16, pady=(4, 12))
        self.save_btn.pack(anchor="w", padx=16, pady=12)
```

Replace with:
```python
    def _lay_out_form(self, initial_cat: str | None):
        """(Re)pack detail widgets, Save button, and (if resolved) unresolve button.

        Order:  cat_combo -> (detail_label -> detail_entry)? -> save_btn -> [unresolve_btn?]
        """
        # Always re-pack from the bottom so Save lands last (and unresolve below that)
        self.detail_label.pack_forget()
        self.detail_entry.pack_forget()
        self.save_btn.pack_forget()
        self.unresolve_btn.pack_forget()

        if initial_cat and initial_cat in REASON_NEEDS_DETAIL:
            self.detail_label.pack(anchor="w", padx=16)
            self.detail_entry.pack(anchor="w", padx=16, pady=(4, 12))
        self.save_btn.pack(anchor="w", padx=16, pady=(12, 4))
        if self._row_is_resolved:
            self.unresolve_btn.pack(anchor="w", padx=16, pady=(0, 12))
```

### Step 4: Add `_on_unresolve` handler

After the existing `_on_save` method (search for `def _on_save(self):`), add this method:

```python
    def _on_unresolve(self):
        if self.selected_id is None:
            return
        confirmed = messagebox.askyesno(
            "Konfirmasi",
            "Batalkan resolve?\n\n"
            "Kategori dan detail alasan akan dihapus.\n"
            "Issue akan kembali ke status Open.",
        )
        if not confirmed:
            return
        with get_connection(DB_PATH) as conn:
            unresolve_issue(conn, attendance_id=self.selected_id)
        self._reload()
        self._build_panel_empty()
        self.selected_id = None
```

### Step 5: Sanity import check

```
../../../.venv/Scripts/python.exe -c "from src.ui.screens.issues import IssuesScreen; print('OK')"
```

Expected: `OK`.

### Step 6: Run pytest — regression

```
../../../.venv/Scripts/python.exe -m pytest -q
```

Expected: **97 passed**.

### Step 7: Commit Task 6

```bash
git add src/ui/screens/issues.py
git commit -m "$(cat <<'EOF'
feat(ui): Issues — Batalkan Resolve button for resolved rows

When a Resolved row is selected, right panel shows additional button
below Save. Confirm dialog asks before clearing fields. After confirm:
unresolve_issue clears reason_category/reason_detail/resolved_at to
NULL, table reloads, row moves back to Open table.

For Open rows (no reason yet): button not shown.

Part 6 of 7 in Coaching + Unresolve feature.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: Build .exe + Deploy

**Files:** none modified — build + deploy only.

### Step 1: Final pytest

```
../../../.venv/Scripts/python.exe -m pytest -q
```

Expected: **97 passed**.

### Step 2: PyInstaller build

```
../../../.venv/Scripts/pyinstaller.exe HR-Absensi.spec --clean --noconfirm
```

Expected: Build complete (~2 minutes). Output in `dist/HR-Absensi/`.

### Step 3: Verify build output

```
ls -la dist/HR-Absensi/HR-Absensi.exe
```

Expected: ~13 MB, timestamp now.

### Step 4: Deploy with rotation

```bash
set -e
TARGET="../../../dist/HR-Absensi"
SRC="dist/HR-Absensi"

# Remove old 2-back if exists (we only keep 1-back)
[ -f "$TARGET/HR-Absensi.exe.bak.old" ] && rm "$TARGET/HR-Absensi.exe.bak.old"
[ -d "$TARGET/_internal.bak.old" ] && rm -rf "$TARGET/_internal.bak.old"
# Rotate current .bak → .bak.old
[ -f "$TARGET/HR-Absensi.exe.bak" ] && mv "$TARGET/HR-Absensi.exe.bak" "$TARGET/HR-Absensi.exe.bak.old"
[ -d "$TARGET/_internal.bak" ] && mv "$TARGET/_internal.bak" "$TARGET/_internal.bak.old"
# Backup current production
mv "$TARGET/HR-Absensi.exe" "$TARGET/HR-Absensi.exe.bak"
mv "$TARGET/_internal" "$TARGET/_internal.bak"
# Deploy new
cp "$SRC/HR-Absensi.exe" "$TARGET/HR-Absensi.exe"
cp -r "$SRC/_internal" "$TARGET/_internal"

echo ""
echo "=== Final state ==="
ls -la "$TARGET/" | grep -v "^total"
echo ""
echo "=== Data preserved? ==="
ls "$TARGET/data/"
```

Expected:
- New `HR-Absensi.exe` with today's timestamp
- `HR-Absensi.exe.bak` from previous deploy (Coaching pre-cleanup)
- `data/hr.db` untouched
- Template still bundled in new `_internal/templates/`

### Step 5: No commit needed for Task 7

Build + deploy doesn't change source. Verify git status clean:

```
git status
```

Expected: `nothing to commit, working tree clean` (no source changes pending).

---

## Definition of Done

- [ ] `coaching_sessions` table exists in schema (idempotent CREATE TABLE IF NOT EXISTS)
- [ ] `src/db/coaching.py` exports 5 functions: `mark_coached`, `unmark_coached`, `get_coaching_notes`, `update_notes`, `list_coaching_for_week`
- [ ] `src/db/attendance.py` exports `unresolve_issue`
- [ ] `src/ui/components/week_nav.py` accepts `include_all: bool = True` parameter
- [ ] `src/ui/screens/coaching.py` exists — CoachingScreen with WeekNavBar (no Semua), KPI cards, Treeview with tag tints + click handlers, right panel notes
- [ ] `src/ui/screens/issues.py` has "Batalkan Resolve" button conditionally rendered for resolved rows
- [ ] `src/ui/app.py` sidebar has 8 items including 🎯 Coaching
- [ ] **97 tests passing** (86 baseline + 8 coaching + 3 unresolve)
- [ ] New .exe deployed to main repo dist with `.bak` rotation
- [ ] User's `data/hr.db` preserved untouched
- [ ] User runs manual smoke test (see Section 8.2 of spec)

---

## Manual Smoke Test (deferred to user, after Task 7)

After Task 7 completes, the controller asks user to perform these on the deployed `.exe`:

1. Launch app → sidebar shows 8 items including "🎯 Coaching"
2. Click Coaching → WeekNavBar shows only Minggu pills (no "Semua"). KPI cards visible.
3. Empty week (or no data): KPI shows zeros, table empty. Right panel shows hint.
4. Week with pegawai over threshold: rows visible, AKSI column shows "⊕ Tandai", row tinted warm
5. Click AKSI on a Belum row → status flips to "✓ Sudah", row re-tinted cool, KPI updates
6. Click AKSI on a Sudah row (now "⊖ Batalkan") → flips back to Belum
7. Click row body (not AKSI col) → right panel shows status info + notes field
8. For Sudah row: type notes, click Simpan Catatan → toast/visual feedback, persists
9. For Belum row: notes field shows hint, disabled
10. Switch weeks via WeekNavBar → table updates, KPI refreshes
11. Switch month via Riwayat Bulan → Coaching screen reflects new month
12. Open Issues → click resolved row → right panel shows red "↶ Batalkan Resolve" below Save
13. Click "Batalkan Resolve" → confirm dialog appears
14. Confirm → row moves from Resolved to Open table; right panel clears
15. Click Open row → right panel shows Save only (no Batalkan button)

---

## Notes for the Implementing Engineer

- **`.venv` lives at main repo root.** Use `../../../.venv/Scripts/python.exe` for pytest + pyinstaller.
- **Do NOT push to remote** without user approval.
- **Do NOT launch the GUI app** for manual smoke. Defer to user post-Task 7.
- **`Coaching` key string** used in sidebar nav_items + `_show()` branch must match exactly (case-sensitive).
- **AKSI column index "#5"** in Treeview is 1-indexed string format. Verify in `_on_tree_click` matches the cols list order (nama, dept, terlambat, status, aksi → aksi = column 5 = "#5").
- **Threshold per spec** = 75 mnt/minggu fixed at this iteration. Reads from `coaching_threshold_min` setting (default "75"). Doesn't scale per-period like Dashboard.
- **`COLOR_ERR` import in issues.py:** verify it exists in theme.py before assuming. If not, fall back to another red-ish color.

---

*End of plan.*
