# Coaching Threshold — Dynamic per Working Day

**Date:** 2026-05-15
**Status:** Design approved, awaiting implementation plan
**Scope:** Dashboard screen + Print PDF + Coaching menu + Settings

## Problem

Today the coaching threshold is hardcoded as **75 menit per Mingguan period** in three places:

1. Dashboard panel title: `⚠ Butuh Coaching (>75 mnt)` regardless of how many actual working days the week contains.
2. Print PDF KPI card: `≥ 75 min`.
3. Print PDF coaching panel footer: `Threshold ≥ 75 menit / periode`.

This produces two real bugs and one wording problem:

- **Bug A — Dashboard ignores the user's setting.** `src/ui/screens/dashboard.py::_dynamic_coaching_threshold` returns `75 * weeks` with a **literal** `75`. The Settings field `coaching_threshold_min` (default 75) is wired only to the standalone Coaching menu and Print, not to the Dashboard panel. Changing it to 60 has no visible effect on the Dashboard.
- **Bug B — Threshold scales by calendar weeks, not actual working days.** A Mingguan period with only 3 working days (e.g., 2 holidays inside the week) still uses 75. The threshold should drop proportionally — e.g., 45 if the daily quota is 15.
- **Wording problem — The text doesn't tell the user how the number was derived.** When the threshold becomes dynamic, "(>75 mnt)" alone is opaque. The wording must explain `daily × working_days`.

The user's mental model is **daily quota × actual working days**, with the user setting the daily quota directly (e.g., 15 menit/hari → 45 menit threshold for a 3-day week).

## Goals

