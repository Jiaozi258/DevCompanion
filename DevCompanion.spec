# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['main_gui.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('startup.gif', '.'),   # 启动动画
        ('analyzer.exe', '.')   # C++ 引擎
        ('app.ico', '.')
    ],
    hiddenimports=[
        'chromadb',
        'chromadb.telemetry.product.posthog',
        'chromadb.api.segment',
        'chromadb.api.rust',
        'chromadb.api.fastapi',
        'sqlite3',
        'onnxruntime',
        'pydantic',
        'requests',
        'dotenv',
        'tokenizers',   
        'tqdm'      
    ],
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
    a.binaries,
    a.datas,
    [],
    name='DevCompanion',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True, # 设置为 False，消除黑框
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['app.ico'], # 如果你有图标，取消这行注释
)