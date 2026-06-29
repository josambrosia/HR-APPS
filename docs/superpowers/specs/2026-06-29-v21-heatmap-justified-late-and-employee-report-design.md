# v21 — Justified-late fix + Heatmap full-width layout + Per-employee report

**Date:** 2026-06-29
**Status:** Approved (design), ready for implementation plan
**Forks from:** `v20.0.1` (`1f9f025`)

## Context

Three related issues, all centred on the attendance heatmap / dashboard and the
"terlambat dengan alasan" (late-with-reason) entity:

1. **Bug** — resolving a row as "Terlambat dengan alasan" does not zero the
   lateness on the Dashboard (employee still appears in Top-5 / ranking) nor on
   the Heatmap (still shown late, or even shown absent).
2. **UI** — the per-employee heatmap card only fills ~55% of the window width
   (1 card, left-aligned); and the "Libur" vs "Belum terinput" colours are
   nearly identical.
3. **Feature** — add a per-employee "Cetak" button on each heatmap card that
   prints a one-employee monthly recap.

---

## Part A — Bug: "Terlambat dengan alasan" not mirrored

### Root cause (confirmed)

There are two late-with-reason categories (`src/core/reason_mapper.py`):

| ID | Label | Justified? |
|---|---|---|
| `terlambat_kerja` | "Masuk Terlambat dengan Alasan Pekerjaan" | ✅ everywhere |
| `terlambat_lain` | **"Terlambat dengan alasan"** | ❌ orphaned |

`terlambat_lain` is **offered** as a resolve choice (it is in
`SEVERE_LATENESS_CATEGORIES` and the Issues resolve list / `REASON_NEEDS_DETAIL`)
but is **excluded from both justification tuples** in `src/config.py`:

- `COACHING_EXCLUDED = ("tugas_lapangan", "tugas_paparan", "terlambat_kerja")`
  → used by `insights.terlambat_ranking` to zero `terlambat_menit`, by
  `insights.karyawan_teladan`, by `db/coaching.py`, and by
  `reason_mapper.effective_attendance` (export). Because `terlambat_lain` is
  absent, its minutes keep being summed → stays in Top-5 / ranking / coaching,
  and export is not corrected. **(Bug 1)**
- `HEATMAP_DINAS_REASONS = ("tugas_lapangan", "tugas_paparan", "tugas_belajar",
  "terlambat_kerja")` → used by `core/heatmap.cell_status`. Because
  `terlambat_lain` is absent, the cell "falls through" to the lateness tiers
  (shows TR/TB); and when the row has no `masuk` punch it falls to step 5 →
  `mangkir` (shown as **X / Absent**). **(Bug 2 + "considered absent")**

`db/attendance.set_reason()` only writes `reason_category`/`reason_detail`/
`resolved_at` — it never mutates `terlambat_menit`/`masuk` (justification is
applied at read time). So the resolve persists correctly; the three readers just
disagree.

**Clincher:** the heatmap legend label already reads
`D · Dinas (lapangan/paparan/belajar/terlambat dengan alasan)` — the code
promises "terlambat dengan alasan" = Dinas but the tuple omits it. The omission
is an oversight, not a final design.

### Decision

`terlambat_lain` must behave exactly like `terlambat_kerja` (which is already
correct): lateness counted as 0, treated as present, rendered **"D · Dinas"** on
the heatmap (user-chosen), consistent across Dashboard + Heatmap + Export.

### Fix (read-time logic; no DB migration → retroactive)

1. **`src/config.py`** — add `"terlambat_lain"` to `COACHING_EXCLUDED`. Update
   the constant's comment to state it now means "lateness-justified reasons
   (work duty **or** other excused reason) — excluded from coaching and zeroed
   in lateness sums." (Keep the name to avoid wide churn; a rename to
   `LATENESS_JUSTIFIED` is optional future cleanup.) This single change cascades
   to `terlambat_ranking`, `karyawan_teladan`, `db/coaching.py`, and
   `effective_attendance`.
2. **`src/config.py`** — add `"terlambat_lain"` to `HEATMAP_DINAS_REASONS`.
   `cell_status` step 3 (`reason in HEATMAP_DINAS_REASONS → "dinas"`) runs before
   the `masuk` check, so this fixes both the "shown late" and "shown absent"
   symptoms at once.
3. **`src/core/insights.py::terlambat_ranking`** — the `tidak_hadir` CASE
   currently excludes only `lupa_absen_datang`. Extend it to also exclude
   `terlambat_kerja` and `terlambat_lain` (present-but-late reasons), so a
   no-punch row resolved as late-with-reason is not counted as "tidak hadir".

> **Retroactive bonus:** because the fix is read-time, every row already resolved
> as "Terlambat dengan alasan" becomes correct the moment the fix ships — no
> re-resolving needed.

### Out of scope (noted)

`insights.pola_jam_masuk` still bins raw clock-in times, so a justified-late
arrival still appears in the histogram. Deliberately unchanged (the histogram is
about *actual* arrival pattern). Flag for a possible future tweak.

### Tests (Part A)

- `terlambat_ranking`: a `terlambat_lain` row contributes 0 to `total_terlambat`
  and 0 to `hari_telat`; a no-punch `terlambat_lain` row is **not** counted in
  `tidak_hadir`.
- `top_n_terlambat` / `coaching_flag`: exclude a `terlambat_lain`-only employee.
- `cell_status`: returns `"dinas"` for `terlambat_lain` both when `masuk` is set
  and when `masuk` is NULL.
- `effective_attendance`: `terlambat_lain` with `masuk` set → `terlambat_menit`
  = 0, `masuk` = schedule_start (now that it is in `COACHING_EXCLUDED`).
