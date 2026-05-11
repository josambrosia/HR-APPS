# Multi-Month + Laporan Bulanan Generator — Design Spec

**Tanggal:** 2026-05-12
**Status:** Draft (menunggu approval user)
**Author:** Brainstorming session

---

## 1. Konteks & Problem

User adalah HR yang setiap bulan harus generate Laporan Bulanan Absensi. Saat ini
workflow:

1. Import fingerprint per minggu sepanjang bulan
2. Input alasan untuk issue yang muncul
3. Akhir bulan: **terima file template `Laporan Bulanan {Month}.xlsx` dari atasan**
4. Pakai Export screen → fill kolom Q (Alasan Ijin)

**Pain point:** Step 3 fragile. File template kadang baru ada di akhir bulan,
itupun jika user bisa dapat filenya. Tanpa template, user blocked.

**Insight kunci:** File Laporan Bulanan sebenarnya hanyalah kompilasi dari data
fingerprint mingguan yang sudah ada di DB, dengan sedikit penyesuaian (Total
Personal row per pegawai, format kolom). App **sudah punya semua data** yang
dibutuhkan — cuma belum bisa generate sendiri.

**Sekaligus:** Saat ini "Mulai Bulan Baru" = `DELETE FROM attendance_records`,
artinya data bulan lalu hilang. Untuk fitur generator yang berguna jangka
panjang, multi-month persistence wajib.

---

## 2. Goals & Non-Goals

### Goals
- Generate `Laporan Bulanan {Month} {Year} [Auto Filled].xlsx` dari data DB
  tanpa butuh template input dari atasan
- Multi-month persistence — data lintas bulan **tidak terhapus**
- UI baru: **Riwayat Bulan** screen — card-per-bulan dengan stats + action
- Format laporan match dengan existing `Laporan Bulanan April.xlsx` (17 kolom,
  Total Personal row per blok pegawai, header dan formatting setara)
- **Workflow lama (Export → Fill Template) tetap ada** sebagai paralel — user
  bisa pilih: fill template kalau atasan kasih file, atau generate sendiri
  kalau tidak

### Non-Goals
- Tidak ada holiday detection / kalender libur nasional (cell `masuk` NULL
  ditampilkan blank di output; rasionalnya Alasan Ijin di kolom Q sudah
  communicate reason)
- Tidak ada auto-archive bulan lama (forever-keep; DB size tetap kecil)
- Tidak ada format customization per atasan (output mengikuti template embed
  fixed)
- Tidak ada migrasi schema DB — semua field derived dihitung on-the-fly saat
  generate
- Tidak ada bulk generate (1 file per bulan; user klik per bulan)
- Tidak ada delete per bulan dari UI sekarang (kalau perlu di masa depan,
  tambah ke screen Riwayat Bulan via context menu)

---

## 3. UI/UX Design

### 3.1 Sidebar — menu baru

Sidebar bertambah 1 item, total 7 (sebelumnya 6):

```
1. Dashboard
2. Import
3. Issues
4. Summary
5. Export        ← tetap (fill template, fallback)
6. Riwayat Bulan ← BARU
7. Settings      ← "Mulai Bulan Baru" button DIHAPUS
```

### 3.2 Riwayat Bulan screen — layout

Vertical list of cards, newest-first. Tiap card represent 1 bulan yang ada di DB.

```
┌─ Riwayat Bulan ──────────────────────────────────┐
│                                                  │
│ ┌──────────────────────────────────────────────┐ │
│ │ ● April 2026                       (aktif)   │ │
│ │   30 hari · 247 records · 5 issue open       │ │
│ │   [Buka]   [📄 Generate Laporan]             │ │
│ └──────────────────────────────────────────────┘ │
│                                                  │
│ ┌──────────────────────────────────────────────┐ │
│ │ ○ Maret 2026                                 │ │
│ │   31 hari · 256 records · 0 issue            │ │
│ │   [Buka]   [📄 Generate Laporan]             │ │
│ └──────────────────────────────────────────────┘ │
│                                                  │
│ ┌──────────────────────────────────────────────┐ │
│ │ ○ Februari 2026                              │ │
│ │   28 hari · 234 records · 0 issue            │ │
│ │   [Buka]   [📄 Generate Laporan]             │ │
│ └──────────────────────────────────────────────┘ │
│                                                  │
└──────────────────────────────────────────────────┘
```

