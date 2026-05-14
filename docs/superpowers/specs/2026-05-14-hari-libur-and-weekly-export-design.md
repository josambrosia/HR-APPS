# Menu Hari Libur + Export Mingguan — Design Spec

**Tanggal:** 2026-05-14
**Status:** Design locked (mockup disetujui), siap implementation plan
**Base branch:** `origin/v11` (worktree sudah di-ff ke v11 = `e383c35`)
**Target:** snapshot v12

---

## 1. Goal

Dua fitur yang saling terkait, dibangun dalam satu spec:

1. **Menu Hari Libur** — kemampuan menandai tanggal sebagai hari libur. Hari libur tidak dihitung sebagai hari kerja, issue karyawan di tanggal itu otomatis ter-resolve, dan tanggal itu keluar dari recap Dashboard + cetak. Laporan Bulanan menampilkan baris libur dengan penanda "Libur".
2. **Export Mingguan** — fitur baru untuk re-export data mingguan yang sudah dinormalisasi ke Excel. Sekaligus merestrukturisasi layar Export menjadi dua mode jelas: **Export** (isi template dari atasan) vs **Generate** (buat file baru dari database).

Hari Libur jadi fondasi: status libur disimpan rapi sehingga Export Mingguan (dan Laporan Bulanan) tinggal membacanya.

---

## 2. Scope

| Surface | Terpengaruh? | Catatan |
|---|---|---|
| Dashboard insights (semua panel) | ✅ Ya | Baris hari libur keluar dari semua agregasi |
| Cetakan Dashboard (HTML print) | ✅ Ya | Otomatis — konsumsi fungsi insight yang sama |
| Coaching screen (`list_coaching_for_week`) | ✅ Ya | Baris hari libur keluar dari hitungan keterlambatan |
| Issues screen | ✅ Sebagian | Issue di tanggal libur jadi "resolved (Libur)" — pindah dari tab Open ke Resolved. Tidak ada perubahan kode di layar Issues |
| Laporan Bulanan — Generate (`report_generator`) | ✅ Ya | Baris libur: "Libur" di kolom G, kolom hitungan kosong |
| Laporan Bulanan — Export/fill (`report_filler`) | ✅ Ya | Baris libur dilewati — tidak menulis kolom Q |
| Export Mingguan (baru) | ✅ Ya | Kolom F (Tipe) = "Hari Libur" untuk tanggal libur |
| Import fingerprint | ✅ Ya | Re-stamp status libur setelah upsert |
| WhatsApp Assistant | ❌ Tidak | Draft pesan tetap dibuat seperti biasa |
| Layar Active Month | ✅ Ya | Tombol "Generate" dihapus dari kartu bulan (pindah ke layar Export) |
| Sidebar | ✅ Ya | Tambah menu "Hari Libur" + dirapatkan (opsi A) |

---

# FITUR 1 — MENU HARI LIBUR

## 3. Data Model (Hybrid)

Status libur disimpan di **dua tempat** yang saling melengkapi:

### 3.1 Tabel `holidays` — sumber kebenaran

```sql
CREATE TABLE IF NOT EXISTS holidays (
    tanggal    TEXT PRIMARY KEY,   -- "YYYY-MM-DD"
    created_at TEXT NOT NULL
);
```

Ditambahkan ke string `DDL` di [src/db/schema.py](src/db/schema.py). Idempoten via `CREATE TABLE IF NOT EXISTS` — aman untuk `data/hr.db` existing. PRIMARY KEY pada `tanggal` sekaligus jadi index untuk lookup. Pola sama dengan cara `outlier_exclusions` ditambahkan di v11.

Tanpa kolom `label`/nama — keputusan YAGNI, gampang ditambah nanti kalau perlu.

### 3.2 Kolom `attendance_records.tipe` — denormalisasi

