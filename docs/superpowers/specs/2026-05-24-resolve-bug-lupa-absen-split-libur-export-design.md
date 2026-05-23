# Resolve Massal Bug Fix · Lupa Absen Split · Hari Libur Export Format

**Date:** 2026-05-24
**Target milestone:** v15 (cumulative on top of v14)
**Status:** Approved by user, ready for implementation plan

---

## Problem Statement

Smoke testing of v14 surfaced three issues that need addressing as one milestone:

1. **BUG — Resolve Massal:** the "Resolve" save button disappears when the user selects any of 5 reason categories that don't require a detail field (Tugas Belajar, Lupa Absen, Cuti, NA/Belum, Libur). Sometimes flipping to another category and back makes it reappear — classic tkinter pack-manager reflow race.
2. **LOGIC — Lupa Absen ambiguity:** the single `lupa_absen` category conflates two distinct cases (forgot to clock in vs. forgot to clock out). The penalty only makes sense for "forgot to clock in" (datang). Additionally, when both clock-in and clock-out are NULL but the user resolves the row as Lupa Absen, the dashboard still counts the day as "tidak masuk" — which is wrong once the issue has been resolved as "datang, just forgot to scan".
3. **EXPORT — Hari Libur in Laporan Bulanan:** the monthly export currently writes `"Hari Kerja"` in the Tipe column (E) and `"Libur"` as a marker in the Masuk column (G). User wants Tipe column to actually say `"Hari Libur"`, Masuk/Keluar to be blank, and a visual fill color to distinguish holiday rows.

These are independent in their code paths but related in user-facing intent ("clean up smoke-test findings before promoting to v15"). They're being delivered together as one v15 milestone.

---

## Section 1 — Bug Fix: Resolve Massal Save Button

### Root cause

In `src/ui/components/batch_resolve_dialog.py`:

- `_build` packs `btn_row` once with `side="bottom"`.
- `_on_cat_change` only `pack_forget()` / `pack()`s `_detail_label` and `_detail_entry`.

Tkinter's pack manager has a known reflow quirk: when sibling widgets get added/removed dynamically in a container that mixes `side="top"` and `side="bottom"` packs, the bottom-side widget can become geometrically "lost" — visible space is allocated but the widget renders at zero height — until another full pack cycle re-triggers layout.

This matches the user-observed symptom: the button is hidden when a no-detail category is the first selection, but reappears after picking a needs-detail category (which packs detail widgets, forcing layout) and then returning to a no-detail category (which forces another layout pass).

The same pattern in `src/ui/screens/issues.py` (single-row resolve) works correctly because `_lay_out_form` `pack_forget`s **and re-`pack`s** the Save button on every category change.

### Fix

Apply the same pattern to the batch dialog: keep `btn_row` as `self._btn_row`, and on every `_on_cat_change`, `pack_forget()` then `pack(...)` it back in with its original geometry parameters.

### Files affected

- `src/ui/components/batch_resolve_dialog.py` — single method modified.

### Acceptance test (manual smoke)

1. Open Resolve Massal, pick any employee with open issues.
2. As the **first** category selection, pick each of: Tugas Belajar, Lupa Absen (after the split: Datang then Pulang), Cuti, NA / Belum ada kabar, Libur.
3. After each pick, the "Resolve N Issue" button must be visible at the bottom of the dialog. No need to flip categories first.
4. Cycle to a needs-detail category (Tugas Lapangan) and back — button still visible, detail field shows/hides correctly.

---

## Section 2 — Logic: Split `lupa_absen` into Datang & Pulang

### Conceptual model

| New category | Semantic | Penalty? | Counts as tidak_masuk? |
|---|---|---|---|
| `lupa_absen_datang` | Karyawan datang tapi lupa scan masuk | Yes (configurable, default 15 mnt, 0 = anggap masuk tepat 08:00) | **No** |
| `lupa_absen_pulang` | Karyawan pulang tapi lupa scan keluar | No | No (raw values pass through; row stays as recorded) |

