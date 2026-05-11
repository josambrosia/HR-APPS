# Dashboard Performance Refactor — Design Spec

**Tanggal:** 2026-05-12
**Status:** Approved (ready for implementation plan)
**Author:** Brainstorming session
**Target file utama:** [src/ui/screens/dashboard.py](../../../src/ui/screens/dashboard.py)

---

## 1. Konteks & Problem

Setelah MVP + serangkaian iterasi (lihat `2026-05-11-hr-absensi-app-design.md` Part II),
`DashboardScreen` punya per-period query cache (`self._query_cache`) yang
seharusnya bikin tab switch instan. Realita: switch antar pill di `WeekNavBar`
(Semua / Minggu 1 / Minggu 2 / dst.) tetap memakan **1-2 detik**, bahkan saat
balik ke periode yang sudah pernah dibuka dalam sesi yang sama.

### Root cause (diagnosis)

Cache hanya memoize hasil SQL. Tapi `_update_data()` **selalu destroy lalu
recreate semua row widget** di 5 panel kiri + Ranking Lengkap di kanan, untuk
setiap tab switch. customtkinter (`CTkLabel`, `CTkFrame`) mahal untuk
di-create karena di-back oleh `tk.Canvas` + `PIL.Image` (rounded corners,
fg_color blending, dll). Per widget biaya ~5-10 ms.

Hitungan kasar untuk dataset normal (~30 pegawai):

| Panel | Rows | Widgets/row | Total widget |
|---|---|---|---|
| Top 5 Late | 5 | 3 | 15 |
| Top 5 Teladan | 5 | 3 | 15 |
| Coaching (Mingguan) | ~10 | 3 | 30 |
| Dept | ~4 | 3 | 12 |
| Hari Rawan | ~5 | 3 | 15 |
| Ranking Lengkap | ~30 | 6 | 180 |
| **Total** | | | **~270** |

270 widget × ~5-10 ms = **1.3-2.7 detik per tab switch.** Cocok dengan gejala.

---

## 2. Goals & Non-Goals

### Goals
- Tab switch end-to-end **<100 ms** untuk dataset normal (≤50 pegawai)
- Preserve visual design (theme purple/orange/gold, medals, accent colors)
- Code consistency dengan pola Treeview di [issues.py](../../../src/ui/screens/issues.py)
- Tidak ada regression di test suite (69 passing)

### Non-Goals
- Tidak refactor query layer (`src/core/insights.py`) — SQL bukan bottleneck
- Tidak ubah `_query_cache` invalidation logic — cache per screen instance sudah benar
- Tidak ubah print/PDF flow
- Tidak migrasi Top 5 / Coaching / Dept / Hari panel ke Treeview (visual mereka pakai
  emoji + warna accent yang sulit di-replicate di ttk; pool sudah cukup)
- Tidak tambah unit test baru (perubahan UI internal; existing tests cover data layer)

---

## 3. Approach yang dipilih (Hybrid)

| Komponen | Solusi | Alasan |
|---|---|---|
| **Ranking Lengkap** (kanan, ~30+ rows) | `ttk.Treeview` | Native, fast, sudah proven di Issues. Insert ~0.1 ms/row vs CTkLabel ~5 ms/row. |
| **5 panel kecil kiri** (Top 5 Late, Top 5 Teladan, Coaching, Dept, Hari Rawan) | **Widget pool** (preallocate + reconfigure) | Pertahankan styling CTk (medals, warna, panel rounded). Tidak ada destroy/create di runtime. |

Ditolak:
- All-Treeview: Top 5 dengan medals + warna sulit di-style di ttk
- All-pool: Ranking 30+ row tetap mahal untuk preallocate; Treeview lebih scalable
- Plain tk widgets (tk.Label/tk.Frame): hanya 10× lebih cepat, mixing widget classes berisiko
  visual inconsistency
- Defer/throttle render: hanya menyamarkan, tidak menyelesaikan

---

## 4. Design — Widget Pool (5 panel kiri)

