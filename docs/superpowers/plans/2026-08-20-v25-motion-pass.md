# v25.0.0 Motion Pass — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Menambahkan 17 animasi ringan ke aplikasi yang saat ini tidak punya animasi sama sekali, lewat satu mesin terpusat, sekaligus menutup 4 cacat umpan-balik yang ditemukan saat menyisir kode.

**Architecture:** Satu modul `src/ui/motion.py` menyediakan `tween()` berbasis jam dinding, registry pembatalan per-widget, dan 8 penolong tingkat tinggi. Sakelar mati ditegakkan **di dalam `tween()`** (melompat ke frame terakhir), sehingga tidak ada percabangan di 17 pemanggil dan seluruh 645 tes lama tetap berlaku tanpa perubahan. Animasi masuk hanya dipicu saat data berubah, dideteksi lewat `RenderSignature` yang menumpang `SessionDataVersion` yang sudah ada.

**Tech Stack:** Python 3.13.5, customtkinter, tkinter Canvas, pytest.

**Spec:** `docs/superpowers/specs/2026-08-20-v25-motion-pass-design.md`

**Perintah dasar (dari root proyek):**
```bash
.venv/Scripts/python.exe -m pytest -q            # suite penuh (~2 menit)
.venv/Scripts/python.exe -m pytest tests/test_motion.py -v
```

---

## Prasyarat: Buat branch

- [ ] **Step 1: Fork branch dari v24.0.2**

```bash
git checkout -b v25.0.0
git branch --show-current   # harus: v25.0.0
```

---

## Task 1: Fungsi murni — interpolasi warna & easing

**Files:**
- Create: `src/ui/motion.py`
- Test: `tests/test_motion.py`

- [ ] **Step 1: Tulis tes yang gagal**

```python
# tests/test_motion.py
"""Mesin animasi v25 — fungsi murni, tween, registry pembatalan."""
import pytest

from src.ui import motion


class TestLerpHex:
    def test_t_nol_mengembalikan_warna_awal(self):
        assert motion.lerp_hex("#000000", "#FFFFFF", 0.0) == "#000000"

    def test_t_satu_mengembalikan_warna_akhir(self):
        assert motion.lerp_hex("#000000", "#FFFFFF", 1.0) == "#FFFFFF"

    def test_titik_tengah_dibulatkan_konsisten(self):
        assert motion.lerp_hex("#000000", "#FFFFFF", 0.5) == "#7F7F7F"

    def test_menangani_warna_asli_aplikasi(self):
        # COLOR_BG -> COLOR_SURFACE_HIGH, dipakai hover nav
        assert motion.lerp_hex("#0A0A0A", "#1F1F1F", 1.0) == "#1F1F1F"

    def test_t_diluar_rentang_dijepit(self):
        assert motion.lerp_hex("#000000", "#FFFFFF", -3.0) == "#000000"
        assert motion.lerp_hex("#000000", "#FFFFFF", 9.0) == "#FFFFFF"

    def test_menolak_bentuk_singkat_tiga_digit(self):
        # Tk menerima #FFF, tapi lerp kita tidak — gagal keras, jangan diam-diam salah.
        with pytest.raises(ValueError):
            motion.lerp_hex("#FFF", "#000000", 0.5)


class TestEasing:
    @pytest.mark.parametrize("fn", [motion.linear, motion.ease_out_cubic,
                                    motion.ease_out_quint])
    def test_semua_easing_terikat_di_ujung(self, fn):
        assert fn(0.0) == pytest.approx(0.0)
        assert fn(1.0) == pytest.approx(1.0)

    def test_ease_out_mendahului_linear_di_tengah(self):
        assert motion.ease_out_cubic(0.5) > motion.linear(0.5)

    @pytest.mark.parametrize("fn", [motion.linear, motion.ease_out_cubic,
                                    motion.ease_out_quint])
    def test_semua_easing_monoton_naik(self, fn):
        vals = [fn(i / 20) for i in range(21)]
        assert all(b >= a for a, b in zip(vals, vals[1:]))
```

- [ ] **Step 2: Jalankan tes, pastikan GAGAL**

Run: `.venv/Scripts/python.exe -m pytest tests/test_motion.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.ui.motion'`

- [ ] **Step 3: Tulis implementasi minimal**

```python
# src/ui/motion.py
"""Mesin animasi terpusat — v25 Motion Pass.

Aplikasi ini berjalan di Tk, yang tidak punya kanal alpha pada widget,
tidak punya transform, dan tidak punya compositor. Yang bisa dianimasikan
hanya: warna (interpolasi), geometri (place/coords), teks, dan alpha pada
Toplevel/root (khusus Windows).

Pengukuran yang mendasari modul ini (mesin target, median ms per frame
termasuk redraw):

    Toplevel -alpha                      0,23 ms   4365 fps
    CTkButton.configure(text)            0,36 ms   2759 fps
    Canvas coords(), 15 bar              1,74 ms    576 fps
    CTkFrame.configure(fg_color)         2,49 ms    401 fps
    Canvas sapuan bertahap per kolom     2,73 ms    366 fps
    Treeview tag_configure di-tween      9,83 ms    102 fps
    20x CTkLabel.configure(text_color)  15,73 ms     64 fps  <- terlalu berat
    675 sel Canvas dipudarkan serentak  32,54 ms     31 fps  <- terlalu berat

Aturan yang lahir dari angka itu: Canvas ~200x lebih murah per elemen
daripada widget customtkinter. Animasi yang menyentuh banyak elemen WAJIB
berjalan di Canvas; animasi widget CTk dibatasi 1-3 widget sekaligus.
"""
from __future__ import annotations


# ─────────────────────────────────────────────── interpolasi warna

def _parse_hex(value: str) -> tuple[int, int, int]:
    """'#RRGGBB' -> (r, g, b). Bentuk singkat 3-digit ditolak keras."""
    if not isinstance(value, str) or len(value) != 7 or value[0] != "#":
        raise ValueError(f"butuh warna '#RRGGBB', dapat {value!r}")
    try:
        return (int(value[1:3], 16), int(value[3:5], 16), int(value[5:7], 16))
    except ValueError as exc:
        raise ValueError(f"warna tidak valid: {value!r}") from exc


def lerp_hex(start: str, end: str, t: float) -> str:
    """Interpolasi dua warna '#RRGGBB'. `t` dijepit ke 0..1."""
    t = 0.0 if t < 0.0 else (1.0 if t > 1.0 else t)
    a = _parse_hex(start)
    b = _parse_hex(end)
    return "#%02X%02X%02X" % tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


# ─────────────────────────────────────────────── easing

def linear(t: float) -> float:
    return t


def ease_out_cubic(t: float) -> float:
    """Cepat di awal, melambat di akhir. Default untuk gerakan masuk."""
    return 1.0 - (1.0 - t) ** 3


def ease_out_quint(t: float) -> float:
    """Lebih tegas daripada cubic — untuk gerakan yang harus terasa 'mendarat'."""
    return 1.0 - (1.0 - t) ** 5
```

- [ ] **Step 4: Jalankan tes, pastikan LULUS**

Run: `.venv/Scripts/python.exe -m pytest tests/test_motion.py -v`
Expected: PASS (13 tes)

- [ ] **Step 5: Commit**

```bash
git add src/ui/motion.py tests/test_motion.py
git commit -m "feat(v25): motion.py — interpolasi warna + easing"
```

---

## Task 2: Sakelar aktif/mati

**Files:**
- Modify: `src/ui/motion.py`
- Modify: `tests/test_motion.py`

Sakelar ditegakkan di dalam `tween()` (Task 3). Task ini hanya menyiapkan
state global-nya, yang dibaca dari DB sekali saat startup.

- [ ] **Step 1: Tulis tes yang gagal**

Tambahkan ke `tests/test_motion.py`:

```python
class TestEnabledFlag:
    def test_default_aktif(self):
        motion.set_enabled(True)
        assert motion.enabled() is True

    def test_bisa_dimatikan_dan_dinyalakan(self):
        motion.set_enabled(False)
        assert motion.enabled() is False
        motion.set_enabled(True)
        assert motion.enabled() is True

    def test_memuat_dari_setting_string(self, tmp_path):
        from src.db.schema import init_db
        from src.db.connection import get_connection
        from src.db.settings import set_setting

        p = tmp_path / "hr.db"
        init_db(p)
        with get_connection(p) as conn:
            set_setting(conn, "motion_enabled", "0")
        with get_connection(p) as conn:
            motion.load_enabled_from_db(conn)
        assert motion.enabled() is False

    def test_setting_belum_ada_berarti_aktif(self, tmp_path):
        from src.db.schema import init_db
        from src.db.connection import get_connection

        p = tmp_path / "hr.db"
        init_db(p)
        motion.set_enabled(False)          # pastikan benar-benar berubah
        with get_connection(p) as conn:
            motion.load_enabled_from_db(conn)
        assert motion.enabled() is True
```

- [ ] **Step 2: Jalankan tes, pastikan GAGAL**

Run: `.venv/Scripts/python.exe -m pytest tests/test_motion.py::TestEnabledFlag -v`
Expected: FAIL — `AttributeError: module 'src.ui.motion' has no attribute 'set_enabled'`

- [ ] **Step 3: Tulis implementasi**

Tambahkan ke `src/ui/motion.py`:

```python
# ─────────────────────────────────────────────── sakelar aktif/mati

SETTING_KEY = "motion_enabled"

_enabled: bool = True


def enabled() -> bool:
    return _enabled


def set_enabled(value: bool) -> None:
    """Dipakai layar Settings dan fixture test. Berlaku seketika untuk
    animasi BERIKUTNYA; tween yang sedang jalan dibiarkan selesai."""
    global _enabled
    _enabled = bool(value)


def load_enabled_from_db(conn) -> None:
    """Baca preferensi dari tabel settings. Nilai selain '0' berarti aktif,
    termasuk saat key-nya belum pernah ditulis."""
    from src.db.settings import get_setting
    set_enabled(get_setting(conn, SETTING_KEY, default="1") != "0")
```

- [ ] **Step 4: Jalankan tes, pastikan LULUS**

Run: `.venv/Scripts/python.exe -m pytest tests/test_motion.py -v`
Expected: PASS (17 tes)

- [ ] **Step 5: Commit**

```bash
git add src/ui/motion.py tests/test_motion.py
git commit -m "feat(v25): motion — sakelar aktif/mati + pembacaan dari settings"
```

---

## Task 3: `tween()` + registry pembatalan

Inti rilis ini. Dua sifat yang tidak boleh hilang:

1. **Progres dari jam dinding, bukan hitungan frame.** Di mesin lambat animasi
   180 ms tetap selesai dalam 180 ms — frame dilewati, durasi tidak melar.
2. **Saat motion mati, `tween()` tidak menjadwalkan timer sama sekali** —
   langsung `on_frame(1.0)` lalu `on_done()`. Inilah yang membuat seluruh 645
   tes lama tetap berlaku tanpa diubah.

**Files:**
- Modify: `src/ui/motion.py`
- Modify: `tests/test_motion.py`

- [ ] **Step 1: Tulis tes yang gagal**

```python
class TestTweenDimatikan:
    def test_langsung_ke_frame_terakhir_tanpa_timer(self, tk_root):
        motion.set_enabled(False)
        seen = []
        done = []
        job = motion.tween(tk_root, 500, seen.append, on_done=lambda: done.append(1))
        assert job is None            # tidak ada timer yang dijadwalkan
        assert seen == [1.0]          # tepat satu frame: keadaan akhir
        assert done == [1]


class TestTweenAktif:
    def test_menjadwalkan_dan_akhirnya_mencapai_satu(self, tk_root):
        motion.set_enabled(True)
        seen = []
        done = []
        motion.tween(tk_root, 60, seen.append, on_done=lambda: done.append(1),
                     easing=motion.linear)
        # pompa event loop sampai selesai (batas aman 3 detik)
        import time
        t0 = time.perf_counter()
        while not done and time.perf_counter() - t0 < 3.0:
            tk_root.update()
        assert done == [1], "tween tidak pernah selesai"
        assert seen[-1] == 1.0, "frame terakhir harus tepat 1.0"
        assert seen[0] < 1.0, "harus ada frame antara, bukan langsung selesai"
        assert all(b >= a for a, b in zip(seen, seen[1:])), "progres harus monoton"

    def test_durasi_nol_langsung_selesai(self, tk_root):
        motion.set_enabled(True)
        seen = []
        motion.tween(tk_root, 0, seen.append)
        assert seen == [1.0]


class TestPembatalan:
    def test_cancel_for_menghentikan_tween_berjalan(self, tk_root):
        motion.set_enabled(True)
        seen = []
        motion.tween(tk_root, 2000, seen.append)
        tk_root.update()
        motion.cancel_for(tk_root)
        n = len(seen)
        for _ in range(5):
            tk_root.update()
        assert len(seen) == n, "tween masih berjalan setelah dibatalkan"
        assert 1.0 not in seen, "tween yang dibatalkan tidak boleh memaksa frame akhir"

    def test_widget_dihancurkan_membatalkan_tween_nya(self, tk_root):
        import customtkinter as ctk
        motion.set_enabled(True)
        child = ctk.CTkFrame(tk_root)
        seen = []
        motion.tween(child, 2000, seen.append)
        tk_root.update()
        child.destroy()
        tk_root.update()
        assert motion.active_count() == 0, "registry bocor setelah widget dihancurkan"

    def test_registry_bersih_setelah_tween_selesai_wajar(self, tk_root):
        import time
        motion.set_enabled(True)
        done = []
        motion.tween(tk_root, 40, lambda t: None, on_done=lambda: done.append(1))
        t0 = time.perf_counter()
        while not done and time.perf_counter() - t0 < 3.0:
            tk_root.update()
        assert motion.active_count() == 0
```

- [ ] **Step 2: Jalankan tes, pastikan GAGAL**

Run: `.venv/Scripts/python.exe -m pytest tests/test_motion.py::TestTweenDimatikan -v`
Expected: FAIL — `AttributeError: module 'src.ui.motion' has no attribute 'tween'`

- [ ] **Step 3: Tulis implementasi**

Tambahkan ke `src/ui/motion.py` (impor `time` dan `tkinter as tk` di atas berkas):

