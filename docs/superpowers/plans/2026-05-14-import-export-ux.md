# Import + Export UX Refresh Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refresh Import + Export screens dengan file chip + active month banner + dry-run preview + history list + 8 R-items (drag-drop, smart filename detection, conflict resolution, progress modal, folder memory, bulk import, preview, save destination).

**Architecture:** 7 commits sequential. Phase 1 lays DB foundation (new `export_history` table + import/export history queries). Phase 2-3 refresh Import. Phase 4-5 refresh Export. Phase 6 adds shared progress modal + windnd drag-drop. Phase 7 handoff doc. TDD for data/parser layers (new tests added); UI changes verified via pytest regression + manual smoke per phase.

**Tech Stack:** Python 3.13, customtkinter, SQLite, pytest, `windnd` (new Windows-only drag-drop library, ~30 lines), PyInstaller.

---

## Source Spec

[docs/superpowers/specs/2026-05-14-import-export-ux-design.md](../specs/2026-05-14-import-export-ux-design.md) — approved 2026-05-14.

---

## File Structure

### Files to CREATE
| File | Purpose |
|---|---|
| `src/db/export_history.py` | Repo for new `export_history` table — record + list_recent |
| `src/core/filename_parser.py` | Helper to detect YYYY-MM from filenames (Indonesian + ISO) |
| `src/ui/components/progress_modal.py` | Shared CTkToplevel-based progress overlay |
| `tests/test_export_history.py` | Repo tests (4 tests) |
| `tests/test_filename_parser.py` | Parser tests (6 tests) |
| `tests/test_db_list_recent_imports.py` | Import history tests (3 tests) |
| `tests/test_report_filler_dry_run.py` | Dry-run param tests (2 tests) |
| `tests/test_attendance_count_overlap.py` | Conflict count tests (3 tests) |
| `docs/superpowers/specs/2026-05-15-session-handoff-v6.md` | v6 handoff doc |

### Files to MODIFY
| File | Phase | Scope |
|---|---|---|
| `src/db/schema.py` | 1 | Add `export_history` DDL |
| `src/db/attendance.py` | 1, 3 | Add `list_recent_imports`, `count_overlap` |
| `src/core/report_filler.py` | 4 | Add `dry_run` + `out_dir` parameters |
| `src/ui/screens/import_screen.py` | 2, 3, 6 | Full refresh + R3/R5/R6 + R1 wiring + R4 wiring |
| `src/ui/screens/export.py` | 4, 5, 6 | Full refresh + R2/R5/R7/R8 + R4 wiring |
| `requirements.txt` | 6 | Add `windnd` |
| `HR-Absensi.spec` | 6 | Add `windnd` to hiddenimports |

### Test count target
- Current: 98 passing
- Phase 1 adds: ~7 tests (4 export_history + 3 list_recent_imports)
- Phase 3 adds: ~3 tests (count_overlap)
- Phase 4 adds: ~2 tests (dry_run)
- Phase 5 adds: ~6 tests (filename_parser)
- **Total target: 116 passing**

---

## Workflow Conventions

**Engineer reading this plan:** You're in worktree `D:\Gawe\Project X\HR App\.claude\worktrees\nifty-jemison-706792`. The shared venv is 3 levels up.

**Commands** (run from worktree root):
```bash
# Tests
../../../.venv/Scripts/python.exe -m pytest -q
# Baseline: 98 passed. Grows per phase as new tests added.

# Run app for smoke test
../../../.venv/Scripts/python.exe -m src.main
# (Close .exe instance first if running.)

# Build .exe (only at end of plan or when explicitly testing R1 drag-drop)
../../../.venv/Scripts/pyinstaller.exe HR-Absensi.spec --clean --noconfirm
```

**Commit guidance:**
- One commit per phase (7 total).
- Use HEREDOC for multi-line commit messages.
- Co-author trailer: `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>`
- **NO `git push`** — user authorizes manually at end.

**TDD discipline:** For Phase 1 + 3 + 4 + 5 (new functions/parsers), follow strict TDD — write test, run (FAIL), implement, run (PASS), commit. For Phase 2 + 6 (mostly UI), regression check + smoke is the gate.

---

## Task 1: Phase 1 — DB Foundation (export_history + import history)

**Files:**
- Modify: `src/db/schema.py`
- Create: `src/db/export_history.py`
- Modify: `src/db/attendance.py`
- Create: `tests/test_export_history.py`
- Create: `tests/test_db_list_recent_imports.py`

**Goal of this task:** Add `export_history` table + queries for import/export history. Pure data layer, fully tested via TDD.

- [ ] **Step 1.1: Add `export_history` DDL to schema.py**

Open `src/db/schema.py`. Find the existing `init_db` function and the DDL definitions inside it. Add a new CREATE TABLE statement:

```python
# In src/db/schema.py, inside init_db, after existing tables:

conn.execute("""
    CREATE TABLE IF NOT EXISTS export_history (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        out_path    TEXT NOT NULL,
        template    TEXT NOT NULL,
        year_month  TEXT NOT NULL,
        filled      INTEGER NOT NULL,
        na          INTEGER NOT NULL,
        not_found   INTEGER NOT NULL,
        created_at  DATETIME DEFAULT (datetime('now', 'localtime'))
    )
""")

conn.execute("""
    CREATE INDEX IF NOT EXISTS idx_export_history_created_at
        ON export_history(created_at DESC)
""")
```

Place these calls in the same block as the existing tables. The `IF NOT EXISTS` makes the DDL idempotent — safe to re-run on existing DBs.

- [ ] **Step 1.2: Write failing test for `record_export`**

Create `tests/test_export_history.py`:

```python
"""Tests for export_history repo functions."""
import pytest
from src.db.connection import get_connection
from src.db.schema import init_db
from src.db.export_history import record_export, list_recent_exports


@pytest.fixture
def empty_db(tmp_path):
    db_path = tmp_path / "test.db"
    init_db(db_path)
    return db_path


def test_record_export_inserts_row(empty_db):
    with get_connection(empty_db) as conn:
        export_id = record_export(
            conn,
            out_path="/tmp/Laporan April [filled].xlsx",
            template="/tmp/Laporan April.xlsx",
            year_month="2026-04",
            filled=130,
            na=12,
            not_found=0,
        )
    assert export_id > 0

    with get_connection(empty_db) as conn:
        row = conn.execute(
            "SELECT * FROM export_history WHERE id = ?", (export_id,)
        ).fetchone()
    assert row["out_path"] == "/tmp/Laporan April [filled].xlsx"
    assert row["year_month"] == "2026-04"
    assert row["filled"] == 130
    assert row["na"] == 12
    assert row["not_found"] == 0
    assert row["created_at"] is not None
```

- [ ] **Step 1.3: Run test to verify FAIL**

```bash
../../../.venv/Scripts/python.exe -m pytest tests/test_export_history.py -v
```

