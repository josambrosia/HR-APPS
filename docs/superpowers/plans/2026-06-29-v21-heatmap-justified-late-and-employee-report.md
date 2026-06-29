# v21 — Justified-late fix + Heatmap full-width + Per-employee report — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make "Terlambat dengan alasan" (`terlambat_lain`) count as justified everywhere (Part A), make the heatmap card full-width 1-per-row with distinct libur/nodata colours (Part B), and add a per-employee monthly "Cetak" report (Part C).

**Architecture:** Part A is pure read-time logic — two `src/config.py` tuple additions + one SQL `CASE` — no DB migration, retroactive. Part B edits the Tkinter-canvas heatmap screen + `STATUS_COLORS` (single source for screen & print). Part C adds a Jinja renderer + template reusing `build_heatmap_context`, opened in the browser like the existing heatmap print.

**Tech Stack:** Python 3.13, customtkinter + `tk.Canvas`, SQLite, Jinja2, pytest.

**Branch:** `v21` (forked from `v20.0.1`). Spec: `docs/superpowers/specs/2026-06-29-v21-heatmap-justified-late-and-employee-report-design.md`.

---

## File Structure

- `src/config.py` — MODIFY: add `terlambat_lain` to `COACHING_EXCLUDED` and `HEATMAP_DINAS_REASONS` (+ comments).
- `src/core/insights.py` — MODIFY: `terlambat_ranking` `tidak_hadir` CASE.
- `src/core/heatmap.py` — MODIFY: `STATUS_COLORS` (libur, nodata).
- `src/ui/screens/heatmap.py` — MODIFY: full-width 1-col layout, hollow-nodata cell, per-employee Cetak button + handler.
- `src/reports/templates/heatmap_print.html.j2` — MODIFY: hollow-nodata cell + legend swatch.
- `src/reports/employee_report.py` — CREATE: `render_employee_report_html`.
- `src/reports/templates/employee_report.html.j2` — CREATE: the report template.
- `tests/test_v21_justified_late.py` — CREATE (Part A).
- `tests/test_v21_heatmap_colors.py` — CREATE (Part B colours).
- `tests/test_employee_report.py` — CREATE (Part C).
- `src/config.py` `APP_VERSION`/`APP_CHANGELOG` + `tests/test_changelog_v20_1.py` rotation — release task.

Test helper pattern (reused from `tests/test_heatmap_print_render.py`):

```python
import os, tempfile
from pathlib import Path
from src.db.schema import init_db
from src.db.connection import get_connection
from src.db.employees import upsert_employee
from src.db.attendance import upsert_attendance, set_reason

def _db():
    fd, p = tempfile.mkstemp(suffix=".db"); os.close(fd); p = Path(p)
    init_db(p)
    return p

def _att(conn, eid, tgl, hari, *, masuk, keluar, telat):
    upsert_attendance(conn, employee_id=eid, tanggal=tgl, hari=hari,
                      tipe="Hari Kerja", jadwal="", masuk=masuk, keluar=keluar,
                      kerja_jam=None, lembur_jam=None, terlambat_menit=telat,
                      has_issue=0, imported_from="W")

def _reason(conn, eid, tgl, cat):
    aid = conn.execute(
        "SELECT id FROM attendance_records WHERE employee_id=? AND tanggal=?",
        (eid, tgl)).fetchone()[0]
    set_reason(conn, attendance_id=aid, category=cat, detail=None)
```

---

# PART A — Justified-late bug fix

### Task A1: `terlambat_lain` is justified (config tuples)

**Files:**
- Modify: `src/config.py` (`COACHING_EXCLUDED`, `HEATMAP_DINAS_REASONS`)
- Test: `tests/test_v21_justified_late.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_v21_justified_late.py` (include the helper block from File Structure at the top), then add:

```python
from src.core.heatmap import cell_status
from src.core.insights import terlambat_ranking, top_n_terlambat
from src.core.reason_mapper import effective_attendance

def _row(**kw):
    base = {"tipe": "Hari Kerja", "reason_category": None,
            "masuk": "08:30", "keluar": "16:30", "terlambat_menit": 30}
    base.update(kw)
    return base

def test_cell_status_terlambat_lain_dinas_with_punch():
    r = _row(reason_category="terlambat_lain")
    assert cell_status(r, tolerance=12, severe=60,
                       is_weekend=False, is_holiday=False) == "dinas"

def test_cell_status_terlambat_lain_dinas_without_punch():
    r = _row(reason_category="terlambat_lain", masuk=None, keluar=None,
             terlambat_menit=None)
    assert cell_status(r, tolerance=12, severe=60,
                       is_weekend=False, is_holiday=False) == "dinas"

def test_effective_attendance_terlambat_lain_zeroed():
    r = _row(reason_category="terlambat_lain")
    eff = effective_attendance(r, schedule_start="08.00", lupa_penalty_min=15)
    assert eff["terlambat_menit"] == 0 and eff["masuk"] == "08:00"

def test_ranking_terlambat_lain_zero_minutes():
    with get_connection(_db()) as conn:
        e = upsert_employee(conn, no_staff="1", nama="ANDI", dept="IT")
        _att(conn, e, "2026-05-04", "Senin", masuk="08:30", keluar="16:30", telat=30)
        _reason(conn, e, "2026-05-04", "terlambat_lain")
        row = terlambat_ranking(conn, "2026-05-01", "2026-05-31")[0]
        top = top_n_terlambat(conn, "2026-05-01", "2026-05-31")
    assert row["total_terlambat"] == 0
    assert row["hari_telat"] == 0
    assert top == []   # zero-minute rows dropped from Top-5
```

- [ ] **Step 2: Run to verify they fail**

Run: `.venv\Scripts\python.exe -m pytest tests/test_v21_justified_late.py -q`
Expected: the four tests FAIL (cell_status returns `"sedang"`, ranking sums 30, effective unchanged).

- [ ] **Step 3: Edit `src/config.py`**

Change `HEATMAP_DINAS_REASONS` (currently lines ~239-241) to add `terlambat_lain`:

```python
# Heatmap colour grouping — reasons shown TEAL ("Dinas") on the attendance
# heatmap. Includes both late-with-reason kinds so the legend label
# "Dinas (…/terlambat dengan alasan)" matches the code.
HEATMAP_DINAS_REASONS = (
    "tugas_lapangan", "tugas_paparan", "tugas_belajar",
    "terlambat_kerja", "terlambat_lain",
)
```

Change `COACHING_EXCLUDED` (currently line ~275) to add `terlambat_lain`:

```python
# Lateness-justified reasons: their lateness is treated as 0 and they are
# excluded from coaching. Work-duty (tugas_*/terlambat_kerja) OR other excused
# lateness (terlambat_lain). Consumed by insights.terlambat_ranking,
# insights.karyawan_teladan, db/coaching.py, reason_mapper.effective_attendance.
COACHING_EXCLUDED = (
    "tugas_lapangan", "tugas_paparan", "terlambat_kerja", "terlambat_lain",
)
```

- [ ] **Step 4: Run to verify pass**

Run: `.venv\Scripts\python.exe -m pytest tests/test_v21_justified_late.py -q`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/config.py tests/test_v21_justified_late.py
git commit -m "fix(v21-A1): terlambat_lain is lateness-justified (config tuples)"
```

### Task A2: a no-punch justified-late row is not counted absent

**Files:**
- Modify: `src/core/insights.py` (`terlambat_ranking` `tidak_hadir` CASE, ~lines 48-52)
- Test: `tests/test_v21_justified_late.py`

- [ ] **Step 1: Add the failing test**

Append to `tests/test_v21_justified_late.py`:

```python
def test_ranking_terlambat_lain_no_punch_not_absent():
    with get_connection(_db()) as conn:
        e = upsert_employee(conn, no_staff="1", nama="ANDI", dept="IT")
        # resolved a missing-scan issue as "Terlambat dengan alasan": present, late
        _att(conn, e, "2026-05-04", "Senin", masuk=None, keluar=None, telat=None)
        _reason(conn, e, "2026-05-04", "terlambat_lain")
        row = terlambat_ranking(conn, "2026-05-01", "2026-05-31")[0]
    assert row["tidak_hadir"] == 0
    assert row["absent_count"] == 0
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_v21_justified_late.py::test_ranking_terlambat_lain_no_punch_not_absent -q`
Expected: FAIL (`tidak_hadir == 1`).

- [ ] **Step 3: Edit the `tidak_hadir` CASE in `src/core/insights.py`**

Replace the `tidak_hadir` SUM CASE:

```python
               SUM(CASE WHEN ar.tipe = 'Hari Kerja'
                          AND ar.masuk IS NULL AND ar.keluar IS NULL
                          AND (ar.reason_category IS NULL
                               OR ar.reason_category NOT IN
                                  ('lupa_absen_datang', 'terlambat_kerja', 'terlambat_lain'))
                        THEN 1 ELSE 0 END) AS tidak_hadir,