```python
import time
import tkinter as tk
from typing import Callable, Optional

# ─────────────────────────────────────────────── registry tween aktif

# key = id(widget) -> set[after_id]. Dipakai untuk membatalkan seluruh
# animasi milik satu widget saat widget itu dihancurkan.
_jobs: dict[int, set[str]] = {}
# widget yang sudah dipasangi binding <Destroy>, supaya tidak dipasang dua kali
_bound: set[int] = set()

_FRAME_MS = 16          # ~60 fps; jam dinding yang menentukan, ini hanya laju polling


def active_count() -> int:
    """Jumlah tween yang sedang berjalan. Untuk tes kebocoran registry."""
    return sum(len(s) for s in _jobs.values())


def _register(widget, job_id: str) -> None:
    key = id(widget)
    _jobs.setdefault(key, set()).add(job_id)
    if key not in _bound:
        _bound.add(key)
        widget.bind("<Destroy>", lambda _e, w=widget: _on_destroy(w), add="+")


def _forget(widget, job_id: str) -> None:
    jobs = _jobs.get(id(widget))
    if jobs is not None:
        jobs.discard(job_id)
        if not jobs:
            _jobs.pop(id(widget), None)


def _on_destroy(widget) -> None:
    cancel_for(widget)
    _bound.discard(id(widget))


def cancel_for(widget) -> None:
    """Batalkan seluruh tween milik `widget`. Frame akhir TIDAK dipaksakan —
    pembatalan berarti berhenti di tempat, bukan melompat ke ujung."""
    for job_id in _jobs.pop(id(widget), set()):
        try:
            widget.after_cancel(job_id)
        except tk.TclError:
            # Widget sudah lenyap bersama seluruh timernya. Ini satu-satunya
            # pengecualian yang ditangkap di jalur ini — JANGAN dilebarkan jadi
            # `except Exception`. Di v24 penangkap selebar itu menyembunyikan
            # tabrakan nama _draw pada CTkFrame selama berjam-jam.
            pass


# ─────────────────────────────────────────────── tween

def tween(
    widget,
    duration_ms: int,
    on_frame: Callable[[float], None],
    on_done: Optional[Callable[[], None]] = None,
    easing: Callable[[float], float] = ease_out_cubic,
) -> Optional[str]:
    """Animasikan `on_frame(t)` dari 0 ke 1 selama `duration_ms`.

    `t` sudah melewati `easing`. Frame terakhir dijamin tepat 1.0, sehingga
    keadaan akhir tidak pernah bergantung pada waktu kedatangan frame.

    Saat motion mati (atau durasi <= 0): tidak ada timer sama sekali —
    `on_frame(1.0)` lalu `on_done()` dipanggil langsung. Ini yang membuat
    setiap pemanggil bisa ditulis tanpa percabangan, dan yang membuat
    keadaan akhir identik dengan v24.

    Mengembalikan id timer pertama, atau None bila berjalan seketika.
    """
    if not _enabled or duration_ms <= 0:
        on_frame(1.0)
        if on_done is not None:
            on_done()
        return None

    start = time.perf_counter()
    holder: dict[str, Optional[str]] = {"job": None}

    def step() -> None:
        if holder["job"] is not None:
            _forget(widget, holder["job"])
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        raw = elapsed_ms / duration_ms
        if raw >= 1.0:
            on_frame(1.0)
            if on_done is not None:
                on_done()
            return
        on_frame(easing(raw))
        job = widget.after(_FRAME_MS, step)
        holder["job"] = job
        _register(widget, job)

    first = widget.after(_FRAME_MS, step)
    holder["job"] = first
    _register(widget, first)
    return first
```

- [ ] **Step 4: Jalankan tes, pastikan LULUS**

Run: `.venv/Scripts/python.exe -m pytest tests/test_motion.py -v`
Expected: PASS (23 tes)

- [ ] **Step 5: Commit**

```bash
git add src/ui/motion.py tests/test_motion.py
git commit -m "feat(v25): motion.tween — basis jam dinding + registry pembatalan"
```

---

## Task 4: Fixture autouse — motion mati di seluruh tes

Tanpa ini, `after()` akan menyala saat konstruksi layar di ratusan tes dan
menghasilkan kegagalan bergantung-urutan — persis kelas bug `_slow_screens`
di v24.

**Files:**
- Modify: `tests/conftest.py`
- Modify: `tests/test_motion.py`

- [ ] **Step 1: Tambahkan fixture ke conftest**

Tambahkan di akhir `tests/conftest.py`:

```python
@pytest.fixture(autouse=True)
def disable_motion():
    """Matikan animasi di SELURUH tes secara default.

    Dua alasan. Pertama, tanpa ini setiap konstruksi layar menjadwalkan
    after() yang menyala di tes lain dan bikin kegagalan bergantung-urutan.
    Kedua — dan ini yang penting — dengan motion mati setiap layar wajib
    tampil persis seperti v24. Kalau ada tes lama yang butuh diubah, itu
    bukan tes usang: itu tanda animasinya menggeser keadaan akhir.

    Tes motion sendiri menyalakannya lewat motion.set_enabled(True).
    """
    from src.ui import motion
    motion.set_enabled(False)
    yield
    motion.set_enabled(False)
```

- [ ] **Step 2: Buat tes motion menyalakan sendiri**

Di `tests/test_motion.py`, tambahkan di paling atas setelah impor:

```python
@pytest.fixture(autouse=True)
def motion_on():
    """Tes di berkas ini menguji mesinnya, jadi harus menyala. Berjalan
    SETELAH fixture disable_motion di conftest (autouse berkas lebih dalam
    dieksekusi belakangan), sehingga menang."""
    motion.set_enabled(True)
    yield
    motion.set_enabled(False)
```

Lalu **hapus** baris `motion.set_enabled(True)` yang redundan di dalam
`TestTweenAktif` dan `TestPembatalan` (fixture sudah menanganinya).
Baris `motion.set_enabled(False)` di `TestTweenDimatikan` dan
`TestEnabledFlag` **tetap dipertahankan** — itu memang bagian dari yang diuji.

- [ ] **Step 3: Jalankan suite penuh**

Run: `.venv/Scripts/python.exe -m pytest -q`
Expected: PASS — **645 tes lama + tes motion baru, nol yang diubah**

> **Gerbang mutu:** kalau ada tes lama yang gagal di sini, JANGAN diubah.
> Cari tahu kenapa keadaan akhirnya bergeser. Itu bug, bukan tes usang.

- [ ] **Step 4: Commit**

```bash
git add tests/conftest.py tests/test_motion.py
git commit -m "test(v25): matikan motion default di seluruh tes"
```

---

## Task 5: `RenderSignature` — kapan animasi masuk boleh main ulang

**Files:**
- Modify: `src/ui/motion.py`
- Modify: `tests/test_motion.py`

- [ ] **Step 1: Tulis tes yang gagal**

```python
class TestRenderSignature:
    def test_render_pertama_selalu_dianggap_berubah(self):
        sig = motion.RenderSignature()
        assert sig.changed(1, "2026-07") is True

    def test_tuple_sama_berarti_tidak_berubah(self):
        sig = motion.RenderSignature()
        sig.changed(1, "2026-07")
        assert sig.changed(1, "2026-07") is False

    def test_satu_bagian_berubah_sudah_cukup(self):
        sig = motion.RenderSignature()
        sig.changed(1, "2026-07")
        assert sig.changed(2, "2026-07") is True

    def test_kembali_ke_nilai_lama_tetap_dihitung_berubah(self):
        sig = motion.RenderSignature()
        sig.changed(1, "2026-07")
        sig.changed(1, "2026-08")
        assert sig.changed(1, "2026-07") is True

    def test_kata_pencarian_heatmap_sengaja_diluar_sidik_jari(self):
        """Regresi jebakan #1: heatmap._repaint() juga dipanggil oleh
        _on_search. Sidik jari heatmap TIDAK memuat kata pencarian, jadi
        mengetik tidak akan pernah bisa memicu sapuan ulang."""
        sig = motion.RenderSignature()
        data_version, month, sort_key = 3, "2026-07", "nama"
        assert sig.changed(data_version, month, sort_key) is True
        # user mengetik di kotak cari — tidak ada bagian sidik jari yang berubah
        assert sig.changed(data_version, month, sort_key) is False
```

- [ ] **Step 2: Jalankan tes, pastikan GAGAL**

Run: `.venv/Scripts/python.exe -m pytest tests/test_motion.py::TestRenderSignature -v`
Expected: FAIL — `AttributeError: module 'src.ui.motion' has no attribute 'RenderSignature'`

- [ ] **Step 3: Tulis implementasi**

```python
# ─────────────────────────────────────────────── kapan boleh main ulang

_UNSET = object()


class RenderSignature:
    """Menjawab satu pertanyaan: 'apakah yang tampil sekarang berbeda dari
    render sebelumnya?'

    Sejak v22 layar disimpan di cache (app.py._show + kontrak on_show), jadi
    tanpa aturan setiap animasi masuk akan main ulang tiap kali user bolak-
    balik menu. Setelah kesepuluh kalinya, 'hidup' berubah jadi 'mengganggu'.

    Apa yang TIDAK dimasukkan ke sidik jari sama pentingnya dengan apa yang
    dimasukkan. Heatmap sengaja tidak memasukkan kata pencarian dan ukuran
    jendela, sehingga mengetik atau resize tidak pernah bisa memicu sapuan —
    bukan karena ada `if` yang mencegah, tapi karena menurut definisinya
    tidak ada yang berubah.
    """

    __slots__ = ("_last",)

    def __init__(self):
        self._last = _UNSET

    def changed(self, *parts) -> bool:
        if self._last is _UNSET or self._last != parts:
            self._last = parts
            return True
        return False

    def reset(self) -> None:
        """Paksa render berikutnya dianggap berubah."""
        self._last = _UNSET
```

- [ ] **Step 4: Jalankan tes, pastikan LULUS**

Run: `.venv/Scripts/python.exe -m pytest tests/test_motion.py -v`
Expected: PASS (28 tes)

- [ ] **Step 5: Commit**

```bash
git add src/ui/motion.py tests/test_motion.py
git commit -m "feat(v25): RenderSignature — animasi masuk hanya saat data berubah"
```

---

## Task 6: Token gerak di `theme.py`

**Files:**
- Modify: `src/ui/theme.py`
- Test: `tests/test_motion_tokens.py`

- [ ] **Step 1: Tulis tes yang gagal**

```python
# tests/test_motion_tokens.py
"""Token durasi gerak — dipusatkan supaya rasa aplikasi bisa disetel di satu tempat."""
from src.ui import theme


def test_semua_token_gerak_ada_dan_masuk_akal():
    for name in ("MOTION_FAST", "MOTION_BASE", "MOTION_SLOW",
                 "MOTION_FLASH", "MOTION_FADE", "MOTION_WIPE_STEP"):
        val = getattr(theme, name)
        assert isinstance(val, int), f"{name} harus int"
        assert 0 < val <= 1000, f"{name} di luar rentang wajar: {val}"


def test_urutan_durasi_konsisten():
    assert theme.MOTION_FAST < theme.MOTION_BASE < theme.MOTION_SLOW
    assert theme.MOTION_SLOW < theme.MOTION_FLASH


def test_langkah_sapuan_cukup_kecil_untuk_terasa_menyapu():
    """31 kolom x MOTION_WIPE_STEP harus selesai di bawah 200 ms, sesuai
    hasil ukur 135 ms. Lebih lambat dari itu terasa seret."""
    assert 31 * theme.MOTION_WIPE_STEP < 200
```

- [ ] **Step 2: Jalankan tes, pastikan GAGAL**

Run: `.venv/Scripts/python.exe -m pytest tests/test_motion_tokens.py -v`
Expected: FAIL — `AttributeError: module 'src.ui.theme' has no attribute 'MOTION_FAST'`

- [ ] **Step 3: Tulis implementasi**

Tambahkan di akhir `src/ui/theme.py`:

```python
# === MOTION (v25) — durasi dalam milidetik ===
# Dipusatkan supaya rasa gerak seluruh aplikasi bisa disetel di satu tempat.
# Nilai dipilih dari hasil ukur di mesin target; lihat docstring src/ui/motion.py.
MOTION_FAST      = 120   # hover, tint — harus lebih cepat dari niat sadar
MOTION_BASE      = 180   # garis nav meluncur, pil segmented
MOTION_SLOW      = 420   # hitung-naik angka KPI
MOTION_FLASH     = 900   # kilat baris yang baru berubah
MOTION_FADE      = 170   # -alpha jendela (toast, dialog, jendela utama)
MOTION_WIPE_STEP = 4     # ms per kolom sapuan heatmap (31 kolom -> ~135 ms)
```

- [ ] **Step 4: Jalankan tes, pastikan LULUS**

Run: `.venv/Scripts/python.exe -m pytest tests/test_motion_tokens.py -v`
Expected: PASS (3 tes)

- [ ] **Step 5: Commit**

```bash
git add src/ui/theme.py tests/test_motion_tokens.py
git commit -m "feat(v25): token durasi gerak di theme.py"
```

---

## Task 7: `hover_tint()` + item 01 (nav) + item 14 (chip bulan aktif)

**Item 14 menutup cacat:** chip "BULAN AKTIF" punya `cursor="hand2"` dan
binding `<Button-1>` (`app.py:110`) tapi **tidak punya `<Enter>`/`<Leave>`
sama sekali** — tidak ada yang memberi tahu benda itu bisa diklik.

**Files:**
- Modify: `src/ui/motion.py`
- Modify: `src/ui/app.py:283-296` (hover nav), `app.py:108-140` (chip)
- Test: `tests/test_motion_hover.py`

- [ ] **Step 1: Tulis tes yang gagal**

