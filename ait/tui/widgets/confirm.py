"""危险操作确认弹窗 — 支持"本次会话记住" """
from __future__ import annotations

import datetime

from textual.app import ComposeResult
from textual.containers import Center, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Static, Checkbox

from ait.config import get_log_path

LOG_PATH = get_log_path("approval.log")


def _dlog(msg: str) -> None:
    try:
        ts = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
        with open(LOG_PATH, "a") as f:
            f.write(f"[{ts}] [DIALOG] {msg}\n")
    except Exception:
        pass


class ConfirmDialog(ModalScreen[tuple]):
    """危险操作确认弹窗，返回 (approved: bool, remember: bool)"""

    def __init__(self, command: str, node: str, reason: str):
        super().__init__()
        self.command = command
        self.node = node
        self.reason = reason
        self._remember = False
        self._resolved = False

    def compose(self) -> ComposeResult:
        with Center():
            with Static(classes="confirm-box"):
                yield Label("[bold red]⚠ 危险操作确认[/]\n", id="confirm-title")
                yield Label(f"命令: [bold]{self.command}[/]")
                yield Label(f"目标节点: [bold]{self.node}[/]")
                yield Label(f"风险: [bold yellow]{self.reason}[/]")
                yield Label("")
                yield Checkbox("本次会话不再询问相同操作", id="chk-remember")
                yield Label("")
                with Horizontal(id="confirm-buttons"):
                    yield Button("确认执行 [Enter]", variant="error", id="btn-confirm")
                    yield Button("取消 [Esc]", variant="primary", id="btn-cancel")

    def _resolve(self, result: tuple) -> None:
        """安全地 dismiss，防止重复触发"""
        if self._resolved:
            _dlog(f"IGNORED duplicate dismiss: {result}")
            return
        self._resolved = True
        _dlog(f"dismiss: approved={result[0]}, remember={result[1]}")
        self.dismiss(result)

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        if event.checkbox.id == "chk-remember":
            self._remember = event.checkbox.value

    def on_button_pressed(self, event: Button.Pressed) -> None:
        _dlog(f"button pressed: id={event.button.id}")
        event.stop()
        if event.button.id == "btn-confirm":
            self._resolve((True, self._remember))
        else:
            self._resolve((False, False))

    def on_key(self, event) -> None:
        _dlog(f"key event: key={event.key!r}")
        if event.key == "escape":
            event.stop()
            self._resolve((False, False))
        # Enter 不在这里处理 — 让焦点所在的 Button 自然触发 Pressed 事件


async def show_confirm_dialog(
    screen, command: str, node: str, reason: str
) -> tuple:
    """在 TUI 中显示确认弹窗并等待用户决策

    返回 (approved: bool, remember: bool)
    """
    dialog = ConfirmDialog(command, node, reason)
    _dlog(f"push_screen_wait start: cmd={str(command)[:60]}")
    result = await screen.app.push_screen_wait(dialog)
    _dlog(f"push_screen_wait returned: {result!r}")
    if isinstance(result, tuple) and len(result) == 2:
        return result
    _dlog("unexpected result type, fallback to (False, False)")
    return (False, False)
