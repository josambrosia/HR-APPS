# v25.0.0 — Motion Pass: 17 Animasi Ringan Lintas Aplikasi

**Status:** Design locked (brainstorming 2026-08-20)
**Fork dari:** `v24.0.2`
**Target versi:** `v25.0.0` (tidak ada fitur baru; pengerasan pengalaman + 4 perbaikan cacat)

## 1. Motivasi

Aplikasi saat ini **tidak punya animasi sama sekali**. Satu-satunya elemen yang
bergerak adalah progress bar di splash (`splash.py:150`); seluruh `after()` lain
di basis kode hanyalah debounce, polling `run_bg`, atau `grab_set` tertunda.
Akibatnya setiap perubahan keadaan terjadi dalam satu frame — hover menjeplak,
garis nav aktif hilang lalu muncul di tempat lain, tooltip melompat masuk, dan
daftar tersusun ulang tanpa jejak.

Sebagian dari itu murni soal rasa. Tapi **empat di antaranya adalah cacat nyata**
yang ditemukan saat menyisir kode untuk rilis ini, dan justru itulah yang
memberi versi ini nilai selain kosmetik:

- **Outlier tidak punya umpan balik apa pun.** `outlier.py` tidak memanggil
  `feedback` maupun toast satu kali pun. Saat pegawai dikecualikan, kartunya
  melompat ke seksi lain yang sering di luar viewport, tanpa konfirmasi. Pada
  roster panjang tombolnya terasa rusak.
- **Coaching berkedip tiap toggle.** `coaching.py:106` menghancurkan lalu
  membangun ulang seluruh kartu KPI setiap `_reload()`.
- **Chip "BULAN AKTIF" di sidebar tidak bereaksi saat disorot** meski
  `cursor="hand2"` dan punya binding `<Button-1>` (`app.py:110`) — tidak ada
  yang memberi tahu benda itu bisa diklik.
- **Baris tabel tidak punya state hover.** `tree_style.py:30` hanya memetakan
  `selected`, sehingga tabel Coaching dan Settings yang jelas interaktif tidak
  bereaksi sama sekali terhadap kursor.

## 2. Dasar pengukuran

Seluruh keputusan di dokumen ini berdiri di atas empat kali jalan benchmark di
mesin target (Python 3.13.5 + customtkinter, Windows 11, skala 125%). Angka
adalah median ms per frame **termasuk redraw**.

| Teknik | ms/frame | fps | Dipakai item |
|---|---:|---:|---|
| Toplevel `-alpha` | 0,23 | 4365 | 08 |
| `CTkButton.configure(text)` | 0,36 | 2759 | 11, 18 |
| Root window `-alpha` | 0,41 | 2448 | 12 |
| Canvas `coords()`, 15 bar | 1,74 | 576 | 02, 07, 13 |
| 6× `CTkLabel.configure(text)` | 2,15 | 465 | 03, 19 |
| Canvas sapuan bertahap per kolom | 2,73 | 366 | 05 |
| 1× `CTkFrame.configure(fg_color)` | 2,49 | 401 | 01, 14, 15 |
| Treeview `tag_configure` di-tween | 9,83 | 102 | 10, 16, 17 |
| 20× `CTkLabel.configure(text_color)` | 15,73 | 64 | **ditolak (04)** |
| Canvas 675 sel dipudarkan serentak | 32,54 | 31 | **diganti sapuan** |

**Temuan yang menentukan arsitektur:** Canvas kira-kira **200× lebih murah per
elemen** daripada widget customtkinter — mengubah warna satu widget CTk memakan
~2 ms, mengubah 200 kotak Canvas juga ~2 ms. Konsekuensi langsung: animasi yang
menyentuh banyak elemen **wajib** berjalan di Canvas, dan animasi widget CTk
dibatasi 1–3 widget sekaligus.

Konsekuensi kedua: versi naif "heatmap memudar masuk" gagal di 31 fps. Versi
menyapu-dari-kiri berjalan 366 fps dan tuntas dalam 135 ms — **12× lebih murah
per frame sekaligus 5× lebih cepat selesai**. Versi yang lebih indah kebetulan
juga versi yang lebih cepat; ini bukan kompromi.

