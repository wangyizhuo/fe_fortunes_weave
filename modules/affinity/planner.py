"""友好度培养 · 纯业务算法（无全局状态、无函数属性副作用、无 HTML 耦合）。

规则摘要：
- 闪光：最爱(3)→2、喜欢(2)→1、普通(1)→0；三人 1+1+1 或 2+2+0 = perfect。
- 讨厌(0)、好感已满(maxed)、不在场(absent)、已入队非领主均不上桌。
- 按有用支援对 (领主, 目标) 计分；每个座位必须参与至少一对有用支援（无凑数）。
- 排序：perfect 优先 → 分数高 → 闪光总和高 → 表顺序靠前；每个 goal 至少保留一桌。
"""
from __future__ import annotations

import itertools
import json
import re
from pathlib import Path
from typing import Any

SPK = ["讨厌", "普通", "喜欢", "最爱"]


def load_people(tab_path: str | Path, cfg: dict[str, Any]) -> tuple[list[str], list[dict[str, Any]]]:
    """解析 diet_tab.json 与配置里的领主喜好，返回 (菜品名列表, 角色列表)。"""
    with open(tab_path, encoding="utf-8") as f:
        rows = json.load(f)
    dishes = [h.split(" - ")[1] for h in rows[0][13:25]]
    people: list[dict[str, Any]] = []
    seen: set[str] = set()
    for r in rows[1:]:
        if len(r) < 25 or not r[8] or r[8] in seen:
            continue
        seen.add(r[8])
        text = (r[1] or "") + " " + (r[2] or "")
        rep = {m.group(1): int(m.group(2)) for m in re.finditer(r"(\S+?)（名声(\d+)", text)}
        sup = {m.group(1): int(m.group(2)) for m in re.finditer(r"(\S+?)（名声\d+/支援(\d+)", text)}
        people.append({
            "name": r[8],
            "pref": [int(x) for x in r[13:25]],
            "rep": rep,
            "sup": sup,
            "tier": r[0] or "",
        })
    for n, p in cfg.get("lord_prefs", {}).items():
        if n not in seen:
            people.append({"name": n, "pref": list(p), "rep": {}, "sup": {}, "lord": True})
    return dishes, people


def sparkle(prefs: list[int]) -> list[int]:
    """好感编码(1~3)转闪光值(0~2)。"""
    return [x - 1 for x in prefs]


def is_perfect(prefs: list[int]) -> bool:
    """判断三人对某道菜的好感(0~3)能否达成 perfect（1+1+1 或 2+2+0，且无人讨厌）。"""
    if not prefs or min(prefs) == 0:
        return False
    sp = sorted(sparkle(prefs))
    return sp[0] >= 1 or sp == [0, 2, 2]


def compute_pair_weights(
    people: list[dict[str, Any]],
    cfg: dict[str, Any],
) -> tuple[dict[tuple[str, str], int], dict[tuple[str, str], int | None]]:
    """纯函数计算 {(领主, 目标): 分数} 及 {(领主, 目标): 所需支援等级}。"""
    rec = set(cfg.get("recruited", []))
    names = {p["name"] for p in people}
    done = {tuple(x) for x in cfg.get("pairs_done", [])}
    weights: dict[tuple[str, str], int] = {}
    need: dict[tuple[str, str], int | None] = {}
    for g in cfg.get("goals", []):
        if g["lord"] not in names:
            continue
        skip = set(g.get("skip", []))
        for p in people:
            n = p["name"]
            r = p["rep"].get(g["route"])
            if r is None or n in rec or n in skip or n == g["lord"]:
                continue
            if (g["lord"], n) in done:
                continue
            if p["sup"].get(g["route"], 99) < g.get("min_support", 0):
                continue
            if "tiers" in g and not any(p.get("tier", "").startswith(t) for t in g["tiers"]):
                continue
            if "renown_weight" in g:
                s = g["renown_weight"].get(str(r), 0) or g.get("support_weight", {}).get(
                    str(p["sup"].get(g["route"])), 0
                )
            else:
                s = g.get("weight", 1) if r <= g.get("max_renown", 99) else 0
            if s:
                key = (g["lord"], n)
                weights[key] = weights.get(key, 0) + s
                need[key] = p["sup"].get(g["route"])
    return weights, need


def table_score(names: list[str], weights: dict[tuple[str, str], int]) -> int:
    return sum(weights.get((a, b), 0) + weights.get((b, a), 0) for a, b in itertools.combinations(names, 2))


