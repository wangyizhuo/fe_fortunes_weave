"""
自动检查：把 Yizhuo 过去检查产出的方式写成程序，每次 build.sh 都跑，有问题就不发布。

    python3 checks.py                 # 跑全部检查（页面数据要先 build 出来，没有就跳过页面类检查）
    python3 checks.py --update-golden # 规则或数据有意改动后，更新「结果快照」（会打印改了什么）

每条检查都写明「来自 Yizhuo 的哪种检查 / 想要什么」，见 docs/检查规则.md。
检查分四类：
  D 数据：种子回测、截图等级/职业、已有职业、权重、技能、规则记录（decisions.json）
  P 规划：职业先拿到再用、考试按种子能过、每级选最好的已有职业、跳过有理由、必考/排除、局部最优……
  U 页面：每个考试都有成功率、所有人同一套职业清单、比较都有具体数值差、没有过时/坏掉的文字……
  G 快照：每个角色的路线结果和上次确认的一样（变了要说清楚变了什么）
"""
from __future__ import annotations

import functools
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import run_plans as R
from run_plans import ORDER, TARGET, MAX_EXAMS
from fe_growth import STATS, level_up
from planner import plan_all, _TIER, _TIER_RANK, plan_gold

OUT_DIR = os.environ.get("FE_OUT_DIR") or os.path.join(HERE, "..", "..", "out")
GOLDEN = os.path.join(HERE, "tests", "golden_plans.json")

CHECKS = []   # (编号, 说明, 函数)；函数返回问题列表（空 = 通过）


def check(cid, desc):
    def deco(f):
        CHECKS.append((cid, desc, f))
        return f
    return deco


@functools.lru_cache(None)
def plan(name):
    p = R.make_planner(name, TARGET[name])
    plans, k = plan_all(p, MAX_EXAMS)
    return p, plans[k]


def page():
    path = os.path.join(OUT_DIR, "page_data.json")
    return json.load(open(path, encoding="utf-8")) if os.path.exists(path) else None


def tier_rank(c):
    return _TIER_RANK.get(_TIER.get(c, ""), 0)


# ============================== D 数据 ==============================

# 种子和观星记录对不上的已知条目（2026-11-05 回测时就查过，都是记录本身的问题）。新出现的不对 = 种子/等级标签/成长率出错。
KNOWN_RECORD_MISMATCH = {
    ("迪托利希", 3): "19 级记录只写了「HP 力」，公式是 HP 力 魔 技（主表那行合计也是空的）",
    ("法毕欧", 2): "记录少了技", ("法毕欧", 12): "记录少了幸",
    ("杨界", 3): "种子从第 3 条起算，第 3 条差两项",
    ("乌尔坦德", 2): "第 2 条没记录加点",
    ("米迦艾拉", 7): "记录多了防",
    ("艾丝梅拉尔达", 3): "第 3 条差 1 项",
    ("奇洛伊卡", 1): "差 1 项（防/魔防）", ("奇洛伊卡", 3): "差 1 项（技/防）",
}


@check("D1", "观星记录回测：有种子的每条升级记录，按种子算出的加点和记录一致（Yizhuo：『实际升级和你的种子预测对不上』）")
def d_backtest():
    bad = []
    for n in ORDER:
        for r in R.records(n):
            if not r["ok"] or r["seed"] is None or r.get("inferred"):
                continue
            g = list(level_up(r["seed"], R.data.growth(n, r["cls"], r["frm"]), 2).gains)
            if g != r["gains"] and (n, r["idx"]) not in KNOWN_RECORD_MISMATCH:
                bad.append(f"{n} 第 {r['idx']} 条 Lv{r['frm']} {r['cls']}：记录 {r['gains']}，种子算出 {g}")
    return bad


@check("D2", "规划起点 = 截图等级，截图职业是已有职业（Yizhuo：『伊欧为什么是 Lv23 轻骑兵，不是战车么』『米迦现在 22』）")
def d_start_matches_shot():
    bad = []
    for n in ORDER:
        shot = R.CURRENT[n]["shot_1105"]
        p, _ = plan(n)
        if p.level != shot["level"]:
            bad.append(f"{n}：规划从 Lv{p.level} 开始，截图是 Lv{shot['level']}")
        if shot["class"] not in R.OWNED[n]:
            bad.append(f"{n}：截图职业 {shot['class']} 不在 OWNED 里")
    return bad


