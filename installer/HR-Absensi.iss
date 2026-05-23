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
