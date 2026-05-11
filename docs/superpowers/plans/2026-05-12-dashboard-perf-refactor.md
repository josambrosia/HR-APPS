# Dashboard Performance Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate the 1-2 second lag when switching periods on the Dashboard by replacing destroy-rebuild widget patterns with `ttk.Treeview` (for Ranking Lengkap) and a preallocated widget pool (for the 5 small left panels).

**Architecture:** Hybrid. Ranking Lengkap (largest contributor, ~30+ rows) migrates from `CTkScrollableFrame` to `ttk.Treeview`, mirroring the proven pattern in [src/ui/screens/issues.py](../../../src/ui/screens/issues.py). The 5 small panels (Top 5 Late, Top 5 Teladan, Coaching, Dept, Hari Rawan) keep their CTk styling but use preallocated row widgets — tab switch only calls `.configure(text=...)` + `pack/pack_forget`, never destroy/create.

**Tech Stack:** Python 3.13, customtkinter, tkinter.ttk (Treeview), pytest (regression only).

---

## Source Spec

[docs/superpowers/specs/2026-05-12-dashboard-perf-refactor-design.md](../specs/2026-05-12-dashboard-perf-refactor-design.md) — approved 2026-05-12.

---

## File Structure

| File | Action | Why |
|---|---|---|
| `src/ui/screens/dashboard.py` | Modify (substantial) | All work lives here |

No other files affected. No new tests created (per spec Section 9 — UI internal refactor; data layer untouched; verification via `pytest -q` regression + manual smoke).

---

## Why No New Unit Tests

Per spec Section 9 explicitly: tkinter widget rendering is notoriously hard to unit test, and this refactor doesn't touch any data layer code. Verification mechanism:

1. **Regression:** `pytest -q` after each task — all 69 existing tests must pass (catches accidental import errors, signature changes).
2. **Manual smoke test:** mandatory end-to-end before final commit (spec Section 9, 9 checkpoints).

Engineers: do NOT add unit tests for the UI changes. If you notice a data-layer bug while working, file it separately rather than expanding scope.

---

## Task 1: Migrate Ranking Lengkap to `ttk.Treeview`

**Files:**
- Modify: `src/ui/screens/dashboard.py`

**Goal of this task:** Replace the right-column `CTkScrollableFrame` + per-row custom `CTkFrame`/`CTkLabel` with a native `ttk.Treeview`. Largest single perf win (~180 widgets per switch eliminated).

- [ ] **Step 1: Add `tkinter.ttk` import**

In `src/ui/screens/dashboard.py`, locate the imports block at the top (lines 1-21). Add this import after `from tkinter import messagebox`:

```python
from tkinter import ttk
```

Final top-of-file should include:
```python
import customtkinter as ctk
from tkinter import messagebox
from tkinter import ttk
```

- [ ] **Step 2: Add `_setup_treeview_style()` method**

In the `DashboardScreen` class, add this method anywhere between `__init__` and `_build_header` (e.g., right after `__init__`):

```python
def _setup_treeview_style(self):
    style = ttk.Style()
    try:
        style.theme_use("clam")
    except Exception:
        pass
    style.configure(
        "Ranking.Treeview",
        background=COLOR_PANEL, fieldbackground=COLOR_PANEL,
        foreground=COLOR_TEXT, rowheight=24, borderwidth=0,
    )
    style.configure(
        "Ranking.Treeview.Heading",
        background="#2C1B47", foreground=COLOR_TEXT_DIM,
        relief="flat", font=(FONT_FAMILY, 10, "bold"),
    )
```

- [ ] **Step 3: Call `_setup_treeview_style()` in `__init__`**

In `DashboardScreen.__init__`, add the call right before `self._build_header()` (around line 60):

```python
self._setup_treeview_style()
self._build_header()
```

- [ ] **Step 4: Replace Ranking right column construction**

In `_build_static_widgets()`, locate the "RIGHT: Ranking Lengkap" block (lines 172-186 in current file):

