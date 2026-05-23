# Windows Installer (Inno Setup) — Design

**Date:** 2026-05-23
**Status:** Design approved, awaiting implementation plan
**Scope:** Build / packaging only — distribute the existing PyInstaller bundle as a proper installable Windows app for the user's personal laptops (1–3 machines)

## Problem

The current "deploy" workflow is: rebuild the PyInstaller bundle into `dist/HR-Absensi/` and manually rotate `.exe` + `_internal/` via the 2-level `.bak` / `.bak.old` pattern (memory: `workflow_rules.md`). To install on another Windows laptop, the user would have to copy the whole folder via USB / Drive and create shortcuts by hand. No Start Menu entry, no Add/Remove Programs presence, no clean uninstall, no upgrade path that preserves `data/hr.db`.

The user wants a "real installer" — a single `setup.exe` that any Windows machine can run without needing Python, pip, or any other dependency, and that delivers a proper install/upgrade/uninstall experience.

PyInstaller already solves "no dependencies on target machine" (the bundle ships Python + libs in `_internal/`). The missing layer is the **install/distribution UX**.

## Goals

- Single deliverable: `HR-Absensi-Setup-v{VERSION}.exe` (~12–15 MB), self-contained, installable on Windows 10/11 without any other prerequisite.
- Per-user install at `%LOCALAPPDATA%\Programs\HR-Absensi\` — no UAC prompt, no admin password.
- Start Menu + (opt-in) Desktop shortcut auto-created.
- Add/Remove Programs entry → clean uninstall, version visible.
- Upgrade-aware: reinstalling a new version over an existing one **preserves `data/hr.db`** (and therefore all user settings + attendance data).
- One-time migration from the existing `D:\Gawe\Project X\HR App\dist\HR-Absensi\data\hr.db` to the new install location, via an opt-in dialog at the end of the wizard.
- Build flow: single command from source to deliverable.

## Non-goals

- Code signing (audience is personal-use 1–3 laptops; SmartScreen "Run anyway" is acceptable). Revisit if distribution scope changes.
- Auto-update infrastructure (manual: keep the new `setup.exe` somewhere, run it when a new version drops).
- MSI / WiX / Store packaging (overkill for this audience).
- System-wide (`Program Files`) install. Per-user only.
- Touching the existing 2-level rotation pattern for the dev workflow inside the worktree — that stays valid for rebuilding `.exe` and testing locally before producing an installer.

## Design

### 1. Tooling & repo structure

**Tool:** [Inno Setup 6](https://jrsoftware.org/isinfo.php) — free, mature, widely used for Python+PyInstaller apps. Installed once on the build machine (laptop dev). Provides `ISCC.exe` CLI for batch builds.

**New files:**

```
installer/
  HR-Absensi.iss         # Inno Setup source script — single source of truth for installer config
  README.md              # Short notes: how to install Inno Setup on dev machine, how to build, how to test
tools/
  build_installer.py     # Orchestrator: runs PyInstaller → runs ISCC → emits setup.exe