Untuk tanggal libur, `attendance_records.tipe` di-stamp dari `'Hari Kerja'` → `'Hari Libur'`. Ini membuat data "benar-benar berubah" — Export Mingguan (yang baca kolom Tipe langsung) dan query lain otomatis melihat status libur tanpa harus JOIN ke tabel `holidays`.

**Kenapa hybrid:** kalau status libur HANYA di `attendance_records.tipe`, re-import fingerprint menimpa kolom `tipe` balik jadi `'Hari Kerja'` dan status hilang tanpa cara pulihkan. Tabel `holidays` jadi catatan awet; `restamp_holidays` (§3.6) mengembalikan stamp setelah tiap import.

### 3.3 Invariant

- `holidays.tanggal` = sumber kebenaran tunggal. "Tanggal D adalah libur" ⟺ ada row di `holidays` dengan `tanggal = D`.
- Untuk setiap `tanggal` di `holidays`, semua `attendance_records` di tanggal itu yang `tipe = 'Hari Kerja'` di-stamp jadi `'Hari Libur'`. Konsistensi ini dijaga oleh `mark_holidays` / `unmark_holidays` / `restamp_holidays`.
- Hari libur berlaku **se-perusahaan** — berlaku untuk semua pegawai di tanggal itu (tidak per-departemen).

## 4. Komponen Fitur 1

### 4.1 `src/db/schema.py` (MODIFY)

- Tambah blok `CREATE TABLE IF NOT EXISTS holidays ...` ke string `DDL`.
- Tambah migrasi idempoten untuk DB existing: kolom `export_history.kind` (lihat §9.4). Buat helper `_migrate(conn)` dipanggil dari `init_db` setelah `executescript(DDL)`:
  - `PRAGMA table_info(export_history)` → kalau kolom `kind` belum ada → `ALTER TABLE export_history ADD COLUMN kind TEXT NOT NULL DEFAULT 'fill'`.
  - Tabel `holidays` tidak perlu migrasi — `CREATE TABLE IF NOT EXISTS` cukup.

### 4.2 `src/db/holidays.py` (NEW)

Data-access layer untuk `holidays` + operasi stamp/resolve. Fungsi:

```python
def list_holidays(conn) -> list[str]:
    """Semua tanggal libur (YYYY-MM-DD), urut ASC."""

def holiday_dates_in_month(conn, year_month: str) -> set[str]:
    """Tanggal libur dalam bulan tertentu. Untuk layar Hari Libur."""

def workday_roster(conn, year_month: str) -> list[dict]:
    """Tanggal yang punya attendance record di bulan tsb dengan
    tipe IN ('Hari Kerja','Hari Libur'), urut tanggal ASC.
    Tiap dict: {tanggal, hari, is_holiday: bool, issue_count: int}.
      - is_holiday: tanggal ada di tabel holidays
      - issue_count: kalau BUKAN holiday → jumlah issue OPEN (has_issue=1
        AND reason_category IS NULL) — preview "akan ter-resolve".
        Kalau holiday → jumlah row reason_category='libur' — preview
        "akan dibuka kembali".
    Sumber daftar tanggal untuk layar Hari Libur (Sabtu/Minggu tidak
    muncul — tipe='Istirahat', tidak ikut)."""

def mark_holidays(conn, dates: list[str]) -> dict:
    """Tandai tanggal-tanggal sebagai libur. Untuk tiap tanggal:
      1. INSERT OR IGNORE ke holidays (tanggal, created_at=now)
      2. UPDATE attendance_records SET tipe='Hari Libur'
         WHERE tanggal=? AND tipe='Hari Kerja'
      3. Auto-resolve: UPDATE attendance_records
         SET reason_category='libur', reason_detail=NULL, resolved_at=now
         WHERE tanggal=? AND has_issue=1 AND reason_category IS NULL
    Idempoten — tanggal yang sudah libur jadi no-op.
    Returns {dates_marked: int, issues_resolved: int}."""

def unmark_holidays(conn, dates: list[str]) -> dict:
    """Batalkan status libur. Untuk tiap tanggal:
      1. DELETE FROM holidays WHERE tanggal=?
      2. UPDATE attendance_records SET tipe='Hari Kerja'
         WHERE tanggal=? AND tipe='Hari Libur'
      3. Un-resolve HANYA yang di-resolve oleh fitur ini:
         UPDATE attendance_records
         SET reason_category=NULL, reason_detail=NULL, resolved_at=NULL
         WHERE tanggal=? AND reason_category='libur'
    Issue yang di-resolve manual (kategori lain) TIDAK disentuh.
    Returns {dates_unmarked: int, issues_reopened: int}."""

def restamp_holidays(conn) -> None:
    """Dipanggil setelah import fingerprint. Untuk semua tanggal di
    tabel holidays: re-apply langkah 2 & 3 dari mark_holidays
    (stamp tipe + auto-resolve issue OPEN). Membuat import idempoten
    terhadap status libur — menutup lubang re-import."""
```

