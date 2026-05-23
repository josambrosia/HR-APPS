; HR Absensi App — Inno Setup script
; Build:   ISCC.exe installer/HR-Absensi.iss /DAppVersion=14.0.0
; Locally: python -m tools.build_installer

#define AppName        "HR Absensi App"
#define AppPublisher   "Josaphat Tech Solution"
#define AppExeName     "HR-Absensi.exe"
#define AppId          "{18FBCFB9-E4BA-41E0-9985-BB96E07FC355}"
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
