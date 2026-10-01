# v26.0.0 — Jam Kantor Berjadwal + Lembur dengan Verifikasi

**Status:** Design locked (brainstorming 2026-10-01)
**Fork dari:** `v25.0.0`
**Target versi:** `v26.0.0`

## 1. Motivasi

Dua perubahan nyata di perusahaan memaksa dua pekerjaan yang saling terkait:

1. **Jam kantor berubah dari 08.00–16.00 menjadi 09.00–17.00, dengan cutoff
   14 September 2026.** Aplikasi saat ini hanya punya satu setelan global
   (`schedule_start`/`schedule_end` di tabel `settings`). Mengubahnya akan
   mengubah hitungan bulan-bulan lama juga — padahal Juli–Agustus tetap harus
   dihitung dengan aturan lama. Diperlukan **jadwal yang berlaku per tanggal**.
2. **Lembur selama ini tidak punya alur.** Kolom `lembur_jam` yang tersimpan
   hanyalah angka dari file fingerprint (atau turunan kaku `keluar − jam
   pulang` di dialog edit), tanpa daftar siapa/kapan, tanpa keputusan
   diterima/tidak. Pemilik perusahaan butuh melihat **siapa lembur, tanggal
   berapa, berapa jam**, lalu memutuskan — dan keputusan itu tercatat.

Sekaligus ditemukan utang teknis yang harus dibayar agar jadwal historis benar:
jam masuk 08.00 masih **hardcoded** di beberapa tempat (band "Pola Jam Masuk"
di `src/core/insights.py`, pembatas cetak di
`src/reports/templates/dashboard.html.j2`, jam pulang 16.00 di
`src/core/report_generator.py:30`). Semua titik ini harus ikut jadwal per
tanggal, bukan konstanta.

## 2. Keputusan terkunci

| # | Keputusan | Nilai |
|---|---|---|
| D1 | Periode daftar lembur | Mengikuti Bulan Aktif global (banner yang sama dengan Dashboard/Heatmap) |
| D2 | Pemicu hari kerja | `keluar > ambang lembur` (default 18.00, dapat diubah); durasi = `keluar − jam pulang kantor tanggal itu` |
| D3 | Hari libur/akhir pekan | Cukup masuk & keluar terisi; durasi penuh = `keluar − masuk`, tanpa ambang |
| D4 | Alur status | Open → Diajukan → Diterima / Tidak Diterima; bertahap; keputusan final bisa dikoreksi dengan konfirmasi |
| D5 | Aksi | Per baris + massal (centang banyak baris) |
| D6 | Jam disetujui | Saat Diterima otomatis = jam terdeteksi, bisa diubah (persetujuan sebagian; 0..terdeteksi) |
| D7 | Model data | Deteksi dihitung ulang saat baca; keputusan disimpan di tabel terpisah + snapshot `detected_minutes` |
| D8 | Sumber angka | Dihitung dari jam masuk/keluar absensi; kolom "Lembur" file fingerprint **tidak** dipakai |
| D9 | Jadwal kantor | Berbasis tanggal (`schedule_periods`); migrasi otomatis khusus nilai default lama; nilai custom dipertahankan |
| D10 | Ambang lembur | Setting global baru `overtime_threshold` (default `18.00`); validasi harus setelah jam pulang berjalan |
| D11 | UI | Menu "Lembur" di grup WORKFLOW; badge belum final di sidebar + kartu KPI Dashboard (bulan aktif) |
| D12 | Cetak | Dialog pilihan: semua status (rekap) atau hanya Diterima (pembayaran) |
| D13 | Laporan Bulanan Excel | Kolom Lembur **dibiarkan seperti sekarang** (angka fingerprint); tidak diubah |
| D14 | Ekspor CSV lembur | Tidak termasuk rilis ini |
| D15 | Catatan | Catatan bebas per baris, tampil di detail & cetakan |

### Alasan D9 — kenapa berbasis tanggal, bukan global

