# v17 Design — "Severe Lateness" Menu

**Date:** 2026-06-09
**Status:** Approved (hardened after adversarial codebase review — see §15)
**Milestone:** v17.0.0
**Forks from:** `origin/v16` (= `origin/latest`, `cfeb789`)

## 1. Summary

Add a new sidebar menu **Severe Lateness** that surfaces work days where the
employee **clocked in AND out**, but was **late by ≥ a configurable threshold**
(default **60 minutes**). HR attaches a reason to each row exactly like the
Issues menu; that reason flows into the DB, the Coaching tally, and the exported
monthly report.

The feature is a structural **clone of the Issues menu** with a different
detector query. It introduces **no DB schema change** and reuses the existing
`reason_category` / `reason_detail` / `resolved_at` resolution columns.

## 2. Detection

A row qualifies as "severe lateness" when **all** of:

```
tipe            = 'Hari Kerja'
masuk           IS NOT NULL          -- clocked in
keluar          IS NOT NULL          -- clocked out
terlambat_menit >= <threshold>       -- default 60
```

- `terlambat_menit` is taken straight from the fingerprint import (the same
  source Coaching / Insights already trust). It is **not** recomputed.
- A NULL `terlambat_menit` is treated as `0` → never severe.
- **Disjoint from Issues by construction:** Issues requires a *NULL* punch
  (`is_issue()` in `src/core/issue_detector.py`); this requires *both* punches
  present. A row can never appear in both lists → no double-counting.

### Detector module

Create **`src/core/severe_lateness_detector.py`** with a pure predicate:

```python
def is_severe_lateness(row, threshold_min: int) -> bool:
    """row supports row["tipe"], row["masuk"], row["keluar"],
    row["terlambat_menit"] (dict or sqlite3.Row). Returns True iff
    tipe == 'Hari Kerja' and masuk and keluar are both set and
    (terlambat_menit or 0) >= threshold_min."""
```

The DB query (§5) encodes the same predicate in SQL; this helper exists for unit
testing the boundary logic in isolation.

## 3. Data model — no schema change

Reuses the existing `attendance_records` columns:

| Column | Meaning here |
|--------|--------------|
| `reason_category` | NULL = open; non-NULL = resolved |
| `reason_detail` | optional free-text detail |
| `resolved_at` | ISO timestamp set when resolved |

- **Open** = `reason_category IS NULL` · **Resolved** = `reason_category IS NOT NULL`
- These columns already drive Coaching exclusion (`COACHING_EXCLUDED`) and
  `effective_attendance()`. Marking a late day as **Tugas Lapangan / Tugas
  Paparan / Terlambat Kerja** automatically (a) removes it from the Coaching
  tally and (b) zeroes the lateness in the generated export — the **approved,
  intended** behavior.

### Coaching lifecycle (verified)

`src/db/coaching.py` counts all rows where `masuk IS NOT NULL` and
`terlambat_menit > 0`, **excluding** `COACHING_EXCLUDED` categories — it does
**not** filter on `has_issue`. Therefore:

- A newly-opened severe-lateness row (`has_issue=0`, both punches, high
  lateness) is **already counted** in the Coaching screen at its next reload —
  even before this feature existed.
- Resolving it with a `COACHING_EXCLUDED` category **removes** it from the
  Coaching tally, exactly mirroring the Issues workflow. Resolving it with a
  non-excluded category (e.g. `terlambat_lain`, `izin_sakit`) **keeps** it
  counted but annotates it. This two-phase lifecycle is intended and must be
  covered by tests.

### Migration safety (verified)

`set_reason()` is the **only** writer of `reason_category`, and it has only ever
been reachable from the Issues menu, which operates on `has_issue=1` rows.
`upsert_attendance()` explicitly preserves `reason_category` on conflict (never
sets it). Therefore **every `has_issue=0` row currently has
`reason_category = NULL`** — this new menu is the first to set it on such rows,
so existing reports are unchanged until a user explicitly resolves a row.
**Pre-deploy sanity check** (add to release smoke): confirm the production DB has
zero `has_issue=0` rows with `reason_category IS NOT NULL`.

## 4. Settings

Mirrors the existing `coaching_threshold_per_day` / `lupa_absen_datang_penalty_min`
wiring.

- **`src/config.py`**: add `DEFAULT_SEVERE_LATENESS_THRESHOLD_MIN = 60`
  (alongside `DEFAULT_LUPA_PENALTY_MIN`).
