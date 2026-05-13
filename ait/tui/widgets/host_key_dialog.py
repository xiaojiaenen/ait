"""SSH 主机密钥确认弹窗"""
from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Center, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Static


class HostKeyConfirmDialog(ModalScreen[bool]):
    """首次连接 SSH 主机时的密钥确认弹窗"""

    def __init__(self, host: str, fingerprint: str, key_type: str):
        super().__init__()
        self.host = host
        self.fingerprint = fingerprint
        self.key_type = key_type

    def compose(self) -> ComposeResult:
        with Center():
            with Static(classes="host-key-box"):
                yield Label("[bold yellow]⚠ 首次连接主机[/]\n", id="hk-title")
                yield Label(f"主机: [bold]{self.host}[/]")
                yield Label(f"密钥类型: [bold]{self.key_type}[/]")
                yield Label(f"指纹: [dim]{self.fingerprint}[/]")
                yield Label("")
                yield Label("[yellow]请确认指纹是否正确，防止中间人攻击[/]")
                yield Label("")
                with Horizontal(id="hk-buttons"):
                    yield Button("接受 [Enter]", variant="primary", id="btn-accept")
                    yield Button("拒绝 [Esc]", variant="error", id="btn-reject")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-accept":
            self.dismiss(True)
        else:
            self.dismiss(False)

    def on_key(self, event) -> None:
        if event.key == "escape":
            self.dismiss(False)
        elif event.key == "enter":
            self.dismiss(True)
