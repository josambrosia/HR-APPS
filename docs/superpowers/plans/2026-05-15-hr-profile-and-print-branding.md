# HR Profile & Print Branding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an HR User profile name field to the Settings screen, and apply four revisions to the dashboard print output — a JTS logo lockup in the footer, a "Tech Solution" line, an "HR Officer in Charge" sign-off block, and removal of the browser's auto path footer.

**Architecture:** The profile is one new `hr_officer_name` setting in the existing K/V `settings` table, surfaced via a new "Profil" tab in `SettingsScreen`. The print revisions are confined to `html_renderer.py` (reads the setting + inlines the brand SVG, passes both to the template context) and `dashboard.html.j2` (footer brand block, sign-off block, `@page` margin). No schema changes; the page header is untouched.

**Tech Stack:** Python 3.13, SQLite (stdlib `sqlite3`), customtkinter (UI), Jinja2 (HTML template), pytest (tests).

---

## Codebase Notes (read before starting)

- **Spec:** `docs/superpowers/specs/2026-05-15-hr-profile-and-print-branding-design.md` — full design rationale.
- **Run all tests** (from the worktree root): `../../../.venv/Scripts/python.exe -m pytest -q`
- **Run one file:** `../../../.venv/Scripts/python.exe -m pytest tests/test_file.py -v`
- **Baseline:** 219 tests passing before this plan (Spec 1 — Issue Resolution — is already implemented on this branch).
- **Settings K/V:** `src/db/settings.py` has `get_setting(conn, key, default=None)` and `set_setting(conn, key, value)`. Values are strings. The `settings` table needs no migration for a new key.
- **`SettingsScreen`** (`src/ui/screens/settings.py`) is a `CTkTabview` with "General" + "Pegawai" tabs, each built by a `_build_*` method. UI tests `monkeypatch` the module's `DB_PATH` to a temp DB.
- **UI screen test pattern** (`tests/test_settings_screen.py`): `monkeypatch.setattr(settings_mod, "DB_PATH", temp_db_path)`, construct with the session-scoped `tk_root` fixture, `tk_root.update_idletasks()`, assert, `.destroy()`. For tests that call a save handler (which pops a `messagebox`), also `monkeypatch.setattr(settings_mod.messagebox, "showinfo", lambda *a, **k: None)`.
- **`render_dashboard_html`** (`src/reports/html_renderer.py`) builds a context dict and calls `tmpl.render(...)`. It already receives a `conn`. The template is `src/reports/templates/dashboard.html.j2`.
- **`test_html_renderer.py`** has `_add_emp(conn, no, nama, dept="X")` and `_add_att(conn, emp_id, tanggal, hari, masuk, keluar, terlambat, has_issue=0)` local helpers, uses the `temp_db_path` + `tmp_path` fixtures.
- **Brand asset:** `assets/brand/lockup-04E-light.svg` — a `480×130` viewBox SVG: the dark "josaphat" wordmark + a magenta cursor rect + a "// from concept to code" tagline. `src/config.py` already defines `BRAND_LOCKUP_LIGHT_SVG` pointing at it.

---

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `src/ui/screens/settings.py` | Modify | New "Profil" tab: `hr_officer_name` field + `_build_profil` + `_save_profil` |
| `src/reports/html_renderer.py` | Modify | Read `hr_officer_name`; inline the brand lockup SVG; pass both to the template context |
| `src/reports/templates/dashboard.html.j2` | Modify | Footer brand block (SVG + "Tech Solution"); `.b-signoff` block; `@page` margin → 0 + `.doc` padding |
| `tests/test_settings_screen.py` | Modify | HR profile save/load tests |
| `tests/test_html_renderer.py` | Modify | Sign-off, inlined-SVG, and `@page`-margin tests; update the footer assertion |

---

## Task 1: HR Profile tab in Settings

**Files:**
- Modify: `src/ui/screens/settings.py`
- Test: `tests/test_settings_screen.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_settings_screen.py`:

```python


def test_settings_screen_saves_hr_officer_name(temp_db_path, monkeypatch, tk_root):
    import src.ui.screens.settings as settings_mod
    monkeypatch.setattr(settings_mod, "DB_PATH", temp_db_path)
    monkeypatch.setattr(settings_mod.messagebox, "showinfo", lambda *a, **k: None)
    init_db(temp_db_path)
    screen = settings_mod.SettingsScreen(tk_root)
    tk_root.update_idletasks()
    screen.hr_name_var.set("Supriyadi, S.E.")
    screen._save_profil()
    with get_connection(temp_db_path) as conn:
        assert get_setting(conn, "hr_officer_name") == "Supriyadi, S.E."
    screen.destroy()


def test_settings_screen_loads_saved_hr_officer_name(temp_db_path, monkeypatch, tk_root):
    import src.ui.screens.settings as settings_mod
    monkeypatch.setattr(settings_mod, "DB_PATH", temp_db_path)
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        from src.db.settings import set_setting
        set_setting(conn, "hr_officer_name", "Budi Hartono")
    screen = settings_mod.SettingsScreen(tk_root)
    tk_root.update_idletasks()
    assert screen.hr_name_var.get() == "Budi Hartono"
    screen.destroy()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `../../../.venv/Scripts/python.exe -m pytest tests/test_settings_screen.py -v`
Expected: FAIL — the two new tests (`AttributeError: 'SettingsScreen' object has no attribute 'hr_name_var'` / `'_save_profil'`).

- [ ] **Step 3: Register the "Profil" tab in `_build`**

In `src/ui/screens/settings.py`, `_build` currently has:

```python
        self.tabs.add("General")
        self.tabs.add("Pegawai")

        self._build_general(self.tabs.tab("General"))
        self._build_pegawai(self.tabs.tab("Pegawai"))
```

Replace it with:

```python
        self.tabs.add("General")
        self.tabs.add("Pegawai")
        self.tabs.add("Profil")

        self._build_general(self.tabs.tab("General"))
        self._build_pegawai(self.tabs.tab("Pegawai"))
        self._build_profil(self.tabs.tab("Profil"))
```

- [ ] **Step 4: Add the `_build_profil` method**

Add this method to `SettingsScreen`, immediately after `_build_general` (i.e. before `_build_pegawai`):

```python
    def _build_profil(self, parent):
        with get_connection(DB_PATH) as conn:
            hr_name = get_setting(conn, "hr_officer_name", default="")

        ctk.CTkLabel(
            parent,
            text="Nama ini muncul di hasil cetak Dashboard sebagai "
                 "HR Officer in Charge.",
            font=FONT_SMALL, text_color=COLOR_TEXT_DIM,
        ).pack(anchor="w", pady=(SPACE_SM, SPACE_XS))

        row = ctk.CTkFrame(
            parent, fg_color=COLOR_SURFACE,
            border_width=1, border_color=COLOR_BORDER,
            corner_radius=RADIUS_MD,
        )
        row.pack(fill="x", pady=SPACE_SM)
        ctk.CTkLabel(
            row, text="Nama:",
            font=FONT_BODY, text_color=COLOR_TEXT,
        ).pack(side="left", padx=SPACE_MD, pady=SPACE_SM + 2)
        self.hr_name_var = ctk.StringVar(value=hr_name)
        ctk.CTkEntry(
            row, textvariable=self.hr_name_var, width=260,
            fg_color=COLOR_SURFACE_HIGH,
            border_width=1, border_color=COLOR_BORDER,
            text_color=COLOR_TEXT,
            font=FONT_BODY,
            placeholder_text_color=COLOR_TEXT_MUTED,
        ).pack(side="left")

        ctk.CTkButton(
            parent, text="Simpan Profil",
            command=self._save_profil,
            fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER,
            text_color=COLOR_BG,
            font=FONT_BODY_BOLD,
            corner_radius=RADIUS_MD,
        ).pack(anchor="w", pady=SPACE_MD)
```

(All theme/font constants used here — `COLOR_SURFACE`, `COLOR_BORDER`, `COLOR_SURFACE_HIGH`, `COLOR_TEXT`, `COLOR_TEXT_DIM`, `COLOR_TEXT_MUTED`, `COLOR_ACCENT`, `COLOR_ACCENT_HOVER`, `COLOR_BG`, `FONT_SMALL`, `FONT_BODY`, `FONT_BODY_BOLD`, `SPACE_XS`, `SPACE_SM`, `SPACE_MD`, `RADIUS_MD` — are already imported in this file. Do NOT add imports.)

- [ ] **Step 5: Add the `_save_profil` method**

Add this method immediately after the existing `_save` method (at the end of the class):

```python
    def _save_profil(self):
        with get_connection(DB_PATH) as conn:
            set_setting(conn, "hr_officer_name", self.hr_name_var.get().strip())
        messagebox.showinfo("Tersimpan", "Profil disimpan.")
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `../../../.venv/Scripts/python.exe -m pytest tests/test_settings_screen.py -v`
Expected: PASS — all 5 tests (3 pre-existing + 2 new).

