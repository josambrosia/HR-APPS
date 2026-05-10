# HR Absensi App — Design Spec

**Tanggal:** 2026-05-11
**Status:** Draft (menunggu approval user)
**Author:** Brainstorming session

---

## 1. Latar Belakang & Problem

User adalah HR yang setiap bulan harus menyerahkan **Laporan Bulanan Absensi** ke atasan, dengan kolom **Alasan Ijin** (kolom Q) terisi lengkap untuk setiap issue absensi pegawai sepanjang bulan.

**Workflow saat ini (manual, melelahkan):**
1. Tarik file fingerprint per minggu (`.xls`) dari mesin absensi
2. Sisir manual baris per baris untuk menemukan issue (kolom Masuk/Keluar kosong)
3. Catat manual: nama pegawai + tanggal issue
4. Konfirmasi via WhatsApp ke pegawai satu per satu
5. Setelah dapat alasan, input manual ke file `Laporan Bulanan.xlsx`

**Pain points:**
- Repetitive scanning baris fingerprint untuk cari issue
- Pencatatan ganda (cari issue, lalu catat lagi untuk WA)
- Input manual ke laporan bulanan = banyak waktu, rentan typo

**Yang dibutuhkan:** Aplikasi Windows desktop yang otomatis deteksi issue, bantu generate template WA, dan otomatis isi kolom Alasan Ijin di laporan bulanan.

---

## 2. Goals & Non-Goals

### Goals
- Mendeteksi issue absensi otomatis dari file fingerprint mingguan
- Menyimpan state issue + alasan sepanjang 1 bulan
- Generate **list issue per pegawai** (hari + tanggal) yang siap copy → user racik kalimat sendiri di WA (personal touch)
- Mengisi kolom Alasan Ijin di file Laporan Bulanan dengan 1 klik
- **Dashboard Insights** mingguan/bulanan: ranking terlambat, top 5, coaching flag (>75 mnt/minggu), karyawan teladan
- Cetak dashboard ke PDF (via HTML → browser print)
- Single-user, offline, portable (zero install)

### Non-Goals (sengaja TIDAK dilakukan)
- Tidak ada integrasi WhatsApp otomatis (cuma copy list issue, bukan draft kalimat lengkap)
- Tidak ada deteksi terlambat / pulang cepat **sebagai issue yang butuh konfirmasi** (terlambat tetap dilacak untuk dashboard, tapi tidak block alur kerja)
- Tidak ada analitik history lintas bulan (per-bulan independen, dashboard hanya di bulan berjalan)
- Tidak ada multi-user / cloud / login
- Tidak ada notifikasi otomatis / scheduling
- Tidak ada deteksi anomali statistik di luar yang ditentukan (counter SELVI 163 absen, dll — anggap input data benar)

---

## 3. Tech Stack

| Aspek | Pilihan |
|---|---|
| Bahasa | **Python 3.12** |
| GUI Framework | **customtkinter** (modern, light, native-feel) |
| Excel reader (.xls lama) | **xlrd 2.0.1** (handle OLE2 quirks) |
| Excel reader/writer (.xlsx) | **openpyxl** (preserve formatting saat update) |
| Data manipulation | **pandas** |
| Database | **SQLite 3** (bawaan Python) |
| Clipboard | **pyperclip** |
| HTML report (dashboard) | **Jinja2** (template) + `webbrowser` (bawaan Python) |
| Build tool | **PyInstaller** (`--onedir`) |
| Testing | **pytest** (minimal, hanya core logic) |

**Estimasi ukuran .exe:** ~40 MB · **RAM idle:** ~80 MB · **Start time:** 1-2 detik

---

## 4. Arsitektur

```
┌────────────────────────────────────────────────────────────────────┐
│  GUI LAYER  (customtkinter)                                        │
│  Dashboard · Import · Issues · Summary · Insights · Export · Set.  │
└──────────────────────────┬─────────────────────────────────────────┘
                           │
┌──────────────────────────▼─────────────────────────────────────────┐
│  BUSINESS LOGIC                                                    │
│  IssueDetector · IssueSummary · ReportFiller · InsightsEngine      │
└──────────────────────────┬─────────────────────────────────────────┘
                           │
       ┌─────────┬─────────┼─────────┬──────────────┐
       ▼         ▼         ▼         ▼              ▼
   ┌────────┐ ┌─────────┐ ┌────────┐ ┌──────────┐ ┌──────────────┐
   │ SQLite │ │ pandas  │ │openpyxl│ │ Jinja2 + │ │  pyperclip   │
   │ hr.db  │ │ + xlrd  │ │ (.xlsx)│ │webbrowser│ │  (clipboard) │
   │        │ │ (.xls)  │ │        │ │ (HTML)   │ │              │
   └────────┘ └─────────┘ └────────┘ └──────────┘ └──────────────┘
```

