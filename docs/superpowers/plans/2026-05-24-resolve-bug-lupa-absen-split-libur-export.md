# v15: Resolve Massal Bug · Lupa Absen Split · Hari Libur Export — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship v15 milestone bundling three smoke-test findings from v14 — (1) fix the Resolve Massal save button vanishing for no-detail categories, (2) split `lupa_absen` into Datang + Pulang with migration and Dashboard exclusion, (3) fix Laporan Bulanan holiday row format to put `"Hari Libur"` in Tipe column with light yellow fill.

**Architecture:** Three loosely-coupled sections delivered as one cumulative milestone on v14. Lupa Absen change has an internal dependency chain (data model → effective_attendance → migration → dashboard SQL → test fixture cleanup → drop legacy "lupa_absen"). Bug fix and Laporan Bulanan changes are independent. Release sequence per CLAUDE.md framework: bump APP_VERSION → installer build → rotate dist/ → smoke → push v15.

**Tech Stack:** Python 3.13, customtkinter (UI), SQLite (data/hr.db), openpyxl (Excel export), Jinja2 (HTML print), pytest (tests), PyInstaller + Inno Setup 6 (bundle).

**Spec:** `docs/superpowers/specs/2026-05-24-resolve-bug-lupa-absen-split-libur-export-design.md` (commit `1cf8325`).

**Test baseline:** 241 passing on v14. Target: **256 passing on v15** (+15 net new tests: 1 for batch_resolve btn_row attr, 4 for effective_attendance (datang forgot-in, datang both-null, datang zero-penalty, pulang no-correction), 4 for schema migration (datang/pulang/fallback/idempotency), 2 for dashboard tidak_hadir exclusion, 4 for settings validation; existing holiday test + lupa_absen renames are updates-in-place, net 0).

---

## File Structure

**Modified:**
- `src/config.py` — REASON_CATEGORIES tuple (drop `lupa_absen`, add `lupa_absen_datang` + `lupa_absen_pulang`); bump `APP_VERSION` to `"15.0.0"` at release time.
- `src/core/reason_mapper.py` — REASON_LABELS (drop old, add new); `effective_attendance()` branch logic.
- `src/core/insights.py` — `terlambat_ranking()` `tidak_hadir` SUM gains exclusion clause.
- `src/core/report_generator.py` — add `HOLIDAY_FILL` constant; `_write_data_row()` `is_holiday` branch rewrites Tipe/Masuk values and applies fill.
- `src/db/schema.py` — `_migrate()` extended with three-step UPDATE block to split legacy `lupa_absen` rows.
- `src/ui/components/batch_resolve_dialog.py` — `_build()` stores `btn_row` as `self._btn_row`; `_on_cat_change()` calls `pack_forget()`/`pack()` on it.
- `src/ui/screens/settings.py` — `_save()` validates `lupa_penalty` is integer in `[0, 999]`.
- Existing test files: see Task F for the list.

**Created:**
- (none — all changes piggyback on existing files)

---

## Task A: Fix Resolve Massal save button vanishing

**Spec section:** §1.

**Files:**
- Modify: `src/ui/components/batch_resolve_dialog.py:192-210` (`_build` btn_row construction) and `:237-243` (`_on_cat_change`).

**Note:** No automated test possible — UI testing is manual per project policy (`memory/workflow_rules.md`). The construction smoke test in `tests/test_batch_resolve_dialog.py` exercises the build path but doesn't verify visual layout. We add a unit test that asserts `self._btn_row` is a real attribute after build, which proves the refactor was applied without regressions to dialog construction.

- [ ] **Step 1: Write failing unit test**

Add to `tests/test_batch_resolve_dialog.py` after `test_batch_resolve_dialog_constructs_with_no_issues`:

```python
def test_batch_resolve_dialog_btn_row_attr_exposed(temp_db_path, monkeypatch, tk_root):
    """btn_row must be exposed as self._btn_row so _on_cat_change can re-pack it.

    Regression guard for the v15 fix: bottom-side pack manager won't reflow
    on detail-widget toggle unless btn_row gets pack_forget()/pack() on each
    category change.
    """
    import src.ui.components.batch_resolve_dialog as mod
    monkeypatch.setattr(mod, "DB_PATH", temp_db_path)
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        a = upsert_employee(conn, no_staff="1", nama="ANDI", dept="X")
        _issue(conn, a, "2026-04-07", "Selasa")
        conn.commit()
    dlg = mod.BatchResolveDialog(
        tk_root, period_start="2026-04-01", period_end="2026-04-30",
        on_done=lambda: None)
    tk_root.update_idletasks()
    assert hasattr(dlg, "_btn_row"), "_btn_row must be set so _on_cat_change can re-pack it"
    assert dlg._btn_row.winfo_manager() == "pack"
    dlg.destroy()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd "D:/Gawe/Project X/HR App/.claude/worktrees/inspiring-dhawan-47161f"
../../../.venv/Scripts/python.exe -m pytest tests/test_batch_resolve_dialog.py::test_batch_resolve_dialog_btn_row_attr_exposed -v
```

Expected: FAIL with `AssertionError: _btn_row must be set so _on_cat_change can re-pack it`.

- [ ] **Step 3: Refactor `_build` to store btn_row as `self._btn_row`**

In `src/ui/components/batch_resolve_dialog.py`, find this block:

```python
        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(fill="x", padx=SPACE_XL, pady=(SPACE_LG, SPACE_LG),
                     side="bottom")
        self._submit_btn = ctk.CTkButton(
            btn_row, text="Resolve", command=self._on_submit,
```

Replace with:

```python
        self._btn_row = ctk.CTkFrame(self, fg_color="transparent")
        self._btn_row.pack(fill="x", padx=SPACE_XL, pady=(SPACE_LG, SPACE_LG),
                           side="bottom")
        self._submit_btn = ctk.CTkButton(
            self._btn_row, text="Resolve", command=self._on_submit,
```

Then update the remaining references in the same method from `btn_row` → `self._btn_row`:

```python
        self._submit_btn.pack(side="right")
        ctk.CTkButton(
            self._btn_row, text="Batal", command=self._on_cancel,
            fg_color="transparent", hover_color=COLOR_SURFACE_HIGH,
            border_width=1, border_color=COLOR_INFO, text_color=COLOR_INFO,
            width=120, height=40, font=FONT_BODY_BOLD, corner_radius=RADIUS_MD,
        ).pack(side="right", padx=(0, SPACE_MD))
        self._preview = ctk.CTkLabel(
            self._btn_row, text="0 tanggal dipilih", font=FONT_SMALL,
            text_color=COLOR_TEXT_DIM)
        self._preview.pack(side="left")
```

- [ ] **Step 4: Modify `_on_cat_change` to re-pack `self._btn_row`**

Replace the existing `_on_cat_change` method (around line 237):

```python
    def _on_cat_change(self, _label):
        key = self._label_to_key.get(self._cat_var.get(), "")
        self._detail_label.pack_forget()
        self._detail_entry.pack_forget()
        if key in REASON_NEEDS_DETAIL:
            self._detail_label.pack(anchor="w")
            self._detail_entry.pack(anchor="w", pady=(SPACE_XS, 0))
        # Force a full reflow of the bottom button row. Without this, tkinter's
        # pack manager leaves self._btn_row "lost" (geometrically zero-height)
        # when only top-side detail widgets get toggled, hiding the Resolve
        # button. Single-resolve form (issues.py _lay_out_form) avoids this
        # quirk by repacking save_btn on every category change.
        self._btn_row.pack_forget()
        self._btn_row.pack(fill="x", padx=SPACE_XL, pady=(SPACE_LG, SPACE_LG),
                           side="bottom")
```

- [ ] **Step 5: Run test to verify it passes**

```bash
../../../.venv/Scripts/python.exe -m pytest tests/test_batch_resolve_dialog.py -v
```

Expected: ALL 5 tests in this file pass (including the new btn_row attr test).

- [ ] **Step 6: Commit**

