# Session Handover — v26.0.2 "Aplikasi Menghitung Sendiri Telat & Lembur"

**Tanggal:** 2026-10-15
**Branch kerja berikutnya:** `v26.0.2` (dibuat dari tip `v26.0.1` @ `b28297d`)
**Status:** analisis selesai + rencana disetujui user; implementasi BELUM dimulai.

---

## 1. Status rilis

| Item | Status |
|---|---|
| `v26.0.0` | **PUSHED** — `origin/v26.0.0` = `origin/latest` = `305d066`. Installer `Installers/HR-Absensi-Setup-v26.0.0.exe` |
| docs konvensi patch | commit `3a11e7e` (CLAUDE.md §5 + workflow_rules Rule 6) — ada di atas v26.0.0, belum dipush |
| `v26.0.1` | **LOKAL, belum dipush** — branch `v26.0.1` @ `b28297d`. Fitur **"Ekspor Diagnostik"** (Settings → Backup & Restore). Installer `Installers/HR-Absensi-Setup-v26.0.1.exe` sudah dibangun + smoke lolos. Produksi `dist/` sudah dirotasi (current v26.0.1 = 14.842.833 B, `.bak` v26.0.0, `.bak.old` v25; `data/hr.db` md5 `b650952cb75dd51609e8240f04ee0ccc` utuh) |
| Tes | **851 hijau** (suite penuh, ±6 menit) |
| Push v26.0.1 | **Menunggu otorisasi eksplisit user** (Rule 1) |

---

## 2. Laporan bug klien (2 laporan)

1. **Lembur:** "saat data lembur dipilih banyak, lalu misal diterima, masih hilang."
2. **Keterlambatan:** "Setelah 14 Sep semua kedatangan masih terhitung telat."

Konteks: database yang dipakai klien ada di **laptop klien** (bukan mesin dev). Data September mereka tersedia di repo: `Export/Laporan Bulanan September 2026 [Auto Filled].xlsx` (hasil ekspor aplikasi dari DB klien, 527 baris).

---

## 3. Temuan analisis

### Bug 2 — TERBUKTI dari data klien ✅

| Bukti (dari xlsx klien) | Angka |
|---|---|
| Kolom **"Jadwal"** (dari file fingerprint) | **SEMUA 527 baris masih `08.00 - 16.00`** — mesin fingerprint belum diubah ke kebijakan baru |
| Baris ≥ 14 Sep: "Terlambat" = `masuk − 08:00` | **171 baris** (09:01→61, 08:46→46, 08:14→14, 09:00→60) |
| Baris masuk ≤ 09:12 tapi tetap telat > 0 | **150 baris** — persis keluhan klien |
| Baris cocok `masuk − 09:00` | 19 baris (khas baris yang pernah diedit manual via dialog Edit Data) |

**Akar masalah:** aplikasi memakai angka "Terlambat" dari file fingerprint apa adanya (by design v26). Karena mesin fingerprint masih basis 08.00, semua kedatangan ≥14 Sep tampil telat di Heatmap, Dashboard, Severe Lateness, dan kedua export.

### Bug 1 — belum terkonfirmasi (butuh DB klien)

- File export tidak memuat keputusan lembur, jadi tidak bisa membuktikan dari xlsx.
- Konteks dari data: September punya **32 kandidat lembur** (keluar > 18:00). Kolom "Lembur" file (basis mesin 16.00, mis. 2,3 jam) **berbeda** dari hitungan app (basis 17.00, mis. 79 mnt) → sumber kebingungan angka.
- Hipotesis utama (hasil simulasi dummy — lihat `scratchpad/`):
  1. **Batch "Terima" hanya berlaku untuk baris berstatus `Diajukan`.** Baris `Open` dilewati (toast: "0 baris diubah… N dilewati"). Jika klien mencentang banyak baris Open lalu menekan Terima → tab "Diterima" tetap kosong → terasa "hilang" (padahal tidak pernah ditulis).
  2. **Bulan aktif pindah otomatis saat import** (auto-detect) → daftar Lembur mengikuti bulan aktif, keputusan bulan lama seolah hilang.
- **Cara konfirmasi:** minta klien install v26.0.1+ → Settings → Backup & Restore → **Ekspor Diagnostik** → kirim zip (berisi `hr.db`, `summary.json`, `samples_setelah_cutoff.csv`, `keputusan_lembur.csv`).

### Temuan arsitektur penting

