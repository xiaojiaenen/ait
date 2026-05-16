"""右侧侧边栏 — 会话活动 / 技能调用 / 审计记录，始终可见且可滚动"""
from __future__ import annotations

from textual.containers import VerticalScroll
from textual.widgets import Static


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
    "load_skill": "加载技能",
}


class Sidebar(VerticalScroll):
    """右侧侧边栏 — 始终可见，展示会话活动、技能调用、审计记录"""

    def __init__(self):
        super().__init__(id="sidebar")
        self._tp_entries: list[dict] = []
        self._tp_pending: dict[str, str] = {}
        self._skill_calls: list[str] = []
        self._audit_entries: list[dict] = []

    def compose(self):
        yield Static("[bold]会话[/]", id="sidebar-session-title")
        yield Static("[dim]工具执行结果将显示在此[/]", id="sidebar-session")

    # -- 工具结果 --

    def start_tool(self, name: str, node: str, cmd: str, call_id: str = "") -> None:
        cn_name = TOOL_CN_NAMES.get(name, name)
        label = cn_name
        if node and node != "-":
            label += " · {}".format(node)
        if cmd:
            label += " [dim]{}[/]".format(cmd[:40])
        key = call_id or name
        self._tp_pending[key] = label
        self._refresh()

    def add_result(self, name: str, node: str, cmd: str, output, call_id: str = "") -> None:
        card = self._format_card(name, node, cmd, output)
        key = call_id or name
        self._tp_pending.pop(key, None)
        self._tp_entries.append({"name": name, "card": card, "call_id": key})
        if len(self._tp_entries) > 30:
            self._tp_entries = self._tp_entries[-30:]
        self._refresh()

    # -- 技能调用 --

    def add_skill_call(self, skill_name: str) -> None:
        import datetime
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        self._skill_calls.append(f"[dim]{ts}[/]  [bold magenta]⚙[/] {skill_name}")
        if len(self._skill_calls) > 20:
            self._skill_calls = self._skill_calls[-20:]
        self._refresh()

    # -- 审计条目 --

    def add_audit(self, entry: dict) -> None:
        self._audit_entries.append(entry)
        if len(self._audit_entries) > 30:
            self._audit_entries = self._audit_entries[-30:]
        self._refresh()

    # -- 渲染 --

    def _refresh(self) -> None:
        parts = []

        # === 会话活动（工具结果） ===
        for entry in self._tp_entries:
            parts.append(entry["card"])
        for label in self._tp_pending.values():
            if parts:
                parts.append("")
            parts.append("[dim yellow]⏳ {} ...[/]".format(label))
        if not parts:
            parts.append("[dim]暂无活动[/]")

        # === 技能调用 ===
        if self._skill_calls:
            parts.append("")
            parts.append("[bold]技能调用[/]")
            parts.extend(self._skill_calls)

        # === 审计记录 ===
        if self._audit_entries:
            parts.append("")
            parts.append("[bold]审计记录[/]")
            for entry in self._audit_entries[-15:]:
                result = entry.get("result", "")
                if result == "ok":
                    status = "[green]✓[/]"
                elif result == "error":
                    status = "[red]✗[/]"
                elif result == "rejected":
                    status = "[yellow]⊘[/]"
                else:
                    status = result
                parts.append(
                    "{} [dim]{}[/] {} {} [dim]{}[/]".format(
                        status,
                        entry.get("time", ""),
                        entry.get("node", "-"),
                        entry.get("command", "")[:30],
                        entry.get("approved", ""),
                    )
                )

        text = "\n".join(parts)
        try:
            w = self.query_one("#sidebar-session", Static)
            w.update(text)
        except Exception:
            pass

    def clear_results(self) -> None:
        self._tp_entries.clear()
        self._tp_pending.clear()
        self._refresh()

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
                stdout = "{} 项:\n{}".format(len(output), "\n".join("- " + n for n in names))
            else:
                names = [n.get("name", str(n)) if isinstance(n, dict) else str(n) for n in output[:6]]
                stdout = "{} 项:\n{}\n  ...(+{} 项)".format(
                    len(output), "\n".join("- " + n for n in names), len(output) - 6
                )
        elif output is not None:
            stdout = str(output)[:500]

        stdout = rich_escape(stdout)
        lines = stdout.strip().split("\n")
        if len(lines) > 5:
            lines = lines[:5]
            stdout = "\n".join(lines) + "\n  ...(已折叠)"

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
        return "[bold][{}]{}[/] {}[/]\n{}".format(color, status, header, body)
