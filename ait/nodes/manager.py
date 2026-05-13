"""NodeManager - 节点生命周期管理"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from ait.nodes.models import Group, Node, NodeStatus
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