1. **Menu Lembur sudah 100% logic aplikasi** (punches + jadwal per tanggal + ambang 18.00; spec v26 D8). Kolom "Lembur" fingerprint hanya bocor ke: **Laporan Bulanan kolom J**, **Weekly Export kolom "Lembur"**, dan **kolom F "Jadwal"** di keduanya (teks `08.00 - 16.00`).
2. **Keterlambatan dari fingerprint** dipakai hampir di semua agregasi (heatmap, dashboard/insights, severe lateness, coaching, laporan, weekly export). Logic app baru ada di dialog Edit Data + `effective_attendance` (baris beralasan).
3. **DB klien "fresh + data historis" kemungkinan hanya punya 1 periode jadwal `09.00–17.00 sejak 1970`** (instalasi baru). Tanpa pemecahan periode, recompute akan menghitung Juli–Agustus dari 09.00 (salah). Cek `schedule_periods` di `summary.json` zip diagnostik.

---

## 4. Keputusan user (terkunci)

1. **Kolom "Lembur"** di Laporan Bulanan & Weekly Export → **`keluar − jam pulang`, tanpa ambang** (logic app).
2. **Kolom F "Jadwal"** di kedua export → **diganti jadwal aplikasi** (read-time, mis. `09.00 - 17.00`).
3. **Data lama** → **recompute saat upgrade** (data klien sudah ada di DB; cukup dihitung ulang dengan logic terbaru — bukan import ulang). Baris yang pernah diedit manual **tidak ditimpa**.
4. **Versi rilis:** **v26.0.2 terpisah** dari v26.0.1.
5. **`kerja_jam`** → biarkan dari fingerprint (tidak ikut recompute).

---

## 5. Rencana implementasi v26.0.2 (disetujui, urutan eksekusi)

**Prinsip:** angka telat & lembur = hitung dari jam absensi + jadwal aplikasi per tanggal; kolom fingerprint "Terlambat"/"Lembur"/"Jadwal" tidak dipakai lagi untuk angka.

### Task 3 dulu (prasyarat Task 2) — Perbaikan riwayat jadwal historis
- Di `_migrate` (`src/db/schema.py`), setelah seeding `schedule_periods`: jika hanya ada **1 periode `1970-01-01` dengan `09.00–17.00`** DAN ada baris absensi `< 2026-09-14` → pecah: `1970-01-01 08.00–16.00` + `2026-09-14 09.00–17.00`. DB yang sudah punya 2 periode tidak disentuh.

### Task 2 — Recompute data lama sekali saat upgrade
- Flag settings `recompute_app_v262` (idempotent). Saat `init_db`, jika flag belum ada: hitung ulang SEMUA baris `attendance_records`:
  - `sched = schedule_for(conn, tanggal)` (cache per tanggal)
  - `calc = attendance_calc.recompute(tipe, masuk, keluar, sched_start, sched_end)`
  - update `terlambat_menit` & `lembur_jam`; **lewati baris `manual_edited_at IS NOT NULL`**; `kerja_jam` tidak disentuh.
- Tulis flag setelah selesai.

### Task 1 — Recompute saat import (data baru)
- `import_screen._import_work`: per baris → `schedule_for` (cache) → `recompute()` → simpan `terlambat_menit`/`lembur_jam` hasil hitung (abaikan kolom file); `kerja_jam` tetap dari file; `has_issue` tetap.

### Task 4 — Kolom F "Jadwal" di export (read-time)
- `report_generator._write_data_row` + `weekly_export`: tulis jadwal dari `schedule_for(tanggal)` (format `"09.00 - 17.00"`), bukan teks tersimpan. Data tersimpan tidak diubah.

### Task 5 — Lembur di export
- Otomatis ikut Task 1/2 (`lembur_jam` recompute = `keluar − jam pulang`, tanpa ambang). Kolom J Laporan Bulanan & Weekly Export konsisten dengan metrik Edit Data.

### Task 6 — Diagnostics (v26.0.1 sudah ada; tambah pembanding)
- `samples_setelah_cutoff.csv`: tambah kolom `terlambat_db` vs `terlambat_app`, `lembur_db` vs `lembur_app` (hitung dari punches + `schedule_for`) untuk verifikasi di laptop klien.

### Task 7 — Tes & edge case
- Formula (hari kerja/libur/jam kosong), cutoff 14 Sep, multi-periode, skip editan manual, flag idempotent, import ulang + konflik import, laporan/heatmap/dashboard setelah recompute, kolom Jadwal baru, diagnostics baru. Suite penuh hijau.
- Edge khusus: `lupa_absen_datang` (masuk kosong → telat 0; penalti tetap via `effective_attendance` saat export), `Istirahat`, hari libur, tanggal tanpa periode (fallback default), baris beralasan (justifikasi tetap di-nol-kan saat baca).