@check("D3", "基础数据完整：每人都有种子、权重（9 项 1～5）、已有职业（都含平民）、截图能力和 12 项技能（Yizhuo：『所有人都有平民』）")
def d_base_data():
    bad, cls = [], set(_TIER)
    for n in ORDER:
        w = R.W.get(n)
        if not w or len(w) != 9 or any(not isinstance(x, int) or not 1 <= x <= 5 for x in w):
            bad.append(f"{n}：权重不对 {w}")
        if n not in __import__("demo").KNOWN_SEEDS:
            bad.append(f"{n}：没有种子")
        if "平民" not in R.OWNED[n]:
            bad.append(f"{n}：已有职业里没有平民")
        bad += [f"{n}：已有职业 {c} 不在职业表里" for c in R.OWNED[n] if c not in cls]
        shot = R.CURRENT[n].get("shot_1105") or {}
        if len(shot.get("stats", [])) != 9:
            bad.append(f"{n}：截图能力不是 9 项")
        sk = shot.get("skills", {})
        if len(sk) != 12 or any(v not in R.RANKS for v in sk.values()):
            bad.append(f"{n}：技能不是 12 项或等级写错 {sk}")
    return bad


@check("D4", "规则记录 decisions.json 格式统一、日期不倒退，写了代码位置的要真的存在（Yizhuo：『找一个地方，记录我所有的决定』）")
def d_decisions():
    bad, last = [], ""
    ds = json.load(open(os.path.join(HERE, "decisions.json"), encoding="utf-8"))
    src = {f[:-3]: open(os.path.join(HERE, f), encoding="utf-8").read() for f in os.listdir(HERE) if f.endswith(".py")}
    for i, d in enumerate(ds):
        if not isinstance(d, dict) or not {"date", "scope", "rule"} <= set(d):
            bad.append(f"第 {i + 1} 条格式不对：{d}")
            continue
        if not re.fullmatch(r"\d{4}-\d\d-\d\d", d["date"]) or d["date"] < last:
            bad.append(f"第 {i + 1} 条日期 {d['date']} 不对或倒退")
        last = max(last, d["date"])
        for mod, sym in re.findall(r"\b(planner|run_plans|make_html|plan45|make_choices)\.([A-Za-z_][A-Za-z0-9_]*)", d.get("where", "")):
            if sym not in ("py",) and not re.search(rf"\b{sym}\b", src.get(mod, "")):
                bad.append(f"第 {i + 1} 条写的代码位置 {mod}.{sym} 已经不存在")
    return bad


# ============================== P 规划 ==============================

@check("D5", "data/ 里每个角色的可读数据和程序一致（Yizhuo 11-11：『所有数据按可读方式存一份，并且有校验』）；不一致 → 跑 export_data.py")
def d_export_fresh():
    import export_data
    return [f"data/{p} 过期或缺失" for p in export_data.stale()]


@check("D6", "种子链连续：每条有种子的记录往后推一步 = 下一条的种子，最后推到的就是规划起点的种子（防止漏记/多记一步）")
def d_seed_chain():
    from fe_growth import next_seed
    bad = []
    for n in ORDER:
        recs = [r for r in R.records(n) if r["seed"] is not None]
        for a, b in zip(recs, recs[1:]):
            if next_seed(a["seed"]) != b["seed"]:
                bad.append(f"{n}：第 {a['idx']} 条种子 {a['seed']} 推一步不是第 {b['idx']} 条的 {b['seed']}")
        seed, _ = R.current_state(n)
        if recs and next_seed(recs[-1]["seed"]) != seed:
            bad.append(f"{n}：最后一条记录推一步 ≠ 规划起点种子 {seed}")
    return bad


