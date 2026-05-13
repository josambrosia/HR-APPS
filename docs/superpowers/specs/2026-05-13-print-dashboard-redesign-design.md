# Print Dashboard Redesign — Design Spec

**Tanggal:** 2026-05-13
**Status:** Design locked, ready for implementation plan
**Base branch:** `origin/v6` (fast-forward worktree before implementation)
**Target:** snapshot v7

---

## 1. Goal

Memperbaiki fitur **Print Dashboard** yang punya dua masalah operasional:

1. **Tema cetak rusak.** Dari 5 tema (Default, Editorial, Dark Glass, Infographic, Corporate), hanya `Default` yang berhasil render. 4 tema lain throw error saat dipilih user.
2. **Dialog cetak overflow.** Dialog 620×680 fixed-size, centered pada parent. Pada laptop 1366×768 atau 1536×864 (125% scaling), tombol "Cetak" sering ketutup taskbar — user harus drag jendela ke atas untuk klik.

Sekaligus: refresh konten panel cetak agar lebih actionable dan match konteks pemakaian sehari-hari (single-user HR, weekly fingerprint review).

---

## 2. Current State (v6)

### Print pipeline
- [`src/reports/html_renderer.py`](src/reports/html_renderer.py) — `render_dashboard_html(conn, period, ..., template_name='default')` memilih satu dari 5 Jinja template via `TEMPLATE_NAMES` dict.
- [`src/reports/templates/dashboard.html.j2`](src/reports/templates/dashboard.html.j2) — tema Default, satu-satunya yang berfungsi.
- `dashboard_v1_editorial.html.j2`, `dashboard_v2_dark_glass.html.j2`, `dashboard_v3_infographic.html.j2`, `dashboard_v4_corporate.html.j2` — broken (variable mismatches dengan signature renderer yang sudah berevolusi).
- [`src/ui/components/print_dialog.py`](src/ui/components/print_dialog.py) — `PrintOptionsDialog(parent, on_submit, initial_sections, initial_theme)` modal dengan checkbox sections + radio tema.

### Sections yang tersedia
```python
SECTION_DEFS = [
    ("kpi",          "KPI Cards (Total Terlambat, Hari Absen, Coaching Flag)"),
    ("top5_late",    "Top 5 Paling Terlambat"),
    ("top5_teladan", "Top 5 Karyawan Teladan"),
    ("coaching",     "Butuh Coaching"),
    ("departemen",   "Ranking Departemen"),
    ("hari_rawan",   "Hari Paling Rawan"),
    ("ranking",      "Ranking Keterlambatan Lengkap"),
]
```

### Insight functions (sumber data)
- `terlambat_ranking(conn, start, end)` — ranking lengkap karyawan
- `top_n_terlambat(conn, start, end, n)` — top N late
- `karyawan_teladan_top_n(conn, start, end, n)` — top N teladan
- `coaching_flag(conn, start, end, threshold)` — emp ≥ 240 min
- `ranking_departemen(conn, start, end)` — per-dept stats
- `hari_paling_rawan(conn, start, end)` — per-weekday stats

---

## 3. Design Decisions (Hasil Brainstorm)

### 3.1 Tema cetak: dari 5 jadi 1

**Drop** 4 tema yang broken (Editorial, Dark Glass, Infographic, Corporate). Delete template file-nya — tidak di-archive (YAGNI; kalau nanti perlu, ambil dari git history).

**Replace** `dashboard.html.j2` (tema Default) dengan tema baru bernama **"Light"** — palette JTS (magenta `#EC4899` primary, cyan `#22D3EE` info, violet `#A855F7` secondary, emerald `#10B981` success) pada white background. Font: Segoe UI + Consolas mono. Cocok dicetak di kertas putih A4.

Soft-sell brand JTS hanya muncul di footer: `[jts] josaphat tech solution`.

### 3.2 Panel composition

KPI strip diperbarui menjadi **4 kartu** (sebelumnya 3):

