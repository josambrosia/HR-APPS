# Resolusi Issue — Design Spec

**Tanggal:** 2026-05-15
**Status:** Design locked — 8 clarifying question selesai, mockup Batch Resolve disetujui. Siap implementation plan.
**Base branch:** `claude/trusting-lederberg-6e61bb` — di atas Part A (Hari Libur + Export Mingguan, HEAD `c1a9928`); Part A akan di-wrap jadi snapshot v12.
**Target:** snapshot setelah v12 (v13). Independen dari spec HR Profile & Cetak Dashboard.

---

## 1. Goal

Tiga perubahan terkait alur resolusi issue di menu Issues, dibangun dalam satu spec:

1. **Kategori reason baru "Tugas Belajar/Kuliah"** — opsi resolve baru, berperilaku sebagai full-day authorized absence (identik `izin_sakit` / `cuti`).
2. **Batch Resolve** — popup untuk resolve banyak issue sekaligus untuk satu karyawan (mis. tugas luar kota 5 hari), supaya tidak mengisi satu-satu.
3. **Logic change** — koreksi nilai Masuk & Terlambat untuk kategori work-justified-late dan "lupa absen datang", di-**derive saat render export** (kolom DB tidak diubah).

Ketiganya kohesif (semua soal resolusi issue) tapi independen satu sama lain — bisa diimplementasi berurutan.

---

## 2. Scope

| Surface | Terpengaruh? | Catatan |
|---|---|---|
| `src/config.py` | ✅ Ya | `REASON_CATEGORIES` +1, konstanta `DEFAULT_LUPA_PENALTY_MIN` |
| `src/core/reason_mapper.py` | ✅ Ya | `REASON_LABELS` +1, helper `effective_attendance` baru |
| `src/core/report_generator.py` | ✅ Ya | Pakai "effective row" untuk kolom G/L + Total Personal |
| `src/core/weekly_export.py` | ✅ Ya | Tambah `reason_category` ke SELECT, pakai effective Masuk/Terlambat |
| `src/ui/screens/issues.py` | ✅ Ya | Tombol "+ Resolve Massal" di header + wiring dialog |
| `src/ui/components/batch_resolve_dialog.py` | ✅ Baru | Modal `CTkToplevel` Batch Resolve |
| `src/ui/screens/settings.py` | ✅ Ya | Baris setting "Penalti Lupa Absen Datang" di tab General |
| `src/db/attendance.py` | ⚪ Reuse | `set_reason` & `list_issues_for_period` dipakai apa adanya |
| `src/core/insights.py` + coaching | ❌ Tidak | Sudah benar — `terlambat_ranking` dll. sudah meng-exclude `COACHING_EXCLUDED` & `masuk IS NULL` via CASE |
| Dashboard HTML print | ❌ Tidak | Konsumsi insights — ikut benar otomatis |
| DB schema | ❌ Tidak | Tidak ada tabel/kolom baru — kategori baru = nilai teks baru; penalti = row K/V `settings` |
| Import fingerprint flow | ❌ Tidak | Pendekatan derive — tidak perlu `restamp` |

---

# FITUR 1 — KATEGORI "TUGAS BELAJAR/KULIAH"

## 3. Perilaku

Kategori reason baru untuk resolve issue, **berperilaku identik `izin_sakit` / `cuti`**: full-day authorized absence. Tidak ada mutasi data, tidak ada detail field, tidak masuk bucket work-justified-late.

- **ID kanonik:** `tugas_belajar`
- **Label:** `Tugas Belajar/Kuliah`

## 4. Komponen Fitur 1

### 4.1 `src/config.py` (MODIFY)

Tambah `"tugas_belajar"` ke tuple `REASON_CATEGORIES` — posisikan setelah `"cuti"` (mengelompok dengan sibling full-day-absence). Tuple jadi 10 entri.

TIDAK ditambahkan ke `COACHING_EXCLUDED` — full-day absence punya `masuk IS NULL`, dan `terlambat_ranking` sudah meng-handle `masuk IS NULL` → kontribusi 0. Sama seperti `izin_sakit`/`cuti` yang juga tidak ada di `COACHING_EXCLUDED`.

