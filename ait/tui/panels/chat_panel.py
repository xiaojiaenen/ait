"""对话面板 — Markdown 渲染 + 滚动支持"""
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
        """追加一行 Markdown 文本"""
        if self._current_text:
            self._current_text += "\n" + text
        else:
            self._current_text = text
        self._refresh()

    def append_text(self, text: str) -> None:
        """追加文本到当前行（流式输出）"""
        self._current_text += text
        self._refresh()

    def _refresh(self) -> None:
        md = self.query_one("#chat-area", Markdown)
        md.update(self._current_text)
        # 延迟滚动确保布局更新后执行
        md.call_after_refresh(lambda: md.scroll_end(animate=False))

    def clear(self) -> None:
        self._current_text = ""
        self.query_one("#chat-area", Markdown).update("")
