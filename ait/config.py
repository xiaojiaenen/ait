"""配置管理 — Pydantic 模型 + TOML 加载"""

from __future__ import annotations

import os
from pathlib import Path

from pydantic import BaseModel, Field


class LLMConfig(BaseModel):
    """LLM 配置（传给 wuwei LLMGateway.from_env）"""
    api_key: str = Field(default="${DEEPSEEK_API_KEY}")
    base_url: str = Field(default="https://api.deepseek.com")
    model: str = Field(default="deepseek-chat")


class TUIConfig(BaseModel):
    """TUI 配置"""
    theme: str = Field(default="dark")


class NodeDefaults(BaseModel):
    """节点默认配置"""
    default_user: str = Field(default="ops")
    default_port: int = Field(default=22)
    key_path: str = Field(default="~/.ssh/id_ed25519")
    connect_timeout: int = Field(default=10)
    command_timeout: int = Field(default=60)


class SecurityRule(BaseModel):
    """自定义安全规则"""
    pattern: str
    level: str = "confirm"
    description: str = ""


class SecurityConfig(BaseModel):
    """安全配置"""
    custom_rules: list[SecurityRule] = Field(default_factory=list)


class SkillsConfig(BaseModel):
    """Skills 配置"""
    auto_generate: bool = Field(default=True)
    min_steps: int = Field(default=3)
    path: str = Field(default="~/.ait/skills")


class AitConfig(BaseModel):
    """ait 主配置"""
    llm: LLMConfig = Field(default_factory=LLMConfig)
    tui: TUIConfig = Field(default_factory=TUIConfig)
    nodes: NodeDefaults = Field(default_factory=NodeDefaults)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    skills: SkillsConfig = Field(default_factory=SkillsConfig)


def _expand_env(value: str) -> str:
    """展开环境变量引用 ${VAR_NAME}"""
    import re

    def replacer(match):
        var_name = match.group(1)
        return os.environ.get(var_name, "")

    return re.sub(r"\$\{(\w+)\}", replacer, value)


def load_config(config_dir: Path) -> AitConfig:
    """加载配置

    优先级：config.toml > 默认值
    """
    config_path = config_dir / "config.toml"

    if config_path.exists():
        import tomllib

        raw = tomllib.loads(config_path.read_text(encoding="utf-8"))
        config = AitConfig.model_validate(raw)
    else:
        config = AitConfig()

    # 展开环境变量
    if "${" in config.llm.api_key:
        config.llm.api_key = _expand_env(config.llm.api_key)

    return config


def save_default_config(config_dir: Path) -> Path:
    """生成默认配置文件"""
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / "config.toml"

    if config_path.exists():
        return config_path

    content = """# ait 配置文件

[llm]
api_key = "${DEEPSEEK_API_KEY}"
base_url = "https://api.deepseek.com"
model = "deepseek-chat"

[tui]
theme = "dark"

[nodes]
default_user = "ops"
default_port = 22
key_path = "~/.ssh/id_ed25519"
connect_timeout = 10
command_timeout = 60

[security]
# [[security.custom_rules]]
# pattern = "kubectl delete ns"
# level = "confirm"
# description = "删除 K8s 命名空间"

[skills]
auto_generate = true
min_steps = 3
path = "~/.ait/skills"
"""
    config_path.write_text(content, encoding="utf-8")
    return config_path
