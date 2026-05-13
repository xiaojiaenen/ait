"""对话面板 — Static 渲染，支持 Rich markup 和流式更新"""
from __future__ import annotations

from textual.containers import Vertical
from textual.widgets import Static


class ChatPanel(Vertical):
    """对话展示面板"""

    def __init__(self):
        super().__init__(id="chat-panel")
        self._current_text = ""

    def compose(self):
        yield Static("", id="chat-area")

    def write_line(self, text: str) -> None:
        """追加一行 Rich markup 文本"""
        if self._current_text:
            self._current_text += "\n" + text
        else:
            self._current_text = text
        self.query_one("#chat-area", Static).update(self._current_text)

    def append_text(self, text: str) -> None:
        """追加文本到当前行（流式输出）"""
        self._current_text += text
        self.query_one("#chat-area", Static).update(self._current_text)

    def clear(self) -> None:
        self._current_text = ""
        self.query_one("#chat-area", Static).update("")
