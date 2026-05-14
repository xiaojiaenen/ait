"""NodeManager - 节点生命周期管理"""

from __future__ import annotations

import asyncio
import json
import sqlite3
import time
from pathlib import Path

from ait.nodes.models import Node, NodeStatus, CommandResult
from ait.nodes.ssh import SSHConnectionPool

LOCALHOST = "localhost"


class NodeManager:
    """管理节点配置和连接"""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        config_dir = db_path.parent
        self.pool = SSHConnectionPool(known_hosts_dir=config_dir)
        self._init_db()
        self._init_groups_db()

    @staticmethod
    def _localhost_node() -> Node:
        import getpass
        import sys
        if sys.platform == "darwin":
            node_os = "macos"
        elif sys.platform in ("win32", "cygwin"):
            node_os = "windows"
        else:
            node_os = "linux"
        return Node(
            name=LOCALHOST,
            host="127.0.0.1",
            port=22,
            user=getpass.getuser(),
            os=node_os,
            tags=["local", "builtin"],
        )

    def set_host_key_callback(self, callback) -> None:
        """设置主机密钥确认回调"""
        self.pool.set_host_key_callback(callback)

    def set_screen(self, screen) -> None:
        """设置 TUI 屏幕引用"""
        self.pool.set_screen(screen)

    def _init_db(self) -> None:
        db = sqlite3.connect(str(self.db_path))
        sql = (
            "CREATE TABLE IF NOT EXISTS nodes ("
            "name TEXT PRIMARY KEY, "
            "host TEXT NOT NULL, "
            "port INTEGER DEFAULT 22, "
            "username TEXT DEFAULT 'root', "
            "auth_method TEXT DEFAULT 'key', "
            "key_path TEXT, "
            "password TEXT, "
            "login_shell INTEGER DEFAULT 1, "
            "os TEXT DEFAULT 'linux', "
            "tags TEXT DEFAULT '[]', "
            "groups TEXT DEFAULT '[]', "
            "created_at TEXT DEFAULT (datetime('now'))"
            ")"
        )
        db.execute(sql)
        db.commit()
        # 兼容旧表
        for col in ["password TEXT", "login_shell INTEGER DEFAULT 1", "os TEXT DEFAULT 'linux'"]:
            try:
                db.execute("ALTER TABLE nodes ADD COLUMN " + col)
                db.commit()
            except sqlite3.OperationalError:
                pass
        db.close()

    def add_node(self, node: Node):
        if node.name == LOCALHOST:
            return node  # localhost 是内置节点，不允许覆盖
        db = sqlite3.connect(str(self.db_path))
        db.execute(
            "INSERT OR REPLACE INTO nodes "
            "(name, host, port, username, auth_method, key_path, password, login_shell, os, tags, groups, created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,datetime('now'))",
            (node.name, node.host, node.port, node.user,
             node.auth_method.value, node.key_path, node.password,
             1 if node.login_shell else 0,
             node.os,
             json.dumps(node.tags), json.dumps(node.groups)),
        )
        db.commit()
        db.close()
        return node

    def remove_node(self, name: str) -> bool:
        if name == LOCALHOST:
            return False  # 不允许删除内置 localhost 节点
        db = sqlite3.connect(str(self.db_path))
        cursor = db.execute("DELETE FROM nodes WHERE name = ?", (name,))
        db.commit()
        deleted = cursor.rowcount > 0
        db.close()
        return deleted

    def list_nodes(self, tags=None):
        db = sqlite3.connect(str(self.db_path))
        db.row_factory = sqlite3.Row
        rows = db.execute("SELECT * FROM nodes").fetchall()
        db.close()
        nodes = [self._localhost_node()]  # 本地节点始终排在第一位
        for row in rows:
            try:
                node_tags = json.loads(row["tags"])
            except (json.JSONDecodeError, TypeError):
                node_tags = []
            if not isinstance(node_tags, list):
                node_tags = []
            if tags and not any(t in node_tags for t in tags):
                continue
            try:
                groups = json.loads(row["groups"])
            except (json.JSONDecodeError, TypeError):
                groups = []
            if not isinstance(groups, list):
                groups = []
            nodes.append(Node(
                name=row["name"], host=row["host"], port=row["port"],
                user=row["username"],
                auth_method=row["auth_method"], key_path=row["key_path"],
                password=row["password"],
                login_shell=bool(row["login_shell"]) if "login_shell" in row.keys() else True,
                os=row["os"] if "os" in row.keys() else "linux",
                tags=node_tags, groups=groups,
            ))
        return nodes

    def get_node(self, name: str):
        if name == LOCALHOST:
            return self._localhost_node()
        db = sqlite3.connect(str(self.db_path))
        db.row_factory = sqlite3.Row
        row = db.execute("SELECT * FROM nodes WHERE name = ?", (name,)).fetchone()
        db.close()
        if row is None:
            return None
        try:
            node_tags = json.loads(row["tags"])
        except (json.JSONDecodeError, TypeError):
            node_tags = []
        if not isinstance(node_tags, list):
            node_tags = []
        try:
            groups = json.loads(row["groups"])
        except (json.JSONDecodeError, TypeError):
            groups = []
        if not isinstance(groups, list):
            groups = []
        return Node(
            name=row["name"], host=row["host"], port=row["port"],
            user=row["username"],
            auth_method=row["auth_method"], key_path=row["key_path"],
            password=row["password"],
            login_shell=bool(row["login_shell"]) if "login_shell" in row.keys() else True,
            os=row["os"] if "os" in row.keys() else "linux",
            tags=node_tags, groups=groups,
        )

    async def exec_command(self, node_name: str, command: str, timeout: int = 60):
        if node_name == LOCALHOST:
            return await self._exec_local(command, timeout)
        node = self.get_node(node_name)
        if node is None:
            return CommandResult(node=node_name, command=command,
                stderr="节点不存在: " + node_name, exit_code=-1, ok=False)
        return await self.pool.execute(node, command, timeout)

    async def _exec_local(self, command: str, timeout: int = 60) -> CommandResult:
        """在本地机器上执行命令（subprocess，不走 SSH）"""
        start = time.time()
        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=timeout
            )
            duration_ms = (time.time() - start) * 1000
            return CommandResult(
                node=LOCALHOST,
                command=command,
                stdout=stdout.decode("utf-8", errors="replace") if stdout else "",
                stderr=stderr.decode("utf-8", errors="replace") if stderr else "",
                exit_code=proc.returncode or 0,
                ok=(proc.returncode or 0) == 0,
                duration_ms=duration_ms,
            )
        except asyncio.TimeoutError:
            duration_ms = (time.time() - start) * 1000
            return CommandResult(
                node=LOCALHOST, command=command,
                stderr=f"命令执行超时 ({timeout}s)", exit_code=-1, ok=False,
                duration_ms=duration_ms,
            )
        except Exception as e:
            duration_ms = (time.time() - start) * 1000
            return CommandResult(
                node=LOCALHOST, command=command,
                stderr=str(e), exit_code=-1, ok=False,
                duration_ms=duration_ms,
            )

    async def health_check(self, node_name: str):
        if node_name == LOCALHOST:
            return NodeStatus.ONLINE  # 本地机器始终在线
        node = self.get_node(node_name)
        if node is None:
            return NodeStatus.OFFLINE
        try:
            result = await self.pool.execute(node, "echo ok", timeout=5)
            return NodeStatus.ONLINE if result.ok else NodeStatus.OFFLINE
        except Exception:
            return NodeStatus.OFFLINE


    # -- 分组管理 --

    def _init_groups_db(self) -> None:
        db = sqlite3.connect(str(self.db_path))
        db.execute("""CREATE TABLE IF NOT EXISTS groups (
            name TEXT PRIMARY KEY,
            description TEXT DEFAULT '',
            nodes TEXT DEFAULT '[]',
            created_at TEXT DEFAULT (datetime('now'))
        )""")
        db.commit()
        db.close()

    def add_group(self, name: str, description: str = "") -> dict:
        db = sqlite3.connect(str(self.db_path))
        db.execute(
            "INSERT OR REPLACE INTO groups VALUES (?,?,?,datetime('now'))",
            (name, description, "[]"),
        )
        db.commit()
        db.close()
        return {"ok": True, "group": name}

    def list_groups(self):
        db = sqlite3.connect(str(self.db_path))
        try:
            rows = db.execute("SELECT * FROM groups").fetchall()
            result = []
            for row in rows:
                result.append({
                    "name": row[0],
                    "description": row[1],
                    "nodes": json.loads(row[2]),
                })
            return result
        except sqlite3.OperationalError:
            self._init_groups_db()
            return []
        finally:
            db.close()

    def add_node_to_group(self, node_name: str, group_name: str):
        db = sqlite3.connect(str(self.db_path))
        row = db.execute("SELECT * FROM groups WHERE name = ?", (group_name,)).fetchone()
        if row is None:
            db.close()
            return {"ok": False, "error": f"分组不存在: {group_name}"}
        nodes = json.loads(row[2])
        if node_name not in nodes:
            nodes.append(node_name)
            db.execute(
                "UPDATE groups SET nodes = ? WHERE name = ?",
                (json.dumps(nodes), group_name),
            )
            db.commit()
        db.close()
        return {"ok": True, "group": group_name, "nodes": nodes}

    def list_nodes_by_group(self, group_name: str):
        db = sqlite3.connect(str(self.db_path))
        row = db.execute("SELECT * FROM groups WHERE name = ?", (group_name,)).fetchone()
        db.close()
        if row is None:
            return []
        node_names = json.loads(row[2])
        result = []
        for name in node_names:
            node = self.get_node(name)
            if node:
                result.append(node)
        return result

    # -- 批量执行 --

    async def batch_exec(self, node_names: list[str], command: str, timeout: int = 60):
        """多节点并发执行命令"""
        import asyncio
        results = {}
        tasks = []
        for name in node_names:
            tasks.append(self.exec_command(name, command, timeout))
        outputs = await asyncio.gather(*tasks, return_exceptions=True)
        for name, output in zip(node_names, outputs):
            if isinstance(output, Exception):
                from ait.nodes.models import CommandResult
                results[name] = CommandResult(
                    node=name, command=command,
                    stderr=str(output), exit_code=-1, ok=False,
                )
            else:
                results[name] = output
        return results

    async def close(self) -> None:
        await self.pool.close_all()
