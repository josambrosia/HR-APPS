# Coaching Threshold — Dynamic per Working Day — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert the Coaching threshold from a hardcoded weekly value to a daily quota that scales by actual working days (distinct `Hari Kerja` dates in the period), with the formula visible in the Dashboard panel and Print PDF.

**Architecture:** New setting key `coaching_threshold_per_day` (default 15 mnt/hari). Idempotent migration converts existing `coaching_threshold_min` (weekly) to daily via integer divide-by-5. New `src/db/holidays.py::working_days_count()` helper computes distinct `Hari Kerja` dates in `[start, end]`. Dashboard `_dynamic_coaching_threshold` returns a `{daily, working_days, effective}` dict consumed by the on-screen panel and the Print template. Coaching menu reads the same key and applies `daily × working_days` for consistency.

**Tech Stack:** Python 3.x, customtkinter, SQLite (sqlite3 stdlib), Jinja2 templates, pytest.

**Spec:** [docs/superpowers/specs/2026-05-15-coaching-threshold-dynamic-design.md](../specs/2026-05-15-coaching-threshold-dynamic-design.md) (commit 159fe5c).

**Baseline tests:** 229 passing. Target after this plan: ~233 passing (4 new tests minimum; existing default-assertion tests are migrated not added).

**Important conventions (from earlier sessions / memory):**
- Tests use the `temp_db_path` fixture from `tests/conftest.py`. Fresh per test.
- UI tests use `tk_root` and `monkeypatch.setattr(<module>, "DB_PATH", temp_db_path)`.
- Settings access via `from src.db.settings import get_setting, set_setting`.
- The project uses CRLF line endings on Windows — git may warn `LF will be replaced by CRLF`. Ignore.
- `pytest -q` is run from the worktree root with `../../../.venv/Scripts/python.exe -m pytest -q` per the memory note. Equivalent on this worktree path: `../../../.venv/Scripts/python.exe -m pytest -q` (the venv lives 3 levels up from `.claude/worktrees/<name>/`).
- No auto-push. Don't push to origin at any task — the user does that explicitly after manual smoke test.

---

## File Structure

**Files modified:**
- `src/config.py` — rename constant, drop unused `DEFAULT_COACHING_THRESHOLD_MINUTES`, add `DEFAULT_COACHING_THRESHOLD_PER_DAY = 15`.
- `src/db/schema.py` — `DEFAULT_SETTINGS` swap + new migration step in `_migrate`.
- `src/db/holidays.py` — append `working_days_count()` helper.
- `src/ui/screens/settings.py` — read/save new key, new label text.
- `src/ui/screens/coaching.py` — read new key, compute effective via `working_days_count`.
- `src/ui/screens/dashboard.py` — rewrite `_dynamic_coaching_threshold` to return dict; add subtitle widget; conditional title/subtitle text; `_do_print` passes dict to renderer.
- `src/reports/html_renderer.py` — `render_dashboard_html` signature change (`threshold: int` → `threshold_info: dict`); pass 3 kwargs to template.
- `src/reports/templates/dashboard.html.j2` — conditional formula on KPI delta + coaching footer.

**Files added: none.** All new tests go into existing test files alongside related cases.

**Test files modified:**
- `tests/test_schema.py` — update default-assertion test; add 4 migration tests.
- `tests/test_settings_repo.py` — update default-assertion test.
- `tests/test_holidays_db.py` — add `working_days_count` tests (4).
- `tests/test_settings_screen.py` — add tests for new label/key save+load.
- `tests/test_html_renderer.py` — extend coaching-section test to assert formula text + fallback.

---

## Task 1 — Setting key migration

**Files:**
- Modify: `src/config.py:55`
- Modify: `src/db/schema.py:86-90, 93-105`
- Modify: `tests/test_schema.py` (lines 17-31 + 4 new tests appended)
- Modify: `tests/test_settings_repo.py:10`

### Step 1: Write the failing default-seeding test (overwrite existing)

Replace the body of `test_init_db_seeds_default_settings` in `tests/test_schema.py` (lines 17-23) so that the assertion targets the new key:

```python
def test_init_db_seeds_default_settings(temp_db_path):
    init_db(temp_db_path)
    with sqlite3.connect(temp_db_path) as conn:
        rows = dict(conn.execute("SELECT key, value FROM settings").fetchall())
    assert rows["schedule_start"] == "08.00"
    assert rows["schedule_end"] == "16.00"
    assert rows["coaching_threshold_per_day"] == "15"
```

The idempotency assertion on line 31 (`cnt == 3`) stays correct: a fresh DB ends with 3 keys (schedule_start, schedule_end, coaching_threshold_per_day).

### Step 2: Append 4 migration tests to `tests/test_schema.py`

Append after the existing `test_migrate_adds_kind_to_legacy_export_history`:

```python
def test_migrate_seeds_threshold_per_day_on_fresh_db(temp_db_path):
    """A brand-new DB has no old key; migration seeds coaching_threshold_per_day = 15."""
    init_db(temp_db_path)
    with sqlite3.connect(temp_db_path) as conn:
        row = conn.execute(
            "SELECT value FROM settings WHERE key = 'coaching_threshold_per_day'"
        ).fetchone()
    assert row is not None
    assert row[0] == "15"


def test_migrate_converts_existing_weekly_threshold(temp_db_path):
    """Existing coaching_threshold_min='60' migrates to coaching_threshold_per_day='12'."""
    with sqlite3.connect(temp_db_path) as conn:
        conn.executescript(
            "CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT);"
        )
        conn.execute(
            "INSERT INTO settings (key, value) VALUES ('coaching_threshold_min', '60')"
        )
        conn.commit()
    init_db(temp_db_path)
    with sqlite3.connect(temp_db_path) as conn:
        per_day = conn.execute(
            "SELECT value FROM settings WHERE key = 'coaching_threshold_per_day'"
        ).fetchone()
        old = conn.execute(
            "SELECT value FROM settings WHERE key = 'coaching_threshold_min'"
        ).fetchone()
    assert per_day[0] == "12"
    assert old[0] == "60"  # orphan preserved, not deleted


def test_migrate_converts_default_75_to_15(temp_db_path):
    """Existing coaching_threshold_min='75' (old default) migrates to '15'."""
    with sqlite3.connect(temp_db_path) as conn:
        conn.executescript(
            "CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT);"
        )
        conn.execute(
            "INSERT INTO settings (key, value) VALUES ('coaching_threshold_min', '75')"
        )
        conn.commit()
    init_db(temp_db_path)
    with sqlite3.connect(temp_db_path) as conn:
        per_day = conn.execute(
            "SELECT value FROM settings WHERE key = 'coaching_threshold_per_day'"
        ).fetchone()
    assert per_day[0] == "15"


def test_migrate_threshold_idempotent(temp_db_path):
    """Second init_db call leaves coaching_threshold_per_day untouched."""
    init_db(temp_db_path)
    # Simulate user changing the value
    with sqlite3.connect(temp_db_path) as conn:
        conn.execute(
            "UPDATE settings SET value = '20' WHERE key = 'coaching_threshold_per_day'"
        )
        conn.commit()
    init_db(temp_db_path)
    with sqlite3.connect(temp_db_path) as conn:
        per_day = conn.execute(
            "SELECT value FROM settings WHERE key = 'coaching_threshold_per_day'"
        ).fetchone()
    assert per_day[0] == "20"
```

### Step 3: Update `tests/test_settings_repo.py:10`

The current line is:
```python
assert get_setting(conn, "coaching_threshold_min") == "75"
```
Replace with:
```python
assert get_setting(conn, "coaching_threshold_per_day") == "15"
```

(Read the file first to confirm the surrounding test name + structure; the assertion line should be the only change.)

### Step 4: Run the failing tests

Run from worktree root:
```
../../../.venv/Scripts/python.exe -m pytest tests/test_schema.py tests/test_settings_repo.py -q
```

Expected: at least 5 failures — the rewritten `test_init_db_seeds_default_settings`, the rewritten `test_settings_repo` assertion, and the 4 new migration tests.

### Step 5: Implement — update `src/config.py:55`

Replace:
```python
DEFAULT_COACHING_THRESHOLD_MINUTES = 75
```
with:
```python
DEFAULT_COACHING_THRESHOLD_PER_DAY = 15
```

Verify no other file imports the old constant name:
```
../../../.venv/Scripts/python.exe -c "import src.config; print(hasattr(src.config, 'DEFAULT_COACHING_THRESHOLD_MINUTES'))"
```
Expected output: `False`.

If grep finds any imports of the old name, update them. (Spec analysis says the constant is unused outside `DEFAULT_SETTINGS` literal — verify before continuing.)

### Step 6: Implement — update `src/db/schema.py` defaults

Replace the `DEFAULT_SETTINGS` block (lines 86-90):

```python
DEFAULT_SETTINGS = {
    "schedule_start": "08.00",
    "schedule_end": "16.00",
    "coaching_threshold_per_day": "15",
}
```

(Removes `coaching_threshold_min`. Adds `coaching_threshold_per_day`.)

### Step 7: Implement — add migration step in `_migrate`

Replace the entire `_migrate` function body (lines 93-105) with:

```python
def _migrate(conn: sqlite3.Connection) -> None:
    """Idempotent column additions and settings-key migrations for pre-existing databases.

    CREATE TABLE IF NOT EXISTS only creates missing tables — it does NOT
    add columns to a table that already exists. For an existing data/hr.db
    the export_history.kind column must be added via ALTER TABLE.

    Also migrates coaching_threshold_min (weekly, default 75) to
    coaching_threshold_per_day (daily, ≈15) by integer divide-by-5.
    """
    cols = {row[1] for row in conn.execute("PRAGMA table_info(export_history)")}
    if "kind" not in cols:
        conn.execute(
            "ALTER TABLE export_history "
            "ADD COLUMN kind TEXT NOT NULL DEFAULT 'fill'"
        )

    # Coaching threshold: weekly → daily (idempotent — only writes if new key absent).
    row = conn.execute(
        "SELECT 1 FROM settings WHERE key = 'coaching_threshold_per_day'"
    ).fetchone()
    if row is None:
        old_row = conn.execute(
            "SELECT value FROM settings WHERE key = 'coaching_threshold_min'"
        ).fetchone()
        new_val = 15
        if old_row is not None:
            try:
                old = int(old_row[0])
                new_val = max(1, round(old / 5))
            except (TypeError, ValueError):
                new_val = 15
        conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?)",
            ("coaching_threshold_per_day", str(new_val)),
        )
```