```bash
git add src/ui/components/batch_resolve_dialog.py tests/test_batch_resolve_dialog.py
git commit -m "$(cat <<'EOF'
fix(batch-resolve): repack btn_row on category change so Resolve button stays visible

Tkinter's pack manager leaves bottom-side siblings "lost" (allocated
space but rendered at zero height) when only top-side widgets get
pack_forget/pack toggled. For categories that don't trigger the detail
field (Tugas Belajar, Lupa Absen, Cuti, NA, Libur), this hid the
Resolve button until the user flipped to a needs-detail category and
back.

Fix mirrors the single-resolve form pattern in issues.py: pack_forget
and re-pack the entire btn_row on every category change, forcing a
full reflow pass.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task B: Add `lupa_absen_datang` & `lupa_absen_pulang` to data model

**Spec section:** §2 — data model changes.

**Strategy:** Additive change first — keep `lupa_absen` alongside the new categories for transitional safety. Task G (later) drops `lupa_absen` once all callers are migrated.

**Files:**
- Modify: `src/config.py` — REASON_CATEGORIES tuple.
- Modify: `src/core/reason_mapper.py` — REASON_LABELS dict.
- Modify: `tests/test_reason_mapper.py` — update `test_all_10_categories_present` to expect 12 categories.

- [ ] **Step 1: Update failing test for category set**

In `tests/test_reason_mapper.py`, replace the existing `test_all_10_categories_present` (line 5-9):

```python
def test_all_categories_present():
    """v15: split lupa_absen → lupa_absen_datang + lupa_absen_pulang.
    Both new + old (transitional) categories live in REASON_LABELS until
    legacy cleanup task drops `lupa_absen`.
    """
    assert set(REASON_LABELS.keys()) == {
        "tugas_lapangan", "tugas_paparan", "izin_sakit", "cuti", "tugas_belajar",
        "terlambat_kerja", "terlambat_lain",
        "lupa_absen",            # transitional — dropped in cleanup task
        "lupa_absen_datang",     # NEW
        "lupa_absen_pulang",     # NEW
        "libur", "na",
    }
```

- [ ] **Step 2: Run test to verify it fails**

```bash
../../../.venv/Scripts/python.exe -m pytest tests/test_reason_mapper.py::test_all_categories_present -v
```

Expected: FAIL — REASON_LABELS still has 10 entries, not 12.

- [ ] **Step 3: Add new categories to REASON_CATEGORIES tuple**

In `src/config.py`, replace the existing REASON_CATEGORIES tuple (around line 59-70):

```python
# Reason categories (canonical IDs used in DB and UI)
REASON_CATEGORIES = (
    "tugas_lapangan",
    "tugas_paparan",
    "izin_sakit",
    "cuti",
    "tugas_belajar",
    "terlambat_kerja",
    "terlambat_lain",
    "lupa_absen",            # transitional — kept during v15 migration; dropped in cleanup task
    "lupa_absen_datang",     # NEW v15
    "lupa_absen_pulang",     # NEW v15
    "libur",
    "na",
)
```

- [ ] **Step 4: Add new categories to REASON_LABELS**

In `src/core/reason_mapper.py`, replace the existing REASON_LABELS dict (line 5-17):

```python
# Human-readable labels for UI
REASON_LABELS = {
    "tugas_lapangan":     "Tugas Lapangan",
    "tugas_paparan":      "Tugas Paparan",
    "izin_sakit":         "Izin Sakit",
    "cuti":               "Cuti",
    "tugas_belajar":      "Tugas Belajar/Kuliah",
    "terlambat_kerja":    "Masuk Terlambat dengan Alasan Pekerjaan",
    "terlambat_lain":     "Terlambat dengan alasan",
    "lupa_absen":         "Lupa Absen",            # transitional — see cleanup task
    "lupa_absen_datang":  "Lupa Absen Datang",     # NEW v15
    "lupa_absen_pulang":  "Lupa Absen Pulang",     # NEW v15
    "libur":              "Libur",
    "na":                 "NA / Belum ada kabar",
}
```

- [ ] **Step 5: Run the targeted test**

```bash
../../../.venv/Scripts/python.exe -m pytest tests/test_reason_mapper.py -v
```

Expected: ALL existing reason_mapper tests pass + the renamed `test_all_categories_present` passes.

- [ ] **Step 6: Run full test suite to confirm no regressions**

```bash
../../../.venv/Scripts/python.exe -m pytest -q
```

Expected: 242 passed (Task A added 1 new test; Task B only added dict entries, no new tests).

- [ ] **Step 7: Commit**

```bash
git add src/config.py src/core/reason_mapper.py tests/test_reason_mapper.py
git commit -m "$(cat <<'EOF'
feat(reasons): add lupa_absen_datang & lupa_absen_pulang categories

Additive change: new categories live alongside the legacy 'lupa_absen'
key for transitional safety. effective_attendance and other consumers
get updated to handle the new keys in subsequent commits, then the
legacy key gets dropped once nothing references it.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task C: Update `effective_attendance` for new categories

**Spec section:** §2 — effective_attendance update.

**Files:**
- Modify: `src/core/reason_mapper.py` — `effective_attendance()` function.
- Modify: `tests/test_reason_mapper.py` — add new test cases.

- [ ] **Step 1: Add failing tests for new categories**

Append to `tests/test_reason_mapper.py`:

```python
def test_effective_attendance_lupa_datang_forgot_clock_in():
    """Lupa Absen Datang with masuk=NULL, keluar set: penalty applied."""
    row = _att_row(reason_category="lupa_absen_datang", masuk=None, keluar="16:05",
                   terlambat_menit=None)
    eff = effective_attendance(row, schedule_start="08.00", lupa_penalty_min=15)
    assert eff == {"masuk": "08:15", "terlambat_menit": 15}


def test_effective_attendance_lupa_datang_both_null():
    """Lupa Absen Datang with both masuk AND keluar NULL: penalty still applied
    because user explicitly labeled the row as 'datang missing'."""
    row = _att_row(reason_category="lupa_absen_datang", masuk=None, keluar=None,
                   terlambat_menit=None)
    eff = effective_attendance(row, schedule_start="08.00", lupa_penalty_min=15)
    assert eff == {"masuk": "08:15", "terlambat_menit": 15}


def test_effective_attendance_lupa_datang_zero_penalty():
    """Penalty=0 means karyawan dianggap masuk tepat pukul 08:00, no terlambat."""
    row = _att_row(reason_category="lupa_absen_datang", masuk=None, keluar="16:00",
                   terlambat_menit=None)
    eff = effective_attendance(row, schedule_start="08.00", lupa_penalty_min=0)
    assert eff == {"masuk": "08:00", "terlambat_menit": 0}


def test_effective_attendance_lupa_pulang_no_correction():
    """Lupa Absen Pulang: raw masuk preserved, no penalty applied to terlambat."""
    row = _att_row(reason_category="lupa_absen_pulang", masuk="08:05", keluar=None,
                   terlambat_menit=5)
    eff = effective_attendance(row, schedule_start="08.00", lupa_penalty_min=15)
    assert eff == {"masuk": "08:05", "terlambat_menit": 5}
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
../../../.venv/Scripts/python.exe -m pytest tests/test_reason_mapper.py::test_effective_attendance_lupa_datang_forgot_clock_in tests/test_reason_mapper.py::test_effective_attendance_lupa_datang_both_null tests/test_reason_mapper.py::test_effective_attendance_lupa_datang_zero_penalty tests/test_reason_mapper.py::test_effective_attendance_lupa_pulang_no_correction -v
```

Expected: FAIL — first three fail because `lupa_absen_datang` falls through to "no correction" (raw masuk=None preserved). Fourth one may pass coincidentally (no correction for unknown category equals raw values).

- [ ] **Step 3: Update `effective_attendance` function**

In `src/core/reason_mapper.py`, replace the existing lupa_absen branch (around line 89-94):

```python
    if cat == "lupa_absen" and masuk is None and keluar is not None:
        return {
            "masuk": _minutes_to_hhmm(
                _schedule_start_minutes(schedule_start) + lupa_penalty_min),
            "terlambat_menit": lupa_penalty_min,
        }

    return {"masuk": masuk, "terlambat_menit": terlambat}
```

With:

```python
    # NEW (v15): explicit Datang/Pulang split
    # Datang: penalty applies whenever masuk is missing (regardless of keluar).
    if cat == "lupa_absen_datang" and masuk is None:
        return {
            "masuk": _minutes_to_hhmm(
                _schedule_start_minutes(schedule_start) + lupa_penalty_min),
            "terlambat_menit": lupa_penalty_min,
        }
    # Pulang: no correction, raw values pass through. Explicit no-op for clarity.
    if cat == "lupa_absen_pulang":
        return {"masuk": masuk, "terlambat_menit": terlambat}

    # LEGACY (transitional): pre-migration 'lupa_absen' rows still get the old
    # behavior. Dropped in cleanup task once schema migration has split them all.
    if cat == "lupa_absen" and masuk is None and keluar is not None:
        return {
            "masuk": _minutes_to_hhmm(
                _schedule_start_minutes(schedule_start) + lupa_penalty_min),
            "terlambat_menit": lupa_penalty_min,
        }

    return {"masuk": masuk, "terlambat_menit": terlambat}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
../../../.venv/Scripts/python.exe -m pytest tests/test_reason_mapper.py -v
```

Expected: ALL tests in this file pass (existing 14 + 4 new = 18).

- [ ] **Step 5: Run full suite to confirm no regressions**

```bash
../../../.venv/Scripts/python.exe -m pytest -q
```

Expected: 246 passed (242 after Task B + 4 new in this task = 246).

- [ ] **Step 6: Commit**

```bash
git add src/core/reason_mapper.py tests/test_reason_mapper.py
git commit -m "$(cat <<'EOF'
feat(reasons): effective_attendance handles lupa_absen_datang/pulang

Datang applies penalty whenever masuk is missing (not just when
keluar is set — user-labeled 'datang missing' is source of truth
even in the both-NULL edge case).

Pulang explicitly returns raw values (no correction).

Legacy 'lupa_absen' branch retained for transitional safety.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task D: Schema migration — auto-split legacy `lupa_absen` rows

**Spec section:** §2 — schema migration.

**Files:**
- Modify: `src/db/schema.py` — `_migrate()` function.
- Modify: `tests/test_schema.py` — add migration test.

- [ ] **Step 1: Write failing migration tests**

Append to `tests/test_schema.py`:

```python
def test_migrate_splits_legacy_lupa_absen_datang(temp_db_path):
    """Legacy lupa_absen rows with masuk=NULL migrate to lupa_absen_datang."""
    init_db(temp_db_path)
    with sqlite3.connect(temp_db_path) as conn:
        # Set up an employee + an attendance row with legacy lupa_absen + masuk=NULL
        conn.execute(
            "INSERT INTO employees (no_staff, nama) VALUES ('1', 'ANDI')"
        )
        emp_id = conn.execute("SELECT id FROM employees WHERE no_staff='1'").fetchone()[0]
        conn.execute(
            "INSERT INTO attendance_records "
            "(employee_id, tanggal, hari, tipe, masuk, keluar, "
            "has_issue, reason_category, imported_from, imported_at) "
            "VALUES (?, '2026-04-01', 'Rabu', 'Hari Kerja', NULL, '16:00', "
            "1, 'lupa_absen', 't.xls', '2026-04-01T00:00:00+00:00')",
            (emp_id,),
        )
        conn.commit()
    # Re-run init_db to trigger migration
    init_db(temp_db_path)
    with sqlite3.connect(temp_db_path) as conn:
        cat = conn.execute(
            "SELECT reason_category FROM attendance_records"
        ).fetchone()[0]
    assert cat == "lupa_absen_datang"


def test_migrate_splits_legacy_lupa_absen_pulang(temp_db_path):
    """Legacy lupa_absen rows with masuk set, keluar=NULL migrate to lupa_absen_pulang."""
    init_db(temp_db_path)
    with sqlite3.connect(temp_db_path) as conn:
        conn.execute(
            "INSERT INTO employees (no_staff, nama) VALUES ('1', 'ANDI')"
        )
        emp_id = conn.execute("SELECT id FROM employees WHERE no_staff='1'").fetchone()[0]
        conn.execute(
            "INSERT INTO attendance_records "
            "(employee_id, tanggal, hari, tipe, masuk, keluar, "
            "has_issue, reason_category, imported_from, imported_at) "
            "VALUES (?, '2026-04-01', 'Rabu', 'Hari Kerja', '08:05', NULL, "
            "1, 'lupa_absen', 't.xls', '2026-04-01T00:00:00+00:00')",
            (emp_id,),
        )
        conn.commit()
    init_db(temp_db_path)
    with sqlite3.connect(temp_db_path) as conn:
        cat = conn.execute(
            "SELECT reason_category FROM attendance_records"
        ).fetchone()[0]
    assert cat == "lupa_absen_pulang"


def test_migrate_splits_legacy_lupa_absen_fallback_both_null(temp_db_path):
    """Legacy lupa_absen rows with both masuk AND keluar NULL fallback to
    lupa_absen_datang (conservative — applies penalty)."""
    init_db(temp_db_path)
    with sqlite3.connect(temp_db_path) as conn:
        conn.execute(
            "INSERT INTO employees (no_staff, nama) VALUES ('1', 'ANDI')"
        )
        emp_id = conn.execute("SELECT id FROM employees WHERE no_staff='1'").fetchone()[0]
        conn.execute(
            "INSERT INTO attendance_records "
            "(employee_id, tanggal, hari, tipe, masuk, keluar, "
            "has_issue, reason_category, imported_from, imported_at) "
            "VALUES (?, '2026-04-01', 'Rabu', 'Hari Kerja', NULL, NULL, "
            "1, 'lupa_absen', 't.xls', '2026-04-01T00:00:00+00:00')",
            (emp_id,),
        )
        conn.commit()
    init_db(temp_db_path)
    with sqlite3.connect(temp_db_path) as conn:
        cat = conn.execute(
            "SELECT reason_category FROM attendance_records"
        ).fetchone()[0]
    assert cat == "lupa_absen_datang"


def test_migrate_lupa_absen_idempotent(temp_db_path):
    """Running migration twice leaves the table in the same state — no
    rows are still 'lupa_absen', and split rows aren't re-touched."""
    init_db(temp_db_path)
    with sqlite3.connect(temp_db_path) as conn:
        conn.execute(
            "INSERT INTO employees (no_staff, nama) VALUES ('1', 'ANDI')"
        )
        emp_id = conn.execute("SELECT id FROM employees WHERE no_staff='1'").fetchone()[0]
        conn.execute(
            "INSERT INTO attendance_records "
            "(employee_id, tanggal, hari, tipe, masuk, keluar, "
            "has_issue, reason_category, imported_from, imported_at) "
            "VALUES (?, '2026-04-01', 'Rabu', 'Hari Kerja', NULL, '16:00', "
            "1, 'lupa_absen', 't.xls', '2026-04-01T00:00:00+00:00')",
            (emp_id,),
        )
        conn.commit()
    init_db(temp_db_path)
    init_db(temp_db_path)  # second migration pass
    with sqlite3.connect(temp_db_path) as conn:
        cat = conn.execute(
            "SELECT reason_category FROM attendance_records"
        ).fetchone()[0]
        legacy_count = conn.execute(
            "SELECT COUNT(*) FROM attendance_records WHERE reason_category='lupa_absen'"
        ).fetchone()[0]
    assert cat == "lupa_absen_datang"
    assert legacy_count == 0
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
../../../.venv/Scripts/python.exe -m pytest tests/test_schema.py -v -k "lupa"
```

Expected: All 4 new tests FAIL — they expect new category values but migration doesn't exist yet, so reason_category stays as `'lupa_absen'`.

- [ ] **Step 3: Add migration SQL to `_migrate()`**

In `src/db/schema.py`, append to the end of `_migrate()` (after the coaching_threshold block):

```python
    # v15: split legacy 'lupa_absen' into lupa_absen_datang / lupa_absen_pulang.
    # Idempotent: after the catch-all sweep, no rows have 'lupa_absen' left;
    # subsequent passes find nothing to update.
    #
    # Order matters:
    #   1. Rows where karyawan forgot to scan IN (masuk NULL) → datang.
    #   2. Rows where karyawan forgot to scan OUT (masuk set, keluar NULL) → pulang.
    #   3. Catch-all sweep → datang (conservative; applies penalty).
    conn.execute(
        "UPDATE attendance_records "
        "SET reason_category = 'lupa_absen_datang' "
        "WHERE reason_category = 'lupa_absen' "
        "  AND masuk IS NULL"
    )
    conn.execute(
        "UPDATE attendance_records "
        "SET reason_category = 'lupa_absen_pulang' "
        "WHERE reason_category = 'lupa_absen' "
        "  AND masuk IS NOT NULL "
        "  AND keluar IS NULL"
    )
    conn.execute(
        "UPDATE attendance_records "
        "SET reason_category = 'lupa_absen_datang' "
        "WHERE reason_category = 'lupa_absen'"
    )
