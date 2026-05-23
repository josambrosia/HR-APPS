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