```python
# ── RIGHT: Ranking Lengkap (tall, always scrollable) ──
rank_box = ctk.CTkFrame(self.body, fg_color=COLOR_PANEL, corner_radius=8)
rank_box.grid(row=1, column=1, sticky="nsew")
ctk.CTkLabel(rank_box, text="📋 Ranking Lengkap",
             font=(FONT_FAMILY, 13, "bold"), text_color=COLOR_TEXT
             ).pack(anchor="w", padx=12, pady=(8, 4))
hdr = ctk.CTkFrame(rank_box, fg_color="transparent")
hdr.pack(fill="x", padx=12)
for col, w in (("NAMA", 130), ("DEPT", 100), ("TERLAMBAT", 80),
               ("TELAT", 50), ("TDK HADIR", 70)):
    ctk.CTkLabel(hdr, text=col, font=(FONT_FAMILY, 10, "bold"),
                 text_color=COLOR_TEXT_DIM, width=w, anchor="w"
                 ).pack(side="left")
self._rank_inner = ctk.CTkScrollableFrame(rank_box, fg_color="transparent")
self._rank_inner.pack(fill="both", expand=True, padx=12, pady=4)
```

Replace the entire block with:

```python
# ── RIGHT: Ranking Lengkap (ttk.Treeview — native, scrollable) ──
rank_box = ctk.CTkFrame(self.body, fg_color=COLOR_PANEL, corner_radius=8)
rank_box.grid(row=1, column=1, sticky="nsew")
ctk.CTkLabel(rank_box, text="📋 Ranking Lengkap",
             font=(FONT_FAMILY, 13, "bold"), text_color=COLOR_TEXT
             ).pack(anchor="w", padx=12, pady=(8, 4))

cols = ["nama", "dept", "terlambat", "telat", "tidak_hadir"]
widths = {"nama": 130, "dept": 100, "terlambat": 80,
          "telat": 50, "tidak_hadir": 70}
labels = {"nama": "Nama", "dept": "Dept", "terlambat": "Terlambat",
          "telat": "Telat", "tidak_hadir": "Tdk Hadir"}

self.rank_tree = ttk.Treeview(
    rank_box, columns=cols, show="headings",
    style="Ranking.Treeview", selectmode="none",
)
for c in cols:
    self.rank_tree.heading(c, text=labels[c])
    self.rank_tree.column(c, width=widths[c], anchor="w")
self.rank_tree.pack(fill="both", expand=True, padx=12, pady=(4, 8))
```

- [ ] **Step 5: Remove `_rank_inner` attribute declaration in `__init__`**

In `__init__`, remove this line (around line 58):

```python
self._rank_inner: ctk.CTkScrollableFrame | None = None
```

It is now superseded by `self.rank_tree`.

- [ ] **Step 6: Update Ranking population in `_update_data()`**

In `_update_data()`, locate the Ranking Lengkap block (lines 367-382 in current file):

```python
# ── Ranking Lengkap (right) ──
# Inner scrollable container is preserved; only rebuild its rows
for w in self._rank_inner.winfo_children():
    w.destroy()
for r in data["ranking"]:
    row = ctk.CTkFrame(self._rank_inner, fg_color="transparent")
    row.pack(fill="x", pady=1)
    for val, w in (
        (r["nama"], 130), (r["dept"] or "-", 100),
        (f"{r['total_terlambat']} mnt", 80),
        (str(r["hari_telat"]), 50),
        (str(r["tidak_hadir"]), 70),
    ):
        ctk.CTkLabel(row, text=val, font=(FONT_FAMILY, 11),
                     text_color=COLOR_TEXT, width=w, anchor="w"
                     ).pack(side="left")
```

Replace with:

```python
# ── Ranking Lengkap (right) — Treeview ──
self.rank_tree.delete(*self.rank_tree.get_children())
for r in data["ranking"]:
    self.rank_tree.insert("", "end", values=(
        r["nama"], r["dept"] or "-",
        f"{r['total_terlambat']} mnt",
        r["hari_telat"], r["tidak_hadir"],
    ))
```

- [ ] **Step 7: Run pytest — regression check**

