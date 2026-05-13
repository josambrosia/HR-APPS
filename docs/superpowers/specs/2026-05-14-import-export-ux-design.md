# Import + Export UX Refresh — Design Spec

**Tanggal:** 2026-05-14
**Status:** Draft (awaiting user spec review)
**Author:** Brainstorming session
**Target screens:** `src/ui/screens/import_screen.py`, `src/ui/screens/export.py`
**Prior context:** [2026-05-13-ui-jts-theme-overhaul-design.md](./2026-05-13-ui-jts-theme-overhaul-design.md) — JTS theme already applied

---

## 1. Konteks & Problem

Post-JTS-overhaul (v5) smoke test pada Import + Export screens menemukan beberapa friction UX:

**Import:**
- Tombol Konfirmasi/Batal di pojok kanan bawah — terputus dari area focus (drop zone + preview cards di atas)
- Setelah pilih file, nama file tidak ditampilkan — user tidak tahu file apa yang sedang diproses
- Drop zone besar (200px) tetap dominan setelah file dipilih — wasted space
- Range tanggal ditampilkan ISO raw ("2026-04-01 → 2026-04-30") — tidak optimal di KPI value font (overflow)
- Tidak ada history — user lupa file mana yang sudah pernah diimpor
- Tidak ada konteks "bulan aktif sekarang apa, apa yang akan berubah setelah impor"

**Export:**
- Tidak ada konteks "akan mengisi laporan untuk bulan apa" — user pilih template tanpa visibility ke data target
- Preview match (filled/NA/not-found) hanya muncul SETELAH klik Export — user tidak bisa verify dulu
- Tombol Browse di kanan dalam card sendiri, tombol Export di bawah — alur scattered
- Result via `messagebox.showinfo` — interrupt workflow, harus dismiss OK
- Tidak ada filename preview ("akan menyimpan sebagai apa?")
- Tidak ada history export
- Tidak ada smart detection (kalau filename mention 'April' tapi current_month 'Mei', user tidak diberitahu)

**Cross-cutting:**
- File picker selalu buka di Documents default — user repeat 2-3 klik tiap impor/export untuk navigate ke folder kerja
- Tidak ada drag-and-drop real (drop zone visual only)
- Tidak ada conflict resolution di Import (kalau impor file yang overlap dengan data lama, silently overwrite)
- Belum ada progress indicator untuk file besar
- Belum ada bulk import untuk multi-week sekaligus

---

## 2. Goals & Non-Goals

### Goals

**Core UX (Import + Export):**
- File chip prominent dengan filename + meta + action buttons inline (replace bottom-right CTA placement)
- Active month context banner di kedua screen
- Drop zone collapses to compact chip after file pick (Import)
- Dry-run preview SEBELUM commit di Export
- Inline result strip menggantikan messagebox (Export)
- Riwayat history list (Import + Export) — 5 entries terakhir
- Indonesian-formatted dates ("22 → 28 Apr 2026" instead of ISO)
- Filename preview ("akan menyimpan sebagai: ...") di Export

**R-items (additive features):**
- R1: Real drag-and-drop via `tkinterdnd2` library
- R2: Smart filename detection (Export) — auto-detect month from filename, warn on mismatch
- R3: Conflict resolution preview (Import) — count "akan menimpa N baris"
- R4: Progress indicator untuk parse + commit (shared component)
- R5: Recently-used folder memory di file picker (Import + Export)
- R6: Bulk import multi-week (multi-select files, merge previews)
- R7: Export preview read-only (open generated .xlsx in default app after dry-run)
- R8: Save destination dropdown di Export (Same folder / Documents/HR Reports / Custom)

### Non-Goals
- Tidak refactor data layer (DB schema, repos) — only UI + read-only DB queries
- Tidak ubah Excel parsing logic (`parse_fingerprint_file`)
- Tidak ubah report filling logic (`fill_monthly_report`)
- Tidak nambah fitur reporting/analytics — pure UX refresh + 8 R-items
- Tidak ubah bulan auto-detect logic di Import (tetap mode of dates)

---

## 3. Tech Constraints