**Catatan transaksi:** semua fungsi tulis menerima `conn` dan TIDAK commit sendiri — caller (layar / import flow) yang commit, konsisten dengan pola `src/db/outlier.py`.

### 4.3 Kategori reason `"libur"` (MODIFY)

- [src/config.py](src/config.py): tambah `"libur"` ke `REASON_CATEGORIES`.
- [src/core/reason_mapper.py](src/core/reason_mapper.py): tambah `"libur": "Libur"` ke `REASON_LABELS`. Tidak masuk `REASON_NEEDS_DETAIL`. `render_alasan_ijin("libur", None)` → `"Libur"`.
- [src/core/report_generator.py](src/core/report_generator.py): `IJIN_CATEGORIES` harus mengecualikan `"libur"` — ubah jadi `tuple(c for c in REASON_CATEGORIES if c not in ("na", "libur"))`. Alasan: hari libur bukan "ijin" personal, tidak boleh menambah hitungan kolom Ijin.

`"libur"` sengaja dipakai sebagai reason_category karena: (a) membuat issue keluar dari daftar Open (mekanisme resolve app yang sudah ada), (b) jadi penanda untuk revert (`unmark_holidays` hanya menyentuh `reason_category='libur'`). Trade-off yang diterima — alternatifnya kolom flag baru, lebih banyak schema.

### 4.4 `src/ui/screens/holiday.py` (NEW) — layar Hari Libur, pola B

Mengikuti struktur visual layar Outlier ([src/ui/screens/outlier.py](src/ui/screens/outlier.py)) — header + badge bulan aktif + info bar + scroll.

**Struktur:**
- **Header:** judul "Hari Libur" + subtitle "Tandai tanggal sebagai hari libur — tidak dihitung sebagai hari kerja" + badge bulan aktif (cyan, baca `get_setting(conn, "current_month")`).
- **Info bar** (cyan border-left): "N hari libur ditandai bulan ini. Hari libur tidak dihitung sebagai hari kerja — issue karyawan di tanggal itu otomatis ter-resolve & keluar dari recap Dashboard + cetak."
- **Daftar checkbox tanggal:** dari `workday_roster(conn, month)`. Tiap baris: checkbox + "Hari, DD Bulan YYYY". Tanggal yang `is_holiday=True` → checkbox ter-centang + baris bertema violet + tag "SUDAH LIBUR". State checkbox disimpan di `dict[str, ctk.BooleanVar]`.
- **Preview dampak** (update saat checkbox berubah): hitung diff antara state checkbox sekarang vs `is_holiday` awal:
  - tanggal baru dicentang → "X tanggal akan jadi libur · Y issue akan ter-resolve" (Y = jumlah `issue_count` tanggal-tanggal itu)
  - tanggal di-uncheck → "Z tanggal dibuka kembali · W issue dibuka lagi"
