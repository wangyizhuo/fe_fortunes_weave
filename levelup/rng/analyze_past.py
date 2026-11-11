"""反推每个角色过去每一步（升级/考试跳过），和期望值比较；再看未来路线的期望。输出 analysis.json。"""
import json, os, random
from functools import lru_cache

from fe_growth import STATS, level_up, Xorshift128, INTERNAL_ORDER, MASK31


def first_round_u(seed, growth):
    """第一轮判定时每项抽到的乱数 U（0～1，越小越好；成长率余数为 0 的项不抽），显示顺序。"""
    rng = Xorshift128(seed)
    out = [None] * 9
    for k in range(9):
        st = INTERNAL_ORDER[k]
        g = max(0, growth[st])
        if g >= 1 and g % 100:
            out[st] = ((rng.next() & MASK31) % 1_000_000) / 1e6
    return out
from planner import plan_all
from run_plans import OWNED, CURRENT, W, data, make_planner, records, units
from make_sheet import TARGET, MAX_EXAMS, ORDER
import demo

HERE = os.path.dirname(os.path.abspath(__file__))
rnd = random.Random(20261105)
SEEDS = [rnd.getrandbits(31) for _ in range(20000)]


@lru_cache(maxsize=None)
def expect(growth):
    """随机种子下这一级的期望：(期望项数, 每项上涨概率[9])。含保底 2 项。"""
    tot, per = 0, [0] * 9
    for s in SEEDS:
        g = level_up(s, list(growth), 2).gains
        tot += sum(g)
        for i, v in enumerate(g):
            per[i] += v
    n = len(SEEDS)
    return tot / n, [p / n for p in per]


def names(g):
    return " ".join(STATS[i] + ("" if v == 1 else f"+{v}") for i, v in enumerate(g) if v) or "—"