- [ ] **Step 7: Commit**

```bash
git add src/ui/screens/settings.py tests/test_settings_screen.py
git commit -m "feat(ui): HR profile tab in Settings"
```

---

## Task 2: "HR Officer in Charge" sign-off block on the dashboard print

**Files:**
- Modify: `src/reports/html_renderer.py`
- Modify: `src/reports/templates/dashboard.html.j2`
- Test: `tests/test_html_renderer.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_html_renderer.py`:

```python


def test_render_html_includes_hr_officer_signoff(temp_db_path, tmp_path):
    """The print includes an HR Officer in Charge sign-off with the saved name."""
    from src.db.settings import set_setting
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        set_setting(conn, "hr_officer_name", "Supriyadi, S.E.")
        emp = _add_emp(conn, "1", "ANDI")
        _add_att(conn, emp, "2026-04-01", "Senin", "08.00", "16.00", 0)
        out = render_dashboard_html(
            conn, period_start="2026-04-01", period_end="2026-04-30",
            period_label="April 2026", out_dir=tmp_path,
        )
    content = out.read_text(encoding="utf-8")
    assert "HR Officer in Charge" in content
    assert "Supriyadi, S.E." in content


def test_render_html_signoff_renders_when_name_empty(temp_db_path, tmp_path):
    """The sign-off block + label render even when no HR name is set."""
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        emp = _add_emp(conn, "1", "ANDI")
        _add_att(conn, emp, "2026-04-01", "Senin", "08.00", "16.00", 0)
        out = render_dashboard_html(
            conn, period_start="2026-04-01", period_end="2026-04-30",
            period_label="April 2026", out_dir=tmp_path,
        )
    content = out.read_text(encoding="utf-8")
    assert "HR Officer in Charge" in content
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `../../../.venv/Scripts/python.exe -m pytest tests/test_html_renderer.py -v`
Expected: FAIL — the two new tests (`"HR Officer in Charge"` not in the rendered HTML yet).

- [ ] **Step 3: Read `hr_officer_name` in `html_renderer.py`**

In `src/reports/html_renderer.py`, add to the imports (after `from src.core.insights import (...)`):

```python
from src.db.settings import get_setting
```

In `render_dashboard_html`, immediately before `env = _build_env()`, add:

```python
    hr_officer_name = get_setting(conn, "hr_officer_name", default="")