- **Tombol "Terapkan Perubahan":** hitung `to_mark = checked - holiday_dates_in_month`, `to_unmark = holiday_dates_in_month - checked`. Panggil `mark_holidays(conn, to_mark)` + `unmark_holidays(conn, to_unmark)`, `conn.commit()`, re-render, tampilkan toast sukses. Tidak ada dialog konfirmasi terpisah — preview + tombol Terapkan itu sendiri sudah jadi gerbang konfirmasi (konsisten gaya app yang ringan).

**State handling:**
- Belum ada bulan aktif → empty state "Belum ada bulan aktif. Pilih bulan di menu Active Month dulu."
- Bulan aktif ada tapi roster kosong → empty state "Belum ada data untuk bulan aktif. Import fingerprint dulu via menu Import."
- Tidak ada perubahan checkbox dari state awal → tombol Terapkan disabled.

### 4.5 Re-stamp saat import (MODIFY)

[src/ui/screens/import_screen.py](src/ui/screens/import_screen.py) — di flow commit import (`_ingest_paths` / setelah loop `upsert_attendance`), sebelum `conn.commit()`, panggil `restamp_holidays(conn)`. Ini memastikan setelah re-import minggu yang sama, tanggal yang ada di tabel `holidays` di-stamp ulang `tipe='Hari Libur'` + issue yang baru muncul ikut ter-resolve.

## 5. Keluar dari Recap (insights + coaching)

Karena baris hari libur punya `tipe='Hari Libur'`, fungsi yang **sudah** memfilter `tipe='Hari Kerja'` di WHERE-nya otomatis mengecualikan baris libur — **tidak perlu diubah**:
- `karyawan_teladan`, `karyawan_teladan_top_n`, `hari_paling_rawan`, `avg_minutes_per_late_event`, `pola_jam_masuk` di [src/core/insights.py](src/core/insights.py).

Fungsi yang **belum** memfilter tipe — tambah `AND tipe = 'Hari Kerja'` (alias `ar.tipe`) ke WHERE:
- `terlambat_ranking` — `WHERE ar.tanggal BETWEEN ? AND ?` → tambah `AND ar.tipe = 'Hari Kerja'`. Aman: baris `Istirahat` selama ini berkontribusi 0, sekarang baris `Hari Libur` ikut tereliminasi. Cascade otomatis ke `top_n_terlambat` & `coaching_flag` yang derive dari sini.
- `ranking_departemen` — tambah `AND ar.tipe = 'Hari Kerja'`.
- `resolution_rate` — `WHERE has_issue = 1 AND tanggal BETWEEN ? AND ?` → tambah `AND tipe = 'Hari Kerja'`. Supaya issue yang di-resolve sebagai 'libur' tidak menggelembungkan resolution rate.
- `list_coaching_for_week` di [src/db/coaching.py](src/db/coaching.py) — di CTE `terlambat`, `WHERE ar.tanggal BETWEEN ? AND ?{exc_frag}` → tambah `AND ar.tipe = 'Hari Kerja'`.

Dashboard ([src/ui/screens/dashboard.py](src/ui/screens/dashboard.py)) & cetak HTML ([src/reports/html_renderer.py](src/reports/html_renderer.py)) konsumsi fungsi-fungsi di atas — **tidak perlu diubah**, ikut benar otomatis.

Layar Issues — issue di tanggal libur jadi `reason_category='libur'`, jadi otomatis pindah dari "Open" ke "Resolved" lewat query `list_open_issues` / `list_issues_for_period` yang sudah ada. **Tidak perlu perubahan kode.**

## 6. Laporan Bulanan & baris hari libur

### 6.1 `src/core/report_generator.py` (MODIFY) — mode Generate Bulanan

