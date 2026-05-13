"""ait Textual App 主入口"""

from __future__ import annotations

from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Footer, Header

from ait.tui.screens.chat import ChatScreen


class AitApp(App):
    """ait AI 智能运维终端"""

    CSS_PATH = "ait.tcss"
    TITLE = "ait"
    SUB_TITLE = "AI 智能运维终端"

    BINDINGS = [
        Binding("ctrl+c", "quit", "退出", show=False),
        Binding("ctrl+l", "clear", "清屏"),
    ]

    def __init__(self, config_dir: Path):
        super().__init__()
        self.config_dir = config_dir

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield ChatScreen(config_dir=self.config_dir)
        yield Footer()

    def action_clear(self) -> None:
        chat = self.query_one(ChatScreen)
        chat.clear()


def launch(config_dir: Path) -> None:
    """启动 ait TUI"""
    app = AitApp(config_dir=config_dir)
    app.run()
