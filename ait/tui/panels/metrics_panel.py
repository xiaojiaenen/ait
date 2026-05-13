"""指标面板 — 实时 CPU/内存/磁盘/负载/网络/运行时间"""
from __future__ import annotations

from textual.containers import Vertical
from textual.widgets import Static, DataTable
import datetime


class MetricsPanel(Vertical):
    """实时指标面板"""

    def __init__(self):
        super().__init__(id="metrics-panel")
        self._last_update = ""

    def compose(self):
        yield Static("[bold]实时指标[/]", id="metrics-title")
        yield DataTable(id="metrics-table", cursor_type="none")
        yield Static("", id="metrics-time")

    def on_mount(self) -> None:
        table = self.query_one("#metrics-table", DataTable)
        table.add_columns(
            "节点", "CPU%", "MEM", "磁盘%",
            "Net↓", "Net↑", "Load1", "Load5", "运行",
        )

    def update_metrics(self, data: list[dict]) -> None:
        """更新指标数据"""
        table = self.query_one("#metrics-table", DataTable)
        table.clear()

        for row in data:
            cpu = self._cell(row.get("cpu", 0), 50, 80)
            mem_gb = row.get("mem_used_gb", 0)
            mem_total = row.get("mem_total_gb", 0)
            mem_str = f"{mem_gb:.1f}/{mem_total:.1f}G" if mem_total > 0 else f"{row.get('mem', 0):.0f}%"
            mem_color = "green" if row.get("mem", 0) < 60 else ("yellow" if row.get("mem", 0) < 85 else "red")
            disk = self._cell(row.get("disk", 0), 70, 90)
            rx = self._bps(row.get("net_rx_kbps", 0))
            tx = self._bps(row.get("net_tx_kbps", 0))
            uptime = f"{row.get('uptime_hours', 0):.0f}h"
            cores = row.get("cpu_cores", 0)

            node_label = f"{row['node']}"
            if cores:
                cpu_str = f"{cpu} ({cores}c)"
            else:
                cpu_str = cpu

            table.add_row(
                node_label,
                cpu_str,
                f"[{mem_color}]{mem_str}[/]",
                disk,
                rx,
                tx,
                f"{row.get('load1', 0):.1f}",
                f"{row.get('load5', 0):.1f}",
                uptime,
            )

        self._last_update = datetime.datetime.now().strftime("%H:%M:%S")
        self.query_one("#metrics-time", Static).update(
            f"[dim]更新于 {self._last_update} · 每 10s 刷新[/]"
        )

    @staticmethod
    def _cell(value: float, warn: float, crit: float) -> str:
        v = f"{value:.0f}%"
        if value < warn:
            return f"[green]{v}[/]"
        elif value < crit:
            return f"[yellow]{v}[/]"
        return f"[red]{v}[/]"

    @staticmethod
    def _bps(kbps: float) -> str:
        if kbps < 1:
            return "[dim]0[/]"
        if kbps < 1024:
            return f"{kbps:.0f}K"
        return f"{kbps/1024:.1f}M"
