"""SSH 连接池 - 基于 asyncssh"""

from __future__ import annotations

import asyncio
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator, Optional

import asyncssh

from ait.nodes.models import CommandResult, Node


class SSHConnectionPool:
    """异步 SSH 连接池，复用连接，自动重连"""

    def __init__(self, max_connections: int = 10):
        self._connections: dict[str, asyncssh.SSHClientConnection] = {}
        self._locks: dict[str, asyncio.Lock] = {}
        self._max_connections = max_connections

    def _key(self, node: Node) -> str:
        return f"{node.user}@{node.host}:{node.port}"

    async def get_connection(self, node: Node) -> asyncssh.SSHClientConnection:
        """获取或创建 SSH 连接"""
        key = self._key(node)

        if key in self._connections:
            conn = self._connections[key]
            if not conn.is_closed():
                return conn
            del self._connections[key]

        # 限流
        if len(self._connections) >= self._max_connections:
            oldest = next(iter(self._connections))
            self._connections[oldest].close()
            del self._connections[oldest]

        conn = await self._connect(node)
        self._connections[key] = conn
        return conn

    async def _connect(self, node: Node) -> asyncssh.SSHClientConnection:
        """建立新的 SSH 连接"""
        if node.auth_method.value == "key":
            key_path = node.key_path or str(Path.home() / ".ssh" / "id_ed25519")
            return await asyncssh.connect(
                node.host,
                port=node.port,
                username=node.user,
                client_keys=[key_path],
                known_hosts=None,
            )
        else:
            return await asyncssh.connect(
                node.host,
                port=node.port,
                username=node.user,
                password=node.password,
                known_hosts=None,
            )

    async def execute(
        self, node: Node, command: str, timeout: int = 60
    ) -> CommandResult:
        """在节点上执行命令"""
        start = time.time()
        try:
            conn = await self.get_connection(node)
            result = await asyncio.wait_for(
                conn.run(command),
                timeout=timeout,
            )
            duration_ms = (time.time() - start) * 1000
            return CommandResult(
                node=node.name,
                command=command,
                stdout=result.stdout or "",
                stderr=result.stderr or "",
                exit_code=result.exit_status or 0,
                ok=(result.exit_status or 0) == 0,
                duration_ms=duration_ms,
            )
        except asyncio.TimeoutError:
            duration_ms = (time.time() - start) * 1000
            return CommandResult(
                node=node.name,
                command=command,
                stderr=f"命令执行超时 ({timeout}s)",
                exit_code=-1,
                ok=False,
                duration_ms=duration_ms,
            )
        except Exception as e:
            duration_ms = (time.time() - start) * 1000
            return CommandResult(
                node=node.name,
                command=command,
                stderr=str(e),
                exit_code=-1,
                ok=False,
                duration_ms=duration_ms,
            )

    async def close_all(self) -> None:
        """关闭所有连接"""
        for conn in self._connections.values():
            conn.close()
        self._connections.clear()