Cutoff 14 Sep 2026 membelah data dalam satu database. Dengan setelan global,
mengubah ke 09.00–17.00 akan membuat keterlambatan Juli–Agustus dihitung dari
09.00 (salah), dan lembur Agustus dihitung dari 17.00 (salah). Tabel
`schedule_periods` menyelesaikannya secara struktural: setiap tanggal
mengambil periode terakhir yang `effective_from <= tanggal`.

### Alasan D8 — kenapa bukan kolom fingerprint

Kolom "Lembur" mesin fingerprint tidak selalu ada, dan bila ada pun tidak
mengikuti kebijakan ambang/jam kantor aplikasi. Karena keputusan pemilik harus
bisa ditelusuri ke jam absensi nyata, angka dihitung dari `masuk`/`keluar`.
Kolom fingerprint tetap tersimpan di `attendance_records.lembur_jam` dan tetap
tampil di Laporan Bulanan (D13) — hanya tidak dipakai fitur ini.

## 3. Aturan deteksi

Semua waktu diparse dengan `to_minutes()` yang sudah ada
(`src/core/attendance_calc.py:16`). Resolusi jadwal: periode terakhir dengan
`effective_from <= tanggal`; jika tidak ada yang cocok, fallback ke default
aplikasi (09.00–17.00).

**Hari kerja efektif** = bukan Sabtu/Minggu (cek weekday tanggal, helper
weekend yang sudah dipakai `src/core/heatmap.py:55`), bukan tanggal di tabel
`holidays`, dan `tipe != 'Hari Libur'`.

```
hari_kerja:
    syarat   : masuk & keluar terisi, keluar > max(ambang, jam_pulang)
    durasi   : keluar − jam_pulang          (menit, > 0)

hari_libur:
    syarat   : masuk & keluar terisi
    durasi   : keluar − masuk               (menit, > 0)
```

- Ambang default `18.00`; jam pulang berlaku 17.00 (mulai 14 Sep 2026) dan
  16.00 (sebelumnya).
- Contoh: pulang 19.30 pada hari kerja → **150 menit (2j 30m)**.
- Contoh: Minggu 09.00–14.00 → **300 menit (5j)**.
- Baris dengan salah satu jam kosong (mis. lupa absen pulang) → tidak muncul.
- Alasan issue (Dinas/Paparan/Izin/Sakit/Cuti) **tidak** mengubah deteksi.
- Karyawan yang di-exclude Outlier **tetap** tampil — lembur adalah fakta
  kehadiran, bukan statistik yang boleh disembunyikan.
- Durasi internal dalam **menit**; tampilan memakai helper
  `format_duration(min) -> "2j 30m"`; total bulanan `"12j 30m"`.

## 4. Arsitektur

### 4.1 Skema database baru

```sql
CREATE TABLE IF NOT EXISTS schedule_periods (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    effective_from TEXT NOT NULL UNIQUE,   -- YYYY-MM-DD, '1970-01-01' = sejak awal
    start_time     TEXT NOT NULL,          -- '09.00' (format setting lama)
    end_time       TEXT NOT NULL,          -- '17.00'
    created_at     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS overtime_decisions (
    employee_id   INTEGER NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
    tanggal       TEXT    NOT NULL,
    status        TEXT    NOT NULL,        -- open|diajukan|diterima|tidak_diterima
    approved_minutes          INTEGER,     -- terisi saat diterima
    detected_minutes_at_decision INTEGER,  -- snapshot audit saat aksi verifikasi
    note          TEXT,
    submitted_at  TEXT,
    decided_at    TEXT,
    updated_at    TEXT NOT NULL,
    PRIMARY KEY (employee_id, tanggal)
);
```

- Baris **Open tidak disimpan** — cukup ketiadaan baris di `overtime_decisions`.
  Baris muncul begitu diaksi (Diajukan/Diterima/Tidak Diterima). Koreksi
  (D4) mengizinkan perpindahan ke status mana pun, termasuk kembali ke
  `open`/`diajukan`, selalu lewat konfirmasi; saat kembali ke `open` baris
  `overtime_decisions` dihapus.
