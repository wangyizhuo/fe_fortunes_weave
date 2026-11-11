import re
from run_plans import P0
"""成长规划 HTML：观星记录（备份）+ 规划器的未来路线，一页。
每个角色：11-05 截图的等级/职业/能力/技能（页面可改）；每一步：这一步种子下所有选择（加点相同的职业并成一组）、
加点项数、加权分；已完成按当前等级自动判断，也可手动勾。状态存 artifact db，可一键同步到主表「成长进度」。"""
import json, os
OUT_DIR = os.environ.get("FE_OUT_DIR") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "out")   # 生成的网页放这里
os.makedirs(OUT_DIR, exist_ok=True)

from fe_growth import STATS, level_up, exam_roll
from planner import plan_all, score
from run_plans import OWNED, EXAM_OPTIONS, REQUIRED, CURRENT, W, data, make_planner, records, units
from make_sheet import TARGET, MAX_EXAMS, ORDER

HERE = os.path.dirname(os.path.abspath(__file__))
SKILLS = ["剑术", "枪术", "斧术", "箭术", "格斗术", "黑魔术", "白魔术", "指挥术", "步兵术", "马术", "重装术", "飞行术"]
CUR_CLASS_EXTRA = {"奇洛伊卡": ["猎兵"], "伊欧": ["战车兵"], "艾丝梅拉尔达": ["天翼兵"]}


def names(g):
    return [STATS[i] + ("" if v == 1 else f"+{v}") for i, v in enumerate(g) if v]


_CLS_TIER = {x["name"]: x.get("tier", "中级") for x in json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "fw_classes.json"), encoding="utf-8"))}


def step_routes(name, p, step, lv, have):
    """Yizhuo 11-09：每一级的四种走法。转职/跳过给游戏成功率（估计）和这个种子过不过；另给未来 15 级平均分（讨论跳过用）。"""
    roll = round(p.exam_value(step), 2)
    exams = []
    for cls in EXAM_OPTIONS[name]:
        if cls in have:
            continue
        pct = p.exam_pct(cls, lv)
        sc = p.result(step, lv, cls)[0]
        exams.append({"cls": cls, "tier": _CLS_TIER.get(cls, "中级"), "pct": pct,
                      "pass": None if pct is None else roll < pct, "s": sc})
    exams.sort(key=lambda e: (e["pass"] is not True, -(e["pct"] or 0)))
    fut = [max(p.result(j, lv, c)[0] for c in have) for j in range(step + 1, step + 16)]
    return {"roll": roll, "exams": exams, "avg10": round(sum(fut[:10]) / 10, 1), "avg15": round(sum(fut) / 15, 1),
            "thr": round(p.skip_threshold, 1)}


def grouped(name, seed, level, classes, have, w):
    """这一步种子下每个职业的加点，加点完全相同的并成一组。"""
    groups = {}
    for cls in classes:
        try:
            g = tuple(level_up(seed, data.growth(name, cls, level), 2).gains)
        except Exception:
            continue
        groups.setdefault(g, []).append(cls)
    out = [{"classes": cs, "owned": [c in have for c in cs], "gains": names(g), "cnt": sum(g), "score": score(g, w)}
           for g, cs in groups.items()]
    out.sort(key=lambda o: (-o["score"], -o["cnt"]))
    return out