@check("D7", "能力和技能合理：9 项能力都在 0～99、HP 最高之一不为 0；起点能力 ≥ 截图能力；技能等级是 E～S+；已有职业都在职业表里；等级随记录单调上升")
def d_sane_values():
    bad, cls = [], {c["name"] for c in json.load(open(os.path.join(HERE, "fw_classes.json"), encoding="utf-8"))}
    for n in ORDER:
        shot = R.CURRENT[n]["shot_1105"]
        st = R.start_stats(n)
        for label, v in (("截图", shot["stats"]), ("起点", st)):
            if len(v) != 9 or any(not (0 <= x <= 99) for x in v) or v[0] <= 0:
                bad.append(f"{n}：{label}能力不合理 {v}")
        if any(a < b for a, b in zip(st, shot["stats"])):
            bad.append(f"{n}：起点能力比截图还低 {st} < {shot['stats']}")
        bad += [f"{n}：技能 {k} 等级 {v} 不认识" for k, v in shot["skills"].items() if v not in R.RANKS]
        bad += [f"{n}：已有职业 {c} 不在职业表" for c in R.OWNED[n] if c not in cls]
        lv = [r["frm"] for r in R.records(n)]
        if lv != sorted(lv):
            bad.append(f"{n}：记录里的等级倒退 {lv}")
        if not (1 <= shot["level"] <= 99):
            bad.append(f"{n}：截图等级 {shot['level']} 不合理")
    return bad


@check("D8", "吃饭喜好：每个已招角色在迪线招募表里都有 12 道菜、每道 0～3（讨厌/普通/喜欢/最爱）；迪的最爱 = 表里「最爱的菜」一栏")
def d_meals():
    import export_data
    path = os.path.join(export_data.ROOT, "meals", "diet_tab.json")
    rows = json.load(open(path, encoding="utf-8"))
    bad, seen = [], {}
    for r in rows[1:]:
        if len(r) >= 25 and r[8] in ORDER and r[8] not in seen:
            seen[r[8]] = r
    for n in ORDER:
        r = seen.get(n)
        if r is None:
            bad.append(f"{n}：吃饭表里没有")
            continue
        v = r[13:25]
        if len(v) != 12 or any(x not in ("0", "1", "2", "3") for x in v):
            bad.append(f"{n}：喜好不是 12 个 0～3：{v}")
            continue
        fav = {d for d, x in zip(export_data.DISHES, v) if x == "3"}
        listed = {x for x in (r[25] if len(r) > 25 else "").replace("，", "、").split("、") if x}
        if listed and fav != listed:
            bad.append(f"{n}：最爱的菜 {sorted(fav)} 和表里写的 {sorted(listed)} 不一致")
    return bad


@check("P1", "职业先拿到再用：每级用的职业是已有的或之前考过的，考进的职业按种子判定能过（Yizhuo：『保证后面需要的职业，前面已经获得了』『后续职业是考过的』）")
def p_owned_before_use():
    bad = []
    for n in ORDER:
        p, pl = plan(n)
        have, lv = set(p.owned), p.level
        for (a, c), r in zip(pl.raw_actions, pl.rows):
            if a == "升级":
                if c not in have:
                    bad.append(f"{n} Lv{lv}：用 {c} 升级，但还没拿到")
                lv += 1
            elif c not in (None, "跳过"):
                if not p.exam_ok(r.step, c, lv):
                    bad.append(f"{n} 第 {r.step + 1} 步：考 {c}，但这个种子考不过")
                have.add(c)
    return bad


@check("P2", "每人都升到目标等级（Lv35）")
def p_reach_target():
    return [f"{n}：只升了 {sum(r.action == '升级' for r in plan(n)[1].rows)} 级" for n in ORDER
            if sum(r.action == "升级" for r in plan(n)[1].rows) != TARGET[n] - plan(n)[0].level]


@check("P3", "必考职业都考到，排除的职业不出现（Yizhuo：迪必考恶棍、法毕欧必考萨满；迪不要重装步兵）")
def p_required_excluded():
    bad = []
    for n in ORDER:
        p, pl = plan(n)
        ex = {c for a, c in pl.raw_actions if a == "考试"}
        bad += [f"{n}：必考的 {c} 没考" for c in R.REQUIRED.get(n, []) if c not in ex and c not in p.owned]
        for c in R.EXCLUDE.get(n, []):
            if c in p.exam_options or any(r.cls == c for r in pl.rows):
                bad.append(f"{n}：排除的 {c} 还在候选或路线里")
    return bad