```

- [ ] **Step 4: Run migration tests to verify they pass**

```bash
../../../.venv/Scripts/python.exe -m pytest tests/test_schema.py -v -k "lupa"
```

Expected: All 4 lupa migration tests PASS.

- [ ] **Step 5: Run full suite**

```bash
../../../.venv/Scripts/python.exe -m pytest -q
```

Expected: 250 passed (246 after Task C + 4 new in this task = 250).

- [ ] **Step 6: Commit**

```bash
git add src/db/schema.py tests/test_schema.py
git commit -m "$(cat <<'EOF'
feat(schema): migrate legacy 'lupa_absen' rows to datang/pulang split

Idempotent 3-step UPDATE block runs in _migrate() on every init_db():
  1. masuk IS NULL → lupa_absen_datang
  2. masuk set, keluar IS NULL → lupa_absen_pulang
  3. catch-all (both NULL, both set, or unexpected) → lupa_absen_datang

After all three statements, no row has reason_category='lupa_absen'.
Re-running finds zero rows to update — fully idempotent.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task E: Dashboard `tidak_hadir` excludes `lupa_absen_datang`

**Spec section:** §2 — Dashboard tidak_hadir SQL update.

**Files:**
- Modify: `src/core/insights.py` — `terlambat_ranking()` SQL.
- Modify: `tests/test_insights.py` — add exclusion test.

- [ ] **Step 1: Write failing test**

Append to `tests/test_insights.py`:

```python
def test_terlambat_ranking_excludes_lupa_datang_from_tidak_hadir(temp_db_path):
    """A Hari Kerja row with both masuk & keluar NULL but marked as
    lupa_absen_datang must NOT count as tidak_hadir. This is the user's
    explicit v15 requirement — once resolved as 'datang missing scan',
    the day is considered attended."""
    from src.db.schema import init_db
    from src.db.connection import get_connection
    from src.db.employees import upsert_employee
    from src.db.attendance import upsert_attendance, set_reason
    from src.core.insights import terlambat_ranking

    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        emp = upsert_employee(conn, no_staff="1", nama="ANDI", dept="X")
        upsert_attendance(
            conn, employee_id=emp, tanggal="2026-04-01", hari="Rabu",
            tipe="Hari Kerja", jadwal="08.00 - 16.00",
            masuk=None, keluar=None, kerja_jam=None, lembur_jam=None,
            terlambat_menit=None, has_issue=1, imported_from="t.xls",
        )
        rid = conn.execute("SELECT id FROM attendance_records").fetchone()["id"]
        set_reason(conn, attendance_id=rid, category="lupa_absen_datang", detail=None)
        ranking = terlambat_ranking(conn, "2026-04-01", "2026-04-30")
    assert len(ranking) == 1
    assert ranking[0]["tidak_hadir"] == 0
    assert ranking[0]["absent_count"] == 0


def test_terlambat_ranking_unresolved_both_null_still_counts(temp_db_path):
    """Sanity: unresolved (reason_category=NULL) both-NULL row still counts
    as tidak_hadir. Confirms the exclusion only triggers on lupa_absen_datang."""
    from src.db.schema import init_db
    from src.db.connection import get_connection
    from src.db.employees import upsert_employee
    from src.db.attendance import upsert_attendance
    from src.core.insights import terlambat_ranking

    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        emp = upsert_employee(conn, no_staff="1", nama="ANDI", dept="X")
        upsert_attendance(
            conn, employee_id=emp, tanggal="2026-04-01", hari="Rabu",
            tipe="Hari Kerja", jadwal="08.00 - 16.00",
            masuk=None, keluar=None, kerja_jam=None, lembur_jam=None,
            terlambat_menit=None, has_issue=1, imported_from="t.xls",
        )
        ranking = terlambat_ranking(conn, "2026-04-01", "2026-04-30")
    assert ranking[0]["tidak_hadir"] == 1
```

- [ ] **Step 2: Run tests to verify the first fails**

```bash
../../../.venv/Scripts/python.exe -m pytest tests/test_insights.py::test_terlambat_ranking_excludes_lupa_datang_from_tidak_hadir tests/test_insights.py::test_terlambat_ranking_unresolved_both_null_still_counts -v
```

Expected: first test FAILS (counts as 1, not 0). Second test passes (sanity check, no new behavior).

- [ ] **Step 3: Update SQL in `terlambat_ranking`**

In `src/core/insights.py`, find the existing `tidak_hadir` SUM in `terlambat_ranking()` (around line 44-46):

```python
               SUM(CASE WHEN ar.tipe = 'Hari Kerja'
                          AND ar.masuk IS NULL AND ar.keluar IS NULL
                        THEN 1 ELSE 0 END) AS tidak_hadir,
```

Replace with:

```python
               SUM(CASE WHEN ar.tipe = 'Hari Kerja'
                          AND ar.masuk IS NULL AND ar.keluar IS NULL
                          AND (ar.reason_category IS NULL
                               OR ar.reason_category != 'lupa_absen_datang')
                        THEN 1 ELSE 0 END) AS tidak_hadir,
```

Also update the docstring (around line 14-16) to note the exclusion:

```python
    """Ranking lengkap karyawan untuk periode tertentu, urut by severity.

    A row contributes to terlambat aggregations only if the employee
    actually clocked in (`masuk IS NOT NULL`). Truly absent days
    (both masuk AND keluar NULL on Hari Kerja) are counted separately
    as `tidak_hadir` (alias: `absent_count`). Rows resolved as
    `lupa_absen_datang` are excluded from `tidak_hadir` because the
    user explicitly asserted that the karyawan came but missed the
    morning fingerprint scan (v15).
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
../../../.venv/Scripts/python.exe -m pytest tests/test_insights.py -v
```

Expected: ALL tests in this file pass.

- [ ] **Step 5: Run full suite**

```bash
../../../.venv/Scripts/python.exe -m pytest -q
```

Expected: 252 passed (250 after Task D + 2 new in this task = 252).

- [ ] **Step 6: Commit**

