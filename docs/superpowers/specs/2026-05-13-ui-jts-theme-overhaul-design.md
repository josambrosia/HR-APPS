# UI JTS Theme Overhaul — Design Spec

**Tanggal:** 2026-05-13
**Status:** Draft (awaiting user spec review)
**Author:** Brainstorming session
**Source brand:** [2026-05-12-josaphat-tech-brand-design.md](./2026-05-12-josaphat-tech-brand-design.md)
**Reversal of:** [2026-05-12-brand-integration-design.md](./2026-05-12-brand-integration-design.md) Hybrid A approach

---

## 1. Konteks & Problem

App `HR Absensi` saat ini di branch v4 menggunakan **Hybrid A** brand approach:
- App theme: **purple/indigo + orange/gold** (legacy MVP palette)
- Brand magenta `#EC4899`: hanya di entry points (splash, icon, sidebar footer "Solution", active month indicator)

Hasilnya: brand JTS muncul sebagai "guest" di app yang masih bertheme lama. User minta **full overhaul** ke brand palette agar app = brand, bukan dua identity yang co-exist.

Selain palette switch, ada kebutuhan paralel:
- Existing palette punya bug `COLOR_OK == COLOR_WARN == #FFC85C` (keduanya gold) yang sudah di-workaround di Coaching (`59446f2`) dan Issues lavender (`3af2277`)
- Sidebar tidak punya active state indicator (cuma transparent CTkButton)
- Spacing & font scale ad-hoc — tidak ada sistem
- 2 menu labels (Riwayat Bulan, Summary) terasa kurang descriptive / Indonesian-only
- Brand magenta hardcoded di 3 file (`app.py`, `splash.py`, `months.py`) — fragile

---

## 2. Goals & Non-Goals

### Goals
- Full theme overhaul ke palette JTS: **Black + Magenta + harmonizing accents** (Violet, Cyan, Emerald, Rose)
- Design system: tokens untuk color, spacing, font scale, radius — semua di `theme.py`
- Sidebar: active state indicator, hover state, 4-group categorization, 2 menu renames
- Dashboard: KPI cards, panels, treeview di-refresh dengan border-based hierarchy + semantic colors
- Other screens (Issues, WhatsApp Assistant, Import, Export, Active Month, Coaching, Settings): polish layer applying the new tokens — bukan redesign penuh
- Brand magenta hardcoded di 3 file dihapus → semua pakai `COLOR_ACCENT` token
- Fix dual-meaning gold bug (`COLOR_OK == COLOR_WARN`) — split jadi emerald (success) + rose (warn)
- 97 existing tests tetap passing (no data layer changes)

### Non-Goals
- **Print HTML themes (5 templates) tidak di-update.** Out of scope — separate effort. PDF report rare task.
- **No light mode toggle.** App tetap dark-only (no regression from current).
- **No new feature work.** Theme + UX polish only — tidak nambah screen baru, tidak ubah business logic.
- **Splash screen visual tidak diubah signifikan.** Brand asset + animation tetap. Tokens-aware tapi visual layout tetap.
- **Tidak refactor query layer / data layer.** Murni UI.

---

## 3. Tech Constraints (customtkinter)

- **Tidak ada real shadow.** Hierarchy via background tiers + 1px border.
- **Tidak ada real backdrop-blur.** Glassmorphism harus di-fake (ditolak di brainstorm — pilih Refined Dark).
- **Border via `border_width` + `border_color`** di CTkFrame. Generated via PIL — first paint cost +5-10ms per widget.
- **Mono font (Consolas)** sudah loaded di v4 (splash + footer) — tidak ada additional font load cost.
- **ttk.Treeview** pakai style.configure() — fast, native widget.

---

## 4. Design Tokens (`src/ui/theme.py`)

Replace seluruh isi `theme.py` dengan token system berikut. Tetap pakai constant export pattern (no class/dataclass) untuk kompatibilitas dengan existing imports.

### 4.1 Color Palette

```python
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

# === SEMANTIC (Tailwind-ish dev-tool palette) ===
COLOR_INFO          = "#22D3EE"   # Cyan — Periode, neutral data, info toast
COLOR_SUCCESS       = "#10B981"   # Emerald — Teladan VALUE, Sudah coaching, success toast
COLOR_WARN          = "#F43F5E"   # Rose — late data values, Belum coaching, warning data
COLOR_ERROR         = "#DC2626"   # Red (darker) — errors, validation, destructive

# === LEGACY ALIASES (transitional — REMOVE in cleanup commit) ===
# Kept temporarily so existing imports don't break mid-migration.
COLOR_PANEL          = COLOR_SURFACE          # alias (used by every screen)
COLOR_OK             = COLOR_SUCCESS           # alias (was gold #FFC85C)
COLOR_PANEL_OPEN     = "#1F1F1F"              # Issues OPEN row tint (was warm purple)
COLOR_PANEL_RESOLVED = "#141414"              # Issues RESOLVED row tint (was cool purple)
```

