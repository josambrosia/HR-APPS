# v18 Design — Heatmap Kehadiran (Attendance Heatmap Dashboard)

**Date:** 2026-06-10
**Status:** Approved from brainstorming · hardened after a 5-lens adversarial review (see §15)
**Milestone:** v18.0.0
**Forks from:** local v17 (`02d4bb4`, not yet pushed). v18 builds on top of v17.

## 1. Summary

A new **Heatmap Kehadiran** dashboard that visualises every active employee's
day-by-day attendance for a month as a colour-coded grid (à la GitHub activity),
plus a print-optimised report. Each day's colour encodes its status.

Two deliverables:
- **(A) Interactive dashboard** — an HTML+JS page served on a **local web server**
  (`127.0.0.1`), opened in the browser from a sidebar menu.
- **(B) Print report** — a landscape A4 HTML page (matrix + appendix), reached via
  a **pre-print dialog** (which tables + outlier inclusion).

No change to the `attendance_records` schema. One new Settings value
(`late_tolerance_min`). The heatmap's colour logic is a **self-contained
presentation mapping**; it deliberately matches the app's "justified → not late"
intent (reason wins over lateness) but does NOT call `effective_attendance()`
(that function is for export/coaching number adjustment — see §3, §15).

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
  every cell is legible, incl. white "Libur" (black date) and grey "no-data".
- `na` shares the red colour; it is **tallied under the `X` summary column** but
  keeps the literal code `NA` in cell/tooltip/appendix.

## 3. Cell status logic (precedence) — `src/core/heatmap.py`

A **pure** function `cell_status(row_or_None, *, tolerance, severe, is_weekend,
is_holiday) -> status_key`. It does **NOT** call `effective_attendance()`; it
applies this precedence directly on the raw row fields. (The reason-over-lateness
ordering reproduces the same "justified → not telat" result as the rest of the
app; correctness is verified by tests, not code reuse — §15.)

Order (first match wins):
1. **Libur** → `·` white. `is_weekend` (Sat/Sun) OR `is_holiday` (date in the
   holidays table) OR `row.tipe == 'Hari Libur'`. Excluded from hari kerja efektif.
2. **Belum ada data** → `–` grey. `row is None` on a working day (weekday, not
   holiday). Covers future/unimported days and a new hire's pre-join days.
3. **Leave/justified reason present** → reason colour (overrides lateness):
   - reason ∈ `HEATMAP_DINAS_REASONS` = **{tugas_lapangan, tugas_paparan,
     tugas_belajar, terlambat_kerja}** → 🟢 **D**
   - `izin_sakit` → 🟦 **S** · `cuti` → 🟪 **C**
   - `lupa_absen_datang` / `lupa_absen_pulang` → 🟨 **LA**
   - `na` → 🟥 **X** (red; tallied under X)
   - `row.tipe`-less reason `libur` → treat as Libur (`·`)
   - **`terlambat_lain` is NOT a leave reason** → fall through to step 4 (shown
     by lateness magnitude). It is an "unjustified late" annotation, so it must
     still read as Telat.
4. **Present (`masuk` not null), no leave reason, by lateness** — using
   `terlambat_menit` (NULL → treated as 0, matching `insights.py`'s
   `COALESCE(terlambat_menit,0)`):
   - `terlambat ≤ tolerance` → 🟩 **H**
   - `tolerance < terlambat < severe` → 🩷 **TR**
   - `terlambat ≥ severe` → 🩷 **TB**
   (At the defaults: `≤12 → H`, `13..59 → TR`, `≥60 → TB`.)
5. **Hari Kerja, no `masuk`, no reason** → 🟥 **X** Absen Tanpa Alasan.

