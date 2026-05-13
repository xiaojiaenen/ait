"""TUI 审批提供者 - 在 Textual 界面中弹窗确认危险操作，支持本次会话记住"""
from __future__ import annotations

import asyncio
import sys

from wuwei.runtime.hitl import ApprovalDecision, ApprovalProvider, ApprovalRequest

from ait.security.policy import DangerousCommandPolicy


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
        print("[HITL] screen set: {}".format(type(screen).__name__),
              file=sys.stderr, flush=True)

    async def request_approval(self, request: ApprovalRequest) -> ApprovalDecision:
        tool_name = request.payload.get("tool_name", "")
        arguments = request.payload.get("arguments", {})

        print("[HITL] request_approval CALLED: tool={}".format(tool_name),
              file=sys.stderr, flush=True)

        # 工具级敏感操作检查
        tool_level, tool_reason = self.policy.SENSITIVE_TOOLS.get(tool_name, (None, None))
        if tool_level == "confirm":
            node = arguments.get("name", "") or arguments.get("node", "")
            reason = tool_reason
            cache_key = f"{tool_name}:{node}"
            if cache_key in self._session_approved:
                print("[HITL] cached approval for {}".format(cache_key), file=sys.stderr)
                return ApprovalDecision(status="approved")
            if self.screen is None:
                print("[HITL] screen is None, rejecting", file=sys.stderr)
                return ApprovalDecision(status="rejected", reason="无法显示确认弹窗")
            print("[HITL] showing confirm dialog for {}".format(tool_name), file=sys.stderr)
            return await self._show_confirm(request, tool_name, node, reason, cache_key)

        # exec_command: 所有命令都弹窗确认（不再依赖 LLM）
        if tool_name == "exec_command":
            command = arguments.get("command", "")
            node = arguments.get("node", "")

            level, reason = self.policy.evaluate(command)
            print("[HITL] exec_command: cmd={}, level={}, reason={}".format(
                command[:50], level, reason), file=sys.stderr, flush=True)

            if level == "block":
                return ApprovalDecision(
                    status="rejected",
                    reason=f"禁止执行: {reason}"
                )

            # 安全命令自动放行
            if level == "auto":
                return ApprovalDecision(status="approved")

            # confirm 级别：弹窗
            cache_key = f"{reason}:{command[:50]}"
            if cache_key in self._session_approved:
                return ApprovalDecision(status="approved")

            if self.screen is None:
                return ApprovalDecision(status="rejected", reason="无法显示确认弹窗")

            return await self._show_confirm(request, command, node, reason, cache_key)

        # 其他工具放行
        return ApprovalDecision(status="approved")

    async def _show_confirm(
        self, request: ApprovalRequest,
        command: str, node: str, reason: str, cache_key: str
    ) -> ApprovalDecision:
        try:
            from ait.tui.widgets.confirm import show_confirm_dialog

            print("[HITL] calling show_confirm_dialog...", file=sys.stderr, flush=True)
            approved, remember = await show_confirm_dialog(
                self.screen, command, node, reason
            )
            print("[HITL] dialog result: approved={}, remember={}".format(
                approved, remember), file=sys.stderr, flush=True)
            if remember:
                self._session_approved.add(cache_key)
            if approved:
                return ApprovalDecision(status="approved")
            return ApprovalDecision(
                status="rejected", reason="用户取消"
            )
        except Exception as e:
            print("[HITL] dialog error: {}".format(e), file=sys.stderr, flush=True)
            import traceback
            traceback.print_exc(file=sys.stderr)
            return ApprovalDecision(
                status="rejected", reason=f"弹窗错误: {e}"
            )
