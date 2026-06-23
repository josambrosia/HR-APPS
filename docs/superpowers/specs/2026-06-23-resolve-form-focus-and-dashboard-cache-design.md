# Resolve-form focus theft + Dashboard freshness — design

**Date:** 2026-06-23
**Branch:** `v19` (forked from `origin/v18` @ `3d28aff`) — the vN/deployed line.
**Status:** approved design, pending spec review → implementation plan.

## Scope

Fix two reported bugs in the deployed app without temporary workarounds:

- **BUG #2 — Resolve Issue form input broken.** Cannot type into the Detail field on the Resolve panel.
- **BUG #1 — Dashboard not realtime.** Dashboard reportedly does not reflect issue changes without an app reload.

Both bugs belong to the **vN feature line** (v16→v18), not the `implement-mvp` trunk, which has no SearchBar and therefore cannot exhibit BUG #2. `implement-mvp` is **not** touched by this work.

## Architecture (existing, unchanged)

- **Framework:** CustomTkinter (`ctk.CTk`). Single content area; `HRApp._show(name)` **destroys all current content children and constructs a fresh screen instance** on every navigation (`app.py:394-398`).
- **Data:** SQLite via `get_connection()` context manager — fresh connection per call, **commit on clean exit** (`connection.py`). No process-level cache, no `lru_cache`, no long-lived/shared connection.
- **Session state:** module-level singletons in `src/core/session_state.py` (today: `period_state`). This is the established pattern for ephemeral cross-screen state and is reused below.

---

## BUG #2 — Resolve Issue form input broken

### Reported symptom
On the Resolve Issue panel users cannot type into the Detail/Description field; it loses focus / drops keystrokes. Reporter suspected the search bar capturing keystrokes.

### Root cause (confirmed)
The suspicion is wrong: `SearchBar` only binds `<KeyRelease>` on its **own** entry (`search_bar.py:57`) — it never grabs global keys.

The real cause is the **click-outside-blur** feature (added in v16.1.1). Each screen registers, on the **toplevel**:

```
issues.py:73   self._click_bind_id = top.bind("<Button-1>", self._on_click_outside_search, add="+")
```

and the handler force-blurs focus when the click is not inside the SearchBar:

```
issues.py:82-99   _on_click_outside_search():
    walk up from event.widget; if it reaches self._search -> return
    else:  self.focus_set()          # <-- steals focus to the screen frame
```

Tk dispatches `<Button-1>` through bindtags in order **widget → widget-class → toplevel → all**. The `Entry`-class binding (which gives the clicked entry keyboard focus) runs *before* the toplevel binding. So when the user clicks the Detail field (`detail_entry`, `issues.py:351`) or the category combo (`cat_combo`, `issues.py:328`):

1. Tk's `Entry` class binding focuses the field.
2. The toplevel `_on_click_outside_search` then runs and calls `self.focus_set()`, ripping focus to the frame.

Net effect: the caret never settles in the field and typing is lost. The SearchBar keeps working only because clicks inside it return early. This exactly matches "search works, form field doesn't."

The handler is **copy-pasted verbatim** into four screens, all calling `self.focus_set()`:

| Screen | handler | has Resolve Detail form? |
|---|---|---|
| `issues.py:82` | `_on_click_outside_search` | **yes** (`detail_entry`) |
| `severe_lateness.py:83` | `_on_click_outside_search` | **yes** (`detail_entry`) |
| `outlier.py:78` | `_on_click_outside_search` | no (search + cards) |
| `heatmap.py:399` | `_on_click_outside_search` | no (search + sort combo + canvas) |

So the Detail field is broken on **both** Issues and Severe Lateness; the handler can also steal focus from any other input on Outlier/Heatmap. The fix must cover all four.

Note: `BatchResolveDialog` is a separate `CTkToplevel`; its widgets do **not** carry the main window's `.` bindtag, so the click-outside handler never fires for them — its inputs were never broken by this bug.

### Fix — shared, corrected helper on `SearchBar`

Add **`SearchBar.install_shortcuts(host)`** (in `search_bar.py`) that owns the whole shortcut block — Ctrl+F focus, click-outside-blur, and `<Destroy>` cleanup — with the blur logic corrected so it **never steals focus from a real input**:

```
on <Button-1> (bound on host's toplevel, add="+"):
    if click target is inside the SearchBar:  return            # interacting with search
    else:  after_idle(decide)                                   # let Tk's native focus settle first

decide():
    f = focus_get()
    if f is still inside the SearchBar:  host.focus_set()       # clicked an inert area -> blur search
    else:                                 do nothing            # clicked another input -> leave its focus
```

