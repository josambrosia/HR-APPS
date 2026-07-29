# v24.0.0 — Edit Alasan dari Editor + Rekap Dinas & Paparan

**Status:** Design locked (brainstorming 2026-07-30)
**Fork dari:** `v23.0.0`
**Target versi:** `v24.0.0` (penambahan fitur; major bump sesuai permintaan user)

## 1. Motivasi

v23.0.0 memperkenalkan editor absensi per-hari dari Heatmap (klik sel → sunting
jam masuk/keluar, tipe, turunan). Tapi editor itu **sengaja tidak menyentuh
`reason_category`** — alasan hanya bisa diisi lewat layar **Issues** (baris
`has_issue=1`) atau **Severe Lateness** (telat ≥ ambang). Akibatnya ada celah:

- Hari yang **bersih** (datang tepat waktu, punch masuk & keluar lengkap) lalu
  pegawai berangkat **dinas/paparan** — tidak bisa ditandai sama sekali, karena
  bukan issue dan bukan telat parah.
- Hari **telat ringan** (punch lengkap, telat > 0 tapi **di bawah** ambang
  Severe Lateness) dengan alasan kerja — juga tak terjangkau flow manapun.

Fitur ini membuka pengisian alasan langsung dari editor untuk menutup celah itu,
dan menambah **Rekap Dinas & Paparan** — rekapitulasi jumlah dinas/paparan per
pegawai (bulan terpilih) plus papan peringkat sepanjang periode.

## 2. Keputusan terkunci

| # | Keputusan | Nilai |
|---|-----------|-------|
| A1 | Lingkup alasan editor (hari apa pun) | Tugas Lapangan, Tugas Paparan, Tugas Belajar, Izin Sakit, Cuti |
| A2 | Alasan telat kontekstual | Muncul **hanya** saat baris terdeteksi telat (>0): "Masuk Terlambat dengan Alasan Pekerjaan" & "Terlambat dengan alasan" |
| A3 | Izin/Cuti pada hari ber-punch | Diizinkan, **tanpa** peringatan (menurunkan % kehadiran hari itu — diterima) |
| B1 | Definisi Dinas (rekap) | `tugas_lapangan` |
| B2 | Definisi Paparan (rekap) | `tugas_paparan` |
| B3 | Total | Dinas + Paparan (belajar TIDAK dihitung) |
| B4 | Penempatan | Menu baru **"Rekap Dinas"** di grup sidebar INSIGHT (setelah Heatmap) |
| B5 | Isi daftar (kedua panel) | Hanya pegawai dengan **≥1** dinas/paparan pada rentangnya |
| C1 | Panel kiri | Bulan terpilih (bulan aktif app) |
| C2 | Panel kanan | Papan peringkat; rentang bisa diatur |
| C3 | Rentang papan peringkat | **Default "Tahun ini" (Jan–Des tahun bulan terpilih)**; opsi **3 bln** & **6 bln** = mundur inklusif dari bulan terpilih |
| C4 | Cetak | Ada tombol Cetak PDF; isi **mengikuti rentang aktif** di layar (WYSIWYG) |
| D1 | Versi | `v24.0.0`, bundle penuh sesuai aturan proyek |

## 3. Bagian A — Edit alasan di `AttendanceEditDialog`

**File:** `src/ui/components/attendance_edit_dialog.py`

### 3.1 UI
Tambah seksi **"Alasan / Keterangan"** di bawah kotak "Dihitung Otomatis"
(sebelum override / footer):

- **OptionMenu alasan** dengan label dari `reason_mapper.REASON_LABELS`.
  Isi opsi bersifat **kontekstual**, dihitung ulang tiap `_recompute_preview()`:
  - Selalu: `— (tidak ada)`, Tugas Lapangan, Tugas Paparan, Tugas
    Belajar/Kuliah, Izin Sakit, Cuti.
  - Ditambahkan **hanya bila** `terlambat_menit > 0` pada hasil recompute:
    Masuk Terlambat dengan Alasan Pekerjaan (`terlambat_kerja`), Terlambat
    dengan alasan (`terlambat_lain`).
  - Bila kategori terpilih saat ini bukan bagian dari daftar kontekstual
    (mis. baris tadinya telat lalu jamnya dibetulkan jadi tidak telat), opsi
    itu tetap dipertahankan di daftar agar nilai lama tak hilang diam-diam.
- **Field detail** (teks bebas) muncul saat kategori ∈
  `reason_mapper.REASON_NEEDS_DETAIL` (`tugas_lapangan`, `tugas_paparan`,
  `terlambat_kerja`, `terlambat_lain`). Sembunyi untuk kategori lain.
- Nilai awal: pre-load `reason_category` / `reason_detail` dari baris existing.

### 3.2 Simpan / hapus alasan
Di `_save()`, setelah `save_manual_attendance(...)` (yang menstempel
`manual_edited_at` dan menyimpan punch/turunan seperti sekarang):

- Jika kategori terpilih = `— (tidak ada)` → panggil
  `unresolve_issue(conn, attendance_id=...)` (set `reason_category`,
  `reason_detail`, `resolved_at` = NULL).
