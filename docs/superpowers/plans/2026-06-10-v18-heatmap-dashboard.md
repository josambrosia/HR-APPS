# Heatmap Kehadiran (v18) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) tracking. TDD: write failing test → run (fail) → implement → run (pass) → commit.

**Goal:** A month-grid attendance heatmap — interactive (browser, served on `127.0.0.1`) + a landscape print report — colour-coding each employee's day-by-day status.

**Architecture:** Pure status logic in `src/core/heatmap.py`; data builder crosses active employees × month dates; a loopback `http.server` renders Jinja2 templates (dashboard + print) opened in the browser from a sidebar launcher. No `attendance_records` schema change; one new setting (`late_tolerance_min`).

**Tech Stack:** Python 3.x, stdlib `http.server` + threading, Jinja2, customtkinter, SQLite, pytest. Spec: `docs/superpowers/specs/2026-06-10-v18-heatmap-dashboard-design.md`.

**Baseline:** 323 tests green on v17 (`02d4bb4`). Run from worktree root:
`../../../.venv/Scripts/python.exe -m pytest -q`

## Verified signatures (do not guess)
- `open_html_in_browser(html_path: Path) -> Tuple[bool,str]` (browser_launcher.py:39) — Popen([exe, str(html_path)]).
- `holiday_dates_in_month(conn, year_month) -> set` (db/holidays.py:21).
- `excluded_employee_ids(conn, year_month) -> set` (db/outlier.py:15).
- `list_employees(conn, include_inactive=False)` → active rows `ORDER BY nama` (db/employees.py:43).
- `read_severe_lateness_threshold(conn) -> int` (db/settings.py) — pattern to mirror.
- `effective_attendance(row, *, schedule_start, lupa_penalty_min)` (reason_mapper.py:55) — NOT used by the heatmap (cell_status is independent).
- Jinja2: `Environment(FileSystemLoader(str(TEMPLATES_DIR)), autoescape=True)`, templates in `src/reports/templates/`.
- `REASON_CATEGORIES`, `COACHING_EXCLUDED` in config.py; `read_late_tolerance` & `severe_lateness_threshold_min` (v17).

---

### Task 0: Green baseline
- [ ] Run `../../../.venv/Scripts/python.exe -m pytest -q` → expect 323 passed. STOP if not.

---

### Task 1: Config constants
**Files:** Modify `src/config.py`; Test `tests/test_config_heatmap.py`

- [ ] **Step 1 — failing test**
```python
# tests/test_config_heatmap.py
from src import config

def test_default_late_tolerance():
    assert config.DEFAULT_LATE_TOLERANCE_MIN == 12

def test_heatmap_dinas_reasons():
    assert config.HEATMAP_DINAS_REASONS == (
        "tugas_lapangan", "tugas_paparan", "tugas_belajar", "terlambat_kerja")
    for r in config.HEATMAP_DINAS_REASONS:
        assert r in config.REASON_CATEGORIES

def test_coaching_excluded_unchanged():
    # Heatmap green group is broader than coaching; coaching set stays 3.
    assert config.COACHING_EXCLUDED == ("tugas_lapangan", "tugas_paparan", "terlambat_kerja")
```
- [ ] **Step 2** Run `pytest tests/test_config_heatmap.py -q` → FAIL (AttributeError).
- [ ] **Step 3 — implement** in `src/config.py` near `DEFAULT_SEVERE_LATENESS_THRESHOLD_MIN`:
```python
DEFAULT_LATE_TOLERANCE_MIN = 12

# Heatmap colour grouping — reasons shown GREEN ("Dinas") on the attendance
# heatmap. Deliberately BROADER than COACHING_EXCLUDED (adds tugas_belajar):
# this is a presentation choice and does NOT change coaching/dashboard logic.
HEATMAP_DINAS_REASONS = (
    "tugas_lapangan", "tugas_paparan", "tugas_belajar", "terlambat_kerja",
)
```
- [ ] **Step 4** Run → PASS.
- [ ] **Step 5** `git add src/config.py tests/test_config_heatmap.py && git commit -m "feat(v18): config constants for heatmap (late tolerance + dinas reasons)"`

---

