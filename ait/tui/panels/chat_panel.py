"""对话面板 — Markdown 渲染 + 流式节流"""
from __future__ import annotations

import time

from textual.containers import Vertical
from textual.widgets import Markdown


def _make_md_parser():
    """创建增强版 Markdown 解析器：表格 + 任务列表 + 脚注"""
    from markdown_it import MarkdownIt
    from mdit_py_plugins.tasklists import tasklists_plugin
    from mdit_py_plugins.deflist import deflist_plugin
    from mdit_py_plugins.footnote import footnote_plugin

    parser = MarkdownIt("gfm-like")
    parser.use(tasklists_plugin)
    parser.use(deflist_plugin)
    try:
        parser.use(footnote_plugin)
    except Exception:
        pass
    return parser


class ChatPanel(Vertical):
    """对话展示面板"""

    def __init__(self):
        super().__init__(id="chat-panel")
        self._current_text = ""
        self._last_flush = 0.0

    def compose(self):
        yield Markdown("", id="chat-area", parser_factory=_make_md_parser)

    def write_line(self, text: str) -> None:
        """追加一行 Markdown 文本，立即刷新"""
        if self._current_text:
            self._current_text += "\n" + text
        else:
            self._current_text = text
        self._do_update()

    def append_text(self, text: str) -> None:
        """追加文本到当前行（流式节流 ~50ms）"""
        self._current_text += text
        now = time.monotonic()
        if now - self._last_flush >= 0.05:
            self._do_update()

    def flush(self) -> None:
        """强制刷新缓冲区"""
        self._do_update()

    def _do_update(self) -> None:
        self._last_flush = time.monotonic()
        try:
            md = self.query_one("#chat-area", Markdown)
            md.update(self._current_text)
            md.scroll_end(animate=False)
        except Exception:
            pass

    def get_current_text(self) -> str:
        """获取当前对话的原始文本"""
        return self._current_text

    def clear(self) -> None:
        self._current_text = ""
        try:
            self.query_one("#chat-area", Markdown).update("")
        except Exception:
            pass
