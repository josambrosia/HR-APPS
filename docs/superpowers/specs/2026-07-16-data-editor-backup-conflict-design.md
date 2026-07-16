# Keamanan Data + Edit Manual — Design Spec

**Tanggal:** 2026-07-16
**Status:** DRAFT — menunggu review user sebelum masuk implementation plan
**Target versi (tentatif):** v23.0.0
**Fork dari:** v22.0.0
**Mockup:** `.superpowers/brainstorm/1758-1784189989/content/data-editor-mockups.html`

---

## 1. Masalah & motivasi

Satu-satunya cara memperbaiki data absensi sekarang adalah **import ulang** file fingerprint.
Itu bermasalah:

- File sumbernya sendiri sering salah/kurang (mis. pegawai lupa scan pulang → baris "issue" yang tak bisa dituntaskan tanpa data pulang).
- Import ulang **menimpa senyap** kolom mentah (`masuk`/`keluar`/dst.) — tak ada cara menyelesaikan konflik antara koreksi manual vs data mesin.
- Tak ada jaring pengaman: sekali user salah import, data lama tertimpa tanpa jalan pulang.

Solusi = satu paket **tiga komponen** yang saling menopang, semuanya bertujuan "bebas membetulkan data tanpa takut import merusaknya":

| ID | Komponen | Inti |
|----|----------|------|
| **B** | Backup & Restore | Snapshot file DB penuh + tab Settings. **Dibangun pertama** = jaring pengaman. |
| **A** | Editor baris absensi | Klik sel Heatmap → dialog edit/tambah/hapus, angka turunan dihitung ulang otomatis. |
| **C** | Resolusi konflik import | Saat import mau menimpa baris yang disunting manual → jendela diff per-baris. |

Urutan build: **B → A → C**. B lebih dulu supaya begitu A & C mulai menulis data, sudah ada rollback.

---

## 2. Lingkup & non-goals

**In scope:**

- Edit, tambah, dan hapus baris `attendance_records` lewat dialog dari Heatmap.
- Recompute otomatis penuh: `has_issue`, `terlambat_menit`, `kerja_jam`, `lembur_jam` dari `masuk`/`keluar`/`tipe`.
- Override manual opsional untuk ketiga angka numerik (escape hatch).
- Penanda `manual_edited_at` per baris.
- Backup file DB penuh (otomatis + manual), retensi 1 tahun + pengaman ukuran, restore.
- Jendela resolusi konflik saat import menimpa baris ber-tanda-manual.

**Non-goals (di luar versi ini):**

- Edit data **pegawai** (nama/dept/HP/no_staff) — kandidat versi lain.
- Membuat pegawai baru dari editor (pegawai harus sudah ada dari import).
- Undo per-aksi / riwayat perubahan granular (backup snapshot menggantikan ini).
- Multi-shift per pegawai (perhitungan pakai jadwal global tunggal, sesuai perilaku app sekarang).
- Restore per-bulan (hanya restore file DB penuh).

---

## 3. Keputusan terkunci (dari brainstorming)

| # | Keputusan | Nilai |
|---|-----------|-------|
| D1 | Data yang diedit | Baris absensi (bukan pegawai) |
| D2 | Recompute | **Otomatis penuh** (issue + telat + kerja + lembur) |
| D3 | Pintu masuk editor | **Inline dari Heatmap** (klik sel → dialog) |
| D4 | Operasi | Edit **+ tambah + hapus** |
| D5 | Konflik import | **Tanya saat bentrok** via jendela khusus, resolve per-baris |
| D6 | Backup | **Snapshot file DB penuh**, otomatis + manual |
| D7 | Retensi backup | **1 tahun** (auto-hapus > 365 hari) + pengaman ukuran ~1 GB, minimal 5 terbaru selalu disimpan |
| D8 | Formula `kerja_jam` | `keluar − masuk` (**tanpa** potong istirahat) |
| D9 | Formula `lembur_jam` | `max(0, keluar − jam_pulang)` (otomatis lewat jam pulang) |
| D10 | Override angka | Ada, opsional, bisa dibuka di dialog |
| D11 | `jadwal` | Teks bebas, display-only, tidak dipakai perhitungan |