**Empty state** (belum ada data sama sekali):
```
┌─ Riwayat Bulan ──────────────────────────────────┐
│                                                  │
│   Belum ada data.                                │
│   Import fingerprint dulu via menu Import.       │
│                                                  │
└──────────────────────────────────────────────────┘
```

### 3.3 Card details

| Element | Detail |
|---|---|
| **Status indicator** | ● (filled bullet, `COLOR_ACCENT`) for active month, ○ (outline bullet, `COLOR_TEXT_DIM`) for others |
| **Active label** | Text `(aktif)` di kanan title, warna `COLOR_TEXT_DIM` |
| **Background** | Active month: `COLOR_PANEL_OPEN` (sedikit lebih terang). Other: `COLOR_PANEL`. |
| **Title** | `{Month Indonesian} {Year}` mis. "April 2026" |
| **Stats line** | `{hari} hari · {records} records · {open_issues} issue open` |
| **Buka button** | Width 100px, `COLOR_GOLD` fg, text dark |
| **Generate Laporan button** | Width 180px, `COLOR_OK` fg, text dark |

### 3.4 Behavior

| Action | Efek |
|---|---|
| **Klik Buka** | Set `current_month` ke "YYYY-MM" bulan tersebut + auto-navigate ke Dashboard. Indikator (●) pindah ke card baru saat user kembali ke Riwayat Bulan. |
| **Klik Generate Laporan** | Trigger generator. Tidak perlu Buka dulu — generator pakai bulan card itu, bukan current_month. Save dialog muncul → user pilih lokasi → file ter-save → toast notifikasi. |
| **Klik card kosong** (area di luar button) | No-op untuk sekarang (tidak ada double-click action). |

### 3.5 Settings screen change

- **Hapus** button "Mulai Bulan Baru" dan section "Bulan Aktif" yang isinya
  picker manual + button reset
- Tetap ada: jadwal kerja, coaching threshold, pegawai CRUD

### 3.6 Toast feedback setelah generate

```
✓ Laporan Bulanan April 2026 berhasil disimpan
File: C:\Users\user\Downloads\Laporan Bulanan April 2026 [Auto Filled].xlsx
247 baris di-generate · 5 baris NA / Belum ada kabar
```

---

## 4. Architecture

### 4.1 File structure (yang baru / berubah)

```
src/
├── core/
│   ├── report_generator.py     ← BARU: generate from DB + template
│   └── report_filler.py        ← TETAP (Export screen workflow)
├── db/
│   └── attendance.py           ← TAMBAH: list_months_with_stats()
├── ui/
│   ├── app.py                  ← TAMBAH: register Riwayat Bulan menu
│   └── screens/
│       ├── months.py           ← BARU: MonthsScreen
│       └── settings.py         ← UBAH: hapus "Mulai Bulan Baru" block

templates/                      ← BARU folder (di-bundle PyInstaller)
└── laporan_bulanan_template.xlsx

HR-Absensi.spec                 ← UBAH: tambah templates/ ke datas
```

### 4.2 Data flow

```
User klik [Generate Laporan] di card "April 2026"
    ↓
MonthsScreen._on_generate("2026-04")
    ↓
filedialog.asksaveasfilename(initialfile="Laporan Bulanan April 2026 [Auto Filled].xlsx")
    ↓
report_generator.generate_monthly_report(
    conn, year_month="2026-04", out_path=<chosen>
)
    ↓
1. Load templates/laporan_bulanan_template.xlsx (headers + format reference rows)
2. Query DB: SELECT ar.*, e.nama, e.dept FROM attendance_records ar
            JOIN employees e ON ar.employee_id = e.id
            WHERE substr(ar.tanggal, 1, 7) = ?
            ORDER BY e.nama, ar.tanggal
3. Group by employee → for each employee: write rows + Total Personal
4. Apply formatting (copy from template's sample rows)
5. wb.save(out_path)
    ↓
Return GenerateSummary(rows_generated, na_count)
    ↓
Toast notification
```

### 4.3 Template strategy

`templates/laporan_bulanan_template.xlsx` berisi:

- **Row 1**: 17 header lengkap (Nama, Dept., Tanggal, Hari, Tipe, Jadwal,
  Masuk, Keluar, Kerja, Lembur, Kurang, Terlambat, Pulang Cepat, Absen,
  Lupa in/out, Ijin, Alasan Ijin)
- **Row 2**: sub-header (Jam, Jam, Jam, Menit, Menit, Hari, Hari, Hari) untuk
  kolom I-P
- **Merged ranges** yang sesuai (mis. A1:A2 untuk single-header columns,
  C1:C2 untuk Tanggal, dst)
- **Row 3**: 1 sample data row (akan jadi reference formatting saat generator
  copy style ke setiap data row baru)
- **Row 4**: 1 sample Total Personal row (akan jadi reference formatting
  untuk Total Personal rows yang di-generate)
- **Column widths** sesuai original

Generator approach:
1. Open template via `openpyxl.load_workbook`
2. Cache style + merged-range info dari row 3 (data sample) dan row 4 (total sample)
3. **Delete row 3 dan row 4** sebelum insert data baru
4. Insert N data rows + M Total Personal rows
5. Apply cached styles to new rows
6. Apply Total Personal merge (A:H span) to each Total Personal row

Template di-create **sekali** sebagai bagian dari development setup:
- Aku tulis script `tools/build_template.py` yang ambil
  `Data Absensi/Laporan Bulanan April.xlsx` → strip data rows 5+ → keep rows
  1-4 → save sebagai `templates/laporan_bulanan_template.xlsx`
- Script di-jalanin sekali, hasilnya di-commit ke repo

### 4.4 Multi-month — apa yang berubah

| Komponen | Sebelum | Sesudah |
|---|---|---|
| `attendance_records` table | DELETED tiap "Mulai Bulan Baru" | Forever-keep, no schema change |
| `current_month` setting | Manual / via "Mulai Bulan Baru" | Auto-set saat import (sudah ada) atau via "Buka" di Riwayat Bulan |
| `reset_month()` function di `db/attendance.py` | Dipakai oleh Settings screen | **Tidak dipakai lagi**. Tetap di code (akan dihapus di cleanup task atau dipertahankan untuk delete-by-month feature di masa depan) |
| Settings screen "Mulai Bulan Baru" button | Ada | Hapus |
| Dashboard, Issues, Summary, Export | Filter via `current_month` | Tidak berubah — masih filter via `current_month`, tapi `current_month` bisa berubah-ubah |

---

## 5. Data Model

### 5.1 Schema — TIDAK BERUBAH

Existing schema sudah cukup untuk multi-month (tanggal field sudah DATE, bisa
hold any year-month). Tidak ada migration.

### 5.2 Query baru di `db/attendance.py`

```python
def list_months_with_stats(conn) -> list[dict]:
    """Return list of months in DB with stats, ordered newest-first.

    Each dict: {
        "year_month": "2026-04",          # for current_month setter
        "label": "April 2026",            # for display
        "hari_count": int,                # distinct tanggal count
        "records_count": int,             # total attendance_records
        "open_issues_count": int,         # has_issue=1 AND reason IS NULL
    }
    """
    return conn.execute("""
        SELECT
            substr(tanggal, 1, 7) AS year_month,
            COUNT(DISTINCT tanggal) AS hari_count,
            COUNT(*) AS records_count,
            SUM(CASE
                WHEN has_issue = 1 AND reason_category IS NULL THEN 1
                ELSE 0
            END) AS open_issues_count
        FROM attendance_records
        GROUP BY year_month
        ORDER BY year_month DESC
    """).fetchall()
```

Label "April 2026" di-derive di Python (`MONTH_NAMES_ID[int(month)] + " " + year`).

---

## 6. Core Logic — `report_generator.py`

### 6.1 Module surface

```python
from dataclasses import dataclass
from pathlib import Path
import sqlite3

@dataclass
class GenerateSummary:
    rows_generated: int        # total data rows
    na_count: int              # rows where Alasan Ijin = "NA / Belum ada kabar"
    employees_count: int       # distinct pegawai in this month

def generate_monthly_report(
    conn: sqlite3.Connection,
    year_month: str,           # "YYYY-MM"
    out_path: Path,
) -> GenerateSummary:
    ...
```