| Kartu | Angka | Insight |
|---|---|---|
| Total Terlambat | count kejadian | volume |
| **Rata-rata Menit/Kejadian** | total ÷ count | severity (NEW) |
| Coaching | emp ≥ 240min | action items |
| **Teladan** | emp hadir penuh tanpa late | recognition (NEW) |

Sections diperbarui:

| Key | Section | Status |
|---|---|---|
| `kpi` | KPI Strip (4 cards) | existing, updated |
| `top5_late` | Top 5 Paling Terlambat | existing |
| `top5_teladan` | Top Karyawan Teladan | existing |
| `coaching` | Butuh Coaching | existing |
| `departemen` | Ranking Departemen | **REMOVED** |
| `hari_rawan` | Hari Paling Rawan | **REMOVED** |
| `pola_jam_masuk` | Pola Jam Masuk | **NEW** |
| `ranking` | Ranking Lengkap (mandatory, page 2) | existing, kolom diperluas |

**Pola Jam Masuk** menggantikan `hari_rawan`+`departemen` karena lebih insightful: distribusi 8-band waktu kedatangan aktual dari sesi present (datang awal / tepat / telat ringan / telat sedang / telat berat / chronic). Memberi cerita "kebanyakan punctual, X% chronic" yang langsung actionable.

**Ranking Lengkap** sekarang wajib di halaman 2, dengan kolom: Rank · Nama · Dept · Menit Terlambat · Kejadian · **Tidak Hadir** (kolom baru — pakai data absent count per emp).

### 3.3 Dialog cetak: Opsi Compact

- **Size:** 560×440 (turun ~35% dari 620×680)
- **Section "TEMA" dihapus** — cuma 1 tema, tidak perlu pilihan
- **Center on screen** (bukan parent): `winfo_screenwidth()//2 - 280`, `winfo_screenheight()//2 - 220`
- **Max-height clamp:** kalau `screen_h - 100 < 440`, kecilkan tinggi dialog supaya tetap fit
- **6 checkbox** section (kpi, top5_late, top5_teladan, coaching, pola_jam_masuk, ranking) + 2 button (Cetak magenta, Batal cyan)
- **Section "ranking" pre-checked dan disabled** — wajib selalu ada (per requirement user)

---

## 4. Component Changes

### 4.1 `src/core/insights.py`

Tambah dua fungsi baru:

```python
def avg_minutes_per_late_event(conn, period_start, period_end) -> float:
    """Returns rata-rata menit terlambat per kejadian (total_min / count).
    Returns 0.0 jika tidak ada late events.
    """

def pola_jam_masuk(conn, period_start, period_end) -> list[dict]:
    """Returns distribusi 8-band waktu kedatangan, urut chronological.
    Hanya count sesi present (masuk IS NOT NULL).
    Bands: <07:45, 07:45-07:59, 08:00, 08:01-08:05, 08:06-08:15,
           08:16-08:30, 08:31-09:00, >09:00
    Returns: [{'band': '<07:45', 'count': int, 'severity': 'early'|'ontime'|'mild'|'mod'|'severe'|'chronic'}]
    """
```

Extend existing `terlambat_ranking(conn, period_start, period_end)` untuk return field tambahan `absent_count` per emp (additive — existing callers cuek). Cara: gabungkan sub-query `SELECT nama, COUNT(*) FROM attendance_records WHERE tipe='Hari Kerja' AND masuk IS NULL AND keluar IS NULL GROUP BY nama` ke existing query via LEFT JOIN, atau hitung di Python layer setelah fetch.

Sort order Ranking Lengkap: `total_terlambat_menit DESC, absent_count DESC, kejadian DESC, nama ASC` (per data exploration — sesuai mockup).

Hapus call-site untuk `ranking_departemen` dan `hari_paling_rawan` dari renderer (fungsi-nya boleh tetap ada di insights.py — dipakai juga oleh dashboard UI, jangan disentuh).

### 4.2 `src/reports/html_renderer.py`