```

**Modified files:**

- `src/config.py`: bump `APP_VERSION = "0.0.1"` → `"14.0.0"` (aligned with the vN milestone scheme). This constant becomes the single source of truth for installer version; `build_installer.py` reads it and passes to `ISCC.exe` via `/DAppVersion=`.
- `.gitignore`: add `installer/Output/` so build artifacts (`HR-Absensi-Setup-vX.Y.Z.exe`) don't enter git.
- `memory/workflow_rules.md` (user memory): update the deploy-rotation rule — production deploys now use the installer; the 2-level rotation remains only for in-worktree dev iteration.

**Output build artifact:**

- `installer/Output/HR-Absensi-Setup-v{APP_VERSION}.exe` — e.g. `HR-Absensi-Setup-v14.0.0.exe`.

### 2. Install behavior

**First-time install flow:**

1. User double-clicks `HR-Absensi-Setup-v14.0.0.exe`.
2. SmartScreen warning (unsigned). User clicks "More info" → "Run anyway". *(One-time per laptop per file.)*
3. Wizard: Welcome → Install Location (defaults to `%LOCALAPPDATA%\Programs\HR-Absensi\`, overridable) → Components (Start Menu always, Desktop shortcut opt-in checkbox, default ON) → Ready → Install → (optional post-install data migration dialog, see Section 5) → Finish (with opt-in "Launch HR Absensi" checkbox).

**File layout after install:**

```
%LOCALAPPDATA%\Programs\HR-Absensi\
├── HR-Absensi.exe                  # main executable (PyInstaller bundled)
├── _internal\                      # Python interpreter, libs, templates, brand assets
│   ├── base_library.zip
│   ├── customtkinter/
│   ├── PIL/
│   ├── src/reports/templates/dashboard.html.j2
│   ├── assets/brand/...
│   └── ...
├── data\                           # writable user data dir (Inno creates with users-modify permission)
│   └── hr.db                       # NOT shipped by installer; created by init_db() at first launch
├── unins000.exe                    # Inno-auto-generated uninstaller
└── unins000.dat
```

**Add/Remove Programs entry:**

- Name: "HR Absensi App"
- Version: "14.0.0" (from `APP_VERSION`)
- Publisher: "Josaphat Tech Solution" (from `APP_BRAND_NAME` in `src/config.py`)
- Estimated install size: ~50 MB
- Uninstall button → calls `unins000.exe`

**Registry footprint:** minimal — only the Add/Remove Programs entry plus uninstall metadata. No other registry keys touched.

**Start Menu structure:**

```
Start Menu\Programs\HR Absensi App\
├── HR Absensi.lnk         → HR-Absensi.exe
└── Uninstall HR Absensi.lnk → unins000.exe
```

### 3. Upgrade & uninstall behavior

**Upgrade scenario** (user already has v14.0.0, installs `HR-Absensi-Setup-v15.0.0.exe`):

1. Inno detects existing install via fixed `AppId` GUID (kept identical across versions in the `.iss` script).
2. Wizard message: "HR Absensi App is already installed. Setup will replace the existing version. Continue?"
3. User confirms → all installed files replaced **EXCEPT** anything not tracked by the previous install — `data/hr.db` is never tracked by the installer (it's created at runtime), so it's automatically preserved. The `[Files]` section ships nothing into `data/`.
4. Start Menu + Desktop shortcuts auto-update to point at the new `.exe`.
5. Add/Remove Programs entry updates version string.
6. First launch of v15 runs `init_db(DB_PATH)` → idempotent `_migrate()` applies any new schema/settings migrations. Existing `coaching_threshold_per_day` (set in v14) survives.

**User actions NOT required on upgrade:**

- No manual uninstall first.
- No backup of `hr.db`.
- No re-creating shortcuts.
- No re-entering settings.

**Uninstall scenario:**

1. User clicks "Uninstall HR Absensi" (from Start Menu group or Add/Remove Programs).
2. Confirmation: "Are you sure you want to completely remove HR Absensi App?"
3. User confirms → uninstaller deletes everything it tracked: `HR-Absensi.exe`, `_internal/`, Start Menu shortcuts, Desktop shortcut, registry entry.
4. **`data/hr.db` is preserved** — it was created at runtime, not tracked by the installer.
5. Final message dialog (custom, via `[Code]` PostUninstall step): "Your data file (hr.db) has been preserved at `%LOCALAPPDATA%\Programs\HR-Absensi\data\`. Delete the folder manually for a complete reset."

**Rollback v15 → v14:**

- Re-run `HR-Absensi-Setup-v14.0.0.exe` (kept as backup). Inno detects v15, replaces with v14.
- Data persists. Any v15-written keys in `hr.db` that v14 doesn't recognize are simply ignored at read time (settings are key-value strings; unknown keys are not enumerated).

### 4. Build workflow

**Single command for a complete build:**

```
../../../.venv/Scripts/python.exe -m tools.build_installer
```

**`tools/build_installer.py`** — orchestrator, ~80 lines:

```python
"""Build the HR-Absensi installer.

Steps:
  1. Verify the dev machine has Inno Setup's ISCC.exe on PATH.
  2. Verify HR-Absensi.exe is not currently running (PyInstaller would fail).
  3. Build the PyInstaller bundle to dist/HR-Absensi/.
  4. Run ISCC.exe against installer/HR-Absensi.iss with /DAppVersion=<value>
     read from src/config.py, producing installer/Output/HR-Absensi-Setup-vX.Y.Z.exe.

Usage:
  python -m tools.build_installer            # full build
  python -m tools.build_installer --skip-pyi # skip PyInstaller (re-package existing dist/)
"""
```

Pre-flight checks:

- `shutil.which("ISCC")` → if absent, print clear error pointing at install URL + default Inno install path (`C:\Program Files (x86)\Inno Setup 6\`).
- `tasklist | grep HR-Absensi` → if running, print "Close HR-Absensi.exe before rebuilding".
- `git status` → warn (don't fail) if there are uncommitted changes. Override: `--allow-dirty`.

Steps fail fast on non-zero exit. Final output prints the absolute path to the produced setup.exe plus its size.

**`installer/HR-Absensi.iss`** — Inno Setup source, ~60 lines:

```ini
; HR Absensi App — Inno Setup script
; Build:   ISCC.exe installer/HR-Absensi.iss /DAppVersion=14.0.0
; Locally: python -m tools.build_installer

