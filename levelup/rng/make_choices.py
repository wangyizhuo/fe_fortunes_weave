"""每个角色的中长期选择：成本 + 收益 + 建议 → choices.json（make_html.py 嵌进页面「到 Lv35」）。"""
import json, os, copy
from planner import plan_all
from run_plans import make_planner, EXAM_OPTIONS, EXAM_CHANCE
import run_plans
from make_sheet import ORDER

HERE = os.path.dirname(os.path.abspath(__file__))
CLS = {c["name"]: c for c in json.load(open(os.path.join(HERE, "fw_classes.json"), encoding="utf-8"))}
PRICE = {"初级": 300, "中级": 500, "高级": 3000}
D = json.load(open(os.path.join(HERE, "detail.json"), encoding="utf-8"))
ST = ["HP", "力", "魔", "速", "技", "防", "魔防", "幸", "魅"]
# 练技能的成本（来自 levelup/exam/技能差距与刷技能建议-2026-11-05.md）
GRIND = {("乌尔坦德", "牧师"): ("白魔 D+→C（最多差 140）", "和杨界竞技场训练 2～3 次（每次 50～62，300G＋活力，不给角色经验）", "下一次升级之前"),
         ("努蒂奴", "重装步兵"): ("斧 D+→C（最多差 140）＋重装术 E+", "和米迦训练 1～2 次（每次 75～87）＋1 本重装术指南书", "Lv25→26 之前"),
         ("米迦艾拉", "斗拳手"): ("格斗 D+→C（最多差 140）", "和迪训练 3～4 次（只高 1 段，每次 37～50）", "下一次升级之前"),
         ("米迦艾拉", "弓箭手"): ("箭 D→C（最多差 185）", "和伊欧或奇洛训练约 3 次（每次 50～62）", "Lv28→29 之前"),
         ("艾丝梅拉尔达", "斗拳手"): ("格斗 E→C（最多差 220）", "和迪训练约 3 次（每次 75～87，300G＋活力）", "Lv24→25 之前")}
ONLY = {"法毕欧": [["牧师"]]}
RISKY = {("乌尔坦德", "牧师"): "约 50～85%", ("努蒂奴", "重装步兵"): "约 0%（斧差 1 段、重装术差 1 段）", ("米迦艾拉", "斗拳手"): "约 50～85%", ("米迦艾拉", "弓箭手"): "约 0%（箭 D，要 C，差 2 段）"}


def tot(plan):
    g = [0] * 9
    for r in plan.rows:
        if r.action == "升级":
            g = [a + b for a, b in zip(g, r.gains)]
    return g


def exams_of(name, p, plan):
    out = []
    lv = p.level
    for r in plan.rows:
        if r.action == "升级":
            lv += 1
            continue
        real = r.cls in EXAM_OPTIONS[name]
        tier = CLS.get(r.cls, {}).get("tier", "中级") if real else "初级"
        pct = p.exam_pct(r.cls, lv) if real else None
        out.append({"cls": r.cls if real else "", "roll": round(p.exam_value(r.step), 2), "tier": tier, "step": r.step + 1, "pct": pct})
    return out


def gdiff(a, b):
    return [x - y for x, y in zip(a, b)]


def gtxt(g):
    return " ".join(ST[i] + (f"+{v}" if v > 0 else str(v)) for i, v in enumerate(g) if v) or "能力一样"


def run(name, chance_override=None):
    saved = copy.deepcopy(run_plans.EXAM_CHANCE)
    if chance_override is not None:
        run_plans.EXAM_CHANCE[name] = chance_override
    try:
        p = make_planner(name, 35)
        plans, k = plan_all(p, 4)
    finally:
        run_plans.EXAM_CHANCE.clear(); run_plans.EXAM_CHANCE.update(saved)
    return p, plans, k


SAFE = {("法毕欧", "牧师"), ("伊欧", "剑客"), ("迪托利希", "恶棍"), ("米迦艾拉", "猎兵"), ("奇洛伊卡", "弓箭手"), ("奇洛伊卡", "剑客"),
        ("艾丝梅拉尔达", "重装步兵"), ("杨界", "萨满巫师"), ("杨界", "牧师")}


