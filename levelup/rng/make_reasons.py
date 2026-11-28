"""每人「为什么这样选」的记录（11-25 Yizhuo：选择原因都记下来，不要每次临时再算）→ reasons.json。

每次 build 由程序重新生成，页面「职业选择」每人卡片最上面和 data/characters/*.md 都直接显示：
  * 路线：到目标级的最终能力、点数、加权分、金币、练技能段数
  * 路线里每场考试：为什么考（你指定必考 / 跳过时顺便考到 / 每人都要考一个中级 / 规则算出来值得），
    和「不考这一场、其余照规则走」按同样多的乱数比：能力差、点数、加权分、金币、练技能段数
  * 每个没选的中级职业：为什么没选（技能差几段 + 本档不练、判定值高于成功率、到目标级更差多少……），
    和现在路线比的能力差、点数、加权分、金币、练技能段数（数字来自 options.json，同样多的乱数）
  * 不考虑的职业：个人排除、性别限定、魔力权重低
  * 你对这个人定过的决定（decisions.json）
输入：run_plans / planner（规划）、options.json（make_options 先跑）。
"""
import contextlib
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
with contextlib.redirect_stdout(io.StringIO()):
    import run_plans as R
from planner import STATS, plan_all, plan_gold, _TIER
from fe_growth import exam_roll
import timing
from compare import seed_diff, explain, exam_seed_summary

def stats_after(p, acts):
    """按动作走完的能力（含考进新职业时的保底）和到达的等级。"""
    st, lv = list(p.stats), p.level
    lifts = p.floor_lifts(acts)
    for step, (a, c) in enumerate(acts):
        for (i, o, n) in lifts.get(step, []):
            st[i] += n - o
        if a == "升级":
            st = [x + y for x, y in zip(st, p.result(step, lv, c)[1])]
            lv += 1
    return st, lv


def diff(p, a, b):
    d = [x - y for x, y in zip(a, b)]
    return {"g": d, "pts": sum(d), "w": sum(w * x for w, x in zip(p.weights, d))}


def exam_why(p, c, mids_in_route):
    fb = (getattr(p, "first_bad_info", None) or {}).get(c)
    if fb and fb["how"] == "你指定":
        return f"你指定在第 {fb['step'] + 1} 个乱数考"
    if fb and fb["how"] == "第一个不好的乱数":
        gains = "、".join(fb.get("gains") or []) or "无"
        cls_txt = f"用{fb['best_cls']}升级" if fb.get("best_cls") else "这一级最好升级"
        raw_s = fb.get("raw_s")
        s_val = fb.get("s")
        if raw_s is not None and s_val is not None and abs(float(s_val) - float(raw_s)) > 1e-6:
            bal = fb.get("bal_why") or "高权重能力差 >3 时每点 ±0.5"
            score_txt = f"涨 {gains}（原始加权 {raw_s} 分，因均衡加点微调「{bal}」权重按 ±0.5 浮动后为 {s_val} 分）"
        else:
            score_txt = f"涨 {gains}（加权 {s_val} 分）"
        return f"默认：第一个不好、又能考过的乱数（{cls_txt}{score_txt}，未来 15 级平均 {fb['avg15']}）。更早或更晚考的对比见下表，由你决定"
    if fb:
        return fb["how"]
    if c in p.required:
        return "你指定必考"
    if c in (getattr(p, "skip_take", ()) or ()):
        return "你指定：要跳过时用考这个职业来跳，保证拿到"
    if getattr(p, "require_mid", False) and _TIER.get(c) == "中级" and mids_in_route == [c]:
        return "每人都要考进一个中级（规则），这是不练技能能考、到目标级最好的一个"
    return "规则算出来值得考（比不考多的分超过门槛）"


def timing_part(p, acts, step, c):
    """11-25 Yizhuo：这场考试换到别的乱数考（其余照规则走，同样多的乱数）会怎样。
    每个能考过的乱数都算，差别按乱数对齐拆成 ①考试用掉的乱数 ②用不同职业升级 ③转职保底。"""
    targets = [x for a, x in acts if a == "考试" and x != "跳过"]
    base_at = {k: v for k, v in (getattr(p, "exam_at", None) or {}).items() if v != c}
    must = tuple(x for x in targets if x in p.keep_classes or x == c)
    out = []
    lv = p.level
    for st in range(len(acts)):
        if st != step and acts[st][0] != "考试":
            sv = p.exam_at
            p.exam_at = {**base_at, st: c}
            try:
                r = p.window_value(targets, len(acts), must)
            finally:
                p.exam_at = sv
            if r is not None and st < len(r[0]) and r[0][st] == ("考试", c):
                d = seed_diff(p, acts, r[0])
                d_alt = seed_diff(p, r[0], acts)
                lv_alt = p.level + sum(1 for a, _ in r[0][:st] if a == "升级")
                out.append({"step": st, "lv": lv_alt, "roll": round(p.exam_value(st), 2), "pct": p.exam_pct(c, lv_alt),
                            "exam": d["examPart"], "cls": d["classPart"], "floor": d["floorPart"], "total": d["total"],
                            "gold": plan_gold_acts(p, acts) - plan_gold_acts(p, r[0]),
                            "explain": explain(d, "现在", f"Lv{lv_alt} 考"),
                            "explainAlt": explain(d_alt, f"改在 Lv{lv_alt} 考", "现在")})
    out.sort(key=lambda x: (x["total"]["w"], x["total"]["pts"]))
    return out


