"""工具执行结果面板 — 右侧栏，不影响主对话"""
from __future__ import annotations

from textual.containers import Vertical
from textual.widgets import Static, Label


TOOL_CN_NAMES = {
    "exec_command": "执行命令",
    "list_nodes": "节点列表",
    "add_node": "添加节点",
    "remove_node": "删除节点",
    "add_group": "创建分组",
    "list_groups": "分组列表",
    "add_node_to_group": "节点入组",
    "batch_exec": "批量执行",
    "upload_file": "上传文件",
    "download_file": "下载文件",
    "get_metrics": "系统指标",
    "get_time": "当前时间",
    "list_skills": "技能列表",
    "run_skill": "运行技能",
}


class ToolPanel(Vertical):
    """右侧工具执行结果面板 — 内部状态管理，不使用 Static.renderable"""

    def __init__(self):
        super().__init__(id="tool-panel")
        self._entries: list[dict] = []  # 历史结果条目
        self._running: dict[str, str] = {}  # call_id -> label

    def compose(self):
        yield Label("[bold]工具[/]", id="tool-panel-title")
        yield Static("", id="tool-results")

    def start_tool(self, name: str, node: str, cmd: str, call_id: str = "") -> None:
        """工具开始执行 — 显示运行中指示"""
        cn_name = TOOL_CN_NAMES.get(name, name)
        label = cn_name
        if node and node != "-":
            label += " · {}".format(node)
        if cmd:
            label += " [dim]{}[/]".format(cmd[:40])
        # 按 call_id 去重
        key = call_id or name
        self._running[key] = label
        self._render()

    def add_result(
        self, name: str, node: str, cmd: str, output, call_id: str = ""
    ) -> None:
        """添加工具执行结果 — 替换对应的运行中指示"""
        card = self._format_card(name, node, cmd, output)
        key = call_id or name
        # 移除对应的运行中项
        self._running.pop(key, None)
        # 添加到历史条目
        self._entries.append({
            "name": name,
            "card": card,
            "call_id": key,
        })
        # 保持最多 20 条历史
        if len(self._entries) > 20:
            self._entries = self._entries[-20:]
        self._render()

    def _render(self) -> None:
        """根据内部状态渲染整个面板"""
        parts = []
        # 历史结果
        for entry in self._entries:
            parts.append(entry["card"])
        # 正在运行的工具
        for label in self._running.values():
            if parts:
                parts.append("")
            parts.append("[dim yellow]⏳ {} ...[/]".format(label))

        if not parts:
            text = "[dim]工具执行结果将显示在此[/]"
        else:
            text = "\n\n".join(parts)

        try:
            results = self.query_one("#tool-results", Static)
            results.update(text)
            results.scroll_end(animate=False)
        except Exception:
            pass

    def _format_card(self, name: str, node: str, cmd: str, output) -> str:
        import json
        from rich.markup import escape as rich_escape

        cn_name = TOOL_CN_NAMES.get(name, name)
        ok = True
        rejected = False
        stdout = ""

        if isinstance(output, str):
            try:
                parsed = json.loads(output)
                if isinstance(parsed, dict):
                    output = parsed
                else:
                    stdout = output
            except (json.JSONDecodeError, TypeError):
                stdout = output

        if isinstance(output, dict):
            ok = output.get("ok", True)
            tool_executed = output.get("tool_executed", True)
            if not ok and not tool_executed:
                rejected = True
            if output.get("stdout"):
                stdout = output["stdout"]
            elif output.get("stderr"):
                stdout = output["stderr"]
            elif output.get("error"):
                err = output["error"]
                if isinstance(err, dict):
                    stdout = err.get("message", str(err))
                else:
                    stdout = str(err)
            elif output.get("instruction"):
                stdout = output["instruction"]
            elif not stdout:
                parts = []
                for k, v in output.items():
                    if k in ("ok", "exit_code", "duration_ms", "stdout", "stderr",
                             "tool_executed", "instruction", "error"):
                        continue
                    if isinstance(v, dict):
                        parts.append("{}: {}".format(k, "✓" if v.get("ok") else "✗"))
                    elif isinstance(v, list):
                        if len(v) <= 5:
                            names = [n.get("name", str(n)) if isinstance(n, dict) else str(n) for n in v]
                            parts.append("{}: [{}]".format(k, ", ".join(names)))
                        else:
                            names = [n.get("name", str(n)) if isinstance(n, dict) else str(n) for n in v[:4]]
                            parts.append("{}: [{}...] ({}项)".format(k, ", ".join(names), len(v)))
                    elif isinstance(v, str) and len(v) > 60:
                        parts.append("{}: {}...".format(k, v[:57]))
                    elif v is not None:
                        parts.append("{}: {}".format(k, v))
                if parts:
                    stdout = "  ".join(parts)
        elif isinstance(output, list):
            if len(output) <= 8:
                names = [n.get("name", str(n)) if isinstance(n, dict) else str(n) for n in output]
                stdout = "找到 {} 个节点:\n{}".format(len(output), "\n".join("- " + n for n in names))
            else:
                names = [n.get("name", str(n)) if isinstance(n, dict) else str(n) for n in output[:6]]
                stdout = "找到 {} 个节点:\n{}\n  ...(+{} 项)".format(
                    len(output), "\n".join("- " + n for n in names), len(output) - 6
                )
        elif output is not None:
            stdout = str(output)[:500]

        stdout = rich_escape(stdout)

        lines = stdout.strip().split("\n")
        folded = ""
        if len(lines) > 5:
            lines = lines[:5]
            folded = "\n  ...(已折叠)"

        if rejected:
            status = "⊘"
            color = "yellow"
        elif ok:
            status = "✓"
            color = "green"
        else:
            status = "✗"
            color = "red"

        header = cn_name
        if node and node != "-":
            header += " · {}".format(node)
        if cmd:
            header += "  [dim]{}[/]".format(rich_escape(cmd[:50]))

        body = "\n".join("  " + line for line in lines) if stdout.strip() else ""

        return "[bold][{}]{}[/] {}[/]\n{}".format(
            color, status, header, body
        ) + folded

    def clear_results(self) -> None:
        self._entries.clear()
        self._running.clear()
        self._render()
