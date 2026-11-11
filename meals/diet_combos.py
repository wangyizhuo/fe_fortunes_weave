"""迪 + 两人，每道菜都 perfect 的组合（Yizhuo 11-08 规则：闪光 最爱2/喜欢1/普通0，1+1+1 或 2+2+0 = perfect；讨厌不带；2+1+0 未确认，不用）。
数据：迪线招募表「Recruit - Diet」tab（贴在 diet_tab.json）。"""
import json, itertools
D = ["岩盐火腿","鱼酱汤","玛达津","烤山羊肉","炭烤蒜香扇贝","南瓜汤","豆炖沙猪","芝士烤小龙虾","糖浆炖梨","卤甜辣鞑古扎七节虫","炭烤鱼","特芙果酱"]
rows = json.load(open("diet_tab.json"))
TIER = {"必招": 0, "满足": 1, "可选": 2}
RECRUITED = {"迪托利希","法毕欧","艾丝梅拉尔达","米迦艾拉","杨界","伊欧","奇洛伊卡","努蒂奴","乌尔坦德"}
people = {}
for r in rows[1:]:
    if len(r) < 25 or r[0] not in TIER or r[8] == "迪托利希": continue
    people[r[8]] = {"tier": TIER[r[0]], "tierName": r[0], "ch": r[5], "renown": r[6], "sup": r[7], "pref": [int(x) for x in r[13:25]], "recruited": r[8] in RECRUITED}
di = [int(x) for x in rows[1][13:25]]
def perfect(vals):
    if min(vals) == 0: return False
    sp = sorted(v - 1 for v in vals)
    return sp[0] >= 1 or sp[1:] == [2, 2]
targets = [n for n, p in people.items() if not p["recruited"]]
rank = {n: (people[n]["tier"], int(str(people[n]["renown"] or 0).split("–")[0] or 0)) for n in targets}
out = {}
for i, d in enumerate(D):
    combos = []
    for a, b in itertools.combinations(targets, 2):
        v = [di[i], people[a]["pref"][i], people[b]["pref"][i]]
        if perfect(v):
            combos.append((sorted([rank[a], rank[b]]), -sum(v), a, b, v))
    combos.sort()
    out[d] = combos
json.dump({d: [[a, b, v] for _, _, a, b, v in c] for d, c in out.items()}, open("diet_combos.json", "w"), ensure_ascii=False, indent=0)
print("迪:", di)
print("目标:", sorted(targets, key=lambda n: rank[n]))
for d, c in out.items():
    print(d, len(c), [(a, b, v) for _, _, a, b, v in c[:5]])
