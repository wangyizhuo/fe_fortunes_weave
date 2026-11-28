"""道具 / 材料采集 · 纯业务逻辑（零 HTML 耦合，完全可单元测试）。

输入：config/items_config.json + weapons.tsv
输出：
  - towns     : 按城镇组织的武器、盾、教本、手形、武具箱、道具列表
  - barter    : 范达尔商会以物易物清单（含结构化 materials 数组）
  - materials : 按材料名反查可兑换装备的采集索引（方便规划采集/钓鱼）
  - csvRows   : 供导出的表格行
"""
from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any


def parse_materials(cost_str: str) -> list[dict[str, Any]]:
    """解析 'バクx10,キンバイx3' 或 'Paradise Fish ×1' 为结构化材料需求列表。"""
    if not cost_str:
        return []
    out: list[dict[str, Any]] = []
    for raw in re.split(r"[,、，]+", cost_str.strip()):
        part = raw.strip()
        if not part:
            continue
        m = re.match(r"^(.+?)\s*[x×\*]\s*(\d+)$", part, flags=re.IGNORECASE)
        if m:
            out.append({"material": m.group(1).strip(), "qty": int(m.group(2))})
        else:
            out.append({"material": part, "qty": 1})
    return out


def _index_weapon_tiers(weapon_tiers: dict[str, Any] | None) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    by_jp: dict[str, dict[str, Any]] = {}
    by_cn: dict[str, dict[str, Any]] = {}
    if not weapon_tiers:
        return by_jp, by_cn
    for w in weapon_tiers.get("weapons") or []:
        if w.get("jp"):
            by_jp[w["jp"]] = w
        for k in (w.get("name"), w.get("repoName"), w.get("officialName")):
            if k:
                by_cn[k] = w
    return by_jp, by_cn


