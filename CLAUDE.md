# HR Absensi — Project Framework

Top-level guidance for any Claude session working on this project. Auto-loaded by Claude Code.

## What this project is

Single-user desktop HR Absensi app for fingerprint-based attendance tracking. Python 3.x + customtkinter (UI) + SQLite (`data/hr.db`) + Jinja2 (HTML report templates) + PyInstaller (bundling) + Inno Setup 6 (installer). Tests via pytest. Versioned as `vN` snapshot branches on origin.

## Project-wide framework rules

These are the operating principles for every task on this repo. They complement (not replace) the detailed rules in `memory/workflow_rules.md`.

### 1. Every version ends in an app bundle

Each `vN` milestone delivers a **distributable bundle**, not just commits. Before a version is considered "done":

- `installer/Output/HR-Absensi-Setup-v{VERSION}.exe` is built via `python -m tools.build_installer`
- `dist/HR-Absensi/HR-Absensi.exe` (and `_internal/`) is rotated to production (`D:\Gawe\Project X\HR App\dist\HR-Absensi\`) per the 2-level `.bak` / `.bak.old` pattern
- **The freshly-built installer is copied to `D:\Gawe\Project X\HR App\Installers\HR-Absensi-Setup-v{VERSION}.exe`** — this is the canonical distributable artifact location at the project root, easy to grab and share to other laptops
- Manual smoke is run at least at the "app launches + dashboard renders" level

**Why:** a `vN` reference on origin must correspond to a runnable artifact the user can install/distribute, not just source code. The `Installers/` folder is the user-facing pickup point — no need to dig into worktrees or `installer/Output/` to find the latest setup.

### 2. Push and merge happen AFTER the bundle is built and smoke-passed

The release sequence is fixed:

1. Implement + commit + (full pytest green)
2. **Build installer** (`python -m tools.build_installer`)
3. **Rotate production .exe** (per `memory/workflow_rules.md` Rule 2)
4. **Copy installer to `D:\Gawe\Project X\HR App\Installers\HR-Absensi-Setup-v{VERSION}.exe`** (distributable pickup point)
5. **Smoke test** (manual, even briefly)
6. Update local `vN` branch → `git push origin vN`
7. **Update the `latest` pointer branch → `git push origin <vN-HEAD>:latest`** (force-fast-forward). `latest` is the repo's **default branch** on GitHub — it ALWAYS tracks the newest released version so the repo landing page shows current work without manual default-branch changes. Every release MUST advance it.
8. Update `memory/version_state.md`

Never push before steps 2-5. The bundle (rotated .exe + Installers/ copy) is the proof the milestone is real.

**`latest` branch convention:** `origin/latest` is a permanent pointer that mirrors the newest `vN` (currently `v16` @ `6070a4c`). It is set as GitHub's default branch ONCE (manually, in repo Settings → Branches). Thereafter, step 7 keeps it current. Do NOT delete it. To advance: `GIT_SSH_COMMAND="C:/Windows/System32/OpenSSH/ssh.exe" git push origin v{N}:latest`.

### 3. Auto-approve execution; use best judgment

When working on this project, the agent operates under these defaults:

1. **Auto-approve file read/write operations** — don't pause to ask permission to read or edit project files.
2. **Auto-approve shell command execution** — don't pause to ask permission to run pytest, git, PyInstaller, ISCC, etc.
3. **Do not pause for permission on any task** — proceed directly to action when the user's intent is clear.
4. **Use best judgment for ambiguous permission decisions** — when something is genuinely unclear (would the user want X or Y?), make the reasonable call and keep going; the user can redirect if needed.

This is the project's standing instruction for `auto mode` behavior. It does NOT override:

- `memory/workflow_rules.md` Rule 1 (**NO auto-push** — `git push` always requires explicit user authorization)
- Destructive ops (`git reset --hard`, `rm -rf` outside worktree, force-push to main) — still ask first
- Anything that touches production `data/hr.db` — never write to it without explicit instruction

### 4. Every new version updates APP_CHANGELOG

The About dialog shows users a scrollable changelog of what changed
per version. **Every new vN release (including patch hotfixes like
v16.0.1 / v16.0.2) MUST prepend an entry to `APP_CHANGELOG` in
`src/config.py`** documenting additions, removals, changes, and bug
fixes in user-facing terms (Indonesian, brief, action-oriented).

Format:
- Newest entry at the top of the list
- Each entry: `{"version", "date" (YYYY-MM-DD), "changes" (list of tuples)}`
- Each change is a `(kind, description)` tuple
- Kinds:
  - `"feat"` — fitur baru
  - `"fix"` — perbaikan bug
  - `"change"` — perubahan/penyesuaian perilaku yang ada
  - `"remove"` — penghapusan fitur

Why: users running the installer want to know what they're getting.
The changelog is also a forcing function for honest release notes —
if you can't describe a change in user-facing language, you probably
haven't thought hard enough about its impact.

## Where to look for more detail

User-level memory (auto-loaded by Claude Code on this project):

- `memory/workflow_rules.md` — detailed push / deploy / test / version conventions
- `memory/version_state.md` — what each `vN` snapshot represents on origin (current: v14 = coaching threshold dynamic + Windows installer)
- `memory/execution_preference.md` — agent execution preferences (subagent-driven default + auto-approval)
- `memory/progress_communication.md` — preference for task count + % progress during multi-step work
- `memory/project_handoff_pointer.md` — where to start when picking up the project after a break
- `memory/debugging_silent_crashes.md` — Windows-specific .exe crash diagnosis (Event Viewer, `0xc0000409` fastfail)

## Quick reference

```bash
# From worktree root (../../../ = .venv parent, project root)

# Full test suite
../../../.venv/Scripts/python.exe -m pytest -q

# Build installer end-to-end (PyInstaller + Inno Setup)
../../../.venv/Scripts/python.exe -m tools.build_installer

# Skip PyInstaller, re-package existing dist/
../../../.venv/Scripts/python.exe -m tools.build_installer --skip-pyi

# SSH push from Git Bash needs the Windows OpenSSH agent (passphrase-protected key):
GIT_SSH_COMMAND="C:/Windows/System32/OpenSSH/ssh.exe" git push origin vN

# Check exe not running before any rebuild
tasklist | grep -i HR-Absensi || echo "not running"
```

## Current state (as of last commit) — HANDOFF for next session

**Branch:** `claude/inspiring-dhawan-47161f` · **HEAD:** `720672c` · tree clean. `APP_VERSION = 18.0.0`.

### What's done (LOCAL only — nothing pushed)
- **v17.0.0** (commit `02d4bb4`) = Severe Lateness menu. Installer built (`Installers/HR-Absensi-Setup-v17.0.0.exe`). **NOT pushed — held.**
- **v18.0.0** = **Heatmap Kehadiran**, rendered **IN-APP** (customtkinter + `tk.Canvas`). Pivoted from an earlier browser/loopback-server design (server removed). ~32 commits on top of v17. Features:
  - In-app heatmap screen `src/ui/screens/heatmap.py`: per-employee grid + **Panel Sorotan** (% kehadiran + bar + HK/total ratio + tepat waktu + total telat + dinas/sakit) + Ringkasan; **sort** dropdown (nama / kehadiran terendah / paling telat / paling absen), **"Perlu perhatian"** red accent (X or TB), **"hari ini"** outline, hover tooltip + click→detail strip, **responsive multi-column reflow** by window width, Ctrl+F + click-outside-blur.
  - Pure logic in `src/core/heatmap.py`: `cell_status`, `build_heatmap_context` (+ per-emp `sorotan`, `today_day`), `pct_band_color`, `needs_attention`, `sort_employees`.
  - **Print** (server-free): `src/reports/heatmap_print.py::render_heatmap_print_html` → temp `.html` → `open_html_in_browser` (Cetak-Dashboard idiom). Appendix shows short `D · Dinas`, wide Alasan / narrow Masuk-Keluar-Telat, and **HR Officer name from Settings** in the header.
  - New setting **Toleransi Telat (menit)** (default 12).
  - Smoke fixes applied: multi-column layout, Cetak→browser (str-path `.as_uri` crash in `browser_launcher`), Dinas short label, appendix column widths, **HR Officer print header** (commit `720672c`).
- **Test baseline: ~362 passing.** (`../../../.venv/Scripts/python.exe -m pytest -q`)
- Specs/plans: `docs/superpowers/specs/2026-06-10-v18-heatmap-dashboard-design.md` (revised v2 in-app), `docs/superpowers/plans/2026-06-10-v18-heatmap-inapp.md`.

### ⚠️ IMMEDIATE NEXT STEPS (do these in the CLI session)
1. **Confirm full suite green.** Last run reached 93% with everything passing; the slow GUI tail (`test_settings_screen_severe_lateness`, `test_severe_lateness_screen`) is v17 code unaffected by the v18 print-only HR-officer change. Re-run if you want a clean 100%.
2. **REBUILD the installer** — the current prod `.exe` + `Installers/HR-Absensi-Setup-v18.0.0.exe` were built **before** the HR-Officer-fix commit `720672c`, so they do **NOT** include it yet. Run `export PATH="/c/Program Files (x86)/Inno Setup 6:$PATH" && python -m tools.build_installer` → rotate prod `dist/HR-Absensi/` 2-level (never touch `data/`) → copy to `Installers/HR-Absensi-Setup-v18.0.0.exe`.
3. **HOLD push.** BOTH `v17` and `v18` are unpushed and require **explicit user authorization** (Rule 1). When authorized: `git push origin HEAD:v18`, advance `latest` (`HEAD:latest`), and push/tag `v17` too; then update `memory/version_state.md`.

### Notes
- Latest installer `Installers/HR-Absensi-Setup-v18.0.0.exe` (in-app v18, but pre-HR-officer-fix → rebuild per step 2). Older v17/v16.x installers preserved for rollback.
- Product screenshots were captured via a dummy dev DB (`seed_dummy.py` + `worktree/data/hr.db`) and then **removed** (tree clean). Re-seed only if more screenshots are needed; never point screenshots at production data.

Subsequent work forks from `v18.0.0`.
