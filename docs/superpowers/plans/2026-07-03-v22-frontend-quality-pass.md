# v22.0.0 — Frontend Quality Pass (P0+P1)

**Tanggal:** 2026-07-03 · **Branch:** `v22.0.0` (fork dari `v21.2.0`) · **Sifat:** refactor + UX hardening, TANPA fitur baru.

Sumber: audit frontend sesi 2026-07-03 (3 agent eksplorasi + review screenshot). Scope disetujui user: item P0 (1-3) + P1 (4-8).

## Sasaran

| # | Item | Hasil yang diharapkan |
|---|------|----------------------|
| P0-1 | Worker thread untuk operasi berat (export fill/generate bulanan/mingguan/preview, parse import) + disable tombol + progress konsisten | UI tidak pernah freeze; tidak ada aksi ganda karena double-click |
| P0-2 | Unifikasi `issues.py` + `severe_lateness.py` → `resolve_base.py` | ~450 baris kembar hilang; satu tempat perbaikan |
| P0-3 | Screen caching di `app.py._show` + protokol `on_show()` | Navigasi instan; scroll/search/minggu terpilih awet; data SELALU di-reload saat show (hindari matriks staleness) |
| P1-4 | Migrasi hex liar → token `theme.py` | Tint semantik (info/warn/success/violet/accent) single-source; palet lokal bernama (`_WA_*`, `_BENTO_*`) boleh tinggal |
| P1-5 | `tkinter.messagebox` → `ui/feedback.py` (dialog gelap) | Satu bahasa visual; error/konfirmasi tidak lagi pop-up putih native |
| P1-6 | Debounce search 200ms + refresh inkremental (issues/severe/heatmap) + throttle resize heatmap | Tidak ada jank per-keystroke |
| P1-7 | Komponen shared: ActiveMonthBanner, EmptyStateCard, FileChip, HistoryList; util periode di `core/week_utils.py` | Duplikasi banner/chip/history/empty & resolver minggu (4×) hilang |
| P1-8 | WhatsApp Assistant pakai `SearchBar`; SQL mentah keluar dari layar UI → lapisan `db/` | Konsistensi perilaku & testability |

## Arsitektur keputusan kunci

- **Threading + SQLite:** `db/connection.get_connection` = context manager per-pemakaian (koneksi fresh). Aturan: worker thread boleh buka koneksinya SENDIRI di dalam thread; koneksi tidak pernah menyeberang thread. Marshaling hasil/progress ke UI via `queue.Queue` + `widget.after` polling (`src/ui/tasks.py::run_bg`).
- **Caching layar:** instance di-cache di `HRApp._screens`; `_show` = grid_remove yang lama → grid yang baru → panggil `on_show()`. Kontrak `on_show()`: selalu re-query data (murah; dashboard sudah memoize via `data_version`), sinkronkan WeekNavBar ke `period_state`.
- **Feedback:** sukses ringan → `toast`; error/warning yang butuh acknowledge → `feedback.show_*`; konfirmasi destruktif → `feedback.ask_yes_no`.

## Urutan eksekusi

1. **Stage 1 — Fondasi** (selesai): `core/week_utils.py` (resolve_period/week_range/parse_week_key/MONTH_NAMES_ID), token theme baru, 5 komponen baru, `feedback.py`, `tasks.py`, tests.
2. **Stage 2 Wave A** (paralel, file disjoint): (a) ResolveScreen unification; (b) Export non-blocking + komponenisasi + SQL→db; (c) Import non-blocking + komponenisasi.
3. **Stage 2 Wave B** (paralel): (d) Heatmap debounce/throttle + token; (e) Dashboard/Coaching/Settings/Holiday/Outlier adopsi util+token+feedback+tree_style; (f) WhatsApp SearchBar+SQL→db+feedback.
4. **Stage 2 Wave C** (main session): screen caching `app.py` + `on_show` di semua layar.
5. **Stage 3 — Release:** changelog v22.0.0 + bump versi + test changelog; full pytest; build installer; rotasi prod 2-level `.bak`; copy ke `Installers/`; smoke; TANPA push (Rule 1).

## Catatan insiden

- Test lama `test_settings_screen_severe_lateness.py` nge-hang suite karena `messagebox.showinfo` native tak dipatch — sudah dipatch (pola sama dengan sibling test). Baseline penuh: **461 passed** setelah Stage 1.
- Baseline pre-v22: 430 tests. Runtime suite penuh ±90 detik.
