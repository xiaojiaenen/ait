"""Macro 管理器 — 从 YAML 文件加载命令模板"""
from __future__ import annotations

import yaml
from pathlib import Path

from ait.macros.models import Macro


class MacroManager:
    """加载和管理命令模板"""

    def __init__(self, macros_dir: Path):
        macros_dir.mkdir(parents=True, exist_ok=True)
        self._macros: dict[str, Macro] = {}
        self._load(macros_dir)

    def _load(self, path: Path) -> None:
        for yaml_file in path.glob("*.yaml"):
            try:
                data = yaml.safe_load(yaml_file.read_text(encoding="utf-8"))
                if data:
                    macro = Macro.model_validate(data)
                    self._macros[macro.name] = macro
            except Exception:
                continue

    def resolve(self, name: str) -> Macro | None:
        return self._macros.get(name)

    def list_all(self) -> list[Macro]:
        return list(self._macros.values())

    def list_names(self) -> list[str]:
        return list(self._macros.keys())