HIDDEN_DONE = {"艾丝梅拉尔达": ["h13-"], "乌尔坦德": ["h4"]}
HIDDEN_NOTE = {"h4": "你说没有跳过，但下一次升 Lv19 的加点对得上，所以这个种子已经用掉了，不用再做"}
chars = []
for name in ORDER:
    cur = CURRENT.get(name, {})
    shot = cur.get("shot_1105", {})
    w = W[name]
    owned = list(dict.fromkeys(OWNED.get(name, []) + CUR_CLASS_EXTRA.get(name, [])))
    opts_pool = list(dict.fromkeys(owned + EXAM_OPTIONS.get(name, [])))
    c = {"name": name, "level": shot.get("level"), "curClass": shot.get("class"), "stats": shot.get("stats"),
         "boosted": shot.get("boosted", []), "skills": shot.get("skills", {}), "owned": owned,
         "classChoices": opts_pool, "weights": w, "required": REQUIRED.get(name, []), "steps": []}
    # 1) 观星记录
    if name in units:
        for r in records(name):
            exam = r["ok"] is not True
            cls = r["cls"]
            pool = list(dict.fromkeys(opts_pool + ([cls] if cls else [])))
            st = {"key": f"h{r['idx']}", "src": "record", "exam": exam, "cls": cls if not exam else "",
                  "seenCls": cls, "frm": r["frm"], "gains": names(r["gains"]), "cnt": sum(r["gains"]),
                  "score": score(r["gains"], w), "hidden": r["ok"] is None, "inferred": bool(r.get("inferred")), "note": r.get("note", ""),
                  "opts": grouped(name, r["seed"], r["frm"], pool, owned, w) if r["seed"] is not None else [],
                  "roll": round(exam_roll(r["seed"]) / 1e4, 2) if r["seed"] is not None else None}
            c["steps"].append(st)
        # 没记录的考试步：截图里已经是下一条记录的新职业 → 视为已完成
        recs = records(name)
        for i, r in enumerate(recs):
            if r["ok"] is None and i + 1 < len(recs) and recs[i + 1]["cls"] == shot.get("class") and recs[i + 1]["cls"] != r["cls"]:
                for st in c["steps"]:
                    if st["key"] == f"h{r['idx']}":
                        st["autoDone"] = True
        # Yizhuo 11-08：艾丝 Lv21 现在就能升级 → 截图后那一步没记录的跳过已经做过了
        for st in c["steps"]:
            if st["key"] in HIDDEN_DONE.get(name, []):
                st["autoDone"] = True
                if name == "乌尔坦德" and st["key"] in HIDDEN_NOTE:
                    st["note"] = HIDDEN_NOTE[st["key"]]
    # 2) 规划
    if name in OWNED:
        p = make_planner(name, TARGET[name])
        plans, k = plan_all(p, MAX_EXAMS)
        plan = plans[k]
        c.update({"planFrom": p.level, "planTo": p.level + p.n_levels, "planTotal": plan.total, "exams": plan.exams})
        c["thr"] = list(p.thresholds)
        # 11-08 晚（规则式）：每个还没转的中级职业，硬加进「要转的职业」后净值变多少（和现在的路线比）
        from planner import _TIER as _T, _TIER_RANK as _TR, STATS as STATS_
        gpp = p.gold_per_pt
        tg = list(getattr(plan, "targets", []))
        base_net = plan.total - plan.gold / gpp
        mg = []
        for cls in [x for x in p.exam_options if _TR.get(_T.get(x, ""), 0) == 2 and x not in tg]:
            r = p.rule_run(tg + [cls], (cls,))
            if r is None or not any(a == "升级" and x == cls for a, x in r[0]):
                continue
            used = sum(1 for a, x in r[0] if a == "升级" and x == cls)
            # 11-11：具体能力差（和现在的路线比）
            g_new, lv_ = [0] * 9, p.level
            for i_, (a_, x_) in enumerate(r[0]):
                if a_ == "升级":
                    g_new = [u + v for u, v in zip(g_new, p.result(i_, lv_, x_)[1])]; lv_ += 1
            g_old = [0] * 9
            for rr in plan.rows:
                if rr.action == "升级":
                    g_old = [u + v for u, v in zip(g_old, rr.gains)]
            dg = [u - v for u, v in zip(g_new, g_old)]
            pts_r = "、".join(f"{STATS_[i_]}{dg[i_]:+d}" for i_ in range(9) if dg[i_]) or "能力一样"
            mg.append({"cls": cls, "total": r[2], "gold": r[3], "net": round(r[2] - r[3] / gpp, 1), "dsc": r[2] - plan.total,
                       "dnet": round(r[2] - r[3] / gpp - base_net, 1), "used": used, "diff": pts_r, "dpts": sum(dg)})
        mg.sort(key=lambda x: -x["dnet"])
        c["midGain"] = mg[:5]
        c["planGold"], c["planNet"], c["targets"], c["gpp"] = plan.gold, round(base_net, 1), tg, round(gpp, 1)
        c["examWarn"] = plan.exams > 4   # Yizhuo：转职+跳过不设上限，次数多了警告
        c["p0"] = name in P0
        # 均衡加点：哪几级因为成长均衡换了职业
        bal = []
        for r in plan.rows:
            note = getattr(r, "balance_note", "")
            if not note:
                continue
            m = re.search(r"均衡：(.*)，所以用(\S+?)换(\S+?)（多 (.*?)、少 (.*?)）", note)
            why, pick, orig, more, less = m.groups()
            s1, s0 = p.result(r.step, r.level_from, pick)[0], p.result(r.step, r.level_from, orig)[0]
            bal.append({"lv": f"Lv{r.level_from}→{r.level_from + 1}", "pick": pick, "orig": orig, "more": more, "less": less, "why": why, "dsc": s1 - s0})
        c["balance"] = bal
        # 趋势：一直用现在的职业升到 35（不转职、不考试）；只换已有职业不考试
        cur_cls = next((st["cls"] for st in reversed(c["steps"]) if st["src"] == "record" and not st["exam"] and st["cls"]), shot.get("class"))
        stay = [0] * 9
        for i in range(p.n_levels):
            _, g = p.result(i, p.level + i, cur_cls)
            stay = [a + b for a, b in zip(stay, g)]
        p0 = plans[0] if plans[0] is not None and plans[0].total > 0 else None
        best0 = None
        if p0:
            best0 = [0] * 9
            for r in p0.rows:
                if r.action == "升级":
                    best0 = [a + b for a, b in zip(best0, r.gains)]
        seg, lv2 = [], p.level
        for r in plan.rows:
            if r.action == "升级":
                if seg and seg[-1][0] == "up" and seg[-1][1] == r.cls:
                    seg[-1][3] = lv2 + 1
                else:
                    seg.append(["up", r.cls, lv2, lv2 + 1])
                lv2 += 1
            else:
                real = r.cls in EXAM_OPTIONS[name]
                pc = p.exam_pct(r.cls, lv2) if real else None
                seg.append(["exam", r.cls if real else "", round(p.exam_value(r.step), 2), pc])
        # 11-11 Yizhuo：每个考试后面写「到目标等级用新职业升几级、比不用它多哪些能力」
        have_, lv_, rows_ = list(OWNED[name]), p.level, []
        for r in plan.rows:
            rows_.append((r, lv_, list(have_)))
            if r.action == "升级":
                lv_ += 1
            elif r.cls in EXAM_OPTIONS[name] and r.cls not in have_:
                have_.append(r.cls)
        ex_i = 0
        for x in seg:
            if x[0] != "exam" or not x[1]:
                continue
            cls_ = x[1]
            n_use, dg, dsc = 0, [0] * 9, 0
            for r, lvr, hv in rows_:
                if r.action == "升级" and r.cls == cls_:
                    alts = [k for k in hv if k != cls_]
                    if not alts:
                        continue
                    alt = max(alts, key=lambda k: p.result(r.step, lvr, k)[0])
                    ga = p.result(r.step, lvr, alt)[1]
                    n_use += 1
                    dg = [u + v - w_ for u, v, w_ in zip(dg, r.gains, ga)]
                    dsc += r.score - p.result(r.step, lvr, alt)[0]
            txt = "、".join(f"{STATS[i]}{dg[i]:+d}" for i in range(9) if dg[i]) or "能力一样"
            x.extend([n_use, txt, dsc])
        use_info = {x[1]: x[4:7] for x in seg if x[0] == "exam" and x[1] and len(x) > 4}
        c["route"] = seg
        c["trend"] = {"cur": cur_cls, "n": p.n_levels, "stay": stay, "best0": best0}
        c["planTotal"] = plan.total   # 11-11：一览的加权分用规划器的合计（含体格）
        c["tier"] = "P0" if name in P0 else "P2" if name in ("努蒂奴", "乌尔坦德") else "P1"
        c["str0"] = p.str_start   # 11-11：页面合计也算体格 +3（力跨过 5 的倍数）
        have = list(OWNED[name])
        lv = p.level
        for r in plan.rows:
            exam = r.action != "升级"
            pool = list(dict.fromkeys(have + list(EXAM_OPTIONS[name])))
            opts = grouped(name, p.seed_at(r.step), lv, pool, have, w)
            have_before = list(have)
            if exam and r.cls in EXAM_OPTIONS[name] and r.cls not in have:
                have.append(r.cls)
            pct = p.exam_pct(r.cls, lv) if exam and r.cls in EXAM_OPTIONS[name] else None
            routes = step_routes(name, p, r.step, lv, have_before)
            c["steps"].append({"routes": routes, "key": str(r.step + 1), "src": "plan", "exam": exam, "pct": pct,
                               "cls": r.cls if (not exam or r.cls in EXAM_OPTIONS[name]) else "",
                               "frm": lv if not exam else None, "gains": names(r.gains) if not exam else [],
                               "cnt": sum(r.gains) if not exam else 0, "score": r.score if not exam else 0,
                               "note": "；".join(x for x in (r.balance_note, r.str_note) if x), "opts": opts, "ownedAfter": list(have),
                               "roll": round(p.exam_value(r.step), 2),
                               "use": use_info.get(r.cls) if exam else None,
                               "train": (getattr(p, "exam_train", {}) or {}).get(r.cls) if exam else None,
                               # 11-11 Yizhuo：同一级里加点一样、职业等级也一样（最高级）的已有职业全部列出
                               "eq": ([k for k in have_before if _CLS_TIER.get(k) == _CLS_TIER.get(r.cls)
                                       and list(level_up(p.seed_at(r.step), data.growth(name, k, lv), 2).gains) == list(r.gains)]
                                      if not exam else None)})
            if not exam:
                lv += 1
    chars.append(c)