```bash
git add src/core/insights.py tests/test_insights.py
git commit -m "$(cat <<'EOF'
feat(dashboard): exclude lupa_absen_datang from tidak_hadir count

Once a both-NULL row is resolved as lupa_absen_datang, the karyawan
is treated as having attended (just missed the morning scan). The
dashboard ranking table 'Tdk Hadir' column and the printed report
'absent_count' both feed from this SQL, so the single change covers
both surfaces.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task F: Migrate existing test fixtures from `lupa_absen` to new categories

**Spec section:** §2 — preparation for cleanup task.

**Goal:** Replace every test fixture that uses `category="lupa_absen"` with the appropriate new category, so Task G can safely drop `lupa_absen` from the data model.

**Affected files:**
- `tests/test_attendance_repo.py:49,59,96` — generic attendance repo tests; use `lupa_absen_datang` (forgot-IN scenario in those fixtures).
- `tests/test_reason_mapper.py:24,78,85,104` — already updated in Task B/C; verify nothing references bare `"lupa_absen"` in assertions.
- `tests/test_report_generator.py:281` — forgot-IN scenario; use `lupa_absen_datang`.
- `tests/test_weekly_export.py:124` — forgot-IN scenario; use `lupa_absen_datang`.
- `tests/test_report_filler.py:20` — `lupa keluar` per comment; use `lupa_absen_pulang`. Verify test assertions still hold (the test asserts "Lupa Absen" label appears in the alasan column — `lupa_absen_pulang` renders as "Lupa Absen Pulang", different string).

**Files:**
- Modify: 5 test files above.

- [ ] **Step 1: Update `tests/test_attendance_repo.py`**

Find all 3 occurrences of `category="lupa_absen"` and change to `category="lupa_absen_datang"`. Also update the assertion at line 59:

```python
assert row["reason_category"] == "lupa_absen_datang"  # preserved
```

Use grep first to find the exact lines:

```bash
grep -n "lupa_absen" tests/test_attendance_repo.py
```

Expected output:
```
49:        set_reason(conn, attendance_id=rec["id"], category="lupa_absen", detail=None)
59:        assert row["reason_category"] == "lupa_absen"  # preserved
96:        set_reason(conn, attendance_id=first["id"], category="lupa_absen", detail=None)
```

Replace all 3 with `lupa_absen_datang` via Edit tool (one replacement per line; the file context disambiguates each).

- [ ] **Step 2: Update `tests/test_reason_mapper.py`**

The test `test_render_without_detail` at line 21-25 references `render_alasan_ijin("lupa_absen", None) == "Lupa Absen"`. This still works because `lupa_absen` is in REASON_LABELS during the transitional window. **Leave this test as-is for now** — Task G will adjust it when dropping the legacy key.

The `test_effective_attendance_*` tests at lines 77-107 use `reason_category="lupa_absen"`:
- Line 78 (`forgot_clock_in`) — change to `"lupa_absen_datang"`. The test asserts penalty applied — still correct under new behavior.
- Line 85 (`forgot_clock_out_untouched`) — change to `"lupa_absen_pulang"`. The test asserts raw values preserved — still correct.
- Line 104 (`custom_penalty`) — change to `"lupa_absen_datang"`.

Use Edit on each occurrence. Verify the assertion semantics still match the new category's behavior (they do; see Task C).

- [ ] **Step 3: Update `tests/test_report_generator.py`**

Change line 281 from `category="lupa_absen"` to `category="lupa_absen_datang"`. The test docstring already says "forgot-IN row" — semantics match.

Also check the existing column-O assertion at line 287: `assert ws.cell(row=3, column=15).value in (None, "")`. Find the source of column-O "lupa_hari" derivation in `src/core/report_generator.py` `compute_derived()`. Verify that effective_attendance returning a non-None masuk for lupa_absen_datang causes lupa_hari=0 (because masuk gets set, `compute_derived` no longer sees forgot-IN pattern). This is preserved by the existing flow — no code change needed.

- [ ] **Step 4: Update `tests/test_weekly_export.py`**

Read line 124 context first:

```bash
sed -n '115,135p' tests/test_weekly_export.py
```

Change `category="lupa_absen"` to `category="lupa_absen_datang"`. Update any assertion that references the literal `"lupa_absen"` string (none expected — the export writes the LABEL "Lupa Absen", not the category key).

- [ ] **Step 5: Update `tests/test_report_filler.py`**

This file has TWO references on lines 20 and 42 (`lupa_absen → "Lupa Absen"`). The test comment on line 11 says "Day 2: lupa keluar — user inputs 'lupa_absen'" — that's the lupa_absen_pulang case (keluar missing).

Change line 20 to `category="lupa_absen_pulang"`. Update line 42 comment to: `# Row 4: BUDI 2026-04-02 (lupa_absen_pulang → "Lupa Absen Pulang")`.

If the test asserts the literal string "Lupa Absen" in an Excel cell, update it to "Lupa Absen Pulang". Verify by reading the assertion context:

```bash
sed -n '35,60p' tests/test_report_filler.py
```

Apply the necessary updates so the assertion matches the new label.

- [ ] **Step 6: Run full test suite to confirm everything still passes**

```bash
../../../.venv/Scripts/python.exe -m pytest -q
```

Expected: 252 passed (same as Task E baseline — Task F only updates existing fixtures, no net change in test count).

If any test fails, the root cause is usually a label-string mismatch in an Excel cell assertion (Task F Step 5 case). Read the failing test output, identify which cell now contains "Lupa Absen Datang" / "Lupa Absen Pulang" instead of "Lupa Absen", and update the assertion to match the new label.

- [ ] **Step 7: Commit**

```bash
git add tests/test_attendance_repo.py tests/test_reason_mapper.py tests/test_report_generator.py tests/test_weekly_export.py tests/test_report_filler.py
git commit -m "$(cat <<'EOF'
test: migrate fixtures from 'lupa_absen' to datang/pulang split

Prepares the test suite for the cleanup task that drops the legacy
'lupa_absen' category. Each fixture's masuk/keluar state determines
the new category:
  - masuk=NULL (forgot to scan IN) → lupa_absen_datang
  - keluar=NULL (forgot to scan OUT) → lupa_absen_pulang

Assertions that reference the label string 'Lupa Absen' updated to
'Lupa Absen Datang' or 'Lupa Absen Pulang' to match new REASON_LABELS.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task G: Drop legacy `lupa_absen` from data model

**Spec section:** §2 — final cleanup.

**Goal:** Remove the transitional `lupa_absen` key from REASON_LABELS, REASON_CATEGORIES, and the legacy branch of `effective_attendance`. After Task F, nothing should reference it.

**Files:**
- Modify: `src/config.py` — remove `"lupa_absen"` from REASON_CATEGORIES.
- Modify: `src/core/reason_mapper.py` — remove `"lupa_absen"` from REASON_LABELS; remove legacy branch in `effective_attendance`.
- Modify: `tests/test_reason_mapper.py` — update `test_all_categories_present`; remove or adapt `test_render_without_detail`'s lupa_absen assertion.

- [ ] **Step 1: Update test for category set**

In `tests/test_reason_mapper.py`, replace the existing `test_all_categories_present` body (from Task B) with:

```python
def test_all_categories_present():
    """v15: lupa_absen split is final — legacy key removed."""
    assert set(REASON_LABELS.keys()) == {
        "tugas_lapangan", "tugas_paparan", "izin_sakit", "cuti", "tugas_belajar",
        "terlambat_kerja", "terlambat_lain",
        "lupa_absen_datang",
        "lupa_absen_pulang",
        "libur", "na",
    }
```

Also update `test_render_without_detail` to use the new keys (replace the `lupa_absen` line):

```python
def test_render_without_detail():
    assert render_alasan_ijin("izin_sakit", None) == "Izin Sakit"
    assert render_alasan_ijin("cuti", None) == "Cuti"
    assert render_alasan_ijin("lupa_absen_datang", None) == "Lupa Absen Datang"
    assert render_alasan_ijin("lupa_absen_pulang", None) == "Lupa Absen Pulang"
    assert render_alasan_ijin("na", None) == "NA / Belum ada kabar"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
../../../.venv/Scripts/python.exe -m pytest tests/test_reason_mapper.py::test_all_categories_present tests/test_reason_mapper.py::test_render_without_detail -v
```

Expected: `test_all_categories_present` FAILS (REASON_LABELS still has 12 entries, not 11). `test_render_without_detail` PASSES because both new keys resolve.

- [ ] **Step 3: Remove `lupa_absen` from REASON_CATEGORIES**

In `src/config.py`, remove the `"lupa_absen",  # transitional ...` line from the tuple. Final shape:

```python
REASON_CATEGORIES = (
    "tugas_lapangan",
    "tugas_paparan",
    "izin_sakit",
    "cuti",
    "tugas_belajar",
    "terlambat_kerja",
    "terlambat_lain",
    "lupa_absen_datang",
    "lupa_absen_pulang",
    "libur",
    "na",
)
```

- [ ] **Step 4: Remove `lupa_absen` from REASON_LABELS**

In `src/core/reason_mapper.py`, remove the `"lupa_absen": "Lupa Absen", ...` line. Final shape:

```python
REASON_LABELS = {
    "tugas_lapangan":     "Tugas Lapangan",
    "tugas_paparan":      "Tugas Paparan",
    "izin_sakit":         "Izin Sakit",
    "cuti":               "Cuti",
    "tugas_belajar":      "Tugas Belajar/Kuliah",
    "terlambat_kerja":    "Masuk Terlambat dengan Alasan Pekerjaan",
    "terlambat_lain":     "Terlambat dengan alasan",
    "lupa_absen_datang":  "Lupa Absen Datang",
    "lupa_absen_pulang":  "Lupa Absen Pulang",
    "libur":              "Libur",
    "na":                 "NA / Belum ada kabar",
}
```

