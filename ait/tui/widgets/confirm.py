"""危险操作确认弹窗"""

from __future__ import annotations

import asyncio

from textual.app import ComposeResult
from textual.containers import Center, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Static


class ConfirmDialog(ModalScreen[bool]):
    """危险操作确认弹窗"""

    def __init__(self, command: str, node: str, reason: str):
        super().__init__()
        self.command = command
        self.node = node
        self.reason = reason

    def compose(self) -> ComposeResult:
        with Center():
            with Static(classes="confirm-box"):
                yield Label("[bold red]⚠ 危险操作确认[/]\n", id="confirm-title")
                yield Label(f"命令: [bold]{self.command}[/]")
                yield Label(f"目标节点: [bold]{self.node}[/]")
                yield Label(f"风险: [bold yellow]{self.reason}[/]")
                yield Label("")
                with Horizontal(id="confirm-buttons"):
                    yield Button("确认执行 [Enter]", variant="error", id="btn-confirm")
                    yield Button("取消 [Esc]", variant="primary", id="btn-cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-confirm":
            self.dismiss(True)
        else:
            self.dismiss(False)

    def on_key(self, event) -> None:
        if event.key == "escape":
            self.dismiss(False)
        elif event.key == "enter":
            self.dismiss(True)


async def show_confirm_dialog(
    screen, command: str, node: str, reason: str
) -> bool:
    """在 TUI 中显示确认弹窗并等待用户决策

    返回 True 表示用户确认执行。
    """
    dialog = ConfirmDialog(command, node, reason)
    result = await screen.app.push_screen_wait(dialog)
    return result if isinstance(result, bool) else False
