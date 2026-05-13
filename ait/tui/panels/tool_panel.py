"""工具执行结果面板 — 右侧栏，不影响主对话"""
from __future__ import annotations

import sys

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
    """右侧工具执行结果面板"""

    def __init__(self):
        super().__init__(id="tool-panel")

    def compose(self):
        yield Label("[bold]工具[/]", id="tool-panel-title")
        yield Static("[dim]工具执行结果将显示在此[/]", id="tool-results")

    def start_tool(self, name: str, node: str, cmd: str) -> None:
        """工具开始执行时显示的提示"""
        cn_name = TOOL_CN_NAMES.get(name, name)
        label = cn_name
        if node and node != "-":
            label += " · {}".format(node)
        if cmd:
            label += " [dim]{}[/]".format(cmd[:40])
        results = self.query_one("#tool-results", Static)
        current = str(results.renderable) if results.renderable else ""
        if current == "[dim]工具执行结果将显示在此[/]":
            current = ""
        hint = "[dim yellow]⏳ {} ...[/]".format(label)
        if current:
            results.update(current + "\n\n" + hint)
        else:
            results.update(hint)

    def add_result(self, name: str, node: str, cmd: str, output) -> None:
        """添加一次工具执行的结果卡片"""
        # Debug: print to stderr
        print(f"[ToolPanel] add_result: name={name}, node={node}, cmd={cmd}, output_type={type(output).__name__}",
              file=sys.stderr, flush=True)

        results = self.query_one("#tool-results", Static)
        current = str(results.renderable) if results.renderable else ""
        if current == "[dim]工具执行结果将显示在此[/]":
            current = ""

        card = self._format_card(name, node, cmd, output)
        print(f"[ToolPanel] card preview: {card[:120]}...", file=sys.stderr, flush=True)

        if current and card:
            # Replace the "running" hint if it exists
            cn_name = TOOL_CN_NAMES.get(name, name)
            running_hint = "[dim yellow]⏳ {} ".format(cn_name)
            if running_hint in current:
                # Replace the running line with the actual card
                lines = current.split("\n\n")
                new_lines = []
                replaced = False
                for line in lines:
                    if running_hint in line and not replaced:
                        new_lines.append(card)
                        replaced = True
                    else:
                        new_lines.append(line)
                if not replaced:
                    new_lines.append(card)
                results.update("\n\n".join(new_lines))
            else:
                results.update(current + "\n\n" + card)
        elif card:
            results.update(card)

        try:
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
            # 尝试解析为 JSON（工具错误/拒绝消息的格式）
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
            # 优先取 stdout
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
                # 生成摘要
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
            # list_nodes 等返回列表的工具
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

        # 转义 Rich 标记符号
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
        self.query_one("#tool-results", Static).update("[dim]工具执行结果将显示在此[/]")
