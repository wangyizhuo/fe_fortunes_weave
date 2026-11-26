"""
生成成长路线（纯逻辑层：所有角色与规则配置数据已抽离到 config/route_config.json）。

    python3 run_plans.py 迪托利希 --to 35 --max-exams 4
    python3 run_plans.py 法毕欧            # 默认往后 10 级、最多考 3 次

角色当前的种子和等级，从观星备份 + demo.py 里反推好的种子算出来。
要改规则参数、角色优先级、已有职业、必考/排除、保留种子、特批训练，请只改 config/route_config.json。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import demo  # noqa: E402
from fe_growth import GrowthData, level_up, next_seed  # noqa: E402
from modules.route.config_loader import load_route_config  # noqa: E402
from planner import Planner, gains_text, plan_all  # noqa: E402

CFG = load_route_config()
data = GrowthData(os.path.join(HERE, "growth_data.json"))

# 坐骑加成：从 config/route_config.json 读取
_raw_growth = data.growth
MOUNT = CFG.mount


def _growth(character, cls, level=1, mount_id=None, mount_level=0, extra=None):
    if mount_id is None and character in MOUNT:
        mount_id, f = MOUNT[character]
        mount_level = f(level)
    return _raw_growth(character, cls, level, mount_id, mount_level, extra)


data.growth = _growth
with open(os.path.join(HERE, "weights.json"), encoding="utf-8") as _f:
    W = json.load(_f)["weights"]
units = demo.load_units()

# ---------------- 从 config/route_config.json 导出的配置常量 ----------------
OWNED = CFG.owned
PHYSICAL = CFG.physical
MOUNTED = CFG.mounted
MAGIC = CFG.magic
ALL_CLASSES = CFG.all_classes
EXCLUDE = CFG.exclude
REQUIRED = CFG.required
SKIP_TAKE = CFG.skip_take
PREFER = CFG.prefer
LEVEL_FIX = CFG.level_fix
EXTRA_AFTER = CFG.extra_after
RECORD_FIX = CFG.record_fix
REPLAN_FROM_SHOT = CFG.replan_from_shot
KEEP_AFTER_SHOT = CFG.keep_after_shot
SHOT_KEY = CFG.shot_key
BOOST = CFG.boost
CONFIDENT = CFG.confident
TIEBREAK = CFG.tiebreak
RANKS = CFG.ranks
EXAM_AT_OVERRIDE = CFG.exam_at_override
TRAIN_CASE = CFG.train_case
TRAIN_TO_PASS = CFG.train_to_pass
MAGIC_MIN_WEIGHT = CFG.magic_min_weight
P0 = CFG.p0
P2 = CFG.p2
PERMIT_GOLD = CFG.permit_gold
GOLD_PER_PT = CFG.gold_per_pt
THRESHOLDS = {k: (round(500 / v, 1), round(300 / v, 1)) for k, v in GOLD_PER_PT.items()}
P2_SKIP_BELOW = CFG.p2_skip_below
ORDER = CFG.order
HORIZON_MIN_LEVEL = CFG.horizon_min_level
HORIZON_MIN_STEPS = CFG.horizon_min_steps
TRAIN_ALLOWED = CFG.train_allowed
TRAIN_PTS = CFG.train_pts
MIN_EXAM_GAIN = CFG.min_exam_gain
RENOWN = CFG.renown
MAX_EXAMS = CFG.max_exams
SKIP_RULE = CFG.skip_rule
NO_SKIP_SEEDS = CFG.no_skip_seeds
EQUAL_SEEDS = CFG.equal_seeds
ADV_CLASSES = CFG.adv_classes

with open(os.path.join(HERE, "fw_characters.json"), encoding="utf-8") as _f:
    _SEX = {c["name"]: c.get("sex") for c in json.load(_f)}
with open(os.path.join(HERE, "fw_classes.json"), encoding="utf-8") as _f:
    _RAW_CLASSES = json.load(_f)
_CLASSES = {c["name"]: c for c in _RAW_CLASSES}
_CLASS_LIMIT = {c["name"]: c.get("limit") for c in _RAW_CLASSES}
_CLS_REQ = {c["name"]: c.get("requirement") or "" for c in _RAW_CLASSES}
_KEYS = ["hp", "str", "mag", "spd", "dex", "def", "res", "lck", "cha"]
FLOORS = {n: [(c.get("minStats") or {}).get(k, 0) for k in _KEYS] for n, c in _CLASSES.items()}

with open(os.path.join(HERE, "current_stats.json"), encoding="utf-8") as _f:
    CURRENT = json.load(_f)

_ec = os.path.join(HERE, "exam_chance.json")
if os.path.exists(_ec):
    with open(_ec, encoding="utf-8") as _f:
        EXAM_CHANCE = {k: v for k, v in json.load(_f).items() if not k.startswith("说明")}
else:
    EXAM_CHANCE = {}


def _allowed(name, cls):
    if cls in EXCLUDE.get(name, []):
        return False
    if _CLASS_LIMIT.get(cls) == "女性" and _SEX.get(name) != "女":
        return False
    if cls in MAGIC and W[name][2] < MAGIC_MIN_WEIGHT:
        return False
    return True


EXAM_OPTIONS = {n: [c for c in ALL_CLASSES if _allowed(n, c)] for n in ORDER}


def shot(name):
    """角色当前的截图快照（等级、职业、能力、技能、seed_index）。全项目只从这里取。"""
    c = CURRENT.get(name, {})
    return c.get(SHOT_KEY) or c.get("shot_1105") or {}


def _cut(name):
    """快照里写了 seed_index 时，记录只保留种子位置在它之前的。"""
    return shot(name).get("seed_index")


def _draws(name):
    out, kept = [], 0
    shot_lv = (CURRENT.get(name, {}).get("shot_1105") or {}).get("level") if name in REPLAN_FROM_SHOT else None
    level = units[name]["startLevel"] + LEVEL_FIX.get(name, 0)
    for idx, d in enumerate(units[name]["draws"], start=1):
        fix = RECORD_FIX.get(name, {}).get(idx, {})
        if fix.get("drop"):
            continue
        d = {**d, **fix}
        if shot_lv is not None and level >= shot_lv:
            if kept < KEEP_AFTER_SHOT.get(name, 0) and not d["ok"]:
                kept += 1
                out.append(d)
                continue
            break
        out.append(d)
        level += d["ok"]
    return out


def current_state(name):
    """备份里最后一条记录之后的种子和等级（✓=升级，✗=考试，都推进一步）。"""
    seed, first = demo.KNOWN_SEEDS[name]
    if _cut(name) is not None:
        for _ in range(_cut(name)):
            seed = next_seed(seed)
        return seed, shot(name)["level"]
    unit = units[name]
    level = unit["startLevel"]
    for idx, draw in enumerate(_draws(name), start=1):
        for _ in range(demo.HIDDEN_STEPS.get(name, {}).get(idx, 0)):
            seed = next_seed(seed)
        if idx >= first:
            seed = next_seed(seed)
        level += draw["ok"]
    n = len(_draws(name))
    if name in REPLAN_FROM_SHOT and n < len(units[name]["draws"]):
        for _ in range(demo.HIDDEN_STEPS.get(name, {}).get(n + 1, 0)):
            seed = next_seed(seed)
    for ex in EXTRA_AFTER.get(name, []):
        seed = next_seed(seed)
        level += ex["ok"]
    return seed, level + LEVEL_FIX.get(name, 0)


TARGET = {n: max(HORIZON_MIN_LEVEL, current_state(n)[1] + HORIZON_MIN_STEPS) for n in ORDER}


def records(name):
    """备份里的观星记录，逐条：dict(idx, seed, ok, cls, frm, to, gains[9])。"""
    unit = units[name]
    seed, first = demo.KNOWN_SEEDS.get(name, (None, 1))
    level = unit["startLevel"] + LEVEL_FIX.get(name, 0)
    out = []
    cut, pos = _cut(name), 0
    if cut is not None:
        draws = [{**d, **RECORD_FIX.get(name, {}).get(i, {})} for i, d in enumerate(units[name]["draws"], start=1)]
        for idx, draw in enumerate(draws, start=1):
            if draw.get("drop"):
                continue
            for _ in range(demo.HIDDEN_STEPS.get(name, {}).get(idx, 0)):
                if idx >= first and pos >= cut:
                    return out
                out.append(dict(idx=f"{idx}-", seed=seed if idx >= first else None, ok=None, cls="", frm=level, to=None, gains=[0] * 9))
                if idx >= first:
                    seed, pos = next_seed(seed), pos + 1
            if idx >= first and pos >= cut:
                return out
            cur = seed if idx >= first else None
            g = [1 if k in draw["gains"] else 0 for k in range(9)]
            out.append(dict(
                idx=idx, seed=cur, ok=bool(draw["ok"]), cls=data.class_ids[str(draw["cls"])],
                frm=level, to=level + 1 if draw["ok"] else None, gains=g,
            ))
            if idx >= first:
                seed, pos = next_seed(seed), pos + 1
            level += draw["ok"]
        return out
    for idx, draw in enumerate(_draws(name), start=1):
        for _ in range(demo.HIDDEN_STEPS.get(name, {}).get(idx, 0)):
            out.append(dict(idx=f"{idx}-", seed=seed if idx >= first else None, ok=None, cls="", frm=level, to=None, gains=[0] * 9))
            if seed is not None and idx >= first:
                seed = next_seed(seed)
        cur = seed if (seed is not None and idx >= first) else None
        g = [1 if k in draw["gains"] else 0 for k in range(9)]
        out.append(dict(
            idx=idx, seed=cur, ok=bool(draw["ok"]), cls=data.class_ids[str(draw["cls"])],
            frm=level, to=level + 1 if draw["ok"] else None, gains=g,
        ))
        if seed is not None and idx >= first:
            seed = next_seed(seed)
        level += draw["ok"]
    n = len(_draws(name))
    if name in REPLAN_FROM_SHOT and n < len(units[name]["draws"]):
        for _ in range(demo.HIDDEN_STEPS.get(name, {}).get(n + 1, 0)):
            out.append(dict(idx=f"{n + 1}-", seed=seed, ok=None, cls="", frm=level, to=None, gains=[0] * 9))
            if seed is not None:
                seed = next_seed(seed)
    for j, ex in enumerate(EXTRA_AFTER.get(name, []), start=1):
        g = list(level_up(seed, data.growth(name, ex["cls"], level), 2).gains) if seed is not None else [0] * 9
        out.append(dict(
            idx=f"x{j}", seed=seed, ok=ex["ok"], cls=ex["cls"], frm=level,
            to=level + 1 if ex["ok"] else None, gains=g, note=ex["note"], inferred=True,
        ))
        if seed is not None:
            seed = next_seed(seed)
        level += ex["ok"]
    return out


def start_stats(name):
    """规划起点（最后一条记录之后）的能力。"""
    sh = shot(name)
    if not sh:
        return CURRENT.get(name, {}).get("stats")
    st = list(sh["stats"])
    for r in records(name) if name in units and _cut(name) is None else []:
        if r["ok"] and r["to"] > sh["level"]:
            st = [a + b for a, b in zip(st, r["gains"])]
    return st


def class_bonus(cls):
    b = (_CLASSES.get(cls) or {}).get("baseStats") or {}
    return [b.get(k, 0) for k in _KEYS]


def raw_start(name):
    """规划起点的裸能力（截图 − 当前职业加成 − 额外加成 + 截图后的记录加点）。"""
    sh = shot(name)
    if not sh:
        return None
    boost = BOOST.get(name, ([0] * 9, ""))[0]
    raw = [s - b - x for s, b, x in zip(sh["stats"], class_bonus(sh["class"]), boost)]
    for r in records(name) if name in units and _cut(name) is None else []:
        if r["ok"] and r["to"] and r["to"] > sh["level"]:
            raw = [a + b for a, b in zip(raw, r["gains"])]
    return raw


def _TIER_OF(cls):
    return (_CLASSES.get(cls) or {}).get("tier")


def renown_req(cls):
    """考 cls 要的名声等级（fw_classes 要求文字里的「名声 LvN」），没有就 None。"""
    m = re.search(r"名声 ?Lv(\d+)", (_CLASSES.get(cls) or {}).get("requirement") or "")
    return int(m.group(1)) if m else None


def exam_req(name, cls):
    """(推荐等级, 技能差几段)。"""
    text = _CLS_REQ.get(cls, "")
    m = re.search(r"推荐 Lv(\d+)", text)
    if not m:
        return None
    skills = shot(name).get("skills", {})

    def gap(sk, rk):
        need = RANKS.index(rk)
        if sk not in skills:
            return 0 if need <= 1 else 1
        return max(0, need - RANKS.index(skills[sk]))

    total = 0
    for part in text.split("·"):
        part = part.strip()
        pairs = re.findall(r"(\S+术) ([EDCBAS]\+?)", part)
        if part.startswith("主要"):
            total += sum(gap(a, b) for a, b in pairs)
        elif part.startswith("任选其一") and pairs:
            total += min(gap(a, b) for a, b in pairs)
    return int(m.group(1)), total


def train_need(name, cls):
    """考 cls 之前要练的技能列表。"""
    text = _CLS_REQ.get(cls, "")
    skills = shot(name).get("skills", {})
    out = []
    for part in text.split("·"):
        part = part.strip()
        pairs = re.findall(r"(\S+术) ([EDCBAS]\+?)", part)

        def short(sk, rk):
            need = RANKS.index(rk)
            if sk not in skills:
                return (0, None) if need <= 1 else (1, f"{sk} →{rk}（截图没有这项）")
            g = need - RANKS.index(skills[sk])
            return (g, f"{sk} {skills[sk]}→{rk}（{g} 段）") if g > 0 else (0, None)

        if part.startswith("主要"):
            out += [x for a, b in pairs if (x := short(a, b)[1])]
        elif part.startswith("任选其一") and pairs:
            _, x = min((short(a, b) for a, b in pairs), key=lambda t: t[0])
            if x:
                out.append(x + "（任选一项）")
    return out


def tier_of(name):
    """优先级标签：P0 / P1 / P2。"""
    return "P0" if name in P0 else "P2" if name in P2 else "P1"


def _TIER_RANK_OF(c):
    from planner import _TIER, _TIER_RANK
    return _TIER_RANK.get(_TIER.get(c, ""), 0)


def make_planner(name, target=None):
    seed, level = current_state(name)
    p = _mk(name, seed, level, target)
    p.confident = set(CONFIDENT.get(name, []))
    p.require_mid = not any(_TIER_RANK_OF(c) >= 2 for c in OWNED[name])
    p.equal_seeds = EQUAL_SEEDS
    tier = "P0" if name in P0 else "P2" if name in P2 else "other"
    p.thresholds = THRESHOLDS[tier]
    p.gold_per_pt, p.permit_gold = GOLD_PER_PT[tier], dict(PERMIT_GOLD)
    p.rule_based = True
    p.skip_threshold = P2_SKIP_BELOW if name in P2 else PERMIT_GOLD["初级"] / GOLD_PER_PT[tier]
    p.skip_rule = SKIP_RULE[tier]
    p.no_skip_seeds = NO_SKIP_SEEDS.get(name, set())
    p.first_bad_exam = name not in P0
    p.bad_rule = SKIP_RULE["P0"]
    p.exam_at_override = dict(EXAM_AT_OVERRIDE.get(name, {}))
    p.exam_req = {c: r for c in EXAM_OPTIONS.get(name, []) if (r := exam_req(name, c))}
    p.TRAIN_PTS_PER_RANK = TRAIN_PTS[tier_of(name)]
    p.min_exam_gain = MIN_EXAM_GAIN
    p.raw_stats = raw_start(name)
    p.floors = FLOORS
    p.renown_req = {c: r for c in EXAM_OPTIONS.get(name, []) if (r := renown_req(c))}
    if RENOWN is not None:
        for c, r in p.renown_req.items():
            if RENOWN < r:
                p.exam_chance = dict(p.exam_chance or {}, **{c: 0})
    p.exam_train_ranks = {}
    p.skip_pool = [
        c for c, x in _CLASSES.items()
        if x.get("tier") == "初级" and not (x.get("limit") == "女性" and _SEX.get(name) != "女")
    ]
    p.skip_req = {c: q for c in p.skip_pool if (q := exam_req(name, c))}
    p.exam_train = {c: t for c in p.exam_req if (t := train_need(name, c))}
    if TRAIN_TO_PASS and TRAIN_ALLOWED[tier_of(name)]:
        p.exam_train = {c: t for c in p.exam_req if (t := train_need(name, c))}
        p.exam_train_ranks = {c: r[1] for c, r in p.exam_req.items() if r[1] > 0}
        p.exam_req = {c: (r[0], 0) for c, r in p.exam_req.items()}
        p.exam_chance = {c: v for c, v in (p.exam_chance or {}).items() if c not in p.exam_train}
    for c in TRAIN_CASE.get(name, []):
        if c in p.exam_req and p.exam_req[c][1] > 0 and not TRAIN_ALLOWED[tier_of(name)]:
            p.exam_train_ranks = dict(p.exam_train_ranks or {}, **{c: p.exam_req[c][1]})
            p.exam_req = dict(p.exam_req, **{c: (p.exam_req[c][0], 0)})
            p.exam_chance = {k: v for k, v in (p.exam_chance or {}).items() if k != c}
    p.mid_train = {}
    if p.require_mid and not TRAIN_ALLOWED[tier_of(name)]:
        p.mid_train = {
            c: (r[0], r[1]) for c, r in p.exam_req.items()
            if _TIER_RANK_OF(c) == 2 and r[1] > 0
        }
    tb = TIEBREAK.get(name, [])
    if tb:
        p.tiebreak = list(tb)
        p.exam_options = tuple(sorted(p.exam_options, key=lambda c: tb.index(c) if c in tb else len(tb)))
    return p


def _mk(name, seed, level, target):
    p = Planner(
        data, name, seed, level, target or level + 10,
        OWNED[name], EXAM_OPTIONS[name], W[name],
        required=REQUIRED.get(name, []), prefer=PREFER.get(name),
        stats=start_stats(name), exam_chance=EXAM_CHANCE.get(name),
    )
    p.skip_take = tuple(SKIP_TAKE.get(name, ()))
    return p


def print_plan(limit, plan):
    print(f"\n最多考 {limit} 次（实际考 {plan.exams} 次）：总分 {plan.total}")
    for r in plan.rows:
        if r.action == "升级":
            print(
                f"  步{r.step + 1:>2}  Lv{r.level_from}→{r.level_from + 1}  升级 {r.cls:4}"
                f" {gains_text(r.gains):24} {r.score:>3}  | {r.compare}"
            )
        else:
            print(f"  步{r.step + 1:>2}  考试 {r.cls}（这一步升级最多 {r.score} 分：{gains_text(r.gains)}）")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("name")
    ap.add_argument("--to", type=int, help="目标等级（默认当前 +10）")
    ap.add_argument("--max-exams", type=int, default=3)
    a = ap.parse_args()
    p = make_planner(a.name, a.to)
    print(f"{a.name} 当前 Lv{p.level}，种子 {p.seed_at(0)}")
    plans, k = plan_all(p, a.max_exams)
    for limit, plan in enumerate(plans):
        print_plan(limit, plan)
    print(f"\n建议：最多考 {k} 次（再多考一次多拿不到 8 分）")