### Task 2: Schema default setting
**Files:** Modify `src/db/schema.py` (`DEFAULT_SETTINGS`); Test `tests/test_schema_late_tolerance.py`

- [ ] **Step 1**
```python
# tests/test_schema_late_tolerance.py
from src.db.schema import init_db
from src.db.connection import get_connection
from src.db.settings import get_setting

def test_late_tolerance_seeded(temp_db_path):
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        assert get_setting(conn, "late_tolerance_min") == "12"
```
- [ ] **Step 2** Run → FAIL (None != "12").
- [ ] **Step 3** Add to `DEFAULT_SETTINGS` dict in `src/db/schema.py`: `"late_tolerance_min": "12",`
- [ ] **Step 4** Run → PASS.
- [ ] **Step 5** commit `feat(v18): seed late_tolerance_min default setting`

---

### Task 3: Settings read helper
**Files:** Modify `src/db/settings.py`; Test `tests/test_settings_read_late_tolerance.py`

- [ ] **Step 1**
```python
# tests/test_settings_read_late_tolerance.py
from src.db.schema import init_db
from src.db.connection import get_connection
from src.db.settings import set_setting, read_late_tolerance

def test_reads_int(temp_db_path):
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        set_setting(conn, "late_tolerance_min", "20")
        assert read_late_tolerance(conn) == 20

def test_fallback(temp_db_path):
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        set_setting(conn, "late_tolerance_min", "bad")
        assert read_late_tolerance(conn) == 12
```
- [ ] **Step 2** Run → FAIL (ImportError).
- [ ] **Step 3** In `src/db/settings.py` add import `from src.config import DEFAULT_LATE_TOLERANCE_MIN` and:
```python
def read_late_tolerance(conn) -> int:
    raw = get_setting(conn, "late_tolerance_min",
                      default=str(DEFAULT_LATE_TOLERANCE_MIN))
    try:
        return int(raw)
    except (TypeError, ValueError):
        return DEFAULT_LATE_TOLERANCE_MIN
```
- [ ] **Step 4** Run → PASS.
- [ ] **Step 5** commit `feat(v18): read_late_tolerance helper`

---

### Task 4: Core status logic — `cell_status` + dicts
**Files:** Create `src/core/heatmap.py`; Test `tests/test_heatmap_cell_status.py`