out = {"chars": [], "rows": []}
for name in ORDER:
    if name not in units:
        continue
    w = W[name]
    shot = CURRENT.get(name, {}).get("shot_1105", {})
    now = shot.get("level")
    recs = records(name)
    seeded = name in demo.KNOWN_SEEDS
    last_cls = units[name]["draws"][0] and None
    rows = []
    for r in recs:
        cls = r["cls"] or last_cls or ""
        last_cls = cls or last_cls
        growth = tuple(data.growth(name, cls, r["frm"])) if cls else None
        e_cnt, e_per = expect(growth) if growth else (None, None)
        pred = list(level_up(r["seed"], list(growth), 2).gains) if (r["seed"] is not None and growth) else None
        recd = r["gains"] if any(r["gains"]) else None
        hidden = r["ok"] is None
        if r.get("inferred"):
            recd = None
        used = pred or recd
        match = None if (recd is None or pred is None) else (recd == pred)
        uvals = first_round_u(r["seed"], list(growth)) if (r["seed"] is not None and growth) else None
        vec = (pred or recd) if (pred or recd) else None
        rows.append(dict(name=name, idx=str(r["idx"]), frm=r["frm"], to=r["to"], ok=r["ok"], hidden=hidden,
                         inferred=bool(r.get("inferred")), cls=cls, recorded=names(recd) if recd else "",
                         predicted=names(pred) if pred else "", match=match, cnt=sum(used) if used else None,
                         score=sum(a * b for a, b in zip(used, w)) if used else None,
                         e_cnt=e_cnt, e_score=sum(p * b for p, b in zip(e_per, w)) if e_per else None,
                         note=r.get("note", ""), vec=vec, e_per=e_per, u=uvals))
    # 完成判定：升级到的等级 ≤ 当前等级；考试/没记录的步看后面第一次升级
    later = False
    for row in reversed(rows):
        if row["ok"]:
            row["done"] = now is not None and row["to"] <= now
            later = row["done"]
        else:
            row["done"] = later
    out["rows"] += rows

    def agg(sel):
        ups = [r for r in sel if r["ok"]]
        skips = [r for r in sel if not r["ok"]]
        known = [r for r in ups if r["cnt"] is not None]
        sk_known = [r for r in skips if r["cnt"] is not None]
        return dict(ups=len(ups), skips=len(skips), hidden=sum(r["hidden"] for r in skips),
                    cnt=sum(r["cnt"] for r in known), e_cnt=sum(r["e_cnt"] for r in known),
                    score=sum(r["score"] for r in known), e_score=sum(r["e_score"] for r in known),
                    unknown=len(ups) - len(known),
                    skip_cnt=sum(r["cnt"] for r in sk_known), skip_e=sum(r["e_cnt"] for r in sk_known), skip_n=len(sk_known))

    past = agg([r for r in rows if r["done"]])

    def perstat(sel):
        """单项：实际 vs 期望（按成长率），和乱数本身（第一轮 U 的平均，0.5 为平均，越小越好）。"""
        act, exp, var, us = [0] * 9, [0.0] * 9, [0.0] * 9, [[] for _ in range(9)]
        for r in sel:
            if r["vec"] is None or r["e_per"] is None:
                continue
            for i in range(9):
                act[i] += r["vec"][i]; exp[i] += r["e_per"][i]; var[i] += r["e_per"][i] * (1 - r["e_per"][i])
            if r["u"]:
                for i in range(9):
                    if r["u"][i] is not None:
                        us[i].append(r["u"][i])
        return dict(act=act, exp=exp, z=[(a - e) / (v ** 0.5) if v > 0 else 0 for a, e, v in zip(act, exp, var)],
                    u=[sum(x) / len(x) if x else None for x in us], un=[len(x) for x in us])

    past_ps = perstat([r for r in rows if r["done"] and r["ok"]])
    all_rolls = perstat([r for r in rows if r["done"]])   # 乱数本身：升级和跳过的步都算
    pending = agg([r for r in rows if not r["done"]])
    fut = None
    if name in OWNED:
        p = make_planner(name, TARGET.get(name))
        plans, k = plan_all(p, MAX_EXAMS)
        plan = plans[k]
        cnt = e = sc = esc = 0
        lv = p.level
        ups = 0
        for r in plan.rows:
            if r.action == "升级":
                g = tuple(data.growth(name, r.cls, lv))
                ec, ep = expect(g)
                cnt += sum(r.gains); e += ec; sc += r.score; esc += sum(a * b for a, b in zip(ep, w))
                ups += 1; lv += 1
        # 对照：不考试、每级用当前主职业直接升
        base = [0, 0, 0.0]
        for i in range(p.n_levels):
            g = data.growth(name, OWNED[name][0], p.level + i)
            res = level_up(p.seed_at(i), g, 2).gains
            base[0] += sum(res); base[1] += sum(a * b for a, b in zip(res, w)); base[2] += expect(tuple(g))[0]
        fact, fexp, fvar, fus = [0] * 9, [0.0] * 9, [0.0] * 9, [[] for _ in range(9)]
        lv2 = p.level
        for r in plan.rows:
            if r.action == "升级":
                g = tuple(data.growth(name, r.cls, lv2))
                ec, ep = expect(g)
                uu = first_round_u(p.seed_at(r.step), list(g))
                for i in range(9):
                    fact[i] += r.gains[i]; fexp[i] += ep[i]; fvar[i] += ep[i] * (1 - ep[i])
                    if uu[i] is not None:
                        fus[i].append(uu[i])
                lv2 += 1
        # 乱数本身：未来每一步（含考试吃掉的）用主职业算 U
        for i in range(len(plan.rows)):
            uu = first_round_u(p.seed_at(i), list(data.growth(name, OWNED[name][0], p.level)))
        fut_ps = dict(act=fact, exp=fexp, z=[(a - e) / (v ** 0.5) if v > 0 else 0 for a, e, v in zip(fact, fexp, fvar)],
                      u=[sum(x) / len(x) if x else None for x in fus], un=[len(x) for x in fus])
        fut = dict(ps=fut_ps, frm=p.level, to=p.level + p.n_levels, ups=ups, exams=plan.exams, cnt=cnt, e_cnt=e, score=sc, e_score=esc,
                   noexam_cnt=base[0], noexam_score=base[1], noexam_e=base[2], main=OWNED[name][0])
    out["chars"].append(dict(name=name, now=now, seeded=seeded, past=past, pending=pending, future=fut,
                             past_ps=past_ps, rolls_ps=all_rolls,
                             first_level=rows[0]["frm"] if rows else None))

json.dump(out, open(os.path.join(HERE, "analysis.json"), "w"), ensure_ascii=False, indent=1)
for c in out["chars"]:
    pa, pe, f = c["past"], c["pending"], c["future"]
    print(c["name"], "now", c["now"], "from", c["first_level"],
          f"| 过去 升{pa['ups']} 跳{pa['skips']}(未记{pa['hidden']}) 加点{pa['cnt']} 期望{pa['e_cnt']:.1f} 加权{pa['score']} 期望{pa['e_score']:.1f} 未知{pa['unknown']} 被跳的{pa['skip_n']}次 {pa['skip_cnt']}项 期望{pa['skip_e']:.1f}",
          f"| 已观星未做 升{pe['ups']} 跳{pe['skips']} 加点{pe['cnt']} 期望{pe['e_cnt']:.1f}",
          f"| 未来 Lv{f['frm']}→{f['to']} 升{f['ups']} 考{f['exams']} 加点{f['cnt']} 期望{f['e_cnt']:.1f} 加权{f['score']} 期望{f['e_score']:.1f} 不考直接升{f['noexam_cnt']}项(期望{f['noexam_e']:.1f})/{f['noexam_score']}" if f else "")