### 6.2 Derived field computation

Untuk setiap row dari DB:

```python
def compute_derived(row, jadwal_end_minutes=16*60):
    """row is attendance_records row (dict-like)."""
    is_kerja = row["tipe"] == "Hari Kerja"
    has_masuk = row["masuk"] is not None
    has_keluar = row["keluar"] is not None
    has_reason = row["reason_category"] in (
        "izin_sakit", "cuti", "tugas_lapangan", "tugas_paparan",
        "terlambat_kerja", "terlambat_lain", "lupa_absen",
    )

    kerja_jam = row["kerja_jam"] or 0
    kurang_jam = max(0, 8 - kerja_jam) if is_kerja else 0

    pulang_cepat_menit = 0
    if has_keluar and is_kerja:
        keluar_min = _hhmm_to_minutes(row["keluar"])
        if keluar_min < jadwal_end_minutes:
            pulang_cepat_menit = jadwal_end_minutes - keluar_min

    absen_hari = 1 if is_kerja and not has_masuk and not has_keluar else 0
    lupa_hari = 1 if is_kerja and (has_masuk ^ has_keluar) else 0
    ijin_hari = 1 if has_reason else 0

    return {
        "kurang_jam": kurang_jam,
        "pulang_cepat_menit": pulang_cepat_menit,
        "absen_hari": absen_hari,
        "lupa_hari": lupa_hari,
        "ijin_hari": ijin_hari,
    }
```

### 6.3 Total Personal computation

Setelah blok per pegawai di-write, append Total Personal row:

```python
def total_personal(employee_rows: list[dict]) -> dict:
    """Sum per-employee numeric columns."""
    return {
        "kerja_jam_sum": sum(r["kerja_jam"] or 0 for r in employee_rows),
        "lembur_jam_sum": sum(r["lembur_jam"] or 0 for r in employee_rows),
        "kurang_jam_sum": sum(r["kurang_jam"] for r in employee_rows),
        "terlambat_menit_sum": sum(r["terlambat_menit"] or 0 for r in employee_rows),
        "pulang_cepat_sum": sum(r["pulang_cepat_menit"] for r in employee_rows),
        "absen_sum": sum(r["absen_hari"] for r in employee_rows),
        "lupa_sum": sum(r["lupa_hari"] for r in employee_rows),
        "ijin_sum": sum(r["ijin_hari"] for r in employee_rows),
    }
```

### 6.4 Column mapping ke worksheet

| Col | Header | Source |
|---|---|---|
| A (1) | Nama | `employees.nama` |
| B (2) | Dept. | `employees.dept` |
| C (3) | Tanggal | `attendance_records.tanggal` (datetime) |
| D (4) | Hari | `attendance_records.hari` |
| E (5) | Tipe | `attendance_records.tipe` |
| F (6) | Jadwal | `attendance_records.jadwal` |
| G (7) | Masuk | `attendance_records.masuk` (HH:MM or blank) |
| H (8) | Keluar | `attendance_records.keluar` (HH:MM or blank) |
| I (9) | Kerja (Jam) | `attendance_records.kerja_jam` |
| J (10) | Lembur (Jam) | `attendance_records.lembur_jam` |
| K (11) | Kurang (Jam) | **derived** |
| L (12) | Terlambat (Menit) | `attendance_records.terlambat_menit` |
| M (13) | Pulang Cepat (Menit) | **derived** |
| N (14) | Absen (Hari) | **derived** |
| O (15) | Lupa in/out (Hari) | **derived** |
| P (16) | Ijin (Hari) | **derived** |
| Q (17) | Alasan Ijin | `render_alasan_ijin(reason_category, reason_detail)` atau `"NA / Belum ada kabar"` jika `has_issue=1` tanpa reason |

Untuk Total Personal row:
- A: text `"Total Personal:"` (merged A:H)
- I-P: sum values
- Q: blank

### 6.5 Format inheritance dari template

```python
def copy_row_style(template_row, target_row, max_col=17):
    """Copy cell style (font, fill, border, alignment, number_format) from template_row to target_row."""
    for col in range(1, max_col + 1):
        src = template_row[col - 1]      # tuple from ws.iter_rows
        dst = target_row[col - 1]
        if src.has_style:
            dst.font = copy(src.font)
            dst.fill = copy(src.fill)
            dst.border = copy(src.border)
            dst.alignment = copy(src.alignment)
            dst.number_format = src.number_format
```