@check("P4", "所有人用同一套职业清单：全部 17 个初级+中级职业减去个人排除（Yizhuo：『保证所有的角色的生成逻辑都一样』『所有职业都要考虑并且列出』）")
def p_same_class_pool():
    bad, allc = [], set(R.ALL_CLASSES)
    if len(allc) != 17:
        bad.append(f"初级+中级职业应是 17 个，现在 {len(allc)} 个")
    for c in allc:
        if _TIER.get(c) not in ("初级", "中级"):
            bad.append(f"{c} 在职业表里不是初级/中级（是 {_TIER.get(c)}）")
    for n in ORDER:
        want = allc - set(R.EXCLUDE.get(n, []))
        if set(R.EXAM_OPTIONS[n]) != want:
            bad.append(f"{n}：可考职业和统一清单不一样，多 {set(R.EXAM_OPTIONS[n]) - want}，少 {want - set(R.EXAM_OPTIONS[n])}")
    return bad


@check("P5", "每级用最好的已有职业：加权分（含体格）不是最高就必须写明原因（均衡/体格）；同分取级别高的（Yizhuo：『22-23 为什么选 15 分而不是 16 分』『杨界有一级用平民更高但没选』『即便点数没区别也用中级拿精通』）")
def p_best_class():
    bad = []
    for n in ORDER:
        p, pl = plan(n)
        have = set(p.owned)
        cs = p.str_start
        for (a, c), r in zip(pl.raw_actions, pl.rows):
            if a != "升级":
                if c not in (None, "跳过"):
                    have.add(c)
                continue
            lv = r.level_from

            def val(x):
                s, g = p.result(r.step, lv, x)
                return s + (p.str_gain_bonus(cs, g) if cs is not None else 0)
            best = max(val(x) for x in have)
            mine = val(r.cls)
            if mine < best - 1e-9 and not (r.balance_note or r.str_note):
                bad.append(f"{n} Lv{lv}→{lv + 1}：用 {r.cls}（{mine}）不是最高（{best}），也没写原因")
            same = [x for x in have if p.result(r.step, lv, x)[1] == p.result(r.step, lv, r.cls)[1]]
            top = max(tier_rank(x) for x in same)
            if tier_rank(r.cls) < top and not r.balance_note:
                bad.append(f"{n} Lv{lv}→{lv + 1}：{r.cls} 和更高级的 {[x for x in same if tier_rank(x) == top]} 加点一样，应该用高级的")
            if cs is not None:
                cs += r.gains[1]
    return bad


@check("P6", "每次考试/跳过都有规则依据：这一步按跳过条件该跳，或者是值得的转职（Yizhuo：『艾丝 31 级为什么跳过』『Lv42 跳过为什么』『米迦 33 级为什么要考剑客』）")
def p_skip_justified():
    bad = []
    for n in ORDER:
        p, pl = plan(n)
        why = getattr(pl, "why", {}) or {}
        for (a, c), r in zip(pl.raw_actions, pl.rows):
            if a != "考试":
                continue
            w = why.get(r.step)
            if w is None:
                bad.append(f"{n} 第 {r.step + 1} 步：考试/跳过没有记录原因")
            elif c in (None, "跳过") and not w.get("want_skip"):
                bad.append(f"{n} 第 {r.step + 1} 步：跳过了，但这一级（{w.get('s')} 分）不满足跳过条件")
            elif w.get("keep"):
                bad.append(f"{n} 第 {r.step + 1} 步：这一级是 Yizhuo 指定保留的，却拿来考试/跳过")
    return bad


@check("P7", "Yizhuo 指定保留的种子不跳过也不拿来考试（迪 Lv25『力 技 幸 魅』、Lv31『魔 防 魔防 幸 魅』）")
def p_no_skip_seeds():
    bad = []
    for n, seeds in R.NO_SKIP_SEEDS.items():
        p, pl = plan(n)
        bad += [f"{n} 第 {r.step + 1} 步：种子 {r.seed} 应保留，却是 {r.action}" for r in pl.rows if r.seed in seeds and r.action != "升级"]
    return bad


@check("P8", "考进去的新职业至少用来升一级，否则显示成跳过（Yizhuo：『后面没有用这个职业，如果是为了跳过就写跳过』）")
def p_exam_used():
    bad = []
    for n in ORDER:
        p, pl = plan(n)
        used = {r.cls for r in pl.rows if r.action == "升级"}
        bad += [f"{n}：考了 {r.cls} 却没用来升级" for r in pl.rows
                if r.action != "升级" and r.cls != "跳过" and r.cls not in used and r.cls not in p.required]
    return bad


