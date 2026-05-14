# HR Profile & Revisi Cetak Dashboard — Design Spec

**Tanggal:** 2026-05-15
**Status:** Design locked — clarifying question selesai, mockup cetak (Variant B) disetujui. Siap implementation plan.
**Base branch:** `claude/trusting-lederberg-6e61bb` — di atas Part A; Part A akan di-wrap jadi snapshot v12.
**Target:** snapshot setelah v12 (v13). Independen dari spec Resolusi Issue — bisa diimplementasi paralel/berurutan.

---

## 1. Goal

Dua hal:

1. **Profil HR User** di menu Settings — field nama + tombol simpan.
2. **Empat revisi cetak Dashboard** — logo JTS (gambar, bukan teks), brand di footer saja, hilangkan path browser di footer, tambah sign-off "HR Officer in Charge" + nama.

Keduanya terhubung: nama profil HR mengisi sign-off cetakan.

---

## 2. Scope

| Surface | Terpengaruh? | Catatan |
|---|---|---|
| `src/ui/screens/settings.py` | ✅ Ya | Tab "Profil" baru di `CTkTabview` |
| `src/db/settings.py` | ⚪ Reuse | `get_setting`/`set_setting` dipakai apa adanya |
| `src/reports/html_renderer.py` | ✅ Ya | Inline SVG lockup + baca `hr_officer_name`, kirim ke template |
| `src/reports/templates/dashboard.html.j2` | ✅ Ya | `@page` margin, footer brand block, sign-off block, CSS |
| `src/config.py` | ⚪ Mungkin | `BRAND_LOCKUP_LIGHT_SVG` sudah ada; tidak ada konstanta baru wajib |
| DB schema | ❌ Tidak | `hr_officer_name` = row K/V di tabel `settings` |
| Dashboard screen / insights | ❌ Tidak | Hanya artefak cetak yang berubah |

---

# FITUR 1 — PROFIL HR USER

## 3. Perilaku

Satu field: nama HR User. Disimpan via K/V store `settings` yang sudah ada. Nama ini muncul di cetakan Dashboard sebagai "HR Officer in Charge".

- **Setting key:** `hr_officer_name` (string). Default `""`.

## 4. Komponen Fitur 1

### 4.1 `src/ui/screens/settings.py` (MODIFY)

`SettingsScreen` saat ini `CTkTabview` dengan tab "General" + "Pegawai". Tambah tab ke-3 **"Profil"**:
- `self.tabs.add("Profil")` + `self._build_profil(self.tabs.tab("Profil"))`.
- `_build_profil(parent)`:
  - Label + entry "Nama" — `CTkEntry` bound ke `StringVar`, di-load dari `get_setting(conn, "hr_officer_name", default="")`.
  - Teks hint (FONT_SMALL, COLOR_TEXT_DIM): "Nama ini muncul di hasil cetak Dashboard sebagai HR Officer in Charge."
  - Tombol "Simpan Profil" — magenta CTA (pola sama "Simpan Pengaturan" di tab General).
- Handler `_save_profil` (atau extend `_save`): `set_setting(conn, "hr_officer_name", value.strip())` + `messagebox.showinfo` sukses.

Pola persis mengikuti `_build_general` yang sudah ada — entry row di dalam frame ber-border + tombol simpan.

### 4.2 Tests

`tests/test_settings*.py` — `hr_officer_name` save/load + default `""`.

---

# FITUR 2 — REVISI CETAK DASHBOARD

Semua di [src/reports/html_renderer.py](src/reports/html_renderer.py) + [src/reports/templates/dashboard.html.j2](src/reports/templates/dashboard.html.j2). Header halaman (`.b-head`) **tidak diubah**.

## 5. Revisi 1 & 2 — Logo JTS di footer

**State sekarang:** brand muncul sebagai TEKS di footer — `.b-footer .jts` berisi `[jts] josaphat tech solution`.

**Target:** ganti teks itu dengan **gambar logo** + teks "Tech Solution" di bawahnya, di footer (Variant B yang disetujui).

### 5.1 `src/reports/html_renderer.py` (MODIFY)

- Baca isi file `BRAND_LOCKUP_LIGHT_SVG` (`assets/brand/lockup-04E-light.svg` — sudah didefinisikan di [src/config.py](src/config.py)).
- Kirim string SVG itu ke context template sebagai variable (mis. `brand_lockup_svg`), dirender dengan `| safe` supaya inline (bukan `<img src=...>`) — print file tetap **self-contained**, tidak ada referensi file eksternal yang putus saat dibuka di browser.
- Kalau file SVG tidak ditemukan → fallback ke teks "josaphat" (jangan sampai render gagal).