- **customtkinter** — same constraints sebelumnya: no real shadow, dashed border, blur
- **`tkinterdnd2`** (untuk R1) — new dependency. Bukan part of stdlib. Harus ditambah ke `requirements.txt` + `HR-Absensi.spec` (PyInstaller hidden import + datas if needed)
- **Threading** (untuk R4 progress) — Tk tidak thread-safe untuk UI updates. Pakai `after()` pattern atau dedicated `Queue` polling. Per-event update via `app.update()` saat dalam loop.
- **Reading existing .xlsx** (untuk R7 preview) — pakai default file association via `os.startfile` (Windows) atau `webbrowser.open` fallback. Tidak embed Excel viewer.
- **Settings persistence** — pakai existing `set_setting`/`get_setting` API di `src.db.settings`

---

## 4. Core Changes — Import Screen

### 4.1 Active Month Context Banner

Top of screen, cyan-tinted banner:

```
┌─────────────────────────────────────────────────────────────┐
│ 📆  Bulan aktif saat ini: April 2026.                       │
│     File baru akan auto-detect bulan dan update jika beda. │
└─────────────────────────────────────────────────────────────┘
   bg rgba(34,211,238,.08), border rgba(34,211,238,.25)
```

When file selected dan auto-detected month BERBEDA dari current_month, banner berubah jadi rose warning:

```
┌─────────────────────────────────────────────────────────────┐
│ ⚠  Bulan aktif akan diubah:                                  │
│    April 2026 → Maret 2026 setelah konfirmasi impor.       │
└─────────────────────────────────────────────────────────────┘
   bg rgba(244,63,94,.08), border rgba(244,63,94,.25)
```

Implementasi:
- Method baru `_update_active_month_banner()` di ImportScreen
- Reads current_month dari settings
- Compares dengan mode month dari pending_rows
- Renders cyan vs rose berdasarkan match

### 4.2 File Chip (replaces post-pick drop zone display)

Sebelum pick file: drop zone besar (200px) tetap. Setelah pick: drop zone replaced dengan compact chip + Konfirmasi inline.

Layout chip:
```
┌──────────────────────────────────────────────────────────────────┐
│ 📄  FILE TERPILIH                       [↻ Ganti] [✓ Konfirmasi] │
│     Fingerprint Minggu 4 - April 2026.xls                       │
│     142 KB · diparsing dalam 0.3s                               │
└──────────────────────────────────────────────────────────────────┘
   fg_color=COLOR_SURFACE, border 1px COLOR_BORDER, RADIUS_MD
```

Details:
- Icon: 📄 (24pt)
- Label "FILE TERPILIH": `FONT_LABEL` `COLOR_TEXT_MUTED`
- Name: `FONT_MONO_DATA` `COLOR_TEXT` truncated dengan ellipsis di overflow
- Meta line: size + parse time, `FONT_MONO_SMALL` `COLOR_TEXT_MUTED`
- Actions (right side):
  - "↻ Ganti": ghost button (transparent + COLOR_BORDER_STRONG border) — re-open file picker
  - "✓ Konfirmasi Impor": magenta primary CTA

Click "Ganti" → reset state, show full drop zone again
Click "Konfirmasi" → existing commit logic

### 4.3 Drop Zone Collapses

Drop zone tetap 200px tall sebelum file pick. Setelah pick, drop zone DIHAPUS dari layout (frame.pack_forget()). Chip replaces it. After cancel/reset, drop zone re-packed.

### 4.4 Preview Cards Refresh

Preview cards tetap 4 (Pegawai, Range Tanggal, Issue Baru, Pegawai Baru) tapi:
- **Range Tanggal** format berubah dari ISO ke Indonesian: `"22 → 28 Apr 2026"` (was `"2026-04-01 → 2026-04-30"`)
- Helper function `_format_short_range(start_iso: str, end_iso: str) -> str` di file
  - Same month: `"22 → 28 Apr 2026"` (drop bulan kedua jika sama)
  - Different month: `"30 Apr → 5 Mei 2026"` (drop year kedua jika sama)
  - Different year: `"30 Des 2025 → 5 Jan 2026"`

### 4.5 Riwayat Import History

Bottom of screen (below preview cards), card-style list:

```
┌──────────────────────────────────────────────────────────────────┐
│ RIWAYAT IMPORT TERAKHIR                                          │
│ ────────────────────────────────────────────────────────────────│
│ Today 09:14    Fingerprint Minggu 3 - April 2026.xls   ✓ 28 emp │
│ May 6 21:30    Fingerprint Minggu 2 - April 2026.xls   ✓ 28 emp │
│ Apr 29 14:22   Fingerprint Minggu 1 - April 2026.xls   ✓ 26 emp │
└──────────────────────────────────────────────────────────────────┘
```