- **`src/db/schema.py`** `DEFAULT_SETTINGS` dict: add
  `"severe_lateness_threshold_min": "60"`. The `init_db` loop already inserts
  every `DEFAULT_SETTINGS` key with `INSERT ... ON CONFLICT(key) DO NOTHING`, so
  **existing DBs receive the default on the next app startup**. No `_migrate()`
  entry is needed — this is a brand-new key (unlike the v15
  `coaching_threshold_min → per_day` rename, which needed a migration).
- **`src/db/settings.py`**: add `read_severe_lateness_threshold(conn) -> int`,
  mirroring `read_lupa_penalty_min`. Add
  `from src.config import DEFAULT_SEVERE_LATENESS_THRESHOLD_MIN` and use it as the
  fallback when the value is missing or non-integer.
- **`src/ui/screens/settings.py`** General tab: new row after *Penalti Lupa Absen
  Datang*:
  - Label: **`Severe Lateness Threshold (menit):`** (use "menit", matching the
    adjacent Penalti label, not "mnt").
  - Entry width 80, value from
    `get_setting(conn, "severe_lateness_threshold_min", "60")`.

### `_save()` control flow (corrected)

The real `_save()` validates a field and, on failure, calls
`messagebox.showwarning(...)` **then `return`s immediately without saving
anything** (it does *not* warn-then-save). All `set_setting` calls happen
together inside one `with get_connection(...)` block *after* validation passes.
The new field must follow the same shape:

1. Validate `lupa_penalty` (existing, `[0, 999]`).
2. Validate `severe_lateness_threshold` as an integer in **`[1, 999]`**; on
   failure → `showwarning` + `return` (no save).
3. Only if **both** pass: open the connection and `set_setting` all values
   (`current_month`, `coaching_threshold_per_day`, `lupa_absen_datang_penalty_min`,
   `severe_lateness_threshold_min`).

`coaching_threshold_per_day` is saved as-is **without** range validation —
existing behavior, preserved unchanged (not in scope to add validation here).

**Why `[1, 999]` not `[0, 999]`:** unlike Lupa Penalty (where `0` legitimately
disables the penalty), a threshold of `0` would flag every minute of lateness and
flood the table with the entire roster. `1` is the meaningful floor. (Documented
deviation from the Lupa precedent.)

### Threshold-change behavior

- **Lower** the threshold → more days qualify on next screen reload.
- **Raise** the threshold → lower-minute rows disappear from the view but are
  **not** auto-unresolved; any already-set `reason_category` persists in the DB
  and continues to affect Coaching + export. The threshold only changes **what is
  displayed**, never the stored resolution.
- Change takes effect on **open/reload** of the screen (no app restart).

## 5. DB query layer (`src/db/attendance.py`)

Add, mirroring `list_issues_for_period` / `count_issues_for_period`:

```python
def list_severe_lateness_for_period(conn, start, end, threshold_min, resolved=None):
    """Rows with tipe='Hari Kerja', masuk IS NOT NULL, keluar IS NOT NULL,
    terlambat_menit >= threshold_min, in [start, end]. resolved=False →
    reason_category IS NULL; resolved=True → IS NOT NULL; None → both.
    Joins employees for nama/dept/no_staff. Sort: e.nama ASC, ar.tanggal ASC."""

def count_severe_lateness_for_period(conn, start, end, threshold_min):
    """Returns {open, resolved, na, total} with the SAME semantics as
    count_issues_for_period: resolved = reason_category IS NOT NULL AND != 'na';
    na = reason_category == 'na'; open = reason_category IS NULL;
    total = open + resolved + na — but scoped to the threshold query above."""
```

- **Reuse as-is** (both are fully generic, operate on an `attendance_id`):
  - `set_reason(conn, *, attendance_id, category, detail)` — note the `*`:
    `attendance_id`, `category`, `detail` are **keyword-only**.
  - `unresolve_issue(conn, attendance_id)`.

## 6. UI screen (`src/ui/screens/severe_lateness.py`)

`SevereLatenessScreen(ctk.CTkFrame)` — a structural clone of `IssuesScreen`.
Replicate these patterns from `src/ui/screens/issues.py` (do not re-invent):

### Layout
- **Header**: title "Severe Lateness" + `WeekNavBar` (sticky via `period_state`)
  + `+ Resolve Massal` button packed `side="right"` **before** the SearchBar
  claims its slot (the v16.0.1 fix). SearchBar lives near the table, **not** in
  the header (the v16.0.2 relocation).
- **KPI cards** (5): Open / Resolved / NA / Total / Resolution rate.
- **Two treeviews** (open + resolved) via the cloned `_make_tree` helper.
- **Right panel**: employee info + reason combobox (the §8 subset) + conditional
  detail entry + Save + Unresolve.