The deferral (`after_idle`) plus a re-check of the **actual resulting focus** is the root-cause fix: if the click landed on another input (entry/combo/tree/button), that widget keeps the focus it just took and the search blurs naturally via its own `FocusOut`; only when focus is *still* in the search (an inert click) do we move it to the host. The click-outside-blur feature is preserved; the focus theft is gone.

Cleanup references the toplevel captured at install time (`self._top`) rather than calling `winfo_toplevel()` during destruction.

The four screens delete their duplicated bind block + the three methods (`_focus_search`, `_on_click_outside_search`, `_on_destroy_cleanup`) and call `self._search.install_shortcuts(self)` after their search bar exists. This removes ~4× duplication (the very thing that let one bug live in four places) — a targeted DRY improvement directly serving the fix.

### Proposed `SearchBar` additions

```python
def install_shortcuts(self, host):
    """Ctrl+F focuses this search; clicking an inert area outside it blurs it.
    Auto-cleans up on host <Destroy>. The blur decision is deferred so it can
    never steal focus from an input the user just clicked."""
    self._host = host
    self._top = host.winfo_toplevel()
    host.bind("<Control-f>", self._focus_shortcut)
    try:
        self._top.bind_all("<Control-f>", self._focus_shortcut)
    except Exception:
        pass
    self._click_bind_id = self._top.bind("<Button-1>", self._on_click_outside, add="+")
    host.bind("<Destroy>", self._on_host_destroy)

def _focus_shortcut(self, _e=None):
    if self.winfo_exists():
        self.focus()
    return "break"

def _on_click_outside(self, event):
    w = event.widget
    while w is not None:
        if w is self:
            return
        w = getattr(w, "master", None)
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
        if w is self:                 # focus still in search -> inert click -> blur to host
            try:
                self._host.focus_set()
            except Exception:
                pass
            return
        w = getattr(w, "master", None)
    # else: focus already moved to another widget -> leave it

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

Side benefit: with focus no longer stolen, the existing Enter-to-save bindings on `detail_entry`/`cat_combo` (`issues.py:341-359`) finally work as intended.

---

## BUG #1 — Dashboard not realtime

### Reported symptom
"Dashboard does not update after a resolve until the app is reloaded."

### Investigation (v18 source)
The literal symptom does **not** reproduce on v18, and the user confirmed: re-opening the Dashboard **does** show fresh numbers. The reasons:

- `set_reason` / `unresolve_issue` commit to SQLite (`connection.py:15`); writes persist.
- `_show("Dashboard")` builds a **new** `DashboardScreen` each navigation; `_query_cache` is **instance-level**, created empty in `__init__` (`dashboard.py:62`).
- `_query()` reads fresh from DB on a cache miss (`dashboard.py:423-441`).
- No process-level cache anywhere; `self._screens` in `app.py:35` is dead code (declared, never read).

So freshness today is an **implicit side effect** of full teardown-on-navigation. The only real artifact is the `_query_cache`: it is safe *only because* the screen is destroyed each navigation. If navigation is ever changed to cache/reuse screens (a common optimization the dead `_screens` dict hints was once intended), the Dashboard would instantly go stale — the reported symptom. BUG #1 task #6 also explicitly requires: "if caching is used, invalidate or refresh cache correctly."

### Fix — explicit data-version cache invalidation

Make freshness explicit and robust instead of accidental.

1. **`src/core/session_state.py`** — add a monotonic counter + helper:

```python
class SessionDataVersion:
    """Bumped whenever issue/attendance analytics inputs change, so cached
    analytics views can detect staleness and refetch."""
    def __init__(self):
        self._version = 0
    def get(self) -> int:
        return self._version
    def bump(self) -> None:
        self._version += 1
    def reset(self) -> None:      # test isolation only
        self._version = 0

data_version = SessionDataVersion()

def notify_data_changed() -> None:
    """Call after any write that changes issue/attendance analytics inputs."""
    data_version.bump()
```

2. **Bump on each issue-lifecycle write** (the scope BUG #1 names: created / edited / resolved / reopened):
   - `issues.py::_on_save` (after `set_reason` commits, ~`issues.py:438`)
   - `issues.py::_on_unresolve` (after `unresolve_issue` commits, ~`issues.py:455`)
   - `severe_lateness.py::_on_save` and `::_on_unresolve` (`set_reason`@440 / `unresolve_issue`@458)
   - `batch_resolve_dialog.py::_on_submit` (after `apply_batch_resolve`'s connection block commits)
   - `import_screen.py` confirm-import (after the import `with get_connection(...)` block commits, ~`import_screen.py:574`) — covers "created"

3. **`dashboard.py`** — invalidate the cache when the version changed:
   - `__init__`: stamp `self._cache_version = data_version.get()` (next to `self._query_cache = {}`).
   - top of `_query()`:

```python
current = data_version.get()
if current != self._cache_version:
    self._query_cache.clear()
    self._cache_version = current
