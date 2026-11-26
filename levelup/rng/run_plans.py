"""
生成成长路线。

    python3 run_plans.py 迪托利希 --to 35 --max-exams 4
    python3 run_plans.py 法毕欧            # 默认往后 10 级、最多考 3 次

角色当前的种子和等级，从观星备份 + demo.py 里反推好的种子算出来。
已有职业、可以考的职业在下面的表里改。
"""

import collections
import argparse
import json
import os

import demo
from fe_growth import GrowthData, level_up, next_seed
from planner import Planner, gains_text, plan_all

HERE = os.path.dirname(os.path.abspath(__file__))
data = GrowthData(os.path.join(HERE, "growth_data.json"))

# 坐骑加成：伊欧骑罗西南，一开始 3 级、后来 4 级（Yizhuo 11-05；按 Lv23 之后算 4 级）
_raw_growth = data.growth
MOUNT = {"伊欧": ("RID_ロシナン", lambda lv: 3 if lv < 23 else 4)}


def _growth(character, cls, level=1, mount_id=None, mount_level=0, extra=None):
    if mount_id is None and character in MOUNT:
        mount_id, f = MOUNT[character]
        mount_level = f(level)
    return _raw_growth(character, cls, level, mount_id, mount_level, extra)


data.growth = _growth
W = json.load(open(os.path.join(HERE, "weights.json"), encoding="utf-8"))["weights"]
units = demo.load_units()

# 已有职业（来自主表「成长记录」和之前的转职记录）
OWNED = {
    "迪托利希": ["剑客", "斗士", "士兵"],   # 11-08 兵种截图：有士兵、没有猎兵
    "法毕欧": ["诅咒师"],
    "杨界": ["诅咒师"],
    "乌尔坦德": ["诅咒师"],
    "米迦艾拉": ["斗士", "士兵", "平民"],   # Yizhuo 11-07 确认有平民
    "努蒂奴": ["飞鸵兵"],
    "艾丝梅拉尔达": ["飞鸵兵", "斗士", "士兵"],   # 11-08 兵种截图：有士兵；11-25 重开章节：天翼兵考试是本章做的，重开后没了
    "伊欧": ["轻骑兵", "平民"],   # 11-25 重开章节：转战车兵的考试是本章做的，重开后没了（种子停在那次考试之前）
    "奇洛伊卡": ["猎兵", "斗士"],
}

# Yizhuo 11-07：所有人都有平民
for _n in OWNED:
    if "平民" not in OWNED[_n]:
        OWNED[_n].append("平民")

# 考试时可以选的新职业（初级 + 中级，不含要坐骑的；上级要 Lv35 和名声 8，先不放）
PHYSICAL = ["斗士", "士兵", "猎兵", "剑客", "弓箭手", "恶棍", "重装步兵", "土匪", "斗拳手"]
# 11-11 Yizhuo：不需要「坐骑类职业只给骑乘角色」的限制 → 骑兵 / 飞行职业所有物理角色都可以考
MOUNTED = ["飞鸵兵", "轻骑兵", "战车兵", "骑甲鸵兵", "天翼兵"]
PHYSICAL = PHYSICAL + MOUNTED
MAGIC = ["诅咒师", "萨满巫师", "牧师"]
# 11-11 Yizhuo：所有角色用同一套逻辑 → 每个人都考虑全部初级 + 中级职业（考不考得过由技能/等级/种子决定），只保留 Yizhuo 明确说的个人排除。
ALL_CLASSES = PHYSICAL + MAGIC
EXCLUDE = {"迪托利希": ["重装步兵"],   # 11-11 Yizhuo：迪不需要重装步兵
           "奇洛伊卡": ["牧师"],       # 11-16 Yizhuo：奇洛不考牧师
           "杨界": ["战车兵"]}         # 11-16 Yizhuo：杨界不考战车兵（练技能不划算）
_SEX = {c["name"]: c.get("sex") for c in json.load(open(os.path.join(HERE, "fw_characters.json"), encoding="utf-8"))}
_CLASS_LIMIT = {c["name"]: c.get("limit") for c in json.load(open(os.path.join(HERE, "fw_classes.json"), encoding="utf-8"))}
# 11-16 Yizhuo：没用的能力不该决定考什么（米迦曾因魔力被排去萨满）→ 魔力权重 ≤ 1 的角色不考法系职业
MAGIC_MIN_WEIGHT = 2