Di loop generate / `_write_data_row`, deteksi baris libur: `is_holiday = db_row.get("tipe") == "Hari Libur"`. Untuk baris libur:
- Kolom **E (Tipe)** = `"Hari Kerja"` — **bukan** "Hari Libur". User memilih "Kolom G saja" (bukan "ubah kolom Tipe"); laporan bulanan harus mirip file referensi `Laporan Bulanan April.xlsx` di mana baris libur tetap Tipe="Hari Kerja". report_generator meng-override balik nilai tipe untuk display.
- Kolom **F (Jadwal)** = nilai apa adanya dari DB (mis. "08.00 - 16.00").
- Kolom **G (Masuk)** = `"Libur"` (teks penanda).
- Kolom **H (Keluar)** = kosong.
- Kolom **I–P** (Kerja, Lembur, Kurang, Terlambat, Pulang Cepat, Absen, Lupa, Ijin) = kosong/0.
- Kolom **Q (Alasan Ijin)** = kosong.
- Baris libur **tidak diakumulasi** ke Total Personal — `_accumulate_total` di-skip untuk baris libur.

### 6.2 `src/core/report_filler.py` (MODIFY) — mode Export (isi template)

`fill_monthly_report` — tambah `ar.tipe` ke SELECT. Kalau `row["tipe"] == "Hari Libur"` → `continue` (lewati baris, tidak menulis kolom Q). Alasan: mode Export menghormati template atasan dan hanya menyentuh kolom Q (Alasan Ijin); hari libur bukan alasan ijin personal, jadi tidak menyuntik teks ke kolom itu.

---

# FITUR 2 — RESTRUKTUR EXPORT + EXPORT MINGGUAN

## 7. Restruktur layar Export

[src/ui/screens/export.py](src/ui/screens/export.py) direstrukturisasi dengan **toggle mode di atas**: `📤 Export` | `⚙ Generate`.

### 7.1 Mode Export (perilaku lama, tidak berubah fungsional)

Pilih template Laporan Bulanan dari atasan → app mengisi kolom Q (Alasan Ijin) dari database via `report_filler.fill_monthly_report`. Semua fitur yang ada (active month banner, save destination, file chip, dry-run preview cards, result strip, riwayat) dipindahkan apa adanya ke dalam builder `_build_export_mode()`.

### 7.2 Mode Generate (mengumpulkan aksi "buat dari database")

Sub-toggle: `Bulanan` | `Mingguan`.
- **Bulanan** → dropdown pilih bulan (semua bulan dari `list_months_with_stats`, default bulan aktif) + tombol "Generate" → `report_generator.generate_monthly_report`. Memindahkan kapabilitas yang dulu ada di kartu Active Month.
- **Mingguan** → `WeekNavBar` untuk bulan aktif (pola sama Dashboard/Coaching, pakai `weeks_in_month`) + tombol "Generate" → `weekly_export.generate_weekly_export` (§8).

Save destination dropdown & result strip dipakai bersama kedua mode. Riwayat di bawah menampilkan semua jenis export.

### 7.3 Refactor struktur

`_build()` jadi: build mode-toggle + container. `_build_export_mode()` (konten lama, di-extract) dan `_build_generate_mode()` (baru). Ganti mode = swap isi container. Nama menu sidebar **tetap "Export"** (lihat §11 — asumsi yang perlu dikonfirmasi).

## 8. `src/core/weekly_export.py` (NEW) — Export Mingguan

```python
def generate_weekly_export(conn, period_start: str, period_end: str,
                           out_path: Path) -> WeeklyExportSummary:
    """Buat file Excel re-export data mingguan yang dinormalisasi.
    Query attendance_records JOIN employees untuk rentang tanggal,
    ORDER BY e.nama, ar.tanggal. Tulis workbook baru (openpyxl, dari
    nol — tanpa template). Returns WeeklyExportSummary(rows, employees)."""
```

**Struktur output — 12 kolom dinormalisasi** (header di baris 1, data dari baris 2):

| Kol | Field | Catatan |
|---|---|---|
| A | Nama | |
| B | No. Staff | |
| C | Dept | |
| D | Tanggal | ISO `YYYY-MM-DD` |
| E | Hari | |
| **F** | **Tipe** | `'Hari Libur'` untuk tanggal libur (langsung dari DB, sudah di-stamp) |
| G | Jadwal | |
| H | Masuk | kosong untuk baris libur |
| I | Keluar | kosong untuk baris libur |
| J | Kerja | kosong untuk baris libur |
| K | Lembur | kosong untuk baris libur |
| L | Terlambat | kosong untuk baris libur |