### Step 8: Run all the touched tests

```
../../../.venv/Scripts/python.exe -m pytest tests/test_schema.py tests/test_settings_repo.py -q
```

Expected: all green. If a test still fails, debug — do **not** edit the test to "match" what the code does. Read the test, read the code, find which is wrong, fix that.

### Step 9: Commit

```bash
git add src/config.py src/db/schema.py tests/test_schema.py tests/test_settings_repo.py
git commit -m "$(cat <<'EOF'
feat(coaching): migrate threshold setting from per-week to per-day

Adds idempotent _migrate step that reads coaching_threshold_min
(default 75 weekly) and writes coaching_threshold_per_day = old/5
(default 15 daily). Old key kept as harmless orphan. config.py
constant renamed to DEFAULT_COACHING_THRESHOLD_PER_DAY = 15.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2 — `working_days_count` helper

**Files:**
- Modify: `src/db/holidays.py` (append helper at the end)
- Modify: `tests/test_holidays_db.py` (append 4 tests)

### Step 1: Write 4 failing tests in `tests/test_holidays_db.py`

Append after the existing tests (use the existing `_emp`, `_att` helpers — already in the file at lines 10-28):

```python
def test_working_days_count_empty_range(temp_db_path):
    from src.db.holidays import working_days_count
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        assert working_days_count(conn, "2026-04-01", "2026-04-07") == 0


def test_working_days_count_only_hari_kerja(temp_db_path):
    """Counts only distinct dates with tipe='Hari Kerja'. Hari Libur and Istirahat excluded."""
    from src.db.holidays import working_days_count
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        emp = _emp(conn, "1", "ANI")
        # 3 Hari Kerja dates (one outside the range, one is Hari Libur, one Istirahat)
        _att(conn, emp, "2026-04-13", tipe="Hari Kerja")          # in range, kerja
        _att(conn, emp, "2026-04-14", tipe="Hari Kerja")          # in range, kerja
        _att(conn, emp, "2026-04-15", tipe="Hari Libur")          # in range, libur
        _att(conn, emp, "2026-04-16", tipe="Istirahat")           # in range, istirahat
        _att(conn, emp, "2026-04-17", tipe="Hari Kerja")          # in range, kerja
        _att(conn, emp, "2026-04-20", tipe="Hari Kerja")          # OUT of range
        assert working_days_count(conn, "2026-04-13", "2026-04-19") == 3


def test_working_days_count_distinct_dates(temp_db_path):
    """Multiple employees on the same date → counted once."""
    from src.db.holidays import working_days_count
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        e1 = _emp(conn, "1", "ANI")
        e2 = _emp(conn, "2", "BUDI")
        _att(conn, e1, "2026-04-13", tipe="Hari Kerja")
        _att(conn, e2, "2026-04-13", tipe="Hari Kerja")
        _att(conn, e1, "2026-04-14", tipe="Hari Kerja")
        assert working_days_count(conn, "2026-04-13", "2026-04-14") == 2


def test_working_days_count_inclusive_bounds(temp_db_path):
    """Date-range filter is BETWEEN — inclusive on both ends."""
    from src.db.holidays import working_days_count
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        emp = _emp(conn, "1", "ANI")
        _att(conn, emp, "2026-04-13", tipe="Hari Kerja")  # start boundary
        _att(conn, emp, "2026-04-17", tipe="Hari Kerja")  # end boundary
        _att(conn, emp, "2026-04-15", tipe="Hari Kerja")  # middle
        assert working_days_count(conn, "2026-04-13", "2026-04-17") == 3
```

### Step 2: Run tests — expected to fail

```
../../../.venv/Scripts/python.exe -m pytest tests/test_holidays_db.py -q
```

Expected: 4 failures with `ImportError: cannot import name 'working_days_count'`.

### Step 3: Implement `working_days_count` in `src/db/holidays.py`

Append at the end of the file (after `restamp_holidays`):

```python
def working_days_count(conn: sqlite3.Connection, start_iso: str, end_iso: str) -> int:
    """Count distinct dates with tipe='Hari Kerja' in [start_iso, end_iso] inclusive.

    Used by the Dashboard coaching panel and the standalone Coaching menu to
    scale the per-day threshold to the actual working days in the period.
    Hari Libur and Istirahat rows are automatically excluded by the tipe filter.
    Returns 0 if no fingerprint data has been imported for the period.
    """
    row = conn.execute(
        "SELECT COUNT(DISTINCT tanggal) FROM attendance_records "
        "WHERE tipe = 'Hari Kerja' AND tanggal BETWEEN ? AND ?",
        (start_iso, end_iso),
    ).fetchone()
    return int(row[0]) if row else 0
```

### Step 4: Run tests — expected to pass

```
../../../.venv/Scripts/python.exe -m pytest tests/test_holidays_db.py -q
```

Expected: all green (including the existing holiday tests — no regression).

### Step 5: Commit

```bash
git add src/db/holidays.py tests/test_holidays_db.py
git commit -m "$(cat <<'EOF'
feat(holidays): add working_days_count helper