**Notable shifts vs current:**

| Token | Before | After | Impact |
|---|---|---|---|
| `COLOR_BG` | `#1E104E` (indigo) | `#0A0A0A` (brand black) | All screens app bg |
| `COLOR_PANEL` / `COLOR_SURFACE` | `#452E5A` (purple) | `#141414` (near-black) | All cards/panels |
| `COLOR_ACCENT` | `#FF653F` (orange) | `#EC4899` (magenta) | Active states, primary CTAs |
| `COLOR_OK` / `COLOR_SUCCESS` | `#FFC85C` (gold) | `#10B981` (emerald) | Teladan, Sudah, success |
| `COLOR_WARN` | `#FFC85C` (gold, dup) | `#F43F5E` (rose) | Late data, Belum, warning |
| `COLOR_TEXT` | `#F5F1FF` (lavender white) | `#FFFFFF` | Primary text everywhere |
| `COLOR_TEXT_DIM` | `#A9A0C5` (lavender) | `#A3A3A3` (neutral gray) | Secondary text |
| `BRAND_MAGENTA` hardcoded | `"#EC4899"` × 3 files | Promoted to `COLOR_ACCENT` | Centralized |

### 4.2 Spacing Scale (8pt grid)

```python
SPACE_XS  = 4    # Tight spacing within rows
SPACE_SM  = 8    # Default gap between siblings
SPACE_MD  = 12   # Padding inside small components
SPACE_LG  = 16   # Padding inside cards/panels
SPACE_XL  = 24   # Section separation
SPACE_XXL = 32   # Screen-level padding
```

Replace ad-hoc `padx=10, pady=(8,4)` patterns across screens with these constants.

### 4.3 Font Scale

```python
FONT_FAMILY = "Segoe UI"
FONT_MONO   = "Consolas"

# Tuples ready to drop into CTkLabel(font=...)
FONT_KPI         = (FONT_FAMILY, 28, "bold")           # Big KPI numbers
FONT_DISPLAY     = (FONT_FAMILY, 24, "bold")           # Screen titles
FONT_HEADING     = (FONT_FAMILY, 18, "bold")           # Section headings
FONT_SUBHEAD     = (FONT_FAMILY, 14, "bold")           # Panel titles
FONT_BODY        = (FONT_FAMILY, 12)                   # Default body
FONT_BODY_BOLD   = (FONT_FAMILY, 12, "bold")
FONT_SMALL       = (FONT_FAMILY, 11)                   # Row text
FONT_LABEL       = (FONT_FAMILY, 10, "bold")           # Uppercase labels

# Mono variants (tabular numbers, brand wordmark, version/tagline)
FONT_MONO_DATA   = (FONT_MONO, 12)                     # Data values in tables/rows
FONT_MONO_BRAND  = (FONT_MONO, 13, "bold")             # Brand wordmark
FONT_MONO_SMALL  = (FONT_MONO, 10)                     # Version, tagline
```

### 4.4 Radius

```python
RADIUS_SM = 4   # Buttons, chips, small elements
RADIUS_MD = 8   # Cards, panels, default
RADIUS_LG = 12  # Dialogs, splash
```

### 4.5 Color Usage Map (Konvensi)

Konsisten cross-screen:

| Color | Use For |
|---|---|
| **Magenta** (`COLOR_ACCENT`) | Active sidebar item · Primary CTAs (Cetak/Save/Konfirmasi/Pilih) · WeekNavBar active pill · Brand wordmarks · Active month indicator · Active card border |
| **Violet** (`COLOR_SECONDARY`) | Top 5 Teladan panel title · Settings active tab indicator · Treeview heading accent |
| **Cyan** (`COLOR_INFO`) | Periode KPI value · Total count KPIs · Resolution Rate % · Date displays · Info toast · NA badge · Secondary buttons (Buka WA Web, Generate) |
| **Emerald** (`COLOR_SUCCESS`) | Top 5 Teladan VALUE · Sudah coaching badge · Coverage% positive · Success toast · Resolved count |
| **Rose** (`COLOR_WARN`) | Top 5 Late VALUES · Coaching panel + values · Hari Rawan values · Total Terlambat KPI · Belum coaching badge · Open issues KPI |
| **Red** (`COLOR_ERROR`) | Hard errors · Validation errors · Destructive buttons (rare) |
| **White** (`COLOR_TEXT`) | Primary text · Panel titles (default) · Neutral KPI values |
| **Gray dim** (`COLOR_TEXT_DIM`) | Secondary text, dept names in tables |
| **Gray muted** (`COLOR_TEXT_MUTED`) | KPI labels (uppercase), captions, divider labels |

