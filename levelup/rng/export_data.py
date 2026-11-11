"""把程序里用到的所有角色数据导出成人能读的文件，放在仓库根目录 data/（每个角色一份 .json + 一份 .md）。

    python3 export_data.py           # 重新导出（build.sh 最后会自动跑）
    python3 export_data.py --check   # 只检查 data/ 是不是最新的（checks.py 的 D5 用它）

data/ 是「看」的副本，不是输入：要改数据请改 levelup/rng 下的源文件（见 docs/ARCHITECTURE.md），再重新导出。
每份角色文件包含：
  基本：优先级、成长率、初始能力、擅长技能
  当前：截图等级 / 职业 / 能力 / 12 项技能，规划起点（等级、种子、能力）
  职业：已有职业、可考职业、必考、排除、坐骑
  权重：9 项能力的权重
  种子：第一条已知种子、每条观星记录（种子、职业、记录的加点、种子算出的加点、是否一致）、
        从现在起往后 25 步的种子链（每步种子 + 考试判定值）
  规划：到 Lv35 的路线（和 checks.py 快照一致）、到 Lv45 的路线（plan45.json）
  吃饭：12 道菜的喜好（0 讨厌 / 1 普通 / 2 喜欢 / 3 最爱，来自迪线招募表）
  装备 / 友好度：目前没有任何数据来源，留空待补
"""
from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import demo  # noqa: E402
import run_plans as R  # noqa: E402
from fe_growth import STATS, exam_roll, level_up, next_seed  # noqa: E402
from run_plans import ORDER  # noqa: E402

ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
DATA = os.path.join(ROOT, "data")
DISHES = ["岩盐火腿", "鱼酱汤", "玛达津", "烤山羊肉", "炭烤蒜香扇贝", "南瓜汤", "豆炖沙猪", "芝士烤小龙虾",
          "糖浆炖梨", "卤甜辣鞑古扎七节虫", "炭烤鱼", "特芙果酱"]
PREF_NAME = {0: "讨厌", 1: "普通", 2: "喜欢", 3: "最爱"}   # 迪线招募表「Recruit - Diet」的编码（见 meals/diet_combos.py）
CHAIN_STEPS = 25
_KEYS = ["hp", "str", "mag", "spd", "dex", "def", "res", "lck", "cha"]


def _stats(v):
    return dict(zip(STATS, v)) if v else None


def _meal_prefs():
    path = os.path.join(ROOT, "meals", "diet_tab.json")
    if not os.path.exists(path):
        return {}
    rows = json.load(open(path, encoding="utf-8"))
    out = {}
    for r in rows[1:]:
        if len(r) >= 25 and r[8] and r[8] not in out:
            try:
                out[r[8]] = {d: int(x) for d, x in zip(DISHES, r[13:25])}
            except ValueError:
                pass
    return out


def _fw_chars():
    return {c["name"]: c for c in json.load(open(os.path.join(HERE, "fw_characters.json"), encoding="utf-8"))}


def _plan35():
    import checks
    return checks.snapshot()