- [ ] **Step 1 — failing test** (the authoritative behaviour table)
```python
# tests/test_heatmap_cell_status.py
from src.core.heatmap import cell_status, STATUS_COLORS, STATUS_CODES, STATUS_LABELS

def row(**kw):
    base = dict(tipe="Hari Kerja", masuk="08:00", keluar="16:00",
                terlambat_menit=0, reason_category=None)
    base.update(kw); return base

def cs(r, **kw):
    opts = dict(tolerance=12, severe=60, is_weekend=False, is_holiday=False)
    opts.update(kw); return cell_status(r, **opts)

def test_libur_weekend_holiday():
    assert cs(None, is_weekend=True) == "libur"
    assert cs(None, is_holiday=True) == "libur"
    assert cs(row(tipe="Hari Libur")) == "libur"

def test_nodata():
    assert cs(None) == "nodata"           # working day, no row

def test_lateness_tiers():
    assert cs(row(terlambat_menit=12)) == "hadir"
    assert cs(row(terlambat_menit=13)) == "sedang"
    assert cs(row(terlambat_menit=59)) == "sedang"
    assert cs(row(terlambat_menit=60)) == "parah"
    assert cs(row(terlambat_menit=None)) == "hadir"   # NULL -> 0

def test_reason_overrides_lateness():
    assert cs(row(terlambat_menit=90, reason_category="terlambat_kerja")) == "dinas"
    assert cs(row(reason_category="tugas_belajar")) == "dinas"
    assert cs(row(reason_category="izin_sakit")) == "sakit"
    assert cs(row(reason_category="cuti")) == "cuti"
    assert cs(row(masuk=None, reason_category="lupa_absen_pulang")) == "lupa"
    assert cs(row(masuk=None, reason_category="na")) == "na"

def test_terlambat_lain_falls_through():
    # not a leave reason -> shown by lateness magnitude
    assert cs(row(terlambat_menit=30, reason_category="terlambat_lain")) == "sedang"
    assert cs(row(terlambat_menit=80, reason_category="terlambat_lain")) == "parah"

def test_absen_tanpa_alasan():
    assert cs(row(masuk=None, reason_category=None)) == "mangkir"

def test_dicts_cover_all_statuses():
    for k in ("hadir","dinas","sedang","parah","sakit","cuti","lupa","mangkir","na","libur","nodata"):
        assert k in STATUS_COLORS and k in STATUS_CODES and k in STATUS_LABELS
```
- [ ] **Step 2** Run → FAIL (module missing).
- [ ] **Step 3 — implement** `src/core/heatmap.py`:
```python
"""Pure presentation logic for the attendance heatmap. cell_status() maps one
(employee, date) to a status key; the dicts give colour/code/label. Independent
of effective_attendance() (which is for export number adjustment) — the
reason-over-lateness precedence reproduces the same justified-late behaviour."""
from src.config import HEATMAP_DINAS_REASONS

# status_key -> hex / code / human label
STATUS_COLORS = {
    "hadir": "#10B981", "dinas": "#047857", "sedang": "#EC4899",
    "parah": "#BE185D", "sakit": "#22D3EE", "cuti": "#A855F7",
    "lupa": "#EAB308", "mangkir": "#DC2626", "na": "#DC2626",
    "libur": "#FFFFFF", "nodata": "#9CA3AF",
}
STATUS_CODES = {
    "hadir": "H", "dinas": "D", "sedang": "TR", "parah": "TB", "sakit": "S",
    "cuti": "C", "lupa": "LA", "mangkir": "X", "na": "NA", "libur": "·",
    "nodata": "–",
}
STATUS_LABELS = {
    "hadir": "Hadir tepat waktu",
    "dinas": "Dinas (lapangan/paparan/belajar/terlambat dengan alasan)",
    "sedang": "Terlambat Ringan", "parah": "Terlambat Berat",
    "sakit": "Izin Sakit", "cuti": "Cuti", "lupa": "Lupa absen",
    "mangkir": "Absen Tanpa Alasan", "na": "NA / belum ada kabar",
    "libur": "Libur / weekend", "nodata": "Belum ada data",
}
# statuses that count toward HK (hari kerja dihadiri)
HK_STATUSES = ("hadir", "sedang", "parah", "dinas", "lupa")
# leave/justified reasons whose colour overrides lateness (terlambat_lain NOT here)
_LEAVE_REASON_STATUS = {
    "izin_sakit": "sakit", "cuti": "cuti",
    "lupa_absen_datang": "lupa", "lupa_absen_pulang": "lupa",
    "na": "na", "libur": "libur",
}


def cell_status(row, *, tolerance, severe, is_weekend, is_holiday):
    """row is a dict-like attendance record or None. Returns a status key."""
    # 1. Libur
    if is_weekend or is_holiday or (row is not None and row["tipe"] == "Hari Libur"):
        return "libur"
    # 2. No data
    if row is None:
        return "nodata"
    reason = row["reason_category"]
    # 3. Leave/justified reason colour wins
    if reason in HEATMAP_DINAS_REASONS:
        return "dinas"
    if reason in _LEAVE_REASON_STATUS:
        return _LEAVE_REASON_STATUS[reason]
    # (terlambat_lain falls through to lateness tiers)
    # 4. Present + lateness tiers
    if row["masuk"]:
        late = row["terlambat_menit"] or 0
        if late <= tolerance:
            return "hadir"
        if late < severe:
            return "sedang"
        return "parah"
    # 5. Hari Kerja, no punch, no reason
    return "mangkir"
```
- [ ] **Step 4** Run → PASS.
- [ ] **Step 5** commit `feat(v18): heatmap cell_status + status dicts`

---

### Task 5: DB query — `list_attendance_matrix`
**Files:** Modify `src/db/attendance.py`; Test `tests/test_attendance_matrix.py`

