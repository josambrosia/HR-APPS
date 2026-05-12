# UI JTS Theme Overhaul Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Full overhaul UI dari Hybrid A (purple/orange/gold + brand di entry points) ke full JTS palette (black + magenta + violet + cyan + emerald + rose), dengan sidebar reorganization, 2 menu renames, dan polish layer di semua 8 screen.

**Architecture:** Tokens-first sweeping refresh — Phase 1 rewrite `theme.py` dengan extended palette + spacing/font scale, Phase 2-5 apply tokens ke sidebar/dashboard/screens/components, Phase 6 cleanup hardcoded literals + handoff. 8 commits sequential, masing-masing pass `pytest -q` sebelum proceed.

**Tech Stack:** Python 3.13, customtkinter, tkinter.ttk (Treeview), pytest (regression only), PyInstaller (build).

---

## Source Spec

[docs/superpowers/specs/2026-05-13-ui-jts-theme-overhaul-design.md](../specs/2026-05-13-ui-jts-theme-overhaul-design.md) — approved 2026-05-13.

---

## File Structure

### Files to CREATE
- `src/ui/screens/whatsapp_assistant.py` — renamed dari `summary.py`, full refresh dengan terminal-style output
- `src/ui/screens/active_month.py` — renamed dari `months.py`, refreshed card grid
- `docs/superpowers/specs/2026-05-14-session-handoff-v5.md` — handoff doc baru

### Files to MODIFY
| File | Phase | Scope |
|---|---|---|
| `src/ui/theme.py` | 1 | Full rewrite — new token system |
| `src/ui/app.py` | 2 | Sidebar redesign + screen key renames |
| `src/ui/screens/dashboard.py` | 3 | KPI cards, panels, Treeview, WeekNav, Cetak |
| `src/ui/components/week_nav.py` | 3 | Pill styles update |
| `src/ui/screens/issues.py` | 4a | KPI cards, reason panel, drop lavender |
| `src/ui/screens/coaching.py` | 4a | KPI, badges, drop COLOR_OK==WARN workaround |
| `src/ui/screens/import_screen.py` | 4b | Drop zone, preview |
| `src/ui/screens/export.py` | 4b | File picker, preview |
| `src/ui/screens/settings.py` | 4c | Tab nav, forms |
| `src/ui/components/print_dialog.py` | 5 | Modal refresh |
| `src/ui/components/toast.py` | 5 | Semantic borders |
| `src/ui/splash.py` | 5 | Internal hardcoded → tokens |

### Files to DELETE
- `src/ui/screens/summary.py` (after rename verified in Phase 2)
- `src/ui/screens/months.py` (after rename verified in Phase 2)

### No new tests
Per spec Section 12, no new unit tests. 97 existing must pass after every commit. Manual smoke tests mandatory at end of each phase.

---

## Workflow Conventions

**Engineer reading this plan:** You're in worktree `D:\Gawe\Project X\HR App\.claude\worktrees\nifty-jemison-706792`. The shared venv lives 3 levels up.

**Commands** (run from worktree root):
```bash
# Tests
../../../.venv/Scripts/python.exe -m pytest -q
# Expected: 97 passed

# Run app for smoke test
../../../.venv/Scripts/python.exe -m src.main
# (Close app between sessions; don't leave running while rebuilding)

# Build .exe (rare — only do at end of plan, not per commit)
../../../.venv/Scripts/pyinstaller.exe HR-Absensi.spec --clean --noconfirm
```

**Commit guidance:**
- One commit per phase (8 total). NEVER skip pytest check before commit.
- Use HEREDOC for commit message (multi-line preserved).
- Co-author line: `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>`
- **NO `git push`** — user authorizes manually.

**If pytest fails after a change:** STOP. Diagnose root cause. Do not proceed to next task. Common pitfall: import that references removed symbol.

---

## Task 1: Phase 1 — Foundation (Tokens)

**Files:**
- Modify: `src/ui/theme.py` (full rewrite)

**Goal of this task:** Replace entire content of `theme.py` with new JTS token system. Existing imports MUST still resolve (legacy aliases preserved transitionally for migration safety).

- [ ] **Step 1.1: Open and read current theme.py state for reference**

Run: Read tool on `src/ui/theme.py`. Note the current exports — every screen imports from this file. Current symbols (must still resolve after rewrite):
- `FONT_FAMILY`, `COLOR_BG`, `COLOR_PANEL`, `COLOR_ACCENT`, `COLOR_OK`, `COLOR_WARN`, `COLOR_ERR`, `COLOR_PANEL_OPEN`, `COLOR_PANEL_RESOLVED`, `COLOR_TEXT`, `COLOR_TEXT_DIM`

- [ ] **Step 1.2: Replace theme.py with new token system**

Replace the entire file content with:

```python
"""Design tokens — Josaphat Tech Solution palette + scale system.

Single source of truth untuk color, spacing, font, radius. Semua screen
harus import token dari sini — tidak ada hardcoded hex literal.

Refactor history: started purple/indigo (MVP) → adopted Hybrid A brand
(magenta at entry points only) → full JTS overhaul (2026-05-13). Lihat
docs/superpowers/specs/2026-05-13-ui-jts-theme-overhaul-design.md.
"""

# === SURFACE TIER (4 levels for hierarchy in dark UI) ===
COLOR_SIDEBAR       = "#000000"   # Pure black — sidebar (1 step darker than bg)
COLOR_BG            = "#0A0A0A"   # App background (brand black)
COLOR_SURFACE       = "#141414"   # Cards, panels (1 step lighter than bg)
COLOR_SURFACE_HIGH  = "#1F1F1F"   # Hover, active row, treeview heading

# === BORDERS (kritis untuk dark UI hierarchy) ===
COLOR_BORDER        = "#262626"   # Subtle 1px border default
COLOR_BORDER_STRONG = "#404040"   # Focused / selected outline / dashed dropzone

# === TEXT TIER (4 levels grayscale) ===
COLOR_TEXT          = "#FFFFFF"   # Primary
COLOR_TEXT_DIM      = "#A3A3A3"   # Secondary (brand tagline color)
COLOR_TEXT_MUTED    = "#737373"   # Captions, placeholders
COLOR_TEXT_DISABLED = "#525252"   # Disabled, divider labels

# === BRAND ACCENT (Magenta — JTS primary, 3 states) ===
COLOR_ACCENT        = "#EC4899"   # Primary action, active state, brand
COLOR_ACCENT_HOVER  = "#F472B6"   # Hover lighter magenta
COLOR_ACCENT_DEEP   = "#DB2777"   # Pressed darker magenta

# === SECONDARY BRAND (Violet — analogous to magenta) ===
COLOR_SECONDARY        = "#A855F7"   # Top 5 Teladan title, Settings tab indicator
COLOR_SECONDARY_HOVER  = "#C084FC"
COLOR_SECONDARY_DEEP   = "#9333EA"

# === SEMANTIC (dev-tool palette) ===
COLOR_INFO          = "#22D3EE"   # Cyan — Periode, neutral data, info toast
COLOR_SUCCESS       = "#10B981"   # Emerald — Teladan VALUE, Sudah, success
COLOR_WARN          = "#F43F5E"   # Rose — late data, Belum, warning
COLOR_ERROR         = "#DC2626"   # Red (dark) — errors, destructive

# === LEGACY ALIASES (transitional — removed in Phase 6a Commit 7) ===
COLOR_PANEL          = COLOR_SURFACE          # alias (every screen)
COLOR_OK             = COLOR_SUCCESS           # alias (was gold)
COLOR_ERR            = COLOR_ERROR             # alias
COLOR_PANEL_OPEN     = "#1F1F1F"               # Issues OPEN row tint
COLOR_PANEL_RESOLVED = "#141414"               # Issues RESOLVED row tint

# === SPACING SCALE (8pt grid) ===
SPACE_XS  = 4
SPACE_SM  = 8
SPACE_MD  = 12
SPACE_LG  = 16
SPACE_XL  = 24
SPACE_XXL = 32

# === FONT FAMILIES ===
FONT_FAMILY = "Segoe UI"
FONT_MONO   = "Consolas"

# === FONT TUPLES (drop into CTkLabel(font=...)) ===
FONT_KPI         = (FONT_FAMILY, 28, "bold")
FONT_DISPLAY     = (FONT_FAMILY, 24, "bold")
FONT_HEADING     = (FONT_FAMILY, 18, "bold")
FONT_SUBHEAD     = (FONT_FAMILY, 14, "bold")
FONT_BODY        = (FONT_FAMILY, 12)
FONT_BODY_BOLD   = (FONT_FAMILY, 12, "bold")
FONT_SMALL       = (FONT_FAMILY, 11)
FONT_LABEL       = (FONT_FAMILY, 10, "bold")

FONT_MONO_DATA   = (FONT_MONO, 12)
FONT_MONO_BRAND  = (FONT_MONO, 13, "bold")
FONT_MONO_SMALL  = (FONT_MONO, 10)

# === RADIUS ===
RADIUS_SM = 4
RADIUS_MD = 8
RADIUS_LG = 12
```

- [ ] **Step 1.3: Verify all existing imports resolve via grep**

Run: Grep tool, pattern `from src\.ui\.theme import`, output_mode `content`, type `py`.

Expected: see imports from `app.py`, `dashboard.py`, `issues.py`, etc. Cross-reference: every imported symbol in the results above must exist in your new `theme.py`.