Source data: query `attendance_records` for distinct `(imported_from, MAX(imported_at), COUNT(DISTINCT employee_id))` — group by `imported_from`, order by latest `imported_at` DESC, limit 5.

Helper function `list_recent_imports(conn, limit=5) -> list[dict]` di `src/db/attendance.py`:

```python
def list_recent_imports(conn, limit=5):
    """Recent fingerprint imports — distinct imported_from with metadata.

    Returns list of dicts with keys: imported_from, imported_at, emp_count.
    Sorted by imported_at DESC. Limit caller-provided.
    """
    return [dict(r) for r in conn.execute("""
        SELECT
            imported_from,
            MAX(imported_at) AS imported_at,
            COUNT(DISTINCT employee_id) AS emp_count
        FROM attendance_records
        WHERE imported_from IS NOT NULL
        GROUP BY imported_from
        ORDER BY MAX(imported_at) DESC
        LIMIT ?
    """, (limit,))]
```

Display:
- "When" column: relative time format ("Today HH:MM", "Yesterday HH:MM", "MMM D HH:MM"). Helper `_format_relative_time(iso)`.
- File column: truncated dengan ellipsis if too long
- Badge: emerald "✓ N emp" if emp_count > 0 (no partial state needed since import is atomic)

Refresh:
- Initial load di `_build()`
- Reload setelah successful `_on_confirm`

Empty state: "(belum ada riwayat impor)" muted text.

### 4.6 Button Placement Removed from Bottom

`action_row` di bottom (Konfirmasi + Batal) DIHAPUS sepenuhnya. File chip menjadi 3-button layout: `[↻ Ganti] [✕ Batal] [✓ Konfirmasi]`.

- **Ganti**: open file picker untuk pilih file lain (replaces current state)
- **Batal**: clear pending state, kembalikan drop zone besar (no file selected)
- **Konfirmasi**: existing commit logic

---

## 5. Core Changes — Export Screen

### 5.1 Active Month Context Banner

Top of screen, cyan banner:

```
┌──────────────────────────────────────────────────────────────────┐
│ 📆  Akan mengisi laporan untuk: April 2026                       │
│     28 pegawai · 142 issues · 12 unresolved                     │
└──────────────────────────────────────────────────────────────────┘
```

Computed from current_month + DB query:
- Total employees: `SELECT COUNT(DISTINCT employee_id) FROM attendance_records WHERE tanggal BETWEEN ?`
- Total issues: `SELECT COUNT(*) WHERE has_issue = 1`
- Unresolved: `... AND reason_category IS NULL`

If no current_month set: banner shows warning rose "(belum ada bulan aktif — pilih di Active Month dulu)".

### 5.2 File Chip with Export Inline

Same pattern as Import file chip. Setelah pick template:

```
┌──────────────────────────────────────────────────────────────────┐
│ 📄  TEMPLATE LAPORAN BULANAN                  [↻ Ganti] [💾 Export]│
│     Laporan Bulanan April 2026.xlsx                              │
│     ~/Documents/HR · 24 KB                                       │
└──────────────────────────────────────────────────────────────────┘
```

### 5.3 Dry-Run Preview Cards (BEFORE export)

Setelah pick template, langsung run dry-match (no write to disk). Display 3 KPI cards:

| Card | Value source |
|---|---|
| Akan terisi | Filled count dari dry-match |
| NA / Belum kabar | Rows yang akan diisi "NA / Belum ada kabar" |
| Tidak ditemukan | Pegawai di template tapi tidak ada di DB |

Implementasi:
- Refactor `fill_monthly_report` in `src/core/report_filler.py` — add `dry_run: bool = False` parameter
- When `dry_run=True`, perform matching logic + return summary, TIDAK save file
- When `dry_run=False` (default), save file + return summary

Then Export screen calls:
1. After pick: `summary = fill_monthly_report(template, conn, dry_run=True)` → render preview
2. After click Export: `out_path, summary = fill_monthly_report(template, conn, dry_run=False)` → write + render result strip

### 5.4 Inline Result Strip (replace messagebox)

After successful export, replace `messagebox.showinfo` dengan inline strip:

```
┌──────────────────────────────────────────────────────────────────┐
│ ✓  Sukses. File tersimpan sebagai:                              │
│    Laporan Bulanan April 2026 [Auto Filled].xlsx                │
│    130 terisi · 12 NA · 0 not found        [📂 Folder] [📄 Open]│
└──────────────────────────────────────────────────────────────────┘
   bg rgba(16,185,129,.08), border rgba(16,185,129,.25)
```