Expected: ImportError (`record_export` doesn't exist yet) or ModuleNotFoundError on `src.db.export_history`.

- [ ] **Step 1.4: Implement `record_export` + `list_recent_exports`**

Create `src/db/export_history.py`:

```python
"""Repo functions for export_history table.

Tracks each successful Laporan Bulanan export so the UI can show
'Riwayat Export Terakhir' history list.
"""
import sqlite3


def record_export(
    conn: sqlite3.Connection,
    out_path: str,
    template: str,
    year_month: str,
    filled: int,
    na: int,
    not_found: int,
) -> int:
    """Insert a row for a completed export. Returns the new row id.

    All parameters are required — caller must compute filled/na/not_found
    from the fill_monthly_report summary.
    """
    cur = conn.execute(
        """
        INSERT INTO export_history
            (out_path, template, year_month, filled, na, not_found)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (out_path, template, year_month, filled, na, not_found),
    )
    conn.commit()
    return cur.lastrowid


def list_recent_exports(
    conn: sqlite3.Connection, limit: int = 5,
) -> list[dict]:
    """Return the most-recent exports, newest first.

    Each dict has keys: id, out_path, template, year_month, filled,
    na, not_found, created_at.
    """
    rows = conn.execute(
        """
        SELECT id, out_path, template, year_month, filled, na, not_found, created_at
        FROM export_history
        ORDER BY created_at DESC, id DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return [dict(r) for r in rows]
```

- [ ] **Step 1.5: Run test to verify PASS**

```bash
../../../.venv/Scripts/python.exe -m pytest tests/test_export_history.py::test_record_export_inserts_row -v
```

Expected: PASS.

- [ ] **Step 1.6: Add list_recent_exports tests**

Append to `tests/test_export_history.py`:

```python
def test_list_recent_exports_empty(empty_db):
    with get_connection(empty_db) as conn:
        rows = list_recent_exports(conn)
    assert rows == []


def test_list_recent_exports_orders_newest_first(empty_db):
    with get_connection(empty_db) as conn:
        # Insert 3 rows; SQLite created_at uses second-resolution so
        # we depend on id DESC tie-break for same-second inserts.
        id1 = record_export(conn, "/a.xlsx", "/t.xlsx", "2026-01", 1, 0, 0)
        id2 = record_export(conn, "/b.xlsx", "/t.xlsx", "2026-02", 2, 0, 0)
        id3 = record_export(conn, "/c.xlsx", "/t.xlsx", "2026-03", 3, 0, 0)
        rows = list_recent_exports(conn)
    assert len(rows) == 3
    assert rows[0]["id"] == id3
    assert rows[1]["id"] == id2
    assert rows[2]["id"] == id1


def test_list_recent_exports_respects_limit(empty_db):
    with get_connection(empty_db) as conn:
        for i in range(10):
            record_export(conn, f"/f{i}.xlsx", "/t.xlsx", "2026-04", i, 0, 0)
        rows = list_recent_exports(conn, limit=3)
    assert len(rows) == 3
```

- [ ] **Step 1.7: Run all export_history tests**

```bash
../../../.venv/Scripts/python.exe -m pytest tests/test_export_history.py -v
```

Expected: 4 passed.

- [ ] **Step 1.8: Write failing test for `list_recent_imports`**

Create `tests/test_db_list_recent_imports.py`:

```python
"""Tests for list_recent_imports — distinct fingerprint files imported."""
import pytest
from datetime import datetime, timedelta
from src.db.connection import get_connection
from src.db.schema import init_db
from src.db.employees import upsert_employee
from src.db.attendance import upsert_attendance, list_recent_imports


@pytest.fixture
def db_with_imports(tmp_path):
    db_path = tmp_path / "test.db"
    init_db(db_path)
    with get_connection(db_path) as conn:
        emp_id = upsert_employee(conn, no_staff="001", nama="Andika", dept="MKT")
        # Two files imported, with employee data in each
        upsert_attendance(
            conn, employee_id=emp_id, tanggal="2026-04-01", hari="Rabu",
            tipe="Hari Kerja", jadwal="08-16",
            masuk="08:00", keluar="16:00",
            kerja_jam=8.0, lembur_jam=0.0, terlambat_menit=0, has_issue=0,
            imported_from="Fingerprint Mgg 1.xls",
        )
        emp_id2 = upsert_employee(conn, no_staff="002", nama="Bagus", dept="OPS")
        upsert_attendance(
            conn, employee_id=emp_id2, tanggal="2026-04-08", hari="Rabu",
            tipe="Hari Kerja", jadwal="08-16",
            masuk="08:00", keluar="16:00",
            kerja_jam=8.0, lembur_jam=0.0, terlambat_menit=0, has_issue=0,
            imported_from="Fingerprint Mgg 2.xls",
        )
    return db_path


def test_list_recent_imports_returns_distinct_files(db_with_imports):
    with get_connection(db_with_imports) as conn:
        rows = list_recent_imports(conn)
    files = [r["imported_from"] for r in rows]
    assert "Fingerprint Mgg 1.xls" in files
    assert "Fingerprint Mgg 2.xls" in files


def test_list_recent_imports_includes_emp_count(db_with_imports):
    with get_connection(db_with_imports) as conn:
        rows = list_recent_imports(conn)
    for r in rows:
        assert r["emp_count"] >= 1
        assert r["imported_at"] is not None


def test_list_recent_imports_respects_limit(db_with_imports):
    with get_connection(db_with_imports) as conn:
        rows = list_recent_imports(conn, limit=1)
    assert len(rows) == 1
```

- [ ] **Step 1.9: Run test to verify FAIL**

```bash
../../../.venv/Scripts/python.exe -m pytest tests/test_db_list_recent_imports.py -v
```

Expected: ImportError on `list_recent_imports` (doesn't exist in attendance.py yet).

- [ ] **Step 1.10: Implement `list_recent_imports`**

In `src/db/attendance.py`, add at the bottom of the file (after existing functions):

```python
def list_recent_imports(
    conn: sqlite3.Connection, limit: int = 5,
) -> list[dict]:
    """Return recent fingerprint imports — distinct imported_from with metadata.

    Each dict has keys: imported_from, imported_at, emp_count.
    Sorted by imported_at DESC (latest first). Limit caller-provided.

    Used by Import screen's 'Riwayat Import Terakhir' history list.
    """
    rows = conn.execute(
        """
        SELECT
            imported_from,
            MAX(imported_at) AS imported_at,
            COUNT(DISTINCT employee_id) AS emp_count
        FROM attendance_records
        WHERE imported_from IS NOT NULL
        GROUP BY imported_from
        ORDER BY MAX(imported_at) DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return [dict(r) for r in rows]
```

Make sure `import sqlite3` exists at top of file (it should already — check).

- [ ] **Step 1.11: Run all Phase 1 tests**

```bash
../../../.venv/Scripts/python.exe -m pytest tests/test_export_history.py tests/test_db_list_recent_imports.py -v
```

Expected: 4 + 3 = 7 passed.

- [ ] **Step 1.12: Full pytest regression**

```bash
../../../.venv/Scripts/python.exe -m pytest -q
```

Expected: 98 + 7 = **105 passed**.

- [ ] **Step 1.13: Commit Phase 1**

```bash
git add src/db/schema.py src/db/attendance.py src/db/export_history.py tests/test_export_history.py tests/test_db_list_recent_imports.py
git commit -m "$(cat <<'EOF'
feat(db): export_history table + import history query

Phase 1/7 dari Import+Export UX refresh:
- New table export_history (id, out_path, template, year_month,
  filled, na, not_found, created_at) untuk track laporan bulanan
  yang sudah di-generate. DDL idempotent di schema.py + index
  on created_at DESC untuk fast list.
- New module src/db/export_history.py dengan record_export()
  + list_recent_exports(conn, limit=5). 4 tests covering insert,
  empty list, ordering, limit.
- New function list_recent_imports(conn, limit=5) di attendance.py
  — group by imported_from, returns distinct files with emp count.
  3 tests covering distinct files, metadata, limit.

Lihat spec: docs/superpowers/specs/2026-05-14-import-export-ux-design.md

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Phase 2 — Import Core Refresh + R5 Folder Memory

**Files:**
- Modify: `src/ui/screens/import_screen.py` (extensive refactor)

**Goal of this task:** Replace post-pick layout (drop zone + bottom buttons) with file chip + active month banner + history list. Add R5 folder memory. Drop zone collapses after pick. Range tanggal Indonesian format. New helpers for date format + relative time.

- [ ] **Step 2.1: Read current import_screen.py for reference**

Use Read tool to read the entire `src/ui/screens/import_screen.py`. Note:
- Existing structure: header → drop zone → preview_frame → action_row
- Existing methods: `_build`, `_render_preview_placeholder`, `_render_preview_cards`, `_on_pick_file`, `_on_cancel`, `_on_confirm`
- Imports include theme tokens + KPICard

You'll be doing a significant refactor — preserve the parse + commit logic (those stay) but restructure the layout.

- [ ] **Step 2.2: Update imports and module-level constants**

In `src/ui/screens/import_screen.py`, update the import block at top to include new tokens + helpers needed:

```python
from collections import Counter
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox
import customtkinter as ctk

from src.config import DB_PATH
from src.db.connection import get_connection
from src.db.employees import upsert_employee, get_employee_by_no_staff
from src.db.attendance import upsert_attendance, list_recent_imports
from src.db.settings import set_setting, get_setting
from src.parsers.fingerprint import parse_fingerprint_file
from src.core.issue_detector import is_issue
from src.core.week_utils import full_month_range
from src.ui.components.kpi_card import KPICard
from src.ui.components.toast import show_success_toast
from src.ui.theme import (
    FONT_FAMILY,
    COLOR_BG, COLOR_SURFACE, COLOR_SURFACE_HIGH,
    COLOR_BORDER, COLOR_BORDER_STRONG,
    COLOR_ACCENT, COLOR_ACCENT_HOVER,
    COLOR_INFO, COLOR_WARN,
    COLOR_TEXT, COLOR_TEXT_DIM, COLOR_TEXT_MUTED, COLOR_TEXT_DISABLED,
    FONT_DISPLAY, FONT_SUBHEAD,
    FONT_BODY, FONT_BODY_BOLD, FONT_SMALL, FONT_LABEL,
    FONT_MONO_DATA, FONT_MONO_SMALL,
    SPACE_XS, SPACE_SM, SPACE_MD, SPACE_LG,
    RADIUS_SM, RADIUS_MD, RADIUS_LG,
)


_MONTH_ID = {
    1: "Januari", 2: "Februari", 3: "Maret", 4: "April",
    5: "Mei", 6: "Juni", 7: "Juli", 8: "Agustus",
    9: "September", 10: "Oktober", 11: "November", 12: "Desember",
}
_MONTH_ID_SHORT = {
    1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr",
    5: "Mei", 6: "Jun", 7: "Jul", 8: "Ags",
    9: "Sep", 10: "Okt", 11: "Nov", 12: "Des",
}


def _format_month_id(month_str: str) -> str:
    """'2026-04' → 'April 2026'. Falls back to the raw string if unparseable."""
    try:
        year_s, m_s = month_str.split("-")
        return f"{_MONTH_ID[int(m_s)]} {year_s}"
    except (ValueError, KeyError):
        return month_str


def _format_short_range(start_iso: str, end_iso: str) -> str:
    """Compact Indonesian date range:
        same month/year → '22 → 28 Apr 2026'
        different month, same year → '30 Apr → 5 Mei 2026'
        different year → '30 Des 2025 → 5 Jan 2026'
    """
    try:
        s = datetime.strptime(start_iso, "%Y-%m-%d")
        e = datetime.strptime(end_iso, "%Y-%m-%d")
    except ValueError:
        return f"{start_iso} → {end_iso}"
    if s.year != e.year:
        return f"{s.day} {_MONTH_ID_SHORT[s.month]} {s.year} → {e.day} {_MONTH_ID_SHORT[e.month]} {e.year}"
    if s.month != e.month:
        return f"{s.day} {_MONTH_ID_SHORT[s.month]} → {e.day} {_MONTH_ID_SHORT[e.month]} {e.year}"
    return f"{s.day} → {e.day} {_MONTH_ID_SHORT[e.month]} {e.year}"


def _format_relative_time(iso_dt: str) -> str:
    """ISO datetime to 'Today HH:MM' / 'Yesterday HH:MM' / 'MMM D HH:MM'."""
    try:
        dt = datetime.strptime(iso_dt, "%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        return iso_dt or "—"
    now = datetime.now()
    today = now.date()
    if dt.date() == today:
        return f"Today {dt.strftime('%H:%M')}"
    delta = today - dt.date()
    if delta.days == 1:
        return f"Yesterday {dt.strftime('%H:%M')}"
    return f"{_MONTH_ID_SHORT[dt.month]} {dt.day} {dt.strftime('%H:%M')}"
```

Note: keep the existing `_format_month_id` function — just add new helpers. Update imports as shown.

- [ ] **Step 2.3: Refactor `_build` method to new layout**

Replace the entire `_build` method with this new layout. Drop the old drop zone + bottom action_row code:

```python
def _build(self):
    # Header
    ctk.CTkLabel(
        self, text="Import Fingerprint",
        font=FONT_DISPLAY, text_color=COLOR_TEXT,
    ).pack(anchor="w", pady=(0, SPACE_LG))

    # ── Active month banner ──
    # State machine: 3 modes
    #   "cyan"  — no file picked yet, shows current_month info
    #   "rose"  — file picked, mode month differs from current_month
    #   "match" — file picked, mode month equals current_month (still cyan)
    self.banner = ctk.CTkFrame(
        self, fg_color="#08222B",  # cyan 8% on dark
        border_width=1, border_color="#12454F",  # cyan 25% on dark
        corner_radius=RADIUS_MD,
    )
    self.banner.pack(fill="x", pady=(0, SPACE_MD))
    self.banner_icon = ctk.CTkLabel(
        self.banner, text="📆",
        font=(FONT_FAMILY, 16),
        text_color=COLOR_INFO,
    )
    self.banner_icon.pack(side="left", padx=(SPACE_MD, SPACE_SM), pady=SPACE_SM)
    self.banner_text = ctk.CTkLabel(
        self.banner, text="",
        font=FONT_BODY,
        text_color=COLOR_TEXT,
        anchor="w", justify="left",
    )
    self.banner_text.pack(side="left", fill="x", expand=True, pady=SPACE_SM)
    self._update_banner()

    # ── Drop zone (shown only when no file pending) ──
    self.dropzone = self._build_dropzone()
    self.dropzone.pack(fill="x", pady=(0, SPACE_LG))

    # ── File chip (shown only when file pending, hidden initially) ──
    self.chip_frame = ctk.CTkFrame(
        self, fg_color=COLOR_SURFACE,
        border_width=1, border_color=COLOR_BORDER,
        corner_radius=RADIUS_MD,
    )
    # Don't pack yet — populated by _show_chip()

    # ── Preview cards (populated after file pick) ──
    self.preview_frame = ctk.CTkFrame(self, fg_color="transparent")
    self.preview_frame.pack(fill="x", pady=(0, SPACE_LG))
    self._render_preview_placeholder()

    # ── History list (always shown at bottom) ──
    self.history_frame = ctk.CTkFrame(
        self, fg_color=COLOR_SURFACE,
        border_width=1, border_color=COLOR_BORDER,
        corner_radius=RADIUS_MD,
    )
    self.history_frame.pack(fill="x", side="bottom")
    self._render_history()
```

- [ ] **Step 2.4: Add `_build_dropzone` helper**

Add this method right after `_build`. It encapsulates the drop zone construction (matches existing style but factored out):

```python
def _build_dropzone(self):
    """Build the large drop zone shown when no file is pending."""
    zone = ctk.CTkFrame(
        self,
        fg_color="#0F0F0F",  # one-off, slightly lighter than COLOR_BG
        border_width=2,
        border_color=COLOR_BORDER_STRONG,
        corner_radius=RADIUS_LG,
        height=200,
    )
    zone.pack_propagate(False)

    inner = ctk.CTkFrame(zone, fg_color="transparent")
    inner.place(relx=0.5, rely=0.5, anchor="center")

    ctk.CTkLabel(
        inner, text="📥",
        font=(FONT_FAMILY, 28),
        text_color=COLOR_TEXT,
    ).pack()
    ctk.CTkLabel(
        inner, text="Drag file fingerprint .xls ke sini",
        font=FONT_SUBHEAD, text_color=COLOR_TEXT,
    ).pack(pady=(SPACE_SM, SPACE_XS))
    ctk.CTkLabel(
        inner, text="atau klik browse",
        font=FONT_SMALL, text_color=COLOR_TEXT_MUTED,
    ).pack(pady=(0, SPACE_SM))

    ctk.CTkButton(
        inner, text="📁 Browse File",
        command=self._on_pick_file,
        fg_color="transparent",
        border_width=1, border_color=COLOR_INFO,
        text_color=COLOR_INFO,
        hover_color=COLOR_SURFACE_HIGH,
        font=FONT_BODY_BOLD,
    ).pack()

    # Hover state — nested counter prevents flicker when crossing children
    self._dropzone_pointer_inside = 0

    def _on_enter(_e):
        self._dropzone_pointer_inside += 1
        if self._dropzone_pointer_inside > 0:
            zone.configure(border_color=COLOR_ACCENT)

    def _on_leave(_e):
        self._dropzone_pointer_inside -= 1
        if self._dropzone_pointer_inside <= 0:
            self._dropzone_pointer_inside = 0
            zone.configure(border_color=COLOR_BORDER_STRONG)

    def _bind_hover_recursive(widget):
        widget.bind("<Enter>", _on_enter, add="+")
        widget.bind("<Leave>", _on_leave, add="+")
        for child in widget.winfo_children():
            _bind_hover_recursive(child)

    _bind_hover_recursive(zone)
    return zone
```

- [ ] **Step 2.5: Add `_show_chip` and `_hide_chip` helpers**

Add after `_build_dropzone`:

```python
def _show_chip(self, filename: str, size_kb: int, parse_ms: int):
    """Replace drop zone with file chip (file selected state)."""
    self.dropzone.pack_forget()

    # Clear previous chip content if any
    for w in self.chip_frame.winfo_children():
        w.destroy()

    icon = ctk.CTkLabel(
        self.chip_frame, text="📄",
        font=(FONT_FAMILY, 24),
        text_color=COLOR_TEXT,
    )
    icon.pack(side="left", padx=(SPACE_MD, SPACE_SM), pady=SPACE_MD)

    info = ctk.CTkFrame(self.chip_frame, fg_color="transparent")
    info.pack(side="left", fill="x", expand=True, pady=SPACE_MD)
    ctk.CTkLabel(
        info, text="FILE TERPILIH",
        font=FONT_LABEL, text_color=COLOR_TEXT_MUTED,
        anchor="w",
    ).pack(fill="x")
    ctk.CTkLabel(
        info, text=filename,
        font=FONT_MONO_DATA, text_color=COLOR_TEXT,
        anchor="w",
    ).pack(fill="x")
    ctk.CTkLabel(
        info, text=f"{size_kb} KB · diparsing dalam {parse_ms} ms",
        font=FONT_MONO_SMALL, text_color=COLOR_TEXT_MUTED,
        anchor="w",
    ).pack(fill="x")

    # 3-button action group on the right
    actions = ctk.CTkFrame(self.chip_frame, fg_color="transparent")
    actions.pack(side="right", padx=SPACE_MD, pady=SPACE_MD)
    ctk.CTkButton(
        actions, text="↻ Ganti",
        command=self._on_pick_file,
        fg_color="transparent",
        border_width=1, border_color=COLOR_BORDER_STRONG,
        text_color=COLOR_TEXT_DIM,
        hover_color=COLOR_SURFACE_HIGH,
        font=FONT_BODY_BOLD,
        width=80,
    ).pack(side="left", padx=(0, SPACE_XS))
    ctk.CTkButton(
        actions, text="✕ Batal",
        command=self._on_cancel,
        fg_color="transparent",
        border_width=1, border_color=COLOR_BORDER_STRONG,
        text_color=COLOR_TEXT_DIM,
        hover_color=COLOR_SURFACE_HIGH,
        font=FONT_BODY_BOLD,
        width=80,
    ).pack(side="left", padx=(0, SPACE_XS))
    ctk.CTkButton(
        actions, text="✓ Konfirmasi",
        command=self._on_confirm,
        fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER,
        text_color=COLOR_BG,
        font=FONT_BODY_BOLD,
        width=120,
    ).pack(side="left")

    # Pack chip frame above preview_frame
    self.chip_frame.pack(fill="x", pady=(0, SPACE_MD), before=self.preview_frame)


def _hide_chip(self):
    """Return to no-file-pending state — drop zone visible, chip hidden."""
    self.chip_frame.pack_forget()
    self.dropzone.pack(fill="x", pady=(0, SPACE_LG), before=self.preview_frame)
```

- [ ] **Step 2.6: Add `_update_banner` and `_render_history` helpers**

Add after `_hide_chip`:

```python
def _update_banner(self):
    """Refresh banner based on current state (active month + pending file)."""
    with get_connection(DB_PATH) as conn:
        current = get_setting(conn, "current_month") or ""
    current_display = _format_month_id(current) if current else "(belum ada bulan aktif)"

    # Detect pending month from rows if any
    if self._pending_rows:
        months = [r.tanggal[:7] for r in self._pending_rows if r.tanggal]
        if months:
            pending_month = Counter(months).most_common(1)[0][0]
            if current and pending_month != current:
                # ROSE warning state
                self.banner.configure(
                    fg_color="#2A0A14",
                    border_color="#5C1E2A",
                )
                self.banner_icon.configure(text="⚠", text_color=COLOR_WARN)
                self.banner_text.configure(
                    text=(
                        f"Bulan aktif akan diubah: "
                        f"{current_display} → {_format_month_id(pending_month)} setelah konfirmasi impor."
                    ),
                )
                return
    # Default: CYAN info state
    self.banner.configure(
        fg_color="#08222B",
        border_color="#12454F",
    )
    self.banner_icon.configure(text="📆", text_color=COLOR_INFO)
    self.banner_text.configure(
        text=(
            f"Bulan aktif saat ini: {current_display}. "
            f"File baru akan auto-detect bulan dan update jika berbeda."
        ),
    )


def _render_history(self):
    """Render the 'Riwayat Import Terakhir' list at the bottom."""
    for w in self.history_frame.winfo_children():
        w.destroy()

    ctk.CTkLabel(
        self.history_frame, text="RIWAYAT IMPORT TERAKHIR",
        font=FONT_LABEL, text_color=COLOR_TEXT_MUTED,
        anchor="w",
    ).pack(fill="x", padx=SPACE_MD, pady=(SPACE_SM, SPACE_XS))

    with get_connection(DB_PATH) as conn:
        items = list_recent_imports(conn, limit=5)

    if not items:
        ctk.CTkLabel(
            self.history_frame, text="(belum ada riwayat impor)",
            font=FONT_BODY, text_color=COLOR_TEXT_MUTED,
            anchor="w",
        ).pack(fill="x", padx=SPACE_MD, pady=(0, SPACE_SM))
        return

    for it in items:
        row = ctk.CTkFrame(self.history_frame, fg_color="transparent")
        row.pack(fill="x", padx=SPACE_MD, pady=2)
        ctk.CTkLabel(
            row, text=_format_relative_time(it["imported_at"]),
            font=FONT_MONO_SMALL, text_color=COLOR_TEXT_MUTED,
            anchor="w", width=120,
        ).pack(side="left")
        ctk.CTkLabel(
            row, text=it["imported_from"],
            font=FONT_MONO_DATA, text_color=COLOR_TEXT,
            anchor="w",
        ).pack(side="left", fill="x", expand=True, padx=(SPACE_SM, SPACE_SM))
        ctk.CTkLabel(
            row, text=f"✓ {it['emp_count']} emp",
            font=FONT_MONO_SMALL, text_color=COLOR_TEXT_DIM,
            fg_color="#0F2218",  # subtle emerald tint
            corner_radius=RADIUS_SM,
            anchor="e", width=70,
        ).pack(side="right")
    # Add tail padding
    ctk.CTkFrame(self.history_frame, fg_color="transparent", height=SPACE_SM).pack()
```

- [ ] **Step 2.7: Update `_on_pick_file` with timing + R5 folder memory**

Replace the existing `_on_pick_file` method:

```python
def _on_pick_file(self):
    """Open file dialog, parse, render preview + chip."""
    # R5 — remember last folder
    with get_connection(DB_PATH) as conn:
        initialdir = get_setting(conn, "last_import_folder") or str(Path.home() / "Documents")

    path = filedialog.askopenfilename(
        title="Pilih file fingerprint",
        initialdir=initialdir,
        filetypes=[("Excel", "*.xls *.xlsx"), ("All files", "*.*")],
    )
    if not path:
        return
    self._pending_path = Path(path)

    # R5 — persist folder for next pick
    with get_connection(DB_PATH) as conn:
        set_setting(conn, "last_import_folder", str(self._pending_path.parent))

    import time
    t0 = time.perf_counter()
    try:
        self._pending_rows = parse_fingerprint_file(self._pending_path)
    except Exception as e:
        messagebox.showerror("Error parsing", str(e))
        self._pending_path = None
        self._pending_rows = []
        return
    parse_ms = int((time.perf_counter() - t0) * 1000)

    if not self._pending_rows:
        messagebox.showwarning("File kosong",
            "File tidak mengandung baris yang bisa diimpor.")
        self._pending_path = None
        self._pending_rows = []
        return

    # Compute metrics
    issue_count = sum(1 for r in self._pending_rows if is_issue(r))
    unique_emps = {r.no_staff for r in self._pending_rows}
    dates = sorted({r.tanggal for r in self._pending_rows})
    date_range = _format_short_range(dates[0], dates[-1]) if dates else "(empty)"

    new_emp_count = 0
    with get_connection(DB_PATH) as conn:
        for no_staff in unique_emps:
            if get_employee_by_no_staff(conn, no_staff) is None:
                new_emp_count += 1

    # Render UI
    size_kb = self._pending_path.stat().st_size // 1024
    self._show_chip(self._pending_path.name, size_kb, parse_ms)
    self._render_preview_cards(
        pegawai_count=len(unique_emps),
        date_range=date_range,
        issue_count=issue_count,
        new_emp_count=new_emp_count,
    )
    self._update_banner()
```

- [ ] **Step 2.8: Update `_on_cancel` to hide chip + reset state**

Replace `_on_cancel`:

```python
def _on_cancel(self):
    self._pending_path = None
    self._pending_rows = []
    self._hide_chip()
    self._render_preview_placeholder()
    self._update_banner()
```

- [ ] **Step 2.9: Update `_on_confirm` to refresh history + hide chip**

Replace `_on_confirm` (preserve commit logic, change post-commit reset):

```python
def _on_confirm(self):
    if not self._pending_rows:
        return

    # Auto-detect mode month
    months = [r.tanggal[:7] for r in self._pending_rows if r.tanggal]
    mode_month = Counter(months).most_common(1)[0][0] if months else None

    with get_connection(DB_PATH) as conn:
        for r in self._pending_rows:
            emp_id = upsert_employee(
                conn, no_staff=r.no_staff, nama=r.nama, dept=r.dept
            )
            upsert_attendance(
                conn, employee_id=emp_id, tanggal=r.tanggal,
                hari=r.hari, tipe=r.tipe, jadwal=r.jadwal,
                masuk=r.masuk, keluar=r.keluar,
                kerja_jam=r.kerja_jam, lembur_jam=r.lembur_jam,
                terlambat_menit=r.terlambat_menit,
                has_issue=1 if is_issue(r) else 0,
                imported_from=r.source_file,
            )
        if mode_month:
            set_setting(conn, "current_month", mode_month)

    row_count = len(self._pending_rows)
    month_display = _format_month_id(mode_month) if mode_month else "-"

    # Reset state, hide chip, restore dropzone, refresh history + banner
    self._pending_rows = []
    self._pending_path = None
    self._hide_chip()
    self._render_preview_placeholder()
    self._update_banner()
    self._render_history()

    show_success_toast(
        self.winfo_toplevel(),
        title="Impor Berhasil",
        message=(
            f"{row_count} baris fingerprint berhasil diimpor.\n"
            f"Bulan aktif diset ke {month_display}."
        ),
    )
```

- [ ] **Step 2.10: Run pytest regression**

```bash
../../../.venv/Scripts/python.exe -m pytest -q
```

Expected: 105 passed (no new tests, just refactor).

- [ ] **Step 2.11: Verify import**

```bash
../../../.venv/Scripts/python.exe -c "from src.ui.screens.import_screen import ImportScreen; print('OK')"
```

Expected: OK.

- [ ] **Step 2.12: Commit Phase 2**

```bash
git add src/ui/screens/import_screen.py
git commit -m "$(cat <<'EOF'
feat(ui): Import core refresh — file chip + banner + history + R5

Phase 2/7 dari Import+Export UX refresh:
- File chip menggantikan post-pick drop zone display:
  3-button layout [↻ Ganti] [✕ Batal] [✓ Konfirmasi] inline dengan
  filename mono + size + parse time. Drop zone collapses (pack_forget)
  setelah file dipilih.
- Active month context banner: cyan saat default, rose warning saat
  pending mode month ≠ current_month ("bulan aktif akan diubah X → Y").
- Bottom action_row removed sepenuhnya — semua actions di chip.
- Indonesian short range format helper: "22 → 28 Apr 2026"
  (single month) / "30 Apr → 5 Mei 2026" (cross-month) / full year
  qualifier kalau cross-year. Replaces ISO "2026-04-01 → 2026-04-30".
- Riwayat Import history list di bottom — 5 entries via
  list_recent_imports query, relative time format ("Today HH:MM",
  "Yesterday HH:MM", "MMM D HH:MM"), refreshed setelah confirm.
- R5: last_import_folder setting persisted on browse, dipakai
  sebagai initialdir untuk next file picker.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Phase 3 — Import R3 Conflict Resolution + R6 Bulk Import

**Files:**
- Modify: `src/db/attendance.py` (add `count_overlap`)
- Create: `tests/test_attendance_count_overlap.py`
- Modify: `src/ui/screens/import_screen.py` (5th KPI card + multi-file)

**Goal of this task:** Add 5th "Akan Menimpa" KPI card showing how many rows would overwrite existing data. Allow multi-file select for bulk import.

- [ ] **Step 3.1: Write failing test for `count_overlap`**

Create `tests/test_attendance_count_overlap.py`:

```python
"""Tests for count_overlap — predict overwrite count before commit."""
import pytest
from src.db.connection import get_connection
from src.db.schema import init_db
from src.db.employees import upsert_employee
from src.db.attendance import upsert_attendance, count_overlap
from src.parsers.fingerprint import FingerprintRow


@pytest.fixture
def db_with_existing(tmp_path):
    db_path = tmp_path / "test.db"
    init_db(db_path)
    with get_connection(db_path) as conn:
        emp_id = upsert_employee(conn, no_staff="001", nama="A", dept="X")
        upsert_attendance(
            conn, employee_id=emp_id, tanggal="2026-04-01", hari="Rabu",
            tipe="Hari Kerja", jadwal="08-16",
            masuk="08:00", keluar="16:00",
            kerja_jam=8.0, lembur_jam=0.0, terlambat_menit=0, has_issue=0,
        )
    return db_path


def _make_row(no_staff, nama, dept, tanggal):
    """Build a FingerprintRow with minimum required fields."""
    return FingerprintRow(
        no_staff=no_staff, nama=nama, dept=dept,
        tanggal=tanggal, hari="Rabu",
        tipe="Hari Kerja", jadwal="08-16",
        masuk="08:00", keluar="16:00",
        kerja_jam=8.0, lembur_jam=0.0, terlambat_menit=0,
        source_file="test.xls",
    )


def test_count_overlap_all_new(db_with_existing):
    pending = [
        _make_row("002", "B", "X", "2026-04-08"),
        _make_row("003", "C", "X", "2026-04-09"),
    ]
    with get_connection(db_with_existing) as conn:
        result = count_overlap(conn, pending)
    assert result == {"new": 2, "overwrite": 0}


def test_count_overlap_all_overwrite(db_with_existing):
    pending = [
        _make_row("001", "A", "X", "2026-04-01"),  # exists
    ]
    with get_connection(db_with_existing) as conn:
        result = count_overlap(conn, pending)
    assert result == {"new": 0, "overwrite": 1}


def test_count_overlap_mixed(db_with_existing):
    pending = [
        _make_row("001", "A", "X", "2026-04-01"),  # overwrite (exists)
        _make_row("001", "A", "X", "2026-04-02"),  # new (emp exists, date doesn't)
        _make_row("002", "B", "X", "2026-04-01"),  # new (emp doesn't exist)
    ]
    with get_connection(db_with_existing) as conn:
        result = count_overlap(conn, pending)
    assert result == {"new": 2, "overwrite": 1}
```

- [ ] **Step 3.2: Verify FingerprintRow fields**

Before running tests, check that `FingerprintRow` has the fields used above. Read the FingerprintRow definition:

```bash
../../../.venv/Scripts/python.exe -c "from src.parsers.fingerprint import FingerprintRow; import dataclasses; print([f.name for f in dataclasses.fields(FingerprintRow)])"
```

Expected output should include: `no_staff, nama, dept, tanggal, hari, tipe, jadwal, masuk, keluar, kerja_jam, lembur_jam, terlambat_menit, source_file` (or similar).

If field names differ in actual code, adjust `_make_row` in step 3.1 to match. Re-read `src/parsers/fingerprint.py` if unsure.

- [ ] **Step 3.3: Run test to verify FAIL**

```bash
../../../.venv/Scripts/python.exe -m pytest tests/test_attendance_count_overlap.py -v
```

Expected: ImportError on `count_overlap`.

- [ ] **Step 3.4: Implement `count_overlap`**

In `src/db/attendance.py`, add (after `list_recent_imports`):

```python
def count_overlap(conn: sqlite3.Connection, pending_rows: list) -> dict:
    """Count how many pending rows would overwrite existing DB rows.

    Returns dict with keys 'new' (would insert) and 'overwrite' (would
    replace existing row at (employee_id, tanggal) via upsert).

    The existing upsert preserves reason_category/reason_detail/resolved_at,
    so 'overwrite' is data-only — user input is not destroyed. UI should
    surface this count so the user knows scope but not raise alarm.

    Uses N+1 lookup pattern (employees + per-row attendance check).
    Typical input < 200 rows, acceptable at SQLite speeds. If profiling
    shows this slow, batch via 'WHERE (employee_id, tanggal) IN (...)'.
    """
    from src.db.employees import get_employee_by_no_staff
    new_count = 0
    overwrite_count = 0
    for r in pending_rows:
        emp = get_employee_by_no_staff(conn, r.no_staff)
        if emp is None:
            new_count += 1
            continue
        existing = conn.execute(
            "SELECT 1 FROM attendance_records WHERE employee_id = ? AND tanggal = ?",
            (emp["id"], r.tanggal),
        ).fetchone()
        if existing:
            overwrite_count += 1
        else:
            new_count += 1
    return {"new": new_count, "overwrite": overwrite_count}
```

Note: `emp["id"]` assumes `get_employee_by_no_staff` returns a Row (dict-like). If it returns a different object (e.g., dataclass), adjust accordingly. Re-check `src/db/employees.py` if needed.

- [ ] **Step 3.5: Run tests to verify PASS**

```bash
../../../.venv/Scripts/python.exe -m pytest tests/test_attendance_count_overlap.py -v
```

Expected: 3 passed.

- [ ] **Step 3.6: Update `_render_preview_cards` to 5 columns**

In `src/ui/screens/import_screen.py`, replace `_render_preview_cards` method:

```python
def _render_preview_cards(self, pegawai_count: int, date_range: str,
                          issue_count: int, new_emp_count: int,
                          overwrite_count: int = 0):
    """Render the 5 preview metric cards in a grid."""
    for child in self.preview_frame.winfo_children():
        child.destroy()

    for i in range(5):
        self.preview_frame.grid_columnconfigure(i, weight=1)

    # 5 KPI cards. Date range gets a smaller body-bold font.
    overwrite_color = COLOR_WARN if overwrite_count > 0 else COLOR_TEXT_MUTED
    cards = [
        ("Pegawai", str(pegawai_count), COLOR_TEXT, True, None),
        ("Range Tanggal", date_range, COLOR_INFO, False, FONT_BODY_BOLD),
        ("Issue Baru", str(issue_count), COLOR_WARN, True, None),
        ("Pegawai Baru", str(new_emp_count), COLOR_INFO, True, None),
        ("Akan Menimpa", str(overwrite_count), overwrite_color, True, None),
    ]
    for col, (label, value, value_color, mono, value_font) in enumerate(cards):
        KPICard(
            self.preview_frame, label, value,
            value_color=value_color, mono=mono, value_font=value_font,
        ).grid(row=0, column=col, sticky="nsew", padx=SPACE_XS, pady=0)

    # Footnote when overwrite > 0
    if overwrite_count > 0:
        footnote = ctk.CTkLabel(
            self.preview_frame,
            text="* Alasan ijin yang sudah diinput tidak akan terhapus.",
            font=FONT_MONO_SMALL, text_color=COLOR_TEXT_DISABLED,
            anchor="w",
        )
        footnote.grid(row=1, column=0, columnspan=5, sticky="w", pady=(SPACE_XS, 0))
```

- [ ] **Step 3.7: Wire `count_overlap` into `_on_pick_file`**

In `_on_pick_file`, after computing `new_emp_count`, add overlap computation. Update the imports section (top of file):

```python
from src.db.attendance import upsert_attendance, list_recent_imports, count_overlap
```

Then in `_on_pick_file`, find the section that calls `_render_preview_cards` and update:

```python
# Existing: new_emp_count loop already computed
with get_connection(DB_PATH) as conn:
    for no_staff in unique_emps:
        if get_employee_by_no_staff(conn, no_staff) is None:
            new_emp_count += 1
    overlap = count_overlap(conn, self._pending_rows)

# Render UI
size_kb = self._pending_path.stat().st_size // 1024
self._show_chip(self._pending_path.name, size_kb, parse_ms)
self._render_preview_cards(
    pegawai_count=len(unique_emps),
    date_range=date_range,
    issue_count=issue_count,
    new_emp_count=new_emp_count,
    overwrite_count=overlap["overwrite"],
)
self._update_banner()
```

- [ ] **Step 3.8: Add R6 multi-file support**

In `_on_pick_file`, replace `filedialog.askopenfilename` (singular) with `filedialog.askopenfilenames` (plural — returns tuple). Update parsing loop:

```python
def _on_pick_file(self):
    """Open file dialog (multi-select OK), parse all, render preview + chip."""
    with get_connection(DB_PATH) as conn:
        initialdir = get_setting(conn, "last_import_folder") or str(Path.home() / "Documents")

    paths_tuple = filedialog.askopenfilenames(
        title="Pilih file fingerprint (boleh multi-select)",
        initialdir=initialdir,
        filetypes=[("Excel", "*.xls *.xlsx"), ("All files", "*.*")],
    )
    if not paths_tuple:
        return
    paths = [Path(p) for p in paths_tuple]

    with get_connection(DB_PATH) as conn:
        set_setting(conn, "last_import_folder", str(paths[0].parent))

    import time
    t0 = time.perf_counter()
    all_rows = []
    try:
        for p in paths:
            all_rows.extend(parse_fingerprint_file(p))
    except Exception as e:
        messagebox.showerror("Error parsing", str(e))
        self._pending_path = None
        self._pending_rows = []
        return
    parse_ms = int((time.perf_counter() - t0) * 1000)

    if not all_rows:
        messagebox.showwarning("File kosong",
            "Tidak ada baris yang bisa diimpor dari file yang dipilih.")
        self._pending_path = None
        self._pending_rows = []
        return

    self._pending_path = paths[0] if len(paths) == 1 else None  # for single-file UI display
    self._pending_paths = paths  # NEW: store all paths
    self._pending_rows = all_rows

    issue_count = sum(1 for r in self._pending_rows if is_issue(r))
    unique_emps = {r.no_staff for r in self._pending_rows}
    dates = sorted({r.tanggal for r in self._pending_rows})
    date_range = _format_short_range(dates[0], dates[-1]) if dates else "(empty)"

    new_emp_count = 0
    with get_connection(DB_PATH) as conn:
        for no_staff in unique_emps:
            if get_employee_by_no_staff(conn, no_staff) is None:
                new_emp_count += 1
        overlap = count_overlap(conn, self._pending_rows)

    # File display label
    if len(paths) == 1:
        filename = paths[0].name
        size_kb = paths[0].stat().st_size // 1024
    else:
        filename = f"{len(paths)} files selected"
        size_kb = sum(p.stat().st_size for p in paths) // 1024

    self._show_chip(filename, size_kb, parse_ms)
    self._render_preview_cards(
        pegawai_count=len(unique_emps),
        date_range=date_range,
        issue_count=issue_count,
        new_emp_count=new_emp_count,
        overwrite_count=overlap["overwrite"],
    )
    self._update_banner()
```

- [ ] **Step 3.9: Update `_show_chip` for multi-file label**

The chip's `FILE TERPILIH` label needs to flex to `FILES TERPILIH (N files)` for bulk:

In `_show_chip`, update the label line:

```python
ctk.CTkLabel(
    info,
    text="FILE TERPILIH" if (hasattr(self, "_pending_paths") and len(self._pending_paths) == 1) else f"FILES TERPILIH ({len(getattr(self, '_pending_paths', [None]))} files)",
    font=FONT_LABEL, text_color=COLOR_TEXT_MUTED,
    anchor="w",
).pack(fill="x")
```

Or simpler: pass a `is_multi` parameter to `_show_chip`. Use the simpler version:

```python
def _show_chip(self, filename: str, size_kb: int, parse_ms: int, is_multi: bool = False):
    ...
    label_text = f"FILES TERPILIH ({len(self._pending_paths)} files)" if is_multi else "FILE TERPILIH"
    ctk.CTkLabel(
        info, text=label_text,
        font=FONT_LABEL, text_color=COLOR_TEXT_MUTED,
        anchor="w",
    ).pack(fill="x")
    ...
```

Then in `_on_pick_file`, call:
```python
self._show_chip(filename, size_kb, parse_ms, is_multi=(len(paths) > 1))
```

- [ ] **Step 3.10: Update `__init__` to declare `_pending_paths`**

In `ImportScreen.__init__`, add:

```python
def __init__(self, parent):
    super().__init__(parent, fg_color="transparent")
    self._pending_path: Path | None = None
    self._pending_paths: list = []
    self._pending_rows: list = []
    self._build()
```

- [ ] **Step 3.11: Update `_on_cancel` to clear paths list**

```python
def _on_cancel(self):
    self._pending_path = None
    self._pending_paths = []
    self._pending_rows = []
    self._hide_chip()
    self._render_preview_placeholder()
    self._update_banner()
```

- [ ] **Step 3.12: Update `_on_confirm` similarly**

After successful commit, clear all paths:

```python
self._pending_rows = []
self._pending_path = None
self._pending_paths = []
self._hide_chip()
...
```

- [ ] **Step 3.13: Run full pytest**

```bash
../../../.venv/Scripts/python.exe -m pytest -q
```

Expected: 105 + 3 = **108 passed**.

- [ ] **Step 3.14: Commit Phase 3**

```bash
git add src/db/attendance.py tests/test_attendance_count_overlap.py src/ui/screens/import_screen.py
git commit -m "$(cat <<'EOF'
feat(ui): Import — R3 conflict resolution + R6 bulk import

Phase 3/7 dari Import+Export UX refresh:
- R3: count_overlap() di src/db/attendance.py menghitung berapa
  baris pending akan overwrite existing rows. 3 tests covering
  all-new / all-overwrite / mixed scenarios.
- 5th KPI card "Akan Menimpa" dengan rose color jika > 0 (else
  muted gray). Plus footnote muted "Alasan ijin yang sudah diinput
  tidak akan terhapus" — clarifies that upsert preserves user input.
- R6: askopenfilenames (plural) menggantikan askopenfilename.
  Multi-file selection iterates parses + accumulates rows.
  File chip label flex: "FILE TERPILIH" → "FILES TERPILIH (N files)".
  Single-file flow tidak terdampak.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Phase 4 — Export Core Refresh + R5 Folder Memory

**Files:**
- Modify: `src/core/report_filler.py` (add dry_run + out_dir params)
- Create: `tests/test_report_filler_dry_run.py`
- Modify: `src/ui/screens/export.py` (extensive refactor)

**Goal of this task:** Refactor report_filler to support dry-run mode (no write to disk). Then refactor Export screen: banner, dry-run preview, file chip with inline Export, result strip replacing messagebox, history, filename preview. Plus R5 folder memory.

- [ ] **Step 4.1: Read current `fill_monthly_report` signature**

Read `src/core/report_filler.py`. Note the current `fill_monthly_report(template_path, conn)` signature and what it returns (probably `(out_path, FillSummary)` or similar). Note the existing logic structure — we'll add a `dry_run` parameter that skips the `wb.save` call.

- [ ] **Step 4.2: Write failing test for dry_run param**

Create `tests/test_report_filler_dry_run.py`:

```python
"""Tests for fill_monthly_report dry_run + out_dir parameters."""
import pytest
from pathlib import Path
import shutil

from src.config import TEMPLATE_LAPORAN_BULANAN
from src.db.connection import get_connection
from src.db.schema import init_db
from src.core.report_filler import fill_monthly_report


@pytest.fixture
def setup_env(tmp_path):
    """Copy bundled template to tmp so we can mutate around it."""
    db_path = tmp_path / "test.db"
    init_db(db_path)
    template = tmp_path / "Laporan April.xlsx"
    shutil.copy(TEMPLATE_LAPORAN_BULANAN, template)
    return db_path, template, tmp_path


def test_dry_run_does_not_write_file(setup_env):
    db_path, template, tmp = setup_env
    # File listing before
    before = set(tmp.iterdir())
    with get_connection(db_path) as conn:
        out_path, summary = fill_monthly_report(
            template, conn, dry_run=True,
        )
    after = set(tmp.iterdir())
    # No new file created
    assert before == after
    # Summary still returned (mostly zeros — no data in DB)
    assert summary is not None
    # out_path is the predicted name, not an actual file
    assert not out_path.exists() or out_path == template  # template untouched


def test_out_dir_redirects_save_location(setup_env):
    db_path, template, tmp = setup_env
    out_dir = tmp / "subdir"
    out_dir.mkdir()
    with get_connection(db_path) as conn:
        out_path, summary = fill_monthly_report(
            template, conn, dry_run=False, out_dir=out_dir,
        )
    assert out_path.parent == out_dir
    assert out_path.exists()
```

- [ ] **Step 4.3: Run test to verify FAIL**

```bash
../../../.venv/Scripts/python.exe -m pytest tests/test_report_filler_dry_run.py -v
```

Expected: TypeError on unexpected keyword argument `dry_run`.

- [ ] **Step 4.4: Add dry_run + out_dir parameters to fill_monthly_report**

In `src/core/report_filler.py`, update `fill_monthly_report` signature + logic. Read current code first to integrate cleanly. The general pattern:

```python
def fill_monthly_report(
    template_path: Path,
    conn,
    *,
    dry_run: bool = False,
    out_dir: Path | None = None,
):
    """Fill 'Alasan Ijin' column in Laporan Bulanan template.

    Args:
        template_path: Path to source .xlsx template.
        conn: SQLite connection.
        dry_run: If True, perform matching + return summary but do
            NOT save the .xlsx to disk. Used by Export UI for preview.
        out_dir: If provided, save output there. Otherwise save next
            to template (existing behavior).

    Returns:
        Tuple (out_path, summary). When dry_run=True, out_path is the
        predicted output path that WOULD be written (still computed
        for UI display) but no file is written.
    """
    # ... existing parsing + matching logic ...

    # Compute output path
    out_name = f"{template_path.stem} [Auto Filled]{template_path.suffix}"
    out_path = (out_dir or template_path.parent) / out_name

    # Existing matching + writing logic — gate the wb.save() on dry_run
    if not dry_run:
        wb.save(out_path)

    return out_path, summary
```

Keep all other logic identical. Just gate the save call.

If existing signature uses positional args differently or returns differently, adapt while preserving existing test compatibility (tests/test_report_filler.py).

- [ ] **Step 4.5: Run tests to verify PASS**

```bash
../../../.venv/Scripts/python.exe -m pytest tests/test_report_filler.py tests/test_report_filler_dry_run.py -v
```

Expected: existing report_filler tests (2) + new tests (2) = all pass.

- [ ] **Step 4.6: Read current export.py**

Read `src/ui/screens/export.py`. Note structure:
- Header
- Picker card with path label + Browse
- preview_frame
- action_row (just Export button)
- Methods: `_render_preview_cards`, `_pick`, `_do_export`

You'll do extensive refactor preserving the underlying export logic but restructuring UI.

- [ ] **Step 4.7: Refactor export.py imports + add module helpers**

Replace top of `src/ui/screens/export.py` with:

```python
import os
from pathlib import Path
from tkinter import filedialog, messagebox
import customtkinter as ctk

from src.config import DB_PATH
from src.db.connection import get_connection
from src.db.settings import get_setting, set_setting
from src.db.export_history import record_export, list_recent_exports
from src.core.report_filler import fill_monthly_report
from src.ui.components.kpi_card import KPICard
from src.ui.screens.import_screen import _format_month_id, _format_relative_time
from src.ui.theme import (
    FONT_FAMILY,
    COLOR_BG, COLOR_SURFACE, COLOR_SURFACE_HIGH,
    COLOR_BORDER, COLOR_BORDER_STRONG,
    COLOR_ACCENT, COLOR_ACCENT_HOVER,
    COLOR_INFO, COLOR_SUCCESS, COLOR_WARN,
    COLOR_TEXT, COLOR_TEXT_DIM, COLOR_TEXT_MUTED, COLOR_TEXT_DISABLED,
    FONT_DISPLAY, FONT_SUBHEAD,
    FONT_BODY, FONT_BODY_BOLD, FONT_SMALL, FONT_LABEL,
    FONT_MONO_DATA, FONT_MONO_SMALL,
    SPACE_XS, SPACE_SM, SPACE_MD, SPACE_LG,
    RADIUS_SM, RADIUS_MD,
)


def _compute_output_filename(template_path: Path) -> str:
    """Predict the [Auto Filled] output name from template path."""
    return f"{template_path.stem} [Auto Filled]{template_path.suffix}"
```

- [ ] **Step 4.8: Refactor `_build` method to new layout**

Replace the `ExportScreen` class `_build` method:

```python
def __init__(self, parent):
    super().__init__(parent, fg_color="transparent")
    self._selected: Path | None = None
    self._dry_summary = None
    self._build()


def _build(self):
    # Header
    ctk.CTkLabel(
        self, text="Export Laporan Bulanan",
        font=FONT_DISPLAY, text_color=COLOR_TEXT,
    ).pack(anchor="w", pady=(0, SPACE_LG))

    # ── Active month banner ──
    self.banner = ctk.CTkFrame(
        self, fg_color="#08222B",  # cyan tint
        border_width=1, border_color="#12454F",
        corner_radius=RADIUS_MD,
    )
    self.banner.pack(fill="x", pady=(0, SPACE_MD))
    self.banner_icon = ctk.CTkLabel(
        self.banner, text="📆",
        font=(FONT_FAMILY, 16),
        text_color=COLOR_INFO,
    )
    self.banner_icon.pack(side="left", padx=(SPACE_MD, SPACE_SM), pady=SPACE_SM)
    self.banner_text = ctk.CTkLabel(
        self.banner, text="",
        font=FONT_BODY,
        text_color=COLOR_TEXT,
        anchor="w", justify="left",
    )
    self.banner_text.pack(side="left", fill="x", expand=True, pady=SPACE_SM)
    self._update_banner()

    # ── Drop zone for template pick (initial state) ──
    self.picker_zone = self._build_picker_zone()
    self.picker_zone.pack(fill="x", pady=(0, SPACE_LG))

    # ── File chip (shown after pick) ──
    self.chip_frame = ctk.CTkFrame(
        self, fg_color=COLOR_SURFACE,
        border_width=1, border_color=COLOR_BORDER,
        corner_radius=RADIUS_MD,
    )
    # Not packed initially

    # ── Preview cards (after dry-run) ──
    self.preview_frame = ctk.CTkFrame(self, fg_color="transparent")
    self.preview_frame.pack(fill="x", pady=(0, SPACE_LG))
    self._render_preview_placeholder()

    # ── Result strip (after successful export) ──
    self.result_frame = ctk.CTkFrame(self, fg_color="transparent")
    # Not packed initially

    # ── History list at bottom ──
    self.history_frame = ctk.CTkFrame(
        self, fg_color=COLOR_SURFACE,
        border_width=1, border_color=COLOR_BORDER,
        corner_radius=RADIUS_MD,
    )
    self.history_frame.pack(fill="x", side="bottom")
    self._render_history()


def _build_picker_zone(self):
    """Build the picker card shown when no template selected."""
    zone = ctk.CTkFrame(
        self, fg_color=COLOR_SURFACE,
        border_width=1, border_color=COLOR_BORDER,
        corner_radius=RADIUS_MD,
    )
    ctk.CTkLabel(
        zone, text="TEMPLATE LAPORAN BULANAN",
        font=FONT_LABEL, text_color=COLOR_TEXT_MUTED,
    ).pack(anchor="w", padx=SPACE_LG, pady=(SPACE_MD, SPACE_XS))

    row = ctk.CTkFrame(zone, fg_color="transparent")
    row.pack(fill="x", padx=SPACE_LG, pady=(0, SPACE_MD))
    ctk.CTkLabel(
        row, text="(belum ada template dipilih)",
        font=FONT_MONO_DATA, text_color=COLOR_TEXT_MUTED,
        anchor="w",
    ).pack(side="left", fill="x", expand=True)
    ctk.CTkButton(
        row, text="📁 Browse",
        command=self._pick,
        fg_color="transparent",
        border_width=1, border_color=COLOR_INFO,
        text_color=COLOR_INFO,
        hover_color=COLOR_SURFACE_HIGH,
        font=FONT_BODY_BOLD,
        width=120,
    ).pack(side="right", padx=(SPACE_SM, 0))
    return zone
```

- [ ] **Step 4.9: Add `_show_chip`, `_hide_chip`, `_update_banner` helpers**

Append to ExportScreen class:

```python
def _show_chip(self, template_path: Path):
    """Replace picker zone with file chip + inline action buttons."""
    self.picker_zone.pack_forget()
    self.result_frame.pack_forget()  # hide result strip if showing from prior export

    for w in self.chip_frame.winfo_children():
        w.destroy()

    icon = ctk.CTkLabel(
        self.chip_frame, text="📄",
        font=(FONT_FAMILY, 24),
        text_color=COLOR_TEXT,
    )
    icon.pack(side="left", padx=(SPACE_MD, SPACE_SM), pady=SPACE_MD)

    info = ctk.CTkFrame(self.chip_frame, fg_color="transparent")
    info.pack(side="left", fill="x", expand=True, pady=SPACE_MD)
    ctk.CTkLabel(
        info, text="TEMPLATE LAPORAN BULANAN",
        font=FONT_LABEL, text_color=COLOR_TEXT_MUTED,
        anchor="w",
    ).pack(fill="x")
    ctk.CTkLabel(
        info, text=template_path.name,
        font=FONT_MONO_DATA, text_color=COLOR_TEXT,
        anchor="w",
    ).pack(fill="x")
    size_kb = template_path.stat().st_size // 1024
    ctk.CTkLabel(
        info, text=f"{template_path.parent} · {size_kb} KB",
        font=FONT_MONO_SMALL, text_color=COLOR_TEXT_MUTED,
        anchor="w",
    ).pack(fill="x")
    # Filename preview line
    out_name = _compute_output_filename(template_path)
    ctk.CTkLabel(
        info, text=f"→ Akan menyimpan sebagai: {out_name}",
        font=FONT_MONO_SMALL, text_color=COLOR_TEXT_DISABLED,
        anchor="w",
    ).pack(fill="x", pady=(SPACE_XS, 0))

    actions = ctk.CTkFrame(self.chip_frame, fg_color="transparent")
    actions.pack(side="right", padx=SPACE_MD, pady=SPACE_MD)
    ctk.CTkButton(
        actions, text="↻ Ganti",
        command=self._pick,
        fg_color="transparent",
        border_width=1, border_color=COLOR_BORDER_STRONG,
        text_color=COLOR_TEXT_DIM,
        hover_color=COLOR_SURFACE_HIGH,
        font=FONT_BODY_BOLD,
        width=80,
    ).pack(side="left", padx=(0, SPACE_XS))
    ctk.CTkButton(
        actions, text="💾 Export",
        command=self._do_export,
        fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER,
        text_color=COLOR_BG,
        font=FONT_BODY_BOLD,
        width=110,
    ).pack(side="left")

    self.chip_frame.pack(fill="x", pady=(0, SPACE_MD), before=self.preview_frame)


def _hide_chip(self):
    """Return to picker-zone state."""
    self.chip_frame.pack_forget()
    self.picker_zone.pack(fill="x", pady=(0, SPACE_LG), before=self.preview_frame)


def _update_banner(self):
    """Refresh banner with current_month info + data summary."""
    with get_connection(DB_PATH) as conn:
        current = get_setting(conn, "current_month") or ""
        if current:
            # Pull data summary for active month
            from src.core.week_utils import full_month_range
            start, end = full_month_range(current)
            row = conn.execute("""
                SELECT
                    COUNT(DISTINCT employee_id) AS emp_count,
                    SUM(CASE WHEN has_issue = 1 THEN 1 ELSE 0 END) AS issue_count,
                    SUM(CASE WHEN has_issue = 1 AND reason_category IS NULL THEN 1 ELSE 0 END) AS unresolved_count
                FROM attendance_records
                WHERE tanggal BETWEEN ? AND ?
            """, (start, end)).fetchone()
            emp = row["emp_count"] or 0
            issues = row["issue_count"] or 0
            unresolved = row["unresolved_count"] or 0
    if current:
        self.banner.configure(fg_color="#08222B", border_color="#12454F")
        self.banner_icon.configure(text="📆", text_color=COLOR_INFO)
        self.banner_text.configure(
            text=(
                f"Akan mengisi laporan untuk: {_format_month_id(current)}\n"
                f"{emp} pegawai · {issues} issues · {unresolved} unresolved"
            ),
        )
    else:
        self.banner.configure(fg_color="#2A0A14", border_color="#5C1E2A")
        self.banner_icon.configure(text="⚠", text_color=COLOR_WARN)
        self.banner_text.configure(
            text="Belum ada bulan aktif — pilih di Active Month dulu.",
        )
```

- [ ] **Step 4.10: Update `_render_preview_placeholder` + `_render_preview_cards`**

Update existing methods to align with new flow (dry-run mode):

```python
def _render_preview_placeholder(self):
    for child in self.preview_frame.winfo_children():
        child.destroy()
    ctk.CTkLabel(
        self.preview_frame, text="(pilih template untuk preview match)",
        font=FONT_BODY, text_color=COLOR_TEXT_MUTED,
    ).pack(anchor="w", pady=SPACE_SM)


def _render_preview_cards(self, filled: int, na: int, not_found: int):
    """Render 3 dry-run preview cards: Akan terisi / NA / Tidak ditemukan."""
    for child in self.preview_frame.winfo_children():
        child.destroy()

    for i in range(3):
        self.preview_frame.grid_columnconfigure(i, weight=1)

    cards = [
        ("Akan terisi", str(filled), COLOR_SUCCESS),
        ("NA / Belum kabar", str(na), COLOR_WARN),
        ("Tidak ditemukan", str(not_found), COLOR_WARN if not_found > 0 else COLOR_TEXT_MUTED),
    ]
    for col, (label, value, value_color) in enumerate(cards):
        KPICard(
            self.preview_frame, label, value,
            value_color=value_color, mono=True,
        ).grid(row=0, column=col, sticky="nsew", padx=SPACE_XS, pady=0)
```

- [ ] **Step 4.11: Add `_render_result_strip` helper**

Append:

```python
def _render_result_strip(self, out_path: Path, summary):
    """Show emerald-bordered success strip with Folder/Open buttons."""
    for w in self.result_frame.winfo_children():
        w.destroy()

    strip = ctk.CTkFrame(
        self.result_frame,
        fg_color="#0F2218",  # emerald 8% tint
        border_width=1, border_color="#1A4434",  # emerald 25%
        corner_radius=RADIUS_MD,
    )
    strip.pack(fill="x")

    icon = ctk.CTkLabel(
        strip, text="✓",
        font=(FONT_FAMILY, 22, "bold"),
        text_color=COLOR_SUCCESS,
    )
    icon.pack(side="left", padx=(SPACE_MD, SPACE_SM), pady=SPACE_MD)

    info = ctk.CTkFrame(strip, fg_color="transparent")
    info.pack(side="left", fill="x", expand=True, pady=SPACE_MD)
    ctk.CTkLabel(
        info, text="Sukses. File tersimpan sebagai:",
        font=FONT_BODY_BOLD, text_color=COLOR_TEXT,
        anchor="w",
    ).pack(fill="x")
    ctk.CTkLabel(
        info, text=out_path.name,
        font=FONT_MONO_DATA, text_color=COLOR_TEXT,
        anchor="w",
    ).pack(fill="x")
    ctk.CTkLabel(
        info,
        text=f"{summary.filled_count} terisi · {summary.na_count} NA · {summary.not_found_count} not found",
        font=FONT_MONO_SMALL, text_color=COLOR_TEXT_MUTED,
        anchor="w",
    ).pack(fill="x", pady=(SPACE_XS, 0))

    actions = ctk.CTkFrame(strip, fg_color="transparent")
    actions.pack(side="right", padx=SPACE_MD, pady=SPACE_MD)
    ctk.CTkButton(
        actions, text="📂 Folder",
        command=lambda: self._open_folder(out_path.parent),
        fg_color="transparent",
        border_width=1, border_color=COLOR_INFO,
        text_color=COLOR_INFO,
        hover_color=COLOR_SURFACE_HIGH,
        font=FONT_BODY_BOLD,
        width=90,
    ).pack(side="left", padx=(0, SPACE_XS))
    ctk.CTkButton(
        actions, text="📄 Open",
        command=lambda: self._open_file(out_path),
        fg_color="transparent",
        border_width=1, border_color=COLOR_INFO,
        text_color=COLOR_INFO,
        hover_color=COLOR_SURFACE_HIGH,
        font=FONT_BODY_BOLD,
        width=90,
    ).pack(side="left")

    self.result_frame.pack(fill="x", pady=(0, SPACE_LG), before=self.history_frame)


def _open_folder(self, folder: Path):
    try:
        os.startfile(str(folder))
    except Exception as e:
        messagebox.showwarning("Tidak bisa buka folder", str(e))


def _open_file(self, file_path: Path):
    try:
        os.startfile(str(file_path))
    except Exception as e:
        messagebox.showwarning("Tidak bisa buka file", str(e))
```

- [ ] **Step 4.12: Add `_render_history` helper**

Append:

```python
def _render_history(self):
    """Render the 'Riwayat Export Terakhir' list at the bottom."""
    for w in self.history_frame.winfo_children():
        w.destroy()

    ctk.CTkLabel(
        self.history_frame, text="RIWAYAT EXPORT TERAKHIR",
        font=FONT_LABEL, text_color=COLOR_TEXT_MUTED,
        anchor="w",
    ).pack(fill="x", padx=SPACE_MD, pady=(SPACE_SM, SPACE_XS))

    with get_connection(DB_PATH) as conn:
        items = list_recent_exports(conn, limit=5)

    if not items:
        ctk.CTkLabel(
            self.history_frame, text="(belum ada riwayat export)",
            font=FONT_BODY, text_color=COLOR_TEXT_MUTED,
            anchor="w",
        ).pack(fill="x", padx=SPACE_MD, pady=(0, SPACE_SM))
        return

    for it in items:
        row = ctk.CTkFrame(self.history_frame, fg_color="transparent")
        row.pack(fill="x", padx=SPACE_MD, pady=2)
        ctk.CTkLabel(
            row, text=_format_relative_time(it["created_at"]),
            font=FONT_MONO_SMALL, text_color=COLOR_TEXT_MUTED,
            anchor="w", width=120,
        ).pack(side="left")
        ctk.CTkLabel(
            row, text=Path(it["out_path"]).name,
            font=FONT_MONO_DATA, text_color=COLOR_TEXT,
            anchor="w",
        ).pack(side="left", fill="x", expand=True, padx=(SPACE_SM, SPACE_SM))
        total = it["filled"] + it["na"]
        is_full = it["na"] == 0 and it["not_found"] == 0
        badge_text = f"✓ {it['filled']}/{total}" if is_full else f"{it['filled']}/{total}"
        badge_bg = "#0F2218" if is_full else "#22141A"
        badge_color = COLOR_SUCCESS if is_full else COLOR_WARN
        ctk.CTkLabel(
            row, text=badge_text,
            font=FONT_MONO_SMALL, text_color=badge_color,
            fg_color=badge_bg, corner_radius=RADIUS_SM,
            anchor="e", width=80,
        ).pack(side="right")
    ctk.CTkFrame(self.history_frame, fg_color="transparent", height=SPACE_SM).pack()
```

- [ ] **Step 4.13: Update `_pick` for dry-run preview + R5 folder memory**

Replace `_pick`:

```python
def _pick(self):
    with get_connection(DB_PATH) as conn:
        initialdir = get_setting(conn, "last_export_template_folder") or str(Path.home() / "Documents")

    path = filedialog.askopenfilename(
        title="Pilih Laporan Bulanan",
        initialdir=initialdir,
        filetypes=[("Excel", "*.xlsx")],
    )
    if not path:
        return
    self._selected = Path(path)

    with get_connection(DB_PATH) as conn:
        set_setting(conn, "last_export_template_folder", str(self._selected.parent))

    # Run dry-run preview
    try:
        with get_connection(DB_PATH) as conn:
            out_path, summary = fill_monthly_report(
                self._selected, conn, dry_run=True,
            )
    except Exception as e:
        messagebox.showerror("Error preview", str(e))
        self._selected = None
        return

    self._dry_summary = summary
    self._show_chip(self._selected)
    self._render_preview_cards(
        filled=summary.filled_count,
        na=summary.na_count,
        not_found=summary.not_found_count,
    )
    self._update_banner()
```

- [ ] **Step 4.14: Update `_do_export` to actual save + result strip**

Replace `_do_export`:

```python
def _do_export(self):
    if not self._selected:
        return
    try:
        with get_connection(DB_PATH) as conn:
            out_path, summary = fill_monthly_report(
                self._selected, conn, dry_run=False,
            )
            # Determine year_month for history record
            from src.db.settings import get_setting as _g
            ym = _g(conn, "current_month") or "?"
            record_export(
                conn,
                out_path=str(out_path),
                template=str(self._selected),
                year_month=ym,
                filled=summary.filled_count,
                na=summary.na_count,
                not_found=summary.not_found_count,
            )
    except Exception as e:
        messagebox.showerror("Error export", str(e))
        return

    self._render_result_strip(out_path, summary)
    self._render_history()
```

- [ ] **Step 4.15: Run pytest**

```bash
../../../.venv/Scripts/python.exe -m pytest -q
```

Expected: 108 + 2 = **110 passed**.

- [ ] **Step 4.16: Verify import**

```bash
../../../.venv/Scripts/python.exe -c "from src.ui.screens.export import ExportScreen; print('OK')"
```

Expected: OK.

- [ ] **Step 4.17: Commit Phase 4**

```bash
git add src/core/report_filler.py tests/test_report_filler_dry_run.py src/ui/screens/export.py
git commit -m "$(cat <<'EOF'
feat(ui): Export core refresh + R5 folder memory

Phase 4/7 dari Import+Export UX refresh:
- fill_monthly_report: tambah dry_run dan out_dir keyword arguments
  (backward compatible). Dry-run = perform matching + return summary
  TANPA wb.save. out_dir redirects save location. 2 new tests.
- Export screen extensive refactor:
  - Active month banner cyan dengan data summary (28 emp · 142
    issues · 12 unresolved), rose warning kalau tidak ada bulan aktif
  - Pick template → langsung dry-run → 3 preview cards (Akan terisi
    emerald, NA/Tidak ditemukan rose)
  - File chip dengan inline [↻ Ganti] [💾 Export] + filename
    preview ("→ Akan menyimpan sebagai: ...")
  - Click Export → emerald result strip dengan [📂 Folder] [📄 Open]
    actionable buttons (os.startfile). messagebox.showinfo dihapus.
  - Riwayat Export history list dari export_history table
- R5: last_export_template_folder setting persisted on browse

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Phase 5 — Export R2 Smart Filename + R7 Preview + R8 Save Destination

**Files:**
- Create: `src/core/filename_parser.py`
- Create: `tests/test_filename_parser.py`
- Modify: `src/ui/screens/export.py`

**Goal of this task:** Add filename detection helper. Warn user if template's detected month doesn't match current_month. Add Preview File button (open temp .xlsx). Add Save Destination dropdown.

- [ ] **Step 5.1: Write failing test for filename detection**

Create `tests/test_filename_parser.py`:

```python
"""Tests for detect_year_month_from_filename."""
import pytest
from pathlib import Path
from src.core.filename_parser import detect_year_month_from_filename


def test_indonesian_full_month_name():
    assert detect_year_month_from_filename(
        Path("Laporan Bulanan April 2026.xlsx")
    ) == "2026-04"


def test_indonesian_short_month_name():
    assert detect_year_month_from_filename(
        Path("Laporan Apr 2026.xlsx")
    ) == "2026-04"


def test_iso_yyyy_mm_format():
    assert detect_year_month_from_filename(
        Path("report-2026-05.xlsx")
    ) == "2026-05"


def test_iso_underscore_format():
    assert detect_year_month_from_filename(
        Path("report_2026_03.xlsx")
    ) == "2026-03"


def test_returns_none_when_no_match():
    assert detect_year_month_from_filename(
        Path("random-file.xlsx")
    ) is None


def test_case_insensitive():
    assert detect_year_month_from_filename(
        Path("Laporan MARET 2026.xlsx")
    ) == "2026-03"
```

- [ ] **Step 5.2: Run test to verify FAIL**

```bash
../../../.venv/Scripts/python.exe -m pytest tests/test_filename_parser.py -v
```

Expected: ModuleNotFoundError.

- [ ] **Step 5.3: Implement filename_parser**

Create `src/core/filename_parser.py`:

```python
"""Detect YYYY-MM from filenames containing month names or ISO codes."""
import re
from pathlib import Path


_MONTH_NAMES = {
    "januari": 1, "jan": 1,
    "februari": 2, "february": 2, "feb": 2,
    "maret": 3, "march": 3, "mar": 3,
    "april": 4, "apr": 4,
    "mei": 5, "may": 5,
    "juni": 6, "june": 6, "jun": 6,
    "juli": 7, "july": 7, "jul": 7,
    "agustus": 8, "august": 8, "ags": 8, "aug": 8,
    "september": 9, "sep": 9, "sept": 9,
    "oktober": 10, "october": 10, "okt": 10, "oct": 10,
    "november": 11, "nov": 11,
    "desember": 12, "december": 12, "des": 12, "dec": 12,
}


def detect_year_month_from_filename(path: Path) -> str | None:
    """Parse filename for Indonesian/English month + year.

    Returns 'YYYY-MM' or None if no match.

    Recognized patterns:
        "Laporan Bulanan April 2026.xlsx" → "2026-04"
        "Laporan Apr 2026 [filled].xlsx" → "2026-04"
        "report-2026-05.xlsx" → "2026-05"
        "report_2026_03.xlsx" → "2026-03"
    """
    name = path.stem.lower()

    # Try ISO 'YYYY-MM' or 'YYYY_MM' first (more specific)
    iso_match = re.search(r"(20\d{2})[-_](\d{2})", name)
    if iso_match:
        return f"{iso_match.group(1)}-{iso_match.group(2)}"

    # Sort month names by length DESC so "september" matches before "sep"
    sorted_months = sorted(_MONTH_NAMES.items(), key=lambda x: -len(x[0]))
    for word, month_num in sorted_months:
        # Match whole-word boundary to avoid false positives
        if re.search(rf"\b{re.escape(word)}\b", name):
            year_match = re.search(r"\b(20\d{2})\b", name)
            if year_match:
                return f"{year_match.group(1)}-{month_num:02d}"

    return None
```

- [ ] **Step 5.4: Run tests to verify PASS**

```bash
../../../.venv/Scripts/python.exe -m pytest tests/test_filename_parser.py -v
```

Expected: 6 passed.

- [ ] **Step 5.5: Wire R2 smart detection into Export `_pick`**

In `src/ui/screens/export.py`, update imports:

```python
from src.core.filename_parser import detect_year_month_from_filename
```

In `_pick`, after `self._selected = Path(path)` and before `set_setting`, add:

```python
# R2 — smart filename detection: warn if file mentions different month
detected_ym = detect_year_month_from_filename(self._selected)
with get_connection(DB_PATH) as conn:
    current_ym = get_setting(conn, "current_month") or ""
self._filename_mismatch = bool(detected_ym and current_ym and detected_ym != current_ym)
self._detected_ym = detected_ym
```

Then in `_update_banner`, add handling for the mismatch state:

```python
def _update_banner(self):
    """Refresh banner with current_month + filename mismatch warn."""
    with get_connection(DB_PATH) as conn:
        current = get_setting(conn, "current_month") or ""
        if current:
            from src.core.week_utils import full_month_range
            start, end = full_month_range(current)
            row = conn.execute("""
                SELECT
                    COUNT(DISTINCT employee_id) AS emp_count,
                    SUM(CASE WHEN has_issue = 1 THEN 1 ELSE 0 END) AS issue_count,
                    SUM(CASE WHEN has_issue = 1 AND reason_category IS NULL THEN 1 ELSE 0 END) AS unresolved_count
                FROM attendance_records
                WHERE tanggal BETWEEN ? AND ?
            """, (start, end)).fetchone()
            emp = row["emp_count"] or 0
            issues = row["issue_count"] or 0
            unresolved = row["unresolved_count"] or 0

    # Check for filename mismatch (R2)
    mismatch = getattr(self, "_filename_mismatch", False)
    detected = getattr(self, "_detected_ym", None)

    if mismatch and detected:
        # Rose warn — file month doesn't match active month
        self.banner.configure(fg_color="#2A0A14", border_color="#5C1E2A")
        self.banner_icon.configure(text="⚠", text_color=COLOR_WARN)
        self.banner_text.configure(
            text=(
                f"Mismatch: File mention '{_format_month_id(detected)}' "
                f"tapi bulan aktif '{_format_month_id(current)}'.\n"
                f"Data dari {_format_month_id(current)} akan dimasukkan ke template tersebut."
            ),
        )
    elif current:
        # Cyan default
        self.banner.configure(fg_color="#08222B", border_color="#12454F")
        self.banner_icon.configure(text="📆", text_color=COLOR_INFO)
        self.banner_text.configure(
            text=(
                f"Akan mengisi laporan untuk: {_format_month_id(current)}\n"
                f"{emp} pegawai · {issues} issues · {unresolved} unresolved"
            ),
        )
    else:
        # Rose — no active month
        self.banner.configure(fg_color="#2A0A14", border_color="#5C1E2A")
        self.banner_icon.configure(text="⚠", text_color=COLOR_WARN)
        self.banner_text.configure(
            text="Belum ada bulan aktif — pilih di Active Month dulu.",
        )
```

Also reset on _hide_chip:

```python
def _hide_chip(self):
    """Return to picker-zone state."""
    self.chip_frame.pack_forget()
    self.picker_zone.pack(fill="x", pady=(0, SPACE_LG), before=self.preview_frame)
    self._filename_mismatch = False
    self._detected_ym = None
    self._update_banner()
```

And update `__init__`:

```python
def __init__(self, parent):
    super().__init__(parent, fg_color="transparent")
    self._selected: Path | None = None
    self._dry_summary = None
    self._filename_mismatch = False
    self._detected_ym: str | None = None
    self._build()
```

- [ ] **Step 5.6: Add R7 Preview File button + R8 Save Destination dropdown**

Update `_show_chip` to add Preview button between Ganti and Export:

```python
def _show_chip(self, template_path: Path):
    """Replace picker zone with file chip + inline action buttons."""
    self.picker_zone.pack_forget()
    self.result_frame.pack_forget()

    for w in self.chip_frame.winfo_children():
        w.destroy()

    icon = ctk.CTkLabel(
        self.chip_frame, text="📄",
        font=(FONT_FAMILY, 24),
        text_color=COLOR_TEXT,
    )
    icon.pack(side="left", padx=(SPACE_MD, SPACE_SM), pady=SPACE_MD)

    info = ctk.CTkFrame(self.chip_frame, fg_color="transparent")
    info.pack(side="left", fill="x", expand=True, pady=SPACE_MD)
    ctk.CTkLabel(
        info, text="TEMPLATE LAPORAN BULANAN",
        font=FONT_LABEL, text_color=COLOR_TEXT_MUTED,
        anchor="w",
    ).pack(fill="x")
    ctk.CTkLabel(
        info, text=template_path.name,
        font=FONT_MONO_DATA, text_color=COLOR_TEXT,
        anchor="w",
    ).pack(fill="x")
    size_kb = template_path.stat().st_size // 1024
    ctk.CTkLabel(
        info, text=f"{template_path.parent} · {size_kb} KB",
        font=FONT_MONO_SMALL, text_color=COLOR_TEXT_MUTED,
        anchor="w",
    ).pack(fill="x")
    out_name = _compute_output_filename(template_path)
    ctk.CTkLabel(
        info, text=f"→ Akan menyimpan sebagai: {out_name}",
        font=FONT_MONO_SMALL, text_color=COLOR_TEXT_DISABLED,
        anchor="w",
    ).pack(fill="x", pady=(SPACE_XS, 0))

    actions = ctk.CTkFrame(self.chip_frame, fg_color="transparent")
    actions.pack(side="right", padx=SPACE_MD, pady=SPACE_MD)
    ctk.CTkButton(
        actions, text="↻ Ganti",
        command=self._pick,
        fg_color="transparent",
        border_width=1, border_color=COLOR_BORDER_STRONG,
        text_color=COLOR_TEXT_DIM,
        hover_color=COLOR_SURFACE_HIGH,
        font=FONT_BODY_BOLD,
        width=80,
    ).pack(side="left", padx=(0, SPACE_XS))
    ctk.CTkButton(
        actions, text="👁 Preview",
        command=self._preview_file,
        fg_color="transparent",
        border_width=1, border_color=COLOR_INFO,
        text_color=COLOR_INFO,
        hover_color=COLOR_SURFACE_HIGH,
        font=FONT_BODY_BOLD,
        width=100,
    ).pack(side="left", padx=(0, SPACE_XS))
    ctk.CTkButton(
        actions, text="💾 Export",
        command=self._do_export,
        fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER,
        text_color=COLOR_BG,
        font=FONT_BODY_BOLD,
        width=110,
    ).pack(side="left")

    self.chip_frame.pack(fill="x", pady=(0, SPACE_MD), before=self.preview_frame)
```

Add `_preview_file` method:

```python
def _preview_file(self):
    """R7 — generate the filled .xlsx in a temp dir and open with default viewer."""
    if not self._selected:
        return
    import tempfile
    tmp_dir = Path(tempfile.gettempdir())
    try:
        with get_connection(DB_PATH) as conn:
            out_path, _summary = fill_monthly_report(
                self._selected, conn, dry_run=False, out_dir=tmp_dir,
            )
        os.startfile(str(out_path))
    except Exception as e:
        messagebox.showerror("Error preview", str(e))
```

Add R8 Save Destination dropdown. Insert above chip_frame in `_build`:

```python
# In _build, between banner and picker_zone:
self.save_dest_frame = self._build_save_destination()
self.save_dest_frame.pack(fill="x", pady=(0, SPACE_MD))
```

Add method `_build_save_destination`:

```python
def _build_save_destination(self):
    """R8 — dropdown to choose where exported file is saved."""
    frame = ctk.CTkFrame(self, fg_color="transparent")
    ctk.CTkLabel(
        frame, text="SIMPAN OUTPUT KE",
        font=FONT_LABEL, text_color=COLOR_TEXT_MUTED,
    ).pack(anchor="w", padx=SPACE_XS)

    options = [
        "Folder template (default)",
        "Documents/HR Reports/",
        "Pilih folder lain...",
    ]
    self.save_dest_var = ctk.StringVar(value=options[0])
    # Restore from settings if previously set
    with get_connection(DB_PATH) as conn:
        mode = get_setting(conn, "export_save_mode") or "template_folder"
    mode_to_label = {
        "template_folder": options[0],
        "hr_reports": options[1],
        "custom": options[2],
    }
    self.save_dest_var.set(mode_to_label.get(mode, options[0]))

    self.save_dest_menu = ctk.CTkOptionMenu(
        frame,
        values=options,
        variable=self.save_dest_var,
        command=self._on_save_dest_change,
        fg_color=COLOR_SURFACE_HIGH,
        button_color=COLOR_BORDER,
        button_hover_color=COLOR_BORDER_STRONG,
        text_color=COLOR_TEXT,
        font=FONT_BODY,
        width=280,
    )
    self.save_dest_menu.pack(anchor="w", padx=SPACE_XS, pady=(SPACE_XS, 0))
    return frame


def _on_save_dest_change(self, value: str):
    label_to_mode = {
        "Folder template (default)": "template_folder",
        "Documents/HR Reports/": "hr_reports",
        "Pilih folder lain...": "custom",
    }
    mode = label_to_mode.get(value, "template_folder")
    if mode == "custom":
        chosen = filedialog.askdirectory(title="Pilih folder save destination")
        if not chosen:
            # Revert to previous value
            with get_connection(DB_PATH) as conn:
                prev_mode = get_setting(conn, "export_save_mode") or "template_folder"
            self.save_dest_var.set({
                "template_folder": "Folder template (default)",
                "hr_reports": "Documents/HR Reports/",
                "custom": "Pilih folder lain...",
            }[prev_mode])
            return
        with get_connection(DB_PATH) as conn:
            set_setting(conn, "export_save_custom_path", chosen)
            set_setting(conn, "export_save_mode", "custom")
    else:
        with get_connection(DB_PATH) as conn:
            set_setting(conn, "export_save_mode", mode)


def _resolve_save_destination(self, template_path: Path) -> Path:
    """Returns the directory to save export based on current save mode."""
    with get_connection(DB_PATH) as conn:
        mode = get_setting(conn, "export_save_mode") or "template_folder"
        custom = get_setting(conn, "export_save_custom_path") or ""
    if mode == "hr_reports":
        target = Path.home() / "Documents" / "HR Reports"
        target.mkdir(parents=True, exist_ok=True)
        return target
    if mode == "custom" and custom:
        return Path(custom)
    # default: template's parent
    return template_path.parent
```

Then update `_do_export` to use the resolver:

```python
def _do_export(self):
    if not self._selected:
        return
    try:
        out_dir = self._resolve_save_destination(self._selected)
        with get_connection(DB_PATH) as conn:
            out_path, summary = fill_monthly_report(
                self._selected, conn, dry_run=False, out_dir=out_dir,
            )
            ym = get_setting(conn, "current_month") or "?"
            record_export(
                conn,
                out_path=str(out_path),
                template=str(self._selected),
                year_month=ym,
                filled=summary.filled_count,
                na=summary.na_count,
                not_found=summary.not_found_count,
            )
    except Exception as e:
        messagebox.showerror("Error export", str(e))
        return

    self._render_result_strip(out_path, summary)
    self._render_history()
```

- [ ] **Step 5.7: Run pytest**

```bash
../../../.venv/Scripts/python.exe -m pytest -q
```

Expected: 110 + 6 = **116 passed**.

- [ ] **Step 5.8: Verify import**

```bash
../../../.venv/Scripts/python.exe -c "from src.ui.screens.export import ExportScreen; from src.core.filename_parser import detect_year_month_from_filename; print('OK')"
```

Expected: OK.

- [ ] **Step 5.9: Commit Phase 5**

```bash
git add src/core/filename_parser.py tests/test_filename_parser.py src/ui/screens/export.py
git commit -m "$(cat <<'EOF'
feat(ui): Export — R2 smart filename + R7 preview + R8 save destination

Phase 5/7 dari Import+Export UX refresh:
- R2: detect_year_month_from_filename() helper di new module
  src/core/filename_parser.py. Mengenali Indonesian + English month
  names + ISO YYYY-MM format. Case-insensitive, whole-word boundary
  match. 6 tests covering various input formats.
- Export banner switches ke rose warn state ketika detected month
  dari filename ≠ current_month — informs user about mismatch.
- R7: tombol "👁 Preview" di antara Ganti dan Export. Generates
  filled .xlsx ke tempfile.gettempdir() + os.startfile() — buka di
  Excel/default viewer untuk verify sebelum commit.
- R8: Save Destination dropdown above file chip. 3 modes:
  template_folder (default) / hr_reports (auto-create Documents/HR
  Reports/) / custom (filedialog.askdirectory). Settings persisted
  via export_save_mode + export_save_custom_path.
- fill_monthly_report's out_dir param (from Phase 4) wired into
  _resolve_save_destination() based on dropdown choice.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: Phase 6 — R4 Progress Modal + R1 Drag-and-Drop

**Files:**
- Create: `src/ui/components/progress_modal.py`
- Modify: `src/ui/screens/import_screen.py` (wire ProgressModal + windnd)
- Modify: `src/ui/screens/export.py` (wire ProgressModal)
- Modify: `requirements.txt`
- Modify: `HR-Absensi.spec`

**Goal of this task:** Add shared ProgressModal component for long operations. Wire windnd library for real drag-and-drop file support.

- [ ] **Step 6.1: Add windnd to requirements.txt**

Read `requirements.txt`. Add a new line:

```
windnd>=1.0.7
```

(Place alphabetically — wherever fits between existing deps.)

- [ ] **Step 6.2: Install windnd locally**

```bash
../../../.venv/Scripts/python.exe -m pip install "windnd>=1.0.7"
```

Verify installation:

```bash
../../../.venv/Scripts/python.exe -c "import windnd; print('windnd OK:', windnd.__version__ if hasattr(windnd, '__version__') else 'installed')"
```

- [ ] **Step 6.3: Update HR-Absensi.spec for windnd**

Read `HR-Absensi.spec`. Find the `hiddenimports` line:

```python
hiddenimports=['customtkinter', 'PIL'],
```

Update to:

```python
hiddenimports=['customtkinter', 'PIL', 'windnd'],
```

- [ ] **Step 6.4: Create ProgressModal component**

Create `src/ui/components/progress_modal.py`:

```python
"""Shared progress overlay modal — reusable for long operations.

Usage:
    with ProgressModal(parent, title="Memproses file") as p:
        p.update_progress(0.0, "Parsing...")
        # ... work ...
        p.update_progress(0.5, "Inserting rows...")
        # ... more work ...
        p.update_progress(1.0, "Selesai")

The modal uses Tk's single-threaded update() to refresh during long
loops. Acceptable since this is a single-user desktop app — no
concurrent user requests to block.
"""
import customtkinter as ctk

from src.ui.theme import (
    FONT_FAMILY,
    COLOR_BG, COLOR_SURFACE, COLOR_BORDER,
    COLOR_ACCENT, COLOR_TEXT, COLOR_TEXT_MUTED,
    FONT_HEADING, FONT_BODY,
    SPACE_MD, SPACE_LG,
    RADIUS_LG,
)


class ProgressModal:
    """Context-manager wrapper around a CTkToplevel progress overlay."""

    def __init__(self, parent, title: str = "Memproses..."):
        self.parent = parent
        self.title = title
        self.window = None

    def __enter__(self):
        self.window = ctk.CTkToplevel(self.parent)
        self.window.overrideredirect(True)
        self.window.attributes("-topmost", True)
        self.window.configure(fg_color=COLOR_BG)

        # Size + center
        w, h = 400, 140
        self.window.update_idletasks()
        x = (self.window.winfo_screenwidth() - w) // 2
        y = (self.window.winfo_screenheight() - h) // 2
        self.window.geometry(f"{w}x{h}+{x}+{y}")

        # Card frame inside for border
        card = ctk.CTkFrame(
            self.window, fg_color=COLOR_SURFACE,
            border_width=1, border_color=COLOR_BORDER,
            corner_radius=RADIUS_LG,
        )
        card.pack(fill="both", expand=True, padx=4, pady=4)

        # Title
        ctk.CTkLabel(
            card, text=self.title,
            font=FONT_HEADING, text_color=COLOR_TEXT,
        ).pack(pady=(SPACE_LG, SPACE_MD), padx=SPACE_LG, anchor="w")

        # Status text (updateable)
        self.status_lbl = ctk.CTkLabel(
            card, text="...",
            font=FONT_BODY, text_color=COLOR_TEXT_MUTED,
        )
        self.status_lbl.pack(pady=(0, SPACE_MD), padx=SPACE_LG, anchor="w")

        # Progress bar
        self.bar = ctk.CTkProgressBar(
            card, width=320, height=6, corner_radius=3,
            progress_color=COLOR_ACCENT,
            fg_color=COLOR_BORDER,
        )
        self.bar.pack(pady=(0, SPACE_LG), padx=SPACE_LG, anchor="w")
        self.bar.set(0)

        self.window.update()
        return self

    def update_progress(self, pct: float, status: str):
        """Set progress bar (0.0-1.0) and status text. Forces redraw."""
        if self.window is None:
            return
        self.bar.set(max(0.0, min(1.0, pct)))
        self.status_lbl.configure(text=status)
        self.window.update()

    def __exit__(self, *args):
        if self.window is not None:
            try:
                self.window.destroy()
            except Exception:
                pass
            self.window = None
```

- [ ] **Step 6.5: Wire ProgressModal into Import commit**

In `src/ui/screens/import_screen.py`, update imports:

```python
from src.ui.components.progress_modal import ProgressModal
```

Update `_on_confirm` to show progress when committing many rows:

```python
def _on_confirm(self):
    if not self._pending_rows:
        return

    months = [r.tanggal[:7] for r in self._pending_rows if r.tanggal]
    mode_month = Counter(months).most_common(1)[0][0] if months else None

    total_rows = len(self._pending_rows)
    use_progress = total_rows > 50

    if use_progress:
        cm = ProgressModal(self.winfo_toplevel(), title="Memproses Import")
    else:
        from contextlib import nullcontext
        cm = nullcontext()

    with cm as progress, get_connection(DB_PATH) as conn:
        if use_progress:
            progress.update_progress(0.0, f"Inserting {total_rows} rows...")
        for i, r in enumerate(self._pending_rows):
            emp_id = upsert_employee(
                conn, no_staff=r.no_staff, nama=r.nama, dept=r.dept
            )
            upsert_attendance(
                conn, employee_id=emp_id, tanggal=r.tanggal,
                hari=r.hari, tipe=r.tipe, jadwal=r.jadwal,
                masuk=r.masuk, keluar=r.keluar,
                kerja_jam=r.kerja_jam, lembur_jam=r.lembur_jam,
                terlambat_menit=r.terlambat_menit,
                has_issue=1 if is_issue(r) else 0,
                imported_from=r.source_file,
            )
            if use_progress and (i + 1) % 10 == 0:
                progress.update_progress(
                    (i + 1) / total_rows,
                    f"Inserting row {i+1}/{total_rows}...",
                )
        if mode_month:
            set_setting(conn, "current_month", mode_month)

    row_count = len(self._pending_rows)
    month_display = _format_month_id(mode_month) if mode_month else "-"

    self._pending_rows = []
    self._pending_path = None
    self._pending_paths = []
    self._hide_chip()
    self._render_preview_placeholder()
    self._update_banner()
    self._render_history()

    show_success_toast(
        self.winfo_toplevel(),
        title="Impor Berhasil",
        message=(
            f"{row_count} baris fingerprint berhasil diimpor.\n"
            f"Bulan aktif diset ke {month_display}."
        ),
    )
```

- [ ] **Step 6.6: Wire windnd drag-and-drop into Import**

In `src/ui/screens/import_screen.py`, update `_build_dropzone` to register windnd hook. At the END of `_build_dropzone` (right before `return zone`), add:

```python
# R1 — register windnd hook for drag-and-drop file support
try:
    import windnd

    def _on_drop(files):
        # files is list[bytes] of dropped paths
        if not files:
            return
        paths = []
        for f in files:
            try:
                p = Path(f.decode("utf-8") if isinstance(f, bytes) else f)
            except Exception:
                continue
            if p.suffix.lower() in (".xls", ".xlsx"):
                paths.append(p)
        if not paths:
            return
        # Trigger the standard pick-file flow with dropped paths
        self._handle_dropped_paths(paths)

    windnd.hook_dropfiles(zone, func=_on_drop)
except ImportError:
    pass  # windnd not installed — drop zone still click-functional
except Exception:
    pass  # registration failure — graceful degradation
```

Then add the handler method to the ImportScreen class:

```python
def _handle_dropped_paths(self, paths: list[Path]):
    """Process files dropped via windnd hook.

    Same logic as _on_pick_file but bypasses the file dialog.
    """
    with get_connection(DB_PATH) as conn:
        set_setting(conn, "last_import_folder", str(paths[0].parent))

    import time
    t0 = time.perf_counter()
    all_rows = []
    try:
        for p in paths:
            all_rows.extend(parse_fingerprint_file(p))
    except Exception as e:
        messagebox.showerror("Error parsing", str(e))
        return
    parse_ms = int((time.perf_counter() - t0) * 1000)

    if not all_rows:
        messagebox.showwarning("File kosong",
            "Tidak ada baris yang bisa diimpor dari file yang dipilih.")
        return

    self._pending_path = paths[0] if len(paths) == 1 else None
    self._pending_paths = paths
    self._pending_rows = all_rows

    issue_count = sum(1 for r in self._pending_rows if is_issue(r))
    unique_emps = {r.no_staff for r in self._pending_rows}
    dates = sorted({r.tanggal for r in self._pending_rows})
    date_range = _format_short_range(dates[0], dates[-1]) if dates else "(empty)"

    new_emp_count = 0
    with get_connection(DB_PATH) as conn:
        for no_staff in unique_emps:
            if get_employee_by_no_staff(conn, no_staff) is None:
                new_emp_count += 1
        overlap = count_overlap(conn, self._pending_rows)

    if len(paths) == 1:
        filename = paths[0].name
        size_kb = paths[0].stat().st_size // 1024
    else:
        filename = f"{len(paths)} files dropped"
        size_kb = sum(p.stat().st_size for p in paths) // 1024

    self._show_chip(filename, size_kb, parse_ms, is_multi=(len(paths) > 1))
    self._render_preview_cards(
        pegawai_count=len(unique_emps),
        date_range=date_range,
        issue_count=issue_count,
        new_emp_count=new_emp_count,
        overwrite_count=overlap["overwrite"],
    )
    self._update_banner()
```

- [ ] **Step 6.7: Run pytest regression**

```bash
../../../.venv/Scripts/python.exe -m pytest -q
```

Expected: still **116 passed** (no new tests this phase).

- [ ] **Step 6.8: Verify import**

```bash
../../../.venv/Scripts/python.exe -c "from src.ui.components.progress_modal import ProgressModal; from src.ui.screens.import_screen import ImportScreen; from src.ui.screens.export import ExportScreen; print('OK')"
```

Expected: OK.

- [ ] **Step 6.9: Commit Phase 6**

```bash
git add src/ui/components/progress_modal.py src/ui/screens/import_screen.py src/ui/screens/export.py requirements.txt HR-Absensi.spec
git commit -m "$(cat <<'EOF'
feat(ui): R4 progress modal (shared) + R1 drag-and-drop via windnd

Phase 6/7 dari Import+Export UX refresh:
- R4: src/ui/components/progress_modal.py — ProgressModal class
  with context-manager API (with ProgressModal(parent) as p:
  p.update_progress(pct, status)). 400×140 centered modal with
  bordered card + heading + status text + CTkProgressBar.
  Wired into Import _on_confirm (threshold: > 50 rows). Update
  every 10 rows. Tk single-threaded — uses window.update() for
  forced redraw during loop.
- R1: windnd added as new dependency (requirements.txt + spec
  hiddenimports). windnd.hook_dropfiles registered di drop zone.
  Drop .xls / .xlsx file dari Explorer → triggers same flow
  sebagai _on_pick_file via new _handle_dropped_paths method.
  Multi-file drop supported (extends R6 bulk import).
  Graceful degradation kalau windnd import fails — drop zone
  tetap functional via click.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: Phase 7 — Handoff Doc v6 + Smoke Test

**Files:**
- Create: `docs/superpowers/specs/2026-05-15-session-handoff-v6.md`

**Goal of this task:** Write v6 handoff doc + final smoke verification.

- [ ] **Step 7.1: Full pytest**

```bash
../../../.venv/Scripts/python.exe -m pytest -q
```

Expected: **116 passed**.

- [ ] **Step 7.2: Verify all key screens import OK**

```bash
../../../.venv/Scripts/python.exe -c "
from src.ui.app import HRApp
from src.ui.screens.import_screen import ImportScreen
from src.ui.screens.export import ExportScreen
from src.ui.components.progress_modal import ProgressModal
from src.core.filename_parser import detect_year_month_from_filename
from src.db.export_history import record_export, list_recent_exports
from src.db.attendance import list_recent_imports, count_overlap
print('OK')
"
```

Expected: OK.

- [ ] **Step 7.3: Write handoff doc v6**

Create `docs/superpowers/specs/2026-05-15-session-handoff-v6.md`:

```markdown
# HR Absensi App — Session Handoff (Post v6)

**Tanggal:** 2026-05-15
**Author:** Multi-session Claude work — Import+Export UX refresh
**Read this first** — captures everything done in the Import+Export UX session 2026-05-14.

---

## 1. TL;DR

Import + Export screens diperbaiki UX-nya. File chip menggantikan
bottom-button placement, active month banners, dry-run preview di
Export, history list di kedua screen, plus 8 R-items (drag-drop,
smart filename, conflict resolution, progress modal, folder memory,
bulk import, preview, save destination).

**Branch state:**
- Local: `claude/nifty-jemison-706792` ahead of `origin/v5` by 9 commits (spec + plan + 7 implementation phases)
- Base: `origin/v5` (post-JTS overhaul)

**Test suite:** 116 passing (was 98 at v5).

---

## 2. Apa yang berubah (Import + Export UX)

### 2.1 DB layer
- New table `export_history` (id, out_path, template, year_month,
  filled, na, not_found, created_at) + index pada created_at DESC
- New module `src/db/export_history.py` with record_export +
  list_recent_exports
- New function `list_recent_imports` di `src/db/attendance.py`
- New function `count_overlap` di `src/db/attendance.py` for R3
- 12 new tests across 3 test files

### 2.2 Core layer
- `fill_monthly_report` tambah `dry_run` + `out_dir` parameters
  (backward compat — both default to existing behavior)
- New module `src/core/filename_parser.py` —
  `detect_year_month_from_filename` for R2

### 2.3 UI layer
- `src/ui/screens/import_screen.py` extensive refactor:
  file chip, banner, drop zone collapse, Indonesian short range,
  5 KPI cards (added "Akan Menimpa"), history list, bulk multi-file,
  windnd drag-drop integration, progress modal wiring
- `src/ui/screens/export.py` extensive refactor:
  banner, dry-run preview, file chip with inline Export, result
  strip menggantikan messagebox, history list, filename preview,
  Save Destination dropdown, Preview File button, R2 filename
  mismatch warning
- `src/ui/components/progress_modal.py` — new shared component

### 2.4 Build
- `requirements.txt` adds `windnd>=1.0.7`
- `HR-Absensi.spec` adds `'windnd'` to hiddenimports

---

## 3. New file structure (vs v5)

```
src/
├── core/
│   └── filename_parser.py        ← NEW: Indonesian + ISO month detection
├── db/
│   └── export_history.py         ← NEW: export history repo
└── ui/
    └── components/
        └── progress_modal.py     ← NEW: shared progress overlay

tests/
├── test_attendance_count_overlap.py    ← NEW: 3 tests
├── test_db_list_recent_imports.py      ← NEW: 3 tests
├── test_export_history.py              ← NEW: 4 tests
├── test_filename_parser.py             ← NEW: 6 tests
└── test_report_filler_dry_run.py       ← NEW: 2 tests
```

---

## 4. Workflow rules (preserved from v5)

1. **NO auto-push.** User authorizes manually.
2. **.exe may be running** — close before rebuild.
3. **Deploy with rotation** — backup → backup.old, current → backup, new → current.
4. **Test before commit:** `pytest -q` should show 116 passed.

---

## 5. Outstanding / Known Items

### Non-blocking
1. **Print HTML themes** still purple/orange — separate effort (deferred from v5)
2. **About dialog** belum ada
3. **Light mode** tidak di plan
4. **Conflict resolution mode toggle** — currently overwrite is silent (existing upsert behavior). R3 only surfaces count. Future: per-row skip/overwrite.
5. **Drag-and-drop multi-file** — current implementation supports single + multi via windnd. Tested with explorer.
6. **Export to PDF** — only .xlsx for now.

---

## 6. Quick-start commands

```bash
cd "D:\Gawe\Project X\HR App\.claude\worktrees\nifty-jemison-706792"

# Run tests
../../../.venv/Scripts/python.exe -m pytest -q
# Expected: 116 passed

# Build .exe (close instance first)
../../../.venv/Scripts/pyinstaller.exe HR-Absensi.spec --clean --noconfirm

# Check branch state
git rev-list --count origin/v5..HEAD
```

---

## 7. Doc index

| # | Doc | What it covers |
|---|---|---|
| 1 | `2026-05-11-hr-absensi-app-design.md` | Original MVP |
| 2 | `2026-05-12-*-design.md` × 4 | v1-v4 iterations |
| 3 | `2026-05-13-session-handoff-v4.md` | v4 cumulative |
| 4 | `2026-05-13-ui-jts-theme-overhaul-design.md` | v5 JTS overhaul |
| 5 | `2026-05-14-session-handoff-v5.md` | v5 cumulative |
| 6 | **`2026-05-14-import-export-ux-design.md`** + plan | **v6 this session** |
| 7 | **This doc** | **v6 cumulative** |

---

*End of handoff.*
```

- [ ] **Step 7.4: Commit Phase 7**

```bash
git add docs/superpowers/specs/2026-05-15-session-handoff-v6.md
git commit -m "$(cat <<'EOF'
chore: handoff doc v6 — Import+Export UX session summary

Phase 7/7 — final wrap-up of Import+Export UX refresh session.

Cumulative summary of v6 changes for next session pickup:
- Import + Export core UX refresh (file chip, banner, history,
  Indonesian formats)
- R1 windnd drag-and-drop
- R2 smart filename detection
- R3 conflict resolution preview
- R4 shared ProgressModal component
- R5 folder memory (Import + Export)
- R6 bulk import multi-week
- R7 Export preview read-only
- R8 save destination dropdown

116 tests passing throughout 7-commit sequence (was 98 at v5).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 7.5: Verify final state**

```bash
git log --oneline -10
git status
git rev-list --count origin/v5..HEAD
```

Expected:
- 9 commits ahead of origin/v5 (spec + plan + 7 phases)
- Clean working tree

---

## Definition of Done

- [ ] DB: `export_history` table + DDL + 3 new repo modules / functions
- [ ] Helper modules: `filename_parser.py`, refactored `report_filler.py`
- [ ] Import screen: file chip + banner + 3-button chip + history + Indonesian range + R3/R5/R6
- [ ] Export screen: banner + file chip + dry-run preview + result strip + history + filename preview + R2/R5/R7/R8
- [ ] Shared: ProgressModal component, windnd drag-drop integration
- [ ] requirements.txt + HR-Absensi.spec updated for windnd
- [ ] 116 tests passing (98 baseline + 18 new)
- [ ] 7 separated commits for reviewability
- [ ] Handoff doc v6 written
- [ ] All hardcoded hex literals in code follow existing one-off convention (no new "raw" tokens)

---

## Notes for the Implementing Engineer

- **NO `git push`.** User authorizes manually. Stay local. After 7 commits, branch is ahead of origin/v5 — user pushes when ready.
- **`.exe` may be running.** Build only at end of plan (Task 7 or after). If `pyinstaller --clean` hits PermissionError, ask user to close instance.
- **Phase 1 + 3 + 4 + 5 use strict TDD:** write test, run (FAIL), implement, run (PASS), commit. Phase 2 + 6 are UI changes — pytest regression check + smoke test is the gate.
- **Read existing files before refactoring.** Especially `import_screen.py` and `export.py` — they have existing logic that must be preserved (parse + commit, fill matching). Refactor by restructuring, not rewriting.
- **CTk gotchas (from prior session):**
  - `CTkLabel` doesn't accept `padx`/`pady` in constructor — use `.pack(padx=..., pady=...)`
  - `CTkFrame` doesn't support `border_style="dashed"`
  - `style.configure()` for ttk doesn't affect CTk widgets
  - For multi-binding on CTk widgets (Enter/Leave), use `add="+"` so handlers chain
- **windnd is Windows-only** — OK for this app. Wrap with try/except for graceful degradation.
- **If a step references "around line X"** and you can't find it: use Grep tool with a unique snippet.

---

*End of plan.*
