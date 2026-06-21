# 应用版本号读取工具
"""Application version helpers."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
import sys

import tomllib


def _read_pyproject_version() -> str:
    """从 pyproject.toml 回退读取版本号"""
    candidates = [
        Path(__file__).resolve().with_name("pyproject.toml"),
        Path(getattr(sys, "_MEIPASS", "")).resolve() / "pyproject.toml"
        if getattr(sys, "_MEIPASS", "")
        else None,
        Path(sys.executable).resolve().parent / "pyproject.toml",
        Path.cwd() / "pyproject.toml",
    ]
    for candidate in candidates:
        if candidate and candidate.is_file():
            with candidate.open("rb") as fh:
                data = tomllib.load(fh)
            return str(data["project"]["version"])
    raise FileNotFoundError("pyproject.toml not found for version fallback")


def get_app_version() -> str:
    """返回已安装包的版本号，失败时回退到 pyproject.toml"""
    try:
        return version("bilitickerbuy")
    except PackageNotFoundError:
        return _read_pyproject_version()