```

Then add `hr_officer_name` to the `tmpl.render(...)` call — add this line inside the `tmpl.render(` argument list (e.g. right after `sections=sections,`):

```python
        hr_officer_name=hr_officer_name,
```

- [ ] **Step 4: Add the `.b-signoff` CSS to `dashboard.html.j2`**

In `src/reports/templates/dashboard.html.j2`, inside the `<style>` block, immediately after the `/* Page 2 header */` rules (the `.b-rank-head ...` lines) and before `/* Print */`, add:

```css
  /* Sign-off */
  .b-signoff{margin-top:28px;display:flex;justify-content:flex-end;break-inside:avoid}
  .b-signoff .so{text-align:center;font-size:10px;min-width:200px}
  .b-signoff .so .role{color:#525252}
  .b-signoff .so .gap{height:46px}
  .b-signoff .so .name{font-weight:700;color:#171717;border-top:1px solid #171717;padding-top:4px}
```

- [ ] **Step 5: Add the sign-off block to the template**

In `dashboard.html.j2`, the page-2 ranking section ends with this (the `{% else %}...{% endif %}` for the `ranking` table) followed immediately by the page-2 footer:

```html
  {% else %}<div class="empty-state">Tidak ada data karyawan di periode ini.</div>{% endif %}

  <div class="b-footer">
    <span>// page 2/2 &middot; confidential</span>
```

Insert the sign-off block between the `{% endif %}` line and the `<div class="b-footer">` line, so it becomes:

```html
  {% else %}<div class="empty-state">Tidak ada data karyawan di periode ini.</div>{% endif %}

  {# === SIGN-OFF === #}
  <div class="b-signoff">
    <div class="so">
      <div class="role">HR Officer in Charge</div>
      <div class="gap"></div>
      <div class="name">{{ hr_officer_name }}</div>
    </div>
  </div>

  <div class="b-footer">
    <span>// page 2/2 &middot; confidential</span>
```

(When `hr_officer_name` is empty, `.name` renders as an empty bordered line — usable as a manual signature line. That is the intended behavior.)

- [ ] **Step 6: Run tests to verify they pass**

Run: `../../../.venv/Scripts/python.exe -m pytest tests/test_html_renderer.py -v`
Expected: PASS — all tests in the file (2 new + the pre-existing ones).

- [ ] **Step 7: Commit**

```bash
git add src/reports/html_renderer.py src/reports/templates/dashboard.html.j2 tests/test_html_renderer.py
git commit -m "feat(report): HR Officer in Charge sign-off on dashboard print"
```

---

## Task 3: JTS logo lockup in the dashboard print footer

**Files:**
- Modify: `src/reports/html_renderer.py`
- Modify: `src/reports/templates/dashboard.html.j2`
- Test: `tests/test_html_renderer.py`

- [ ] **Step 1: Update the existing footer assertion + write the new test**

In `tests/test_html_renderer.py`, the test `test_render_html_contains_key_sections` currently has:

```python
    # Footer
    assert "[jts] josaphat tech solution" in content
```

Replace those two lines with:

```python
    # Footer — brand lockup (inlined SVG) + "Tech Solution" line
    assert "<svg" in content
    assert "Tech Solution" in content
```

Then append this new test to the end of the file:

```python


def test_render_html_inlines_brand_lockup_svg(temp_db_path, tmp_path):
    """The JTS lockup is inlined as <svg>, not referenced as an external file,
    and the old plain-text footer is gone."""
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        emp = _add_emp(conn, "1", "ANDI")
        _add_att(conn, emp, "2026-04-01", "Senin", "08.00", "16.00", 0)
        out = render_dashboard_html(
            conn, period_start="2026-04-01", period_end="2026-04-30",
            period_label="April 2026", out_dir=tmp_path,
        )
    content = out.read_text(encoding="utf-8")
    assert "<svg" in content                              # lockup inlined as SVG
    assert "josaphat" in content                          # the lockup wordmark text
    assert "[jts] josaphat tech solution" not in content  # old text footer removed
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `../../../.venv/Scripts/python.exe -m pytest tests/test_html_renderer.py -v`
Expected: FAIL — `test_render_html_contains_key_sections` (no `<svg>` / no "Tech Solution" yet) and `test_render_html_inlines_brand_lockup_svg`.

- [ ] **Step 3: Add the SVG-loading helper to `html_renderer.py`**

In `src/reports/html_renderer.py`, extend the existing config import. It currently reads:

```python
from src.config import DEFAULT_COACHING_THRESHOLD_MINUTES
```

Change it to:

```python
from src.config import DEFAULT_COACHING_THRESHOLD_MINUTES, BRAND_LOCKUP_LIGHT_SVG
```

Add this helper function immediately after `_build_env`:

```python
def _load_brand_lockup() -> str:
    """Return the JTS light-background lockup SVG markup, ready to inline into
    the print HTML. Strips the XML prolog (not valid mid-HTML-document).
    Falls back to a plain text wordmark if the asset is missing, so rendering
    never fails."""
    try:
        svg = BRAND_LOCKUP_LIGHT_SVG.read_text(encoding="utf-8")
    except (FileNotFoundError, OSError):
        return "josaphat"
    if svg.lstrip().startswith("<?xml"):
        svg = svg.split("?>", 1)[1]
    return svg.strip()
```

- [ ] **Step 4: Pass the inlined SVG to the template context**

In `render_dashboard_html`, immediately after the `hr_officer_name = ...` line added in Task 2 (and before `env = _build_env()`), add:

```python
    brand_lockup_svg = _load_brand_lockup()
```

Add `brand_lockup_svg` to the `tmpl.render(...)` call — add this line right after the `hr_officer_name=hr_officer_name,` line:

```python
        brand_lockup_svg=brand_lockup_svg,
```

- [ ] **Step 5: Update the footer CSS in `dashboard.html.j2`**

In `dashboard.html.j2`, the `<style>` block currently has:

```css
  /* Footer */
  .b-footer{margin-top:22px;padding-top:12px;border-top:1px solid #e5e5e5;display:flex;justify-content:space-between;font-size:9.5px;color:#737373;font-family:Consolas,monospace}
  .b-footer .jts{color:#ec4899;letter-spacing:1.5px;text-transform:uppercase;font-weight:700}
```

Replace those two lines with:

```css
  /* Footer */
  .b-footer{margin-top:22px;padding-top:12px;border-top:1px solid #e5e5e5;display:flex;justify-content:space-between;align-items:flex-end;font-size:9.5px;color:#737373;font-family:Consolas,monospace}
  .b-footer .brand{text-align:right;line-height:1.35}
  .b-footer .brand svg{height:26px;width:auto;display:block}
  .b-footer .brand .sub{font-size:8px;color:#525252;letter-spacing:.5px;font-family:'Segoe UI',sans-serif}
```

- [ ] **Step 6: Replace the footer brand markup (both occurrences)**

In `dashboard.html.j2` there are TWO `.b-footer` blocks (page 1 and page 2). Each currently looks like:

```html
  <div class="b-footer">
    <span>// page 1/2 &middot; confidential</span>
    <span class="jts">[jts] josaphat tech solution</span>
  </div>
```

For the **page 1** footer, replace it with:

```html
  <div class="b-footer">
    <span>// page 1/2 &middot; confidential</span>
    <div class="brand">{{ brand_lockup_svg | safe }}<span class="sub">Tech Solution</span></div>
  </div>
```

For the **page 2** footer (the one after the sign-off block, with `// page 2/2`), replace it with:

```html
  <div class="b-footer">
    <span>// page 2/2 &middot; confidential</span>
    <div class="brand">{{ brand_lockup_svg | safe }}<span class="sub">Tech Solution</span></div>
  </div>
```

(The `| safe` filter is required — without it Jinja2's autoescape would escape the SVG markup into visible text.)

- [ ] **Step 7: Run tests to verify they pass**

Run: `../../../.venv/Scripts/python.exe -m pytest tests/test_html_renderer.py -v`
Expected: PASS — all tests in the file (the updated `test_render_html_contains_key_sections`, the new `test_render_html_inlines_brand_lockup_svg`, and all pre-existing tests).

- [ ] **Step 8: Commit**

```bash
git add src/reports/html_renderer.py src/reports/templates/dashboard.html.j2 tests/test_html_renderer.py
git commit -m "feat(report): JTS logo lockup in dashboard print footer"
```

---

## Task 4: Remove the browser's path footer via `@page` margin

**Files:**
- Modify: `src/reports/templates/dashboard.html.j2`
- Test: `tests/test_html_renderer.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_html_renderer.py`:

```python


def test_render_html_page_margin_zero(temp_db_path, tmp_path):
    """@page margin is 0 (suppresses the browser's auto path/header/footer);
    the page inset moves into .doc padding."""
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        emp = _add_emp(conn, "1", "ANDI")
        _add_att(conn, emp, "2026-04-01", "Senin", "08.00", "16.00", 0)
        out = render_dashboard_html(
            conn, period_start="2026-04-01", period_end="2026-04-30",
            period_label="April 2026", out_dir=tmp_path,
        )
    content = out.read_text(encoding="utf-8")
    assert "@page{size:A4;margin:0}" in content
    assert ".doc{padding:14mm}" in content
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `../../../.venv/Scripts/python.exe -m pytest tests/test_html_renderer.py::test_render_html_page_margin_zero -v`
Expected: FAIL — the template still has `@page{size:A4;margin:14mm}` and `.doc{padding:8px 12px}`.

- [ ] **Step 3: Change `@page` margin and `.doc` padding**

In `src/reports/templates/dashboard.html.j2`, the `<style>` block currently has these two lines:

```css
  @page{size:A4;margin:14mm}
  body{font-family:'Segoe UI','Inter',sans-serif;background:#fff;color:#171717;font-size:11px;line-height:1.45}
  .doc{padding:8px 12px}
```

Change the `@page` line to `margin:0` and the `.doc` line to `padding:14mm` (leave the `body` line untouched):

```css
  @page{size:A4;margin:0}
  body{font-family:'Segoe UI','Inter',sans-serif;background:#fff;color:#171717;font-size:11px;line-height:1.45}
  .doc{padding:14mm}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `../../../.venv/Scripts/python.exe -m pytest tests/test_html_renderer.py -v`
Expected: PASS — all tests in the file.

- [ ] **Step 5: Run the full suite**

Run: `../../../.venv/Scripts/python.exe -m pytest -q`
Expected: PASS — 219 baseline + 6 new (3 in test_settings_screen.py... no: +2 in settings, +4 in html_renderer) ≈ 225, no regressions.

- [ ] **Step 6: Commit**

```bash
git add src/reports/templates/dashboard.html.j2 tests/test_html_renderer.py
git commit -m "fix(report): drop @page margin so browser path footer is suppressed"
```

---

## Manual Smoke Test (after all tasks)

Cannot be automated — needs a human at the desktop app:

1. **Profil:** Settings → "Profil" tab → enter a name → "Simpan Profil" → reopen Settings, confirm the name persisted.
2. **Sign-off:** generate/print the Dashboard → page 2 ends with "HR Officer in Charge" + the name above a signature line.
3. **Footer logo:** the footer (both pages) shows the JTS lockup graphic + "Tech Solution", no longer the plain "[jts] josaphat tech solution" text.
4. **Path removal:** open the generated HTML in Chrome/Edge → `Ctrl+P` → the browser's auto footer (the `file://...` path) is gone. Content is not clipped at the page edges. *If the path still shows on the target browser, the fallback is a one-time "uncheck Headers and footers" in the print dialog — see spec §6.*

---

## Implementation Notes

- **Suggested task order:** 1 (Profil) → 2 (sign-off) → 3 (footer logo) → 4 (`@page`). Tasks 2–4 all edit `dashboard.html.j2` but in different sections (sign-off block + CSS / footer block + CSS / `@page` + `.doc`), so sequential execution has no conflicts.
- **`.exe` build note (for the build step, not this plan):** `html_renderer._load_brand_lockup()` reads `assets/brand/lockup-04E-light.svg` at runtime. The PyInstaller build (`HR-Absensi.spec`) must bundle `assets/brand/` as a data file for the logo to appear in the packaged `.exe`. If it is not bundled, `_load_brand_lockup` falls back to the plain text "josaphat" — the renderer never crashes, but the logo will be missing. Verify/add the data-file inclusion when building.
- **Worktree:** branch `claude/trusting-lederberg-6e61bb`. No rebase needed.
- **Test before commit** — run the relevant test file after each task; run the full suite at the end of Task 4.
- **No auto-push** — wait for user instruction.

---

## Keputusan Desain (from the spec — for quick review)

1. **Profil = nama saja** — one field; the role label "HR Officer in Charge" is fixed.
2. **Logo in the footer (Variant B)** — the page header is not touched.
3. **"Tech Solution"** is a small muted text line below the inlined lockup SVG.
4. **Sign-off label: "HR Officer in Charge"** (English), bottom of page 2, always rendered (blank name line = manual signature line).
5. **Path in footer = the browser's own print footer** — fixed via `@page margin:0` + `.doc` padding, not by editing template content.
6. **SVG inlined** (not `<img src>`) so the print HTML file stays self-contained.

---

## Self-Review

**Spec coverage** (against `2026-05-15-hr-profile-and-print-branding-design.md`):
- §3–4 HR profile (`hr_officer_name` setting + "Profil" tab + `_build_profil` + `_save_profil`) → Task 1. ✓
- §5 Revisi 1 (logo image, inlined SVG) → Task 3. ✓
- §5 Revisi 2 (footer placement / "Tech Solution") → Task 3. ✓
- §6 Revisi 3 (remove path footer via `@page` margin) → Task 4. ✓
- §7 Revisi 4 (sign-off block + `html_renderer` reads `hr_officer_name`) → Task 2. ✓
- §9 error handling: `hr_officer_name` empty → sign-off renders blank line (Task 2 test `test_render_html_signoff_renders_when_name_empty`); SVG missing → `_load_brand_lockup` fallback (Task 3); `@page` browser-dependence noted in the Manual Smoke Test + spec §6. ✓
- §2 "page header untouched" — no task modifies `.b-head`. ✓

**Placeholder scan:** No TBD/TODO; every code step has complete code.

**Type consistency:** `hr_officer_name` (settings key + template var + `_save_profil`/`_build_profil` + `html_renderer`) is spelled identically everywhere. `hr_name_var` is the `StringVar` attribute used in both Task 1 tests and `_build_profil`/`_save_profil`. `brand_lockup_svg` (the `_load_brand_lockup` return → context var → template `| safe`) is consistent. `_load_brand_lockup` is defined in Task 3 and used in Task 3.

**Task ordering:** Task 2 adds `hr_officer_name` to the render context; Task 3 adds `brand_lockup_svg` right after it — Task 3's "right after the `hr_officer_name = ...` line" instruction depends on Task 2 having run first, which the suggested order guarantees.
