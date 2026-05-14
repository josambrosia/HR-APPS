# Menu Outlier / Pengecualian — Design Spec

**Tanggal:** 2026-05-14
**Status:** Design locked (UI mockup approved), ready for implementation plan
**Base branch:** `origin/v10` (worktree sudah di v10 + sesi ini)
**Target:** snapshot v11

---

## 1. Goal

Tambah kemampuan untuk **mengecualikan (exclude) karyawan tertentu dari analisis Dashboard & Coaching**. Beberapa karyawan punya pola kehadiran yang secara sah berbeda (mis. direktur, staff lapangan, karyawan cuti panjang) — kehadiran mereka mendistorsi statistik tim. Fitur ini membuat mereka tidak ikut dihitung di angka analitik, tanpa menghapus mereka dari sistem.

Pengecualian:
- **Reversible** — bisa di-include kembali kapan saja
- **Carry-forward** — sekali dikecualikan, berlaku untuk bulan itu dan seterusnya
- **History-preserving** — revert tidak menghapus jejak bulan-bulan lampau (soft revert)
- **Analytics-only** — tidak menyentuh workflow operasional (Issues, WhatsApp, laporan resmi)

---

## 2. Scope

| Surface | Terpengaruh? | Catatan |
|---|---|---|
| Dashboard insights (semua panel) | ✅ Ya | Keterlambatan, jumlah terlambat, akumulasi menit, Coaching, Teladan, Ranking Lengkap, Pola Jam Masuk, Rata-rata |
| Cetakan Dashboard (HTML print) | ✅ Ya | Otomatis — renderer konsumsi fungsi insight yang sama; renderer & template TIDAK perlu diubah |
| Coaching screen (via `src/db/coaching.py`) | ✅ Ya | Karyawan Outlier tidak muncul di daftar Butuh Coaching — filter di `list_coaching_for_week` |
| Issues screen | ❌ Tidak | Issue karyawan Outlier tetap terbuka, tetap perlu di-resolve, detail resolve tetap masuk DB |
| WhatsApp Assistant | ❌ Tidak | Draft pesan tetap dibuat untuk karyawan Outlier |
| Report Generator (.xlsx laporan bulanan) | ❌ Tidak | Laporan resmi tetap menampilkan semua karyawan |

**Tidak ada catatan transparansi di cetakan** — angka tampil apa adanya tanpa disclaimer (keputusan user).

---

## 3. Data Model

Tabel baru `outlier_exclusions` — menyimpan **riwayat rentang pengecualian** (bukan flag tunggal):

```sql
CREATE TABLE IF NOT EXISTS outlier_exclusions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id     INTEGER NOT NULL REFERENCES employees(id),
    effective_from  TEXT NOT NULL,    -- "YYYY-MM" — bulan mulai dikecualikan
    effective_until TEXT,             -- "YYYY-MM" atau NULL (NULL = masih aktif/ongoing)
    created_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_outlier_employee ON outlier_exclusions(employee_id);
```

Ditambahkan ke `DDL` string di [src/db/schema.py](src/db/schema.py) — idempoten via `CREATE TABLE IF NOT EXISTS`, aman untuk DB existing (`data/hr.db`). Pola sama persis dengan cara `coaching_sessions` & `export_history` ditambahkan di v3/v6.

### 3.1 Aturan inti

**"Apakah karyawan E dikecualikan untuk bulan analisis M?"**
```sql
SELECT 1 FROM outlier_exclusions
 WHERE employee_id = E
   AND effective_from <= M
   AND (effective_until IS NULL OR M < effective_until)
```

**Invariant:** satu karyawan punya **maksimal 1 row aktif** (`effective_until IS NULL`) pada satu waktu. Boleh punya banyak row historis (rentang yang sudah ditutup).

### 3.2 Toggle logic (operasi dari layar Outlier, bulan aktif = `AM`)

**Exclude (ON)** — `exclude_employee(conn, employee_id, AM)`:
- Kalau sudah ada row aktif untuk karyawan ini → no-op (sudah dikecualikan)
- Kalau belum → `INSERT (employee_id, effective_from=AM, effective_until=NULL, created_at=now)`

