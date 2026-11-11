"""每个角色的完整成长档案（给「角色成长详情」页用），存为 detail.json。

  * 入队：等级、职业、初始能力（不含职业补正）
  * 过去：逐级加点（迪从 Lv1 起逐级反推；其他人从第一条观星记录起，之前只有合计）
  * 现在：11-05 截图 → 去掉职业补正、▲（兵种精通 / 坐骑 / 装备）→ 裸能力
  * 未来：到 Lv35 每一步，所有职业（已有 + 可考）各会涨什么、多少分，建议和原因
  * 考试收益：推荐路线里每次考试，和「不考这次」的最优路线比，到 35 级多/少几点、几分
"""
import json
import os

from fe_growth import STATS, exam_roll, level_up
from planner import gains_text, plan_all
from run_plans import (OWNED, EXAM_OPTIONS, REQUIRED, EXAM_CHANCE, CURRENT, data, make_planner,
                       records, ORDER, MAX_EXAMS)

HERE = os.path.dirname(os.path.abspath(__file__))
TARGET = 35   # 这里只做 35 级明细（int）；全局 TARGET 在 run_plans
KEYS = ["hp", "str", "mag", "spd", "dex", "def", "res", "lck", "cha"]

_chars = {c["name"]: c for c in json.load(open(os.path.join(HERE, "fw_characters.json"), encoding="utf-8"))}
_cls = {c["name"]: c for c in json.load(open(os.path.join(HERE, "fw_classes.json"), encoding="utf-8"))}


def class_bonus(cls):
    b = (_cls.get(cls) or {}).get("baseStats") or {}
    return [b.get(k, 0) for k in KEYS]


# 入队（初始能力不含职业补正）。来源 fire-emblem-fw.site，按 global.fireemblem.top / Yizhuo 确认的改。
JOIN_FIX = {"迪托利希": {"spd": 10, "dex": 11},   # global 站：速10 技11（种子反推也证实）
            }
JOIN_LEVEL = {"米迦艾拉": 5}                      # Yizhuo 11-02 确认 Lv5 入队
JOIN_NOTE = {"乌尔坦德": "网站的初始能力可能不对（她现在的能力有几项比网站初始值还低）",
             "米迦艾拉": "网站写 Lv1，实际 Lv5 入队；能力按网站（= 她 Lv5 入队时的值）",
             "伊欧": "Lv20 入队，骑罗西南"}

# ▲（截图里黄色上箭头）= 兵种精通技能 / 坐骑属性 / 装备，显示顺序 HP 力 魔 速 技 防 魔防 幸 魅
BOOST = {
    "迪托利希": ([0, 1, 0, 0, 5, 0, 0, 0, 0], "力+1 攻击的基本；技+5 披风（Lv25 截图 9 项和种子推算全对上，已证实）"),
    "法毕欧": ([0, 0, 1, 0, 0, 0, 1, 0, 0], "魔+1 魔防+1 魔道的基本（估计）"),
    "杨界": ([0, 0, 1, 0, 0, 0, 1, 0, 0], "魔+1 魔防+1 魔道的基本（估计）"),
    "米迦艾拉": ([0, 1, 0, 0, 0, 1, 0, 0, 0], "力+1 攻击的基本、防+1 防卫的基本（估计）"),
    "伊欧": ([3, 0, 0, 1, 2, 2, 0, 0, 0], "HP+3 体力强化；速+1 技+2 防+2 罗西南 4 级属性（估计）"),
    "艾丝梅拉尔达": ([0, 1, 1, 0, 0, 0, 0, 0, 0], "力+1 魔+1 攻势的基本（估计）"),
}

# 另一个对话里按「推荐等级 + 技能等级」做的成功率预测（不是游戏显示值）
EXAM_PRED = {("法毕欧", "牧师"): "预测 100%（白魔 C、等级够）", ("伊欧", "剑客"): "预测 100%",
             ("迪托利希", "恶棍"): "预测 100%", ("米迦艾拉", "猎兵"): "预测 100%",
             ("奇洛伊卡", "弓箭手"): "预测 100%", ("艾丝梅拉尔达", "重装步兵"): "预测接近 100%（重装术够就 100%）",
             ("乌尔坦德", "牧师"): "预测约 50～85%（白魔差一段），有风险", ("努蒂奴", "重装步兵"): "预测可能偏低（斧 D+），有风险",
             ("米迦艾拉", "斗拳手"): "预测约 50～85%，多半能过", ("奇洛伊卡", "重装步兵"): "预测 0～15%（枪斧都是 E），基本过不了"}


def vec(d):
    return [d[k] for k in KEYS]


