"""NodeManager - 节点生命周期管理"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from ait.nodes.models import Node, NodeStatus
from ait.nodes.ssh import SSHConnectionPool


class NodeManager:
    """管理节点配置和连接"""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.pool = SSHConnectionPool()
        self._init_db()

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
            "tags TEXT DEFAULT '[]', "
            "groups TEXT DEFAULT '[]', "
            "created_at TEXT DEFAULT (datetime('now'))"
            ")"
        )
        db.execute(sql)
        db.commit()
        db.close()

    def add_node(self, node: Node):
        db = sqlite3.connect(str(self.db_path))
        db.execute(
            "INSERT OR REPLACE INTO nodes VALUES (?,?,?,?,?,?,?,?,datetime('now'))",
            (node.name, node.host, node.port, node.user,
             node.auth_method.value, node.key_path,
             json.dumps(node.tags), json.dumps(node.groups)),
        )
        db.commit()
        db.close()
        return node

    def remove_node(self, name: str) -> bool:
        db = sqlite3.connect(str(self.db_path))
        cursor = db.execute("DELETE FROM nodes WHERE name = ?", (name,))
        db.commit()
        deleted = cursor.rowcount > 0
        db.close()
        return deleted

    def list_nodes(self, tags=None):
        db = sqlite3.connect(str(self.db_path))
        rows = db.execute("SELECT * FROM nodes").fetchall()
        db.close()
        nodes = []
        for row in rows:
            node_tags = json.loads(row[6])
            if tags and not any(t in node_tags for t in tags):
                continue
            nodes.append(Node(
                name=row[0], host=row[1], port=row[2], user=row[3],
                auth_method=row[4], key_path=row[5],
                tags=node_tags, groups=json.loads(row[7]),
            ))
        return nodes

    def get_node(self, name: str):
        db = sqlite3.connect(str(self.db_path))
        row = db.execute("SELECT * FROM nodes WHERE name = ?", (name,)).fetchone()
        db.close()
        if row is None:
            return None
        return Node(
            name=row[0], host=row[1], port=row[2], user=row[3],
            auth_method=row[4], key_path=row[5],
            tags=json.loads(row[6]), groups=json.loads(row[7]),
        )

    async def exec_command(self, node_name: str, command: str, timeout: int = 60):
        from ait.nodes.models import CommandResult
        node = self.get_node(node_name)
        if node is None:
            return CommandResult(node=node_name, command=command,
                stderr="节点不存在: " + node_name, exit_code=-1, ok=False)
        return await self.pool.execute(node, command, timeout)

    async def health_check(self, node_name: str):
        node = self.get_node(node_name)
        if node is None:
            return NodeStatus.OFFLINE
        try:
            result = await self.pool.execute(node, "echo ok", timeout=5)
            return NodeStatus.ONLINE if result.ok else NodeStatus.OFFLINE
        except Exception:
            return NodeStatus.OFFLINE

    async def close(self) -> None:
        await self.pool.close_all()