**Revert (OFF)** — `revert_employee(conn, employee_id, AM)`:
- Ambil row aktif (`effective_until IS NULL`) untuk karyawan ini
- Kalau `effective_from == AM` → `DELETE` row tersebut (rentang akan kosong — seolah batal exclude)
- Kalau `effective_from < AM` → `UPDATE effective_until = AM` (bulan lampau tetap excluded, AM dst dihitung lagi)
- Kalau tidak ada row aktif → no-op

**Revert Semua** — `revert_all(conn, AM)`: jalankan `revert_employee` untuk semua karyawan yang punya row aktif.

**Re-exclude setelah revert:** otomatis tertangani — `exclude_employee` membuat row baru karena tidak ada row aktif lagi.

### 3.3 Edge case: bulan aktif < effective_from

Layar Outlier selalu beroperasi pada bulan aktif. Kalau user pindah ke bulan lampau lalu toggle, perlakuannya tetap konsisten dengan aturan di atas (effective_from = bulan aktif saat itu). Tidak ada penanganan khusus — aturan §3.1 & §3.2 sudah deterministik untuk semua kasus.

---

## 4. Komponen

### 4.1 `src/db/outlier.py` (NEW)

Data-access layer untuk `outlier_exclusions`. Fungsi:

```python
def excluded_employee_ids(conn, year_month: str) -> set[int]:
    """Set employee_id yang dikecualikan untuk bulan analisis tertentu.
    Dipakai oleh insights layer + coaching screen."""

def list_active_exclusions(conn) -> list[dict]:
    """Semua row aktif (effective_until IS NULL) + nama/dept dari JOIN employees.
    Untuk render section 'Dikecualikan' di layar Outlier."""

def exclude_employee(conn, employee_id: int, active_month: str) -> None:
    """Toggle ON. Lihat §3.2."""

def revert_employee(conn, employee_id: int, active_month: str) -> None:
    """Toggle OFF (soft revert). Lihat §3.2."""

def revert_all(conn, active_month: str) -> int:
    """Bulk revert semua row aktif. Returns jumlah yang di-revert."""

def month_roster(conn, year_month: str) -> list[dict]:
    """Karyawan yang punya attendance record di bulan tsb (id, nama, dept),
    urut nama ASC. Untuk daftar di layar Outlier.
    Query: SELECT DISTINCT ... WHERE substr(tanggal,1,7) = ?"""
```

### 4.2 `src/db/schema.py` (MODIFY)

Tambah blok `CREATE TABLE IF NOT EXISTS outlier_exclusions ...` + index ke string `DDL`.

### 4.3 `src/core/insights.py` (MODIFY)

`from src.db.outlier import excluded_employee_ids`.

Setiap fungsi insight resolve bulan dari `period_start[:7]`, panggil `excluded_employee_ids(conn, month)`, lalu filter `employee_id NOT IN (excluded)`. Fungsi yang disentuh:

| Fungsi | Cara filter |
|---|---|
| `terlambat_ranking` | Tambah `AND employee_id NOT IN (...)` di query — **cascade otomatis** ke `top_n_terlambat` & `coaching_flag` yang derive darinya |
| `karyawan_teladan_top_n` | Filter di query — karyawan Outlier juga tidak bisa jadi Teladan |
| `karyawan_teladan` | Sama |
| `avg_minutes_per_late_event` | Tambah filter di WHERE |
| `pola_jam_masuk` | Tambah filter di WHERE |
| `ranking_departemen` | Tambah filter di WHERE |
| `hari_paling_rawan` | Tambah filter di WHERE |

Implementasi filter: karena `excluded_employee_ids` mengembalikan `set[int]`, masing-masing fungsi build placeholder `NOT IN (?,?,...)` secara dinamis, atau filter di Python layer setelah fetch (pilih yang paling konsisten dengan gaya tiap fungsi — beberapa sudah Python-side seperti `terlambat_ranking`).

**Edge case empty set:** kalau `excluded` kosong, filter jadi no-op (jangan generate `NOT IN ()` yang invalid SQL — guard dengan `if excluded:`).

**Dashboard & print renderer TIDAK diubah** — keduanya konsumsi fungsi insight di atas, jadi otomatis ikut benar.

### 4.4 `src/ui/screens/outlier.py` (NEW)

