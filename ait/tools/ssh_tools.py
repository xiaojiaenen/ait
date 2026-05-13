"""SSH 运维工具 - exec_command / upload / download"""

from __future__ import annotations

from ait.nodes.manager import NodeManager


def register_ssh_tools(registry, node_manager: NodeManager):
    """注册 SSH 运维工具到 wuwei ToolRegistry"""

    @registry.tool(
        name="exec_command",
        description="在指定节点上执行 Shell 命令并返回结果。节点名必须是已配置的节点。",
    )
    async def exec_command(node: str, command: str, timeout: int = 60) -> dict:
        """在远程节点上执行命令"""
        result = await node_manager.exec_command(node, command, timeout)
        return {
            "ok": result.ok,
            "node": result.node,
            "command": result.command,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "exit_code": result.exit_code,
            "duration_ms": result.duration_ms,
        }

    @registry.tool(
        name="list_nodes",
        description="列出已配置的节点。可选按标签筛选。",
    )
    def list_nodes(tags: list[str] | None = None) -> list[dict]:
        """列出节点"""
        nodes = node_manager.list_nodes(tags)
        return [
            {
                "name": n.name,
                "host": n.host,
                "port": n.port,
                "user": n.user,
                "tags": n.tags,
                "groups": n.groups,
            }
            for n in nodes
        ]

    @registry.tool(
        name="add_node",
        description="添加新的运维节点。",
    )
    def add_node(
        name: str, host: str, port: int = 22, user: str = "root",
        tags: list[str] | None = None, groups: list[str] | None = None,
    ) -> dict:
        """添加节点"""
        from ait.nodes.models import Node
        node = Node(
            name=name, host=host, port=port, user=user,
            tags=tags or [], groups=groups or [],
        )
        node_manager.add_node(node)
        return {"ok": True, "node": name}