Baris libur (`tipe='Hari Libur'`): F apa adanya (`'Hari Libur'`), G (Jadwal) dipertahankan, H–L dikosongkan.

**Styling:** header baris 1 bold, lebar kolom diset wajar. Tanpa template embedded — workbook dibuat dari nol (scope ringan; styling kaya = out of scope).

**Nama file default:** `Laporan Mingguan {rentang}.xlsx` — `{rentang}` pakai format Indonesia ringkas mirroring helper di [src/ui/screens/import_screen.py](src/ui/screens/import_screen.py) (mis. "7-11 April 2026"). User tetap bisa rename di dialog Save.

## 9. Perubahan pendukung Fitur 2

### 9.1 `src/ui/screens/active_month.py` (MODIFY)

Hapus tombol "Generate" dari `_render_card`, hapus method `_on_generate`, hapus import `generate_monthly_report`. Kartu bulan tinggal "✓ Pilih" / "✓ Sedang Aktif". Layar kembali murni untuk memilih bulan aktif.

### 9.2 `src/db/export_history.py` (MODIFY)

`record_export` — tambah parameter `kind: str = "fill"`. Nilai: `"fill"` (mode Export), `"generate_bulanan"`, `"generate_mingguan"`. Untuk flow generate: `filled` = jumlah baris ter-generate, `na` = `na_count` (bulanan) atau 0 (mingguan), `not_found` = 0, `template` = `"-"`.

### 9.3 `src/db/schema.py` (MODIFY)

`export_history` di `DDL` tambah kolom `kind TEXT NOT NULL DEFAULT 'fill'`. Untuk DB existing, migrasi `ALTER TABLE` (lihat §4.1).

### 9.4 Riwayat list di Export screen

`_render_history` adaptasi badge per `kind` — label/ikon beda untuk fill vs generate. `list_recent_exports` ikut mengembalikan `kind`.

---

# SIDEBAR — Opsi A (rapikan)

## 10. Penataan sidebar

[src/ui/app.py](src/ui/app.py) `_build_sidebar`:
- **Tambah menu:** `("🌴", "Hari Libur", "Holiday")` ke grup `EXCEPTIONAL CASE` (setelah Outlier). 5 kategori tetap.
- **Wiring:** `_show()` tambah cabang `elif name == "Holiday": from src.ui.screens.holiday import HolidayScreen; HolidayScreen(self.content).grid(...)`.
- **Rapatkan (opsi A):**
  - Tinggi nav item di `_build_nav_item`: `height=36` → `height=32`.
  - Padding label kategori dikurangi (`pady=(SPACE_SM, SPACE_XS)` → lebih kecil).
  - Footer 4 baris → 2 baris: 1 baris brand horizontal ("Josaphat Tech" putih + "Solution" magenta berdampingan) + 1 baris mono "v{APP_VERSION} · {tagline}". Pisahkan dari blok footer lama yang 4 label vertikal.
  - Chip bulan aktif: kurangi padding internal kedua label.

Tidak ada perubahan struktur kategori — perubahan paling minim, sesuai pilihan user.

---

## 11. Asumsi yang diputuskan (perlu dikonfirmasi user saat review spec)

1. **Nama menu tetap "Export"** — bukan "Export & Generate" atau "Laporan". Konsisten dengan pilihan sidebar opsi A (perubahan minim).
2. **Hari libur se-perusahaan** — berlaku untuk semua pegawai di tanggal itu, bukan per-departemen.
3. **`report_filler` melewati baris libur** — tidak menulis "Libur" ke kolom Q template atasan. Mode Export hanya menyentuh kolom Q dan hari libur bukan alasan ijin personal.
4. **Tabel `holidays` tanpa kolom label/nama** — YAGNI.
5. **`export_history` ditambah kolom `kind`** + migrasi ALTER TABLE untuk DB existing.
6. **Laporan Bulanan (Generate): kolom E tetap "Hari Kerja"** untuk baris libur (penanda hanya di kolom G), meniru file referensi April. Berbeda dengan Export Mingguan yang kolom F-nya memang "Hari Libur".