If any symbol missing (e.g., a screen imports `COLOR_GOLD` which we don't have): either (a) add as legacy alias temporarily, or (b) note the file for Phase 6a cleanup.

- [ ] **Step 1.4: Run pytest regression check**

Run: `../../../.venv/Scripts/python.exe -m pytest -q`

Expected: `97 passed`. If anything fails, the new theme.py likely broke an import. Fix before proceeding.

- [ ] **Step 1.5: Manual smoke test — app launches without crash**

Run: `../../../.venv/Scripts/python.exe -m src.main`

Expected: app opens. Visual will look broken/inconsistent at this stage (only tokens changed, screens not yet refactored). Goal: verify NO import error, NO crash. Close app.

- [ ] **Step 1.6: Commit Phase 1**

```bash
git add src/ui/theme.py
git commit -m "$(cat <<'EOF'
feat(theme): JTS palette + spacing + font scale tokens

Foundation commit untuk UI overhaul (Phase 1/8). Replace theme.py
dengan token system: 4-tier surface, 4-tier text, magenta + violet
+ cyan + emerald + rose semantic palette, 8pt spacing scale, named
font scale dengan mono variants.

Legacy aliases (COLOR_PANEL, COLOR_OK, COLOR_PANEL_OPEN, etc.) tetap
ada transitional — akan dihapus di Phase 6a (Commit 7) setelah semua
screen migrate.

Lihat spec: docs/superpowers/specs/2026-05-13-ui-jts-theme-overhaul-design.md

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Phase 2 — Sidebar Redesign

**Files:**
- Modify: `src/ui/app.py` (extensive)
- Create: `src/ui/screens/whatsapp_assistant.py` (rename from summary.py)
- Create: `src/ui/screens/active_month.py` (rename from months.py)
- Delete: `src/ui/screens/summary.py`
- Delete: `src/ui/screens/months.py`

**Goal of this task:** Sidebar bg → pure black, width 220, refined header with subtitle, active month chip widget, custom nav items dengan active state indicator + section labels, 2 file renames, 1 icon change.

- [ ] **Step 2.1: Rename summary.py → whatsapp_assistant.py (file + class)**

```bash
git mv src/ui/screens/summary.py src/ui/screens/whatsapp_assistant.py
```

Then edit the renamed file — change class name:

In `src/ui/screens/whatsapp_assistant.py`, find `class SummaryScreen(...):` and rename to `class WhatsAppAssistantScreen(...)`. Update any internal references (likely none — class is referenced only externally).

- [ ] **Step 2.2: Rename months.py → active_month.py (file + class)**

```bash
git mv src/ui/screens/months.py src/ui/screens/active_month.py
```

Edit the renamed file — change `class MonthsScreen(...):` to `class ActiveMonthScreen(...)`.

- [ ] **Step 2.3: Update app.py screen registration keys + imports**

In `src/ui/app.py`, find `_show()` method. The dispatch currently has these elif branches:

```python
elif name == "Months":
    from src.ui.screens.months import MonthsScreen
    MonthsScreen(self.content).grid(row=0, column=0, sticky="nsew")
elif name == "Summary":
    from src.ui.screens.summary import SummaryScreen
    SummaryScreen(self.content).grid(row=0, column=0, sticky="nsew")
```

Replace with:

```python
elif name == "ActiveMonth":
    from src.ui.screens.active_month import ActiveMonthScreen
    ActiveMonthScreen(self.content).grid(row=0, column=0, sticky="nsew")
elif name == "WhatsAppAssistant":
    from src.ui.screens.whatsapp_assistant import WhatsAppAssistantScreen
    WhatsAppAssistantScreen(self.content).grid(row=0, column=0, sticky="nsew")
```

Also find `self._active_month_label.bind("<Button-1>", lambda _e: self._show("Months"))` and change `"Months"` to `"ActiveMonth"`.

- [ ] **Step 2.4: Update _build_sidebar — bg, width, padding**

In `src/ui/app.py` `_build_sidebar()`, find:

```python
self.sidebar = ctk.CTkFrame(self, width=200, corner_radius=0, fg_color=COLOR_PANEL)
```

Replace with:

```python
self.sidebar = ctk.CTkFrame(
    self, width=220, corner_radius=0, fg_color=COLOR_SIDEBAR,
    border_width=0,
)
```

Also import `COLOR_SIDEBAR` at top of `app.py`:

```python
from src.ui.theme import (
    FONT_FAMILY, FONT_MONO,
    COLOR_BG, COLOR_SIDEBAR, COLOR_SURFACE, COLOR_SURFACE_HIGH,
    COLOR_BORDER, COLOR_ACCENT, COLOR_ACCENT_HOVER,
    COLOR_TEXT, COLOR_TEXT_DIM, COLOR_TEXT_MUTED, COLOR_TEXT_DISABLED,
    SPACE_XS, SPACE_SM, SPACE_MD, SPACE_LG,
    FONT_BODY, FONT_BODY_BOLD, FONT_SMALL, FONT_LABEL,
    FONT_MONO_BRAND, FONT_MONO_SMALL,
)
```

(Keep existing `COLOR_PANEL` import temporarily if used elsewhere in the file. Phase 6a will clean.)

- [ ] **Step 2.5: Update sidebar header — subtitle + larger icon**

In `_build_sidebar()`, find the header section (icon + "HR ABSENSI" title). Replace:

```python
header_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
header_frame.pack(pady=(20, 10), fill="x", padx=8)
self._load_sidebar_icon(header_frame)
ctk.CTkLabel(header_frame, text="HR ABSENSI",
             font=(FONT_FAMILY, 16, "bold")
             ).pack(side="left", padx=(4, 0))
```

With:

```python
header_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
header_frame.pack(pady=(SPACE_LG, SPACE_MD), fill="x", padx=SPACE_LG)
self._load_sidebar_icon(header_frame)  # internal: change size to 36 in step 2.5b

title_stack = ctk.CTkFrame(header_frame, fg_color="transparent")
title_stack.pack(side="left", padx=(SPACE_SM, 0))
ctk.CTkLabel(
    title_stack, text="HR ABSENSI",
    font=(FONT_FAMILY, 14, "bold"),
    text_color=COLOR_TEXT,
).pack(anchor="w")
ctk.CTkLabel(
    title_stack, text="attendance manager",
    font=FONT_MONO_SMALL,
    text_color=COLOR_TEXT_MUTED,
).pack(anchor="w")
```

Then update `_load_sidebar_icon` — find `output_width=32, output_height=32` and change to `64, 64` (PIL resampling for crisp 36 final), then `pil.resize((32, 32)` to `pil.resize((36, 36)`. Same for the fallback path. Update `size=(32, 32)` in CTkImage to `size=(36, 36)`.

- [ ] **Step 2.6: Replace plain active-month label with chip widget**

In `_build_sidebar()`, find:

```python
self._active_month_label = ctk.CTkLabel(
    self.sidebar,
    text=self._format_active_month_label(),
    font=(FONT_FAMILY, 11, "bold"),
    text_color="#EC4899",   # brand magenta
    anchor="w",
    cursor="hand2",
)
self._active_month_label.pack(fill="x", padx=12, pady=(0, 8))
self._active_month_label.bind(
    "<Button-1>", lambda _e: self._show("Months"),
)
```

Replace with:

```python
# Active month chip — clickable card with subtle magenta tint
self._active_month_chip = ctk.CTkFrame(
    self.sidebar,
    fg_color="#27101C",  # rgba-equivalent of magenta 10% on bg
    border_width=1,
    border_color="#5A1E3A",  # rgba-equivalent of magenta 25% on bg
    corner_radius=RADIUS_MD,
    cursor="hand2",
)
self._active_month_chip.pack(fill="x", padx=SPACE_LG, pady=(0, SPACE_MD))

# Label "BULAN AKTIF" uppercase
ctk.CTkLabel(
    self._active_month_chip,
    text="BULAN AKTIF",
    font=FONT_LABEL,
    text_color=COLOR_TEXT_MUTED,
    anchor="w",
).pack(fill="x", padx=SPACE_MD, pady=(SPACE_SM, 0))

# Value (active month display)
self._active_month_label = ctk.CTkLabel(
    self._active_month_chip,
    text=self._format_active_month_label(),
    font=FONT_BODY_BOLD,
    text_color=COLOR_ACCENT_HOVER,  # lighter magenta for value text
    anchor="w",
)
self._active_month_label.pack(fill="x", padx=SPACE_MD, pady=(0, SPACE_SM))

# Make entire chip + children clickable
def _on_chip_click(_e):
    self._show("ActiveMonth")

for widget in (self._active_month_chip, self._active_month_label):
    widget.bind("<Button-1>", _on_chip_click)
```

Also import `RADIUS_MD` at top.

**Update `_format_active_month_label` format** — chip has its own "BULAN AKTIF" header, so format function should return short form (e.g., "◆ April 2026"), not redundant "◆ Aktif: April 2026":

```python
def _format_active_month_label(self) -> str:
    """Return short-form active month for chip value display."""
    try:
        from src.config import DB_PATH
        from src.db.connection import get_connection
        from src.db.settings import get_setting
        from src.core.report_generator import month_label
        with get_connection(DB_PATH) as conn:
            ym = get_setting(conn, "current_month") or ""
        if ym:
            return f"◆ {month_label(ym)}"
        return "◆ Belum diset"
    except Exception:
        return ""
```

- [ ] **Step 2.7: Replace flat nav loop with grouped sections + custom nav items**

In `_build_sidebar()`, find the nav loop (currently `nav_items = [...]` followed by `for label, screen in nav_items:`). Replace the entire block:

```python
nav_items = [
    ("📊 Dashboard", "Dashboard"),
    # ...8 items
]
for label, screen in nav_items:
    ctk.CTkButton(
        self.sidebar, text=label, anchor="w",
        command=lambda s=screen: self._show(s),
        fg_color="transparent", hover_color="#334155",
    ).pack(fill="x", padx=8, pady=2)
```

With:

```python
# Sections (label + items) — categorized navigation
nav_groups = [
    ("INSIGHT", [
        ("📊", "Dashboard", "Dashboard"),
    ]),
    ("DATA MANAGEMENT", [
        ("📥", "Import", "Import"),
        ("📤", "Export", "Export"),
        ("📆", "Active Month", "ActiveMonth"),
    ]),
    ("WORKFLOW", [
        ("🚩", "Issues", "Issues"),
        ("💬", "WhatsApp Assistant", "WhatsAppAssistant"),
        ("🎯", "Coaching", "Coaching"),
    ]),
    ("SYSTEM", [
        ("⚙", "Settings", "Settings"),
    ]),
]

self._nav_items: dict[str, ctk.CTkFrame] = {}
self._active_nav_key: str = "Dashboard"  # default starting screen

for group_label, items in nav_groups:
    # Section label
    ctk.CTkLabel(
        self.sidebar,
        text=group_label,
        font=FONT_LABEL,
        text_color=COLOR_TEXT_DISABLED,
        anchor="w",
    ).pack(fill="x", padx=SPACE_LG, pady=(SPACE_SM, SPACE_XS))

    # Nav items in group
    for icon, label, screen_key in items:
        item = self._build_nav_item(icon, label, screen_key)
        item.pack(fill="x", pady=0)
        self._nav_items[screen_key] = item
```

Then add a new method `_build_nav_item` to `HRApp`. Place it after `_build_sidebar`:

```python
def _build_nav_item(self, icon: str, label: str, screen_key: str) -> ctk.CTkFrame:
    """Custom nav item with active state indicator (3px magenta left bar).

    Frame layout: [left bar 3px] [icon + label content]
    State stored visually — when this item becomes active, left bar shows
    + bg tints. Click handled by binding on the entire frame.
    """
    frame = ctk.CTkFrame(self.sidebar, fg_color="transparent", height=36)
    frame.pack_propagate(False)

    # Left active bar — created hidden, shown when active
    left_bar = ctk.CTkFrame(
        frame, fg_color=COLOR_ACCENT, width=3, corner_radius=0,
    )
    # Pack hidden initially; activate via _set_active_nav_item

    # Inner content row (padding mimics left_bar=3 + SPACE_LG=16, total 16)
    content = ctk.CTkFrame(frame, fg_color="transparent")
    content.pack(side="left", fill="both", expand=True, padx=(SPACE_LG, SPACE_LG))

    icon_lbl = ctk.CTkLabel(
        content, text=icon, font=FONT_BODY,
        text_color=COLOR_TEXT_DIM, anchor="w", width=22,
    )
    icon_lbl.pack(side="left")

    text_lbl = ctk.CTkLabel(
        content, text=label, font=FONT_BODY,
        text_color="#C0C0C0", anchor="w",
    )
    text_lbl.pack(side="left", padx=(SPACE_SM, 0))

    # Store refs on frame for state updates
    frame._left_bar = left_bar
    frame._content = content
    frame._icon_lbl = icon_lbl
    frame._text_lbl = text_lbl
    frame._screen_key = screen_key

    # Click handler (bind on frame + children to catch all)
    def _on_click(_e):
        self._show(screen_key)

    for widget in (frame, content, icon_lbl, text_lbl):
        widget.bind("<Button-1>", _on_click)
        widget.configure(cursor="hand2")

    # Hover handlers
    def _on_enter(_e):
        if frame._screen_key != self._active_nav_key:
            frame.configure(fg_color=COLOR_SURFACE)

    def _on_leave(_e):
        if frame._screen_key != self._active_nav_key:
            frame.configure(fg_color="transparent")

    for widget in (frame, content, icon_lbl, text_lbl):
        widget.bind("<Enter>", _on_enter)
        widget.bind("<Leave>", _on_leave)

    return frame
```

- [ ] **Step 2.8: Add _set_active_nav_item method**

Add this method to `HRApp`, right below `_build_nav_item`:

```python
def _set_active_nav_item(self, screen_key: str):
    """Toggle visual active state on nav items.

    Show left magenta bar + bg tint + bold text on newly active item.
    Hide indicators on previously active item.
    """
    prev = self._nav_items.get(self._active_nav_key)
    if prev is not None:
        prev.configure(fg_color="transparent")
        prev._left_bar.pack_forget()
        prev._text_lbl.configure(text_color="#C0C0C0", font=FONT_BODY)

    new = self._nav_items.get(screen_key)
    if new is not None:
        new.configure(fg_color=COLOR_SURFACE_HIGH)
        new._left_bar.pack(side="left", fill="y", pady=SPACE_XS)
        new._text_lbl.configure(text_color=COLOR_TEXT, font=FONT_BODY_BOLD)
        self._active_nav_key = screen_key
```

- [ ] **Step 2.9: Hook _set_active_nav_item into _show**

In `_show()` method, find:

```python
def _show(self, name: str):
    # Refresh sidebar active-month indicator on every navigation
    self._refresh_active_month_label()
    # Clear current content
    for child in self.content.winfo_children():
        child.destroy()
```

Replace with:

```python
def _show(self, name: str):
    # Refresh sidebar active-month indicator on every navigation
    self._refresh_active_month_label()
    # Update sidebar nav visual state
    self._set_active_nav_item(name)
    # Clear current content
    for child in self.content.winfo_children():
        child.destroy()
```

- [ ] **Step 2.10: Update footer — remove hardcoded BRAND_MAGENTA, use token**

In `_build_sidebar()`, find the footer block. Find:

```python
BRAND_MAGENTA = "#EC4899"
```

Replace with using token (delete the line) and update references:

```python
# Brand line 2: "Solution" — magenta bold (visual accent)
if brand_line2:
    ctk.CTkLabel(
        footer, text=brand_line2,
        font=(FONT_FAMILY, 13, "bold"),
        text_color=BRAND_MAGENTA, anchor="w",
    ).pack(fill="x", pady=(0, 6))
```

Changes:
- Delete `BRAND_MAGENTA = "#EC4899"` line
- Replace `text_color=BRAND_MAGENTA` with `text_color=COLOR_ACCENT`

Also find separator:

```python
sep = ctk.CTkFrame(footer, fg_color=COLOR_TEXT_DIM, height=1)
```

Replace with:

```python
sep = ctk.CTkFrame(footer, fg_color=COLOR_BORDER, height=1)
```

Also import `COLOR_BORDER` at top.

- [ ] **Step 2.11: Update content area bg (was transparent on purple bg, now black)**

In `_build_content_area()`, find:

```python
self._content_outer = ctk.CTkScrollableFrame(
    self, fg_color="transparent", corner_radius=0,
)
```

No change to fg_color (transparent inherits app bg `COLOR_BG` which is now black). But verify by reading the method. If any hardcoded color there, replace with `"transparent"`.

- [ ] **Step 2.12: Run pytest regression**

Run: `../../../.venv/Scripts/python.exe -m pytest -q`

Expected: `97 passed`.

If fails — most likely culprit is import error in renamed screens. Check:
- `whatsapp_assistant.py` has `class WhatsAppAssistantScreen`
- `active_month.py` has `class ActiveMonthScreen`
- `app.py` imports use new names
- No leftover `summary.py` or `months.py` reference

- [ ] **Step 2.13: Manual smoke — sidebar visuals**

Run: `../../../.venv/Scripts/python.exe -m src.main`

Verify:
1. Sidebar pure black bg
2. Header "HR ABSENSI" + "attendance manager" mono subtitle
3. Active month chip dengan border + label + value
4. 4 section labels visible (INSIGHT, DATA MANAGEMENT, WORKFLOW, SYSTEM)
5. Click Dashboard — magenta left bar appears, bg tints, text bold
6. Click Issues — bar moves to Issues, Dashboard returns to inactive
7. Click "💬 WhatsApp Assistant" — renders renamed screen content
8. Click "📆 Active Month" — renders renamed screen content
9. Hover any nav item — bg tints slightly, returns on leave
10. Click active month chip — navigates to Active Month

Close app.

- [ ] **Step 2.14: Commit Phase 2**

```bash
git add src/ui/app.py src/ui/screens/whatsapp_assistant.py src/ui/screens/active_month.py
# git mv already staged the deletion of summary.py and months.py
git status  # verify deletes shown
git commit -m "$(cat <<'EOF'
feat(ui): sidebar redesign — JTS theme + 4 sections + renames

Phase 2/8 dari UI overhaul:
- Sidebar bg: COLOR_PANEL purple → COLOR_SIDEBAR pure black
- Width: 200 → 220px untuk breathing room
- Header: + mono subtitle "attendance manager"; icon size 32→36
- Active month: plain label → chip widget dengan magenta border + 2-row layout
- Nav items: custom CTkFrame dengan 3px magenta left bar + hover/active states
- Sections: 4 groups (INSIGHT/DATA MANAGEMENT/WORKFLOW/SYSTEM) — was flat 8 items
- Renames: summary.py → whatsapp_assistant.py, months.py → active_month.py
- Icon changes: ⚠→🚩 Issues, 🗓→📆 Active Month, 📋→💬 WhatsApp Assistant
- Footer: drop hardcoded BRAND_MAGENTA, use COLOR_ACCENT token

Screen dispatch keys updated: "Months"→"ActiveMonth", "Summary"→"WhatsAppAssistant".

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Phase 3 — Dashboard Polish

**Files:**
- Modify: `src/ui/screens/dashboard.py` (extensive)
- Modify: `src/ui/components/week_nav.py` (pill styles)

**Goal of this task:** Apply tokens + semantic colors + borders to KPI cards, 5 panels, Treeview, WeekNavBar pills, Cetak CTA.

- [ ] **Step 3.1: Update dashboard.py imports**

At top of `src/ui/screens/dashboard.py`, find:

```python
from src.ui.theme import (
    FONT_FAMILY, COLOR_OK, COLOR_WARN, COLOR_ACCENT, COLOR_PANEL,
    COLOR_TEXT, COLOR_TEXT_DIM,
)
```

Replace with:

```python
from src.ui.theme import (
    FONT_FAMILY, FONT_MONO,
    COLOR_BG, COLOR_SURFACE, COLOR_SURFACE_HIGH,
    COLOR_BORDER, COLOR_BORDER_STRONG,
    COLOR_ACCENT, COLOR_ACCENT_HOVER,
    COLOR_SECONDARY,
    COLOR_INFO, COLOR_SUCCESS, COLOR_WARN,
    COLOR_TEXT, COLOR_TEXT_DIM, COLOR_TEXT_MUTED, COLOR_TEXT_DISABLED,
    FONT_KPI, FONT_DISPLAY, FONT_HEADING, FONT_SUBHEAD,
    FONT_BODY, FONT_BODY_BOLD, FONT_SMALL, FONT_LABEL,
    FONT_MONO_DATA, FONT_MONO_SMALL,
    SPACE_XS, SPACE_SM, SPACE_MD, SPACE_LG, SPACE_XL,
    RADIUS_MD,
)
# Legacy alias still referenced by name in places; keep import for transition:
from src.ui.theme import COLOR_OK, COLOR_PANEL
```

- [ ] **Step 3.2: Update KPI card builder**

In `_build_static_widgets()`, find:

```python
def _kpi(parent, label_text, name, color):
    card = ctk.CTkFrame(parent, fg_color=COLOR_PANEL, corner_radius=8)
    ctk.CTkLabel(card, text=label_text.upper(),
                 font=(FONT_FAMILY, 10), text_color=COLOR_TEXT_DIM
                 ).pack(anchor="w", padx=14, pady=(12, 0))
    value_lbl = ctk.CTkLabel(
        card, text="—", font=(FONT_FAMILY, 22, "bold"),
        text_color=color,
    )
    value_lbl.pack(anchor="w", padx=14, pady=(0, 12))
    self._kpi_labels[name] = value_lbl
    return card
```

Replace with:

```python
def _kpi(parent, label_text, name, color, mono=False):
    card = ctk.CTkFrame(
        parent, fg_color=COLOR_SURFACE,
        border_width=1, border_color=COLOR_BORDER,
        corner_radius=RADIUS_MD,
    )
    ctk.CTkLabel(
        card, text=label_text.upper(),
        font=FONT_LABEL, text_color=COLOR_TEXT_MUTED,
    ).pack(anchor="w", padx=SPACE_LG, pady=(SPACE_MD, 0))
    value_lbl = ctk.CTkLabel(
        card, text="—",
        font=(FONT_MONO, 24, "bold") if mono else (FONT_FAMILY, 17, "bold"),
        text_color=color,
    )
    value_lbl.pack(anchor="w", padx=SPACE_LG, pady=(0, SPACE_MD))
    self._kpi_labels[name] = value_lbl
    return card
```

Then update the three KPI calls below:

```python
_kpi(kpi_frame, "Periode", "periode", COLOR_TEXT).grid(...)
_kpi(kpi_frame, "Total Terlambat", "total_terlambat", COLOR_ACCENT).grid(...)
_kpi(kpi_frame, "Coaching Flag", "coaching_count", COLOR_WARN).grid(...)
```

Replace with:

```python
_kpi(kpi_frame, "Periode", "periode", COLOR_INFO, mono=False).grid(
    row=0, column=0, padx=SPACE_XS, sticky="ew")
_kpi(kpi_frame, "Total Terlambat", "total_terlambat", COLOR_WARN, mono=True).grid(
    row=0, column=1, padx=SPACE_XS, sticky="ew")
_kpi(kpi_frame, "Coaching Flag", "coaching_count", COLOR_WARN, mono=True).grid(
    row=0, column=2, padx=SPACE_XS, sticky="ew")
```

- [ ] **Step 3.3: Update panel maker to add borders**

In `_build_static_widgets()`, find the `make_panel` function:

```python
def make_panel(parent, title, color, panel_key, fixed_height):
    box = ctk.CTkFrame(parent, fg_color=COLOR_PANEL, corner_radius=8,
                        height=fixed_height)
    box.grid_propagate(False)
    # ... etc
```

Replace with:

```python
def make_panel(parent, title, color, panel_key, fixed_height):
    box = ctk.CTkFrame(
        parent, fg_color=COLOR_SURFACE,
        border_width=1, border_color=COLOR_BORDER,
        corner_radius=RADIUS_MD,
        height=fixed_height,
    )
    box.grid_propagate(False)
    box.grid_columnconfigure(0, weight=1)
    box.grid_rowconfigure(1, weight=1)
    title_lbl = ctk.CTkLabel(
        box, text=title,
        font=FONT_SUBHEAD,
        text_color=color,
    )
    title_lbl.grid(row=0, column=0, sticky="w", padx=SPACE_MD, pady=(SPACE_SM, SPACE_XS))
    self._panel_titles[panel_key] = title_lbl

    content = ctk.CTkFrame(box, fg_color="transparent")
    content.grid(row=1, column=0, sticky="nsew", padx=SPACE_XS, pady=(0, SPACE_SM))
    self._panel_content[panel_key] = content
    self._panel_boxes[panel_key] = box
    return box
```

- [ ] **Step 3.4: Update make_panel call sites — title colors per role**

Find the 5 make_panel calls. Update colors:

```python
make_panel(left, "🔥 Top 5 Terlambat", COLOR_ACCENT, ...)
make_panel(left, "🏆 Top 5 Teladan", COLOR_OK, ...)
make_panel(left, "⚠ Butuh Coaching", COLOR_WARN, ...)
make_panel(left, "🏢 Ranking Departemen", COLOR_ACCENT, ...)
make_panel(left, "📅 Hari Paling Rawan", COLOR_WARN, ...)
```

Replace with:

```python
make_panel(left, "🔥 Top 5 Terlambat", COLOR_TEXT,
           "late", self.PANEL_H_REGULAR)
make_panel(left, "🏆 Top 5 Teladan", COLOR_SECONDARY,
           "teladan", self.PANEL_H_REGULAR)
make_panel(left, "⚠ Butuh Coaching", COLOR_WARN,
           "coaching", self.PANEL_H_COACH)
make_panel(left, "🏢 Ranking Departemen", COLOR_TEXT,
           "dept", self.PANEL_H_REGULAR)
make_panel(left, "📅 Hari Paling Rawan", COLOR_TEXT,
           "hari", self.PANEL_H_HARI)
```

- [ ] **Step 3.5: Update _make_pool_row — mono value + better divider**

Find `_make_pool_row`:

```python
def _make_pool_row(self, panel_key: str) -> dict:
    parent = self._panel_content[panel_key]
    frame = ctk.CTkFrame(parent, fg_color="transparent")
    left = ctk.CTkLabel(frame, text="", font=(FONT_FAMILY, 11),
                         text_color=COLOR_TEXT, anchor="w")
    right = ctk.CTkLabel(frame, text="", font=(FONT_FAMILY, 11),
                          text_color=COLOR_TEXT, anchor="e")
    left.pack(side="left")
    right.pack(side="right")
    return {"frame": frame, "left": left, "right": right}
```

Replace with:

```python
def _make_pool_row(self, panel_key: str) -> dict:
    parent = self._panel_content[panel_key]
    frame = ctk.CTkFrame(parent, fg_color="transparent", height=22)
    frame.pack_propagate(False)
    left = ctk.CTkLabel(
        frame, text="", font=FONT_SMALL,
        text_color=COLOR_TEXT, anchor="w",
    )
    right = ctk.CTkLabel(
        frame, text="", font=FONT_MONO_DATA,
        text_color=COLOR_TEXT, anchor="e",
    )
    left.pack(side="left", padx=(SPACE_SM, 0))
    right.pack(side="right", padx=(0, SPACE_SM))

    # Hover handlers — subtle bg tint
    def _on_enter(_e):
        frame.configure(fg_color=COLOR_SURFACE_HIGH)

    def _on_leave(_e):
        frame.configure(fg_color="transparent")

    for w in (frame, left, right):
        w.bind("<Enter>", _on_enter)
        w.bind("<Leave>", _on_leave)

    return {"frame": frame, "left": left, "right": right}
```

- [ ] **Step 3.6: Update Teladan medal accent in _update_data**

In `_update_data()`, find the Teladan section:

```python
medals = ["🥇", "🥈", "🥉", "4.", "5."]
teladan_indexed = list(enumerate(data["top5_teladan"]))
self._populate_pool(
    "teladan", teladan_indexed,
    lambda iv: (f"{medals[iv[0]]} {iv[1]['nama']}",
                f"skor {iv[1]['score']}", COLOR_OK),
)
```

The medal text in cols 4 and 5 should be magenta accent. Update by formatting differently. Since the pool row's left label is single text, we can't color part of it differently via the current API. Acceptable compromise: keep medal in label, use `COLOR_SUCCESS` (emerald) for value, accept text uniform color. If you want medal magenta — would need pool row redesign (3-segment instead of 2). Defer to future improvement.

So just update value color from `COLOR_OK` → `COLOR_SUCCESS`:

```python
medals = ["🥇", "🥈", "🥉", "4.", "5."]
teladan_indexed = list(enumerate(data["top5_teladan"]))
self._populate_pool(
    "teladan", teladan_indexed,
    lambda iv: (f"{medals[iv[0]]} {iv[1]['nama']}",
                f"skor {iv[1]['score']}", COLOR_SUCCESS),
)
```

- [ ] **Step 3.7: Update Top 5 Late and Coaching value colors → COLOR_WARN**

In `_update_data()`, the Top 5 Late and Coaching blocks already pass COLOR_ACCENT (old orange) and COLOR_WARN (old gold). Update:

Top 5 Late:
```python
# Before
lambda r: (r["nama"], f"{r['total_terlambat']} mnt", COLOR_ACCENT),
# After
lambda r: (r["nama"], f"{r['total_terlambat']} mnt", COLOR_WARN),
```

Coaching: already uses COLOR_WARN — no change.

Dept ranking value color:
```python
# Before
lambda r: (f"{r['dept']} ({r['pegawai_count']})",
           f"{r['total_terlambat']} mnt", COLOR_ACCENT),
# After
lambda r: (f"{r['dept']} ({r['pegawai_count']})",
           f"{r['total_terlambat']} mnt", COLOR_WARN),
```

Hari Rawan: already uses COLOR_WARN — no change.

- [ ] **Step 3.8: Update Treeview style**

Find `_setup_treeview_style`:

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

Replace with:

```python
def _setup_treeview_style(self):
    style = ttk.Style()
    try:
        style.theme_use("clam")
    except Exception:
        pass
    style.configure(
        "Ranking.Treeview",
        background=COLOR_SURFACE,
        fieldbackground=COLOR_SURFACE,
        foreground=COLOR_TEXT,
        rowheight=24,
        borderwidth=0,
        font=FONT_SMALL,
    )
    style.configure(
        "Ranking.Treeview.Heading",
        background=COLOR_SURFACE_HIGH,
        foreground=COLOR_TEXT_MUTED,
        relief="flat",
        font=(FONT_FAMILY, 9, "bold"),
    )
    style.map(
        "Ranking.Treeview",
        background=[("selected", COLOR_SURFACE_HIGH)],
        foreground=[("selected", COLOR_TEXT)],
    )
```

- [ ] **Step 3.9: Update Ranking Lengkap card border + heading label color**

Find the Ranking Lengkap section in `_build_static_widgets()`:

```python
rank_box = ctk.CTkFrame(self.body, fg_color=COLOR_PANEL, corner_radius=8)
rank_box.grid(row=1, column=1, sticky="nsew")
ctk.CTkLabel(rank_box, text="📋 Ranking Lengkap",
             font=(FONT_FAMILY, 13, "bold"), text_color=COLOR_TEXT
             ).pack(anchor="w", padx=12, pady=(8, 4))
```

Replace with:

```python
rank_box = ctk.CTkFrame(
    self.body, fg_color=COLOR_SURFACE,
    border_width=1, border_color=COLOR_BORDER,
    corner_radius=RADIUS_MD,
)
rank_box.grid(row=1, column=1, sticky="nsew")
ctk.CTkLabel(
    rank_box, text="📋 Ranking Lengkap",
    font=FONT_SUBHEAD,
    text_color=COLOR_TEXT,
).pack(anchor="w", padx=SPACE_MD, pady=(SPACE_SM, SPACE_XS))
```

- [ ] **Step 3.10: Update header — title + micro-label + Cetak CTA**

In `_build_header()`, find:

```python
ctk.CTkLabel(
    header, text="Dashboard", font=(FONT_FAMILY, 24, "bold"),
    text_color=COLOR_TEXT,
).pack(side="left", padx=(0, 16))
```

Add micro-label after it. Replace whole block with:

```python
ctk.CTkLabel(
    header, text="Dashboard",
    font=FONT_DISPLAY,
    text_color=COLOR_TEXT,
).pack(side="left", padx=(0, 0))

ctk.CTkLabel(
    header, text="/ insights",
    font=FONT_MONO_SMALL,
    text_color=COLOR_TEXT_DISABLED,
).pack(side="left", padx=(SPACE_SM, SPACE_LG), pady=(SPACE_SM, 0))
```

Find Cetak button:

```python
ctk.CTkButton(
    header, text="📄 Cetak / Export PDF",
    fg_color=COLOR_OK, text_color="#1E104E",
    command=self._on_print,
).pack(side="right", padx=(8, 0))
```

Replace with:

```python
ctk.CTkButton(
    header, text="📄 Cetak / Export PDF",
    fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER,
    text_color=COLOR_BG,
    font=FONT_BODY_BOLD,
    command=self._on_print,
).pack(side="right", padx=(SPACE_SM, 0))
```

- [ ] **Step 3.11: Update week_nav.py pill styles**

Open `src/ui/components/week_nav.py`. Read it. Find where active/inactive pills are styled. Common pattern:

```python
# Active
button.configure(fg_color=COLOR_ACCENT, text_color=...)
# Inactive
button.configure(fg_color="transparent", border_color=COLOR_GOLD, ...)
```

Update token references. Replace COLOR_ACCENT (already magenta in new tokens — no change needed, was orange). Replace `COLOR_GOLD` (legacy) with `COLOR_BORDER`. Replace text_color for active to `COLOR_BG` (dark on magenta for contrast). Update font to `FONT_SMALL` if not already.

If you can't find COLOR_GOLD reference, the file may use other names. Search by reading the actual file. Update tokens accordingly to match new system.

- [ ] **Step 3.12: Run pytest regression**

Run: `../../../.venv/Scripts/python.exe -m pytest -q`

Expected: `97 passed`.

- [ ] **Step 3.13: Manual smoke — dashboard visuals**

Run: `../../../.venv/Scripts/python.exe -m src.main`

Verify:
1. Dashboard renders with new dark theme
2. KPI cards: border visible, mono numbers in rose, Periode in cyan
3. Panel titles: Top 5 Late white, Teladan violet, Coaching rose, Dept white, Hari white
4. Pool rows: numeric values in rose (warn) for late panels, emerald for Teladan
5. Hover on a panel row: bg tints
6. WeekNavBar pills: active magenta, inactive border + dim text
7. Cetak button magenta
8. Header micro-label "/ insights" mono dim
9. Tab switch (Semua → Mgg 1 → Mgg 2) instant <200ms, no flicker
10. Ranking Lengkap Treeview: heading bg `#1F1F1F`, rows alternating, no purple leftover

Close app.

- [ ] **Step 3.14: Commit Phase 3**

```bash
git add src/ui/screens/dashboard.py src/ui/components/week_nav.py
git commit -m "$(cat <<'EOF'
feat(ui): dashboard polish — borders + semantic colors + mono

Phase 3/8 dari UI overhaul:
- KPI cards: COLOR_SURFACE bg + 1px COLOR_BORDER, FONT_LABEL untuk
  label uppercase, mono FONT_KPI 24pt untuk numerik (Total Terlambat,
  Coaching Flag = rose; Periode = cyan sans 17pt karena string)
- Panels (5): border + RADIUS_MD; title colors per semantic role
  (Top 5 Late white, Teladan violet COLOR_SECONDARY, Coaching rose,
  Dept/Hari white)
- Pool rows: hover bg COLOR_SURFACE_HIGH, FONT_MONO_DATA untuk value,
  rose untuk late data, emerald untuk teladan score
- Treeview style: COLOR_SURFACE bg, COLOR_SURFACE_HIGH heading bg,
  COLOR_TEXT_MUTED heading text, FONT_SMALL body
- WeekNavBar: active pill magenta + dark text, inactive border-only
- Header: "Dashboard" FONT_DISPLAY + "/ insights" mono dim micro-label
- Cetak button: COLOR_OK gold → COLOR_ACCENT magenta primary CTA

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Phase 4a — Workflow Screens (Issues, WhatsApp Assistant, Coaching)

**Files:**
- Modify: `src/ui/screens/issues.py`
- Modify: `src/ui/screens/whatsapp_assistant.py`
- Modify: `src/ui/screens/coaching.py`

**Goal of this task:** Apply tokens + semantic colors to 3 workflow screens. Remove Coaching lavender selection workaround and the `COLOR_OK==COLOR_WARN` distinct-color hack.

- [ ] **Step 4.1: Issues — update imports + KPI cards**

In `src/ui/screens/issues.py`, find existing theme imports and expand them to use new tokens (similar to dashboard.py Step 3.1).

Locate the KPI row construction. Find the 5 KPI card creations (Open, Resolved, NA, Total, Resolution Rate). Each follows similar pattern to dashboard KPIs. Apply same refactor: COLOR_SURFACE bg + COLOR_BORDER + semantic colors:

- Open: COLOR_WARN (rose, mono)
- Resolved: COLOR_SUCCESS (emerald, mono)
- NA: COLOR_INFO (cyan, mono)
- Total: COLOR_TEXT (white, mono)
- Resolution Rate %: COLOR_SUCCESS if rate > 75 else COLOR_WARN (conditional)

For conditional, in the function that updates KPI values, compute:
```python
rate = (resolved / total * 100) if total > 0 else 0
rate_color = COLOR_SUCCESS if rate > 75 else COLOR_WARN
# apply via .configure(text_color=rate_color)
```

- [ ] **Step 4.2: Issues — Treeview tints + drop lavender selection workaround**

Find Issues Treeview style setup. Currently has lavender selection workaround per commit `3af2277`. Locate the `style.map(...)` block:

```python
style.map(
    "Issues.Treeview",  # or similar style name
    background=[("selected", "#9B86C7")],  # or similar lavender
    foreground=[("selected", "#0A0A0A")],  # or similar
)
```

Replace with:

```python
style.map(
    "Issues.Treeview",
    background=[("selected", COLOR_SURFACE_HIGH)],
    foreground=[("selected", COLOR_TEXT)],
)
```

For row tint (OPEN/RESOLVED differentiation), if currently using `COLOR_PANEL_OPEN` and `COLOR_PANEL_RESOLVED` as backgrounds, they're now both very subtle (`#1F1F1F` and `#141414`). Visual differentiation almost gone — acceptable. Or update to subtle semantic tints via tag-based bg:

```python
tree.tag_configure("open_row", background="#1A1518")  # ~rose 4% over surface
tree.tag_configure("resolved_row", background="#13181B")  # ~emerald 4% over surface
```

Apply tags on insert based on row state.

- [ ] **Step 4.3: Issues — reason panel refresh**

Find the right-side reason input panel construction. Apply:
- Panel container: `fg_color=COLOR_SURFACE`, `border_width=1`, `border_color=COLOR_BORDER`, `corner_radius=RADIUS_MD`
- Dropdown (CTkOptionMenu): `fg_color=COLOR_SURFACE_HIGH`, `button_color=COLOR_ACCENT`, `text_color=COLOR_TEXT`
- Save button: `fg_color=COLOR_ACCENT`, `hover_color=COLOR_ACCENT_HOVER`, `text_color=COLOR_BG`
- Batalkan Resolve button: `fg_color="transparent"`, `border_width=1`, `border_color=COLOR_INFO`, `text_color=COLOR_INFO`

Read the existing file to find exact widget references and update token names.

- [ ] **Step 4.4: WhatsApp Assistant — terminal-style output box**

In `src/ui/screens/whatsapp_assistant.py`, find the main rendered output widget (currently likely CTkTextbox or CTkLabel). Update:

```python
self.output_textbox = ctk.CTkTextbox(
    main_pane,
    fg_color=COLOR_BG,  # darker than surface, like terminal
    border_width=1,
    border_color=COLOR_BORDER,
    corner_radius=RADIUS_MD,
    text_color=COLOR_TEXT,
    font=(FONT_MONO, 12),
    wrap="word",
    spacing1=2, spacing2=2,
)
```

(If the screen uses CTkLabel for rendering text, switch to CTkTextbox — better mono rendering and scrollable.)

- [ ] **Step 4.5: WhatsApp Assistant — Copy magenta + optional Buka WA Web cyan**

Find the action buttons section. Update:

Copy button:
```python
self.copy_btn = ctk.CTkButton(
    actions_frame, text="📋 Copy ke Clipboard",
    fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER,
    text_color=COLOR_BG,
    font=FONT_BODY_BOLD,
    command=self._on_copy,
)
self.copy_btn.pack(side="left", padx=(0, SPACE_SM))
```

Add new "Buka WA Web" button. Check if current employee has phone in DB:

```python
# Add to whatsapp_assistant.py after Copy button
def _build_wa_web_button(self, parent, employee_id: int):
    """Cyan secondary CTA — opens https://wa.me/{phone} if phone available."""
    from src.db.connection import get_connection
    from src.config import DB_PATH
    with get_connection(DB_PATH) as conn:
        cur = conn.execute(
            "SELECT phone FROM employees WHERE id = ?", (employee_id,)
        )
        row = cur.fetchone()
    has_phone = row and row["phone"]

    btn = ctk.CTkButton(
        parent, text="🟢 Buka WA Web",
        fg_color="transparent",
        border_width=1, border_color=COLOR_INFO,
        text_color=COLOR_INFO,
        hover_color=COLOR_SURFACE_HIGH,
        font=FONT_BODY_BOLD,
        state="normal" if has_phone else "disabled",
        command=(lambda: self._open_wa_web(row["phone"])) if has_phone else None,
    )
    btn.pack(side="left")
    if not has_phone:
        # Add tooltip-like hint
        ctk.CTkLabel(
            parent, text="(phone belum diset)",
            font=FONT_MONO_SMALL, text_color=COLOR_TEXT_DISABLED,
        ).pack(side="left", padx=(SPACE_SM, 0))
    return btn

def _open_wa_web(self, phone: str):
    """Convert phone to E.164 wa.me URL and open in browser.

    Indonesian phone formats handled: '08123...', '+628...', '628...'.
    """
    import webbrowser
    digits = "".join(c for c in phone if c.isdigit())
    if digits.startswith("0"):
        digits = "62" + digits[1:]
    elif digits.startswith("62"):
        pass  # already E.164 without '+'
    url = f"https://wa.me/{digits}"
    webbrowser.open(url)
```

Wire `_build_wa_web_button` into the screen render. (Note: implementation detail varies based on existing screen layout — read the file and integrate appropriately.)

- [ ] **Step 4.6: Coaching — KPI cards + badge refresh**

In `src/ui/screens/coaching.py`, find the 4 KPI cards (Total, Sudah, Belum, Coverage%). Update similar to Issues:
- Total: COLOR_TEXT white
- Sudah: COLOR_SUCCESS emerald
- Belum: COLOR_WARN rose
- Coverage %: conditional emerald > 75 else rose

Find the Treeview badge logic. Currently per commit `59446f2`, uses orange for "Belum" as workaround (since old COLOR_OK == COLOR_WARN both gold). Now:
- Sudah badge: use emerald bg tint + emerald text
- Belum badge: use rose bg tint + rose text

Tag-based:
```python
tree.tag_configure("sudah", background="#1B2820", foreground=COLOR_SUCCESS)  # subtle emerald tint
tree.tag_configure("belum", background="#281A20", foreground=COLOR_WARN)     # subtle rose tint
```

Update wherever badge column is constructed. If column shows literal `🟢 SUDAH` / `🟠 BELUM`, change to `🟢 SUDAH` / `🔴 BELUM` (red circle matches rose better). Or keep emoji and rely on row tint for color signal.

- [ ] **Step 4.7: Coaching — drop lavender selection workaround**

Find Coaching Treeview's `style.map(...)` for selection — if it uses lavender (per commit `3af2277` propagated), update to `COLOR_SURFACE_HIGH`:

```python
style.map(
    "Coaching.Treeview",
    background=[("selected", COLOR_SURFACE_HIGH)],
    foreground=[("selected", COLOR_TEXT)],
)
```

- [ ] **Step 4.8: Run pytest + manual smoke**

```bash
../../../.venv/Scripts/python.exe -m pytest -q
# Expected: 97 passed
```

Then run app and verify:
- Issues screen: 5 KPI cards with new colors, Treeview tints subtle, reason panel refined, save magenta
- WhatsApp Assistant: output box mono terminal-style, Copy magenta, Buka WA Web cyan (or disabled if no phone)
- Coaching: 4 KPIs with semantic colors, Sudah/Belum badges with new colors, lavender gone

Close app.

- [ ] **Step 4.9: Commit Phase 4a**

```bash
git add src/ui/screens/issues.py src/ui/screens/whatsapp_assistant.py src/ui/screens/coaching.py
git commit -m "$(cat <<'EOF'
feat(ui): workflow screens polish — Issues + WhatsApp + Coaching

Phase 4a/8 dari UI overhaul:
- Issues: 5 KPI cards dengan semantic colors (Open rose, Resolved
  emerald, NA cyan, Total white, Resolution Rate conditional).
  Treeview subtle row tints. Reason panel refresh: magenta Save,
  cyan Batalkan Resolve. Lavender selection workaround dihapus
  (was 3af2277) — pakai COLOR_SURFACE_HIGH consistent.
- WhatsApp Assistant: terminal-style mono output box (CTkTextbox
  Consolas 12pt). Copy = magenta primary CTA. New: Buka WA Web
  cyan secondary (gracefully disabled when phone tidak tersedia).
- Coaching: 4 KPI dengan semantic colors. Sudah/Belum badges
  refresh — emerald + rose (was orange workaround per 59446f2).
  Lavender selection workaround dihapus.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Phase 4b — Data Screens (Import, Export, Active Month)

**Files:**
- Modify: `src/ui/screens/import_screen.py`
- Modify: `src/ui/screens/export.py`
- Modify: `src/ui/screens/active_month.py`

**Goal of this task:** Apply tokens to 3 data management screens. Drop zone refresh, preview cards, Active Month grid + active state visuals.

- [ ] **Step 5.1: Import — drop zone refresh**

In `src/ui/screens/import_screen.py`, find the drop zone widget. Apply:

```python
self.dropzone = ctk.CTkFrame(
    parent,
    fg_color="#0F0F0F",  # slightly lighter than COLOR_BG
    border_width=2, border_color=COLOR_BORDER_STRONG,
    corner_radius=RADIUS_LG,
    height=200,
)
self.dropzone.pack_propagate(False)

# Hover state
def _on_enter(_e):
    self.dropzone.configure(border_color=COLOR_ACCENT)

def _on_leave(_e):
    self.dropzone.configure(border_color=COLOR_BORDER_STRONG)

self.dropzone.bind("<Enter>", _on_enter)
self.dropzone.bind("<Leave>", _on_leave)
```

Inner content: 📥 icon 28pt + title "Drag file fingerprint .xls ke sini" + "Browse..." outlined button. Use tokens for fonts.

(Note: customtkinter CTkFrame doesn't support `border_style="dashed"` — accept solid border per spec Section 11 Risk #10.)

- [ ] **Step 5.2: Import — preview cards + Konfirm CTA**

Find preview section (after file selected). Apply card pattern:

```python
preview_frame = ctk.CTkFrame(
    parent, fg_color=COLOR_SURFACE,
    border_width=1, border_color=COLOR_BORDER,
    corner_radius=RADIUS_MD,
)
```

For each metric (Jumlah Pegawai, Range Tanggal, Issue Baru, Pegawai Baru), use grid of small cards with label + mono value + semantic color (emerald for positive, rose for warning, cyan for neutral).

Konfirmasi Impor button: `fg_color=COLOR_ACCENT`, `hover_color=COLOR_ACCENT_HOVER`, `text_color=COLOR_BG`.

- [ ] **Step 5.3: Export — file picker + preview**

Same pattern as Import. File picker card with path display in mono. Matching preview cards with semantic colors:
- Filled count: COLOR_SUCCESS emerald mono
- NA count: COLOR_WARN rose mono
- Not found: COLOR_WARN rose mono

Export button: magenta primary CTA.

- [ ] **Step 5.4: Active Month — card grid + active state**

In `src/ui/screens/active_month.py` (renamed from months.py), find card per month. Update each card:

```python
card = ctk.CTkFrame(
    parent, fg_color=COLOR_SURFACE,
    border_width=1, border_color=COLOR_BORDER,
    corner_radius=RADIUS_MD,
)
```

For active month card, override border:
```python
if is_active:
    card.configure(border_color=COLOR_ACCENT)
```

Add 3px magenta left bar to active card:
```python
if is_active:
    left_bar = ctk.CTkFrame(
        card, fg_color=COLOR_ACCENT, width=3, corner_radius=0,
    )
    left_bar.pack(side="left", fill="y")
```

Add "AKTIF" badge top-right of active card:
```python
if is_active:
    badge = ctk.CTkLabel(
        card, text="AKTIF",
        font=FONT_MONO_SMALL,
        text_color=COLOR_BG,
        fg_color=COLOR_ACCENT,
        corner_radius=RADIUS_SM,
        padx=8, pady=2,
    )
    badge.place(relx=1.0, x=-SPACE_SM, y=SPACE_SM, anchor="ne")
```

(Note: `padx` / `pady` are not direct CTkLabel kwargs — use a wrapper frame or use `place()` with positioning. Adjust per actual CTk API.)

Month name: `FONT_SUBHEAD`. Stats: `FONT_MONO_SMALL` `COLOR_TEXT_MUTED`.

- [ ] **Step 5.5: Active Month — buttons (Pilih magenta, Generate cyan)**

For Pilih button:
- Inactive month: magenta primary
- Active month: emerald disabled-style ("✓ Sedang Aktif")

```python
if is_active:
    pilih_btn = ctk.CTkButton(
        actions_frame, text="✓ Sedang Aktif",
        fg_color="transparent",
        border_width=1, border_color=COLOR_SUCCESS,
        text_color=COLOR_SUCCESS,
        state="disabled",
    )
else:
    pilih_btn = ctk.CTkButton(
        actions_frame, text="✓ Pilih",
        fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER,
        text_color=COLOR_BG,
        command=lambda m=month: self._on_pilih(m),
    )

# Generate button: cyan secondary always
gen_btn = ctk.CTkButton(
    actions_frame, text="Generate",
    fg_color="transparent",
    border_width=1, border_color=COLOR_INFO,
    text_color=COLOR_INFO,
    hover_color=COLOR_SURFACE_HIGH,
    command=lambda m=month: self._on_generate(m),
)
```

Update scroll panel container bg from `COLOR_PANEL_RESOLVED` (was purple) to `COLOR_BG`.

- [ ] **Step 5.6: Run pytest + manual smoke**

```bash
../../../.venv/Scripts/python.exe -m pytest -q
# Expected: 97 passed
```

Smoke test:
- Import: drop zone hovers magenta border, dotted-equivalent look, Konfirm magenta
- Export: matching preview semantic colors
- Active Month: active card with magenta border + left bar + AKTIF badge + emerald "Sedang Aktif" button; inactive cards with magenta Pilih + cyan Generate

Close app.

- [ ] **Step 5.7: Commit Phase 4b**

```bash
git add src/ui/screens/import_screen.py src/ui/screens/export.py src/ui/screens/active_month.py
git commit -m "$(cat <<'EOF'
feat(ui): data screens polish — Import + Export + Active Month

Phase 4b/8 dari UI overhaul:
- Import: drop zone refresh — COLOR_BORDER_STRONG 2px solid border
  (CTk tidak support dashed — accept), magenta hover border, magenta
  Konfirm primary CTA. Preview cards dengan semantic colors per
  metric (success/warn/info).
- Export: file picker card mono path, matching preview cards
  (filled emerald, NA/not-found rose), magenta Export CTA.
- Active Month (was Riwayat Bulan): card grid refresh. Active card
  visual: magenta border + 3px left bar + AKTIF badge + emerald
  "Sedang Aktif" disabled-style button. Inactive: magenta Pilih +
  cyan Generate. Scroll panel bg COLOR_BG (was COLOR_PANEL_RESOLVED).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: Phase 4c + Phase 5 — Settings + Shared Components

**Files:**
- Modify: `src/ui/screens/settings.py`
- Modify: `src/ui/components/print_dialog.py`
- Modify: `src/ui/components/toast.py`
- Modify: `src/ui/splash.py`

**Goal of this task:** Settings tab nav + forms refresh. Print dialog modal refresh. Toast semantic borders. Splash internal hardcoded colors → tokens.

- [ ] **Step 6.1: Settings — tab nav with violet underline**

In `src/ui/screens/settings.py`, find tab buttons. Currently likely uses `CTkSegmentedButton` or custom tab implementation.

If using CTkSegmentedButton:
```python
self.tabs = ctk.CTkSegmentedButton(
    parent,
    values=["General", "Pegawai"],
    command=self._on_tab_change,
    fg_color="transparent",
    selected_color=COLOR_SECONDARY,  # violet
    selected_hover_color=COLOR_SECONDARY_HOVER,
    unselected_color="transparent",
    unselected_hover_color=COLOR_SURFACE_HIGH,
    text_color=COLOR_TEXT_DIM,
    text_color_disabled=COLOR_TEXT_MUTED,
)
```

If custom — apply violet for active, dim for inactive.

- [ ] **Step 6.2: Settings — form fields + Save magenta**

For form input fields (CTkEntry):
```python
entry = ctk.CTkEntry(
    parent,
    fg_color=COLOR_SURFACE_HIGH,
    border_width=1, border_color=COLOR_BORDER,
    text_color=COLOR_TEXT,
    font=FONT_BODY,
)
```

For focused state, CTkEntry should change border_color to COLOR_ACCENT automatically via `border_color` styling kwarg. If not, wire focus events manually.

Save button: magenta primary as elsewhere.

For Pegawai tab Treeview: use shared `Ranking.Treeview` style (already configured in dashboard.py setup). Or create local `Pegawai.Treeview` with same params.

- [ ] **Step 6.3: Print dialog refresh**

In `src/ui/components/print_dialog.py`, find dialog window setup. Apply:
- Window bg: `COLOR_BG`
- Border (if CTkToplevel supports): 1px `COLOR_BORDER`
- Corner radius: `RADIUS_LG`

For checkboxes (CTkCheckBox):
```python
checkbox = ctk.CTkCheckBox(
    parent, text=label,
    fg_color=COLOR_ACCENT,  # checked color
    hover_color=COLOR_ACCENT_HOVER,
    border_color=COLOR_BORDER,
    text_color=COLOR_TEXT,
    font=FONT_BODY,
    checkbox_width=18, checkbox_height=18,
)
```

For radio buttons (CTkRadioButton):
```python
radio = ctk.CTkRadioButton(
    parent, text=label,
    fg_color=COLOR_ACCENT,
    border_color=COLOR_BORDER,
    text_color=COLOR_TEXT,
    font=FONT_BODY,
)
```

Cancel button: `fg_color="transparent"`, cyan border. Cetak: magenta primary.

- [ ] **Step 6.4: Toast component refresh**

In `src/ui/components/toast.py`, find toast card construction. Update:

```python
card = ctk.CTkFrame(
    overlay,
    fg_color=COLOR_SURFACE,
    border_width=2,
    border_color=COLOR_SUCCESS,  # default success; override for error/info variants
    corner_radius=RADIUS_LG,
)
```

If toast.py has separate success/error/info variants, parameterize border_color. Otherwise: keep single default success path.

For title and message:
```python
title_lbl = ctk.CTkLabel(card, text=title, font=FONT_HEADING, text_color=COLOR_TEXT)
msg_lbl = ctk.CTkLabel(card, text=message, font=FONT_BODY, text_color=COLOR_TEXT_DIM)
```

Overlay bg: keep `rgba(0,0,0,.6)` equivalent → if implemented as CTkToplevel with alpha, no change needed.

- [ ] **Step 6.5: Splash internal — replace hardcoded with tokens**

In `src/ui/splash.py`, find the constants at top of SplashScreen class:

```python
BG_COLOR = "#0A0A0A"
ICON_BG = "#1a1a1a"
ACCENT_COLOR = "#EC4899"
TEXT_COLOR = "#FFFFFF"
DIM_COLOR = "#A3A3A3"
DIMMER_COLOR = "#525252"
PROGRESS_BG = "#1a1a1a"
```

Replace with token imports:

```python
from src.ui.theme import (
    COLOR_BG, COLOR_SURFACE, COLOR_SURFACE_HIGH,
    COLOR_ACCENT, COLOR_TEXT, COLOR_TEXT_DIM, COLOR_TEXT_DISABLED,
)
```

Then in class:
```python
class SplashScreen(ctk.CTkToplevel):
    WINDOW_W = 520
    WINDOW_H = 360
    PROGRESS_MS = 2000
    PROGRESS_STEPS = 100

    BG_COLOR = COLOR_BG
    ICON_BG = COLOR_SURFACE        # was #1a1a1a, now #141414 (consistent)
    ACCENT_COLOR = COLOR_ACCENT
    TEXT_COLOR = COLOR_TEXT
    DIM_COLOR = COLOR_TEXT_DIM
    DIMMER_COLOR = COLOR_TEXT_DISABLED
    PROGRESS_BG = COLOR_SURFACE
```

Visual structure tetap. Only internal color refs changed.

- [ ] **Step 6.6: Run pytest + manual smoke**

```bash
../../../.venv/Scripts/python.exe -m pytest -q
# Expected: 97 passed
```

Smoke test:
- Settings: tab switch with violet underline (or selected color), form fields styled, Save magenta. Pegawai tab Treeview uses shared style.
- Click Cetak/Export PDF in dashboard → print dialog opens. Verify: checkbox magenta checked color, radio magenta, Cancel cyan border, Cetak magenta. Submit → HTML opens in browser.
- Successful import → toast renders with emerald border.

Close app.

- [ ] **Step 6.7: Commit Phase 4c + 5**

```bash
git add src/ui/screens/settings.py src/ui/components/print_dialog.py src/ui/components/toast.py src/ui/splash.py
git commit -m "$(cat <<'EOF'
feat(ui): settings + shared components refresh

Phase 4c+5 / 8 dari UI overhaul:
- Settings: tab nav dengan COLOR_SECONDARY violet selected color
  (was COLOR_ACCENT orange). Form fields: COLOR_SURFACE_HIGH bg +
  COLOR_BORDER border + magenta focus border. Save magenta primary.
  Pegawai Treeview pakai shared style.
- Print Dialog: COLOR_BG bg + RADIUS_LG corner. Checkbox + radio:
  COLOR_ACCENT checked color. Cancel = transparent + cyan border.
  Cetak = magenta primary.
- Toast: COLOR_SURFACE bg + 2px semantic border (emerald success,
  rose error, cyan info). Title FONT_HEADING, message FONT_BODY dim.
- Splash internal: hardcoded #0A0A0A / #1a1a1a / #EC4899 / #A3A3A3
  literals replaced dengan theme tokens. Visual structure unchanged.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: Phase 6a — Cleanup (Drop hardcoded literals + legacy aliases)

**Files:**
- Modify: `src/ui/theme.py` (remove legacy aliases if safe)
- Modify: various screens (grep + replace any leftover hardcoded hex)

**Goal of this task:** Find and replace remaining hardcoded color literals. Verify legacy aliases can be removed (all callsites migrated).

- [ ] **Step 7.1: Grep all hardcoded magenta literals**

Run: Grep tool, pattern `"#EC4899"`, output_mode `content`, type `py`.

Expected: should find 0 references (already replaced in Phase 2 + Phase 5). If any remain, replace with `COLOR_ACCENT` import.

Verify: `BRAND_MAGENTA = "#EC4899"` line specifically — must not exist in any .py file.

- [ ] **Step 7.2: Grep legacy color hex literals**

Run multiple grep searches, pattern: `"#FF653F"` (was COLOR_ACCENT orange), `"#FFC85C"` (was COLOR_OK/COLOR_WARN gold), `"#452E5A"` (was COLOR_PANEL purple), `"#1E104E"` (was COLOR_BG indigo), `"#A9A0C5"` (was COLOR_TEXT_DIM lavender), `"#F5F1FF"` (was COLOR_TEXT lavender white), `"#523456"` (was COLOR_PANEL_OPEN), `"#3B2A4D"` (was COLOR_PANEL_RESOLVED), `"#2C1B47"` (was treeview heading bg).

For each match: replace with appropriate new token.

Also grep `"#FF8E72"` (proposed accent hover that might exist hardcoded — should be `COLOR_ACCENT_HOVER`).

- [ ] **Step 7.3: Verify legacy aliases can be removed safely**

Grep references to legacy alias symbols in `.py` files:
- `COLOR_PANEL` — should be replaced with `COLOR_SURFACE` everywhere
- `COLOR_OK` — should be replaced with `COLOR_SUCCESS`
- `COLOR_ERR` — should be replaced with `COLOR_ERROR`
- `COLOR_PANEL_OPEN` — verify usage in issues.py
- `COLOR_PANEL_RESOLVED` — verify usage

If any callsite remains using legacy alias, decide: (a) keep alias as documented compatibility, or (b) migrate the callsite. Recommended: migrate all, then remove aliases for clean theme.py.

After migration, remove the legacy aliases block from `src/ui/theme.py`:

```python
# DELETE this block:
# === LEGACY ALIASES (transitional) ===
COLOR_PANEL          = COLOR_SURFACE
COLOR_OK             = COLOR_SUCCESS
COLOR_ERR            = COLOR_ERROR
COLOR_PANEL_OPEN     = "#1F1F1F"
COLOR_PANEL_RESOLVED = "#141414"
```

If `COLOR_PANEL_OPEN` / `COLOR_PANEL_RESOLVED` are used by Issues row tints (intentional), keep them but rename:

```python
COLOR_ROW_TINT_OPEN     = "#1A1518"  # subtle rose tint
COLOR_ROW_TINT_RESOLVED = "#13181B"  # subtle emerald tint
```

Then update Issues callsite.

- [ ] **Step 7.4: Run pytest + smoke after cleanup**

```bash
../../../.venv/Scripts/python.exe -m pytest -q
# Expected: 97 passed
```

Smoke: open app, visit every screen. Verify no leftover purple/orange/gold anywhere. Look specifically at:
- Treeview heading bgs
- Button colors
- Card borders
- Active state indicators

If anything looks "stale" (purple flash, orange tint), grep the specific hex and fix.

- [ ] **Step 7.5: Commit Phase 6a**

```bash
git add src/ui/theme.py src/ui/screens/*.py src/ui/components/*.py src/ui/app.py
git commit -m "$(cat <<'EOF'
refactor: drop BRAND_MAGENTA hardcoded + legacy color aliases

Phase 6a/8 dari UI overhaul (cleanup):
- Grep all .py files untuk hardcoded hex literals (BRAND_MAGENTA,
  legacy purple/orange/gold) — replaced with theme.py tokens
- Legacy aliases removed dari theme.py: COLOR_PANEL, COLOR_OK,
  COLOR_ERR, COLOR_PANEL_OPEN, COLOR_PANEL_RESOLVED
- Issues row tints renamed: COLOR_PANEL_OPEN/RESOLVED → COLOR_ROW_TINT_OPEN/RESOLVED
  dengan nilai semantic-tinted (rose/emerald subtle)
- Single source of truth: semua color reference sekarang melalui theme.py

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: Phase 6b — Final Smoke + Handoff Doc

**Files:**
- Create: `docs/superpowers/specs/2026-05-14-session-handoff-v5.md`
- Modify (build): `dist/HR-Absensi/*` (PyInstaller output)

**Goal of this task:** Final end-to-end smoke test across all screens + features. Update handoff doc for v5.

- [ ] **Step 8.1: Full pytest run + count check**

```bash
../../../.venv/Scripts/python.exe -m pytest -q
```

Expected: `97 passed`.

If less, investigate before continuing.

- [ ] **Step 8.2: Full manual smoke test — 9 step checklist**

Run: `../../../.venv/Scripts/python.exe -m src.main`

Walk through:

1. **Splash screen** — opens with JTS logo, animated progress 0-100% over 2s, then app reveals maximized
2. **Sidebar** — pure black bg, header with icon + subtitle, active month chip with magenta border, 4 section labels, 8 nav items. Click each — magenta left bar appears, transitions smooth
3. **Dashboard** — KPI cards (Periode cyan, Total Terlambat + Coaching Flag rose mono), 5 panels with borders + semantic titles, Ranking Lengkap Treeview. Tab switch <200ms. Coaching panel only in Mingguan view
4. **Issues** — 5 KPI cards, 2 stacked Treeviews subtle row tints, reason input panel works (set kategori → Save magenta), Batalkan Resolve cyan
5. **WhatsApp Assistant** — sidebar shows employees with rose badge counts, click employee → main shows terminal-style mono output. Click Copy — clipboard updated (test by pasting elsewhere). If phone tersedia: click Buka WA Web — browser opens wa.me URL
6. **Import** — drop zone hovers magenta border, file picker works, preview cards semantic. Konfirmasi Impor magenta. Toast success emerald border
7. **Export** — file picker, matching preview cards (filled emerald, NA rose), Export magenta. Output file generated
8. **Active Month** — card grid, active card with magenta border + left bar + AKTIF badge + emerald "Sedang Aktif" button. Click Pilih on inactive month — switches active. Click Generate — generates report
9. **Coaching** — Mingguan only. 4 KPI cards (Total white, Sudah emerald, Belum rose, Coverage conditional). Treeview rows with sudah/belum badges. Click row → right panel: status + notes + toggle button. Toggle works
10. **Settings** — General tab works (jadwal, coaching threshold), violet tab indicator. Pegawai tab Treeview shows employees, edit works
11. **Print** — Cetak/Export PDF di Dashboard, dialog opens (checkboxes magenta checked, radio magenta selected, Cancel cyan, Cetak magenta), submit → HTML opens in browser

Close app. Tick off each — if any fails, fix before commit 8.

- [ ] **Step 8.3: Build .exe**

User confirms `.exe` is closed (not running). Then:

```bash
../../../.venv/Scripts/pyinstaller.exe HR-Absensi.spec --clean --noconfirm
```

Expected: output in `dist/HR-Absensi/HR-Absensi.exe`. Size ~14-15 MB.

If PyInstaller fails (PermissionError, etc.), ask user to close any running instance and retry.

- [ ] **Step 8.4: Deploy with rotation (optional — user-driven)**

Per handoff workflow rule 5, deploy with rotation:

```bash
# From project root (D:\Gawe\Project X\HR App):
# Step 1: rotate existing backups
# Existing .bak.old → delete (drop oldest)
# Existing .bak → .bak.old
# Existing current → .bak
# Step 2: copy new build → current

# (User typically runs this manually with confirmation.
#  Ask before executing if not already confirmed.)
```

This step optional within this plan — engineer may defer to user.

- [ ] **Step 8.5: Write handoff doc v5**

Create `docs/superpowers/specs/2026-05-14-session-handoff-v5.md` modeled after `2026-05-13-session-handoff-v4.md`. Cover:
- TL;DR: UI JTS overhaul done, single coherent palette (black + magenta + accents), theme tokens system, sidebar reorganized, 2 menu renames, 7 screens polished, lavender + COLOR_OK==WARN workarounds dropped
- Branch state: current branch at HEAD = Commit 8 of this plan
- Feature inventory: theme.py rewrite, sidebar redesign, dashboard refresh, 7 screens, shared components
- New file structure (vs v4): theme.py expanded, summary.py → whatsapp_assistant.py, months.py → active_month.py
- Brand integration status: full overhaul achieved — BRAND_MAGENTA hardcoded references removed, all references via COLOR_ACCENT
- Outstanding/deferred:
  - Print HTML themes (5 templates) still purple/orange — separate effort
  - About dialog not yet added
  - Light mode not in scope
- Workflow rules: preserved from v4 handoff (no auto push, etc.)

- [ ] **Step 8.6: Final commit**

```bash
git add docs/superpowers/specs/2026-05-14-session-handoff-v5.md
git commit -m "$(cat <<'EOF'
chore: smoke test pass + v5 handoff doc

Phase 6b/8 — final wrap-up of UI JTS overhaul:
- Full 11-step manual smoke test passed
- 97 pytest passing
- .exe built (~14-15 MB)
- Handoff doc v5 written for next session pickup

UI overhaul complete. App now fully aligned dengan Josaphat Tech
Solution brand: black + magenta + supporting semantic palette,
single source of truth di theme.py, no hardcoded literals.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 8.7: Verify final state**

```bash
git log --oneline -10
```

Expected: 8 new commits (Phase 1 through 6b) on top of the prior baseline.

```bash
git status
```

Expected: clean working tree.

```bash
git rev-list --count HEAD ^origin/v4
```

Expected: 8 (commits ahead of v4).

---

## Definition of Done (mirrors spec Section 13)

- [ ] `theme.py` rewritten with full JTS token system (Phase 1)
- [ ] Sidebar redesigned with 4-group categorization, 2 renames + 1 icon rename, active state indicator (Phase 2)
- [ ] Dashboard polished with semantic colors, mono numbers, border-based hierarchy (Phase 3)
- [ ] 7 other screens (Issues, WhatsApp Assistant, Import, Export, Active Month, Coaching, Settings) polished (Phase 4)
- [ ] Shared components (Print Dialog, Toast, Splash internal) referenced tokens (Phase 5)
- [ ] Hardcoded `BRAND_MAGENTA` removed; legacy aliases cleanup (Phase 6a)
- [ ] Coaching workarounds (lavender, COLOR_OK==WARN) reverted
- [ ] 97 existing tests pass
- [ ] Manual smoke checklist 11 steps pass
- [ ] 8 separated commits for reviewability
- [ ] Handoff doc v5 written
- [ ] No leftover legacy color hex literals (grep clean)

---

## Notes for the Implementing Engineer

- **NO `git push`.** User authorizes pushes manually. Stay local. After 8 commits, commit log akan menunjukkan branch ahead of v4 — biarkan begitu sampai user instruksi push.
- **`.exe` may be running.** If `pyinstaller --clean` hits `PermissionError`, ask user to close any open `HR-Absensi.exe`, then retry. Don't kill processes without permission.
- **Smoke test mandatory.** UI work tidak punya unit test coverage. Quality gate adalah manual smoke. Don't shortcut.
- **Line numbers in this plan are illustrative.** If your file has shifted due to earlier edits in same plan, locate by content match (e.g., "make_panel function definition") not line number.
- **CTk widget API gotchas:**
  - `CTkLabel` doesn't accept `padx`/`pady` in constructor — use `.pack(padx=..., pady=...)`
  - `CTkFrame` doesn't support `border_style="dashed"` — fallback to solid border
  - `CTkButton` text color expects hex string, not theme token name string — use the imported variable
  - `style.configure()` for ttk does not affect CTkFrame — only ttk widgets (Treeview, etc.)
- **If a step references a function/widget you can't find,** use Grep tool with a unique snippet from the spec or surrounding context.

---

*End of plan.*
