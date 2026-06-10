# v18 Design — Heatmap Kehadiran (Attendance Heatmap)

**Date:** 2026-06-10
**Status:** Approved from brainstorming · **REVISED v2 — in-app render** (was browser/loopback-server; see §16) · hardened after a 5-lens adversarial review (§15)
**Milestone:** v18.0.0
**Forks from:** local v17 (`02d4bb4`, not yet pushed). v18 builds on top of v17.

## 1. Summary

A new **Heatmap Kehadiran** screen that visualises every active employee's
day-by-day attendance for a month as a colour-coded grid (à la GitHub activity).
Each day's colour encodes its status.

Two deliverables:
- **(A) Interactive screen — IN-APP** (customtkinter). The heatmap renders inside
  the application window (no browser, no local server). The dense grid is drawn on
  a **`tk.Canvas`** for performance; toolbar / legend / detail strip are normal CTk
  widgets. Vertical scroll over employee cards.
- **(B) Print report** — a landscape A4 HTML page (matrix + appendix), reached via
  a **pre-print dialog**. The app renders the print template to a **temporary HTML
  file** and opens it in the browser for Ctrl-P / Save PDF — **exactly the existing
  "Cetak Dashboard" pattern** (no server).

No change to the `attendance_records` schema. One new Settings value
(`late_tolerance_min`). The heatmap's colour logic is a **self-contained
presentation mapping**; it matches the app's "justified → not late" intent (reason
wins over lateness) but does NOT call `effective_attendance()` (§3, §15).

## 2. Status taxonomy, palette & codes

| Status | Hex | Code | Trigger |
|--------|-----|------|---------|
| Hadir tepat waktu | `#10B981` | `H` | present, no leave reason, lateness ≤ tolerance |
| Dinas | `#047857` | `D` | reason ∈ **HEATMAP_DINAS_REASONS** (§3) |
| Terlambat Ringan | `#EC4899` | `TR` | present, no leave reason, tolerance < lateness < severe |
| Terlambat Berat | `#BE185D` | `TB` | present, no leave reason, lateness ≥ severe |
| Izin Sakit | `#22D3EE` | `S` | reason `izin_sakit` |
| Cuti | `#A855F7` | `C` | reason `cuti` |
| Lupa absen | `#EAB308` | `LA` | reason `lupa_absen_datang` / `lupa_absen_pulang` |
| Absen Tanpa Alasan | `#DC2626` | `X` | Hari Kerja, no punch, no reason — **and** reason `na` |
| Libur / weekend | `#FFFFFF` | `·` | weekend OR holiday (white; print date text = black) |
| Belum ada data | `#9CA3AF` | `–` | working day with no attendance row yet (grey) |

- Cell text colour is luminance-derived (dark on light fills, light on dark) so
  every cell is legible, incl. white "Libur" and grey "no-data".
- `na` shares the red colour; it is **tallied under the `X` summary column** but
  keeps the literal code `NA` in cell/tooltip/appendix.

*(Unchanged from v1 — already implemented in `src/core/heatmap.py`: `STATUS_COLORS`
/ `STATUS_CODES` / `STATUS_LABELS`.)*

## 3. Cell status logic (precedence) — `src/core/heatmap.py`

A **pure** function `cell_status(row_or_None, *, tolerance, severe, is_weekend,
is_holiday) -> status_key`. It does **NOT** call `effective_attendance()`; it
applies this precedence directly on raw row fields.

Order (first match wins):
1. **Libur** → `·`. `is_weekend` OR `is_holiday` OR `row.tipe == 'Hari Libur'`.
2. **Belum ada data** → `–`. `row is None` on a working day.
3. **Leave/justified reason present** (overrides lateness):
   - reason ∈ `HEATMAP_DINAS_REASONS` = **{tugas_lapangan, tugas_paparan,
     tugas_belajar, terlambat_kerja}** → **D**
   - `izin_sakit` → **S** · `cuti` → **C** · `lupa_absen_*` → **LA** · `na` → **X**
   - `terlambat_lain` is **NOT** a leave reason → falls through to step 4.