(openpyxl style objects perlu di-copy karena reference-shared by default.)

---

## 7. Implementation Notes

### 7.1 Template generation script (one-time)

`tools/build_template.py`:

```python
"""One-time script to create templates/laporan_bulanan_template.xlsx
from the reference Laporan Bulanan April.xlsx."""
from openpyxl import load_workbook
from pathlib import Path

REF = Path("Data Absensi/Laporan Bulanan April.xlsx")
OUT = Path("templates/laporan_bulanan_template.xlsx")

def main():
    wb = load_workbook(REF)
    ws = wb.active

    # Keep rows 1, 2 (headers), 3 (sample data row), 4 (sample Total Personal row)
    # Delete everything from row 5 onwards
    if ws.max_row > 4:
        ws.delete_rows(5, ws.max_row - 4)

    OUT.parent.mkdir(exist_ok=True)
    wb.save(OUT)
    print(f"Wrote {OUT}")

if __name__ == "__main__":
    main()
```

Run sekali: `python tools/build_template.py`. Commit hasilnya.

### 7.2 PyInstaller bundle

Update `HR-Absensi.spec`:

```python
datas=[
    ('src/reports/templates/*.j2', 'src/reports/templates'),
    ('templates/laporan_bulanan_template.xlsx', 'templates'),   # ← BARU
],
```

Resolve at runtime via `src/config.py`:

```python
TEMPLATE_LAPORAN_BULANAN = APP_ROOT / "templates" / "laporan_bulanan_template.xlsx"
```

`APP_ROOT` sudah ada (PyInstaller-aware).

### 7.3 Indonesian month names

```python
# src/core/report_generator.py
MONTH_NAMES_ID = [
    None, "Januari", "Februari", "Maret", "April", "Mei", "Juni",
    "Juli", "Agustus", "September", "Oktober", "November", "Desember",
]

def month_label(year_month: str) -> str:
    """'2026-04' -> 'April 2026'"""
    y, m = year_month.split("-")
    return f"{MONTH_NAMES_ID[int(m)]} {y}"
```

### 7.4 Removing "Mulai Bulan Baru"

Di `src/ui/screens/settings.py`:
- Hapus button "Mulai Bulan Baru"
- Hapus 2-tahap confirmation dialog terkait
- Hapus call ke `reset_month()`
- `reset_month()` di `db/attendance.py` **tetap ada** sebagai dead code (untuk
  potential future delete-by-month feature). Bisa di-cleanup di task terpisah.

---

## 8. Testing

### 8.1 Unit tests (yang ditambah)

| File baru | Test |
|---|---|
| `tests/test_report_generator.py` | (1) Derived field computation untuk semua kombinasi (Hari Kerja vs Istirahat, masuk null vs ada, dst). (2) Total Personal sum benar. (3) End-to-end: feed fixture DB month, generate file, verify openpyxl-read output has correct header row, data rows, total row. (4) Edge: bulan kosong → file dengan cuma header. |
| `tests/test_db_list_months.py` | (1) Empty DB → list kosong. (2) 1 bulan → 1 entry. (3) 2 bulan → 2 entries, newest-first. (4) Stats counts match expected. |

Target: 6-8 test baru. Existing 69 tests harus tetap pass.

### 8.2 Manual smoke test

1. Buka app → Sidebar terlihat 7 menu (Dashboard, Import, Issues, Summary, Export, **Riwayat Bulan**, Settings)
2. Settings → "Mulai Bulan Baru" button **tidak ada**
3. Import fingerprint Maret + April → DB punya 2 bulan
4. Menu Riwayat Bulan → 2 card muncul, newest-first (April aktif)
5. Klik [Buka] di Maret → kembali ke Dashboard, indicator pindah ke Maret saat balik ke Riwayat Bulan
6. Klik [Generate Laporan] di April → save dialog, simpan ke Desktop → file `Laporan Bulanan April 2026 [Auto Filled].xlsx` tercipta
7. Buka file di Excel → format match Laporan Bulanan April.xlsx asli (17 kolom, header benar, Total Personal per pegawai, semua kolom terisi sesuai data)
8. Compare visual: side-by-side dengan `Laporan Bulanan April [filled].xlsx` (output workflow lama) — angka harus identik (selain perbedaan: workflow lama mungkin punya text "Libur" yang generator tidak punya)