### 4.1 Pool sizes (dipilih dengan buffer untuk small org)

| Panel | Pool size | Catatan |
|---|---|---|
| Top 5 Late | 5 | Literal Top 5, tidak tumbuh |
| Top 5 Teladan | 5 | Sama |
| Coaching | 20 | Worst case ~all pegawai over threshold; auto-grow kalau terlewati |
| Dept | 8 | Typical 3-5 departments, buffer |
| Hari Rawan | 7 | Max 7 weekdays |

**Total preallocate:** 45 row × 3 widget = **135 widget**. One-time cost di
`_build_static_widgets()`. Estimated ~700 ms tambahan di first dashboard open
— tapi `_update_data()` saat ini juga membuat jumlah serupa, jadi net tidak
lebih lambat.

### 4.2 Struktur per row (di-store di `self._panel_rows[panel_key]`)

```python
{
    "frame": ctk.CTkFrame,  # transparent, holds left+right labels
    "left":  ctk.CTkLabel,  # name / label text
    "right": ctk.CTkLabel,  # value text (color reconfigurable)
}
```

Plus 1 `empty_label` per panel di `self._panel_empty[panel_key]` —
pre-created CTkLabel untuk state "Belum ada data" / "Tidak ada. ✓" dll.
Hidden by default.

### 4.3 Helper APIs

```python
def _make_pool_row(self, panel_key: str) -> dict:
    """Create one row dict. Used at build time + on overflow grow."""
    parent = self._panel_content[panel_key]
    frame = ctk.CTkFrame(parent, fg_color="transparent")
    left  = ctk.CTkLabel(frame, text="", font=(FONT_FAMILY, 11),
                         text_color=COLOR_TEXT, anchor="w")
    right = ctk.CTkLabel(frame, text="", font=(FONT_FAMILY, 11),
                         text_color=COLOR_TEXT, anchor="e")
    left.pack(side="left")
    right.pack(side="right")
    # Hidden until packed by _populate_pool
    return {"frame": frame, "left": left, "right": right}

def _populate_pool(self, panel_key: str, items: list,
                   formatter, empty_text: str) -> None:
    """Reconfigure pool to show `items`. formatter(item) -> (left_text, right_text, right_color)."""
    rows = self._panel_rows[panel_key]
    empty_lbl = self._panel_empty[panel_key]

    if not items:
        empty_lbl.pack(padx=8, pady=4)
        for r in rows:
            r["frame"].pack_forget()
        return

    empty_lbl.pack_forget()
    # Auto-grow on overflow (rare)
    while len(rows) < len(items):
        rows.append(self._make_pool_row(panel_key))

    for i, item in enumerate(items):
        lt, rt, rc = formatter(item)
        rows[i]["frame"].pack(fill="x", padx=6, pady=1)
        rows[i]["left"].configure(text=lt)
        rows[i]["right"].configure(text=rt, text_color=rc)
    for j in range(len(items), len(rows)):
        rows[j]["frame"].pack_forget()
```

### 4.4 Formatter per panel (contoh)

```python
# Top 5 Late
def _fmt_late(r): return r["nama"], f"{r['total_terlambat']} mnt", COLOR_ACCENT

# Top 5 Teladan (with medals)
MEDALS = ["🥇", "🥈", "🥉", "4.", "5."]
def _fmt_teladan(r, idx): return f"{MEDALS[idx]} {r['nama']}", f"skor {r['score']}", COLOR_OK

# Coaching
def _fmt_coaching(r): return r["nama"], f"{r['total_terlambat']} mnt", COLOR_WARN

# Dept
def _fmt_dept(r): return (f"{r['dept']} ({r['pegawai_count']})",
                          f"{r['total_terlambat']} mnt", COLOR_ACCENT)

# Hari Rawan
def _fmt_hari(r): return r["hari"], f"{r['terlambat_count']} hari telat", COLOR_WARN
```

Teladan butuh index-aware formatter (untuk medal) — handle dengan `enumerate`
di call site, atau closure factory. Implementasi rinci ditentukan di plan.