@check("P9", "局部最优：去掉路线里任何一个非必考的考试（按规则重走），净值都不会更高（Yizhuo：『米迦为什么要考诅咒师，这个算法不对吧』）")
def p_local_optimum():
    bad = []
    for n in ORDER:
        p, pl = plan(n)
        mine = p.plan_net(pl.raw_actions, pl.total, pl.gold)
        for c in [t for t in pl.targets if t not in p.required]:
            alt = p.rule_run([t for t in pl.targets if t != c])
            if alt and p.plan_net(alt[0], alt[2], alt[3]) > mine + 1e-6:
                bad.append(f"{n}：不考 {c} 净值 {p.plan_net(alt[0], alt[2], alt[3]):.1f} > 现在 {mine:.1f}")
    return bad


@check("P10", "合计口径一致：路线加权分 = 每级分 + 体格加分；手形金币 = 实际买的手形（Yizhuo：『页面 171 你说 174』这类口径不一致）")
def p_totals():
    bad = []
    for n in ORDER:
        p, pl = plan(n)
        s = sum(r.score + r.bonus for r in pl.rows if r.action == "升级")
        if s != pl.total:
            bad.append(f"{n}：合计 {pl.total} ≠ 逐级相加 {s}")
        g = sum(p.permit_gold["初级"] if c in (None, "跳过") else p.permit_gold.get(_TIER.get(c, "中级"), 500)
                for a, c in pl.raw_actions if a == "考试")
        if g != pl.gold or g != plan_gold(p, pl):
            bad.append(f"{n}：手形金币对不上 {pl.gold} / {g} / {plan_gold(p, pl)}")
    return bad


@check("P11", "到 Lv45：每人最多转一次上级职业（Yizhuo 11-08）")
def p_lv45():
    path = os.path.join(HERE, "plan45.json")
    if not os.path.exists(path):
        return []
    adv = {"上级", "高级"}
    bad = []
    for n, d in json.load(open(path, encoding="utf-8")).items():
        ex = [s.get("exam") for s in d.get("steps", []) if s.get("exam")]
        k = sum(_TIER.get(c) in adv for c in ex)
        if k > 1:
            bad.append(f"{n}：到 Lv45 转了 {k} 次上级 {ex}")
    return bad


@check("P12", "全局对比：只换 1～2 个要考的职业（任意组合和顺序），净值都不会比现在的路线高出 1 分以上（P9 的加强版，抓贪心漏掉的组合）")
def p_pair_search():
    import itertools
    bad = []
    for n in ORDER:
        p, pl = plan(n)
        mine = p.plan_net(pl.raw_actions, pl.total, pl.gold)
        req = list(dict.fromkeys(p.required))
        cands = [c for c in p.exam_options if c not in req]
        for k in (1, 2):
            for combo in itertools.combinations(cands, k):
                for order in itertools.permutations(combo):
                    r = p.rule_run(req + list(order))
                    if r is None or not all(any(a == "升级" and x == c for a, x in r[0]) for c in combo):
                        continue
                    v = p.plan_net(r[0], r[2], r[3])
                    if v > mine + PAIR_TOL:
                        bad.append(f"{n}：考 {'、'.join(order)} 净值 {v:.1f}，比现在 {mine:.1f} 高")
    return bad


PAIR_TOL = 1.0   # 差 1 分以内算一样（训练成本本身是估计的）；11-11 米迦「猎兵+诅咒师」比「弓箭手」高 0.2，Yizhuo 已定考弓箭手


# ============================== U 页面 ==============================

def _plan_chars(pg):
    return [c for c in pg["chars"] if "planTotal" in c]


@check("U1", "页面和规划器一致：总分、考试次数、步数、优先级标签（Yizhuo：『确定全部都更新好了么』）")
def u_consistent():
    pg = page()
    if pg is None:
        return []
    bad = []
    for c in _plan_chars(pg):
        p, pl = plan(c["name"])
        if c["planTotal"] != pl.total:
            bad.append(f"{c['name']}：页面总分 {c['planTotal']} ≠ 规划 {pl.total}")
        steps = [s for s in c["steps"] if s["src"] == "plan"]
        if len(steps) != len(pl.rows):
            bad.append(f"{c['name']}：页面 {len(steps)} 步 ≠ 规划 {len(pl.rows)} 步")
        if c.get("tier") != R.tier_of(c["name"]):
            bad.append(f"{c['name']}：页面优先级 {c.get('tier')} ≠ {R.tier_of(c['name'])}")
        if c.get("examWarn") != (pl.exams > 4):
            bad.append(f"{c['name']}：考试+跳过 {pl.exams} 次，警告标记不对")
        if c.get("avg", {}).get("ws") not in (None, pl.total):
            bad.append(f"{c['name']}：平均对比用的加权分 {c['avg']['ws']} ≠ {pl.total}")
    return bad