### `_make_tree` helper (cloned, with one column change)
`IssuesScreen._make_tree(parent, *, style_name, show_reason)` hardcodes
`cols = ["nama","dept","tanggal","hari","masuk","keluar"]` (+ `"alasan"` when
`show_reason=True`). The clone changes the column list to insert `terlambat`
**after `keluar`, before the optional `alasan`**:

- open table: `["nama","dept","tanggal","hari","masuk","keluar","terlambat"]`
- resolved table: `[... ,"terlambat","alasan"]`
- add to the widths/labels dicts: `terlambat` → width ~80, label **`Telat (mnt)`**.

This is the **sole deviation** from Issues table parity. It is required — the
lateness magnitude is the trigger value, and Masuk/Keluar are always populated
here (so a `—` is never the signal as it is in Issues).

### Styles (reuse, no new registration)
Reuse the existing ttk styles `"Open.Treeview"` / `"Open.Treeview.Heading"` /
`"Resolved.Treeview"` / `"Resolved.Treeview.Heading"` already registered by
Issues (rose open rows via `COLOR_ROW_TINT_OPEN`, green resolved via
`COLOR_ROW_TINT_RESOLVED`). No new style names.

### Resolve panel (`_lay_out_form` / `_on_cat_change`)
Clone the conditional-detail logic: when the selected category is in
`REASON_NEEDS_DETAIL = {tugas_lapangan, tugas_paparan, terlambat_kerja,
terlambat_lain}`, show the detail label+entry; otherwise hide them. `_on_cat_change`
re-runs `_lay_out_form(cat)`. Of the §8 subset, those four need detail;
`izin_sakit`, `cuti`, `na` do not. Save calls
`set_reason(conn, attendance_id=..., category=..., detail=...)`; Unresolve calls
`unresolve_issue`.

### Search + shortcuts + lifecycle (clone verbatim)
- `SearchBar` near the table; `_row_cache` dict + `_search_query` string;
  `_reload()` populates `_row_cache` from `list_severe_lateness_for_period`
  (open + resolved); `_apply_filter(query)` filters by employee name and
  re-renders.
- **Ctrl+F**: bind in `__init__` via `self.bind("<Control-f>")` **and**
  `self.winfo_toplevel().bind_all("<Control-f>", ...)`; **unbind** in
  `_on_destroy_cleanup` to prevent keybinding leaks across navigation.
- **Click-outside-blur**: bind `<Button-1>` on the toplevel (`add="+"`, store the
  bind id), walk `event.widget`'s parent chain; if the click isn't inside the
  SearchBar, `focus_set()` the screen. Unbind in `_on_destroy_cleanup`.
- **Enter-submit** on the resolve panel (bind `<Return>` on the category combobox,
  its inner `_entry`, and the detail entry → `_on_save`).

### Cross-screen week + KPIs
- In `__init__`, read & cache `self._current_month` from
  `get_setting(conn, "current_month")`; pass it to `WeekNavBar(initial=period_state.get())`.
- `_on_period_change(key)` → `period_state.set(key)` then `self._reload()`.
- **KPI counts come from `count_severe_lateness_for_period`** (threshold-filtered).
  The **resolution-rate KPI is derived from those counts**
  (`round(resolved / total * 100)` when `total`), **NOT** from
  `insights.resolution_rate` — that function is hardcoded to `has_issue = 1` and
  would report the *Issues* rate, not the severe-lateness rate.

## 7. Sidebar + router (`src/ui/app.py`)

Insert in the **WORKFLOW** group, **between Issues and WhatsApp Assistant**:

```python
("WORKFLOW", [
    ("🚩", "Issues", "Issues"),
    ("◷", "Severe Lateness", "SevereLateness"),   # new
    ("💬", "WhatsApp Assistant", "WhatsAppAssistant"),
    ("🎯", "Coaching", "Coaching"),
]),
```

- Icon **◷** (U+25F7) is a text-default glyph → renders **monochrome** in the
  theme text color, like the existing `⚙` and `ℹ` (not a color emoji).
- In `_show()`, add a branch mirroring the Issues handler: lazy-import
  `from src.ui.screens.severe_lateness import SevereLatenessScreen`, instantiate
  under the `"SevereLateness"` key, and `grid(row=0, column=0, sticky="nsew")`.

## 8. Reason categories (subset)

Add to `src/config.py`:

```python
SEVERE_LATENESS_CATEGORIES = (
    "tugas_lapangan", "tugas_paparan", "terlambat_kerja",
    "terlambat_lain", "izin_sakit", "cuti", "na",
)
```

