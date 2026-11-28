"""探索规划纯业务逻辑：融合 PR #31 最强武器评级、旺达尔商会实测库存/配方与迷宫宝箱构建地图规划数据。"""
from __future__ import annotations

import json
import math
import re
from collections import defaultdict
from pathlib import Path
from typing import Any
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[2]
TIER_RANK = {"P0": 0, "P1": 1, "P2": 2, "—": 9}
WEAPON_TO_PRIO = {"SS": "P0", "S": "P0", "A": "P1", "B": "P2"}


def _load_json(path: Path) -> Any:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def strip_weapon_suffix(name: str) -> str:
    """去除武器名称后的 +3 / +5 / III 等强化后缀（如「雷电剑+3」→「雷电剑」）。"""
    return re.sub(r"(\+\d+|III|II|I)$", "", str(name or "").strip()).strip()


def _compass_region(x: float, y: float, cx: float, cy: float) -> str:
    dx = x - cx
    dy = y - cy
    dist = math.hypot(dx, dy)
    if dist < 240:
        return "帝都周边"
    angle = math.degrees(math.atan2(dy, dx))
    if -22.5 <= angle < 22.5:
        return "帝都正东"
    if 22.5 <= angle < 67.5:
        return "帝都东南"
    if 67.5 <= angle < 112.5:
        return "帝都正南"
    if 112.5 <= angle < 157.5:
        return "帝都西南"
    if angle >= 157.5 or angle < -157.5:
        return "帝都正西"
    if -157.5 <= angle < -112.5:
        return "帝都西北"
    if -112.5 <= angle < -67.5:
        return "帝都正北"
    return "帝都东北"