Actions:
- "📂 Folder": open output file's parent folder in Windows Explorer (`os.startfile(parent_dir)`)
- "📄 Open": open the .xlsx file (`os.startfile(out_path)`)

Both buttons cyan secondary (transparent + COLOR_INFO border).

### 5.5 Riwayat Export History

Below result strip (or at bottom regardless). Similar pattern ke Import history.

Source data: query a NEW table OR use settings JSON. Decision: NEW table `export_history`.

```sql
CREATE TABLE IF NOT EXISTS export_history (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    out_path    TEXT NOT NULL,
    template    TEXT NOT NULL,
    year_month  TEXT NOT NULL,
    filled      INTEGER NOT NULL,
    na          INTEGER NOT NULL,
    not_found   INTEGER NOT NULL,
    created_at  DATETIME DEFAULT (datetime('now', 'localtime'))
);
```

DDL added to `src/db/schema.py` (idempotent `init_db`).

Helper functions in `src/db/export_history.py` (new file):
- `record_export(conn, out_path, template, year_month, filled, na, not_found)` — INSERT
- `list_recent_exports(conn, limit=5)` — SELECT ORDER BY created_at DESC LIMIT N

Display similar to Import history:
- When: relative time
- File: out_path basename
- Badge: emerald `"✓ {filled}/{total}"` if 100% filled, rose `"{filled}/{total}"` if partial.

### 5.6 Filename Preview

In dry-run state, banner/text shows:
"Akan menyimpan sebagai: `Laporan Bulanan April 2026 [Auto Filled].xlsx`"

Output filename logic existing in `fill_monthly_report` — extract to a helper `compute_output_filename(template_path) -> Path`. Reuse for preview display.

---

## 6. R-items (R1-R8)

### R1 — Drag-and-Drop via `tkinterdnd2`

**Add dependency:**
- `requirements.txt`: add `tkinterdnd2>=0.3.0`
- `HR-Absensi.spec`: add `'tkinterdnd2'` to `hiddenimports`. Bundle the package's TCL files via `datas` if PyInstaller doesn't auto-detect.

**Code changes:**

In `src/main.py`, replace `app = HRApp()` with:
```python
# tkinterdnd2's TkinterDnD wraps tk.Tk; CTk.CTk subclasses tk.Tk so we need
# to patch the base class via TkinterDnD.Tk._classic_drag_init pattern, OR
# instantiate via the library's Window class. Decision in implementation.

from tkinterdnd2 import TkinterDnD
class HRApp(TkinterDnD.Tk, ctk.CTk):
    ...
```

Multiple inheritance approach is tricky with CTk's metaclass. Alternative:
1. Use `tkinterdnd2.TkinterDnD.Tk` as root, manually configure CTk styling on top
2. Use `windnd` library instead (simpler API, monkey-patches existing widget)

**Decision:** Use `windnd` library — single-function API, no class hierarchy issues:

```python
import windnd

def _on_drop(files):
    for f in files:
        path = Path(f.decode("utf-8") if isinstance(f, bytes) else f)
        if path.suffix.lower() in (".xls", ".xlsx"):
            self._handle_file(path)
            break

windnd.hook_dropfiles(self.dropzone, func=_on_drop)
```

`windnd` is Windows-only (acceptable — this is a Windows desktop app). Library is tiny (~30 lines). Falls back gracefully if not installed (try/except wrap).

Update `requirements.txt`: add `windnd` (not `tkinterdnd2`).
Update `HR-Absensi.spec`: add `'windnd'` to `hiddenimports`.

### R2 — Smart Filename Detection (Export)

Helper function `detect_year_month_from_filename(path: Path) -> str | None`:

```python
import re
_MONTH_NAMES = {
    "januari": 1, "jan": 1, "february": 2, "februari": 2, "feb": 2,
    "maret": 3, "mar": 3, "april": 4, "apr": 4, "mei": 5, "may": 5,
    "juni": 6, "jun": 6, "juli": 7, "jul": 7, "agustus": 8, "ags": 8,
    "september": 9, "sep": 9, "sept": 9, "oktober": 10, "okt": 10,
    "november": 11, "nov": 11, "desember": 12, "des": 12, "dec": 12,
}

def detect_year_month_from_filename(path: Path) -> str | None:
    """Parse filename for Indonesian/English month + year. Returns 'YYYY-MM' or None.

    Examples:
        "Laporan Bulanan April 2026.xlsx" → "2026-04"
        "Laporan Maret 2026 [filled].xlsx" → "2026-03"
        "report-2026-05.xlsx" → "2026-05" (via ISO match)
    """
    name = path.stem.lower()

    # Try ISO 'YYYY-MM' match first
    iso_match = re.search(r"(\d{4})[-_](\d{2})", name)
    if iso_match:
        return f"{iso_match.group(1)}-{iso_match.group(2)}"

    # Try month name + year
    for word, month_num in _MONTH_NAMES.items():
        if word in name:
            year_match = re.search(r"\b(20\d{2})\b", name)
            if year_match:
                return f"{year_match.group(1)}-{month_num:02d}"

    return None
```

Place in `src/core/report_generator.py` (already has Indonesian month logic) OR new `src/core/filename_parser.py`.

Wiring in Export screen:
- After file pick, call `detected = detect_year_month_from_filename(path)`
- Compare with current_month
- If `detected and detected != current_month`: show warn banner inline (instead of cyan):
  ```
  ⚠ Mismatch: File mention 'April 2026' tapi bulan aktif 'Mei 2026'.
    Data dari Mei 2026 akan dimasukkan ke template April 2026.
  ```

### R3 — Conflict Resolution Preview (Import)

When parsing file, check overlap with existing DB rows.

Helper `count_overlap(conn, pending_rows) -> dict`:
```python
def count_overlap(conn, pending_rows):
    """Count how many pending rows would overwrite existing DB rows.

    Returns {'new': N, 'overwrite': M}.
    """
    new_count = 0
    overwrite_count = 0
    for r in pending_rows:
        emp = get_employee_by_no_staff(conn, r.no_staff)
        if emp is None:
            new_count += 1
            continue
        existing = conn.execute(
            "SELECT 1 FROM attendance_records WHERE employee_id = ? AND tanggal = ?",
            (emp.id, r.tanggal)
        ).fetchone()
        if existing:
            overwrite_count += 1
        else:
            new_count += 1
    return {'new': new_count, 'overwrite': overwrite_count}
```

Display: add 5th KPI card "Akan Menimpa" with rose value if > 0:

| Card | Value |
|---|---|
| Pegawai | 28 |
| Range Tanggal | 22 → 28 Apr 2026 |
| Issue Baru | 12 |
| Pegawai Baru | 2 |
| **Akan Menimpa** | **45 baris** (rose) |

Note: existing upsert preserves `reason_category` and `reason_detail` — overwrite is data-only, not destructive of user input. Documented in card hover tooltip (future) or below as muted footnote: "*Alasan ijin yang sudah diinput tidak akan terhapus.*"

### R4 — Progress Indicator

Reusable component `src/ui/components/progress_modal.py` (new):

```python
class ProgressModal(ctk.CTkToplevel):
    """Modal overlay with progress bar + status text.

    Usage:
        with ProgressModal(parent, title="Memproses file") as p:
            p.update_progress(0.0, "Parsing...")
            # ... work ...
            p.update_progress(0.5, "Inserting rows...")
            # ... more work ...
            p.update_progress(1.0, "Selesai")
    """
    def __init__(self, parent, title="Memproses..."):
        super().__init__(parent)
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        # 400x140 centered, COLOR_SURFACE + 1px COLOR_BORDER, RADIUS_LG
        # Title FONT_HEADING + status FONT_BODY + CTkProgressBar
        ...

    def update_progress(self, pct: float, status: str):
        self.bar.set(pct)
        self.status_lbl.configure(text=status)
        self.update()  # force redraw — Tk single-threaded

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.destroy()
```

Wired into:
- Import: parse → insert flow. Update progress after parse done, then in insert loop every 10 rows.
- Export: dry-run match + write. Update before write.
- Bulk import (R6): per-file progress.

Threshold: only show progress if `len(rows) > 50` or estimated duration > 500ms. Below that, skip — just instant.

### R5 — Recently-Used Folder Memory

Settings keys (new):
- `last_import_folder` — folder of last imported file
- `last_export_template_folder` — folder of last picked template
- `last_export_save_folder` — folder where last export was saved (default = template folder)

Update both `_on_pick_file` (Import) and `_pick` (Export):