def character(name, fw, meals, p35, p45):
    shot = R.CURRENT.get(name, {}).get("shot_1105") or {}
    seed0, first = demo.KNOWN_SEEDS[name]
    seed, level = R.current_state(name)
    recs = []
    for r in R.records(name):
        e = {"序号": str(r["idx"]), "种子": r["seed"], "从等级": r["frm"],
             "动作": "升级" if r["ok"] else ("没记下的一步" if r["ok"] is None else "考试/没升级"),
             "职业": r["cls"] or None, "记录的加点": [s for s, g in zip(STATS, r["gains"]) if g]}
        if r["ok"] and r["seed"] is not None:
            pred = list(level_up(r["seed"], R.data.growth(name, r["cls"], r["frm"]), 2).gains)
            e["种子算出的加点"] = [s for s, g in zip(STATS, pred) if g]
            e["一致"] = pred == r["gains"]
        if r.get("inferred"):
            e["说明"] = r.get("note", "按种子推算，备份里没有")
        recs.append(e)
    chain, s = [], seed
    for k in range(CHAIN_STEPS):
        chain.append({"第几步": k + 1, "种子": s, "考试判定值": exam_roll(s)})
        s = next_seed(s)
    f = fw.get(name, {})
    return {
        "角色": name,
        "优先级": R.tier_of(name),
        "成长率": _stats(R.data.characters.get(name)),
        "初始能力": {"等级": f.get("baseLevel"), "能力": _stats([f["baseStats"][k] for k in _KEYS]) if f.get("baseStats") else None},
        "擅长技能": f.get("skillsGood", []),
        "当前（截图）": {"等级": shot.get("level"), "职业": shot.get("class"), "能力": _stats(shot.get("stats")),
                     "技能": shot.get("skills"), "来源": shot.get("skills_src")},
        "规划起点": {"等级": level, "种子": seed, "能力": _stats(R.start_stats(name))},
        "职业": {"已有": R.OWNED[name], "可考": R.EXAM_OPTIONS[name], "必考": R.REQUIRED.get(name, []),
               "排除": R.EXCLUDE.get(name, []), "坐骑": R.MOUNT[name][0] if name in R.MOUNT else None},
        "权重": dict(zip(STATS, R.W[name])),
        "种子": {"第一条已知种子": seed0, "从第几条记录开始": first, "观星记录": recs,
               "往后种子链": chain, "不跳过的种子": sorted(R.NO_SKIP_SEEDS.get(name, []))},
        "规划": {"到Lv35": p35.get(name), "到Lv45": p45.get(name)},
        "吃饭喜好": {d: PREF_NAME[v] for d, v in meals[name].items()} if name in meals else None,
        "装备": None,
        "友好度": None,
    }


def to_md(c):
    L = [f"# {c['角色']}（{c['优先级']}）", "", "> 自动导出（levelup/rng/export_data.py），不要手改。", ""]
    cur, st = c["当前（截图）"], c["规划起点"]
    L += ["## 当前", f"- 截图：Lv{cur['等级']} {cur['职业']}（{cur['来源'] or '—'}）",
          f"- 规划起点：Lv{st['等级']}，种子 {st['种子']}",
          f"- 已有职业：{'、'.join(c['职业']['已有'])}",
          f"- 必考：{'、'.join(c['职业']['必考']) or '—'}；排除：{'、'.join(c['职业']['排除']) or '—'}；坐骑：{c['职业']['坐骑'] or '—'}",
          f"- 擅长技能：{'、'.join(c['擅长技能']) or '—'}", ""]
    L += ["| | " + " | ".join(STATS) + " |", "|---" * 10 + "|"]
    for label, v in (("截图能力", cur["能力"]), ("起点能力", st["能力"]), ("成长率 %", c["成长率"]),
                     ("初始能力", c["初始能力"]["能力"]), ("权重", c["权重"])):
        if v:
            L.append(f"| {label} | " + " | ".join(str(v[s]) for s in STATS) + " |")
    if cur["技能"]:
        L += ["", "技能：" + "，".join(f"{k} {v}" for k, v in cur["技能"].items())]
    sd = c["种子"]
    L += ["", "## 过去的成长（观星记录）", f"第一条已知种子 {sd['第一条已知种子']}（从第 {sd['从第几条记录开始']} 条记录开始）", "",
          "| # | Lv | 动作 | 职业 | 种子 | 记录的加点 | 种子算出 | 一致 |", "|---|---|---|---|---|---|---|---|"]
    for r in sd["观星记录"]:
        ok = "" if "一致" not in r else ("✓" if r["一致"] else "✗")
        L.append(f"| {r['序号']} | {r['从等级']} | {r['动作']} | {r['职业'] or ''} | {r['种子'] or '—'} | "
                 f"{' '.join(r['记录的加点'])} | {' '.join(r.get('种子算出的加点', []))} | {ok} |")
    L += ["", f"## 往后 {CHAIN_STEPS} 步种子", "判定值 < 成功率×10000 就能考过（例：成功率 60% → 判定值 < 600000）。", "", "| 步 | 种子 | 考试判定值 |", "|---|---|---|"]
    L += [f"| {x['第几步']} | {x['种子']} | {x['考试判定值']} |" for x in sd["往后种子链"]]
    L += ["", "## 规划"]
    p = c["规划"]["到Lv35"]
    if p:
        L.append(f"- 到 Lv35：加权分 {p['加权分']}，点数 {p['点数']}，净值 {p['净值']}，手形金币 {p['手形金币']}G")
        L.append(f"  - 路线：{p['路线']}")
    p = c["规划"]["到Lv45"]
    if p:
        L.append(f"- 到 Lv45：加权分 {p.get('total')}，点数 {p.get('pts')}")
    if c["吃饭喜好"]:
        L += ["", "## 吃饭喜好", "，".join(f"{d} {v}" for d, v in c["吃饭喜好"].items())]
    L += ["", "## 装备 / 友好度", "还没有数据来源（截图或表格提供后补上）。", ""]
    return "\n".join(L)


