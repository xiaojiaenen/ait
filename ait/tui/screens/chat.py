"""向后兼容 — 旧的 ChatScreen 别名，已迁移到 MainScreen + ChatPanel"""
from __future__ import annotations

from pathlib import Path

from ait.tui.screens.main import MainScreen


def ChatScreen(config_dir: Path):  # noqa: N802
    """废弃：请使用 MainScreen + ChatPanel"""
    import warnings
    warnings.warn("ChatScreen is deprecated, use MainScreen + ChatPanel", DeprecationWarning)
    return MainScreen(config_dir=config_dir)
