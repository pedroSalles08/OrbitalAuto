# -*- mode: python ; coding: utf-8 -*-
# ── OrbitalAuto · PyInstaller Spec ────────────────────────────────
"""
Build command:
    pyinstaller OrbitalAuto.spec

Produces a single-folder dist/OrbitalAuto/ with OrbitalAuto.exe inside.
For single-file .exe:  set onefile=True below (slower startup).
"""

import os

block_cipher = None

# ── Config ────────────────────────────────────────────────────────

onefile = True  # True = single .exe, False = folder

# Paths
backend_dir = os.path.abspath(".")
frontend_out = os.path.join(backend_dir, "out")

# ── Analysis ──────────────────────────────────────────────────────

a = Analysis(
    ["launcher.py"],
    pathex=[backend_dir],
    binaries=[],
    datas=[
        # Frontend static build → bundled as "out/" inside the exe
        (frontend_out, "out"),
    ],
    hiddenimports=[
        # FastAPI / Starlette / Uvicorn
        "uvicorn.logging",
        "uvicorn.loops",
        "uvicorn.loops.auto",
        "uvicorn.protocols",
        "uvicorn.protocols.http",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.websockets",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.lifespan",
        "uvicorn.lifespan.on",
        "uvicorn.lifespan.off",
        # App modules
        "app",
        "config",
        "models",
        "orbital_client",
        "session_manager",
        # Pydantic
        "pydantic",
        "pydantic.deprecated.decorator",
        # Email validator (pydantic dep)
        "email_validator",
        # Dotenv
        "dotenv",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Remove unnecessary large packages if present
        "tkinter",
        "matplotlib",
        "numpy",
        "pandas",
        "scipy",
        "PIL",
        "cv2",
    ],
    noarchive=False,
    optimize=0,
    cipher=block_cipher,
)

# ── PYZ ───────────────────────────────────────────────────────────

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# ── EXE ───────────────────────────────────────────────────────────

if onefile:
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.datas,
        [],
        name="OrbitalAuto",
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        upx_exclude=[],
        runtime_tmpdir=None,
        console=True,  # Console visible so user sees status
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
        icon=None,  # Add icon path here if desired: icon="icon.ico"
    )
else:
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name="OrbitalAuto",
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        console=True,
        icon=None,
    )
    coll = COLLECT(
        exe,
        a.binaries,
        a.datas,
        strip=False,
        upx=True,
        upx_exclude=[],
        name="OrbitalAuto",
    )
