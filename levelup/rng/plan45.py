"""到 Lv45 的最优路线（Yizhuo 11-08）：可以转上级职业，但每人只转一次。
和到 Lv35 的路线分开算；再算「按 35 级路线走到 35、之后再最优」，看 35 级前的选择对 45 级有没有影响。
输出 plan45.json。

假设：上级职业的技能要求（多数是 B）到 35 级时练够了，所以只按等级算成功率（Lv35 起 100%，34 级 50%，33 级 32%）。
"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import contextlib, io
import run_plans as R
from planner import plan_all, STATS, exam_tiers
with contextlib.redirect_stdout(io.StringIO()):
    from make_sheet import MAX_EXAMS

HERE = os.path.dirname(os.path.abspath(__file__))
MAX45 = 6
PHYS_ADV = ["侍道", "勇士", "狙击手", "巨型重甲兵", "卫士", "游侠", "锻造师"]
MAGIC_ADV = ["先知", "主教", "游唱诗人"]
ADV = {
    "迪托利希": PHYS_ADV, "米迦艾拉": PHYS_ADV, "奇洛伊卡": PHYS_ADV,
    "伊欧": PHYS_ADV + ["荣光骑士", "森林骑士", "铁甲骑兵"],          # 骑罗西南
    "艾丝梅拉尔达": PHYS_ADV + ["驭龙兵", "铁甲骑兵"],                # 天翼兵/骑甲鸵兵
    "努蒂奴": PHYS_ADV + ["驭龙兵", "铁甲骑兵"],
    "法毕欧": MAGIC_ADV + ["锻造师"], "杨界": MAGIC_ADV, "乌尔坦德": MAGIC_ADV,
}


RANKS = ["E", "E+", "D", "D+", "C", "C+", "B", "B+", "A", "A+", "S", "S+"]


def adv_ok(name, cls):
    """上级职业：现在的技能离要求差 ≤ 2 段（到 35 级练得到）才算能转。"""
    r = R.exam_req(name, cls)
    return r is not None and r[1] <= 2


def net(p, plan):
    """总分 − 每次转职的门槛（中级/上级按中级门槛，初级/跳过按初级门槛）：比较不同转职次数的路线用。"""
    from planner import plan_gold
    return plan.total - plan_gold(p, plan) / p.gold_per_pt   # 11-08 晚：门槛按手形金币（和 DP 同一套成本）


def best_net(p, k):
    plans = [p.best_plan(i) for i in range(k + 1)]
    plans = [x for x in plans if x is not None and x.total > 0]
    return max(plans, key=lambda x: (net(p, x), -x.exams))


def mk45(name):
    p = R.make_planner(name, 45)
    adv = [c for c in ADV[name] if c not in p.owned and adv_ok(name, c)]
    p.exam_options = tuple(p.exam_options) + tuple(adv)
    for c in adv:
        p.exam_req[c] = (35, 0)
        p.confident.add(c)
    p.adv_cap = 1
    return p


def steps_of(p, plan):
    out, lv = [], p.level
    for r in plan.rows:
        if r.action == "升级":
            out.append({"lv": lv, "cls": r.cls, "gains": [STATS[i] for i, g in enumerate(r.gains) if g], "score": r.score + r.bonus})
            lv += 1
        else:
            out.append({"lv": lv, "exam": r.cls})
    return out


def summary(p, plan):
    add = [0] * 9
    for r in plan.rows:
        if r.action == "升级":
            add = [a + g for a, g in zip(add, r.gains)]
    return add


res = {}
for name in R.OWNED:
    p35 = R.make_planner(name, 35)
    plans35, k35 = plan_all(p35, MAX_EXAMS)
    plan35 = plans35[k35]
    p = mk45(name)
    best = best_net(p, MAX45)
    # 按 35 级路线走到 35，之后再最优（35 级前的动作固定）
    pf = mk45(name)
    pf.forced = tuple(plan35.raw_actions)
    follow = best_net(pf, MAX45)
    s35 = steps_of(p35, plan35)
    s45 = steps_of(p, best)
    sf = steps_of(pf, follow)
    # 会影响 45 级的只有 35 级前的转职/跳过（时机、次数、拿到哪些职业）；同一级换已有职业只影响那一级的加点
    ex35 = [(x["lv"], x["exam"]) for x in s35 if "exam" in x]
    ex45 = [(x["lv"], x["exam"]) for x in s45 if "exam" in x and x["lv"] < 35]
    diffs = []
    if ex35 != ex45:
        diffs.append({"r35": [f"Lv{l} {e}" for l, e in ex35], "r45": [f"Lv{l} {e}" for l, e in ex45]})
    adv = [x for x in s45 if "exam" in x and x["exam"] in ADV[name]]
    fadv = [x for x in sf if "exam" in x and x["exam"] in ADV[name]]
    res[name] = {
        "from": p.level, "total": best.total, "pts": sum(summary(p, best)), "add": summary(p, best),
        "steps": s45, "adv": adv[0] if adv else None, "exams": best.exams,
        "net": net(p, best), "advOptions": [c for c in ADV[name] if c in p.exam_options],
        "follow": {"total": follow.total, "pts": sum(summary(pf, follow)), "net": net(pf, follow), "exams": follow.exams,
                   "steps": sf, "adv": fadv[0] if fadv else None},
        "diffs": diffs, "loss": round(net(p, best) - net(pf, follow), 1),
        "plan35": {"total": plan35.total},
    }
    print(name, "45最优", best.total, net(p, best), "按35走", follow.total, net(pf, follow), "上级", adv[0] if adv else None,
          "转职", [(x["lv"], x["exam"]) for x in s45 if "exam" in x], "可选上级", [c for c in ADV[name] if c in p.exam_options])
    for d in diffs:
        print("    35:", d["r35"], " 45:", d["r45"])
json.dump(res, open(os.path.join(HERE, "plan45.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