- [ ] **Step 1**
```python
# tests/test_attendance_matrix.py
from src.db.schema import init_db
from src.db.connection import get_connection
from src.db.employees import upsert_employee
from src.db.attendance import upsert_attendance, list_attendance_matrix

def test_matrix_returns_rows_with_employee(temp_db_path):
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        a = upsert_employee(conn, no_staff="1", nama="ANDI", dept="IT")
        upsert_attendance(conn, employee_id=a, tanggal="2026-05-04", hari="Senin",
                          tipe="Hari Kerja", jadwal="08.00 - 16.00", masuk="09:15",
                          keluar="16:30", kerja_jam=None, lembur_jam=None,
                          terlambat_menit=75, has_issue=0, imported_from="W1.xls")
        rows = list_attendance_matrix(conn, "2026-05-01", "2026-05-31")
    assert len(rows) == 1
    r = rows[0]
    assert r["nama"] == "ANDI" and r["dept"] == "IT"
    assert r["tanggal"] == "2026-05-04" and r["terlambat_menit"] == 75
    assert r["reason_category"] is None and r["tipe"] == "Hari Kerja"

def test_matrix_filters_range(temp_db_path):
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        a = upsert_employee(conn, no_staff="1", nama="ANDI", dept="IT")
        for d in ("2026-04-30", "2026-05-15", "2026-06-01"):
            upsert_attendance(conn, employee_id=a, tanggal=d, hari="X",
                              tipe="Hari Kerja", jadwal="", masuk="08:00", keluar="16:00",
                              kerja_jam=None, lembur_jam=None, terlambat_menit=0,
                              has_issue=0, imported_from="W")
        rows = list_attendance_matrix(conn, "2026-05-01", "2026-05-31")
    assert [r["tanggal"] for r in rows] == ["2026-05-15"]
```
- [ ] **Step 2** Run → FAIL (ImportError).
- [ ] **Step 3** Add to `src/db/attendance.py`:
```python
def list_attendance_matrix(conn, start, end):
    """All attendance rows in [start,end] joined with employee, for the heatmap.
    Returns only rows that exist; the renderer fills missing (employee,date)
    cells. Sorted by nama, tanggal."""
    sql = """
        SELECT ar.employee_id, e.nama, e.dept, ar.tanggal, ar.hari, ar.tipe,
               ar.masuk, ar.keluar, ar.terlambat_menit,
               ar.reason_category, ar.reason_detail, ar.has_issue
          FROM attendance_records ar
          JOIN employees e ON ar.employee_id = e.id
         WHERE ar.tanggal BETWEEN ? AND ?
         ORDER BY e.nama ASC, ar.tanggal ASC
    """
    return [dict(r) for r in conn.execute(sql, (start, end)).fetchall()]
```
- [ ] **Step 4** Run → PASS.
- [ ] **Step 5** commit `feat(v18): list_attendance_matrix query`

---

### Task 6: Heatmap context builder
**Files:** Modify `src/core/heatmap.py`; Test `tests/test_heatmap_context.py`

Builds the full render context (active employees × every month date). **Context schema** (consumed by both templates):
```
{ year_month, month_label, prev_month, next_month, days:[1..N],
  weekday_of:{day->0..6}, weekday_labels:["Sn".."Mg"], weeks:[[day|0]*7,...],
  eff_hari_kerja:int, is_empty:bool, legend:[{code,color,label}],
  employees:[ {employee_id,nama,dept, hk:int,
               summary:{H,D,TR,TB,S,C,LA,X (int)},
               cells:{ day -> {status,code,color,text_color,date,
                               masuk,keluar,telat,alasan} } } ] }
```
- [ ] **Step 1 — failing test**
```python
# tests/test_heatmap_context.py
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
```
- [ ] **Step 2** Run → FAIL.
- [ ] **Step 3 — implement** in `src/core/heatmap.py` (add imports at top: `import calendar`, `from datetime import date`, and the DB/helpers). Key logic:
  - Parse `year_month` → year, month; `n_days = calendar.monthrange(y,m)[1]`.
  - `weekday_of[d] = date(y,m,d).weekday()` (Mon=0). weekend = weekday >= 5.
  - `weeks` via `calendar.Calendar(firstweekday=0).monthdayscalendar(y,m)`.
  - `tol = read_late_tolerance(conn)`, `sev = read_severe_lateness_threshold(conn)`.
  - holidays = `holiday_dates_in_month(conn, year_month)`.
  - employees = `list_employees(conn, include_inactive=False)`; if exclude_outliers, drop ids in `excluded_employee_ids(conn, year_month)`.
  - rows = `list_attendance_matrix(conn, f"{ym}-01", f"{ym}-{n_days:02d}")`; index by (employee_id, tanggal).
  - For each employee × day: build the row-or-None, compute `cell_status(...)`, code/color, luminance text colour, detail (masuk/keluar/telat/alasan via `render_alasan_ijin`), tally summary + hk.
  - `eff_hari_kerja` = count of weekdays not in holidays.
  - `is_empty` = no rows at all OR no employees.
  - `month_label` Indonesian month name; prev/next month strings.
  Provide a `_text_color(hex)` luminance helper (>150 → "#0a0a0a" else "#e8e8e8").