def _allowed(name, cls):
    if cls in EXCLUDE.get(name, []):
        return False
    if _CLASS_LIMIT.get(cls) == "女性" and _SEX.get(name) != "女":   # 11-16：天翼兵女性限定
        return False
    if cls in MAGIC and W[name][2] < MAGIC_MIN_WEIGHT:
        return False
    return True


EXAM_OPTIONS = {n: [c for c in ALL_CLASSES if _allowed(n, c)]
                for n in ["迪托利希", "米迦艾拉", "努蒂奴", "法毕欧", "杨界", "乌尔坦德", "艾丝梅拉尔达", "伊欧", "奇洛伊卡"]}

# 一定要考到的职业（拿精通技能等）
# 11-11 Yizhuo：取消米迦重装必考（原 11-08 重装优先于土匪）；11-25 Yizhuo：艾丝走天翼兵+重装步兵（重开章节后，不练格斗）
REQUIRED = {"迪托利希": ["恶棍"], "法毕欧": ["萨满巫师"], "艾丝梅拉尔达": ["天翼兵", "重装步兵"]}
# 11-25 Yizhuo：伊欧路线上如果要跳过，就用「考战车兵」来跳（能考过时），保证有这个职业；没跳过就不考
SKIP_TAKE = {"伊欧": ["战车兵"]}
# 想多用的职业：每用它升一级 +x 虚拟分（同分或差一点时优先用它，方便练兵种精通）
PREFER = {}

# 备份的 startLevel 是「第 1 条记录升完之后」的等级（11-05 截图对过：奇洛、法毕欧、努蒂奴、杨界、米迦的加点完全对上），
# 所以记录 i 是 (Lv-1)→Lv。主表「成长记录」的等级也是「升完之后」的等级。只影响等级标签，不影响种子。
LEVEL_FIX = {"迪托利希": -1, "法毕欧": -1, "杨界": -1, "米迦艾拉": -1, "努蒂奴": -1, "乌尔坦德": 0,
             "艾丝梅拉尔达": -1, "伊欧": -1, "奇洛伊卡": -1}


# 备份最后一条记录之后、实际已经做了但备份里没有的步（主表有）：迪的「25 great」没记加点，
# 11-01→11-05 截图的能力差正好等于种子算出的这一级（HP 力 速 防 魔防 幸 魅）。
EXTRA_AFTER = {"迪托利希": [{"ok": True, "cls": "剑客", "note": "主表「25 great」：备份里没有，加点按种子推算（和截图能力差对上）"}]}


# 备份和主表对不上、按主表改的记录：角色 -> {第几条: 改哪些字段}
RECORD_FIX = {"伊欧": {2: {"ok": True}},   # 主表：Lv23「ok 速 技 防 魔防 幸」是升了的，备份标成了跳过
              "奇洛伊卡": {10: {"gains": [0, 4]}, 11: {"drop": True}, 12: {"drop": True}}}
# 奇洛：备份第 10 条（✗）= 主表「21 bad HP 技」；第 11、12 条没加点、主表也没有，去掉


# 截图等级之后的观星记录只是预览、还没做 → 从截图等级重新规划（这些记录不算已做）。
# Yizhuo 11-07：杨界 Lv21→22 用平民更好，说明截图之后的记录还没升。
REPLAN_FROM_SHOT = {"杨界", "奇洛伊卡", "努蒂奴", "法毕欧", "伊欧", "艾丝梅拉尔达", "乌尔坦德"}   # 11-08 兵种截图：所有人都还在截图等级


# Yizhuo 11-08：乌 没有跳过，但下一次升级到 Lv19 的加点（力 魔 速 技 防 幸）是对的 → 记录 4（✗）那个种子已经用掉了
KEEP_AFTER_SHOT = {"乌尔坦德": 1}


# 11-25 Yizhuo 重开章节：当前状态 = 重开后的部队表截图（current_stats.json 的 shot_1125）。
# seed_index = 从 demo.KNOWN_SEEDS 的种子起已经用掉几步（升级、考试都算），由重开后的 30 张观星升级截图逐条对上得出（checks.py S1 会复核）。
SHOT_KEY = "shot_1125"