---

## 5. Sidebar Redesign (`src/ui/app.py`)

### 5.1 Structural changes

- Width: 200 → **220px**
- Background: `COLOR_PANEL` (purple) → **`COLOR_SIDEBAR`** (`#000000`)
- Border-right: `1px solid #1F1F1F` (subtle separation vs app bg)
- Padding: 18px top, 14px bottom, 0 left/right (inner items padded individually)

### 5.2 Header

```
[icon 36×36]  HR ABSENSI            ← Segoe UI 14pt bold
              attendance manager     ← Consolas 9pt #737373
```

- Icon: tetap pakai SVG → CTkImage 36×36 (was 32) — sedikit lebih besar untuk balance dengan width 220
- Subtitle "attendance manager" mono — micro-detail signature Refined Dark

### 5.3 Active Month Chip (replaces plain label)

```
┌────────────────────────────┐
│ BULAN AKTIF                │   ← FONT_LABEL #737373
│ ◆ April 2026               │   ← FONT_SMALL_BOLD #F472B6
└────────────────────────────┘
   bg rgba(236,72,153,.10), border rgba(236,72,153,.25), RADIUS_MD
```

Click → navigate to Active Month screen (existing behavior preserved).

### 5.4 Nav Items — Section Groupings

```
┌─ INSIGHT ─────────
│ 📊 Dashboard
├─ DATA MANAGEMENT ─
│ 📥 Import
│ 📤 Export
│ 📆 Active Month       ← was: 🗓 Riwayat Bulan
├─ WORKFLOW ────────
│ 🚩 Issues              ← was: ⚠
│ 💬 WhatsApp Assistant  ← was: 📋 Summary
│ 🎯 Coaching
├─ SYSTEM ──────────
│ ⚙ Settings
```

Section labels: `FONT_LABEL` `COLOR_TEXT_DISABLED` uppercase, padding 6/16/4/16.

### 5.5 Nav Item Visual States

| State | Background | Text Color | Indicator |
|---|---|---|---|
| **Inactive** | transparent | `#C0C0C0` | — |
| **Hover** | `#141414` | `#FFFFFF` | — |
| **Active** | `#1F1F1F` | `#FFFFFF` bold | 3px magenta left bar (rounded 0/3/3/0) |

Implementation:
- Nav item = `ctk.CTkFrame` (not CTkButton — needs custom layout with left bar)
- Left bar = small `CTkFrame` (3px wide, magenta bg), packed `side="left"`. Hidden when inactive via `pack_forget()`.
- Bind `<Button-1>` for click, `<Enter>`/`<Leave>` for hover
- Track current active item in `self._active_nav_item` to toggle states

### 5.6 Renames (Display label + class/file)

| Old | New | File rename |
|---|---|---|
| `📋 Summary` | `💬 WhatsApp Assistant` | `summary.py` → `whatsapp_assistant.py`, class `SummaryScreen` → `WhatsAppAssistantScreen` |
| `🗓 Riwayat Bulan` | `📆 Active Month` | `months.py` → `active_month.py`, class `MonthsScreen` → `ActiveMonthScreen` |
| `⚠ Issues` | `🚩 Issues` | (icon only) |

Screen registration key di `HRApp._show()`: rename "Months" → "ActiveMonth", "Summary" → "WhatsAppAssistant". Update all callers (sidebar click handlers, active-month indicator click).

### 5.7 Footer

Existing footer structure dipertahankan, tapi:
- Separator: `COLOR_BORDER` (`#262626`) — was `COLOR_TEXT_DIM` (too bright)
- `BRAND_MAGENTA` hardcoded literal dihapus → pakai `COLOR_ACCENT`
- Brand line 1 + 2: tetap stacked white + magenta
- Version + tagline: `FONT_MONO_SMALL`

---

## 6. Dashboard Polish (`src/ui/screens/dashboard.py`)

Widget structure tetap (pool + Treeview architecture). Yang berubah: styling.

### 6.1 Header

```
Dashboard   / insights    [Semua][Mgg 1*][Mgg 2][Mgg 3][Mgg 4]      [📄 Cetak/Export PDF]
24pt bold   mono 10 dim    WeekNavBar (magenta active pill)         magenta CTA
```

