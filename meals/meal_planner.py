"""吃饭规划（11-25 Yizhuo）：每道菜给出三人一桌的组合，perfect 优先；没有 perfect 时给备选。

规则
- 闪光：最爱 2、喜欢 1、普通 0；三人 1+1+1 或 2+2+0 = perfect（Yizhuo 11-08）。2+1+0 等未确认，只当备选。
- 讨厌这道菜的人不上桌。好感满了（maxed）、不在队伍附近（absent）的人不上桌。
- 不按主角筛人：所有角色和领主都是候选，一桌三人按「有用的支援对」打分。
  支援是两两之间涨的，一对 (领主, 目标) 有用 = 目标在该领主那条线还要靠支援挖，分数见 meal_config.json 的 goals。
- 游戏规则：还没入队的人要和当前主角同桌才请得动（gamewith），开关 unscouted_need_current_lord。
- 排序：perfect 在前 → 分数高 → 闪光多 → 表里靠前的人。每个 goal 至少有一桌出现在该菜的选项里（有得选时）。

用法：python3 meal_planner.py [--config meal_config.json]  → 打印表格，写 meal_plan.json
"""
import argparse
import itertools
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
SPK = ["讨厌", "普通", "喜欢", "最爱"]


def load_people(tab_path, cfg):
    """diet_tab.json 每行 → {name, pref[12], rep{route: 名声}}，加上领主。顺序 = 表里顺序（同分时靠前的优先）。"""
    rows = json.load(open(tab_path, encoding="utf-8"))
    dishes = [h.split(" - ")[1] for h in rows[0][13:25]]
    people, seen = [], set()
    for r in rows[1:]:
        if len(r) < 25 or not r[8] or r[8] in seen:
            continue
        seen.add(r[8])
        rep = {m.group(1): int(m.group(2)) for m in re.finditer(r"(\S+?)（名声(\d+)", (r[1] or "") + " " + (r[2] or ""))}
        people.append({"name": r[8], "pref": [int(x) for x in r[13:25]], "rep": rep})
    for n, p in cfg.get("lord_prefs", {}).items():
        if n not in seen:
            people.append({"name": n, "pref": list(p), "rep": {}, "lord": True})
    return dishes, people


def sparkle(v):
    return [x - 1 for x in v]


def is_perfect(v):
    """v = 三人的好感（0～3）。"""
    if min(v) == 0:
        return False
    sp = sorted(sparkle(v))
    return sp[0] >= 1 or sp == [0, 2, 2]


def pair_weights(people, cfg):
    """{(领主, 目标): 分数}：目标还没入队、在这条线要挖、名声在范围内。"""
    rec = set(cfg.get("recruited", []))
    names = {p["name"] for p in people}
    w = {}
    for g in cfg.get("goals", []):
        if g["lord"] not in names:
            continue
        skip = set(g.get("skip", []))
        for p in people:
            n, r = p["name"], p["rep"].get(g["route"])
            if r is None or n in rec or n in skip or n == g["lord"]:
                continue
            if "renown_weight" in g:
                s = g["renown_weight"].get(str(r), 0)
            else:
                s = g.get("weight", 1) if r <= g.get("max_renown", 99) else 0
            if s:
                w[(g["lord"], n)] = w.get((g["lord"], n), 0) + s
    return w


def table_score(names, w):
    return sum(w.get((a, b), 0) + w.get((b, a), 0) for a, b in itertools.combinations(names, 2))


def plan(cfg, tab_path=os.path.join(HERE, "diet_tab.json")):
    dishes, people = load_people(tab_path, cfg)
    out_of = set(cfg.get("maxed", [])) | set(cfg.get("absent", []))
    cand = [p for p in people if p["name"] not in out_of]
    order = {p["name"]: i for i, p in enumerate(cand)}
    w = pair_weights(cand, cfg)
    rec = set(cfg.get("recruited", []))
    lord = cfg.get("current_lord")
    need_lord = cfg.get("unscouted_need_current_lord", False) and lord
    useful = {n for pr in w for n in pr}
    k = cfg.get("options_per_dish", 3)
    res = []
    for i, d in enumerate(dishes):
        pool = [p for p in cand if p["pref"][i] > 0 and p["name"] in useful | ({lord} if need_lord else set())]
        tables = []
        for t in itertools.combinations(pool, 3):
            ns = [p["name"] for p in t]
            s = table_score(ns, w)
            if s <= 0:
                continue
            if need_lord and lord not in ns and any(n not in rec for n in ns):
                continue
            v = [p["pref"][i] for p in t]
            tables.append({"who": ns, "pref": v, "sparkle": sparkle(v), "perfect": is_perfect(v), "score": s,
                           "pairs": [[a, b] for a, b in w if a in ns and b in ns],
                           "_k": (not is_perfect(v), -s, -sum(v), sorted(order[n] for n in ns))})
        tables.sort(key=lambda x: x["_k"])
        pick = tables[:k]
        for g in cfg.get("goals", []):   # 每个 goal 至少一桌（同样 perfect 的优先）
            hit = [t for t in tables if any(a == g["lord"] for a, _ in t["pairs"])]
            if hit and not any(t in pick for t in hit):
                pick.append(next((t for t in hit if t["perfect"]), hit[0]))
        for t in tables:
            t.pop("_k")
        res.append({"dish": d, "perfect": bool(tables) and tables[0]["perfect"], "options": pick})
    return {"dishes": res, "weights": [{"lord": a, "target": b, "score": s} for (a, b), s in sorted(w.items(), key=lambda x: (-x[1], order[x[0][1]]))]}


def fmt(t):
    sp = "+".join(str(x) for x in t["sparkle"])
    return f"{' + '.join(t['who'])}（{sp}，{'perfect' if t['perfect'] else '非 perfect'}，分 {t['score']}）"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=os.path.join(HERE, "meal_config.json"))
    ap.add_argument("--out", default=os.path.join(HERE, "meal_plan.json"))
    a = ap.parse_args()
    cfg = json.load(open(a.config, encoding="utf-8"))
    p = plan(cfg)
    json.dump(p, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    for r in p["dishes"]:
        print(f"{r['dish']}：" + ("；".join(fmt(t) for t in r["options"]) or "没有能用的组合"))
    print("目标：", "、".join(f"{x['lord']}–{x['target']}({x['score']})" for x in p["weights"]))


if __name__ == "__main__":
    main()