Run:
```
.venv/Scripts/python.exe -m pytest -q
```

Expected: **69 passed, 0 failed** (or whatever the current baseline is — must match pre-task count).

If anything fails: the import or attribute change likely broke something. Check the failure message before proceeding.

- [ ] **Step 8: Manual smoke test — Ranking renders**

Run:
```
.venv/Scripts/python.exe -m src.main
```

Verify:
1. App opens to Dashboard
2. Ranking Lengkap on the right shows employee rows with 5 columns (Nama, Dept, Terlambat, Telat, Tdk Hadir)
3. Treeview headers are styled (purple-ish background `#2C1B47`, dim text)
4. Switching tabs (Semua / Minggu 1 / etc.) updates Ranking content correctly
5. No visual glitches (header overlap, missing columns, etc.)

Close the app.

- [ ] **Step 9: Commit Task 1**

```
git add src/ui/screens/dashboard.py
git commit -m "$(cat <<'EOF'
perf(dashboard): migrate Ranking Lengkap from CTkScrollableFrame to ttk.Treeview

Eliminates ~180 CTkLabel/CTkFrame creations per tab switch (the largest
contributor to the 1-2s lag). Mirrors the proven Treeview pattern from
issues.py with a Ranking.Treeview style matching the dashboard panel.

Part 1 of 3 in dashboard perf refactor — see spec
docs/superpowers/specs/2026-05-12-dashboard-perf-refactor-design.md

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Widget Pool for 5 Small Left Panels

**Files:**
- Modify: `src/ui/screens/dashboard.py`

**Goal of this task:** Preallocate row widgets once at build time. Tab switch only calls `.configure(text=...)` + `pack/pack_forget`. Eliminates remaining ~90 widget creations per switch.

- [ ] **Step 1: Add pool state dicts to `__init__`**

In `DashboardScreen.__init__`, after the existing `self._panel_boxes` line (around line 57), add:

```python
self._panel_rows: dict[str, list[dict]] = {}   # panel_key -> [{"frame", "left", "right"}, ...]
self._panel_empty: dict[str, ctk.CTkLabel] = {}  # panel_key -> empty-state label
```

- [ ] **Step 2: Add `_make_pool_row()` and `_build_panel_pool()` helpers**

Add these methods to the `DashboardScreen` class. A good location is right after `_build_static_widgets()` and before `_period_range()`:

```python
def _make_pool_row(self, panel_key: str) -> dict:
    """Create one pool row (frame + left/right labels). Created hidden — packed by _populate_pool."""
    parent = self._panel_content[panel_key]
    frame = ctk.CTkFrame(parent, fg_color="transparent")
    left = ctk.CTkLabel(frame, text="", font=(FONT_FAMILY, 11),
                         text_color=COLOR_TEXT, anchor="w")
    right = ctk.CTkLabel(frame, text="", font=(FONT_FAMILY, 11),
                          text_color=COLOR_TEXT, anchor="e")
    left.pack(side="left")
    right.pack(side="right")
    return {"frame": frame, "left": left, "right": right}

def _build_panel_pool(self, panel_key: str, size: int, empty_text: str) -> None:
    """Pre-create row pool + empty-state label for a panel."""
    parent = self._panel_content[panel_key]
    self._panel_empty[panel_key] = ctk.CTkLabel(
        parent, text=empty_text, text_color=COLOR_TEXT_DIM,
        font=(FONT_FAMILY, 11),
    )
    self._panel_rows[panel_key] = [
        self._make_pool_row(panel_key) for _ in range(size)
    ]