4. **Present, no leave reason, by lateness** (`terlambat_menit` NULL→0):
   `≤ tolerance → H` · `tolerance < t < severe → TR` · `≥ severe → TB`.
5. **Hari Kerja, no `masuk`, no reason** → **X**.

> **`HEATMAP_DINAS_REASONS`** is a heatmap-only constant in `config.py`,
> deliberately broader than `COACHING_EXCLUDED` (unchanged at
> {tugas_lapangan, tugas_paparan, terlambat_kerja}). The green grouping is a colour
> choice; it does NOT change Coaching/Dashboard/Issues behaviour.

*(Unchanged from v1 — already implemented + tested.)*

## 4. Thresholds & Settings

- **`late_tolerance_min`** — NEW setting, default **12**. Boundary Hadir → Telat Ringan.
- **Severe threshold** — REUSE v17 `severe_lateness_threshold_min` (default 60).

Wiring (mirrors v17, already implemented): `config.DEFAULT_LATE_TOLERANCE_MIN`;
`schema.DEFAULT_SETTINGS["late_tolerance_min"]="12"`; `db.settings.read_late_tolerance`;
Settings → Umum row "Toleransi Telat (menit)" validated `[0,999]`.

## 5. Data layer + Sorotan metrics

- **Active employees** — `list_employees(conn, include_inactive=False)` (`active=1`,
  `ORDER BY nama`). Resigned = inactive = absent; new hire = active, grey pre-data days.
- **Matrix query** — `list_attendance_matrix(conn, start, end)` in `db/attendance.py`
  (JOIN attendance × employees over `[start,end]`; only rows that exist). *(Done.)*
- **`build_heatmap_context(conn, year_month, *, exclude_outliers)`** crosses active
  employees × every date; per cell `cell_status` + colour/code/label + masuk/keluar/
  telat/alasan. Already returns: `days, weekday_of, weekday_labels, weeks, month_label,
  prev/next_month, legend, summary_meta, eff_hari_kerja, is_empty, print_weeks,
  wsep_days`, and per employee `{nama, dept, hk, summary{H..X}, cells{}}`.
- **Holidays** — `holiday_dates_in_month(conn, year_month)`.
- **Outlier exclusion** — `excluded_employee_ids(conn, year_month)`. Used by the
  **print dialog's Kecualikan only**; the in-app screen always shows all active.
- **Hari kerja efektif** = weekdays − holidays. **HK (per employee)** = days whose
  status ∈ {H, TR, TB, D, LA}.

**NEW for v18 in-app — per-employee `sorotan` sub-dict** (added to
`build_heatmap_context`, so the metric math is unit-tested, not in the screen):

```
sorotan = {
  "work_days":  eff_hari_kerja,                       # context-level, copied for convenience
  "pct_hadir":  round(hk / eff_hari_kerja * 100) or 0,  # 0 when work_days == 0
  "ontime_days": summary["H"],                        # on-time present days
  "telat_total": Σ terlambat_menit over cells where status ∈ {sedang(TR), parah(TB)},
  "telat_days":  summary["TR"] + summary["TB"],
  "dinas":       summary["D"],
  "sakit":       summary["S"],
}
```

`pct_hadir` colour band (for the bar + number): **≥ 90 → green `#10B981`**,
**75–89 → amber `#FBBF24`**, **< 75 → rose `#EC4899`**.

## 6. Architecture — in-app render (no server)

- **`src/core/heatmap.py`** (pure, done + extended with `sorotan`) is the data/colour
  source of truth — the main unit-test surface.
- **(A) Interactive** is drawn with customtkinter + one `tk.Canvas`. **No
  `src/web` server, no dashboard `.j2` template.**
- **(B) Print** reuses Jinja2: a NEW pure function
  **`render_heatmap_print_html(conn, year_month, *, scope, outlier) -> str`**
  (in `src/reports/heatmap_print.py`) builds the context and renders
  `heatmap_print.html.j2` via the existing `html_renderer._build_env()`
  (FileSystemLoader on `TEMPLATES_DIR`, PyInstaller-safe). The screen writes the
  string to a temp `.html` (`tempfile`) and calls `open_html_in_browser(path)`.