- [ ] **Step 5: Remove legacy branch from `effective_attendance`**

In `src/core/reason_mapper.py`, remove the LEGACY block added in Task C:

```python
    # LEGACY (transitional): pre-migration 'lupa_absen' rows still get the old
    # behavior. Dropped in cleanup task once schema migration has split them all.
    if cat == "lupa_absen" and masuk is None and keluar is not None:
        return {
            "masuk": _minutes_to_hhmm(
                _schedule_start_minutes(schedule_start) + lupa_penalty_min),
            "terlambat_menit": lupa_penalty_min,
        }
```

The function now goes from `lupa_absen_pulang` branch directly to the final `return {"masuk": masuk, "terlambat_menit": terlambat}`.

- [ ] **Step 6: Run full suite to confirm no regressions**

```bash
../../../.venv/Scripts/python.exe -m pytest -q
```

Expected: 252 passed (same as Task F — Task G only renames existing tests, no net change).

If a test fails with `ValueError: Unknown reason category: lupa_absen`, it means Task F missed a fixture. Find it via `grep -rn '"lupa_absen"' tests/` and update accordingly, then re-run.

- [ ] **Step 7: Commit**

```bash
git add src/config.py src/core/reason_mapper.py tests/test_reason_mapper.py
git commit -m "$(cat <<'EOF'
refactor(reasons): drop legacy 'lupa_absen' key

Schema migration has split all legacy rows; test fixtures all use
the explicit datang/pulang variants. REASON_LABELS and
REASON_CATEGORIES drop the bare 'lupa_absen' entry, and
effective_attendance loses its transitional legacy branch.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task H: Settings input validation (clamp `[0, 999]`)

**Spec section:** §2 — Settings UI tweak.

**Files:**
- Modify: `src/ui/screens/settings.py` — `_save()` method.
- Modify: `tests/test_settings_screen.py` — add validation tests.

- [ ] **Step 1: Read current test patterns for settings**

```bash
sed -n '1,60p' tests/test_settings_screen.py
```

Note the test pattern: most settings tests construct the screen via `SettingsScreen(tk_root)`, set `lupa_penalty_var.set("...")`, call `screen._save()`, and assert the resulting DB state.

- [ ] **Step 2: Write failing validation tests**

Append to `tests/test_settings_screen.py`:

```python
def test_save_rejects_lupa_penalty_negative(temp_db_path, monkeypatch, tk_root):
    """Negative penalty values must be rejected, settings unchanged."""
    import src.ui.screens.settings as mod
    monkeypatch.setattr(mod, "DB_PATH", temp_db_path)
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        set_setting(conn, "lupa_absen_datang_penalty_min", "15")
    monkeypatch.setattr(mod.messagebox, "showinfo", lambda *a, **k: None)
    warnings = []
    monkeypatch.setattr(
        mod.messagebox, "showwarning",
        lambda *a, **k: warnings.append(a))
    screen = mod.SettingsScreen(tk_root)
    screen.lupa_penalty_var.set("-1")
    screen._save()
    with get_connection(temp_db_path) as conn:
        assert get_setting(conn, "lupa_absen_datang_penalty_min") == "15"  # unchanged
    assert len(warnings) == 1  # showwarning called once


def test_save_rejects_lupa_penalty_too_large(temp_db_path, monkeypatch, tk_root):
    """Penalty values above 999 must be rejected, settings unchanged."""
    import src.ui.screens.settings as mod
    monkeypatch.setattr(mod, "DB_PATH", temp_db_path)
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        set_setting(conn, "lupa_absen_datang_penalty_min", "15")
    monkeypatch.setattr(mod.messagebox, "showinfo", lambda *a, **k: None)
    monkeypatch.setattr(mod.messagebox, "showwarning", lambda *a, **k: None)
    screen = mod.SettingsScreen(tk_root)
    screen.lupa_penalty_var.set("1000")
    screen._save()
    with get_connection(temp_db_path) as conn:
        assert get_setting(conn, "lupa_absen_datang_penalty_min") == "15"  # unchanged


def test_save_rejects_lupa_penalty_non_integer(temp_db_path, monkeypatch, tk_root):
    """Non-integer string (letters, decimals) must be rejected, settings unchanged."""
    import src.ui.screens.settings as mod
    monkeypatch.setattr(mod, "DB_PATH", temp_db_path)
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        set_setting(conn, "lupa_absen_datang_penalty_min", "15")
    monkeypatch.setattr(mod.messagebox, "showinfo", lambda *a, **k: None)
    monkeypatch.setattr(mod.messagebox, "showwarning", lambda *a, **k: None)
    screen = mod.SettingsScreen(tk_root)
    screen.lupa_penalty_var.set("abc")
    screen._save()
    with get_connection(temp_db_path) as conn:
        assert get_setting(conn, "lupa_absen_datang_penalty_min") == "15"


def test_save_accepts_lupa_penalty_zero(temp_db_path, monkeypatch, tk_root):
    """Zero (no penalty) must be accepted."""
    import src.ui.screens.settings as mod
    monkeypatch.setattr(mod, "DB_PATH", temp_db_path)
    init_db(temp_db_path)
    monkeypatch.setattr(mod.messagebox, "showinfo", lambda *a, **k: None)
    screen = mod.SettingsScreen(tk_root)
    screen.lupa_penalty_var.set("0")
    screen._save()
    with get_connection(temp_db_path) as conn:
        assert get_setting(conn, "lupa_absen_datang_penalty_min") == "0"
```

Note: the existing test file may already import what's needed. If not, add:

```python
from src.db.connection import get_connection
from src.db.schema import init_db
from src.db.settings import get_setting, set_setting
```

(check top-of-file imports first).

- [ ] **Step 3: Run tests to verify they fail**

```bash
../../../.venv/Scripts/python.exe -m pytest tests/test_settings_screen.py -v -k "lupa"
```

Expected: First 3 tests FAIL (current `_save` writes any string without validation). Fourth (`zero`) test passes coincidentally.

- [ ] **Step 4: Add validation to `_save`**

In `src/ui/screens/settings.py`, replace the existing `_save` method (around line 293-299):

```python
    def _save(self):
        # Validate Lupa Absen Datang penalty: integer in [0, 999]
        raw = self.lupa_penalty_var.get().strip()
        try:
            penalty = int(raw)
        except ValueError:
            messagebox.showwarning(
                "Penalti tidak valid",
                f"'{raw}' bukan angka. Penalti harus berupa bilangan "
                f"bulat antara 0 dan 999.")
            return
        if penalty < 0 or penalty > 999:
            messagebox.showwarning(
                "Penalti di luar rentang",
                f"{penalty} di luar rentang yang diizinkan. "
                f"Penalti harus antara 0 dan 999 menit.")
            return
        with get_connection(DB_PATH) as conn:
            set_setting(conn, "current_month", self.month_var.get().strip())
            set_setting(conn, "coaching_threshold_per_day", self.thr_var.get().strip())
            set_setting(conn, "lupa_absen_datang_penalty_min", str(penalty))
        messagebox.showinfo("Tersimpan", "Pengaturan disimpan.")
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
../../../.venv/Scripts/python.exe -m pytest tests/test_settings_screen.py -v
```

Expected: ALL settings_screen tests pass (existing + 4 new = check via `pytest --collect-only`).

- [ ] **Step 6: Run full suite**

```bash
../../../.venv/Scripts/python.exe -m pytest -q
```

Expected: 256 passed (252 after Task G + 4 new in this task = 256).

- [ ] **Step 7: Commit**

```bash
git add src/ui/screens/settings.py tests/test_settings_screen.py
git commit -m "$(cat <<'EOF'
feat(settings): validate Lupa Absen Datang penalty as int in [0, 999]

Previously the _save handler wrote any string verbatim, including
'abc' or negative numbers — silent corruption of the setting until
the next read raised a ValueError deep in effective_attendance.

Now: parse → range check → warning dialog on bad input → leave the
DB value unchanged. Zero (no penalty) is explicitly allowed.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task I: Laporan Bulanan holiday row format

**Spec section:** §3.

**Files:**
- Modify: `src/core/report_generator.py` — add `HOLIDAY_FILL` constant; rewrite `_write_data_row` is_holiday branch.
- Modify: `tests/test_report_generator.py` — update `test_generate_monthly_report_holiday_row`.

