# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['src\\main.py'],
    pathex=['src'],
    binaries=[],
    datas=[
        ('src/reports/templates/dashboard.html.j2', 'src/reports/templates'),
        ('assets/templates/laporan_bulanan_template.xlsx', 'assets/templates'),
        # Brand assets (Josaphat Tech Solution) — readable at runtime via src.config.BRAND_*
        ('assets/brand/icon-04E.svg', 'assets/brand'),
        ('assets/brand/lockup-04E-dark.svg', 'assets/brand'),
        ('assets/brand/lockup-04E-light.svg', 'assets/brand'),
        ('assets/brand/animation-02-typing-04E.svg', 'assets/brand'),
        ('assets/brand/animation-02-typing-04E.gif', 'assets/brand'),
        ('assets/brand/icon-04E.ico', 'assets/brand'),
    ],
    hiddenimports=['customtkinter', 'PIL'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='HR-Absensi',
    icon='assets/brand/icon-04E.ico',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='HR-Absensi',
)
