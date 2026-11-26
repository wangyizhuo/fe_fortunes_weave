"""友好度培养 · 数据服务层（生成标准化 affinity.json）。"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .planner import plan_meals

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = ROOT / "meals" / "meal_config.json"
DEFAULT_TAB = ROOT / "meals" / "diet_tab.json"


def build_affinity_data(
    config_path: str | Path = DEFAULT_CONFIG,
    tab_path: str | Path = DEFAULT_TAB,
) -> dict[str, Any]:
    with open(config_path, encoding="utf-8") as f:
        cfg = json.load(f)
    plan = plan_meals(cfg, tab_path)
    return {
        "module": "affinity",
        "schemaVersion": 1,
        "lord": cfg.get("current_lord"),
        "dishes": plan["dishes"],
        "weights": plan["weights"],
        "maxed": cfg.get("maxed", []),
        "absent": cfg.get("absent", []),
        "pairsDone": cfg.get("pairs_done", []),
        "goals": [g.get("why", "") for g in cfg.get("goals", [])],
    }
