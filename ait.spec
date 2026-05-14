# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for ait — AI 智能运维终端 (one-file 模式)"""
from pathlib import Path as _Path

_root = _Path(SPECPATH)

_datas = [
    (str(_root / "ait" / "ait.tcss"), "ait"),
    (str(_root / "ait" / "macros" / "example_uptime.yaml"), "ait/macros"),
]

# 收集包元数据（可编辑安装时在项目根目录的 egg-info）
_egg_info = _root / "ait.egg-info"
if _egg_info.is_dir():
    _datas.append((str(_egg_info), "ait.egg-info"))

a = Analysis(
    [str(_root / "ait" / "cli.py")],
    pathex=[str(_root)],
    binaries=[],
    datas=_datas,
    hiddenimports=[
        "textual",
        "textual.widgets",
        "textual.containers",
        "textual.screen",
        "textual.app",
        "textual.binding",
        "asyncssh",
        "wuwei",
        "wuwei.runtime",
        "wuwei.runtime.hitl",
        "wuwei.runtime.hooks",
        "wuwei.llm",
        "wuwei.tools",
        "wuwei.skill",
        "wuwei.memory",
        "pydantic",
        "pydantic_core",
        "typer",
        "yaml",
        "markitdown",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "matplotlib",
        "numpy",
        "pandas",
        "PIL",
        "cv2",
        "onnxruntime",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    a.zipfiles,
    name="ait",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
