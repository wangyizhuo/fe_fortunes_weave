"""道具 / 材料采集 · 数据服务层（生成标准化 items.json）。"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .catalog import build_catalog

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = ROOT / "config" / "items_config.json"
DEFAULT_WEAPON_TIERS = ROOT / "config" / "weapon_tier_ref.json"


def build_items_data(config_path: str | Path = DEFAULT_CONFIG) -> dict[str, Any]:
    cfg_path = Path(config_path)
    with open(cfg_path, encoding="utf-8") as f:
        cfg = json.load(f)
    weapons_tsv = ROOT / cfg["weaponsTsv"]
    wt_ref = None
    if DEFAULT_WEAPON_TIERS.exists():
        with open(DEFAULT_WEAPON_TIERS, encoding="utf-8") as f:
            wt_ref = json.load(f)
    cat = build_catalog(cfg, weapons_tsv, weapon_tiers=wt_ref)
    return {
        "module": "items",
        "schemaVersion": 2,
        "categories": cat["categories"],
        "towns": cat["towns"],
        "barter": cat["barter"],
        "materials": cat["materials"],
        "weaponTiers": cat["weaponTiers"],
        "notes": cat["notes"],
        "sources": cat["sources"],
        "summary": {
            "townCount": len(cat["towns"]),
            "shopItemCount": sum(len(t["items"]) for t in cat["towns"]),
            "barterCount": len(cat["barter"]),
            "materialCount": len(cat["materials"]),
            "ratedWeaponCount": len((cat["weaponTiers"] or {}).get("weapons") or []),
        },
    }
