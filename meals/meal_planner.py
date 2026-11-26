"""吃饭规划入口（薄封装：核心纯逻辑已拆分至 modules/affinity/planner.py）。

用法：python3 meal_planner.py [--config meal_config.json]  → 打印表格，写 meal_plan.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from modules.affinity.planner import (  # noqa: E402
    SPK,
    compute_pair_weights,
    fmt_table as fmt,
    is_perfect,
    load_people,
    plan_meals,
    sparkle,
    table_score,
)


def pair_weights(people, cfg):
    """兼容旧接口：核心代码请使用无副作用的 modules.affinity.planner.compute_pair_weights。"""
    w, need = compute_pair_weights(people, cfg)
    pair_weights.need = need
    return w


def plan(cfg, tab_path=os.path.join(HERE, "diet_tab.json")):
    return plan_meals(cfg, tab_path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=os.path.join(HERE, "meal_config.json"))
    ap.add_argument("--out", default=os.path.join(HERE, "meal_plan.json"))
    a = ap.parse_args()
    with open(a.config, encoding="utf-8") as f:
        cfg = json.load(f)
    p = plan(cfg)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(p, f, ensure_ascii=False, indent=1)
    for r in p["dishes"]:
        print(f"{r['dish']}：" + ("；".join(fmt(t) for t in r["options"]) or "没有能用的组合"))
    print("目标：", "、".join(f"{x['lord']}–{x['target']}(分{x['score']}，要支援{x['support']})" for x in p["weights"]))
    lv2 = [x for x in p["weights"] if x["support"] == 2 and x["lord"] == cfg.get("current_lord")]
    print("主角线支援 2 就能招：", "、".join(x["target"] for x in lv2) or "没有")


if __name__ == "__main__":
    main()