def wsum(g, w):
    return sum(a * b for a, b in zip(g, w))


def past_rows(name):
    """过去逐级：[(标签, 职业, 类型, 加点[9], 说明)]，以及第一条记录前的等级。"""
    if name == "迪托利希":
        rows = json.load(open(os.path.join(HERE, "di_full_chain.json"), encoding="utf-8"))
        return rows, None
    out = []
    first_lv = None
    for r in records(name):
        if first_lv is None:
            first_lv = r["frm"]
        if r["ok"] is None:
            out.append(dict(lv=f"Lv{r['frm']}", cls="", kind="考试", g=[0] * 9, note="没记下的一步（考试）"))
        elif not r["ok"]:
            v = exam_roll(r["seed"]) / 1e4 if r["seed"] is not None else None
            out.append(dict(lv=f"Lv{r['frm']}", cls=r["cls"], kind="考试", g=[0] * 9,
                            note="考试（观星记录 ✗）" + (f"，判定值 {v:.2f}%" if v is not None else "")))
        else:
            g = r["gains"]
            note = r.get("note", "")
            if r["seed"] is not None:
                pred = [int(x) for x in level_up(r["seed"], data.growth(name, r["cls"], r["frm"]), 2).gains]
                if pred != g and not r.get("inferred"):
                    note = f"观星记的是「{gains_text(g)}」，种子算「{gains_text(pred)}」"
                    g = pred
            out.append(dict(lv=f"Lv{r['frm']}→{r['frm'] + 1}", cls=r["cls"], kind="升级", g=g, note=note))
    return out, first_lv