```

- [ ] **Step 3: Add `_populate_pool()` helper**

Add this method right below `_build_panel_pool` (in the same location):

```python
def _populate_pool(self, panel_key: str, items: list, formatter) -> None:
    """Reconfigure pool to show `items`. formatter(item) -> (left_text, right_text, right_color)."""
    rows = self._panel_rows[panel_key]
    empty_lbl = self._panel_empty[panel_key]

    # Hide everything first to guarantee correct stack order
    empty_lbl.pack_forget()
    for r in rows:
        r["frame"].pack_forget()

    if not items:
        empty_lbl.pack(padx=8, pady=4)
        return

    # Auto-grow pool if dataset exceeds preallocated size (rare)
    while len(rows) < len(items):
        rows.append(self._make_pool_row(panel_key))

    # Pack visible rows in order, with text + color updated
    for i, item in enumerate(items):
        lt, rt, rc = formatter(item)
        rows[i]["left"].configure(text=lt)
        rows[i]["right"].configure(text=rt, text_color=rc)
        rows[i]["frame"].pack(fill="x", padx=6, pady=1)
```

- [ ] **Step 4: Simplify `make_panel()` (drop `scrollable` param)**

In `_build_static_widgets()`, locate the nested `make_panel()` function (lines 130-153):

```python
def make_panel(parent, title, color, panel_key, fixed_height,
               scrollable):
    box = ctk.CTkFrame(parent, fg_color=COLOR_PANEL, corner_radius=8,
                        height=fixed_height)
    box.grid_propagate(False)
    box.grid_columnconfigure(0, weight=1)
    box.grid_rowconfigure(1, weight=1)
    title_lbl = ctk.CTkLabel(
        box, text=title, font=(FONT_FAMILY, 12, "bold"),
        text_color=color,
    )
    title_lbl.grid(row=0, column=0, sticky="w", padx=10, pady=(8, 4))
    self._panel_titles[panel_key] = title_lbl

    if scrollable:
        content = ctk.CTkScrollableFrame(
            box, fg_color="transparent", corner_radius=0,
        )
    else:
        content = ctk.CTkFrame(box, fg_color="transparent")
    content.grid(row=1, column=0, sticky="nsew", padx=4, pady=(0, 6))
    self._panel_content[panel_key] = content
    self._panel_boxes[panel_key] = box
    return box
```

Replace with:

```python
def make_panel(parent, title, color, panel_key, fixed_height):
    box = ctk.CTkFrame(parent, fg_color=COLOR_PANEL, corner_radius=8,
                        height=fixed_height)
    box.grid_propagate(False)
    box.grid_columnconfigure(0, weight=1)
    box.grid_rowconfigure(1, weight=1)
    title_lbl = ctk.CTkLabel(
        box, text=title, font=(FONT_FAMILY, 12, "bold"),
        text_color=color,
    )
    title_lbl.grid(row=0, column=0, sticky="w", padx=10, pady=(8, 4))
    self._panel_titles[panel_key] = title_lbl

    content = ctk.CTkFrame(box, fg_color="transparent")
    content.grid(row=1, column=0, sticky="nsew", padx=4, pady=(0, 6))
    self._panel_content[panel_key] = content
    self._panel_boxes[panel_key] = box
    return box
```

- [ ] **Step 5: Update `make_panel` call sites (drop `scrollable=False`)**

Right below the function definition (lines 155-168), update all 5 calls:

```python
# Top 5 panels — bounded, non-scrollable
make_panel(left, "🔥 Top 5 Terlambat", COLOR_ACCENT,
           "late", self.PANEL_H_REGULAR, scrollable=False)
make_panel(left, "🏆 Top 5 Teladan", COLOR_OK,
           "teladan", self.PANEL_H_REGULAR, scrollable=False)
make_panel(left, "⚠ Butuh Coaching", COLOR_WARN,
           "coaching", self.PANEL_H_COACH, scrollable=False)
make_panel(left, "🏢 Ranking Departemen", COLOR_ACCENT,
           "dept", self.PANEL_H_REGULAR, scrollable=False)
make_panel(left, "📅 Hari Paling Rawan", COLOR_WARN,
           "hari", self.PANEL_H_HARI, scrollable=False)
```

Becomes:

```python
# Top 5 panels — bounded
make_panel(left, "🔥 Top 5 Terlambat", COLOR_ACCENT,
           "late", self.PANEL_H_REGULAR)
make_panel(left, "🏆 Top 5 Teladan", COLOR_OK,
           "teladan", self.PANEL_H_REGULAR)