```

- [ ] **Step 4: Run the whole Part-A test file + the insights suite**

Run: `.venv\Scripts\python.exe -m pytest tests/test_v21_justified_late.py tests/test_insights.py -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/core/insights.py tests/test_v21_justified_late.py
git commit -m "fix(v21-A2): no-punch justified-late row not counted tidak_hadir"
```

---

# PART B — Heatmap UI

### Task B1: distinct libur / nodata colours (slate + hollow)

**Files:**
- Modify: `src/core/heatmap.py` (`STATUS_COLORS`)
- Modify: `src/ui/screens/heatmap.py` (`_paint_card` cell loop, `_render_legend`)
- Modify: `src/reports/templates/heatmap_print.html.j2` (cell + legend)
- Test: `tests/test_v21_heatmap_colors.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_v21_heatmap_colors.py`:

```python
from src.core.heatmap import STATUS_COLORS

def test_libur_nodata_na_all_distinct():
    libur = STATUS_COLORS["libur"]
    nodata = STATUS_COLORS["nodata"]
    na = STATUS_COLORS["na"]
    assert libur != nodata
    assert libur != na
    assert nodata != na

def test_libur_is_slate():
    assert STATUS_COLORS["libur"] == "#39414F"
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_v21_heatmap_colors.py -q`
Expected: `test_libur_is_slate` FAILS (still `#404040`); distinctness may already pass.

- [ ] **Step 3: Edit `STATUS_COLORS` in `src/core/heatmap.py`**

```python
    "lupa": "#94A3B8", "mangkir": "#EF4444", "na": "#737373",
    "libur": "#39414F", "nodata": "#3A3F4A",
```

(`nodata` colour is the hollow-cell *outline*; the renderers special-case the
fill so it reads as an empty slot on both the dark screen and the white print.)

- [ ] **Step 4: Edit the canvas cell loop in `src/ui/screens/heatmap.py::_paint_card`**

Replace the rectangle-drawing block inside the `for w in range(nweeks):` cell
loop (the `rid = c.create_rectangle(... fill=cell["color"] ...)` line) with a
hollow branch for `nodata`:

```python
                cell = e["cells"][day]
                cx = gx + _WD_W + w * (_CELL_W + _CELL_GAP)
                if cell["status"] == "nodata":
                    rid = c.create_rectangle(cx, ry, cx + _CELL_W, ry + _CELL_H,
                                             fill=COLOR_SURFACE, outline=cell["color"],
                                             tags=("cell", "cellrect"))
                    tid = c.create_text(cx + 4, ry + 2, anchor="nw",
                                        fill=COLOR_TEXT_MUTED,
                                        font=(FONT_FAMILY, 10, "bold"),
                                        text=str(day), tags=("cell",))
                else:
                    rid = c.create_rectangle(cx, ry, cx + _CELL_W, ry + _CELL_H,
                                             fill=cell["color"], outline="",
                                             tags=("cell", "cellrect"))
                    tid = c.create_text(cx + 4, ry + 2, anchor="nw",
                                        fill=cell["text_color"],
                                        font=(FONT_FAMILY, 10, "bold"),
                                        text=str(day), tags=("cell",))
                self._cell_by_item[rid] = cell
                self._cell_by_item[tid] = cell
```

- [ ] **Step 5: Edit the screen legend `_render_legend` (hollow swatch for nodata)**

Inside the `for item in (...):` loop, special-case the swatch:

```python
            sw_kwargs = dict(width=22, height=16, font=(FONT_FAMILY, 10, "bold"),
                             corner_radius=4)
            if item["code"] == "–":   # nodata: hollow swatch
                ctk.CTkLabel(chip, text=item["code"], text_color=COLOR_TEXT_MUTED,
                             fg_color=COLOR_SURFACE, border_width=1,
                             border_color=item["color"], **sw_kwargs
                             ).pack(side="left", padx=(0, 4))
            else:
                ctk.CTkLabel(chip, text=item["code"], fg_color=item["color"],
                             text_color=item["text_color"], **sw_kwargs
                             ).pack(side="left", padx=(0, 4))
```

(Ensure `COLOR_TEXT_MUTED` and `COLOR_SURFACE` are already imported in
`heatmap.py` — they are.)

- [ ] **Step 6: Edit the print template `src/reports/templates/heatmap_print.html.j2`**

