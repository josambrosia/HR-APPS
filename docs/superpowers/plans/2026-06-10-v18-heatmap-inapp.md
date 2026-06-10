# v18 Heatmap — In-App Render Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert the v18 Heatmap from a browser/loopback-server feature into an **in-app customtkinter screen** (grid painted on a `tk.Canvas`), keeping print as browser→PDF via a temp HTML file, and add a per-employee **Panel Sorotan** plus three quick-wins (sort, "perlu perhatian" highlight, "hari ini" marker).

**Architecture:** Pure data/colour logic in `src/core/heatmap.py` stays the source of truth and gains `sorotan` metrics + small helpers. The screen consumes that context and paints all cells on one Canvas (fast; hover tooltip + click→detail strip; in-app search + sort + month nav). Print is extracted into a pure `render_heatmap_print_html()` that the screen writes to a temp file and opens in the browser. The loopback server + dashboard template are deleted.

**Tech Stack:** Python 3.13, customtkinter, tkinter.Canvas, Jinja2, pytest. Spec: `docs/superpowers/specs/2026-06-10-v18-heatmap-dashboard-design.md`.

**Baseline:** v18 browser version is committed + green (349 tests). This plan is the delta to in-app. Run tests from the worktree root: `../../../.venv/Scripts/python.exe -m pytest -q`.

---

### Task 1: Pure helpers — `pct_band_color`, `needs_attention`, `sort_employees`

**Files:**
- Modify: `src/core/heatmap.py` (append three module-level functions)
- Test: `tests/test_heatmap_helpers.py` (create)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_heatmap_helpers.py
from src.core.heatmap import pct_band_color, needs_attention, sort_employees


def test_pct_band_color():
    assert pct_band_color(100) == "#10B981"
    assert pct_band_color(90) == "#10B981"
    assert pct_band_color(89) == "#FBBF24"
    assert pct_band_color(75) == "#FBBF24"
    assert pct_band_color(74) == "#EC4899"
    assert pct_band_color(0) == "#EC4899"


def test_needs_attention():
    assert needs_attention({"X": 1, "TB": 0}) is True
    assert needs_attention({"X": 0, "TB": 2}) is True
    assert needs_attention({"X": 0, "TB": 0}) is False


def _emp(nama, x, pct, td, tt):
    return {"nama": nama, "summary": {"X": x},
            "sorotan": {"pct_hadir": pct, "telat_days": td, "telat_total": tt}}