- `detected_minutes_at_decision` memungkinkan penanda **"data berubah"**
  (§6) tanpa membekukan data absensi.
- Riwayat lengkap per perubahan status **tidak** disimpan di v26 (hanya status
  terakhir + timestamp); dicatat sebagai batas lingkup.

### 4.2 Migrasi (idempoten)

Di `init_db` (`src/db/schema.py`): seeding `DEFAULT_SETTINGS` dipindah
**sebelum** `_migrate()` agar migrasi bisa membaca nilai yang ada. Di
`_migrate()`, jika `schedule_periods` kosong:

| Kondisi `schedule_start/end` tersimpan | Periode yang dibuat |
|---|---|
| `08.00` / `16.00` (default lama) | `1970-01-01` → 08.00–16.00, lalu `2026-09-14` → 09.00–17.00 |
| `09.00` / `17.00` (instalasi baru v26) | `1970-01-01` → 09.00–17.00 |
| nilai custom lain | satu periode `1970-01-01` dengan nilai custom (dipertahankan; user dapat menambah perubahan jadwal sendiri dari Settings) |

- `DEFAULT_SETTINGS['schedule_start'/'schedule_end']`, `DEFAULT_SCHEDULE_START/END`
  di `src/config.py`, dan fallback di UI berubah ke `09.00`/`17.00`.
- Setting baru `overtime_threshold` default `18.00` ikut di-seed.
- Setting lama `schedule_start/end` **tetap ada** sebagai cermin jadwal
  berjalan (ditulis ulang setiap periode baru ditambahkan) agar pembaca lama
  tidak pecah selama transisi.
- Keterbatasan yang disadari: database yang jam kantornya pernah diubah manual
  sebelum v26 tidak punya riwayat — hanya nilai terakhirnya yang bisa
  dipertahankan.

### 4.3 Modul baru

| Modul | Isi |
|---|---|
| `src/core/schedule.py` | `periods()`, `schedule_for(date) -> (start_min, end_min)`, `current_schedule()`, `add_period(effective_from, start, end)`, validasi |
| `src/core/overtime.py` | mesin deteksi murni: `detect(row, schedule, threshold_min, is_nonworkday) -> int | None`, `month_rows()`, `summarize()`, `format_duration()` |
| `src/db/schedule.py` | CRUD `schedule_periods` + mirror ke settings |
| `src/db/overtime.py` | CRUD `overtime_decisions`, hitung badge (Open + Diajukan, bulan aktif) |
| `src/ui/screens/overtime.py` | layar "Lembur"; pola layar v22 (cache `on_show`, `run_bg` + `BusyGuard`, debounce, toast/flash, token motion v25) |
| `src/reports/templates/overtime.html.j2` | template cetak A4 (kop, tabel, ringkasan, tanda tangan) |

### 4.4 Titik yang harus ikut jadwal per tanggal

Semua pembaca `get_setting("schedule_start"/"schedule_end")` diganti resolver
`schedule_for(tanggal)`:

- `src/ui/components/attendance_edit_dialog.py:84` — dialog Edit Data.
- `src/core/weekly_export.py:56` + `src/core/reason_mapper.py` — mapping
  Lupa Absen per baris.
- `src/core/report_generator.py:271` + `JADWAL_END_MINUTES = 16 * 60`
  (baris 30) — pulang cepat per tanggal.
- `src/core/insights.py` — `_POLA_JAM_BANDS`/`_classify_jam_masuk` menjadi
  fungsi `bands_for(start_min)` dan klasifikasi relatif jam masuk tanggal itu
  (band tetap 8, label bergeser; mis. `<08:45`, `08:45-08:59`, `09:00`,
  `09:01-09:05`, `09:06-09:15`, `09:16-09:30`, `09:31-10:00`, `>10:00`).
- `src/reports/templates/dashboard.html.j2:204` — pembatas "ambang tepat
  waktu" memakai label jam masuk berjalan, bukan literal `'08:00'`.