make_panel(left, "⚠ Butuh Coaching", COLOR_WARN,
           "coaching", self.PANEL_H_COACH)
make_panel(left, "🏢 Ranking Departemen", COLOR_ACCENT,
           "dept", self.PANEL_H_REGULAR)
make_panel(left, "📅 Hari Paling Rawan", COLOR_WARN,
           "hari", self.PANEL_H_HARI)
```

- [ ] **Step 6: Pre-build pools after the `make_panel` calls**

Immediately after the last `make_panel` call (Hari Paling Rawan) and before the comment "Initial grid positions set by _apply_layout() in _update_data()", insert:

```python
# Pre-build widget pools for each panel (eliminates destroy/rebuild on tab switch)
self._build_panel_pool("late", size=5, empty_text="Tidak ada keterlambatan.")
self._build_panel_pool("teladan", size=5, empty_text="Belum ada data.")
self._build_panel_pool("coaching", size=20, empty_text="Tidak ada. ✓")
self._build_panel_pool("dept", size=8, empty_text="Belum ada data.")
self._build_panel_pool("hari", size=7, empty_text="Belum ada data harian.")
```

- [ ] **Step 7: Refactor Top 5 Late section in `_update_data()`**

In `_update_data()`, locate the Top 5 Late block (lines 314-322):

```python
# ── Top 5 Late ──
self._clear_panel("late")
content = self._panel_content["late"]
if not data["top5_late"]:
    self._empty(content, "Tidak ada keterlambatan.")
else:
    for r in data["top5_late"]:
        self._two_col_row(content, r["nama"],
                          f"{r['total_terlambat']} mnt", COLOR_ACCENT)
```

Replace with:

```python
# ── Top 5 Late ──
self._populate_pool(
    "late", data["top5_late"],
    lambda r: (r["nama"], f"{r['total_terlambat']} mnt", COLOR_ACCENT),
)
```

- [ ] **Step 8: Refactor Top 5 Teladan section (medals + index)**

Locate the Top 5 Teladan block (lines 324-333):

```python
# ── Top 5 Teladan ──
self._clear_panel("teladan")
content = self._panel_content["teladan"]
if not data["top5_teladan"]:
    self._empty(content, "Belum ada data.")
else:
    medals = ["🥇", "🥈", "🥉", "4.", "5."]
    for idx, r in enumerate(data["top5_teladan"]):
        self._two_col_row(content, f"{medals[idx]} {r['nama']}",
                          f"skor {r['score']}", COLOR_OK)
```

Replace with:

```python
# ── Top 5 Teladan (medals require index → wrap with enumerate) ──
medals = ["🥇", "🥈", "🥉", "4.", "5."]
teladan_indexed = list(enumerate(data["top5_teladan"]))
self._populate_pool(
    "teladan", teladan_indexed,
    lambda iv: (f"{medals[iv[0]]} {iv[1]['nama']}",
                f"skor {iv[1]['score']}", COLOR_OK),
)
```

- [ ] **Step 9: Refactor Coaching section**

Locate the Coaching block (lines 335-343):

```python
# ── Coaching ──
self._clear_panel("coaching")
content = self._panel_content["coaching"]
if not data["coaching"]:
    self._empty(content, "Tidak ada. ✓")
else:
    for r in data["coaching"]:
        self._two_col_row(content, r["nama"],
                          f"{r['total_terlambat']} mnt", COLOR_WARN)
```

Replace with:

```python
# ── Coaching ──
self._populate_pool(
    "coaching", data["coaching"],
    lambda r: (r["nama"], f"{r['total_terlambat']} mnt", COLOR_WARN),
)
```

- [ ] **Step 10: Refactor Departemen section**

Locate the Departemen block (lines 345-354):

```python
# ── Departemen ──
self._clear_panel("dept")
content = self._panel_content["dept"]
if not data["dept_rows"]:
    self._empty(content, "Belum ada data.")
else:
    for r in data["dept_rows"]:
        self._two_col_row(content,
                          f"{r['dept']} ({r['pegawai_count']})",
                          f"{r['total_terlambat']} mnt", COLOR_ACCENT)
