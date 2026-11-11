"""第七章开始重开规划：以 11-07 上传的第 7 章开始部队表截图为起点（等级、能力），种子取观星记录里对应等级的位置。
输出 ch7.json：每人 新规划 vs 实际已走+现规划（同一起点到 Lv35）。"""
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))  # 一次性脚本放在 tools/，数据和模块在上一层
_os.chdir(_sys.path[0])
import json, os, sys
import run_plans as R
from planner import Planner, plan_all, gains_text, score
from fe_growth import STATS

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# 第 7 章开始（截图，显示值，顺序 HP 力 魔 速 技 防 魔防 幸 魅）
CH7 = {
    "迪托利希": (20, "剑客", [36, 23, 14, 24, 27, 13, 6, 19, 24]),
    "伊欧": (22, "轻骑兵", [37, 18, 7, 12, 18, 22, 8, 14, 13]),
    "杨界": (17, "诅咒师", [33, 11, 18, 13, 12, 10, 17, 11, 8]),
    "米迦艾拉": (16, "士兵", [36, 23, 8, 13, 13, 10, 7, 12, 15]),
    "奇洛伊卡": (12, "猎兵", [32, 11, 5, 17, 15, 8, 6, 9, 5]),
    "法毕欧": (15, "诅咒师", [31, 7, 25, 12, 15, 8, 16, 11, 10]),
    "艾丝梅拉尔达": (15, "飞鸵兵", [36, 18, 7, 15, 13, 16, 7, 15, 11]),
}
# 第 7 章时已有的职业（之后考到的不算）
OWN7 = {
    "迪托利希": ["剑客", "斗士", "猎兵", "平民"],
    "伊欧": ["轻骑兵", "平民"],
    "杨界": ["诅咒师", "平民"],
    "米迦艾拉": ["斗士", "士兵", "平民"],
    "奇洛伊卡": ["猎兵", "平民"],
    "法毕欧": ["诅咒师", "平民"],
    "艾丝梅拉尔达": ["飞鸵兵", "平民"],
}
# 第 7 章开始在记录里的位置：该等级的隐藏步（考试）算在第 7 章之前还是之后
#   after_hidden=True：截图里的职业是那次考试考到的（迪 剑客、米迦 士兵）
AFTER_HIDDEN = {"迪托利希": True, "米迦艾拉": True}

def start_index(name, lv, after_hidden):
    rs = R.records(name)
    for i, r in enumerate(rs):
        if r["frm"] == lv and (r["ok"] is not None or not after_hidden):
            return i, rs
    raise ValueError(name)

out = {}
for name, (lv, cls, st) in CH7.items():
    i, rs = start_index(name, lv, AFTER_HIDDEN.get(name, False))
    seed = rs[i]["seed"]
    w = R.W[name]
    # 实际已走（第 7 章 → 现在的记录）+ 现在的 Lv35 规划
    old_g, old_rows = [0] * 9, []
    for r in rs[i:]:
        if r["ok"]:
            old_g = [a + b for a, b in zip(old_g, r["gains"])]
            old_rows.append({"lv": r["frm"], "act": "升级", "cls": r["cls"], "g": r["gains"], "src": "已走"})
        else:
            old_rows.append({"lv": r["frm"], "act": "考试/跳过", "cls": r["cls"] if r["ok"] is False else "", "g": [0] * 9, "src": "已走"})
    p0 = R.make_planner(name, 35); pl0, k0 = plan_all(p0, 4); plan0 = pl0[k0]
    for r in plan0.rows:
        if r.action == "升级":
            old_g = [a + b for a, b in zip(old_g, r.gains)]
            old_rows.append({"lv": r.level_from, "act": "升级", "cls": r.cls, "g": list(r.gains), "src": "规划"})
        else:
            old_rows.append({"lv": None, "act": "考试", "cls": r.cls, "g": [0] * 9, "src": "规划"})
    # 新规划
    opts = list(dict.fromkeys(list(R.EXAM_OPTIONS[name]) + [c for c in R.OWNED[name] if c not in OWN7[name]]))
    p = Planner(R.data, name, seed, lv, 35, OWN7[name], opts, w,
                required=R.REQUIRED.get(name, []), stats=st, exam_chance=R.EXAM_CHANCE.get(name))
    p.confident = set(R.CONFIDENT.get(name, [])) | {c for c in R.OWNED[name] if c not in OWN7[name]}   # 实际考到过的职业：技能够
    p.exam_req = {c: q for c in opts if (q := R.exam_req(name, c))}
    p.tiebreak = list(R.TIEBREAK.get(name, []))
    p.require_mid = True
    p.thresholds = R.THRESHOLDS["P0" if name in R.P0 else "other"]
    pls, k = plan_all(p, 7)
    plan = pls[k]
    new_g, new_rows = [0] * 9, []
    for r in plan.rows:
        if r.action == "升级":
            new_g = [a + b for a, b in zip(new_g, r.gains)]
            new_rows.append({"lv": r.level_from, "act": "升级", "cls": r.cls, "g": list(r.gains), "sc": r.score, "bal": getattr(r, "balance_note", "")})
        else:
            new_rows.append({"lv": None, "act": "考试", "cls": r.cls, "roll": round(p.exam_value(r.step), 2),
                             "pct": p.exam_pct(r.cls, p.level + sum(1 for x in plan.rows[:r.step] if x.action == "升级")) if r.cls != "跳过" else None})
    # 填考试所在等级
    cur = lv
    for x in new_rows:
        if x["act"] == "考试":
            x["lv"] = cur
        else:
            cur += 1
    cur = None
    cross = lambda g: 3 * ((st[1] + g[1]) // 5 - st[1] // 5)   # 体格阈值加分（同 planner.STR_BONUS）
    out[name] = {"lv": lv, "cls": cls, "stats": st, "w": w, "seed": seed, "pos": i,
                 "old": {"g": old_g, "pts": sum(old_g), "sc": score(old_g, w) + cross(old_g), "str": cross(old_g), "rows": old_rows},
                 "new": {"g": new_g, "pts": sum(new_g), "sc": score(new_g, w) + cross(new_g), "str": cross(new_g), "rows": new_rows, "exams": plan.exams,
                         "budgets": [q.total if q else None for q in pls]},
                 "own": OWN7[name], "after_hidden": AFTER_HIDDEN.get(name, False)}
    d = [a - b for a, b in zip(new_g, old_g)]
    print(f"{name} Lv{lv} {cls} pos{i}: 旧 {sum(old_g)}点/{score(old_g, w) + cross(old_g)}  新 {sum(new_g)}点/{score(new_g, w) + cross(new_g)}  差 {sum(d):+} 点 {score(new_g, w) + cross(new_g) - score(old_g, w) - cross(old_g):+} 分  {gains_text(d) if any(d) else ''}")
    print("    新:", " ".join((f"{x['lv']}{x['cls']}" if x['act'] == '升级' else f"[考{x['cls']}@{x['lv']} {x.get('roll')}]") for x in new_rows))
json.dump(out, open(os.path.join(HERE, "ch7.json"), "w", encoding="utf-8"), ensure_ascii=False)