- Selain itu → panggil `set_reason(conn, attendance_id=..., category=...,
  detail=...)` (stempel `resolved_at`).

Karena `save_manual_attendance` melakukan upsert lebih dulu, ambil
`attendance_id` via `get_attendance` setelah simpan (atau kembalikan id dari
`save_manual_attendance`). Alasan disimpan pada koneksi yang sama sebelum commit.

**Catatan ownership:** stempel `manual_edited_at` tetap dipasang (perilaku v23).
Bila hanya alasan yang berubah (punch sama), `import_conflicts.find_conflicts`
tidak akan memunculkan kartu konflik karena field yang dibanding tidak berbeda —
jadi tidak ada gangguan saat import ulang. `reason_category` selalu dipertahankan
oleh `upsert_attendance`, jadi tag alasan aman melewati import.

### 3.3 Non-goal Bagian A
- Tidak mengubah Issues / Severe Lateness (tetap jalur resolve masing-masing).
- Tidak mengubah `has_issue`: menandai hari bersih **tidak** menjadikannya issue.

## 4. Bagian B — Layar "Rekap Dinas"

### 4.1 Data layer
**File:** `src/db/attendance.py` (fungsi baru)

```
def count_dinas_paparan_by_employee(conn, start, end) -> list[dict]:
    # Untuk tiap employee dengan >=1 baris ber-reason dinas/paparan di [start,end]:
    #   {employee_id, nama, dept, dinas, paparan, total}
    # dinas   = COUNT reason_category = 'tugas_lapangan'
    # paparan = COUNT reason_category = 'tugas_paparan'
    # total   = dinas + paparan
    # HAVING total >= 1  (D2)
    # ORDER BY total DESC, dinas DESC, nama ASC
```

Satu fungsi melayani kedua panel (beda argumen rentang). Tanpa filter `tipe`
(hitung di mana pun alasan itu ditandai — sederhana, deterministik).

### 4.2 Core — resolusi rentang & peringkat (murni, teruji)
**File baru:** `src/core/dinas_recap.py`

```
def resolve_range(year_month, span) -> (start, end):
    # span in {"year","3m","6m"} — semua inklusif bulan terpilih.
    # "year" -> (YYYY-01-01, YYYY-12-31) dari tahun year_month
    # "3m"   -> awal bulan (m-2) .. akhir bulan (m)
    # "6m"   -> awal bulan (m-5) .. akhir bulan (m)  (lintas-tahun aman)

def rank(rows) -> list[dict]:
    # rows sudah terurut dari SQL; tambahkan field 'rank' 1..N (sekuensial).
    # Tie-break sudah ditangani ORDER BY (total, dinas, nama) → deterministik.
```

Label rentang untuk header/print (mis. "Ags 2025 – Jul 2026", "Jan – Des 2026")
memakai `week_utils.MONTH_NAMES_ID`.

### 4.3 Layar
**File baru:** `src/ui/screens/dinas_recap.py` — `DinasRecapScreen(parent)`
- Didaftarkan di `src/ui/app.py`:
  - `nav_groups` INSIGHT: tambah `("▤", "Rekap Dinas", "DinasRecap")` setelah Heatmap.
  - `_create_screen`: cabang `"DinasRecap"` → `DinasRecapScreen`.
- Digerakkan **bulan aktif** app (`get_setting(conn, "current_month")`), seperti
  Dashboard/Heatmap. `on_show()` membaca ulang bulan aktif + rentang aktif,
  merender ulang tanpa membangun ulang chrome.
- **Panel kiri "Bulan Terpilih":** tabel Nama · Dept · Dinas · Paparan · Total
  + baris grand total. Sumber: `count_dinas_paparan_by_employee(month_start, month_end)`.
- **Panel kanan "Papan Peringkat":**
  - Segmented control rentang: `[3 bln] [6 bln] [Tahun ini]`, default **Tahun ini**.
    Simpan pilihan di state layar (bertahan lewat `on_show`). Label rentang aktif
    ditampilkan (mis. "Jan – Des 2026").
  - Baris peringkat (desain final, lihat §4.4). Sumber:
    `count_dinas_paparan_by_employee(*resolve_range(month, span))`.
  - Tombol **Cetak** magenta di header kanan.
- Kerja baca via `tasks.run_bg` bila perlu (konsisten v22 non-blocking); data
  ringan, boleh sinkron bila cepat.

