"""迪 + 两人，每道菜都 perfect 的组合（Yizhuo 11-08 规则：闪光 最爱2/喜欢1/普通0，1+1+1 或 2+2+0 = perfect；讨厌不带；2+1+0 未确认，不用）。
数据：迪线招募表「Recruit - Diet」tab（贴在 diet_tab.json）。"""
import json, itertools
D = ["岩盐火腿","鱼酱汤","玛达津","烤山羊肉","炭烤蒜香扇贝","南瓜汤","豆炖沙猪","芝士烤小龙虾","糖浆炖梨","卤甜辣鞑古扎七节虫","炭烤鱼","特芙果酱"]
rows = json.load(open("diet_tab.json"))
TIER = {"必招": 0, "满足": 1, "可选": 2}
RECRUITED = {"迪托利希","法毕欧","艾丝梅拉尔达","米迦艾拉","杨界","伊欧","奇洛伊卡","努蒂奴","乌尔坦德"}
MAXED = {"哥莱亚斯"}   # Yizhuo 11-18：好感满了，不再带
RENOWN_NOW = 6          # Yizhuo 11-18：现在名声 6，名声 ≤6 能挖的人优先
people = {}
for r in rows[1:]:
    if len(r) < 25 or r[0] not in TIER or r[8] == "迪托利希" or r[8] in MAXED: continue
    people[r[8]] = {"tier": TIER[r[0]], "tierName": r[0], "ch": r[5], "renown": r[6], "sup": r[7], "pref": [int(x) for x in r[13:25]], "recruited": r[8] in RECRUITED}
di = [int(x) for x in rows[1][13:25]]
def perfect(vals):
    if min(vals) == 0: return False
    sp = sorted(v - 1 for v in vals)
    return sp[0] >= 1 or sp[1:] == [2, 2]
targets = [n for n, p in people.items() if not p["recruited"]]
def _rn(n): return int(str(people[n]["renown"] or 0).split("–")[0] or 0)
rank = {n: (0 if _rn(n) <= RENOWN_NOW else 1, people[n]["tier"], _rn(n)) for n in targets}
out = {}
for i, d in enumerate(D):
    combos = []
    for a, b in itertools.combinations(targets, 2):
        v = [di[i], people[a]["pref"][i], people[b]["pref"][i]]
        if perfect(v):
            combos.append(((rank[a][0] + rank[b][0], sorted([rank[a], rank[b]])), -sum(v), a, b, v))   # 先看几个人现在能挖
    combos.sort()
    out[d] = combos
# 表格「迪吃饭 perfect 组合」的行（diet_plan_rows.json）
SPK = ["讨厌", "普通", "喜欢", "最爱"]
def rn_tag(n): return f"{n}（名声{_rn(n)}）"
rows_out = [["菜", "首选：迪 + 两人", "好感（迪 / 两人）", "闪光", "备选（按优先级）", f"这道菜能 perfect 的目标（按优先级；名声 ≤{RENOWN_NOW} 现在能挖的在前）"]]
for d, c in out.items():
    if not c:
        rows_out.append([d, "没有两人能和迪一起 perfect", "", "", "", ""]); continue
    _, _, a, b, v = c[0]
    who = sorted({n for _, _, x, y, _ in c for n in (x, y)}, key=lambda n: (rank[n], targets.index(n)))
    rows_out.append([d, f"迪 + {a} + {b}", " / ".join(SPK[x] for x in v), "+".join(str(x - 1) for x in v),
                     "；".join(f"迪+{x}+{y}" for _, _, x, y, _ in c[1:5]), "、".join(rn_tag(n) for n in who)])
json.dump(rows_out, open("diet_plan_rows.json", "w"), ensure_ascii=False, indent=0)
print("迪:", di)
print("目标:", sorted(targets, key=lambda n: rank[n]))
for d, c in out.items():
    print(d, len(c), [(a, b, v) for _, _, a, b, v in c[:5]])
