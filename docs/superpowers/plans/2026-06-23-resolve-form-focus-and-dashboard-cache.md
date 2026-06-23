# Resolve-form Focus Fix + Dashboard Cache Invalidation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the Resolve-form Detail field (users can't type — focus is stolen) and make the Dashboard's `_query_cache` provably fresh after issue changes.

**Architecture:** Centralize the four copy-pasted "search shortcut" blocks into one `SearchBar.install_shortcuts(host)` whose click-outside-blur is **deferred + focus-aware** so it never steals focus from another input. Add a session-level `data_version` counter bumped on issue-lifecycle writes; the Dashboard clears its cache when the version changed.

**Tech Stack:** Python 3, CustomTkinter (Tkinter), SQLite, pytest. Branch `v19` (forked from `origin/v18`).

**Spec:** `docs/superpowers/specs/2026-06-23-resolve-form-focus-and-dashboard-cache-design.md`

**Conventions (from existing tests):**
- UI tests use the session-scoped `tk_root` fixture and `screen.destroy()` at the end.
- Screen tests redirect the DB with `monkeypatch.setattr(mod, "DB_PATH", temp_db_path)` + `init_db(temp_db_path)`.
- Call `tk_root.update_idletasks()` after construction / state changes.
- Run a single test: `python -m pytest tests/test_x.py::test_name -v` from the repo root (venv active).

---

## File Structure

| File | Responsibility | Change |
|---|---|---|
| `src/ui/components/search_bar.py` | The search input component — now also owns its Ctrl+F + click-outside-blur shortcuts | Add `install_shortcuts` + 4 helpers |
| `src/ui/screens/issues.py` | Issues screen | Use helper; remove dup; bump on resolve/unresolve |
| `src/ui/screens/severe_lateness.py` | Severe Lateness screen (Issues clone) | Use helper; remove dup; bump on resolve/unresolve |
| `src/ui/screens/outlier.py` | Outlier screen | Use helper; remove dup |
| `src/ui/screens/heatmap.py` | Heatmap screen | Use helper; remove dup |
| `src/core/session_state.py` | Ephemeral cross-screen session state | Add `SessionDataVersion` + `data_version` + `notify_data_changed` |
| `src/ui/screens/dashboard.py` | Dashboard analytics | Invalidate `_query_cache` on version change |
| `src/ui/components/batch_resolve_dialog.py` | Batch resolve dialog | Bump after batch commit |
| `src/ui/screens/import_screen.py` | Import screen | Bump after import commit |
| `tests/conftest.py` | Shared fixtures | Add autouse `reset_data_version` |
| `tests/test_search_bar.py` … | Tests | New cases per task |

**Build order:** BUG #2 first (Tasks 1–5: helper, then wire each screen), then BUG #1 (Tasks 6–10: counter, dashboard, bump sites), then full verification (Task 11). Task 6 must precede Tasks 7–10 (they import `notify_data_changed`).

---

## Task 1: `SearchBar.install_shortcuts` — the focus-fix helper

**Files:**
- Modify: `src/ui/components/search_bar.py` (add methods to the `SearchBar` class, after `focus()` at line 109)
- Test: `tests/test_search_bar.py`

- [ ] **Step 1: Write the failing tests** — append to `tests/test_search_bar.py`:

```python
import customtkinter as ctk


def test_install_shortcuts_blurs_when_focus_stays_in_search(tk_root, monkeypatch):
    """Inert click outside search (focus still in search) -> blur to host."""
    host = ctk.CTkFrame(tk_root)
    bar = SearchBar(host, on_change=lambda _q: None)
    bar.install_shortcuts(host)
    tk_root.update_idletasks()
    monkeypatch.setattr(bar, "focus_get", lambda: bar)   # focus still in the search
    blurred = []
    monkeypatch.setattr(host, "focus_set", lambda: blurred.append(True))
    bar._release_if_orphaned()
    assert blurred == [True]
    host.destroy()


def test_install_shortcuts_leaves_focus_on_other_input(tk_root, monkeypatch):
    """Click landed on another input (focus moved out) -> do NOT steal it."""
    host = ctk.CTkFrame(tk_root)
    other = ctk.CTkEntry(host)
    bar = SearchBar(host, on_change=lambda _q: None)
    bar.install_shortcuts(host)
    tk_root.update_idletasks()
    monkeypatch.setattr(bar, "focus_get", lambda: other)   # focus on a different widget
    blurred = []
    monkeypatch.setattr(host, "focus_set", lambda: blurred.append(True))
    bar._release_if_orphaned()
    assert blurred == []
    host.destroy()


def test_install_shortcuts_installs_and_cleans_up(tk_root):
    host = ctk.CTkFrame(tk_root)
    bar = SearchBar(host, on_change=lambda _q: None)
    bar.install_shortcuts(host)
    tk_root.update_idletasks()
    assert bar._click_bind_id is not None
    assert host.bind("<Control-f>") != ""
    bar._on_host_destroy()
    assert bar._click_bind_id is None
    host.destroy()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_search_bar.py -v`
