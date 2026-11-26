"""吃饭规划（11-25 Yizhuo）：每道菜给出三人一桌的组合，perfect 优先；没有 perfect 时给备选。

规则
- 闪光：最爱 2、喜欢 1、普通 0；三人 1+1+1 或 2+2+0 = perfect（Yizhuo 11-08）。2+1+0 等未确认，只当备选。
- 讨厌这道菜的人不上桌。招这个人只要支援 1 的不列（min_support 2）；支援 2 就能招的单独列出。好感满了（maxed）、不在队伍附近（absent）的人不上桌。
- 不按主角筛人：所有角色和领主都是候选，一桌三人按「有用的支援对」打分。
  支援是两两之间涨的，一对 (领主, 目标) 有用 = 目标在该领主那条线还要靠支援挖，分数见 meal_config.json 的 goals。
- 任何三个人都能一桌，不用带当前主角（Yizhuo 11-25 游戏里确认；gamewith 说要带，是错的）。开关 unscouted_need_current_lord 默认关。
- 凑数（不涨有用支援）的座位只用已入队的人。
- 排序：perfect 在前 → 分数高 → 闪光多 → 表里靠前的人。这道菜有 perfect 就只列 perfect；每个 goal 至少有一桌（有得选时）。

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
    """diet_tab.json 每行 → {name, pref[12], rep{route: 名声}, sup{route: 要的支援等级}}，加上领主。顺序 = 表里顺序（同分时靠前的优先）。"""
    rows = json.load(open(tab_path, encoding="utf-8"))
    dishes = [h.split(" - ")[1] for h in rows[0][13:25]]
    people, seen = [], set()
    for r in rows[1:]:
        if len(r) < 25 or not r[8] or r[8] in seen:
            continue
        seen.add(r[8])
        rep = {m.group(1): int(m.group(2)) for m in re.finditer(r"(\S+?)（名声(\d+)", (r[1] or "") + " " + (r[2] or ""))}
        sup = {m.group(1): int(m.group(2)) for m in re.finditer(r"(\S+?)（名声\d+/支援(\d+)", (r[1] or "") + " " + (r[2] or ""))}
        people.append({"name": r[8], "pref": [int(x) for x in r[13:25]], "rep": rep, "sup": sup, "tier": r[0] or ""})
    for n, p in cfg.get("lord_prefs", {}).items():
        if n not in seen:
            people.append({"name": n, "pref": list(p), "rep": {}, "sup": {}, "lord": True})
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
    done = {tuple(x) for x in cfg.get("pairs_done", [])}   # 支援已经够了的 (领主, 目标)
    w, need = {}, {}
    for g in cfg.get("goals", []):
        if g["lord"] not in names:
            continue
        skip = set(g.get("skip", []))
        for p in people:
            n, r = p["name"], p["rep"].get(g["route"])
            if r is None or n in rec or n in skip or n == g["lord"]:
                continue
            if (g["lord"], n) in done:
                continue
            if p["sup"].get(g["route"], 99) < g.get("min_support", 0):
                continue   # 11-25：支援 1 就能招的不用吃饭
            if "tiers" in g and not any(p.get("tier", "").startswith(t) for t in g["tiers"]):
                continue   # 招募表第一栏（迪线招募）：只要还要招的
            if "renown_weight" in g:
                s = g["renown_weight"].get(str(r), 0) or g.get("support_weight", {}).get(str(p["sup"].get(g["route"])), 0)
            else:
                s = g.get("weight", 1) if r <= g.get("max_renown", 99) else 0
            if s:
                w[(g["lord"], n)] = w.get((g["lord"], n), 0) + s
                need[(g["lord"], n)] = p["sup"].get(g["route"])
    pair_weights.need = need
    return w


def table_score(names, w):
    return sum(w.get((a, b), 0) + w.get((b, a), 0) for a, b in itertools.combinations(names, 2))


def plan(cfg, tab_path=os.path.join(HERE, "diet_tab.json")):
    dishes, people = load_people(tab_path, cfg)
    out_of = set(cfg.get("maxed", [])) | set(cfg.get("absent", []))
    cand = [p for p in people if p["name"] not in out_of]
    order = {p["name"]: i for i, p in enumerate(cand)}
    pref = {p["name"]: p["pref"] for p in cand}
    w = pair_weights(cand, cfg)
    rec = set(cfg.get("recruited", []))
    lord = cfg.get("current_lord")
    need_lord = cfg.get("unscouted_need_current_lord", False) and lord
    useful = {n for pr in w for n in pr}
    lord_rank = {lord: 0, **{g["lord"]: 1 for g in cfg.get("goals", []) if g["lord"] != lord}}
    k = cfg.get("options_per_dish", 3)
    res = []
    for i, d in enumerate(dishes):
        # 候选：有用的人 + 已入队的人（凑数用，同分时优先已入队的凑数，不占没入队目标的名额）
        pool = [p for p in cand if p["pref"][i] > 0 and p["name"] in useful | rec | ({lord} if need_lord else set())]
        tables = []
        for t in itertools.combinations(pool, 3):
            ns = sorted((p["name"] for p in t), key=lambda n: (lord_rank.get(n, 9), order[n]))   # 主角排第一，其他领主第二
            s = table_score(ns, w)
            if s <= 0:
                continue
            if need_lord and lord not in ns and any(n not in rec for n in ns):
                continue
            v = [pref[n][i] for n in ns]   # 和 who 同一顺序
            tables.append({"who": ns, "pref": v, "sparkle": sparkle(v), "perfect": is_perfect(v), "score": s,
                           "pairs": (pr := [[a, b] for a, b in w if a in ns and b in ns]),
                           "filler": [n for n in ns if not any(n in x for x in pr)],
                           "_k": (not is_perfect(v), -s, -sum(v), sorted(order[n] for n in ns))})
        tables = [t for t in tables if all(n in rec for n in t["filler"])]   # 凑数只用已入队的；没入队的人上桌必须有用
        tables.sort(key=lambda x: x["_k"])
        pick = tables[:k]
        any_pf = bool(tables) and tables[0]["perfect"]
        for g in cfg.get("goals", []):   # 每个 goal 至少一桌；这道菜有 perfect 时只补 perfect 的
            hit = [t for t in tables if any(a == g["lord"] for a, _ in t["pairs"]) and (t["perfect"] or not any_pf)]
            if hit and not any(t in pick for t in hit):
                pick.append(hit[0])
        if any_pf:
            pick = [t for t in pick if t["perfect"]]
        for t in tables:
            t.pop("_k")
        res.append({"dish": d, "perfect": bool(tables) and tables[0]["perfect"], "options": pick})
    need = pair_weights.need
    return {"dishes": res, "weights": [{"lord": a, "target": b, "score": s, "support": need.get((a, b))} for (a, b), s in sorted(w.items(), key=lambda x: (-x[1], order[x[0][1]]))]}


def fmt(t):
    sp = "+".join(str(x) for x in t["sparkle"])
    fl = f"，{'、'.join(t['filler'])}凑数" if t["filler"] else ""
    return f"{' + '.join(t['who'])}（{sp}，{'perfect' if t['perfect'] else '非 perfect'}，分 {t['score']}{fl}）"


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
    print("目标：", "、".join(f"{x['lord']}–{x['target']}(分{x['score']}，要支援{x['support']})" for x in p["weights"]))
    lv2 = [x for x in p["weights"] if x["support"] == 2 and x["lord"] == cfg.get("current_lord")]
    print("主角线支援 2 就能招：", "、".join(x["target"] for x in lv2) or "没有")


if __name__ == "__main__":
    main()
