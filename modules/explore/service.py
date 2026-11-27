"""探索规划模块服务入口：供 build_site.py 生成独立 out/data/explore.json。"""
from __future__ import annotations

from typing import Any

from .planner import build_explore_plan


def build_explore_data() -> dict[str, Any]:
    return build_explore_plan()