- The Settings value represents a daily coaching quota in minutes (`mnt/hari`).
- The Dashboard and Print PDF compute `effective_threshold = daily × working_days_in_period`, where `working_days` is **distinct dates with `attendance_records.tipe = 'Hari Kerja'`** in the period.
- Wording on Dashboard panel + Print PDF shows the effective number AND the derivation formula (small subtitle).
- The standalone Coaching menu uses the same effective-threshold calculation for consistency (its rows otherwise wouldn't match the Dashboard panel).
- Existing user data migrates safely: old `coaching_threshold_min` (weekly, default 75) is converted to `coaching_threshold_per_day` (daily, ≈15) once on next app launch.

## Non-goals

- Showing the Coaching panel in Bulanan period (stays hidden as today).
- Adding a threshold display to the Coaching menu header (out of scope).
- Per-employee threshold overrides.
- Backfilling historical coaching session records based on the new threshold.
- A migration banner / notice (single-user app — user is informed via this spec).

## Design

### 1. Data model & migration

- **New setting key:** `coaching_threshold_per_day` (string, integer minutes, default `"15"`).
- **Update `src/db/schema.py`:**
  - `DEFAULT_SETTINGS` gains `"coaching_threshold_per_day": "15"`.
  - `DEFAULT_SETTINGS["coaching_threshold_min"]` is **removed** (so it's not re-seeded on fresh DBs).
  - `_migrate(conn)` gains a settings-migration step (idempotent):
    1. If `coaching_threshold_per_day` already exists in `settings`, return (no-op).
    2. Else, read `coaching_threshold_min` value. If present and parseable as int, compute `new = max(1, round(int(old) / 5))`. If absent or unparseable, `new = 15`.
    3. `INSERT INTO settings (key, value) VALUES ('coaching_threshold_per_day', ?)`.
  - The old `coaching_threshold_min` row is **not** deleted (harmless orphan; no code reads it after the migration).
- **`src/config.py`:** rename `DEFAULT_COACHING_THRESHOLD_MINUTES = 75` to `DEFAULT_COACHING_THRESHOLD_PER_DAY = 15`. This constant is a fallback only — actual default comes from the DB. Verify no callers still reference the old name (the only current callers are `src/db/schema.py` indirectly via `DEFAULT_SETTINGS` literal; update both).

### 2. Working-days helper

In `src/db/holidays.py` (placement chosen because the module already owns workday/holiday concepts and this is pure SQL on `attendance_records`):

```python
def working_days_count(conn: sqlite3.Connection, start_iso: str, end_iso: str) -> int:
    """Count distinct dates with tipe='Hari Kerja' in [start_iso, end_iso] inclusive."""
    row = conn.execute(
        "SELECT COUNT(DISTINCT tanggal) FROM attendance_records "
        "WHERE tipe = 'Hari Kerja' AND tanggal BETWEEN ? AND ?",
        (start_iso, end_iso),
    ).fetchone()
    return int(row[0]) if row else 0
```

Properties:

- Returns `0` if no fingerprint data has been imported for the period.
- Outlier exclusions are **not** applied — working days is a calendar/period property, not per-employee.
- Holiday-stamped rows (`tipe='Hari Libur'`) are automatically excluded by the `tipe = 'Hari Kerja'` filter.

### 3. Dashboard (on-screen panel) — `src/ui/screens/dashboard.py`

- Rewrite `_dynamic_coaching_threshold(self, start_iso, end_iso)` (line 345) to return a dict:

  ```python
  def _dynamic_coaching_threshold(self, start_iso, end_iso):
      with get_connection(DB_PATH) as conn:
          daily_raw = get_setting(conn, "coaching_threshold_per_day", default="15")
          try:
              daily = int(daily_raw)
          except (ValueError, TypeError):
              daily = 15
          working_days = working_days_count(conn, start_iso, end_iso)
      return {
          "daily": daily,
          "working_days": working_days,
          "effective": daily * working_days,
      }
  ```

- `_query` (line 394) calls it once per period; the dict goes into `data["threshold"]` (replaces the scalar).
- `coaching_flag(conn, start, end, threshold=threshold_dict["effective"])` (line 405) — same downstream signature, just pass the `effective` value.
- **New widget:** a subtitle `CTkLabel` is created in the coaching panel header during `_build_*` (same time `_panel_titles["coaching"]` is created), kept under `self._panel_subtitles["coaching"]`. Font `FONT_SMALL`, color `COLOR_TEXT_MUTED`.
- **Update in `_update_data` (line 414):** replace line 430's panel-title text with conditional logic:

  ```python
  t = data["threshold"]
  if t["working_days"] > 0:
      self._panel_titles["coaching"].configure(
          text=f"⚠ Butuh Coaching (>{t['effective']} mnt)"
      )
      self._panel_subtitles["coaching"].configure(
          text=f"{t['daily']} mnt/hari × {t['working_days']} hari kerja"
      )
  else:
      self._panel_titles["coaching"].configure(text="⚠ Butuh Coaching")
      self._panel_subtitles["coaching"].configure(
          text="Belum ada data hari kerja periode ini."
      )
  ```

- **Bulanan unchanged:** the panel is hidden by `_apply_layout` (line 380). The threshold dict is still computed in `_query` (cheap — one COUNT query), but the panel widgets aren't drawn.

### 4. Print PDF — `src/reports/html_renderer.py` + `dashboard.html.j2`

**`src/reports/html_renderer.py::render_dashboard_html` signature change (line 114):**

- Replace the single `threshold: int` parameter and `coaching_threshold=threshold` template kwarg with three kwargs derived from the dict:
  - `coaching_threshold_effective` (int)
  - `coaching_threshold_daily` (int)
  - `coaching_working_days` (int)
- The function's `threshold` parameter is replaced by a `threshold_info: dict` parameter (matching the dict shape from `_dynamic_coaching_threshold`).
- Caller in `dashboard.py::_do_print` (line 490) reuses the rewritten `_dynamic_coaching_threshold` and passes the dict.
- The single test caller in `tests/test_html_renderer.py` is updated to construct an equivalent dict.

**`src/reports/templates/dashboard.html.j2`:**

- **Line 130 (KPI card delta):**
  ```jinja
  <div class="delta">
    {% if coaching_working_days > 0 %}
      &ge; {{ coaching_threshold_effective }} mnt / {{ coaching_working_days }} hari
    {% else %}
      tanpa data hari kerja
    {% endif %}
  </div>
  ```
- **Line 169 (coaching panel footer):**
  ```jinja
  <div style="font-size:10px;color:#737373;margin-top:8px">
    {% if coaching_working_days > 0 %}
      Threshold &ge; {{ coaching_threshold_effective }} mnt
      ({{ coaching_threshold_daily }} mnt/hari &times; {{ coaching_working_days }} hari kerja)
    {% else %}
      Belum ada data hari kerja periode ini.
    {% endif %}
  </div>
  ```

No other template changes — the coaching pill list (`{% for r in coaching %}`) is already driven by the filtered `coaching` rows from the SQL.

### 5. Coaching menu — `src/ui/screens/coaching.py`

Mandatory for consistency: if the Dashboard panel uses `daily × working_days` but the Coaching menu still applies a flat threshold, the two views disagree.

- Lines 38-44 currently read `coaching_threshold_min` (with `"75"` fallback) and store as `self._threshold`. Replace with:

  ```python
  with get_connection(DB_PATH) as conn:
      self._current_month = get_setting(conn, "current_month") or ""
      daily_raw = get_setting(conn, "coaching_threshold_per_day") or "15"
      try:
          self._daily_threshold = int(daily_raw)
      except ValueError:
          self._daily_threshold = 15
  ```

- `_reload()` (line 200) now computes effective per the active week:

  ```python
  start, end, _num = self._active_range()
  ...
  with get_connection(DB_PATH) as conn:
      working_days = working_days_count(conn, start, end)
      effective = self._daily_threshold * working_days
      if working_days == 0:
          self._render_stats([])
          # tree already cleared above
          return
      raw_rows = list_coaching_for_week(
          conn, week_start=start, week_end=end,
          threshold_minutes=effective,
      )
  ```

- No header/KPI wording change in this screen — explicit non-goal.

### 6. Settings UI — `src/ui/screens/settings.py`

- **Line 88:** `threshold = get_setting(conn, "coaching_threshold_min", default="75")` → `threshold = get_setting(conn, "coaching_threshold_per_day", default="15")`.
- **Line 119:** label text `"Coaching Threshold (mnt/minggu):"` → `"Coaching Threshold (mnt/hari):"`.
- **Line 296:** `set_setting(conn, "coaching_threshold_min", ...)` → `set_setting(conn, "coaching_threshold_per_day", ...)`.
- Input field, validation, Save button remain identical.

### 7. Tests

**Existing tests requiring update:**

- `tests/test_schema.py:23` — change default assertion from `coaching_threshold_min == "75"` to `coaching_threshold_per_day == "15"`.
- `tests/test_settings_repo.py:10` — same.
- `tests/test_coaching_db.py` — verify no test relies on the flat 75 default semantically; `list_coaching_for_week`'s signature (`threshold_minutes`) is unchanged so call sites stay valid.

**New tests:**

- `tests/test_schema.py` — migration tests:
  - Fresh DB → seeds `coaching_threshold_per_day = "15"`, no `coaching_threshold_min` row.
  - Pre-seed old DB with `coaching_threshold_min = "60"` (simulating an existing user) → after `init_db()`, `coaching_threshold_per_day == "12"`.
  - Pre-seed `coaching_threshold_min = "75"` → migrates to `"15"`.
  - Migration idempotent: second `init_db()` run leaves `coaching_threshold_per_day` untouched.
  - Old key absent + new key absent → new key written as `"15"`.
- `tests/test_holidays_db.py` — `working_days_count` (added alongside existing holiday tests in the same module):
  - Empty range / no data → 0.
  - Mixed `Hari Kerja` / `Hari Libur` / `Istirahat` rows → counts only Hari Kerja distinct dates.
  - Same date with rows for multiple employees → counted once.
  - Date-range inclusive at both ends.
- `tests/test_html_renderer.py` — extend an existing scenario:
  - `coaching_working_days > 0` case → rendered HTML contains the formula string `"mnt/hari × N hari kerja"` (or `&times;`) and the effective number.
  - `coaching_working_days == 0` case → rendered HTML contains `"Belum ada data hari kerja periode ini."` and does NOT contain the formula.

**Test count expectation:** baseline 229 → ~233 (4+ new tests).

**Manual smoke (post-deploy):**

- Open Dashboard, switch Mingguan periods → panel title + subtitle update on each switch.
- Change setting to 12, save, reload Dashboard → subtitle shows `12 mnt/hari × N hari kerja`, title number = 12 × N.
- Pick a Mingguan period that contains holidays (use Hari Libur menu first) → working_days drops, effective threshold drops accordingly.
- Print PDF (with data) → KPI delta + panel footer both show formula; (without data) → both show fallback text.
- Open Coaching menu → rows match what Dashboard panel shows for the same week.

## Files touched (summary)

| File | Change |
|---|---|
| `src/config.py` | Rename constant `DEFAULT_COACHING_THRESHOLD_MINUTES` → `DEFAULT_COACHING_THRESHOLD_PER_DAY = 15` |
| `src/db/schema.py` | `DEFAULT_SETTINGS` swap; new migration step in `_migrate` |
| `src/db/holidays.py` | New `working_days_count()` helper |
| `src/ui/screens/dashboard.py` | Rewrite `_dynamic_coaching_threshold`; new subtitle widget; conditional title/subtitle in `_update_data`; `_do_print` passes dict |
| `src/ui/screens/coaching.py` | Read daily key; compute effective with `working_days_count`; guard `working_days == 0` |
| `src/ui/screens/settings.py` | New key, new label, save to new key |
| `src/reports/html_renderer.py` | Accept `threshold_info` dict; pass 3 kwargs to template |
| `src/reports/templates/dashboard.html.j2` | Two `{% if coaching_working_days > 0 %}` blocks |
| `tests/test_schema.py` | Update default assertion + new migration tests |
| `tests/test_settings_repo.py` | Update default assertion |
| `tests/test_holidays_db.py` | New `working_days_count` tests |
| `tests/test_html_renderer.py` | Formula/fallback assertions |

## Open questions

None — design fully resolved through brainstorm.