## 3. Keputusan terkunci

| # | Keputusan | Nilai |
|---|---|---|
| D1 | Lingkup | 17 animasi (item 01–03, 05–08, 10–19) |
| D2 | Ditolak | 04 (stagger baris panel dashboard — 64 fps, p95 21 ms), 09 (transisi antar layar) |
| D3 | Ditunda | 20 (reorder baris WhatsApp) — butuh mekanisme reorder yang tidak dipakai fitur lain |
| D4 | Pemicu ulang animasi masuk | **Hanya saat data berubah**, dideteksi lewat `RenderSignature` |
| D5 | Sakelar mati | Ada, di Settings; disimpan sebagai setting DB `motion_enabled` (default `1`) |
| D6 | Titik penegakan sakelar | **Di dalam `tween()`**, bukan di 17 pemanggil |
| D7 | Basis waktu | Jam dinding (`time.perf_counter`), bukan hitungan frame |
| D8 | Palet & token | Tidak ada warna baru; hanya token durasi/easing baru di `theme.py` |

### Alasan D2 — kenapa 09 ditolak

Widget Tk **tidak punya kanal alpha sama sekali**; silang-pudar antar layar
mustahil, dan varian gesernya berarti menata ulang tata letak tiap frame.
Lebih menentukan lagi: v24 justru menghabiskan kerja besar membuat perpindahan
layar terasa seketika (9337 ms → 206 ms). Menambahkan 200 ms transisi di sini
membatalkan kerja itu.

## 4. Arsitektur

### 4.1 Modul baru `src/ui/motion.py`

Satu tulang punggung:

```python
tween(widget, duration_ms, on_frame, on_done=None, easing=ease_out_cubic) -> str | None
```

- `on_frame(t)` dipanggil dengan `t` ternormalisasi 0..1 **setelah** easing.
- Progres dihitung dari jam dinding. Di mesin lambat animasi 180 ms tetap
  selesai dalam 180 ms — frame dilewati, durasi tidak melar. Ini yang menjaga
  rasa tetap sama di laptop yang belum pernah diukur.
- Interval target ~16 ms lewat `widget.after`.
- Mengembalikan id tween (untuk pembatalan manual), atau `None` bila motion mati.

Fungsi pendukung: `lerp_hex(a, b, t)`, `ease_out_cubic`, `ease_out_quint`,
`linear`, `enabled()`, `set_enabled(bool)`.

### 4.2 Sakelar mati = satu langkah, bukan satu percabangan

```python
if not enabled():
    on_frame(1.0)
    if on_done:
        on_done()
    return None
```

Seluruh pemanggil ditulis identik tanpa `if`. **Mematikan animasi bukan
melewati kode animasi — melainkan menjalankannya dalam satu langkah.** Inilah
yang membuat D5 tidak menambah 17 percabangan yang harus diuji, dan yang
membuat strategi uji di §6 mungkin.

### 4.3 `RenderSignature` — kapan animasi boleh main ulang

Sejak v22 layar disimpan di cache (`app.py._show()` + kontrak `on_show()`), jadi
tanpa aturan setiap animasi masuk akan main ulang tiap kali user bolak-balik
menu. Rel untuk mendeteksi perubahan **sudah ada**: `SessionDataVersion`
(`src/core/session_state.py:58`), dinaikkan oleh `notify_data_changed()` dan
sudah dipakai Dashboard untuk memoisasi query per `(periode, data_version)`.

```python
class RenderSignature:
    def changed(self, *parts) -> bool:
        """True bila tuple berbeda dari render sebelumnya; menyimpan yang baru."""
```

Hanya layar yang punya animasi masuk yang memegang instance ini — **Dashboard**
(03), **Heatmap** (05), **Rekap Dinas Paparan** (07), dan **Coaching** (19).
Layar lain tidak memerlukannya karena animasinya dipicu interaksi langsung
(hover, klik, aksi), bukan penampilan layar. Berubah → animasikan; sama →
gambar langsung ke keadaan akhir.

Sidik jari per layar:

| Layar | Sidik jari | Sengaja **tidak** termasuk |
|---|---|---|
| Dashboard | `(data_version, current_month, period_key)` | — |
| Heatmap | `(data_version, month, sort_key)` | kata pencarian, ukuran jendela |
| Rekap Dinas | `(data_version, month, span, paparan_span)` | — |
| Coaching | `(data_version, month)` | — |

Untuk Dashboard, tuple ini sama persis dengan kunci memoisasi query yang sudah
dipakai `_update_data()` (`dashboard.py:469`), jadi "animasikan" setara dengan
"cache meleset" — tidak ada keadaan baru yang perlu dipelihara.

**Ini menyelesaikan jebakan heatmap secara struktural.** `heatmap._repaint()`
dipanggil juga oleh `_on_search` (debounce 200 ms), `_on_sort`, dan
`_apply_resize`. Sidik jari heatmap **sengaja tidak memasukkan kata pencarian**:

```python
sig.changed(data_version.get(), self._month, self._sort_key)
```

Mengetik di kotak cari karena itu tidak pernah bisa memicu sapuan — bukan karena
ada `if` yang mencegah, tapi karena menurut definisinya tidak ada yang berubah.
Hal yang sama berlaku untuk resize.

### 4.4 Pembatalan timer

`motion.py` menyimpan `dict[widget_id, set[after_id]]` dan mengikat `<Destroy>`
sekali per widget pemilik. Saat layar dihancurkan seluruh tween-nya dibatalkan
serentak.

**Tanpa `except Exception` yang longgar di jalur ini.** Di v24 justru penangkap
selebar itu yang menyembunyikan tabrakan nama `_draw` pada `CTkFrame` selama
berjam-jam. Yang ditangkap hanya `tk.TclError` pada `after_cancel` (widget sudah
lenyap), dengan komentar yang menyebut alasannya.

### 4.5 Token gerak di `theme.py`

Tidak ada warna baru. Hanya:

```python
MOTION_FAST  = 120   # hover, tint
MOTION_BASE  = 180   # slide indicator, pil segmented
MOTION_SLOW  = 420   # count-up KPI
MOTION_FLASH = 900   # kilat baris
MOTION_WIPE_STEP = 4 # ms per kolom heatmap
MOTION_FADE  = 170   # -alpha jendela
```

## 5. Pemetaan 17 item ke 8 penolong

| Penolong | Item | Berkas tersentuh |
|---|---|---|
| `hover_tint()` | 01, 14, 15 | `app.py`, `tree_style.py`, `import_screen.py` |
| `SlidingIndicator` | 02, 13 | `app.py`, `week_nav.py`, `dinas_recap.py` |
| `count_up()` | 03, 19 | `dashboard.py`, `coaching.py` |
| `wipe_canvas()` / `grow_bar()` | 05, 07 | `heatmap.py`, `dinas_recap.py` |
| `fade_window()` | 08, 12 | `toast.py`, `message_dialog.py`, `app.py` |
| `flash()` | 10, 16, 17 | `resolve_base.py`, `outlier.py`, `history_list.py` |
| `busy_pulse()` | 11, 18 | `tasks.py` (BusyGuard), `export.py`, `settings.py` |
| sorotan sel + tooltip | 06 | `heatmap.py` |

### Catatan per item yang bukan sekadar pemasangan

- **02 `SlidingIndicator`** — garis aktif sekarang di-`pack()`/`pack_forget()`
  ulang di dalam frame item masing-masing (`app.py:309`, `317`, `326`). Supaya
  bisa meluncur, satu garis **tunggal** dipindah ke sidebar dan diposisikan
  dengan `place(y=…)`. Ini refactor kecil, bukan penambahan.
- **16 Outlier** — selain kilat, tambahkan `show_success_toast` mengikuti pola
  `holiday.py:225`. Cacat utamanya adalah ketiadaan konfirmasi; kilat saja tidak
  cukup karena kartu bisa berada di luar viewport.
- **19 Coaching** — perbaikannya adalah **berhenti menghancurkan kartu KPI** dan
  memperbarui teks di tempat (memakai `KPICard.set_value` yang sudah ada), lalu
  `count_up()` di atasnya. Ini menghilangkan kedipan yang sudah ada sekarang;
  animasinya efek samping, bukan tujuan.
