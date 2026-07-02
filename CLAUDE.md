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

## Current state (2026-07-03) — HANDOFF for next session

**Branch:** `v22.0.0` (forked from local `v21.2.0`) · `APP_VERSION = 22.0.0`.

### v22.0.0 = "Frontend Quality Pass" (P0+P1 dari audit frontend 2026-07-03)
No new features — behavior/architecture hardening. Plan: `docs/superpowers/plans/2026-07-03-v22-frontend-quality-pass.md`. Highlights:
- **Non-blocking UI**: Export/Generate/Preview/Import berjalan via `src/ui/tasks.py::run_bg` (worker thread + queue + `after` polling; worker buka koneksi SQLite sendiri) + `BusyGuard` anti klik-ganda.
- **Screen caching**: `app.py._show` menyimpan instance layar (`grid_remove`/`grid`), memanggil kontrak `on_show()` pada tiap re-display (semua 12 layar punya `on_show` — selalu re-read data volatil, chrome tidak dibangun ulang). `WeekNavBar.sync()` untuk bar persisten.
- **ResolveScreenBase** (`src/ui/screens/resolve_base.py`): `issues.py` (485→37 LOC) dan `severe_lateness.py` (476→70) kini subclass tipis.
- **feedback.py + MessageDialog**: semua `tkinter.messagebox` diganti dialog gelap; sukses ringan → toast.
- **Token & komponen**: tint semantik terpusat di `theme.py` (zero hex liar di semua screen kecuali palet lokal bernama `_WA_*`/`_BENTO_*` + `#0F0F0F` dropzone); komponen shared baru: ActiveMonthBanner, EmptyStateCard, FileChip, HistoryList; `core/week_utils.py` = resolve_period/week_range/parse_week_key/MONTH_NAMES_ID (dedup 4× resolver + 3× dict bulan).
- **SearchBar debounce** (200ms di resolve/heatmap/whatsapp), heatmap resize throttle, SQL mentah keluar dari layar UI ke `src/db/`.

### Push state (verified 2026-07-03)
- `origin/v21` = `origin/latest` = `0ff4e6c` — jadi **v21.1.0 + v21.2.0 (sampai `7e3ddee`) + seluruh v22 masih LOKAL, belum dipush**. Rule 1 tetap: push hanya dengan otorisasi eksplisit user. Saat diotorisasi: push `v21.2.0` (opsional, atau langsung) + `git push origin v22.0.0`, lalu advance `latest`; update `memory/version_state.md`.

### Notes
- Suite penuh hijau (500+ tests, ±2 menit). Test lama yang nge-hang di dialog native sudah dipatch (`test_settings_screen_severe_lateness.py`).
- Screenshots di `Screenshots/` + 4 mockup HTML `_mockup_v*.html` + `color-palette.txt` di root = artefak eksplorasi desain (untracked, sengaja).
- Arah desain laporan cetak (editorial dsb.) BELUM dieksekusi — kandidat v22.1/v23 (lihat item P2 di plan doc).

Subsequent work forks from `v22.0.0`.