Counts distinct dates with tipe='Hari Kerja' in [start, end] inclusive.
Used by the dashboard coaching panel to scale per-day threshold by the
actual working days in the period (so a week with 2 holidays gets a
3-day threshold instead of a flat 5-day one).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3 — Settings UI

**Files:**
- Modify: `src/ui/screens/settings.py:88, 119, 296`
- Modify: `tests/test_settings_screen.py` (append 2 tests + adjust nothing existing)

### Step 1: Write 2 failing screen-level tests

Append to `tests/test_settings_screen.py`:

```python
def test_settings_screen_saves_threshold_per_day(temp_db_path, monkeypatch, tk_root):
    """Edit thr_var and save → coaching_threshold_per_day persists."""
    import src.ui.screens.settings as settings_mod
    monkeypatch.setattr(settings_mod, "DB_PATH", temp_db_path)
    monkeypatch.setattr(settings_mod.messagebox, "showinfo", lambda *a, **k: None)
    init_db(temp_db_path)
    screen = settings_mod.SettingsScreen(tk_root)
    tk_root.update_idletasks()
    screen.thr_var.set("12")
    screen._save()
    with get_connection(temp_db_path) as conn:
        assert get_setting(conn, "coaching_threshold_per_day") == "12"
    screen.destroy()


def test_settings_screen_loads_saved_threshold_per_day(temp_db_path, monkeypatch, tk_root):
    """Pre-seed coaching_threshold_per_day → screen populates thr_var with it."""
    import src.ui.screens.settings as settings_mod
    monkeypatch.setattr(settings_mod, "DB_PATH", temp_db_path)
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        from src.db.settings import set_setting
        set_setting(conn, "coaching_threshold_per_day", "18")
    screen = settings_mod.SettingsScreen(tk_root)
    tk_root.update_idletasks()
    assert screen.thr_var.get() == "18"
    screen.destroy()
```

### Step 2: Run — expected to fail

```
../../../.venv/Scripts/python.exe -m pytest tests/test_settings_screen.py -q
```

Expected: the two new tests fail (Save still writes `coaching_threshold_min`, Load still reads `coaching_threshold_min`).

### Step 3: Update `src/ui/screens/settings.py`

Three changes (lines based on v13 HEAD):

- **Line 88** — change the read:
  ```python
  threshold = get_setting(conn, "coaching_threshold_min", default="75")
  ```
  to:
  ```python
  threshold = get_setting(conn, "coaching_threshold_per_day", default="15")
  ```

- **Line 119** — change the label text:
  ```python
  row2, text="Coaching Threshold (mnt/minggu):",
  ```
  to:
  ```python
  row2, text="Coaching Threshold (mnt/hari):",
  ```

- **Line 296** — change the save:
  ```python
  set_setting(conn, "coaching_threshold_min", self.thr_var.get().strip())
  ```
  to:
  ```python
  set_setting(conn, "coaching_threshold_per_day", self.thr_var.get().strip())
  ```

### Step 4: Run — expected to pass

```
../../../.venv/Scripts/python.exe -m pytest tests/test_settings_screen.py -q
```

Expected: all green.

### Step 5: Commit

```bash
git add src/ui/screens/settings.py tests/test_settings_screen.py
git commit -m "$(cat <<'EOF'
feat(settings): switch coaching threshold to mnt/hari unit

Setting label is now 'Coaching Threshold (mnt/hari):'. Reads and writes
go to coaching_threshold_per_day. Migration (Task 1) handles the
unit conversion of any existing weekly value.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4 — Coaching menu screen

**Files:**
- Modify: `src/ui/screens/coaching.py:8, 13, 38-44, 200-214`

No screen-level tests exist for the Coaching menu; the underlying `list_coaching_for_week` is covered by `tests/test_coaching_db.py` and its signature is unchanged. This task is mechanical and verified by running the full suite + manual smoke.

### Step 1: Update imports and constructor read (lines 8-13 imports, lines 38-44 constructor)

In the existing import block at lines 6-13, add `working_days_count`:

```python
from src.db.coaching import (
    list_coaching_for_week, mark_coached, unmark_coached,
    get_coaching_notes, update_notes,
)
from src.db.connection import get_connection
from src.db.holidays import working_days_count
from src.db.settings import get_setting
```

Replace lines 38-44 (the constructor block that reads `self._threshold`) with:

```python
with get_connection(DB_PATH) as conn:
    self._current_month = get_setting(conn, "current_month") or ""
    daily_raw = get_setting(conn, "coaching_threshold_per_day") or "15"
    try:
        self._daily_threshold = int(daily_raw)
    except ValueError:
        self._daily_threshold = 15
```

### Step 2: Update `_reload` (lines 200-214)

Replace the body of `_reload` (currently lines 200-216) with:

```python
def _reload(self):
    start, end, _num = self._active_range()
    self._row_cache = {}
    for item in self.tree.get_children():
        self.tree.delete(item)

    if not start:
        self._render_stats([])
        return

    with get_connection(DB_PATH) as conn:
        working_days = working_days_count(conn, start, end)
        if working_days == 0:
            self._render_stats([])
            return
        effective = self._daily_threshold * working_days
        raw_rows = list_coaching_for_week(
            conn, week_start=start, week_end=end,
            threshold_minutes=effective,
        )
    rows = [dict(r) for r in raw_rows]
    self._render_stats(rows)

    for r in rows:
        iid = str(r["employee_id"])
        self._row_cache[iid] = r
        is_coached = bool(r["is_coached"])
        status_text = "🟢 SUDAH" if is_coached else "🔴 BELUM"
        tag = "sudah" if is_coached else "belum"
        self.tree.insert(
            "", "end", iid=iid,
            values=(
                r["nama"], r["dept"] or "-",
                f"{r['total_terlambat']} mnt",
                status_text,
            ),
            tags=(tag,),
        )