D8–D11 diajukan saat presentasi desain & disetujui implisit ("oke aku suka"); dicantumkan eksplisit di sini agar review gate menangkap kalau ada yang meleset.

---

## 4. Perubahan skema

### 4.1 Kolom baru — `attendance_records.manual_edited_at`

```sql
ALTER TABLE attendance_records ADD COLUMN manual_edited_at TEXT;
```

- `NULL` = baris murni dari import.
- ISO timestamp = terakhir kali disunting manual (dipakai deteksi konflik).
- Ditambahkan lewat `schema._migrate()` dengan `PRAGMA table_info` guard (persis pola kolom `export_history.kind` yang sudah ada). `CREATE TABLE IF NOT EXISTS` **tidak** menambah kolom ke tabel lama, jadi `ALTER` wajib.

### 4.2 Folder backup — `data/backups/`

- Dibuat otomatis (`mkdir parents=True, exist_ok=True`).
- Berisi file snapshot `hr-YYYYMMDD-HHMMSS-<reason>.db`.
- Tidak ada tabel baru untuk metadata backup — semua info diturunkan dari nama file + `stat()`.
- **Tambahkan `data/backups/` ke `.gitignore`** — glob `data/*.db` yang ada TIDAK mencakup subfolder, jadi snapshot bisa ikut ter-track kalau tak dikecualikan eksplisit.

---

## 5. Komponen B — Backup & Restore

### 5.1 Modul `src/db/backup.py` (murni I/O file, tanpa Tk)

```python
BACKUP_DIRNAME = "backups"
REASONS = {"import": "sebelum-import", "manual": "manual",
           "hapus": "sebelum-hapus", "restore": "sebelum-restore"}

def backup_dir(db_path) -> Path                      # <db_path>.parent / "backups"
def create_backup(db_path, *, reason, now=None) -> Path
    # copy2(db_path -> backups/hr-YYYYMMDD-HHMMSS-<reason>.db), lalu prune_backups(); return path
def list_backups(db_path) -> list[dict]
    # [{path, filename, created_at, size_bytes, reason}], terbaru dulu
def restore_backup(db_path, snapshot_path, *, now=None) -> Path
    # 1) create_backup(reason="restore")  2) copy2(snapshot -> db_path); return pre-restore backup path
def prune_backups(db_path, *, max_age_days=365, max_total_bytes=1_000_000_000,
                  keep_min=5, now=None) -> list[Path]   # return yang dihapus
```

**Retensi (`prune_backups`) — D7:**

1. Urutkan snapshot terbaru→terlama.
2. **Selalu simpan** `keep_min` (5) terbaru (floor — user tak pernah kehabisan).
3. Dari sisanya, hapus yang **umur > `max_age_days`** (365).
4. Jika total ukuran folder masih > `max_total_bytes` (~1 GB), hapus **terlama** sampai di bawah batas (tetap hormati floor 5).

`create_backup` memanggil `prune_backups` setiap kali; app juga memanggilnya sekali saat start.

- `now` di-inject (default `datetime.now()`) supaya test deterministik.
- Waktu file diturunkan dari nama file (parse `YYYYMMDD-HHMMSS`); fallback ke `mtime`.

### 5.2 Trigger auto-backup

| Kapan | reason |
|-------|--------|
| Sebelum confirm import menulis | `import` |
| Sebelum hapus baris di editor | `hapus` |
| Sebelum restore (otomatis di `restore_backup`) | `restore` |
| Tombol "Backup sekarang" | `manual` |

> Catatan implementasi: hapus baris membuat 1 snapshot per aksi. Retensi (umur + ukuran + floor) menahan pertumbuhan. Jika di praktik ternyata terlalu sering, throttle "maks 1 snapshot `hapus` per hari" bisa ditambah tanpa mengubah kontrak.

### 5.3 UI — tab baru "Backup & Restore" di Settings

- `SettingsScreen._build()` menambah `self.tabs.add("Backup & Restore")` + `self._build_backup(tab)`.
- Isi:
  - Toolbar: tombol **"＋ Backup sekarang"** (magenta), **"📂 Buka folder"** (ghost), teks info.
  - Baris path + retensi: `data/backups/ · retensi 1 tahun · auto-hapus yang lama (batas ~1 GB, min. 5 terbaru)`.
  - Daftar snapshot (reuse pola `HistoryList` atau list manual): ikon, nama file (mono), waktu + ukuran, **badge alasan** berwarna (import=amber, manual=magenta, hapus=merah, restore=cyan), tombol **Restore** + **Hapus** per baris.
  - Strip caution amber soal restore.