---

## 9. Risks & Edge Cases

| Risk | Mitigation |
|---|---|
| Template di-bundle berbeda dari hasil generator (drift) | One-time script `tools/build_template.py` deterministic dari reference file. Commit both to git. |
| Pegawai tidak ada di `employees` table tapi ada di `attendance_records` (data integrity issue) | JOIN query akan exclude row tersebut. Tambah pre-check di generator: log/warn ke user kalau ada records tanpa employee match. |
| Bulan kosong (no records) tapi user klik Generate | Generator return GenerateSummary(0, 0, 0), file di-save dengan header saja. Toast: "0 baris di-generate (bulan kosong)." |
| Format Excel sumber berubah di masa depan (kolom Q bukan Alasan Ijin lagi) | Bukan concern saat ini; spec menyebut kolom Q sebagai konstanta. Kalau berubah, re-run build_template.py. |
| Performance — bulan dengan 10 pegawai × 30 hari = 300 rows + 10 Total Personal | Negligible untuk openpyxl. Tested up to 1000 rows under 1 second. |
| User generate berkali-kali bulan sama | Setiap generate save dialog muncul, user bebas overwrite atau pilih nama lain. Tidak ada state at risk. |
| Settings "current_month" tidak match dengan data | Riwayat Bulan compute dari `attendance_records` langsung (substr(tanggal, 1, 7)). `current_month` setting cuma untuk "default view". Tidak ada inconsistency risk. |
| `reset_month()` function dead code | Acceptable. Cleanup task terpisah kalau nanti diperlukan. |

---

## 10. Migration / Backward Compatibility

### 10.1 Existing data
- Hr.db users yang sudah ada: tetap dipakai. Schema tidak berubah. Data dipertahankan.
- Setelah upgrade ke versi ini, user yang dulu langganan klik "Mulai Bulan Baru" akan otomatis preserve data berikutnya (button-nya dihapus, tidak ada DELETE).

### 10.2 First-run experience
- Existing user: buka app → tidak ada efek otomatis. Mereka harus discover Riwayat Bulan via sidebar.
- New install: sama. Riwayat Bulan kosong sampai user import fingerprint pertama.

### 10.3 No DB migration needed
Schema unchanged. Existing `hr.db` files compatible.

---

## 11. Definition of Done

- [ ] `src/core/report_generator.py` module exists with `generate_monthly_report()` working
- [ ] `templates/laporan_bulanan_template.xlsx` exists in repo + di-bundle di PyInstaller
- [ ] `tools/build_template.py` script committed (untuk regenerate template kalau perlu)
- [ ] `src/db/attendance.py` punya `list_months_with_stats()` function
- [ ] `src/ui/screens/months.py` exists — Riwayat Bulan screen
- [ ] Sidebar di `src/ui/app.py` register menu Riwayat Bulan (urutan: setelah Export, sebelum Settings)
- [ ] `src/ui/screens/settings.py` — "Mulai Bulan Baru" block dihapus
- [ ] 6-8 unit test baru passing
- [ ] 69 existing tests tetap passing
- [ ] Manual smoke test pass (semua 8 step di Section 8.2)
- [ ] Generated file `Laporan Bulanan April 2026 [Auto Filled].xlsx` visually identik (dalam toleransi) dengan reference `Laporan Bulanan April.xlsx`
- [ ] Export screen (workflow lama) tidak terkena regresi — `Fill Template` masih jalan

---

## 12. Out of Scope (future iteration ideas)

- Delete bulan dari Riwayat Bulan (context menu / ⋯ button per card)
- Bulk generate semua bulan sekaligus
- Compare 2 bulan side-by-side di UI
- Stats per bulan lebih kaya (top pegawai, total lembur, dll) di card
- Holiday detection / kalender libur nasional untuk akurasi "Libur" di output
- Customize template format per atasan
- Export ke PDF langsung (sekarang lewat browser print Dashboard saja)

---

*End of spec.*
