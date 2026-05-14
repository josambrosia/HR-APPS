# Session Handoff — 2026-05-15

**Read this first.** Two things are in flight; this doc lets a fresh session pick up both.

---

## TL;DR

1. **Hari Libur + Export Mingguan (v12 feature)** — fully implemented, tested, reviewed, and the `.exe` is deployed. NOT yet wrapped as a `v12` snapshot branch / not pushed. Awaiting user authorization + a manual GUI smoke test.
2. **Issue Resolution feature** — a NEW `superpowers:brainstorming` session was JUST STARTED (3 changes: new reason category, Batch Resolve, lateness logic change). It paused right after the user accepted the Visual Companion. Resume the brainstorm from there.

**Worktree state:** branch `claude/trusting-lederberg-6e61bb`, HEAD `0e626a8`, **29 commits ahead of `origin/v11` (`e383c35`)**, **194 tests passing** (`../../../.venv/Scripts/python.exe -m pytest -q` from the worktree root), working tree clean.

---

## PART A — Hari Libur + Export Mingguan (DONE, not wrapped)

A full brainstorm → spec → plan → 17-task subagent-driven implementation cycle completed this session. Every task was spec-reviewed + code-quality-reviewed; a final whole-branch review passed ("ready to wrap as v12", all 6 spec assumptions honored, no Critical/Important issues).

**What was built:**
- **Menu Hari Libur** — new `🌴 Hari Libur` sidebar screen (`src/ui/screens/holiday.py`, EXCEPTIONAL CASE group). Multi-select work-day checkboxes + impact preview + "Terapkan" button. Hybrid data model: new `holidays` table (source of truth) + `attendance_records.tipe` stamped `'Hari Libur'`; `src/db/holidays.py` has `mark_holidays`/`unmark_holidays`/`restamp_holidays` + read queries. Marking a date auto-resolves open issues on it (`reason_category='libur'`). `restamp_holidays` is wired into the import flow (re-stamps after `upsert_attendance` overwrites `tipe`). Holiday rows excluded from Dashboard/coaching/print recap (via `tipe='Hari Kerja'` filters). Monthly report shows "Libur" in column G; `report_filler` skips holiday rows.
- **Export Mingguan** — `src/ui/screens/export.py` restructured into a `📤 Export` / `⚙ Generate` mode toggle; Generate has `Bulanan` + `Mingguan` sub-modes. New `src/core/weekly_export.py` produces a normalised 12-column weekly `.xlsx`. New `export_history.kind` column. Generate button removed from Active Month (consolidated into Export). Sidebar tightened ("opsi A").
- New `"libur"` reason category; `holidays` table + `export_history.kind` schema + `_migrate()` for existing DBs; session-scoped `tk_root` test fixture in `conftest.py`.

**Docs:** spec `docs/superpowers/specs/2026-05-14-hari-libur-and-weekly-export-design.md`, plan `docs/superpowers/plans/2026-05-14-hari-libur-and-weekly-export.md`.

**Deployed:** rebuilt `.exe` from HEAD `0e626a8` and rotated into `dist/HR-Absensi/` with the standard 2-level backup rotation (`.bak` / `.bak.old`); `data/hr.db` untouched.

**What's NOT done (needs user authorization — workflow rule: no auto-push, user authorizes vN snapshots):**
- Wrap branch as a local `v12` + push to `origin/v12`.
- **Manual GUI smoke test** — was NOT done (the implementing agent is headless and cannot click a desktop window). The 194 tests include screen-construction smoke tests, but the actual UX needs human eyes: Hari Libur multi-select flow, Export/Generate toggles, sidebar fit at maximized size, mark-a-holiday → Dashboard/Coaching numbers drop, re-import a week → holiday status survives.

**Known minor follow-ups (from the final review, non-blocking):**
- Weekly-export default filename uses ISO dates (`Laporan Mingguan 2026-04-06 sd 2026-04-12.xlsx`) instead of the prettier Indonesian range the spec §8 described. (Note: the existing `_format_short_range` helper in `import_screen.py` outputs `->` which is filename-invalid on Windows — a filename-safe variant is needed if this is fixed.)
- Issues-screen "Batalkan Resolve" on a holiday-resolved issue clears `reason_category` but leaves `tipe='Hari Libur'` + the `holidays` row — a transient desync that self-heals on the next import.
- `workday_roster` issue-count preview is slightly off only if a user *manually* picks the "Libur" reason on a non-holiday date.

---

## PART B — Issue Resolution feature (brainstorm IN PROGRESS — resume here)

User invoked `superpowers:brainstorming` for a new feature set. The brainstorm paused right after step 2 (offer Visual Companion) — **the user accepted it ("Mau")**. Resume: start the Visual Companion server, then begin clarifying questions (step 3).

### The user's request (3 changes — verbatim intent)

**1. MENU ISSUE — new resolve category:** Add `"Tugas Belajar/Kuliah"` as a new option in the resolve-Issue category list.

**2. Batch Resolve:** Add a button that opens a popup to resolve multiple issues at once — e.g. an employee on a 5-day out-of-town field assignment, instead of filling each day one-by-one. The popup: pick the employee, pick which dates, and a resolve-input section identical to the existing right-side resolve panel.

**3. LOGIC CHANGE — resolve categories should mutate the attendance data:**
- When an issue is resolved as a **work-justified-late** category (`Tugas Lapangan`, `Tugas Paparan`, `Masuk Terlambat dengan Alasan Pekerjaan`) → counted as **not late**, and set the **Masuk column to `08.00`**.
- When resolved as **"Lupa Absen Datang"** (forgot to clock IN) → counted as **15 minutes late**.

### Where the brainstorm is

