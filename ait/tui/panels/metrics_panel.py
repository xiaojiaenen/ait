"""指标面板 — 实时 CPU/内存/磁盘/负载"""
from __future__ import annotations

from textual.containers import Vertical
from textual.widgets import Static, DataTable


class MetricsPanel(Vertical):
    """实时指标面板"""

    def __init__(self):
        super().__init__(id="metrics-panel")

    def compose(self):
        yield Static("[bold]实时指标[/]", id="metrics-title")
        yield DataTable(id="metrics-table", cursor_type="none")

    def on_mount(self) -> None:
        table = self.query_one("#metrics-table", DataTable)
        table.add_columns("节点", "CPU%", "MEM%", "磁盘%", "Load1", "Load5", "Load15")

    def update_metrics(self, data: list[dict]) -> None:
        """更新指标数据
        data: [{"node": str, "cpu": float, "mem": float, "disk": float,
                 "load1": float, "load5": float, "load15": float}]
        """
        table = self.query_one("#metrics-table", DataTable)
        table.clear()

        for row in data:
            cpu = self._cell(row.get("cpu", 0), 50, 80)
            mem = self._cell(row.get("mem", 0), 60, 85)
            disk = self._cell(row.get("disk", 0), 70, 90)
            table.add_row(
                row["node"],
                cpu,
                mem,
                disk,
                f"{row.get('load1', 0):.1f}",
                f"{row.get('load5', 0):.1f}",
                f"{row.get('load15', 0):.1f}",
            )

    @staticmethod
    def _cell(value: float, warn: float, crit: float) -> str:
        v = f"{value:.0f}%"
        if value < warn:
            return f"[green]{v}[/]"
        elif value < crit:
            return f"[yellow]{v}[/]"
        return f"[red]{v}[/]"