- Hapus `TEMPLATE_NAMES` dict.
- Hapus parameter `template_name` di signature `render_dashboard_html`.
- Hapus computation `dept_rows` dan `day_rows`.
- Tambah computation `avg_min_per_event` dan `pola_jam_masuk_rows`.
- Update `DEFAULT_SECTIONS`:
  ```python
  DEFAULT_SECTIONS = {
      "kpi": True, "top5_late": True, "top5_teladan": True,
      "coaching": True, "pola_jam_masuk": True, "ranking": True,
  }
  ```
- Render selalu pakai `dashboard.html.j2`.

### 4.3 `src/reports/templates/dashboard.html.j2`

**Rewrite total** mengikuti mockup "Tema B Final" (`.superpowers/brainstorm/669-1778670666/content/05-tema-b-final.html`).

Struktur:
- Page 1: header → KPI strip 4 → Top 5 → Teladan+Coaching twocol → Pola Jam Masuk → footer
- Page break (CSS `page-break-before: always`) sebelum Ranking Lengkap
- Page 2: header → Ranking Lengkap 27 emp → footer

Highlight pada Ranking Lengkap:
- Emerald row tint (`#f0fdf4`) untuk emp dengan 0/0/0 (teladan)
- Violet text color (`#a855f7`) untuk kolom "Tidak Hadir" yang ≥ 1

### 4.4 `src/reports/templates/dashboard_v*.html.j2`

**Delete** keempat file ini:
- `dashboard_v1_editorial.html.j2`
- `dashboard_v2_dark_glass.html.j2`
- `dashboard_v3_infographic.html.j2`
- `dashboard_v4_corporate.html.j2`

### 4.5 `src/ui/components/print_dialog.py`

- Hapus konstanta `THEME_DEFS`.
- Hapus parameter `initial_theme` dari `__init__` dan `on_submit` callback signature.
- Hapus pembuatan radio button tema.
- Update `SECTION_DEFS`:
  ```python
  SECTION_DEFS = [
      ("kpi",            "KPI Cards (4 metrik utama)"),
      ("top5_late",      "Top 5 Paling Terlambat"),
      ("top5_teladan",   "Karyawan Teladan"),
      ("coaching",       "Butuh Coaching"),
      ("pola_jam_masuk", "Pola Jam Masuk"),
      ("ranking",        "Ranking Lengkap Karyawan"),
  ]
  ```
- "ranking" checkbox di-disable (always-on) — render dengan `state="disabled"` di CTkCheckBox.
- Update geometry: 560×440, centered on screen, dengan height clamp.
- Update `_on_ok` — `on_submit(sections)` saja (tanpa theme).

### 4.6 `src/ui/screens/dashboard.py`

Update call site `PrintOptionsDialog(...)` dan `render_dashboard_html(...)` — hapus argumen theme.

### 4.7 `tests/test_insights.py`

Tambah test untuk:
- `avg_minutes_per_late_event` — kasus: empty (0.0), single event, multi-event, zero terlambat_menit excluded
- `pola_jam_masuk` — kasus: all 8 bands populated, edge cases (07:45 boundary, 08:00 boundary), absent rows excluded

### 4.8 `tests/test_html_renderer.py`

Update existing:
- Hapus parametrize untuk multiple themes
- Hapus assertion untuk `Ranking Departemen` dan `Hari Paling Rawan` headings
- Tambah assertion untuk `Pola Jam Masuk` heading dan band labels
- Tambah assertion untuk kolom `Tidak Hadir` di ranking lengkap
- Tambah assertion bahwa KPI strip punya 4 cards (cek "Rata-rata" dan "Teladan" labels)

---

## 5. Data Flow

```
DB (attendance_records, employees)
  │
  ▼
insights.py functions:
  - terlambat_ranking()      → ranking lengkap (sekarang include absent_count per emp)
  - top_n_terlambat(5)       → top 5 panel
  - karyawan_teladan_top_n() → teladan panel
  - coaching_flag()          → coaching panel
  - avg_minutes_per_late_event()  [NEW]
  - pola_jam_masuk()              [NEW]
  │
  ▼
render_dashboard_html(conn, period, sections, out_dir)
  - compute total_terlambat (sum of ranking[*].total_terlambat)
  - compute avg_min (= total / count)
  - compute teladan_count (= len of karyawan_teladan filtered to 0/0)
  - render dashboard.html.j2 dengan context lengkap
  │
  ▼
output: out_dir/hr-dashboard-{ts}.html
```

