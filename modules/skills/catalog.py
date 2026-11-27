"""技能图鉴核心构建逻辑（纯函数式数据聚合，严禁硬编码评级表）。"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from modules.character_tiers import (
    PRIORITY_ORDER,
    STRENGTH_ORDER,
    get_character_tier,
    load_character_tiers,
    zh_name_key,
)

ROOT = Path(__file__).resolve().parents[2]

DISCIPLINES = [
    "剑术", "枪术", "斧术", "箭术", "格斗术",
    "黑魔术", "白魔术", "指挥术",
    "步兵术", "重装术", "马术", "飞行术",
]

RANK_ORDER = {
    r: i for i, r in enumerate(["E", "E+", "D", "D+", "C", "C+", "B", "B+", "A", "A+", "S", "S+"])
}

TIER_ORDER = {"S": 0, "A": 1, "B": 2, "C": 3}

CATEGORY_ORDER = [
    "个人特技", "角色等级特技", "职业精通", "职业固有",
    "熟练度特技", "战技", "黑魔术", "白魔术", "血印",
]


def _load_json(path: Path) -> Any:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _parse_lv_skills_fallback(raw: list[str]) -> list[tuple[str, str]]:
    """解析部分角色（如救世主）交替排列的 lvSkills 字符串数组。"""
    out: list[tuple[str, str]] = []
    i = 0
    while i < len(raw):
        name = str(raw[i]).strip()
        cond = ""
        if i + 1 < len(raw) and (str(raw[i + 1]).startswith("（") or str(raw[i + 1]).startswith("(")):
            cond = str(raw[i + 1]).strip("（）() ")
            i += 2
        else:
            i += 1
        if name and not name.startswith("（") and not name.startswith("("):
            out.append((name, cond))
    return out


def _dietrich_route_names() -> set[str]:
    path = ROOT / "meals" / "diet_tab.json"
    if not path.exists():
        return set()
    rows = _load_json(path)
    out = set()
    for r in rows[1:]:
        if len(r) >= 9 and r[8]:
            out.add(str(r[8]).strip())
    return out


def build_skills_catalog() -> dict[str, Any]:
    chars_raw: list[dict[str, Any]] = _load_json(ROOT / "levelup" / "rng" / "fw_characters.json")
    classes_raw: list[dict[str, Any]] = _load_json(ROOT / "levelup" / "rng" / "fw_classes.json")
    skills_cfg: dict[str, Any] = _load_json(ROOT / "config" / "skills_config.json")
    ref_path = ROOT / "config" / "community_skills_ref.json"
    ref_data: dict[str, Any] = _load_json(ref_path) if ref_path.exists() else {"skills": {}, "charEnMap": {}}
    meal_cfg: dict[str, Any] = _load_json(ROOT / "meals" / "meal_config.json")

    recruited_list: list[str] = list(meal_cfg.get("recruited") or [])
    recruited_set = set(recruited_list)
    recruited_rank = {n: i for i, n in enumerate(recruited_list)}
    dietrich_set = _dietrich_route_names() | recruited_set

    ref_skills: dict[str, dict[str, Any]] = ref_data.get("skills") or {}
    char_en_map: dict[str, str] = ref_data.get("charEnMap") or {}
    ratings_cfg: dict[str, dict[str, str]] = skills_cfg.get("ratings") or {}
    char_notes_cfg: dict[str, str] = skills_cfg.get("charNotes") or {}
    default_tier: str = skills_cfg.get("defaultTier") or "B"

    # skill_name -> accumulator
    entries: dict[str, dict[str, Any]] = {}

    def ensure_skill(name: str, category: str, discipline: str = "角色") -> dict[str, Any]:
        if name not in entries:
            ref = ref_skills.get(name) or {}
            rt = ratings_cfg.get(name) or {}
            entries[name] = {
                "name": name,
                "enName": ref.get("enName", ""),
                "category": category,
                "categories": [category],
                "discipline": discipline,
                "disciplines": [discipline] if discipline else [],
                "rating": rt.get("tier") or default_tier,
                "ratedExplicit": name in ratings_cfg,
                "review": rt.get("note", ""),
                "effect": ref.get("effect", ""),
                "params": ref.get("params") or None,
                "classSources": [],
                "charSources": [],
            }
        else:
            e = entries[name]
            if category not in e["categories"]:
                e["categories"].append(category)
            if discipline and discipline not in e["disciplines"]:
                e["disciplines"].append(discipline)
                if e["discipline"] in ("角色", "职业", "") and discipline in DISCIPLINES:
                    e["discipline"] = discipline
        return entries[name]

    # 1) 职业精通 & 职业固有（通用获取来源）
    for cl in classes_raw:
        cname = cl.get("name", "")
        ctier = cl.get("tier", "")
        mexp = cl.get("masteryExp")
        mastery = cl.get("mastery")
        if mastery:
            e = ensure_skill(mastery, "职业精通", "职业")
            e["classSources"].append({
                "cls": cname,
                "tier": ctier,
                "how": "精通",
                "masteryExp": mexp,
            })
        for inn in (cl.get("innate") or []):
            e = ensure_skill(inn, "职业固有", "职业")
            e["classSources"].append({
                "cls": cname,
                "tier": ctier,
                "how": "固有",
                "masteryExp": None,
            })

    # 2) 全角色个人特技 / 等级特技 / 血印 / 12 项熟练度习得（特技、战技、黑魔术、白魔术）
    char_matrix_acc: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))

    for c in chars_raw:
        ch_name = c.get("name", "")
        is_rec = ch_name in recruited_set

        # 个人特技
        ps = c.get("personalSkill")
        if isinstance(ps, dict) and ps.get("name"):
            e = ensure_skill(ps["name"], "个人特技", "角色")
            if ps.get("text"):
                e["effect"] = ps["text"]
            e["charSources"].append({
                "char": ch_name,
                "recruited": is_rec,
                "how": "个人特技",
                "discipline": "角色",
                "rank": "",
                "lv": None,
            })

        # 血印
        for bm in (c.get("bloodMarks") or []):
            if isinstance(bm, dict) and bm.get("name"):
                e = ensure_skill(bm["name"], "血印", "角色")
                if bm.get("text"):
                    e["effect"] = bm["text"]
                e["charSources"].append({
                    "char": ch_name,
                    "recruited": is_rec,
                    "how": "血印",
                    "discipline": "角色",
                    "rank": "",
                    "lv": None,
                })

        # 等级习得特技（lvLearn / lvSkills）
        seen_lv = set()
        for item in (c.get("lvLearn") or []):
            if isinstance(item, dict) and item.get("name"):
                nm = item["name"]
                seen_lv.add(nm)
                e = ensure_skill(nm, "角色等级特技", "角色")
                e["charSources"].append({
                    "char": ch_name,
                    "recruited": is_rec,
                    "how": f"Lv{item['lv']}" if item.get("lv") else "等级习得",
                    "discipline": "角色",
                    "rank": "",
                    "lv": item.get("lv"),
                })
        for nm, cond in _parse_lv_skills_fallback(c.get("lvSkills") or []):
            if nm in seen_lv:
                continue
            m_lv = re.search(r"Lv(\d+)", cond)
            lv_val = int(m_lv.group(1)) if m_lv else None
            e = ensure_skill(nm, "角色等级特技", "角色")
            e["charSources"].append({
                "char": ch_name,
                "recruited": is_rec,
                "how": cond or "等级习得",
                "discipline": "角色",
                "rank": "",
                "lv": lv_val,
            })

        # 熟练度习得（特技 / 战技 / 黑魔术 / 白魔术）
        lr = c.get("learn") or {}
        ranks = lr.get("ranks") or {}
        skills_set = set(lr.get("skills") or [])
        arts_set = set(lr.get("arts") or [])
        magic_set = set(lr.get("magic") or [])

        all_learned = list(dict.fromkeys([
            *(lr.get("skills") or []),
            *(lr.get("arts") or []),
            *(lr.get("magic") or []),
        ]))
        for sk_name in all_learned:
            rk_info = ranks.get(sk_name) or {}
            disc = rk_info.get("sk") or ""
            rk = rk_info.get("r") or ""

            if sk_name in magic_set:
                cat = "白魔术" if disc == "白魔术" else "黑魔术"
            elif sk_name in arts_set:
                cat = "战技"
            else:
                cat = "熟练度特技"

            if not disc:
                disc = "白魔术" if cat == "白魔术" else ("黑魔术" if cat == "黑魔术" else "角色")

            e = ensure_skill(sk_name, cat, disc)
            e["charSources"].append({
                "char": ch_name,
                "recruited": is_rec,
                "how": f"{disc} {rk}".strip() if (disc or rk) else cat,
                "discipline": disc,
                "rank": rk,
                "lv": None,
            })
            if disc in DISCIPLINES:
                char_matrix_acc[ch_name][disc].append({
                    "name": sk_name,
                    "rank": rk,
                    "category": cat,
                    "rating": e["rating"],
                })

    # 3) 计算 scope（角色特有 / 稀有 / 全员通用·职业 / 角色表限定·多人熟练度）与排序
    tiers_data = load_character_tiers()
    total_chars = len(chars_raw)
    skills_list: list[dict[str, Any]] = []
    for name, e in entries.items():
        # 去重并排序角色来源（已招 9 人优先）
        dedup_chars: dict[tuple[str, str], dict[str, Any]] = {}
        for cs in e["charSources"]:
            dedup_chars[(cs["char"], cs["how"])] = cs
        char_sources = sorted(
            dedup_chars.values(),
            key=lambda x: (
                0 if x["recruited"] else 1,
                recruited_rank.get(x["char"], 999),
                RANK_ORDER.get(x["rank"], 99),
                x["char"],
            ),
        )
        unique_owners = list(dict.fromkeys(x["char"] for x in char_sources))
        rec_owners = [x for x in unique_owners if x in recruited_set]
        owner_cnt = len(unique_owners)
        has_class = len(e["classSources"]) > 0

        if has_class and owner_cnt == 0:
            scope = "common_class"
            scope_label = "全员通用（职业精通/固有）"
        elif has_class and owner_cnt > 0:
            scope = "common_class"
            scope_label = f"全员通用（职业 + {owner_cnt}/{total_chars} 人习得）"
        elif owner_cnt <= 1:
            scope = "unique"
            scope_label = "角色特有（唯一）"
        elif owner_cnt <= 5:
            scope = "rare"
            scope_label = f"稀有习得（仅 {owner_cnt}/{total_chars} 人）"
        else:
            scope = "common_learn"
            scope_label = f"角色表限定（{owner_cnt}/{total_chars} 人熟练度）"

        e["charSources"] = char_sources
        e["ownerCount"] = owner_cnt
        e["recruitedOwners"] = rec_owners
        e["scope"] = scope
        e["scopeLabel"] = scope_label
        skills_list.append(e)

    cat_rank = {c: i for i, c in enumerate(CATEGORY_ORDER)}
    skills_list.sort(
        key=lambda x: (
            TIER_ORDER.get(x["rating"], 9),
            0 if x["ratedExplicit"] else 1,
            0 if x["recruitedOwners"] else 1,
            cat_rank.get(x["category"], 99),
            x["name"],
        )
    )
    scope_by_name = {s["name"]: s["scope"] for s in skills_list}

    # 4) 组装全 63 位角色技能速览表（已招 9 人优先，其次迪线，其余按 SS~D 强度排序）
    characters_list: list[dict[str, Any]] = []
    for idx, c in enumerate(chars_raw):
        ch_name = c.get("name", "")
        is_rec = ch_name in recruited_set
        in_diet = ch_name in dietrich_set
        ct = get_character_tier(ch_name, tiers_data)

        matrix: dict[str, list[dict[str, Any]]] = {}
        s_skills: list[str] = []
        a_skills: list[str] = []
        unique_skills: list[str] = []

        for disc in DISCIPLINES:
            items = char_matrix_acc[ch_name].get(disc) or []
            items.sort(key=lambda x: (RANK_ORDER.get(x["rank"], 99), x["name"]))
            enriched = []
            for it in items:
                sc = scope_by_name.get(it["name"], "common_learn")
                enriched.append({**it, "scope": sc})
                if it["rating"] == "S" and it["name"] not in s_skills:
                    s_skills.append(it["name"])
                elif it["rating"] == "A" and it["name"] not in a_skills:
                    a_skills.append(it["name"])
                if sc in ("unique", "rare") and it["name"] not in unique_skills:
                    unique_skills.append(it["name"])
            if enriched:
                matrix[disc] = enriched

        ps = c.get("personalSkill")
        personal_obj = (
            {"name": ps.get("name", ""), "text": ps.get("text", "")}
            if isinstance(ps, dict) and ps.get("name")
            else None
        )
        lv_list = []
        for item in (c.get("lvLearn") or []):
            if isinstance(item, dict) and item.get("name"):
                ref_eff = (ref_skills.get(item["name"]) or {}).get("effect", "")
                lv_list.append({"name": item["name"], "lv": item.get("lv"), "effect": ref_eff})
        if not lv_list:
            for nm, cond in _parse_lv_skills_fallback(c.get("lvSkills") or []):
                ref_eff = (ref_skills.get(nm) or {}).get("effect", "")
                lv_list.append({"name": nm, "cond": cond, "effect": ref_eff})

        characters_list.append({
            "name": ch_name,
            "enName": char_en_map.get(ch_name, ""),
            "faction": c.get("faction") or "",
            "startClass": c.get("startClass") or "",
            "growthTotal": c.get("growthTotal") or 0,
            "skillsGood": list(c.get("skillsGood") or []),
            "recruited": is_rec,
            "dietrichRoute": in_diet,
            "strengthTier": ct["strengthTier"],
            "pserTier": ct["pserTier"],
            "role": ct["role"],
            "defaultPriority": ct["defaultPriority"],
            "dietrichPriority": ct["dietrichPriority"],
            "priorityNote": ct["priorityNote"],
            "tierSummary": ct["tierSummary"],
            "personalSkill": personal_obj,
            "lvSkills": lv_list,
            "bloodMarks": [
                {"name": bm.get("name", ""), "text": bm.get("text", "")}
                for bm in (c.get("bloodMarks") or [])
                if isinstance(bm, dict) and bm.get("name")
            ],
            "note": char_notes_cfg.get(ch_name, ""),
            "sSkills": s_skills,
            "aSkills": a_skills,
            "rareSkills": unique_skills[:8],
            "matrix": matrix,
            "_order": idx,
        })

    characters_list.sort(
        key=lambda x: (
            0 if x["recruited"] else (1 if x["dietrichRoute"] else 2),
            PRIORITY_ORDER.get(x["dietrichPriority"] or "", 9) if x["recruited"] else 0,
            STRENGTH_ORDER.get(x["strengthTier"], 9),
            zh_name_key(x["name"]),
        )
    )
    for ch in characters_list:
        ch.pop("_order", None)

    tier_counts = {t["key"]: sum(1 for s in skills_list if s["rating"] == t["key"]) for t in skills_cfg["tiers"]}
    scope_counts = {
        "unique": sum(1 for s in skills_list if s["scope"] == "unique"),
        "rare": sum(1 for s in skills_list if s["scope"] == "rare"),
        "common_learn": sum(1 for s in skills_list if s["scope"] == "common_learn"),
        "common_class": sum(1 for s in skills_list if s["scope"] == "common_class"),
    }
    strength_counts = {
        k: sum(1 for ch in characters_list if ch["strengthTier"] == k)
        for k in ("SS", "S", "A", "B", "C", "D")
    }

    return {
        "meta": skills_cfg["meta"],
        "tiers": skills_cfg["tiers"],
        "characterTierScale": tiers_data.get("scale", []),
        "characterTierSource": tiers_data.get("source", ""),
        "priorityLinkNote": tiers_data.get("priorityLinkNote", ""),
        "categories": CATEGORY_ORDER,
        "disciplines": DISCIPLINES,
        "summary": {
            "skillCount": len(skills_list),
            "charCount": len(characters_list),
            "recruitedCount": len(recruited_set),
            "tierCounts": tier_counts,
            "scopeCounts": scope_counts,
            "strengthCounts": strength_counts,
        },
        "skills": skills_list,
        "characters": characters_list,
    }