# 3) 档案数据（detail/summary/summary_text）并进来：回顾过往、平均对比、考试收益、说明文字
D = json.load(open(os.path.join(HERE, "detail.json"), encoding="utf-8"))
SUM = json.load(open(os.path.join(HERE, "summary.json"), encoding="utf-8"))
TXT = json.load(open(os.path.join(HERE, "summary_text.json"), encoding="utf-8"))
CHO = json.load(open(os.path.join(HERE, "choices.json"), encoding="utf-8"))
L45 = json.load(open(os.path.join(HERE, "plan45.json"), encoding="utf-8")) if os.path.exists(os.path.join(HERE, "plan45.json")) else {}
GUIDE = json.load(open(os.path.join(HERE, "guide_hanse.json"), encoding="utf-8"))
for c in chars:
    if c["name"] in L45:
        c["l45"] = L45[c["name"]]
    if c["name"] in GUIDE:
        c["guide"] = GUIDE[c["name"]]
    d, sm, tx = D.get(c["name"]), SUM.get(c["name"]), TXT["chars"].get(c["name"])
    if d:
        ps = [s for s in c["steps"] if s["src"] == "plan"]
        assert len(ps) == len(d["future"])
        avg = {(r["lv"], r["cls"]): r for r in (sm or {}).get("rows", [])}
        for s, f in zip(ps, d["future"]):
            assert s["exam"] == (f["kind"] == "考试")
            if f.get("why"): s["why"] = f["why"]
            if f.get("pred"): s["pred"] = f["pred"]
            a = avg.get((f.get("lv"), f.get("cls")))
            if a: s["es"] = a["es"]
        c["hist"] = {k: d[k] for k in ("join", "gap", "past", "now", "exam_benefit", "plan_scores", "total", "end", "wtotal", "options")}
    if sm:
        c["avg"] = {k: sm[k] for k in ("exp", "act", "ws", "wexp")}
        if c.get("planTotal") is not None:
            c["avg"]["ws"] = c["planTotal"]
    if tx:
        c["text"] = tx
    if d and sm and "trend" in c:
        exp, act, n, flags = sm["exp"], d["total"], c["trend"]["n"], []
        for i, k in enumerate(STATS):
            e, a, st0 = exp[i], act[i], c["trend"]["stay"][i]
            wt = c["weights"][i]
            tag = f"（权重 {wt}）" if wt <= 2 else ""
            if a - e <= -2 and a <= 0.65 * e:
                flags.append({"lv": "bad", "t": f"{k}到 Lv35 只涨 {a}，平均 {e}{tag}，明显偏低" + ("；一直用现在的职业也只涨 %d" % st0 if st0 <= a else "；一直用现在的职业反而能涨 %d" % st0)})
            elif a - e >= 3 and a >= 1.5 * e:
                flags.append({"lv": "good", "t": f"{k}到 Lv35 涨 {a}，平均 {e}{tag}，明显偏高"})
            if st0 - e <= -2.5 and st0 <= 0.5 * e and not (a - e <= -2 and a <= 0.65 * e):
                flags.append({"lv": "warn", "t": f"一直用现在的职业的话{k}只涨 {st0}（平均 {e}）{tag}，推荐路线补到 {a}"})
        c["trend"]["flags"] = flags
    if c["name"] in CHO:
        c["choices"] = CHO[c["name"]]["opts"]