### 4.2 `src/core/reason_mapper.py` (MODIFY)

- Tambah `"tugas_belajar": "Tugas Belajar/Kuliah"` ke `REASON_LABELS`.
- TIDAK ditambahkan ke `REASON_NEEDS_DETAIL` — tanpa detail field.
- `render_alasan_ijin` — tanpa branch khusus; jatuh ke `return REASON_LABELS[category]` → `"Tugas Belajar/Kuliah"`.

### 4.3 Efek otomatis (tanpa perubahan kode)

- **Combo Issues panel:** muncul otomatis — `_build_panel_for` pakai `list(REASON_LABELS.values())`.
- **`IJIN_CATEGORIES` (report_generator):** `tuple(c for c in REASON_CATEGORIES if c not in ("na", "libur"))` → `tugas_belajar` otomatis masuk → baris resolved jadi `ijin_hari=1` di Laporan Bulanan. Perilaku yang diinginkan (sama izin_sakit/cuti).
- **Tidak ada migrasi DB** — `reason_category` adalah kolom TEXT; `tugas_belajar` hanya nilai baru yang valid.

### 4.4 Tests

`tests/test_reason_mapper.py` — rename `test_all_9_categories_present` → `test_all_10_categories_present`, update assertion. `test_reason_categories_and_labels_in_sync` lulus otomatis (guard test).

---

# FITUR 2 — BATCH RESOLVE ("RESOLVE MASSAL")

## 5. Tujuan & Alur

Resolve banyak issue OPEN untuk **satu karyawan** sekaligus lewat satu popup — use case utama: karyawan tugas luar kota beberapa hari, semua harinya di-resolve dengan satu kategori.

**Alur popup:**
1. Pilih karyawan (combo) — hanya karyawan yang punya ≥1 issue OPEN di periode aktif.
2. Centang tanggal — daftar scrollable tanggal issue OPEN karyawan itu (default semua ter-centang).
3. Pilih 1 kategori + detail opsional — meniru struktur field panel resolve single-issue.
4. Tombol "Resolve N Issue" → `set_reason` untuk tiap tanggal ter-centang.

## 6. Komponen Fitur 2

### 6.1 `src/ui/components/batch_resolve_dialog.py` (NEW)

Modal `CTkToplevel`, mengikuti pola [src/ui/components/print_dialog.py](src/ui/components/print_dialog.py) (`PrintOptionsDialog`):
- `transient(parent)`, `resizable(False, False)`, `configure(fg_color=COLOR_BG)`.
- Size + center on screen dengan screen-height clamp.
- `self.after(50, lambda: (self.grab_set(), self.focus_set()))` — modal.
- `bind("<Escape>", ...)` + `protocol("WM_DELETE_WINDOW", ...)` → cancel.

**Struktur (atas→bawah):**
- Header: judul "Resolve Massal" + subtitle "Selesaikan beberapa issue sekaligus untuk satu karyawan."
- Combo "Karyawan" — `CTkComboBox`; label tiap item "Nama (Dept) — N issue terbuka".
- Daftar tanggal (muncul setelah karyawan dipilih): `CTkScrollableFrame` berisi kartu checkbox per tanggal (pola kartu [src/ui/screens/holiday.py](src/ui/screens/holiday.py)) — checkbox + "Hari, DD Bulan YYYY" + info "masuk … · keluar …". Default semua ter-centang. State di `dict[attendance_id, ctk.BooleanVar]`.
- Field resolve: combo "Kategori alasan" + entry "Detail" opsional. Logika show/hide detail mengikuti `REASON_NEEDS_DETAIL` (sama seperti `_on_cat_change` / `_lay_out_form` di issues.py).
- Footer: teks preview "N tanggal dipilih" + tombol "Resolve N Issue" (magenta CTA) + "Batal".

**Konstruktor:** `BatchResolveDialog(parent, *, period_start, period_end, on_done: Callable)`. `on_done` dipanggil setelah submit sukses supaya Issues screen bisa refresh.

### 6.2 Data — reuse query existing

