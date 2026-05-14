"""TUI 审批提供者 - 在 Textual 界面中弹窗确认危险操作，支持本次会话记住"""
from __future__ import annotations

import asyncio
import datetime

from wuwei.runtime.hitl import ApprovalDecision, ApprovalProvider, ApprovalRequest

from ait.security.policy import DangerousCommandPolicy

from ait.config import get_log_path

LOG_PATH = get_log_path("approval.log")


def _log(msg: str) -> None:
    """追加写入审批日志"""
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        ts = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
        with open(LOG_PATH, "a") as f:
            f.write(f"[{ts}] {msg}\n")
    except Exception:
        pass


class TuiApprovalProvider(ApprovalProvider):
    """在 TUI 中弹出确认对话框的审批提供者"""

    def __init__(self, screen=None):
        self.screen = screen
        self._pending: dict[str, asyncio.Event] = {}
        self._decisions: dict[str, ApprovalDecision] = {}
        self.policy = DangerousCommandPolicy()
        self._session_approved: set[str] = set()

    def set_screen(self, screen):
        self.screen = screen
        _log(f"screen set: {type(screen).__name__}")

    async def request_approval(self, request: ApprovalRequest) -> ApprovalDecision:
        tool_name = request.payload.get("tool_name", "")
        arguments = request.payload.get("arguments", {})

        _log(f"request_approval: tool={tool_name}, args={ {k: str(v)[:80] for k, v in arguments.items()} }")

        # 工具级敏感操作检查
        tool_level, tool_reason = self.policy.SENSITIVE_TOOLS.get(tool_name, (None, None))
        if tool_level == "confirm":
            node = arguments.get("name", "") or arguments.get("node", "")
            reason = tool_reason
            cache_key = f"{tool_name}:{node}"
            if cache_key in self._session_approved:
                _log(f"cached approval: {cache_key} → approved")
                return ApprovalDecision(status="approved")
            if self.screen is None:
                _log("screen is None → rejected")
                return ApprovalDecision(status="rejected", reason="无法显示确认弹窗")
            _log(f"showing confirm dialog for tool: {tool_name} node={node}")
            decision = await self._show_confirm(request, tool_name, node, reason, cache_key)
            _log(f"dialog result: status={decision.status}, reason={decision.reason}")
            return decision

        # exec_command: 所有命令都弹窗确认（不再依赖 LLM）
        if tool_name == "exec_command":
            command = arguments.get("command", "")
            node = arguments.get("node", "")

            level, reason = self.policy.evaluate(command)
            _log(f"exec_command: cmd={command[:80]}, level={level}, reason={reason}")

            if level == "block":
                _log(f"blocked: {reason} → rejected")
                return ApprovalDecision(
                    status="rejected",
                    reason=f"禁止执行: {reason}"
                )

            if level == "auto":
                _log("auto-approved (safe command) → approved")
                return ApprovalDecision(status="approved")

            cache_key = f"{reason}:{command[:50]}"
            if cache_key in self._session_approved:
                _log(f"cached approval: {cache_key} → approved")
                return ApprovalDecision(status="approved")

            if self.screen is None:
                _log("screen is None → rejected")
                return ApprovalDecision(status="rejected", reason="无法显示确认弹窗")

            decision = await self._show_confirm(request, command, node, reason, cache_key)
            _log(f"dialog result: status={decision.status}, reason={decision.reason}")
            return decision

        # 其他工具放行
        _log(f"tool {tool_name} not in SENSITIVE_TOOLS and not exec_command → auto-approved")
        return ApprovalDecision(status="approved")

    async def _show_confirm(
        self, request: ApprovalRequest,
        command: str, node: str, reason: str, cache_key: str
    ) -> ApprovalDecision:
        try:
            from ait.tui.widgets.confirm import show_confirm_dialog

            _log(f"_show_confirm: cmd={str(command)[:80]}, node={node}, reason={reason}")
            approved, remember = await show_confirm_dialog(
                self.screen, command, node, reason
            )
            _log(f"_show_confirm returned: approved={approved}, remember={remember}")
            if remember:
                self._session_approved.add(cache_key)
                _log(f"remembered cache_key={cache_key}")
            if approved:
                return ApprovalDecision(status="approved")
            return ApprovalDecision(
                status="rejected", reason="用户取消"
            )
        except Exception as e:
            _log(f"dialog error: {e}")
            import traceback
            _log(traceback.format_exc())
            return ApprovalDecision(
                status="rejected", reason=f"弹窗错误: {e}"
            )
