"""技能面板 — 展示 Skills 和 Macros"""
from __future__ import annotations

from textual.containers import Vertical
from textual.widgets import Static


class SkillsPanel(Vertical):
    """技能和宏列表面板"""

    def __init__(self):
        super().__init__(id="skills-panel")

    def compose(self):
        yield Static("[bold]技能 & 宏[/]", id="skills-title")
        yield Static("(加载中...)", id="skills-list")

    def reload_list(self, skills: list[dict] | None = None, macros: list[dict] | None = None) -> None:
        """刷新列表"""
        lines = []
        if macros:
            lines.append("[bold]命令模板[/]")
            for m in macros:
                lines.append(f"  /{m.get('name', '')} [dim]{m.get('description', '')}[/]")
            lines.append("")
        if skills:
            lines.append("[bold]运维技能[/]")
            for s in skills:
                lines.append(f"  ● {s.get('name', '')} [dim]{s.get('description', '')}[/]")
        if not lines:
            lines.append("[dim](暂无)[/]")
        self.query_one("#skills-list", Static).update("\n".join(lines))
