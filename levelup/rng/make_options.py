"""每人职业选择清单（Yizhuo 11-16：「主要转职的中级职业 + 额外的中级/初级职业」列成清单，自己选）→ options.json。

每个可考职业单独算一遍：一定要考到它（rule_run 的 must），其余照规则走，和「只考必考职业」的基准路线比。
  * 到目标级（Lv35 或 +15）和到 Lv45 各算一次；「35 级之后」= 到 Lv45 的差 − 到目标级的差
  * 11-17 Yizhuo：两条路线按「用掉同样多的乱数」比（考了的那条会少升一级），不按到同一级比
  * 训练：P0 允许先练技能（标出要练几段、按本档每段扣分）；P1/P2 按规则不练（只有规则破例的那个中级可以练），
    不练考不过的职业按「先练够」算出来、标 ruleBlocked，页面折起来不当建议（11-23 Yizhuo）
  * 判定值、估计成功率、考试时等级、用它升几级、保底补的项
"""
import json, os
import run_plans as R
from planner import STATS

HERE = os.path.dirname(os.path.abspath(__file__))


def planner(name, target, train):
    p = R.make_planner(name, target)
    if train:   # 清单里算「先练够」的版本：对所有仍有技能差的职业补齐训练并移除练前成功率
        extra_ranks = {c: r[1] for c, r in p.exam_req.items() if r[1] > 0}
        if extra_ranks:
            p.exam_train_ranks = dict(p.exam_train_ranks or {}, **extra_ranks)
            p.exam_req = {c: (r[0], 0) for c, r in p.exam_req.items()}
            p.exam_chance = {k: v for k, v in (p.exam_chance or {}).items() if k not in extra_ranks}
    p.min_exam_gain = 0
    return p


def run(p, targets, S=None):
    p.seed_budget = S
    try:
        r = p.rule_run(list(dict.fromkeys(list(p.required) + targets)), tuple(targets))
    finally:
        p.seed_budget = None
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
    return dict(acts=acts, total=total, gold=gold, g=g, net=p.plan_net(acts, total, gold), end=p.level + done,
                train=p.train_ranks(acts), floor=p.floor_lifts(acts), lv_exam=lv_exam, used=used)


def eq(p, ta, tb):
    """11-25 Yizhuo：两条路线都在同样多的乱数（p.n_seeds）里走，直接比。"""
    return run(p, ta), run(p, tb)


def diff(a, b):
    return {"g": [x - y for x, y in zip(a["g"], b["g"])], "total": a["total"] - b["total"],
            "net": round(a["net"] - b["net"], 1), "gold": a["gold"] - b["gold"], "train": a["train"] - b["train"],
            "seeds": len(a["acts"]), "endA": a["end"], "endB": b["end"]}


def now_pct(name, c, lv):
    """不练技能、按现在技能的估计成功率。"""
    q = R.exam_req(name, c)
    if not q:
        return None
    from planner import exam_rate
    return exam_rate(lv - q[0], q[1])


MID = "中级"


def _metrics(p, acts, total, gold):
    """路线的能力加点、点数、加权分、保底（点数/加权）、金币——分开给，不合成净值（Yizhuo 11-17）。"""
    g, done, used = [0] * 9, 0, {}
    for st, (a, c) in enumerate(acts):
        if a == "升级":
            g = [x + y for x, y in zip(g, p.result(st, p.level + done, c)[1])]
            used[c] = used.get(c, 0) + 1
            done += 1
    lifts = [(i, x, v) for ls in p.floor_lifts(acts).values() for i, x, v in ls]
    return {"g": g, "total": total, "gold": gold, "end": p.level + done, "used": used,
            "floorPts": sum(v - x for _, x, v in lifts), "floorW": sum(p.weights[i] * (v - x) for i, x, v in lifts),
            "floor": [f"{STATS[i]} {x}→{v}" for i, x, v in lifts]}