- [ ] **Step 4** Run → PASS.
- [ ] **Step 5** commit `feat(v18): build_heatmap_context data builder`

---

### Task 7: Browser launcher supports URLs
**Files:** Modify `src/ui/browser_launcher.py`; Test `tests/test_browser_launcher_url.py`

- [ ] **Step 1**
```python
# tests/test_browser_launcher_url.py
import src.ui.browser_launcher as bl

def test_open_url_passes_url_not_path(monkeypatch):
    captured = {}
    monkeypatch.setattr(bl.shutil, "which", lambda exe: r"C:\fake\chrome.exe")
    monkeypatch.setattr(bl.subprocess, "Popen", lambda args: captured.setdefault("args", args))
    monkeypatch.setattr(bl.sys, "platform", "win32")
    ok, name = bl.open_html_in_browser("http://127.0.0.1:8765/heatmap?month=2026-05")
    assert ok
    assert captured["args"][1] == "http://127.0.0.1:8765/heatmap?month=2026-05"
```
- [ ] **Step 2** Run → FAIL (AttributeError: 'str' has no 'as_uri' / passes path).
- [ ] **Step 3** Generalise `open_html_in_browser(target)` to accept `str | Path`: if `isinstance(target, str) and target.startswith("http")`, use `target` directly as the arg (and `webbrowser.open(target)` in the non-win32 / fallback branches); else keep the existing `Path` behaviour (`str(html_path)` for Popen, `html_path.as_uri()` for webbrowser). Update the type hint to `target: "Path | str"`.
- [ ] **Step 4** Run → PASS. Then full suite to ensure Dashboard print path unaffected: `pytest -q`.
- [ ] **Step 5** commit `feat(v18): open_html_in_browser accepts http URLs`

---

### Task 8: Settings UI — Toleransi Telat
**Files:** Modify `src/ui/screens/settings.py`; Test `tests/test_settings_screen_late_tolerance.py`

- [ ] **Step 1** (mirror the v17 severe-threshold settings test): construct `SettingsScreen`, assert `tol_var` exists, set "20", `_save()`, assert `get_setting == "20"`; and a rejects-out-of-range case (set "1000" → unchanged, `messagebox.showwarning` patched).
- [ ] **Step 2** Run → FAIL.
- [ ] **Step 3** In `_build_general`: read `tol = get_setting(conn, "late_tolerance_min", default="12")`; add a row "Toleransi Telat (menit):" with `self.tol_var = ctk.StringVar(value=tol)` + entry (mirror the Severe Lateness row). In `_save`: validate integer in `[0,999]` (warn+return on fail) BEFORE the connection block; inside it `set_setting(conn, "late_tolerance_min", str(tol))`.
- [ ] **Step 4** Run → PASS; then `pytest -q`.
- [ ] **Step 5** commit `feat(v18): Toleransi Telat setting UI + validation`

---

### Task 9: Jinja2 templates (dashboard + print)
**Files:** Create `src/reports/templates/heatmap.html.j2`, `src/reports/templates/heatmap_print.html.j2`