- **18 Export/Settings** — `export.py:648` menjalankan dry-run sinkron padahal
  varian non-dry-run di baris 676 sudah memakai `run_bg` + `BusyGuard`; cukup
  disamakan. `settings.py` tidak punya `run_bg`/`BusyGuard`/`ProgressModal` sama
  sekali — dipasangi `BusyGuard` saja.
  **Catatan ukuran:** sisiran sempat melaporkan Backup membekukan aplikasi karena
  menyalin database "ratusan MB". Diverifikasi: database produksi **84 KB**.
  Lubang strukturnya nyata, dampak praktisnya tidak ada. Jangan naikkan ini jadi
  prioritas atas dasar angka yang salah.

## 6. Strategi uji

Karena mematikan animasi berarti melompat ke frame terakhir (§4.2), maka
**dengan motion mati setiap layar wajib tampil persis seperti v24**.

Konsekuensinya tegas: **jika ada satu saja dari 645 tes yang ada sekarang perlu
diubah, itu bukan tes usang — itu tanda animasinya menggeser keadaan akhir,
alias bug.** Tes lama adalah jaring pengaman utama rilis ini, bukan beban.

Lapisan uji baru:

1. **Fungsi murni** — `lerp_hex`, easing, matematika durasi. Tanpa Tk.
2. **Mesin** — `tween()` menjadwalkan; membatalkan saat `<Destroy>`; saat motion
   mati memanggil `on_frame(1.0)` + `on_done()` **tanpa** menjadwalkan timer.
3. **`RenderSignature`** — tuple sama → `changed()` False; termasuk kasus
   heatmap: mengubah kata pencarian **tidak** mengubah sidik jari.
4. **Titik pasang** — dengan motion mati, keadaan akhir tiap layar identik.
5. **Regresi cacat** — 4 cacat di §1 diuji langsung: Outlier memanggil toast;
   Coaching tidak lagi `destroy()` kartu KPI saat toggle; chip bulan aktif punya
   binding `<Enter>`/`<Leave>`; `tree_style` memetakan state hover.

**Isolasi:** motion dimatikan default di test lewat fixture autouse di
`conftest.py`; hanya tes motion yang menyalakannya. Tanpa ini `after()` akan
menyala saat konstruksi layar di ratusan tes dan menghasilkan kegagalan
bergantung-urutan — persis kelas bug `_slow_screens` di v24.

## 7. Batas lingkup

Tidak termasuk rilis ini:

- Item 04, 09 (ditolak, §3), item 20 (ditunda).
- Smooth-scroll di canvas heatmap — easing scroll di Tk cenderung terasa berat
  dan melawan gerakan tangan.
- Mempercantik animasi splash — sudah ada dan hanya tampil sekejap.
- Pola "reveal bertahap daftar" di `active_month.py`, `holiday.py`,
  `import_conflict_dialog.py`, `batch_resolve_dialog.py`. Keempatnya memang
  membangun ulang total, tapi itu callsite berikutnya kalau util-nya sudah
  terbukti — bukan item rilis tersendiri.

## 8. Protokol rilis

Mengikuti CLAUDE.md §1–§2 tanpa pengecualian:

1. Implementasi + commit + `pytest` penuh hijau
2. `python -m tools.build_installer`
3. Rotasi produksi `.exe` 2 level (`data/` tidak pernah ikut dipindah; md5 DB
   diverifikasi tidak berubah)
4. Salin ke `Installers/HR-Absensi-Setup-v25.0.0.exe`
5. Smoke manual — **terhadap salinan data yang realistis**, bukan DB kosong.
   (Pelajaran v24.0.2: smoke dengan DB kosong tidak akan pernah menangkap crash
   pegawai resign.) Untuk rilis ini, smoke harus menyentuh Dashboard, Heatmap,
   Rekap Dinas, dan satu aksi resolve.
6. `APP_CHANGELOG` di `src/config.py` — entri `25.0.0` di paling atas
7. Push **hanya setelah otorisasi eksplisit user** (workflow_rules Rule 1),
   lalu majukan `latest`
8. Perbarui `memory/version_state.md`