### Tata letak file di disk

```
HR-Absensi-App/
├── HR-Absensi.exe          ← single executable
├── _internal/              ← libraries bundled by PyInstaller
├── icon.ico
├── data/
│   └── hr.db               ← SQLite, data bulan berjalan
├── templates/
│   └── dashboard.html.j2   ← Jinja2 template untuk laporan PDF
└── README.txt
```

User boleh taruh folder ini di mana saja (Documents, flashdisk, dll).

---

## 5. Data Model (SQLite)

### Tabel `employees`
```sql
CREATE TABLE employees (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    no_staff  TEXT    UNIQUE NOT NULL,
    nama      TEXT    NOT NULL,
    dept      TEXT,
    phone     TEXT,
    active    INTEGER DEFAULT 1
);
```

### Tabel `attendance_records`
```sql
CREATE TABLE attendance_records (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id     INTEGER NOT NULL REFERENCES employees(id),
    tanggal         DATE    NOT NULL,
    hari            TEXT,
    tipe            TEXT,                    -- "Hari Kerja" | "Istirahat"
    jadwal          TEXT,                    -- "08.00 - 16.00"
    masuk           TEXT,                    -- "08.06" atau NULL
    keluar          TEXT,                    -- NULL kalau lupa absen
    kerja_jam       REAL,
    lembur_jam      REAL,
    terlambat_menit INTEGER,
    -- workflow state (diisi user)
    has_issue       INTEGER DEFAULT 0,       -- auto: 1 jika issue
    reason_category TEXT,                    -- enum 8 kategori
    reason_detail   TEXT,                    -- lokasi/alasan tambahan
    resolved_at     DATETIME,
    -- audit
    imported_from   TEXT,                    -- "Fingerprint W2.xls"
    imported_at     DATETIME,
    UNIQUE (employee_id, tanggal)
);
```

### Tabel `settings`
```sql
CREATE TABLE settings (
    key   TEXT PRIMARY KEY,
    value TEXT
);
-- contoh isi:
-- ('schedule_start',  '08.00')
-- ('schedule_end',    '16.00')
-- ('current_month',   '2026-04')
-- ('wa_template',     'Halo {nama}, mohon konfirmasi alasan absensi {daftar_issue}. Terima kasih.')
```

### Aturan
- `UNIQUE(employee_id, tanggal)` mencegah duplikasi saat re-impor
- `has_issue` dihitung di code saat insert (bukan trigger), dari rule `tipe='Hari Kerja' AND (masuk IS NULL OR keluar IS NULL)`
- Saat re-impor: pakai SQL upsert eksplisit yang **mempertahankan** `reason_category`, `reason_detail`, `resolved_at`:
  ```sql
  INSERT INTO attendance_records (...) VALUES (...)
  ON CONFLICT (employee_id, tanggal) DO UPDATE SET
    masuk = excluded.masuk,
    keluar = excluded.keluar,
    kerja_jam = excluded.kerja_jam,
    has_issue = excluded.has_issue,
    imported_from = excluded.imported_from,
    imported_at = excluded.imported_at;
    -- reason_category & reason_detail TIDAK ada di SET → preserved
  ```
- "Mulai Bulan Baru" = `DELETE FROM attendance_records` (employees & settings tetap)

---

## 6. Mapping Kategori Alasan

8 kategori pilihan + format output ke kolom Alasan Ijin + flag untuk dashboard:

| `reason_category` | Detail dipakai? | Output ke Excel | Hitung di coaching counter? |
|---|---|---|---|
| `tugas_lapangan` | Ya (lokasi) | `Tugas Lapangan di {detail}` | **TIDAK** (work-justified) |
| `tugas_paparan` | Ya (lokasi) | `Tugas Paparan di {detail}` | **TIDAK** (work-justified) |
| `izin_sakit` | Tidak | `Izin Sakit` | TIDAK (absent, no terlambat data) |
| `cuti` | Tidak | `Cuti` | TIDAK (absent, no terlambat data) |
| `terlambat_kerja` | Ya (alasan) | `Masuk Terlambat dengan Alasan Pekerjaan: {detail}` | **TIDAK** (work-justified) |
| `terlambat_lain` | Ya (alasan) | `Terlambat dengan alasan: {detail}` | YA |
| `lupa_absen` | Tidak | `Lupa Absen` | YA (kalau ada terlambat_menit) |
| `na` | Tidak | `NA / Belum ada kabar` | YA (default, belum dikonfirmasi) |

**Aturan coaching counter:** `terlambat_menit` dijumlahkan per pegawai per minggu, **kecuali** baris dengan `reason_category IN ('tugas_lapangan', 'tugas_paparan', 'terlambat_kerja')` — di-exclude karena dianggap valid/sah.

---

## 7. Screens & User Flow

### User flow 1 bulan kerja
```
[Mulai bulan] → Dashboard → loop tiap minggu (Import → Issues → WA Template → tunggu balasan → input alasan)
                                                    ↓
                                              [akhir bulan]
                                                    ↓
                                       Export Laporan Bulanan → kirim ke atasan
                                                    ↓
                                          [Mulai Bulan Baru] (reset)
```

### Screen 1 — Dashboard (home)
- Header: bulan aktif (e.g., "April 2026")
- Counter card: Open issues / Resolved issues / NA
- Last import: nama file + tanggal impor
- Progress bar: % resolved
- Tombol shortcut: [Import] [Lihat Issues] [Export]

### Screen 2 — Import Fingerprint
- Drop zone (drag-drop file `.xls`) + tombol Browse
- Setelah file dipilih → preview parsing:
  - Jumlah pegawai terdeteksi
  - Range tanggal
  - Jumlah issue baru (yang belum ada di DB)
  - Pegawai baru (belum ada di tabel `employees`) → opsi auto-add
- Tombol [Konfirmasi Impor] / [Batal]

### Screen 3 — Issues (screen inti)
- Top filter: Tab `Open (N)` / `All` / `Resolved`, dropdown filter pegawai/dept
- Tabel: Tanggal · Hari · Pegawai · Dept · Issue Type · Status
- Klik baris → panel kanan terbuka:
  - Detail issue (Masuk/Keluar/Jadwal)
  - Dropdown 8 kategori
  - Field detail (muncul kondisional sesuai kategori)
  - Tombol [Simpan] [Generate WA Template]
- Bulk action: pilih multiple → set kategori sekaligus (untuk Cuti masal misalnya)

### Screen 4 — Issue Summary per Pegawai (untuk WA)
- Sidebar: daftar pegawai yang punya issue terbuka (dengan badge count)
- Click pegawai → render list minimalis (bukan draft kalimat):
  ```
  ANDIKA (3 issue)
  - Kamis, 9 April 2026 (lupa absen pulang)
  - Jumat, 10 April 2026 (tidak masuk)
  - Senin, 13 April 2026 (lupa absen pulang)
  ```
- Tombol [📋 Copy ke Clipboard]
- User paste ke WA, lalu **ketik prefix kalimat sendiri** (personal touch — tidak rigid/kaku)
- Catatan: sengaja TIDAK auto-generate kalimat lengkap, sesuai preferensi user untuk komunikasi yang lebih personal

### Screen 5 — Export Laporan Bulanan
- Pilih file `.xlsx` (Laporan Bulanan dari atasan)
- Preview matching:
  - X baris match (alasan tersedia)
  - Y baris akan diisi "NA / Belum ada kabar"
  - Z baris tidak ketemu di DB (warning)
- Tombol [Export] → save dialog → output: `Laporan Bulanan April [filled].xlsx`
- Toast notification: "Sukses, X dari Y baris terisi"

### Screen 6 — Insights (Dashboard Analitik)
- Top filter: **Periode** (Mingguan / Bulanan), **Pilih Minggu/Bulan** (dropdown)
- Layout grid:
  - **4 KPI cards:** Total Terlambat (mnt), Hari Absen, Coaching Flag count, Karyawan Teladan
  - **Top 5 Paling Terlambat** (table, color-coded)
  - **Butuh Coaching** (>75 mnt/minggu) — list dengan badge warning
  - **Ranking Lengkap** (table sortable: nama · dept · terlambat · hari telat · hari absen · jam kerja)
  - **Karyawan Teladan** card — top 1 per minggu + top 1 per bulan (formula komposit di Section 8.5)