def shot(name):
    """角色当前的截图快照（等级、职业、能力、技能、seed_index）。全项目只从这里取，别直接写 shot_xxxx。"""
    c = CURRENT.get(name, {})
    return c.get(SHOT_KEY) or c.get("shot_1105") or {}


def _cut(name):
    """快照里写了 seed_index 时，记录只保留种子位置在它之前的。"""
    return shot(name).get("seed_index")


def _draws(name):
    out, kept = [], 0
    shot = (CURRENT.get(name, {}).get("shot_1105") or {}).get("level") if name in REPLAN_FROM_SHOT else None
    level = units[name]["startLevel"] + LEVEL_FIX.get(name, 0)
    for idx, d in enumerate(units[name]["draws"], start=1):
        fix = RECORD_FIX.get(name, {}).get(idx, {})
        if fix.get("drop"):
            continue
        d = {**d, **fix}
        if shot is not None and level >= shot:
            if kept < KEEP_AFTER_SHOT.get(name, 0) and not d["ok"]:
                kept += 1          # 截图之后、已经用掉的那一个种子（没升级）
                out.append(d)
                continue
            break
        out.append(d)
        level += d["ok"]
    return out


def current_state(name):
    """备份里最后一条记录之后的种子和等级（✓=升级，✗=考试，都推进一步）。
    快照有 seed_index（11-25 重开后）时：种子 = 已知种子往后走 seed_index 步，等级 = 截图等级。"""
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
        # 截断处如果有没记下的考试步（之后的职业已经到手），那一步已经做了
        for _ in range(demo.HIDDEN_STEPS.get(name, {}).get(n + 1, 0)):
            seed = next_seed(seed)
    for ex in EXTRA_AFTER.get(name, []):
        seed = next_seed(seed)
        level += ex["ok"]
    return seed, level + LEVEL_FIX.get(name, 0)


# 当前能力估算（11-01 截图 + 之后记录的加点），用于成长均衡
CURRENT = json.load(open(os.path.join(HERE, "current_stats.json"), encoding="utf-8"))


def records(name):
    """备份里的观星记录，逐条：dict(idx, seed（推不出时 None）, ok, cls, frm, to, gains[9])。
    记录之间没记下的种子步（HIDDEN_STEPS）也作为 ok=None 的一条返回。"""
    unit = units[name]
    seed, first = demo.KNOWN_SEEDS.get(name, (None, 1))
    level = unit["startLevel"] + LEVEL_FIX.get(name, 0)   # 第 1 条记录升级前的等级
    out = []
    cut, pos = _cut(name), 0
    if cut is not None:
        # 11-25：按种子位置截断（已知种子之前的记录没有种子，照常保留）
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
            out.append(dict(idx=idx, seed=cur, ok=bool(draw["ok"]), cls=data.class_ids[str(draw["cls"])],
                            frm=level, to=level + 1 if draw["ok"] else None, gains=g))
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
        out.append(dict(idx=idx, seed=cur, ok=bool(draw["ok"]), cls=data.class_ids[str(draw["cls"])],
                        frm=level, to=level + 1 if draw["ok"] else None, gains=g))
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
        out.append(dict(idx=f"x{j}", seed=seed, ok=ex["ok"], cls=ex["cls"], frm=level,
                        to=level + 1 if ex["ok"] else None, gains=g, note=ex["note"], inferred=True))
        if seed is not None:
            seed = next_seed(seed)
        level += ex["ok"]
    return out


def start_stats(name):
    """规划起点（最后一条记录之后）的能力：11-05 截图 + 还没升的记录加点。"""
    sh = shot(name)
    if not sh:
        return CURRENT.get(name, {}).get("stats")
    st = list(sh["stats"])
    for r in records(name) if name in units and _cut(name) is None else []:   # 有 seed_index 时记录都在截图之前
        if r["ok"] and r["to"] > sh["level"]:
            st = [a + b for a, b in zip(st, r["gains"])]
    return st


_CLASSES = {c["name"]: c for c in json.load(open(os.path.join(HERE, "fw_classes.json"), encoding="utf-8"))}
_KEYS = ["hp", "str", "mag", "spd", "dex", "def", "res", "lck", "cha"]
# 11-16：职业最低能力（保底），来源 Yuphas Temple（fw_classes.json 的 minStats）。考进新职业时，裸能力低于保底的项补到保底。
FLOORS = {n: [(c.get("minStats") or {}).get(k, 0) for k in _KEYS] for n, c in _CLASSES.items()}