Tidak ada query DB baru. Dialog memanggil `list_issues_for_period(conn, period_start, period_end, resolved=False)` (sudah ada di [src/db/attendance.py](src/db/attendance.py)) sekali, lalu **group by employee di Python** untuk: isi combo karyawan (karyawan dengan ≥1 baris) + daftar tanggal per karyawan.

### 6.3 On submit

```
for attendance_id in tanggal_tercentang:
    set_reason(conn, attendance_id=attendance_id, category=cat, detail=detail)
conn.commit()
```

`set_reason` adalah fungsi yang sama dipakai resolve single-issue — satu kategori+detail diterapkan ke semua tanggal terpilih. Lalu: tutup dialog, panggil `on_done()` (Issues screen `_reload()`), tampilkan success toast.

Validasi: kalau belum ada kategori dipilih atau tidak ada tanggal ter-centang → messagebox warning, tidak submit.

### 6.4 `src/ui/screens/issues.py` (MODIFY)

- `_build_header`: tambah tombol "+ Resolve Massal" di sisi kanan header (magenta CTA), `pack(side="right")`.
- Handler `_on_batch_resolve`: buka `BatchResolveDialog` dengan `period_start, period_end` dari `_active_range()` dan `on_done=self._reload`.
- Tidak ada perubahan lain di issues.py — panel resolve single-issue tetap apa adanya.

## 7. Interaksi dengan Fitur 3

Tidak ada interaksi langsung — Batch Resolve hanya memanggil `set_reason` (sama seperti resolve biasa). Helper derive Fitur 3 bekerja saat export, terlepas dari resolve itu single atau batch. Catatan: batch-resolve tugas luar kota 5 hari sebagai `tugas_lapangan` → hari tanpa badge (`masuk` NULL) tetap jadi justified absence di export (lihat §13 — keputusan no-badge).

---

# FITUR 3 — LOGIC CHANGE: KOREKSI MASUK/TERLAMBAT (DERIVE)

## 8. Pendekatan

Issue yang di-resolve dengan kategori tertentu harus tampil dengan Masuk/Terlambat yang dikoreksi di **export Excel**. Pendekatan: **derive saat render** — kolom DB `masuk`/`terlambat_menit` TIDAK diubah; helper menghitung nilai "efektif" dari `reason_category` saat export dirender.

**Kenapa derive (bukan mutate kolom DB):**
- Data fingerprint mentah tidak pernah hilang.
- Re-import bukan masalah — tidak perlu machinery `restamp` seperti Hari Libur.
- Unresolve trivial — cukup hapus `reason_category`, derivasi berhenti berlaku.
- Otomatis retroaktif — semua issue yang sudah di-resolve sebelum fitur ini ikut terkoreksi saat export, tanpa migrasi.
- **Insight layer sudah benar** — `terlambat_ranking` dkk. sudah meng-exclude `COACHING_EXCLUDED` & `masuk IS NULL` via CASE. Perubahan ini murni soal **2 export Excel**.

## 9. Helper `effective_attendance`

Di [src/core/reason_mapper.py](src/core/reason_mapper.py):

```python
def effective_attendance(row, *, schedule_start: str, lupa_penalty_min: int) -> dict:
    """Hitung Masuk & Terlambat 'efektif' dari satu attendance row
    berdasarkan reason_category. Tidak menyentuh DB.
    Returns {"masuk": str|None, "terlambat_menit": int|None}.
    Fallback ke nilai raw kalau tidak ada koreksi yang berlaku."""
```

**Aturan koreksi:**

| Kondisi | Effective Masuk | Effective Terlambat |
|---|---|---|
| `reason_category in COACHING_EXCLUDED` **dan** `masuk` raw ada (telat beneran) | `schedule_start` (mis. `08:00`) | `0` |
| `reason_category in COACHING_EXCLUDED` **dan** `masuk` raw NULL (no-badge) | raw (tidak dikoreksi) | raw |
| `reason_category == "lupa_absen"` **dan** `masuk` NULL **dan** `keluar` NOT NULL (lupa absen datang) | `schedule_start` + `lupa_penalty_min` menit (mis. `08:15`) | `lupa_penalty_min` (default 15) |
| selainnya (`lupa_absen` lupa pulang, kategori lain, no reason) | raw | raw |

