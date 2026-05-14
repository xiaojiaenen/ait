"""节点管理面板 — 支持搜索、选择、详情展开"""
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
        self._selected_idx = -1
        self._expanded_node = None

    def compose(self):
        yield Label("[bold]节点管理[/]", id="nodes-title")
        yield Input(placeholder="/ 搜索节点...", id="node-search")
        yield Static("(加载中...)", id="node-list")
        yield Label("[dim]↑↓ 选择  Enter 详情  Del 删除  / 搜索  Esc 退出[/]", id="nodes-help")

    def on_mount(self) -> None:
        self.query_one("#node-search", Input).display = False
        self.reload_nodes()

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "node-search":
            self._search_term = event.value.strip()
            self._selected_idx = -1
            self._expanded_node = None
            self._render_nodes()

    def on_key(self, event) -> None:
        if not self.display:
            return
        if event.key == "slash":
            search = self.query_one("#node-search", Input)
            search.display = True
            search.focus()
        elif event.key == "escape":
            self._search_term = ""
            self._expanded_node = None
            self._selected_idx = -1
            search = self.query_one("#node-search", Input)
            search.value = ""
            search.display = False
            self._render_nodes()
        elif event.key == "up":
            if self._selected_idx > 0:
                self._selected_idx -= 1
                self._render_nodes()
        elif event.key == "down":
            if self._selected_idx < len(self._node_items) - 1:
                self._selected_idx += 1
                self._render_nodes()
        elif event.key == "enter":
            self._toggle_detail()
        elif event.key == "delete":
            self._delete_selected()

    def _toggle_detail(self) -> None:
        """展开/收起当前选中节点"""
        if self._selected_idx < 0 or self._selected_idx >= len(self._node_items):
            return
        node = self._node_items[self._selected_idx]
        if self._expanded_node == node.name:
            self._expanded_node = None
        else:
            self._expanded_node = node.name
        self._render_nodes()

    def _delete_selected(self) -> None:
        """删除选中节点"""
        if self._selected_idx < 0 or self._selected_idx >= len(self._node_items):
            return
        node = self._node_items[self._selected_idx]
        if node.name == "localhost":
            return  # 不允许删除内置 localhost 节点
        try:
            from ait.nodes.manager import NodeManager
            nm = NodeManager(db_path=self.config_dir / "nodes.db")
            nm.remove_node(node.name)
            self._expanded_node = None
            self._selected_idx = max(-1, self._selected_idx - 1)
            self.reload_nodes()
        except Exception:
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
        self._render_nodes()

    def update_status(self, health_map: dict[str, str]) -> None:
        """更新健康状态颜色: name -> 'online'|'offline'|'busy'"""
        self._health = health_map
        self._render_nodes()

    def _render_nodes(self) -> None:
        node_list = self.query_one("#node-list", Static)

        if not self._node_items and not self._group_items:
            node_list.update("[dim](暂无节点)[/]")
            return

        lines = []

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
                    idx = self._node_index(node_name)
                    lines.append(self._node_line(node_name, idx))
                lines.append("")

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
                idx = self._node_index(n.name)
                lines.append(self._node_line(n.name, idx))

        node_list.update("\n".join(lines) if lines else "[dim](无匹配)[/]")

    def _node_index(self, name: str) -> int:
        for i, n in enumerate(self._node_items):
            if n.name == name:
                return i
        return -1

    def _node_line(self, name: str, idx: int = -1) -> str:
        """渲染单行节点信息"""
        node = None
        for n in self._node_items:
            if n.name == name:
                node = n
                break
        if not node:
            return f"  {name}"

        selected = idx >= 0 and idx == self._selected_idx
        cursor = "[bold]>[/]" if selected else " "

        status = getattr(self, "_health", {}).get(name, "offline")
        icons = {"online": "[green]●[/]", "offline": "[red]●[/]", "busy": "[yellow]●[/]"}
        icon = icons.get(status, "[red]●[/]")

        auth = node.auth_method.value if hasattr(node, 'auth_method') else "key"
        auth_icon = "[dim italic]key[/]" if auth == "key" else "[dim italic]pwd[/]"

        line = f"{cursor} {icon} {node.name} {auth_icon} [dim]{node.host}[/]"
        if selected:
            line = "[bold]" + line + "[/]"

        # 展开详情
        if self._expanded_node == node.name:
            detail_lines = [
                f"    host: {node.host}:{node.port}",
                f"    user: {node.user}",
                f"    auth: {auth}",
            ]
            if node.tags:
                detail_lines.append(f"    tags: {', '.join(node.tags)}")
            if node.groups:
                detail_lines.append(f"    groups: {', '.join(node.groups)}")
            line += "\n" + "\n".join("[dim]" + d + "[/]" for d in detail_lines)

        return line
