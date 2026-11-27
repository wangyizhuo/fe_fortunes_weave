"""友好度培养 · 数据服务层（生成标准化 affinity.json，含主角与待挖角名册）。"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from modules.character_tiers import get_character_tier, load_character_tiers
from .planner import build_roster, plan_meals

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = ROOT / "meals" / "meal_config.json"
DEFAULT_TAB = ROOT / "meals" / "diet_tab.json"
DEFAULT_ROUTE_CONFIG = ROOT / "config" / "route_config.json"


def _load_current_renown() -> int | None:
    if not DEFAULT_ROUTE_CONFIG.exists():
        return None
    with open(DEFAULT_ROUTE_CONFIG, encoding="utf-8") as f:
        return json.load(f).get("renown")


def _enrich_tier(entry: dict[str, Any], tiers_data: dict[str, Any]) -> dict[str, Any]:
    t = get_character_tier(entry.get("name", ""), tiers_data)
    return {
        **entry,
        "strengthTier": t["strengthTier"],
        "pserTier": t["pserTier"],
        "role": t["role"],
        "defaultPriority": t["defaultPriority"],
    }


def build_affinity_data(
    config_path: str | Path = DEFAULT_CONFIG,
    tab_path: str | Path = DEFAULT_TAB,
) -> dict[str, Any]:
    with open(config_path, encoding="utf-8") as f:
        cfg = json.load(f)
    plan = plan_meals(cfg, tab_path)
    roster_info = build_roster(tab_path, cfg, current_renown=_load_current_renown())
    tiers_data = load_character_tiers()
    lords = [_enrich_tier(l, tiers_data) for l in roster_info["lords"]]
    roster = [_enrich_tier(r, tiers_data) for r in roster_info["roster"]]
    return {
        "module": "affinity",
        "schemaVersion": 2,
        "lord": cfg.get("current_lord"),
        "currentRenown": roster_info["currentRenown"],
        "lords": lords,
        "roster": roster,
        "dishes": plan["dishes"],
        "weights": plan["weights"],
        "maxed": cfg.get("maxed", []),
        "absent": cfg.get("absent", []),
        "pairsDone": cfg.get("pairs_done", []),
        "goals": [g.get("why", "") for g in cfg.get("goals", [])],
    }