### Task 8 — Rilis v26.0.2
- Bump `APP_VERSION` + `APP_BUILD_DATE` + prepend `APP_CHANGELOG` (Indonesian, user-facing).
- Build `HR-Absensi-Setup-v26.0.2.exe` → rotasi 2-level → copy `Installers/` → smoke (pakai salinan data; cek angka September berubah) → **push menunggu otorisasi**.
- Update `memory/version_state.md`.

**Risiko yang sudah disadari user:** setelah recompute, angka September di Dashboard/Heatmap turun drastis (memang tujuan) dan berbeda dari file fingerprint; mesin fingerprint tetap tidak diubah.

---

## 6. Prosedur build yang sudah terbukti (jangan trial-error)

1. **Tutup aplikasi** (`Get-Process HR-Absensi` harus kosong) — PyInstaller tidak bisa menimpa exe yang berjalan.
2. **Inno Setup tidak di PATH**: `$env:PATH = "$env:PATH;C:\Program Files (x86)\Inno Setup 6"` sebelum `python -m tools.build_installer`.
3. **PyInstaller menimpa `dist/HR-Absensi/` yang berisi `data/`**: pindahkan dulu ke `dist/HR-Absensi.PRODSAVE` (script `v26_presave.ps1`), build, lalu kembalikan `data/` + rotasi 2-level + verifikasi md5 DB (`b650952cb75dd51609e8240f04ee0ccc`) + hapus PRODSAVE.
4. Script bantu (di `C:\Users\user\AppData\Local\Temp\opencode\`): `v26_presave.ps1`, `v26_smoke3.ps1` (launch + cek template bundle + Event Log), `v26_rotate3.ps1` (sesuaikan nama installer). Kalau temp terhapus, pola-nya terdokumentasi di sini + `workflow_rules.md` Rule 2.
5. **Push**: `$env:GIT_SSH_COMMAND="C:/Windows/System32/OpenSSH/ssh.exe"; git push origin <branch>` (Git Bash ssh tidak melihat agent Windows).
6. Konvensi patch: `CLAUDE.md` §5 + `memory/workflow_rules.md` Rule 6 (vN.0.1, vN.0.2, …; installer baru tidak menimpa yang lama).

---

## 7. File & referensi penting

| Hal | Path |
|---|---|
| Spec v26 | `docs/superpowers/specs/2026-10-01-v26-lembur-jadwal-kantor-design.md` |
| Plan v26 | `docs/superpowers/plans/2026-10-01-v26-lembur-jadwal-kantor.md` |
| Recompute murni | `src/core/attendance_calc.py::recompute` |
| Resolver jadwal | `src/db/schedule.py::schedule_for` |
| Migrasi/seed | `src/db/schema.py::_migrate` |
| Import worker | `src/ui/screens/import_screen.py::_import_work` |
| Laporan Bulanan | `src/core/report_generator.py` |
| Weekly export | `src/core/weekly_export.py` |
| Diagnostics | `src/core/diagnostics.py` |
| Settings (Jam Kantor/toleransi/ekspor diagnostik) | `src/ui/screens/settings.py` |
| Data klien (bukti bug 2) | `Export/Laporan Bulanan September 2026 [Auto Filled].xlsx` |
| Installer | `Installers/HR-Absensi-Setup-v26.0.{0,1}.exe` |
| Produksi | `dist/HR-Absensi/` (data md5 `b650952cb75dd51609e8240f04ee0ccc`) |
| Script analisa (untuk direproduksi) | `scratchpad/v26_bug_analysis.py`, `scratchpad/v26_client_sept.py`, `scratchpad/v26_client_sept2.py`, `scratchpad/v26_matrix.py` |

---

## 8. Pending / menunggu

- **Push v26.0.1** (+ docs `3a11e7e`) ke origin — menunggu otorisasi user.
- **Implementasi v26.0.2** sesuai §5 (branch `v26.0.2` sudah dibuat dari tip v26.0.1).
- **Minta zip diagnostik dari klien** untuk konfirmasi bug 1 (dan melihat `schedule_periods` DB mereka).
- Kandidat lain (belum diputuskan): audit-log keputusan lembur; Severe Lateness & Coaching Threshold berjadwal seperti toleransi.