```python
# tests/test_motion_hover.py
"""Hover: item nav (01) dan chip bulan aktif (14)."""
import customtkinter as ctk

from src.ui import motion
from src.ui.theme import COLOR_SURFACE, COLOR_ACCENT_TINT_BG


def test_hover_tint_mencapai_warna_tujuan_saat_motion_mati(tk_root):
    motion.set_enabled(False)
    f = ctk.CTkFrame(tk_root, fg_color="#0A0A0A")
    motion.hover_tint(f, "#0A0A0A", COLOR_SURFACE)
    assert f.cget("fg_color") == COLOR_SURFACE
    f.destroy()


def test_hover_tint_balik_ke_warna_asal(tk_root):
    motion.set_enabled(False)
    f = ctk.CTkFrame(tk_root, fg_color="#0A0A0A")
    motion.hover_tint(f, "#0A0A0A", COLOR_SURFACE)
    motion.hover_tint(f, COLOR_SURFACE, "#0A0A0A")
    assert f.cget("fg_color") == "#0A0A0A"
    f.destroy()


class _SidebarHarness(ctk.CTkFrame):
    """Sidebar asli tanpa membuat root Tk kedua.

    Mengonstruksi HRApp() di dalam tes akan membuat ctk.CTk() kedua di
    samping fixture tk_root yang berlingkup sesi — Tk di Windows tidak
    bisa itu, dan hasilnya tes ngambang yang bergantung urutan (persis
    yang kita perbaiki di v24). Proyek ini sudah punya pola yang sama di
    tests/test_app_caching.py::_ShellHarness.
    """
    _build_sidebar = HRApp._build_sidebar
    _build_nav_item = HRApp._build_nav_item
    _set_active_nav_item = HRApp._set_active_nav_item
    _load_sidebar_icon = HRApp._load_sidebar_icon
    _format_active_month_label = HRApp._format_active_month_label

    def __init__(self, root):
        super().__init__(root)
        self._nav_items = {}
        self._active_nav_key = "Dashboard"
        self._build_sidebar()

    def _show(self, name):
        self._set_active_nav_item(name)


def test_chip_bulan_aktif_punya_umpan_balik_hover(tk_root):
    """Regresi cacat: chip bisa diklik + berkursor tangan tapi tidak
    bereaksi saat disorot, jadi tidak ada yang menandakan ia interaktif."""
    h = _SidebarHarness(tk_root)
    try:
        binds = h._active_month_chip.bind()
        assert "<Enter>" in binds, "chip tidak punya umpan balik hover"
        assert "<Leave>" in binds
    finally:
        h.destroy()


def test_hover_chip_mengubah_warna_lalu_mengembalikannya(tk_root):
    motion.set_enabled(False)
    h = _SidebarHarness(tk_root)
    try:
        chip = h._active_month_chip
        chip.event_generate("<Enter>")
        assert chip.cget("fg_color") != COLOR_ACCENT_TINT_BG
        chip.event_generate("<Leave>")
        assert chip.cget("fg_color") == COLOR_ACCENT_TINT_BG
    finally:
        h.destroy()
```

- [ ] **Step 2: Jalankan tes, pastikan GAGAL**

Run: `.venv/Scripts/python.exe -m pytest tests/test_motion_hover.py -v`
Expected: FAIL — `AttributeError: module 'src.ui.motion' has no attribute 'hover_tint'`

- [ ] **Step 3: Tambahkan penolong ke `motion.py`**

Pembatalannya **per (widget, properti)**, bukan per widget. Alasannya konkret:
chip bulan aktif menganimasikan `fg_color` dan `border_color` sekaligus, dan
pembatalan per-widget akan membuat pemanggilan kedua membunuh yang pertama.

```python
# ─────────────────────────────────────────────── penolong: hover

_hover_jobs: dict[tuple[int, str], str] = {}


def hover_tint(widget, from_color: str, to_color: str,
               duration_ms: int = None, option: str = "fg_color") -> None:
    """Alirkan satu properti warna widget dari `from_color` ke `to_color`.

    Dipakai untuk hover 1-3 widget sekaligus. JANGAN dipakai untuk puluhan
    widget serentak — 20 CTkLabel hanya dapat 64 fps (lihat docstring modul).

    Tween lama pada (widget, properti) YANG SAMA dibatalkan lebih dulu supaya
    masuk-keluar kursor cepat tidak menumpuk dua animasi yang saling melawan.
    Properti berbeda pada widget yang sama berjalan berdampingan.
    """
    from src.ui.theme import MOTION_FAST
    if duration_ms is None:
        duration_ms = MOTION_FAST
    key = (id(widget), option)
    old = _hover_jobs.pop(key, None)
    if old is not None:
        try:
            widget.after_cancel(old)
        except tk.TclError:
            pass
        _forget(widget, old)
    job = tween(widget, duration_ms,
                lambda t: widget.configure(**{option: lerp_hex(from_color, to_color, t)}),
                on_done=lambda: _hover_jobs.pop(key, None))
    if job is not None:
        _hover_jobs[key] = job
```

- [ ] **Step 4: Pasang di item nav (item 01)**

Di `src/ui/app.py`, ganti blok hover di `_build_nav_item` (baris 283-296):

```python
        # Hover handlers — tint mengalir, bukan menjeplak (v25 item 01).
        def _on_enter(_e):
            if frame._screen_key != self._active_nav_key:
                motion.hover_tint(frame, COLOR_SIDEBAR, COLOR_SURFACE)

        def _on_leave(_e):
            if frame._screen_key != self._active_nav_key:
                motion.hover_tint(frame, COLOR_SURFACE, COLOR_SIDEBAR)
```

> **Catatan penting:** warna asal ditulis `COLOR_SIDEBAR` (`#000000`), bukan
> `"transparent"`. `lerp_hex` butuh hex sungguhan; `"transparent"` akan melempar
> `ValueError`. Sidebar memang berlatar `COLOR_SIDEBAR`, jadi hasil akhirnya
> tampak identik dengan v24.

Tambahkan impor di bagian atas `app.py`:

```python
from src.ui import motion
```

dan tambahkan `COLOR_SIDEBAR` ke daftar impor dari `src.ui.theme` bila belum ada
(sudah ada di baris 6).

- [ ] **Step 5: Pasang di chip bulan aktif (item 14)**

Di `src/ui/app.py`, setelah blok binding klik chip (sekitar baris 138-140),
tambahkan:

```python
        # Hover chip — v25 item 14. Sebelumnya chip punya cursor="hand2" dan
        # binding klik tapi NOL umpan balik visual, jadi tidak ada yang
        # menandakan ia bisa diklik sampai kursor kebetulan lewat.
        def _chip_enter(_e):
            motion.hover_tint(self._active_month_chip,
                              COLOR_ACCENT_TINT_BG, COLOR_ACCENT_TINT_HOVER)
            motion.hover_tint(self._active_month_chip,
                              COLOR_ACCENT_TINT_BORDER, COLOR_ACCENT,
                              option="border_color")

        def _chip_leave(_e):
            motion.hover_tint(self._active_month_chip,
                              COLOR_ACCENT_TINT_HOVER, COLOR_ACCENT_TINT_BG)
            motion.hover_tint(self._active_month_chip,
                              COLOR_ACCENT, COLOR_ACCENT_TINT_BORDER,
                              option="border_color")

        for widget in (self._active_month_chip, self._active_month_label, bulan_lbl):
            widget.bind("<Enter>", _chip_enter)
            widget.bind("<Leave>", _chip_leave)
```

Tambahkan token baru di `src/ui/theme.py` (di dekat `COLOR_ACCENT_TINT_BG`):

```python
COLOR_ACCENT_TINT_HOVER   = "#3A1628"   # magenta 15% — chip bulan aktif saat disorot
```

- [ ] **Step 6: Jalankan tes, pastikan LULUS**

Run: `.venv/Scripts/python.exe -m pytest tests/test_motion_hover.py -v`
Expected: PASS (4 tes)

- [ ] **Step 7: Jalankan suite penuh**

Run: `.venv/Scripts/python.exe -m pytest -q`
Expected: PASS — tidak ada tes lama yang berubah

- [ ] **Step 8: Commit**

```bash
git add src/ui/motion.py src/ui/theme.py src/ui/app.py tests/test_motion_hover.py
git commit -m "feat(v25): item 01+14 — hover nav mengalir + chip bulan aktif akhirnya bereaksi"
```

---

## Task 8: Item 15 — hover baris Treeview

**Menutup cacat:** `tree_style.py:30` hanya memetakan state `selected`, jadi
tabel Coaching dan Settings yang jelas interaktif tidak bereaksi terhadap kursor.

ttk.Treeview tidak punya state hover bawaan di `style.map`, jadi hover
diimplementasikan lewat `<Motion>` + `identify_row` + tag.

**Files:**
- Modify: `src/ui/components/tree_style.py`
- Modify: `src/ui/screens/coaching.py` (pasang), `src/ui/screens/settings.py` (pasang)
- Test: `tests/test_tree_hover.py`

- [ ] **Step 1: Tulis tes yang gagal**

```python
# tests/test_tree_hover.py
"""Item 15 — hover baris Treeview (satu implementasi, dipakai semua layar)."""
from tkinter import ttk

from src.ui.components.tree_style import RowHover, HOVER_TAG, style_treeview


def _tree(tk_root):
    style_treeview("Hov.Treeview")
    t = ttk.Treeview(tk_root, style="Hov.Treeview", columns=("a",),
                     show="tree headings", height=4)
    for i in range(4):
        t.insert("", "end", iid=str(i), text=f"Pegawai {i}", values=(i,))
    t.pack()
    return t


def test_hover_menandai_baris_di_bawah_kursor(tk_root):
    t = _tree(tk_root)
    try:
        RowHover(t)
        t.event_generate("<Motion>", x=10, y=10)   # tidak deterministik -> panggil langsung
        hover = t._row_hover
        hover._apply("2")
        assert HOVER_TAG in t.item("2", "tags")
    finally:
        t.destroy()


def test_pindah_baris_melepas_tanda_dari_baris_sebelumnya(tk_root):
    t = _tree(tk_root)
    try:
        RowHover(t)
        t._row_hover._apply("1")
        t._row_hover._apply("3")
        assert HOVER_TAG not in t.item("1", "tags")
        assert HOVER_TAG in t.item("3", "tags")
    finally:
        t.destroy()


def test_keluar_dari_tabel_membersihkan_tanda(tk_root):
    t = _tree(tk_root)
    try:
        RowHover(t)
        t._row_hover._apply("1")
        t._row_hover._apply(None)
        assert HOVER_TAG not in t.item("1", "tags")
    finally:
        t.destroy()


def test_tag_zebra_tidak_hilang_setelah_hover(tk_root):
    """Regresi: baris zebra harus kembali ke tag semula, bukan kehilangannya."""
    t = _tree(tk_root)
    try:
        t.item("1", tags=("evenrow",))
        RowHover(t)
        t._row_hover._apply("1")
        t._row_hover._apply(None)
        assert "evenrow" in t.item("1", "tags")
    finally:
        t.destroy()
```

- [ ] **Step 2: Jalankan tes, pastikan GAGAL**

Run: `.venv/Scripts/python.exe -m pytest tests/test_tree_hover.py -v`
Expected: FAIL — `ImportError: cannot import name 'RowHover'`

- [ ] **Step 3: Tulis implementasi**

Tambahkan ke `src/ui/components/tree_style.py`:

```python
HOVER_TAG = "rowhover"


class RowHover:
    """Menyorot baris di bawah kursor.

    ttk.Treeview tidak punya state hover di style.map (tree_style hanya
    memetakan 'selected'), jadi tabel yang jelas interaktif tidak bereaksi
    sama sekali terhadap kursor. Ini menambalnya lewat <Motion> +
    identify_row + tag.

    Tanpa animasi: warna baris berpindah dalam satu frame. Menganimasikannya
    berarti men-tween tag_configure (9,83 ms/frame) pada setiap gerakan mouse
    — terlalu mahal untuk imbalannya. Kilat baris (item 10) memang memakai
    tween tag, tapi hanya sekali per aksi, bukan per piksel gerakan.
    """

    def __init__(self, tree: ttk.Treeview):
        self.tree = tree
        self._current = None
        tree.tag_configure(HOVER_TAG, background=COLOR_SURFACE_HIGH)
        tree.bind("<Motion>", self._on_motion, add="+")
        tree.bind("<Leave>", lambda _e: self._apply(None), add="+")
        tree._row_hover = self          # pegangan untuk tes & pembersihan

    def _on_motion(self, event):
        self._apply(self.tree.identify_row(event.y) or None)

    def _apply(self, iid):
        if iid == self._current:
            return
        if self._current:
            self._set_tags(self._current, add=False)
        self._current = iid
        if iid:
            self._set_tags(iid, add=True)

    def _set_tags(self, iid, *, add: bool):
        try:
            tags = [t for t in self.tree.item(iid, "tags") if t != HOVER_TAG]
        except tk.TclError:
            return                      # baris sudah lenyap saat daftar dibangun ulang
        if add:
            tags.append(HOVER_TAG)
        self.tree.item(iid, tags=tuple(tags))
```

Pastikan `tree_style.py` mengimpor `tkinter as tk` dan `COLOR_SURFACE_HIGH`.

- [ ] **Step 4: Pasang di Coaching dan Settings**

Di `src/ui/screens/coaching.py`, setelah pembuatan `self.tree` (sekitar baris 152):

```python
        RowHover(self.tree)     # v25 item 15
```

Di `src/ui/screens/settings.py`, setelah pembuatan tree tab Pegawai
(sekitar baris 399-408), tambahkan baris serupa pada nama variabel tree di sana.

Tambahkan impor di kedua berkas:

```python
from src.ui.components.tree_style import RowHover
```

- [ ] **Step 5: Jalankan tes, pastikan LULUS**

Run: `.venv/Scripts/python.exe -m pytest tests/test_tree_hover.py -v`
Expected: PASS (4 tes)

- [ ] **Step 6: Suite penuh + commit**

```bash
.venv/Scripts/python.exe -m pytest -q
git add src/ui/components/tree_style.py src/ui/screens/coaching.py src/ui/screens/settings.py tests/test_tree_hover.py
git commit -m "feat(v25): item 15 — baris tabel akhirnya bereaksi terhadap kursor"
```

---

## Task 9: `SlidingIndicator` + item 02 (garis nav meluncur)

Garis aktif sekarang di-`pack()`/`pack_forget()` ulang di dalam frame item
masing-masing (`app.py:309`, `317`, `326`). Supaya bisa meluncur, satu garis
**tunggal** dipindah ke sidebar dan diposisikan dengan `place(y=…)`.