```

Note: only the very start of the function changed (added `working_days = ...` and an early-return guard). The loop body after `rows = [dict(r) for r in raw_rows]` is identical to current. If a literal patch is preferred, the smaller diff is: between lines 209 (`if not start:` block ends with `return`) and line 210 (`with get_connection(DB_PATH) as conn:`), insert no change yet; replace lines 210-214 to use `working_days_count` and the early-return for `working_days == 0`.

### Step 3: Verify no other references to `self._threshold` in coaching.py

Run from worktree root:
```
../../../.venv/Scripts/python.exe -c "import src.ui.screens.coaching"
```
Expected: no error.

Grep:
```
Grep self._threshold src/ui/screens/coaching.py
```
Expected: zero matches (we renamed to `_daily_threshold`).

### Step 4: Run the coaching DB tests

```
../../../.venv/Scripts/python.exe -m pytest tests/test_coaching_db.py -q
```

Expected: all green (signature of `list_coaching_for_week` is unchanged).

### Step 5: Run the full suite to catch any unexpected regressions

```
../../../.venv/Scripts/python.exe -m pytest -q
```

Expected: still all green up to this point.

### Step 6: Commit

```bash
git add src/ui/screens/coaching.py
git commit -m "$(cat <<'EOF'
feat(coaching-screen): use daily threshold scaled by working days

Reads coaching_threshold_per_day and applies threshold = daily ×
working_days_count(week). Empty data → renders empty stats and skips
the SQL query (avoids surfacing everyone as 'over threshold 0').
Consistent with Dashboard panel's new model.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5 — Dashboard panel (on-screen)

**Files:**
- Modify: `src/ui/screens/dashboard.py` — imports, `__init__` (panel subtitle widget), `_dynamic_coaching_threshold`, `_query`, `_update_data`, `_do_print`.

This is the largest mechanical change but has no unit tests (no dashboard test scaffold exists). Verified by full suite + manual smoke.

### Step 1: Add `working_days_count` import + `get_setting` (if not present)

Open `src/ui/screens/dashboard.py`. Find the existing block of `from src.db.*` and `from src.db.settings import get_setting` imports. Ensure both are imported. If `working_days_count` is not imported, add:

```python
from src.db.holidays import working_days_count
```

(Place it alphabetically alongside other `src.db` imports.)

### Step 2: Find and locate the coaching panel widget creation in `_build_*`

Read the current dashboard.py to find where `self._panel_titles["coaching"]` is created (likely in `_build_panels` or `_build_left_grid`). The pattern is one of:

```python
self._panel_titles["coaching"] = ctk.CTkLabel(coach_frame, text="...", ...)
self._panel_titles["coaching"].pack(...)
```

Right after that, add a sibling subtitle label:

```python
self._panel_subtitles["coaching"] = ctk.CTkLabel(
    coach_frame,
    text="",
    font=FONT_SMALL,
    text_color=COLOR_TEXT_MUTED,
    anchor="w",
    justify="left",
)
self._panel_subtitles["coaching"].pack(anchor="w", padx=SPACE_MD, pady=(0, SPACE_XS))
```

Use the same parent frame and pack/grid style as the existing title. Match the spacing constants already imported by the file (`SPACE_MD`, `SPACE_XS`, etc.).

**Before this step**: add `self._panel_subtitles = {}` to `__init__` next to `self._panel_titles = {}` (the file already has the latter; mirror it).

If the title widget uses `grid` instead of `pack`, mirror that — read the surrounding code carefully and match the layout idiom of the surrounding 5 panels.

### Step 3: Rewrite `_dynamic_coaching_threshold` (lines 345-351)

Replace:

```python
def _dynamic_coaching_threshold(self, start_iso, end_iso):
    from datetime import date
    s = date.fromisoformat(start_iso)
    e = date.fromisoformat(end_iso)
    days = (e - s).days + 1
    weeks = max(1, (days + 6) // 7)
    return 75 * weeks
```

with:

```python
def _dynamic_coaching_threshold(self, start_iso, end_iso):
    """Compute coaching threshold for the period.

    Returns dict {'daily': int, 'working_days': int, 'effective': int}.
    Effective = daily quota × distinct Hari Kerja dates in [start, end].
    """
    with get_connection(DB_PATH) as conn:
        daily_raw = get_setting(conn, "coaching_threshold_per_day", default="15")
        try:
            daily = int(daily_raw)
        except (TypeError, ValueError):
            daily = 15
        working_days = working_days_count(conn, start_iso, end_iso)
    return {
        "daily": daily,
        "working_days": working_days,
        "effective": daily * working_days,
    }
```

### Step 4: Update `_query` (line 400)

Find the line:
```python
threshold = self._dynamic_coaching_threshold(start, end)
```
and change the downstream reference to use `threshold["effective"]`:

```python
threshold_info = self._dynamic_coaching_threshold(start, end)
with get_connection(DB_PATH) as conn:
    data = {
        "ranking": [dict(r) for r in terlambat_ranking(conn, start, end)],
        "top5_late": [dict(r) for r in top_n_terlambat(conn, start, end, 5)],
        "coaching": [dict(r) for r in coaching_flag(conn, start, end, threshold=threshold_info["effective"])],
        "top5_teladan": [dict(r) for r in karyawan_teladan_top_n(conn, start, end, 5)],
        "dept_rows": [dict(r) for r in ranking_departemen(conn, start, end)],
        "day_rows": [dict(r) for r in hari_paling_rawan(conn, start, end)],
        "threshold": threshold_info,
    }
```

`data["threshold"]` now stores the full dict, not a scalar.

### Step 5: Update `_update_data` (line 421-431)

Find:

```python
threshold = data["threshold"]

# KPI updates (just text — labels are reused)
self._kpi_labels["periode"].configure(text=label)
self._kpi_labels["total_terlambat"].configure(text=f"{total_late} mnt")
self._kpi_labels["coaching_count"].configure(text=str(len(data["coaching"])))

# Coaching panel title with dynamic threshold
self._panel_titles["coaching"].configure(
    text=f"⚠ Butuh Coaching (>{threshold} mnt)"
)
```

Replace with:

```python
threshold = data["threshold"]

# KPI updates (just text — labels are reused)
self._kpi_labels["periode"].configure(text=label)
self._kpi_labels["total_terlambat"].configure(text=f"{total_late} mnt")
self._kpi_labels["coaching_count"].configure(text=str(len(data["coaching"])))

# Coaching panel title + subtitle with dynamic threshold
if threshold["working_days"] > 0:
    self._panel_titles["coaching"].configure(
        text=f"⚠ Butuh Coaching (>{threshold['effective']} mnt)"
    )
    self._panel_subtitles["coaching"].configure(
        text=f"{threshold['daily']} mnt/hari × {threshold['working_days']} hari kerja"
    )
else:
    self._panel_titles["coaching"].configure(text="⚠ Butuh Coaching")
    self._panel_subtitles["coaching"].configure(
        text="Belum ada data hari kerja periode ini."
    )
```

### Step 6: Update `_do_print` (line 489-499) to pass the dict

Find:

```python
start, end, label = self._period_range()
dynamic_threshold = self._dynamic_coaching_threshold(start, end)
out_dir = Path(tempfile.gettempdir())
try:
    with get_connection(DB_PATH) as conn:
        html_path = render_dashboard_html(
            conn, period_start=start, period_end=end,
            period_label=label, out_dir=out_dir,
            sections=sections,
            threshold=dynamic_threshold,
        )
```

Replace with:

```python
start, end, label = self._period_range()
threshold_info = self._dynamic_coaching_threshold(start, end)
out_dir = Path(tempfile.gettempdir())
try:
    with get_connection(DB_PATH) as conn:
        html_path = render_dashboard_html(
            conn, period_start=start, period_end=end,
            period_label=label, out_dir=out_dir,
            sections=sections,
            threshold_info=threshold_info,
        )
```

The `threshold_info=` kwarg matches the renderer signature change done in Task 6.

### Step 7: Verify the file imports/compiles

```
../../../.venv/Scripts/python.exe -c "import src.ui.screens.dashboard"
```
Expected: no error.

### Step 8: Run the full test suite

```
../../../.venv/Scripts/python.exe -m pytest -q
```

Expected: still all green up to this point (no dashboard unit tests; this is just a compile-clean check).

### Step 9: Commit

```bash
git add src/ui/screens/dashboard.py
git commit -m "$(cat <<'EOF'
feat(dashboard): scale coaching threshold by working days

_dynamic_coaching_threshold now returns dict {daily, working_days,
effective}. Panel title shows effective number; new subtitle shows
the derivation 'N mnt/hari × M hari kerja'. Empty-data periods show
'Belum ada data hari kerja periode ini.' fallback.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6 — Print PDF renderer + template

**Files:**
- Modify: `src/reports/html_renderer.py` — `render_dashboard_html` signature.
- Modify: `src/reports/templates/dashboard.html.j2` — two conditional blocks.
- Modify: `tests/test_html_renderer.py` — extend coaching-section test.

### Step 1: Write the failing template assertions

Append to `tests/test_html_renderer.py`:

```python
def test_coaching_section_shows_formula_when_working_days_present(temp_db_path, tmp_path):
    """When threshold_info has working_days > 0, the rendered HTML shows the formula."""
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        emp = _add_emp(conn, "1", "ANI", dept="X")
        _add_att(conn, emp, "2026-04-13", "Senin", "08.00", "16.00", 0)
        out = render_dashboard_html(
            conn, period_start="2026-04-13", period_end="2026-04-19",
            period_label="Minggu 3 (2026-04-13 → 2026-04-19)",
            out_dir=tmp_path,
            threshold_info={"daily": 15, "working_days": 3, "effective": 45},
        )
    html = out.read_text(encoding="utf-8")
    # KPI delta uses effective + working days
    assert "&ge; 45 mnt / 3 hari" in html or ">= 45 mnt / 3 hari" in html
    # Coaching panel footer shows the full formula
    assert "Threshold" in html
    assert "45 mnt" in html
    assert "15 mnt/hari" in html
    assert "3 hari kerja" in html