- Action buttons:
  - [📄 Cetak / Export PDF] → generate HTML, buka di default browser, user pakai Ctrl+P
  - [🖼 Save as Image] (opsional, kalau gampang)
  - [📊 Bandingkan Minggu] (opsional, side-by-side 2 minggu)

### Screen 7 — Settings (sub-tabs)
- **Pegawai:** CRUD daftar (nama, no_staff, dept, phone, active). Auto-populated dari import pertama.
- **Jadwal Kerja:** start/end time (default 08.00 - 16.00)
- **Bulan Aktif:** picker, tombol [Mulai Bulan Baru] (konfirmasi 2x untuk safety)
- **Coaching Threshold:** angka menit (default 75) — bisa diubah

---

## 8. Core Logic

### 8.1 Issue Detection
```python
def is_issue(row: AttendanceRow) -> bool:
    if row.tipe != "Hari Kerja":
        return False
    if row.masuk is None or row.keluar is None:
        return True
    return False
```

### 8.2 Import Algorithm
1. Baca file `.xls` via `pandas.read_excel(file, header=0, skiprows=[1])`
2. Filter out baris "Total Personal" dan baris kosong
3. Untuk setiap row:
   - Cari/auto-create employee by `(no_staff, nama, dept)`
   - Parse tanggal (`DD/MM/YYYY` → ISO)
   - Parse decimal koma → float (`"7,9"` → `7.9`)
   - Hitung `has_issue` via `is_issue()`
   - `INSERT OR REPLACE` ke `attendance_records`, **kecuali** `reason_*` field yang sudah berisi (preserve)
4. Return summary (count baris baru, count issue baru, count pegawai baru)

### 8.3 Export Algorithm
1. Buka `Laporan Bulanan.xlsx` via `openpyxl.load_workbook(path)` (preserve formatting)
2. Iterasi setiap row mulai dari row 3 (row 1 = header, row 2 = sub-unit)
3. Ambil `nama` (kolom A), `tanggal` (kolom C)
4. Lookup di DB:
   ```sql
   SELECT ar.reason_category, ar.reason_detail
   FROM attendance_records ar
   JOIN employees e ON ar.employee_id = e.id
   WHERE e.nama = ? AND ar.tanggal = ?
   ```
5. Render text via mapping (Section 6) → tulis ke kolom Q (Alasan Ijin) menggunakan `sheet.cell(row=r, column=17, value=text)`
6. Save: `wb.save(f"{original_stem} [filled].xlsx")` — file asli **tidak** ditimpa
7. Return summary: `{filled_count, na_count, not_found_count}`

### 8.4 Issue Summary per Pegawai (untuk WA copy)

```python
def render_issue_summary(employee_id: int) -> str:
    open_issues = db.query("""
        SELECT tanggal, hari, masuk, keluar
        FROM attendance_records
        WHERE employee_id = ? AND has_issue = 1 AND reason_category IS NULL
        ORDER BY tanggal
    """, employee_id)

    nama = db.get_employee_name(employee_id)
    lines = [f"{nama} ({len(open_issues)} issue)"]
    for r in open_issues:
        kind = describe_issue(r.masuk, r.keluar)   # "lupa absen pulang" / "tidak masuk" / dll
        lines.append(f"- {r.hari}, {format_date_id(r.tanggal)} ({kind})")
    return "\n".join(lines)
```

Output langsung ke clipboard via `pyperclip.copy(text)`. User racik kalimat prefix sendiri.

### 8.5 Insights / Dashboard Queries