def build():
    """返回 {相对路径: 文本}，不写盘。"""
    fw, meals, p35 = _fw_chars(), _meal_prefs(), _plan35()
    p45_path = os.path.join(HERE, "plan45.json")
    p45 = json.load(open(p45_path, encoding="utf-8")) if os.path.exists(p45_path) else {}
    files, index = {}, []
    for n in ORDER:
        c = character(n, fw, meals, p35, p45)
        files[f"characters/{n}.json"] = json.dumps(c, ensure_ascii=False, indent=1) + "\n"
        files[f"characters/{n}.md"] = to_md(c)
        index.append(f"| [{n}](characters/{n}.md) | {c['优先级']} | Lv{c['规划起点']['等级']} | {c['当前（截图）']['职业']} | "
                     f"{(c['规划']['到Lv35'] or {}).get('加权分', '—')} | {(c['规划']['到Lv45'] or {}).get('total', '—')} |")
    files["classes.json"] = json.dumps({"所有人可考（初级/中级 17 个）": R.ALL_CLASSES, "骑乘职业": R.MOUNTED,
                                        "考试费用": R.PERMIT_GOLD, "职业数据": json.load(open(os.path.join(HERE, "fw_classes.json"), encoding="utf-8"))},
                                       ensure_ascii=False, indent=1) + "\n"
    files["rules.json"] = json.dumps({"优先级": {n: R.tier_of(n) for n in ORDER}, "跳过条件": R.SKIP_RULE,
                                      "每分值多少金币": R.GOLD_PER_PT, "每级目标": 35, "最多考试数": R.MAX_EXAMS,
                                      "不跳过的种子": {k: sorted(v) for k, v in R.NO_SKIP_SEEDS.items()}},
                                     ensure_ascii=False, indent=1) + "\n"
    files["README.md"] = "\n".join([
        "# 数据（自动导出，只读）", "",
        "由 `levelup/rng/export_data.py` 生成，`bash levelup/rng/build.sh` 最后会自动更新；",
        "改数据请改 `levelup/rng/` 下的源文件（current_stats.json、run_plans.py 等，见 docs/ARCHITECTURE.md）。",
        "`python3 levelup/rng/checks.py` 的 D5～D8 会检查这里是不是最新、种子链是否连续、能力和技能是否合理。", "",
        "| 角色 | 优先级 | 规划起点 | 截图职业 | Lv35 加权分 | Lv45 加权分 |", "|---|---|---|---|---|---|", *index, "",
        "- `characters/<角色>.json / .md`：种子、观星记录（过去的成长）、等级、职业、能力、技能、权重、规划、吃饭喜好",
        "- `classes.json`：职业数据和可考清单；`rules.json`：优先级、跳过条件等规则常数",
        "- 装备、友好度：目前程序和表格里都没有，字段留空（null）待补", ""])
    return files


def stale():
    """data/ 里和重新导出结果不一样的文件。"""
    out = []
    for rel, text in build().items():
        p = os.path.join(DATA, rel)
        if not os.path.exists(p) or open(p, encoding="utf-8").read() != text:
            out.append(rel)
    return out


if __name__ == "__main__":
    if "--check" in sys.argv:
        s = stale()
        print("\n".join(s) or "data/ 是最新的")
        sys.exit(1 if s else 0)
    for rel, text in build().items():
        p = os.path.join(DATA, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        open(p, "w", encoding="utf-8").write(text)
    print(f"导出 {len(build())} 个文件到 {DATA}")