### 5.2 `src/reports/templates/dashboard.html.j2` (MODIFY)

- `.b-footer` (dipakai 2× — page 1 & page 2): sisi kanan diganti dari `<span class="jts">[jts] josaphat tech solution</span>` jadi blok brand bertingkat:
  - baris 1: SVG lockup inline (`{{ brand_lockup_svg | safe }}`) — di-scale via CSS ke tinggi wajar footer (mis. ~16-20px).
  - baris 2: teks "Tech Solution" — kecil, muted (`#525252` per palet brand light-bg).
- CSS `.b-footer` disesuaikan: `align-items: flex-end` supaya teks halaman (kiri) sejajar bawah dengan blok brand (kanan). Tambah class untuk blok brand + sizing SVG.

## 6. Revisi 3 — Hilangkan path di footer

**Diagnosis:** baris `file:///C:/Users/…/Temp/hr-dashboard-….html` yang muncul di footer cetakan adalah **header/footer bawaan browser** (Chrome/Edge auto-menambah path, tanggal, judul, nomor halaman saat print) — **bukan** dari template kita. Print HTML dibuka via [src/ui/browser_launcher.py](src/ui/browser_launcher.py) lalu user `Ctrl+P`.

**Fix:** di `dashboard.html.j2` `<style>`, ubah `@page { size:A4; margin:14mm }` → `@page { size:A4; margin:0 }`, dan pindahkan jarak `14mm` jadi padding di `body` / `.doc`. Tanpa ruang margin, Chrome/Edge tidak menggambar header/footer bawaannya — path, tanggal, judul ikut hilang. Baris "page X/2 · confidential" milik template kita tetap ada.

**Catatan (browser-dependent):** perilaku `@page margin:0` menekan header/footer browser adalah trik standar Chrome/Edge tapi bergantung versi/setting browser. Implementasi **harus verifikasi** di browser target. Fallback kalau tidak mempan: instruksi sekali ke user untuk uncheck "Headers and footers" di dialog print. Trade-off diterima: nomor halaman bawaan browser ikut hilang — tidak masalah, template sudah punya "page X/2" sendiri.

## 7. Revisi 4 — Sign-off block

Blok tanda tangan di **bawah halaman 2**, setelah tabel Ranking Lengkap, sebelum `.b-footer` page 2.

### 7.1 `src/reports/html_renderer.py` (MODIFY)

- Baca `hr_officer_name` via `get_setting(conn, "hr_officer_name", default="")`.
- Kirim ke context template.

### 7.2 `src/reports/templates/dashboard.html.j2` (MODIFY)

- Tambah `.b-signoff` block setelah tabel ranking (sebelum footer page 2):
  - Rata kanan (`display:flex; justify-content:flex-end`).
  - Label "HR Officer in Charge" (muted).
  - Ruang tanda tangan (tinggi ~40px kosong).
  - Nama (`{{ hr_officer_name }}`) di atas garis (`border-top`).
- **Selalu dirender** — kalau `hr_officer_name` kosong, baris nama kosong (garis tetap ada, bisa dipakai tanda tangan manual).
- CSS `.b-signoff` ditambahkan ke `<style>`.

---

## 8. Data Flow

```
Settings → tab Profil
  │  Simpan Profil
  ▼
set_setting(conn, "hr_officer_name", nama)  ──►  tabel settings (K/V)
                                                      │
Cetak Dashboard (dashboard.py → render_dashboard_html) │
  │                                                   │
  ├─ baca hr_officer_name  ◄───────────────────────────┘
  ├─ baca + inline lockup-04E-light.svg
  ▼
dashboard.html.j2 render:
  • footer  → SVG lockup + "Tech Solution"  (ganti teks lama)
  • @page   → margin 0  (tekan header/footer browser → path hilang)
  • page 2  → .b-signoff: "HR Officer in Charge" + nama
  ▼
hr-dashboard-{ts}.html  →  browser_launcher  →  print
```

---

## 9. Error Handling & Edge Cases

- **`hr_officer_name` belum di-set** → sign-off render label + garis kosong (dipakai tanda tangan manual). Tidak error.
- **File SVG lockup tidak ada** → `html_renderer` fallback ke teks "josaphat" — render tidak boleh gagal.
- **`@page margin:0` tidak menekan footer browser di versi browser tertentu** → fallback instruksi manual (uncheck "Headers and footers"). Implementasi verifikasi dulu.
- **Nama HR sangat panjang** → blok sign-off `min-width` + teks wrap wajar; tidak merusak layout.
- **Margin `@page` 0 + padding body** → pastikan konten tidak terpotong di tepi kertas — padding `body`/`.doc` harus menggantikan persis `14mm` yang hilang.

