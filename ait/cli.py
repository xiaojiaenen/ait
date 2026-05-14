"""ait CLI 入口"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from ait.config import get_config_dir

app = typer.Typer(
    name="ait",
    help="AI 智能运维终端 - 用自然语言管理服务器",
    no_args_is_help=False,
)


def _config_dir_callback(value: str | None) -> Path:
    """解析配置目录路径"""
    if value is None:
        return get_config_dir()
    return Path(value).expanduser()


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    config_dir: Annotated[
        str | None,
        typer.Option("--config-dir", "-c", help="配置目录路径"),
    ] = None,
) -> None:
    """启动 ait 运维终端"""
    if ctx.invoked_subcommand is not None:
        return

    from ait.app import launch

    path = _config_dir_callback(config_dir)
    launch(config_dir=path)


@app.command()
def version() -> None:
    """显示版本信息"""
    try:
        from importlib.metadata import version as get_version
        ver = get_version("ait")
    except Exception:
        ver = "dev"
    typer.echo(f"ait {ver}")


@app.command()
def nodes() -> None:
    """管理节点（WIP）"""
    typer.echo("节点管理功能开发中...")


@app.command()
def skills() -> None:
    """管理 Skills（WIP）"""
    typer.echo("Skills 管理功能开发中...")


if __name__ == "__main__":
    app()
