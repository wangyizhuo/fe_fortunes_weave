"""每人职业选择清单（Yizhuo 11-16：「主要转职的中级职业 + 额外的中级/初级职业」列成清单，自己选）→ options.json。

每个可考职业单独算一遍：一定要考到它（rule_run 的 must），其余照规则走，和「只考必考职业」的基准路线比。
  * 到目标级（Lv35 或 +15）和到 Lv45 各算一次；「35 级之后」= 到 Lv45 的差 − 到目标级的差
  * 训练：清单里所有档位都允许先练技能（标出要练几段、按本档每段扣分），规则默认 P1/P2 不练的也列出来让 Yizhuo 自己选
  * 判定值、估计成功率、考试时等级、用它升几级、保底补的项
"""
import json, os
import run_plans as R
from planner import STATS

HERE = os.path.dirname(os.path.abspath(__file__))


def planner(name, target, train):
    p = R.make_planner(name, target)
    if train and not p.exam_train_ranks:   # P1/P2：清单里也算「先练够」的版本
        p.exam_train_ranks = {c: r[1] for c, r in p.exam_req.items() if r[1] > 0}
        p.exam_req = {c: (r[0], 0) for c, r in p.exam_req.items()}
    p.min_exam_gain = 0
    return p


def run(p, targets):
    r = p.rule_run(list(dict.fromkeys(list(p.required) + targets)), tuple(targets))
    if r is None:
        return None
    acts, _, total, gold, _ = r
    g, done, lv_exam, used = [0] * 9, 0, {}, {}
    for st, (a, c) in enumerate(acts):
        if a == "升级":
            g = [x + y for x, y in zip(g, p.result(st, p.level + done, c)[1])]
            used[c] = used.get(c, 0) + 1
            done += 1
        elif c not in (None, "跳过"):
            lv_exam.setdefault(c, (st, p.level + done))
    return dict(acts=acts, total=total, gold=gold, g=g, net=p.plan_net(acts, total, gold),
                train=p.train_ranks(acts), floor=p.floor_lifts(acts), lv_exam=lv_exam, used=used)


def diff(a, b):
    return {"g": [x - y for x, y in zip(a["g"], b["g"])], "total": a["total"] - b["total"],
            "net": round(a["net"] - b["net"], 1), "gold": a["gold"] - b["gold"], "train": a["train"] - b["train"]}


def now_pct(name, c, lv):
    """不练技能、按现在技能的估计成功率。"""
    q = R.exam_req(name, c)
    if not q:
        return None
    rec_lv, gap = q
    pct = 100 if gap <= 0 else 50 if gap == 1 else 0
    d = rec_lv - lv
    return min(pct, 100 if d <= 0 else 50 if d == 1 else 32 if d == 2 else 0)


def build(name):
    T = R.TARGET[name]
    out = {"name": name, "tier": R.tier_of(name), "level": R.current_state(name)[1], "target": T,
           "owned": list(R.OWNED[name]), "required": list(R.REQUIRED.get(name, [])),
           "trainAllowed": R.TRAIN_ALLOWED[R.tier_of(name)], "options": []}
    pT, p45 = planner(name, T, True), planner(name, 45, True)
    bT, b45 = run(pT, []), run(p45, [])
    rec = R.make_planner(name, T).rule_plan()
    out["recommended"] = [c for a, c in rec.raw_actions if a == "考试" and c != "跳过" and c not in R.REQUIRED.get(name, [])]
    # 现在规划器推荐的组合，和基准比（同一套计分）
    if out["recommended"]:
        rT, r45 = run(pT, out["recommended"]), run(p45, out["recommended"])
        dT = diff(rT, bT)
        d45 = diff(r45, b45) if r45 else None
        out["recRow"] = {"toT": dT, "after": None if d45 is None else {"g": [x - y for x, y in zip(d45["g"], dT["g"])],
                                                                        "total": d45["total"] - dT["total"], "net": round(d45["net"] - dT["net"], 1)}}
    for c in R.EXAM_OPTIONS[name]:
        if c in R.OWNED[name] or c in R.REQUIRED.get(name, []):
            continue
        aT, a45 = run(pT, [c]), run(p45, [c])
        if not aT or c not in aT["lv_exam"]:
            out["options"].append({"cls": c, "tier": R._TIER_OF(c), "ok": False, "why": "到目标级前没有能考过的种子"})
            continue
        st, lv = aT["lv_exam"][c]
        dT = diff(aT, bT)
        d45 = diff(a45, b45) if a45 and c in a45["lv_exam"] else None
        after = None if d45 is None else {"g": [x - y for x, y in zip(d45["g"], dT["g"])], "total": d45["total"] - dT["total"],
                                          "net": round(d45["net"] - dT["net"], 1)}
        out["options"].append({
            "cls": c, "tier": R._TIER_OF(c), "ok": True, "lv": lv, "roll": round(pT.exam_value(st), 2),
            "pct": pT.exam_pct(c, lv), "pctNow": now_pct(name, c, lv), "train": pT.exam_train.get(c) or [], "ranks": pT.exam_train_ranks.get(c, 0),
            "used": aT["used"].get(c, 0), "used45": (a45 or {}).get("used", {}).get(c, 0),
            "floor": [f"{STATS[i]} {x}→{v}" for lifts in aT["floor"].values() for i, x, v in lifts],
            "toT": dT, "after": after, "rec": c in out["recommended"],
            "ruleBlocked": bool(pT.exam_train_ranks.get(c)) and not out["trainAllowed"]})
    out["options"].sort(key=lambda o: (not o.get("ok"), -(o.get("toT", {}).get("net", -999))))
    return out


if __name__ == "__main__":
    res = {n: build(n) for n in R.ORDER}
    json.dump(res, open(os.path.join(HERE, "options.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    for n, v in res.items():
        print(n, v["tier"], f"Lv{v['level']}→{v['target']}", "推荐", v["recommended"])
        for o in v["options"][:6]:
            if o.get("ok"):
                print(f"   {o['cls']}{'*' if o['rec'] else ''} Lv{o['lv']} 判定{o['roll']} 估{o['pct']} 练{o['ranks']} 用{o['used']}/{o['used45']} "
                      f"到{v['target']} 净{o['toT']['net']:+} 分{o['toT']['total']:+} 金{o['toT']['gold']:+} 之后 净{o['after']['net'] if o['after'] else '—'}")
