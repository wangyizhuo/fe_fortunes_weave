"""角色综合强度评级（SS~D）纯配置读取器（唯一数据源：config/character_tiers.json）。"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TIERS_PATH = ROOT / "config" / "character_tiers.json"

STRENGTH_ORDER = {"SS": 0, "S": 1, "A": 2, "B": 3, "C": 4, "D": 5}
PRIORITY_ORDER = {"P0": 0, "P1": 1, "P2": 2}
MEAL_CONFIG_PATH = ROOT / "meals" / "meal_config.json"


def get_current_lord(meal_config_path: str | Path = MEAL_CONFIG_PATH) -> str:
    p = Path(meal_config_path)
    if p.exists():
        try:
            with open(p, encoding="utf-8") as f:
                lord = json.load(f).get("current_lord")
                if lord:
                    return str(lord)
        except Exception:
            pass
    return "迪托利希"


def zh_name_key(name: str) -> bytes:
    """按 GB18030（一级汉字严格按拼音顺序）生成稳定的中文姓名排序键。"""
    return str(name or "").encode("gb18030", errors="replace")


def char_sort_key(
    name: str,
    priority: str | None = None,
    strength_tier: str | None = None,
    current_lord: str | None = None,
) -> tuple[int, int, int, bytes]:
    """统一排序键：当前主角永远第一 → P 级（P0→P1→P2）→ 综合强度（SS→S→A→B→C→D）→ 名字升序。"""
    lord = current_lord if current_lord is not None else get_current_lord()
    return (
        0 if (lord and name == lord) else 1,
        PRIORITY_ORDER.get(priority or "", 9),
        STRENGTH_ORDER.get(strength_tier or "", 9),
        zh_name_key(name),
    )


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