- Semua operasi berat (copy file) via `run_bg` bila file besar; untuk DB kecil boleh sinkron dengan `BusyGuard`.

### 5.4 Alur restore

1. User klik **Restore** pada satu snapshot → `feedback.ask_yes_no` konfirmasi ("Ganti seluruh data dengan snapshot ini? Data sekarang di-backup dulu.").
2. `restore_backup(DB_PATH, snapshot)` → buat backup `sebelum-restore` → copy snapshot menimpa `hr.db`.
3. `notify_data_changed()` supaya semua layar cache refetch.
4. Dialog info menyarankan **restart aplikasi** (aman, karena koneksi SQLite berumur pendek via `get_connection`; tidak ada handle panjang, tapi restart menjamin state in-memory bersih).

**Keamanan data produksi:** semua path memakai `DB_PATH` dari `src.config`; test **wajib** pakai temp dir + temp db, tak pernah menyentuh `dist/HR-Absensi/data/hr.db`.

---

## 6. Komponen A — Editor baris absensi

### 6.1 Mesin hitung ulang — `src/core/attendance_calc.py` (murni, unit-tested)

```python
def _to_minutes(s: str | None) -> int | None
    # "08:15" -> 495 ; "08.00" -> 480 ; None/garbage -> None
    # terima pemisah ":" (masuk/keluar) maupun "." (setting jadwal)

def recompute(*, tipe, masuk, keluar, schedule_start, schedule_end) -> dict:
    """Return {has_issue, terlambat_menit, kerja_jam, lembur_jam}. Murni, tanpa I/O."""
```

**Formula (D2, D8, D9):**

| Field | Aturan |
|-------|--------|
| `has_issue` | `1` bila `tipe == "Hari Kerja"` **dan** (`masuk` kosong **atau** `keluar` kosong), else `0`. Identik `core.issue_detector.is_issue`. |
| `terlambat_menit` | `max(0, menit(masuk) − menit(schedule_start))` bila `tipe=="Hari Kerja"` & ada `masuk`; else `0`. **Mentah** (toleransi diterapkan di hilir seperti sekarang). |
| `kerja_jam` | `round(max(0, menit(keluar) − menit(masuk)) / 60, 1)` bila `masuk` & `keluar` ada; else `0.0`. Tanpa potong istirahat. |
| `lembur_jam` | `round(max(0, menit(keluar) − menit(schedule_end)) / 60, 1)` bila ada `keluar`; else `0.0`. |

**Edge cases:**

- Overnight (`keluar < masuk`): `max(0, …)` → `kerja_jam = 0.0`. Kasus langka; didokumentasikan, bukan didukung penuh.
- `tipe` selain "Hari Kerja" (Libur/Istirahat): `has_issue=0`, `terlambat=0`. `kerja/lembur` tetap dihitung bila kedua punch ada (mis. lembur di hari libur).
- Input jam invalid → diperlakukan `None`.

### 6.2 Override (D10)

- Dialog punya section "Angka manual (override)" yang bisa dibuka (default tertutup).
- Bila dibuka & diisi, nilai yang diketik user **menggantikan** hasil `recompute` untuk field itu saat simpan.
- Berguna kalau mesin fingerprint memotong istirahat sehingga `kerja_jam` otomatis meleset ~1 jam.

### 6.3 DB layer — `src/db/attendance.py` (tambahan)

```python
def get_attendance(conn, *, employee_id, tanggal) -> dict | None       # 1 baris, atau None
def save_manual_attendance(conn, *, employee_id, tanggal, hari, tipe, jadwal,
                           masuk, keluar, kerja_jam, lembur_jam, terlambat_menit,
                           has_issue, now=None) -> None
    # INSERT/UPDATE (employee_id, tanggal); SET manual_edited_at = now;
    # PRESERVE reason_category/reason_detail/resolved_at (sama seperti upsert_attendance)
def delete_attendance(conn, *, employee_id, tanggal) -> None
def list_manual_edited_keys(conn, keys) -> set                          # untuk deteksi konflik
```