`COACHING_EXCLUDED` = `("tugas_lapangan", "tugas_paparan", "terlambat_kerja")` — set ini **persis sama** dengan "work-justified-late". Helper mereferensikan konstanta `COACHING_EXCLUDED` langsung (dengan komentar bahwa set ini juga berarti "work-justified-late").

**Helper format:** `schedule_start` setting tersimpan format titik (`"08.00"`); kolom `masuk` format titik-dua (`"08:15"` — lihat `parse_time_dot` di [src/parsers/helpers.py](src/parsers/helpers.py)). Helper kecil menormalkan: parse `schedule_start` → menit, tambah penalti, format balik `"HH:MM"`.

## 10. Konsumen helper

### 10.1 `src/core/report_generator.py` (MODIFY)

Di `generate_monthly_report`, untuk tiap baris non-libur, bangun **effective row**:

```python
eff = effective_attendance(r, schedule_start=sched, lupa_penalty_min=penalty)
eff_r = {**r, "masuk": eff["masuk"], "terlambat_menit": eff["terlambat_menit"]}
```

Lalu gunakan `eff_r` (bukan `r`) untuk `compute_derived`, `_write_data_row`, `_accumulate_total`. Dengan begitu:
- Kolom G (Masuk) & L (Terlambat) tampil nilai efektif.
- `compute_derived` re-derive `absen_hari`/`lupa_hari` dari Masuk efektif — baris lupa-absen-datang yang dikoreksi otomatis berhenti dihitung `lupa_hari`.
- Total Personal mengakumulasi Terlambat efektif.

`schedule_start` & `lupa_penalty_min` dibaca sekali via `get_setting` di awal `generate_monthly_report` (fungsi sudah punya `conn`). `keluar`, `kerja_jam`, `kurang_jam` TIDAK disentuh.

### 10.2 `src/core/weekly_export.py` (MODIFY)

- Tambah `ar.reason_category` ke SELECT (saat ini belum di-fetch).
- Baca `schedule_start` + `lupa_penalty_min` via `get_setting`.
- Untuk tiap baris non-libur, hitung `effective_attendance` dan tulis Masuk efektif (kolom H) + Terlambat efektif (kolom L).
- Baris libur (`tipe='Hari Libur'`) tetap seperti sekarang — H–L dikosongkan.

### 10.3 Setting "Penalti Lupa Absen Datang"

- **Key:** `lupa_absen_datang_penalty_min` (string, pola sama `coaching_threshold_min`). Default `"15"`.
- **`src/config.py`:** tambah `DEFAULT_LUPA_PENALTY_MIN = 15`.
- **`src/ui/screens/settings.py`:** `_build_general` — tambah baris ke-4 "Penalti Lupa Absen Datang (menit)" dengan entry editable. `_save` — tambah `set_setting(conn, "lupa_absen_datang_penalty_min", ...)`.
- Konsumen (`report_generator`, `weekly_export`) baca via `get_setting(conn, "lupa_absen_datang_penalty_min", default=str(DEFAULT_LUPA_PENALTY_MIN))`, parse `int`, fallback ke default kalau parse gagal.

## 11. Yang TIDAK berubah

- **`src/core/insights.py` + coaching** — `terlambat_ranking` sudah `WHEN reason_category IN (COACHING_EXCLUDED) THEN 0` dan `WHEN masuk IS NULL THEN 0`. Koreksi work-justified-late = 0 menit konsisten dengan yang sudah dilakukan ranking. Penalti lupa-absen-datang **tidak** mengalir ke coaching (tetap 0 di sana) — disengaja: 15 menit jauh di bawah threshold 75 menit, dan badge slip bukan alasan coaching. **Konsekuensi:** scope perubahan = 2 export Excel saja; klaim "insight sudah benar" tetap utuh.
- **Dashboard HTML print** — konsumsi insights, ikut benar otomatis.

---

## 12. Data Flow