- `/ insights` micro-label di sebelah title — mono `FONT_MONO_SMALL` `COLOR_TEXT_DISABLED`
- Cetak button: `fg_color=COLOR_ACCENT, text_color=COLOR_BG, hover_color=COLOR_ACCENT_HOVER`

### 6.2 KPI Row (3 cards)

Setiap card:
- `fg_color=COLOR_SURFACE` (`#141414`)
- `border_width=1, border_color=COLOR_BORDER` (`#262626`)
- `corner_radius=RADIUS_MD` (8)
- Padding: SPACE_LG (16)
- Label: `FONT_LABEL` `COLOR_TEXT_MUTED` uppercase, letter-spacing simulated via natural Tk
- Value: 24pt bold, semantic color
  - Periode: `COLOR_INFO` (cyan), font-size 17 (string date)
  - Total Terlambat: `COLOR_WARN` (rose), `FONT_MONO_DATA` 24pt
  - Coaching Flag: `COLOR_WARN` (rose), `FONT_MONO_DATA` 24pt
- Unit suffix: 13pt `COLOR_TEXT_MUTED` non-bold, marginleft 4

### 6.3 Left Panels (5)

Setiap panel:
- `fg_color=COLOR_SURFACE` + `border_width=1` + `border_color=COLOR_BORDER`
- `corner_radius=RADIUS_MD`
- Title position: top-left, padding 14/12
- Title font: `FONT_SUBHEAD`
- Title color per panel:

| Panel | Title color | Value color |
|---|---|---|
| 🔥 Top 5 Terlambat | `COLOR_TEXT` (white) | `COLOR_WARN` rose mono |
| 🏆 Top 5 Teladan | `COLOR_SECONDARY` (violet) | `COLOR_SUCCESS` emerald mono |
| ⚠ Butuh Coaching | `COLOR_WARN` (rose) | `COLOR_WARN` rose mono |
| 🏢 Ranking Departemen | `COLOR_TEXT` | `COLOR_WARN` rose mono |
| 📅 Hari Paling Rawan | `COLOR_TEXT` | `COLOR_WARN` rose mono |

Coaching threshold suffix: ` > {threshold} mnt` — mono `FONT_MONO_SMALL` `COLOR_TEXT_MUTED`.

### 6.4 Pool Rows

```python
# Per row:
# - Frame transparent
# - Left label: FONT_SMALL COLOR_TEXT anchor="w"
# - Right value: FONT_MONO_DATA semantic color anchor="e"
# - 1px top border via CTkFrame separator OR pack divider — TBD by implementation
# - On <Enter>: bg COLOR_SURFACE_HIGH, padx negative trick to extend
# - On <Leave>: bg back to transparent
```

Medal accent for Teladan: medals `["🥇", "🥈", "🥉", "4.", "5."]` — index 3+4 numerical, color `COLOR_ACCENT` (magenta) for brand touch.

### 6.5 Ranking Lengkap Treeview

`Ranking.Treeview` style updated:

```python
style.configure(
    "Ranking.Treeview",
    background=COLOR_SURFACE,
    fieldbackground=COLOR_SURFACE,
    foreground=COLOR_TEXT,
    rowheight=24,
    borderwidth=0,
)
style.configure(
    "Ranking.Treeview.Heading",
    background=COLOR_SURFACE_HIGH,
    foreground=COLOR_TEXT_MUTED,
    relief="flat",
    font=(FONT_FAMILY, 9, "bold"),  # smaller heading, letter-spacing visual via FONT_LABEL would be ideal
)
style.map(
    "Ranking.Treeview",
    background=[("selected", COLOR_SURFACE_HIGH)],
    foreground=[("selected", COLOR_TEXT)],
)
```

Numeric columns: Treeview tidak support per-column foreground natively (tag berlaku per-row, bukan per-cell). Keputusan: **semua text di Ranking Treeview pakai neutral white** (`COLOR_TEXT`), pakai `FONT_MONO_DATA` untuk kolom numerik supaya angka tabular-align. Rose accent muncul di **pool rows (5 panels)** yang dirancang sebagai "spotlight", sementara Treeview = "comprehensive view" yang netral. Konsisten dengan filosofi "color reserved untuk emphasis spotlight" (Section 3 color tweak rationale).

```python
# Default heading style — applies to all columns
style.configure("Ranking.Treeview", font=FONT_MONO_DATA)  # Or split: sans for name/dept, mono for numbers
# Trade-off: ttk Treeview doesn't support per-column fonts either.
# Acceptable approach: keep all FONT_BODY 11pt for consistency; visual hierarchy from heading + spacing.
```

