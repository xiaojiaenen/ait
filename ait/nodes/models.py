"""节点和分组数据模型"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class NodeStatus(str, Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    BUSY = "busy"


class AuthMethod(str, Enum):
    KEY = "key"
    PASSWORD = "password"


class Node(BaseModel):
    """远程节点配置"""

    name: str = Field(..., description="节点名称")
    host: str = Field(..., description="主机名或 IP")
    port: int = Field(default=22, description="SSH 端口")
    user: str = Field(default="root", description="SSH 用户")
    auth_method: AuthMethod = Field(default=AuthMethod.KEY, description="认证方式")
    key_path: Optional[str] = Field(default=None, description="SSH 私钥路径")
    password: Optional[str] = Field(default=None, description="SSH 密码（不推荐）")
    tags: list[str] = Field(default_factory=list, description="标签")
    groups: list[str] = Field(default_factory=list, description="所属分组")
    status: NodeStatus = Field(default=NodeStatus.OFFLINE, description="当前状态")


class Group(BaseModel):
    """节点分组"""

    name: str = Field(..., description="分组名称")
    description: str = Field(default="", description="分组描述")
    nodes: list[str] = Field(default_factory=list, description="节点名称列表")


class CommandResult(BaseModel):
    """命令执行结果"""

    node: str = Field(..., description="节点名称")
    command: str = Field(..., description="执行的命令")
    stdout: str = Field(default="", description="标准输出")
    stderr: str = Field(default="", description="标准错误")
    exit_code: int = Field(default=0, description="退出码")
    ok: bool = Field(default=True, description="是否成功")
    duration_ms: float = Field(default=0, description="执行耗时(ms)")


class NodeMetrics(BaseModel):
    """节点实时指标"""

    node: str
    cpu_percent: float = 0
    mem_percent: float = 0
    disk_percent: float = 0
    load_1min: float = 0
    load_5min: float = 0
    load_15min: float = 0
    net_rx_kbps: float = 0
    net_tx_kbps: float = 0
    uptime_hours: float = 0
    cpu_cores: int = 0
    mem_total_gb: float = 0
    mem_used_gb: float = 0