Dialog flow:
```
User klik tombol Cetak di Dashboard
  │
  ▼
PrintOptionsDialog dimunculkan (560×440, center screen)
  - default sections: all True (ranking disabled, always True)
  │
  ▼ user klik "Cetak"
on_submit(sections_dict) callback
  │
  ▼
dashboard.py: render_dashboard_html(conn, period_start, period_end,
                                     period_label, out_dir, sections=sections_dict)
  │
  ▼
File HTML dibuka di default browser via os.startfile() / webbrowser
```

---

## 6. Error Handling

- **Render error** (Jinja undefined variable, dll): catch di `render_dashboard_html`, raise wrapped exception dengan pesan user-friendly. Dashboard caller tampilkan toast error (existing pattern). Sekarang tidak ada lagi "user pilih tema yang broken" — render selalu pakai template valid.
- **Data kosong** (period tanpa data): template menggunakan Jinja `{% if rows %}` guard per panel — tampilkan "Tidak ada data untuk periode ini" placeholder. Halaman 2 (Ranking Lengkap) sama — kalau 0 emp, tampilkan placeholder.
- **Output dir tidak writable**: `out_dir.mkdir(parents=True, exist_ok=True)` akan raise — caller catch dan tampilkan toast.
- **Dialog di-cancel** (Escape / X / Batal button): `on_submit` tidak terpanggil; dashboard tetap di state semula. Existing pattern.

---

## 7. Testing

| Layer | Coverage |
|---|---|
| `pola_jam_masuk` (unit) | All 8 bands · band boundaries (07:45, 08:00) · absent excluded · empty period · single emp |
| `avg_minutes_per_late_event` (unit) | empty → 0.0 · 1 event · many events · zero-late rows excluded |
| `render_dashboard_html` | 4-KPI structure · pola_jam panel present · ranking lengkap punya kolom Tidak Hadir · teladan row tint applied · sections filter (semua on / sebagian off) · period kosong (placeholder) |
| Dialog (smoke manual) | Tampil di tengah layar 1366×768 · semua tombol visible · ranking checkbox disabled · cancel restore state |

Target test count: 120 (baseline v6) − ~3 (theme parametrize dihapus) + ~7 (new tests) ≈ **124 passing**.

---

## 8. Implementation Notes

- **Worktree state:** worktree ini di branch `claude/optimistic-cohen-7d9c88` (forked dari `initial-design`, v1-era). Implementation harus fast-forward dulu: `git merge --ff-only origin/v6`.
- **Build:** standard pyinstaller flow per workflow rule (close .exe → build di worktree → rotate .exe ke main project saat user authorize "deploy").
- **No auto-push:** per workflow rule, push ke origin manual via user instruction.
- **vN snapshot:** wrap sebagai `v7` saat user "bungkus".
- **Smoke test wajib di laptop 1366×768** (atau scaled equivalent) untuk verify dialog tidak overflow.

---

## 9. Out of Scope

- Light mode untuk UI app (bukan untuk print) — separate effort.
- About dialog — separate effort.
- Export PDF langsung (sekarang HTML, user print-to-PDF via browser).
- Multiple themes — kalau nanti perlu, bring back theme picker + tambah template baru. Sekarang YAGNI.
- Conflict resolution toggle (R3 dari Import UX) — separate effort.
- Cross-screen helper extraction — separate effort.

---

## 10. Reference Mockups

- `.superpowers/brainstorm/669-1778670666/content/05-tema-b-final.html` — final Tema B layout (page 1 + page 2)
- `.superpowers/brainstorm/669-1778670666/content/06-dialog-options.html` — dialog size/position comparison

Data sample yang dipakai: `Data Absensi/APRIL/April 13-17.xlsx` (27 emp, 4 dept, 5 hari kerja, 55 late events, 33 absent days).
