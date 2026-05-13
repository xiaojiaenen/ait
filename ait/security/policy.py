"""危险命令安全策略"""
from __future__ import annotations

import re

from wuwei.runtime import ApprovalPolicy


SAFE_COMMAND_PATTERNS = [
    # 只读/查询类
    r"^(ls|ll|dir|cat|head|tail|less|more)\b",
    r"^(echo|printf|date|whoami|hostname|uname|pwd)\b",
    r"^(ps|top|htop|pgrep|pidof|free|df|du|uptime|w|who|last)\b",
    r"^(ip|ifconfig|ss|netstat|ping|traceroute|nslookup|dig|host|curl|wget)\b",
    r"^(systemctl\s+(status|is-active|is-enabled|list-units|show))\b",
    r"^(journalctl\b(?!.*--vacuum))",
    r"^(docker\s+(ps|images|inspect|logs|stats|info|version))\b",
    r"^(kubectl\s+(get|describe|logs|top|explain|api-resources))\b",
    r"^(git\s+(status|log|diff|show|branch|tag|remote))\b",
    r"^(grep|find|which|whereis|locate|stat|file|wc|sort|uniq)\b",
    r"^(id|groups|env|printenv|ulimit)\b",
    # 条件性安全
    r"^(crontab\s+-l)\b",
    r"^(service\s+\S+\s+status)\b",
]

BLOCK_PATTERNS = [
    (r"\brm\s+.*-rf\s+/",              "递归删除根目录"),
    (r"\bdd\s+if=",                     "磁盘直接写入"),
    (r"\bmkfs\.",                       "格式化文件系统"),
    (r"\bchmod\s+.*-R\s+777\s+/",      "递归开放全部权限"),
    (r">\s*/dev/sd[a-z]",              "覆写磁盘设备"),
]

CONFIRM_PATTERNS = [
    (r"\brm\s+.*-rf\b",                "递归强制删除"),
    (r"\brm\s+-rf\b",                  "递归强制删除"),
    (r"\bsystemctl\s+(restart|stop|disable|mask)\b", "系统服务启停"),
    (r"\bkill\s+-9",                    "强制终止进程"),
    (r"\biptables\s+-[ADILF]",         "防火墙规则变更"),
    (r"\breboot|shutdown|init\s+[06]", "系统关机/重启"),
    (r"\bmount|umount",                "挂载/卸载文件系统"),
    (r"\buseradd|userdel|usermod",     "用户账号管理"),
    (r"\bpasswd\b",                    "修改密码"),
    (r"\bchmod\s+777",                 "开放全部文件权限"),
    (r"\bchown\s+-R",                  "递归修改所有者"),
    (r"\bdocker\s+(rm|stop|kill|restart|prune)", "容器删除/停止/清理"),
    (r"\bkubectl\s+(delete|apply|patch|scale|rollout)", "K8s 资源变更"),
    (r"\bpip\s+(uninstall|install)",   "Python 包管理"),
    (r"\bapt\s+(remove|purge|install)", "系统包管理"),
    (r"\byum\s+(remove|install|update)", "系统包管理"),
    (r"\bnpm\s+(uninstall|install\s+-g)", "Node 包管理"),
    (r"\bcrontab\s+-e",                "编辑定时任务"),
    (r"\bsed\s+.*-i",                  "文件就地修改"),
    (r"\bchkconfig\s+(on|off|reset)",  "服务自启动配置"),
]

SENSITIVE_TOOLS = {
    "remove_node": ("confirm", "删除运维节点"),
    "add_node": ("confirm", "添加运维节点"),
}


class DangerousCommandPolicy(ApprovalPolicy):
    """运维危险命令审批策略"""

    SENSITIVE_TOOLS = SENSITIVE_TOOLS

    def __init__(self, custom_rules=None):
        super().__init__()
        self._safe_patterns = [re.compile(p, re.IGNORECASE) for p in SAFE_COMMAND_PATTERNS]

    def evaluate(self, command: str) -> tuple:
        """评估命令风险级别

        Returns:
            ("auto", "")          - 安全白名单，自动放行
            ("confirm", reason)   - 需确认
            ("block", reason)     - 禁止
            ("unknown", "")       - 未识别，默认需确认
        """
        # 先检查 block 级别
        for pattern, description in BLOCK_PATTERNS:
            if re.search(pattern, command, re.IGNORECASE):
                return ("block", description)

        # 已知安全命令
        for pattern in self._safe_patterns:
            if pattern.search(command.strip()):
                return ("auto", "")

        # 已知危险命令
        for pattern, description in CONFIRM_PATTERNS:
            if re.search(pattern, command, re.IGNORECASE):
                return ("confirm", description)

        # 未识别命令 → 需确认
        return ("confirm", "未识别的命令，请确认安全后执行")

    def requires_tool_approval(self, tool_call, *, session, task=None, tool=None) -> bool:
        """实现 wuwei ApprovalPolicy 接口"""
        import sys
        tool_name = tool_call.function.name

        # 工具级敏感操作
        if tool_name in SENSITIVE_TOOLS:
            print("[POLICY] {} in SENSITIVE_TOOLS -> True".format(tool_name), file=sys.stderr)
            return True

        # exec_command 按命令内容匹配
        if tool_name != "exec_command":
            return False

        command = tool_call.function.arguments.get("command", "")
        level, reason = self.evaluate(command)

        # block → 触发审批(provider 中会拒绝)
        # confirm → 触发审批弹窗
        # unknown → 触发审批弹窗
        # auto → 放行
        result = level != "auto"
        print("[POLICY] '{}': level={}, reason={}, needs_approval={}".format(
            command[:50], level, reason, result), file=sys.stderr)
        return result