def ex_cost(exs, name="", skip=()):
    money = sum(PRICE.get(e["tier"], 500) for e in exs)
    names = "、".join((e["cls"] or "跳过") for e in exs) or "不考"
    # 11-08 起技能等级全有了：技能、等级都够（估计 100%）的考试不算风险
    def unsure(e):
        return e["cls"] and (name, e["cls"]) not in SAFE and e["cls"] not in skip and (e.get("pct") is None or e["pct"] < 100)
    risk = [f"{e['cls']} 判定值 {e['roll']}%（估计成功率 {e['pct'] if e.get('pct') is not None else '?'}%）" for e in exs
            if unsure(e) and e["roll"] >= 30 and (name, e["cls"]) not in RISKY]
    hard = any(unsure(e) and e["roll"] >= 90 for e in exs)
    return money, names, ("；风险：" + "、".join(risk) + "，技能或等级不够，游戏显示要高于判定值才过" if risk else ""), hard


out = {}
for name in ORDER:
    p, plans, k = run(name)
    TM, TB = p.thresholds
    base = plans[k]
    bt = tot(base)
    bex = exams_of(name, p, base)
    opts = []
    # 1) 考几次
    prev = None
    for j, pl in enumerate(plans):
        if pl is None or pl.total <= 0 or (prev is not None and pl.total == prev):
            continue
        prev = pl.total
        exs = exams_of(name, p, pl)
        money, names, risk, hard = ex_cost(exs, name)
        d = pl.total - base.total
        extra = j - k
        if j == k:
            rec, why = "推荐（现在的路线）", f"多考的每一场：中级要多 {TM} 分、初级（含跳过）要多 {TB} 分；这是超出门槛最多的次数"
        elif extra > 0:
            per = d / extra
            bt_ = [e["tier"] for e in bex]
            mid = max(0, sum(e["tier"] != "初级" for e in exs) - sum(t != "初级" for t in bt_))
            need = TM * mid + TB * (extra - mid)
            if hard:
                rec, why = "不建议", "里面有一场判定值 90% 以上的新职业考试，几乎要游戏显示 100% 才过"
            elif d >= need:
                rec, why = "可选", f"多 {d} 分，够门槛（中级每场 {TM}、初级每场 {TB}，共 {need}），但不如现在的路线划算"
            elif d > 0:
                rec, why = "不建议", f"多 {d} 分，不够门槛（中级每场 {TM}、初级每场 {TB}，共 {need}）"
            else:
                rec, why = "不建议", "不多分"
        else:
            rec, why = "不建议", f"少考试 {-extra} 次，少 {-d} 分"
        opts.append({"kind": "budget", "title": f"考试 {j} 次：{names}", "cost": f"{len(exs)} 张手形，约 {money}G" + risk,
                     "gain": d, "pts": sum(gdiff(tot(pl), bt)), "tpts": sum(tot(pl)), "diff": gtxt(gdiff(tot(pl), bt)), "total": pl.total, "rec": rec, "why": why, "cur": j == k, "money": money})
    # 2) 有风险的考试：挂了少多少、练技能的成本
    for e in bex:
        key = (name, e["cls"])
        if key in RISKY:
            ov = dict(EXAM_CHANCE.get(name, {})); ov[e["cls"]] = 0
            _, fp, fk = run(name, ov)
            best = max((x for x in fp[:k + 1] if x is not None), key=lambda x: x.total)
            loss = base.total - best.total
            g = GRIND.get(key)
            opts.append({"kind": "risk", "title": f"{e['cls']}考试：先练技能再考", "cost": (f"{g[0]}：{g[1]}；{g[2]}" if g else "练技能"),
                         "gain": loss, "pts": sum(gdiff(bt, tot(best))), "diff": f"不练直接考：成功率{RISKY[key]}，判定值 {e['roll']}%；挂了到 Lv35 少 {sum(gdiff(bt, tot(best)))} 点、{loss} 分（{gtxt(gdiff(bt, tot(best)))}）",
                         "total": base.total, "rec": "建议" if loss >= 8 else "可选",
                         "why": f"等于花几次训练买保险：挂的话少 {loss} 分" + ("，值得" if loss >= 8 else "，损失不大，可以赌"), "cur": False})
        elif key in GRIND:
            g = GRIND[key]
            opts.append({"kind": "risk", "title": f"{e['cls']}考试：确认技能", "cost": f"{g[0]}：{g[1]}；{g[2]}", "gain": 0, "pts": 0,
                         "diff": f"判定值 {e['roll']}%，技能够了基本必过", "total": base.total, "rec": "建议", "why": "成本很低，顺手做", "cur": False})
    # 3) 练技能解锁现在考不过的职业
    for (n, cls), g in GRIND.items():
        if n != name or cls in [e["cls"] for e in bex]:
            continue
        ov = dict(EXAM_CHANCE.get(name, {})); ov[cls] = 100
        p2, pl2, k2 = run(name, ov)
        best = pl2[k2]
        exs = exams_of(name, p2, best)
        money, names, risk, hard = ex_cost(exs, name, (cls,))
        d = best.total - base.total
        same = plans[len(exs)] if len(exs) < len(plans) else None
        dsame = best.total - same.total if same is not None and same.total > 0 else None
        opts.append({"kind": "grind", "title": f"练{g[0].split('（')[0]}，解锁{cls}（考试 {len(exs)} 次：{names}）",
                     "cost": f"{g[1]}；{g[2]}；{len(exs)} 张手形约 {money}G{risk}", "gain": d, "pts": sum(gdiff(tot(best), bt)), "diff": gtxt(gdiff(tot(best), bt)),
                     "money": money, "total": best.total, "rec": "建议" if (dsame if dsame is not None else d) >= 8 else "可选",
                     "why": f"比现在的路线多 {d} 分" + (f"；但不练、同样考试 {len(exs)} 次也能多 {same.total - base.total} 分，练格斗本身只多 {dsame} 分" if dsame is not None and dsame < d else ""), "cur": False})
    # 4) 不考某职业的路线（Yizhuo 11-08：法毕欧加「只考牧师」）
    for ex_only in ONLY.get(name, []):
        sv_r, sv_o = list(run_plans.REQUIRED.get(name, [])), list(EXAM_OPTIONS[name])
        run_plans.REQUIRED[name] = []; EXAM_OPTIONS[name][:] = ex_only
        try:
            p3 = make_planner(name, 35); pl3, _ = plan_all(p3, 4)
        finally:
            run_plans.REQUIRED[name] = sv_r; EXAM_OPTIONS[name][:] = sv_o
        prev3 = None
        for j, pl in enumerate(pl3):
            if pl is None or pl.total <= 0 or j > k or (prev3 is not None and pl.total == prev3):
                continue
            prev3 = pl.total
            exs = [{"cls": r.cls if r.cls in ex_only else "", "tier": "中级" if r.cls in ex_only else "初级"} for r in pl.rows if r.action != "升级"]
            money = sum(PRICE.get(e["tier"], 500) for e in exs)
            names = "、".join(e["cls"] or "跳过" for e in exs)
            d = pl.total - base.total
            opts.append({"kind": "budget", "title": f"只考{'、'.join(ex_only)}（考试 {j} 次：{names}）", "cost": f"{len(exs)} 张手形，约 {money}G",
                         "gain": d, "pts": sum(gdiff(tot(pl), bt)), "tpts": sum(tot(pl)), "diff": gtxt(gdiff(tot(pl), bt)), "total": pl.total, "money": money,
                         "rec": "可选" if d >= 0 else "不建议",
                         "why": ("和现在的路线同分，但拿不到" + "、".join(run_plans.REQUIRED.get(name, [])) + "的精通") if d == 0 else (f"少 {-d} 分" if d < 0 else f"多 {d} 分"), "cur": False})
    # 11-11 Yizhuo：路线比较除了加权分，也给净值差（加权分差 − 多花的手形金币 ÷ 每分金币）
    gpp = p.gold_per_pt
    bm = next((o.get("money") for o in opts if o.get("cur")), None)
    for o in opts:
        if o.get("money") is not None and bm is not None:
            o["dnet"] = round(o["gain"] - (o["money"] - bm) / gpp, 1)
            if o["kind"] == "budget" and not o["cur"]:
                o["rec"] = "可选" if o["dnet"] > 0 else "不建议"
                o["why"] = f"加权分 {o['gain']:+d}，多花 {o['money'] - bm:+d}G，净值 {o['dnet']:+.1f}"
        if o.get("cur"):
            o["why"] = "按跳过条件逐级走出来的路线"
    out[name] = {"base": base.total, "k": k, "opts": opts}
    print(name, base.total, [(o["title"], o["gain"], o["rec"]) for o in opts])
json.dump(out, open(os.path.join(HERE, "choices.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