def class_bonus(cls):
    b = (_CLASSES.get(cls) or {}).get("baseStats") or {}
    return [b.get(k, 0) for k in _KEYS]


# 截图里不属于职业加成的额外加成（特技、坐骑等），算裸能力时要减掉
BOOST = {
    "迪托利希": ([0, 1, 0, 0, 5, 0, 0, 0, 0], "力+1 攻击的基本；技+5 披风（Lv25 截图 9 项和种子推算全对上，已证实）"),
    "法毕欧": ([0, 0, 1, 0, 0, 0, 1, 0, 0], "魔+1 魔防+1 魔道的基本（估计）"),
    "杨界": ([0, 0, 1, 0, 0, 0, 1, 0, 0], "魔+1 魔防+1 魔道的基本（估计）"),
    "米迦艾拉": ([0, 1, 0, 0, 0, 1, 0, 0, 0], "力+1 攻击的基本、防+1 防卫的基本（估计）"),
    "伊欧": ([3, 0, 0, 1, 2, 2, 0, 0, 0], "HP+3 体力强化；速+1 技+2 防+2 罗西南 4 级属性（估计）"),
    "艾丝梅拉尔达": ([0, 1, 1, 0, 0, 0, 0, 0, 0], "力+1 魔+1 攻势的基本（估计）"),
}


def raw_start(name):
    """规划起点的裸能力（截图 − 当前职业加成 − 额外加成 + 截图后的记录加点），保底和它比。"""
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
    import re
    m = re.search(r"名声 ?Lv(\d+)", (_CLASSES.get(cls) or {}).get("requirement") or "")
    return int(m.group(1)) if m else None


# 游戏里考试画面显示的成功率（%），按角色、职业填。考试成败由种子决定（模拟器 Ver1.1）。
_ec = os.path.join(HERE, "exam_chance.json")
EXAM_CHANCE = {k: v for k, v in json.load(open(_ec, encoding="utf-8")).items() if not k.startswith("说明")} if os.path.exists(_ec) else {}


# 预测 100% 的考试（技能、等级都够）：判定值再高也按能过算
CONFIDENT = {"法毕欧": ["牧师"]}
# 同分时优先的职业（Yizhuo 11-06：奇洛本职是弓，和剑客一样时用弓箭手或恶棍）
TIEBREAK = {"奇洛伊卡": ["弓箭手", "恶棍"]}


RANKS = ["E", "E+", "D", "D+", "C", "C+", "B", "B+", "A", "A+", "S", "S+"]
_CLS_REQ = {c["name"]: c.get("requirement") or "" for c in json.load(open(os.path.join(HERE, "fw_classes.json"), encoding="utf-8"))}


def exam_req(name, cls):
    """(推荐等级, 技能差几段)。技能用 11-05 截图；截图里没有的（重装/马术/飞行/步兵术）：要求 E+ 及以下当够，更高当差 1 段。"""
    import re
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


# 11-11 Yizhuo：考试技能不够时，可以提前训练到够再考 → 规划时技能差当 0（只看等级），路线里写出要先练什么。
TRAIN_TO_PASS = True


def train_need(name, cls):
    """考 cls 之前要练的技能，如 ['箭术 D→C']；技能截图没有的项写「（截图没有，按差 1 段）」。"""
    import re
    text = _CLS_REQ.get(cls, "")
    skills = shot(name).get("skills", {})
    out = []
    for part in text.split("·"):
        part = part.strip()
        pairs = re.findall(r"(\S+术) ([EDCBAS]\+?)", part)
        def short(sk, rk):
            need = RANKS.index(rk)
            if sk not in skills:
                return None if need <= 1 else f"{sk} →{rk}（截图没有这项）"
            return f"{sk} {skills[sk]}→{rk}" if RANKS.index(skills[sk]) < need else None
        if part.startswith("主要"):
            out += [x for a, b in pairs if (x := short(a, b))]
        elif part.startswith("任选其一") and pairs:
            opts = [short(a, b) for a, b in pairs]
            if all(opts):
                out.append(min(opts, key=len) + "（任选一项）")
    return out