Cell rendering (matrix body row) — replace the single `<td class="cell ...">`
with a hollow branch:

```jinja
        {% for d in days %}{% set c = e.cells[d] %}{% if c.status == 'nodata' %}<td class="cell hollow {{ 'wsep' if d in wsep_days }}">{{ c.code }}</td>{% else %}<td class="cell {{ 'wsep' if d in wsep_days }}" style="background:{{ c.color }};color:{{ c.text_color }}">{{ c.code }}</td>{% endif %}{% endfor %}
```

Legend swatch — replace the legend item swatch span:

```jinja
    {% for l in legend %}<div class="it">{% if l.code == '–' %}<span class="sw hollow">{{ l.code }}</span>{% else %}<span class="sw" style="background:{{ l.color }};color:{{ l.text_color }}">{{ l.code }}</span>{% endif %}{{ l.label }}</div>{% endfor %}
```

Add CSS (inside `<style>`):

```css
  table.mx td.cell.hollow{background:#fff;border:1px dashed #c4c4cc;color:#b5b5bd}
  .legend .sw.hollow{background:#fff;border:1px dashed #c4c4cc;color:#b5b5bd}
```

- [ ] **Step 7: Run colour + print tests**

Run: `.venv\Scripts\python.exe -m pytest tests/test_v21_heatmap_colors.py tests/test_heatmap_print_render.py -q`
Expected: all pass.

- [ ] **Step 8: Commit**

```bash
git add src/core/heatmap.py src/ui/screens/heatmap.py src/reports/templates/heatmap_print.html.j2 tests/test_v21_heatmap_colors.py
git commit -m "feat(v21-B1): distinct libur (slate) vs nodata (hollow) colours"
```

### Task B2: full-width card, one employee per row

**Files:**
- Modify: `src/ui/screens/heatmap.py` (`_repaint`, `_on_canvas_configure`, `_paint_card`, layout constants)
- Test: `tests/test_v21_heatmap_layout.py` (smoke) + MANUAL visual

- [ ] **Step 1: Write a smoke test**

Create `tests/test_v21_heatmap_layout.py` (uses the shared `tk_root` fixture
pattern from `tests/test_dashboard_screen.py` / `conftest.py`):

```python
import pytest
from src.ui.screens import heatmap as mod

def test_heatmap_screen_one_column(tk_root, monkeypatch):
    # build_heatmap_context is hit on construction; stub to a tiny empty ctx
    empty = {"is_empty": True, "employees": [], "legend": [],
             "month_label": "Mei 2026", "eff_hari_kerja": 21,
             "prev_month": "2026-04", "next_month": "2026-06",
             "weeks": [], "summary_meta": [], "today_day": None}
    monkeypatch.setattr(mod, "build_heatmap_context", lambda *a, **k: empty)
    screen = mod.HeatmapScreen(tk_root)
    screen._repaint()
    assert screen._ncols == 1
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_v21_heatmap_layout.py -q`
Expected: FAIL (`_ncols` may be `None` or >1 on a wide root).

- [ ] **Step 3: Force single column + responsive width in `_repaint`**

In `src/ui/screens/heatmap.py::_repaint`, replace the `card_w`/`ncols` block
(the lines computing `card_w = self._card_width(...)`, `avail`, `ncols`) with:

```python
        ctx = self._ctx
        avail = max(self._canvas.winfo_width(), 320)
        card_w = avail - 2 * _PAD          # one card fills the row
        card_h = _HEAD_H + 7 * (_CELL_H + _CELL_GAP) + 2 * _CARD_PAD
        ncols = 1
        self._ncols = ncols
        for i, e in enumerate(emps):
            self._paint_card(e, _PAD, _PAD + i * (card_h + _CARD_GAP), card_w)
        c.configure(scrollregion=(0, 0, 0, _PAD + len(emps) * (card_h + _CARD_GAP)))
```

In `_on_canvas_configure`, repaint when the available width changes enough to
matter (replace the `ncols`-based guard):

```python
    def _on_canvas_configure(self, event):
        if not self._ctx or self._ctx.get("is_empty"):
            return
        w = event.width
        if self._last_w is None or abs(w - self._last_w) > 8:
            self._last_w = w
            self._repaint()
```

Add `self._last_w = None` next to `self._ncols = None` in `__init__`.

- [ ] **Step 4: Make `_paint_card` accept the card width and anchor panels right**

Change the signature to `def _paint_card(self, e, x, y, card_w):` and replace the
geometry that computes `gx/sx/rx/card_right`:

```python
        weeks = ctx["weeks"]; nweeks = len(weeks)
        grid_w = _WD_W + nweeks * (_CELL_W + _CELL_GAP)
        card_right = x + card_w
        # Kehadiran + Ringkasan anchored to the right edge
        rx = card_right - _CARD_PAD - _SUM_W
        sx = rx - _COL_GAP - _SPOT_W
        gx = x + _CARD_PAD + _NAME_W + _COL_GAP   # grid after name, left side
```

(Everything else in `_paint_card` already uses `gx/sx/rx/card_right`; the grid
sits on the left after the name, the two panels hug the right edge, and the gap
between them flexes with the window.)

Enlarge cells for readability — bump constants near the top of the file:

```python
_CELL_W = 34
_CELL_H = 24
```

- [ ] **Step 5: Run smoke test + full heatmap suite**

Run: `.venv\Scripts\python.exe -m pytest tests/test_v21_heatmap_layout.py tests/test_heatmap_helpers.py tests/test_heatmap_context_sorotan.py -q`
Expected: all pass.

- [ ] **Step 6: MANUAL visual check**

Seed a demo DB and screenshot the heatmap at a normal window width; confirm one
card fills the row with no large empty right margin, and that nodata cells read
as hollow and libur as slate-blue. (Reuse the scratchpad render/launch approach.)

- [ ] **Step 7: Commit**

```bash
git add src/ui/screens/heatmap.py tests/test_v21_heatmap_layout.py
git commit -m "feat(v21-B2): heatmap card full-width, one employee per row"
```

---

# PART C — Per-employee monthly report

### Task C1: renderer + template (identity + stats)

**Files:**
- Create: `src/reports/employee_report.py`
- Create: `src/reports/templates/employee_report.html.j2`
- Test: `tests/test_employee_report.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_employee_report.py`:

```python
import os, tempfile
from pathlib import Path
from src.db.schema import init_db
from src.db.connection import get_connection
from src.db.employees import upsert_employee
from src.db.attendance import upsert_attendance
from src.db.settings import set_setting
from src.reports.employee_report import render_employee_report_html

def _seed():
    fd, p = tempfile.mkstemp(suffix=".db"); os.close(fd); p = Path(p)
    init_db(p)
    with get_connection(p) as conn:
        set_setting(conn, "hr_officer_name", "Budi Officer")
        e = upsert_employee(conn, no_staff="7", nama="ANDIKA WIJAYA", dept="ARGA DIRGA")
        upsert_attendance(conn, employee_id=e, tanggal="2026-05-04", hari="Senin",
                          tipe="Hari Kerja", jadwal="", masuk="08:30", keluar="16:30",
                          kerja_jam=None, lembur_jam=None, terlambat_menit=30,
                          has_issue=0, imported_from="W")
    return p, e

def test_report_has_identity_and_stats():
    p, e = _seed()
    with get_connection(p) as conn:
        html = render_employee_report_html(conn, "2026-05", e)
    assert "ANDIKA WIJAYA" in html
    assert "ARGA DIRGA" in html
    assert "Mei 2026" in html
    assert "Budi Officer" in html          # HR officer sign-off
    assert "Kehadiran" in html             # stats block label
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_employee_report.py -q`
Expected: FAIL (module/function does not exist).

- [ ] **Step 3: Create `src/reports/employee_report.py`**

```python
"""Render a one-employee monthly recap to an HTML string (browser → Ctrl-P).

Reuses build_heatmap_context (one employee slice) and the reports Jinja env so
paths resolve in dev and the PyInstaller bundle."""
from datetime import date

from src.db.settings import get_setting
from src.core.heatmap import build_heatmap_context
from src.reports.html_renderer import _build_env


def render_employee_report_html(conn, year_month, employee_id):
    month = (year_month or "").strip() or date.today().strftime("%Y-%m")
    ctx = build_heatmap_context(conn, month, exclude_outliers=False)
    emp = next((e for e in ctx["employees"] if e["employee_id"] == employee_id), None)
    if emp is None:
        emp = {"nama": "—", "dept": "", "employee_id": employee_id,
               "hk": 0, "summary": {}, "cells": {},
               "sorotan": {"hk": 0, "work_days": ctx["eff_hari_kerja"],
                           "pct_hadir": 0, "pct_color": "#737373",
                           "ontime_days": 0, "telat_total": 0, "telat_days": 0,
                           "dinas": 0, "sakit": 0}}
    no_staff = ""
    row = conn.execute("SELECT no_staff FROM employees WHERE id=?",
                       (employee_id,)).fetchone()
    if row and row[0]:
        no_staff = row[0]
    env = _build_env()
    return env.get_template("employee_report.html.j2").render(
        emp=emp,
        no_staff=no_staff,
        month_label=ctx["month_label"],
        days=ctx["days"],
        weekday_of=ctx["weekday_of"],
        weekday_labels=ctx["weekday_labels"],
        weeks=ctx["weeks"],
        eff_hari_kerja=ctx["eff_hari_kerja"],
        legend=ctx["legend"],
        hr_officer_name=get_setting(conn, "hr_officer_name", default=""),
    )
```