- [ ] **Step 1: Update the existing holiday test to expect new format**

In `tests/test_report_generator.py`, replace the `test_generate_monthly_report_holiday_row` body (around line 208-245) — the change is to the docstring + the three cell-value assertions on lines 241-243, plus add fill assertion:

```python
def test_generate_monthly_report_holiday_row(tmp_path):
    """Holiday row (v15 format): E='Hari Libur', G+H blank, count columns blank,
    yellow HOLIDAY_FILL applied to all cells, no contribution to Total Personal."""
    from src.db.holidays import mark_holidays
    from src.core.report_generator import HOLIDAY_FILL
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(DDL)
    a = upsert_employee(conn, no_staff="1", nama="ANDI", dept="X")
    upsert_attendance(
        conn, employee_id=a, tanggal="2026-04-01", hari="Senin",
        tipe="Hari Kerja", jadwal="08.00 - 16.00", masuk="08:30",
        keluar="16:00", kerja_jam=7.5, lembur_jam=None,
        terlambat_menit=30, has_issue=0, imported_from="t.xls",
    )
    upsert_attendance(
        conn, employee_id=a, tanggal="2026-04-03", hari="Jumat",
        tipe="Hari Kerja", jadwal="08.00 - 16.00", masuk="09:00",
        keluar="16:00", kerja_jam=7.0, lembur_jam=None,
        terlambat_menit=60, has_issue=0, imported_from="t.xls",
    )
    mark_holidays(conn, ["2026-04-03"])
    out = tmp_path / "out.xlsx"
    generate_monthly_report(conn, year_month="2026-04", out_path=out)
    ws = load_workbook(out).active

    holiday_row = total_row = None
    for r in range(3, ws.max_row + 1):
        c = ws.cell(row=r, column=3).value
        if c is not None and str(c).startswith("2026-04-03"):
            holiday_row = r
        if ws.cell(row=r, column=1).value == "Total Personal:":
            total_row = r
    assert holiday_row is not None and total_row is not None
    assert ws.cell(row=holiday_row, column=5).value == "Hari Libur"   # E Tipe
    assert ws.cell(row=holiday_row, column=7).value in (None, "")      # G Masuk -> empty
    assert ws.cell(row=holiday_row, column=8).value in (None, "")      # H Keluar -> empty
    assert ws.cell(row=holiday_row, column=12).value in (None, "")     # L Terlambat
    assert ws.cell(row=total_row, column=12).value == 30              # only April 1
    # Fill check: holiday row cell A must carry HOLIDAY_FILL color
    assert ws.cell(row=holiday_row, column=1).fill.fgColor.rgb == HOLIDAY_FILL.fgColor.rgb
```

- [ ] **Step 2: Run test to verify it fails**

```bash
../../../.venv/Scripts/python.exe -m pytest tests/test_report_generator.py::test_generate_monthly_report_holiday_row -v
```

Expected: FAIL — first failed assertion is column E showing `"Hari Kerja"` instead of `"Hari Libur"`. Also `HOLIDAY_FILL` doesn't exist as an importable name.

- [ ] **Step 3: Add `HOLIDAY_FILL` constant**

In `src/core/report_generator.py`, find the existing `TOTAL_PERSONAL_FILL` line (around line 37) and add directly after it:

```python
TOTAL_PERSONAL_FILL = PatternFill(fill_type="solid", fgColor="FFC0C0C0")
HOLIDAY_FILL = PatternFill(fill_type="solid", fgColor="FFFFF2CC")  # light cream/calendar yellow
```

- [ ] **Step 4: Rewrite `_write_data_row` is_holiday branch**

In `src/core/report_generator.py`, replace the existing holiday block (around line 147-166):

```python
    if is_holiday:
        # Holiday row: marker "Libur" in column G only; Tipe shown as
        # "Hari Kerja" (matches the reference Laporan Bulanan April); all
        # count columns + Alasan Ijin left blank.
        values = [
            db_row["nama"],              # A Nama
            db_row.get("dept") or "",     # B Dept
            tanggal_val,                 # C Tanggal
            db_row.get("hari") or "",     # D Hari
            "Hari Kerja",                # E Tipe (override)
            db_row.get("jadwal") or "",   # F Jadwal
            "Libur",                     # G Masuk -> marker
            "",                          # H Keluar
            "", "", "", "", "", "", "", "",  # I-P counts blank
            "",                          # Q Alasan Ijin blank
        ]
        for col, val in enumerate(values, start=1):
            ws.cell(row=row_num, column=col, value=val)
        _apply_row_styles(ws, row_num, styles)
        return
```

With:

```python
    if is_holiday:
        # Holiday row (v15): Tipe='Hari Libur' in column E, Masuk/Keluar/count
        # columns all blank, and a light yellow fill overlay (HOLIDAY_FILL) so
        # holiday rows pop visually when scrolling the export.
        values = [
            db_row["nama"],              # A Nama
            db_row.get("dept") or "",     # B Dept
            tanggal_val,                 # C Tanggal
            db_row.get("hari") or "",     # D Hari
            "Hari Libur",                # E Tipe — was "Hari Kerja"
            db_row.get("jadwal") or "",   # F Jadwal
            "",                          # G Masuk — was "Libur" marker
            "",                          # H Keluar
            "", "", "", "", "", "", "", "",  # I-P counts blank
            "",                          # Q Alasan Ijin blank
        ]
        for col, val in enumerate(values, start=1):
            ws.cell(row=row_num, column=col, value=val)
        _apply_row_styles(ws, row_num, styles)
        # Overlay holiday fill on top of base styles. Mirrors the pattern used
        # for TOTAL_PERSONAL_FILL in _write_total_row. MergedCell guard prevents
        # accidental writes to merged regions.
        for col in range(1, 18):
            cell = ws.cell(row=row_num, column=col)
            if not isinstance(cell, MergedCell):
                cell.fill = HOLIDAY_FILL
        return
```

- [ ] **Step 5: Run test to verify it passes**

```bash
../../../.venv/Scripts/python.exe -m pytest tests/test_report_generator.py::test_generate_monthly_report_holiday_row -v
```

Expected: PASS.

- [ ] **Step 6: Run full suite**

```bash
../../../.venv/Scripts/python.exe -m pytest -q
```

Expected: 256 passed (no net new tests; existing test was updated in place).

- [ ] **Step 7: Commit**

```bash
git add src/core/report_generator.py tests/test_report_generator.py
git commit -m "$(cat <<'EOF'
feat(laporan-bulanan): holiday row uses Tipe='Hari Libur' + yellow fill

Replaces the old convention (Tipe='Hari Kerja' + 'Libur' marker in
Masuk column G) with the cleaner v15 format:
  - Tipe (column E) = 'Hari Libur' (matches DB attendance_records.tipe)
  - Masuk (G) and Keluar (H) blank
  - HOLIDAY_FILL (#FFF2CC light cream/yellow) overlay on all 17 cells

The fill makes holiday rows easy to spot while scrolling the export,
mirroring the existing TOTAL_PERSONAL_FILL pattern for total rows.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task J: Release sequence — bump version, build installer, rotate, smoke, push v15

**Spec section:** Cross-section concerns + CLAUDE.md framework.

**Hard requirement:** user must explicitly authorize the push (`git push origin v15`). Per `memory/workflow_rules.md` Rule 1: NO auto-push.

**Pre-flight:**
- All Tasks A-I committed.
- Full test suite green.
- Production `dist/HR-Absensi/HR-Absensi.exe` NOT running (PyInstaller can't overwrite a locked file).

- [ ] **Step 1: Run full test suite to confirm green**

```bash
../../../.venv/Scripts/python.exe -m pytest -q
```

Expected: 256 passed. If anything is red, stop and fix before proceeding.

- [ ] **Step 2: Bump APP_VERSION to 15.0.0**

In `src/config.py` line 5:

```python
APP_VERSION = "15.0.0"
```

(was `"14.0.0"`)

- [ ] **Step 3: Commit version bump**

```bash
git add src/config.py
git commit -m "$(cat <<'EOF'
chore: bump APP_VERSION to 15.0.0

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 4: Check production .exe is not running**