Expected: FAIL with `AttributeError: 'SearchBar' object has no attribute 'install_shortcuts'`.

- [ ] **Step 3: Implement the helper** — in `src/ui/components/search_bar.py`, add these methods to the `SearchBar` class (right after the existing `focus()` method, line 109-110):

```python
    def install_shortcuts(self, host):
        """Wire Ctrl+F (focus this search) and click-outside-to-blur for the
        given host screen, with auto-cleanup on host <Destroy>.

        Centralizes what used to be a per-screen copy-pasted block. The blur
        decision is DEFERRED until after Tk's native click->focus handling so
        it can never steal focus from an input the user just clicked (the
        Resolve-form typing bug)."""
        self._host = host
        self._top = host.winfo_toplevel()
        host.bind("<Control-f>", self._focus_shortcut)
        try:
            self._top.bind_all("<Control-f>", self._focus_shortcut)
        except Exception:
            pass
        self._click_bind_id = self._top.bind(
            "<Button-1>", self._on_click_outside, add="+")
        host.bind("<Destroy>", self._on_host_destroy)

    def _focus_shortcut(self, _e=None):
        if self.winfo_exists():
            self.focus()
        return "break"

    def _on_click_outside(self, event):
        # Click inside the search bar? Leave it entirely alone.
        w = event.widget
        while w is not None:
            if w is self:
                return
            w = getattr(w, "master", None)
        # Outside: defer the decision so Tk's native click->focus runs first.
        try:
            self.after_idle(self._release_if_orphaned)
        except Exception:
            pass

    def _release_if_orphaned(self):
        try:
            focused = self.focus_get()
        except Exception:
            return
        w = focused
        while w is not None:
            if w is self:
                # Focus is STILL inside the search -> inert click -> blur to host.
                try:
                    self._host.focus_set()
                except Exception:
                    pass
                return
            w = getattr(w, "master", None)
        # Focus already moved to another real widget -> leave it untouched.

    def _on_host_destroy(self, _e=None):
        try:
            self._top.unbind_all("<Control-f>")
        except Exception:
            pass
        try:
            if getattr(self, "_click_bind_id", None):
                self._top.unbind("<Button-1>", self._click_bind_id)
                self._click_bind_id = None
        except Exception:
            pass
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_search_bar.py -v`
Expected: PASS (all SearchBar tests).

- [ ] **Step 5: Commit**

```bash
git add src/ui/components/search_bar.py tests/test_search_bar.py
git commit -m "feat(search_bar): install_shortcuts with deferred focus-aware blur"
```

---

## Task 2: Wire Issues screen to the helper (remove duplicated block)

**Files:**
- Modify: `src/ui/screens/issues.py` (remove lines 54-113; add one call)
- Test: `tests/test_issues_screen.py`

- [ ] **Step 1: Write the failing test** — append to `tests/test_issues_screen.py`:

```python
def test_issues_uses_searchbar_shortcuts_helper(temp_db_path, monkeypatch, tk_root):
    """The screen delegates shortcuts to SearchBar.install_shortcuts and no
    longer carries its own click-outside handler (the focus-theft bug)."""
    import src.ui.screens.issues as mod
    monkeypatch.setattr(mod, "DB_PATH", temp_db_path)
    init_db(temp_db_path)
    screen = mod.IssuesScreen(tk_root)
    tk_root.update_idletasks()
    assert getattr(screen._search, "_click_bind_id", None) is not None
    assert not hasattr(screen, "_on_click_outside_search")
    screen.destroy()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_issues_screen.py::test_issues_uses_searchbar_shortcuts_helper -v`