# Yizhuo 11-07：P0 角色照常；其他角色多考/跳过的门槛提高，省资源（中级, 初级/纯跳过）
P0 = {"迪托利希", "艾丝梅拉尔达", "米迦艾拉", "伊欧"}   # 11-08 加奇洛；11-09 Yizhuo：奇洛改 P1；11-23 Yizhuo：法毕欧改 P1
# Yizhuo 11-08 晚：门槛统一按手形金币算。初级 300G、中级 500G（跳过也按初级手形）；上级 3000G（游戏价，待确认）。
# 每个优先级「1 加权分值多少金币」：P0 中级 500G = 8 分 → 62.5G/分；P1 = 12 分 → 41.7G/分；P2 = 16 分 → 31.25G/分。
PERMIT_GOLD = {"初级": 300, "中级": 500, "上级": 3000, "高级": 3000}
GOLD_PER_PT = {"P0": 500 / 8, "other": 500 / 12, "P2": 500 / 16}
THRESHOLDS = {k: (round(500 / v, 1), round(300 / v, 1)) for k, v in GOLD_PER_PT.items()}   # 只用来显示
P2_SKIP_BELOW = 6   # Yizhuo 11-08：P2 只有这一级升级不到 6 分才跳过（初级/跳过不另设门槛，只要有赚）
P2 = {"努蒂奴", "乌尔坦德"}   # 11-08 乌也是 P2；杨界 = P1（其他人，12/6）   # Yizhuo 11-08：努蒂奴是 P2，门槛再提高一档（中级 16、初级/跳过 8）

# 与主表「成长记录」的角色顺序一致（全项目共用，别处不要再写一份）
ORDER = ["迪托利希", "法毕欧", "艾丝梅拉尔达", "米迦艾拉", "杨界", "伊欧", "奇洛伊卡", "努蒂奴", "乌尔坦德"]
# 11-16 Yizhuo：规划到 Lv35 或「当前 +15 级」里更远的那个（至少覆盖未来 15 级）。Lv45 由 plan45 另算。
HORIZON_MIN_LEVEL, HORIZON_MIN_STEPS = 35, 15
TARGET = {n: max(HORIZON_MIN_LEVEL, current_state(n)[1] + HORIZON_MIN_STEPS) for n in ORDER}
# 11-16 Yizhuo：练技能要花时间。按档位：P0 可以为考试练技能（每段扣分）；P1/P2 不练，只考技能已经够的职业（按实际成功率）
TRAIN_ALLOWED = {"P0": True, "P1": False, "P2": False}
TRAIN_PTS = {"P0": 0.5, "P1": 2.0, "P2": 3.0}   # 每段训练扣的加权分（P1/P2 只在开关打开时用）
# 11-16：单独加一场考试，净值至少多这么多分才考（米迦战车兵 +0.8 那种不考）
MIN_EXAM_GAIN = 2.0
# 11-16：玩家当前名声等级（游戏里「名声 Lv」）。None = 没录入，考试只提示要求不判断
RENOWN = 6   # 11-16 Yizhuo：名声 Lv6
MAX_EXAMS = 4


def tier_of(name):
    """优先级标签：P0 / P1 / P2（页面、检查都用这一个函数，别在别处再写一遍名单）。"""
    return "P0" if name in P0 else "P2" if name in P2 else "P1"


SKIP_RULE = {"P0": {"cap": 8, "pct": 0.35, "or": True}, "other": {"cap": 8, "pct": 0.50, "or": False},
             "P2": {"cap": 6, "pct": 0.60, "or": False}}
NO_SKIP_SEEDS = {"迪托利希": {2066637942, 1518001801},
                 "伊欧": {246621131}}   # 11-25 Yizhuo：伊欧 Lv23 这个种子（轻骑兵 速 技 魔防）用来升级，不拿来考试（魔防+1 魅+1，HP 魔 幸 各−1）
#   # 11-11 Yizhuo：迪 Lv25 那级（力 技 幸 魅）也保留   # 11-09 Yizhuo：迪 Lv31 那个种子（魔 防 魔防 幸 魅）保留不跳（按种子记，不按等级）


EQUAL_SEEDS = True


def _TIER_RANK_OF(c):
    from planner import _TIER, _TIER_RANK
    return _TIER_RANK.get(_TIER.get(c, ""), 0)