- `save_manual_attendance` mirip `upsert_attendance` tetapi **menulis** `manual_edited_at` (bukan `imported_from/at`) dan menerima angka turunan yang sudah dihitung.
- `hari` (nama hari Sen–Min) dihitung dari `weekday()` tanggal saat tambah baris (mapping Indonesia; sediakan util kecil bila belum ada).

### 6.4 Integrasi Heatmap (`src/ui/screens/heatmap.py`)

- Saat paint grid (`_paint_grid`), setiap sel sudah punya `e["employee_id"]` + hari; sisipkan ke map: `self._edit_by_item[item_id] = {"employee_id": eid, "tanggal": f"{self._month}-{day:02d}", "nama": e["nama"]}` (sel `nodata` sudah dipaint & ber-tag `"cell"`, jadi tambah baris langsung didukung).
- `_on_cell_click` → buka `AttendanceEditDialog(...)` alih-alih hanya update detail strip. Hover tooltip tetap = peek cepat; klik = edit. (Detail strip boleh tetap update.)
- Callback `on_saved`/`on_deleted` → `self._load()` (repaint) + `notify_data_changed()`.

### 6.5 Dialog — `src/ui/components/attendance_edit_dialog.py`

- `CTkToplevel` mengikuti pola `BatchResolveDialog` (transient + `grab_set` + Escape/Return + `_regrab` setelah nested dialog + WM_DELETE handler).
- Header: "Edit Absensi" / "Tambah Absensi" + "{nama} · {hari}, {tanggal-id}".
- Fields: `Tipe` (dropdown), `Masuk`, `Keluar` (entry HH:MM), `Jadwal` (entry, hint "teks bebas, tak dipakai hitung").
- Kotak **"◆ Dihitung otomatis"**: Status (pill ✓/⚠), Telat, Kerja, Lembur — **update live** saat field jam/tipe berubah (bind `KeyRelease`/`command`).
- Section override (collapsible) untuk 3 angka.
- Footer: **Hapus baris** (kiri, merah ghost; hanya jika baris sudah ada) · **Batal** · **Simpan** (magenta).
- Simpan: baca setting `schedule_start/end` → `recompute` (atau override) → `save_manual_attendance` → callback.
- Hapus: `ask_yes_no` → `create_backup(reason="hapus")` → `delete_attendance` → callback.
- Nilai jam divalidasi (regex `HH:MM`, 00–23:00–59); invalid → `feedback.show_warning` + `_regrab`.

---

## 7. Komponen C — Resolusi konflik import

### 7.1 Deteksi konflik — `src/core/import_conflicts.py` (murni)

```python
CONFLICT_FIELDS = ("tipe", "jadwal", "masuk", "keluar",
                   "kerja_jam", "lembur_jam", "terlambat_menit")

def find_conflicts(pending_rows, existing_by_key) -> list[dict]:
    """Konflik = baris incoming yang (employee_id, tanggal)-nya cocok dengan baris
    existing ber-`manual_edited_at` NOT NULL DAN salah satu CONFLICT_FIELDS berbeda.
    Return [{key, nama, tanggal, hari, manual: {...}, incoming: {...}, changed: [field,...]}]."""
```

- Baris tanpa `manual_edited_at` → **tidak** konflik, ditimpa senyap seperti sekarang.
- Baris identik (tak ada field berubah) → bukan konflik.

### 7.2 Perubahan alur import (`src/ui/screens/import_screen.py`)

1. Parse (worker) → `rows` (seperti sekarang).
2. **Pra-scan** (read-only): ambil existing manual-edited untuk (employee, tanggal) yang relevan → `find_conflicts`.
3. Bila ada konflik → buka **`ImportConflictDialog`** (main thread) → user pilih per-baris `keep`/`take` (+ aksi massal) → hasilkan `resolution: dict[key -> "keep"|"take"]`. Batal = batalkan seluruh import.
4. `create_backup(reason="import")`.
5. Confirm-write (worker, `run_import_confirm` diperluas terima `resolution`):
   - Baris **non-konflik** → `upsert_attendance` seperti sekarang.
   - Baris konflik **`take`** → `upsert_attendance` **+ set `manual_edited_at = NULL`** (kembali "milik import").
   - Baris konflik **`keep`** → **skip** (baris manual dibiarkan utuh).