Expected: FAIL — `screen._search._click_bind_id` is None (helper not called) and `screen._on_click_outside_search` still exists.

- [ ] **Step 3: Edit `src/ui/screens/issues.py`**

(a) Replace the shortcut-binding block at the end of `__init__` (currently lines 54-76, beginning with the `# Bind Ctrl+F app-wide…` comment and ending at `self.bind("<Destroy>", self._on_destroy_cleanup)`) with a single line:

```python
        # Search shortcuts (Ctrl+F focus + click-outside blur) live in the
        # SearchBar component so the corrected focus logic is shared, not
        # copy-pasted across screens.
        self._search.install_shortcuts(self)
```

(b) Delete the three now-unused methods: `_focus_search` (lines 77-80), `_on_click_outside_search` (lines 82-99), and `_on_destroy_cleanup` (lines 101-112).

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_issues_screen.py -v`
Expected: PASS (new test + all existing Issues tests, including `test_issues_screen_binds_ctrl_f`).

- [ ] **Step 5: Commit**

```bash
git add src/ui/screens/issues.py tests/test_issues_screen.py
git commit -m "refactor(issues): use SearchBar.install_shortcuts (fixes Detail-field focus theft)"
```

---

## Task 3: Wire Severe Lateness screen to the helper

**Files:**
- Modify: `src/ui/screens/severe_lateness.py` (remove lines 55-113; add one call)
- Test: `tests/test_severe_lateness_screen.py`

- [ ] **Step 1: Write the failing test** — append to `tests/test_severe_lateness_screen.py`:

```python
def test_severe_uses_searchbar_shortcuts_helper(temp_db_path, monkeypatch, tk_root):
    import src.ui.screens.severe_lateness as mod
    monkeypatch.setattr(mod, "DB_PATH", temp_db_path)
    init_db(temp_db_path)
    screen = mod.SevereLatenessScreen(tk_root)
    tk_root.update_idletasks()
    assert getattr(screen._search, "_click_bind_id", None) is not None
    assert not hasattr(screen, "_on_click_outside_search")
    screen.destroy()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_severe_lateness_screen.py::test_severe_uses_searchbar_shortcuts_helper -v`
Expected: FAIL (helper not called; old handler present).

- [ ] **Step 3: Edit `src/ui/screens/severe_lateness.py`**

(a) Replace the shortcut block at the end of `__init__` (lines 55-76, the `# Bind Ctrl+F app-wide…` comment through `self.bind("<Destroy>", self._on_destroy_cleanup)`) with:

```python
        self._search.install_shortcuts(self)
```

(b) Delete `_focus_search` (lines 78-81), `_on_click_outside_search` (lines 83-100), and `_on_destroy_cleanup` (lines 102-113).

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_severe_lateness_screen.py -v`
Expected: PASS (new test + existing, incl. `test_screen_binds_ctrl_f`).

- [ ] **Step 5: Commit**

```bash
git add src/ui/screens/severe_lateness.py tests/test_severe_lateness_screen.py
git commit -m "refactor(severe_lateness): use SearchBar.install_shortcuts (fixes Detail-field focus theft)"
```

---

## Task 4: Wire Outlier screen to the helper

**Files:**
- Modify: `src/ui/screens/outlier.py` (remove lines 50-108; add one call)
- Test: `tests/test_outlier_screen.py`

- [ ] **Step 1: Write the failing test** — append to `tests/test_outlier_screen.py`:

```python
def test_outlier_uses_searchbar_shortcuts_helper(temp_db_path, monkeypatch, tk_root):
    import src.ui.screens.outlier as mod
    monkeypatch.setattr(mod, "DB_PATH", temp_db_path)
    init_db(temp_db_path)
    screen = mod.OutlierScreen(tk_root)
    tk_root.update_idletasks()
    assert getattr(screen._search, "_click_bind_id", None) is not None
    assert not hasattr(screen, "_on_click_outside_search")
    screen.destroy()
```

If `tests/test_outlier_screen.py` lacks the standard imports, ensure the top of the file has:

```python
from src.db.schema import init_db
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_outlier_screen.py::test_outlier_uses_searchbar_shortcuts_helper -v`
Expected: FAIL (helper not called; old handler present).

- [ ] **Step 3: Edit `src/ui/screens/outlier.py`**

(a) Replace the shortcut block at the end of `__init__` (lines 50-71, the `# Bind Ctrl+F app-wide…` comment through `self.bind("<Destroy>", self._on_destroy_cleanup)`) with:

```python
        self._search.install_shortcuts(self)
```

(b) Delete `_focus_search` (lines 73-76), `_on_click_outside_search` (lines 78-95), and `_on_destroy_cleanup` (lines 97-108).

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_outlier_screen.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/ui/screens/outlier.py tests/test_outlier_screen.py
git commit -m "refactor(outlier): use SearchBar.install_shortcuts"
```

---

## Task 5: Wire Heatmap screen to the helper

**Files:**
- Modify: `src/ui/screens/heatmap.py` (remove the bind block at lines 79-86 and the three handler methods near line 399; add one call)
- Test: `tests/test_heatmap_screen.py`

- [ ] **Step 1: Write the failing test** — append to `tests/test_heatmap_screen.py`:

```python
def test_heatmap_uses_searchbar_shortcuts_helper(temp_db_path, monkeypatch, tk_root):
    import src.ui.screens.heatmap as mod
    monkeypatch.setattr(mod, "DB_PATH", temp_db_path)
    init_db(temp_db_path)
    screen = mod.HeatmapScreen(tk_root)
    tk_root.update_idletasks()
    assert getattr(screen._search, "_click_bind_id", None) is not None
    assert not hasattr(screen, "_on_click_outside_search")
    screen.destroy()
```

If the file lacks `from src.db.schema import init_db`, add it to the imports.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_heatmap_screen.py::test_heatmap_uses_searchbar_shortcuts_helper -v`
Expected: FAIL (helper not called; old handler present).

- [ ] **Step 3: Edit `src/ui/screens/heatmap.py`**

(a) Replace the bind block in `__init__` (lines 79-86):

```python
        self.bind("<Control-f>", self._focus_search)
        try:
            self.winfo_toplevel().bind_all("<Control-f>", self._focus_search)
        except Exception:
            pass
        self._click_bind_id = self.winfo_toplevel().bind(
            "<Button-1>", self._on_click_outside_search, add="+")
        self.bind("<Destroy>", self._on_destroy_cleanup)
```

with:

```python
        self._search.install_shortcuts(self)
```

