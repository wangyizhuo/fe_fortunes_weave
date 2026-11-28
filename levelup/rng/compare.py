"""两条路线按乱数对齐比较（11-25 Yizhuo）。

两条路线用掉同样多的乱数，逐个乱数对齐（不按等级对齐），差别拆成三部分：
  1. 考试用掉的乱数：一条路线拿这个乱数考试、另一条拿它升级 → 这个乱数本来能涨的点
  2. 用不同职业升级的乱数：两条都升级、但职业不同（例如早拿到重装步兵）→ 每个乱数的加点差
  3. 保底：考进新职业时补到最低能力，补的点不同
合计 = 1 + 2 + 3 = 走完两条路线的能力差。
"""
from planner import STATS


def _walk(p, acts):
    """每个乱数：(动作, 职业, 当时等级, 加点)；考试/跳过的加点为 None。"""
    out, lv = [], p.level
    for k, (a, c) in enumerate(acts):
        if a == "升级":
            out.append((a, c, lv, tuple(p.result(k, lv, c)[1])))
            lv += 1
        else:
            out.append((a, c, lv, None))
    return out


def _floor_total(p, acts):
    t = [0] * 9
    for lifts in p.floor_lifts(acts).values():
        for i, x, v in lifts:
            t[i] += v - x
    return t


def _pw(p, g):
    return {"g": list(g), "pts": sum(g), "w": sum(w * x for w, x in zip(p.weights, g))}


def gtxt(g):
    return " ".join(f"{s}{v:+d}" for s, v in zip(STATS, g) if v) or "一样"


def seed_diff(p, acts_a, acts_b):
    """路线 A 减路线 B。两条要用同样多的乱数（不够长的按没有这个乱数算）。"""
    wa, wb = _walk(p, acts_a), _walk(p, acts_b)
    n = max(len(wa), len(wb))
    exam_seeds, class_seeds = [], []
    tot_lv = [0] * 9
    for k in range(n):
        x = wa[k] if k < len(wa) else ("无", None, None, None)
        y = wb[k] if k < len(wb) else ("无", None, None, None)
        ga, gb = x[3] or (0,) * 9, y[3] or (0,) * 9
        d = [i - j for i, j in zip(ga, gb)]
        tot_lv = [a + b for a, b in zip(tot_lv, d)]
        if (x[3] is None) != (y[3] is None):
            exam_seeds.append({"step": k, "a": x[1] if x[3] is None else f"{x[1]}升级", "b": y[1] if y[3] is None else f"{y[1]}升级",
                               "lvA": x[2], "lvB": y[2], "roll": round(p.exam_value(k), 2),
                               "lost": [STATS[i] for i, v in enumerate(gb if x[3] is None else ga) if v], **_pw(p, d)})
        elif x[3] is not None and d != [0] * 9:
            class_seeds.append({"step": k, "a": x[1], "b": y[1], "lvA": x[2], "lvB": y[2],
                                "gA": [STATS[i] for i, v in enumerate(ga) if v], "gB": [STATS[i] for i, v in enumerate(gb) if v], **_pw(p, d)})
    fl = [a - b for a, b in zip(_floor_total(p, acts_a), _floor_total(p, acts_b))]
    tot = [a + b for a, b in zip(tot_lv, fl)]
    sum_g = lambda rows: [sum(r["g"][i] for r in rows) for i in range(9)]
    return {"seeds": n, "examSeeds": exam_seeds, "examPart": _pw(p, sum_g(exam_seeds)),
            "classSeeds": class_seeds, "classPart": _pw(p, sum_g(class_seeds)),
            "floorPart": _pw(p, fl), "total": _pw(p, tot)}


def explain(d, label_a="A", label_b="B"):
    """拆成三部分的一段中文说明（页面和 data/*.md 用）。"""
    L = []
    e = d["examPart"]
    seeds = "；".join(f"第 {r['step'] + 1} 个乱数（判定值 {r['roll']}）{label_a if '升级' not in r['a'] else label_b}拿来考试，"
                      f"{label_b if '升级' not in r['a'] else label_a}拿来升级涨 {'、'.join(r['lost']) or '无'}"
                      for r in d["examSeeds"])
    L.append(f"① 考试用掉的乱数（{label_a}减{label_b}）：{seeds or '同一个'}　→ {gtxt(e['g'])}（{e['pts']:+d} 点，{e['w']:+d} 加权）")
    c = d["classPart"]
    rows = "；".join(f"第 {r['step'] + 1} 个乱数 {label_a}用{r['a']}（{'、'.join(r['gA'])}），{label_b}用{r['b']}（{'、'.join(r['gB'])}）"
                     for r in d["classSeeds"])
    L.append(f"② 用不同职业升级：{rows or '没有'}　→ {gtxt(c['g'])}（{c['pts']:+d} 点，{c['w']:+d} 加权）")
    f = d["floorPart"]
    L.append(f"③ 转职保底：{gtxt(f['g'])}（{f['pts']:+d} 点，{f['w']:+d} 加权）")
    t = d["total"]
    L.append(f"合计（同样 {d['seeds']} 个乱数）：{gtxt(t['g'])}（{t['pts']:+d} 点，{t['w']:+d} 加权）")
    return L


def exam_seed_summary(d, label_a="路线A", label_b="路线B"):
    """仅提取两条路线「考试/跳过用掉的乱数」差异，便于页面直观说明消耗了哪一个乱数。"""
    out = []
    for r in d.get("examSeeds") or []:
        step_no = r["step"] + 1
        roll = r["roll"]
        lost = "、".join(r.get("lost") or []) or "无"
        a_is_exam = "升级" not in str(r["a"])
        if a_is_exam:
            act_a = "跳过" if r["a"] == "跳过" else f"考{r['a']}"
            out.append(
                f"第 {step_no} 个乱数（判定值 {roll}%）：{label_a}在 Lv{r['lvA']} 用来{act_a}；"
                f"{label_b}在 Lv{r['lvB']} 用来{r['b']}（涨 {lost}，{abs(r['pts'])} 点 / {abs(r['w'])} 加权分）"
            )
        else:
            act_b = "跳过" if r["b"] == "跳过" else f"考{r['b']}"
            out.append(
                f"第 {step_no} 个乱数（判定值 {roll}%）：{label_a}在 Lv{r['lvA']} 用来{r['a']}（涨 {lost}，{abs(r['pts'])} 点 / {abs(r['w'])} 加权分）；"
                f"{label_b}在 Lv{r['lvB']} 用来{act_b}"
            )
    return out

