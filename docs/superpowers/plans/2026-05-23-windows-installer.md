# Windows Installer (Inno Setup) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Package the existing PyInstaller `.exe` bundle as a single `HR-Absensi-Setup-vX.Y.Z.exe` Windows installer that installs per-user without admin, creates Start Menu + Desktop shortcuts, registers with Add/Remove Programs, preserves `data/hr.db` across upgrades, and offers a one-time data migration from the legacy deploy folder.

**Architecture:** Free **Inno Setup 6** with a single `installer/HR-Absensi.iss` script as the source of truth. A `tools/build_installer.py` orchestrator runs PyInstaller then `ISCC.exe` against the `.iss`, reading version from `src/config.py::APP_VERSION` and passing it via `/DAppVersion=`. The `.iss` includes a small `[Code]` Pascal Script section that handles one-time data migration on first install. No new Python runtime dependencies; Inno Setup is installed once on the dev machine.

**Tech Stack:** Inno Setup 6 (free, https://jrsoftware.org/isinfo.php), Pascal Script (Inno's `[Code]` language, ~30 lines), Python 3.x for the orchestrator, existing PyInstaller flow unchanged.

**Spec:** [docs/superpowers/specs/2026-05-23-windows-installer-design.md](../specs/2026-05-23-windows-installer-design.md) (commit `524fcf7`).

**Baseline tests:** 241 passing. Target after this plan: still 241 passing (this is a build/packaging-only change; only `APP_VERSION` constant is touched in application code).

**Total tasks: 6.** Sequential — each task ends with a commit. No parallelism.

**Per-task progress reporting (user preference, per `memory/progress_communication.md`):** When dispatching each implementation subagent, the controller should announce `"Task N of 6 — <task name> (M% complete)"` before dispatch. Percentages: Task 1 → 17%, 2 → 33%, 3 → 50%, 4 → 67%, 5 → 83%, 6 → 100%.

**Important conventions to respect:**
- Worktree at `D:\Gawe\Project X\HR App\.claude\worktrees\inspiring-dhawan-47161f`. Use absolute paths or `cd` once at the worktree root.
- pytest command: `../../../.venv/Scripts/python.exe -m pytest -q` (venv is 3 levels up).
- NO auto-push to origin. Commits only; user authorizes push explicitly later.
- Inno Setup must be installed on the dev machine **before Task 3** can run end-to-end. If it isn't, build_installer.py prints a clear install URL. Implementer should install it manually if missing — install URL: https://jrsoftware.org/isdl.php (download `innosetup-6.x.x.exe`, run, accept defaults).
- Project line-ending warnings (`LF will be replaced by CRLF`) are expected on Windows — ignore.

---

## File Structure

**Files created:**

```
installer/
  HR-Absensi.iss         # Inno Setup source script. Single source of truth for installer
                         # config: install path, files, shortcuts, uninstall, plus the
                         # [Code] Pascal Script for one-time data migration.
  README.md              # Developer notes: Inno Setup install instructions, build command,
                         # manual smoke checklist (copy from spec Section 6).
tools/
  build_installer.py     # Orchestrator script. Verifies ISCC on PATH, runs PyInstaller,
                         # runs ISCC against HR-Absensi.iss with /DAppVersion=<value>.
                         # Single responsibility: produce installer/Output/HR-Absensi-Setup-vX.Y.Z.exe
                         # from a clean source tree.
```

**Files modified:**

- `src/config.py`: bump `APP_VERSION = "0.0.1"` → `"14.0.0"`. Single line change. `tools/build_installer.py` reads this value at build time.
- `.gitignore`: add `installer/Output/` to keep build artifacts out of git.

**Files NOT touched (deliberately):**

- `src/main.py`, `src/db/`, `src/ui/`, `src/reports/`: zero application logic changes.
- `tests/`: no new tests (build/packaging task, no unit-testable code path).
- `HR-Absensi.spec`: PyInstaller config stays as-is.
- `data/hr.db` in production: never touched by the installer build process.

---

## Task 1 — Bump APP_VERSION and prepare .gitignore

Foundational. Both downstream tasks read `APP_VERSION`. Trivial scope (~2 minutes).

**Files:**
- Modify: `src/config.py:5`
- Modify: `.gitignore`

### Step 1: Update `src/config.py:5`

Replace:
```python
APP_VERSION = "0.0.1"
```
with:
```python
APP_VERSION = "14.0.0"
```

### Step 2: Verify no test depends on the old literal

Run from worktree root:
```
../../../.venv/Scripts/python.exe -m pytest -q
```

Expected: still 241 passed. If any test fails because it asserted `APP_VERSION == "0.0.1"` literally, that's a real test to update — but the codebase grep shows no such reference. If pytest is green, move on.

### Step 3: Update `.gitignore`

Append the installer output directory to the end of the file. Read the existing `.gitignore` first to find an appropriate insertion point (probably alongside other build artifact ignores like `dist/`, `build/`).

Add:
```
# Inno Setup build artifacts
installer/Output/
```

### Step 4: Commit

```bash
git add src/config.py .gitignore
git commit -m "$(cat <<'EOF'
chore(version): bump APP_VERSION to 14.0.0 and ignore installer output

Aligns the constant with the vN milestone. Downstream installer build
script reads APP_VERSION via /DAppVersion= to ISCC.exe.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2 — Create installer/HR-Absensi.iss (base, no migration code yet)

The Inno Setup source script. Produces a working installer that does install/upgrade/uninstall correctly. Pascal Script for data migration is added in Task 4 so this task can be reviewed in isolation.

**Files:**
- Create: `installer/HR-Absensi.iss`

### Step 1: Generate the AppId GUID

Run from any shell:
```
../../../.venv/Scripts/python.exe -c "import uuid; print('{' + str(uuid.uuid4()).upper() + '}')"
```

Example output:
```
{A3F8E2D1-7B4C-4F9A-B6E5-1234567890AB}
```

Capture this value — it must be embedded as a string literal in the `.iss` script. **Once committed, this GUID must NEVER change across versions** — Inno uses it to detect upgrade vs fresh install.

### Step 2: Create `installer/HR-Absensi.iss`

Write the file with the GUID from Step 1 substituted at the `{REPLACE-WITH-GENERATED-GUID}` placeholder below:

```ini
; HR Absensi App — Inno Setup script
; Build:   ISCC.exe installer/HR-Absensi.iss /DAppVersion=14.0.0
; Locally: python -m tools.build_installer

#define AppName        "HR Absensi App"
#define AppPublisher   "Josaphat Tech Solution"
#define AppExeName     "HR-Absensi.exe"
#define AppId          "{REPLACE-WITH-GENERATED-GUID}"
; AppVersion is injected at build time via /DAppVersion=

[Setup]
AppId={#AppId}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={localappdata}\Programs\HR-Absensi
DefaultGroupName={#AppName}
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=Output
OutputBaseFilename=HR-Absensi-Setup-v{#AppVersion}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
SetupIconFile=..\assets\brand\icon-04E.ico
UninstallDisplayIcon={app}\{#AppExeName}

[Tasks]
Name: "desktopicon"; Description: "Create desktop shortcut"; \
    GroupDescription: "Additional shortcuts:"

[Files]
Source: "..\dist\HR-Absensi\HR-Absensi.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\dist\HR-Absensi\_internal\*"; DestDir: "{app}\_internal"; \
    Flags: ignoreversion recursesubdirs createallsubdirs
; data\hr.db deliberately NOT shipped. First launch's init_db() creates it.

[Dirs]
Name: "{app}\data"; Permissions: users-modify

[Icons]
Name: "{group}\HR Absensi"; Filename: "{app}\{#AppExeName}"; \
    IconFilename: "{app}\{#AppExeName}"
Name: "{group}\Uninstall HR Absensi"; Filename: "{uninstallexe}"
Name: "{userdesktop}\HR Absensi"; Filename: "{app}\{#AppExeName}"; \
    IconFilename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "Launch HR Absensi App"; \
    Flags: nowait postinstall skipifsilent
```

### Step 3: (Optional) Validate `.iss` syntax with ISCC if installed

If Inno Setup is already on the dev machine, run:
```
ISCC.exe /DAppVersion=14.0.0 /Q installer/HR-Absensi.iss
```

Expected: produces `installer/Output/HR-Absensi-Setup-v14.0.0.exe` (if `dist/HR-Absensi/` exists from a previous PyInstaller build).

If ISCC is not yet installed, skip this step. Task 3's orchestrator will detect missing ISCC and print install instructions.

### Step 4: Commit

```bash
git add installer/HR-Absensi.iss
git commit -m "$(cat <<'EOF'
feat(installer): add Inno Setup source script for HR Absensi installer

Per-user install at %LOCALAPPDATA%\Programs\HR-Absensi\, no UAC.
Ships PyInstaller bundle, creates Start Menu + opt-in Desktop shortcut,
registers with Add/Remove Programs. Migration Pascal Script added in
the next commit.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3 — Create tools/build_installer.py orchestrator

Single-command build from source to deliverable. Verifies prereqs, runs PyInstaller, runs ISCC.

**Files:**
- Create: `tools/build_installer.py`

### Step 1: Create `tools/build_installer.py`

```python
"""Build the HR-Absensi installer.

Single-command end-to-end build: PyInstaller bundle → Inno Setup installer.

Steps:
  1. Pre-flight: verify Inno Setup CLI (ISCC.exe) is on PATH; verify
     HR-Absensi.exe is not currently running (PyInstaller would fail);
     read APP_VERSION from src/config.py.
  2. PyInstaller: produce dist/HR-Absensi/ from HR-Absensi.spec.
  3. ISCC: run installer/HR-Absensi.iss with /DAppVersion=<value>,
     producing installer/Output/HR-Absensi-Setup-vX.Y.Z.exe.

Usage:
  python -m tools.build_installer            # full build
  python -m tools.build_installer --skip-pyi # skip PyInstaller (re-package existing dist/)
  python -m tools.build_installer --allow-dirty  # don't warn about uncommitted changes

Fail-fast: any step's non-zero exit code aborts the build.
"""
import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path


WORKTREE_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PY = WORKTREE_ROOT / "src" / "config.py"
ISS_FILE = WORKTREE_ROOT / "installer" / "HR-Absensi.iss"
ISS_OUTPUT_DIR = WORKTREE_ROOT / "installer" / "Output"
PYI_DIST_DIR = WORKTREE_ROOT / "dist" / "HR-Absensi"
PYI_EXE = PYI_DIST_DIR / "HR-Absensi.exe"

INNO_INSTALL_URL = "https://jrsoftware.org/isdl.php"
INNO_DEFAULT_PATH_HINT = (
    "Default install path: C:\\Program Files (x86)\\Inno Setup 6\\ "
    "(ISCC.exe must be on PATH or in that folder)"
)


def read_app_version() -> str:
    """Parse APP_VERSION literal from src/config.py without importing it."""
    text = CONFIG_PY.read_text(encoding="utf-8")
    m = re.search(r'^APP_VERSION\s*=\s*[\'"]([^\'"]+)[\'"]', text, re.MULTILINE)
    if not m:
        sys.exit(f"ERROR: could not parse APP_VERSION from {CONFIG_PY}")
    return m.group(1)


def find_iscc() -> str:
    """Locate ISCC.exe on PATH; exit with install hint if missing."""
    iscc = shutil.which("ISCC") or shutil.which("ISCC.exe")
    if iscc:
        return iscc
    sys.exit(
        f"ERROR: Inno Setup CLI (ISCC.exe) not found on PATH.\n"
        f"  Install from: {INNO_INSTALL_URL}\n"
        f"  {INNO_DEFAULT_PATH_HINT}\n"
        f"  After install, restart your shell so PATH refreshes."
    )


def check_exe_not_running() -> None:
    """Warn if HR-Absensi.exe is running (PyInstaller would fail)."""
    try:
        out = subprocess.check_output(
            ["tasklist", "/FI", "IMAGENAME eq HR-Absensi.exe"],
            text=True, stderr=subprocess.DEVNULL,
        )
    except FileNotFoundError:
        return  # tasklist not available (non-Windows dev env?) — skip
    if "HR-Absensi.exe" in out:
        sys.exit(
            "ERROR: HR-Absensi.exe is currently running. Close it before rebuilding "
            "(PyInstaller can't overwrite a running .exe)."
        )


def check_git_clean(allow_dirty: bool) -> None:
    """Warn (not fail) if there are uncommitted changes."""
    try:
        out = subprocess.check_output(
            ["git", "status", "--porcelain"],
            text=True, cwd=WORKTREE_ROOT, stderr=subprocess.DEVNULL,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return
    if out.strip() and not allow_dirty:
        print(
            "WARNING: working tree has uncommitted changes. The built installer "
            "may not match any committed version. Use --allow-dirty to silence."
        )


def run_pyinstaller() -> None:
    print("=== Step 2/3: PyInstaller ===")
    rc = subprocess.call(
        [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
         "HR-Absensi.spec"],
        cwd=WORKTREE_ROOT,
    )
    if rc != 0:
        sys.exit(f"ERROR: PyInstaller failed with exit code {rc}")
    if not PYI_EXE.exists():
        sys.exit(f"ERROR: PyInstaller succeeded but {PYI_EXE} is missing")


def run_iscc(iscc: str, version: str) -> Path:
    print(f"=== Step 3/3: Inno Setup (version {version}) ===")
    rc = subprocess.call(
        [iscc, f"/DAppVersion={version}", str(ISS_FILE)],
        cwd=WORKTREE_ROOT,
    )
    if rc != 0:
        sys.exit(f"ERROR: ISCC failed with exit code {rc}")
    out_path = ISS_OUTPUT_DIR / f"HR-Absensi-Setup-v{version}.exe"
    if not out_path.exists():
        sys.exit(f"ERROR: ISCC succeeded but {out_path} is missing")
    return out_path


def main(argv: list[str]) -> None:
    parser = argparse.ArgumentParser(description="Build the HR-Absensi installer.")
    parser.add_argument("--skip-pyi", action="store_true",
                        help="Skip PyInstaller; reuse existing dist/HR-Absensi/")
    parser.add_argument("--allow-dirty", action="store_true",
                        help="Suppress the uncommitted-changes warning")
    args = parser.parse_args(argv)

    print("=== Step 1/3: Pre-flight ===")
    iscc = find_iscc()
    print(f"  ISCC: {iscc}")
    check_exe_not_running()
    print("  HR-Absensi.exe: not running")
    check_git_clean(args.allow_dirty)
    version = read_app_version()
    print(f"  APP_VERSION: {version}")

    if args.skip_pyi:
        if not PYI_EXE.exists():
            sys.exit(
                f"ERROR: --skip-pyi was passed but {PYI_EXE} is missing. "
                "Run without --skip-pyi to build it first."
            )
        print("  Skipping PyInstaller (--skip-pyi)")
    else:
        run_pyinstaller()

    out_path = run_iscc(iscc, version)
    size_mb = out_path.stat().st_size / (1024 * 1024)
    print()
    print(f"=== Build complete ===")
    print(f"  Output: {out_path}")
    print(f"  Size:   {size_mb:.1f} MB")
    print()
    print("Next: smoke-test by running the .exe on a clean Windows account,")
    print("or by following installer/README.md section 'Manual smoke checklist'.")


if __name__ == "__main__":
    main(sys.argv[1:])
```

### Step 2: Verify the script imports + parses correctly

Run from worktree root:
```
../../../.venv/Scripts/python.exe -c "import tools.build_installer; print('imports ok')"
```

Expected: `imports ok` printed. Any ImportError or syntax error must be fixed before proceeding.

Then verify the version parser works:
```
../../../.venv/Scripts/python.exe -c "from tools.build_installer import read_app_version; print(read_app_version())"
```

Expected: `14.0.0`.

### Step 3: (Optional) Dry-run pre-flight without building

If ISCC is installed:
```
../../../.venv/Scripts/python.exe -m tools.build_installer --skip-pyi --allow-dirty
```

If `dist/HR-Absensi/` exists from a prior PyInstaller build, this will produce `installer/Output/HR-Absensi-Setup-v14.0.0.exe`.

If ISCC is not installed, expect a clear error pointing at the install URL. **Do not proceed to Task 6 (end-to-end build) without installing Inno Setup first.**

### Step 4: Commit

```bash
git add tools/build_installer.py
git commit -m "$(cat <<'EOF'
feat(installer): add tools/build_installer.py orchestrator

Single-command end-to-end build: pre-flight checks (ISCC on PATH,
HR-Absensi.exe not running, parse APP_VERSION) → PyInstaller →
ISCC.exe → installer/Output/HR-Absensi-Setup-vX.Y.Z.exe.

Flags: --skip-pyi reuses existing dist/, --allow-dirty silences the
uncommitted-changes warning. Fail-fast on any subprocess non-zero exit.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4 — Add `[Code]` Pascal Script migration to .iss

One-time data migration from the legacy deploy folder, triggered only on fresh install when the legacy file exists. ~30 lines of Pascal Script appended to the existing `.iss`.

**Files:**
- Modify: `installer/HR-Absensi.iss` (append `[Code]` section at end)

### Step 1: Append `[Code]` section to `installer/HR-Absensi.iss`

Append at the very end of the file (after `[Run]`):

```ini

[Code]
//
// One-time data migration from the legacy deploy folder.
//
// Context: pre-installer, the user copied the PyInstaller dist/ folder to
// D:\Gawe\Project X\HR App\dist\HR-Absensi\ and ran the .exe in-place.
// Real production data lives at <legacy>\data\hr.db. After the first
// install via this setup.exe, the new install location is empty until the
// user copies that legacy file over.
//
// This [Code] section automates the copy by surfacing an opt-in dialog at
// the end of the install wizard. Triggers only on fresh install (when the
// new data\hr.db does not yet exist). Upgrades skip this branch because
// data\hr.db survives upgrades (it's never tracked by [Files]).
//
// The legacy path is hardcoded for the project owner's machine. On other
// machines the dialog simply does not appear (FileExists returns False).
//
procedure CurStepChanged(CurStep: TSetupStep);
var
  LegacyDb: String;
  NewDb: String;
begin
  if CurStep = ssPostInstall then
  begin
    LegacyDb := 'D:\Gawe\Project X\HR App\dist\HR-Absensi\data\hr.db';
    NewDb := ExpandConstant('{app}\data\hr.db');

    // Fresh install only: skip if the new data file already exists.
    if FileExists(NewDb) then
      Exit;

    // Legacy file must exist to offer migration.
    if not FileExists(LegacyDb) then
      Exit;

    if MsgBox(
      'Found existing data at:' + #13 + #10 +
      LegacyDb + #13 + #10 + #13 + #10 +
      'Copy to the new install location?',
      mbConfirmation, MB_YESNO
    ) = IDYES then
    begin
      if not FileCopy(LegacyDb, NewDb, False) then
      begin
        MsgBox(
          'Copy failed. You can copy the file manually after install.',
          mbError, MB_OK
        );
      end;
    end;
  end;
end;

//
// Post-uninstall reminder: data is preserved on uninstall.
//
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  DataDir: String;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    DataDir := ExpandConstant('{app}\data');
    if DirExists(DataDir) then
    begin
      MsgBox(
        'Your data file (hr.db) has been preserved at:' + #13 + #10 +
        DataDir + #13 + #10 + #13 + #10 +
        'Delete the folder manually if you want a complete reset.',
        mbInformation, MB_OK
      );
    end;
  end;
end;
```

### Step 2: Verify Pascal Script syntax via ISCC dry-build

If Inno Setup is installed:
```
ISCC.exe /DAppVersion=14.0.0 /Q installer/HR-Absensi.iss
```

Expected: succeeds and produces `installer/Output/HR-Absensi-Setup-v14.0.0.exe` (assuming `dist/HR-Absensi/` exists). Any Pascal Script syntax error surfaces here with a line number.

If ISCC is not installed, skip and let Task 6's end-to-end build catch any issue.

### Step 3: Commit

```bash
git add installer/HR-Absensi.iss
git commit -m "$(cat <<'EOF'
feat(installer): add Pascal Script for legacy data migration + uninstall reminder

CurStepChanged on ssPostInstall: if data\hr.db does not yet exist in the
new install AND the legacy hardcoded path D:\Gawe\Project X\HR App\
dist\HR-Absensi\data\hr.db exists, offer to copy it. Fresh-install only.

CurUninstallStepChanged on usPostUninstall: surfaces a reminder that
data\hr.db is preserved at uninstall, with the path for manual cleanup.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5 — Create installer/README.md

Developer-facing docs: how to install Inno Setup on the dev machine, how to build, the manual smoke checklist (copied from spec Section 6), and notes about SmartScreen handling.

**Files:**
- Create: `installer/README.md`

### Step 1: Create `installer/README.md`

```markdown
# HR Absensi Installer

This folder holds the Inno Setup source for the Windows installer.

## Prerequisites (dev machine, one-time)

Install **Inno Setup 6** from https://jrsoftware.org/isdl.php (free).

After install, verify `ISCC.exe` is on PATH:

```
ISCC.exe /?
```

Default install location: `C:\Program Files (x86)\Inno Setup 6\`. If `ISCC.exe`
is not on PATH after install, add that folder to your PATH and restart the shell.

## Build

From the worktree root:

```
../../../.venv/Scripts/python.exe -m tools.build_installer
```

This runs PyInstaller (producing `dist/HR-Absensi/`) and then ISCC against
`installer/HR-Absensi.iss`, producing the final installer at:

```
installer/Output/HR-Absensi-Setup-v<VERSION>.exe
```

Where `<VERSION>` is read from `src/config.py::APP_VERSION`.

Flags:

- `--skip-pyi` — skip PyInstaller, re-package an existing `dist/HR-Absensi/`.
- `--allow-dirty` — suppress the warning about uncommitted git changes.

## What the installer does

- Per-user install at `%LOCALAPPDATA%\Programs\HR-Absensi\` (no admin / UAC).
- Creates Start Menu group "HR Absensi App" with shortcuts to the app and uninstaller.
- Opt-in Desktop shortcut (checkbox in wizard, default ON).
- Registers with Add/Remove Programs ("HR Absensi App" + version).
- Detects existing install via fixed `AppId` GUID — reinstall on top performs upgrade.
- Preserves `data\hr.db` across upgrades (file is created by the app at first launch, never shipped by the installer).
- On **fresh install only**, offers to copy `D:\Gawe\Project X\HR App\dist\HR-Absensi\data\hr.db` (legacy deploy location) to the new install location.
- Uninstall removes everything except `data\hr.db`; surfaces a reminder dialog with the data folder path.

## SmartScreen warning

The installer is unsigned. On each new target laptop, Windows SmartScreen will
warn on first run with "Windows protected your PC". To proceed:

1. Click **More info** (small link on the warning dialog).
2. Click **Run anyway**.

This happens once per `setup.exe` per Windows user account. Subsequent runs of
the same installer file are not blocked. A different version's installer
triggers the warning again — expected.

## Manual smoke checklist (run after each fresh build)

### A. Fresh install on a clean Windows account
1. Double-click `HR-Absensi-Setup-v14.0.0.exe`. SmartScreen → More info → Run anyway.
2. Accept default install path, both shortcut checkboxes ON, Next, Install.
3. Verify `%LOCALAPPDATA%\Programs\HR-Absensi\` contains `HR-Absensi.exe`, `_internal\`, empty `data\`.
4. Verify Start Menu → "HR Absensi App" group → click → splash → main window.
5. Verify Desktop shortcut → click → app launches.
6. Open Settings → field "Coaching Threshold (mnt/hari)" shows `15` (fresh DB).
7. Verify Add/Remove Programs lists "HR Absensi App 14.0.0".

### B. Legacy data migration (run on the main laptop with prod data)
1. Confirm `D:\Gawe\Project X\HR App\dist\HR-Absensi\data\hr.db` exists.
2. Run installer. Wizard proceeds. After "Install" step, post-install dialog appears: "Found existing data at … Copy?" → Yes.
3. Launch → Dashboard shows real production data.
4. Settings shows "Coaching Threshold (mnt/hari): 15" (matches pre-install value).

### C. Upgrade test (simulate v14.0.0 → v14.0.1)
1. With v14.0.0 installed + data present, bump `APP_VERSION` to `"14.0.1"`, rebuild.
2. Run `HR-Absensi-Setup-v14.0.1.exe` over the v14.0.0 install.
3. Wizard: "Already installed, replace?" → Yes. No post-install migration dialog (existing data not re-migrated).
4. Launch → Settings still shows the existing value (data preserved).
5. Add/Remove Programs version updates to `14.0.1`.

### D. Uninstall test
1. Add/Remove Programs → Uninstall HR Absensi → confirm.
2. `%LOCALAPPDATA%\Programs\HR-Absensi\` → all files removed EXCEPT `data\hr.db` (and its parent dir).
3. Start Menu group + Desktop shortcut removed.
4. Add/Remove Programs entry gone.
5. Post-uninstall message dialog appears with the preserved `data\` folder path.

## Versioning

`src/config.py::APP_VERSION` is the single source of truth.

- Major (14 → 15): new vN milestone
- Minor (14.0 → 14.1): bugfix or small enhancement on the same milestone
- Patch (14.0.0 → 14.0.1): hotfix

The `.iss` file does NOT contain a version literal — version is injected at
build time by `tools/build_installer.py` via `ISCC.exe /DAppVersion=<value>`.

## Caveats

- **Hardcoded legacy migration path.** `D:\Gawe\Project X\HR App\dist\HR-Absensi\data\hr.db` is literal in the Pascal Script. Personal-use scope only. On other machines where the legacy path doesn't match, the migration dialog never fires — user copies manually after install.
- **No code signing.** Acceptable for personal use; revisit if distribution scope grows beyond a handful of laptops.
- **AppId GUID must stay stable.** Inno uses it to detect upgrades. Never regenerate.
```

### Step 2: Commit

```bash
git add installer/README.md
git commit -m "$(cat <<'EOF'
docs(installer): add developer README

Covers Inno Setup install prereq, build command, what the installer does,
SmartScreen handling, manual smoke checklist (A-D scenarios), versioning
convention, and known caveats (hardcoded legacy migration path, no code
signing, stable AppId GUID).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6 — End-to-end build verification + final report

Run the full build pipeline and verify the output. No commit — this task is verification only. Also runs the full pytest suite to confirm no regression from the `APP_VERSION` bump.

**Files:** none changed; this task is verification only.

### Step 1: Confirm Inno Setup is installed on the dev machine

```
ISCC.exe /? 2>&1 | head -5
```

Expected: prints Inno Setup CLI help text (version banner). If "ISCC not found" or similar, install Inno Setup from https://jrsoftware.org/isdl.php first, then retry. **Do not proceed without ISCC available.**

### Step 2: Confirm HR-Absensi.exe is not running

```
tasklist | grep -i HR-Absensi || echo "not running"
```

Expected: `not running` (or empty grep). If running, close any open instance first.

### Step 3: Run the full pytest suite

```
../../../.venv/Scripts/python.exe -m pytest -q
```

Expected: `241 passed`. The only application code change is `APP_VERSION` constant — no test should fail. If pytest fails, fix before continuing.

### Step 4: Run the end-to-end build

```
../../../.venv/Scripts/python.exe -m tools.build_installer
```

Expected output (truncated):
```
=== Step 1/3: Pre-flight ===
  ISCC: C:\Program Files (x86)\Inno Setup 6\ISCC.exe
  HR-Absensi.exe: not running
  APP_VERSION: 14.0.0
=== Step 2/3: PyInstaller ===
[ ... PyInstaller log ... ]
=== Step 3/3: Inno Setup (version 14.0.0) ===
[ ... ISCC log ... ]
=== Build complete ===
  Output: <worktree>/installer/Output/HR-Absensi-Setup-v14.0.0.exe
  Size:   12.X MB
```

Build duration: ~2-3 minutes (mostly PyInstaller).

### Step 5: Verify output artifact

```
ls -la installer/Output/HR-Absensi-Setup-v14.0.0.exe
```

Expected: file exists, size > 5 MB. Typical Inno-compressed PyInstaller bundle is 10-15 MB.

### Step 6: Confirm git status

```
git status --short
```

Expected: clean working tree (only `installer/Output/HR-Absensi-Setup-v14.0.0.exe` may show as ignored per `.gitignore`).

### Step 7: Report final state

DO NOT make any commits in this task. Verification only.

Report back to the orchestrator with:

- Pytest result (count, failures if any).
- Build duration (rough estimate from log timestamps if visible).
- Output file absolute path + size.
- Commit chain since `524fcf7` (the spec commit; should be 5 implementation commits).
- Manual smoke checklist pointer: `installer/README.md` section "Manual smoke checklist".

### Step 8: Hand off to user for manual smoke

The user (project owner) runs scenarios A-D from `installer/README.md` by hand:
- A: Fresh install on a clean Windows account
- B: Legacy data migration on the main laptop
- C: Upgrade test (bump APP_VERSION, rebuild, install over)
- D: Uninstall test

These cannot be automated in this environment — they require GUI interaction with the Windows shell, double-clicking the setup.exe, and observing the wizard behavior. The orchestrator's job ends after Task 6 succeeds; the user handles A-D manually.

---

## Self-Review

**Spec coverage:**
- §1 (tooling + repo structure): Task 2 creates `.iss`, Task 3 creates `build_installer.py`, Task 5 creates `README.md`, Task 1 modifies `src/config.py` + `.gitignore`. ✓
- §2 (install behavior, file layout, Add/Remove Programs entry): Task 2 `.iss` covers all of `[Setup]`, `[Files]`, `[Dirs]`, `[Icons]`, `[Run]`, `[Tasks]`. ✓
- §3 (upgrade & uninstall): same `AppId` from Task 2 enables upgrade detection; preserve `data/hr.db` is automatic because `[Files]` doesn't ship it; Task 4 adds the post-uninstall reminder. ✓
- §4 (build workflow): Task 3 implements the orchestrator end-to-end. ✓
- §5 (versioning + migration): Task 1 bumps APP_VERSION; Task 4 adds the Pascal Script migration. ✓
- §6 (testing): Task 6 verification + the smoke checklist is copied into Task 5's README. ✓

**Placeholder scan:** No "TBD" / "TODO" / "fill in details". Every code block is concrete. The GUID placeholder `{REPLACE-WITH-GENERATED-GUID}` in Task 2 is explicit — Step 1 of Task 2 generates it and Step 2 substitutes it. ✓

**Type consistency:** `build_installer.py` defines `read_app_version()`, `find_iscc()`, `check_exe_not_running()`, `check_git_clean(allow_dirty)`, `run_pyinstaller()`, `run_iscc(iscc, version)`, `main(argv)`. All referenced from `main`. Constants (`WORKTREE_ROOT`, `CONFIG_PY`, `ISS_FILE`, `ISS_OUTPUT_DIR`, `PYI_DIST_DIR`, `PYI_EXE`, `INNO_INSTALL_URL`, `INNO_DEFAULT_PATH_HINT`) defined once at module top. ✓

**Scope:** Single implementation plan, ~6 tasks, no decomposition needed. Build/packaging only — zero application logic touched. ✓

---

## Execution

Per `memory/execution_preference.md` the user always picks subagent-driven. After this plan is committed, the parent should immediately invoke `superpowers:subagent-driven-development` without asking the "two options" question.

When dispatching subagents, the orchestrator must follow the user's progress-reporting preference (`memory/progress_communication.md`):

- Announce total task count at start: "6 tasks total."
- Before each task: "Task N of 6 — <name> (M% complete)" where M is the **post-completion** percentage of the prior task. E.g., before Task 3 dispatches: "Task 3 of 6 — build_installer.py orchestrator (33% complete)" (because Tasks 1+2 = 2/6 = 33%).
- After all 6 tasks land: "100% complete. Final review next."