---

## 5. Design — ttk.Treeview untuk Ranking Lengkap

### 5.1 Style setup

Method baru `_setup_treeview_style()` di `__init__` (sebelum
`_build_static_widgets`), mirror pola Issues:

```python
def _setup_treeview_style(self):
    style = ttk.Style()
    try:
        style.theme_use("clam")
    except Exception:
        pass
    style.configure(
        "Ranking.Treeview",
        background=COLOR_PANEL, fieldbackground=COLOR_PANEL,
        foreground=COLOR_TEXT, rowheight=24, borderwidth=0,
    )
    style.configure(
        "Ranking.Treeview.Heading",
        background="#2C1B47", foreground=COLOR_TEXT_DIM,
        relief="flat", font=(FONT_FAMILY, 10, "bold"),
    )
    # No selection map needed (view-only ranking)
```

### 5.2 Treeview construction

Di `_build_static_widgets()`, ganti `CTkScrollableFrame` + custom header CTkLabels:

```python
rank_box = ctk.CTkFrame(self.body, fg_color=COLOR_PANEL, corner_radius=8)
rank_box.grid(row=1, column=1, sticky="nsew")
ctk.CTkLabel(rank_box, text="📋 Ranking Lengkap",
             font=(FONT_FAMILY, 13, "bold"), text_color=COLOR_TEXT
             ).pack(anchor="w", padx=12, pady=(8, 4))

cols = ["nama", "dept", "terlambat", "telat", "tidak_hadir"]
widths = {"nama": 130, "dept": 100, "terlambat": 80,
          "telat": 50, "tidak_hadir": 70}
labels = {"nama": "Nama", "dept": "Dept", "terlambat": "Terlambat",
          "telat": "Telat", "tidak_hadir": "Tdk Hadir"}

self.rank_tree = ttk.Treeview(
    rank_box, columns=cols, show="headings",
    style="Ranking.Treeview", selectmode="none",
)
for c in cols:
    self.rank_tree.heading(c, text=labels[c])
    self.rank_tree.column(c, width=widths[c], anchor="w")
self.rank_tree.pack(fill="both", expand=True, padx=12, pady=(4, 8))
```

Custom header CTkLabel row yang sekarang dihapus — Treeview punya headings
internal yang sudah di-style.

### 5.3 Populate

```python
self.rank_tree.delete(*self.rank_tree.get_children())
for r in data["ranking"]:
    self.rank_tree.insert("", "end", values=(
        r["nama"], r["dept"] or "-",
        f"{r['total_terlambat']} mnt",
        r["hari_telat"], r["tidak_hadir"],
    ))
```

Ranking ~30 row insert estimated ~3 ms.

---

## 6. Refactor `_update_data()`

Sebelum (skema):
```
clear all panel content → loop data → create CTkFrame + CTkLabels per row
```

Sesudah (skema):
```
update KPI labels (sama seperti sekarang)
update coaching panel title (sama)
_populate_pool("late", data["top5_late"], fmt_late, "Tidak ada keterlambatan.")
_populate_pool("teladan", data["top5_teladan"], fmt_teladan_indexed, "Belum ada data.")
_populate_pool("coaching", data["coaching"], fmt_coaching, "Tidak ada. ✓")
_populate_pool("dept", data["dept_rows"], fmt_dept, "Belum ada data.")
_populate_pool("hari", data["day_rows"], fmt_hari, "Belum ada data harian.")
# Ranking
self.rank_tree.delete(*self.rank_tree.get_children())
for r in data["ranking"]:
    self.rank_tree.insert(...)
```

`_clear_panel()`, `_two_col_row()`, `_empty()` dihapus.

---

## 7. Migration Steps (urutan implementasi)