```python
# Total terlambat per pegawai per minggu (excluding work-justified)
EXCLUDED_CATEGORIES = ('tugas_lapangan', 'tugas_paparan', 'terlambat_kerja')

def total_terlambat_per_employee(week_start, week_end):
    return db.query("""
        SELECT e.id, e.nama, e.dept,
               SUM(CASE
                   WHEN ar.reason_category IN (?,?,?) THEN 0
                   ELSE COALESCE(ar.terlambat_menit, 0)
               END) AS total_terlambat,
               COUNT(CASE WHEN ar.terlambat_menit > 0 THEN 1 END) AS hari_telat,
               SUM(CASE WHEN ar.has_issue = 1 THEN 1 ELSE 0 END) AS issue_count
        FROM attendance_records ar
        JOIN employees e ON ar.employee_id = e.id
        WHERE ar.tanggal BETWEEN ? AND ?
        GROUP BY e.id
        ORDER BY total_terlambat DESC
    """, EXCLUDED_CATEGORIES, week_start, week_end)

# Karyawan teladan — composite score (lower = better)
def karyawan_teladan(period_start, period_end):
    return db.query("""
        SELECT e.nama, e.dept,
               COALESCE(SUM(ar.terlambat_menit), 0)
                  + SUM(CASE WHEN ar.tipe='Hari Kerja' AND ar.masuk IS NULL AND ar.keluar IS NULL THEN 60 ELSE 0 END)
                  + SUM(CASE WHEN ar.has_issue = 1 THEN 30 ELSE 0 END) AS score,
               COUNT(*) AS hari_kerja
        FROM attendance_records ar
        JOIN employees e ON ar.employee_id = e.id
        WHERE ar.tanggal BETWEEN ? AND ?
              AND ar.tipe = 'Hari Kerja'
        GROUP BY e.id
        HAVING hari_kerja >= 3
        ORDER BY score ASC
        LIMIT 1
    """, period_start, period_end)

# Coaching flag — pegawai yang butuh coaching minggu ini
def coaching_flag(week_start, week_end, threshold=75):
    rows = total_terlambat_per_employee(week_start, week_end)
    return [r for r in rows if r.total_terlambat > threshold]
```

**Karyawan Teladan formula:**
```
score = SUM(terlambat_menit) + (hari_absen × 60) + (issue_count × 30)
       (1 mnt = 1 pt)         (1 absen = 60 pt)   (1 issue = 30 pt)

Pegawai dengan score TERENDAH = teladan.
Filter: minimum 3 hari kerja (excludes pegawai cuti panjang).
Dihitung 2x: per minggu (4-5 winners) + per bulan (1 winner).
```

### 8.6 Cetak Dashboard (HTML → PDF)

1. Render data dashboard ke template Jinja2 → HTML string
2. Tulis HTML ke file temporer `~/AppData/Local/Temp/hr-dashboard-{timestamp}.html`
3. Buka di default browser via `webbrowser.open(file_url)`
4. User pakai Ctrl+P → "Save as PDF" (built-in di browser)
5. CSS pakai `@media print` rules untuk layout yang rapi saat di-print

---

## 9. File I/O — Quirks yang Harus di-Handle

- **xlrd OLE2 warning** pada file dari mesin fingerprint — suppress warning, tetap lanjut parsing
- **Decimal koma Indonesia** — `"7,9"` di-convert manual ke `7.9` (jangan rely on locale Python)
- **Format jam `08.06`** (titik bukan colon) — pakai regex `r'(\d{2})\.(\d{2})'`
- **Header file fingerprint:** baris 0 = header utama, baris 1 = sub-unit ("Jam", "Menit", "Hari") → skip dengan `skiprows=[1]`
- **Baris "Total Personal:"** muncul setelah blok per pegawai → filter `df[~df['Nama'].str.contains('Total', na=False)]`
- **Field `Tanggal`** bisa berupa string `"01/04/2026"` atau datetime — handle keduanya
- **Encoding:** mesin fingerprint biasanya output UTF-8, tapi xlrd kadang return bytes — decode eksplisit kalau perlu

---

## 10. Error Handling

### Soft failures (warning, tetap proses)
- Pegawai di file fingerprint tidak ada di tabel `employees` → dialog "Tambahkan otomatis?" (default Ya)
- Tanggal di luar `current_month` → skip dengan warning
- Issue tanpa alasan saat export → tulis `NA / Belum ada kabar`
- File fingerprint berisi pegawai inactive → tetap impor, flag warning

### Hard failures (block, dialog error)
- File `.xls`/`.xlsx` rusak / tidak bisa dibuka
- Kolom wajib (Nama, Tanggal, Tipe) hilang
- SQLite error (locked, corrupt)
- Disk penuh saat export
- Permission error (file Laporan Bulanan dibuka di Excel)