def plan_meals(cfg: dict[str, Any], tab_path: str | Path) -> dict[str, Any]:
    """生成 12 道菜的三人同桌方案和目标支援权重清单。"""
    dishes, people = load_people(tab_path, cfg)
    out_of = set(cfg.get("maxed", [])) | set(cfg.get("absent", []))
    cand = [p for p in people if p["name"] not in out_of]
    order = {p["name"]: i for i, p in enumerate(cand)}
    pref = {p["name"]: p["pref"] for p in cand}
    weights, need = compute_pair_weights(cand, cfg)
    rec = set(cfg.get("recruited", []))
    lord = cfg.get("current_lord")
    need_lord = bool(cfg.get("unscouted_need_current_lord", False) and lord)
    useful = {n for pr in weights for n in pr}
    lord_rank = {lord: 0, **{g["lord"]: 1 for g in cfg.get("goals", []) if g["lord"] != lord}}
    k = cfg.get("options_per_dish", 3)

    res = []
    for i, d in enumerate(dishes):
        allowed = useful | ({lord} if need_lord else set())
        pool = [p for p in cand if p["pref"][i] > 0 and p["name"] in allowed]
        tables = []
        for t in itertools.combinations(pool, 3):
            ns = sorted((p["name"] for p in t), key=lambda n: (lord_rank.get(n, 9), order[n]))
            s = table_score(ns, weights)
            if s <= 0:
                continue
            if need_lord and lord not in ns and any(n not in rec for n in ns):
                continue
            v = [pref[n][i] for n in ns]
            pairs = [[a, b] for a, b in weights if a in ns and b in ns]
            filler = [n for n in ns if not any(n in x for x in pairs)]
            if filler:
                continue
            pf = is_perfect(v)
            tables.append({
                "who": ns,
                "pref": v,
                "sparkle": sparkle(v),
                "perfect": pf,
                "score": s,
                "pairs": pairs,
                "filler": filler,
                "_k": (not pf, -s, -sum(v), sorted(order[n] for n in ns)),
            })
        tables.sort(key=lambda x: x["_k"])
        pick = tables[:k]
        any_pf = bool(tables) and tables[0]["perfect"]
        for g in cfg.get("goals", []):
            hit = [t for t in tables if any(a == g["lord"] for a, _ in t["pairs"]) and (t["perfect"] or not any_pf)]
            if hit and not any(t in pick for t in hit):
                pick.append(hit[0])
        if any_pf:
            pick = [t for t in pick if t["perfect"]]
        for t in tables:
            t.pop("_k", None)
        res.append({"dish": d, "perfect": any_pf, "options": pick})

    weight_rows = [
        {"lord": a, "target": b, "score": s, "support": need.get((a, b))}
        for (a, b), s in sorted(weights.items(), key=lambda x: (-x[1], order[x[0][1]]))
    ]
    return {"dishes": res, "weights": weight_rows}


def fmt_table(t: dict[str, Any]) -> str:
    sp = "+".join(str(x) for x in t["sparkle"])
    fl = f"，{'、'.join(t['filler'])}凑数" if t.get("filler") else ""
    return f"{' + '.join(t['who'])}（{sp}，{'perfect' if t['perfect'] else '非 perfect'}，分 {t['score']}{fl}）"


def _parse_int(val: Any) -> int | None:
    s = str(val or "").strip()
    if not s:
        return None
    if s.endswith(".0") and s[:-2].isdigit():
        return int(s[:-2])
    return int(s) if s.isdigit() else None