```

Replace with:

```python
# ── Departemen ──
self._populate_pool(
    "dept", data["dept_rows"],
    lambda r: (f"{r['dept']} ({r['pegawai_count']})",
               f"{r['total_terlambat']} mnt", COLOR_ACCENT),
)
```

- [ ] **Step 11: Refactor Hari Rawan section**

Locate the Hari Rawan block (lines 356-365):

```python
# ── Hari Rawan ──
self._clear_panel("hari")
content = self._panel_content["hari"]
if not data["day_rows"]:
    self._empty(content, "Belum ada data harian.")
else:
    for r in data["day_rows"]:
        self._two_col_row(content, r["hari"],
                          f"{r['terlambat_count']} hari telat",
                          COLOR_WARN)
```

Replace with:

```python
# ── Hari Rawan ──
self._populate_pool(
    "hari", data["day_rows"],
    lambda r: (r["hari"], f"{r['terlambat_count']} hari telat", COLOR_WARN),
)
```

- [ ] **Step 12: Run pytest — regression check**

Run:
```
.venv/Scripts/python.exe -m pytest -q
```

Expected: **69 passed, 0 failed**.

- [ ] **Step 13: Manual smoke test — perf check**

Run:
```
.venv/Scripts/python.exe -m src.main
```

Verify:
1. Dashboard opens normally (first render OK, might take ~1s due to pool preallocation — acceptable)
2. **Switch between tabs rapidly**: Semua → Minggu 1 → Minggu 2 → Minggu 3 → Semua. Each switch should feel **near-instant** (<200 ms perceptual). No visible flicker, no empty-flash.
3. Coaching panel: hidden in Bulanan view, shown in Mingguan
4. Switch to a week with no late data — empty-state messages ("Tidak ada keterlambatan.", etc.) appear correctly
5. Switch to a week with very many coaching candidates (if dataset allows >20) — auto-grow works, all rows visible
6. Top 5 Teladan: medals (🥇🥈🥉 4. 5.) appear in correct order
7. Visual styling identical to before (purple panels, orange/gold accents, font sizes)

Close the app.

- [ ] **Step 14: Commit Task 2**

```
git add src/ui/screens/dashboard.py
git commit -m "$(cat <<'EOF'
perf(dashboard): widget pool for 5 small panels (no more destroy/rebuild)

Preallocates row widgets once in _build_static_widgets, then tab switches
only reconfigure text + pack/pack_forget. Eliminates the remaining ~90
widget creations per switch. Auto-grow handles overflow for Coaching.

Pool sizes: Top 5 Late/Teladan=5, Coaching=20, Dept=8, Hari Rawan=7.
Empty-state labels preallocated per panel.

Part 2 of 3 in dashboard perf refactor — see spec
docs/superpowers/specs/2026-05-12-dashboard-perf-refactor-design.md

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Cleanup + Final Smoke Test

**Files:**
- Modify: `src/ui/screens/dashboard.py`

**Goal of this task:** Remove dead helpers, run the full Section 9 smoke test from the spec, and tag DoD complete.

- [ ] **Step 1: Remove `_clear_panel()` method**

In `dashboard.py`, locate and delete the entire method (around lines 277-281):

```python
def _clear_panel(self, panel_key):
    """Wipe row widgets inside a panel's content frame (preserve container)."""
    content = self._panel_content[panel_key]
    for w in content.winfo_children():
        w.destroy()
```

- [ ] **Step 2: Remove `_two_col_row()` method**

Locate and delete (around lines 283-289):

```python
def _two_col_row(self, parent, left_text, right_text, right_color):
    row = ctk.CTkFrame(parent, fg_color="transparent")
    row.pack(fill="x", padx=6, pady=1)
    ctk.CTkLabel(row, text=left_text, font=(FONT_FAMILY, 11),
                 text_color=COLOR_TEXT, anchor="w").pack(side="left")
    ctk.CTkLabel(row, text=right_text, font=(FONT_FAMILY, 11),
                 text_color=right_color, anchor="e").pack(side="right")
```