Catatan penting: `terlambat_menit` yang **tersimpan dari file fingerprint**
tidak dihitung ulang otomatis di v26 (otoritas mesin fingerprint). Hanya baris
yang diedit manual dari Heatmap yang dihitung ulang memakai jadwal tanggalnya.
Ini menjaga angka lama tetap sama persis, sesuai D13.

### 4.5 Settings

- Bagian baru **"Jam Kantor"**: menampilkan jadwal berjalan + riwayat periode
  (berlaku mulai, jam masuk, jam pulang). Tombol "Tambah perubahan jadwal…"
  membuka dialog (tanggal berlaku, jam masuk, jam pulang).
  Validasi: `mulai < pulang`; tanggal berlaku unik; tanggal **minimal hari
  ini** (tidak boleh memutarbalikkan masa lalu; koreksi migrasi hanya lewat
  migrasi).
  Entri dengan `effective_from > hari ini` boleh dihapus; entri yang sudah
  berlaku terkunci.
- Field **"Ambang Lembur"** (default `18.00`, format `HH.MM`); validasi harus
  setelah jam pulang jadwal berjalan; bila tidak valid, simpan ditolak dengan
  pesan.
- Field lama Jam Masuk/Jam Pulang di Settings digantikan bagian ini.

## 5. Layar Lembur

- **Navigasi**: grup WORKFLOW, setelah "Severe Lateness"; key layar
  `Overtime`, label "Lembur", ikon baru di `src/ui/icons.py` (glyph, fallback
  aman); badge angka belum final.
- **Header**: judul, ActiveMonthBanner, search nama (debounce 200 ms seperti
  layar lain), tombol Cetak (magenta), tab status: Semua / Open / Diajukan /
  Diterima / Tidak Diterima dengan jumlah per tab.
- **KPI row**: Orang lembur, Total jam terdeteksi, Total jam disetujui,
  Belum diproses (Open + Diajukan).
- **Tabel utama**: Tanggal, Nama, Dept, Masuk, Keluar, Jam Lembur, Jam
  Disetujui, Status, Catatan. Sort per kolom; default kronologis.
- **Panel ringkasan per karyawan** (bisa diciutkan): total hari, total jam
  terdeteksi, total jam disetujui; sort jumlah jam.
- **Aksi massal**: checkbox per baris; bar aksi muncul saat ada yang dicentang
  → Ajukan / Terima / Tolak / Bersihkan. Aturan kelayakan: **Ajukan** hanya
  untuk baris Open; **Terima/Tolak** hanya untuk baris Diajukan (langsung
  Open → final tidak diizinkan, sesuai D4). Baris lain dilewati dan jumlahnya
  dilaporkan (mis. "3 baris dilewati karena belum Diajukan").
- **Dialog detail** (klik baris): identitas, jam masuk/keluar, jam terdeteksi,
  linimasa status + timestamp, jam disetujui (aktif saat Diterima; input jam &
  menit, default = terdeteksi), catatan, tombol aksi, penanda **"data
  berubah"** bila `detected` sekarang ≠ snapshot.
- **Badge**: item sidebar + kartu KPI baru di Dashboard "Lembur belum
  diproses" (Open + Diajukan bulan aktif); klik kartu → layar Lembur.
- **Feedback**: dialog gelap + toast; baris berkilat setelah aksi (pola v25,
  tunduk pada sakelar Animasi); Ctrl+F cari, Esc tutup dialog.
- **Empty state** per tab.

## 6. Cetak/PDF

- Dialog pilihan sebelum cetak: **Semua status** (rekap lengkap) atau **Hanya
  Diterima** (untuk pembayaran).
- Lembar A4 mengikuti pola cetak yang ada: kop perusahaan, periode, tabel
  kronologis, ringkasan + subtotal per karyawan (kolom Jam vs Jam Disetujui;
  mode Diterima memakai jam disetujui), blok tanda tangan HR, pengingat
  mematikan headers/footers browser.
