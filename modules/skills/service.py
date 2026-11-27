"""技能图鉴模块服务入口：供 build_site.py 生成独立 out/data/skills.json。"""
from __future__ import annotations

from typing import Any

from .catalog import build_skills_catalog


def build_skills_data() -> dict[str, Any]:
    return build_skills_catalog()