- [ ] **Step 3: Remove `_empty()` method**

Locate and delete (around lines 291-293):

```python
def _empty(self, parent, text):
    ctk.CTkLabel(parent, text=text, text_color=COLOR_TEXT_DIM,
                 font=(FONT_FAMILY, 11)).pack(padx=8, pady=4)
```

- [ ] **Step 4: Verify no leftover references**

Search the file for these now-removed identifiers:

Use Grep tool with pattern `_clear_panel|_two_col_row|_empty\(` in `src/ui/screens/dashboard.py`.

Expected: **0 matches**. If any match, that's a leftover call site — fix or remove.

- [ ] **Step 5: Run pytest — final regression check**

Run:
```
.venv/Scripts/python.exe -m pytest -q
```

Expected: **69 passed, 0 failed**.

- [ ] **Step 6: Full manual smoke test (spec Section 9, all 9 steps)**

Run:
```
.venv/Scripts/python.exe -m src.main
```

Execute each of these and tick mentally:

1. ✓ pytest 69 passed (already done in Step 5)
2. ✓ App opens
3. (If DB empty: import 4 minggu data dummy; otherwise use existing DB)
4. Open Dashboard
5. Switch tab Semua ↔ Minggu 1 ↔ Minggu 2 ↔ Minggu 3 — **perceptual: tab switch instant (<200 ms), no flicker**
6. Toggle Bulanan ↔ Mingguan — Coaching panel hide/show correctly
7. Period with zero data (if available) — empty state messages render in every panel
8. Click "Cetak / Export PDF" — dialog opens, generate PDF works in browser
9. Ranking Lengkap with 30+ employees — scroll smooth, header stays visible at top

Close app.

If any step fails: do NOT proceed to Step 7. Diagnose and fix in a follow-up commit before final cleanup.

- [ ] **Step 7: Commit Task 3 (cleanup)**

```
git add src/ui/screens/dashboard.py
git commit -m "$(cat <<'EOF'
chore(dashboard): remove dead helpers after pool/Treeview migration

_clear_panel, _two_col_row, _empty are no longer called — _populate_pool
and the Treeview API have replaced them entirely.

Part 3 of 3 in dashboard perf refactor — see spec
docs/superpowers/specs/2026-05-12-dashboard-perf-refactor-design.md

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 8: Verify final state**

Run:
```
git log --oneline -5
```

Expected: 3 new commits (Task 1, Task 2, Task 3) on top of the prior `9760bc8` baseline.

Run:
```
git status
```

Expected: clean working tree.

---

## Definition of Done (mirrors spec Section 10)

- [ ] `ttk.Treeview` mengganti `CTkScrollableFrame` di Ranking Lengkap
- [ ] 5 panel kiri pakai widget pool dengan empty state handling
- [ ] `_clear_panel`, `_two_col_row`, `_empty` dihapus dari `dashboard.py`
- [ ] Tab switch perceptual <200 ms (subjektif user, dikonfirmasi di smoke test)
- [ ] 69 existing tests tetap passing
- [ ] Manual smoke test pass (semua step di Task 3 Step 6)
- [ ] Tidak ada regression visual (theme tetap purple/orange, medal masih muncul, warna accent benar)
- [ ] 3 commit terpisah untuk Treeview migration, pool refactor, cleanup

---

## Notes for the Implementing Engineer

- **Do NOT push to remote.** User explicitly requires manual push approval (see project handoff spec). Stop after local commits.
- **The .exe may be running** — user often has `dist/HR-Absensi/HR-Absensi.exe` open for smoke-testing. If `pyinstaller --clean` fails with `PermissionError`, ask user to close it before retry. (This plan doesn't require rebuild — just `python -m src.main`.)
- **Line numbers in this plan reference the file state at commit `9760bc8`.** If your file has shifted due to other edits, locate by content match (e.g., "_two_col_row method") not line number.
- **If a step references "around line X"** and you can't find it: use Grep tool with a unique snippet from the code block.

---

*End of plan.*