- Dirender lewat Jinja2 + dibuka di browser, sama seperti cetak Dashboard/
  Heatmap.

## 7. Kasus tepi

| Kasus | Perilaku |
|---|---|
| Salah satu jam kosong | Tidak muncul; perbaiki dulu dari Heatmap |
| Data absensi berubah setelah keputusan | Deteksi ter-update; baris diberi penanda "data berubah"; snapshot keputusan tetap tersimpan |
| Tanggal yang kemudian ditandai Hari Libur | Deteksi berpindah ke aturan libur (durasi penuh); penanda "data berubah" muncul bila berbeda dari snapshot |
| Baris ber-keputusan tidak lagi memenuhi syarat | Tetap tampil di tab statusnya dengan penanda "tidak lagi memenuhi syarat"; jam disetujui tersimpan |
| Aksi massal pada baris tidak sah | Dilewati, dilaporkan jumlahnya |
| Ambang ≤ jam pulang | Ditolak saat simpan dengan pesan jelas |
| Karyawan dihapus | Keputusan ikut terhapus (FK cascade) |
| Durasi ≤ 0 (data aneh) | Dianggap tidak ada lembur |

## 8. Strategi uji

1. **Mesin deteksi (murni)**: hari kerja di atas ambang; keluar di antara jam
   pulang dan ambang (tidak muncul); hari libur tanpa ambang; durasi penuh;
   Sabtu/Minggu; `tipe='Hari Libur'`; jam kosong; durasi ≤ 0.
2. **Resolusi jadwal**: sebelum/sesudah 14 Sep 2026; periode custom; tanggal
   tepat di `effective_from`; fallback default.
3. **Migrasi**: DB dengan default lama → dua periode; DB custom → satu periode
   dipertahankan; idempoten (dijalankan dua kali tidak menggandakan); jumlah
   `terlambat_menit` lama tidak berubah setelah migrasi.
4. **Keputusan & audit**: transisi sah/tidak sah; koreksi final; persetujuan
   sebagian (0..terdeteksi); snapshot & penanda "data berubah"; badge Open +
   Diajukan.
5. **Cetak**: render template dua mode; baris tanpa keputusan tidak muncul di
   mode Diterima.
6. **Regresi**: audit tes lama yang mengandalkan default `08.00`/`16.00` —
   fixture harus menyemai periode eksplisit. Suite penuh wajib hijau.
7. **Smoke aplikasi**: buka layar Lembur dengan data realistis (ada hari
   kerja & hari libur), lakukan satu verifikasi, satu cetak.

## 9. Batas lingkup

Tidak termasuk rilis ini:

- Ekspor CSV lembur (D14), notifikasi WhatsApp ke karyawan.
- Aturan setengah hari untuk kerja di hari libur.
- Ambang lembur per-periode jadwal (v26: satu ambang global).
- Penambahan baris lembur manual tanpa data absensi.
- Perubahan kolom Lembur di Laporan Bulanan Excel (D13).
- Riwayat audit lengkap tiap perubahan status (hanya status terakhir +
  timestamp).
- Perubahan perilaku `terlambat_menit` fingerprint yang sudah tersimpan.

## 10. Protokol rilis

Mengikuti CLAUDE.md §1–§2 tanpa pengecualian:

1. Implementasi + commit + `pytest` penuh hijau
2. `python -m tools.build_installer`
3. Rotasi produksi `.exe` 2 level (`data/` tidak pernah ikut dipindah)
4. Salin ke `Installers/HR-Absensi-Setup-v26.0.0.exe`
5. Smoke manual dengan data realistis (termasuk satu tanggal sebelum dan
   sesudah 14 Sep 2026)
6. Entri `APP_CHANGELOG` `26.0.0` di `src/config.py` + bump `APP_VERSION`/
   `APP_BUILD_DATE`
7. Push hanya setelah otorisasi eksplisit user, lalu majukan `latest`
8. Perbarui `memory/version_state.md`