Context fully explored (see codebase facts below). Visual Companion offered + accepted. **Next steps:** start `scripts/start-server.sh --project-dir <worktree>` (Windows: `run_in_background: true`, then read `$STATE_DIR/server-info`), push a mock when a question is visual, then work through clarifying questions one at a time.

### Clarifying questions already identified (so they don't need re-deriving)

**New category "Tugas Belajar/Kuliah":**
- Does it need a detail field (like `tugas_lapangan` → "Tugas Lapangan di {detail}")?
- Is it work-justified-late (added to `COACHING_EXCLUDED` + the §3 logic bucket)? Or a full-day absence like `izin_sakit`/`cuti`? Or its own thing?

**Batch Resolve:**
- Which dates are selectable in the popup — only dates where the chosen employee has OPEN issues in the active period, or any date?
- Button placement (Issues screen header? above the OPEN table?).
- One category+detail applied to all selected dates? (Assume yes.)
- The popup's resolve fields mirror `IssuesScreen._build_panel_for` (category combo + optional detail entry).

**LOGIC CHANGE (the meaty part — same architectural tension as Hari Libur's mutate-vs-derive):**
- **Mutate vs derive:** mutate `masuk`/`terlambat_menit` in the DB on resolve, or compute an "effective" value at render time? If mutate, re-import overwrites `masuk`/`terlambat_menit` (upsert preserves `reason_category` only) — so it needs a `restamp`-style re-apply on import, exactly like `restamp_holidays`.
- **Work-justified-late:** set `masuk='08.00'` — also set `terlambat_menit=0`? Touch `kerja_jam` (work hours change if masuk moves 09.40→08.00)? (User only mentioned Masuk.)
- **"Lupa Absen Datang":** the current `lupa_absen` category is generic (covers forgot-IN and forgot-OUT). Split into `lupa_absen_datang` + `lupa_absen_pulang`, OR keep `lupa_absen` and apply the 15-min rule only when `masuk IS NULL`? Set `masuk='08.15'` and/or `terlambat_menit=15`?
- Schedule start: always `08.00`, or use the `schedule_start` setting (`DEFAULT_SCHEDULE_START="08.00"`)?
- Retroactive (migrate already-resolved issues) or going-forward-only?
- Note the overlap: `terlambat_ranking` ALREADY zeroes `COACHING_EXCLUDED` categories and `masuk IS NULL` rows in its `total_terlambat` sum — so the *insight* is already partly correct. The logic change is really about making the raw `masuk`/`terlambat_menit` columns coherent so the monthly/weekly Excel reports show the right thing.

### Codebase facts the new session needs

- **Reason categories:** `src/config.py` `REASON_CATEGORIES` (9 entries: tugas_lapangan, tugas_paparan, izin_sakit, cuti, terlambat_kerja, terlambat_lain, lupa_absen, libur, na). `COACHING_EXCLUDED = ("tugas_lapangan", "tugas_paparan", "terlambat_kerja")`.
- **`src/core/reason_mapper.py`:** `REASON_LABELS` dict, `REASON_NEEDS_DETAIL` set, `render_alasan_ijin()`. Adding a category requires updating BOTH constants + the `test_all_9_categories_present` snapshot test in `tests/test_reason_mapper.py` (rename to `_10_`) — there is also a `test_reason_categories_and_labels_in_sync` guard test.
- **`src/ui/screens/issues.py`:** `IssuesScreen` — OPEN + RESOLVED `ttk.Treeview`s on the left, a right-side resolve panel built by `_build_panel_for(row_data)` (category `CTkComboBox` + optional `detail_entry` + Save button + "Batalkan Resolve" button). `_on_save` calls `set_reason(conn, attendance_id=, category=, detail=)`. The Batch Resolve popup should reuse this panel's field structure.
- **`src/db/attendance.py` `set_reason()`:** currently only updates `reason_category`, `reason_detail`, `resolved_at`. The logic change extends this (or wraps it) to also touch `masuk`/`terlambat_menit`.
- **`src/core/insights.py` `terlambat_ranking`:** `total_terlambat = SUM(CASE WHEN reason_category IN (COACHING_EXCLUDED) THEN 0 WHEN masuk IS NULL THEN 0 ELSE COALESCE(terlambat_menit,0) END)`. Also filters `tipe='Hari Kerja'`.
- **`src/core/report_generator.py`:** writes raw `masuk` → column G, raw `terlambat_menit` → column L of the monthly report. `compute_derived()` derives absen/lupa/kurang/etc. from masuk/keluar.
- **`src/core/weekly_export.py`:** also reads raw `masuk`/`terlambat_menit` (12-column weekly export).
- **Precedent pattern:** the Hari Libur feature's HYBRID model (separate table + column-stamp + `restamp` on import) is the established way this codebase handles "mutate a column on a user action + survive re-import". The logic change should likely follow the same pattern.

### Scope note

The 3 changes are cohesive (all "Issue resolution") — likely one spec, comparable in size to the Hari Libur + Export Mingguan spec. The logic change is the riskiest part (data mutation, re-import handling). Watch that the spec stays focused enough for a single plan.

---

## Workflow rules (reminder — also in memory)

- **NO auto-push.** User explicitly authorizes each push / vN snapshot ("bungkus versi ini" / "push to vN").
- **Deploy `.exe` with 2-level rotation** when user says "deploy" — `data/hr.db` never touched.
- **Test before commit** — current baseline 194.
- **Plan execution is subagent-driven** — skip the execution-options question, go straight to `superpowers:subagent-driven-development`.
- **Worktrees are harness-managed** — `finishing-a-development-branch` must NOT auto-clean this worktree (it lives under `.claude/worktrees/`).
- **Diagnosing silent `.exe` crashes:** Event Viewer + file logging — see memory `debugging_silent_crashes.md`.

*End of handoff.*
