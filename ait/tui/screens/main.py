"""主屏幕 — Tab 布局 + Agent 生命周期 + 快捷键驱动"""
from __future__ import annotations

from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import (
    TabbedContent,
    TabPane,
    Input,
    Header,
    Footer,
)
from textual.binding import Binding
from textual.screen import Screen

from ait.tui.panels.chat_panel import ChatPanel
from ait.tui.panels.nodes_panel import NodesPanel
from ait.tui.panels.metrics_panel import MetricsPanel
from ait.tui.panels.skills_panel import SkillsPanel
from ait.tui.panels.audit_panel import AuditPanel


class MainScreen(Screen):
    """运维主屏幕"""

    BINDINGS = [
        Binding("ctrl+c", "quit", "退出", show=False),
        Binding("ctrl+l", "clear", "清屏"),
        Binding("1", "switch_tab('chat')", "对话", show=False),
        Binding("2", "switch_tab('nodes')", "节点", show=False),
        Binding("3", "switch_tab('metrics')", "指标", show=False),
        Binding("4", "switch_tab('skills')", "技能", show=False),
        Binding("5", "switch_tab('audit')", "审计", show=False),
        Binding("up", "history_up", "", show=False),
        Binding("down", "history_down", "", show=False),
    ]

    def __init__(self, config_dir: Path):
        super().__init__()
        self.config_dir = config_dir
        self.agent = None
        self._command_history: list[str] = []
        self._history_index: int = -1
        self._saved_input: str = ""

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with TabbedContent(id="main-tabs"):
            with TabPane("对话", id="tab-chat"):
                yield ChatPanel()
            with TabPane("节点", id="tab-nodes"):
                yield NodesPanel(config_dir=self.config_dir)
            with TabPane("指标", id="tab-metrics"):
                yield MetricsPanel()
            with TabPane("技能", id="tab-skills"):
                yield SkillsPanel()
            with TabPane("审计", id="tab-audit"):
                yield AuditPanel()
        yield Input(id="input-bar", placeholder="输入运维操作... (/ 触发宏)")
        yield Footer()

    def on_mount(self) -> None:
        self._write_welcome()
        self.query_one("#input-bar", Input).focus()
        self.run_worker(self._init_agent())
        self.set_interval(10, self._refresh_metrics)

    def _write_welcome(self) -> None:
        chat = self.query_one(ChatPanel)
        chat.write_line("# ait")
        chat.write_line("")
        chat.write_line("*AI 运维助手*")
        chat.write_line("")
        chat.write_line("> 查看所有节点状态")
        chat.write_line("> 重启 nginx 服务")
        chat.write_line("")
        chat.write_line("*`1-5` 面板  `↑↓` 历史  `Ctrl+L` 清屏*")

    # -- Tab switching --

    def action_switch_tab(self, tab: str) -> None:
        tabs = self.query_one("#main-tabs", TabbedContent)
        tabs.active = f"tab-{tab}"

    # -- Input history --

    def action_history_up(self) -> None:
        if not self._command_history:
            return
        focused = self.focused
        if focused and isinstance(focused, Input):
            if self._history_index == -1:
                self._saved_input = focused.value
            if self._history_index < len(self._command_history) - 1:
                self._history_index += 1
            idx = len(self._command_history) - 1 - self._history_index
            focused.value = self._command_history[idx]
            focused.action_end()

    def action_history_down(self) -> None:
        focused = self.focused
        if focused and isinstance(focused, Input):
            if self._history_index > 0:
                self._history_index -= 1
                idx = len(self._command_history) - 1 - self._history_index
                focused.value = self._command_history[idx]
            elif self._history_index == 0:
                self._history_index = -1
                focused.value = self._saved_input
            focused.action_end()

    def action_clear(self) -> None:
        self.query_one(ChatPanel).clear()

    # -- Agent lifecycle --

    async def _init_agent(self) -> None:
        chat = self.query_one(ChatPanel)
        try:
            from ait.agent.ops_agent import OpsAgent
            self.agent = OpsAgent(config_dir=self.config_dir)

            # 设置 SSH 主机密钥验证回调
            self.agent.node_manager.set_screen(self)
            self.agent.node_manager.set_host_key_callback(self._verify_host_key)

            for hook in self.agent.agent.hooks._hooks:
                from ait.security.tui_provider import TuiApprovalProvider
                if hasattr(hook, "provider") and isinstance(hook.provider, TuiApprovalProvider):
                    hook.provider.set_screen(self)
            tools = self.agent.tools.list_tools()
            tool_names = [t.name for t in tools]
            chat.write_line("*已加载 {} 个工具: {}*".format(len(tools), ", ".join(tool_names)))

            # Refresh skills & macros
            skills = self._list_skills()
            macros = self._list_macros()
            self.query_one(SkillsPanel).reload_list(skills=skills, macros=macros)
        except Exception as e:
            chat.write_line("*初始化失败，请检查 API Key 后重启*")
        chat.write_line("")

    async def _verify_host_key(self, host: str, fingerprint: str, key_type: str) -> bool:
        """SSH 主机密钥验证回调 — 在 TUI 中弹窗确认"""
        from ait.tui.widgets.host_key_dialog import HostKeyConfirmDialog
        dialog = HostKeyConfirmDialog(host, fingerprint, key_type)
        result = await self.app.push_screen_wait(dialog)
        return result if isinstance(result, bool) else False

    def _list_skills(self) -> list[dict]:
        """列出可用技能"""
        if self.agent is None:
            return []
        try:
            skills = self.agent.skill_manager.list_skills()
            return [{"name": s.name, "description": s.description} for s in skills]
        except Exception:
            return []

    def _list_macros(self) -> list[dict]:
        """列出可用宏"""
        try:
            from ait.macros.manager import MacroManager
            manager = MacroManager(self.config_dir / "macros")
            return [
                {"name": m.name, "description": m.description}
                for m in manager.list_all()
            ]
        except Exception:
            return []

    def on_input_submitted(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        if not text:
            return
        input_bar = self.query_one("#input-bar", Input)
        self._command_history.append(text)
        self._history_index = -1
        self._saved_input = ""

        chat = self.query_one(ChatPanel)
        chat.write_line("")
        chat.write_line("> " + text)

        # Switch to chat tab on submission
        self.query_one("#main-tabs", TabbedContent).active = "tab-chat"

        if self.agent is None:
            chat.write_line("**Agent 未就绪，请等待初始化完成**")
            chat.write_line("")
            input_bar.clear()
            return

        # Check for macro prefix
        if text.startswith("/"):
            self.run_worker(self._run_macro(text))
        else:
            self.run_worker(self._run_agent(text))
        input_bar.clear()

    # -- Agent execution --

    async def _run_agent(self, text: str) -> None:
        chat = self.query_one(ChatPanel)
        audit = self.query_one(AuditPanel)
        import datetime
        try:
            first_text = True
            async for event in self.agent.stream(text):
                if event.type == "text_delta":
                    content = event.data.get("content", "")
                    if first_text:
                        chat.write_line("")
                        first_text = False
                    chat.append_text(content)
                elif event.type == "tool_start":
                    first_text = True
                    args = event.data.get("args", {})
                    self._tool_name = event.data.get("tool_name", "")
                    self._tool_node = args.get("node", "-")
                    self._tool_cmd = str(args.get("command", ""))[:80]
                    self._tool_time = datetime.datetime.now().strftime("%H:%M:%S")
                elif event.type == "tool_end":
                    first_text = True
                    name = getattr(self, "_tool_name", "")
                    node = getattr(self, "_tool_node", "-")
                    cmd = getattr(self, "_tool_cmd", "")
                    output = event.data.get("output", {})
                    self._render_tool_result(chat, name, node, cmd, output)
                    result = "ok" if isinstance(output, dict) and output.get("ok") else "done"
                    audit.add_entry({
                        "time": getattr(self, "_tool_time", ""),
                        "node": node,
                        "command": cmd or name,
                        "result": result,
                        "approved": "auto",
                    })
                elif event.type == "error":
                    first_text = True
                    chat.write_line("*操作未能完成，请重试*")
                    audit.add_entry({
                        "time": getattr(self, "_tool_time", ""),
                        "node": getattr(self, "_tool_node", "-"),
                        "command": getattr(self, "_tool_cmd", "")[:60],
                        "result": "error",
                        "approved": "blocked",
                    })
                elif event.type == "done":
                    chat.write_line("")
        except Exception:
            chat.write_line("")
            chat.write_line("*请求失败，请检查网络后重试*")
        chat.write_line("")

    def _render_tool_result(self, chat, name: str, node: str, cmd: str, output) -> None:
        """渲染紧凑的命令执行结果框"""
        stdout = ""
        ok = True
        if isinstance(output, dict):
            ok = output.get("ok", True)
            stdout = output.get("stdout", "") or output.get("error", "")
        else:
            stdout = str(output)

        lines = stdout.strip().split("\n")
        folded = False
        if len(lines) > 6:
            lines = lines[:6]
            folded = True

        chat.write_line("")
        chat.write_line("---")
        header = "{} · `{}`".format(name, node) if node and node != "-" else name
        if cmd:
            header += "  `{}`".format(cmd)
        status = " ✓" if ok else " ✗"
        chat.write_line("**" + header + "**" + status)
        if lines and stdout.strip():
            chat.write_line("")
            for line in lines:
                chat.write_line("  " + line)
            if folded:
                chat.write_line("  *...(输出已折叠)*")
        chat.write_line("---")

    async def _run_macro(self, text: str) -> None:
        """执行宏命令"""
        chat = self.query_one(ChatPanel)
        macro_name = text[1:].strip().split()[0]
        try:
            from ait.macros.manager import MacroManager
            manager = MacroManager(self.config_dir / "macros")
            macro = manager.resolve(macro_name)
            if macro is None:
                chat.write_line("**未知宏: " + macro_name + "**")
                chat.write_line("*可用宏: " + ", ".join(manager.list_names()) + "*")
                chat.write_line("")
                return
            command = f"在 {macro.target or '指定节点'} 上执行: {macro.command}"
            chat.write_line("**宏:** " + macro.description)
            chat.write_line("")
            await self._run_agent(command)
        except Exception:
            chat.write_line("**宏执行出错**")
            chat.write_line("")

    def _refresh_nodes(self) -> None:
        """刷新节点面板"""
        self.query_one(NodesPanel).reload_nodes()

    async def _refresh_metrics(self) -> None:
        """定时刷新所有节点指标"""
        if self.agent is None:
            return
        try:
            from ait.health.metrics import MetricsCollector
            collector = MetricsCollector(self.agent.node_manager)
        except Exception:
            return

        nodes = self.agent.node_manager.list_nodes()
        if not nodes:
            return

        # 并发采集
        import asyncio
        tasks = [collector.collect(n.name) for n in nodes]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        metrics_data = []
        health_map = {}
        for node, result in zip(nodes, results):
            if isinstance(result, Exception):
                health_map[node.name] = "offline"
                continue
            if result is not None and result.cpu_percent >= 0:
                metrics_data.append({
                    "node": node.name,
                    "cpu": result.cpu_percent,
                    "mem": result.mem_percent,
                    "disk": result.disk_percent,
                    "load1": result.load_1min,
                    "load5": result.load_5min,
                    "load15": result.load_15min,
                })
                health_map[node.name] = "online" if result.cpu_percent < 90 else "busy"
            else:
                health_map[node.name] = "offline"

        self.query_one("MetricsPanel").update_metrics(metrics_data)
        self.query_one("NodesPanel").update_status(health_map)