def test_coaching_section_fallback_when_no_working_days(temp_db_path, tmp_path):
    """When threshold_info.working_days == 0, the rendered HTML shows the fallback text."""
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        # No attendance rows seeded — but render should still succeed using threshold_info
        emp = _add_emp(conn, "1", "ANI", dept="X")
        out = render_dashboard_html(
            conn, period_start="2026-04-13", period_end="2026-04-19",
            period_label="Minggu 3", out_dir=tmp_path,
            threshold_info={"daily": 15, "working_days": 0, "effective": 0},
        )
    html = out.read_text(encoding="utf-8")
    assert "Belum ada data hari kerja periode ini." in html
    assert "tanpa data hari kerja" in html
    # Formula MUST NOT appear when working_days == 0
    assert "mnt/hari ×" not in html and "mnt/hari &times;" not in html
```

Also update `test_render_html_contains_key_sections` (line 24-60) to pass a `threshold_info` kwarg so it doesn't break after the signature change. Find line 33-36 in that test:

```python
out = render_dashboard_html(
    conn, period_start="2026-04-01", period_end="2026-04-30",
    period_label="April 2026", out_dir=tmp_path,
)
```

Add a `threshold_info` kwarg with realistic dummy values for the test data:

```python
out = render_dashboard_html(
    conn, period_start="2026-04-01", period_end="2026-04-30",
    period_label="April 2026", out_dir=tmp_path,
    threshold_info={"daily": 15, "working_days": 1, "effective": 15},
)
```

Repeat for `test_ranking_is_mandatory_even_if_section_false` (line 63-77) and any other tests in `test_html_renderer.py` that call `render_dashboard_html` — every call site must pass `threshold_info`. (Grep the file first to enumerate.)

### Step 2: Run — expected to fail

```
../../../.venv/Scripts/python.exe -m pytest tests/test_html_renderer.py -q
```

Expected: failures with `TypeError: render_dashboard_html() got an unexpected keyword argument 'threshold_info'` OR the two new tests fail asserting strings that don't appear in the template.

### Step 3: Update `src/reports/html_renderer.py::render_dashboard_html` signature

Find the function definition (around line 30-50). It currently takes (paraphrased):

```python
def render_dashboard_html(
    conn,
    *,
    period_start,
    period_end,
    period_label,
    out_dir,
    sections=None,
    threshold=None,
):
```

Change `threshold=None` to `threshold_info=None`, and update the internal logic. Find where the current `threshold` is used:

- The existing internal usage typically computes a default if `threshold is None`. Replace that block. Around line 80 (where `coaching = coaching_flag(...)` and the dict args are assembled), replace with:

```python
if threshold_info is None:
    threshold_info = {"daily": 15, "working_days": 0, "effective": 0}
threshold_effective = threshold_info["effective"]
```

- Where the function calls `coaching_flag(conn, ..., threshold=threshold)` (use ripgrep to confirm exact line), change to:

```python
coaching = coaching_flag(conn, period_start, period_end, threshold=threshold_effective)
```

(If the existing code already accepted `threshold` as the scalar and forwarded it to `coaching_flag`, this is a one-line rename.)

- The template render call (around line 99-119) — replace `coaching_threshold=threshold,` with three kwargs:

```python
coaching_threshold_effective=threshold_info["effective"],
coaching_threshold_daily=threshold_info["daily"],
coaching_working_days=threshold_info["working_days"],
```

### Step 4: Update `src/reports/templates/dashboard.html.j2`

Find line 130 (KPI card delta for coaching) — currently:

```jinja
<div class="k violet"><div class="l">Coaching</div><div class="n">{{ kpi.coaching_count }}</div><div class="delta">&ge; {{ coaching_threshold }} min</div></div>
```

Replace the `<div class="delta">` portion with conditional logic:

```jinja
<div class="k violet"><div class="l">Coaching</div><div class="n">{{ kpi.coaching_count }}</div><div class="delta">{% if coaching_working_days > 0 %}&ge; {{ coaching_threshold_effective }} mnt / {{ coaching_working_days }} hari{% else %}tanpa data hari kerja{% endif %}</div></div>
```

Find line 169 (coaching panel footer) — currently:

```jinja
<div style="font-size:10px;color:#737373;margin-top:8px">Threshold &ge; {{ coaching_threshold }} menit / periode</div>
```

Replace with:

```jinja
<div style="font-size:10px;color:#737373;margin-top:8px">{% if coaching_working_days > 0 %}Threshold &ge; {{ coaching_threshold_effective }} mnt ({{ coaching_threshold_daily }} mnt/hari &times; {{ coaching_working_days }} hari kerja){% else %}Belum ada data hari kerja periode ini.{% endif %}</div>
```

### Step 5: Run tests — expected to pass

```
../../../.venv/Scripts/python.exe -m pytest tests/test_html_renderer.py -q
```

Expected: all green.

### Step 6: Run the full suite

```
../../../.venv/Scripts/python.exe -m pytest -q
```

Expected: all green. Test count should now be ~233+ (the four migration tests, the four working_days_count tests, the two settings_screen tests, the two new html_renderer tests = +12 net, minus the count is offset by the renamed assertions in the two repo/schema tests that were updated in place, so net new ~ 12).

### Step 7: Commit

```bash
git add src/reports/html_renderer.py src/reports/templates/dashboard.html.j2 tests/test_html_renderer.py
git commit -m "$(cat <<'EOF'
feat(print): show dynamic coaching threshold formula