@check("U2", "每个考试/跳过都显示判定值和成功率；每级都有四种走法（正常/转职/考试/跳过）（Yizhuo 11-09：『每个考试或跳过都要显示具体的通过概率』）")
def u_exam_info():
    pg = page()
    if pg is None:
        return []
    bad = []
    for c in _plan_chars(pg):
        for s in c["steps"]:
            if s["src"] != "plan":
                continue
            if s.get("roll") is None:
                bad.append(f"{c['name']} 第 {s['key']} 步：没有判定值")
            if s["exam"] and s.get("cls") and s.get("pct") is None:
                bad.append(f"{c['name']} 第 {s['key']} 步：考 {s['cls']} 没有成功率")
            rt = s.get("routes") or {}
            if "exams" not in rt or "avg15" not in rt:
                bad.append(f"{c['name']} 第 {s['key']} 步：缺四种走法数据")
            for e in rt.get("exams", []):
                if e.get("pct") is None or e.get("pass") is None:
                    bad.append(f"{c['name']} 第 {s['key']} 步：考 {e['cls']} 的成功率/能否通过缺失")
    return bad


@check("U3", "每级的选项列出全部职业（已有 + 17 个可考），所有人一样（Yizhuo：『Fabio 每个等级为什么没有像迪一样显示所有其他职业』）")
def u_all_options():
    pg = page()
    if pg is None:
        return []
    bad = []
    for c in _plan_chars(pg):
        want = set(c["owned"]) | set(R.EXAM_OPTIONS[c["name"]])
        for s in c["steps"]:
            if s["src"] != "plan":
                continue
            got = {x for o in s["opts"] for x in o["classes"]}
            if not want <= got:
                bad.append(f"{c['name']} 第 {s['key']} 步：选项少了 {sorted(want - got)}")
                break
    return bad


@check("U4", "比较都给具体数值差（每项能力 ± 和净值），不只给加权分（Yizhuo：『不讲成长率，只讲具体的数值区别』『展示具体的数值差距，包括差值和净值』）")
def u_concrete_diffs():
    pg = page()
    if pg is None:
        return []
    bad = []
    for c in _plan_chars(pg):
        for m in c.get("midGain", []):
            if not m.get("diff") or m.get("dnet") is None:
                bad.append(f"{c['name']}：多转 {m['cls']} 的比较缺能力差或净值差")
        for s in c["steps"]:
            if s["src"] == "plan" and s["exam"] and s.get("cls") and s.get("use") is None:
                bad.append(f"{c['name']} 第 {s['key']} 步：考 {s['cls']} 没写之后用几级、多哪些能力")
        for o in c.get("choices", []):
            if "diff" not in o or "dnet" not in o:
                bad.append(f"{c['name']}：长期选择「{o.get('title')}」缺能力差或净值差")
    return bad


@check("U5", "同一级加点一样、级别一样的已有职业全部列出（Yizhuo：『剑客和恶棍升级结果一样，都显示出来』）")
def u_equal_classes():
    pg = page()
    if pg is None:
        return []
    bad = []
    for c in _plan_chars(pg):
        for s in c["steps"]:
            if s["src"] == "plan" and not s["exam"] and s.get("cls") and s["cls"] not in (s.get("eq") or []):
                bad.append(f"{c['name']} 第 {s['key']} 步：并列职业列表里没有用的那个 {s['cls']}")
    return bad


BANNED = {
    "随便考": "11-06 起统一叫「跳过」", "[需考]": "11-08 起写「要先转职：X」", "需考": "11-08 起写「要先转职/考试」",
    "技能没确认": "11-08 技能都有了，这个标签是过时的", "undefined": "页面渲染出错", "NaN": "页面渲染出错",
    "[object Object]": "页面渲染出错",
}