def test_sort_employees():
    emps = [_emp("Budi", 0, 100, 1, 10), _emp("Andi", 2, 80, 3, 50),
            _emp("Citra", 0, 90, 0, 0)]
    assert [e["nama"] for e in sort_employees(emps, "nama")] == ["Andi", "Budi", "Citra"]
    assert [e["nama"] for e in sort_employees(emps, "kehadiran")] == ["Andi", "Citra", "Budi"]
    assert [e["nama"] for e in sort_employees(emps, "telat")] == ["Andi", "Budi", "Citra"]
    assert [e["nama"] for e in sort_employees(emps, "absen")] == ["Andi", "Budi", "Citra"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `../../../.venv/Scripts/python.exe -m pytest tests/test_heatmap_helpers.py -q`
Expected: FAIL — `ImportError: cannot import name 'pct_band_color'`.

- [ ] **Step 3: Append the helpers to `src/core/heatmap.py`** (after `build_heatmap_context`)

```python
def pct_band_color(pct):
    """Colour band for the % Kehadiran bar/number (≥90 green, 75–89 amber, <75 rose)."""
    if pct >= 90:
        return "#10B981"
    if pct >= 75:
        return "#FBBF24"
    return "#EC4899"


def needs_attention(summary):
    """True when the employee has an unexcused absence (X) or severe lateness (TB)."""
    return summary.get("X", 0) > 0 or summary.get("TB", 0) > 0


def sort_employees(employees, key):
    """Stable sort of heatmap employee dicts, tiebreak by nama (case-insensitive).
    key ∈ {"nama","kehadiran","telat","absen"}; unknown → nama A–Z."""
    if key == "kehadiran":
        return sorted(employees, key=lambda e: (e["sorotan"]["pct_hadir"], e["nama"].lower()))
    if key == "telat":
        return sorted(employees, key=lambda e: (-e["sorotan"]["telat_days"],
                                                -e["sorotan"]["telat_total"], e["nama"].lower()))
    if key == "absen":
        return sorted(employees, key=lambda e: (-e["summary"]["X"], e["nama"].lower()))
    return sorted(employees, key=lambda e: e["nama"].lower())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `../../../.venv/Scripts/python.exe -m pytest tests/test_heatmap_helpers.py -q`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add src/core/heatmap.py tests/test_heatmap_helpers.py
git commit -m "feat(v18): heatmap pure helpers — pct_band_color, needs_attention, sort_employees"
```

---

### Task 2: `build_heatmap_context` — per-employee `sorotan` + `today_day`

**Files:**
- Modify: `src/core/heatmap.py` (function `build_heatmap_context`)
- Test: `tests/test_heatmap_context_sorotan.py` (create)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_heatmap_context_sorotan.py
from datetime import date
from src.db.schema import init_db
from src.db.connection import get_connection
from src.db.employees import upsert_employee
from src.db.attendance import upsert_attendance
from src.core.heatmap import build_heatmap_context


def _seed(conn):
    a = upsert_employee(conn, no_staff="1", nama="ANDI", dept="IT")
    # Mon 75min -> TB(parah), Tue 20min -> TR(sedang), Wed 5min -> H(hadir)
    for tgl, hari, masuk, telat in (("2026-05-04", "Senin", "09:15", 75),
                                    ("2026-05-05", "Selasa", "08:20", 20),
                                    ("2026-05-06", "Rabu", "08:05", 5)):
        upsert_attendance(conn, employee_id=a, tanggal=tgl, hari=hari,
                          tipe="Hari Kerja", jadwal="", masuk=masuk, keluar="16:30",
                          kerja_jam=None, lembur_jam=None, terlambat_menit=telat,
                          has_issue=0, imported_from="W")
    return a


def test_sorotan_metrics():
    import tempfile, os
    fd, p = tempfile.mkstemp(suffix=".db"); os.close(fd)
    init_db(p)
    with get_connection(p) as conn:
        _seed(conn)
        ctx = build_heatmap_context(conn, "2026-05", exclude_outliers=False)
    e = ctx["employees"][0]
    s = e["sorotan"]
    assert s["hk"] == 3                     # H+TR+TB attended
    assert s["work_days"] == ctx["eff_hari_kerja"]
    assert s["ontime_days"] == 1            # only the 5-min day
    assert s["telat_total"] == 95           # 75 + 20
    assert s["telat_days"] == 2             # TR + TB
    assert s["pct_hadir"] == round(3 / ctx["eff_hari_kerja"] * 100)
    assert s["pct_color"] in ("#10B981", "#FBBF24", "#EC4899")
    assert e["needs_attention"] is True     # has a TB day


def test_today_day_present_and_absent():
    import tempfile, os
    fd, p = tempfile.mkstemp(suffix=".db"); os.close(fd)
    init_db(p)
    with get_connection(p) as conn:
        _seed(conn)
        in_month = build_heatmap_context(conn, "2026-05", exclude_outliers=False,
                                         today=date(2026, 5, 15))
        other = build_heatmap_context(conn, "2026-05", exclude_outliers=False,
                                      today=date(2026, 6, 1))
    assert in_month["today_day"] == 15
    assert other["today_day"] is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `../../../.venv/Scripts/python.exe -m pytest tests/test_heatmap_context_sorotan.py -q`
Expected: FAIL — `KeyError: 'sorotan'` (and `today` is an unexpected kwarg).

- [ ] **Step 3: Edit `build_heatmap_context` in `src/core/heatmap.py`**

3a. Change the signature to accept an injectable `today`:

```python
def build_heatmap_context(conn, year_month, *, exclude_outliers, today=None):
```

3b. Inside the per-employee loop, initialise a lateness accumulator next to `hk = 0`:

```python
        cells = {}
        summary = {k: 0 for k in _SUMMARY_KEYS}
        hk = 0
        telat_total = 0
```

3c. Inside the `for d in range(...)` loop, after `status = cell_status(...)`, accumulate late minutes:

```python
            if status in ("sedang", "parah"):
                telat_total += (row["terlambat_menit"] or 0)
```

3d. Replace the `out_emps.append({...})` block with one that adds `sorotan` + `needs_attention`:

```python
        sorotan = {
            "hk": hk,
            "work_days": eff_hk,
            "pct_hadir": round(hk / eff_hk * 100) if eff_hk else 0,
            "ontime_days": summary["H"],
            "telat_total": telat_total,
            "telat_days": summary["TR"] + summary["TB"],
            "dinas": summary["D"],
            "sakit": summary["S"],
        }
        sorotan["pct_color"] = pct_band_color(sorotan["pct_hadir"])
        out_emps.append({
            "employee_id": eid, "nama": e["nama"], "dept": e.get("dept") or "",
            "hk": hk, "summary": summary, "cells": cells,
            "sorotan": sorotan, "needs_attention": needs_attention(summary),
        })
```

3e. Compute `today_day` just before the `return {` (after `prev_m, next_m = ...`):

```python
    today = today or date.today()
    today_day = today.day if (today.year == y and today.month == m) else None
```

3f. Add `"today_day": today_day,` to the returned dict (e.g., right after `"year_month": year_month,`).

> `date` is already imported at the top of the module; `pct_band_color` / `needs_attention` are defined in Task 1 (same module). `eff_hk` already exists in the function.

- [ ] **Step 4: Run tests to verify they pass**

Run: `../../../.venv/Scripts/python.exe -m pytest tests/test_heatmap_context_sorotan.py tests/test_heatmap_context.py -q`
Expected: PASS (2 new + 3 existing still green).

- [ ] **Step 5: Commit**

```bash
git add src/core/heatmap.py tests/test_heatmap_context_sorotan.py
git commit -m "feat(v18): build_heatmap_context adds per-employee sorotan + today_day"
```

---

### Task 3: `render_heatmap_print_html` (server-free print render)

**Files:**
- Create: `src/reports/heatmap_print.py`
- Test: `tests/test_heatmap_print_render.py` (create)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_heatmap_print_render.py
import tempfile, os
from src.db.schema import init_db
from src.db.connection import get_connection
from src.db.employees import upsert_employee
from src.db.attendance import upsert_attendance
from src.reports.heatmap_print import render_heatmap_print_html


def _db():
    fd, p = tempfile.mkstemp(suffix=".db"); os.close(fd)
    init_db(p)
    with get_connection(p) as conn:
        a = upsert_employee(conn, no_staff="1", nama="ANDI", dept="IT")
        upsert_attendance(conn, employee_id=a, tanggal="2026-05-04", hari="Senin",
                          tipe="Hari Kerja", jadwal="", masuk="09:15", keluar="16:30",
                          kerja_jam=None, lembur_jam=None, terlambat_menit=75,
                          has_issue=0, imported_from="W")
    return p


APPENDIX = "Lampiran — Detail Hari Kerja"


def test_full_has_matrix_and_appendix():
    with get_connection(_db()) as conn:
        html = render_heatmap_print_html(conn, "2026-05", scope="full", outlier="inc")
    assert "Mei 2026" in html and "ANDI" in html
    assert 'class="mx"' in html and APPENDIX in html


def test_matrix_only_omits_appendix():
    with get_connection(_db()) as conn:
        html = render_heatmap_print_html(conn, "2026-05", scope="matrix", outlier="inc")
    assert 'class="mx"' in html and APPENDIX not in html


def test_lampiran_only_omits_matrix():
    with get_connection(_db()) as conn:
        html = render_heatmap_print_html(conn, "2026-05", scope="lampiran", outlier="inc")
    assert APPENDIX in html and 'class="mx"' not in html
```

- [ ] **Step 2: Run test to verify it fails**

Run: `../../../.venv/Scripts/python.exe -m pytest tests/test_heatmap_print_render.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.reports.heatmap_print'`.

- [ ] **Step 3: Create `src/reports/heatmap_print.py`**

```python
"""Render the Heatmap print report (matrix + appendix) to an HTML string.

Server-free: mirrors the old loopback route, reusing the reports Jinja2 env so
template paths resolve in dev AND the PyInstaller bundle. The caller writes the
string to a temp file and opens it in the browser (Ctrl-P / Save PDF)."""
from datetime import date

from src.db.settings import get_setting
from src.core.heatmap import build_heatmap_context
from src.reports.html_renderer import _build_env


def render_heatmap_print_html(conn, year_month=None, *, scope="full", outlier="inc"):
    """scope ∈ {'full','matrix','lampiran'}; outlier ∈ {'inc','exc'}."""
    month = (year_month or "").strip()
    if not month:
        month = get_setting(conn, "current_month", default="") or date.today().strftime("%Y-%m")
    ctx = build_heatmap_context(conn, month, exclude_outliers=(outlier == "exc"))
    env = _build_env()
    return env.get_template("heatmap_print.html.j2").render(scope=scope, **ctx)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `../../../.venv/Scripts/python.exe -m pytest tests/test_heatmap_print_render.py -q`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add src/reports/heatmap_print.py tests/test_heatmap_print_render.py
git commit -m "feat(v18): render_heatmap_print_html (server-free print render)"
```

---

### Task 4: Remove the loopback server + dashboard template + spec entries

**Files:**
- Delete: `src/web/heatmap_server.py`, `src/web/__init__.py`, `src/reports/templates/heatmap.html.j2`, `tests/test_heatmap_server.py`
- Modify: `HR-Absensi.spec`

- [ ] **Step 1: Delete the obsolete files**

```bash
git rm src/web/heatmap_server.py src/web/__init__.py src/reports/templates/heatmap.html.j2 tests/test_heatmap_server.py
```

- [ ] **Step 2: Edit `HR-Absensi.spec` — drop the dashboard template from `datas`**

Remove this exact line (line ~10):

```python
        ('src/reports/templates/heatmap.html.j2', 'src/reports/templates'),
```

(Keep the `heatmap_print.html.j2` line.)

- [ ] **Step 3: Edit `HR-Absensi.spec` — drop the server from `hiddenimports`**

Change:

```python
    hiddenimports=['customtkinter', 'PIL', 'src.web.heatmap_server'],
```

to:

```python
    hiddenimports=['customtkinter', 'PIL'],
```

- [ ] **Step 4: Verify nothing still imports the deleted modules**

Run: `../../../.venv/Scripts/python.exe -c "import ast,sys; sys.exit(0)"` then
Run: `grep -rn "heatmap_server\|src.web\|heatmap.html.j2" src tests` (PowerShell: use Grep tool)
Expected: **no matches** in `src/` or `tests/` (the screen rewrite in Task 5 already drops them; if Task 5 not done yet, the only hit is the current `src/ui/screens/heatmap.py`, which Task 5 replaces — that is expected).

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "refactor(v18): remove loopback heatmap server + dashboard template (in-app render)"
```

---

### Task 5: Rewrite `HeatmapScreen` as the in-app Canvas screen

**Files:**
- Replace: `src/ui/screens/heatmap.py` (full rewrite)
- Test: `tests/test_heatmap_screen.py` (replace existing launcher test)

- [ ] **Step 1: Write the failing smoke test** (replace the file's contents)

```python
# tests/test_heatmap_screen.py
import tempfile, os
import src.ui.screens.heatmap as mod
from src.db.schema import init_db
from src.db.employees import upsert_employee
from src.db.attendance import upsert_attendance
from src.db.connection import get_connection


def _seed_two(p):
    init_db(p)
    with get_connection(p) as conn:
        a = upsert_employee(conn, no_staff="1", nama="ANDI", dept="IT")
        b = upsert_employee(conn, no_staff="2", nama="BUDI", dept="HR")
        # ANDI: a severe-late day (75') -> needs_attention + low-ish pct
        upsert_attendance(conn, employee_id=a, tanggal="2026-05-04", hari="Senin",
                          tipe="Hari Kerja", jadwal="", masuk="09:15", keluar="16:30",
                          kerja_jam=None, lembur_jam=None, terlambat_menit=75,
                          has_issue=0, imported_from="W")
        # BUDI: an on-time day
        upsert_attendance(conn, employee_id=b, tanggal="2026-05-04", hari="Senin",
                          tipe="Hari Kerja", jadwal="", masuk="08:03", keluar="16:10",
                          kerja_jam=None, lembur_jam=None, terlambat_menit=3,
                          has_issue=0, imported_from="W")
    return a, b


def _screen(monkeypatch, tk_root, p):
    monkeypatch.setattr(mod, "DB_PATH", p)
    with get_connection(p) as conn:
        from src.db.settings import set_setting
        set_setting(conn, "current_month", "2026-05")
    s = mod.HeatmapScreen(tk_root)
    tk_root.update_idletasks()
    return s


def test_constructs_and_paints_cells(tmp_path, monkeypatch, tk_root):
    p = str(tmp_path / "h.db"); _seed_two(p)
    s = _screen(monkeypatch, tk_root, p)
    # 31 days in May × 2 employees = 62 day-cell rectangles
    assert len(s._canvas.find_withtag("cellrect")) == 62
    s.destroy()


def test_search_filters(tmp_path, monkeypatch, tk_root):
    p = str(tmp_path / "h.db"); _seed_two(p)
    s = _screen(monkeypatch, tk_root, p)
    s._search.set("ANDI")
    tk_root.update_idletasks()
    assert [e["nama"] for e in s._visible_employees] == ["ANDI"]
    s._search.set("ZZZ")
    tk_root.update_idletasks()
    assert s._visible_employees == []
    s.destroy()


def test_sort_by_attendance(tmp_path, monkeypatch, tk_root):
    p = str(tmp_path / "h.db"); _seed_two(p)
    s = _screen(monkeypatch, tk_root, p)
    s._on_sort("Kehadiran terendah")
    tk_root.update_idletasks()
    # ANDI (1 attended / many work days) has the lower % than BUDI -> first
    assert s._visible_employees[0]["nama"] == "ANDI"
    s.destroy()


def test_click_detail_and_print(tmp_path, monkeypatch, tk_root):
    p = str(tmp_path / "h.db"); _seed_two(p)
    s = _screen(monkeypatch, tk_root, p)
    s._show_detail({"date": 4, "label": "Terlambat Berat", "masuk": "09:15",
                    "keluar": "16:30", "telat": 75, "alasan": "—"})
    assert "Terlambat Berat" in s._detail_var.get()
    captured = {}
    monkeypatch.setattr(mod, "open_html_in_browser", lambda path: captured.setdefault("p", path))
    s._do_print("full", "inc")
    assert os.path.exists(captured["p"])
    with open(captured["p"], encoding="utf-8") as f:
        assert "Mei 2026" in f.read()
    s.destroy()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `../../../.venv/Scripts/python.exe -m pytest tests/test_heatmap_screen.py -q`
Expected: FAIL — current `HeatmapScreen` has no `_canvas` / `_visible_employees` / `_show_detail`.

- [ ] **Step 3: Replace `src/ui/screens/heatmap.py` with the full in-app screen**

```python
"""In-app attendance heatmap screen (customtkinter + tk.Canvas).

The dense per-employee grid is painted on a single tk.Canvas (fast for ~1k+
cells); toolbar / legend / detail strip are CTk widgets. Hover a cell for a
floating tooltip; click to pin its detail to the strip. Search + sort + month
nav repaint in place. Print renders heatmap_print.html.j2 to a temp file and
opens it in the browser (Ctrl-P / Save PDF) — no server.
See docs/superpowers/specs/2026-06-10-v18-heatmap-dashboard-design.md.
"""
import os
import tempfile
from datetime import date

import tkinter as tk
import customtkinter as ctk

from src.config import DB_PATH
from src.db.connection import get_connection
from src.db.settings import get_setting
from src.core.heatmap import build_heatmap_context, sort_employees
from src.reports.heatmap_print import render_heatmap_print_html
from src.ui.browser_launcher import open_html_in_browser
from src.ui.components.search_bar import SearchBar
from src.ui.components.heatmap_print_dialog import HeatmapPrintDialog
from src.ui.theme import (
    COLOR_BG, COLOR_SURFACE, COLOR_SURFACE_HIGH, COLOR_BORDER, COLOR_ERROR,
    COLOR_TEXT, COLOR_TEXT_DIM, COLOR_TEXT_MUTED,
    FONT_FAMILY, FONT_DISPLAY, FONT_BODY, FONT_BODY_BOLD, FONT_SMALL,
    SPACE_XS, SPACE_SM, SPACE_MD, SPACE_LG, SPACE_XL, RADIUS_MD,
)

_PAD = 14
_CARD_GAP = 10
_CARD_PAD = 12
_NAME_W = 116
_WD_W = 22
_CELL_W = 30
_CELL_H = 22
_CELL_GAP = 3
_HEAD_H = 16
_COL_GAP = 16
_SPOT_W = 178
_SUM_W = 150

_SORT_OPTIONS = {
    "Nama (A–Z)": "nama",
    "Kehadiran terendah": "kehadiran",
    "Paling sering telat": "telat",
    "Paling sering absen": "absen",
}


class HeatmapScreen(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(4, weight=1)

        with get_connection(DB_PATH) as conn:
            m = get_setting(conn, "current_month", default="")
        self._month = m or date.today().strftime("%Y-%m")
        self._query = ""
        self._sortkey = "nama"
        self._ctx = None
        self._cell_by_item = {}
        self._visible_employees = []
        self._tip = None

        self._build_header()
        self._build_toolbar()
        self._legend = ctk.CTkFrame(self, fg_color="transparent")
        self._legend.grid(row=2, column=0, sticky="ew", padx=SPACE_XL, pady=(0, SPACE_XS))
        self._build_detail_strip()
        self._build_canvas()
        self._load()

        self.bind("<Control-f>", self._focus_search)
        try:
            self.winfo_toplevel().bind_all("<Control-f>", self._focus_search)
        except Exception:
            pass
        self._click_bind_id = self.winfo_toplevel().bind(
            "<Button-1>", self._on_click_outside_search, add="+")
        self.bind("<Destroy>", self._on_destroy_cleanup)

    # ---------- build ----------
    def _build_header(self):
        head = ctk.CTkFrame(self, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew", padx=SPACE_XL, pady=(SPACE_LG, SPACE_XS))
        ctk.CTkLabel(head, text="Heatmap Kehadiran", font=FONT_DISPLAY,
                     text_color=COLOR_TEXT).pack(side="left")
        self._subtitle = ctk.CTkLabel(head, text="", font=FONT_SMALL, text_color=COLOR_TEXT_DIM)
        self._subtitle.pack(side="left", padx=(SPACE_MD, 0))

    def _build_toolbar(self):
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.grid(row=1, column=0, sticky="ew", padx=SPACE_XL, pady=(0, SPACE_SM))
        self._search = SearchBar(bar, on_change=self._on_search, width=240)
        self._search.pack(side="left")
        self._sort_var = ctk.StringVar(value="Nama (A–Z)")
        ctk.CTkOptionMenu(
            bar, values=list(_SORT_OPTIONS.keys()), variable=self._sort_var,
            command=self._on_sort, width=190,
            fg_color=COLOR_SURFACE_HIGH, button_color=COLOR_SURFACE_HIGH,
            button_hover_color=COLOR_BORDER, text_color=COLOR_TEXT, font=FONT_SMALL,
        ).pack(side="left", padx=(SPACE_SM, 0))
        ctk.CTkButton(bar, text="🖨️  Cetak…", command=self._open_print,
                      fg_color="transparent", border_width=1, border_color=COLOR_BORDER,
                      text_color=COLOR_TEXT, hover_color=COLOR_SURFACE,
                      font=FONT_BODY_BOLD, corner_radius=RADIUS_MD, width=110
                      ).pack(side="right")
        self._next_btn = ctk.CTkButton(bar, text="›", width=34, command=self._go_next,
                                       fg_color=COLOR_SURFACE_HIGH, hover_color=COLOR_BORDER,
                                       text_color=COLOR_TEXT, font=FONT_BODY_BOLD)
        self._next_btn.pack(side="right", padx=(SPACE_XS, SPACE_MD))
        self._month_lbl = ctk.CTkLabel(bar, text="", font=FONT_BODY_BOLD,
                                       text_color=COLOR_TEXT, width=120)
        self._month_lbl.pack(side="right")
        self._prev_btn = ctk.CTkButton(bar, text="‹", width=34, command=self._go_prev,
                                       fg_color=COLOR_SURFACE_HIGH, hover_color=COLOR_BORDER,
                                       text_color=COLOR_TEXT, font=FONT_BODY_BOLD)
        self._prev_btn.pack(side="right", padx=(0, SPACE_XS))

    def _render_legend(self):
        for w in self._legend.winfo_children():
            w.destroy()
        for item in (self._ctx["legend"] if self._ctx else []):
            chip = ctk.CTkFrame(self._legend, fg_color="transparent")
            chip.pack(side="left", padx=(0, SPACE_MD))
            ctk.CTkLabel(chip, text=item["code"], width=22, height=16,
                         fg_color=item["color"], text_color=item["text_color"],
                         font=(FONT_FAMILY, 10, "bold"), corner_radius=4).pack(side="left", padx=(0, 4))
            ctk.CTkLabel(chip, text=item["label"], font=FONT_SMALL,
                         text_color=COLOR_TEXT_DIM).pack(side="left")

    def _build_detail_strip(self):
        strip = ctk.CTkFrame(self, fg_color=COLOR_SURFACE_HIGH, border_width=1,
                             border_color=COLOR_BORDER, corner_radius=RADIUS_MD)
        strip.grid(row=3, column=0, sticky="ew", padx=SPACE_XL, pady=(SPACE_XS, SPACE_SM))
        self._detail_var = ctk.StringVar(value="Klik sel untuk detail.")
        ctk.CTkLabel(strip, textvariable=self._detail_var, font=FONT_SMALL,
                     text_color=COLOR_TEXT, anchor="w").pack(side="left", padx=SPACE_MD, pady=6)

    def _build_canvas(self):
        wrap = ctk.CTkFrame(self, fg_color="transparent")
        wrap.grid(row=4, column=0, sticky="nsew", padx=SPACE_XL, pady=(0, SPACE_LG))
        wrap.grid_columnconfigure(0, weight=1)
        wrap.grid_rowconfigure(0, weight=1)
        self._canvas = tk.Canvas(wrap, bg=COLOR_BG, highlightthickness=0, bd=0)
        self._canvas.grid(row=0, column=0, sticky="nsew")
        sb = ctk.CTkScrollbar(wrap, command=self._canvas.yview)
        sb.grid(row=0, column=1, sticky="ns")
        self._canvas.configure(yscrollcommand=sb.set)
        self._canvas.bind("<MouseWheel>",
                          lambda e: self._canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"))
        self._canvas.tag_bind("cell", "<Motion>", self._on_cell_motion)
        self._canvas.tag_bind("cell", "<Leave>", lambda e: self._hide_tip())
        self._canvas.tag_bind("cell", "<Button-1>", self._on_cell_click)

    # ---------- data / nav ----------
    def _load(self):
        with get_connection(DB_PATH) as conn:
            self._ctx = build_heatmap_context(conn, self._month, exclude_outliers=False,
                                              today=date.today())
        self._month_lbl.configure(text=self._ctx["month_label"])
        self._subtitle.configure(
            text=("Hover sel untuk tooltip, klik untuk detail. "
                  f"Hari kerja efektif {self._ctx['month_label']}: "
                  f"{self._ctx['eff_hari_kerja']} hari."))
        self._render_legend()
        self._repaint()

    def _go_prev(self):
        self._month = self._ctx["prev_month"]
        self._load()

    def _go_next(self):
        self._month = self._ctx["next_month"]
        self._load()

    def _on_search(self, q):
        self._query = q
        self._repaint()

    def _on_sort(self, label):
        self._sortkey = _SORT_OPTIONS.get(label, "nama")
        self._repaint()

    # ---------- paint ----------
    def _visible(self):
        emps = self._ctx["employees"]
        q = self._query.lower().strip()
        if q:
            emps = [e for e in emps if q in (e["nama"] + " " + e.get("dept", "")).lower()]
        return sort_employees(emps, self._sortkey)

    def _repaint(self):
        c = self._canvas
        c.delete("all")
        self._cell_by_item = {}
        total = len(self._ctx["employees"]) if self._ctx else 0
        if not self._ctx or self._ctx["is_empty"]:
            c.create_text(20, 36, anchor="nw", fill=COLOR_TEXT_DIM, font=FONT_BODY,
                          text="Belum ada data untuk bulan ini — import data fingerprint dulu.")
            self._visible_employees = []
            self._search.set_count(0, total)
            c.configure(scrollregion=(0, 0, 0, 80))
            return
        emps = self._visible()
        self._visible_employees = emps
        self._search.set_count(len(emps), total)
        if not emps:
            c.create_text(20, 36, anchor="nw", fill=COLOR_TEXT_DIM, font=FONT_BODY,
                          text="Tidak ada hasil.")
            c.configure(scrollregion=(0, 0, 0, 80))
            return
        y = _PAD
        for e in emps:
            y = self._paint_card(e, y) + _CARD_GAP
        c.configure(scrollregion=(0, 0, 0, y + _PAD))

    def _round_rect(self, x0, y0, x1, y1, r, **kw):
        pts = [x0 + r, y0, x1 - r, y0, x1, y0, x1, y0 + r, x1, y1 - r, x1, y1,
               x1 - r, y1, x0 + r, y1, x0, y1, x0, y1 - r, x0, y0 + r, x0, y0]
        return self._canvas.create_polygon(pts, smooth=True, **kw)

    def _paint_card(self, e, y):
        c = self._canvas
        ctx = self._ctx
        weeks = ctx["weeks"]
        nweeks = len(weeks)
        grid_w = _WD_W + nweeks * (_CELL_W + _CELL_GAP)
        x = _PAD
        gx = x + _CARD_PAD + _NAME_W + _COL_GAP
        sx = gx + grid_w + _COL_GAP + 8
        rx = sx + _SPOT_W + _COL_GAP
        card_right = rx + _SUM_W + _CARD_PAD
        grid_h = _HEAD_H + 7 * (_CELL_H + _CELL_GAP)
        card_h = grid_h + 2 * _CARD_PAD
        self._round_rect(x, y, card_right, y + card_h, RADIUS_MD,
                         fill=COLOR_SURFACE, outline=COLOR_BORDER)
        if e.get("needs_attention"):
            c.create_rectangle(x, y + 6, x + 3, y + card_h - 6, fill=COLOR_ERROR, outline="")
        nx, ny = x + _CARD_PAD, y + _CARD_PAD
        c.create_text(nx, ny, anchor="nw", fill=COLOR_TEXT, font=FONT_BODY_BOLD, text=e["nama"])
        if e.get("dept"):
            c.create_text(nx, ny + 18, anchor="nw", fill=COLOR_TEXT_MUTED, font=FONT_SMALL, text=e["dept"])
        if e.get("needs_attention"):
            c.create_text(nx, ny + 40, anchor="nw", fill=COLOR_ERROR,
                          font=(FONT_FAMILY, 10, "bold"), text="● Perlu perhatian")
        gy = y + _CARD_PAD
        for w in range(nweeks):
            cx = gx + _WD_W + w * (_CELL_W + _CELL_GAP)
            c.create_text(cx + _CELL_W / 2, gy, anchor="n", fill=COLOR_TEXT_MUTED,
                          font=(FONT_FAMILY, 10, "bold"), text=f"M{w + 1}")
        wd_labels = ctx["weekday_labels"]
        today_day = ctx.get("today_day")
        for wd in range(7):
            ry = gy + _HEAD_H + wd * (_CELL_H + _CELL_GAP)
            c.create_text(gx + _WD_W - 4, ry + _CELL_H / 2, anchor="e", fill=COLOR_TEXT_DIM,
                          font=(FONT_FAMILY, 10, "bold"), text=wd_labels[wd])
            for w in range(nweeks):
                day = weeks[w][wd]
                if day == 0:
                    continue
                cell = e["cells"][day]
                cx = gx + _WD_W + w * (_CELL_W + _CELL_GAP)
                rid = c.create_rectangle(cx, ry, cx + _CELL_W, ry + _CELL_H,
                                         fill=cell["color"], outline="", tags=("cell", "cellrect"))
                tid = c.create_text(cx + 4, ry + 2, anchor="nw", fill=cell["text_color"],
                                    font=(FONT_FAMILY, 10, "bold"), text=str(day), tags=("cell",))
                self._cell_by_item[rid] = cell
                self._cell_by_item[tid] = cell
                if today_day and day == today_day:
                    c.create_rectangle(cx, ry, cx + _CELL_W, ry + _CELL_H,
                                       outline=COLOR_TEXT, width=2)
        self._paint_sorotan(sx, y + _CARD_PAD, e["sorotan"])
        self._paint_summary(rx, y + _CARD_PAD, e)
        return y + card_h

    def _paint_sorotan(self, sx, sy, s):
        c = self._canvas
        c.create_line(sx - 10, sy, sx - 10, sy + 166, fill=COLOR_BORDER)
        c.create_text(sx, sy, anchor="nw", fill=COLOR_TEXT_DIM, font=FONT_SMALL, text="Kehadiran")
        c.create_text(sx + _SPOT_W - 12, sy - 4, anchor="ne", fill=s["pct_color"],
                      font=(FONT_FAMILY, 18, "bold"), text=f"{s['pct_hadir']}%")
        by = sy + 26
        c.create_rectangle(sx, by, sx + _SPOT_W - 12, by + 6, fill=COLOR_BORDER, outline="")
        fillw = int((_SPOT_W - 12) * min(max(s["pct_hadir"], 0), 100) / 100)
        if fillw > 0:
            c.create_rectangle(sx, by, sx + fillw, by + 6, fill=s["pct_color"], outline="")
        c.create_text(sx, by + 11, anchor="nw", fill=COLOR_TEXT, font=(FONT_FAMILY, 12, "bold"),
                      text=f"{s['hk']}/{s['work_days']}")
        c.create_text(sx + 48, by + 13, anchor="nw", fill=COLOR_TEXT_MUTED,
                      font=(FONT_FAMILY, 10), text="hari kerja dihadiri")
        ly = by + 34
        for i, line in enumerate((
                f"Tepat waktu {s['ontime_days']} hari",
                f"Telat {s['telat_total']} mnt · {s['telat_days']} hari",
                f"Dinas {s['dinas']} · Sakit {s['sakit']}")):
            c.create_text(sx, ly + i * 18, anchor="nw", fill=COLOR_TEXT_DIM, font=FONT_SMALL, text=line)

    def _paint_summary(self, rx, sy, e):
        c = self._canvas
        c.create_line(rx - 10, sy, rx - 10, sy + 166, fill=COLOR_BORDER)
        c.create_text(rx, sy, anchor="nw", fill=COLOR_TEXT_MUTED, font=FONT_SMALL,
                      text=f"Ringkasan — HK {e['hk']}")
        summ = e["summary"]
        for i, m in enumerate(self._ctx["summary_meta"]):
            col, row = i % 2, i // 2
            ex = rx + col * 74
            ey = sy + 22 + row * 18
            c.create_rectangle(ex, ey + 2, ex + 10, ey + 12, fill=m["color"], outline="")
            c.create_text(ex + 16, ey, anchor="nw", fill=COLOR_TEXT_DIM, font=FONT_SMALL,
                          text=f"{m['code']} {summ[m['code']]}")

    # ---------- hover / click ----------
    def _current_cell(self):
        item = self._canvas.find_withtag("current")
        return self._cell_by_item.get(item[0]) if item else None

    def _on_cell_motion(self, event):
        cell = self._current_cell()
        if cell:
            self._show_tip(event, cell)

    def _show_tip(self, event, cell):
        if self._tip is None:
            self._tip = tk.Toplevel(self)
            self._tip.wm_overrideredirect(True)
            self._tip_lbl = tk.Label(self._tip, justify="left", bg="#000000", fg="#FFFFFF",
                                     font=(FONT_FAMILY, 9), bd=1, relief="solid", padx=8, pady=6)
            self._tip_lbl.pack()
        self._tip_lbl.configure(text=(
            f"{cell['label']}\n"
            f"Tanggal {cell['date']} · Masuk {cell['masuk']} · Keluar {cell['keluar']}\n"
            f"Telat {cell['telat']} · Alasan {cell['alasan']}"))
        self._tip.wm_geometry(f"+{event.x_root + 14}+{event.y_root + 12}")
        self._tip.deiconify()

    def _hide_tip(self):
        if self._tip is not None:
            self._tip.withdraw()

    def _on_cell_click(self, _event):
        cell = self._current_cell()
        if cell:
            self._show_detail(cell)

    def _show_detail(self, cell):
        self._detail_var.set(
            f"{cell['date']} {self._ctx['month_label']} · {cell['label']} · "
            f"Masuk {cell['masuk']} · Keluar {cell['keluar']} · "
            f"Telat {cell['telat']} · Alasan {cell['alasan']}")

    # ---------- print ----------
    def _open_print(self):
        HeatmapPrintDialog(self, on_confirm=self._do_print)

    def _do_print(self, scope, outlier):
        with get_connection(DB_PATH) as conn:
            html = render_heatmap_print_html(conn, self._month, scope=scope, outlier=outlier)
        fd, path = tempfile.mkstemp(suffix=".html", prefix="heatmap_")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(html)
        open_html_in_browser(path)

    # ---------- shortcuts / cleanup ----------
    def _focus_search(self, _e=None):
        if hasattr(self, "_search") and self._search.winfo_exists():
            self._search.focus()
        return "break"

    def _on_click_outside_search(self, event):
        if not hasattr(self, "_search"):
            return
        t = event.widget
        while t is not None:
            if t is self._search:
                return
            try:
                t = t.master
            except Exception:
                break
        try:
            self.focus_set()
        except Exception:
            pass

    def _on_destroy_cleanup(self, _e=None):
        try:
            self.winfo_toplevel().unbind_all("<Control-f>")
        except Exception:
            pass
        try:
            if getattr(self, "_click_bind_id", None):
                self.winfo_toplevel().unbind("<Button-1>", self._click_bind_id)
        except Exception:
            pass
        if self._tip is not None:
            try:
                self._tip.destroy()
            except Exception:
                pass
```

- [ ] **Step 4: Run the screen tests to verify they pass**

Run: `../../../.venv/Scripts/python.exe -m pytest tests/test_heatmap_screen.py -q`
Expected: PASS (4 passed). If `find_withtag("cellrect")` count differs, confirm May 2026 has 31 days × 2 employees = 62.

- [ ] **Step 5: Commit**

```bash
git add src/ui/screens/heatmap.py tests/test_heatmap_screen.py
git commit -m "feat(v18): rewrite HeatmapScreen as in-app Canvas (sorotan, sort, attention, today, tooltip, print)"
```

---

### Task 6: Changelog wording — in-app instead of browser

**Files:**
- Modify: `src/config.py` (the v18.0.0 `APP_CHANGELOG` entry)

- [ ] **Step 1: Edit the first v18 feat tuple**

Replace the first change tuple of the `"version": "18.0.0"` entry:

```python
            ("feat", "Menu baru 'Heatmap' (grup INSIGHT): peta kehadiran bulanan "
                     "per karyawan dengan kode warna status (hadir, terlambat, "
                     "dinas, sakit, cuti, lupa absen, absen). Tampil interaktif di "
                     "browser — bisa cari/sortir nama, hover untuk detail, dan "
                     "navigasi antar bulan."),
```

with:

```python
            ("feat", "Menu baru 'Heatmap' (grup INSIGHT): peta kehadiran bulanan "
                     "per karyawan dengan kode warna status (hadir, terlambat, "
                     "dinas, sakit, cuti, lupa absen, absen). Tampil interaktif di "
                     "dalam aplikasi — cari & urutkan nama (kehadiran terendah / "
                     "paling sering telat / absen), hover & klik sel untuk detail, "
                     "navigasi antar bulan, plus panel ringkasan kehadiran "
                     "(% hadir, tepat waktu, total telat) per karyawan."),
```

- [ ] **Step 2: Run the changelog test to verify it still passes**

Run: `../../../.venv/Scripts/python.exe -m pytest tests/test_changelog_v18.py -q`
Expected: PASS (2 passed) — entry stays at top, kind `feat`, still contains "Heatmap".

- [ ] **Step 3: Commit**

```bash
git add src/config.py
git commit -m "docs(v18): changelog wording — Heatmap is in-app (not browser)"
```

---

### Task 7: Full suite green

**Files:** none (verification gate)

- [ ] **Step 1: Run the whole suite**

Run: `../../../.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: all PASS. New: `test_heatmap_helpers` (3), `test_heatmap_context_sorotan` (2), `test_heatmap_print_render` (3), `test_heatmap_screen` (4). Removed: `test_heatmap_server`. Net vs the 349 browser baseline ≈ +11 new − 1 removed, minus any old launcher-test cases replaced.

- [ ] **Step 2: If anything fails, fix it before proceeding.** Common suspects: a stale import of `src.web` (Task 4 grep), or a screen test count mismatch (verify days-in-month × employees).

- [ ] **Step 3: No commit** (verification only). If fixes were needed, commit them with `fix(v18): …`.

---

### Task 8: Release — build installer, rotate prod, copy to Installers/ (PUSH HELD)

**Files:** build artifacts only. `APP_VERSION` stays `18.0.0` (never pushed).

- [ ] **Step 1: Confirm the exe is not running**

PowerShell: `if (Get-Process -Name "HR-Absensi" -ErrorAction SilentlyContinue) { "RUNNING" } else { "not running" }`
Expected: `not running` (if running, stop it before rotating).

- [ ] **Step 2: Build the installer**

Run (Git Bash): `export PATH="/c/Program Files (x86)/Inno Setup 6:$PATH" && ../../../.venv/Scripts/python.exe -m tools.build_installer`
Expected: ends with `installer/Output/HR-Absensi-Setup-v18.0.0.exe` built. Verify the frozen bundle still includes `heatmap_print.html.j2` and NO `heatmap.html.j2`:
`ls dist/HR-Absensi/_internal/src/reports/templates/ | grep heatmap` → only `heatmap_print.html.j2`.

- [ ] **Step 3: Rotate production exe (2-level, never touch `data/`)**

```bash
PROD="D:/Gawe/Project X/HR App/dist/HR-Absensi"
NEW="D:/Gawe/Project X/HR App/.claude/worktrees/inspiring-dhawan-47161f/dist/HR-Absensi"
rm -f "$PROD/HR-Absensi.exe.bak.old"; rm -rf "$PROD/_internal.bak.old"
mv "$PROD/HR-Absensi.exe.bak" "$PROD/HR-Absensi.exe.bak.old"; mv "$PROD/_internal.bak" "$PROD/_internal.bak.old"
mv "$PROD/HR-Absensi.exe" "$PROD/HR-Absensi.exe.bak"; mv "$PROD/_internal" "$PROD/_internal.bak"
cp "$NEW/HR-Absensi.exe" "$PROD/HR-Absensi.exe"; cp -r "$NEW/_internal" "$PROD/_internal"
```

- [ ] **Step 4: Copy installer to the canonical pickup point**

```bash
cp "installer/Output/HR-Absensi-Setup-v18.0.0.exe" "D:/Gawe/Project X/HR App/Installers/HR-Absensi-Setup-v18.0.0.exe"
```

- [ ] **Step 5: STOP — hold the push.** Report to the user: in-app v18 built, installer at `Installers/HR-Absensi-Setup-v18.0.0.exe`, prod rotated, push HELD pending smoke + explicit authorization. Do NOT `git push`.

---

## Self-Review

**Spec coverage (§ → task):**
- §2 taxonomy / §3 cell_status — unchanged, already implemented (covered by existing tests; Task 7 keeps them green).
- §4 settings — done previously; no task needed.
- §5 sorotan (+ hk, pct_color), today_day, needs_attention, sort_employees — **Tasks 1, 2**.
- §6/§8 print render (server-free) — **Task 3**; temp-file + browser open — **Task 5** `_do_print`.
- §7 in-app screen (toolbar+search+sort+nav, legend, detail strip, Canvas cards, sorotan, ringkasan, attention accent, today outline, hover tooltip, click→strip, Ctrl+F, empty/no-match) — **Task 5**.
- §9 sidebar + router — already wired (no change). `HeatmapScreen` rewritten — Task 5.
- §10 changelog wording + version — **Task 6**; release — **Task 8**.
- §11 testing — Tasks 1–5 tests; server test removed — Task 4. §13 file removals — Task 4.
- §16 quick-wins (sort/attention/today) — Tasks 1, 2, 5.

**Placeholder scan:** none — every step has concrete code/commands.

**Type/name consistency:** `sorotan` keys (`hk, work_days, pct_hadir, pct_color, ontime_days, telat_total, telat_days, dinas, sakit`) defined in Task 2 are exactly those read in Task 5 paint + Task 1 `sort_employees`. `_SORT_OPTIONS` labels match the `_on_sort` test in Task 5. `render_heatmap_print_html(conn, year_month, *, scope, outlier)` signature matches its Task 3 test and Task 5 caller. `HeatmapPrintDialog(parent, on_confirm)` with `on_confirm(scope, outlier)` matches the real component. Canvas tag `"cellrect"` asserted in the Task 5 test is applied in `_paint_card`.

**Note for executor:** the screen smoke tests are slow (real widget construction). After Task 5, run the full suite (Task 7) in the background / with a generous timeout — and remember every test that calls a screen `_save`-style modal must patch `messagebox` (the heatmap screen has no save modal, so this is N/A here, but keep it in mind if adding cases).