Layar Outlier. Mengikuti mockup yang disetujui (`.superpowers/brainstorm/696-1778743382/content/01-outlier-screen.html`).

Struktur:
- **Header:** judul "Outlier — Pengecualian" + subtitle + badge bulan aktif (cyan, baca `get_setting(conn, "current_month")`)
- **Info bar** (cyan border-left): ringkasan "N dari M karyawan dikecualikan" + reassurance bahwa issue tetap jalan
- **Search box:** filter daftar by nama (client-side)
- **Section "Dikecualikan · N":** dari `list_active_exclusions` yang juga ada di roster bulan aktif. Tiap baris: avatar inisial, nama, dept, "sejak [bulan]", tombol "↩ Sertakan kembali" (violet outline). Baris bertema violet + badge "DIKECUALIKAN".
- **Section "Disertakan · N":** sisa roster bulan aktif. Tiap baris: avatar, nama, dept, tombol "Kecualikan" (abu outline).
- **Footer:** tombol "↩ Revert Semua (N)" — hanya muncul kalau N > 0.

State handling:
- Bulan aktif belum di-set / belum ada data → empty state "Belum ada data untuk bulan aktif. Pilih bulan di menu Active Month."
- Roster ada tapi 0 dikecualikan → section "Dikecualikan" hilang, hanya "Disertakan" + tidak ada tombol Revert Semua.
- Tiap toggle → tulis ke DB → re-render daftar (mirror pola screen lain yang refresh setelah aksi DB).

Catatan: "Revert Semua" **tanpa dialog konfirmasi** (konsisten dengan gaya app yang ringan; revert reversible — tinggal exclude lagi).

### 4.5 `src/ui/app.py` (MODIFY)

Di `nav_groups` (sekitar baris 140), tambah grup baru **sebelum** `("SYSTEM", ...)`:
```python
("EXCEPTIONAL CASE", [
    ("🔸", "Outlier", "Outlier"),
]),
("SYSTEM", [
    ("⚙", "Settings", "Settings"),
]),
```
Di `_show()` (sekitar baris 397), tambah cabang:
```python
elif name == "Outlier":
    from src.ui.screens.outlier import OutlierScreen
    OutlierScreen(self.content).grid(row=0, column=0, sticky="nsew")
```

### 4.6 `src/db/coaching.py` (MODIFY)

Coaching screen **TIDAK** lewat `coaching_flag` insights — ia punya jalur data sendiri: `src/ui/screens/coaching.py` memanggil `list_coaching_for_week(conn, week_start, week_end, threshold_minutes)` dari `src/db/coaching.py`. Jadi cascade §4.3 **tidak** mengenai layar Coaching.

Fix: di `list_coaching_for_week`, resolve bulan dari `week_start[:7]`, panggil `excluded_employee_ids(conn, month)`, dan filter hasil agar karyawan Outlier tidak muncul di daftar Butuh Coaching. `src/ui/screens/coaching.py` sendiri tidak perlu diubah — ia hanya konsumsi `list_coaching_for_week`.

Catatan: `coaching_sessions` (tabel resolusi coaching) tidak disentuh — kalau karyawan Outlier kebetulan sudah punya sesi coaching tercatat, datanya tetap ada, hanya tidak ditampilkan di daftar aktif.

---

## 5. Data Flow

```
Layar Outlier
  │  exclude_employee / revert_employee / revert_all
  ▼
src/db/outlier.py  ──writes──►  outlier_exclusions table
       │                               │
       │  excluded_employee_ids(conn, month)
       ├───────────────┬───────────────┘
       ▼               ▼
src/core/insights.py   src/db/coaching.py
  │ (terlambat_ranking,   │ (list_coaching_for_week
  │  karyawan_teladan*,   │  — filter di sini)
  │  avg_minutes_per_late_event,
  │  pola_jam_masuk, ranking_departemen,
  │  hari_paling_rawan)   │
  ▼                       ▼
┌─────────────────┬──────────────────────┐   ┌─────────────────┐
│ Dashboard       │ Dashboard HTML print │   │ Coaching screen │
│ (insights)      │ (renderer, no change)│   │ (no change)     │
└─────────────────┴──────────────────────┘   └─────────────────┘
   semua otomatis exclude karyawan Outlier
```

