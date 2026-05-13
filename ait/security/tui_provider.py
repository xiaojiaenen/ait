"""TUI 审批提供者 - 在 Textual 界面中弹窗确认危险操作，支持本次会话记住"""
from __future__ import annotations

import asyncio

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

    async def request_approval(self, request: ApprovalRequest) -> ApprovalDecision:
        tool_name = request.payload.get("tool_name", "")
        arguments = request.payload.get("arguments", {})
        command = arguments.get("command", "")
        node = arguments.get("node", "")

        level, reason = self.policy.evaluate(command)

        if level == "block":
            return ApprovalDecision(
                status="rejected",
                reason=f"禁止执行: {reason}"
            )

        if level != "confirm":
            return ApprovalDecision(status="approved")

        # 检查会话缓存
        cache_key = f"{reason}:{command[:50]}"
        if cache_key in self._session_approved:
            return ApprovalDecision(status="approved")

        if self.screen is None:
            return ApprovalDecision(
                status="rejected",
                reason="无法显示确认弹窗"
            )

        return await self._show_confirm(request, command, node, reason, cache_key)

    async def _show_confirm(
        self, request: ApprovalRequest,
        command: str, node: str, reason: str, cache_key: str
    ) -> ApprovalDecision:
        try:
            from ait.tui.widgets.confirm import show_confirm_dialog

            approved, remember = await show_confirm_dialog(
                self.screen, command, node, reason
            )
            if remember:
                self._session_approved.add(cache_key)
            if approved:
                return ApprovalDecision(status="approved")
            return ApprovalDecision(
                status="rejected", reason="用户取消"
            )
        except Exception as e:
            return ApprovalDecision(
                status="rejected", reason=f"弹窗错误: {e}"
            )