- Regression: a severe-lateness row resolved as `terlambat_lain` disappears from
  Top-5.

---

## Part B — Heatmap UI

### B1 — Full-width card, one employee per row

`src/ui/screens/heatmap.py`. Today `_paint_card` draws a fixed-width (~711px)
card and `_repaint`/`_on_canvas_configure` reflow into N columns; on a
1366–1536px screen only one column fits, left-aligned (~55% width).

Change: **one card per row, stretched to the canvas width.**
- Force `ncols = 1` (drop the multi-column reflow path, or clamp to 1).
- Card width = `canvas_width - 2 * _PAD`.
- Internal layout: Name/Dept fixed on the **left**; the 5×7 calendar grid after
  it (cells enlarged moderately for readability, e.g. `_CELL_W` 30→34,
  `_CELL_H` 22→24 — tune visually); the **Kehadiran** and **Ringkasan** panels
  anchored to the **right edge**; the gap between grid and panels flexes to fill.
- Card height unchanged (7 weekday rows + header).
- Keep hover/click/tooltip/detail behaviour intact.

Verify visually (render the screen, screenshot) that one card fills the row at
~1366px and ~1536px with no large empty right margin.

### B2 — Distinguish "Libur" vs "Belum terinput"

`src/core/heatmap.py::STATUS_COLORS` is the single source (feeds both the canvas
screen and the print template).
- **`libur`**: `#404040` → `#39414F` (slate blue, solid) — reads "rest/weekend",
  distinct by hue from the neutral greys (`na` `#737373`).
- **`nodata`**: render as **hollow** — no fill (background `COLOR_BG`), a faint
  outline (e.g. `#3A3A3A`) and a muted "–". Reads "empty slot / not imported".
  - Canvas: special-case `status == "nodata"` in `_paint_card` to draw an
    outline-only rect instead of a filled rect.
  - Print template (`heatmap_print.html.j2`): `nodata` cell → transparent fill +
    dashed/solid faint border.
  - Legend swatches (screen `_render_legend` + print legend) follow automatically
    from `STATUS_COLORS`, but the hollow look needs a matching swatch treatment.
  - Fallback if hollow proves fiddly: flat light grey `#6B6B6B` for `nodata`
    (still clearly distinct from the new slate `libur`).

### Tests (Part B)

- `STATUS_COLORS["libur"] != STATUS_COLORS["nodata"]` and both differ from `na`.
- Heatmap-screen smoke (construct screen with a seeded DB) does not error with
  the new layout/colour code paths.
- Print render still contains the matrix + legend (existing tests stay green).

---

## Part C — Per-employee monthly report (Lengkap)

### Button

In `_paint_card` (`heatmap.py`), draw a small "🖨 Cetak" affordance at the card's
top-right corner, tagged uniquely per employee (e.g. tag
`("cetak", f"cetak{employee_id}")`). Bind `<Button-1>` on the `cetak` tag →
resolve the employee id from the clicked item → `_print_employee(employee_id)`.
`_print_employee` renders the report HTML to a temp file and opens it via
`open_html_in_browser` (same idiom as `_do_print`).

### Renderer + template

- New `src/reports/employee_report.py::render_employee_report_html(conn,
  year_month, employee_id) -> str`. Reuse `build_heatmap_context` and select the
  one employee (by `employee_id`); pull `hr_officer_name` from settings; reuse
  `_build_env()` from `html_renderer`.
- New template `src/reports/templates/employee_report.html.j2` (A4 portrait,
  mirrors the existing print styling + footer + sign-off).

### Content (Lengkap)

1. **Identitas** — nama, dept, NIP (`no_staff`), bulan (`month_label`),
   HR Officer, generated-at, brand footer.
2. **Statistik** — kehadiran % (`sorotan.pct_hadir`), HK / hari-kerja efektif
   (`hk` / `work_days`), tepat waktu (`ontime_days`), total telat
   (`telat_total` mnt · `telat_days` hari), plus the summary counts
   (D / S / C / LA / X) — from `summary` + `sorotan`.
3. **Mini-heatmap** — the employee's month grid rendered in HTML/CSS, cells
   coloured from `cells[d].color` (same palette as the matrix), weekday labels +
   week columns. Includes the new Part-B colour treatment.
4. **Tabel rincian per hari** — one row per day in the month: tanggal, hari
   (weekday), status (coloured pill), masuk, keluar, telat, alasan.
5. **Sign-off** — "HR Officer in Charge" block (from settings), consistent with
   the dashboard/heatmap prints.

### Tests (Part C)

- `render_employee_report_html` returns HTML containing the employee's name,
  the stats block, a per-day table, the mini-heatmap, and the sign-off.
- Employee with no rows in the month → graceful empty/partial render (no crash).
- Unknown `employee_id` → clear error or empty report (decide in plan).

---

## Implementation order

1. **Part A** (bug) — smallest, highest value, verify with tests.
2. **Part B** (UI layout + colours) — verify visually + tests.
3. **Part C** (per-employee report) — new module/template + button + tests.

## Release

Bundle as **v21.0.0** (new feature present): changelog entry, installer,
2-level prod rotation (`data/hr.db` untouched), copy to `Installers/`, smoke,
then push **only on explicit authorization** (Rule 1).

## Non-goals

- No DB schema/migration changes (Part A is read-time).
- No change to `pola_jam_masuk` histogram bins.
- No merge/rename of the `terlambat_kerja` / `terlambat_lain` categories (both
  kept; they keep distinct Alasan text, only their justification converges).