render_dashboard_html now takes threshold_info dict (daily,
working_days, effective). Template KPI delta shows '≥ X mnt / N hari'
when data present, 'tanpa data hari kerja' otherwise. Coaching panel
footer shows the full formula 'Threshold ≥ X mnt (Y mnt/hari × N
hari kerja)' or the no-data fallback.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 7 — Verification & smoke checklist

**Files:** none changed; this task is verification only.

### Step 1: Full pytest pass

Run:
```
../../../.venv/Scripts/python.exe -m pytest -q
```

Expected: all green. Count should be 229 baseline + ~12 new = ~241 passing. (If the actual delta is different, that's fine — what matters is **0 failures** and **0 errors** and that the count is **higher than 229**, not lower.)

If any test fails, **do not commit anything else** — debug, fix the root cause (not the test), re-run.

### Step 2: Static-import smoke (catches typos that don't run at test time)

```
../../../.venv/Scripts/python.exe -c "import src.ui.app; import src.ui.screens.dashboard; import src.ui.screens.coaching; import src.ui.screens.settings; import src.reports.html_renderer; print('imports ok')"
```

Expected: `imports ok`.

### Step 3: Manual smoke checklist (recorded here for the user — NOT executed by subagents)

These cannot be unit-tested in this codebase (no UI test infrastructure beyond construct-and-destroy). The user runs these post-deploy by hand:

1. **Dashboard, Mingguan period (data present):** open the Dashboard. Switch through several Mingguan periods. Verify the coaching panel title shows `⚠ Butuh Coaching (>X mnt)` and the small subtitle below shows `Y mnt/hari × Z hari kerja`. Confirm X = Y * Z for each period.

2. **Settings → Change daily quota:** open Settings, change `Coaching Threshold (mnt/hari)` from default 15 to e.g. 12. Save. Return to Dashboard. Confirm subtitle now shows `12 mnt/hari × Z hari kerja` and title shows `>12*Z mnt`. Confirm the standalone Coaching menu's listed employees also reflect the new daily quota (compare set of names with the Dashboard's coaching panel — should be identical for the same week).

3. **Hari Libur effect:** open Hari Libur menu, mark a date in the current Mingguan period as a holiday. Return to Dashboard. Confirm working_days subtitle dropped by 1 and effective threshold dropped accordingly.

4. **No data fallback:** pick a Mingguan period that has NO fingerprint data imported (e.g., a future week). Confirm Dashboard panel title says `⚠ Butuh Coaching` (no number) and subtitle says `Belum ada data hari kerja periode ini.`.

5. **Print PDF (data present):** print the Dashboard for a Mingguan period. Confirm KPI Coaching card delta says `≥ X mnt / Z hari` and the Butuh Coaching section footer says `Threshold ≥ X mnt (Y mnt/hari × Z hari kerja)`.

6. **Print PDF (no data):** print for an empty period. Confirm KPI delta says `tanpa data hari kerja` and the panel footer says `Belum ada data hari kerja periode ini.`.

7. **Migration sanity (one-time):** before the first launch with the new build, the user's existing `data/hr.db` has `coaching_threshold_min = "75"` (or whatever the user set). After first launch, the new key `coaching_threshold_per_day` should be `"15"` (or `old/5`). Verify via Settings — opening it should show `Coaching Threshold (mnt/hari): 15` (or whatever migrated value).

### Step 4: Final verification commit (optional)

No code changes — this task is purely verification. If a small doc/note update is needed (e.g., updating `version_state.md` is **not** in scope of this plan; user owns memory updates), skip. Otherwise: nothing to commit.

---

## Self-review notes (post-write, fix-inline)

- **Spec coverage:** All 7 sections of the spec (data model, working_days helper, dashboard, print, coaching menu, settings UI, tests) have a corresponding task. ✓
- **Type consistency:** `threshold_info` (dict) is the param name in `render_dashboard_html`, in `_do_print`'s call site, and in the dashboard's `_dynamic_coaching_threshold` return type. The dict shape `{daily, working_days, effective}` is consistent across all 5 references. ✓
- **Test commands:** all reference `../../../.venv/Scripts/python.exe -m pytest -q` per memory. ✓
- **Placeholder scan:** no TBD/TODO/"fill in details"; every code step has concrete code. The only "verify line numbers before editing" hints are about the live file state (line numbers can drift between v13 HEAD and execution time) — that's a precaution, not a placeholder. ✓
- **Migration heuristic:** explicit (`max(1, round(old/5))`), with fallback to `15` if old key absent/unparseable. ✓
- **Idempotency:** migration writes ONLY if new key absent. Verified in Task 1 test (`test_migrate_threshold_idempotent`). ✓

---

## Execution

Per `memory/execution_preference.md` the user always picks subagent-driven. After this plan is committed, the parent should immediately invoke `superpowers:subagent-driven-development` without asking the "two options" question.