**Files:**
- Modify: `src/ui/motion.py`, `src/ui/app.py`
- Test: `tests/test_motion_nav_bar.py`

- [ ] **Step 1: Tulis tes yang gagal**

Pakai `_SidebarHarness` yang sama seperti Task 7 (impor dari
`tests/test_motion_hover.py`, jangan disalin ulang) — mengonstruksi `HRApp()`
akan membuat root Tk kedua dan menghasilkan tes ngambang.

```python
# tests/test_motion_nav_bar.py
"""Item 02 — garis nav aktif meluncur, bukan hilang lalu muncul."""
from src.ui import motion
from tests.test_motion_hover import _SidebarHarness


def test_hanya_ada_satu_garis_aktif_untuk_seluruh_sidebar(tk_root):
    """Regresi arsitektur: sebelumnya tiap item punya garisnya sendiri, jadi
    mustahil meluncur. Sekarang satu garis dipakai bersama."""
    h = _SidebarHarness(tk_root)
    try:
        assert hasattr(h, "_nav_indicator")
        for item in h._nav_items.values():
            assert not hasattr(item, "_left_bar"), \
                "garis per-item masih ada — luncuran tidak akan mungkin"
    finally:
        h.destroy()


def test_garis_pindah_ke_posisi_item_yang_dipilih(tk_root):
    motion.set_enabled(False)
    h = _SidebarHarness(tk_root)
    try:
        h.pack()
        h.update_idletasks()
        h._set_active_nav_item("Heatmap")
        h.update_idletasks()
        y_heatmap = h._nav_indicator.winfo_y()
        h._set_active_nav_item("Coaching")
        h.update_idletasks()
        y_coaching = h._nav_indicator.winfo_y()
        assert y_coaching != y_heatmap, "garis tidak berpindah"
        target = h._nav_items["Coaching"].winfo_y()
        assert abs(y_coaching - target) <= 8, "garis tidak mendarat di item tujuan"
    finally:
        h.destroy()


def test_garis_terlihat_setelah_item_pertama_diaktifkan(tk_root):
    h = _SidebarHarness(tk_root)
    try:
        h.pack()
        h._set_active_nav_item("Dashboard")
        h.update_idletasks()
        assert h._nav_indicator.winfo_ismapped()
    finally:
        h.destroy()
```

- [ ] **Step 2: Jalankan tes, pastikan GAGAL**

Run: `.venv/Scripts/python.exe -m pytest tests/test_motion_nav_bar.py -v`
Expected: FAIL — `AssertionError: hasattr(h, "_nav_indicator")`

- [ ] **Step 3: Tambahkan penolong ke `motion.py`**

```python
# ─────────────────────────────────────────────── penolong: indikator meluncur

def slide_to_y(widget, from_y: int, to_y: int, duration_ms: int = None) -> None:
    """Geser widget ber-`place()` secara vertikal dari `from_y` ke `to_y`.

    Widget WAJIB sudah diposisikan dengan place(); pack/grid tidak bisa
    dianimasikan tanpa menata ulang tata letak tiap frame.
    """
    from src.ui.theme import MOTION_BASE
    if duration_ms is None:
        duration_ms = MOTION_BASE
    cancel_for(widget)
    tween(widget, duration_ms,
          lambda t: widget.place_configure(y=int(from_y + (to_y - from_y) * t)))
```

- [ ] **Step 4: Ubah `app.py` — satu garis untuk seluruh sidebar**

Di `_build_nav_item`, **hapus** pembuatan `left_bar` dan baris `frame._left_bar = left_bar`.

Di `_build_sidebar`, setelah seluruh item nav di-`pack()`, tambahkan:

```python
        # Satu garis aktif untuk SELURUH sidebar (v25 item 02). Sebelumnya
        # tiap item punya garisnya sendiri yang di-pack/pack_forget, sehingga
        # perpindahan tampak sebagai "hilang lalu muncul di tempat lain".
        self._nav_indicator = ctk.CTkFrame(
            self.sidebar, fg_color=COLOR_ACCENT, width=3, height=22,
            corner_radius=0,
        )
        self._nav_indicator.place(x=0, y=0)
        self._nav_indicator.place_forget()      # ditampilkan saat item pertama aktif
```

Ganti isi `_set_active_nav_item` sepenuhnya:

```python
    def _set_active_nav_item(self, screen_key: str):
        """Pindahkan garis aktif + perbarui warna teks/ikon.

        Garisnya tunggal dan meluncur; item lama hanya kehilangan tint dan
        ketebalan teksnya.
        """
        prev = self._nav_items.get(self._active_nav_key)
        if prev is not None and self._active_nav_key != screen_key:
            prev.configure(fg_color="transparent")
            prev._text_lbl.configure(text_color=COLOR_TEXT_SOFT, font=FONT_BODY)
            prev._icon_lbl.configure(text_color=COLOR_TEXT_DIM)

        new = self._nav_items.get(screen_key)
        if new is None:
            return
        new.configure(fg_color=COLOR_SURFACE_HIGH)
        new._text_lbl.configure(text_color=COLOR_TEXT, font=FONT_BODY_BOLD)
        new._icon_lbl.configure(text_color=COLOR_ACCENT)

        self.update_idletasks()          # pastikan winfo_y() item sudah valid
        target_y = new.winfo_y() + (new.winfo_height() - 22) // 2
        if not self._nav_indicator.winfo_ismapped():
            self._nav_indicator.place(x=0, y=target_y)
        else:
            motion.slide_to_y(self._nav_indicator,
                              self._nav_indicator.winfo_y(), target_y)
        self._active_nav_key = screen_key
```

- [ ] **Step 5: Jalankan tes, pastikan LULUS**

Run: `.venv/Scripts/python.exe -m pytest tests/test_motion_nav_bar.py -v`
Expected: PASS (3 tes)

- [ ] **Step 6: Suite penuh**

Run: `.venv/Scripts/python.exe -m pytest -q`

> Tes lama `test_app_dinas_recap_nav.py` menyentuh nav. Kalau ia gagal karena
> memeriksa `_left_bar`, itu **memang** perlu diperbarui — arsitektur garisnya
> sengaja berubah, dan itu bukan pergeseran keadaan akhir yang tidak disengaja.
> Perbarui tes itu untuk memeriksa `_nav_indicator`.

- [ ] **Step 7: Commit**

```bash
git add src/ui/motion.py src/ui/app.py tests/
git commit -m "feat(v25): item 02 — garis nav aktif meluncur antar menu"
```

---

## Task 10: Item 13 — pil geser pada WeekNavBar

`WeekNavBar._refresh_styles` (`week_nav.py:84`) mengganti `fg_color` tombol
seketika. Karena tombolnya `CTkButton` dengan lebar berbeda-beda, pil geser
sungguhan butuh satu overlay ber-`place()`. Pendekatan yang lebih murah dan
tidak mengubah tata letak: **alirkan warnanya**, bukan menggeser pil.

Keputusan ini menyimpang dari mockup (yang memperagakan pil geser) dan
alasannya harus dicatat: tombol WeekNavBar lebarnya dinamis (`Minggu 1 (01-07)`),
sehingga pil geser butuh pengukuran ulang tiap perubahan bulan. Aliran warna
memberi 90% rasanya dengan 10% risikonya.

**Files:**
- Modify: `src/ui/components/week_nav.py:80-98`
- Test: `tests/test_motion_week_nav.py`

- [ ] **Step 1: Tulis tes yang gagal**

```python
# tests/test_motion_week_nav.py
"""Item 13 — perpindahan pil periode mengalir, bukan menjeplak."""
from src.ui import motion
from src.ui.components.week_nav import WeekNavBar
from src.ui.theme import COLOR_ACCENT, COLOR_BG


def test_keadaan_akhir_identik_dengan_v24_saat_motion_mati(tk_root):
    motion.set_enabled(False)
    calls = []
    bar = WeekNavBar(tk_root, current_month="2026-07",
                     on_change=calls.append, initial="semua")
    try:
        bar.set_active("minggu_2")
        btn = bar._buttons["minggu_2"]
        assert btn.cget("fg_color") == COLOR_ACCENT
        assert btn.cget("text_color") == COLOR_BG
    finally:
        bar.destroy()


def test_tombol_tak_aktif_kembali_ke_transparan(tk_root):
    motion.set_enabled(False)
    bar = WeekNavBar(tk_root, current_month="2026-07",
                     on_change=lambda k: None, initial="minggu_2")
    try:
        bar.set_active("semua")
        assert bar._buttons["minggu_2"].cget("fg_color") == "transparent"
    finally:
        bar.destroy()
```

- [ ] **Step 2: Jalankan tes, pastikan LULUS lebih dulu**

Run: `.venv/Scripts/python.exe -m pytest tests/test_motion_week_nav.py -v`
Expected: PASS — ini tes **karakterisasi**: mengunci keadaan akhir v24
SEBELUM disentuh, supaya perubahan berikutnya terbukti tidak menggesernya.

- [ ] **Step 3: Ganti `_refresh_styles`**

```python
    def _refresh_styles(self):
        """Alirkan warna tombol ke keadaan barunya (v25 item 13).

        Kenapa aliran warna, bukan pil geser seperti sidebar: lebar tombol di
        sini dinamis ("Minggu 1 (01-07)"), sehingga pil ber-place() harus
        diukur ulang tiap ganti bulan. Aliran warna memberi hampir seluruh
        rasanya tanpa risiko itu.
        """
        for key, btn in self._buttons.items():
            active = key == self._active
            to_fg = COLOR_ACCENT if active else COLOR_SURFACE
            to_text = COLOR_BG if active else COLOR_TEXT_DIM
            to_border = COLOR_ACCENT if active else COLOR_BORDER
            from_fg = btn.cget("fg_color")
            if from_fg == "transparent":
                from_fg = COLOR_SURFACE
            motion.tween(
                btn, MOTION_BASE,
                lambda t, b=btn, f=from_fg, g=to_fg: b.configure(
                    fg_color=lerp_hex(f, g, t)),
                on_done=lambda b=btn, a=active, g=to_fg, x=to_text, r=to_border: b.configure(
                    fg_color=g if a else "transparent",
                    text_color=x, border_color=r),
            )
```

Tambahkan impor di `week_nav.py`:

```python
from src.ui import motion
from src.ui.motion import lerp_hex
from src.ui.theme import MOTION_BASE, COLOR_SURFACE
```

> Perhatikan `on_done`: nilai akhir dipasang eksplisit termasuk
> `"transparent"` untuk tombol tak aktif. Ini yang menjaga keadaan akhir
> identik dengan v24 dan membuat tes karakterisasi di Step 2 tetap lulus.

- [ ] **Step 4: Jalankan tes, pastikan MASIH LULUS**

Run: `.venv/Scripts/python.exe -m pytest tests/test_motion_week_nav.py -v`
Expected: PASS (2 tes) — keadaan akhir tidak bergeser

- [ ] **Step 5: Suite penuh + commit**

```bash
.venv/Scripts/python.exe -m pytest -q
git add src/ui/components/week_nav.py tests/test_motion_week_nav.py
git commit -m "feat(v25): item 13 — perpindahan pil periode mengalir"
```

---

## Task 11: `count_up()` + item 03 (KPI Dashboard)

**Files:**
- Modify: `src/ui/motion.py`, `src/ui/screens/dashboard.py`
- Test: `tests/test_motion_count_up.py`

- [ ] **Step 1: Tulis tes yang gagal**

```python
# tests/test_motion_count_up.py
"""Item 03 — angka KPI berhitung naik, dan hanya saat datanya berubah."""
import customtkinter as ctk

from src.ui import motion


def test_count_up_mendarat_tepat_di_nilai_akhir(tk_root):
    motion.set_enabled(False)
    lbl = ctk.CTkLabel(tk_root, text="0")
    motion.count_up(lbl, 4238)
    assert lbl.cget("text") == "4238"
    lbl.destroy()


def test_count_up_menghormati_formatter(tk_root):
    motion.set_enabled(False)
    lbl = ctk.CTkLabel(tk_root, text="")
    motion.count_up(lbl, 87, fmt=lambda v: f"{v} mnt")
    assert lbl.cget("text") == "87 mnt"
    lbl.destroy()


def test_count_up_nilai_nol_tetap_menulis_nol(tk_root):
    motion.set_enabled(False)
    lbl = ctk.CTkLabel(tk_root, text="99")
    motion.count_up(lbl, 0)
    assert lbl.cget("text") == "0"
    lbl.destroy()


def test_dashboard_tidak_menganimasikan_kunjungan_ulang_tanpa_perubahan(tk_root, monkeypatch, tmp_path):
    """Regresi jebakan #2: layar disimpan di cache sejak v22, jadi tanpa
    RenderSignature animasi masuk akan main ulang tiap bolak-balik menu."""
    from src.db.schema import init_db
    from src.db.connection import get_connection
    from src.db.settings import set_setting
    from src.ui.screens import dashboard as M

    p = tmp_path / "hr.db"
    init_db(p)
    with get_connection(p) as conn:
        set_setting(conn, "current_month", "2026-07")
    monkeypatch.setattr(M, "DB_PATH", p)

    s = M.DashboardScreen(tk_root)
    try:
        assert s._anim_sig.changed(*s._anim_parts()) is False, \
            "render pertama sudah mencatat sidik jarinya"
        s.on_show()
        assert s._anim_sig.changed(*s._anim_parts()) is False, \
            "kunjungan ulang tanpa perubahan data seharusnya tidak menganimasikan"
    finally:
        s.destroy()
```

- [ ] **Step 2: Jalankan tes, pastikan GAGAL**

Run: `.venv/Scripts/python.exe -m pytest tests/test_motion_count_up.py -v`
Expected: FAIL — `AttributeError: module 'src.ui.motion' has no attribute 'count_up'`

- [ ] **Step 3: Tambahkan penolong ke `motion.py`**