def build_catalog(
    cfg: dict[str, Any],
    weapons_tsv_path: str | Path,
    weapon_tiers: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """根据纯配置与武器 TSV 构建商店、以物易物及采集材料反查数据结构，并融合武器强度评级。"""
    weapon_names: dict[str, str] = cfg["weaponNames"]
    item_notes: dict[str, str] = cfg.get("itemNotes", {})
    town_meta: dict[str, dict[str, Any]] = cfg["towns"]
    type_map: dict[str, str] = cfg["typeMap"]
    wt_by_jp, wt_by_cn = _index_weapon_tiers(weapon_tiers)

    def _wt_fields(cn_name: str, jp_name: str) -> dict[str, Any]:
        w = wt_by_jp.get(jp_name) or wt_by_cn.get(cn_name)
        if not w:
            return {}
        return {
            "weaponTier": w.get("tier", ""),
            "weaponForge": w.get("forge", ""),
            "weaponRank": w.get("rank", ""),
            "weaponReason": w.get("reason", ""),
        }

    towns: dict[str, dict[str, Any]] = {}
    barter: list[dict[str, Any]] = []
    csv_rows: list[list[Any]] = []
    weapon_places: dict[str, list[str]] = {}

    def add_town_item(jp_town: str, row: dict[str, Any]) -> None:
        meta = town_meta[jp_town]
        towns.setdefault(
            jp_town,
            {
                "cn": meta["cn"],
                "en": meta.get("en", ""),
                "jp": jp_town,
                "priority": bool(meta.get("priority", False)),
                "items": [],
            },
        )["items"].append(row)

    with open(weapons_tsv_path, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line:
                continue
            name_jp, typ_jp, shop, price_str, stock = line.split("\t")
            cn = weapon_names[name_jp]
            cat = type_map[typ_jp]
            note = item_notes.get(name_jp, "")
            wtf = _wt_fields(cn, name_jp)
            if "ヴァンダル" in shop:
                mats = parse_materials(price_str)
                barter.append({
                    "cn": cn,
                    "jp": name_jp,
                    "type": cat,
                    "cost": price_str,
                    "materials": mats,
                    "location": "帝都达格席翁 · 范达尔商会",
                    "note": note,
                    **wtf,
                })
                if wtf:
                    weapon_places.setdefault(name_jp, []).append("商会以物易物")
                csv_rows.append([
                    "帝都达格席翁 · 范达尔商会", "Dagsion", cat, cn, name_jp,
                    "以物易物：" + price_str, "", note, "AppMedia",
                ])
                continue
            price_clean = price_str.replace("G", "").strip()
            price_val = int(price_clean) if price_clean.isdigit() else None
            row = {
                "cat": cat,
                "cn": cn,
                "jp": name_jp,
                "price": price_val,
                "stock": "" if stock == "-" else stock,
                "note": note,
                "src": "AppMedia",
                **wtf,
            }
            add_town_item(shop, row)
            meta = town_meta[shop]
            if wtf:
                p_txt = f"{meta['cn']}（{price_val}G）" if price_val is not None else meta["cn"]
                weapon_places.setdefault(name_jp, []).append(p_txt)
            csv_rows.append([meta["cn"], meta.get("en", ""), cat, cn, name_jp, price_clean, stock, note, "AppMedia"])

    for ex in cfg.get("extraShopItems", []):
        wtf = _wt_fields(ex["cn"], ex["jp"])
        row = {
            "cat": ex["cat"],
            "cn": ex["cn"],
            "jp": ex["jp"],
            "price": ex.get("price"),
            "stock": ex.get("stock", ""),
            "note": ex.get("note", ""),
            "src": ex.get("src", ""),
            **wtf,
        }
        add_town_item(ex["town"], row)
        meta = town_meta[ex["town"]]
        csv_rows.append([
            meta["cn"], meta.get("en", ""), row["cat"], row["cn"], row["jp"],
            row["price"] if row["price"] is not None else "", row["stock"], row["note"], row["src"],
        ])

    for b in cfg.get("extraBarter", []):
        wtf = _wt_fields(b["cn"], b["jp"])
        barter.append({
            "cn": b["cn"],
            "jp": b["jp"],
            "type": b["type"],
            "cost": b["cost"],
            "materials": parse_materials(b["cost"]),
            "location": b.get("location", "范达尔商会"),
            "note": b.get("note", ""),
            **wtf,
        })

    # 按材料反查可兑换装备（道具/材料采集视图用）
    mat_map: dict[str, list[dict[str, Any]]] = {}
    for b in barter:
        for m in b["materials"]:
            entry = {
                "cn": b["cn"],
                "jp": b["jp"],
                "type": b["type"],
                "qty": m["qty"],
                "location": b["location"],
                "note": b["note"],
            }
            if b.get("weaponTier"):
                entry["weaponTier"] = b["weaponTier"]
            mat_map.setdefault(m["material"], []).append(entry)
    materials = [
        {"material": mat, "totalUses": len(uses), "usedIn": uses}
        for mat, uses in sorted(mat_map.items(), key=lambda kv: (-len(kv[1]), kv[0]))
    ]

    ordered_towns = sorted(
        towns.values(),
        key=lambda t: (not t["priority"], -len(t["items"]), t["cn"]),
    )
    for t in ordered_towns:
        t.pop("priority", None)

    wt_out: dict[str, Any] | None = None
    if weapon_tiers:
        wt_list = []
        for w in weapon_tiers.get("weapons") or []:
            jp = w.get("jp", "")
            places = list(dict.fromkeys(weapon_places.get(jp, [])))
            wt_list.append({
                "tier": w.get("tier", ""),
                "name": w.get("name", ""),
                "repoName": w.get("repoName") or w.get("name", ""),
                "forge": w.get("forge", ""),
                "jp": jp,
                "type": w.get("type", ""),
                "rank": w.get("rank", ""),
                "might": w.get("might"),
                "hit": w.get("hit"),
                "crit": w.get("crit"),
                "avoid": w.get("avoid"),
                "range": w.get("range", ""),
                "weight": w.get("weight"),
                "durability": w.get("durability"),
                "effect": w.get("effect", ""),
                "description": w.get("description", ""),
                "reason": w.get("reason", ""),
                "shopPlaces": places,
            })
        wt_out = {
            "source": weapon_tiers.get("source", {}),
            "weapons": wt_list,
        }

    return {
        "towns": ordered_towns,
        "barter": barter,
        "materials": materials,
        "weaponTiers": wt_out,
        "categories": cfg.get("categories", ["全部"]),
        "notes": cfg.get("notes", []),
        "sources": cfg.get("sources", ""),
        "csvRows": csv_rows,
    }


def export_csv(csv_rows: list[list[Any]], out_path: str | Path) -> None:
    with open(out_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["城镇", "英文名", "类别", "物品", "原名", "价格G", "库存", "备注", "来源"])
        writer.writerows(csv_rows)