```python
# Read last folder
initialdir = get_setting(conn, "last_import_folder") or str(Path.home() / "Documents")

path = filedialog.askopenfilename(
    title="Pilih file fingerprint",
    initialdir=initialdir,
    filetypes=[("Excel", "*.xls *.xlsx")],
)
if not path:
    return

# Save parent folder for next time
set_setting(conn, "last_import_folder", str(Path(path).parent))
```

Same pattern for Export.

### R6 — Bulk Import Multi-Week

Modify `_on_pick_file` to allow multi-select:

```python
paths = filedialog.askopenfilenames(  # plural → returns tuple
    title="Pilih file fingerprint (boleh multi-select)",
    initialdir=initialdir,
    filetypes=[("Excel", "*.xls *.xlsx")],
)
if not paths:
    return
```

For each path, parse → accumulate rows in `self._pending_rows`. Update preview cards with totals across all files. File chip becomes a "files chip" showing count + size sum:

```
📄  FILES TERPILIH (4 files)              [↻ Ganti] [✕ Batal] [✓ Konfirmasi]
    Fingerprint Minggu 1-4 April 2026.xls — 4 files, 142 KB total
    diparsing dalam 1.2s
```

On confirm, commit all rows in one transaction (existing logic — wrap in single `with get_connection`).

### R7 — Export Preview Read-Only

After dry-run preview is rendered, add new button `👁 Preview File` to file chip (cyan tertiary):

```
[↻ Ganti] [👁 Preview File] [💾 Export]
```

Click action:
1. Run actual export to a TEMP file (e.g., `~/AppData/Local/Temp/HR-preview-{timestamp}.xlsx`)
2. Open with default system viewer: `os.startfile(temp_path)` on Windows
3. User reviews in Excel/LibreOffice/etc., can close without saving
4. Note: temp file not auto-cleaned — user may save-as if they want

Simpler approach (preferred): the temp .xlsx IS the actual output but saved to temp dir instead of next-to-template. User can open + verify, then if happy save to actual location via Excel's Save As.

Implementation detail: button only enabled when dry-run passes (i.e., file chip in normal state).

### R8 — Save Destination Dropdown

Add CTkOptionMenu to file chip OR separate row below banner:

```
┌──────────────────────────────────────────────────────────────────┐
│ SIMPAN OUTPUT KE                                                 │
│ [Folder template (default) ▾]                                    │
└──────────────────────────────────────────────────────────────────┘
```

Options:
- "Folder template (default)" → save next to template file (existing behavior)
- "Documents/HR Reports/" → auto-create + save there
- "Pilih folder..." → opens `filedialog.askdirectory()` modal, persists choice

Settings key: `export_save_mode` (enum: `template_folder | hr_reports | custom`)
Settings key: `export_save_custom_path` (string, only when mode=custom)

Refactor `fill_monthly_report` signature to accept optional `out_dir: Path | None`:

```python
def fill_monthly_report(template_path: Path, conn, dry_run=False, out_dir=None):
    """If out_dir is None, save next to template. Otherwise save to out_dir."""
    ...
```

---

## 7. Implementation Phases / Commit Breakdown

**Total: 7 commits, ~30 tasks.**

| # | Commit | Scope | Tasks |
|---|---|---|---|
| 1 | `feat(db): export_history table + import history query` | Foundation — DB schema + queries for both history features | 4 |
| 2 | `feat(ui): Import core refresh + R5 folder memory` | Import file chip + banner + collapse + Indonesian range + history + folder memory + button placement | 8 |
| 3 | `feat(ui): Import — R3 conflict resolution + R6 bulk import` | Conflict count preview + multi-file select + accumulated preview | 5 |
| 4 | `feat(ui): Export core refresh + R5 folder memory` | Export banner + file chip + dry-run preview + result strip + history + filename preview + folder memory | 8 |
| 5 | `feat(ui): Export — R2 smart filename + R7 preview + R8 save destination` | Filename mismatch warning + temp preview button + destination dropdown | 5 |
| 6 | `feat(ui): R4 progress modal (shared) + R1 drag-and-drop` | New ProgressModal component + windnd drag-drop integration | 5 |
| 7 | `chore: handoff doc v6 + smoke test` | Final wrap-up | 2 |

### Per-phase task detail

**Phase 1 — Foundation (4 tasks):**
1. Add `export_history` table to `src/db/schema.py` DDL (idempotent)
2. Create `src/db/export_history.py` with `record_export` + `list_recent_exports`
3. Add `list_recent_imports` to `src/db/attendance.py`
4. Unit tests untuk new repo functions (~3-4 tests)