- [ ] **Step 4: Create `src/reports/templates/employee_report.html.j2` (identity + stats first)**

```jinja
<!DOCTYPE html>
<html lang="id"><head><meta charset="utf-8"/>
<title>Laporan Kehadiran — {{ emp.nama }} — {{ month_label }}</title>
<style>
  @page{ size:A4 portrait; margin:12mm; }
  *{box-sizing:border-box}
  body{margin:0;background:#fff;color:#111;font-family:"Segoe UI",Arial,sans-serif;font-size:11px}
  .bar{display:flex;justify-content:space-between;align-items:flex-end;border-bottom:2px solid #111;padding-bottom:6px}
  .bar h1{font-size:16px;margin:0}
  .bar .meta{font-size:11px;color:#444;text-align:right;line-height:1.5}
  .stats{display:flex;flex-wrap:wrap;gap:8px 22px;margin:12px 0}
  .stats .s{font-size:11px}
  .stats .s b{font-size:15px;display:block}
  h2.sec{font-size:12px;margin:14px 0 4px;border-bottom:1px solid #999;padding-bottom:3px}
  table.det{width:100%;border-collapse:collapse;font-size:9px}
  table.det th,table.det td{border:.5px solid #ccc;padding:3px 6px;text-align:left}
  table.det thead th{background:#222;color:#fff}
  table.det td.c{text-align:center}
  .signoff{margin-top:18px;display:flex;justify-content:flex-end}
  .signoff .so{text-align:center;font-size:10px;min-width:220px}
  .signoff .so .gap{height:46px}
  .signoff .so .name{font-weight:700;border-top:1px solid #111;padding-top:4px}
  .foot{margin-top:14px;font-size:9px;color:#555}
  .mx{border-collapse:collapse;table-layout:fixed;margin-top:6px}
  .mx td,.mx th{border:.5px solid #dcdce2;text-align:center;width:18px;height:16px;font-size:8px;font-weight:700;-webkit-print-color-adjust:exact;print-color-adjust:exact}
  .mx td.hollow{background:#fff;border:1px dashed #c4c4cc;color:#b5b5bd}
</style></head><body>
  <div class="bar">
    <h1>LAPORAN KEHADIRAN — {{ emp.nama }}</h1>
    <div class="meta">Josaphat Tech Solution · HR Absensi<br>
      {{ emp.dept }}{% if no_staff %} · NIP {{ no_staff }}{% endif %} · {{ month_label }}</div>
  </div>
  {% set s = emp.sorotan %}
  <div class="stats">
    <div class="s">Kehadiran<b>{{ s.pct_hadir }}%</b></div>
    <div class="s">Hari kerja dihadiri<b>{{ s.hk }}/{{ s.work_days }}</b></div>
    <div class="s">Tepat waktu<b>{{ s.ontime_days }} hari</b></div>
    <div class="s">Telat<b>{{ s.telat_total }} mnt · {{ s.telat_days }} hari</b></div>
    <div class="s">Dinas<b>{{ s.dinas }}</b></div>
    <div class="s">Sakit<b>{{ s.sakit }}</b></div>
  </div>
  {# mini-heatmap + per-day table added in Task C2 #}
  <div class="signoff"><div class="so">
    <div>HR Officer in Charge</div><div class="gap"></div>
    <div class="name">{{ hr_officer_name if hr_officer_name else "____________" }}</div>
  </div></div>
  <div class="foot">HR Absensi · Laporan per-pegawai · {{ month_label }}</div>
</body></html>
```

- [ ] **Step 5: Run to verify pass**

Run: `.venv\Scripts\python.exe -m pytest tests/test_employee_report.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/reports/employee_report.py src/reports/templates/employee_report.html.j2 tests/test_employee_report.py
git commit -m "feat(v21-C1): per-employee report renderer + identity/stats template"
```