> **`HEATMAP_DINAS_REASONS` is a NEW heatmap-only constant** (in `config.py`),
> deliberately broader than `COACHING_EXCLUDED` (which stays
> `{tugas_lapangan, tugas_paparan, terlambat_kerja}` and is NOT modified). The
> green grouping is a colour choice the user requested; it does **not** change
> Coaching/Dashboard/Issues behaviour. *(If the user later wants `tugas_belajar`
> coaching-excluded too, that's a separate config change — out of scope here.)*

## 4. Thresholds & Settings

- **`late_tolerance_min`** — NEW setting, default **12**. Boundary Hadir → Telat
  Ringan.
- **Severe threshold** — REUSE v17 `severe_lateness_threshold_min` (default 60).
  Boundary Ringan → Berat.

Wiring mirrors v17's severe-threshold exactly:
1. `config.py`: `DEFAULT_LATE_TOLERANCE_MIN = 12`.
2. `schema.py` `DEFAULT_SETTINGS`: `"late_tolerance_min": "12"`. The `init_db`
   loop inserts every key with `INSERT ... ON CONFLICT(key) DO NOTHING`, so new
   AND existing DBs get the default on next startup (verified for v17 — no
   separate `_migrate` entry needed; confirm with a test like v17's).
3. `db/settings.py`: `read_late_tolerance(conn) -> int` (mirror
   `read_severe_lateness_threshold`, fallback to `DEFAULT_LATE_TOLERANCE_MIN`).
4. `settings.py` General tab: a new row "Toleransi Telat (menit)", validated
   `[0, 999]`, saved in `_save()` (validate-then-return pattern).

## 5. Data layer

- **Active employees** — `list_employees(conn, include_inactive=False)`
  (confirmed: returns `active=1`, `ORDER BY nama`). Single source of truth for
  who appears; resigned = inactive = absent; new hire = active, grey pre-data days.
  No join/resign date fields.
- **Matrix query** — NEW `list_attendance_matrix(conn, start, end)` in
  `db/attendance.py`: JOIN `attendance_records` × `employees` over `[start,end]`,
  returning per **existing** (employee,date) row: `{employee_id, nama, dept,
  tanggal, hari, tipe, masuk, keluar, terlambat_menit, reason_category,
  reason_detail, has_issue}`. Returns only rows that exist.
- **Renderer gap-fill (explicit):** the renderer crosses **active employees ×
  every date in the month**. For each (employee, date): use the row if present;
  else weekend/holiday → Libur, else working day → "Belum ada data". So the grid
  always covers the full month even for employees with zero rows.
- **Holidays** — `holiday_dates_in_month(conn, year_month)` (confirmed, returns a
  set of ISO dates; sourced from Menu Hari Libur + `restamp_holidays` on import).
- **Outlier exclusion** — per-employee-per-month, confirmed:
  `excluded_employee_ids(conn, year_month)` (set of employee_ids) /
  `list_active_exclusions(conn, year_month)`. Used **only by the print dialog's
  Kecualikan**: excluded employees are **omitted entirely** (matrix + appendix)
  for that month. The interactive dashboard always shows all active employees
  (no outlier filter).
- **Hari kerja efektif** (bottom note) = weekdays in the month − holidays.
- **HK (per employee)** = count of that employee's days whose `cell_status` ∈
  **{H, TR, TB, D, LA}** (attended: present/late/on-duty/forgot-scan; both
  lupa_absen_datang and lupa_absen_pulang count as attended). Excludes S, C, X,
  Libur, Belum-ada-data.

## 6. Architecture — local web server

A small **local HTTP server** the app starts on demand (chosen over in-app
customtkinter: hundreds of cells render smoothly in a browser + free
zoom/Ctrl-P/JS search & hover).

- **Module** `src/web/heatmap_server.py`: `http.server`-based handler in a
  **daemon thread**, bound to **`127.0.0.1`** on an **OS-assigned ephemeral port**
  (`bind((127.0.0.1, 0))`; read back the chosen port). `ensure_started() ->
  base_url` is **idempotent** (stores server+port in module state; returns the
  existing URL if already running). Daemon thread dies on app exit; the request
  handler wraps work in try/except so a request during shutdown can't crash the
  app. Loopback-only → no inbound firewall exposure (verify no Defender prompt on
  a clean box during smoke).
- **Routes** (each queries SQLite live, fresh data on refresh):
  - `GET /heatmap?month=YYYY-MM` → dashboard page.
  - `GET /heatmap/print?month=YYYY-MM&scope=full|matrix|lampiran&outlier=inc|exc`
    → print page.
- **Rendering:** Jinja2, reusing the reports stack. Templates
  `src/reports/templates/heatmap.html.j2` & `heatmap_print.html.j2`, loaded via
  **`TEMPLATES_DIR` from `config.py`** (so it resolves in dev AND PyInstaller
  `--onedir`, exactly like `html_renderer.py`). Server-side renders the grid;
  client-side JS does search, hover tooltip, click-detail, month nav (`?month=`).
- **Opening the browser:** `open_html_in_browser` currently accepts only a
  `Path` and emits `file://` — it **cannot open `http://`**. Change required:
  generalise it to `open_in_browser(target: str | Path)` (if `str` startswith
  `http` → pass the URL straight to the browser exe / `webbrowser.open(url)`;
  else keep the existing `file://` path behaviour), OR add a sibling
  `open_url_in_browser(url: str)`. Update the existing Dashboard-print caller
  accordingly. (`src/ui/browser_launcher.py`.)
- **Status/colour logic** lives in the pure `src/core/heatmap.py`: `cell_status`
  (§3) + `STATUS_COLORS` / `STATUS_CODES` / `STATUS_LABELS` / `HEATMAP_DINAS_REASONS`
  dicts (shared by both templates). This is the main unit-test surface.

## 7. (A) Interactive dashboard page

- **Sticky header** (does NOT scroll): title + month nav `‹ Mei 2026 ›` + SearchBar
  + legend. Only the employee list scrolls under it.
  - **Month nav** is free: prev/next always available, links to `?month=YYYY-MM`.
    Default = active month (`current_month`). A month with no rows renders the
    empty-state (header + legend still shown).
- **Body:** one full-width row/card per **active employee** (A–Z): name + dept,
  GitHub-style grid (weekday rows Sen–Min × week columns, date number in each
  cell, status colour), and a per-employee **summary** (H/D/TR/TB/S/C/LA/X counts
  + **HK**).
- **Search:** real-time, case-insensitive filter on nama/dept (hide non-matches);
  no match → "Tidak ada hasil"; Esc clears. (Mirror Issues/Outlier search.)
- **Hover** a cell → tooltip (tanggal, masuk, keluar, telat, alasan).
- **Click** a cell → **read-only** detail popup (same fields). View-only;
  resolving stays in Issues / Severe Lateness.
- **Empty state:** no data / no active employees →
  "Belum ada data untuk bulan ini — import data fingerprint dulu." (exact text).
- App dark theme tokens.

## 8. (B) Print report

Reached via a **NEW `HeatmapPrintDialog`** (customtkinter; the existing
`PrintOptionsDialog` is dashboard-specific and is NOT reused). Fields:
- **Tabel yang dicetak:** Full / Matrix saja / Lampiran saja.
- **Karyawan outlier:** Sertakan / Kecualikan.

The dialog opens `GET /heatmap/print?...` in the browser (landscape A4, light
theme, `print-color-adjust:exact`); user does Ctrl-P / Save PDF.

**Scope behaviour:** `full` → matrix + appendix · `matrix` → matrix only ·
`lampiran` → appendix only. `Kecualikan` omits outlier employees from BOTH tables.

### Matrix (single design — "padat")
- Rows = active (non-excluded) employees A–Z; columns = day 1..N.
- **Week-group header** (M1..M5 spanning each ISO week) + **week separators**
  (thicker border each Monday).
- Cell = colour + **code** (`H/TR/TB/D/S/C/LA/X/NA/·/–`); weekend/holiday white
  `·`, no-data grey `–`. Codes keep it legible printed greyscale.
- **Bold name column** + thick right border; **zebra** on name+summary cells.
- **Summary columns** (right): **HK** (plain styling — follows the name-column
  background, no green) then per-category counts `H TR TB D S C LA X`.
- **Bottom note (text):** "Hari kerja efektif {bulan}: N hari. HK = jumlah hari
  kerja yang dihadiri (Hadir, Terlambat, Dinas, Lupa absen); Sakit/Cuti/Absen
  tidak dihitung. Sel abu-abu = hari kerja yang datanya belum tersedia."
- **Legend** below the matrix.

### Appendix — Detail Hari Kerja (scope ∈ {full, lampiran})
Every **abnormal working day** (status ∉ {H, Libur, Belum-ada-data}):
- Columns: **Nama** (leftmost) · Dept · Tanggal · **Status** · Masuk · Keluar ·
  Telat · Alasan. Sorted **by nama** then date.
- **Status** cell = a **rounded full-cell pill** (fills the column width).
- **Per-employee grouping:** thick top border at each new employee + zebra per
  group + bold name. Employees with zero abnormal days are omitted; a month with
  zero abnormal days renders a "Tidak ada hari kerja abnormal bulan ini" note.

## 9. Sidebar + screen + router

- `app.py nav_groups` **INSIGHT** group (next to Dashboard): `("⊞", "Heatmap",
  "Heatmap")` (⊞ monochrome theme glyph). `_show("Heatmap")` instantiates
  `HeatmapScreen`.
- **`src/ui/screens/heatmap.py`** — a small **launcher** panel (the heatmap lives
  in the browser): a "🔳 Buka Heatmap di browser" button (ensures server started →
  opens `/heatmap?month=<active>`), a "🖨️ Cetak…" button (opens
  `HeatmapPrintDialog`), and a short note that it opens in an external browser
  window. Uses the active month from `current_month`.

## 10. Schema & changelog

- **No `attendance_records` schema change.** One new Settings key
  (`late_tolerance_min`) + one new heatmap constant (`HEATMAP_DINAS_REASONS`).
  `COACHING_EXCLUDED` is **unchanged**.
- **Rule #4:** prepend `APP_CHANGELOG` v18.0.0 (feat: Heatmap dashboard + print;
  feat: setting Toleransi Telat). Bump `APP_VERSION = "18.0.0"`, `APP_BUILD_DATE`.
- Release per framework: build installer → rotate prod `.exe` → copy to
  `Installers/` → smoke → push `v18` + advance `latest` (with explicit auth).

## 11. Testing (TDD)

- **`src/core/heatmap.py` — `cell_status` (primary surface), concrete cases:**
  - `{masuk:"08:05", terlambat_menit:12, reason:None, tipe:"Hari Kerja"}`, tol=12,
    sev=60, weekend=F, holiday=F → `H`; same with 13 → `TR`; 59 → `TR`; 60 → `TB`.
  - `terlambat_menit:None` + masuk present → `H` (NULL→0).
  - reason `terlambat_kerja` + terlambat 90 → `D` (reason wins over lateness).
  - reason `tugas_belajar` → `D`; `izin_sakit` → `S`; `cuti` → `C`;
    `lupa_absen_pulang` → `LA`; `na` → `X`; `terlambat_lain` + terlambat 30 → `TR`
    (NOT a leave; falls through).
  - `row=None`, weekday, not holiday → `–`; weekend → `·`; holiday → `·`;
    `tipe="Hari Libur"` → `·`.
  - Hari Kerja, masuk None, reason None → `X`.
  - HK helper: counts cells in {H,TR,TB,D,LA}; STATUS_* dict coverage.
- **DB** — `list_attendance_matrix` returns expected rows for a range; active-only
  via `list_employees`; gap-fill produces nodata/libur correctly.
- **Settings** — `late_tolerance_min` seeded (new + existing DB); `read_late_tolerance`
  fallback; Settings UI saves + `[0,999]` validation.
- **Server** — test helper starts the server on a seeded temp-DB; poll `base_url`
  (≤5×50ms) until up; assert `GET /heatmap` → 200 `text/html`,
  `GET /heatmap/print?scope=matrix` → 200; `ensure_started()` idempotent (same
  port twice); binds `127.0.0.1`. Daemon thread → no explicit teardown.
- **Render** — both templates render without error for: normal month, empty month
  (empty-state text), month with holidays + nodata, outlier `exc` omits a flagged
  employee; appendix sorted by nama with grouping; HK attended-only;
  effective-working-days note present.

## 12. Approaches considered

- **(chosen)** Browser page on a loopback server — scales to many cells, free
  zoom/print/search, reuses Jinja2. Cost: separate browser window + a small server
  thread (loopback-only, negligible risk).
- **(rejected)** In-app customtkinter grid — hundreds–thousands of widgets is
  heavy; search/zoom/print all bespoke.
- **(rejected)** Static temp-file HTML — simpler but no live refresh; user chose a
  localhost server.

## 13. Files touched (summary)

| File | Change |
|------|--------|
| `src/config.py` | `DEFAULT_LATE_TOLERANCE_MIN`, `HEATMAP_DINAS_REASONS`, version + changelog |
| `src/db/schema.py` | `late_tolerance_min` default in `DEFAULT_SETTINGS` |
| `src/db/settings.py` | `read_late_tolerance` |
| `src/db/attendance.py` | `list_attendance_matrix(conn, start, end)` |
| `src/core/heatmap.py` | **new** — `cell_status` + STATUS_* dicts + HK/summary helpers |
| `src/web/heatmap_server.py` | **new** — loopback HTTP server + routes |
| `src/reports/templates/heatmap.html.j2` | **new** — dashboard page |
| `src/reports/templates/heatmap_print.html.j2` | **new** — print matrix + appendix |
| `src/ui/screens/heatmap.py` | **new** — launcher panel |
| `src/ui/components/heatmap_print_dialog.py` | **new** — scope + outlier dialog |
| `src/ui/browser_launcher.py` | generalise to open `http://` URLs (or add `open_url_in_browser`) + update Dashboard caller |
| `src/ui/screens/settings.py` | Toleransi Telat row + validation |
| `src/ui/app.py` | ⊞ Heatmap sidebar entry (INSIGHT) + `_show` handler |
| `tests/...` | heatmap logic, DB, settings, server, render |

## 14. New symbols to create (confirmed absent — expected for a design spec)

The review confirmed these don't exist yet; they are the build targets, not spec
errors: `DEFAULT_LATE_TOLERANCE_MIN`, `HEATMAP_DINAS_REASONS`, `late_tolerance_min`
seed, `read_late_tolerance`, `list_attendance_matrix`, `src/core/heatmap.py`,
`src/web/heatmap_server.py`, both `.j2` templates, `HeatmapScreen`,
`HeatmapPrintDialog`, the sidebar entry + router branch, and the
`browser_launcher` URL support.

## 15. Verification notes (post-review)

Hardened against a 5-lens adversarial review of the spec vs. the real code.
Confirmed-correct integration points: `list_employees`, `attendance_records`
schema, `holiday_dates_in_month` / `restamp_holidays`, `excluded_employee_ids`
(per-employee-per-month), `effective_attendance` signature, v17 settings pattern.
Corrections applied:

1. **`tugas_belajar` / Dinas group** — the heatmap green group is a NEW explicit
   constant `HEATMAP_DINAS_REASONS` ({lapangan, paparan, belajar, terlambat_kerja}),
   NOT `COACHING_EXCLUDED` (which stays 3 categories, unchanged). The earlier spec
   wrongly equated them.
2. **No `effective_attendance` reuse** — `cell_status()` is a pure function on raw
   fields; the reason-over-lateness precedence reproduces the justified-late
   behaviour; consistency is proven by tests, not by calling that function.
3. **`terlambat_lain`** is NOT a leave reason → it falls through to the lateness
   tier (TR/TB), so it still reads as Telat.
4. **`open_html_in_browser`** only opens `file://` → generalise it (or add
   `open_url_in_browser`) for the `http://127.0.0.1:PORT` heatmap URL.
5. **`terlambat_menit` NULL** with masuk present → treated as 0 (on-time),
   matching `insights.py` COALESCE.
6. **Outlier** = `excluded_employee_ids(conn, year_month)`; excluded employees are
   omitted entirely; outlier filter applies to PRINT only (dashboard shows all
   active).
7. **Settings migration** — adding to `DEFAULT_SETTINGS` + the `init_db`
   `ON CONFLICT DO NOTHING` loop seeds both new and existing DBs (verified for
   v17); a test asserts the seed.
8. **Server** — OS-assigned ephemeral port via `bind((127.0.0.1,0))`, idempotent
   `ensure_started`, daemon thread, `TEMPLATES_DIR`-based Jinja2 loading for
   PyInstaller compatibility.