#define AppName        "HR Absensi App"
#define AppPublisher   "Josaphat Tech Solution"
#define AppExeName     "HR-Absensi.exe"
#define AppId          "{{REPLACE-WITH-GENERATED-GUID}}"
; AppVersion injected via /D from build_installer.py

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

[Tasks]
Name: "desktopicon"; Description: "Create desktop shortcut"; \
    GroupDescription: "Additional shortcuts:"

[Files]
Source: "..\dist\HR-Absensi\HR-Absensi.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\dist\HR-Absensi\_internal\*"; DestDir: "{app}\_internal"; \
    Flags: ignoreversion recursesubdirs createallsubdirs
; data/hr.db deliberately NOT shipped. First launch's init_db() creates it.

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

[Code]
// Pascal Script section — handles one-time data migration from legacy deploy.
// See Section 5 for the procedure body.
```

**Key file notes:**

- `AppId` is a fixed GUID. **Generation step (one-time, during implementation):** run `python -c "import uuid; print('{' + str(uuid.uuid4()).upper() + '}')"`, paste the result (including curly braces) into the `.iss` literal, then commit it. Same GUID stays across all future versions so Inno recognizes the same app for upgrade detection. Not a secret — committed to git is fine.
- `PrivilegesRequired=lowest` → no admin / UAC.
- `[Dirs] Permissions: users-modify` ensures the `data\` dir is writable by the current user.
- `[Files]` ships only the app bundle, never `hr.db`. Fresh installs get an empty data dir; the app populates `hr.db` on first launch via `init_db()`.

### 5. Versioning & one-time migration from legacy deploy

**Versioning scheme:**

`src/config.py::APP_VERSION` is bumped from `"0.0.1"` to `"14.0.0"` (aligned with current vN milestone). Going forward:

- Major (14 → 15): new vN milestone — significant feature set
- Minor (14.0 → 14.1): bugfix or small enhancement on the same milestone
- Patch (14.0.0 → 14.0.1): hotfix

Single source of truth: `src/config.py`. `tools/build_installer.py` reads it and passes to ISCC via `/DAppVersion=`. No version literal lives in `installer/HR-Absensi.iss`.

**Deliverable name:** `installer/Output/HR-Absensi-Setup-v14.0.0.exe`.

**Migration from existing legacy deploy** (one-time, only on first install on the user's current main laptop):

The user currently has production data at `D:\Gawe\Project X\HR App\dist\HR-Absensi\data\hr.db` (post-v14 deploy). After installing `HR-Absensi-Setup-v14.0.0.exe`, the new install would have an empty `data\hr.db` at `%LOCALAPPDATA%\Programs\HR-Absensi\data\` — losing visibility of the real data.

**Solution: `[Code]` Pascal Script in the `.iss` (~20–30 lines)** that runs after `[Files]` completes:

```pascal
procedure CurStepChanged(CurStep: TSetupStep);
var
  LegacyDb, NewDb: String;
  IsFreshInstall: Boolean;
begin
  if CurStep = ssPostInstall then
  begin
    LegacyDb := 'D:\Gawe\Project X\HR App\dist\HR-Absensi\data\hr.db';
    NewDb := ExpandConstant('{app}\data\hr.db');
    IsFreshInstall := not FileExists(NewDb);

    if IsFreshInstall and FileExists(LegacyDb) then
    begin
      if MsgBox(
        'Found existing data at:' + #13 + #10 + LegacyDb + #13 + #10 +
        'Copy to the new install location?',
        mbConfirmation, MB_YESNO
      ) = IDYES then
      begin
        if not FileCopy(LegacyDb, NewDb, False) then
          MsgBox('Copy failed. You can copy it manually later.', mbError, MB_OK);
      end;
    end;
  end;