```

This guarantees a fresh Dashboard regardless of navigation behavior. Today it is belt-and-suspenders (teardown already refreshes); it becomes load-bearing the moment any screen is cached, and it satisfies task #6 with a correct, explicit invalidation rather than a hidden side effect.

### Out of scope for BUG #1
- Outlier exclusions and Hari Libur edits affect Dashboard analytics too, but they are not *issue-lifecycle* writes; they already refresh via teardown-on-navigation, and instrumenting them is not required by the bug. They may be added to `notify_data_changed()` later if desired (no harm).
- No change to cache lifetime/perf — it stays instance-level. (Making it a persistent module-level cache for performance is a possible future enhancement, not part of this fix.)

---

## Files modified

| File | Change |
|---|---|
| `src/ui/components/search_bar.py` | Add `install_shortcuts(host)` + 4 helper methods (corrected blur). |
| `src/ui/screens/issues.py` | Remove dup shortcut block + 3 methods; call `install_shortcuts`; `notify_data_changed()` in `_on_save`/`_on_unresolve`. |
| `src/ui/screens/severe_lateness.py` | Same as Issues. |
| `src/ui/screens/outlier.py` | Remove dup shortcut block + 3 methods; call `install_shortcuts`. |
| `src/ui/screens/heatmap.py` | Remove dup shortcut block + 3 methods; call `install_shortcuts`. |
| `src/core/session_state.py` | Add `SessionDataVersion`, `data_version`, `notify_data_changed`. |
| `src/ui/components/batch_resolve_dialog.py` | `notify_data_changed()` after batch commit. |
| `src/ui/screens/import_screen.py` | `notify_data_changed()` after import commit. |
| `src/ui/screens/dashboard.py` | Stamp `_cache_version`; clear `_query_cache` on version change. |
| `tests/...` | New unit tests (below). |

## Test plan

Headless Tk cannot reliably verify real keyboard focus (documented project constraint), so focus correctness is split into a unit-testable decision + a manual smoke check.

- **Unit — blur decision** (`SearchBar._release_if_orphaned`): with `focus_get` patched to return (a) a widget inside the search → asserts host blur invoked; (b) a widget outside the search → asserts focus left untouched.
- **Unit — data-version:** `notify_data_changed()` increments `data_version`; `reset()` zeroes it (autouse reset fixture for isolation, mirroring the existing `reset_period_state` fixture).
- **Unit — Dashboard invalidation:** build a `DashboardScreen`, prime `_query_cache`, `notify_data_changed()`, call `_query`/`_update_data`, assert the cache was rebuilt (e.g., spy on a query fn or check `_cache_version` advanced and a re-query occurred).
- **Unit — helper teardown:** after `install_shortcuts` + host destroy, the `<Control-f>` bind_all and `<Button-1>` bind are removed (no leak).
- **Manual smoke:** type a multi-word detail in Issues Resolve **and** Severe Lateness Resolve → text appears, caret stable; SearchBar still filters; Ctrl+F focuses search; click empty space exits search; resolve as *Tugas Lapangan* → Dashboard late-minutes drop on next view.

## Validation checklist (proves both bugs fixed)

- [ ] Type a multi-word Detail in **Issues** Resolve → all characters appear, caret stays, no focus loss.
- [ ] Same on **Severe Lateness** Resolve panel.
- [ ] SearchBar still filters Open + Resolved live; counter updates; Ctrl+F focuses it; clicking empty space blurs it.
- [ ] Clicking a tree row / Save / category combo behaves normally; Enter in Detail saves.
- [ ] Resolve an issue as *Tugas Lapangan* → that employee's late minutes drop on next Dashboard view.
- [ ] Unit test proves Dashboard re-queries after `notify_data_changed()`.
- [ ] No `<Control-f>` / `<Button-1>` binding leaks after leaving a search screen.
- [ ] Full suite green (363 baseline + new tests).

## Risks / mitigations

- **`after_idle` timing** — the blur decision must run after Tk's native click→focus. `after_idle` schedules on the idle queue, which drains after current event processing → correct ordering. Mitigation: unit test the decision logic directly.
- **Destroy-time toplevel access** — cleanup uses the toplevel captured at install (`self._top`), avoiding `winfo_toplevel()` calls during widget teardown.
- **bind_all Ctrl+F** — behavior preserved (one search screen mounted at a time; unbound on host destroy), matching current code.