LONG = json.load(open(os.path.join(HERE, "longview.json"), encoding="utf-8"))
for c in chars:
    if c["name"] in LONG:
        c["long"] = LONG[c["name"]]

# 吃饭（11-08）：迪线招募表「Recruit - Diet」tab 的好感（3 最爱 2 喜欢 1 普通 0 讨厌），加上三位领主（fortunesweave）
_dt = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "meals", "diet_tab.json"), encoding="utf-8"))
_REC = {"迪托利希","法毕欧","艾丝梅拉尔达","米迦艾拉","杨界","伊欧","奇洛伊卡","努蒂奴","乌尔坦德"}
_ppl = []
for r in _dt[1:]:
    if len(r) < 25 or r[0] not in ("必招", "满足", "可选"): continue
    _ppl.append({"name": r[8], "tier": r[0], "pref": [int(x) for x in r[13:25]], "in": r[8] in _REC})
_LORDS = {"蕾达": [2,2,0,0,2,2,2,0,2,2,2,2], "凯伊": [3,3,2,3,3,2,3,3,3,3,3,2], "赛奥朵拉": [2,2,1,2,2,1,2,2,1,0,2,1]}
MEALS = {"dishes": [h.split(" - ")[1] for h in _dt[0][13:25]], "people": _ppl,
         "lords": [{"name": k, "tier": "领主", "pref": v, "in": False} for k, v in _LORDS.items()]}
