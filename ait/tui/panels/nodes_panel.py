"""节点管理面板 — 支持搜索、详情展开"""
from __future__ import annotations

from pathlib import Path

from textual.containers import Vertical
from textual.widgets import Static, Input, Label


class NodesPanel(Vertical):
    """节点管理面板"""

    def __init__(self, config_dir: Path):
        super().__init__(id="nodes-panel")
        self.config_dir = config_dir
        self._search_term = ""
        self._node_items = []
        self._group_items = []
        self._expanded_node = None

    def compose(self):
        yield Label("[bold]节点管理[/]", id="nodes-title")
        yield Input(placeholder="/ 搜索节点...", id="node-search")
        yield Static("(加载中...)", id="node-list")
        yield Label("[dim]Enter 详情  Esc 清除搜索[/]", id="nodes-help")

    def on_mount(self) -> None:
        self.query_one("#node-search", Input).display = False
        self.reload_nodes()

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "node-search":
            self._search_term = event.value.strip()
            self._render()

    def on_key(self, event) -> None:
        if event.key == "slash" and self.display:
            search = self.query_one("#node-search", Input)
            search.display = True
            search.focus()
        elif event.key == "escape":
            self._search_term = ""
            self._expanded_node = None
            search = self.query_one("#node-search", Input)
            search.value = ""
            search.display = False
            self._render()
        elif event.key == "enter" and self.display:
            self._toggle_detail()

    def _toggle_detail(self) -> None:
        """展开/收起当前选中节点"""
        pass

    def reload_nodes(self) -> None:
        """重新加载节点列表"""
        try:
            from ait.nodes.manager import NodeManager
            nm = NodeManager(db_path=self.config_dir / "nodes.db")
            self._node_items = nm.list_nodes()
            self._group_items = nm.list_groups()
        except Exception:
            self._node_items = []
            self._group_items = []
        self._render()

    def update_status(self, health_map: dict[str, str]) -> None:
        """更新健康状态颜色: name -> 'online'|'offline'|'busy'"""
        self._health = health_map
        self._render()

    def _render(self) -> None:
        node_list = self.query_one("#node-list", Static)

        if not self._node_items and not self._group_items:
            node_list.update("[dim](暂无节点)[/]")
            return

        lines = []

        # 分组展示
        grouped_names = set()
        if self._group_items:
            for g in self._group_items:
                g_nodes = g.get("nodes", [])
                if self._search_term:
                    g_nodes = [n for n in g_nodes if self._search_term.lower() in n.lower()]
                if not g_nodes:
                    continue
                grouped_names.update(g_nodes)
                lines.append(f"[bold]{g['name']}[/]")
                for node_name in g_nodes:
                    lines.append(self._node_line(node_name))
                lines.append("")

        # 未分组节点
        ungrouped = [n for n in self._node_items if n.name not in grouped_names]
        if self._search_term:
            ungrouped = [
                n for n in ungrouped
                if self._search_term.lower() in n.name.lower()
                or self._search_term.lower() in n.host.lower()
                or any(self._search_term.lower() in t.lower() for t in n.tags)
            ]

        if ungrouped:
            if self._group_items:
                lines.append("[bold]未分组[/]")
            for n in ungrouped:
                lines.append(self._node_line(n.name))

        node_list.update("\n".join(lines) if lines else "[dim](无匹配)[/]")

    def _node_line(self, name: str) -> str:
        """渲染单行节点信息"""
        from ait.nodes.manager import NodeManager
        nm = NodeManager(db_path=self.config_dir / "nodes.db")
        node = nm.get_node(name)
        if not node:
            return f"  {name}"

        status = getattr(self, "_health", {}).get(name, "offline")
        icons = {"online": "[green]●[/]", "offline": "[red]●[/]", "busy": "[yellow]●[/]"}
        icon = icons.get(status, "[red]●[/]")

        return f"  {icon} {node.name} [dim]{node.host}[/]"