def build(name):
    ch = _chars[name]
    shot = CURRENT[name]["shot_1105"]
    cur_cls = shot["class"]
    bonus = class_bonus(cur_cls)
    boost, boost_note = BOOST.get(name, ([0] * 9, "无"))
    raw_now = [s - b - x for s, b, x in zip(shot["stats"], bonus, boost)]

    join = vec(ch["baseStats"])
    for k, v in JOIN_FIX.get(name, {}).items():
        join[KEYS.index(k)] = v
    join_lv = JOIN_LEVEL.get(name, ch["baseLevel"])

    past, first_lv = past_rows(name)
    # 截图之后已经做了的记录（等级 > 截图等级）不算在截图里
    rec_gain = [0] * 9
    for r in past:
        if r["kind"] == "升级":
            rec_gain = [a + b for a, b in zip(rec_gain, r["g"])]
    # 截图等级之后还有的记录加点（规划起点 = 截图 + 这些）
    after = [0] * 9
    for r in records(name):
        if r["ok"] and r["to"] and r["to"] > shot["level"]:
            after = [a + b for a, b in zip(after, r["gains"])]
    raw_start = [a + b for a, b in zip(raw_now, after)]

    if name == "迪托利希":
        gap = None
    else:
        before = [n - j - rg + af for n, j, rg, af in zip(raw_now, join, rec_gain, after)]
        gap = dict(frm=join_lv, to=first_lv, g=before, n=(first_lv or join_lv) - join_lv)

    # ---------- 未来 ----------
    p = make_planner(name, TARGET)
    W = p.weights
    plans, k = plan_all(p, MAX_EXAMS)
    plan = plans[k]
    everyone = list(dict.fromkeys(list(OWNED[name]) + list(EXAM_OPTIONS[name])))
    have = list(OWNED[name])
    fut = []
    stats = list(raw_start)
    main = OWNED[name][0]
    for r in plan.rows:
        if r.action == "升级":
            lv = r.level_from
            opts = []
            for c in everyone:
                s, g = p.result(r.step, lv, c)
                opts.append(dict(cls=c, owned=c in have, g=list(g), s=s))
            opts.sort(key=lambda o: -o["s"])
            best_owned = max((o for o in opts if o["owned"]), key=lambda o: o["s"])
            why = []
            if r.balance_note:
                why.append(r.balance_note)
            elif r.score >= best_owned["s"]:
                tied = [o["cls"] for o in opts if o["owned"] and o["s"] == r.score and o["cls"] != r.cls]
                why.append(f"已有职业里分最高（{r.score} 分）" + (f"，和{'、'.join(tied)}同分" if tied else ""))
            if r.cls in REQUIRED.get(name, []) or r.cls in (p.prefer or {}):
                why.append(f"同分或差一点时优先用{r.cls}，练兵种精通")
            better = [o for o in opts if not o["owned"] and o["s"] > r.score]
            if better:
                b = better[0]
                why.append(f"没考到的{b['cls']}这一级 {b['s']} 分（{gains_text(b['g'])}），比现在多 {b['s'] - r.score} 分，但为它多考一次不划算或来不及")
            stats = [a + b for a, b in zip(stats, r.gains)]
            fut.append(dict(kind="升级", step=r.step + 1, lv=f"Lv{lv}→{lv + 1}", cls=r.cls, g=list(r.gains), s=r.score,
                            opts=opts, why="；".join(why), stats=list(stats)))
        else:
            v = p.exam_value(r.step)
            real = r.cls in EXAM_OPTIONS[name]
            if real and r.cls not in have:
                have.append(r.cls)
            lvl_opts = []
            for c in everyone:
                s, g = p.result(r.step, p.level + sum(f["kind"] == "升级" for f in fut), c)
                lvl_opts.append(dict(cls=c, owned=c in have, g=list(g), s=s))
            lvl_opts.sort(key=lambda o: -o["s"])
            chance = (EXAM_CHANCE.get(name) or {}).get(r.cls)
            fut.append(dict(kind="考试", step=r.step + 1, cls=r.cls if real else "", roll=round(v, 2), s=r.score,
                            g=list(r.gains), opts=lvl_opts, chance=chance, pred=EXAM_PRED.get((name, r.cls), "")))
    total_g = [0] * 9
    for f in fut:
        if f["kind"] == "升级":
            total_g = [a + b for a, b in zip(total_g, f["g"])]

    # ---------- 考试收益 ----------
    exams = []
    for f in fut:
        if f["kind"] != "考试":
            continue
        q = make_planner(name, TARGET)
        if not f["cls"]:
            q.no_skip_steps = {f["step"] - 1}   # 跳过的价值：这一步不跳、照常升级
        if f["cls"]:
            q.exam_options = tuple(c for c in q.exam_options if c != f["cls"])
            q.required = tuple(c for c in q.required if c != f["cls"])
            q.prefer = {c: v for c, v in (q.prefer or {}).items() if c != f["cls"]}
        alt = q.best_plan(max(plan.exams - 1, 0))
        if alt is None:   # 去掉这场后满足不了「至少一个中级」：按不要求中级比较这场考试的价值
            q.require_mid = False
            alt = q.best_plan(max(plan.exams - 1, 0))
        ag = [0] * 9
        for r in alt.rows:
            if r.action == "升级":
                ag = [a + b for a, b in zip(ag, r.gains)]
        diff = [a - b for a, b in zip(total_g, ag)]
        exams.append(dict(step=f["step"], cls=f["cls"] or "跳过", roll=f["roll"], diff=diff,
                          pts=sum(diff[1:]), pts_hp=diff[0], wdiff=plan.total - alt.total,
                          alt_exams=[r.cls for r in alt.rows if r.action == "考试"],
                          req=f["cls"] in REQUIRED.get(name, []),
                          # 11-11：净值差 = 加权分差 − 多花的手形金币 ÷ 每分金币
                          dgold=(getattr(plan, "gold", 0) or 0) - (getattr(alt, "gold", 0) or 0),
                          net=round(plan.total - alt.total - ((getattr(plan, "gold", 0) or 0) - (getattr(alt, "gold", 0) or 0)) / q.gold_per_pt, 1)))

    return dict(
        name=name, weights=W,
        join=dict(lv=join_lv, cls=ch["startClass"], stats=join, note=JOIN_NOTE.get(name, "")),
        gap=gap, past=past,
        now=dict(lv=shot["level"], cls=cur_cls, shot=shot["stats"], bonus=bonus, boost=boost, boost_note=boost_note,
                 raw=raw_now, after=after, raw_start=raw_start, start_lv=p.level),
        future=fut, total=total_g, wtotal=plan.total, exams_n=plan.exams,
        plan_scores=[pl.total if pl and pl.rows else None for pl in plans],
        exam_benefit=exams, owned=list(OWNED[name]),
        options=[c for c in EXAM_OPTIONS[name] if c not in OWNED[name]],
        required=REQUIRED.get(name, []),
        end=stats,
    )


if __name__ == "__main__":
    import sys
    names = sys.argv[1:] or ORDER
    out = {}
    path = os.path.join(HERE, "detail.json")
    if os.path.exists(path) and sys.argv[1:]:
        out = json.load(open(path, encoding="utf-8"))
    for n in names:
        out[n] = build(n)
        d = out[n]
        print(n, "Lv", d["now"]["start_lv"], "→35", "考", d["exams_n"], "次", "合计", gains_text(d["total"]), d["wtotal"],
              [(e["cls"], e["pts"], e["wdiff"]) for e in d["exam_benefit"]], flush=True)
    json.dump(out, open(path, "w"), ensure_ascii=False)
