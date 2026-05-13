"""OpsAgent - 运维 Agent 门面，组装 wuwei 组件"""

from __future__ import annotations

import datetime
import os
from pathlib import Path

from wuwei import (
    Agent,
    AgentSession,
    ConsoleHook,
    ContextCompressionHook,
    FileStorage,
    FileSystemSkillProvider,
    HitlHook,
    LLMGateway,
    SkillHook,
    SkillManager,
    StorageHook,
    ToolRegistry,
)
from wuwei.memory.context_compressor import LLMContextCompressor
from ait.security.tui_provider import TuiApprovalProvider
from wuwei.tools.builtin.skill_tools import register_skill_tools

from ait.agent.prompts import OPS_SYSTEM_PROMPT
from ait.nodes.manager import NodeManager
from ait.tools.ssh_tools import register_ssh_tools


class OpsAgent:
    """运维 Agent 门面

    职责：组装 wuwei 组件 + 注入运维工具和安全策略。
    Agent 运行时、LLM 调用、工具执行、持久化全部交给 wuwei。
    每次启动生成新会话 ID，不复用旧会话。
    """

    def __init__(self, config_dir: Path):
        self.config_dir = config_dir
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self._session_id = f"session_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"

        # Skills 目录
        skills_dir = config_dir / "skills"
        skills_dir.mkdir(parents=True, exist_ok=True)

        # 会话存储目录
        sessions_dir = config_dir / "sessions"
        sessions_dir.mkdir(parents=True, exist_ok=True)

        # 节点管理
        self.node_manager = NodeManager(config_dir / "nodes.db")

        # LLM - 完全交给 wuwei
        # 尝试从配置或环境变量加载
        try:
            from ait.config import load_config
            config = load_config(config_dir)
            llm_config = config.llm

            # 推断 env_prefix
            base = llm_config.base_url or ""
            if "deepseek" in base:
                prefix = "DEEPSEEK"
            elif "openai" in base:
                prefix = "OPENAI"
            else:
                prefix = "DEEPSEEK"

            self.llm = LLMGateway.from_env(
                env_prefix=prefix,
                base_url=llm_config.base_url or None,
                model=llm_config.model or None,
            )
        except Exception as e:
            raise RuntimeError(
                "无法初始化 LLM 网关。请设置环境变量，例如:\n"
                "  export DEEPSEEK_API_KEY=your-key\n"
                f"原始错误: {e}"
            ) from e

        # Skills
        self.skill_provider = FileSystemSkillProvider(skill_path=str(skills_dir))
        self.skill_manager = SkillManager([self.skill_provider])

        # 工具
        self.tools = ToolRegistry.from_builtin(["time"])
        register_skill_tools(self.tools, self.skill_manager)
        register_ssh_tools(self.tools, self.node_manager)

        # 存储
        self.storage = FileStorage(str(sessions_dir))

        # TUI 审批提供者（延迟设置 screen）
        self.approval_provider = TuiApprovalProvider()

        # Agent
        self.agent = Agent(
            llm=self.llm,
            tools=self.tools,
            hooks=[
                SkillHook(),
                ContextCompressionHook(
                    compressor=LLMContextCompressor(self.llm),
                    compress_after_turns=30,
                    keep_recent_turns=10,
                ),
                StorageHook(self.storage),
                HitlHook(
                    provider=self.approval_provider,
                ),
                ConsoleHook(),
            ],
            default_system_prompt=OPS_SYSTEM_PROMPT,
            default_max_steps=20,
        )

    def set_tui_screen(self, screen) -> None:
        """设置 TUI 屏幕引用（用于弹窗审批和主机密钥确认）"""
        self.node_manager.set_screen(screen)
        self.node_manager.set_host_key_callback(screen._verify_host_key)
        self.approval_provider.set_screen(screen)

    def register_tools(self, tools: list) -> None:
        """注册额外的运维工具"""
        for tool in tools:
            from wuwei import Tool
            if isinstance(tool, Tool):
                self.tools.register(tool)
            elif callable(tool):
                self.tools.register_callable(tool)

    async def run(self, user_input: str) -> str:
        """执行一次运维对话"""
        session_id = self._session_id
        session = await self.storage.load(session_id)
        if session is None:
            session = self.agent.create_session(session_id=session_id)

        result = await self.agent.run(user_input, session=session)
        return str(result)

    def stream(self, user_input: str):
        """流式执行运维对话（异步生成器）"""
        return self.agent.stream_events(user_input, session_id=self._session_id)
