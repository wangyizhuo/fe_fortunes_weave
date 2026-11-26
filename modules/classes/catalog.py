"""职业图鉴 · 纯数据整理逻辑（整理自 fire-emblem-fw.site/classes.html 与 fireemblem.top/archive/classes）。"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CLASSES_PATH = ROOT / "levelup" / "rng" / "fw_classes.json"

TIER_ORDER: tuple[str, ...] = ("基础", "初级", "中级", "上级", "最上级", "神将")

# 来源：fireemblem.top/archive/classes（基础 15 / 初级 30 / 中级 60 / 上级 100 / 最上级 150 / 神将 200）
TIER_MASTERY_EXP: dict[str, int] = {
    "基础": 15,
    "初级": 30,
    "中级": 60,
    "上级": 100,
    "最上级": 150,
    "神将": 200,
}

SKILL_GROUPS: list[dict[str, Any]] = [
    {
        "key": "weapon",
        "label": "武器 / 魔法技能",
        "skills": ["剑术", "枪术", "斧术", "箭术", "格斗术", "黑魔术", "白魔术"],
    },
    {
        "key": "move",
        "label": "兵种 / 移动技能",
        "skills": ["步兵术", "重装术", "马术", "飞行术"],
    },
]

ALL_SKILLS: list[str] = [s for g in SKILL_GROUPS for s in g["skills"]]


def load_classes_catalog(classes_path: str | Path = DEFAULT_CLASSES_PATH) -> dict[str, Any]:
    """加载并规范化全职业数据，按阶级顺序排列并补充精通 EXP 与技能分布汇总。"""
    with open(classes_path, encoding="utf-8") as f:
        raw_list: list[dict[str, Any]] = json.load(f)

    tier_rank = {t: i for i, t in enumerate(TIER_ORDER)}
    ordered = sorted(
        enumerate(raw_list),
        key=lambda pair: (tier_rank.get(pair[1].get("tier") or "", 99), pair[0]),
    )

    normalized: list[dict[str, Any]] = []
    tier_counts: dict[str, int] = {t: 0 for t in TIER_ORDER}
    skill_counts: dict[str, int] = {s: 0 for s in ALL_SKILLS}

    for _, raw in ordered:
        tier = raw.get("tier") or "其他"
        usable = list(raw.get("usableSkills") or [])
        tier_counts[tier] = tier_counts.get(tier, 0) + 1
        for sk in usable:
            skill_counts[sk] = skill_counts.get(sk, 0) + 1

        mastery_exp = raw.get("masteryExp")
        if mastery_exp is None:
            mastery_exp = TIER_MASTERY_EXP.get(tier)

        normalized.append({
            "id": raw.get("id") or "",
            "name": raw["name"],
            "tier": tier,
            "tierKey": raw.get("tierKey") or "",
            "limit": raw.get("limit"),
            "family": raw.get("family"),
            "unitType": raw.get("unitType"),
            "move": raw.get("move"),
            "usableSkills": usable,
            "requirement": raw.get("requirement") or "—",
            "unlock": raw.get("unlock"),
            "skillExp": raw.get("skillExp"),
            "growth": raw.get("growth") or {},
            "growthTotal": raw.get("growthTotal", 0),
            "growthLv": raw.get("growthLv") or [],
            "growthLvNote": raw.get("growthLvNote"),
            "baseStats": raw.get("baseStats") or {},
            "minStats": raw.get("minStats") or {},
            "innate": list(raw.get("innate") or []),
            "mastery": raw.get("mastery") or "—",
            "masteryExp": mastery_exp,
        })

    tiers_meta = [
        {"tier": t, "count": tier_counts.get(t, 0), "masteryExp": TIER_MASTERY_EXP.get(t)}
        for t in TIER_ORDER
        if tier_counts.get(t, 0) > 0
    ]

    return {
        "schemaVersion": 1,
        "module": "classes",
        "sources": [
            {"name": "fire-emblem-fw.site 职业一览", "url": "https://fire-emblem-fw.site/classes.html"},
            {"name": "fireemblem.top 兵种图鉴", "url": "https://fireemblem.top/archive/classes"},
        ],
        "tierOrder": list(TIER_ORDER),
        "tiers": tiers_meta,
        "skillGroups": SKILL_GROUPS,
        "summary": {
            "classCount": len(normalized),
            "tierCount": len(tiers_meta),
            "skillCount": len(ALL_SKILLS),
            "tierCounts": tier_counts,
            "skillCounts": skill_counts,
        },
        "classes": normalized,
    }
