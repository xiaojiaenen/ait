"""SSH 连接池 - 基于 asyncssh，支持 known_hosts 验证"""
from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import Callable

import asyncssh

from ait.nodes.models import CommandResult, Node


class SSHConnectionPool:
    """异步 SSH 连接池，复用连接，自动重连，主机密钥验证"""

    def __init__(self, max_connections: int = 10, known_hosts_dir: Path | None = None):
        self._connections: dict[str, asyncssh.SSHClientConnection] = {}
        self._locks: dict[str, asyncio.Lock] = {}
        self._max_connections = max_connections
        from ait.config import get_config_dir
        self._known_hosts_dir = known_hosts_dir or get_config_dir()
        self._known_hosts_dir.mkdir(parents=True, exist_ok=True)
        self._known_hosts_path = self._known_hosts_dir / "known_hosts"
        self._host_key_callback: Callable | None = None
        self._screen = None

    def set_host_key_callback(self, callback: Callable) -> None:
        """设置主机密钥验证回调"""
        self._host_key_callback = callback

    def set_screen(self, screen) -> None:
        """设置 TUI 屏幕引用"""
        self._screen = screen

    def _key(self, node: Node) -> str:
        return f"{node.user}@{node.host}:{node.port}"

    async def get_connection(self, node: Node) -> asyncssh.SSHClientConnection:
        key = self._key(node)

        if key in self._connections:
            conn = self._connections[key]
            if not conn.is_closed():
                return conn
            del self._connections[key]

        if len(self._connections) >= self._max_connections:
            oldest = next(iter(self._connections))
            try:
                self._connections[oldest].close()
            except Exception:
                pass
            del self._connections[oldest]

        conn = await self._connect(node)
        self._connections[key] = conn
        return conn

    async def _connect(self, node: Node) -> asyncssh.SSHClientConnection:
        connect_kwargs = {
            "host": node.host,
            "port": node.port,
            "username": node.user,
            "known_hosts": str(self._known_hosts_path) if self._known_hosts_path.exists() else None,
        }

        if node.auth_method.value == "key":
            key_path = node.key_path or str(Path.home() / ".ssh" / "id_ed25519")
            connect_kwargs["client_keys"] = [key_path]
        else:
            connect_kwargs["password"] = node.password

        try:
            return await asyncssh.connect(**connect_kwargs)
        except asyncssh.HostKeyNotVerifiable as exc:
            # 未知主机密钥，需要用户确认
            if not self._host_key_callback or not self._screen:
                raise

            key = exc.server_host_key
            approved = await self._host_key_callback(
                node.host,
                key.get_fingerprint(),
                key.get_algorithm().__name__ if hasattr(key, 'get_algorithm') else "ssh-rsa",
            )

            if not approved:
                raise

            # 接受密钥后保存到 known_hosts
            self._append_known_host(node, key)
            connect_kwargs["known_hosts"] = str(self._known_hosts_path)
            return await asyncssh.connect(**connect_kwargs)

    def _append_known_host(self, node: Node, key) -> None:
        """将主机密钥追加到 known_hosts 文件"""
        import base64
        import hashlib

        line = f"{node.host} {key.get_algorithm().__name__ if hasattr(key, 'get_algorithm') else 'ssh-rsa'} {base64.b64encode(key.get_public_bytes()).decode()}\n"
        with open(self._known_hosts_path, "a") as f:
            f.write(line)

    def _wrap_command(self, node: Node, command: str) -> str:
        """根据目标 OS 选择合适的 shell 包装命令"""
        import shlex
        node_os = getattr(node, "os", "linux") or "linux"
        use_login = getattr(node, "login_shell", True)

        if node_os == "windows":
            # Windows: 不包装，直接执行（默认 shell 是 cmd）
            # 如果 AI 需要 PowerShell，它会在命令中使用 powershell -Command "..."
            return command

        # Linux / macOS
        if use_login and not command.startswith("bash "):
            return "bash -l -c " + shlex.quote(command)

        return command

    async def execute(
        self, node: Node, command: str, timeout: int = 60
    ) -> CommandResult:
        start = time.time()
        try:
            conn = await self.get_connection(node)
            # 根据目标 OS 选择 shell 包装
            command = self._wrap_command(node, command)
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
        for conn in self._connections.values():
            try:
                conn.close()
            except Exception:
                pass
        self._connections.clear()
