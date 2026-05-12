# Brand Integration + UI Shell Polish — Design Spec

**Tanggal:** 2026-05-12
**Status:** Draft (menunggu approval user)
**Author:** Brainstorming session

---

## 1. Konteks & Problem

User sudah generate brand identity **"Josaphat Tech Solution"** di sesi paralel
(branch `claude/eager-nightingale-3845ec`), tinggal integrasi ke app. Sekalian,
beberapa UI shell quirks belum di-polish:

- App default 1180×720 — user harus manual maximize tiap kali buka
- Belum ada loading screen / splash
- Versi app (`APP_VERSION = "0.1.0"`) gak terlihat di mana pun di UI
- `.exe` pakai default PyInstaller icon (penguin generik)
- Window non-responsive — kalau di-resize lebih kecil dari content, isi terpotong

Hybrid approach **(Big A)** dipilih: brand muncul di "entry signature" (splash,
.exe icon, sidebar accent) tanpa overhaul tema utama. App look-and-feel
purple/orange tetap, brand jadi pemanis di edge.

---

## 2. Goals & Non-Goals

### Goals
- `.exe` punya icon JTS (taskbar + file icon di Explorer)
- Splash screen dengan animated GIF logo + tagline + versi (min 2s)
- Sidebar bawah tampilkan versi app + brand credit subtle
- Sidebar atas tampilkan small logo + wordmark
- App start dalam state **maximized** (title bar tetap visible)
- Content area responsive — scrollable kalau window di-resize kecil
- Version bump ke **0.0.1** (per user request, fresh versioning cycle)
- Folder structure rapi: `assets/brand/` + `assets/templates/` (consolidate)