def plan_gold_acts(p, acts):
    used = {x for a, x in acts if a == "升级"}
    g = 0
    for a, x in acts:
        if a == "考试":
            t = "初级" if x == "跳过" or (x not in used and x not in p.keep_classes) else _TIER.get(x, "中级")
            g += p.permit_gold.get(t, p.permit_gold["中级"])
    return g


def route_part(p, pl):
    acts = pl.raw_actions
    S = len(acts)
    st, lv = stats_after(p, acts)
    lifts_now = p.floor_lifts(acts)
    floor_w_now = p.floor_value(acts)
    gold, train = plan_gold(p, pl), p.train_ranks(acts)
    exams = [c for a, c in acts if a == "考试" and c != "跳过"]
    mids = [c for c in exams if _TIER.get(c) == "中级"]
    rows, lv_now = [], p.level
    for step, (a, c) in enumerate(acts):
        if a == "升级":
            lv_now += 1
            continue
        if c == "跳过":
            continue
        ub = p.class_usage_breakdown(acts, c)
        used = ub["used"]
        step_floor = [f"{STATS[i]}+{n - o}" for (i, o, n) in lifts_now.get(step, [])]
        row = {"cls": c, "tier": _TIER.get(c), "lv": lv_now, "roll": round(exam_roll(p.seed_at(step)) / 10_000, 2),
               "pct": p.exam_pct(c, lv_now), "used": used, "usedStrict": ub["strict"], "usedTied": ub["tied"],
               "strictLvs": ub["strictLvs"], "why": exam_why(p, c, mids),
               "floor": step_floor,
               # 11-25 Yizhuo：要练的技能在哪一级练好（考试那一级之前）
               "trainRanks": (p.exam_train_ranks or {}).get(c, 0) if (used or step_floor) else 0,
               "trainSkills": ((getattr(p, "exam_train", {}) or {}).get(c) or []) if (used or step_floor) and (p.exam_train_ranks or {}).get(c) else []}
        rest = [x for x in exams if x != c]
        keep_req = tuple(x for x in rest if x in p.required)
        sv, sk = p.required, getattr(p, "skip_take", ())
        p.required = tuple(x for x in p.required if x != c)   # 「不考这一场」：连必考、指定也拿掉，看它值多少
        p.skip_take = tuple(x for x in sk if x != c)
        try:
            r = p.window_value(rest, S, keep_req)
        finally:
            p.required, p.skip_take = sv, sk
        if r is None:
            row["vsDrop"] = None
            row["dropNote"] = "不考它的话照规则走不通（比如没有别的中级能考）"
        else:
            a2, _, g2, _ = r
            st2, lv2 = stats_after(p, a2)
            d = diff(p, st, st2)
            sd = seed_diff(p, acts, a2)
            d.update(gold=gold - g2, train=train - p.train_ranks(a2), lvDrop=lv2,
                     floorW=floor_w_now - p.floor_value(a2),
                     seedDiff=exam_seed_summary(sd, f"考{c}", f"不考{c}"),
                     dropExams=[x for y, x in a2 if y == "考试" and x != "跳过"],
                     dropSkips=sum(1 for y, x in a2 if x == "跳过"))
            row["vsDrop"] = d
        row["timing"] = timing_part(p, acts, step, c)
        rows.append(row)
    return {"seeds": S, "endLv": lv, "end": st, "pts": sum(st) - sum(p.stats),
            "w": sum(w * (x - y) for w, x, y in zip(p.weights, st, p.stats)),
            "gold": gold, "train": train, "skips": sum(1 for a, c in acts if c == "跳过"),
            "stopAdv": getattr(pl, "stop_adv", None), "exams": rows}