```
Issues screen
  ├─ resolve single  → set_reason ─┐
  └─ Batch Resolve   → set_reason ─┤  (loop per tanggal)
                                   ▼
       attendance_records.reason_category   (DB — masuk/terlambat_menit TIDAK diubah)
                                   │
                                   ▼  saat render export
        effective_attendance(row, schedule_start, lupa_penalty_min)
                                   │
        ┌──────────────────────────┴───────────────────────────┐
        ▼                                                      ▼
  report_generator.py                                  weekly_export.py
  (effective row → compute_derived                     (effective Masuk/Terlambat
   + kolom G/L + Total Personal)                        → kolom H/L)
        │                                                      │
        ▼                                                      ▼
  Laporan Bulanan .xlsx                              Laporan Mingguan .xlsx

insights.py / coaching / Dashboard print — TIDAK berubah (sudah benar via CASE)
```

---

## 13. Error Handling & Edge Cases

- **`terlambat_kerja` dengan `masuk` NULL** — kontradiktif (kategori ini menyiratkan ada clock-in), tapi tertangani: aturan §9 hanya mengoreksi kalau `masuk` ada, jadi baris ini tetap nilai raw.
- **`lupa_absen` lupa pulang (`keluar` NULL)** — tidak kena aturan 15-menit; nilai raw dipertahankan.
- **Baris lupa-absen-datang yang dikoreksi tetap `ijin_hari=1`** — `lupa_absen` ada di `IJIN_CATEGORIES`; `ijin_hari` ditentukan oleh adanya `reason_category`, bukan oleh Masuk. Perilaku existing, tidak diubah Fitur 3.
- **`lupa_penalty_min` setting berisi nilai non-integer** — konsumen fallback ke `DEFAULT_LUPA_PENALTY_MIN`.
- **No-badge work-justified day** — tugas luar kota tanpa badge (`masuk` & `keluar` NULL) di-resolve `tugas_lapangan` → tetap justified absence (`absen_hari=1` + `ijin_hari=1`), koreksi Masuk hanya berlaku kalau ada clock-in telat beneran. Keputusan brainstorm.
- **Batch Resolve: karyawan tanpa issue OPEN di periode** — tidak muncul di combo. Combo kosong kalau tidak ada issue OPEN sama sekali → tampilkan state kosong di dialog.
- **Batch Resolve: semua tanggal di-uncheck** — tombol Resolve disabled / warning.
- **Batch Resolve dibuka, lalu periode Issues screen diganti** — dialog modal (`grab_set`) → user tidak bisa ganti periode saat dialog terbuka. Periode dialog = snapshot saat dibuka.

---

## 14. Testing

| Layer | Coverage |
|---|---|
| `tests/test_reason_mapper.py` (MODIFY) | `test_all_10_categories_present` · `effective_attendance`: work-justified-late dengan masuk telat → 08:00/0 · work-justified-late dengan masuk NULL → raw · lupa-absen-datang → 08:15/15 · lupa-absen pulang → raw · kategori lain → raw · penalti custom (mis. 20) |
| `tests/test_report_generator.py` (MODIFY) | Kolom G/L pakai nilai efektif · `compute_derived` re-derive benar dari effective row (lupa-absen-datang berhenti `lupa_hari`) · Total Personal akumulasi Terlambat efektif · `keluar`/`kerja_jam` tidak berubah |
| `tests/test_weekly_export.py` (MODIFY) | `reason_category` di SELECT · kolom H/L pakai nilai efektif · baris libur tetap kosong |
| `tests/test_settings*.py` (MODIFY/NEW) | Setting `lupa_absen_datang_penalty_min` save/load + default |
| `tests/test_batch_resolve_dialog.py` (NEW) | Konstruksi dialog (smoke) · group-by-employee dari `list_issues_for_period` · submit memanggil `set_reason` per tanggal ter-centang · validasi (tanpa kategori / tanpa tanggal) |
| `tests/test_issues_screen*.py` (MODIFY) | Tombol "+ Resolve Massal" ada di header · membuka dialog |
| Manual smoke | Resolve issue sebagai Tugas Belajar/Kuliah → cek combo + Laporan Bulanan `ijin_hari` · Batch Resolve karyawan multi-hari → cek semua ter-resolve · ubah penalti di Settings → cek Laporan Mingguan · resolve work-justified-late telat → cek Masuk `08:00` di export |

