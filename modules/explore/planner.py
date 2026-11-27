"""探索规划纯业务逻辑：按采集物需求优先级、旺达尔商会兑换价值与迷宫宝箱评分构建地图规划数据。"""
from __future__ import annotations

import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[2]
TIER_RANK = {"P0": 0, "P1": 1, "P2": 2}


def _load_json(path: Path) -> Any:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _compass_region(x: float, y: float, cx: float, cy: float) -> str:
    dx = x - cx
    dy = y - cy
    dist = math.hypot(dx, dy)
    if dist < 240:
        return "帝都周边"
    angle = math.degrees(math.atan2(dy, dx))
    # screen coords: +x East, +y South
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


def _classify_item(
    name: str,
    item_priorities: dict[str, dict[str, Any]],
    barter_by_mat: dict[str, list[dict[str, Any]]],
    dungeon_rules: list[dict[str, Any]],
    is_dungeon: bool = False,
) -> dict[str, Any]:
    clean = name.replace("★", "").strip()
    cfg = item_priorities.get(clean)
    exchanges = barter_by_mat.get(clean, [])
    if cfg:
        return {
            "name": clean,
            "tier": cfg["tier"],
            "score": int(cfg["score"]),
            "tag": cfg.get("tag", ""),
            "reason": cfg.get("reason", ""),
            "exchanges": exchanges,
        }
    if is_dungeon:
        for rule in dungeon_rules:
            if rule["keyword"] in clean:
                return {
                    "name": clean,
                    "tier": rule["tier"],
                    "score": int(rule["score"]),
                    "tag": rule.get("tag", ""),
                    "reason": f"迷宫稀有宝箱：{clean}",
                    "exchanges": exchanges,
                }
    if exchanges:
        top_ex = "、".join(f"{e['reward']}({e['place']})" for e in exchanges[:2])
        return {
            "name": clean,
            "tier": "P2",
            "score": 32,
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


def _nearest_station(x: float, y: float, stations: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not stations:
        return None
    best = min(stations, key=lambda s: math.hypot(s["x"] - x, s["y"] - y))
    return {"name": best["n"], "dist": round(math.hypot(best["x"] - x, best["y"] - y))}


def build_explore_plan(
    cfg_path: Path | None = None,
    ref_path: Path | None = None,
) -> dict[str, Any]:
    cfg = _load_json(cfg_path or (ROOT / "config" / "explore_config.json"))
    ref = _load_json(ref_path or (ROOT / cfg["mapRefPath"]))

    aliases: dict[str, str] = cfg.get("aliases") or {}
    item_priorities: dict[str, dict[str, Any]] = cfg.get("itemPriorities") or {}
    dungeon_rules: list[dict[str, Any]] = cfg.get("dungeonKeywordRules") or []
    route_order: list[str] = list(cfg.get("routeOrder") or ["dietrich"])

    def canon(name: str) -> str:
        c = str(name or "").replace("★", "").strip()
        return aliases.get(c, c)

    # 1) 索引所有旺达尔商会以物易物关系（素材 -> 可换物品列表）& 商会地点表
    barter_by_mat: dict[str, list[dict[str, Any]]] = defaultdict(list)
    merchant_by_place: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for m in ref.get("merchants") or []:
        if m.get("kind") != "旺达尔商会":
            continue
        place = m.get("place", "")
        for st in m.get("stock") or []:
            reward = st.get("n", "")
            cost_list = st.get("cost") or []
            if not reward or not cost_list:
                continue
            cost_fmt = [
                {"mat": canon(c[0]), "qty": int(c[1]) if len(c) > 1 else 1}
                for c in cost_list
            ]
            merchant_by_place[place].append({
                "reward": reward,
                "qty": st.get("qty"),
                "cost": cost_fmt,
            })
            for cf in cost_fmt:
                barter_by_mat[cf["mat"]].append({
                    "place": place,
                    "reward": reward,
                    "qty": cf["qty"],
                })

    # 2) 索引迷宫宝箱表
    chest_by_place: dict[str, dict[str, Any]] = {
        c["place"]: c for c in (ref.get("chests") or []) if c.get("place")
    }

    # 3) 按路线组装点位（采集点：矿石/道具/鱼/蔬菜 + 迷宫宝箱 + 旺达尔商会）
    maps_meta = ref.get("maps") or {}
    routes_out: dict[str, Any] = {}
    all_pins = ref.get("pins") or []

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
                    _classify_item(it, item_priorities, barter_by_mat, dungeon_rules, is_dungeon=False)
                    for it in unique_items
                ]
                item_objs.sort(key=lambda it: (TIER_RANK[it["tier"]], -it["score"], it["name"]))
                best_tier = item_objs[0]["tier"]
                # 综合含金量：最高项分 + 其余高价值项加权，鼓励一趟多采
                top_score = item_objs[0]["score"]
                bonus = sum(
                    round(it["score"] * (0.28 if it["tier"] == "P0" else (0.18 if it["tier"] == "P1" else 0.05)))
                    for it in item_objs[1:]
                )
                spot_score = top_score + min(bonus, 60)
                highlights = [it["name"] for it in item_objs if it["tier"] == best_tier][:3]
                if not highlights:
                    highlights = [it["name"] for it in item_objs[:2]]

                spots.append({
                    "id": str(p.get("id") or f"{rkey}-{pname}"),
                    "route": rkey,
                    "name": pname,
                    "type": ptype,
                    "x": round(px, 1),
                    "y": round(py, 1),
                    "priority": best_tier,
                    "score": spot_score,
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
                    _classify_item(b, item_priorities, barter_by_mat, dungeon_rules, is_dungeon=True)
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
                    "highlights": highlights,
                    "items": item_objs,
                    "desc": f"推荐 Lv{chest.get('lv', '?')} 迷宫宝箱",
                    "region": region,
                    "nearestStation": st_info["name"] if st_info else "",
                    "stationDist": st_info["dist"] if st_info else None,
                    "fwMapUrl": fw_url,
                })

            # 若该点位（据点/小据点/蔬菜/鱼等）设有旺达尔商会，额外生成一个「商会」标记方便规划「采完顺路换」
            if pname in merchant_by_place and pname not in seen_merchant_places:
                seen_merchant_places.add(pname)
                m_stock = merchant_by_place[pname]
                m_items = []
                for st in m_stock:
                    rew = st["reward"]
                    cost_txt = " + ".join(f"{c['mat']}×{c['qty']}" for c in st["cost"])
                    # 按兑换物判断优先级
                    tier = "P1"
                    score = 72
                    if any(k in rew for k in ("巨人戒指", "疾风戒指", "书箱", "追击宝珠", "挑战宝珠", "必圣宝珠", "绝风宝珠", "迅雷宝珠", "风来宝珠", "精灵宝珠")):
                        tier = "P0"
                        score = 88
                    elif any(k in rew for k in ("伤药", "解毒剂", "混合药", "肉箱", "鱼箱")):
                        tier = "P2"
                        score = 30
                    m_items.append({
                        "name": rew,
                        "tier": tier,
                        "score": score,
                        "tag": "旺达尔兑换",
                        "reason": f"需要：{cost_txt}",
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
                    "highlights": [it["name"] for it in m_items if it["tier"] == best_tier][:3],
                    "items": m_items,
                    "desc": f"旺达尔商会素材兑换点（共 {len(m_items)} 项）",
                    "region": region,
                    "nearestStation": st_info["name"] if st_info else "",
                    "stationDist": st_info["dist"] if st_info else None,
                    "fwMapUrl": fw_url,
                })

        # 按 优先级(P0→P1→P2) → 综合含金量降序 → 类型 → 地名 稳定排序并赋予全局序号
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
        "schemaVersion": cfg.get("schemaVersion", 1),
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
        "routes": routes_out,
        "summary": {
            "routeCount": len(routes_out),
            "defaultRoute": default_route,
            **default_sum,
        },
    }
