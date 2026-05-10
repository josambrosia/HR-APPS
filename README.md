# HR Absensi App

Single-user Windows desktop app for HR attendance workflow:
- Detect issues from weekly fingerprint .xls
- Track resolution per employee
- Fill Alasan Ijin column in monthly report .xlsx
- Insights dashboard (top 5 terlambat, coaching flag, karyawan teladan)
- Print to PDF via HTML

## Run from source

```powershell
py -3 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
python -m src.main
```

## Build .exe

```powershell
pyinstaller HR-Absensi.spec --clean --noconfirm
```

Output: `dist/HR-Absensi/`. Copy/zip the folder for distribution.

## Test

```powershell
pytest
```

## Architecture

See `docs/superpowers/specs/2026-05-11-hr-absensi-app-design.md`.
