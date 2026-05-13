"""主对话屏幕"""

from __future__ import annotations

from textual.screen import Screen
from textual.widgets import RichLog, Input
from textual.containers import Vertical


class ChatScreen(Screen):
    """运维对话主屏幕"""

    def compose(self):
        with Vertical():
            yield RichLog(id="chat-area", markup=True, wrap=True, highlight=True)
            yield Input(id="input-bar", placeholder="输入运维操作...")

    def on_mount(self) -> None:
        chat_area = self.query_one("#chat-area", RichLog)
        chat_area.write("[bold green]ait[/] [dim]AI 智能运维终端[/]")
        chat_area.write("")
        chat_area.write("用自然语言管理服务器，例如：")
        chat_area.write("  [dim]> 查看 web-01 的 nginx 状态[/]")
        chat_area.write("  [dim]> 重启所有前端 nginx[/]")
        chat_area.write("")
        chat_area.write("[dim]Tab 补全  Ctrl+N 节点  Ctrl+S Skills  Ctrl+L 清屏[/]")
        chat_area.write("")

        input_bar = self.query_one("#input-bar", Input)
        input_bar.focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """处理用户提交的消息"""
        text = event.value.strip()
        if not text:
            return

        chat_area = self.query_one("#chat-area", RichLog)
        input_bar = self.query_one("#input-bar", Input)

        chat_area.write("\n[bold green]>[/] " + text)
        chat_area.write("")
        chat_area.write("[dim italic]Agent 收到: " + text[:60] + "...[/]")
        chat_area.write("")

        input_bar.clear()

    def add_message(self, role: str, content: str) -> None:
        """向对话区添加消息"""
        chat_area = self.query_one("#chat-area", RichLog)
        if role == "user":
            chat_area.write("\n[bold green]>[/] " + content)
        elif role == "tool":
            chat_area.write("[dim italic]" + content + "[/]")
        elif role == "error":
            chat_area.write("[bold red]✗[/] " + content)

    def clear(self) -> None:
        """清屏"""
        chat_area = self.query_one("#chat-area", RichLog)
        chat_area.clear()
        self.on_mount()
