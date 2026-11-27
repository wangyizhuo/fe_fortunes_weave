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


STAT_KEYS: tuple[str, ...] = ("hp", "str", "mag", "spd", "dex", "def", "res", "lck", "cha")
STAT_LABELS: tuple[str, ...] = ("HP", "力", "魔", "速", "技", "防", "魔防", "幸", "魅")
STAT_KEY_TO_LABEL: dict[str, str] = dict(zip(STAT_KEYS, STAT_LABELS))

ADVANTAGE_ALGORITHM = (
    "综合得分 S(k) = 成长率补正(%) + 5 × 职业常驻加成(baseStats)（每 +1 常驻加成折合 +5% 成长率）；"
    "相对同阶级均值差 Δ(k) = S(k) − 同阶级均值(k)。"
    "优势属性：S(k) ≥ 门槛（基础/初级 5，中级及以上 10）且（Δ(k) ≥ 4 或 S(k) ≥ 25），按 Δ(k) 取前 3 项；"
    "劣势属性：S(k) < 0，或 S(k) ≤ 0 且 Δ(k) ≤ -10，按 S(k) 升序取前 3 项。"
)


def _composite_stat_score(raw: dict[str, Any], key: str) -> float:
    g = (raw.get("growth") or {}).get(key, 0) or 0
    b = (raw.get("baseStats") or {}).get(key, 0) or 0
    return float(g + 5 * b)


def compute_class_stat_profiles(raw_list: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """按同阶级横向对比 + 成长/加成综合得分，为每个职业计算优势属性与劣势属性。"""
    by_tier: dict[str, list[dict[str, Any]]] = {}
    for c in raw_list:
        by_tier.setdefault(c.get("tier") or "其他", []).append(c)

    tier_avg: dict[str, dict[str, float]] = {}
    for t, arr in by_tier.items():
        n = max(1, len(arr))
        tier_avg[t] = {k: sum(_composite_stat_score(c, k) for c in arr) / n for k in STAT_KEYS}

    profiles: dict[str, dict[str, Any]] = {}
    for c in raw_list:
        t = c.get("tier") or "其他"
        scores = {k: _composite_stat_score(c, k) for k in STAT_KEYS}
        diffs = {k: scores[k] - tier_avg[t][k] for k in STAT_KEYS}
        min_pos = 5.0 if t in ("基础", "初级") else 10.0

        adv_keys = [k for k in STAT_KEYS if scores[k] >= min_pos and (diffs[k] >= 4.0 or scores[k] >= 25.0)]
        adv_keys.sort(key=lambda k: (-diffs[k], -scores[k]))
        adv_keys = adv_keys[:3]

        weak_keys = [k for k in STAT_KEYS if scores[k] < 0 or (scores[k] <= 0 and diffs[k] <= -10.0)]
        weak_keys.sort(key=lambda k: (scores[k], diffs[k]))
        weak_keys = weak_keys[:3]

        profiles[c["name"]] = {
            "advantageStats": [STAT_KEY_TO_LABEL[k] for k in adv_keys],
            "disadvantageStats": [STAT_KEY_TO_LABEL[k] for k in weak_keys],
            "statScores": {STAT_KEY_TO_LABEL[k]: int(scores[k]) for k in STAT_KEYS},
        }
    return profiles


def load_classes_catalog(classes_path: str | Path = DEFAULT_CLASSES_PATH) -> dict[str, Any]:
    """加载并规范化全职业数据，按阶级顺序排列并补充精通 EXP、技能分布与优势/劣势属性。"""
    with open(classes_path, encoding="utf-8") as f:
        raw_list: list[dict[str, Any]] = json.load(f)

    profiles = compute_class_stat_profiles(raw_list)

    tier_rank = {t: i for i, t in enumerate(TIER_ORDER)}
    ordered = sorted(
        enumerate(raw_list),
        key=lambda pair: (tier_rank.get(pair[1].get("tier") or "", 99), pair[0]),
    )

    normalized: list[dict[str, Any]] = []
    tier_counts: dict[str, int] = {t: 0 for t in TIER_ORDER}
    skill_counts: dict[str, int] = {s: 0 for s in ALL_SKILLS}
    advantage_counts: dict[str, int] = {s: 0 for s in STAT_LABELS}

    for _, raw in ordered:
        tier = raw.get("tier") or "其他"
        usable = list(raw.get("usableSkills") or [])
        tier_counts[tier] = tier_counts.get(tier, 0) + 1
        for sk in usable:
            skill_counts[sk] = skill_counts.get(sk, 0) + 1

        prof = profiles.get(raw["name"]) or {"advantageStats": [], "disadvantageStats": [], "statScores": {}}
        for st_lbl in prof["advantageStats"]:
            advantage_counts[st_lbl] = advantage_counts.get(st_lbl, 0) + 1

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
            "advantageStats": prof["advantageStats"],
            "disadvantageStats": prof["disadvantageStats"],
            "statScores": prof["statScores"],
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
        "schemaVersion": 2,
        "module": "classes",
        "sources": [
            {"name": "fire-emblem-fw.site 职业一览", "url": "https://fire-emblem-fw.site/classes.html"},
            {"name": "fireemblem.top 兵种图鉴", "url": "https://fireemblem.top/archive/classes"},
        ],
        "tierOrder": list(TIER_ORDER),
        "tiers": tiers_meta,
        "skillGroups": SKILL_GROUPS,
        "statLabels": list(STAT_LABELS),
        "advantageAlgorithm": ADVANTAGE_ALGORITHM,
        "summary": {
            "classCount": len(normalized),
            "tierCount": len(tiers_meta),
            "skillCount": len(ALL_SKILLS),
            "tierCounts": tier_counts,
            "skillCounts": skill_counts,
            "advantageCounts": advantage_counts,
        },
        "classes": normalized,
    }