Implemented from the **validated mockup design** (already approved by the user) made data-driven over the Task-6 context. Implementer (driver) writes these directly.
- **heatmap.html.j2** (dashboard): dark theme; sticky header (title + month nav `‹ {{month_label}} ›` linking `?month={{prev_month}}`/`{{next_month}}` + search input + legend from `ctx.legend`); body = one card per `ctx.employees` (nama/dept + GitHub grid from `ctx.weeks`/`cells` with date+colour + per-cell `data-*` for tooltip + summary + HK); JS for case-insensitive name/dept filter, hover tooltip, click detail; empty-state text when `ctx.is_empty`.
- **heatmap_print.html.j2** (print): light theme, `@page landscape`, `print-color-adjust:exact`; sections gated by `scope` (full/matrix/lampiran): matrix (week-group header, week separators, bold name col, zebra, code cells, HK + per-cat summary, bottom "Hari kerja efektif" note, legend) + appendix (Nama-left, sorted by nama, full-cell rounded status pill, per-employee thick separator + zebra).
- [ ] **Step — verify:** templates load via Jinja2 and render with a Task-6 context without error (covered by the server test in Task 10). Commit with Task 10.

---

### Task 10: Loopback web server
**Files:** Create `src/web/__init__.py`, `src/web/heatmap_server.py`; Test `tests/test_heatmap_server.py`

- [ ] **Step 1 — test**
```python
# tests/test_heatmap_server.py
import urllib.request
from src.db.schema import init_db
from src.db.connection import get_connection
from src.db.employees import upsert_employee
from src.db.attendance import upsert_attendance
import src.web.heatmap_server as hs

def test_server_serves_heatmap(temp_db_path, monkeypatch):
    monkeypatch.setattr(hs, "DB_PATH", temp_db_path)
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        a = upsert_employee(conn, no_staff="1", nama="ANDI", dept="IT")
        upsert_attendance(conn, employee_id=a, tanggal="2026-05-04", hari="Senin",
                          tipe="Hari Kerja", jadwal="", masuk="09:15", keluar="16:30",
                          kerja_jam=None, lembur_jam=None, terlambat_menit=75,
                          has_issue=0, imported_from="W")
    base = hs.ensure_started()
    assert base.startswith("http://127.0.0.1:")
    assert hs.ensure_started() == base  # idempotent
    html = urllib.request.urlopen(base + "/heatmap?month=2026-05", timeout=5).read().decode()
    assert "ANDI" in html and "Heatmap" in html
    pr = urllib.request.urlopen(base + "/heatmap/print?month=2026-05&scope=matrix", timeout=5).read().decode()
    assert pr  # 200, non-empty
```
- [ ] **Step 2** Run → FAIL.
- [ ] **Step 3 — implement** `src/web/heatmap_server.py`: module-level `_server`/`_port`. `ensure_started()` binds `ThreadingHTTPServer(("127.0.0.1", 0), Handler)`, reads `server_address[1]`, starts a daemon `serve_forever` thread, stores state, returns `f"http://127.0.0.1:{port}"`; idempotent. `Handler(BaseHTTPRequestHandler)`: parse path+query; for `/heatmap` and `/heatmap/print` open `get_connection(DB_PATH)`, `build_heatmap_context(...)`, render the matching Jinja2 template (env from `src.reports.templates`), write 200 `text/html`; wrap in try/except → 500 on error; 404 otherwise. Import `DB_PATH` from `src.config`.
- [ ] **Step 4** Run `pytest tests/test_heatmap_server.py -q` → PASS.
- [ ] **Step 5** commit templates + server: `git add src/web src/reports/templates/heatmap*.j2 tests/test_heatmap_server.py && git commit -m "feat(v18): loopback heatmap server + Jinja2 templates"`

---

### Task 11: Heatmap print dialog
**Files:** Create `src/ui/components/heatmap_print_dialog.py`; Test `tests/test_heatmap_print_dialog.py`

- [ ] **Step 1** structural test: dialog constructs (CTkToplevel) with `scope` default "full" and `outlier` default "inc"; exposes the selected values via attributes; a callback receives `(scope, outlier)` on confirm.
- [ ] **Step 2** Run → FAIL.
- [ ] **Step 3** Implement a small `HeatmapPrintDialog(parent, on_confirm)` with two radio groups (Tabel: Full/Matrix/Lampiran; Outlier: Sertakan/Kecualikan) + a "Cetak" button calling `on_confirm(scope, "inc"/"exc")`. (Mirror existing dialog patterns; Esc closes.)
- [ ] **Step 4** Run → PASS.
- [ ] **Step 5** commit `feat(v18): heatmap print dialog (scope + outlier)`

---