Target: 194 (baseline) + ~30-40 test baru ≈ **~225-235 passing**.

---

## 15. Implementation Notes

**Urutan disarankan:**
1. Fitur 1 — `config.py` + `reason_mapper.py` (kategori `tugas_belajar`) + test_reason_mapper. Kecil, fondasional.
2. Fitur 3 helper — `effective_attendance` + helper format di `reason_mapper.py` + tests (unit murni, tanpa UI).
3. Fitur 3 konsumen — `report_generator.py` + `weekly_export.py` pakai effective row + tests.
4. Fitur 3 setting — `config.py` `DEFAULT_LUPA_PENALTY_MIN` + `settings.py` baris General + tests.
5. Fitur 2 — `batch_resolve_dialog.py` + wiring `issues.py` + tests.
6. Full `pytest -q` + manual smoke.

- **Worktree:** branch `claude/trusting-lederberg-6e61bb`. Tidak perlu rebase.
- **Test sebelum commit** — `pytest -q` match baseline tiap tahap.
- **No auto-push** — tunggu instruksi user.

---

## 16. Keputusan Desain (dari brainstorm — untuk review cepat)

1. **"Tugas Belajar/Kuliah" = full-day authorized absence**, identik izin_sakit/cuti. Bukan work-justified-late, bukan label-only.
2. **Tanpa detail field** untuk kategori baru — konsisten izin_sakit/cuti.
3. **Derive at render time**, bukan mutate kolom DB — data raw aman, retroaktif otomatis, tanpa machinery restamp.
4. **Work-justified-late: koreksi Masuk + Terlambat saja** — `kerja_jam`/`kurang_jam` tidak disentuh.
5. **Lupa Absen tetap satu kategori** — aturan 15-menit di-infer dari pola data (`masuk IS NULL`), bukan split kategori.
6. **Lupa absen datang → "hadir, telat X menit"** — Masuk efektif `08:15`, Terlambat `15`, berhenti dihitung sebagai hari Lupa.
7. **Penalti lupa-absen-datang adjustable** di Settings (default 15), bukan hardcoded.
8. **No-badge work-justified day** (tugas luar kota tanpa badge) → tetap justified absence; koreksi Masuk hanya berlaku kalau ada clock-in telat beneran.

---

## 17. Out of Scope

- Mutasi kolom DB `masuk`/`terlambat_menit` (ditolak — pilih derive).
- Penalti lupa-absen-datang mengalir ke coaching/insights (exports-only).
- Split `lupa_absen` jadi `lupa_absen_datang` + `lupa_absen_pulang` (di-infer dari data).
- Membuat `render_alasan_ijin` "pintar" untuk `lupa_absen` (baca "Lupa Absen Datang" vs "Pulang") — enhancement opsional, bisa ditambah nanti kalau user mau.
- Recompute `kerja_jam` dari Masuk yang dikoreksi.
- Batch Resolve lintas-karyawan (popup hanya satu karyawan per sesi).
- Batch Resolve di luar periode aktif WeekNavBar.

---

## 18. Reference

- **Mockup Batch Resolve (disetujui):** `.superpowers/brainstorm/729-1778786820/content/batch-resolve.html`.
- **Pola modal:** [src/ui/components/print_dialog.py](src/ui/components/print_dialog.py) (`PrintOptionsDialog`).
- **Pola kartu multi-select:** [src/ui/screens/holiday.py](src/ui/screens/holiday.py) (`HolidayScreen`).
- **Pola panel resolve single-issue:** `_build_panel_for` / `_on_cat_change` / `_lay_out_form` di [src/ui/screens/issues.py](src/ui/screens/issues.py).
- **Format waktu:** `parse_time_dot` di [src/parsers/helpers.py](src/parsers/helpers.py) — fingerprint `08.00` → DB `08:00`.
- **Insight CASE existing:** `terlambat_ranking` di [src/core/insights.py](src/core/insights.py).
