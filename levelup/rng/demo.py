"""
用反推出的种子回测 Yizhuo 的观星记录，并往后推演。

运行：
    python3 demo.py                 # 回测 + 推演（使用下面已反推好的种子）
    python3 demo.py --solve 努蒂奴  # 从头反推某个角色的种子（numpy，约几分钟）

观星记录来自 ../观星凹点模拟备份-导入.json（fireemblem.top/levelup 导出的备份）。
备份里每一条记录（不论「满意=升级」还是「不满意=考试跳过」）都对应种子的一步。
"""

from __future__ import annotations

import json
import os
import sys

from fe_growth import STATS, GrowthData, Step, forecast, level_up, next_seed

HERE = os.path.dirname(os.path.abspath(__file__))
BACKUP = os.path.join(HERE, "..", "观星凹点模拟备份-导入.json")
ROUTE = "迪托利希篇"
MIN_STATS = 2          # 第一、二部保底 2 项

# 已反推出的种子：角色 -> (种子, 这个种子对应第几条记录, 从 1 数)
KNOWN_SEEDS = {
    "努蒂奴":   (1060419758, 1),
    "乌尔坦德": (325626779, 1),
    "法毕欧":   (1555121991, 1),
    "杨界":     (559608179, 3),   # 第 3 条对不上，从第 4 条起全对（见说明）
    "米迦艾拉": (1696380973, 1),
    "迪托利希": (1320706839, 1),  # 用主表 21～24 级（含同级斗士/剑客两次观星）反推，再往前接
    # 11-05 晚：C 暴力搜索（csolve/brute.c）找到一段连续记录的唯一种子，再用 csolve/chain.py 往回接
    "艾丝梅拉尔达": (472547300, 1),   # 17～21 级唯一；往回接到第 1 条（第 3 条差 1 项）
    "奇洛伊卡": (1171680555, 1),       # 16～21 级唯一；第 1 条差 1 项（防/魔防），第 3 条差 1 项（技/防）
    "伊欧": (1759145251, 1),           # 原表 4 条（含被转战车兵考试吃掉的「24 轻骑兵 bad」）唯一
}

# 记录之间夹了没记下来的种子步（多半是没记的考试）：角色 -> {第几条记录: 之前多走几步}
HIDDEN_STEPS = {
    "米迦艾拉": {5: 1, 6: 1},
    "迪托利希": {2: 1, 4: 1, 5: 1},
    "艾丝梅拉尔达": {3: 1, 8: 1, 13: 1},   # 第 3 条前一步没记；转斗士、转天翼兵的考试
    "奇洛伊卡": {2: 1},                     # 第 1、2 条之间多一步
    "伊欧": {3: 1},                         # 「24 轻骑兵 bad」被转战车兵的考试吃掉
}

# 推演时想比较的职业（只算成长率，不检查能否转入）
COMPARE_CLASSES = {
    "努蒂奴": ["飞鸵兵", "天翼兵", "骑甲鸵兵"],
    "乌尔坦德": ["诅咒师", "萨满巫师", "牧师"],
    "法毕欧": ["诅咒师", "萨满巫师", "先知"],
    "杨界": ["诅咒师", "牧师", "萨满巫师"],
    "米迦艾拉": ["斗士", "士兵", "土匪"],
    "迪托利希": ["剑客", "侍道", "刀剑将领"],
}


def load_units():
    with open(BACKUP, encoding="utf-8") as f:
        return json.load(f)["saves"][ROUTE]["units"]


def fmt(gains):
    return " ".join(STATS[i] for i, g in enumerate(gains) if g) or "—"


def backtest(data: GrowthData, name: str, unit: dict, seed: int, first: int):
    print(f"\n=== {name}  （种子 {seed}，从第 {first} 条记录起）")
    print(f"{'#':>3}  {'动作':4} {'职业':6} {'观星记录':22} {'公式算出':22} 结果")
    level = unit["startLevel"]
    hit = total = 0
    for idx, draw in enumerate(unit["draws"], start=1):
        cls = data.class_ids[str(draw["cls"])]
        for _ in range(HIDDEN_STEPS.get(name, {}).get(idx, 0)):
            seed = next_seed(seed)
            print(f"{'':>3}  （这里多走了一步种子：没记录的考试或升级）")
        if idx >= first:
            growth = data.growth(name, cls, level)
            pred = level_up(seed, growth, MIN_STATS).gains
            recorded = [1 if i in draw["gains"] else 0 for i in range(9)]
            if draw["gains"]:
                same = [1 if g else 0 for g in pred] == recorded
                total += 1
                hit += same
                verdict = "✓" if same else "✗ 不同"
            else:
                verdict = "（没记录）"
            print(f"{idx:>3}  {'升级' if draw['ok'] else '考试':4} {cls:6} "
                  f"{fmt(recorded) if draw['gains'] else '':22} {fmt(pred):22} {verdict}")
            seed = next_seed(seed)
        if draw["ok"]:
            level += 1
    print(f"  命中 {hit}/{total}")
    return seed, level


def show_forecast(data: GrowthData, name: str, seed: int, level: int, n: int = 5):
    print(f"  —— 记录之后再升 {n} 级（从 Lv{level} 起，不考试）——")
    for cls in COMPARE_CLASSES.get(name, []):
        steps = [Step(data.growth(name, cls, level + k)) for k in range(n)]
        rows = forecast(seed, steps, MIN_STATS)
        total = sum(sum(r.gains) for _, r in rows)
        line = " | ".join(r.names() for _, r in rows)
        print(f"  {cls:6} 共+{total:<2}  {line}")


def main():
    data = GrowthData(os.path.join(HERE, "growth_data.json"))
    units = load_units()

    if len(sys.argv) >= 3 and sys.argv[1] == "--solve":
        from solve import solve
        name = sys.argv[2]
        unit = units[name]
        records = []
        level = unit["startLevel"]
        for draw in unit["draws"]:
            cls = data.class_ids[str(draw["cls"])]
            gains = [1 if i in draw["gains"] else 0 for i in range(9)] if draw["gains"] else None
            records.append((data.growth(name, cls, level), gains))
            level += draw["ok"]
        print(f"反推 {name}：{len(records)} 条记录")
        for seed, miss in solve(records[:8], MIN_STATS):
            print(f"  种子 {seed}  对不上 {miss} 项")
        return

    for name, (seed, first) in KNOWN_SEEDS.items():
        end_seed, level = backtest(data, name, units[name], seed, first)
        show_forecast(data, name, end_seed, level)


if __name__ == "__main__":
    main()
