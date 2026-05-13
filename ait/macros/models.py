"""Macro 数据模型"""
from __future__ import annotations

from pydantic import BaseModel, Field


class Macro(BaseModel):
    """命令模板"""
    name: str = Field(..., description="宏名称，用于 /name 触发")
    description: str = Field(default="", description="描述")
    command: str = Field(..., description="执行的命令")
    target: str = Field(default="", description="目标节点/分组")
    confirm: bool = Field(default=False, description="是否需要确认")
