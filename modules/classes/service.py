"""职业图鉴模块服务入口：供 build_site.py 生成独立的 out/data/classes.json。"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .catalog import DEFAULT_CLASSES_PATH, load_classes_catalog


def build_classes_data(classes_path: str | Path = DEFAULT_CLASSES_PATH) -> dict[str, Any]:
    return load_classes_catalog(classes_path)