### 4.4 Desain baris papan peringkat (terkunci via mockup)
- **Garis aksen kiri** 3px berwarna magenta yang **memudar tiap turun peringkat**
  (#1 `#EC4899` → makin pudar). (Pilihan eksplisit user; abaikan hook "side-tab".)
- **Angka peringkat** magenta memudar (#1 `#EC4899`, #2 `#F472B6`, #3 `#F9A8D4`,
  sisanya abu `#737373`).
- **Penanda nama:** #1 = 👑, #2 & #3 = 💎.
- **Bar bertumpuk:** panjang ∝ total relatif ke pemuncak; isi = teal Dinas
  (`#0D9488`) + ungu Paparan (`#A855F7`).
- **Kolom angka sejajar** kanan: Din (teal) · Pap (ungu) · Total (putih tebal),
  mono `tabular-nums`.

### 4.5 Cetak
**File baru:** `src/reports/dinas_recap_print.py` + template
`src/reports/templates/dinas_recap_print.html` (Jinja2), mengikuti pola
`heatmap_print` / `html_renderer` + `browser_launcher`.
- A4 **potret**, WYSIWYG terhadap rentang aktif (C4).
- Muatan: kop beraksen (label + judul + chip periode + garis magenta/teal/ungu),
  strip ringkasan (Total Dinas, Total Paparan, kartu Juara), tabel Bulan
  Terpilih (+total), papan peringkat dengan bar komposisi + 👑/💎, blok tanda
  tangan **"HR Officer in Charge"**, tip cetak (aktifkan Background graphics,
  matikan Headers/footers).
- Bila pegawai banyak, biarkan mengalir multi-halaman (page-break natural).

## 5. Analisis interaksi (terverifikasi di kode)

- **% kehadiran tetap** saat hari bersih ditandai Dinas/Paparan: status `dinas`
  ada di `heatmap.HK_STATUSES`, jadi tetap masuk `hk` (pembilang % hadir).
- **"Tepat waktu" (H) berkurang 1** untuk hari on-time yang ditandai
  Dinas/Paparan (status pindah `hadir` → `dinas`). Diterima.
- **`izin_sakit`/`cuti` pada hari ber-punch** → status `sakit`/`cuti` (di luar
  `HK_STATUSES`) → **% kehadiran hari itu turun**. Diterima tanpa peringatan (A3).
- **Telat ringan dialasani** (`terlambat_kerja`/`terlambat_lain`) → masuk
  `COACHING_EXCLUDED` → `reason_mapper.effective_attendance` menolkan telat →
  hilang dari Top-5 telat & kandidat coaching (efek surut, sama seperti Severe
  Lateness). Diterima.
- **Export Laporan Bulanan** (`report_filler.fill_monthly_report`) sudah mengisi
  Alasan Ijin untuk **tiap** baris ber-`reason_category` (tak peduli `has_issue`)
  → hari bersih bertag paparan otomatis muncul. **Tanpa perubahan kode export.**
- **Kolom "D" Heatmap** tetap gabungan semua `HEATMAP_DINAS_REASONS`; Rekap
  adalah pemecahan resmi Dinas vs Paparan. Heatmap tak diubah.

## 6. Pengujian (TDD)

**Core (`tests/`):**
- `dinas_recap.resolve_range` untuk year/3m/6m termasuk kasus lintas-tahun
  (mis. bulan Feb → 6 bln menembus tahun sebelumnya) & Januari.
- `rank` penomoran + determinisme tie-break.

**DB:**
- `count_dinas_paparan_by_employee`: hitung dinas/paparan benar, `HAVING total>=1`
  menyembunyikan pegawai nol, urutan `total,dinas,nama`, batas tanggal inklusif.

**Editor:**
- Opsi alasan kontekstual: alasan telat muncul hanya saat `terlambat_menit>0`.
- Field detail muncul/sembunyi sesuai `REASON_NEEDS_DETAIL`.
- Simpan alasan → `set_reason` terpanggil (resolved_at terisi); pilih
  "— (tidak ada)" pada baris ber-alasan → `unresolve_issue` (fields NULL).
- Preload nilai existing.

**Screen:**
- Render dua panel; hanya pegawai ≥1 tampil; grand total benar.
- Ganti segmented rentang → data papan peringkat berubah sesuai `resolve_range`.
- Builder cetak menghasilkan HTML memuat kedua seksi + tanda tangan.

**Rilis:**
- `tests/test_changelog_v24_0_0.py`: `APP_VERSION == "24.0.0"`, entri changelog
  teratas memuat "edit alasan"/"rekap"/"dinas"/"paparan".
- `tests/test_changelog_v23_0_0.py` dikonversi ke gaya retensi (entri v23.0.0
  tetap ada tapi bukan lagi teratas).

## 7. Rilis (aturan proyek)

`v24.0.0`: bump `APP_VERSION` + `APP_BUILD_DATE`, prepend `APP_CHANGELOG`
(3 poin: edit alasan dari Heatmap, Rekap Dinas & Paparan + papan peringkat,
cetak rekap). Suite hijau → build installer → rotasi produksi 2-level (DB
`data/` tak dipindah, md5-verify) → copy ke `Installers/HR-Absensi-Setup-v24.0.0.exe`
→ smoke → push `v24.0.0` + advance `latest` (**hanya dengan otorisasi eksplisit**).

## 8. Non-goals

- Tidak mengubah logika/warna Heatmap (kolom "D" tetap gabungan).
- Tidak mengubah export.
- Tidak menambah kategori alasan baru di `config.REASON_CATEGORIES`.
- Tidak menyentuh Issues / Severe Lateness.
- Tidak ada rentang kustom (date-picker) — hanya 3 bln / 6 bln / Tahun ini.
```