(b) Delete the three handler methods on `HeatmapScreen`: `_focus_search`, `_on_click_outside_search` (defined at line 399), and `_on_destroy_cleanup`. (They are byte-identical to the versions removed in Task 2; the heatmap defines `self._search` in `_build_toolbar`, so the helper call has a valid search bar.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_heatmap_screen.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/ui/screens/heatmap.py tests/test_heatmap_screen.py
git commit -m "refactor(heatmap): use SearchBar.install_shortcuts"
```

---

## Task 6: Session `data_version` counter + test isolation

**Files:**
- Modify: `src/core/session_state.py` (append after the `period_state` singleton, line 35)
- Modify: `tests/conftest.py` (add autouse reset fixture)
- Test: `tests/test_session_state.py`

- [ ] **Step 1: Write the failing tests** — append to `tests/test_session_state.py`:

```python
from src.core.session_state import (
    SessionDataVersion, data_version, notify_data_changed,
)


def test_data_version_starts_at_zero():
    v = SessionDataVersion()
    assert v.get() == 0


def test_data_version_bump_increments():
    v = SessionDataVersion()
    v.bump()
    v.bump()
    assert v.get() == 2


def test_data_version_reset_zeroes():
    v = SessionDataVersion()
    v.bump()
    v.reset()
    assert v.get() == 0


def test_notify_data_changed_bumps_singleton():
    before = data_version.get()
    notify_data_changed()
    assert data_version.get() == before + 1


def test_data_version_module_singleton_type():
    assert isinstance(data_version, SessionDataVersion)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_session_state.py -v`
Expected: FAIL with `ImportError: cannot import name 'SessionDataVersion'`.

- [ ] **Step 3: Implement** — append to `src/core/session_state.py` (after the `period_state = SessionPeriodState()` line):

```python
class SessionDataVersion:
    """Monotonic counter bumped whenever issue/attendance analytics inputs
    change, so cached analytics views (Dashboard) can detect staleness and
    refetch. Session-only; never persisted."""

    def __init__(self):
        self._version = 0

    def get(self) -> int:
        return self._version

    def bump(self) -> None:
        self._version += 1

    def reset(self) -> None:
        """For test isolation. Production code should never call this."""
        self._version = 0


# Module-level singleton. One instance per app process.
data_version = SessionDataVersion()


def notify_data_changed() -> None:
    """Call after any write that changes issue/attendance analytics inputs
    (resolve, reopen, batch resolve, import). Bumps the shared data_version."""
    data_version.bump()
```

- [ ] **Step 4: Add the autouse reset fixture** — append to `tests/conftest.py`:

```python
@pytest.fixture(autouse=True)
def reset_data_version():
    """Reset the cross-screen data-version singleton between every test so
    bump-counting tests don't bleed state into each other."""
    from src.core.session_state import data_version
    data_version.reset()
    yield
    data_version.reset()
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_session_state.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/core/session_state.py tests/test_session_state.py tests/conftest.py
git commit -m "feat(session_state): data_version counter + notify_data_changed"
```

---

## Task 7: Dashboard invalidates its cache on version change

**Files:**
- Modify: `src/ui/screens/dashboard.py` (import line 19; `__init__` line 62; `_query` line 423)
- Test: `tests/test_dashboard_screen.py`

- [ ] **Step 1: Write the failing test** — append to `tests/test_dashboard_screen.py`:

```python
def test_dashboard_query_cache_invalidated_by_data_version(temp_db_path, monkeypatch, tk_root):
    """A data change (bump) forces _query to refetch instead of serving the
    memoized result for the same period."""
    import src.ui.screens.dashboard as mod
    from src.core.session_state import notify_data_changed
    monkeypatch.setattr(mod, "DB_PATH", temp_db_path)
    _setup_db(temp_db_path)

    calls = {"n": 0}
    real = mod.terlambat_ranking
    def counting(conn, s, e):
        calls["n"] += 1
        return real(conn, s, e)
    monkeypatch.setattr(mod, "terlambat_ranking", counting)

    screen = mod.DashboardScreen(tk_root)          # __init__ -> _update_data -> _query (1 call)
    tk_root.update_idletasks()
    start, end, _ = screen._period_range()
    base = calls["n"]
    screen._query(start, end)                      # same period, no change -> cache hit
    assert calls["n"] == base
    notify_data_changed()
    screen._query(start, end)                      # version changed -> cache cleared -> refetch
    assert calls["n"] == base + 1
    screen.destroy()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_dashboard_screen.py::test_dashboard_query_cache_invalidated_by_data_version -v`
Expected: FAIL — the second `_query` is a cache hit, so `calls["n"]` stays at `base` (no refetch).

- [ ] **Step 3: Edit `src/ui/screens/dashboard.py`**

(a) Change the import on line 19 from:

```python
from src.core.session_state import period_state
```

to:

```python
from src.core.session_state import period_state, data_version
```

(b) In `__init__`, right after `self._query_cache: dict = {}` (line 62), add:

```python
        # Version the cache was built at; cleared when issue data changes.
        self._cache_version: int = data_version.get()
```

(c) At the top of `_query` (line 423, before `key = (start, end)`), add the invalidation:

```python
    def _query(self, start, end):
        """Memoized data fetch. Returns a dict of pre-computed result lists."""
        # Drop the whole cache if issue data changed since it was built.
        current_version = data_version.get()
        if current_version != self._cache_version:
            self._query_cache.clear()
            self._cache_version = current_version
        key = (start, end)
        if key in self._query_cache:
            return self._query_cache[key]
        # ... existing body unchanged ...
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_dashboard_screen.py -v`
Expected: PASS (new test + existing Dashboard tests).

- [ ] **Step 5: Commit**

```bash
git add src/ui/screens/dashboard.py tests/test_dashboard_screen.py
git commit -m "fix(dashboard): invalidate _query_cache on data_version change"
```

---

## Task 8: Bump `data_version` on Issues resolve / unresolve

**Files:**
- Modify: `src/ui/screens/issues.py` (import line 13; `_on_save`; `_on_unresolve`)
- Test: `tests/test_issues_screen.py`

- [ ] **Step 1: Write the failing tests** — append to `tests/test_issues_screen.py`:

```python
def test_issues_on_save_bumps_data_version(temp_db_path, monkeypatch, tk_root):
    import src.ui.screens.issues as mod
    monkeypatch.setattr(mod, "DB_PATH", temp_db_path)
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        a = upsert_employee(conn, no_staff="1", nama="ANDI", dept="X")
        upsert_attendance(
            conn, employee_id=a, tanggal="2026-04-07", hari="Selasa",
            tipe="Hari Kerja", jadwal="08.00 - 16.00",
            masuk="08.30", keluar="16:00", kerja_jam=None,
            lembur_jam=None, terlambat_menit=30,
            has_issue=1, imported_from="W1.xls")
        set_setting(conn, "current_month", "2026-04")
    screen = mod.IssuesScreen(tk_root)
    tk_root.update_idletasks()
    children = screen.open_tree.get_children()
    screen.open_tree.selection_set(children[0])
    screen._on_select_open(None)
    tk_root.update_idletasks()
    screen.cat_var.set(screen.cat_combo.cget("values")[0])   # any valid category
    calls = []
    monkeypatch.setattr(mod, "notify_data_changed", lambda: calls.append(1))
    screen._on_save()
    assert calls == [1]
    screen.destroy()


def test_issues_on_unresolve_bumps_data_version(temp_db_path, monkeypatch, tk_root):
    import src.ui.screens.issues as mod
    monkeypatch.setattr(mod, "DB_PATH", temp_db_path)
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        a = upsert_employee(conn, no_staff="1", nama="ANDI", dept="X")
        upsert_attendance(
            conn, employee_id=a, tanggal="2026-04-07", hari="Selasa",
            tipe="Hari Kerja", jadwal="08.00 - 16.00",
            masuk=None, keluar="16:00", kerja_jam=None,
            lembur_jam=None, terlambat_menit=None,
            has_issue=1, imported_from="W1.xls")
        rid = conn.execute("SELECT id FROM attendance_records").fetchone()["id"]
        set_setting(conn, "current_month", "2026-04")
    screen = mod.IssuesScreen(tk_root)
    tk_root.update_idletasks()
    screen.selected_id = rid
    monkeypatch.setattr(mod.messagebox, "askyesno", lambda *a, **k: True)
    calls = []
    monkeypatch.setattr(mod, "notify_data_changed", lambda: calls.append(1))
    screen._on_unresolve()
    assert calls == [1]
    screen.destroy()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_issues_screen.py::test_issues_on_save_bumps_data_version tests/test_issues_screen.py::test_issues_on_unresolve_bumps_data_version -v`
Expected: FAIL — `notify_data_changed` is not imported into the issues module (`AttributeError` on the monkeypatch) / not called.

- [ ] **Step 3: Edit `src/ui/screens/issues.py`**

(a) Change line 13 from:

```python
from src.core.session_state import period_state
```

to:

```python
from src.core.session_state import period_state, notify_data_changed
```

(b) In `_on_save`, after the write block and before `self._reload()`:

```python
        with get_connection(DB_PATH) as conn:
            set_reason(conn, attendance_id=self.selected_id,
                       category=cat, detail=detail)
        notify_data_changed()
        self._reload()
```

(c) In `_on_unresolve`, after the write block and before `self._reload()`:

```python
        with get_connection(DB_PATH) as conn:
            unresolve_issue(conn, attendance_id=self.selected_id)
        notify_data_changed()
        self._reload()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_issues_screen.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/ui/screens/issues.py tests/test_issues_screen.py
git commit -m "feat(issues): notify_data_changed on resolve/unresolve"
```

---

## Task 9: Bump `data_version` on Severe Lateness resolve / unresolve

**Files:**
- Modify: `src/ui/screens/severe_lateness.py` (import line 13; `_on_save`; `_on_unresolve`)
- Test: `tests/test_severe_lateness_screen.py`

- [ ] **Step 1: Write the failing tests** — append to `tests/test_severe_lateness_screen.py`:

```python
def test_severe_on_save_bumps_data_version(temp_db_path, monkeypatch, tk_root):
    import src.ui.screens.severe_lateness as mod
    monkeypatch.setattr(mod, "DB_PATH", temp_db_path)
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        _seed(conn)
    screen = mod.SevereLatenessScreen(tk_root)
    tk_root.update_idletasks()
    children = screen.open_tree.get_children()
    screen.open_tree.selection_set(children[0])
    screen._on_select_open(None)
    tk_root.update_idletasks()
    screen.cat_var.set(screen.cat_combo.cget("values")[0])
    calls = []
    monkeypatch.setattr(mod, "notify_data_changed", lambda: calls.append(1))
    screen._on_save()
    assert calls == [1]
    screen.destroy()


def test_severe_on_unresolve_bumps_data_version(temp_db_path, monkeypatch, tk_root):
    import src.ui.screens.severe_lateness as mod
    monkeypatch.setattr(mod, "DB_PATH", temp_db_path)
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        _seed(conn)
        rid = conn.execute("SELECT id FROM attendance_records").fetchone()["id"]
    screen = mod.SevereLatenessScreen(tk_root)
    tk_root.update_idletasks()
    screen.selected_id = rid
    monkeypatch.setattr(mod.messagebox, "askyesno", lambda *a, **k: True)
    calls = []
    monkeypatch.setattr(mod, "notify_data_changed", lambda: calls.append(1))
    screen._on_unresolve()
    assert calls == [1]
    screen.destroy()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_severe_lateness_screen.py::test_severe_on_save_bumps_data_version tests/test_severe_lateness_screen.py::test_severe_on_unresolve_bumps_data_version -v`
Expected: FAIL — `notify_data_changed` not imported / not called in the severe_lateness module.

- [ ] **Step 3: Edit `src/ui/screens/severe_lateness.py`**

(a) Change line 13 from:

```python
from src.core.session_state import period_state
```

to:

```python
from src.core.session_state import period_state, notify_data_changed
```

(b) In `_on_save`, after the `set_reason` write block and before `self._reload()`:

```python
        notify_data_changed()
        self._reload()
```

(c) In `_on_unresolve`, after the `unresolve_issue` write block and before `self._reload()`:

```python
        notify_data_changed()
        self._reload()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_severe_lateness_screen.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/ui/screens/severe_lateness.py tests/test_severe_lateness_screen.py
git commit -m "feat(severe_lateness): notify_data_changed on resolve/unresolve"
```

---

## Task 10: Bump `data_version` on Batch Resolve + Import

**Files:**
- Modify: `src/ui/components/batch_resolve_dialog.py` (`_on_submit` line 343; add import)
- Modify: `src/ui/screens/import_screen.py` (`_on_confirm` after the import block; add import)
- Test: `tests/test_batch_resolve_dialog.py`

- [ ] **Step 1: Write the failing test (batch)** — append to `tests/test_batch_resolve_dialog.py`:

```python
def test_batch_submit_bumps_data_version(temp_db_path, monkeypatch, tk_root):
    import src.ui.components.batch_resolve_dialog as mod
    monkeypatch.setattr(mod, "DB_PATH", temp_db_path)
    init_db(temp_db_path)
    with get_connection(temp_db_path) as conn:
        a = upsert_employee(conn, no_staff="1", nama="ANDI", dept="X")
        _issue(conn, a, "2026-04-07", "Selasa")
        conn.commit()
        ids = [r["id"] for r in conn.execute(
            "SELECT id FROM attendance_records").fetchall()]
    dlg = mod.BatchResolveDialog(
        tk_root, period_start="2026-04-01", period_end="2026-04-30",
        on_done=lambda: None)
    tk_root.update_idletasks()
    monkeypatch.setattr(dlg, "_checked_ids", lambda: ids)
    dlg._cat_var.set("Cuti")                       # valid, no-detail category
    calls = []
    monkeypatch.setattr(mod, "notify_data_changed", lambda: calls.append(1))
    dlg._on_submit()
    assert calls == [1]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_batch_resolve_dialog.py::test_batch_submit_bumps_data_version -v`
Expected: FAIL — `notify_data_changed` not in the batch_resolve_dialog module.

- [ ] **Step 3a: Edit `src/ui/components/batch_resolve_dialog.py`**

Add the import alongside the existing imports (next to `from src.config import DB_PATH`):

```python
from src.core.session_state import notify_data_changed
```

In `_on_submit`, after the `with get_connection(DB_PATH) as conn: apply_batch_resolve(...)` block (line 343-344) and before `self.grab_release()`:

```python
        with get_connection(DB_PATH) as conn:
            apply_batch_resolve(conn, ids, cat, detail)
        notify_data_changed()
        try:
            self.grab_release()
```

- [ ] **Step 3b: Edit `src/ui/screens/import_screen.py`**

Add the import alongside the existing `from src.core....` / `from src.db....` imports:

```python
from src.core.session_state import notify_data_changed
```

In `_on_confirm`, immediately after the import `with ... get_connection(DB_PATH) as conn:` block closes (right after `restamp_holidays(conn)`, i.e. after the `with` block at ~line 573, before `row_count = len(self._pending_rows)`):

```python
            restamp_holidays(conn)

        notify_data_changed()

        row_count = len(self._pending_rows)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_batch_resolve_dialog.py -v`
Expected: PASS.

> Note on the import bump: the project has no headless ImportScreen test harness, and `_on_confirm` depends on ProgressModal / pending-row objects / toast, so a from-scratch unit test is disproportionate to a one-line call whose mechanism is already covered by Task 6 (`notify_data_changed`) and Task 7 (Dashboard reacts to a bump). The import bump is verified by the manual smoke step in Task 11 (import → Dashboard reflects new issues without restart).

- [ ] **Step 5: Commit**

```bash
git add src/ui/components/batch_resolve_dialog.py src/ui/screens/import_screen.py tests/test_batch_resolve_dialog.py
git commit -m "feat(writes): notify_data_changed on batch resolve + import"
```

---

## Task 11: Full suite + manual smoke

**Files:** none (verification only)

- [ ] **Step 1: Run the full test suite**

Run: `python -m pytest -q`
Expected: PASS — 363 baseline + the new tests added above (≈ 16 new), 0 failures.

- [ ] **Step 2: Launch the app for manual smoke**

Run: `python -m src.main`

- [ ] **Step 3: Walk the validation checklist** (these verify the real focus/refresh behavior that headless Tk cannot):

- [ ] Issues → select an open issue → click the **Detail** field → type a multi-word reason. All characters appear; caret stays; focus is not lost.
- [ ] Severe Lateness → select an open row → pick a needs-detail category → type in **Detail**. Same: typing works.
- [ ] In both, the SearchBar still filters Open + Resolved live; the "N dari M" counter updates; **Ctrl+F** focuses the search; clicking empty space below the tables blurs the search (placeholder returns).
- [ ] Click a tree row / the **Simpan** button / the category combo — all behave normally; pressing **Enter** in the Detail field saves.
- [ ] Resolve an employee's late day as **Tugas Lapangan**, then open the **Dashboard** — that employee's late-minutes total has dropped (no app restart).
- [ ] **Import** a fingerprint file, then open the Dashboard — new issues are reflected without restart.
- [ ] Navigate Issues ↔ Heatmap ↔ Outlier ↔ Dashboard repeatedly — no errors; search still works on each.

- [ ] **Step 4: Commit any smoke-found fixes** (if needed), otherwise the feature is complete on `v19`.

---

## Self-review

**Spec coverage:**
- BUG #2 root cause (deferred focus-aware blur) → Task 1. ✓
- Applied to all 4 screens (Issues, Severe Lateness, Outlier, Heatmap) → Tasks 2–5. ✓
- BUG #1 `data_version` + `notify_data_changed` → Task 6. ✓
- Dashboard cache invalidation → Task 7. ✓
- Bump on issue-lifecycle writes (resolve/unresolve/batch/import) → Tasks 8–10. ✓
- Test plan (blur decision, version mechanics, dashboard refetch, helper teardown) → Tasks 1, 6, 7. ✓
- Validation checklist → Task 11. ✓

**Placeholder scan:** No TBD/TODO; every code step shows full code; deletions name exact methods + line anchors; the one untested site (import) has an explicit, justified rationale + manual-smoke coverage (not a silent gap).

**Type consistency:** `install_shortcuts`, `_focus_shortcut`, `_on_click_outside`, `_release_if_orphaned`, `_on_host_destroy`, `_click_bind_id`, `_host`, `_top` (Task 1) used consistently in Tasks 2–5. `SessionDataVersion`, `data_version`, `notify_data_changed`, `_cache_version` (Task 6) used consistently in Tasks 7–10. Existing public attrs referenced (`screen._search`, `screen.cat_var`, `screen.cat_combo`, `screen.open_tree`, `screen.selected_id`, `dlg._checked_ids`, `dlg._cat_var`) match the v18 source.