(Subset of `REASON_CATEGORIES`; excludes `lupa_absen_datang`, `lupa_absen_pulang`,
`libur` — meaningless when both punches exist.) The screen builds its combobox by
mapping these through `REASON_LABELS`. Note `terlambat_kerja` ∈ `COACHING_EXCLUDED`
(justified → drops from coaching) while `terlambat_lain` is not (stays counted).

## 9. Export plumbing — only the *fill* path changes

There are **two** export paths (both in `src/ui/screens/export.py`):

### Generate mode → `report_generator.generate_monthly_report` — **no change**
Builds a fresh report from the DB. `_write_data_row` (report_generator.py:176-183)
already writes the Alasan Ijin column for **any** row whose `reason_category` is
set, regardless of `has_issue` (`if reason → render; elif has_issue → "NA / Belum
ada kabar"; else → blank`), and it already calls `effective_attendance()`
(line 324) to zero lateness for `COACHING_EXCLUDED` rows. **Resolved
severe-lateness rows already flow through this path correctly** — no edit needed.

### Export/fill mode → `report_filler.fill_monthly_report` — **one change**
Fills only **column Q (Alasan Ijin)** into the user's *existing* uploaded report;
it does **not** write time columns, so `effective_attendance` is irrelevant here.
Today it gates on `has_issue` (report_filler.py:81): `if row["has_issue"] != 1:
continue` → severe-lateness rows (`has_issue=0`) are skipped.

**Change:** replace that gate with the same ladder `report_generator` uses, so the
two paths agree:

```python
if row["tipe"] == "Hari Libur":
    continue
if row["reason_category"]:
    text = render_alasan_ijin(row["reason_category"], row["reason_detail"])
    summary.filled_count += 1
elif row["has_issue"] == 1:
    text = "NA / Belum ada kabar"      # preserve existing unresolved-issue behavior
    summary.na_count += 1
else:
    continue                            # non-issue, unresolved → no Alasan
```

> **Do NOT** use `if row["reason_category"] is None: continue` (the naive fix) — it
> would drop the "NA / Belum ada kabar" text that unresolved Issues currently get,
> a regression. The ladder above adds severe-lateness rows **and** preserves the
> NA behavior.

**Regression guarantee:** unresolved non-issue rows (`reason_category` NULL,
`has_issue=0`) still hit `continue`, so existing filled reports are byte-identical
until a user resolves a severe-lateness row.

## 10. Batch resolve (`src/ui/components/batch_resolve_dialog.py`)

The dialog currently hardcodes `list_issues_for_period(conn, start, end,
resolved=False)` (line ~117). Generalize via an injected lister:

- Add to `__init__`: `lister_fn: Callable[[Connection, str, str], list] | None = None`.
  When `None`, default to
  `lambda c, s, e: list_issues_for_period(c, s, e, resolved=False)` (backward
  compatible). Use `lister_fn` at the call site instead of the hardcoded import.
- Issues passes the default (or the explicit Issues lambda).
- Severe Lateness passes
  `lambda c, s, e: list_severe_lateness_for_period(c, s, e, threshold, resolved=False)`.
- `apply_batch_resolve` (loops `set_reason`) is reused **unchanged**.
- *Minor (optional):* the dialog's button text is hardcoded "Resolve {n} Issue".
  Leave as-is for scope, or parametrize the noun via an optional `item_label`
  arg. Not required for v17.

## 11. Changelog & release (framework rules)

- **Rule #4:** prepend an `APP_CHANGELOG` v17.0.0 entry in `src/config.py`
  (Indonesian, user-facing):
  - `("feat", "Menu baru 'Severe Lateness': deteksi keterlambatan harian ≥ ambang (default 60 mnt) walau jam masuk & keluar lengkap; resolusi alasan seperti Issues.")`
  - `("feat", "Pengaturan baru 'Severe Lateness Threshold (menit)' di Settings → Umum (default 60, rentang 1–999).")`
- Bump `APP_VERSION = "17.0.0"`, `APP_BUILD_DATE`.
- Full release sequence (CLAUDE.md rules 1–2): build installer → rotate prod
  `.exe` (2-level) → copy to `Installers/HR-Absensi-Setup-v17.0.0.exe` → smoke →
  push `v17` + advance `latest` (with explicit user authorization).
- **Smoke additions:** (a) verify the **◷** sidebar icon renders as a monochrome
  glyph (not a tofu box / color emoji) in the bundled font — if not, swap to a
  fallback glyph (e.g. U+29D7) and update `app.py`; (b) run the §3 pre-deploy DB
  sanity check.

## 12. Testing (TDD)

Concrete files & cases:

- **`tests/test_severe_lateness_detector.py`**
  - `test_is_severe_at_boundary` — 60 with threshold 60 → True; 59 → False.
  - `test_is_severe_requires_both_punches` — masuk or keluar None → False.
  - `test_is_severe_hari_kerja_only` — tipe != 'Hari Kerja' → False.
  - `test_is_severe_null_terlambat_not_severe` — terlambat None → False.
- **`tests/test_attendance_severe_lateness.py`** (mirror `test_attendance*`)
  - `test_list_filters_by_threshold` — only rows ≥ threshold, both punches.
  - `test_list_excludes_missing_punch_rows` — has_issue rows never appear.
  - `test_list_open_vs_resolved_split` — `resolved=` filter.
  - `test_count_open_resolved_na_total`.
- **`tests/test_settings_severe_lateness.py`**
  - `test_default_present_in_default_settings`.
  - `test_read_helper_fallback_on_missing_and_invalid`.
  - `test_settings_save_validates_range` (1–999) + round-trip.
- **`tests/test_severe_lateness_screen.py`** (mirror `test_issues_screen.py`)
  - constructs; `_reads_period_state_on_mount`; `_writes_period_state_on_change`;
    `_binds_ctrl_f`; `_apply_filter_reduces_visible_rows`;
    `_header_has_resolve_massal_no_searchbar`; `_resolve_panel_binds_return`;
    `_has_batch_resolve` (`_on_batch_resolve` attr).
- **`tests/test_report_filler_severe_lateness.py`**
  - `test_resolved_severe_lateness_row_writes_alasan` (has_issue=0 + reason → Q).
  - `test_unresolved_issue_still_writes_na` (regression: has_issue=1, no reason).
  - `test_unresolved_non_issue_row_skipped` (has_issue=0, no reason → no Q).

## 13. Approaches considered

- **A (chosen)** — shared reason columns + screen clone. Minimal: no schema
  change, automatic Coaching/export integration.
- **B (rejected)** — separate `lateness_reason_*` columns. Full isolation but
  needs a migration + duplicate export/coaching plumbing, and contradicts the
  approved "justified lateness reduces coaching" decision.
- **C (rejected)** — fold into the Issues screen as a tab/filter. The user wants
  a distinct sidebar menu, and the disjoint detection sets make a separate screen
  cleaner.

## 14. Files touched (summary)

| File | Change |
|------|--------|
| `src/config.py` | `DEFAULT_SEVERE_LATENESS_THRESHOLD_MIN`, `SEVERE_LATENESS_CATEGORIES`, `APP_VERSION`, `APP_BUILD_DATE`, `APP_CHANGELOG` |
| `src/db/schema.py` | `DEFAULT_SETTINGS` entry (new key; init_db loop handles existing DBs) |
| `src/db/settings.py` | `read_severe_lateness_threshold` + import of the default |
| `src/db/attendance.py` | `list_/count_severe_lateness_for_period` |
| `src/core/severe_lateness_detector.py` | **new** — `is_severe_lateness(row, threshold_min)` |
| `src/ui/screens/severe_lateness.py` | **new** screen (clone of Issues + Telat column) |
| `src/ui/screens/settings.py` | new threshold row + `_save` validation (validate-then-return) |
| `src/ui/app.py` | sidebar entry (between Issues & WhatsApp) + `_show` router branch |
| `src/ui/components/batch_resolve_dialog.py` | `lister_fn` injection (default = Issues) |
| `src/core/report_filler.py` | replace `has_issue` gate with reason→elif-has_issue→else ladder |
| `src/core/report_generator.py` | **no change** (already correct) |
| `tests/...` | detector, DB, settings, screen smoke, report_filler |

## 15. Verification notes (post-review)

Hardened against a 5-lens adversarial review of the spec vs. the real codebase
(blocker/major findings resolved). Non-obvious facts that drove corrections:

1. `insights.resolution_rate(conn, start, end)` is **`has_issue=1`-scoped**
   (insights.py:238) → SevereLateness must compute its rate from
   `count_severe_lateness_for_period`, not reuse it.
2. `report_generator._write_data_row` **already** writes Alasan for any
   `reason_category` and already applies `effective_attendance` → Generate mode
   needs no change; only `report_filler` does.
3. The correct `report_filler` fix is the reason→elif-`has_issue`→else ladder
   (§9), **not** `if reason_category is None: continue` (which regresses the NA
   text for unresolved Issues).
4. `set_reason` is keyword-only after `conn`; `_save()` validates-then-returns
   (never warn-then-save); `REASON_NEEDS_DETAIL = {tugas_lapangan, tugas_paparan,
   terlambat_kerja, terlambat_lain}`.