1. **Setup Treeview style:** tambah `_setup_treeview_style()` + dipanggil di `__init__`
2. **Refactor right column:** hapus `CTkScrollableFrame` + custom header CTkLabels, ganti `ttk.Treeview`. Test render manual.
3. **Refactor `make_panel()` helper:** ubah untuk skip `CTkScrollableFrame` path (semua 5 panel kecil pakai plain `CTkFrame` untuk content). Tidak ada lagi panel yang scrollable di kiri.
4. **Tambah pool infrastructure:**
   - `self._panel_rows: dict[str, list[dict]] = {}`
   - `self._panel_empty: dict[str, ctk.CTkLabel] = {}`
   - `_make_pool_row(panel_key)` helper
   - Build pool + empty_label untuk masing-masing dari 5 panel di `_build_static_widgets()`
5. **Tambah `_populate_pool()` helper**
6. **Refactor `_update_data()`:** ganti destroy-rebuild → `_populate_pool` calls + Treeview populate
7. **Cleanup:** hapus `_clear_panel`, `_two_col_row`, `_empty`
8. **Run tests:** `pytest -q` — semua 69 harus tetap pass
9. **Manual smoke test:**
   - Buka Dashboard dengan data ≥1 minggu terimport
   - Switch Semua → Minggu 1 → Minggu 2 → Semua → Minggu 1 (timing perceptual)
   - Cek Coaching panel hide di Bulanan, show di Mingguan
   - Cek empty state (period tanpa data)
   - Cek Print masih jalan

---

## 8. Risks & Edge Cases

| Risk | Mitigation |
|---|---|
| Pool overflow (Coaching >20 pegawai) | Auto-grow di `_populate_pool` — sekali grow, persist sampai screen recreated |
| `grid_remove`/`grid` panel saat layout switch ngarusin pool widgets | Pool widgets di-pack ke `self._panel_content[panel_key]`, ikut visibility parent box. No special handling needed. |
| ttk.Treeview tidak ikut tema dark mode toggle | Issues sudah pakai pattern ini dan stabil; theme app statis purple/orange (tidak ada light mode toggle) |
| First dashboard open agak lebih lambat (pool preallocation) | Acceptable — yang dirasakan user adalah switch latency, dan switch jadi instan |
| Treeview heading font tidak match dengan Issues persis | OK — pakai font/style yang sama (`FONT_FAMILY, 10, "bold"`) |
| `selectmode="none"` di Ranking Treeview menghilangkan keyboard nav | Acceptable — Ranking view-only; user tidak interact dengan row-nya |

---

## 9. Testing

### Unit tests
Tidak ada tambahan baru. Existing 69 tests harus tetap pass (perubahan murni
UI internal; data layer tidak disentuh).

### Manual smoke test (mandatory sebelum commit)
1. `pytest -q` → 69 passed
2. Run app: `python -m src.main`
3. Import 4 minggu data dummy (atau pakai DB existing)
4. Buka Dashboard, switch tab Semua ↔ Minggu 1 ↔ Minggu 2 ↔ Minggu 3
5. **Perceptual benchmark:** tab switch terasa instan (<200 ms). Tidak ada flicker.
6. Toggle Bulanan ↔ Mingguan: Coaching panel hide/show benar
7. Period tanpa data (mis. minggu kosong): empty state muncul di tiap panel
8. Klik Cetak / Export PDF: dialog muncul, generate PDF jalan
9. Cek Ranking Lengkap: 30+ pegawai tetap scroll smooth, header tetap visible

---

## 10. Definition of Done

- [ ] `ttk.Treeview` mengganti `CTkScrollableFrame` di Ranking Lengkap
- [ ] 5 panel kiri pakai widget pool dengan empty state handling
- [ ] `_clear_panel`, `_two_col_row`, `_empty` dihapus dari `dashboard.py`
- [ ] Tab switch perceptual <200 ms (subjektif user)
- [ ] 69 existing tests tetap passing
- [ ] Manual smoke test pass (semua 9 step di Section 9)
- [ ] Tidak ada regression visual (theme tetap purple/orange, medal masih muncul, warna accent benar)
- [ ] Commit terpisah untuk Treeview migration + pool refactor (atau 1 commit kalau scope kecil)

---

*End of spec.*