**Phase 2 — Import core + R5 (8 tasks):**
1. Add active month banner (cyan) + state machine
2. Replace post-pick layout: drop zone hides, file chip shows
3. Implement file chip widget (icon + info + 3 buttons)
4. Helper `_format_short_range(start, end) -> str` — Indonesian compact range
5. Wire `_format_short_range` into preview cards
6. Implement history list widget at bottom of screen, call `list_recent_imports` on load + after confirm
7. Wire R5: persist `last_import_folder` setting, pass `initialdir` to filedialog
8. Remove bottom action_row, run pytest + smoke, commit

**Phase 3 — Import R3 + R6 (5 tasks):**
1. Implement `count_overlap(conn, pending_rows)` in `src/db/attendance.py`
2. Add 5th "Akan Menimpa" KPI card (rose when > 0, COLOR_TEXT_MUTED when 0)
3. Add footer note "Alasan ijin yang sudah diinput tidak akan terhapus" (muted)
4. R6: change filedialog to `askopenfilenames`, iterate paths, accumulate rows
5. Update file chip label to "FILES TERPILIH" when multiple, run tests + smoke + commit

**Phase 4 — Export core + R5 (8 tasks):**
1. Add active month banner with data summary (cyan, or rose if no current_month)
2. Refactor `fill_monthly_report` to accept `dry_run` parameter (no write, return summary)
3. Replace post-pick state: file chip with inline Konfirmasi/Ganti/Export buttons
4. Implement dry-run preview cards (3 cards: filled/NA/not_found) after pick
5. Replace messagebox.showinfo dengan inline result strip + Folder/Open buttons (`os.startfile`)
6. Implement filename preview helper `compute_output_filename(template)`, render in chip or banner
7. Implement history list at bottom calling `list_recent_exports`, refresh after export
8. Wire R5 folder memory for template browse + run tests + smoke + commit

**Phase 5 — Export R2 + R7 + R8 (5 tasks):**
1. Implement `detect_year_month_from_filename` helper in `src/core/filename_parser.py` (new file) + tests
2. After pick, check `detect_year_month_from_filename` vs current_month; show rose warn banner if mismatch
3. R7: add "👁 Preview File" button between Ganti and Export. On click, write to temp dir + `os.startfile`
4. R8: add Save Destination CTkOptionMenu above file chip area. Persist via settings. Modify `fill_monthly_report(out_dir=...)`.
5. Run tests + smoke + commit

**Phase 6 — R4 + R1 (5 tasks):**
1. Create `src/ui/components/progress_modal.py` with `ProgressModal` class (CTkToplevel + bar + status)
2. Wire ProgressModal into Import commit loop (every 10 rows update). Threshold: only show if rows > 50.
3. Wire ProgressModal into Export dry-run + write (single update per phase).
4. R1: add `windnd` to requirements.txt + HR-Absensi.spec hiddenimports. Wire `windnd.hook_dropfiles` on Import dropzone. Fallback gracefully via try/except if library missing.
5. Run tests + smoke + commit

**Phase 7 — Handoff (2 tasks):**
1. Write `docs/superpowers/specs/2026-05-15-session-handoff-v6.md` (model after v5 handoff)
2. Final commit

---

## 8. Risks & Cons

| # | Risk | Mitigation |
|---|---|---|
| 1 | `windnd` library bundling issue di PyInstaller | Try/except wrap; fallback to click-only drop zone if hook_dropfiles fails. Test build before merge. |
| 2 | Multi-inheritance CTk + TkinterDnD complications (avoided by choosing windnd) | Use windnd which monkey-patches existing widget — no inheritance. |
| 3 | Dry-run preview perf untuk template besar | Most templates are < 500 rows. Acceptable scan time < 200ms. If issue, add caching by template+mtime. |
| 4 | Conflict preview slow karena N+1 query | Batch query: single `SELECT employee_id, tanggal FROM attendance_records WHERE (employee_id, tanggal) IN (...)` then set-diff. |
| 5 | Progress modal "freezes" if work is single-statement | `update()` calls during loop body. Acceptable since this is single-user desktop app — no concurrent user requests. |
| 6 | `os.startfile` Windows-only | OK — app is Windows desktop. macOS/Linux would need `subprocess.Popen(['open'/'xdg-open', path])` but out of scope. |
| 7 | Filename detection ambiguous (e.g., "Laporan April Mei 2026.xlsx") | Helper returns first month match. Acceptable — user pickable filenames are typically single-month. |
| 8 | Bulk import duplicate rows across files | Existing upsert handles via UNIQUE constraint on `(employee_id, tanggal)`. No additional logic needed. |
| 9 | Temp preview file (R7) accumulates di Temp folder | Windows auto-cleans %TEMP%. Acceptable — file size small (~30 KB each). |
| 10 | Save destination "Documents/HR Reports" auto-create may fail (permissions) | Try/except + fallback to template folder + show warning toast. |
| 11 | History query slow as table grows | Both queries have `LIMIT 5` and use indexed columns (`imported_at`, `created_at`). Acceptable for thousands of entries. |

