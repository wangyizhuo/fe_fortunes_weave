"""把种子、各角色路线整理成表格行（写入主表「种子」「成长路线」用），存为 sheet_rows.json。"""
import json

import demo
from fe_growth import STATS
from planner import gains_text, plan_all
from run_plans import (OWNED, EXAM_OPTIONS, REQUIRED, EXAM_CHANCE, current_state, make_planner,
                       ORDER, TARGET, MAX_EXAMS)  # noqa: F401  ORDER/TARGET/MAX_EXAMS 在这里再导出，兼容旧代码

BACKTEST = {"努蒂奴": "7/7", "乌尔坦德": "6/6", "法毕欧": "13/15", "杨界": "10/11",
            "米迦艾拉": "11/12", "迪托利希": "7/8",
            "艾丝梅拉尔达": "13/14", "奇洛伊卡": "7/9", "伊欧": "3/3"}
NOTES = {
    "迪托利希": "17级后、19级后、20级后各多一步（没记的考试）；23级转剑客没推进种子",
    "米迦艾拉": "第4、5条记录后各多一步（没记的考试或升级）",
    "杨界": "种子对应第3条记录；第1～2条接不上",
}

def main():
    seed_rows = [["角色", "当前等级", "当前种子（下一级用）", "备份第1条记录的种子", "回测命中", "说明", "更新"]]
    route_rows = [["角色", "步", "等级", "动作", "职业", "已有职业（这一步之后）", *STATS, "加权分", "这一步各职业得分", "建议", "换职业会涨不同项（分低也列，供参考）"]]

    for name in [n for n in ORDER if n in demo.KNOWN_SEEDS]:
        seed, level = current_state(name)
        s0, first = demo.KNOWN_SEEDS[name]
        seed_rows.append([name, level, seed, s0 if first == 1 else f"{s0}（第{first}条）",
                          BACKTEST[name], NOTES.get(name, ""), "2026-11-05"])

        p = make_planner(name, TARGET[name])
        plans, k = plan_all(p, MAX_EXAMS)
        plan = plans[k]
        route_rows.append([f"{name}  Lv{p.level}→{p.level + p.n_levels}", "", "", "", "",
                           "、".join(OWNED[name]), *[""] * 9, "",
                           "考试上限→总分：" + "  ".join(f"{i}次 {pl.total if pl and pl.rows else '不可行'}" for i, pl in enumerate(plans)),
                           (f"必考：{'、'.join(REQUIRED[name])}（练精通，同分时优先用它升级）；" if name in REQUIRED else "") + f"建议考 {plan.exams} 次" + (f"（比不考多 {plan.total - plans[0].total} 分）" if plans[0] and plans[0].rows else "") + f"；可考：{'、'.join(c for c in EXAM_OPTIONS[name] if c not in OWNED[name])}", ""])
        # 每次换职业的好处：和「主职业」（OWNED 第一个）同一级相比，多涨/少涨了什么
        main = OWNED[name][0]
        benefit, uses = {}, {}
        for r in plan.rows:
            if r.action != "升级" or r.cls == main:
                continue
            base_score, base = p.result(r.step, r.level_from, main)
            more = [STATS[k] for k in range(9) if r.gains[k] > base[k]]
            less = [STATS[k] for k in range(9) if r.gains[k] < base[k]]
            if more or less:
                text = f"比{main}多 {' '.join(more) or '—'}" + (f"、少 {' '.join(less)}" if less else "") + f"（+{r.score - base_score} 分）"
            else:
                text = f"加点和{main}一样" + ("，用它练精通" if r.cls in REQUIRED.get(name, []) else "")
            benefit[r.step] = text
            uses.setdefault(r.cls, []).append(f"Lv{r.level_from}→{r.level_from + 1}：{text}")

        sums = [0] * 9
        have = list(OWNED[name])
        for i, r in enumerate(plan.rows):
            tip = f"先观星确认：用{r.cls if r.action == '升级' else '当前职业'}应看到「{gains_text(r.gains)}」，对上说明种子没错位" if i == 0 else ""
            if r.action == "升级":
                sums = [a + b for a, b in zip(sums, r.gains)]
                why = f"换{r.cls}：{benefit[r.step]}" if r.step in benefit else ""
                route_rows.append([name, r.step + 1, f"{r.level_from}→{r.level_from + 1}", "升1级", r.cls, "、".join(have),
                                   *[g if g else "" for g in r.gains], r.score, r.compare,
                                   "；".join(x for x in (r.balance_note, why, tip) if x), r.alternatives])
            else:
                if r.cls in EXAM_OPTIONS[name] and r.cls not in have:
                    have.append(r.cls)
                if r.cls in EXAM_OPTIONS[name]:
                    gain = "；".join(uses.get(r.cls, [])) or "后面没用上"
                    extra = "；为了拿精通技能" if r.cls in REQUIRED.get(name, []) else ""
                    v = p.exam_value(r.step)
                    ch = (EXAM_CHANCE.get(name) or {}).get(r.cls)
                    verdict = (f"游戏显示成功率 {ch}% → {'能过' if v < ch else '会失败'}" if ch is not None
                               else f"游戏里显示的成功率要高于 {v:.2f}% 才能过（低于就失败，种子照样前进）")
                    what = f"考{r.cls}：判定值 {v:.2f}%，{verdict}。好处：{gain}{extra}"
                else:
                    what = f"跳过：用任意一场初级考试吃掉这一级（判定值 {p.exam_value(r.step):.2f}%，过不过都行）"
                route_rows.append([name, r.step + 1, "", "跳过（考试）", r.cls if r.cls in EXAM_OPTIONS[name] else "", "、".join(have), *[""] * 9, "",
                                   r.compare, f"{what}；这一步升级最多只有 {r.score} 分（{gains_text(r.gains)}）" + ("；" + tip if tip else ""), ""])
        route_rows.append([name, "", "合计", "", "", "", *sums, plan.total, "", "", ""])
        route_rows.append([""] * 19)

    json.dump({"seeds": seed_rows, "routes": route_rows}, open("sheet_rows.json", "w"), ensure_ascii=False)
    for r in route_rows:
        print(r[:6], r[15:])


if __name__ == "__main__":
    main()
