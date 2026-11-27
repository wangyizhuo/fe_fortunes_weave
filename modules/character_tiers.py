"""角色综合强度评级（SS~D）纯配置读取器（唯一数据源：config/character_tiers.json）。"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TIERS_PATH = ROOT / "config" / "character_tiers.json"

STRENGTH_ORDER = {"SS": 0, "S": 1, "A": 2, "B": 3, "C": 4, "D": 5}


def load_character_tiers(path: str | Path = TIERS_PATH) -> dict[str, Any]:
    p = Path(path)
    if not p.exists():
        return {"source": "", "scale": [], "priorityLinkNote": "", "characters": {}}
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def get_character_tier(name: str, tiers_data: dict[str, Any] | None = None) -> dict[str, Any]:
    data = tiers_data if tiers_data is not None else load_character_tiers()
    entry = (data.get("characters") or {}).get(name) or {}
    return {
        "strengthTier": entry.get("rating") or "",
        "pserTier": entry.get("pserTier") or "",
        "role": entry.get("role") or "",
        "defaultPriority": entry.get("defaultPriority") or "",
        "dietrichPriority": entry.get("dietrichPriority"),
        "priorityNote": entry.get("priorityNote") or "",
        "tierSummary": entry.get("summary") or "",
    }
