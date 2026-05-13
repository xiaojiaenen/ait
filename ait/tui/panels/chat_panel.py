"""对话面板 — Markdown 实时渲染"""
from __future__ import annotations

from textual.containers import Vertical
from textual.widgets import Markdown


class ChatPanel(Vertical):
    """对话展示面板"""

    def __init__(self):
        super().__init__(id="chat-panel")
        self._current_text = ""

    def compose(self):
        yield Markdown("", id="chat-area")

    def write_line(self, text: str) -> None:
        """追加一行"""
        markdown = self.query_one("#chat-area", Markdown)
        if self._current_text:
            self._current_text += "\n" + text
        else:
            self._current_text = text
        markdown.update(self._current_text)
        markdown.scroll_end(animate=False)

    def append_text(self, text: str) -> None:
        """追加文本到当前行（流式输出）"""
        markdown = self.query_one("#chat-area", Markdown)
        self._current_text += text
        markdown.update(self._current_text)
        markdown.scroll_end(animate=False)

    def clear(self) -> None:
        self._current_text = ""
        self.query_one("#chat-area", Markdown).update("")
