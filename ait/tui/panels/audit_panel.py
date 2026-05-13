"""审计面板 — 命令执行历史"""
from __future__ import annotations

from textual.containers import Vertical
from textual.widgets import Static, DataTable


class AuditPanel(Vertical):
    """审计日志面板"""

    def __init__(self):
        super().__init__(id="audit-panel")
        self._entries: list[dict] = []

    def compose(self):
        yield Static("[bold]审计日志[/]", id="audit-title")
        yield DataTable(id="audit-table", cursor_type="none")

    def on_mount(self) -> None:
        table = self.query_one("#audit-table", DataTable)
        table.add_columns("时间", "节点", "命令", "结果", "确认")

    def add_entry(self, entry: dict) -> None:
        """添审计条目
        entry: {"time": str, "node": str, "command": str, "result": str, "approved": str}
        """
        self._entries.append(entry)
        table = self.query_one("#audit-table", DataTable)
        result = entry.get("result", "")
        result_color = "[green]成功[/]" if result == "ok" else "[red]失败[/]" if result == "error" else f"[yellow]{result}[/]"
        table.add_row(
            entry.get("time", ""),
            entry.get("node", "-"),
            entry.get("command", ""),
            result_color,
            entry.get("approved", ""),
        )