---

## 10. Testing

| Layer | Coverage |
|---|---|
| `tests/test_settings*.py` (MODIFY/NEW) | `hr_officer_name` save/load + default `""` |
| `tests/test_html_renderer.py` (MODIFY) | Output HTML memuat nama HR di blok sign-off · memuat SVG lockup inline (bukan `<img>`) · sign-off tetap render saat nama kosong · `@page` margin 0 di `<style>` · fallback teks saat SVG tidak ada |
| Manual smoke | Set nama di Settings → Profil · cetak Dashboard → cek logo di footer + "Tech Solution" · cek sign-off "HR Officer in Charge" + nama di bawah page 2 · `Ctrl+P` di Chrome/Edge → cek path browser hilang · cek konten tidak terpotong di tepi |

Target: 194 (baseline) + ~10-15 test baru ≈ **~205-210 passing**. (Kalau spec Resolusi Issue diimplementasi lebih dulu, baseline naik — sesuaikan.)

---

## 11. Implementation Notes

**Urutan disarankan:**
1. Fitur 1 — `settings.py` tab Profil + setting `hr_officer_name` + tests.
2. Revisi 4 (sign-off) — `html_renderer.py` baca nama + `.b-signoff` di template + tests. (Butuh Fitur 1.)
3. Revisi 1&2 (logo footer) — inline SVG di `html_renderer.py` + footer brand block di template.
4. Revisi 3 (path) — `@page` margin + body padding. Verifikasi manual di browser.
5. Full `pytest -q` + manual smoke cetak.

- **Worktree:** branch `claude/trusting-lederberg-6e61bb`. Tidak perlu rebase.
- **Independen dari spec Resolusi Issue** — satu-satunya file beririsan: `settings.py` (spec ini tambah tab Profil; spec Resolusi Issue tambah baris di tab General — tidak konflik) dan `config.py` (konstanta beda). Kalau diimplementasi paralel oleh agent berbeda, merge trivial; berurutan menghindari itu sama sekali.
- **No auto-push** — tunggu instruksi user.

---

## 12. Keputusan Desain (dari brainstorm — untuk review cepat)

1. **Profil = nama saja** — bukan nama+jabatan, bukan nama+jabatan+NIP. Label peran ("HR Officer in Charge") tetap, hanya nama yang variabel.
2. **Logo di footer (Variant B)** — bukan header. Header halaman tidak diubah.
3. **"Tech Solution" sebagai baris teks** di bawah lockup "josaphat" — melengkapi nama brand.
4. **Label sign-off: "HR Officer in Charge"** (Inggris) — padanan terdekat "Penanggung Jawab", terbaca profesional.
5. **Path di footer = footer bawaan browser** — fix via `@page margin:0`, bukan edit konten template.
6. **Sign-off selalu dirender** — garis kosong kalau profil belum diisi (bisa untuk tanda tangan manual).
7. **SVG di-inline** ke HTML — print file self-contained.

---

## 13. Out of Scope

- Field profil lain (jabatan, NIP, foto, kontak).
- Logo di header halaman (dipilih footer).
- Logo/brand di body halaman (eksplisit dilarang user — header/footer saja).
- Generate PDF langsung (tetap HTML → print via browser).
- Mengubah tema/warna/layout cetakan selain 4 revisi ini.
- Tanda tangan digital / QR.

---

## 14. Reference

- **Mockup cetak (disetujui):** `.superpowers/brainstorm/729-1778786820/content/print-revision.html` + `print-revision-v2.html` (Variant B refined — "Tech Solution" di bawah lockup).
- **Brand asset:** `assets/brand/lockup-04E-light.svg` (lockup white-bg), `assets/brand/README.md` (palet: teks light-bg `#0A0A0A`, accent `#EC4899`, tagline light-bg `#525252`).
- **Template cetak existing:** [src/reports/templates/dashboard.html.j2](src/reports/templates/dashboard.html.j2) — `.b-head`, `.b-footer .jts`, `@page`.
- **Renderer:** [src/reports/html_renderer.py](src/reports/html_renderer.py) — `render_dashboard_html`, `tmpl.render(...)` context.
- **Settings pattern:** `_build_general` / `_save` di [src/ui/screens/settings.py](src/ui/screens/settings.py); K/V via [src/db/settings.py](src/db/settings.py).
- **Launcher:** [src/ui/browser_launcher.py](src/ui/browser_launcher.py).
