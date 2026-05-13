"""指标采集器 — 通过 SSH 解析 /proc 文件系统"""
from __future__ import annotations

from ait.nodes.models import NodeMetrics


class MetricsCollector:
    """通过 SSH 采集节点实时指标（CPU/内存/磁盘/负载）"""

    def __init__(self, node_manager):
        self._node_manager = node_manager
        self._prev_cpu: dict[str, tuple[float, float]] = {}

    async def collect(self, node_name: str) -> NodeMetrics | None:
        """采集单个节点指标"""
        result = await self._node_manager.exec_command(
            node_name,
            "cat /proc/stat /proc/meminfo /proc/loadavg 2>/dev/null; df / | tail -1",
            timeout=10,
        )
        if not result.ok:
            return NodeMetrics(node=node_name, cpu_percent=-1, mem_percent=-1,
                               disk_percent=-1, load_1min=-1)

        return self._parse(result.stdout, node_name)

    def _parse(self, raw: str, node_name: str) -> NodeMetrics:
        """解析 /proc 输出"""
        metrics = NodeMetrics(node=node_name)

        lines = raw.split("\n")

        # 解析 /proc/stat (第一行是 cpu 总)
        for line in lines:
            if line.startswith("cpu "):
                parts = line.split()
                # cpu user nice system idle iowait irq softirq steal
                user = int(parts[1])
                nice = int(parts[2])
                system = int(parts[3])
                idle = int(parts[4])
                iowait = int(parts[5]) if len(parts) > 5 else 0
                irq = int(parts[6]) if len(parts) > 6 else 0
                softirq = int(parts[7]) if len(parts) > 7 else 0
                steal = int(parts[8]) if len(parts) > 8 else 0

                total = user + nice + system + idle + iowait + irq + softirq + steal
                idle_total = idle + iowait

                prev = self._prev_cpu.get(node_name)
                if prev:
                    prev_idle, prev_total = prev
                    total_delta = total - prev_total
                    idle_delta = idle_total - prev_idle
                    if total_delta > 0:
                        metrics.cpu_percent = round(
                            (1 - idle_delta / total_delta) * 100, 1
                        )
                self._prev_cpu[node_name] = (idle_total, total)
                break

        # 解析 /proc/meminfo
        mem_total = 0
        mem_avail = 0
        for line in lines:
            if line.startswith("MemTotal:"):
                mem_total = self._extract_kb(line)
            elif line.startswith("MemAvailable:"):
                mem_avail = self._extract_kb(line)
            if mem_total > 0 and mem_avail > 0:
                metrics.mem_percent = round(
                    (1 - mem_avail / mem_total) * 100, 1
                )
                break

        # 解析 /proc/loadavg
        for line in lines:
            if "load average" in line.lower() or line.strip().count(" ") >= 2:
                parts = line.strip().split()
                if len(parts) >= 3:
                    try:
                        metrics.load_1min = float(parts[0])
                        metrics.load_5min = float(parts[1])
                        metrics.load_15min = float(parts[2])
                        break
                    except ValueError:
                        continue

        # 解析 df
        for line in lines:
            if line.strip().endswith("%"):
                parts = line.split()
                for p in parts:
                    if p.endswith("%"):
                        try:
                            metrics.disk_percent = int(p.rstrip("%"))
                        except ValueError:
                            pass

        return metrics

    @staticmethod
    def _extract_kb(line: str) -> int:
        """从 /proc/meminfo 行提取 KB 数值"""
        parts = line.split()
        if len(parts) >= 2:
            try:
                return int(parts[1])
            except ValueError:
                pass
        return 0
