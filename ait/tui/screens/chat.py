"""主对话屏幕"""

from __future__ import annotations

from pathlib import Path

from textual.screen import Screen
from textual.widgets import Static, Input
from textual.containers import Horizontal, Vertical, ScrollableContainer

from ait.tui.widgets.node_panel import NodePanel


class ChatScreen(Screen):
    """运维对话主屏幕"""

    BINDINGS = [
        ("ctrl+n", "toggle_nodes", "节点列表"),
    ]

    def __init__(self, config_dir: Path):
        super().__init__()
        self.config_dir = config_dir
        self.agent = None
        self._messages = []
        self._chat_text = ""

    def compose(self):
        with Horizontal():
            yield NodePanel(config_dir=self.config_dir)
            with Vertical(id="chat-main"):
                yield ScrollableContainer(
                    Static(id="chat-area"),
                    id="chat-scroll",
                )
                yield Input(id="input-bar", placeholder="输入运维操作...")

    def action_toggle_nodes(self) -> None:
        panel = self.query_one(NodePanel)
        panel.toggle()

    def on_mount(self) -> None:
        self.write_line("[bold green]ait[/] [dim]AI 智能运维终端[/]")
        self.write_line("")
        self.write_line("[dim]正在初始化 AI 引擎...[/]")
        self.write_line("")
        self.write_line("用自然语言管理服务器，例如：")
        self.write_line("  [dim]> 查看所有节点的状态[/]")
        self.write_line("  [dim]> 重启前端 nginx[/]")
        self.write_line("")
        self.write_line("[dim]Ctrl+N 节点  Ctrl+S Skills  Ctrl+L 清屏[/]")
        self.write_line("")
        self.query_one("#input-bar", Input).focus()
        self.run_worker(self._init_agent())

    def write_line(self, text: str) -> None:
        """向对话区追加一行"""
        chat = self.query_one("#chat-area", Static)
        if self._chat_text:
            self._chat_text += "\n" + text
        else:
            self._chat_text = text
        chat.update(self._chat_text)
        container = self.query_one("#chat-scroll", ScrollableContainer)
        container.scroll_end(animate=False)

    async def _init_agent(self) -> None:
        try:
            from ait.agent.ops_agent import OpsAgent
            self.agent = OpsAgent(config_dir=self.config_dir)
            for hook in self.agent.agent._hooks._hooks:
                from ait.security.tui_provider import TuiApprovalProvider
                if isinstance(hook.provider, TuiApprovalProvider):
                    hook.provider.set_screen(self)
            session = await self.agent.storage.load("default")
            if session and session.context.get_messages():
                msg_count = len(session.context.get_messages())
                self.write_line(f"[dim]已恢复上次会话 ({msg_count} 条消息)[/]")
            tools = self.agent.tools.list_tools()
            tool_names = [t.name for t in tools]
            self.write_line("[dim]已加载 " + str(len(tools)) + " 个工具: " + ", ".join(tool_names) + "[/]")
            self.write_line("[dim green]AI 引擎就绪[/]")
        except Exception as e:
            self.write_line("[bold red]Agent 初始化失败: " + str(e) + "[/]")
            self.write_line("[dim]请设置 API Key 后重启[/]")
        self.write_line("")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        if not text:
            return
        input_bar = self.query_one("#input-bar", Input)
        self.write_line("\n[bold green]>[/] " + text)
        if self.agent is None:
            self.write_line("[bold red]Agent 未就绪，请等待初始化完成[/]")
            self.write_line("")
            input_bar.clear()
            return
        self.run_worker(self._run_agent(text))
        input_bar.clear()

    async def _run_agent(self, text: str) -> None:
        try:
            async for event in self.agent.stream(text):
                if event.type == "text_delta":
                    content = event.data.get("content", "")
                    self.write_line(content)
                elif event.type == "tool_start":
                    name = event.data.get("tool_name", "")
                    self.write_line("[dim]  > 执行 " + name + "...[/]")
                elif event.type == "tool_end":
                    name = event.data.get("tool_name", "")
                    output = str(event.data.get("output", ""))[:100]
                    self.write_line("[dim]  < " + name + " 完成[/]")
                elif event.type == "error":
                    msg = event.data.get("message", "未知错误")
                    self.write_line("[bold red]Error: " + msg + "[/]")
                elif event.type == "done":
                    self.write_line("")
        except Exception as e:
            self.write_line("[bold red]执行出错: " + str(e) + "[/]")
        self.write_line("")

    def clear(self) -> None:
        chat = self.query_one("#chat-area", Static)
        self._chat_text = ""
        chat.update("")