## 7. (A) Interactive screen — `HeatmapScreen(ctk.CTkFrame)`

Layout (top→bottom), matching the approved mockup:

- **Header (fixed):** title "Heatmap Kehadiran" + subtitle
  ("Hover sel untuk tooltip, klik untuk pin detail. Hari kerja efektif {bulan}: N hari.").
- **Toolbar (fixed):** `SearchBar` (reused v16 component) · month nav `‹ {Bulan Thn} ›`
  · `🖨 Cetak…` button.
- **Legend (fixed):** the 10 status chips (code swatch + label), from `context["legend"]`.
- **Detail strip (fixed):** one line under the legend. Default hint
  "Klik sel untuk detail". On **click** a cell → fills with
  `{tanggal} · {status label} · Masuk {…} · Keluar {…} · Telat {…} · Alasan {…}`.
- **Body (scrollable `tk.Canvas` + vertical scrollbar, mousewheel):** one **card per
  active employee** (A–Z), painted on the canvas:
  - **Name + dept** (left).
  - **Grid**: weekday rows **Sn–Mg** × week columns **M1..M5**; each working-day cell
    = filled rounded rect + date number (+ code) in luminance-derived text colour;
    weekend/holiday white, no-data grey.
  - **Panel Sorotan** (fills the mid gap): **% Kehadiran** (banded colour) + thin
    progress bar; **Tepat waktu** `ontime_days/work_days` hari; **Telat**
    `telat_total` mnt · `telat_days` hari; **Dinas** d · **Sakit** s.
  - **Ringkasan** (right): `HK {hk}` + counts H/D/TR/TB/S/C/LA/X with colour dots.
  - Bottom note: HK definition + "Sel abu-abu = belum ada data".

**Interactions**
- **Search** → repaint, case-insensitive substring on nama/dept; `SearchBar`
  N-of-M counter; no match → "Tidak ada hasil" painted in the body.
- **Month nav ‹ / ›** → prev/next month (from `current_month` initially); rebuild
  context + repaint. Empty month → empty-state text (header/legend stay).
- **Hover** a cell → floating tooltip (one reusable borderless `Toplevel`) near the
  cursor: tanggal, status, masuk, keluar, telat, alasan.
- **Click** a cell → fill the **detail strip** (read-only; resolving stays in Issues /
  Severe Lateness).
- **Ctrl+F** focuses search; **click-outside** releases search focus — reuse the
  `bind_all` + walk-parent-chain pattern from `SevereLatenessScreen`; unbind on
  `<Destroy>`.
- **Empty state:** "Belum ada data untuk bulan ini — import data fingerprint dulu."

**Rendering approach (why Canvas):** up to ~40 employees × 35 cells ≈ ~1.4k cells.
One `CTkLabel`/cell ⇒ heavy construction + janky scroll (customtkinter is heavy per
widget). A single `tk.Canvas` paints all cells as items (rect + text), scrolls
smoothly, and supports hover/click via `tag_bind`. Toolbar/legend/strip stay CTk.

## 8. (B) Print report

Reached via the existing **`HeatmapPrintDialog`** (customtkinter; done). Fields:
**Tabel** (Full / Matrix saja / Lampiran saja) · **Karyawan outlier** (Sertakan /
Kecualikan).

On confirm: `render_heatmap_print_html(conn, month, scope, outlier)` → temp `.html`
→ `open_html_in_browser(path)` → landscape A4 light theme (`print-color-adjust:exact`)
→ user Ctrl-P / Save PDF.

**Scope:** `full` → matrix + appendix · `matrix` → matrix only · `lampiran` →
appendix only. `Kecualikan` omits outlier employees from BOTH tables.

### Matrix (single "padat" design) — *unchanged from v1, already in `heatmap_print.html.j2`*
Rows = active (non-excluded) A–Z; columns = day 1..N; week-group header (M1..M5) +
week separators; cell = colour + code; bold name column + thick right border; zebra;
**HK** column (plain, follows name-column bg) + counts `H TR TB D S C LA X`; bottom
note (hari kerja efektif + HK definition); legend below.