def mid_part(name, p, opts, route_classes):
    """没选的中级：原因 + 和现在路线的差（options.json 里每个选项和推荐组合都是对同一个基准、同样多乱数的差）。"""
    rec = (opts.get("recRow") or {}).get("toT")
    tier_name = opts.get("tier")
    out = []
    for o in opts.get("options", []):
        if o.get("floorOnly") or o.get("tier") != "中级" or o["cls"] in route_classes:
            continue
        row = {"cls": o["cls"], "floor": o.get("floor", [])}
        if not o.get("ok"):
            row["why"] = o.get("why") or "考不过"
        else:
            t = o["toT"]
            seed_diff_list = t.get("seedDiffVsRoute") if t.get("seedDiffVsRoute") is not None else (t.get("seedDiff") or [])
            if rec:
                g = [x - y for x, y in zip(t["g"], rec["g"])]
                row["vsRoute"] = {"g": g, "pts": sum(g), "w": t["total"] - rec["total"],
                                  "gold": t["gold"] - rec["gold"], "train": t.get("train", 0) - rec.get("train", 0),
                                  "seeds": t.get("seeds"), "endA": t.get("endA"), "endB": rec.get("endA"),
                                  "seedDiff": seed_diff_list}
            else:
                row["vsRoute"] = {"g": t["g"], "pts": sum(t["g"]), "w": t["total"], "gold": t["gold"], "train": t.get("train", 0),
                                  "seeds": t.get("seeds"), "endA": t.get("endA"), "endB": t.get("endB"),
                                  "seedDiff": seed_diff_list}
            row.update(lv=o["lv"], roll=o["roll"], pctNow=o.get("pctNow"), pct=o.get("pct"), ranks=o.get("ranks", 0),
                       train=o.get("train", []))
            v = row["vsRoute"]
            if o.get("ruleBlocked"):
                row["why"] = f"现在技能不够（{'、'.join(o.get('train', [])) or '差技能'}），{tier_name} 按规则不练技能，不练成功率 {o.get('pctNow', 0)}%"
            elif v["w"] < 0 or (v["w"] == 0 and v["pts"] < 0):
                row["why"] = "能考，但和现在路线比到目标级更差（同样多的乱数）"
            elif v["w"] == 0 and v["pts"] == 0:
                row["why"] = "能考，到目标级能力和现在路线一样" + ("，但要多花钱" if v["gold"] > 0 else "") + ("、多练技能" if v["train"] > 0 else "")
            else:
                row["why"] = "能考，到目标级略好，但规划器内部换算（含金币、练技能）没有超过门槛"
        out.append(row)
    return out


def excluded_part(name):
    out = []
    for c in R.ALL_CLASSES:
        if c in R.EXAM_OPTIONS[name]:
            continue
        if c in R.EXCLUDE.get(name, []):
            why = "你指定不考"
        elif R._CLASS_LIMIT.get(c) == "女性" and R._SEX.get(name) != "女":
            why = "女性限定"
        elif c in R.MAGIC and R.W[name][2] < R.MAGIC_MIN_WEIGHT:
            why = "魔力权重低，不考法系职业（规则）"
        else:
            why = "不在可考清单"
        out.append({"cls": c, "why": why})
    return out


SHORT = {"迪托利希": "迪", "艾丝梅拉尔达": "艾丝", "米迦艾拉": "米迦", "奇洛伊卡": "奇洛", "法毕欧": "法", "乌尔坦德": "乌", "努蒂奴": "努"}


def _for(name, scope):
    """这条决定是不是针对这个人（scope 用全名或简称，「、」分隔）；「全部」的规则不列，页面「我的决定」里有。"""
    parts = [x.strip() for x in scope.replace("，", "、").split("、")]
    return name in parts or SHORT.get(name) in parts


def build(name, opts, decisions):
    with timing.timed("make_reasons.build（每人）"):
        p = R.make_planner(name, R.TARGET[name])
        plans, k = plan_all(p, R.MAX_EXAMS)
        pl = plans[k]
        route = route_part(p, pl)
        cls_in_route = {e["cls"] for e in route["exams"]}
        return {
            "tier": R.tier_of(name), "level": p.level, "target": R.TARGET[name],
            "trainAllowed": bool(R.TRAIN_ALLOWED[R.tier_of(name)]),
            "skills": R.shot(name).get("skills", {}),
            "route": route,
            "mids": mid_part(name, p, opts.get(name, {}), cls_in_route | set(p.owned)),
            "excluded": excluded_part(name),
            "decisions": [d for d in decisions if _for(name, d.get("scope") or "")],
        }


if __name__ == "__main__":
    opts = json.load(open(os.path.join(HERE, "options.json"), encoding="utf-8"))
    decisions = json.load(open(os.path.join(HERE, "decisions.json"), encoding="utf-8"))
    res = {n: build(n, opts, decisions) for n in R.ORDER}
    json.dump(res, open(os.path.join(HERE, "reasons.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    for n, r in res.items():
        print(n, r["route"]["endLv"], r["route"]["pts"], r["route"]["w"], [(e["cls"], e["why"][:8]) for e in r["route"]["exams"]])
