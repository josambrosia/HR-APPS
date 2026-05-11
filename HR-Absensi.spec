# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['src\\main.py'],
    pathex=['src'],
    binaries=[],
    datas=[
        ('src/reports/templates/dashboard.html.j2', 'src/reports/templates'),
        ('src/reports/templates/dashboard_v1_editorial.html.j2', 'src/reports/templates'),
        ('src/reports/templates/dashboard_v2_dark_glass.html.j2', 'src/reports/templates'),
        ('src/reports/templates/dashboard_v3_infographic.html.j2', 'src/reports/templates'),
        ('src/reports/templates/dashboard_v4_corporate.html.j2', 'src/reports/templates'),
        ('templates/laporan_bulanan_template.xlsx', 'templates'),
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
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
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
    upx=True,
    upx_exclude=[],
    name='HR-Absensi',
)