### 6.6 WeekNavBar (`src/ui/components/week_nav.py`)

Active pill:
- `fg_color=COLOR_ACCENT`
- `text_color=COLOR_BG`
- `border_width=0`

Inactive pill:
- `fg_color="transparent"`
- `border_width=1, border_color=COLOR_BORDER`
- `text_color=COLOR_TEXT_DIM`

---

## 7. Other Screens Polish

### 7.1 Issues (`src/ui/screens/issues.py`)

KPI cards (5): Open (rose), Resolved (emerald), NA (cyan), Total (white), Resolution Rate % (emerald if > 75 else rose).

Treeviews:
- OPEN tint: `rgba(244,63,94,.04)` subtle rose row bg
- RESOLVED tint: `rgba(16,185,129,.04)` subtle emerald row bg
- Shared `Ranking.Treeview` style (or custom `Issues.Treeview` jika perlu tints)

Reason input panel (right):
- Card `COLOR_SURFACE` + border
- Dropdown: `fg_color=COLOR_SURFACE_HIGH`, border `COLOR_BORDER`, focused `COLOR_ACCENT`
- Save button: magenta primary
- Batalkan Resolve: cyan secondary (transparent + cyan border)

Selection workaround lavender (`3af2277`) dihapus — pakai `COLOR_SURFACE_HIGH` konsisten.

### 7.2 WhatsApp Assistant (`src/ui/screens/whatsapp_assistant.py`)

**File + class rename** dari `summary.py` / `SummaryScreen`.

Layout 2 kolom:
- Left sidebar (200px): employee list cards dengan badge count rose `FONT_MONO_DATA`
- Main area: terminal-style output box (Consolas mono, `COLOR_BG` bg, `COLOR_BORDER` border, line-height 1.6)

Actions:
- `[📋 Copy ke Clipboard]` — magenta primary
- `[🟢 Buka WA Web]` (opsional, jika phone tersedia di DB):
  - URL: `https://wa.me/{phone_e164}` where `phone_e164` is `+62...` stripped of `+`, leading 0 → 62
  - Cyan secondary button
  - Disabled state + tooltip "Phone belum diset" jika no phone

### 7.3 Import (`src/ui/screens/import_screen.py`)

Drop zone:
- `fg_color="#0F0F0F"` (slightly lighter than bg for contrast)
- `border_width=2, border_color=COLOR_BORDER_STRONG`
- `border_style="dashed"` — **NOTE:** customtkinter CTkFrame tidak support dashed border natively. Implementation options:
  1. Skip dashed, pakai solid border `COLOR_BORDER_STRONG`
  2. Custom: paint dashed via tk.Canvas behind CTkFrame
- **Decision in plan**: pakai solid border + label "drag .xls file ke sini" — efficiently feasible
- Hover state: bind `<Enter>`/`<Leave>`, swap border_color → `COLOR_ACCENT` + tint bg
- Inner icon: `📥` 28pt + title 13pt + sub 11pt + "Browse..." outlined button

Preview cards (after file selected): 2×2 or 4-col grid, semantic colors per metric.

Konfirmasi Impor: magenta primary CTA.

Success toast: emerald border, message "Import berhasil — bulan aktif: {Month}".

### 7.4 Export (`src/ui/screens/export.py`)

File picker + matching preview cards. Layout analogous to Import.

- Matching preview:
  - Filled count: `COLOR_SUCCESS` emerald
  - NA count: `COLOR_WARN` rose
  - Not found: `COLOR_WARN` rose
- Export button: magenta primary CTA
- Output filename displayed mono after save

### 7.5 Active Month (`src/ui/screens/active_month.py`)

**File + class rename** dari `months.py` / `MonthsScreen`.

Card grid:
- Each card: `COLOR_SURFACE` + 1px `COLOR_BORDER` + `RADIUS_MD`
- Month name: `FONT_SUBHEAD`
- Stats: `FONT_MONO_SMALL` `COLOR_TEXT_MUTED`
- Actions row: 2 buttons (Pilih + Generate)

Active card:
- `border_color=COLOR_ACCENT` (magenta)
- 3px magenta left bar (CTkFrame indicator)
- Top-right small badge "AKTIF" magenta bg + dark text
- Pilih button replaced with disabled-style:
  - bg `rgba(16,185,129,.15)`, text `COLOR_SUCCESS`, border `COLOR_SUCCESS`
  - Text "✓ Sedang Aktif"
  - state disabled

Inactive card:
- Pilih: magenta primary
- Generate: cyan secondary