end;
```

Properties of this migration:

- Triggers only when `data/hr.db` does NOT yet exist in the new install — i.e. **fresh install only**. Upgrade installs (which carry forward existing `data/hr.db` automatically per Section 3) skip this branch.
- Checks for the legacy file. If absent (e.g., installing on a different laptop that never had the legacy deploy), the dialog never shows — installer proceeds to fresh install with empty data dir.
- Read-only on the source — the legacy `hr.db` is left in place. User can delete the legacy folder manually later, or keep it as a backup.
- Failure is non-fatal — copy failure surfaces a message, user can copy manually.
- **Hardcoded legacy path caveat:** the path `D:\Gawe\Project X\HR App\dist\HR-Absensi\data\hr.db` is literal in the Pascal Script. This is intentional for this user's specific situation. If the legacy deploy is at a different drive/path (e.g., another laptop where the project was cloned somewhere else), the dialog won't fire and the user simply copies manually. Acceptable for personal-use scope; documented as a known limitation in `installer/README.md`.

**Post-migration cleanup (user's responsibility, not automated):**

- `D:\Gawe\Project X\HR App\dist\HR-Absensi\` can be deleted manually after the user confirms the new install works.
- `.bak` and `.bak.old` files in the legacy folder are also redundant — Inno's installer-based versioning replaces the 2-level rotation pattern for production. Keep the legacy folder around as a safety backup until smoke passes.

### 6. Testing strategy

No new Python unit tests — this work is build/packaging only. Existing 241-test suite must remain green throughout.

**Automated checks** built into `tools/build_installer.py`:

- Step 1: `shutil.which("ISCC")` — exits with clear error if Inno Setup CLI is not on PATH.
- Step 1 (optional pre-build): `ISCC.exe /? > NUL` or syntax-only validation of the `.iss` file. Fast fail on script errors before running the full build.
- Step 2: PyInstaller subprocess exits 0.
- Step 3: ISCC subprocess exits 0.
- Final: assert output file `installer/Output/HR-Absensi-Setup-v{APP_VERSION}.exe` exists and is > 5 MB.

**Application code regression test:** full pytest suite must remain at 241 passing. The only application code change is `APP_VERSION` constant bump — verify no test depends on the literal `"0.0.1"` value (grep for `APP_VERSION` in tests/; expected: zero matches).

**Manual smoke checklist** (user runs by hand after implementation lands):

**A. Fresh install on a clean Windows account**
1. Double-click `HR-Absensi-Setup-v14.0.0.exe`. SmartScreen → More info → Run anyway.
2. Accept default install path, both shortcut checkboxes ON, next, install.
3. Verify `%LOCALAPPDATA%\Programs\HR-Absensi\` contains `HR-Absensi.exe`, `_internal\`, empty `data\`.
4. Verify Start Menu → "HR Absensi App" group → click → splash → main window.
5. Verify Desktop shortcut → click → app launches.
6. Open Settings → field `Coaching Threshold (mnt/hari): 15` (fresh DB seeded).
7. Verify Add/Remove Programs lists "HR Absensi App 14.0.0".

**B. Data migration from legacy deploy** (run on the main laptop with real prod data)
1. Confirm `D:\Gawe\Project X\HR App\dist\HR-Absensi\data\hr.db` exists.
2. Run installer. Wizard proceeds, post-install dialog appears: "Found existing data at … Copy?" → Yes.
3. Launch → Dashboard shows real production data.
4. Settings shows `Coaching Threshold (mnt/hari): 15` (matches pre-install value — file copied verbatim, no re-migration needed since `coaching_threshold_per_day` already exists).

**C. Upgrade test** (simulate v14.0.0 → v14.0.1 by building a stub)
1. With v14.0.0 installed + data present, bump `APP_VERSION` to `"14.0.1"`, rebuild via `python -m tools.build_installer`.
2. Run `HR-Absensi-Setup-v14.0.1.exe` over the v14.0.0 install.
3. Wizard: "Already installed, replace?" → Yes. No post-install migration dialog (existing data not re-migrated).
4. Launch → Settings still shows the existing value (data preserved).
5. Add/Remove Programs version updates to `14.0.1`.

**D. Uninstall test**
1. Add/Remove Programs → Uninstall HR Absensi → confirm.
2. `%LOCALAPPDATA%\Programs\HR-Absensi\` → all files removed EXCEPT `data\hr.db` (and its parent dir).
3. Start Menu group + Desktop shortcut removed.
4. Add/Remove Programs entry gone.
5. Custom post-uninstall message dialog appeared, pointing at the preserved `data\` folder.

**E. SmartScreen handling**
- First time per laptop per file: SmartScreen blocks. User clicks "More info" → "Run anyway".
- Subsequent runs of the same file: no SmartScreen. Different version of the file (different setup.exe) triggers it again — expected.
- Document the click-through path in `installer/README.md`.

## Files touched (summary)

| File | Action | Notes |
|---|---|---|
| `installer/HR-Absensi.iss` | Create | Inno Setup source, ~60 lines + ~30 lines Pascal Script for migration |
| `installer/README.md` | Create | Dev setup: install Inno Setup, build commands, smoke checklist pointer |
| `tools/build_installer.py` | Create | Orchestrator, ~80 lines |
| `src/config.py` | Modify | `APP_VERSION = "0.0.1"` → `"14.0.0"` |
| `.gitignore` | Modify | Add `installer/Output/` |
| `memory/workflow_rules.md` | Modify | Note that production deploy is now via installer; rotation pattern is dev-only |

No application source code changes other than the `APP_VERSION` literal. No database schema changes. No new Python dependencies.

## Open questions

None — design fully resolved through brainstorming.
