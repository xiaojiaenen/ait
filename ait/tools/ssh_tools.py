"""SSH 运维工具 - exec_command / upload / download"""

from __future__ import annotations

from ait.nodes.manager import NodeManager


def register_ssh_tools(registry, node_manager: NodeManager):
    """注册 SSH 运维工具到 wuwei ToolRegistry"""

    @registry.tool(
        name="exec_command",
        description="在指定节点上执行 Shell 命令。不指定节点时默认在当前机器 (localhost) 执行。",
    )
    async def exec_command(command: str, node: str = "localhost", timeout: int = 60) -> dict:
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
        description="列出已配置的节点。返回节点名、主机、OS 类型等。",
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
                "os": n.os,
                "tags": n.tags,
                "groups": n.groups,
            }
            for n in nodes
        ]

    @registry.tool(
        name="add_node",
        description="添加运维节点。os 参数指定操作系统: linux/macos/windows，默认 linux。Windows 节点建议设置 login_shell=false。",
    )
    def add_node(
        name: str, host: str, port: int = 22, user: str = "root",
        auth_method: str = "key", key_path: str | None = None,
        password: str | None = None,
        login_shell: bool = True,
        os: str = "linux",
        tags: list[str] | None = None, groups: list[str] | None = None,
    ) -> dict:
        """添加节点"""
        from ait.nodes.models import Node, AuthMethod
        method = AuthMethod.KEY if auth_method == "key" else AuthMethod.PASSWORD
        node = Node(
            name=name, host=host, port=port, user=user,
            auth_method=method, key_path=key_path, password=password,
            login_shell=login_shell, os=os,
            tags=tags or [], groups=groups or [],
        )
        node_manager.add_node(node)
        return {"ok": True, "node": name}
    @registry.tool(
        name="remove_node",
        description="删除已配置的运维节点。此操作不可逆，需要用户确认。",
    )
    def remove_node(name: str) -> dict:
        """删除节点"""
        ok = node_manager.remove_node(name)
        return {"ok": ok, "node": name}

    @registry.tool(
        name="add_group",
        description="创建节点分组。",
    )
    def add_group(name: str, description: str = "") -> dict:
        """创建分组"""
        return node_manager.add_group(name, description)

    @registry.tool(
        name="list_groups",
        description="列出所有节点分组。",
    )
    def list_groups() -> list[dict]:
        """列出分组"""
        return node_manager.list_groups()

    @registry.tool(
        name="add_node_to_group",
        description="将节点添加到分组。",
    )
    def add_node_to_group(node: str, group: str) -> dict:
        """将节点添加到分组"""
        return node_manager.add_node_to_group(node, group)

    @registry.tool(
        name="batch_exec",
        description="在多个节点上并发执行相同的命令。node_names 是节点名称列表。",
    )
    async def batch_exec(node_names: list[str], command: str, timeout: int = 60) -> dict:
        """多节点并发执行命令"""
        results = await node_manager.batch_exec(node_names, command, timeout)
        return {
            name: {
                "ok": r.ok,
                "stdout": r.stdout,
                "stderr": r.stderr,
                "exit_code": r.exit_code,
            }
            for name, r in results.items()
        }
    @registry.tool(
        name="upload_file",
        description="上传本地文件到远程节点。local_path 必须是本地存在的文件路径。",
    )
    async def upload_file(node: str, local_path: str, remote_path: str) -> dict:
        """上传文件到远程节点"""
        try:
            from pathlib import Path
            local = Path(local_path).expanduser()
            if not local.exists():
                return {"ok": False, "error": f"本地文件不存在: {local_path}"}

            target = node_manager.get_node(node)
            if target is None:
                return {"ok": False, "error": f"节点不存在: {node}"}

            conn = await node_manager.pool.get_connection(target)
            async with conn.start_sftp_client() as sftp:
                await sftp.put(str(local), remote_path)

            return {"ok": True, "node": node, "remote_path": remote_path}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    @registry.tool(
        name="download_file",
        description="从远程节点下载文件到本地。",
    )
    async def download_file(node: str, remote_path: str, local_path: str) -> dict:
        """从远程节点下载文件"""
        try:
            from pathlib import Path
            local = Path(local_path).expanduser()

            target = node_manager.get_node(node)
            if target is None:
                return {"ok": False, "error": f"节点不存在: {node}"}

            conn = await node_manager.pool.get_connection(target)
            async with conn.start_sftp_client() as sftp:
                await sftp.get(remote_path, str(local))

            return {"ok": True, "node": node, "local_path": str(local)}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    @registry.tool(
        name="get_metrics",
        description="获取节点的实时系统指标 (CPU%/内存%/磁盘%/负载)。不指定节点时默认获取当前机器指标。",
    )
    async def get_metrics(node: str = "localhost") -> dict:
        """获取节点实时指标"""
        from ait.health.metrics import MetricsCollector
        collector = MetricsCollector(node_manager)
        metrics = await collector.collect(node)
        if metrics is None:
            return {"ok": False, "error": "采集失败"}
        return metrics.model_dump()