### Appendix — Detail Hari Kerja (scope ∈ {full, lampiran}) — *unchanged from v1*
Every abnormal working day (status ∉ {H, Libur, Belum-ada-data}); columns Nama ·
Dept · Tanggal · **Status pill** · Masuk · Keluar · Telat · Alasan; sorted by nama
then date; per-employee grouping (thick top border + zebra + bold name); zero
abnormal days → "Tidak ada hari kerja abnormal bulan ini".

> Print stays HK-only (no Sorotan %) — the matrix is intentionally dense. (Adding a
> "%Hadir" column later is a trivial follow-up if wanted.)

## 9. Sidebar + screen + router

- `app.py nav_groups` **INSIGHT** group, after Dashboard: `("⊞", "Heatmap",
  "Heatmap")`. `_show("Heatmap")` instantiates `HeatmapScreen`. *(Done — entry +
  router already wired.)*
- **`src/ui/screens/heatmap.py`** — **REWRITTEN** from the v1 browser-launcher into
  the full in-app screen described in §7. The `🖨 Cetak…` button still opens
  `HeatmapPrintDialog`; its `on_confirm` now uses the temp-file print path (§8).

## 10. Schema & changelog

- **No `attendance_records` schema change.** One Settings key + one heatmap constant.
  `COACHING_EXCLUDED` unchanged.
- **Rule #4 — REVISE the existing v18 changelog entry** so feature #1 says the
  heatmap is **interaktif di dalam aplikasi** (not "di browser"); keep the Toleransi
  Telat entry. `APP_VERSION` stays **18.0.0** (never pushed). Mention the per-employee
  Sorotan (ringkasan kehadiran) in user-facing terms.
- Release per framework: full pytest green → build installer → rotate prod `.exe` →
  copy to `Installers/` → smoke → **HOLD push** until user authorises.

## 11. Testing (TDD)

- **`cell_status`** — unchanged suite stays green (tolerance/severe tiers, reason
  precedence, terlambat_lain fall-through, NULL→0, libur/nodata, X).
- **`build_heatmap_context` — `sorotan`** (NEW): on a seeded fixture assert
  `pct_hadir = round(hk/work_days*100)` (and `0` when work_days 0), `ontime_days =
  summary['H']`, `telat_total = Σ TR/TB minutes`, `telat_days = TR+TB`, `dinas`,
  `sakit`. Plus existing context tests (grid coverage, HK, empty month).
- **`render_heatmap_print_html`** (NEW, replaces server route tests): returns HTML
  containing the month label + a known employee for `scope ∈ {full, matrix, lampiran}`;
  `matrix` omits the appendix heading, `lampiran` omits the matrix; `outlier='exc'`
  omits a flagged employee. (Pure string assertions — no browser.)
- **`HeatmapScreen` smoke** (pattern of other screen tests; `tk_root` + `temp_db`):
  constructs; canvas has the expected cell-item count (visible employees × working-day
  cells); `SearchBar` filter hides non-matches (repaint count); month nav ‹/›
  changes the rendered month. **Patch `messagebox`** where a modal could block.
- **DB / Settings** — `list_attendance_matrix`, `late_tolerance_min` seed +
  `read_late_tolerance` + Settings `[0,999]` — already green.
- **Removed:** `tests/test_heatmap_server.py` (server deleted).

## 12. Approaches considered

