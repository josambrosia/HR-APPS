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
7. Update `memory/version_state.md`

Never push before steps 2-5. The bundle (rotated .exe + Installers/ copy) is the proof the milestone is real.

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

## Current state (as of last commit)

- Latest milestone: `v16.0.1` hotfix (commit `10c967d`, LOCAL only — awaiting push authorization) — fixes Resolve Massal button regression introduced in v16.0.0 T6 (SearchBar pack order pushed button off-screen). Otherwise same as v16.0.0 below.
- v16.0.0 bundle (commit `23c7bf1`) = UX polish: cross-screen week (SessionPeriodState), Search/filter (Issues + Outlier), Keyboard shortcuts (Ctrl+F / Esc / Enter), About dialog (sidebar), Print dashboard improvements (dynamic badge + period in H1 + KPI deltas + resolution strip + outlier line)
- Test baseline: **295 passing** (was 256 baseline; +37 from v16.0.0 + 2 from v16.0.1 regression guard)
- Latest installer artifact: `Installers/HR-Absensi-Setup-v16.0.1.exe` (33.4 MB) — canonical distributable
- Backup installer: `Installers/HR-Absensi-Setup-v16.0.0.exe` (33.4 MB) — for rollback (older v15.x also preserved)
- Production `.exe` at `D:\Gawe\Project X\HR App\dist\HR-Absensi\` is v16.0.1 with `.bak` of v16.0.0 + `.bak.old` of v15.3 (full 2-level rotation)

Subsequent work forks from `v16.0.1`. New features → new `vN+1` milestone following the 3-rule framework above.