```python
# ─────────────────────────────────────────────── penolong: hitung-naik

def count_up(label, to_value: int, fmt: Callable[[int], str] = str,
             duration_ms: int = None) -> None:
    """Naikkan teks angka sebuah label dari 0 ke `to_value`.

    Hanya mengganti teks — 0,36 ms per frame, salah satu yang termurah.
    Selalu mendarat tepat di `to_value`, tidak pernah di angka pembulatan.
    """
    from src.ui.theme import MOTION_SLOW
    if duration_ms is None:
        duration_ms = MOTION_SLOW
    cancel_for(label)
    tween(label, duration_ms,
          lambda t: label.configure(text=fmt(int(round(to_value * t)))))
```

- [ ] **Step 4: Pasang di Dashboard**

Di `src/ui/screens/dashboard.py.__init__`, tambahkan sebelum `self._update_data()`:

```python
        # Sidik jari render — animasi masuk hanya main saat datanya berubah
        # (v25 item 03). Tuple-nya sama persis dengan kunci memoisasi query
        # di _update_data, jadi "animasikan" setara dengan "cache meleset".
        self._anim_sig = motion.RenderSignature()
```

Tambahkan metode:

```python
    def _anim_parts(self):
        """Bagian-bagian yang menentukan apakah tampilan benar-benar berubah."""
        return (data_version.get(), self._current_month, period_state.get())
```

Di `_update_data()`, di tempat nilai KPI dipasang, ganti pemasangan langsung
menjadi:

```python
        animate = self._anim_sig.changed(*self._anim_parts())
        for name, value in kpi_values.items():
            lbl = self._kpi_labels[name]
            if animate:
                motion.count_up(lbl, value)
            else:
                lbl.configure(text=str(value))
```

> Sesuaikan nama `kpi_values` dengan struktur yang sudah ada di
> `_update_data()`; yang penting: **saat `animate` False, jalur lama dipakai
> apa adanya**, sehingga keadaan akhir identik.

Tambahkan impor `from src.ui import motion` di `dashboard.py`.

- [ ] **Step 5: Jalankan tes, pastikan LULUS**

Run: `.venv/Scripts/python.exe -m pytest tests/test_motion_count_up.py -v`
Expected: PASS (4 tes)

- [ ] **Step 6: Suite penuh + commit**

```bash
.venv/Scripts/python.exe -m pytest -q
git add src/ui/motion.py src/ui/screens/dashboard.py tests/test_motion_count_up.py
git commit -m "feat(v25): item 03 — angka KPI berhitung naik saat data berubah"
```

---

## Task 12: Item 19 — Coaching berhenti berkedip

**Ini memperbaiki cacat, bukan menambah hiasan.** `coaching.py:106`
menghancurkan lalu membangun ulang empat `KPICard` setiap `_reload()`, yang
dipicu tiap toggle "Sudah Coaching". Perbaikannya: bangun kartu sekali,
perbarui nilainya di tempat lewat `KPICard.set_value` yang sudah ada.

**Files:**
- Modify: `src/ui/screens/coaching.py:106-139`
- Test: `tests/test_coaching_no_flicker.py`

- [ ] **Step 1: Tulis tes yang gagal**

```python
# tests/test_coaching_no_flicker.py
"""Item 19 — kartu KPI Coaching diperbarui di tempat, tidak dihancurkan."""
import pytest

from src.db.schema import init_db
from src.db.connection import get_connection
from src.db.settings import set_setting
from src.db.employees import upsert_employee


@pytest.fixture
def dbp(tmp_path):
    p = tmp_path / "hr.db"
    init_db(p)
    with get_connection(p) as conn:
        set_setting(conn, "current_month", "2026-07")
        upsert_employee(conn, no_staff="S1", nama="Andi", dept="Ops")
        upsert_employee(conn, no_staff="S2", nama="Budi", dept="Sales")
    return p


def test_kartu_kpi_tidak_dibangun_ulang_saat_reload(tk_root, monkeypatch, dbp):
    """Regresi cacat: _render_stats() men-destroy() semua kartu tiap reload,
    jadi Total/Sudah/Belum/Coverage berkedip putih tiap toggle."""
    from src.ui.screens import coaching as M
    monkeypatch.setattr(M, "DB_PATH", dbp)
    s = M.CoachingScreen(tk_root)
    try:
        before = [id(c) for c in s._stats_cards]
        assert len(before) == 4
        s._reload()
        after = [id(c) for c in s._stats_cards]
        assert after == before, "kartu KPI dibangun ulang — kedipannya masih ada"
    finally:
        s.destroy()


def test_nilai_kartu_tetap_benar_setelah_reload(tk_root, monkeypatch, dbp):
    from src.ui.screens import coaching as M
    monkeypatch.setattr(M, "DB_PATH", dbp)
    s = M.CoachingScreen(tk_root)
    try:
        s._reload()
        total_card = s._stats_cards[0]
        assert total_card._value_label.cget("text") == str(len(s._rows))
    finally:
        s.destroy()
```

- [ ] **Step 2: Jalankan tes, pastikan GAGAL**

Run: `.venv/Scripts/python.exe -m pytest tests/test_coaching_no_flicker.py -v`
Expected: FAIL — `AssertionError: kartu KPI dibangun ulang`

- [ ] **Step 3: Tulis implementasi**

Ganti `_render_stats` di `src/ui/screens/coaching.py`:

```python
    _STATS_SLOTS = ("Total", "Sudah", "Belum", "Coverage")

    def _build_stats_cards(self):
        """Bangun keempat kartu SEKALI. Sebelumnya kartu dihancurkan dan
        dibangun ulang tiap _reload(), jadi setiap toggle 'Sudah Coaching'
        membuat seluruh baris KPI berkedip putih (v25 item 19)."""
        from src.ui.components.kpi_card import KPICard
        self._stats_cards = []
        for i, label in enumerate(self._STATS_SLOTS):
            c = KPICard(self.stats, label, "—", value_color=COLOR_TEXT)
            c.grid(row=0, column=i, padx=SPACE_XS, sticky="ew")
            self._stats_cards.append(c)

    def _render_stats(self, rows):
        """Perbarui nilai kartu DI TEMPAT."""
        total = len(rows)
        sudah = sum(1 for r in rows if r["is_coached"])
        belum = total - sudah
        if total > 0:
            coverage_pct = round(sudah / total * 100)
            coverage = f"{coverage_pct}%"
            coverage_color = COLOR_SUCCESS if coverage_pct > 75 else COLOR_WARN
        else:
            coverage = "—"
            coverage_color = COLOR_TEXT_MUTED

        animate = self._anim_sig.changed(data_version.get(), self._month)

        numeric = ((0, total, COLOR_TEXT),
                   (1, sudah, COLOR_SUCCESS),
                   (2, belum, COLOR_WARN))
        for idx, value, color in numeric:
            card = self._stats_cards[idx]
            if animate:
                card._value_label.configure(text_color=color)
                motion.count_up(card._value_label, value)
            else:
                card.set_value(str(value), color)
        self._stats_cards[3].set_value(coverage, coverage_color)
```

Di `__init__` (setelah `self._stats_cards = []` di baris 104), ganti dengan:

```python
        self._anim_sig = motion.RenderSignature()
        self._build_stats_cards()
```

Tambahkan impor:

```python
from src.ui import motion
from src.core.session_state import data_version
```

- [ ] **Step 4: Jalankan tes, pastikan LULUS**

Run: `.venv/Scripts/python.exe -m pytest tests/test_coaching_no_flicker.py -v`
Expected: PASS (2 tes)

- [ ] **Step 5: Suite penuh + commit**

```bash
.venv/Scripts/python.exe -m pytest -q
git add src/ui/screens/coaching.py tests/test_coaching_no_flicker.py
git commit -m "fix(v25): item 19 — kartu KPI Coaching berhenti berkedip tiap toggle"
```

---

## Task 13: `wipe_canvas()` + item 05 (sapuan heatmap)

Sel heatmap sudah bertag `("cell", "cellrect")` (`heatmap.py:418`), jadi sapuan
tidak perlu menyentuh `_paint_grid` sama sekali: baca warna tujuan tiap sel,
kosongkan, lalu nyalakan kolom demi kolom.

**Ukuran yang mendasari:** memudarkan 675 sel serentak = 31 fps (patah-patah).
Menyapu 4 kolom per frame = 366 fps dan tuntas dalam 135 ms.

**Files:**
- Modify: `src/ui/motion.py`, `src/ui/screens/heatmap.py`
- Test: `tests/test_motion_wipe.py`

- [ ] **Step 1: Tulis tes yang gagal**

```python
# tests/test_motion_wipe.py
"""Item 05 — sapuan heatmap, dan jaminan ia tidak menyala saat mencari."""
import tkinter as tk

from src.ui import motion


def test_wipe_mendarat_di_warna_tujuan_saat_motion_mati(tk_root):
    motion.set_enabled(False)
    cv = tk.Canvas(tk_root, width=200, height=60)
    items = [cv.create_rectangle(i * 10, 0, i * 10 + 8, 20,
                                 fill="#10B981", tags=("cellrect",))
             for i in range(10)]
    motion.wipe_canvas(cv, "cellrect", "#141414")
    for it in items:
        assert cv.itemcget(it, "fill") == "#10B981"
    cv.destroy()


def test_wipe_tanpa_sel_tidak_meledak(tk_root):
    motion.set_enabled(False)
    cv = tk.Canvas(tk_root, width=50, height=20)
    motion.wipe_canvas(cv, "cellrect", "#141414")     # tidak ada item bertag itu
    cv.destroy()


def test_mengetik_di_pencarian_tidak_memicu_sapuan(tk_root, monkeypatch, tmp_path):
    """Regresi jebakan #1: _repaint() juga dipanggil _on_search (debounce
    200 ms), _on_sort, dan _apply_resize. Sapuan hanya boleh ikut saat
    sidik jari berubah — dan kata pencarian sengaja di luar sidik jari."""
    from src.db.schema import init_db
    from src.db.connection import get_connection
    from src.db.settings import set_setting
    from src.ui.screens import heatmap as M

    p = tmp_path / "hr.db"
    init_db(p)
    with get_connection(p) as conn:
        set_setting(conn, "current_month", "2026-07")
    monkeypatch.setattr(M, "DB_PATH", p)

    s = M.HeatmapScreen(tk_root)
    try:
        parts = s._anim_parts()
        s._on_search("bud")
        assert s._anim_parts() == parts, \
            "kata pencarian bocor ke sidik jari — sapuan akan berkedip tiap ketukan"
        assert s._anim_sig.changed(*s._anim_parts()) is False
    finally:
        s.destroy()
```

- [ ] **Step 2: Jalankan tes, pastikan GAGAL**

Run: `.venv/Scripts/python.exe -m pytest tests/test_motion_wipe.py -v`
Expected: FAIL — `AttributeError: module 'src.ui.motion' has no attribute 'wipe_canvas'`

- [ ] **Step 3: Tambahkan penolong ke `motion.py`**

```python
# ─────────────────────────────────────────────── penolong: sapuan Canvas

def wipe_canvas(canvas, tag: str, base_color: str,
                step_ms: int = None, group_px: int = 14) -> None:
    """Nyalakan item ber-`tag` kolom demi kolom, dari kiri ke kanan.

    Kenapa bertahap dan bukan memudarkan semuanya serentak: memudarkan 675
    sel sekaligus hanya dapat 31 fps (32,54 ms per frame) — patah-patah.
    Menyapu per kolom hanya menyentuh belasan item per frame: 366 fps, dan
    seluruh sapuan tuntas dalam ~135 ms. Versi yang lebih indah kebetulan
    juga versi yang lebih cepat.

    Warna tujuan dibaca dari item itu sendiri, jadi pemanggil tidak perlu
    tahu apa pun soal palet — dan `_paint_grid` tidak perlu diubah.
    """
    from src.ui.theme import MOTION_WIPE_STEP
    if step_ms is None:
        step_ms = MOTION_WIPE_STEP

    items = canvas.find_withtag(tag)
    if not items:
        return

    targets = [(canvas.coords(i)[0], i, canvas.itemcget(i, "fill")) for i in items]

    if not _enabled:
        return                      # warnanya memang sudah benar; tak ada yang perlu dilakukan

    columns: dict[int, list] = {}
    for x, item, fill in targets:
        columns.setdefault(int(x // group_px), []).append((item, fill))

    for item, _fill in [(i, f) for col in columns.values() for i, f in col]:
        canvas.itemconfig(item, fill=base_color)

    order = sorted(columns)
    for n, key in enumerate(order):
        def light(col=columns[key]):
            for item, fill in col:
                try:
                    canvas.itemconfig(item, fill=fill)
                except tk.TclError:
                    return          # canvas dibersihkan di tengah sapuan
        job = canvas.after(n * step_ms, light)
        _register(canvas, job)
```

- [ ] **Step 4: Pasang di Heatmap**

Di `HeatmapScreen.__init__`, tambahkan:

```python
        self._anim_sig = motion.RenderSignature()
```

Tambahkan metode:

```python
    def _anim_parts(self):
        """Sidik jari sapuan. Kata pencarian dan ukuran jendela SENGAJA tidak
        termasuk: _repaint() juga dipanggil oleh _on_search dan _apply_resize,
        dan sapuan yang ikut menyala di sana akan berkedip tiap ketukan tombol."""
        return (data_version.get(), self._month, self._sort_key)
```

Di akhir `_repaint()` (setelah `c.configure(scrollregion=...)`), tambahkan:

```python
        if self._anim_sig.changed(*self._anim_parts()):
            motion.wipe_canvas(c, "cellrect", _BENTO_TILE)
```

Tambahkan impor `from src.ui import motion` dan
`from src.core.session_state import data_version` di `heatmap.py`.

> Sesuaikan `self._sort_key` dengan nama atribut sort yang sudah dipakai
> `_on_sort` di berkas itu.

- [ ] **Step 5: Jalankan tes, pastikan LULUS**

Run: `.venv/Scripts/python.exe -m pytest tests/test_motion_wipe.py -v`
Expected: PASS (3 tes)

- [ ] **Step 6: Suite penuh + commit**

```bash
.venv/Scripts/python.exe -m pytest -q
git add src/ui/motion.py src/ui/screens/heatmap.py tests/test_motion_wipe.py
git commit -m "feat(v25): item 05 — sel heatmap menyala menyapu dari kiri"
```

---

## Task 14: Item 06 — sorotan sel heatmap + tooltip memudar

