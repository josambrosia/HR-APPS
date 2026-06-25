# v20 — Design System Refresh

**Date:** 2026-06-25 · **Branch:** `v20` (forked from `v19`) · **Status:** approved direction (user OK'd all recommendations), building in phases.

## Goal
Lift the app from "solid dark UI" to "distinctive, intentional product" by fixing the few high-leverage weaknesses found in the screenshot audit, without disturbing the strong 4-tier dark foundation. Six areas, executed in ROI/risk order, each verified by a real launch + screenshot (visual quality is not unit-testable).

## Design principles for this pass
- The dark surface tier (`#000 → #0A0A0A → #141414 → #1F1F1F`), 8pt spacing, and card structure are **kept**. We refine, not rebuild.
- **Brand magenta means one thing: interactive/brand.** Status/data never wears the brand color.
- The subject is *attendance patterns over time* — lean into the heatmap's visual language as the through-line (color ramp + the signature micro-strip).

---

## A. COLOR — disentangle brand from status (the #1 fix)

**Problem:** `COLOR_ACCENT` magenta `#EC4899` (brand) and `COLOR_WARN` rose `#F43F5E` (late/bad) are perceptually the same pink, so late data reads as brand color across Dashboard + Heatmap.

**Decision — magenta is brand-only.** Remove magenta from every status/data usage. Introduce a proper attendance **heat ramp** (green → amber → orange → red) reused by Heatmap cells *and* all "late" data:

| Token | New value | Meaning | Was |
|---|---|---|---|
| `COLOR_SUCCESS` | `#10B981` emerald | hadir / tepat waktu / "sudah" | keep |
| `COLOR_WARN` | `#FBBF24` **amber** | telat ringan / open / "belum" / caution | was rose `#F43F5E` (reuses the v16.1.1 FIX-badge amber) |
| `COLOR_DANGER` | `#F97316` **orange** (NEW) | telat berat | new tier |
| `COLOR_ERROR` | `#EF4444` red | absen tanpa alasan / destructive | was `#DC2626` (brighter for dark) |
| `COLOR_INFO` | `#22D3EE` cyan | periode / izin sakit / neutral | keep |
| `COLOR_ACCENT` | `#EC4899` magenta | **brand/interactive ONLY** | keep value, restrict usage |
| `COLOR_SECONDARY` | `#A855F7` violet | teladan / cuti / secondary | keep |

**Heatmap legend remap** (`src/core/heatmap.py` status→color map): H=`SUCCESS`, D(dinas)=`#34D399` (emerald-light, "excused-present"), TR=`WARN` amber, TB=`DANGER` orange, S(sakit)=`INFO` cyan, C(cuti)=`SECONDARY` violet, LA(lupa absen)=`COLOR_TEXT_MUTED` gray, X(absen)=`ERROR` red, NA=`COLOR_TEXT_DISABLED`. Result: a true green→amber→orange→red heat gradient; excused states (sakit/cuti/dinas) sit on a separate cool/violet track so they don't read as "bad."

**Row tints** (amber-ify "needs attention"): `COLOR_ROW_TINT_OPEN` `#1A1518`→`#1F1B12` (amber tint); `COLOR_ROW_TINT_BELUM` `#281A20`→`#1F1B12`; RESOLVED/SUDAH emerald tints keep.

**Sweep:** every `COLOR_WARN`/`COLOR_ACCENT` used for *data* (Dashboard KPI "Total Terlambat", Top 5, Dept, Hari Rawan; Issues OPEN/rate cards) re-points to the ramp; magenta stays only on buttons, active nav, focus, brand.

---

## B. TYPOGRAPHY — a display face with character

Display and body are both Segoe UI → generic. **Decision:** bundle **Space Grotesk** (SIL OFL) for headings + KPI numbers only; body stays Segoe UI, data stays Consolas.

- Add `assets/fonts/SpaceGrotesk-Bold.ttf`, `SpaceGrotesk-Medium.ttf`.
- Load at startup via Windows `ctypes.windll.gdi32.AddFontResourceExW(path, FR_PRIVATE, 0)` — **no install needed**, process-private. Wrap in try/except; on failure, `FONT_DISPLAY_FAMILY` falls back to `"Segoe UI"`.
- `theme.py`: `FONT_DISPLAY_FAMILY` resolved at import (probe load + fallback). `FONT_DISPLAY`, `FONT_HEADING`, `FONT_KPI` use it; everything else unchanged.
- **Risk:** font load + PyInstaller bundling. Mitigation: fallback to Segoe UI is automatic and invisible; smoke must confirm titles render in the new face.

---

## C. ICONS — Lucide line icons instead of emoji

Emoji (📊🔥🏆🚩…) render inconsistently and read as hobbyist. **Decision:** one monochrome Lucide set (ISC license).

- Add needed SVGs under `assets/icons/` (sidebar: layout-dashboard, grid-3x3, download, upload, calendar-days, flag, alarm-clock, message-circle, target, circle-slash, palmtree, settings, info; panels: trending-up, award, building-2, calendar, list).
- New `src/ui/icons.py`: `icon(name, size_px, color_hex) -> ctk.CTkImage | None` — render SVG via cairosvg→PIL, recolor stroke to `color_hex`, LRU-cache by (name,size,color). If cairosvg unavailable → return `None`; callers keep their text and just skip the image (no crash).
- Sidebar nav + panel titles use `icon(...)`, tinted `TEXT_DIM` (idle) / `ACCENT` (active). Keep text labels.
- **Risk:** cairosvg/cairo DLLs already used by `app.py` (with fallback); must add `assets/icons` + cairo libs to PyInstaller `datas`/`binaries`. Fallback path keeps the app functional iconless.

---

## D. TABLES — make `ttk.Treeview` look intentional

The Ranking Lengkap + Issues tables are the weakest surface. **Decision:** one shared style helper `src/ui/components/tree_style.py::apply_tree_style(tree, *, zebra=True)`:
- `rowheight=28`, body `FONT_SMALL`; header uppercase text + `TEXT_MUTED` fg + `SURFACE_HIGH` bg + flat.
- Zebra: `evenrow`/`oddrow` tags (`#141414` / `#171717`); selected = `SURFACE_HIGH` fg `TEXT`.
- Numeric columns `anchor="e"` (Terlambat/Telat/Tdk Hadir/Masuk/Keluar).
- **Alasan** column: widen + a hover tooltip (Treeview `<Motion>` → Toplevel label) showing full untruncated text.
- Applied in `dashboard.py`, `issues.py`, `severe_lateness.py` (replaces their inline `_setup_treeview_style`).

---

## E. DENSITY / LAYOUT

- **KPI cards** (Dashboard + Issues): trim vertical padding; add a one-line delta sublabel `▲/▼ N vs bln lalu` for Total Terlambat & Coaching (down=good→emerald, up=bad→amber/orange). Compute in-app via a small `_kpi_delta` helper (previous-period query already exists in the print path; mirror it lightly).
- **Issues right panel empty-state:** replace the lone dim line with an icon + "Pilih issue di kiri untuk input alasan" + a compact period summary (Open N · Resolved M · Rate X%), so the 40%-wide panel isn't dead space.

---

## F. SIGNATURE — attendance micro-strip

The one memorable element, born from the subject. New `src/ui/components/attendance_strip.py`:
- `render_strip(day_statuses, *, cell=8, gap=2) -> PIL.Image` — a single-row dot strip of the month's days, each dot colored by the **same heat ramp** as the Heatmap (`cell_status` → color).
- Shown as the Treeview **row image** (the `#0` tree column, width ~140) in Dashboard **Ranking Lengkap** and **Coaching** (both per-employee). Tables flip from flat text to scannable pattern rows, unifying the whole app with the Heatmap's language.
- Cached per (employee_id, month, version). Strip uses `data_version` (v19) so it refreshes on data change.

---

## Execution phases (each: implement → launch → screenshot → adjust → commit)
- **P1 Color** — theme tokens + status sweep + heatmap remap + row tints. *(lowest risk, biggest win)*
- **P2 Tables** — shared tree style + alignment + Alasan tooltip.
- **P3 Density** — KPI delta sublabels + Issues empty-state.
- **P4 Icons** — `icons.py` + replace emoji + bundle assets.
- **P5 Typography** — bundle + private-load Space Grotesk + apply to display tokens.
- **P6 Signature** — attendance strip + Treeview row images (Ranking Lengkap, Coaching).
- **P7 Release** — `APP_VERSION=20.0.0` + changelog + installer + 2-level rotate (`data/hr.db` untouched) + `Installers/` copy + smoke.

## Testing & risk
- Unit-testable: new tokens exist; `icon()` returns CTkImage/None; `render_strip()` returns an Image of expected size; `apply_tree_style` configures rowheight; `_kpi_delta` math. Existing 382 tests must stay green (esp. any asserting specific colors — update them with the token changes).
- **Not** unit-testable (verified by launch + screenshot): actual color harmony, font rendering, icon crispness, table feel, strip legibility.
- PyInstaller `HR-Absensi.spec` must bundle `assets/fonts`, `assets/icons` (+ cairo libs already needed). Every new asset path uses the frozen-safe resource resolver (`sys._MEIPASS`).
- All visual risk items (font load, cairosvg) have automatic text/Segoe-UI fallbacks → the app never crashes if an asset fails to load.