### Non-Goals
- Full theme overhaul ke black/magenta — tetap purple/orange (Hybrid A)
- HTML report header lockup integration — bisa ditambah lain waktu (handoff task #3)
- Theme sync ke brand palette — bisa nanti (handoff task #4)
- True fullscreen mode (no title bar) — pakai maximized (zoomed) saja
- Dark/light mode toggle — out of scope
- Audio splash (sound effects)
- Splash skippable via click — fixed 2s minimum, no skip

---

## 3. Brand Asset Integration

### 3.1 Merge brand branch

```
git merge claude/eager-nightingale-3845ec
```

3 commits brought in:
- `15585e4` — initial assets
- `0cbe370` — palette lock
- `582066b` — config.py + spec registration

**Expected conflicts:** `src/config.py` (BRAND_* constants vs my TEMPLATE_LAPORAN_BULANAN)
and `HR-Absensi.spec` (brand datas vs my template+dashboard themes). Resolve
by accepting both additive sides.

### 3.2 Folder consolidation (tidying)

Move existing `templates/laporan_bulanan_template.xlsx` → `assets/templates/`:

```
assets/
├── brand/                      ← from brand branch
│   ├── icon-04E.svg
│   ├── icon-04E.ico            ← BARU (generated, see 3.3)
│   ├── lockup-04E-dark.svg
│   ├── lockup-04E-light.svg
│   ├── animation-02-typing-04E.svg
│   ├── animation-02-typing-04E.gif
│   ├── animation-02-typing-04E.html
│   ├── README.md
│   └── tools/render_gif.py
└── templates/                  ← MOVED from /templates/
    └── laporan_bulanan_template.xlsx
```

Update affected paths:
- `src/config.py`: `TEMPLATE_LAPORAN_BULANAN = RESOURCE_ROOT / "assets" / "templates" / "laporan_bulanan_template.xlsx"`
- `HR-Absensi.spec` datas tuple: `('assets/templates/laporan_bulanan_template.xlsx', 'assets/templates')`
- `tools/build_template.py`: write to `assets/templates/` instead of `templates/`
- `.gitignore`: negation rule references already cover by pattern

### 3.3 SVG → ICO conversion

Brand provides `icon-04E.svg` (256×256 rounded square). PyInstaller needs `.ico`
(multi-resolution embedded). Convert via Python in a one-time script.

**Strategy:** new script `tools/svg_to_ico.py` uses Pillow + cairosvg to
rasterize SVG → PNG at multiple sizes (16, 32, 48, 64, 128, 256), then bundle
into multi-resolution `.ico` via Pillow's `Image.save()` with `sizes=` param.

**Dependencies:** add `cairosvg` to `requirements-dev.txt` (build-time only,
not runtime). Pillow already a dep.

**Output:** `assets/brand/icon-04E.ico` (committed to repo).

**Fallback if cairosvg fails on Windows (libcairo missing):**
Use Inkscape CLI if installed, OR manual convert via online tool
(https://convertio.co/svg-ico/) and commit the result. Script documents this.

### 3.4 PyInstaller wiring

Update `HR-Absensi.spec`:

1. Add `icon='assets/brand/icon-04E.ico'` to `EXE(...)` block
2. Add ICO + GIF to datas tuple (already partially done by brand branch merge)
3. Add `assets/templates/laporan_bulanan_template.xlsx` (after move)

Final datas tuple (post-merge + reorganize):
```python
datas=[
    ('src/reports/templates/dashboard.html.j2', 'src/reports/templates'),
    ('src/reports/templates/dashboard_v1_editorial.html.j2', 'src/reports/templates'),
    ('src/reports/templates/dashboard_v2_dark_glass.html.j2', 'src/reports/templates'),
    ('src/reports/templates/dashboard_v3_infographic.html.j2', 'src/reports/templates'),
    ('src/reports/templates/dashboard_v4_corporate.html.j2', 'src/reports/templates'),
    ('assets/templates/laporan_bulanan_template.xlsx', 'assets/templates'),
    ('assets/brand/icon-04E.svg', 'assets/brand'),
    ('assets/brand/icon-04E.ico', 'assets/brand'),
    ('assets/brand/lockup-04E-dark.svg', 'assets/brand'),
    ('assets/brand/lockup-04E-light.svg', 'assets/brand'),
    ('assets/brand/animation-02-typing-04E.svg', 'assets/brand'),
    ('assets/brand/animation-02-typing-04E.gif', 'assets/brand'),
],
```

---

## 4. UI Integration

### 4.1 Versioning

`src/config.py`:
```python
APP_VERSION = "0.0.1"          # was "0.1.0" — fresh cycle per user
APP_TAGLINE = "From Concept to Code."     # JTS company tagline
APP_BRAND = "Josaphat Tech Solution"
```

### 4.2 Sidebar — top (logo + wordmark)

Current:
```
[Sidebar]
HR ABSENSI                      ← bold text, font 16
[nav items below]
```

New:
```
[Sidebar]
[icon 32×32] HR ABSENSI         ← icon left of wordmark
[nav items below]
```

`icon-04E` (PNG-rasterized from SVG at 32×32) shown as `CTkImage` in a
`CTkLabel` next to the existing wordmark. Loaded once at startup via Pillow.

### 4.3 Sidebar — bottom (version + brand credit)

Add at sidebar bottom (`side="bottom"` packed):

```
─────────────────────              ← thin separator
v0.0.1                              ← small text, COLOR_TEXT_DIM, font 11
Josaphat Tech Solution              ← smaller, COLOR_TEXT_DIM, font 9 italic
// from concept to code             ← mono font, COLOR_TEXT_DIM, font 9
─────────────────────
```

Pack order with `side="bottom"`: thin sep + 3 labels pinned to sidebar bottom.

### 4.4 Window setup

`HRApp.__init__`:
```python
self.title("HR Absensi App")
self.geometry("1180x720")       # default before maximize
self.minsize(800, 540)          # smaller minsize → triggers scrollbar
self.iconbitmap(str(BRAND_ICON_ICO))   # window title bar + taskbar icon
# Maximize after window initialized
self.after(0, lambda: self.state("zoomed"))
```

`zoomed` keeps title bar + taskbar; user can un-maximize by clicking restore.

### 4.5 Responsive content area (scrollbar)

Wrap `self.content` (currently a `CTkFrame`) in `CTkScrollableFrame`. Each
screen instance grids into the scrollable inner frame.

Tradeoffs:
- **Always-visible scrollbar** on right side of content area — slight visual
  cost, but never confusing ("where did my content go?")
- **CTkScrollableFrame** has minor perf overhead vs CTkFrame, negligible for
  our content sizes
- Each screen's own internal layout (e.g., Dashboard's panels) doesn't change;
  the OUTER content scrolls if screen height exceeds window viewport

If a screen has its own internal scrollable section (Dashboard's Ranking
Treeview, Coaching's Treeview), there will be **two scrollbars** when content
overflows — outer (whole content) and inner (the Treeview). Acceptable; ttk
Treeview only shows scrollbar when needed.

---

## 5. Splash / Loading Screen

### 5.1 SplashScreen window design

New module: `src/ui/splash.py`

**Window properties:**
- Type: `ctk.CTkToplevel` (or plain `tk.Toplevel` for true splash feel)
- Size: 520×360
- Centered on screen
- No title bar / no decoration (`overrideredirect(True)`)
- Black background (`#0A0A0A` — brand color, contrast with GIF)
- Stays on top until dismissed

**Content layout (centered):**
```
┌─────────────────────────────────────┐
│                                     │
│                                     │
│         [animated GIF, 256×256]     │
│         (typing animation)          │
│                                     │
│      // from concept to code        │  ← mono font, magenta (#EC4899)
│                                     │
│      HR Absensi · v0.0.1            │  ← white, smaller
│                                     │
│                                     │
└─────────────────────────────────────┘
```

### 5.2 GIF animation logic

```python
# Open GIF, preload all frames as CTkImage
from PIL import Image
img = Image.open(BRAND_ANIMATION_GIF)
frames = []
try:
    while True:
        frames.append(ctk.CTkImage(
            light_image=img.copy(),
            dark_image=img.copy(),
            size=(256, 256),
        ))
        img.seek(img.tell() + 1)
except EOFError:
    pass

# Cycle frames in CTkLabel
def _animate(idx=0):
    self._gif_label.configure(image=frames[idx % len(frames)])
    self._after_id = self.after(40, _animate, idx + 1)  # ~24fps
_animate()
```

### 5.3 Lifecycle

```python
# src/main.py
def main():
    init_db(DB_PATH)
    splash = SplashScreen()                 # opens immediately
    splash.update()                          # force render

    # Heavy init in background (or just await)
    app = HRApp()                            # construct main window (hidden)
    app.withdraw()                           # hide until splash done

    # Wait minimum 2s + actual init complete
    def _reveal():
        splash.destroy()
        app.deiconify()
        app.state("zoomed")

    splash.after(2000, _reveal)              # min 2s, more if heavy
    app.mainloop()
```

Splash destroys itself; main window deiconifies + zooms. Total perceptual
delay: 2s minimum. If `HRApp()` construction takes >2s (rare), reveal happens
when init is done.

### 5.4 Splash close behavior

- After 2s + main ready → splash destroys, main reveals
- User can't close splash early (no title bar, no skip button) — keep simple
- If splash throws error (e.g., GIF load fail): catch, log, skip splash, go
  directly to main window. Don't block app start.

---

## 6. Architecture Updates

### 6.1 File structure (final)

```
assets/
├── brand/                  (from brand branch + ICO BARU)
└── templates/              (moved from /templates/)
docs/
├── superpowers/
│   ├── specs/...
│   └── plans/...
src/
├── config.py               (APP_VERSION→0.0.1, APP_TAGLINE, paths)
├── main.py                 (splash flow added)
├── ui/
│   ├── app.py              (icon, maximize, scrollable content, sidebar updates)
│   ├── splash.py           ← BARU
│   ├── theme.py
│   └── screens/...
tests/
tools/
├── build_template.py       (path update for assets/templates/)
└── svg_to_ico.py           ← BARU
HR-Absensi.spec
```

### 6.2 Imports added/changed

`src/config.py` (existing, after brand merge):
```python
BRAND_DIR = RESOURCE_ROOT / "assets" / "brand"
BRAND_ICON_SVG = BRAND_DIR / "icon-04E.svg"
BRAND_ICON_ICO = BRAND_DIR / "icon-04E.ico"        # ADD this
BRAND_LOCKUP_DARK_SVG = BRAND_DIR / "lockup-04E-dark.svg"
BRAND_LOCKUP_LIGHT_SVG = BRAND_DIR / "lockup-04E-light.svg"
BRAND_ANIMATION_SVG = BRAND_DIR / "animation-02-typing-04E.svg"
BRAND_ANIMATION_GIF = BRAND_DIR / "animation-02-typing-04E.gif"

APP_VERSION = "0.0.1"
APP_TAGLINE = "From Concept to Code."
APP_BRAND_NAME = "Josaphat Tech Solution"

# UPDATED path after consolidation
TEMPLATE_LAPORAN_BULANAN = RESOURCE_ROOT / "assets" / "templates" / "laporan_bulanan_template.xlsx"
```

---

## 7. Implementation Order / Dependencies

Recommended execution order (subagent tasks):

1. **Merge brand branch** + resolve conflicts in config.py/spec
2. **Folder consolidation** — move `templates/` → `assets/templates/` + update paths
3. **SVG → ICO conversion** — script + run + commit `.ico` file
4. **HR-Absensi.spec** — add `icon=` + finalize datas tuple
5. **Version bump** — `APP_VERSION = "0.0.1"` + new constants
6. **SplashScreen module** — `src/ui/splash.py` with GIF animation
7. **main.py update** — splash → main app handoff
8. **HRApp.app.py updates** — iconbitmap, state("zoomed"), CTkScrollableFrame
   wrap, sidebar header logo, sidebar bottom version
9. **Smoke test** — manual

Each step is independent enough for separate commit.

---

## 8. Risks & Edge Cases

| Risk | Mitigation |
|---|---|
| `cairosvg` install fails on Windows (libcairo C lib missing) | Fallback to Inkscape CLI; document manual web converter. The .ico is committed once. |
| GIF preload OOM (96 frames × 256×256 RGBA) | ~24 MB estimated. Acceptable for desktop app. Frames stored as PIL Image, converted to CTkImage on demand if needed. |
| Splash window steals focus from background apps | Tkinter Toplevel typically only takes app focus, not OS-wide. Mitigated by 2s timeout. |
| `state("zoomed")` only works on Windows | Fine — app is Windows-only per spec II.1. On other platforms tk falls back gracefully. |
| Multiple monitors: maximized on wrong screen | tk's "zoomed" maximizes on the screen the window was last positioned. Should default to primary; user can drag if needed. |
| `iconbitmap()` needs absolute path | Use `str(BRAND_ICON_ICO)` which resolves via config.py's `_resource_root()`. |
| Existing `templates/` folder after move — stale? | Delete `templates/` dir after move + remove from .gitignore if mentioned. Verify nothing references old path. |
| Brand branch conflicts with my changes | Conflicts are additive — resolve by combining lines (both BRAND_* and my TEMPLATE_LAPORAN_BULANAN). |
| `withdraw()` + `deiconify()` flash | Window briefly visible during construction. Mitigated by `withdraw()` immediately after `HRApp()` constructor's `super().__init__()` call. Slight risk of brief flash. |
| Scrollable content area: existing screens may layout differently | Each screen does its own grid layout. The wrap shouldn't break existing layout, just adds scrollability. Verify in smoke. |

---

## 9. Testing

### 9.1 Unit tests
- No new unit tests (UI + asset integration, hard to unit-test)
- Existing 97 tests must remain green

### 9.2 Manual smoke test

After build + deploy:

1. Launch .exe — title bar shows JTS icon (not penguin); taskbar shows JTS icon
2. **Splash appears** — animated typing GIF visible, tagline + version below
3. Splash lasts ~2s, then disappears
4. **Main window opens MAXIMIZED** (zoomed state, title bar + taskbar still visible)
5. Sidebar top shows **small JTS icon + "HR ABSENSI"** wordmark
6. Sidebar bottom shows **"v0.0.1" + "Josaphat Tech Solution" + "// from concept to code"**
7. **Resize window smaller** (e.g., 800×500): vertical scrollbar appears on right of content area
8. Scroll → content can be reached fully
9. Restore window to max → scrollbar disappears
10. Navigate all screens (Dashboard, Import, Issues, Summary, Export, Riwayat Bulan, Coaching, Settings) — no layout breakage
11. Click Generate Laporan in Riwayat Bulan — file generates from `assets/templates/` (moved location), output correct
12. Verify no regression: 97 tests `pytest -q`

---

## 10. Definition of Done

- [ ] Brand branch merged, conflicts resolved
- [ ] `templates/` moved to `assets/templates/`, all references updated
- [ ] `assets/brand/icon-04E.ico` committed (multi-res from SVG)
- [ ] `HR-Absensi.spec` has icon= in EXE block + all datas wired
- [ ] `APP_VERSION = "0.0.1"` + APP_TAGLINE constants in config
- [ ] `src/ui/splash.py` exists with animated GIF + tagline + version
- [ ] `src/main.py` integrates splash → main flow
- [ ] HRApp shows JTS icon (window + taskbar)
- [ ] HRApp opens **maximized** (zoomed)
- [ ] Sidebar top: logo + wordmark
- [ ] Sidebar bottom: version + brand credit
- [ ] Content area scrollable when window shrinks below content height
- [ ] 97 tests still pass (no regression in DB / core / parsers)
- [ ] Manual smoke pass (all 12 steps in 9.2)
- [ ] New .exe deployed; old `.exe.bak` available for rollback

---

## 11. Out of Scope (future)

- HTML report header lockup (handoff task #3)
- Theme overhaul to brand black/magenta (handoff task #4, deferred per Hybrid A)
- About dialog with full brand lockup display
- Customizable splash duration in Settings
- Skip splash via Escape key
- Logo in print PDF footer
- App credits screen
- Dark/light mode toggle (always dark for now)

---

*End of spec.*