def skip_mid(name, target):
    """11-18 Yizhuo：规划里要「跳过」的那一级，判定值好（能考过）的话改成考一个中级职业，能不能提高数值。
    每个跳过的种子 × 每个没有的中级职业：这一步改考它（考过才算）、其余照规则走，和原路线按同样多的乱数比。
    所有档位都列（不分 P0/P1/P2）；要练技能的写段数，不练的成功率也写出来。"""
    p = R.make_planner(name, target)
    pl = p.rule_plan()
    # 11-23 Yizhuo（「要先练 6 段的为什么需要考虑」）：不练技能的档位（P1/P2）只有规则破例的那个中级可以练，其余要练的标「规则不考虑」，页面不拿它当建议
    no_train = not R.TRAIN_ALLOWED[R.tier_of(name)]
    mid_ok = getattr(p, "mid_trained", None)
    if pl is None:
        return {"target": target, "skips": []}
    base_acts, base_at, base_tg = pl.raw_actions, dict(p.exam_at or {}), list(pl.targets)
    S = len(base_acts)
    # 原路线（同一个窗口）重算一遍，拿加点/保底
    p.seed_budget, p.exam_at = S, base_at
    try:
        rb = p.rule_run(base_tg)
    finally:
        p.seed_budget = None
    base = _metrics(p, rb[0], rb[2], rb[3])
    base["gold"] = pl.gold          # 没用来升级的职业按跳过算钱（和路线页一致）
    q = planner(name, target, True)   # 允许先练技能的版本（只用来判断能不能考过、算这个职业）
    q.exam_at = {}
    mids = [c for c in R.EXAM_OPTIONS[name] if R._TIER_OF(c) == MID and c not in R.OWNED[name] and c not in base_tg]
    out = []
    done = 0
    for st, (a, c0) in enumerate(base_acts):
        lv = p.level + done
        if a == "升级":
            done += 1
            continue
        if c0 != "跳过":
            continue
        row = {"step": st, "lv": lv, "roll": round(p.exam_value(st), 2), "opts": []}
        for c in mids:
            pct, pnow = q.exam_pct(c, lv), now_pct(name, c, lv)
            roll = p.exam_value(st)
            ok, oknow = pct is not None and roll < pct, pnow is not None and roll < pnow
            o = {"cls": c, "pct": pct, "pctNow": pnow, "ok": ok, "okNow": oknow,
                 "ranks": 0 if oknow else q.exam_train_ranks.get(c, 0), "train": [] if oknow else (q.exam_train.get(c) or [])}
            o["ruleBlocked"] = bool(o["ranks"]) and no_train and c != mid_ok
            if not ok:
                out_why = "判定值高于成功率，考不过" if pct else "等级/技能不够，成功率 0"
                row["opts"].append(dict(o, why=out_why))
                continue
            q.exam_at, q.seed_budget = {**base_at, st: c}, S
            try:
                r = q.rule_run(base_tg + [c], (c,))
            finally:
                q.seed_budget = None
            if r is None or ("考试", c) not in r[0]:
                row["opts"].append(dict(o, ok=False, why="照规则走不通"))
                continue
            m = _metrics(q, r[0], r[2], r[3])
            # 考进去却没用来升级：页面上会显示成「跳过」，金币按初级算，但保底照拿
            if not m["used"].get(c):
                m["gold"] -= p.permit_gold[MID] - p.permit_gold["初级"]
            d = {"g": [x - y for x, y in zip(m["g"], base["g"])], "pts": sum(m["g"]) - sum(base["g"]),
                 "total": round(m["total"] - base["total"], 1),
                 "floorPts": m["floorPts"] - base["floorPts"], "floorW": m["floorW"] - base["floorW"],
                 "gold": m["gold"] - base["gold"], "seeds": S, "endA": m["end"], "endB": base["end"]}
            # 只用来排序/标记：规划器内部换算（加权分 + 保底 − 金币÷每分金币 − 段×每段扣分），页面不合成一个数
            inner = d["total"] + d["floorW"] - d["gold"] / p.gold_per_pt - o["ranks"] * R.TRAIN_PTS[R.tier_of(name)]
            later = [(x, c2) for x, (a2, c2) in enumerate(r[0]) if a2 == "考试" and x != st]
            o.update(d=d, used=m["used"].get(c, 0), floor=[f for f in m["floor"] if f not in base["floor"]],
                     worth=inner >= R.MIN_EXAM_GAIN and not o["ruleBlocked"], inner=round(inner, 1),
                     acts=[f"{'跳过' if c2 == '跳过' else '考' + c2}@{x}" for x, c2 in later])
            row["opts"].append(o)
        row["opts"].sort(key=lambda o: (not o["ok"], -o.get("inner", -999)))
        out.append(row)
    return {"target": target, "seeds": S, "skips": out, "baseExams": [c for a, c in base_acts if a == "考试"]}