Semua hard error tampilkan dialog dengan pesan jelas + saran tindakan.

---

## 11. Testing (Minimal Scope)

User explicitly requested: "testing tidak terlalu makan banyak waktu, kecuali benar-benar fatal error."

### Yang DI-TEST (pytest)
- **Issue detection** — `is_issue()` untuk berbagai kombinasi (Hari Kerja, Istirahat, Masuk null, Keluar null, dll)
- **Import parsing** — fixture pakai file `Data Per 2 Minggu.xls` asli; verifikasi jumlah row, deteksi pegawai, decimal parsing benar
- **Export matching** — fixture pakai `Laporan Bulanan April.xlsx` asli; verifikasi kolom Q ter-update, kolom lain tidak tersentuh, formatting preserved
- **Mapping kategori → text** — 8 kategori, semua format output sesuai
- **Coaching counter exclusion** — verifikasi `tugas_lapangan/paparan/terlambat_kerja` benar-benar di-exclude dari sum terlambat

### Yang TIDAK di-test (manual saja)
- GUI behavior (visual, click flow)
- Window resize, dark/light mode toggle
- Edge case kosmetik

### Smoke test final
1 kali end-to-end manual sebelum release: impor 4 minggu data dummy → input alasan → export → buka hasil di Excel, cek visual.

---

## 12. Build & Distribusi

### Build
```bash
pyinstaller --onedir --windowed --icon=icon.ico \
            --name "HR-Absensi" \
            --add-data "data:data" \
            main.py
```

### Output
- Folder `dist/HR-Absensi/` — siap di-ZIP

### Distribusi
- ZIP folder → kirim via Drive/USB → unzip di laptop target → jalan
- Update versi: overwrite isi folder kecuali `data/hr.db` (preserve user data)

---

## 13. Estimasi Effort

| Phase | Estimasi |
|---|---|
| Setup project, Python env, dependencies | 0.5 hari |
| Data layer (SQLite, models, repos) | 0.5 hari |
| Excel I/O (parser .xls, writer .xlsx) | 0.5 hari |
| GUI: Dashboard + Import + Issues + Settings | 1 hari |
| GUI: Issue Summary + Export | 0.5 hari |
| **GUI + logika: Insights/Dashboard Analitik** | **1 hari** |
| **HTML report template (Jinja2 + CSS print-friendly)** | **0.5 hari** |
| Testing minimal + smoke test | 0.5 hari |
| PyInstaller build + dokumentasi | 0.5 hari |
| **Total** | **~5-6 hari** |

---

## 14. Open Questions / Future Work

Hal-hal yang ditunda atau perlu konfirmasi nanti:

1. **Nomor HP pegawai** — apakah perlu diinput manual, atau di-import juga dari file lain?
2. **Multi-bulan archive** — kalau di kemudian hari user butuh, tambah tabel `monthly_archives` (snapshot)
3. **Laporan kerja atasan** — apakah pernah ada permintaan format lain (PDF summary, dll)?
4. **Auto-detect bulan dari nama file** — apakah nama file fingerprint konsisten? (e.g., always contains "April")
5. **Backup otomatis** — sederhana: copy `hr.db` ke `hr.db.bak` sebelum operasi besar (delete, mass update)

---

## 15. Definition of Done

App dianggap selesai (MVP) jika:
- [ ] Bisa impor 4 file fingerprint mingguan tanpa error
- [ ] Issue terdeteksi 100% match dengan deteksi manual
- [ ] User bisa input alasan untuk 8 kategori (termasuk yang ada detail)
- [ ] Generate issue summary list (hari + tanggal + jenis issue), copy ke clipboard, paste di WA berhasil
- [ ] Export laporan bulanan → buka hasil di Excel → kolom Alasan Ijin terisi sesuai
- [ ] Dashboard Insights menampilkan: Top 5 terlambat, coaching flag (>75 mnt), karyawan teladan (weekly + monthly), ranking lengkap
- [ ] Coaching counter benar-benar exclude `tugas_lapangan/paparan/terlambat_kerja`
- [ ] Cetak dashboard via HTML → buka di browser → Save as PDF berhasil
- [ ] Smoke test end-to-end pass
- [ ] User bisa "Mulai Bulan Baru" dan flow ulang dari awal

---

*End of spec.*