data_json = json.dumps({"meals": MEALS, "chars": chars, "stats": STATS, "skills": SKILLS, "team": TXT["team"], "decisions": json.load(open(os.path.join(HERE, "decisions.json"), encoding="utf-8"))}, ensure_ascii=False)
tpl = open(os.path.join(HERE, "app_template.html"), encoding="utf-8").read()
out = tpl.replace("/*ROUTE_DATA*/{}", data_json)
assert out != tpl
os.makedirs(os.path.join(HERE, "..", "html"), exist_ok=True)
open(os.path.join(HERE, "..", "html", "成长路线.html"), "w", encoding="utf-8").write(out)
open(os.path.join(OUT_DIR, "growth-route.html"), "w", encoding="utf-8").write(out)
print(len(chars), "characters", sum(len(c["steps"]) for c in chars), "steps", len(out), "bytes")

# 排版自检（11-08 加，11-11 改）：只有页面模板或本脚本改过时才跑浏览器检查；只换数据时跳过（省 ~20 秒）。
import subprocess, sys, hashlib
_h = hashlib.md5(open(os.path.join(HERE, "app_template.html"), "rb").read() + open(__file__, "rb").read()).hexdigest()
_stamp = os.path.join(HERE, ".layout_ok")
if os.path.exists(_stamp) and open(_stamp).read().strip() == _h and "--check" not in sys.argv:
    print("模板没改，跳过排版检查")
else:
    _r = subprocess.run(["node", os.path.join(HERE, "check_layout.js"), os.path.join(OUT_DIR, "growth-route.html")], capture_output=True, text=True)
    print(_r.stdout.strip())
    if _r.returncode != 0:
        sys.exit("排版自检失败，先修好再发布")
    open(_stamp, "w").write(_h)