def _nearest_station(x: float, y: float, stations: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not stations:
        return None
    best = min(stations, key=lambda s: math.hypot(s["x"] - x, s["y"] - y))
    return {"name": best["n"], "dist": round(math.hypot(best["x"] - x, best["y"] - y))}


def _build_barter_summary(
    cfg: dict[str, Any],
    weapon_tiers: dict[str, dict[str, Any]],
    dietrich_spots_by_mat: dict[str, list[str]],
    canon,
) -> tuple[dict[str, Any], dict[str, dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    """根据 PR #31 武器评级（SS/S→P0, A→P1, B→P2）与实测库存重整 Google Sheet 置换优先级与材料缺口。"""
    bp = cfg.get("barterPlan") or {}
    inv: dict[str, int] = {canon(k): int(v) for k, v in (bp.get("inventory") or {}).items()}
    free_credits: dict[str, dict[str, Any]] = bp.get("freeBarterCredits") or {}
    buy_notes: dict[str, str] = bp.get("buyNotes") or {}

    resolved_entries: list[dict[str, Any]] = []
    mat_uses: dict[str, list[dict[str, Any]]] = defaultdict(list)
    mat_done_uses: dict[str, list[dict[str, Any]]] = defaultdict(list)
    sheet_merchant_by_place: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for raw in bp.get("entries") or []:
        item = raw["item"]
        orig_p = raw.get("origPriority", "P2")
        done = bool(raw.get("done")) or orig_p == "—"
        base = strip_weapon_suffix(item)
        w_info = weapon_tiers.get(base)
        wtier = w_info["tier"] if w_info else ""

        if done:
            new_p = "—"
            change_reason = "已换完"
        elif raw.get("forcePriority"):
            new_p = raw["forcePriority"]
            f_reason = raw.get("forceReason") or "人工调整"
            change_reason = f"{orig_p}→{new_p}（{f_reason}）" if orig_p != new_p else f_reason
        elif wtier:
            new_p = WEAPON_TO_PRIO.get(wtier, orig_p)
            if new_p != orig_p:
                change_reason = f"{orig_p}→{new_p}（武器榜 {wtier} 级）"
            else:
                change_reason = f"武器榜 {wtier} 级确认 {new_p}"
        else:
            new_p = orig_p
            change_reason = ""

        costs = []
        lack_parts = []
        for c in raw.get("cost") or []:
            m = canon(c["mat"])
            q = int(c["qty"])
            have = inv.get(m, 0)
            lack = max(0, q - have)
            costs.append({"mat": m, "qty": q, "have": have, "lack": lack})
            if lack > 0:
                lack_parts.append(f"{m}缺{lack}")
            use_rec = {
                "priority": new_p,
                "item": item,
                "weaponTier": wtier,
                "qty": q,
                "place": raw.get("place", ""),
            }
            if done:
                mat_done_uses[m].append(use_rec)
            else:
                mat_uses[m].append(use_rec)

        entry_obj = {
            "priority": new_p,
            "origPriority": orig_p,
            "changed": (not done) and (new_p != orig_p),
            "changeReason": change_reason,
            "item": item,
            "weaponTier": wtier,
            "type": raw.get("type", ""),
            "place": raw.get("place", ""),
            "stock": raw.get("stock", ""),
            "done": done,
            "cost": costs,
            "canExchangeNow": (not done) and len(lack_parts) == 0,
            "lackText": "已换" if done else ("✅ 可换" if not lack_parts else "、".join(lack_parts)),
            "source": raw.get("source", ""),
            "note": raw.get("note", ""),
        }
        resolved_entries.append(entry_obj)
        if not done and raw.get("place"):
            sheet_merchant_by_place[raw["place"]].append(entry_obj)

    resolved_entries.sort(
        key=lambda e: (
            TIER_RANK.get(e["priority"], 9),
            0 if e["weaponTier"] in ("SS", "S") else (1 if e["weaponTier"] == "A" else 2),
            0 if e["changed"] else 1,
            e["item"],
        )
    )

    # 按材料汇总 P0 / P1 真实缺口与地图有效优先级
    all_mats = sorted(set(mat_uses.keys()) | set(mat_done_uses.keys()))
    materials_summary: list[dict[str, Any]] = []
    mat_override: dict[str, dict[str, Any]] = {}

    for m in all_mats:
        uses = sorted(mat_uses.get(m, []), key=lambda u: (TIER_RANK.get(u["priority"], 9), -u["qty"], u["item"]))
        done_uses = mat_done_uses.get(m, [])
        have = inv.get(m, 0)
        credit_info = free_credits.get(m) or {}
        credit_qty = int(credit_info.get("qty") or 0)

        need_p0 = sum(u["qty"] for u in uses if u["priority"] == "P0")
        need_p01 = sum(u["qty"] for u in uses if u["priority"] in ("P0", "P1"))
        lack_p0 = max(0, need_p0 - have - credit_qty)
        lack_p01 = max(0, need_p01 - have - credit_qty)

        spots_cnt = len(dietrich_spots_by_mat.get(m, []))
        top_uses = [u for u in uses if u["priority"] in ("P0", "P1")]
        if not top_uses:
            top_uses = uses[:2]
        use_label = " / ".join(
            f"{(u['weaponTier'] + ' ' if u['weaponTier'] else u['priority'] + ' ')}{u['item']}×{u['qty']}"
            for u in top_uses[:3]
        )

        if lack_p0 > 0:
            eff_tier = "P0"
            # P0 缺口素材分数极高，稀缺度越高越靠前（SS/S 武器材料优先）
            has_ss = any(u["weaponTier"] == "SS" for u in uses if u["priority"] == "P0")
            has_s = any(u["weaponTier"] == "S" for u in uses if u["priority"] == "P0")
            score = 106 if has_ss else (103 if has_s else 100)
            first_u = next(u for u in uses if u["priority"] == "P0")
            tag = f"缺{lack_p0}·{(first_u['weaponTier'] or 'P0')}{first_u['item']}"
            reason = f"实测库存 {have}，P0 需 {need_p0}（还缺 {lack_p0}）→ {use_label}"
        elif lack_p01 > 0:
            eff_tier = "P1"
            # 稀缺点位（2~3处）分数高，满图 26 处的姬金鱼草给 58 分避免盖过稀缺素材
            has_a = any(u["weaponTier"] == "A" for u in uses if u["priority"] == "P1")
            if has_a:
                score = 79
            elif spots_cnt <= 3:
                score = 76
            elif spots_cnt <= 10:
                score = 68
            else:
                score = 58
            first_u = next((u for u in uses if u["priority"] == "P1"), uses[0])
            tag = f"缺{lack_p01}·{(first_u['weaponTier'] or 'P1')}{first_u['item']}"
            extra = (
                "（P0 封魔盾 10/10 已够，P1 达·米纳盾缺 10）" if m == "姬金鱼草"
                else "（P0 铁枪 6/6 已够，P1 达·米纳盾缺 10）" if m == "津吉"
                else ""
            )
            reason = f"实测库存 {have}，P0+P1 需 {need_p01}（还缺 {lack_p01}）→ {use_label}{extra}"
        elif need_p01 > 0:
            # 已有库存已够 P0/P1！不再占地图 P0/P1 红橙大标
            eff_tier = "P2"
            score = 32
            tag = f"库存已够({have}/{need_p01})"
            reason = f"已有 {have} ≥ 需 {need_p01}（暂不缺）→ {use_label}"
        elif done_uses and not uses:
            eff_tier = "P2"
            score = 20
            done_names = "、".join(u["item"] for u in done_uses)
            tag = f"{done_names}已换"
            reason = f"{done_names}已换完（库存剩余 {have}），无需再专门采集"
        else:
            eff_tier = "P2"
            score = 26
            tag = "P2备选兑换"
            reason = f"P2 备选（已有 {have}）→ {use_label}" if use_label else ""

        if buy_notes.get(m):
            reason = f"{reason}｜可买：{buy_notes[m]}" if reason else buy_notes[m]

        need_all = sum(u["qty"] for u in uses)
        mat_obj = {
            "material": m,
            "priority": eff_tier,
            "hasShortage": lack_p01 > 0,
            "shortageTier": "P0" if lack_p0 > 0 else ("P1" if lack_p01 > 0 else ""),
            "have": have,
            "credit": credit_qty,
            "creditNote": credit_info.get("note", ""),
            "needP0": need_p0,
            "needP01": need_p01,
            "needAll": need_all,
            "lackP0": lack_p0,
            "lackP01": lack_p01,
            "buyNote": buy_notes.get(m, ""),
            "dietrichSpots": dietrich_spots_by_mat.get(m, []),
            "uses": uses,
            "doneUses": done_uses,
            "tag": tag,
            "reason": reason,
        }
        materials_summary.append(mat_obj)
        mat_override[m] = {
            "tier": eff_tier,
            "score": score,
            "tag": tag,
            "reason": reason,
            "have": have,
            "lackP0": lack_p0,
            "lackP01": lack_p01,
            "shortageTier": mat_obj["shortageTier"],
            "buyNote": buy_notes.get(m, ""),
        }

    materials_summary.sort(
        key=lambda x: (
            0 if x["lackP0"] > 0 else (1 if x["lackP01"] > 0 else 2),
            TIER_RANK.get(x["priority"], 9),
            -x["lackP0"],
            -x["lackP01"],
            len(x["dietrichSpots"]) if x["dietrichSpots"] else 999,
            x["material"],
        )
    )

    barter_summary = {
        "title": bp.get("title", ""),
        "sheetUrl": bp.get("sheetUrl", ""),
        "snapshotDate": bp.get("snapshotDate", ""),
        "weaponTierRule": bp.get("weaponTierRule", ""),
        "counts": {
            "P0": sum(1 for e in resolved_entries if e["priority"] == "P0"),
            "P1": sum(1 for e in resolved_entries if e["priority"] == "P1"),
            "P2": sum(1 for e in resolved_entries if e["priority"] == "P2"),
            "done": sum(1 for e in resolved_entries if e["done"]),
            "changed": sum(1 for e in resolved_entries if e["changed"]),
            "lackP0Mats": sum(1 for m in materials_summary if m["lackP0"] > 0),
            "lackP1Mats": sum(1 for m in materials_summary if m["lackP0"] == 0 and m["lackP01"] > 0),
        },
        "entries": resolved_entries,
        "materials": materials_summary,
    }
    return barter_summary, mat_override, sheet_merchant_by_place


def _classify_item(
    name: str,
    item_priorities: dict[str, dict[str, Any]],
    mat_override: dict[str, dict[str, Any]],
    weapon_tiers: dict[str, dict[str, Any]],
    barter_by_mat: dict[str, list[dict[str, Any]]],
    dungeon_rules: list[dict[str, Any]],
    is_dungeon: bool = False,
) -> dict[str, Any]:
    clean = name.replace("★", "").strip()
    exchanges = barter_by_mat.get(clean, [])

    # 1) 优先匹配 Google Sheet 实测库存 + PR #31 重整后的商会素材优先级
    ov = mat_override.get(clean)
    if ov and not is_dungeon:
        return {
            "name": clean,
            "tier": ov["tier"],
            "score": int(ov["score"]),
            "tag": ov["tag"],
            "reason": ov["reason"],
            "have": ov["have"],
            "lackP0": ov["lackP0"],
            "lackP01": ov["lackP01"],
            "shortageTier": ov["shortageTier"],
            "buyNote": ov["buyNote"],
            "exchanges": exchanges,
        }

    # 2) 迷宫或道具点直接产出武器时，按 PR #31 最强武器评级（SS/S→P0, A→P1, B→P2）
    w = weapon_tiers.get(strip_weapon_suffix(clean))
    if w:
        wt = w["tier"]
        prio = WEAPON_TO_PRIO.get(wt, "P2")
        score = 98 if wt == "SS" else (93 if wt == "S" else (76 if wt == "A" else 42))
        return {
            "name": clean,
            "tier": prio,
            "score": score,
            "tag": f"武器榜{wt}级",
            "reason": f"PR#31 最强武器榜 {wt} 级：{w.get('reason', '')}",
            "exchanges": exchanges,
        }

    # 3) 静态配置表（矿石 / 指南书 / 能力露 / 稀有箱）
    cfg = item_priorities.get(clean)
    if cfg:
        return {
            "name": clean,
            "tier": cfg["tier"],
            "score": int(cfg["score"]),
            "tag": cfg.get("tag", ""),
            "reason": cfg.get("reason", ""),
            "exchanges": exchanges,
        }

    # 4) 迷宫宝箱关键词规则
    if is_dungeon:
        for rule in dungeon_rules:
            if rule["keyword"] in clean:
                return {
                    "name": clean,
                    "tier": rule["tier"],
                    "score": int(rule["score"]),
                    "tag": rule.get("tag", ""),
                    "reason": f"迷宫宝箱：{clean}",
                    "exchanges": exchanges,
                }

    # 5) 其余全图商会可换素材归为 P2
    if exchanges:
        top_ex = "、".join(f"{e['reward']}({e['place']})" for e in exchanges[:2])
        return {
            "name": clean,
            "tier": "P2",
            "score": 28,
            "tag": "商会兑换",
            "reason": f"可兑换：{top_ex}",
            "exchanges": exchanges,
        }

    return {
        "name": clean,
        "tier": "P2",
        "score": 15,
        "tag": "",
        "reason": "",
        "exchanges": [],
    }


def build_explore_plan(
    cfg_path: Path | None = None,
    ref_path: Path | None = None,
) -> dict[str, Any]:
    cfg = _load_json(cfg_path or (ROOT / "config" / "explore_config.json"))
    ref = _load_json(ref_path or (ROOT / cfg["mapRefPath"]))
    wt_path = ROOT / cfg.get("weaponTierRefPath", "config/weapon_tier_ref.json")
    wt_data = _load_json(wt_path) if wt_path.exists() else {"weapons": []}
    weapon_tiers: dict[str, dict[str, Any]] = {
        strip_weapon_suffix(w["name"]): w for w in (wt_data.get("weapons") or []) if w.get("name")
    }

    aliases: dict[str, str] = cfg.get("aliases") or {}
    item_priorities: dict[str, dict[str, Any]] = cfg.get("itemPriorities") or {}
    dungeon_rules: list[dict[str, Any]] = cfg.get("dungeonKeywordRules") or []
    route_order: list[str] = list(cfg.get("routeOrder") or ["dietrich"])

    def canon(name: str) -> str:
        c = str(name or "").replace("★", "").strip()
        return aliases.get(c, c)

    all_pins = ref.get("pins") or []

    # 预统计迪托利希篇每个素材の采集点列表（供 barterSummary 展示 & 稀缺度计算）
    dietrich_spots_by_mat: dict[str, list[str]] = defaultdict(list)
    for p in all_pins:
        if p.get("r") == "dietrich" and p.get("t") in ("矿石", "道具", "鱼", "蔬菜"):
            for it in p.get("items") or []:
                m = canon(it)
                if p["n"] not in dietrich_spots_by_mat[m]:
                    dietrich_spots_by_mat[m].append(p["n"])

    # 1) 重整 Google Sheet 置换优先级与真实缺口
    barter_summary, mat_override, sheet_merchant_by_place = _build_barter_summary(
        cfg, weapon_tiers, dietrich_spots_by_mat, canon
    )

    # 2) 索引全部旺达尔商会以物易物关系（Sheet 实测优先，其次资料站补充）
    barter_by_mat: dict[str, list[dict[str, Any]]] = defaultdict(list)
    merchant_by_place: dict[str, list[dict[str, Any]]] = defaultdict(list)
    seen_place_reward: set[tuple[str, str]] = set()

    for place, entries in sheet_merchant_by_place.items():
        for e in entries:
            seen_place_reward.add((place, e["item"]))
            cost_fmt = [{"mat": c["mat"], "qty": c["qty"]} for c in e["cost"]]
            merchant_by_place[place].append({
                "reward": e["item"],
                "priority": e["priority"],
                "weaponTier": e["weaponTier"],
                "qty": e["stock"],
                "cost": cost_fmt,
                "lackText": e["lackText"],
                "note": e["note"],
            })
            for cf in cost_fmt:
                barter_by_mat[cf["mat"]].append({
                    "place": place,
                    "reward": f"{(e['weaponTier'] + ' ' if e['weaponTier'] else '')}{e['item']}",
                    "qty": cf["qty"],
                    "priority": e["priority"],
                })

    for m in ref.get("merchants") or []:
        if m.get("kind") != "旺达尔商会":
            continue
        place = m.get("place", "")
        for st in m.get("stock") or []:
            reward = st.get("n", "")
            cost_list = st.get("cost") or []
            if not reward or not cost_list or (place, reward) in seen_place_reward:
                continue
            cost_fmt = [
                {"mat": canon(c[0]), "qty": int(c[1]) if len(c) > 1 else 1}
                for c in cost_list
            ]
            w = weapon_tiers.get(strip_weapon_suffix(reward))
            wt = w["tier"] if w else ""
            prio = WEAPON_TO_PRIO.get(wt, "P2") if wt else "P2"
            merchant_by_place[place].append({
                "reward": reward,
                "priority": prio,
                "weaponTier": wt,
                "qty": st.get("qty"),
                "cost": cost_fmt,
                "lackText": "",
                "note": "资料站参考",
            })
            for cf in cost_fmt:
                barter_by_mat[cf["mat"]].append({
                    "place": place,
                    "reward": reward,
                    "qty": cf["qty"],
                    "priority": prio,
                })

    # 3) 索引迷宫宝箱表
    chest_by_place: dict[str, dict[str, Any]] = {
        c["place"]: c for c in (ref.get("chests") or []) if c.get("place")
    }

    # 4) 按路线组装点位（采集点 + 迷宫宝箱 + 旺达尔商会）
    maps_meta = ref.get("maps") or {}
    routes_out: dict[str, Any] = {}

    for rkey in route_order:
        if rkey not in maps_meta:
            continue
        rpins = [p for p in all_pins if p.get("r") == rkey]
        stations = [p for p in rpins if p.get("t") == "驿站"]
        hubs = [p for p in rpins if p.get("t") == "据点"]
        capital = next((p for p in hubs if "帝都" in p.get("n", "")), None)
        cx = capital["x"] if capital else ref.get("mapWidth", 3328) / 2
        cy = capital["y"] if capital else ref.get("mapHeight", 2560) / 2

        spots: list[dict[str, Any]] = []
        seen_merchant_places: set[str] = set()

        for p in rpins:
            ptype = p.get("t", "")
            pname = p.get("n", "")
            px = float(p.get("x", 0))
            py = float(p.get("y", 0))
            st_info = _nearest_station(px, py, stations)
            region = _compass_region(px, py, cx, cy)
            fw_url = f"https://fire-emblem-fw.site/map.html#n:{quote(pname)}"

            if ptype in ("矿石", "道具", "鱼", "蔬菜"):
                raw_items = [canon(i) for i in (p.get("items") or []) if str(i).strip()]
                unique_items = list(dict.fromkeys(raw_items))
                if not unique_items:
                    continue
                item_objs = [
                    _classify_item(it, item_priorities, mat_override, weapon_tiers, barter_by_mat, dungeon_rules, is_dungeon=False)
                    for it in unique_items
                ]
                item_objs.sort(key=lambda it: (TIER_RANK[it["tier"]], -it["score"], it["name"]))
                best_tier = item_objs[0]["tier"]
                top_score = item_objs[0]["score"]
                bonus = sum(
                    round(it["score"] * (0.28 if it["tier"] == "P0" else (0.18 if it["tier"] == "P1" else 0.04)))
                    for it in item_objs[1:]
                )
                spot_score = top_score + min(bonus, 60)
                highlights = []
                for it in item_objs:
                    if it["tier"] == best_tier:
                        lbl = f"{it['name']}(缺{it['lackP0'] if it.get('lackP0') else it['lackP01']})" if (it.get("lackP0") or it.get("lackP01")) else it["name"]
                        highlights.append(lbl)
                highlights = highlights[:3] or [item_objs[0]["name"]]

                lack_tiers = [it.get("shortageTier") for it in item_objs if it.get("shortageTier")]
                barter_lack_tier = "P0" if "P0" in lack_tiers else ("P1" if "P1" in lack_tiers else "")

                spots.append({
                    "id": str(p.get("id") or f"{rkey}-{pname}"),
                    "route": rkey,
                    "name": pname,
                    "type": ptype,
                    "x": round(px, 1),
                    "y": round(py, 1),
                    "priority": best_tier,
                    "score": spot_score,
                    "hasBarterLack": bool(barter_lack_tier),
                    "barterLackTier": barter_lack_tier,
                    "highlights": highlights,
                    "items": item_objs,
                    "desc": " · ".join(p.get("d") or []),
                    "region": region,
                    "nearestStation": st_info["name"] if st_info else "",
                    "stationDist": st_info["dist"] if st_info else None,
                    "fwMapUrl": fw_url,
                })

            elif ptype == "迷宫":
                chest = chest_by_place.get(pname)
                if not chest or not chest.get("boxes"):
                    continue
                boxes = list(dict.fromkeys(canon(b) for b in chest["boxes"] if str(b).strip()))
                item_objs = [
                    _classify_item(b, item_priorities, mat_override, weapon_tiers, barter_by_mat, dungeon_rules, is_dungeon=True)
                    for b in boxes
                ]
                item_objs.sort(key=lambda it: (TIER_RANK[it["tier"]], -it["score"], it["name"]))
                best_tier = item_objs[0]["tier"]
                spot_score = item_objs[0]["score"] + min(
                    sum(round(it["score"] * 0.2) for it in item_objs[1:] if it["tier"] in ("P0", "P1")),
                    45,
                )
                highlights = [it["name"] for it in item_objs if it["tier"] == best_tier][:3]
                spots.append({
                    "id": str(p.get("id") or f"{rkey}-dg-{pname}"),
                    "route": rkey,
                    "name": pname,
                    "type": "迷宫",
                    "lv": chest.get("lv"),
                    "x": round(px, 1),
                    "y": round(py, 1),
                    "priority": best_tier,
                    "score": spot_score,
                    "hasBarterLack": False,
                    "barterLackTier": "",
                    "highlights": highlights,
                    "items": item_objs,
                    "desc": f"推荐 Lv{chest.get('lv', '?')} 迷宫宝箱",
                    "region": region,
                    "nearestStation": st_info["name"] if st_info else "",
                    "stationDist": st_info["dist"] if st_info else None,
                    "fwMapUrl": fw_url,
                })

            if pname in merchant_by_place and pname not in seen_merchant_places:
                seen_merchant_places.add(pname)
                m_stock = merchant_by_place[pname]
                m_items = []
                for st in m_stock:
                    rew = st["reward"]
                    cost_txt = " + ".join(f"{c['mat']}×{c['qty']}" for c in st["cost"])
                    tier = st.get("priority", "P2")
                    score = 94 if tier == "P0" else (74 if tier == "P1" else 30)
                    wt = st.get("weaponTier", "")
                    lack_t = st.get("lackText", "")
                    m_items.append({
                        "name": rew,
                        "tier": tier,
                        "score": score,
                        "tag": f"武器榜{wt}级" if wt else "旺达尔兑换",
                        "reason": f"需 {cost_txt}" + (f"（{lack_t}）" if lack_t else ""),
                        "cost": st["cost"],
                    })
                m_items.sort(key=lambda it: (TIER_RANK[it["tier"]], -it["score"], it["name"]))
                best_tier = m_items[0]["tier"]
                spots.append({
                    "id": f"{rkey}-mer-{pname}",
                    "route": rkey,
                    "name": f"{pname}（旺达尔商会）",
                    "placeName": pname,
                    "type": "商会",
                    "x": round(px, 1),
                    "y": round(py, 1),
                    "priority": best_tier,
                    "score": m_items[0]["score"],
                    "hasBarterLack": best_tier in ("P0", "P1"),
                    "barterLackTier": best_tier if best_tier in ("P0", "P1") else "",
                    "highlights": [it["name"] for it in m_items if it["tier"] == best_tier][:3],
                    "items": m_items,
                    "desc": f"旺达尔商会素材兑换点（共 {len(m_items)} 项）",
                    "region": region,
                    "nearestStation": st_info["name"] if st_info else "",
                    "stationDist": st_info["dist"] if st_info else None,
                    "fwMapUrl": fw_url,
                })

        type_rank = {t: i for i, t in enumerate(cfg["pinTypes"])}
        spots.sort(key=lambda s: (TIER_RANK[s["priority"]], -s["score"], type_rank.get(s["type"], 9), s["name"]))
        for idx, s in enumerate(spots, 1):
            s["rank"] = idx

        tier_counts = {
            t["key"]: sum(1 for s in spots if s["priority"] == t["key"])
            for t in cfg["tiers"]
        }
        type_counts = {
            t: sum(1 for s in spots if s["type"] == t)
            for t in cfg["pinTypes"]
        }

        routes_out[rkey] = {
            "key": rkey,
            "name": maps_meta[rkey]["name"],
            "view": maps_meta[rkey].get("view") or [0, 0, ref["mapWidth"], ref["mapHeight"]],
            "summary": {
                "totalSpots": len(spots),
                "tierCounts": tier_counts,
                "typeCounts": type_counts,
                "barterLackCount": sum(1 for s in spots if s.get("hasBarterLack") and s["type"] != "商会"),
                "stationCount": len(stations),
            },
            "stations": [
                {"name": s["n"], "x": round(float(s["x"]), 1), "y": round(float(s["y"]), 1)}
                for s in stations
            ],
            "hubs": [
                {"name": h["n"], "x": round(float(h["x"]), 1), "y": round(float(h["y"]), 1)}
                for h in hubs
            ],
            "spots": spots,
        }

    default_route = cfg.get("defaultRoute", "dietrich")
    default_sum = routes_out[default_route]["summary"] if default_route in routes_out else {}

    return {
        "module": "explore",
        "schemaVersion": cfg.get("schemaVersion", 2),
        "defaultRoute": default_route,
        "routeOrder": [r for r in route_order if r in routes_out],
        "mapImage": "./assets/world_map.jpg",
        "mapWidth": ref.get("mapWidth", 3328),
        "mapHeight": ref.get("mapHeight", 2560),
        "defaultViewBox": cfg.get("defaultViewBox", [210, 230, 2900, 2100]),
        "tiers": cfg["tiers"],
        "pinTypes": cfg["pinTypes"],
        "arrows": ref.get("arrows") or [],
        "externalMaps": cfg.get("externalMaps") or [],
        "notes": cfg.get("notes") or [],
        "barterSummary": barter_summary,
        "routes": routes_out,
        "summary": {
            "routeCount": len(routes_out),
            "defaultRoute": default_route,
            **default_sum,
        },
    }
