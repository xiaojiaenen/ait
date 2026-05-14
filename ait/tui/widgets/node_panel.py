"""节点管理侧边栏"""

from __future__ import annotations

from pathlib import Path

from textual.widgets import Static, Label
from textual.containers import Vertical


class NodePanel(Vertical):
    """节点管理侧边栏，默认隐藏"""

    def __init__(self, config_dir: Path):
        super().__init__(id="node-panel")
        self.config_dir = config_dir

    def compose(self):
        yield Label("[bold]节点列表[/]", id="node-panel-title")
        yield Static("(空)", id="node-list")
        yield Label("[dim]Ctrl+N 关闭[/]", id="node-panel-help")

    def on_mount(self) -> None:
        self.display = False
        self.refresh_nodes()

    def toggle(self) -> None:
        self.visible = not self.visible
        self.display = self.visible
        if self.visible:
            self.refresh_nodes()

    def refresh_nodes(self) -> None:
        try:
            from ait.nodes.manager import NodeManager
            nm = NodeManager(db_path=self.config_dir / "nodes.db")
            nodes = nm.list_nodes()
            groups = nm.list_groups()
        except Exception:
            nodes = []
            groups = []

        node_list = self.query_one("#node-list", Static)

        if not nodes and not groups:
            node_list.update("[dim](暂无节点)[/]")
            return

        lines = []

        # Show groups first
        if groups:
            for g in groups:
                g_nodes = g.get("nodes", [])
                online_count = sum(1 for n in g_nodes if n)
                lines.append(f"[bold]{g['name']}[/] ([dim]{online_count}[/])")
                for node_name in g_nodes:
                    node = nm.get_node(node_name)
                    if node:
                        icon = "[green]O[/]"
                        lines.append(f"  {icon} {node.name}")
                        lines.append(f"    [dim]{node.host}[/]")
                lines.append("")

        # Then ungrouped nodes
        grouped_node_names = set()
        for g in groups:
            grouped_node_names.update(g.get("nodes", []))

        ungrouped = [n for n in nodes if n.name not in grouped_node_names]
        if ungrouped:
            lines.append("[bold]未分组[/]")
            for n in ungrouped:
                icon = "[green]O[/]"
                lines.append(f"  {icon} {n.name}")
                lines.append(f"    [dim]{n.user}@{n.host}:{n.port}[/]")
                if n.tags:
                    tags_str = ", ".join(n.tags)
                    lines.append(f"    [dim italic]{tags_str}[/]")

        node_list.update("\n".join(lines))
