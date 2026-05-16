"""本地文件工具 — 无 workspace 限制，支持绝对路径和相对路径"""
from __future__ import annotations

import os
import shutil
from pathlib import Path

from wuwei.tools.registry import ToolRegistry

DEFAULT_READ_LIMIT = 20_000
MAX_LIST_DEPTH = 3


def _resolve(path: str) -> Path:
    p = Path(path).expanduser()
    if p.is_absolute():
        return p.resolve()
    return Path.cwd().joinpath(p).resolve()


def register_local_file_tools(registry: ToolRegistry) -> None:

    @registry.tool(
        name="read_file",
        description="读取本地文件内容。支持绝对路径和相对路径，默认最多返回 20000 字符。",
    )
    def read_file(path: str, max_chars: int = DEFAULT_READ_LIMIT) -> dict:
        target = _resolve(path)
        if not target.exists():
            return {"ok": False, "error": f"文件不存在: {path}"}
        if target.is_dir():
            return {"ok": False, "error": f"路径是目录而非文件: {path}"}
        text = target.read_text(encoding="utf-8")
        truncated = len(text) > max_chars
        content = text[:max_chars] if truncated else text
        return {
            "ok": True,
            "path": str(target),
            "size_chars": len(text),
            "content": content,
            "truncated": truncated,
        }

    @registry.tool(
        name="write_file",
        description="写入本地文本文件。支持绝对路径和相对路径。overwrite=true 时覆盖已有文件。",
    )
    def write_file(path: str, content: str, overwrite: bool = False) -> dict:
        target = _resolve(path)
        if target.exists() and target.is_dir():
            return {"ok": False, "error": f"路径是目录: {path}"}
        if target.exists() and not overwrite:
            return {"ok": False, "error": f"文件已存在，设置 overwrite=true 覆盖: {path}"}
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return {"ok": True, "path": str(target), "bytes": len(content.encode("utf-8"))}

    @registry.tool(
        name="append_file",
        description="向本地文件末尾追加内容。支持绝对路径和相对路径。文件不存在时会创建。",
    )
    def append_file(path: str, content: str) -> dict:
        target = _resolve(path)
        if target.exists() and target.is_dir():
            return {"ok": False, "error": f"路径是目录: {path}"}
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("a", encoding="utf-8") as f:
            f.write(content)
        return {"ok": True, "path": str(target), "bytes": len(content.encode("utf-8"))}

    @registry.tool(
        name="list_dir",
        description="列出本地目录内容。支持绝对路径和相对路径。",
    )
    def list_dir(path: str) -> dict:
        target = _resolve(path)
        if not target.exists():
            return {"ok": False, "error": f"目录不存在: {path}"}
        if not target.is_dir():
            return {"ok": False, "error": f"路径不是目录: {path}"}
        entries = []
        for p in sorted(target.iterdir()):
            entry = {
                "name": p.name,
                "type": "dir" if p.is_dir() else "file",
            }
            if p.is_file():
                entry["size"] = p.stat().st_size
            entries.append(entry)
        return {"ok": True, "path": str(target), "entries": entries}

    @registry.tool(
        name="delete_file",
        description="删除本地文件。只删除文件，不删除目录。",
    )
    def delete_file(path: str) -> dict:
        target = _resolve(path)
        if not target.exists():
            return {"ok": False, "error": f"文件不存在: {path}"}
        if target.is_dir():
            return {"ok": False, "error": f"路径是目录，只允许删除文件: {path}"}
        target.unlink()
        return {"ok": True, "path": str(target), "deleted": True}

    @registry.tool(
        name="copy_file",
        description="复制本地文件或目录。",
    )
    def copy_file(src: str, dst: str) -> dict:
        src_path = _resolve(src)
        dst_path = _resolve(dst)
        if not src_path.exists():
            return {"ok": False, "error": f"源文件不存在: {src}"}
        dst_path.parent.mkdir(parents=True, exist_ok=True)
        if src_path.is_dir():
            shutil.copytree(str(src_path), str(dst_path), dirs_exist_ok=True)
        else:
            shutil.copy2(str(src_path), str(dst_path))
        return {"ok": True, "src": str(src_path), "dst": str(dst_path)}

    @registry.tool(
        name="file_to_md",
        description="将文件（docx/xlsx/pptx/pdf/html/csv 等）转换为 Markdown 文本。",
    )
    def file_to_md(path: str) -> str:
        from markitdown import MarkItDown
        target = _resolve(path)
        if not target.is_file():
            return f"文件不存在: {path}"
        try:
            md = MarkItDown()
            result = md.convert(str(target))
        except Exception as e:
            return f"转换失败: {e}"
        if result is None or not result.text_content.strip():
            return "转换结果为空"
        return result.text_content

    @registry.tool(
        name="replace_in_file",
        description="在本地文件中查找并替换文本。old_str 替换为 new_str，count=-1 表示全部替换。",
    )
    def replace_in_file(path: str, old_str: str, new_str: str, count: int = -1) -> dict:
        if not old_str:
            return {"ok": False, "error": "old_str 不能为空"}
        target = _resolve(path)
        if not target.is_file():
            return {"ok": False, "error": f"文件不存在: {path}"}
        text = target.read_text(encoding="utf-8")
        occurrences = text.count(old_str)
        if occurrences == 0:
            return {"ok": False, "error": "未找到匹配内容"}
        n = occurrences if count < 0 else min(count, occurrences)
        updated = text.replace(old_str, new_str, n)
        target.write_text(updated, encoding="utf-8")
        return {"ok": True, "path": str(target), "replacements": n}

    @registry.tool(
        name="list_files",
        description="递归列出目录文件树，最多 3 层深度。忽略 .git node_modules __pycache__ .DS_Store 等。",
    )
    def list_files(path: str) -> dict:
        target = _resolve(path)
        if not target.exists():
            return {"ok": False, "error": f"路径不存在: {path}"}
        if not target.is_dir():
            return {"ok": False, "error": f"路径不是目录: {path}"}

        skip_dirs = {".git", "node_modules", "__pycache__", ".venv", "venv",
                     ".idea", ".vscode", ".claude", "egg-info", ".eggs",
                     ".mypy_cache", ".pytest_cache", ".ruff_cache"}

        def _walk(dir_path: Path, depth: int) -> list[dict]:
            if depth > MAX_LIST_DEPTH:
                return []
            entries = []
            try:
                items = sorted(dir_path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
            except PermissionError:
                return []
            for p in items:
                name = p.name
                if name in skip_dirs or name.startswith(".") and name not in (".env.example",):
                    continue
                entry = {"name": name, "type": "dir" if p.is_dir() else "file"}
                if p.is_file():
                    entry["size"] = p.stat().st_size
                elif p.is_dir():
                    children = _walk(p, depth + 1)
                    if children:
                        entry["children"] = children
                entries.append(entry)
            return entries

        tree = _walk(target, 0)
        return {"ok": True, "path": str(target), "tree": tree}