---

## 12. Data Flow

```
Layar Hari Libur (pola B: multi-pilih + Terapkan)
  │  mark_holidays / unmark_holidays
  ▼
src/db/holidays.py ──writes──► tabel holidays  (sumber kebenaran)
       │                  └──► attendance_records.tipe = 'Hari Libur'  (stamp)
       │                  └──► attendance_records.reason_category = 'libur'  (auto-resolve issue OPEN)
       │
Import fingerprint ──► upsert_attendance ──► restamp_holidays(conn) ──┘ (re-stamp pasca import)
       │
       ▼  (baris libur punya tipe='Hari Libur')
┌──────────────────────────────────────────────────────────────┐
│ insights.py + coaching.py  — filter AND tipe='Hari Kerja'    │
│   → Dashboard, cetak HTML, Coaching screen (semua otomatis)  │
│ report_generator.py  — baris libur: G="Libur", kolom lain kosong │
│ report_filler.py     — baris libur: di-skip                  │
│ weekly_export.py     — baris libur: kolom F="Hari Libur"      │
└──────────────────────────────────────────────────────────────┘

Layar Export
  ├─ mode Export   → report_filler.fill_monthly_report  (isi template atasan)
  └─ mode Generate
       ├─ Bulanan  → report_generator.generate_monthly_report
       └─ Mingguan → weekly_export.generate_weekly_export
```

---

## 13. Error Handling & Edge Cases

- **Belum ada bulan aktif / belum ada data** → layar Hari Libur tampil empty state. Mode Generate Mingguan: WeekNavBar kosong / tombol disabled.
- **Re-import minggu yang sudah ada hari libur** → `restamp_holidays` mengembalikan stamp `tipe` + re-resolve issue OPEN yang baru muncul. Tertangani.
- **Tanggal libur punya issue yang sudah di-resolve manual** (kategori selain 'libur') → `mark_holidays` hanya menyentuh issue OPEN (`reason_category IS NULL`); yang manual tidak disentuh. `unmark_holidays` hanya membuka yang `reason_category='libur'`.
- **Pegawai sempat absen masuk di tanggal yang kemudian jadi libur** → data masuk/keluar tetap di DB, tapi `tipe='Hari Libur'` → keluar dari recap; Laporan Bulanan/Mingguan mengosongkan kolom hitungannya.
- **Semua tanggal di bulan ditandai libur** → fungsi insight return list kosong → Dashboard & cetak tampil empty state existing.
- **DB existing tanpa tabel `holidays` / kolom `kind`** → `CREATE TABLE IF NOT EXISTS` + migrasi `ALTER TABLE` di `init_db` menanganinya saat startup.
- **Generate ke folder yang tidak writable** → `out_path.parent.mkdir(...)` raise → caller tangkap, tampilkan messagebox error (pola existing).
- **Toggle mode Export saat ada file chip terpilih** → state tiap mode dipertahankan terpisah; pindah mode lalu kembali tidak me-reset pilihan template di mode Export.

---

## 14. Testing

Pola fixture `temp_db_path` + helper `_add_emp` / `_add_att` yang sudah ada.

