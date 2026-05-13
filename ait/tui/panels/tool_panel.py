"""工具执行结果面板 — 右侧栏，不影响主对话"""
from __future__ import annotations

from textual.containers import Vertical
from textual.widgets import Static, Label


# 工具中文名映射
TOOL_CN_NAMES = {
    "exec_command": "执行命令",
    "list_nodes": "节点列表",
    "add_node": "添加节点",
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
        yield Static("", id="tool-results")

    def add_result(self, name: str, node: str, cmd: str, output) -> None:
        """添加一次工具执行的结果卡片"""
        results = self.query_one("#tool-results", Static)
        current = results.renderable
        prev = str(current) if current else ""

        card = self._format_card(name, node, cmd, output)
        if prev:
            results.update(prev + "\n\n" + card)
        else:
            results.update(card)
        self.query_one("#tool-results", Static).scroll_end(animate=False)

    def _format_card(self, name: str, node: str, cmd: str, output) -> str:
        cn_name = TOOL_CN_NAMES.get(name, name)
        ok = True
        stdout = ""

        if isinstance(output, dict):
            ok = output.get("ok", True)
            stdout = output.get("stdout", "") or output.get("error", "")
            # 处理 batch_exec 的特殊格式
            if not stdout and "error" in output and isinstance(output.get("error"), str):
                stdout = output["error"]
            if not stdout:
                # 生成摘要
                parts = []
                for k, v in output.items():
                    if k in ("ok", "exit_code", "duration_ms"):
                        continue
                    if isinstance(v, dict):
                        parts.append("{}: {}".format(k, "✓" if v.get("ok") else "✗"))
                    elif isinstance(v, list):
                        parts.append("{}: {} 项".format(k, len(v)))
                    elif isinstance(v, str) and len(v) > 60:
                        parts.append("{}: ...".format(k))
                    elif v is not None:
                        parts.append("{}: {}".format(k, v))
                if parts:
                    stdout = "  ".join(parts)
        else:
            stdout = str(output)

        # 折叠长输出
        lines = stdout.strip().split("\n")
        folded = ""
        if len(lines) > 5:
            lines = lines[:5]
            folded = "\n  ...(已折叠)"

        status = "✓" if ok else "✗"
        color = "green" if ok else "red"

        header = cn_name
        if node and node != "-":
            header += " · {}".format(node)
        if cmd:
            header += "  [dim]{}[/]".format(cmd[:50])

        body = "\n".join("  " + line for line in lines) if stdout.strip() else ""

        return "[bold][{}]{}[/] {}[/]\n{}".format(
            color, status, header, body
        ) + folded

    def clear_results(self) -> None:
        self.query_one("#tool-results", Static).update("")