def make_planner(name, target=None):
    seed, level = current_state(name)
    p = _mk(name, seed, level, target)
    p.confident = set(CONFIDENT.get(name, []))
    # 11-17 Yizhuo：所有角色都要考到中级职业（上级不一定）。已经有中级职业的人算满足（迪 剑客、艾丝 天翼兵、伊欧 战车兵/轻骑兵）
    p.require_mid = not any(_TIER_RANK_OF(c) >= 2 for c in OWNED[name])
    p.equal_seeds = EQUAL_SEEDS   # 11-17 Yizhuo：比较按用掉同样多的乱数
    tier = "P0" if name in P0 else "P2" if name in P2 else "other"
    p.thresholds = THRESHOLDS[tier]
    p.gold_per_pt, p.permit_gold = GOLD_PER_PT[tier], dict(PERMIT_GOLD)
    # 11-08 晚（Yizhuo）：规则式规划。跳过阈值 = 300G ÷ 每分金币（P0 4.8、P1 7.2）；P2 用 Yizhuo 定的 6 分
    p.rule_based = True
    p.skip_threshold = P2_SKIP_BELOW if name in P2 else PERMIT_GOLD["初级"] / GOLD_PER_PT[tier]
    # 11-09 Yizhuo（讨论稿评论）：P0 ≤8 分或比未来 15 级平均低 ≥35%；P1 ≤8 分且低 ≥50%；P2 ≤6 分且低 ≥60%
    p.skip_rule = SKIP_RULE[tier]
    p.no_skip_seeds = NO_SKIP_SEEDS.get(name, set())
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
    # 11-16：跳过用的初级考试池（不受个人排除/法系限制，只看性别），按真实技能估成功率
    p.skip_pool = [c for c, x in _CLASSES.items() if x.get("tier") == "初级"
                   and not (x.get("limit") == "女性" and _SEX.get(name) != "女")]
    p.skip_req = {c: q for c in p.skip_pool if (q := exam_req(name, c))}
    p.exam_train = {c: t for c in p.exam_req if (t := train_need(name, c))}   # 要练什么（不练的档位也列出来，页面提示）
    if TRAIN_TO_PASS and TRAIN_ALLOWED[tier_of(name)]:
        # 技能差当 0（提前训练）；游戏里记下的低成功率也是练之前的数，同样不再用
        p.exam_train = {c: t for c in p.exam_req if (t := train_need(name, c))}
        p.exam_train_ranks = {c: r[1] for c, r in p.exam_req.items() if r[1] > 0}   # 要练几段（训练成本按段算）
        p.exam_req = {c: (r[0], 0) for c, r in p.exam_req.items()}
        p.exam_chance = {c: v for c, v in (p.exam_chance or {}).items() if c not in p.exam_train}
    # 不练技能的档位：考不过任何中级时，只为这个中级破例练（planner.rule_plan 用）
    p.mid_train = {}
    if p.require_mid and not TRAIN_ALLOWED[tier_of(name)]:
        p.mid_train = {c: (r[0], r[1]) for c, r in p.exam_req.items()
                       if _TIER_RANK_OF(c) == 2 and r[1] > 0}
    tb = TIEBREAK.get(name, [])
    if tb:
        p.tiebreak = list(tb)
        # 考试也按这个顺序：同分时先考优先的职业
        p.exam_options = tuple(sorted(p.exam_options, key=lambda c: tb.index(c) if c in tb else len(tb)))
    return p


def _mk(name, seed, level, target):
    p = Planner(data, name, seed, level, target or level + 10,
                   OWNED[name], EXAM_OPTIONS[name], W[name], required=REQUIRED.get(name, []), prefer=PREFER.get(name),
                   stats=start_stats(name), exam_chance=EXAM_CHANCE.get(name))
    p.skip_take = tuple(SKIP_TAKE.get(name, ()))
    return p


def print_plan(limit, plan):
    print(f"\n最多考 {limit} 次（实际考 {plan.exams} 次）：总分 {plan.total}")
    for r in plan.rows:
        if r.action == "升级":
            print(f"  步{r.step + 1:>2}  Lv{r.level_from}→{r.level_from + 1}  升级 {r.cls:4}"
                  f" {gains_text(r.gains):24} {r.score:>3}  | {r.compare}")
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