Scroll panel container bg: `COLOR_BG` (no more purple panel resolved color).

### 7.6 Coaching (`src/ui/screens/coaching.py`)

4 KPI cards: Total (white), Sudah (emerald), Belum (rose), Coverage % (emerald > 75% else rose).

Treeview rows dengan badge column:
- 🟢 SUDAH: bg `rgba(16,185,129,.15)`, text `COLOR_SUCCESS`, padded pill
- 🟠 BELUM: bg `rgba(244,63,94,.15)`, text `COLOR_WARN`, padded pill

**REMOVE workaround:**
- `style/(ui)/coaching/distinct-colors-workaround` (`59446f2`) — sekarang COLOR_SUCCESS dan COLOR_WARN beneran distinct (emerald vs rose), tidak perlu hack
- Lavender selection (`3af2277`) — pakai `COLOR_SURFACE_HIGH` konsisten

Right panel:
- Status display (current state visual: emerald checkmark or rose minus)
- Notes textarea: refined
- Toggle button: bigger, color sesuai current state (toggling from belum→sudah: button magenta primary)

### 7.7 Settings (`src/ui/screens/settings.py`)

Tab nav:
- Active tab: text `COLOR_TEXT` bold + 2px `COLOR_SECONDARY` (violet) bottom border
- Inactive: text `COLOR_TEXT_DIM`
- Tab bar bg transparent

Form fields:
- Field bg `COLOR_SURFACE_HIGH`
- Border `COLOR_BORDER`
- Focused border `COLOR_ACCENT` magenta
- Label `FONT_LABEL` `COLOR_TEXT_MUTED` above field

Save: magenta primary. Cancel/Reset: transparent + cyan border.

Pegawai tab: Treeview pakai `Ranking.Treeview` shared style.

---

## 8. Shared Components Refresh

### 8.1 Print Dialog (`src/ui/components/print_dialog.py`)

- Modal bg: `COLOR_BG`
- Border: 1px `COLOR_BORDER`
- Corner radius: `RADIUS_LG` (12)
- Checkboxes (7 section toggles): checked bg `COLOR_ACCENT`, dark check
- Radio buttons (5 themes): selected fill `COLOR_ACCENT`
- Cancel: transparent + cyan border
- Cetak: magenta primary

### 8.2 Toast (`src/ui/components/toast.py`)

- Overlay: `rgba(0,0,0,.6)` semi-transparent
- Card: 480×220, `COLOR_SURFACE` bg, border semantic color
  - Success: `COLOR_SUCCESS` border
  - Error: `COLOR_ERROR` border
  - Info: `COLOR_INFO` border (new)
- Title: `FONT_HEADING` `COLOR_TEXT`
- Message: `FONT_BODY` `COLOR_TEXT_DIM`
- Click-anywhere-dismiss preserved

### 8.3 Empty State (inline pattern, no new component file)

Standardize across screens:
```python
ctk.CTkLabel(
    parent,
    text=empty_text,
    font=FONT_BODY,
    text_color=COLOR_TEXT_MUTED,
).pack(padx=SPACE_SM, pady=SPACE_SM)
```

3 patterns documented:
- Panel kosong: "Belum ada data."
- Filter empty: "Tidak ada yang match filter ini."
- First time: "Mulai dengan impor file fingerprint." + magenta CTA button

### 8.4 Splash Screen (`src/ui/splash.py`)

**Visual structure unchanged.** Hanya internal color refs di-update:
- `BG_COLOR`, `ICON_BG`, `ACCENT_COLOR`, dll. → reference `theme.py` tokens (was hardcoded)
- Layout, animation, dimensions: tidak berubah

---

## 9. Migration Strategy — Task & Commit Breakdown

Refactor di-split jadi **8 commits** untuk reviewability + safe rollback per chunk. Each commit harus pass `pytest -q` (97 tests).

| # | Commit | Scope | Tasks |
|---|---|---|---|
| 1 | `feat(theme): JTS palette + spacing + font scale tokens` | Phase 1 — Foundation | 4 |
| 2 | `feat(ui): sidebar redesign — JTS theme + sections + renames` | Phase 2 — Sidebar | 8 |
| 3 | `feat(ui): dashboard polish — borders + semantic colors + mono` | Phase 3 — Dashboard | 7 |
| 4 | `feat(ui): workflow screens polish (Issues/WhatsApp/Coaching)` | Phase 4a | 6 |
| 5 | `feat(ui): data screens polish (Import/Export/ActiveMonth)` | Phase 4b | 5 |
| 6 | `feat(ui): settings + shared components refresh` | Phase 4c + Phase 5 | 5 |
| 7 | `refactor: drop BRAND_MAGENTA hardcoded + legacy color aliases` | Phase 6a — Cleanup | 3 |
| 8 | `chore: smoke test + handoff doc update` | Phase 6b — Wrap-up | 2 |