@__import__("timing").timed("make_options.build（每人）")
def build(name):
    T = R.TARGET[name]
    out = {"name": name, "tier": R.tier_of(name), "level": R.current_state(name)[1], "target": T,
           "owned": list(R.OWNED[name]), "required": list(R.REQUIRED.get(name, [])),
           "trainAllowed": R.TRAIN_ALLOWED[R.tier_of(name)], "options": []}
    pT, p45 = planner(name, T, True), planner(name, 45, True)
    rp = R.make_planner(name, T)
    rec = rp.rule_plan()
    mid_ok = getattr(rp, "mid_trained", None)   # P1/P2 规则破例可以练的那个中级
    # 11-23 Yizhuo（「要先练 6 段的为什么需要考虑」）：不练技能的档位按规则算（不练，只有破例的那个中级可以练）；
    # 不练考不过的职业才用「先练够」的版本算出来，标「规则不考虑」，页面折起来
    pR, pR45 = pT, p45
    if not out["trainAllowed"]:
        pR, pR45 = planner(name, T, False), planner(name, 45, False)
        for q in (pR, pR45):
            if mid_ok and mid_ok in q.exam_req and q.exam_req[mid_ok][1] > 0:
                q.exam_train_ranks = {mid_ok: q.exam_req[mid_ok][1]}
                q.exam_req = dict(q.exam_req, **{mid_ok: (q.exam_req[mid_ok][0], 0)})
                q.exam_chance = {k: v for k, v in (q.exam_chance or {}).items() if k != mid_ok}
    out["recommended"] = [c for a, c in rec.raw_actions if a == "考试" and c != "跳过" and c not in R.REQUIRED.get(name, [])]
    # 现在规划器推荐的组合，和基准比（同一套计分）
    if out["recommended"]:
        (rT, bT), (r45, b45) = eq(pR, out["recommended"], []), eq(pR45, out["recommended"], [])
        dT = diff(rT, bT)
        d45 = diff(r45, b45) if r45 else None
        out["recRow"] = {"toT": dT, "after": None if d45 is None else {"g": [x - y for x, y in zip(d45["g"], dT["g"])],
                                                                        "total": d45["total"] - dT["total"], "net": round(d45["net"] - dT["net"], 1)}}
    for c in R.EXAM_OPTIONS[name]:
        if c in R.OWNED[name] or c in R.REQUIRED.get(name, []):
            continue
        P, P45, blocked = pR, pR45, False
        (aT, bT), (a45, b45) = eq(P, [c], []), eq(P45, [c], [])
        if P is not pT and (not aT or c not in aT["lv_exam"]):
            P, P45, blocked = pT, p45, True
            (aT, bT), (a45, b45) = eq(P, [c], []), eq(P45, [c], [])
        if not aT or c not in aT["lv_exam"]:
            out["options"].append({"cls": c, "tier": R._TIER_OF(c), "ok": False, "why": "到目标级前没有能考过的种子"})
            continue
        st, lv = aT["lv_exam"][c]
        dT = diff(aT, bT)
        d45 = diff(a45, b45) if a45 and c in a45["lv_exam"] else None
        after = None if d45 is None else {"g": [x - y for x, y in zip(d45["g"], dT["g"])], "total": d45["total"] - dT["total"],
                                          "net": round(d45["net"] - dT["net"], 1)}
        out["options"].append({
            "cls": c, "tier": R._TIER_OF(c), "ok": True, "lv": lv, "roll": round(P.exam_value(st), 2),
            "pct": P.exam_pct(c, lv), "pctNow": now_pct(name, c, lv),
            "train": (P.exam_train.get(c) or []) if P.exam_train_ranks.get(c) else [], "ranks": P.exam_train_ranks.get(c, 0),
            "used": aT["used"].get(c, 0), "used45": (a45 or {}).get("used", {}).get(c, 0),
            "floor": [f"{STATS[i]} {x}→{v}" for lifts in aT["floor"].values() for i, x, v in lifts],
            "toT": dT, "after": after, "rec": c in out["recommended"],
            "ruleBlocked": blocked})
    out["skipMid"] = [skip_mid(name, T)] + ([skip_mid(name, 45)] if T < 45 else [])
    out["options"].sort(key=lambda o: (not o.get("ok"), -(o.get("toT", {}).get("total", -999))))
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