**Files:**
- Modify: `src/ui/screens/heatmap.py:614-635`
- Test: `tests/test_heatmap_cell_hover.py`

- [ ] **Step 1: Tulis tes yang gagal**

```python
# tests/test_heatmap_cell_hover.py
"""Item 06 — sel yang disorot ditandai; tooltip memudar, tidak menjeplak."""
import tkinter as tk


def _screen(tk_root, monkeypatch, tmp_path):
    from src.db.schema import init_db
    from src.db.connection import get_connection
    from src.db.settings import set_setting
    from src.ui.screens import heatmap as M
    p = tmp_path / "hr.db"
    init_db(p)
    with get_connection(p) as conn:
        set_setting(conn, "current_month", "2026-07")
    monkeypatch.setattr(M, "DB_PATH", p)
    return M.HeatmapScreen(tk_root)


def test_menyorot_sel_memberi_outline_dan_melepasnya_lagi(tk_root, monkeypatch, tmp_path):
    s = _screen(tk_root, monkeypatch, tmp_path)
    try:
        cv = s._canvas
        item = cv.create_rectangle(0, 0, 10, 10, fill="#10B981", outline="")
        s._highlight_cell(item)
        assert cv.itemcget(item, "outline") != ""
        s._highlight_cell(None)
        assert cv.itemcget(item, "outline") == ""
    finally:
        s.destroy()


def test_tooltip_mulai_transparan_lalu_terlihat(tk_root, monkeypatch, tmp_path):
    from src.ui import motion
    motion.set_enabled(False)
    s = _screen(tk_root, monkeypatch, tmp_path)
    try:
        cell = {"label": "Senin", "date": "03", "masuk": "07.58",
                "keluar": "16.05", "telat": "0", "alasan": "-"}
        evt = tk.Event()
        evt.x_root, evt.y_root = 100, 100
        s._show_tip(evt, cell)
        assert float(s._tip.attributes("-alpha")) == 1.0
    finally:
        s.destroy()
```

- [ ] **Step 2: Jalankan tes, pastikan GAGAL**

Run: `.venv/Scripts/python.exe -m pytest tests/test_heatmap_cell_hover.py -v`
Expected: FAIL — `AttributeError: 'HeatmapScreen' object has no attribute '_highlight_cell'`

- [ ] **Step 3: Tulis implementasi**

Tambahkan ke `HeatmapScreen`:

```python
    def _highlight_cell(self, item_id):
        """Tandai sel di bawah kursor dengan outline putih tipis (v25 item 06).

        Sebelumnya tooltip muncul tanpa penanda apa pun di kanvas, jadi user
        harus menebak sel mana yang sedang dibaca — terutama saat kursor
        berada di antara dua sel yang berdempetan.
        """
        prev = getattr(self, "_hover_item", None)
        if prev == item_id:
            return
        if prev is not None:
            try:
                self._canvas.itemconfig(prev, outline=self._hover_prev_outline,
                                        width=1)
            except tk.TclError:
                pass
        self._hover_item = item_id
        if item_id is not None:
            self._hover_prev_outline = self._canvas.itemcget(item_id, "outline")
            self._canvas.itemconfig(item_id, outline=COLOR_TEXT, width=2)
```

Ubah `_on_cell_motion`:

```python
    def _on_cell_motion(self, event):
        item = self._canvas.find_withtag("current")
        item_id = item[0] if item else None
        cell = self._cell_by_item.get(item_id) if item_id else None
        if cell:
            self._highlight_cell(item_id)
            self._show_tip(event, cell)
        else:
            self._highlight_cell(None)
```

Ubah akhir `_show_tip` (ganti `self._tip.deiconify()`):

```python
        self._tip.wm_geometry(f"+{event.x_root + 14}+{event.y_root + 12}")
        if not self._tip.winfo_viewable():
            self._tip.attributes("-alpha", 0.0)
            self._tip.deiconify()
            motion.tween(self._tip, MOTION_FADE,
                         lambda t: self._tip.attributes("-alpha", t))
        else:
            self._tip.deiconify()
```

Ubah `_hide_tip` untuk membersihkan sorotan:

```python
    def _hide_tip(self):
        self._highlight_cell(None)
        if self._tip is not None:
            self._tip.withdraw()
```

Tambahkan impor `MOTION_FADE` dari `src.ui.theme`.

- [ ] **Step 4: Jalankan tes, pastikan LULUS**

Run: `.venv/Scripts/python.exe -m pytest tests/test_heatmap_cell_hover.py -v`
Expected: PASS (2 tes)

- [ ] **Step 5: Suite penuh + commit**

```bash
.venv/Scripts/python.exe -m pytest -q
git add src/ui/screens/heatmap.py tests/test_heatmap_cell_hover.py
git commit -m "feat(v25): item 06 — sel heatmap tersorot + tooltip memudar"
```

---

## Task 15: `grow_bar()` + item 07 (bar Rekap Dinas)

`_draw_metric_bar` menggambar dari `canvas._pct` (`dinas_recap.py:81`), jadi
menumbuhkan bar cukup dengan men-tween `_pct`.

**Files:**
- Modify: `src/ui/motion.py`, `src/ui/screens/dinas_recap.py`
- Test: `tests/test_motion_bars.py`

- [ ] **Step 1: Tulis tes yang gagal**

```python
# tests/test_motion_bars.py
"""Item 07 — bar papan peringkat tumbuh dari nol."""
import customtkinter as ctk

from src.ui import motion
from src.ui.screens.dinas_recap import _make_metric_bar


def test_bar_mendarat_di_persen_tujuan_saat_motion_mati(tk_root):
    motion.set_enabled(False)
    host = ctk.CTkFrame(tk_root)
    bar = _make_metric_bar(host, "#0D9488")
    motion.grow_bar(bar, 76)
    assert bar._pct == 76
    host.destroy()


def test_bar_nol_persen_tetap_nol(tk_root):
    motion.set_enabled(False)
    host = ctk.CTkFrame(tk_root)
    bar = _make_metric_bar(host, "#0D9488")
    bar._pct = 50
    motion.grow_bar(bar, 0)
    assert bar._pct == 0
    host.destroy()
```

- [ ] **Step 2: Jalankan tes, pastikan GAGAL**

Run: `.venv/Scripts/python.exe -m pytest tests/test_motion_bars.py -v`
Expected: FAIL — `AttributeError: module 'src.ui.motion' has no attribute 'grow_bar'`

- [ ] **Step 3: Tambahkan penolong ke `motion.py`**

```python
# ─────────────────────────────────────────────── penolong: bar Canvas

def grow_bar(bar_canvas, to_pct: float, duration_ms: int = None) -> None:
    """Tumbuhkan bar metrik Rekap Dinas dari 0 ke `to_pct`.

    Bar-nya Canvas yang menggambar dari atribut `_pct`, jadi menumbuhkannya
    hanya soal men-tween satu angka lalu menggambar ulang — 1,74 ms per frame
    untuk 15 bar sekaligus.
    """
    from src.ui.theme import MOTION_SLOW
    from src.ui.screens.dinas_recap import _draw_metric_bar
    if duration_ms is None:
        duration_ms = MOTION_SLOW
    cancel_for(bar_canvas)

    def frame(t):
        bar_canvas._pct = to_pct * t
        _draw_metric_bar(bar_canvas)

    tween(bar_canvas, duration_ms, frame,
          on_done=lambda: (setattr(bar_canvas, "_pct", to_pct),
                           _draw_metric_bar(bar_canvas)))
```

> **Catatan impor melingkar:** `_draw_metric_bar` diimpor **di dalam fungsi**,
> bukan di tingkat modul, karena `dinas_recap.py` mengimpor `motion`.

- [ ] **Step 4: Pasang di `_MetricPanel.render`**

Di `dinas_recap.py`, di tempat `bar._pct` dipasang lalu `_draw_metric_bar`
dipanggil, ganti menjadi:

```python
            if animate:
                motion.grow_bar(entry["bar"], r["bar_pct"])
            else:
                entry["bar"]._pct = r["bar_pct"]
                _draw_metric_bar(entry["bar"])
```

Di `DinasRecapScreen`, tambahkan `self._anim_sig = motion.RenderSignature()` dan
teruskan `animate = self._anim_sig.changed(data_version.get(), self._month, self._span, self._paparan_span)`
ke `render()`.

- [ ] **Step 5: Jalankan tes, pastikan LULUS**

Run: `.venv/Scripts/python.exe -m pytest tests/test_motion_bars.py tests/test_dinas_recap_screen.py -v`
Expected: PASS

- [ ] **Step 6: Suite penuh + commit**

```bash
.venv/Scripts/python.exe -m pytest -q
git add src/ui/motion.py src/ui/screens/dinas_recap.py tests/test_motion_bars.py
git commit -m "feat(v25): item 07 — bar papan peringkat tumbuh dari nol"
```

---

## Task 16: `fade_window()` + item 08 (toast/dialog) + item 12 (jendela utama)

`-alpha` sudah diverifikasi berfungsi di mesin target untuk Toplevel (0,23 ms)
maupun root (0,41 ms). Ini satu-satunya tempat di seluruh aplikasi yang bisa
memudar sungguhan.

**Files:**
- Modify: `src/ui/motion.py`, `src/ui/components/toast.py`,
  `src/ui/components/message_dialog.py`, `src/ui/app.py`, `main.py`
- Test: `tests/test_motion_fade.py`

- [ ] **Step 1: Tulis tes yang gagal**

```python
# tests/test_motion_fade.py
"""Item 08 & 12 — satu-satunya fade sungguhan yang mungkin di Tk."""
import tkinter as tk

from src.ui import motion


def test_fade_window_berakhir_di_alpha_penuh(tk_root):
    motion.set_enabled(False)
    top = tk.Toplevel(tk_root)
    try:
        motion.fade_window(top)
        assert float(top.attributes("-alpha")) == 1.0
    finally:
        top.destroy()


def test_fade_window_aman_di_jendela_yang_sudah_hancur(tk_root):
    motion.set_enabled(True)
    top = tk.Toplevel(tk_root)
    motion.fade_window(top)
    top.destroy()
    tk_root.update()          # tidak boleh melempar TclError


def test_fade_window_tidak_meledak_bila_alpha_tak_didukung(tk_root, monkeypatch):
    """Di platform tanpa dukungan -alpha, jendela harus tetap tampil penuh."""
    motion.set_enabled(True)
    top = tk.Toplevel(tk_root)
    try:
        def boom(*a, **k):
            raise tk.TclError("bad option -alpha")
        monkeypatch.setattr(top, "attributes", boom)
        motion.fade_window(top)     # tidak boleh melempar
    finally:
        top.destroy()
```

- [ ] **Step 2: Jalankan tes, pastikan GAGAL**

Run: `.venv/Scripts/python.exe -m pytest tests/test_motion_fade.py -v`
Expected: FAIL — `AttributeError: module 'src.ui.motion' has no attribute 'fade_window'`

- [ ] **Step 3: Tambahkan penolong ke `motion.py`**

```python
# ─────────────────────────────────────────────── penolong: fade jendela

def fade_window(window, duration_ms: int = None) -> None:
    """Munculkan Toplevel/root dengan memudar dari transparan ke penuh.

    Widget Tk tidak punya kanal alpha, tapi JENDELA punya — di Windows.
    Ini satu-satunya tempat di seluruh aplikasi yang bisa memudar sungguhan,
    dan biayanya praktis nol (0,23 ms per frame).

    Kalau platform tidak mendukung -alpha, jendela tetap tampil penuh:
    tanpa fade lebih baik daripada tanpa jendela.
    """
    from src.ui.theme import MOTION_FADE
    if duration_ms is None:
        duration_ms = MOTION_FADE

    def _set(value: float) -> bool:
        try:
            window.attributes("-alpha", value)
            return True
        except tk.TclError:
            return False

    if not _set(0.0):
        _set(1.0)
        return
    tween(window, duration_ms, lambda t: _set(t), on_done=lambda: _set(1.0),
          easing=linear)
```

- [ ] **Step 4: Pasang di toast**

Di `src/ui/components/toast.py`, ganti baris 108:

```python
    # Modal + focus, but grab AFTER window is ready (otherwise grab fails)
    toast.after(50, lambda: (toast.grab_set(), toast.focus_set()))
    motion.fade_window(toast)       # v25 item 08
    toast.wait_window()
```

Tambahkan `from src.ui import motion` di atas.

- [ ] **Step 5: Pasang di message_dialog**

Di `src/ui/components/message_dialog.py`, tepat setelah
`self.after(50, self._deferred_grab)` (baris 87):

```python
        motion.fade_window(self)     # v25 item 08
```

- [ ] **Step 6: Pasang di jendela utama (item 12)**

Di `src/ui/app.py`, di akhir `HRApp.__init__` setelah `self._show("Dashboard")`:

```python
        # Jendela utama memudar masuk (v25 item 12). Sebelumnya splash menutup
        # lalu jendela ini menjeplak muncul dengan widget bermunculan satu per
        # satu — bagian paling kasar dari pengalaman, dan yang pertama dilihat.
        motion.fade_window(self)
```

Muat preferensi motion dari DB sebelum layar pertama dibangun — tambahkan di
`__init__` sebelum `self._build_sidebar()`:

```python
        try:
            from src.config import DB_PATH
            from src.db.connection import get_connection
            with get_connection(DB_PATH) as conn:
                motion.load_enabled_from_db(conn)
        except Exception:
            pass    # DB belum ada saat first-run wizard; default aktif sudah benar
```

- [ ] **Step 7: Jalankan tes, pastikan LULUS**

Run: `.venv/Scripts/python.exe -m pytest tests/test_motion_fade.py -v`
Expected: PASS (3 tes)

- [ ] **Step 8: Suite penuh + commit**

```bash
.venv/Scripts/python.exe -m pytest -q
git add src/ui/motion.py src/ui/components/toast.py src/ui/components/message_dialog.py src/ui/app.py tests/test_motion_fade.py
git commit -m "feat(v25): item 08+12 — toast, dialog, dan jendela utama memudar masuk"
```

---

## Task 17: `flash()` + item 10 (baris resolve) + item 17 (riwayat)

**Files:**
- Modify: `src/ui/motion.py`, `src/ui/screens/resolve_base.py`,
  `src/ui/components/history_list.py`