**Total: ~40 tasks across 8 commits.**

### Per-phase task detail

**Phase 1 — Token foundation (4 tasks):**
1. Rewrite `theme.py` with new token system
2. Verify all existing imports still resolve (compat aliases)
3. Run `pytest -q` — must pass 97
4. Manual smoke: open app, verify no import error (visual will look weird since only tokens changed)

**Phase 2 — Sidebar (8 tasks):**
1. Update `app.py` sidebar bg to `COLOR_SIDEBAR`, width 220
2. Update header: icon size 36, subtitle "attendance manager"
3. Replace plain active month label with chip widget
4. Build nav item with active state + hover (custom CTkFrame)
5. Add 4 section labels (Insight/Data Management/Workflow/System)
6. Rename `summary.py` → `whatsapp_assistant.py`, class + screen key
7. Rename `months.py` → `active_month.py`, class + screen key
8. Update icons: ⚠→🚩 Issues, 🗓→📆 Active Month, 📋→💬 WhatsApp Assistant. Update `_refresh_active_month_label()` etc. Run tests + smoke.

**Phase 3 — Dashboard (7 tasks):**
1. Update KPI cards: border + semantic colors + mono numbers
2. Update panel boxes: border + title colors per role
3. Update pool row visuals: divider + hover state
4. Update Teladan medal accent magenta
5. Update `Ranking.Treeview` style + numeric column foreground
6. Update WeekNavBar pill styles (magenta active, cyan border inactive)
7. Header `/ insights` micro-label + Cetak magenta CTA. Run tests + smoke.

**Phase 4a — Workflow screens (6 tasks):**
1. Issues KPI cards + treeview tints (subtle rose/emerald)
2. Issues reason panel refresh
3. WhatsApp Assistant: terminal-style output box
4. WhatsApp Assistant: Copy magenta + optional Buka WA Web cyan deep link
5. Coaching: KPI semantic colors + badge refresh (emerald/rose pills)
6. Coaching: drop lavender workaround + COLOR_OK==COLOR_WARN hack. Run tests + smoke.

**Phase 4b — Data screens (5 tasks):**
1. Import drop zone refresh (solid border, hover, magenta CTA)
2. Import preview cards
3. Export file picker + matching preview cards
4. Active Month grid refresh + active card visual states
5. Active Month buttons (Pilih magenta, Generate cyan). Run tests + smoke.

**Phase 4c + 5 — Settings + shared (5 tasks):**
1. Settings tab nav + violet underline indicator
2. Settings form field styling + Save magenta CTA
3. Print Dialog refresh (checkbox/radio + buttons)
4. Toast component refresh (semantic border)
5. Splash internal: reference theme.py tokens, no hardcoded values. Run tests + smoke.

**Phase 6a — Cleanup (3 tasks):**
1. Grep all `"#EC4899"` literals — replace with `COLOR_ACCENT`
2. Grep `"#FF653F"`, `"#FFC85C"`, `"#452E5A"`, `"#1E104E"`, `"#A9A0C5"`, `"#F5F1FF"` — replace with new tokens
3. Remove legacy aliases `COLOR_PANEL` etc. if all callsites migrated. Otherwise keep + document.

**Phase 6b — Wrap-up (2 tasks):**
1. Full smoke test all 8 screens. Build .exe. Update handoff doc for v5.
2. Verify pytest 97 pass, document any new manual smoke checklist items.

---

## 10. Performance Impact Assessment

Realistic estimate:

| Operation | Current | After | Delta |
|---|---|---|---|
| App startup | 1-2s | 1.2-2.2s | +100-200ms (border PIL gen) |
| Dashboard first render | ~700ms | ~800-900ms | +100-200ms (border gen for cards/panels) |
| Dashboard tab switch | <100ms | <100ms | **0 impact** (pool unchanged) |
| Sidebar nav click | instant | instant | +5-10ms (active state toggle) |
| Memory | ~80MB | ~82-84MB | +1-2MB (border image cache) |
| .exe size | 14.3MB | ~14.3MB | +2-3KB code |

**Net verdict:** Negligible perf cost. UI changes are mostly styling, not new widget count.

---

## 11. Risks & Cons