### 7.3 Dialog — `src/ui/components/import_conflict_dialog.py`

- `CTkToplevel` pola sama (header/scroll-content/footer).
- Header: "⚠ Konflik Import — N baris pernah disunting manual" + subteks (nama file, jumlah baris non-konflik yang diimpor otomatis).
- Aksi massal: "Pertahankan manual semua" / "Pakai import semua".
- Per baris: kartu diff 2 kolom (**Manual** cyan vs **Import** amber), field berbeda disorot; toggle radio `keep`/`take` (default **keep**).
- Footer: "Batal impor" · "Terapkan & lanjut import (N)".

---

## 8. Strategi test

| Area | Test |
|------|------|
| `attendance_calc.recompute` | Unit murni: punch lengkap/kurang, telat 0/kecil/besar, lembur, overnight clamp, non-Hari-Kerja, jam invalid, override. |
| `db/backup.py` | Temp dir + temp db: create → list → restore; retensi (umur via `now` inject + `mtime`, batas ukuran, floor 5); nama file & reason parse. **Tak pernah** sentuh DB produksi. |
| `import_conflicts.find_conflicts` | Murni: manual vs non-manual, identik (bukan konflik), sebagian field beda, baris baru. |
| Migrasi `manual_edited_at` | DB lama tanpa kolom → `init_db` idempotent menambah kolom. |
| DB editor | `save_manual_attendance` (insert+update, preserve reason, set flag), `delete_attendance`. |
| Import flow | `run_import_confirm` dengan `resolution` (keep skip, take clear flag). |
| Changelog | Retensi entri versi + entri baru v23. |
| Smoke layar | Render dialog headless bila memungkinkan (tanpa modal loop). |

Baseline suite penuh harus tetap hijau (500+). Jalankan `--ignore-glob='*screen*'` lalu screen test terpisah.

---

## 9. Urutan build (untuk implementation plan)

1. **Fase B1** — `db/backup.py` + test (retensi, restore). Jaring pengaman lebih dulu.
2. **Fase B2** — tab Settings "Backup & Restore" + wiring auto-backup ke import.
3. **Fase A1** — `core/attendance_calc.py` + test.
4. **Fase A2** — migrasi `manual_edited_at` + DB layer (`save_manual_attendance`/`delete_attendance`/`get_attendance`).
5. **Fase A3** — `AttendanceEditDialog` + integrasi klik Heatmap.
6. **Fase C1** — `core/import_conflicts.py` + test.
7. **Fase C2** — `ImportConflictDialog` + perluas alur import (pra-scan + resolution).
8. **Rilis** — changelog, bundle installer, rotasi .exe, smoke (per CLAUDE.md).

Tiap fase: test hijau sebelum commit.

---

## 10. Versi & changelog

- Tentatif **v23.0.0** (feature set baru). Angka final ditetapkan saat rilis.
- `APP_CHANGELOG` (`src/config.py`) dapat entri baru: fitur Edit Data manual dari Heatmap, hitung ulang otomatis, jendela konflik import, Backup & Restore. Bahasa Indonesia, action-oriented.

---

## 11. Risiko & catatan

- **Akurasi `kerja_jam`/`lembur_jam`** vs mesin fingerprint (D8/D9): bila mesin memotong istirahat, angka editan bisa berbeda. Dimitigasi override (D10) + label "Dihitung otomatis" yang jujur.
- **Restore saat app jalan:** aman karena koneksi berumur pendek, tapi dialog menyarankan restart untuk kepastian.
- **Ledakan jumlah backup** dari hapus beruntun: ditahan retensi umur+ukuran+floor; throttle harian bisa ditambah bila perlu.
- **Konsistensi lintas layar:** semua tulis memanggil `notify_data_changed()` agar layar cache (Dashboard/Heatmap/Issues/dll.) refetch.
- **Keamanan DB produksi:** semua test pakai temp db; tak ada test/alur yang menulis `dist/HR-Absensi/data/hr.db` tanpa perintah eksplisit.