- Test: `tests/test_motion_flash.py`

- [ ] **Step 1: Tulis tes yang gagal**

```python
# tests/test_motion_flash.py
"""Item 10 & 17 — kilat pada baris yang baru berubah."""
from tkinter import ttk
import customtkinter as ctk

from src.ui import motion
from src.ui.components.tree_style import style_treeview


def test_flash_row_mengembalikan_latar_semula(tk_root):
    motion.set_enabled(False)
    style_treeview("Fl.Treeview")
    t = ttk.Treeview(tk_root, style="Fl.Treeview", show="tree", height=3)
    t.insert("", "end", iid="a", text="Andi")
    try:
        motion.flash_row(t, "a", "#10B981", "#141414")
        assert t.tag_configure(motion.FLASH_TAG, "background") in ("#141414", "")
    finally:
        t.destroy()


def test_flash_row_pada_baris_yang_sudah_lenyap_tidak_meledak(tk_root):
    motion.set_enabled(True)
    style_treeview("Fl2.Treeview")
    t = ttk.Treeview(tk_root, style="Fl2.Treeview", show="tree", height=3)
    t.insert("", "end", iid="a", text="Andi")
    motion.flash_row(t, "a", "#10B981", "#141414")
    t.delete("a")
    tk_root.update()          # tidak boleh melempar


def test_flash_widget_mengembalikan_warna_semula(tk_root):
    motion.set_enabled(False)
    f = ctk.CTkFrame(tk_root, fg_color="#141414")
    try:
        motion.flash_widget(f, "#10B981", "#141414")
        assert f.cget("fg_color") == "#141414"
    finally:
        f.destroy()


def test_history_list_menandai_baris_teratas_saat_diminta(tk_root):
    """Item 17: hasil kerja yang barusan dilakukan muncul sebagai baris
    teratas yang tampilannya identik dengan baris lama."""
    from src.ui.components.history_list import HistoryList, HistoryRow
    motion.set_enabled(False)
    hl = HistoryList(tk_root, header="RIWAYAT", empty_text="kosong")
    try:
        hl.set_rows([HistoryRow(time="10:00", text="Laporan Juli.xlsx", tag="OK")],
                    flash_first=True)
        assert hl._first_row is not None
    finally:
        hl.destroy()
```

- [ ] **Step 2: Jalankan tes, pastikan GAGAL**

Run: `.venv/Scripts/python.exe -m pytest tests/test_motion_flash.py -v`
Expected: FAIL — `AttributeError: module 'src.ui.motion' has no attribute 'flash_row'`

- [ ] **Step 3: Tambahkan penolong ke `motion.py`**

```python
# ─────────────────────────────────────────────── penolong: kilat

FLASH_TAG = "rowflash"


def flash_row(tree, iid: str, from_color: str, to_color: str,
              duration_ms: int = None) -> None:
    """Kilatkan satu baris Treeview lalu pudarkan kembali ke warna biasa.

    Setelah aksi resolve, daftar tersusun ulang dan tidak ada apa pun yang
    memberi tahu baris mana yang barusan berubah — pada daftar panjang user
    harus mencarinya sendiri.

    Men-tween tag_configure memakan 9,83 ms per frame. Mahal untuk hover,
    tapi ini hanya berjalan sekali per aksi.
    """
    from src.ui.theme import MOTION_FLASH
    if duration_ms is None:
        duration_ms = MOTION_FLASH

    tree.tag_configure(FLASH_TAG, background=from_color)
    try:
        tags = [t for t in tree.item(iid, "tags") if t != FLASH_TAG]
        tree.item(iid, tags=tuple(tags) + (FLASH_TAG,))
    except tk.TclError:
        return

    def restore():
        try:
            keep = [t for t in tree.item(iid, "tags") if t != FLASH_TAG]
            tree.item(iid, tags=tuple(keep))
        except tk.TclError:
            pass

    tween(tree, duration_ms,
          lambda t: tree.tag_configure(FLASH_TAG,
                                       background=lerp_hex(from_color, to_color, t)),
          on_done=restore, easing=linear)


def flash_widget(widget, from_color: str, to_color: str,
                 duration_ms: int = None) -> None:
    """Versi kilat untuk widget CTk (kartu, baris riwayat)."""
    from src.ui.theme import MOTION_FLASH
    if duration_ms is None:
        duration_ms = MOTION_FLASH
    cancel_for(widget)
    tween(widget, duration_ms,
          lambda t: widget.configure(fg_color=lerp_hex(from_color, to_color, t)),
          on_done=lambda: widget.configure(fg_color=to_color), easing=linear)
```

- [ ] **Step 4: Pasang di `resolve_base.py` (item 10)**

Di `_reload()`, setelah baris dimasukkan ke tree, kilatkan baris yang baru
diselesaikan. Simpan iid target sebelum reload:

```python
    def _flash_after_reload(self, iid: str) -> None:
        """Tandai baris yang barusan berubah (v25 item 10)."""
        motion.flash_row(self.resolved_tree, iid, COLOR_SUCCESS, ZEBRA_ODD)
```

Panggil dari jalur resolve setelah `self._reload()`.

- [ ] **Step 5: Pasang di `history_list.py` (item 17)**

Ubah tanda tangan `set_rows`:

```python
    def set_rows(self, rows: list, *, flash_first: bool = False) -> None:
        """Bangun ulang seluruh daftar.

        `flash_first=True` mengilatkan baris teratas — dipakai saat rebuild
        dipicu oleh aksi user (import/export baru selesai), supaya hasil
        kerjanya tidak muncul sebagai baris yang tampak identik dengan yang
        lama. JANGAN dinyalakan saat rebuild dipicu on_show.
        """
```

Simpan referensi baris pertama di `_render_row` dan kilatkan:

```python
        self._first_row = None
        for i, r in enumerate(rows):
            row = self._render_row(r)
            if i == 0:
                self._first_row = row
        if flash_first and self._first_row is not None:
            motion.flash_widget(self._first_row, COLOR_SUCCESS_TINT_BG, COLOR_SURFACE)
```

Buat `_render_row` mengembalikan `row`.

Pemanggil yang harus memakai `flash_first=True`: `import_screen.py:648`,
`export.py:687`, `export.py:909`. Yang **tidak** boleh: `import_screen.py:403`,
`export.py:447`, `export.py:868` (jalur on_show/inisialisasi).

- [ ] **Step 6: Jalankan tes, pastikan LULUS**

Run: `.venv/Scripts/python.exe -m pytest tests/test_motion_flash.py -v`
Expected: PASS (4 tes)

- [ ] **Step 7: Suite penuh + commit**

```bash
.venv/Scripts/python.exe -m pytest -q
git add src/ui/motion.py src/ui/screens/resolve_base.py src/ui/components/history_list.py src/ui/screens/import_screen.py src/ui/screens/export.py tests/test_motion_flash.py
git commit -m "feat(v25): item 10+17 — kilat pada baris yang baru berubah"
```

---

## Task 18: Item 16 — Outlier akhirnya memberi konfirmasi

**Menutup cacat terkuat dari sisiran:** `outlier.py` tidak memanggil `feedback`
maupun toast **satu kali pun**. Kartu pegawai melompat ke seksi lain yang sering
di luar viewport, tanpa konfirmasi apa pun.

**Files:**
- Modify: `src/ui/screens/outlier.py:263-282`
- Test: `tests/test_outlier_feedback.py`

- [ ] **Step 1: Tulis tes yang gagal**

```python
# tests/test_outlier_feedback.py
"""Item 16 — exclude/revert di Outlier akhirnya mengonfirmasi dirinya."""
import pytest

from src.db.schema import init_db
from src.db.connection import get_connection
from src.db.settings import set_setting
from src.db.employees import upsert_employee


@pytest.fixture
def dbp(tmp_path):
    p = tmp_path / "hr.db"
    init_db(p)
    with get_connection(p) as conn:
        set_setting(conn, "current_month", "2026-07")
        upsert_employee(conn, no_staff="S1", nama="Andi", dept="Ops")
    return p


def test_exclude_memunculkan_konfirmasi(tk_root, monkeypatch, dbp):
    """Regresi cacat: sebelumnya tombol ini tidak memberi umpan balik apa pun,
    jadi pada roster panjang ia terasa rusak."""
    from src.ui.screens import outlier as M
    monkeypatch.setattr(M, "DB_PATH", dbp)
    shown = []
    monkeypatch.setattr(M, "show_success_toast",
                        lambda *a, **k: shown.append(a))
    s = M.OutlierScreen(tk_root)
    try:
        with get_connection(dbp) as conn:
            eid = conn.execute("SELECT id FROM employees WHERE nama='Andi'").fetchone()["id"]
        s._on_exclude(eid)
        assert shown, "exclude tidak mengonfirmasi apa pun"
    finally:
        s.destroy()


def test_revert_all_juga_mengonfirmasi(tk_root, monkeypatch, dbp):
    from src.ui.screens import outlier as M
    monkeypatch.setattr(M, "DB_PATH", dbp)
    shown = []
    monkeypatch.setattr(M, "show_success_toast", lambda *a, **k: shown.append(a))
    s = M.OutlierScreen(tk_root)
    try:
        s._on_revert_all()
        assert shown
    finally:
        s.destroy()
```

- [ ] **Step 2: Jalankan tes, pastikan GAGAL**

Run: `.venv/Scripts/python.exe -m pytest tests/test_outlier_feedback.py -v`
Expected: FAIL — `AttributeError: module 'src.ui.screens.outlier' has no attribute 'show_success_toast'`

- [ ] **Step 3: Tulis implementasi**

Di `src/ui/screens/outlier.py`, tambahkan impor:

```python
from src.ui.components.toast import show_success_toast
```

Ganti ketiga aksi:

```python
    def _on_exclude(self, employee_id: int):
        with get_connection(DB_PATH) as conn:
            exclude_employee(conn, employee_id, self._month)
            nama = conn.execute(
                "SELECT nama FROM employees WHERE id=?", (employee_id,)
            ).fetchone()["nama"]
            conn.commit()
        notify_data_changed()
        self._render()
        # v25 item 16 — sebelumnya layar ini tidak memanggil toast maupun
        # feedback SATU KALI PUN. Kartu melompat ke seksi lain yang sering
        # di luar viewport, jadi tombolnya terasa rusak di roster panjang.
        show_success_toast(self, "Dikecualikan",
                           f"{nama} tidak lagi dihitung di bulan ini.")

    def _on_revert(self, employee_id: int):
        with get_connection(DB_PATH) as conn:
            revert_employee(conn, employee_id, self._month)
            nama = conn.execute(
                "SELECT nama FROM employees WHERE id=?", (employee_id,)
            ).fetchone()["nama"]
            conn.commit()
        notify_data_changed()
        self._render()
        show_success_toast(self, "Disertakan kembali",
                           f"{nama} kembali dihitung di bulan ini.")

    def _on_revert_all(self):
        with get_connection(DB_PATH) as conn:
            revert_all(conn, self._month)
            conn.commit()
        notify_data_changed()
        self._render()
        show_success_toast(self, "Semua disertakan",
                           "Seluruh pengecualian bulan ini dibatalkan.")
```

- [ ] **Step 4: Jalankan tes, pastikan LULUS**

Run: `.venv/Scripts/python.exe -m pytest tests/test_outlier_feedback.py -v`
Expected: PASS (2 tes)

- [ ] **Step 5: Suite penuh + commit**

```bash
.venv/Scripts/python.exe -m pytest -q
git add src/ui/screens/outlier.py tests/test_outlier_feedback.py
git commit -m "fix(v25): item 16 — Outlier akhirnya mengonfirmasi aksinya"
```

---

## Task 19: `busy_pulse()` + item 11 (BusyGuard) + item 18 (Export/Settings)

Saat ini `BusyGuard` memasang teks **diam** "Memproses…". Untuk operasi lama,
aplikasi jadi tidak bisa dibedakan dari aplikasi yang hang.

**Files:**
- Modify: `src/ui/motion.py`, `src/ui/tasks.py`, `src/ui/screens/export.py`,
  `src/ui/screens/settings.py`
- Test: `tests/test_motion_busy.py`

- [ ] **Step 1: Tulis tes yang gagal**

```python
# tests/test_motion_busy.py
"""Item 11 & 18 — indikator sibuk yang membuktikan proses masih hidup."""
import customtkinter as ctk

from src.ui import motion
from src.ui.tasks import BusyGuard


def test_teks_sibuk_dipasang_saat_acquire(tk_root):
    motion.set_enabled(False)
    btn = ctk.CTkButton(tk_root, text="Export")
    guard = BusyGuard(btn, busy_text="Memproses")
    try:
        assert guard.acquire() is True
        assert "Memproses" in btn.cget("text")
    finally:
        guard.release()
        btn.destroy()


def test_release_mengembalikan_teks_asli(tk_root):
    motion.set_enabled(False)
    btn = ctk.CTkButton(tk_root, text="Export Laporan")
    guard = BusyGuard(btn, busy_text="Memproses")
    try:
        guard.acquire()
        guard.release()
        assert btn.cget("text") == "Export Laporan"
    finally:
        btn.destroy()


def test_denyut_berhenti_setelah_release(tk_root):
    """Regresi kebocoran: timer denyut harus mati bersama release, kalau
    tidak ia akan terus menulis ke tombol yang sudah kembali normal."""
    motion.set_enabled(True)
    btn = ctk.CTkButton(tk_root, text="Export")
    guard = BusyGuard(btn, busy_text="Memproses")
    guard.acquire()
    tk_root.update()
    guard.release()
    after = btn.cget("text")
    for _ in range(6):
        tk_root.update()
    assert btn.cget("text") == after, "denyut masih menulis setelah release"
    btn.destroy()


def test_settings_backup_memakai_busy_guard(tk_root):
    """Item 18: settings.py sebelumnya tidak punya run_bg, BusyGuard,
    maupun ProgressModal sama sekali."""
    import inspect
    import src.ui.screens.settings as mod
    src = inspect.getsource(mod)
    assert "BusyGuard" in src, "backup/restore masih tanpa indikator apa pun"
```

- [ ] **Step 2: Jalankan tes, pastikan GAGAL**

