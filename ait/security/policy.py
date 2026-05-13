"""危险命令安全策略"""

from __future__ import annotations

import re

from wuwei.runtime import ApprovalPolicy


# 默认危险命令规则: (正则模式, 风险级别, 描述)
DEFAULT_DANGER_RULES = [
    # block 级别 - 直接拒绝
    (r"\brm\s+.*-rf\s+/",              "block",   "递归删除根目录"),
    (r"\bdd\s+if=",                     "block",   "磁盘直接写入"),
    (r"\bmkfs\.",                       "block",   "格式化文件系统"),
    (r"\bchmod\s+.*-R\s+777\s+/",      "block",   "递归开放全部权限"),
    # confirm 级别 - 弹窗确认
    (r"\bsystemctl\s+(restart|stop)",   "confirm", "系统服务启停"),
    (r"\bkill\s+-9",                    "confirm", "强制终止进程"),
    (r"\biptables\s+-[ADILF]",           "confirm", "防火墙规则变更"),
    (r"\breboot|shutdown|init\s+[06]",   "confirm", "系统关机/重启"),
    (r"\bmount|umount",                  "confirm", "挂载/卸载文件系统"),
    (r"\buseradd|userdel|usermod",        "confirm", "用户账号管理"),
    (r"\bchmod\s+777",                  "confirm", "开放全部文件权限"),
    (r"\bdocker\s+(rm|stop|kill)",       "confirm", "容器删除/停止"),
    (r"\bkubectl\s+delete",              "confirm", "K8s 资源删除"),
]


class DangerousCommandPolicy(ApprovalPolicy):
    """运维危险命令审批策略

    继承 wuwei ApprovalPolicy，对 exec_command 工具的命令做风险评估。
    """

    def __init__(self, custom_rules=None):
        super().__init__()
        self.rules = custom_rules or DEFAULT_DANGER_RULES

    def evaluate(self, command: str) -> tuple:
        """评估命令风险级别

        Returns:
            ("auto", "")          - 安全
            ("confirm", reason)   - 需确认
            ("block", reason)     - 禁止
        """
        for pattern, level, description in self.rules:
            if re.search(pattern, command, re.IGNORECASE):
                return (level, description)
        return ("auto", "")

    def requires_tool_approval(self, tool_call, *, session, task=None) -> bool:
        """实现 wuwei ApprovalPolicy 接口"""
        if tool_call.function.name != "exec_command":
            return False

        command = tool_call.function.arguments.get("command", "")
        level, _ = self.evaluate(command)
        return level in ("confirm", "block")
