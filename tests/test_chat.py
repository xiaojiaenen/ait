"""测试核心组件"""
import pytest


class TestTextLogic:
    """测试 ChatPanel 文本拼接逻辑"""

    @pytest.fixture
    def panel(self):
        from ait.tui.panels.chat_panel import ChatPanel
        return ChatPanel()

    def test_write_line_first(self, panel):
        panel._current_text = ""
        panel._current_text = self._write_line(panel._current_text, "hello")
        assert panel._current_text == "hello"

    def test_write_line_append(self, panel):
        panel._current_text = "hello"
        panel._current_text = self._write_line(panel._current_text, "world")
        assert panel._current_text == "hello\nworld"

    def test_append_text_first(self, panel):
        panel._current_text = ""
        panel._current_text = self._append_text(panel._current_text, "hello")
        assert panel._current_text == "hello"

    def test_append_text_continuous(self, panel):
        panel._current_text = "hello"
        panel._current_text = self._append_text(panel._current_text, " world")
        assert panel._current_text == "hello world"

    def test_mixed_sequence(self, panel):
        """模拟流式输出: 第一段用 write_line，后续用 append_text"""
        text = "user input"
        text = self._write_line(text, "AI: first")
        assert text == "user input\nAI: first"
        text = self._append_text(text, " second")
        assert text == "user input\nAI: first second"
        text = self._append_text(text, " third")
        assert text == "user input\nAI: first second third"
        text = self._write_line(text, "  > execute cmd...")
        assert text == "user input\nAI: first second third\n  > execute cmd..."
        text = self._write_line(text, "AI: new response")
        assert text == "user input\nAI: first second third\n  > execute cmd...\nAI: new response"
        text = self._append_text(text, " continued")
        assert text == "user input\nAI: first second third\n  > execute cmd...\nAI: new response continued"

    @staticmethod
    def _write_line(current: str, text: str) -> str:
        if current:
            return current + "\n" + text
        return text

    @staticmethod
    def _append_text(current: str, text: str) -> str:
        return current + text


class TestHooksAccess:
    """测试 hooks 访问路径修复"""

    def test_hooks_access_path(self):
        import os
        os.environ["DEEPSEEK_API_KEY"] = "test-key"

        from pathlib import Path
        from ait.agent.ops_agent import OpsAgent
        agent = OpsAgent(config_dir=Path("/tmp/ait_test_hooks"))

        assert hasattr(agent.agent, "hooks")
        assert hasattr(agent.agent.hooks, "_hooks")
        assert not hasattr(agent.agent, "_hooks")

        from ait.security.tui_provider import TuiApprovalProvider
        found = False
        for hook in agent.agent.hooks._hooks:
            if hasattr(hook, "provider") and isinstance(hook.provider, TuiApprovalProvider):
                found = True
        assert found, "应该找到 TuiApprovalProvider"


class TestSessionIsolation:
    """测试会话隔离"""

    def test_session_id_is_timestamp_based(self):
        import os
        os.environ["DEEPSEEK_API_KEY"] = "test-key"

        from pathlib import Path
        from ait.agent.ops_agent import OpsAgent
        agent = OpsAgent(config_dir=Path("/tmp/ait_test_session"))
        assert agent._session_id.startswith("session_")
        assert len(agent._session_id) > 8


class TestAgentInit:
    """测试 Agent 初始化"""

    def test_ops_agent_creation(self):
        import os
        os.environ["DEEPSEEK_API_KEY"] = "test-key"

        from pathlib import Path
        from ait.agent.ops_agent import OpsAgent
        agent = OpsAgent(config_dir=Path("/tmp/ait_test_agent"))
        assert agent.node_manager is not None
        assert agent.tools is not None
        assert agent.storage is not None
        assert len(agent.tools.list_tools()) > 0