---

## 6. Error Handling & Edge Cases

- **Semua karyawan dikecualikan** → fungsi insight return list kosong → Dashboard & Coaching tampil empty state existing ("Tidak ada data"). Print: panel tampil empty-state placeholder (sudah ada dari v7). Tambahkan guard di Outlier screen sendiri agar tetap bisa "Revert Semua".
- **Karyawan dikecualikan tapi tidak ada di roster bulan aktif** → tidak muncul di daftar layar Outlier bulan itu, tapi row `outlier_exclusions` tetap ada & tetap berlaku untuk bulan-bulan di mana dia memang punya data.
- **Periode analisis lintas 2 bulan** → bulan exclusion diambil dari `period_start[:7]`. Dashboard app beroperasi dalam 1 bulan aktif jadi kasus ini jarang; didokumentasikan sebagai known limitation.
- **Revert di bulan yang sama dengan exclude** → row di-DELETE (rentang kosong), bukan di-update. Sudah ditangani §3.2.
- **DB existing tanpa tabel** → `CREATE TABLE IF NOT EXISTS` di DDL menangani saat `init_db` dipanggil di startup.

---

## 7. Testing

| Layer | Coverage |
|---|---|
| `src/db/outlier.py` (unit) | `exclude_employee` (baru + no-op kalau sudah aktif) · `revert_employee` (kedua cabang: same-month DELETE, past-month UPDATE) · `revert_all` · `excluded_employee_ids` (boundary effective_from/until: bulan tepat di batas, sebelum, sesudah) · `list_active_exclusions` · `month_roster` |
| `src/core/insights.py` (unit) | Tiap fungsi insight: tanpa exclusion (baseline tidak berubah) + dengan 1-2 karyawan dikecualikan (count/agregat turun benar). Re-pakai pola fixture `temp_db_path` + `_add_emp`/`_add_att` yang sudah ada |
| `tests/test_schema.py` (modify) | Assert tabel `outlier_exclusions` ada setelah `init_db` |
| `src/db/coaching.py` (unit) | `list_coaching_for_week` dengan karyawan dikecualikan — tidak muncul di hasil. Tanpa exclusion — baseline tidak berubah |
| Manual smoke | Buka layar Outlier, exclude 2 orang, cek Dashboard + cetakan + Coaching screen angkanya turun; revert; cek angkanya naik lagi |

Target: 131 (baseline v10) + ~15-20 test baru ≈ **~148 passing**.

---

## 8. Implementation Notes

- **Worktree:** sudah di `claude/optimistic-cohen-7d9c88` di atas v10. Tidak perlu rebase.
- **Build & deploy:** pola standar — close .exe, build di worktree, rotate dari main project `dist/HR-Absensi/`. Push sebagai snapshot `v11` saat user authorize.
- **No auto-push** — tunggu instruksi user.
- **Urutan implementasi disarankan:** schema → `src/db/outlier.py` + tests → insights filter + tests → `src/db/coaching.py` filter + tests → Outlier screen → app.py wiring → full test + smoke.

---

## 9. Out of Scope

- Field "Alasan" pengecualian (keputusan user — tidak perlu)
- Catatan transparansi di cetakan (keputusan user — tidak ada)
- Pengecualian per-bulan independen (keputusan user — pakai carry-forward)
- Pengaruh ke Issues / WhatsApp Assistant / Report Generator (sengaja tidak disentuh)
- Bulk exclude (pilih banyak sekaligus lalu exclude) — hanya per-baris + "Revert Semua". Bisa jadi enhancement nanti kalau perlu.

---

## 10. Reference

- **UI mockup (approved):** `.superpowers/brainstorm/696-1778743382/content/01-outlier-screen.html` — rekomendasi utama
- **Sidebar struktur:** [src/ui/app.py](src/ui/app.py) `nav_groups` ~baris 140, `_show()` ~baris 397
- **Schema pattern:** [src/db/schema.py](src/db/schema.py) `DDL` string + `init_db`
- **Insight functions:** [src/core/insights.py](src/core/insights.py)
- **Active month setting:** key `current_month` di tabel `settings`, baca via `get_setting(conn, "current_month")`