Lupa Absen Datang specifically must **not** count as "tidak masuk" in the dashboard ranking — even when both `masuk` and `keluar` are NULL in the raw data (which is the case that triggered the user's report).

### Data model changes

**`src/config.py`** — REASON_CATEGORIES tuple:

```python
REASON_CATEGORIES = (
    "tugas_lapangan", "tugas_paparan", "izin_sakit", "cuti", "tugas_belajar",
    "terlambat_kerja", "terlambat_lain",
    "lupa_absen_datang",   # NEW
    "lupa_absen_pulang",   # NEW
    "libur", "na",
)
```

`"lupa_absen"` is removed from the canonical list (existing rows are migrated — see Schema migration below).

**`src/core/reason_mapper.py`** — REASON_LABELS:

```python
REASON_LABELS = {
    "tugas_lapangan":     "Tugas Lapangan",
    "tugas_paparan":      "Tugas Paparan",
    "izin_sakit":         "Izin Sakit",
    "cuti":               "Cuti",
    "tugas_belajar":      "Tugas Belajar/Kuliah",
    "terlambat_kerja":    "Masuk Terlambat dengan Alasan Pekerjaan",
    "terlambat_lain":     "Terlambat dengan alasan",
    "lupa_absen_datang":  "Lupa Absen Datang",   # NEW
    "lupa_absen_pulang":  "Lupa Absen Pulang",   # NEW
    "libur":              "Libur",
    "na":                 "NA / Belum ada kabar",
}
```

`REASON_NEEDS_DETAIL` is unchanged — neither new category requires a detail entry.

### `effective_attendance()` update (reason_mapper.py)

Replace the existing `lupa_absen` branch with:

```python
if cat == "lupa_absen_datang" and masuk is None:
    return {
        "masuk": _minutes_to_hhmm(_schedule_start_minutes(schedule_start) + lupa_penalty_min),
        "terlambat_menit": lupa_penalty_min,
    }
# lupa_absen_pulang: no correction; raw values pass through
```

The original guard `masuk is None and keluar is not None` is relaxed to just `masuk is None`. Reasoning: if the user explicitly labeled the row as "Lupa Absen Datang" then the datang IS missing — even if keluar is also missing (both NULL case), the penalty should still apply. The label is the source of truth, not the raw fingerprint state.

Penalty=0 case: `_schedule_start_minutes(...) + 0 = 480` → masuk = `"08:00"` and `terlambat_menit = 0`. No special-case needed.

### Dashboard "Tidak Hadir" count update (insights.py)

In `terlambat_ranking()`, modify the tidak_hadir SUM to exclude rows marked as `lupa_absen_datang`:

```sql
SUM(CASE WHEN ar.tipe = 'Hari Kerja'
          AND ar.masuk IS NULL AND ar.keluar IS NULL
          AND (ar.reason_category IS NULL OR ar.reason_category != 'lupa_absen_datang')
        THEN 1 ELSE 0 END) AS tidak_hadir,
```

This is the only counting path: the live Dashboard ranking table and the printed HTML report both consume `absent_count` (alias of `tidak_hadir`) from the same dict.

`lupa_absen_pulang` is implicitly handled — if it's set, `masuk` is non-NULL by definition, so the row already doesn't match the `masuk IS NULL AND keluar IS NULL` predicate.

### Settings UI tweak (settings.py)

Label change only — setting key stays `lupa_absen_datang_penalty_min` (already named that way; no rename needed):

```
"Lupa Absen — Penalti (mnt):"
→ "Lupa Absen Datang — Penalti (mnt):"
```

Also: add input validation clamping to `[0, 999]` on save. Currently the field accepts any string and silently fails on bad input. Cheap to fix while we're touching it. Out-of-range or non-integer input shows a Tkinter warning dialog and leaves the value unchanged.

### Schema migration (db/schema.py `_migrate`)

Idempotent migration runs at startup. Existing rows with `reason_category='lupa_absen'` get split by inspecting `masuk`/`keluar` state:

```sql
-- Forgot to clock IN (datang) — masuk NULL, keluar set
UPDATE attendance_records
   SET reason_category = 'lupa_absen_datang'
 WHERE reason_category = 'lupa_absen'
   AND masuk IS NULL;

-- Forgot to clock OUT (pulang) — masuk set, keluar NULL
UPDATE attendance_records
   SET reason_category = 'lupa_absen_pulang'
 WHERE reason_category = 'lupa_absen'
   AND masuk IS NOT NULL
   AND keluar IS NULL;

-- Fallback (both set or both NULL ambiguous): default to datang (conservative — applies penalty)
UPDATE attendance_records
   SET reason_category = 'lupa_absen_datang'
 WHERE reason_category = 'lupa_absen';
```

Order matters: the WHERE-narrow updates run first, then the catch-all sweeps any remaining `'lupa_absen'` rows. After all three statements, no rows have `reason_category='lupa_absen'` anymore.

Migration is idempotent because once the catch-all sweep runs, subsequent passes find zero rows to update.

### Files affected

1. `src/config.py` — REASON_CATEGORIES tuple.
2. `src/core/reason_mapper.py` — REASON_LABELS, `effective_attendance()`.
3. `src/core/insights.py` — `terlambat_ranking()` SQL.
4. `src/db/schema.py` — `_migrate` extended with the three-step UPDATE block.
5. `src/ui/screens/settings.py` — label text + `[0, 999]` clamp.

`src/core/report_generator.py` and `src/reports/html_renderer.py` need NO direct changes — they consume REASON_LABELS via `render_alasan_ijin()`, which transparently picks up the new labels.

### Tests

Update existing `lupa_absen` test cases (find via `grep -r lupa_absen tests/`) to use one of the new categories:

- `effective_attendance` tests that exercised forgot-IN → use `lupa_absen_datang`.
- `effective_attendance` tests that exercised forgot-OUT → use `lupa_absen_pulang`.

Add new tests:

1. **Migration test** (`tests/db/test_schema.py`):
   - Setup: insert 4 rows with `reason_category='lupa_absen'` — one each for (masuk=NULL, keluar=set), (masuk=set, keluar=NULL), (both NULL), (both set).
   - Run `_migrate(conn)`.
   - Assert: row 1 → `lupa_absen_datang`. Row 2 → `lupa_absen_pulang`. Row 3 → `lupa_absen_datang` (fallback). Row 4 → `lupa_absen_datang` (fallback).
   - Re-run `_migrate(conn)` and assert no rows still have `reason_category='lupa_absen'` (idempotency).

2. **Dashboard tidak_hadir exclusion** (`tests/core/test_insights.py`):
   - Setup: one employee with one Hari Kerja date, both masuk & keluar NULL, `reason_category='lupa_absen_datang'`.
   - Assert: `terlambat_ranking` returns `tidak_hadir = 0` for this employee.
   - Repeat with `reason_category=NULL` (truly unresolved) — assert `tidak_hadir = 1`.

3. **Settings validation** (`tests/ui/test_settings_screen.py` or new `tests/db/test_settings.py`):
   - Out-of-range input (`-1`, `1000`, `"abc"`) → setting unchanged after save, warning shown (mock the messagebox).
   - In-range (`0`, `15`, `999`) → setting updated.

4. **`effective_attendance` for lupa_absen_datang with both NULL**:
   - Input row: masuk=NULL, keluar=NULL, category=lupa_absen_datang.
   - Assert: masuk = `"08:00"` (when penalty=0) or `"08:15"` (when penalty=15), terlambat_menit equals penalty.

---

## Section 3 — Export Fix: Hari Libur Row Format in Laporan Bulanan

### Current behavior (report_generator.py `_write_data_row` `is_holiday=True` branch)

```python
"Hari Kerja",   # E Tipe (override)         ← wrong
"Libur",        # G Masuk -> marker text    ← wrong
"",             # H Keluar                   ← correct
```

### Target behavior

```python
"Hari Libur",   # E Tipe — matches DB tipe value (1:1 with attendance_records.tipe)
"",             # G Masuk — empty
"",             # H Keluar — empty
```

Plus: apply a yellow fill (`FFFFF2CC`, light cream/calendar-yellow) to all 17 cells of the holiday row so it's visually distinct.

### Code changes (`src/core/report_generator.py`)

**Add module constant** near existing `TOTAL_PERSONAL_FILL`:

```python
HOLIDAY_FILL = PatternFill(fill_type="solid", fgColor="FFFFF2CC")
```

**Update `_write_data_row`** is_holiday branch:

```python
if is_holiday:
    values = [
        db_row["nama"],              # A
        db_row.get("dept") or "",     # B
        tanggal_val,                 # C
        db_row.get("hari") or "",     # D
        "Hari Libur",                # E Tipe — was "Hari Kerja"
        db_row.get("jadwal") or "",   # F
        "",                          # G Masuk — was "Libur"
        "",                          # H Keluar
        "", "", "", "", "", "", "", "",  # I-P counts blank
        "",                          # Q Alasan Ijin blank
    ]
    for col, val in enumerate(values, start=1):
        ws.cell(row=row_num, column=col, value=val)
    _apply_row_styles(ws, row_num, styles)
    # Overlay holiday fill on top of base styles
    for col in range(1, 18):
        cell = ws.cell(row=row_num, column=col)
        if not isinstance(cell, MergedCell):
            cell.fill = HOLIDAY_FILL
    return
```

The fill loop matches the existing pattern in `_write_total_row` (which overlays `TOTAL_PERSONAL_FILL` after `_apply_row_styles`). The `MergedCell` guard is the same safety measure.

### Files affected

- `src/core/report_generator.py` — single function plus one constant.

### Tests

Update existing Laporan Bulanan holiday test (search for the test that exercises `is_holiday=True` path):

- Assert column E (Tipe) cell value is `"Hari Libur"` (was `"Hari Kerja"`).
- Assert column G (Masuk) cell value is `""` (was `"Libur"`).
- Assert column H (Keluar) cell value is `""` (unchanged).
- Assert `cell.fill.fgColor.rgb == "FFFFF2CC"` for at least one cell in the holiday row (sample column A or E).

### Out of scope (deliberate)

- `src/core/weekly_export.py` (Mingguan export) — already does Tipe='Hari Libur' and blanks Masuk/Keluar. Missing only the fill color treatment. **Will not touch unless user explicitly asks.**

---

## Cross-Section Concerns

### Test baseline

Current: 241 passing on v14. Expected after v15:

- Migration test (4 assertions): +1 test
- Dashboard tidak_hadir exclusion: +1 test
- Settings validation: +3 tests (out-of-range, non-integer, in-range — likely as parametrize cases counted as 1)
- effective_attendance both-NULL: +1 test
- Updates to existing lupa_absen tests: 0 net (just rename categories)
- Laporan Bulanan holiday test updates: 0 net (existing test gets new assertions)

Estimated v15 baseline: **~245 passing**. The implementation plan can pin the exact number once tests are written.

### Migration safety

The `_migrate` schema change runs at startup on every app launch. It's idempotent (catch-all sweep means re-running finds nothing to update). Backout: if the user reverts to v14, the new categories `lupa_absen_datang` / `lupa_absen_pulang` would not be in v14's `REASON_LABELS` dict — `render_alasan_ijin` would raise `ValueError`. So v14 → v15 is a one-way migration. This is acceptable per project convention (vN snapshots are forward-only).

### v15 milestone deliverables (per CLAUDE.md framework)

1. All code changes + tests committed.
2. `pytest -q` passes (~245 baseline).
3. `APP_VERSION` bumped from `14.0.0` → `15.0.0` in `src/config.py`.
4. Installer rebuilt: `installer/Output/HR-Absensi-Setup-v15.0.0.exe`.
5. `dist/HR-Absensi/` rotated (per Rule 2: current → .bak → .bak.old).
6. Manual smoke: app launches, dashboard renders, Resolve Massal works for all 10 categories, Laporan Bulanan export inspection.
7. `git push origin v15` (only after smoke passes).
8. `memory/version_state.md` updated with v15 row.

---

## Out of Scope (NOT in this milestone)

- Weekly export holiday fill color (only Laporan Bulanan gets it in v15).
- Renaming the setting key `lupa_absen_datang_penalty_min` (already correctly named).
- Adding penalty configurability per-category beyond datang (only datang has a penalty by design).
- Any other smoke-test findings not in this spec.