| # | Risk | Mitigation |
|---|---|---|
| 1 | Print HTML themes still purple/orange — mismatch dengan in-app dashboard | Out of scope explicit. Separate effort kalau dirasa perlu. PDF report rare task. |
| 2 | Hardcoded `BRAND_MAGENTA` di 3 files harus dihapus systematic | Phase 6a Cleanup task — grep + replace |
| 3 | Theme migration miss → leftover purple/orange/gold di obscure spots | Phase 6a grep all old hex literals |
| 4 | Coaching workarounds (lavender, COLOR_OK==WARN) explicit reversal | Phase 4a smoke test |
| 5 | Visual shock first impression — user familiar dengan purple | Acceptable. User chose this. Brand alignment > comfort. |
| 6 | Secondary text contrast (`#A3A3A3` on `#0A0A0A` at 10-11pt) borderline AA | Use `#E5E5E5` (or `#C0C0C0`) when text is important + small |
| 7 | Big diff per commit | Split jadi 8 commits, reviewable per chunk |
| 8 | Regression di v2/v3 features (Coaching, Active Month, Issues unresolve) | Mandatory smoke test list in Section 13 |
| 9 | WhatsApp deep link feature needs phone column populated | Optional — gracefully degrade (button disabled + tooltip) |
| 10 | Dashed border tidak tersedia di CTk natively | Fallback ke solid border `COLOR_BORDER_STRONG`. Visual acceptable. |

---

## 12. Testing

### Unit tests
**No new tests.** 97 existing must pass after each commit. Data layer untouched.

### Manual smoke checklist (per commit + final)

Per commit (lightweight):
- [ ] `pytest -q` → 97 passed
- [ ] App opens (no import error)
- [ ] Screen aktif yang diubah render benar (no missing widget, no crash)

Final smoke (after Commit 8):
- [ ] All 8 sidebar items navigable
- [ ] Active state indicator visible on sidebar click
- [ ] Active month chip clickable → Active Month screen
- [ ] Dashboard renders correctly: KPI cards, 5 panels, Ranking Treeview
- [ ] Dashboard tab switch (Semua → Mgg 1-N) <200ms
- [ ] Bulanan vs Mingguan adaptive layout works
- [ ] Issues: KPI + 2 Treeviews + reason input works
- [ ] WhatsApp Assistant: copy works, output looks terminal-style. If phone tersedia: Buka WA Web works (opens browser to wa.me URL).
- [ ] Import: drop zone hover, file pick, preview, konfirm import success toast
- [ ] Export: file pick, preview, export success
- [ ] Active Month: grid renders, active card has visual indicators, Pilih works, Generate works
- [ ] Coaching: KPI + Treeview badges, toggle Sudah/Belum works
- [ ] Settings: tab switch, form save works
- [ ] Print dialog: checkboxes + radio + Cetak — generated HTML opens in browser
- [ ] Toast (Import success, errors) renders correctly
- [ ] No visual leftover purple/orange/gold anywhere

---

## 13. Definition of Done

- [ ] `theme.py` rewritten with full JTS token system (4.1-4.5)
- [ ] Sidebar redesigned with 4-group categorization, 2 renames + 1 icon rename, active state indicator
- [ ] Dashboard polished with semantic colors, mono numbers, border-based hierarchy
- [ ] 7 other screens (Issues, WhatsApp Assistant, Import, Export, Active Month, Coaching, Settings) polished with token system
- [ ] Shared components (Print Dialog, Toast, Splash internal) referenced tokens
- [ ] Hardcoded `BRAND_MAGENTA` di app.py / splash.py / months.py dihapus
- [ ] Coaching workarounds (lavender, COLOR_OK==WARN) di-revert
- [ ] 97 existing tests pass
- [ ] Manual smoke checklist (Section 12) pass
- [ ] 8 separated commits for reviewability
- [ ] Updated handoff doc (`2026-05-XX-session-handoff-v5.md`)
- [ ] No leftover legacy color hex literals in screen files (grep clean)

---

## 14. Open Questions / Future Work

1. **Print HTML themes overhaul.** 5 templates masih purple/orange/gold. Future spec untuk align dengan JTS palette di printed PDF.
2. **Splash screen visual refresh.** Saat ini Option D+S2. Bisa di-tweak di future kalau dirasa perlu (e.g., add subtle JTS pattern/grain).
3. **About dialog.** Belum ada. Bisa ditambah dengan full brand lockup + version + credits.
4. **Light mode toggle.** Tidak di plan. Kalau di future user butuh untuk presentation mode, bisa ditambah.
5. **Accessibility audit.** WCAG check di setiap screen + ukuran teks kecil. Bisa dilakukan setelah overhaul stabil.

---

*End of spec.*