def build_roster(
    tab_path: str | Path,
    cfg: dict[str, Any],
    current_renown: int | None = None,
) -> dict[str, Any]:
    """构建友好度培养页的主角（领主）卡片与全部待挖角角色名册（含声望/友好度要求及迪线满足标记）。"""
    with open(tab_path, encoding="utf-8") as f:
        rows = json.load(f)
    dishes = [h.split(" - ")[1] for h in rows[0][13:25]]

    recruited = set(cfg.get("recruited", []))
    maxed = set(cfg.get("maxed", []))
    absent = set(cfg.get("absent", []))
    pairs_done = {tuple(x) for x in cfg.get("pairs_done", [])}
    current_lord = cfg.get("current_lord", "迪托利希")

    _, people = load_people(tab_path, cfg)
    weights, _ = compute_pair_weights(people, cfg)

    # 1) 四大主角（领主）信息
    lord_names = [current_lord] + [n for n in cfg.get("lord_prefs", {}) if n != current_lord]
    people_by_name = {p["name"]: p for p in people}
    lords = []
    for ln in lord_names:
        p = people_by_name.get(ln)
        prefs = p["pref"] if p else []
        favs = [d for d, v in zip(dishes, prefs) if v == 3]
        likes = [d for d, v in zip(dishes, prefs) if v == 2]
        hates = [d for d, v in zip(dishes, prefs) if v == 0]
        active_targets = [b for (a, b) in weights if a == ln and b not in maxed and b not in absent]
        done_targets = [b for (a, b) in pairs_done if a == ln]
        if ln == current_lord:
            for m in cfg.get("maxed", []):
                if m not in done_targets and m not in recruited:
                    done_targets.append(f"{m}（满好感）")
        lords.append({
            "name": ln,
            "isCurrent": ln == current_lord,
            "favoriteDishes": favs,
            "likedDishes": likes,
            "hatedDishes": hates,
            "activeTargets": active_targets,
            "doneTargets": done_targets,
        })

    # 2) 待挖角与已招角色名册（基于 Recruit - Diet 表格）
    roster: list[dict[str, Any]] = []
    seen: set[str] = set()
    for r in rows[1:]:
        if len(r) < 9 or not r[8] or r[8] in seen:
            continue
        name = r[8].strip()
        seen.add(name)
        diet_tier = (r[0] or "").strip()
        easiest = (r[1] or "").strip()
        second = (r[2] or "").strip()
        method = (r[4] or "").strip()
        chapter = (r[5] or "").strip()
        diet_renown = _parse_int(r[6])
        diet_support = _parse_int(r[7])
        jp_name = (r[9] if len(r) > 9 else "").strip()
        condition = (r[10] if len(r) > 10 else "").strip()
        difficulty = (r[11] if len(r) > 11 else "").strip()
        note = (r[12] if len(r) > 12 else "").strip()
        prefs = [int(x) for x in r[13:25]] if len(r) >= 25 and all(str(x).isdigit() for x in r[13:25]) else []
        favs = [d for d, v in zip(dishes, prefs) if v == 3]

        is_recruited = name in recruited
        is_maxed = name in maxed
        is_absent = name in absent
        is_diet_pair_done = (current_lord, name) in pairs_done
        is_sheet_met = diet_tier == "满足"
        is_story = method == "剧情加入"
        is_part2 = diet_tier == "第二部" or method == "第二部"
        is_important = diet_tier in ("必招", "满足", "可选")

        if is_recruited:
            diet_affinity_met = True
            diet_affinity_reason = "已入队"
            status_key = "recruited"
        elif is_maxed:
            diet_affinity_met = True
            diet_affinity_reason = "好感已满（已满足）"
            status_key = "met"
        elif is_diet_pair_done:
            diet_affinity_met = True
            diet_affinity_reason = "迪线支援已达标"
            status_key = "met"
        elif is_sheet_met:
            diet_affinity_met = True
            diet_affinity_reason = "表格标记已满足"
            status_key = "met"
        elif is_part2:
            diet_affinity_met = False
            diet_affinity_reason = "第二部事件加入"
            status_key = "part2"
        elif is_story:
            diet_affinity_met = True
            diet_affinity_reason = "剧情自动加入"
            status_key = "recruited"
        elif diet_support == 1:
            diet_affinity_met = False
            diet_affinity_reason = "支援 1（无需吃饭）"
            status_key = "todo" if is_important else "other_route"
        else:
            diet_affinity_met = False
            diet_affinity_reason = "待刷迪线支援" if is_important else "别线更易（迪线未刷）"
            status_key = "todo" if is_important else "other_route"

        renown_met = (
            True
            if (is_recruited or is_story or diet_renown is None)
            else (None if current_renown is None else current_renown >= diet_renown)
        )

        # 检查是否同时是其他领主（如蕾达）的刷支援对象
        other_lords = []
        for g in cfg.get("goals", []):
            gl = g["lord"]
            if gl == current_lord:
                continue
            if (gl, name) in pairs_done:
                other_lords.append({"lord": gl, "met": True, "label": f"{gl}线支援已达标"})
            elif (gl, name) in weights:
                other_lords.append({"lord": gl, "met": False, "label": f"{gl}线待刷（分{weights[(gl, name)]}）"})

        roster.append({
            "name": name,
            "jpName": jp_name,
            "isLord": name in lord_names,
            "dietTier": diet_tier,
            "isImportant": is_important,
            "method": method,
            "chapter": chapter,
            "dietRenown": diet_renown,
            "dietSupport": diet_support,
            "renownMet": renown_met,
            "condition": condition,
            "difficulty": difficulty,
            "note": note,
            "easiestRoute": easiest,
            "secondRoute": second,
            "favoriteDishes": favs,
            "recruited": is_recruited,
            "maxed": is_maxed,
            "absent": is_absent,
            "dietAffinityMet": diet_affinity_met,
            "dietAffinityReason": diet_affinity_reason,
            "statusKey": status_key,
            "otherLords": other_lords,
        })

    return {"lords": lords, "roster": roster, "currentRenown": current_renown}