### Task 12: Heatmap launcher screen
**Files:** Create `src/ui/screens/heatmap.py`; Test `tests/test_heatmap_screen.py`

- [ ] **Step 1** smoke test: `HeatmapScreen(tk_root)` constructs; has `_open_dashboard` and `_open_print` methods; `_open_print` opens the dialog. (Monkeypatch `ensure_started` + `open_html_in_browser` to avoid real browser/socket.)
- [ ] **Step 2** Run → FAIL.
- [ ] **Step 3** Implement `HeatmapScreen(ctk.CTkFrame)`: header + a note + "🔳 Buka Heatmap di browser" button → `hs.ensure_started()` then `open_html_in_browser(base + "/heatmap?month=" + active_month)`, and "🖨️ Cetak…" button → `HeatmapPrintDialog(self, on_confirm=self._do_print)` where `_do_print` opens `base + f"/heatmap/print?month=...&scope=...&outlier=..."`. Active month from `get_setting(conn, "current_month")`.
- [ ] **Step 4** Run → PASS.
- [ ] **Step 5** commit `feat(v18): heatmap launcher screen`

---

### Task 13: Sidebar + router
**Files:** Modify `src/ui/app.py`; Test `tests/test_app_heatmap_nav.py`

- [ ] **Step 1** test: source contains `"Heatmap"` in the INSIGHT group right after Dashboard; `_show` has a Heatmap branch.
- [ ] **Step 2** Run → FAIL.
- [ ] **Step 3** Add `("⊞", "Heatmap", "Heatmap")` to the INSIGHT nav group after Dashboard; add `_show` branch importing `HeatmapScreen` and gridding it (mirror Dashboard handler).
- [ ] **Step 4** Run → PASS; then `pytest -q`.
- [ ] **Step 5** commit `feat(v18): sidebar entry + router for Heatmap`

---

### Task 14: Changelog + version bump
**Files:** Modify `src/config.py`; Test `tests/test_changelog_v18.py`

- [ ] **Step 1** test: `APP_VERSION == "18.0.0"`; top `APP_CHANGELOG` entry version "18.0.0" with a "feat" mentioning "Heatmap".
- [ ] **Step 2** Run → FAIL.
- [ ] **Step 3** Set `APP_VERSION = "18.0.0"`, `APP_BUILD_DATE = "2026-06-10"`; prepend changelog entry (feat Heatmap dashboard+cetak; feat Toleransi Telat setting).
- [ ] **Step 4** Run → PASS.
- [ ] **Step 5** commit `chore(v18): bump APP_VERSION 18.0.0 + changelog`

---

### Task 15: Full suite green
- [ ] Run `../../../.venv/Scripts/python.exe -m pytest -q` → all pass (323 + new). Fix any regression before release.

---

### Task 16: Build installer (release; push HELD)
- [ ] Confirm `HR-Absensi.exe` not running.
- [ ] `export PATH="/c/Program Files (x86)/Inno Setup 6:$PATH" && ../../../.venv/Scripts/python.exe -m tools.build_installer` → `installer/Output/HR-Absensi-Setup-v18.0.0.exe`.
- [ ] Rotate prod `D:/Gawe/Project X/HR App/dist/HR-Absensi/` (2-level `.bak`/`.bak.old`; **never** touch `data/`).
- [ ] Copy installer → `D:/Gawe/Project X/HR App/Installers/HR-Absensi-Setup-v18.0.0.exe`.
- [ ] **STOP. Do NOT push.** Hand off for user smoke + explicit push authorization.

---

## Self-review
- **Spec coverage:** palette/logic→T4; thresholds/settings→T1-3,T8; query→T5; context→T6; server→T10; templates→T9; dialog→T11; screen→T12; sidebar→T13; browser URL→T7; changelog→T14; release→T16. All covered.
- **Type consistency:** `cell_status(row,*,tolerance,severe,is_weekend,is_holiday)`, `build_heatmap_context(conn,year_month,*,exclude_outliers)`, `list_attendance_matrix(conn,start,end)`, `read_late_tolerance(conn)`, `ensure_started()→str`, status keys consistent across T4/T6/T9/T10.
- **No placeholders:** logic tasks have full code; templates (T9) are large HTML adapted from the approved mockup — produced during execution by the driver, validated by the T10 server render test.
