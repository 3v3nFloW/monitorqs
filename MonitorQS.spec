# -*- mode: python ; coding: utf-8 -*-
import os
from pathlib import Path

a = Analysis(
    ['main.py'],
    pathex=[str(Path('.').resolve())],
    binaries=[],
    # TG18-Testmuster werden nicht mitgeliefert, sondern beim ersten Start geladen (app/testbilder.py)
    datas=[],
    hiddenimports=['pydicom', 'pydicom.encoders', 'PIL', 'reportlab', 'certifi'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='MonitorQS',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='MonitorQS',
)

app = BUNDLE(
    coll,
    name='MonitorQS.app',
    icon='MonitorQS.icns',
    bundle_identifier='vet.kappa1.monitorqs',
    info_plist={
        'NSPrincipalClass': 'NSApplication',
        'NSHighResolutionCapable': True,
        'CFBundleShortVersionString': '3.2.0',
        'CFBundleVersion': '3.2.0',
        'NSHumanReadableCopyright': '© 2026 Kappa1-VRS GmbH · GPL-3.0',
    },
)
