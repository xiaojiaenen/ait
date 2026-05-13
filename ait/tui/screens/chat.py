"""主对话屏幕"""

from __future__ import annotations

from pathlib import Path

from textual.screen import Screen
from textual.widgets import RichLog, Input
from textual.containers import Vertical


class ChatScreen(Screen):
    """运维对话主屏幕"""

    def __init__(self, config_dir: Path):
        super().__init__()
        self.config_dir = config_dir
        self.agent = None

    def compose(self):
        with Vertical():
            yield RichLog(id="chat-area", markup=True, wrap=True, highlight=True)
            yield Input(id="input-bar", placeholder="输入运维操作...")

    async def on_mount(self) -> None:
        chat_area = self.query_one("#chat-area", RichLog)
        chat_area.write("[bold green]ait[/] [dim]AI 智能运维终端[/]")
        chat_area.write("")

        # 初始化 Agent
        chat_area.write("[dim]正在初始化 AI 引擎...[/]")
        try:
            from ait.agent.ops_agent import OpsAgent
            self.agent = OpsAgent(config_dir=self.config_dir)
            tools = self.agent.tools.list_tools()
            tool_names = [t.name for t in tools]
            chat_area.write("[dim]已加载 " + str(len(tools)) + " 个工具: " + ", ".join(tool_names) + "[/]")
        except Exception as e:
            chat_area.write("[bold red]Agent 初始化失败: " + str(e) + "[/]")
            chat_area.write("[dim]请设置 API Key 后重启: export DEEPSEEK_API_KEY=sk-...[/]")

        chat_area.write("")
        chat_area.write("用自然语言管理服务器，例如：")
        chat_area.write("  [dim]> 查看所有节点的状态[/]")
        chat_area.write("  [dim]> 重启前端 nginx[/]")
        chat_area.write("")
        chat_area.write("[dim]Tab 补全  Ctrl+N 节点  Ctrl+S Skills  Ctrl+L 清屏[/]")
        chat_area.write("")

        self.query_one("#input-bar", Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        if not text:
            return

        chat_area = self.query_one("#chat-area", RichLog)
        input_bar = self.query_one("#input-bar", Input)

        chat_area.write("\n[bold green]>[/] " + text)

        if self.agent is None:
            chat_area.write("[bold red]Agent 未初始化，请先设置 API Key[/]")
            chat_area.write("")
            input_bar.clear()
            return

        self.run_worker(self._run_agent(text))
        input_bar.clear()

    async def _run_agent(self, text: str) -> None:
        chat_area = self.query_one("#chat-area", RichLog)
        try:
            async for event in self.agent.stream(text):
                if event.type == "text_delta":
                    content = event.data.get("content", "")
                    chat_area.write(content)
                elif event.type == "tool_start":
                    name = event.data.get("tool_name", "")
                    chat_area.write("\n[dim]  > 执行 " + name + "...[/]")
                elif event.type == "tool_end":
                    name = event.data.get("tool_name", "")
                    output = str(event.data.get("output", ""))[:100]
                    chat_area.write("\n[dim]  < " + name + " 完成[/]")
                elif event.type == "error":
                    msg = event.data.get("message", "未知错误")
                    chat_area.write("\n[bold red]Error: " + msg + "[/]")
                elif event.type == "done":
                    chat_area.write("")
        except Exception as e:
            chat_area.write("\n[bold red]执行出错: " + str(e) + "[/]")
        chat_area.write("")

    def add_message(self, role: str, content: str) -> None:
        chat_area = self.query_one("#chat-area", RichLog)
        if role == "user":
            chat_area.write("\n[bold green]>[/] " + content)
        elif role == "tool":
            chat_area.write("[dim italic]" + content + "[/]")
        elif role == "error":
            chat_area.write("[bold red]  [/] " + content)

    def clear(self) -> None:
        chat_area = self.query_one("#chat-area", RichLog)
        chat_area.clear()