### Task C2: mini-heatmap + per-day table

**Files:**
- Modify: `src/reports/templates/employee_report.html.j2`
- Test: `tests/test_employee_report.py`

- [ ] **Step 1: Add failing assertions**

Append to `tests/test_employee_report.py`:

```python
def test_report_has_grid_and_perday_row():
    p, e = _seed()
    with get_connection(p) as conn:
        html = render_employee_report_html(conn, "2026-05", e)
    assert 'class="mx"' in html                 # mini-heatmap grid
    assert "Lampiran — Rincian Harian" in html  # per-day table heading
    assert "08:30" in html                      # the seeded punch appears
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_employee_report.py::test_report_has_grid_and_perday_row -q`
Expected: FAIL.

- [ ] **Step 3: Insert the mini-heatmap + table where the C1 comment marker is**

Replace `{# mini-heatmap + per-day table added in Task C2 #}` with:

```jinja
  <h2 class="sec">Pola Bulan</h2>
  <table class="mx">
    <tr><th></th>{% for w in range(weeks|length) %}<th>M{{ w + 1 }}</th>{% endfor %}</tr>
    {% for wd in range(7) %}
    <tr><td style="font-weight:400;color:#999">{{ weekday_labels[wd] }}</td>
      {% for w in range(weeks|length) %}{% set day = weeks[w][wd] %}{% if day == 0 %}<td></td>{% elif emp.cells[day].status == 'nodata' %}<td class="hollow">{{ emp.cells[day].code }}</td>{% else %}<td style="background:{{ emp.cells[day].color }};color:{{ emp.cells[day].text_color }}">{{ emp.cells[day].code }}</td>{% endif %}{% endfor %}
    </tr>{% endfor %}
  </table>

  <h2 class="sec">Lampiran — Rincian Harian</h2>
  <table class="det">
    <thead><tr><th>Tgl</th><th>Hari</th><th>Status</th><th>Masuk</th><th>Keluar</th><th>Telat</th><th>Alasan</th></tr></thead>
    <tbody>
    {% for d in days %}{% set c = emp.cells[d] %}{% if c.status not in ('libur', 'nodata') %}
      <tr><td class="c">{{ d }}</td><td>{{ weekday_labels[weekday_of[d]] }}</td>
        <td>{{ c.code }} · {{ "Dinas" if c.status == "dinas" else c.label }}</td>
        <td class="c">{{ c.masuk }}</td><td class="c">{{ c.keluar }}</td>
        <td class="c">{{ c.telat }}</td><td>{{ c.alasan }}</td></tr>
    {% endif %}{% endfor %}
    </tbody>
  </table>
```

- [ ] **Step 4: Run to verify pass**

Run: `.venv\Scripts\python.exe -m pytest tests/test_employee_report.py -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/reports/templates/employee_report.html.j2 tests/test_employee_report.py
git commit -m "feat(v21-C2): per-employee report mini-heatmap + daily detail table"
```

### Task C3: per-employee Cetak button on the card

**Files:**
- Modify: `src/ui/screens/heatmap.py` (`_paint_card` draws button; new `_on_cetak_click` + `_print_employee`; bind in `_build_canvas`)
- Test: MANUAL (canvas button) + ensure suite green

- [ ] **Step 1: Add the import**

At the top of `src/ui/screens/heatmap.py`, add:

```python
from src.reports.employee_report import render_employee_report_html
```

- [ ] **Step 2: Draw the button in `_paint_card`**

After the card background is drawn (right after the `self._round_rect(...)` and
the needs_attention accent), add a small button at the card's top-right:

```python
        bx1 = card_right - _CARD_PAD
        bx0 = bx1 - 78
        by0 = y + 8
        by1 = by0 + 20
        bid = self._round_rect(bx0, by0, bx1, by1, 6,
                               fill=COLOR_SURFACE_HIGH, outline=COLOR_BORDER)
        tid = c.create_text((bx0 + bx1) / 2, (by0 + by1) / 2, fill=COLOR_TEXT,
                            font=(FONT_FAMILY, 10, "bold"), text="🖨 Cetak")
        for it in (bid, tid):
            c.addtag_withtag("cetak", it)
            self._cell_by_item[it] = {"_cetak_emp": e["employee_id"]}
```

(`card_right` is computed at the top of `_paint_card`. Place this block after the
name/dept text so the button paints on top.)

- [ ] **Step 3: Bind the cetak tag + handlers**

In `_build_canvas`, add:

