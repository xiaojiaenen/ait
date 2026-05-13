"""主屏幕 — Tab 布局 + Agent 生命周期 + 快捷键驱动"""
from __future__ import annotations

from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal
from textual.widgets import (
    TabbedContent,
    TabPane,
    Input,
    Header,
    Footer,
    Static,
)
from textual.binding import Binding
from textual.screen import Screen

from ait.tui.panels.chat_panel import ChatPanel
from ait.tui.panels.tool_panel import ToolPanel
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
        self._suggest_index: int = 0
        self._suggest_matches: list[str] = []

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with TabbedContent(id="main-tabs"):
            with TabPane("对话", id="tab-chat"):
                with Horizontal(id="chat-split"):
                    yield ChatPanel()
                    yield ToolPanel()
            with TabPane("节点", id="tab-nodes"):
                yield NodesPanel(config_dir=self.config_dir)
            with TabPane("指标", id="tab-metrics"):
                yield MetricsPanel()
            with TabPane("技能", id="tab-skills"):
                yield SkillsPanel()
            with TabPane("审计", id="tab-audit"):
                yield AuditPanel()
        yield Input(id="input-bar", placeholder="输入运维操作... @节点名 /宏名")
        yield Static("", id="node-suggest")
        yield Footer()

    def on_mount(self) -> None:
        self._write_welcome()
        self.query_one("#input-bar", Input).focus()
        self.query_one("#node-suggest", Static).display = False
        self.run_worker(self._init_agent())
        self.set_interval(10, self._refresh_metrics)

    def _write_welcome(self) -> None:
        chat = self.query_one(ChatPanel)
        chat.write_line("# ait — AI 运维助手")
        chat.write_line("")
        chat.write_line("`1-5` 面板  `↑↓` 历史  `Ctrl+L` 清屏")

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
        self.query_one(ToolPanel).clear_results()

    # -- Agent lifecycle --

    async def _init_agent(self) -> None:
        chat = self.query_one(ChatPanel)
        try:
            from ait.agent.ops_agent import OpsAgent
            self.agent = OpsAgent(config_dir=self.config_dir)
            self.agent.set_tui_screen(self)

            # Refresh skills & macros
            skills = self._list_skills()
            macros = self._list_macros()
            self.query_one(SkillsPanel).reload_list(skills=skills, macros=macros)
            chat.write_line("*AI 引擎就绪*")
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

    def on_input_changed(self, event: Input.Changed) -> None:
        """检测 @ 输入，显示节点建议列表"""
        if event.input.id != "input-bar":
            return
        value = event.value or ""
        suggest = self.query_one("#node-suggest", Static)

        # 查找最后一个 @ 位置
        at_idx = value.rfind("@")
        if at_idx < 0:
            suggest.display = False
            return

        # 提取 @ 后面的部分
        after_at = value[at_idx + 1:]
        # 如果 @ 后面有空格，不显示建议
        if " " in after_at:
            suggest.display = False
            return

        # 获取节点列表
        nodes = self._get_node_names()
        if not nodes:
            suggest.display = False
            return

        # 过滤匹配的节点
        if after_at:
            matched = [n for n in nodes if after_at.lower() in n.lower()]
        else:
            matched = nodes

        if not matched:
            suggest.display = False
            return

        # 渲染建议列表
        lines = ["[bold]节点:[/]"]
        for i, name in enumerate(matched[:8]):
            prefix = "[bold]>[/]" if i == self._suggest_index else " "
            lines.append("{} {}".format(prefix, name))
        if len(matched) > 8:
            lines.append("  ...(+{})".format(len(matched) - 8))
        lines.append("[dim]Tab 补全  Esc 取消[/]")
        suggest.update("\n".join(lines))
        suggest.display = True
        self._suggest_matches = matched
        self._suggest_index = 0

    def on_key(self, event) -> None:
        """处理 @ 建议快捷键"""
        suggest = self.query_one("#node-suggest", Static)
        if not suggest.display:
            return
        matches = getattr(self, "_suggest_matches", [])
        if event.key == "escape":
            suggest.display = False
            self._suggest_matches = []
            self._suggest_index = 0
        elif event.key == "tab":
            if matches and self._suggest_index < len(matches):
                name = matches[self._suggest_index]
                input_bar = self.query_one("#input-bar", Input)
                value = input_bar.value
                at_idx = value.rfind("@")
                # 替换 @partial 为 @name
                new_value = value[:at_idx + 1] + name + " "
                input_bar.value = new_value
                input_bar.action_end()
                suggest.display = False
                self._suggest_matches = []
                self._suggest_index = 0
            event.prevent_default()
        elif event.key == "up":
            if self._suggest_index > 0:
                self._suggest_index -= 1
                self._refresh_suggest()
        elif event.key == "down":
            if self._suggest_index < len(matches) - 1:
                self._suggest_index += 1
                self._refresh_suggest()

    def _refresh_suggest(self) -> None:
        """刷新建议列表显示"""
        suggest = self.query_one("#node-suggest", Static)
        matches = getattr(self, "_suggest_matches", [])
        if not matches:
            return
        lines = ["[bold]节点:[/]"]
        for i, name in enumerate(matches[:8]):
            prefix = "[bold]>[/]" if i == self._suggest_index else " "
            lines.append("{} {}".format(prefix, name))
        if len(matches) > 8:
            lines.append("  ...(+{})".format(len(matches) - 8))
        lines.append("[dim]Tab 补全  Esc 取消[/]")
        suggest.update("\n".join(lines))

    def _get_node_names(self) -> list[str]:
        """获取已配置的节点名称列表"""
        if self.agent is None:
            return []
        try:
            nodes = self.agent.node_manager.list_nodes()
            return [n.name for n in nodes]
        except Exception:
            return []

    def on_input_submitted(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        if not text:
            return
        # 隐藏建议
        self.query_one("#node-suggest", Static).display = False

        input_bar = self.query_one("#input-bar", Input)
        self._command_history.append(text)
        self._history_index = -1
        self._saved_input = ""

        chat = self.query_one(ChatPanel)
        chat.write_line("")
        chat.write_line("> **You** " + text)
        chat.write_line("")
        self.query_one(ToolPanel).clear_results()

        self.query_one("#main-tabs", TabbedContent).active = "tab-chat"

        if self.agent is None:
            chat.write_line("*Agent 未就绪，请等待初始化完成*")
            chat.write_line("")
            input_bar.clear()
            return

        # @node 前缀：限定在指定节点执行
        if text.startswith("@"):
            parts = text.split(None, 1)
            node_name = parts[0][1:]  # 去掉 @
            rest = parts[1] if len(parts) > 1 else ""
            # 验证节点存在
            nodes = self._get_node_names()
            if node_name not in nodes:
                chat.write_line("*节点 `{}` 不存在，可用: {}*".format(
                    node_name, ", ".join(nodes) if nodes else "(无)"
                ))
                chat.write_line("")
                input_bar.clear()
                return
            if not rest:
                chat.write_line("*请输入要在 {} 上执行的命令*".format(node_name))
                chat.write_line("")
                input_bar.clear()
                return
            # 构造节点限定命令
            text = "在 {} 节点上执行: {}".format(node_name, rest)
        elif text.startswith("/"):
            self.run_worker(self._run_macro(text))
            input_bar.clear()
            return

        self.run_worker(self._run_agent(text))
        input_bar.clear()

    # -- Agent execution --

    async def _run_agent(self, text: str) -> None:
        chat = self.query_one(ChatPanel)
        tools = self.query_one(ToolPanel)
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
                    chat.flush()
                    first_text = True
                    args = event.data.get("args", {})
                    self._tool_name = event.data.get("tool_name", "")
                    self._tool_node = args.get("node", "-")
                    self._tool_cmd = str(args.get("command", ""))[:80]
                    self._tool_time = datetime.datetime.now().strftime("%H:%M:%S")
                    try:
                        tools.start_tool(self._tool_name,
                                         self._tool_node,
                                         self._tool_cmd)
                    except Exception:
                        pass
                elif event.type == "tool_end":
                    chat.flush()
                    first_text = True
                    name = getattr(self, "_tool_name", "")
                    node = getattr(self, "_tool_node", "-")
                    cmd = getattr(self, "_tool_cmd", "")
                    output = event.data.get("output", {})
                    # 解析 JSON 字符串输出（工具拒绝/错误消息格式）
                    output_dict = output
                    if isinstance(output, str):
                        import json as _json
                        try:
                            output_dict = _json.loads(output)
                        except (_json.JSONDecodeError, TypeError):
                            output_dict = {}
                    try:
                        tools.add_result(name, node, cmd, output)
                    except Exception:
                        pass
                    # 根据解析结果确定状态
                    ok = isinstance(output_dict, dict) and output_dict.get("ok") is not False
                    tool_executed = isinstance(output_dict, dict) and output_dict.get("tool_executed") is not False
                    if not tool_executed and isinstance(output_dict, dict) and "tool_executed" in output_dict:
                        result = "rejected"
                        approved = "rejected"
                        reason = ""
                        if isinstance(output_dict.get("error"), dict):
                            reason = output_dict["error"].get("message", "")
                        chat.write_line("*操作已被拒绝* {}".format(reason))
                    elif not ok:
                        result = "error"
                        approved = "auto"
                    else:
                        result = "ok"
                        approved = "auto"
                    try:
                        audit.add_entry({
                            "time": getattr(self, "_tool_time", ""),
                            "node": node,
                            "command": cmd or name,
                            "result": result,
                            "approved": approved,
                        })
                    except Exception:
                        pass
                elif event.type in ("error", "tool_error"):
                    chat.flush()
                    first_text = True
                    msg = event.data.get("message", "")
                    if msg:
                        chat.write_line("*操作未能完成: {}*".format(msg))
                    else:
                        chat.write_line("*操作未能完成*")
                    try:
                        audit.add_entry({
                            "time": getattr(self, "_tool_time", ""),
                            "node": getattr(self, "_tool_node", "-"),
                            "command": getattr(self, "_tool_cmd", "")[:60],
                            "result": "error",
                            "approved": "blocked",
                        })
                    except Exception:
                        pass
                elif event.type == "done":
                    chat.flush()
                    chat.write_line("")
        except Exception as e:
            chat.flush()
            chat.write_line("")
            err_type = type(e).__name__
            chat.write_line("*响应中断: {}*".format(err_type))
            # 将详细错误写入日志文件
            try:
                log_path = self.config_dir / "error.log"
                with open(log_path, "a") as f:
                    import traceback
                    f.write("\n[{}]\n".format(datetime.datetime.now()))
                    traceback.print_exc(file=f)
                    f.write("\n")
            except Exception:
                pass
        chat.flush()
        chat.write_line("")

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
                    "net_rx_kbps": result.net_rx_kbps,
                    "net_tx_kbps": result.net_tx_kbps,
                    "uptime_hours": result.uptime_hours,
                    "cpu_cores": result.cpu_cores,
                    "mem_used_gb": result.mem_used_gb,
                    "mem_total_gb": result.mem_total_gb,
                })
                health_map[node.name] = "online" if result.cpu_percent < 90 else "busy"
            else:
                health_map[node.name] = "offline"

        self.query_one(MetricsPanel).update_metrics(metrics_data)
        self.query_one(NodesPanel).update_status(health_map)