```bash
tasklist | grep -i HR-Absensi || echo "not running"
```

Expected output: `not running`. If you see `HR-Absensi.exe ...`, ask the user to close the app before proceeding (PyInstaller fails with `PermissionError` if the file is locked).

- [ ] **Step 5: Build installer**

```bash
../../../.venv/Scripts/python.exe -m tools.build_installer
```

Expected: PyInstaller runs (writes `dist/HR-Absensi/` inside the worktree), ISCC runs (writes `installer/Output/HR-Absensi-Setup-v15.0.0.exe`). Build duration: 60-180 seconds depending on machine.

If ISCC errors with `Unknown constant`, see the worktree's `installer/HR-Absensi.iss` line 10 — the AppId GUID must use double-brace escape `{{18FBCFB9-...}` (Inno preprocessor treats single brace as constant reference). This is already fixed in v14, just verify if compile fails.

- [ ] **Step 6: Verify installer artifact**

```bash
ls -la installer/Output/HR-Absensi-Setup-v15.0.0.exe
```

Expected: file exists, ~33 MB.

- [ ] **Step 7: Rotate production `dist/HR-Absensi/`**

Run these from the project root (NOT the worktree). The pattern is the 2-level rotation per `memory/workflow_rules.md` Rule 2:

```bash
# Move to project root for the rotation
cd "D:/Gawe/Project X/HR App"

# Drop oldest backup (level 2)
rm -f dist/HR-Absensi/HR-Absensi.exe.bak.old
rm -rf dist/HR-Absensi/_internal.bak.old

# Rotate level 1 → level 2
mv dist/HR-Absensi/HR-Absensi.exe.bak dist/HR-Absensi/HR-Absensi.exe.bak.old
mv dist/HR-Absensi/_internal.bak dist/HR-Absensi/_internal.bak.old

# Move current → level 1
mv dist/HR-Absensi/HR-Absensi.exe dist/HR-Absensi/HR-Absensi.exe.bak
mv dist/HR-Absensi/_internal dist/HR-Absensi/_internal.bak

# Copy new build from worktree into production
cp ".claude/worktrees/inspiring-dhawan-47161f/dist/HR-Absensi/HR-Absensi.exe" dist/HR-Absensi/HR-Absensi.exe
cp -r ".claude/worktrees/inspiring-dhawan-47161f/dist/HR-Absensi/_internal" dist/HR-Absensi/_internal

# Return to worktree for remaining steps
cd ".claude/worktrees/inspiring-dhawan-47161f"
```

- [ ] **Step 8: Verify rotation**

```bash
ls -la "D:/Gawe/Project X/HR App/dist/HR-Absensi/"
```

Expected: `HR-Absensi.exe`, `HR-Absensi.exe.bak`, `HR-Absensi.exe.bak.old` all present. Same for `_internal/`, `_internal.bak/`, `_internal.bak.old/`. The `data/` folder is untouched.

- [ ] **Step 9: Manual smoke test (pause for user)**

Print this message and wait for user confirmation before proceeding:

> **MANUAL SMOKE — please test now:**
> 1. Launch `D:\Gawe\Project X\HR App\dist\HR-Absensi\HR-Absensi.exe`.
> 2. App opens, Dashboard renders the current month without errors.
> 3. Open Resolve Massal: pick an employee, cycle each of the 10 reason categories (Tugas Belajar, Lupa Absen Datang, Lupa Absen Pulang, Cuti, Libur, NA, etc.) — confirm the "Resolve" button is visible for every selection without flipping.
> 4. Settings → "Penalti Lupa Absen Datang (menit)" — try entering `abc`, `-1`, `1000` — all should show a warning and not save. `0` and `15` should save.
> 5. Generate a Laporan Bulanan that includes a holiday date. Open the .xlsx — confirm column E = "Hari Libur", columns G + H are empty, and the row has a light yellow fill.
>
> **Confirm with 'ok' or describe what failed.**

- [ ] **Step 10: Update local `v15` branch and push (after user approval)**

```bash
# Create or fast-forward local v15 from current HEAD
git branch -f v15 HEAD

# Push v15 using Windows-native ssh.exe (Git Bash's ssh can't see Windows ssh-agent)
GIT_SSH_COMMAND="C:/Windows/System32/OpenSSH/ssh.exe" timeout 30 git push origin v15
```

Expected: push succeeds; remote `origin/v15` matches local HEAD.

If push fails with `Permission denied (publickey)`, the Windows ssh-agent service is the issue — see `memory/workflow_rules.md` Rule 1's SSH push workaround.

- [ ] **Step 11: Update `memory/version_state.md`**

Add a new row for v15 to the version table at `C:\Users\user\.claude\projects\D--Gawe-Project-X-HR-App\memory\version_state.md`. Use the existing v14 row as template:

- New commit SHA: result of `git rev-parse HEAD`
- Description: `Resolve Massal bug fix + Lupa Absen split (datang/pulang) + Hari Libur format in Laporan Bulanan`
- Add a "Done in v15" section listing the highlights from the spec.

- [ ] **Step 12: Commit memory update if any version_state.md changes were made**

Note: `memory/` lives under `C:\Users\user\.claude\projects\...` (user-level memory), NOT under the project worktree. It's not tracked in this repo, so no commit is needed. Just save the file edit.

- [ ] **Step 13: Final summary to user**

Report:
- v15 milestone is live at origin/v15.
- Installer: `installer/Output/HR-Absensi-Setup-v15.0.0.exe`.
- Production .exe rotated.
- Test baseline: 256 passing.
- Memory updated.

---

## Self-Review

### Spec coverage check

| Spec section | Plan task(s) | Status |
|---|---|---|
| §1 Resolve Massal bug fix | Task A | ✓ |
| §2 REASON_CATEGORIES + REASON_LABELS update | Tasks B, G | ✓ |
| §2 effective_attendance update | Tasks C, G | ✓ |
| §2 Dashboard tidak_hadir exclusion | Task E | ✓ |
| §2 Settings label change | Settings file already has "Penalti Lupa Absen Datang (menit):" — verified during exploration, no change needed. |
| §2 Settings input validation | Task H | ✓ |
| §2 Schema migration | Task D | ✓ |
| §3 Laporan Bulanan holiday format | Task I | ✓ |
| §3 HOLIDAY_FILL = light yellow #FFF2CC | Task I | ✓ |
| Cross-section: release sequence | Task J | ✓ |

### Placeholder scan

Scanned all 10 tasks — no "TBD", "implement later", or naked "appropriate error handling". Every code step contains the full code; every assertion is concrete.

### Type / name consistency

- `self._btn_row` introduced in Task A; not referenced again in later tasks (correct — bug fix is self-contained).
- `lupa_absen_datang` / `lupa_absen_pulang` strings appear consistently across Tasks B, C, D, E, F, G, H.
- `HOLIDAY_FILL` constant created in Task I Step 3, imported in test Step 1 — order swapped: the import in the test fails until Step 3 lands. **Fix:** Step 1 writes the failing test, Step 2 runs it and EXPECTS the failure (which now includes the ImportError). The plan already structures this correctly — both will fail at Step 2.
- Test counts: 241 → 242 (A) → 242 (B; renamed test) → 246 (C; +4) → 250 (D; +4) → 252 (E; +2) → 252 (F; updates, no net) → 252 (G; net 0 — `test_all_categories_present` updated in place, `test_render_without_detail` updated in place) → 256 (H; +4) → 256 (I; updates, no net). Final: **256 passing**. The header's target of ~247 was conservative; revise the header — done.

Wait — header says ~247 but the actual computation lands at 256. Let me re-tally:

- Task A: +1 test (`test_batch_resolve_dialog_btn_row_attr_exposed`)
- Task B: 0 net (renamed existing test)
- Task C: +4 tests
- Task D: +4 tests
- Task E: +2 tests
- Task F: 0 net (fixture updates)
- Task G: 0 net (renamed/updated existing tests)
- Task H: +4 tests
- Task I: 0 net (updated existing test in place)

Sum: 241 + 1 + 4 + 4 + 2 + 4 = **256**

**Fix the header.** The target is 256, not ~247.

### Self-review revision

Updating the header.

---

**Final test target: 256 passing on v15.** (Header section "Test baseline" updated.)