```python
        self._canvas.tag_bind("cetak", "<Button-1>", self._on_cetak_click)
```

Add the handlers to the class:

```python
    def _on_cetak_click(self, _event):
        item = self._canvas.find_withtag("current")
        info = self._cell_by_item.get(item[0]) if item else None
        if info and "_cetak_emp" in info:
            self._print_employee(info["_cetak_emp"])
        return "break"

    def _print_employee(self, employee_id):
        with get_connection(DB_PATH) as conn:
            html = render_employee_report_html(conn, self._month, employee_id)
        fd, path = tempfile.mkstemp(suffix=".html", prefix="emp_report_")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(html)
        open_html_in_browser(Path(path))
```

Note: the `cetak` `<Button-1>` binding is checked before the `cell` binding
because the button items are drawn last (higher in the stacking order) and carry
the `cetak` tag; `_on_cetak_click` returns `"break"` so the cell-click handler
does not also fire.

- [ ] **Step 4: Run the full suite (no regressions)**

Run: `.venv\Scripts\python.exe -m pytest -q`
Expected: all green (previous baseline + the new v21 tests).

- [ ] **Step 5: MANUAL check**

Launch the app on a seeded demo DB, open Heatmap, click a card's "🖨 Cetak" →
the browser opens that employee's report (identity, stats, mini-heatmap, daily
table, sign-off). Confirm clicking a normal cell still pins the detail strip.

- [ ] **Step 6: Commit**

```bash
git add src/ui/screens/heatmap.py
git commit -m "feat(v21-C3): per-employee Cetak button opens monthly report"
```

---

# RELEASE — Task R

**Files:** `src/config.py` (`APP_VERSION`, `APP_CHANGELOG`), `tests/test_changelog_v20_1.py` (rotate), `tests/test_changelog_v21.py` (new).

- [ ] **Step 1:** Bump `APP_VERSION = "21.0.0"` and `APP_BUILD_DATE` to the build date; prepend an `APP_CHANGELOG` entry (Indonesian, user-facing) covering: fix "Terlambat dengan alasan" kini dihitung tidak-telat & hadir di Dashboard + Heatmap; heatmap kartu penuh-lebar 1 nama/baris; warna libur vs belum-terinput dibedakan; fitur tombol Cetak laporan per-pegawai.
- [ ] **Step 2:** Rotate changelog tests: demote `tests/test_changelog_v20_1.py` to a retention test (assert the 20.0.1 entry persists), add `tests/test_changelog_v21.py` (top entry == 21.0.0, kinds include feat+fix, blob mentions "Terlambat dengan alasan" and "Cetak").
- [ ] **Step 3:** `.venv\Scripts\python.exe -m pytest -q` → all green.
- [ ] **Step 4:** Build installer (data-safe): record prod `data/hr.db` md5; `Move dist/HR-Absensi → dist/HR-Absensi.PRODSAVE`; `python -m tools.build_installer` (ISCC on PATH); reconstruct 2-level rotation (restore `data/`, shift `.bak`/`.bak.old`, drop oldest); verify md5 unchanged.
- [ ] **Step 5:** Copy installer to `Installers/HR-Absensi-Setup-v21.0.0.exe`; smoke-launch; verify md5 unchanged.
- [ ] **Step 6:** Commit the release; **HOLD push** until explicit user authorization (Rule 1). When authorized: `git push origin v21`, advance `origin/latest`, update `memory/version_state.md`.

---

## Self-Review

- **Spec coverage:** A1+A2 cover Part A (tuples + tidak_hadir). B1 covers colours, B2 covers full-width layout. C1+C2+C3 cover renderer+template+button. R covers release. ✓
- **Placeholder scan:** every code step has real code; commands have expected outcomes. The C1 unknown-`employee_id` path is implemented (graceful empty `emp`). ✓
- **Type consistency:** `render_employee_report_html(conn, year_month, employee_id)` used identically in the test, the module, and `_print_employee`. `build_heatmap_context` keys (`employees`, `employee_id`, `cells`, `sorotan`, `summary`, `eff_hari_kerja`, `weeks`, `weekday_of`, `weekday_labels`, `month_label`, `days`, `legend`) match `src/core/heatmap.py`. Cell keys (`status`, `code`, `color`, `text_color`, `masuk`, `keluar`, `telat`, `alasan`) match. ✓
- **Risk:** B2 layout + C3 button are canvas-drawn → verified by smoke test + manual screenshot, not pure unit tests (documented).