| Layer | Coverage |
|---|---|
| `tests/test_holidays_db.py` (NEW) | `mark_holidays` (stamp tipe + auto-resolve hanya issue OPEN + idempoten) · `unmark_holidays` (un-stamp + un-resolve hanya 'libur') · `restamp_holidays` (idempoten, re-apply pasca import) · `workday_roster` (is_holiday + issue_count benar) · `holiday_dates_in_month` |
| `tests/test_insights.py` (MODIFY) | Tiap fungsi terfilter: baseline tanpa libur tidak berubah + dengan 1-2 tanggal libur (agregat turun benar). `terlambat_ranking`, `ranking_departemen`, `resolution_rate` |
| `tests/test_coaching_db.py` (MODIFY) | `list_coaching_for_week` mengecualikan tanggal libur |
| `tests/test_report_generator.py` (MODIFY) | Baris libur: G="Libur", E="Hari Kerja", H–Q kosong, Total Personal tidak terpengaruh |
| `tests/test_report_filler*.py` (MODIFY) | Baris libur dilewati — kolom Q tidak ditulis |
| `tests/test_weekly_export.py` (NEW) | 12 kolom + header benar · baris libur F="Hari Libur" & H–L kosong · filter rentang tanggal · urutan nama→tanggal |
| `tests/test_schema.py` (MODIFY) | Tabel `holidays` ada · kolom `export_history.kind` ada setelah `init_db` · migrasi ALTER aman di DB existing |
| `tests/test_export_history.py` (MODIFY) | `record_export` dengan `kind` |
| Manual smoke | Tandai 2 tanggal libur → cek Dashboard/cetak/Coaching angkanya turun · cek Issues pindah ke Resolved · Generate Bulanan & Mingguan → cek baris libur · revert → cek balik · re-import → cek status libur bertahan · sidebar muat di layar maximized |

Target: 160 (baseline v11) + ~35-45 test baru ≈ **~195-205 passing**.

---

## 15. Implementation Notes

- **Worktree:** sudah di branch `claude/trusting-lederberg-6e61bb` di atas v11. Tidak perlu rebase.
- **Urutan implementasi disarankan:** (1) schema + migrasi + test_schema → (2) `src/db/holidays.py` + tests → (3) config + reason_mapper ("libur") → (4) insights + coaching filter + tests → (5) report_generator + report_filler baris libur + tests → (6) re-stamp wiring di import → (7) layar `holiday.py` + sidebar wiring + rapikan → (8) `src/core/weekly_export.py` + tests → (9) restruktur `export.py` (mode Export/Generate) + `active_month.py` (hapus Generate) + `export_history.kind` → (10) full test + manual smoke.
- **Build & deploy:** pola standar — tutup .exe, build di worktree, rotate dari `dist/HR-Absensi/` main project. Push sebagai snapshot `v12` saat user authorize.
- **No auto-push** — tunggu instruksi user.
- **Test sebelum commit** — `pytest -q` harus match baseline yang terdokumentasi tiap tahap.

---

## 16. Out of Scope

- Field "label"/nama hari libur (mis. "Wafat Isa Almasih") — YAGNI.
- Hari libur per-departemen.
- Auto-load kalender hari libur nasional.
- Styling/template kaya untuk file Export Mingguan — hanya formatting dasar.
- Pengaruh ke WhatsApp Assistant.
- Item deferred lama (About dialog, conflict resolution toggle, cross-screen helper extraction, dll) — tetap di luar scope.

---

## 17. Reference

- **Mockup (disetujui):** `.superpowers/brainstorm/4753-1778755120/content/` — `hari-libur-screen.html` (pola B), `export-generate-v2.html` (restruktur Export), `sidebar-reorg.html` (opsi A), `recap.html`.
- **File referensi data:** `Data Absensi/Laporan Bulanan April.xlsx` — baris libur 3 April 2026 (G="Libur", E="Hari Kerja").
- **Pola precedent:** fitur Outlier v11 — `src/db/outlier.py` + `src/ui/screens/outlier.py` + `docs/superpowers/specs/2026-05-14-outlier-exclusion-design.md`.
- **Schema pattern:** [src/db/schema.py](src/db/schema.py) `DDL` string + `init_db`.
- **Active month setting:** key `current_month` di tabel `settings`, baca via `get_setting(conn, "current_month")`.