- **(chosen v2)** In-app customtkinter + `tk.Canvas` — renders inside the app
  (user's explicit requirement); Canvas keeps ~1.4k cells smooth; reuses the pure
  data layer; print via temp-file HTML reuses the app's existing print idiom.
- **(rejected — was v1)** Browser page on a loopback server — extra window + a server
  thread; the user wants the heatmap inside the app, not a browser.
- **(rejected)** One `CTkLabel` per cell — hundreds–thousands of heavy widgets;
  slow construction + janky scroll.

## 13. Files touched (v2)

| File | Change |
|------|--------|
| `src/config.py` | `DEFAULT_LATE_TOLERANCE_MIN`, `HEATMAP_DINAS_REASONS`, version; **revise v18 changelog wording** (in-app) |
| `src/db/schema.py` | `late_tolerance_min` default *(done)* |
| `src/db/settings.py` | `read_late_tolerance` *(done)* |
| `src/db/attendance.py` | `list_attendance_matrix` *(done)* |
| `src/core/heatmap.py` | `cell_status` + STATUS_* *(done)*; **add per-employee `sorotan`** |
| `src/reports/heatmap_print.py` | **new** — `render_heatmap_print_html(conn, ym, *, scope, outlier) -> str` |
| `src/reports/templates/heatmap_print.html.j2` | keep (print) |
| `src/ui/screens/heatmap.py` | **rewrite** — in-app Canvas screen (§7) |
| `src/ui/components/heatmap_print_dialog.py` | keep; `on_confirm` → temp-file print |
| `src/ui/screens/settings.py` | Toleransi Telat row *(done)* |
| `src/ui/app.py` | ⊞ Heatmap entry + router *(done)* |
| `HR-Absensi.spec` | **drop** `heatmap.html.j2` data + `src.web.heatmap_server` hiddenimport; **keep** `heatmap_print.html.j2` |
| **DELETE** `src/web/heatmap_server.py`, `src/web/__init__.py`, `src/reports/templates/heatmap.html.j2`, `tests/test_heatmap_server.py` | server + dashboard template removed |
| `src/ui/browser_launcher.py` | http-URL support is now unused but harmless — keep (tested) |
| `tests/...` | add `sorotan`, `render_heatmap_print_html`, `HeatmapScreen` smoke; remove server test |

## 14. New symbols to create (v2)

`sorotan` in `build_heatmap_context`; `src/reports/heatmap_print.py` +
`render_heatmap_print_html`; the rewritten `HeatmapScreen` (Canvas paint + tooltip +
detail strip + month nav + search). Everything else (settings, query, constants,
dialog, sidebar) already exists.

## 15. Verification notes (post-review) — still valid

Hardened against a 5-lens adversarial review. Confirmed integration points:
`list_employees`, `attendance_records` schema, `holiday_dates_in_month`,
`excluded_employee_ids` (per-employee-per-month), v17 settings pattern. Corrections
applied (all still hold in v2): (1) `HEATMAP_DINAS_REASONS` ≠ `COACHING_EXCLUDED`;
(2) no `effective_attendance` reuse — pure `cell_status`; (3) `terlambat_lain` falls
through to lateness; (4) `terlambat_menit` NULL → 0; (5) outlier filter = print only;
(6) settings seeded via `DEFAULT_SETTINGS` + `ON CONFLICT DO NOTHING`.

## 16. Revision log — browser → in-app (v2)

The v1 spec rendered (A) as an HTML page on a loopback `127.0.0.1` server opened in
the browser. **User decision (2026-06-10): the heatmap must render *inside the
application*, not a browser.** v2 changes:

- **Removed** `src/web/heatmap_server.py` + `src/web/__init__.py` +
  `src/reports/templates/heatmap.html.j2` + `tests/test_heatmap_server.py`; dropped
  the corresponding `.spec` `datas`/`hiddenimports`.
- **`HeatmapScreen` rewritten** from a browser launcher into the full in-app screen
  (§7), grid on a `tk.Canvas`, hover tooltip + click→detail-strip, in-app search +
  month nav.
- **Print kept** but server-free: `render_heatmap_print_html` → temp HTML →
  `open_html_in_browser` (the existing Cetak-Dashboard idiom). Print medium is still
  the browser (Ctrl-P / Save PDF) — only the *interactive* view moved in-app.
- **Added Panel Sorotan** per employee (§5/§7): % Kehadiran + bar, tepat waktu, total
  telat, dinas/sakit — fills the space between grid and ringkasan with real metrics.
- Core data/colour logic, settings, query, taxonomy, and the print matrix/appendix
  design are **unchanged** from v1 (already implemented + green).
