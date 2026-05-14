"""指标采集器 — 支持 Linux (/proc) 和 macOS (sysctl/vm_stat)"""
from __future__ import annotations

from ait.nodes.models import NodeMetrics


class MetricsCollector:
    """通过 exec_command 采集节点实时指标（CPU/内存/磁盘/负载）"""

    def __init__(self, node_manager):
        self._node_manager = node_manager
        self._prev_cpu: dict[str, tuple[float, float]] = {}

    async def collect(self, node_name: str) -> NodeMetrics | None:
        """采集单个节点指标，根据节点 OS 选择采集方式"""
        node = self._node_manager.get_node(node_name)
        node_os = getattr(node, "os", "linux") or "linux" if node else "linux"

        if node_os == "macos":
            return await self._collect_macos(node_name)
        elif node_os == "windows":
            return await self._collect_windows(node_name)
        else:
            return await self._collect_linux(node_name)

    async def _collect_linux(self, node_name: str) -> NodeMetrics | None:
        """Linux: 解析 /proc 文件系统"""
        result = await self._node_manager.exec_command(
            node_name,
            "echo '---STAT---'; cat /proc/stat | head -1; "
            "echo '---MEM---'; cat /proc/meminfo | head -3; "
            "echo '---LOAD---'; cat /proc/loadavg; "
            "echo '---UPTIME---'; cat /proc/uptime; "
            "echo '---NET---'; cat /proc/net/dev | tail -2; "
            "echo '---DF---'; df / | tail -1; "
            "echo '---CPUINFO---'; grep -c processor /proc/cpuinfo 2>/dev/null || echo 0",
            timeout=10,
        )
        if not result.ok:
            return NodeMetrics(node=node_name, cpu_percent=-1, mem_percent=-1,
                               disk_percent=-1, load_1min=-1)

        return self._parse_linux(result.stdout, node_name)

    async def _collect_macos(self, node_name: str) -> NodeMetrics | None:
        """macOS: 使用 sysctl + vm_stat + top + df"""
        cmd = (
            "echo '---CPU---'; top -l1 -n0 | head -5; "
            "echo '---MEM---'; vm_stat; sysctl -n hw.memsize; "
            "echo '---LOAD---'; sysctl -n vm.loadavg; "
            "echo '---UPTIME---'; uptime; "
            "echo '---DF---'; df / | tail -1; "
            "echo '---CPUINFO---'; sysctl -n hw.ncpu"
        )
        result = await self._node_manager.exec_command(node_name, cmd, timeout=10)
        if not result.ok:
            return NodeMetrics(node=node_name, cpu_percent=-1, mem_percent=-1,
                               disk_percent=-1, load_1min=-1)

        return self._parse_macos(result.stdout, node_name)

    async def _collect_windows(self, node_name: str) -> NodeMetrics | None:
        """Windows: 使用 wmic 采集基本指标"""
        cmd = (
            "wmic cpu get loadpercentage /value & "
            "wmic os get totalvisiblememorysize,freephysicalmemory /value & "
            "wmic logicaldisk where DeviceID='C:' get size,freespace /value"
        )
        result = await self._node_manager.exec_command(node_name, cmd, timeout=10)
        if not result.ok:
            return NodeMetrics(node=node_name, cpu_percent=-1, mem_percent=-1,
                               disk_percent=-1, load_1min=-1)

        return self._parse_windows(result.stdout, node_name)

    # -- Linux 解析 --

    def _parse_linux(self, raw: str, node_name: str) -> NodeMetrics:
        metrics = NodeMetrics(node=node_name)
        sections = self._split_sections(raw)

        # CPU
        stat = sections.get("STAT", "")
        for line in stat.split("\n"):
            if line.startswith("cpu "):
                parts = line.split()
                vals = [int(p) for p in parts[1:9]]
                if len(vals) >= 4:
                    user, nice, system, idle = vals[0], vals[1], vals[2], vals[3]
                    iowait = vals[4] if len(vals) > 4 else 0
                    irq = vals[5] if len(vals) > 5 else 0
                    softirq = vals[6] if len(vals) > 6 else 0
                    steal = vals[7] if len(vals) > 7 else 0
                    total = user + nice + system + idle + iowait + irq + softirq + steal
                    idle_total = idle + iowait
                    prev = self._prev_cpu.get(node_name)
                    if prev:
                        prev_idle, prev_total = prev
                        total_delta = total - prev_total
                        idle_delta = idle_total - prev_idle
                        if total_delta > 0:
                            metrics.cpu_percent = round((1 - idle_delta / total_delta) * 100, 1)
                    self._prev_cpu[node_name] = (idle_total, total)
                break

        # 内存
        mem = sections.get("MEM", "")
        mem_total = mem_avail = 0
        for line in mem.split("\n"):
            if line.startswith("MemTotal:"):
                mem_total = self._extract_kb(line)
            elif line.startswith("MemAvailable:"):
                mem_avail = self._extract_kb(line)
        if mem_total > 0 and mem_avail > 0:
            metrics.mem_percent = round((1 - mem_avail / mem_total) * 100, 1)
            metrics.mem_total_gb = round(mem_total / 1024 / 1024, 1)
            metrics.mem_used_gb = round((mem_total - mem_avail) / 1024 / 1024, 1)

        # 负载
        self._parse_load(sections.get("LOAD", ""), metrics)

        # 运行时间
        self._parse_uptime_linux(sections.get("UPTIME", ""), metrics)

        # 网络
        self._parse_net(sections.get("NET", ""), node_name, metrics)

        # CPU 核心数
        cpuinfo = sections.get("CPUINFO", "0")
        try:
            metrics.cpu_cores = int(cpuinfo.strip().split("\n")[0])
        except ValueError:
            metrics.cpu_cores = 0

        # 磁盘
        self._parse_disk(sections.get("DF", ""), metrics)

        return metrics

    # -- macOS 解析 --

    def _parse_macos(self, raw: str, node_name: str) -> NodeMetrics:
        metrics = NodeMetrics(node=node_name)
        sections = self._split_sections(raw)

        # CPU: top -l1 输出格式: "CPU usage: 5.26% user, 10.52% sys, 84.21% idle"
        cpu = sections.get("CPU", "")
        for line in cpu.split("\n"):
            if "CPU usage:" in line:
                import re
                match = re.search(r'(\d+\.?\d*)%\s+idle', line)
                if match:
                    idle_pct = float(match.group(1))
                    metrics.cpu_percent = round(100 - idle_pct, 1)

        # 内存: vm_stat 输出 "Pages free: xxx." + hw.memsize
        mem_section = sections.get("MEM", "")
        metrics = self._parse_macos_mem(mem_section, metrics)

        # 负载: vm.loadavg 输出 "{ 1.50 1.20 1.10 }"
        self._parse_load(sections.get("LOAD", ""), metrics)

        # 运行时间
        self._parse_uptime_macos(sections.get("UPTIME", ""), metrics)

        # CPU 核心数
        cpuinfo = sections.get("CPUINFO", "0")
        try:
            metrics.cpu_cores = int(cpuinfo.strip())
        except ValueError:
            metrics.cpu_cores = 0

        # 磁盘
        self._parse_disk(sections.get("DF", ""), metrics)

        return metrics

    def _parse_macos_mem(self, raw: str, metrics: NodeMetrics) -> NodeMetrics:
        """解析 vm_stat + hw.memsize 输出"""
        page_size = 16384  # macOS 默认页大小 16KB (arm64) / 4KB (x86)
        pages_free = pages_inactive = 0
        hw_memsize = 0

        for line in raw.split("\n"):
            line = line.strip()
            if line.endswith("."):
                line = line[:-1]
            if "page size of" in line:
                import re
                match = re.search(r'(\d+)\s*bytes', line)
                if match:
                    page_size = int(match.group(1))
            elif ": " in line:
                key, val = line.rsplit(": ", 1) if ": " in line else (line, "0")
                key = key.strip().strip('"')
                try:
                    v = int(val.strip().rstrip("."))
                except ValueError:
                    v = 0
                if "free" in key.lower() and "page" in key.lower():
                    pages_free = v
                elif "inactive" in key.lower():
                    pages_inactive = v
            else:
                try:
                    hw_memsize = int(line.strip())
                except ValueError:
                    pass

        if hw_memsize > 0:
            total_bytes = hw_memsize
            # free + inactive 是可回收的
            free_bytes = (pages_free + pages_inactive) * page_size
            metrics.mem_percent = round((1 - free_bytes / total_bytes) * 100, 1)
            metrics.mem_total_gb = round(total_bytes / 1024 / 1024 / 1024, 1)
            metrics.mem_used_gb = round((total_bytes - free_bytes) / 1024 / 1024 / 1024, 1)

        return metrics

    # -- Windows 解析 --

    def _parse_windows(self, raw: str, node_name: str) -> NodeMetrics:
        metrics = NodeMetrics(node=node_name)
        # wmic 输出格式: Key=Value 对
        kv = {}
        for line in raw.split("\n"):
            line = line.strip()
            if "=" in line:
                parts = line.split("=", 1)
                key = parts[0].strip().lower()
                try:
                    kv[key] = int(parts[1].strip())
                except ValueError:
                    pass

        if "loadpercentage" in kv:
            metrics.cpu_percent = kv["loadpercentage"]

        if "totalvisiblememorysize" in kv and "freephysicalmemory" in kv:
            total_kb = kv["totalvisiblememorysize"]
            free_kb = kv["freephysicalmemory"]
            if total_kb > 0:
                metrics.mem_percent = round((1 - free_kb / total_kb) * 100, 1)
                metrics.mem_total_gb = round(total_kb / 1024 / 1024, 1)
                metrics.mem_used_gb = round((total_kb - free_kb) / 1024 / 1024, 1)

        if "size" in kv and "freespace" in kv:
            total_bytes = kv["size"]
            free_bytes = kv["freespace"]
            if total_bytes > 0:
                metrics.disk_percent = round((1 - free_bytes / total_bytes) * 100, 1)

        return metrics

    # -- 共享解析 --

    @staticmethod
    def _parse_load(raw: str, metrics: NodeMetrics) -> None:
        """解析负载，兼容 Linux 和 macOS 格式"""
        text = raw.strip().strip("{").strip("}").strip()
        parts = text.replace(",", " ").split()
        if len(parts) >= 3:
            try:
                metrics.load_1min = float(parts[0])
                metrics.load_5min = float(parts[1])
                metrics.load_15min = float(parts[2])
            except ValueError:
                pass

    @staticmethod
    def _parse_uptime_linux(uptime_raw: str, metrics: NodeMetrics) -> None:
        """Linux: /proc/uptime 格式 '12345.67 98765.43'"""
        parts = uptime_raw.strip().split()
        if len(parts) >= 1:
            try:
                metrics.uptime_hours = round(float(parts[0]) / 3600, 1)
            except ValueError:
                pass

    @staticmethod
    def _parse_uptime_macos(uptime_raw: str, metrics: NodeMetrics) -> None:
        """macOS: 'uptime' 输出格式 '14:32  up 3 days, 2:15, 3 users'"""
        import re
        match = re.search(r'up\s+(.+?),?\s+\d+\s+user', uptime_raw)
        if match:
            up_str = match.group(1)
            hours = 0
            day_match = re.search(r'(\d+)\s+day', up_str)
            if day_match:
                hours += int(day_match.group(1)) * 24
            # 时间部分: "2:15" 或 "2 hrs" 等
            time_match = re.search(r'(\d+):(\d+)', up_str)
            if time_match:
                hours += int(time_match.group(1)) + int(time_match.group(2)) / 60
            elif re.search(r'(\d+)\s+hr', up_str):
                hours += int(re.search(r'(\d+)\s+hr', up_str).group(1))
            if hours > 0:
                metrics.uptime_hours = round(hours, 1)

    @staticmethod
    def _parse_disk(df_raw: str, metrics: NodeMetrics) -> None:
        """解析 df 输出，取最后一列的百分比"""
        for part in df_raw.split():
            if part.endswith("%"):
                try:
                    metrics.disk_percent = int(part.rstrip("%"))
                except ValueError:
                    pass

    def _parse_net(self, net_raw: str, node_name: str, metrics: NodeMetrics) -> None:
        """解析 /proc/net/dev 网络流量"""
        prev_net = getattr(self, "_prev_net", {})
        prev_rx, prev_tx, prev_ts = prev_net.get(node_name, (0, 0, 0))
        cur_rx = cur_tx = 0
        for line in net_raw.split("\n"):
            if ":" in line and "lo:" not in line:
                parts = line.strip().split()
                if len(parts) >= 10:
                    try:
                        cur_rx += int(parts[1])
                        cur_tx += int(parts[9])
                    except ValueError:
                        continue
        import time
        now_ts = time.time()
        if prev_ts > 0 and (now_ts - prev_ts) > 0:
            metrics.net_rx_kbps = round((cur_rx - prev_rx) / (now_ts - prev_ts) / 1024, 1)
            metrics.net_tx_kbps = round((cur_tx - prev_tx) / (now_ts - prev_ts) / 1024, 1)
        if not hasattr(self, "_prev_net"):
            self._prev_net = {}
        self._prev_net[node_name] = (cur_rx, cur_tx, now_ts)

    @staticmethod
    def _split_sections(raw: str) -> dict[str, str]:
        """按 ---NAME--- 分隔符拆分输出"""
        sections = {}
        current_name = ""
        current_lines = []
        for line in raw.split("\n"):
            if line.startswith("---") and line.endswith("---"):
                if current_name:
                    sections[current_name] = "\n".join(current_lines)
                current_name = line.strip("-")
                current_lines = []
            else:
                current_lines.append(line)
        if current_name:
            sections[current_name] = "\n".join(current_lines)
        return sections

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