---

## 9. Testing

### Unit tests (new)
- `tests/test_export_history.py` — record + list_recent (3-4 tests)
- `tests/test_filename_parser.py` — detect_year_month for Indonesian + ISO formats (5-6 tests)
- `tests/test_import_history.py` — list_recent_imports (2-3 tests)
- `tests/test_report_filler_dry_run.py` — dry_run parameter behavior (2 tests)

Target: 98 passed (current) + ~13 new = **~111 passed** after full implementation.

### Manual smoke test (post-implementation)
1. **Import core:**
   - Pick file → drop zone collapses, chip appears with filename + meta + 3 buttons
   - Active month banner cyan when match, rose when mismatch
   - Range tanggal Indonesian short ("22 → 28 Apr 2026")
   - History list shows last 5 imports
   - Click Ganti → file picker opens at last folder
   - Click Konfirmasi → import success toast, screen resets, history refreshes
2. **Import R3 + R6:**
   - 5th KPI "Akan Menimpa" shown if file overlaps with existing data
   - Multi-select 2+ files → chip shows "FILES TERPILIH (N files)"
3. **Export core:**
   - Active month banner top
   - Pick template → dry-run runs, 3 preview cards (filled/NA/not-found)
   - Click Export → result strip emerald with Folder/Open buttons
   - History list shows last 5 exports
4. **Export R2 + R7 + R8:**
   - Pick template with mismatched month → rose warn banner
   - Click "👁 Preview File" → opens temp .xlsx in default app
   - Save Destination dropdown → switch between 3 modes, output goes to correct folder
5. **R4 Progress:**
   - Import file with > 50 rows → modal shows progress 0% → 100%
6. **R1 Drag-drop:**
   - Drag .xls from Explorer to drop zone → file is loaded as if browsed

---

## 10. Definition of Done

- [ ] All core Import changes (file chip, banner, collapse, range format, history, button placement)
- [ ] All core Export changes (banner, dry-run, file chip, result strip, history, filename preview)
- [ ] R1 windnd drag-drop integrated
- [ ] R2 smart filename detection (Export)
- [ ] R3 conflict resolution preview (Import)
- [ ] R4 progress modal (shared component)
- [ ] R5 folder memory (Import + Export)
- [ ] R6 bulk import multi-week
- [ ] R7 export preview read-only button
- [ ] R8 save destination dropdown
- [ ] DB: `export_history` table + DDL + `list_recent_*` functions
- [ ] Helper: `_format_short_range`, `detect_year_month_from_filename`, `compute_output_filename`
- [ ] Existing 98 tests pass + ~13 new tests = ~111 total
- [ ] Manual smoke test pass (Section 9)
- [ ] 7 separate commits for reviewability
- [ ] Handoff doc v6 written
- [ ] .exe rebuilt + deployed via rotation
- [ ] No new hardcoded color literals

---

## 11. Open Questions / Future Work

1. **Conflict resolution mode toggle** — currently overwrite is silent (existing upsert). After this spec, user sees count but can't choose "skip" vs "overwrite" per-row. Future: add "Pilih per row" option dengan checkboxes.
2. **Drag-and-drop multi-file** — R1 + R6 combo: if user drags multiple .xls files, batch them. Currently spec'd as single-file drop. Easy extension.
3. **Import file format detection** — currently only `.xls/.xlsx`. Could add CSV support in future.
4. **Export to PDF** — currently only fills .xlsx template. Future: optional "Export ke PDF" button via openpyxl + libreoffice command-line.
5. **Recent files persistence beyond current month** — after "Mulai Bulan Baru" (now removed), history might want to span months. Acceptable as-is.

---

*End of spec.*
