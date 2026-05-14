"""ait Textual App 主入口"""
from __future__ import annotations

from pathlib import Path

from textual.app import App
from textual.binding import Binding


class AitApp(App):
    """ait AI 智能运维终端"""

    CSS_PATH = "ait.tcss"
    TITLE = "ait"
    SUB_TITLE = "AI 智能运维终端"

    BINDINGS = [
        Binding("ctrl+c", "quit", "退出", show=False),
    ]

    def __init__(self, config_dir: Path):
        super().__init__()
        self.config_dir = config_dir

    def on_mount(self) -> None:
        from ait.tui.screens.main import MainScreen
        self.push_screen(MainScreen(config_dir=self.config_dir))


def launch(config_dir: Path) -> None:
    """启动 ait TUI"""
    app = AitApp(config_dir=config_dir)
    app.run()