Run: `.venv/Scripts/python.exe -m pytest tests/test_motion_busy.py -v`
Expected: FAIL pada `test_denyut_berhenti_setelah_release` dan
`test_settings_backup_memakai_busy_guard`

- [ ] **Step 3: Tambahkan penolong ke `motion.py`**

```python
# ─────────────────────────────────────────────── penolong: denyut sibuk

_BUSY_FRAMES = ("·  ", "·· ", "···", " ··", "  ·")
_BUSY_MS = 130


def busy_pulse(widget, base_text: str) -> Optional[str]:
    """Animasikan titik pada teks widget selama operasi panjang berjalan.

    Teks diam "Memproses…" membuat aplikasi tidak bisa dibedakan dari
    aplikasi yang hang — dan user baru tahu bedanya setelah menunggu terlalu
    lama. Titik yang bergerak membuktikan proses masih hidup.

    Ini yang termurah dari seluruh animasi (0,36 ms per frame) dan mungkin
    yang paling berguna. Mengembalikan id timer; hentikan dengan
    `stop_busy_pulse(widget, job)`.

    Berjalan juga saat motion dimatikan? TIDAK — saat mati, teks diam saja
    dipasang. Sakelar itu ada untuk mesin bermasalah, dan denyut ini bukan
    pengecualian.
    """
    if not _enabled:
        widget.configure(text=f"{base_text}…")
        return None

    state = {"i": 0, "job": None}

    def tick():
        try:
            widget.configure(text=f"{base_text} {_BUSY_FRAMES[state['i'] % len(_BUSY_FRAMES)]}")
        except tk.TclError:
            return                  # widget lenyap saat operasi masih jalan
        state["i"] += 1
        job = widget.after(_BUSY_MS, tick)
        state["job"] = job
        _register(widget, job)
        widget._busy_job = job

    tick()
    return state["job"]


def stop_busy_pulse(widget) -> None:
    """Hentikan denyut. Aman dipanggil walau denyutnya tidak pernah mulai."""
    job = getattr(widget, "_busy_job", None)
    if job is None:
        return
    try:
        widget.after_cancel(job)
    except tk.TclError:
        pass
    _forget(widget, job)
    widget._busy_job = None
```

- [ ] **Step 4: Pasang di `BusyGuard`**

Di `src/ui/tasks.py`, di `acquire()` tempat `busy_text` dipasang pada tombol
pertama, ganti menjadi:

```python
            motion.busy_pulse(btn, self._busy_text)     # v25 item 11
```

dan di `release()`, sebelum teks dikembalikan:

```python
            motion.stop_busy_pulse(btn)
```

Tambahkan `from src.ui import motion` di `tasks.py`.

- [ ] **Step 5: Pasang di Export dan Settings (item 18)**

Di `src/ui/screens/export.py._pick()` (baris 648), bungkus dry-run dengan
`BusyGuard` pada tombol Browse.

Di `src/ui/screens/settings.py`, bungkus `_do_manual_backup`, `_restore`, dan
`_delete_backup` dengan `BusyGuard` pada tombolnya masing-masing.

> **Jangan naikkan ini jadi prioritas atas dasar angka yang salah.** Sisiran
> sempat melaporkan Backup membekukan aplikasi karena menyalin database
> "ratusan MB"; database produksi sebenarnya **84 KB**. Lubang strukturnya
> nyata, dampak praktisnya tidak ada. Cukup `BusyGuard` — jangan tambahkan
> `run_bg` atau `ProgressModal` di sini.

- [ ] **Step 6: Jalankan tes, pastikan LULUS**

Run: `.venv/Scripts/python.exe -m pytest tests/test_motion_busy.py -v`
Expected: PASS (4 tes)

- [ ] **Step 7: Suite penuh + commit**

```bash
.venv/Scripts/python.exe -m pytest -q
git add src/ui/motion.py src/ui/tasks.py src/ui/screens/export.py src/ui/screens/settings.py tests/test_motion_busy.py
git commit -m "feat(v25): item 11+18 — indikator sibuk yang benar-benar bergerak"
```

---

## Task 20: Sakelar "Matikan animasi" di Settings

**Files:**
- Modify: `src/ui/screens/settings.py`
- Test: `tests/test_settings_motion_toggle.py`

- [ ] **Step 1: Tulis tes yang gagal**

```python
# tests/test_settings_motion_toggle.py
"""Sakelar animasi — jaring pengaman untuk laptop yang belum pernah diukur."""
import pytest

from src.db.schema import init_db
from src.db.connection import get_connection
from src.db.settings import get_setting


@pytest.fixture
def dbp(tmp_path):
    p = tmp_path / "hr.db"
    init_db(p)
    return p


def test_mematikan_menulis_setting_dan_berlaku_seketika(tk_root, monkeypatch, dbp):
    from src.ui import motion
    from src.ui.screens import settings as M
    monkeypatch.setattr(M, "DB_PATH", dbp)
    s = M.SettingsScreen(tk_root)
    try:
        s._on_motion_toggle(False)
        with get_connection(dbp) as conn:
            assert get_setting(conn, "motion_enabled") == "0"
        assert motion.enabled() is False
    finally:
        s.destroy()


def test_menyalakan_kembali_menulis_satu(tk_root, monkeypatch, dbp):
    from src.ui import motion
    from src.ui.screens import settings as M
    monkeypatch.setattr(M, "DB_PATH", dbp)
    s = M.SettingsScreen(tk_root)
    try:
        s._on_motion_toggle(False)
        s._on_motion_toggle(True)
        with get_connection(dbp) as conn:
            assert get_setting(conn, "motion_enabled") == "1"
        assert motion.enabled() is True
    finally:
        s.destroy()
```

- [ ] **Step 2: Jalankan tes, pastikan GAGAL**

Run: `.venv/Scripts/python.exe -m pytest tests/test_settings_motion_toggle.py -v`
Expected: FAIL — `AttributeError: 'SettingsScreen' object has no attribute '_on_motion_toggle'`

- [ ] **Step 3: Tulis implementasi**

Tambahkan ke `SettingsScreen` (di tab Tampilan/Umum, mengikuti pola switch yang
sudah ada di berkas itu):

```python
    def _on_motion_toggle(self, value: bool) -> None:
        """Sakelar animasi. Berlaku seketika untuk animasi berikutnya;
        tween yang sedang berjalan dibiarkan selesai."""
        with get_connection(DB_PATH) as conn:
            set_setting(conn, motion.SETTING_KEY, "1" if value else "0")
            conn.commit()
        motion.set_enabled(value)
```

Dan widget-nya:

```python
        self._motion_switch = ctk.CTkSwitch(
            parent, text="Animasi antarmuka",
            command=lambda: self._on_motion_toggle(bool(self._motion_switch.get())),
            progress_color=COLOR_ACCENT,
        )
        self._motion_switch.pack(anchor="w", padx=SPACE_LG, pady=SPACE_SM)
        if motion.enabled():
            self._motion_switch.select()
        else:
            self._motion_switch.deselect()
```

Tambahkan `from src.ui import motion`.

- [ ] **Step 4: Jalankan tes, pastikan LULUS**

Run: `.venv/Scripts/python.exe -m pytest tests/test_settings_motion_toggle.py -v`
Expected: PASS (2 tes)

- [ ] **Step 5: Suite penuh + commit**

```bash
.venv/Scripts/python.exe -m pytest -q
git add src/ui/screens/settings.py tests/test_settings_motion_toggle.py
git commit -m "feat(v25): sakelar Animasi antarmuka di Settings"
```

---

## Task 21: Versi + APP_CHANGELOG

**Files:**
- Modify: `src/config.py`
- Test: `tests/test_changelog_v25.py`

- [ ] **Step 1: Tulis tes yang gagal**

```python
# tests/test_changelog_v25.py
from src import config


def test_versi_naik_ke_25():
    assert config.APP_VERSION == "25.0.0"


def test_changelog_punya_entri_v25_paling_atas():
    entry = config.APP_CHANGELOG[0]
    assert entry["version"] == "25.0.0"
    assert entry["date"] == "2026-08-20"
    blob = " ".join(d for _, d in entry["changes"]).lower()
    assert "animasi" in blob


def test_changelog_menyebut_perbaikan_bukan_hanya_hiasan():
    entry = config.APP_CHANGELOG[0]
    kinds = {k for k, _ in entry["changes"]}
    assert "fix" in kinds, "4 dari 17 item menutup cacat — harus tercermin"
    assert "feat" in kinds


def test_entri_lama_tetap_ada():
    versions = [e["version"] for e in config.APP_CHANGELOG]
    for v in ("24.0.2", "24.0.1", "24.0.0"):
        assert v in versions
```

- [ ] **Step 2: Jalankan tes, pastikan GAGAL**

Run: `.venv/Scripts/python.exe -m pytest tests/test_changelog_v25.py -v`
Expected: FAIL — `assert '24.0.2' == '25.0.0'`

- [ ] **Step 3: Tulis implementasi**

Di `src/config.py`, ubah `APP_VERSION = "25.0.0"` dan
`APP_BUILD_DATE = "2026-08-20"`, lalu tambahkan di paling atas `APP_CHANGELOG`:

```python
    {
        "version": "25.0.0",
        "date": "2026-08-20",
        "changes": [
            ("feat", "Antarmuka kini bergerak: hover menu, garis menu aktif meluncur, angka Dashboard berhitung naik, sel Heatmap menyala menyapu, dan bar Rekap Dinas tumbuh dari nol."),
            ("feat", "Toast, dialog, dan jendela utama memudar masuk, bukan menjeplak."),
            ("feat", "Baris yang baru berubah berkilat sebentar di Issues, Severe Lateness, Coaching, dan daftar Riwayat — jadi hasil kerjamu tidak lagi hilang di tengah daftar."),
            ("fix", "Outlier akhirnya mengonfirmasi aksinya. Sebelumnya mengecualikan pegawai tidak memberi umpan balik apa pun dan kartunya melompat ke luar layar."),
            ("fix", "Kartu ringkasan Coaching berhenti berkedip setiap kali status coaching diubah."),
            ("fix", "Chip Bulan Aktif di sidebar kini bereaksi saat disorot — sebelumnya bisa diklik tapi tidak ada tandanya."),
            ("fix", "Baris tabel di Coaching dan Settings kini menyorot saat dilewati kursor."),
            ("feat", "Tombol yang sedang bekerja menampilkan titik bergerak, jadi proses panjang tidak lagi tampak seperti aplikasi yang hang."),
            ("feat", "Sakelar baru di Settings untuk mematikan seluruh animasi."),
        ],
    },
```

- [ ] **Step 4: Jalankan tes, pastikan LULUS**

Run: `.venv/Scripts/python.exe -m pytest tests/test_changelog_v25.py -v`
Expected: PASS (4 tes)

- [ ] **Step 5: Commit**

```bash
git add src/config.py tests/test_changelog_v25.py
git commit -m "chore(v25): naikkan versi ke 25.0.0 + entri changelog"
```

---

## Task 22: Suite penuh + build installer

- [ ] **Step 1: Pastikan .exe tidak sedang berjalan**

```bash
tasklist | grep -i HR-Absensi || echo "tidak berjalan"
```

Kalau berjalan: **JANGAN dimatikan sendiri.** Minta user menutupnya.

- [ ] **Step 2: Catat md5 DB produksi SEBELUM build**

```bash
md5sum "dist/HR-Absensi/data/hr.db"
```

Catat nilainya. Harus tetap sama di Step 7.

- [ ] **Step 3: Suite penuh**

```bash
.venv/Scripts/python.exe -m pytest -q
```

Expected: seluruh tes lulus, nol skip tak terduga.

- [ ] **Step 4: Build installer**

```bash
.venv/Scripts/python.exe -m tools.build_installer
```

Expected: `installer/Output/HR-Absensi-Setup-v25.0.0.exe` terbentuk.

- [ ] **Step 5: Rotasi produksi 2 level**

```bash
cd "dist/HR-Absensi"
mv HR-Absensi.exe.bak HR-Absensi.exe.bak.old
mv HR-Absensi.exe HR-Absensi.exe.bak
# salin .exe hasil build baru ke sini
```

> **`data/` TIDAK PERNAH ikut dipindah.** Hanya berkas .exe yang dirotasi.

- [ ] **Step 6: Salin installer ke titik ambil**

```bash
cp installer/Output/HR-Absensi-Setup-v25.0.0.exe "Installers/HR-Absensi-Setup-v25.0.0.exe"
ls -l "Installers/HR-Absensi-Setup-v25.0.0.exe"
```

- [ ] **Step 7: Verifikasi DB produksi tidak tersentuh**

```bash
md5sum "dist/HR-Absensi/data/hr.db"
```

Expected: **identik** dengan Step 2.

- [ ] **Step 8: Smoke terhadap data realistis**

> **Bukan DB kosong.** Pelajaran v24.0.2: smoke dengan DB kosong tidak akan
> pernah menangkap crash pegawai resign. Salin DB produksi ke scratchpad,
> jalankan .exe terhadap salinan itu, dan sentuh: Dashboard, Heatmap
> (termasuk sapuan + hover sel), Rekap Dinas, satu aksi resolve, satu toast,
> dan sakelar animasi di Settings.

Setelah smoke: hapus salinan DB dari scratchpad.

- [ ] **Step 9: Commit apa pun yang tersisa**

```bash
git status --short
git add -A
git commit -m "build(v25): installer v25.0.0"
```

---

## Task 23: Serah terima

- [ ] **Step 1: Perbarui `memory/version_state.md`** dengan baris untuk v25.0.0.

- [ ] **Step 2: JANGAN push.**

`git push` **selalu** butuh otorisasi eksplisit user (workflow_rules Rule 1).
Laporkan bahwa branch `v25.0.0` siap dan tunggu izin. Saat diizinkan:

```bash
GIT_SSH_COMMAND="C:/Windows/System32/OpenSSH/ssh.exe" git push origin v25.0.0
GIT_SSH_COMMAND="C:/Windows/System32/OpenSSH/ssh.exe" git push origin v25.0.0:latest
```

- [ ] **Step 3: Hentikan server brainstorm**

```bash
ls .superpowers/brainstorm/
# hentikan sesi yang masih hidup
```