@check("U6", "页面里没有过时或坏掉的文字（Yizhuo：『为什么迪线还有技能没确认』『不要用考试这种 ambiguous word』『我的决定』表里的 undefined）")
def u_banned_words():
    pg = page()
    if pg is None:
        return []
    text = json.dumps({k: v for k, v in pg.items() if k != "decisions"}, ensure_ascii=False)   # 规则记录会引用旧说法，不算
    bad = [f"页面数据里有「{w}」：{why}" for w, why in BANNED.items() if w in text]
    tpl = open(os.path.join(HERE, "app_template.html"), encoding="utf-8").read()
    bad += [f"页面模板里有「{w}」：{why}" for w, why in BANNED.items() if w in ("随便考", "[需考]", "需考", "技能没确认") and w in tpl]
    return bad


@check("U7", "四种走法的名称在页面上统一：正常 / 转职 / 考试 / 跳过（Yizhuo 11-09：『使用我要求的术语』）")
def u_terms():
    tpl = open(os.path.join(HERE, "app_template.html"), encoding="utf-8").read()
    return [f"页面模板里没有「{t}」这个走法名" for t in ("正常", "转职", "考试", "跳过") if t not in tpl]


@check("U8", "手写说明里不写数字：分数、等级、判定值一律由程序生成（Yizhuo：『所有的规则都应该固化在程序里，用数据 + 程序生成』；11-11 发现手写说明还停在 11-05 的旧路线）")
def u_no_handwritten_numbers():
    d = json.load(open(os.path.join(HERE, "summary_text.json"), encoding="utf-8"))
    return [f"{n} 的手写简介里有数字：{v['intro']}" for n, v in d["chars"].items() if re.search(r"\d", json.dumps(v, ensure_ascii=False))]


# ============================== G 快照 ==============================

def snapshot():
    out = {}
    for n in ORDER:
        p, pl = plan(n)
        pts = [0] * 9
        for r in pl.rows:
            if r.action == "升级":
                pts = [a + b for a, b in zip(pts, r.gains)]
        out[n] = {"from": p.level, "to": TARGET[n], "加权分": pl.total, "点数": sum(pts),
                  "各项": dict(zip(STATS, pts)), "净值": round(p.plan_net(pl.raw_actions, pl.total, pl.gold), 2),
                  "手形金币": pl.gold, "路线": " ".join(f"{r.level_from}{r.cls}" if r.action == "升级" else f"[{r.cls}]" for r in pl.rows)}
    return out


def golden_diff(old, new):
    lines = []
    for n in ORDER:
        a, b = old.get(n), new.get(n)
        if a == b:
            continue
        if a is None:
            lines.append(f"{n}：新加入")
            continue
        ch = [f"{k} {a[k]}→{b[k]}" for k in ("from", "加权分", "点数", "净值", "手形金币") if a.get(k) != b.get(k)]
        st = [f"{s}{b['各项'][s] - a['各项'][s]:+d}" for s in STATS if a["各项"].get(s) != b["各项"].get(s)]
        if st:
            ch.append("能力 " + " ".join(st))
        if a["路线"] != b["路线"]:
            ch.append(f"路线变了：{b['路线']}")
        lines.append(f"{n}：" + "；".join(ch))
    return lines


@check("G1", "结果快照：每人的路线、加权分、点数、净值和上次确认的一样；有意改了规则就跑 --update-golden，并把变化告诉 Yizhuo")
def g_golden():
    if not os.path.exists(GOLDEN):
        return ["还没有快照，先跑 python3 checks.py --update-golden"]
    return golden_diff(json.load(open(GOLDEN, encoding="utf-8")), snapshot())


def run(ids=None):
    failed = 0
    for cid, desc, f in CHECKS:
        if ids and cid not in ids:
            continue
        probs = f()
        print(("✗ " if probs else "✓ ") + cid + " " + desc.split("（")[0])
        for x in probs[:20]:
            print("    " + x)
        failed += bool(probs)
    return failed


if __name__ == "__main__":
    if "--update-golden" in sys.argv:
        new = snapshot()
        old = json.load(open(GOLDEN, encoding="utf-8")) if os.path.exists(GOLDEN) else {}
        print("\n".join(golden_diff(old, new)) or "快照没有变化")
        json.dump(new, open(GOLDEN, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        sys.exit(0)
    n = run([a for a in sys.argv[1:] if not a.startswith("-")])
    print(f"\n{len(CHECKS) - n}/{len(CHECKS)} 项检查通过" if n else f"\n全部 {len(CHECKS)} 项检查通过")
    sys.exit(1 if n else 0)
