"""吃饭 perfect 组合（迪线）。Yizhuo 11-08 规则：闪光 最爱2/喜欢1/普通0，1+1+1 或 2+2+0 = perfect；讨厌不带；2+1+0 未确认，不用。
11-25 Yizhuo：去掉班迪兹、哥莱亚斯（都满足了）；优先迪自己——迪线名声 6、7 要挖的人（迪 + 两人）；
另外列蕾达线名声 ≤5 能挖的人（迪 + 蕾达 + 一人，刷蕾达的支援）。数据：迪线招募表「Recruit - Diet」tab（diet_tab.json）。"""
import json, itertools, re
rows = json.load(open("diet_tab.json"))
D = [h.split(" - ")[1] for h in rows[0][13:25]]
di = [int(x) for x in rows[1][13:25]]
LEDA = [2, 2, 0, 0, 2, 2, 2, 0, 2, 2, 2, 2]   # fortunesweave meals 页
RECRUITED = {"迪托利希", "法毕欧", "艾丝梅拉尔达", "米迦艾拉", "杨界", "伊欧", "奇洛伊卡", "努蒂奴", "乌尔坦德"}
MAXED = {"哥莱亚斯", "班迪兹"}
ABSENT = {"莱桑达"}        # 11-25 Yizhuo：莱桑达目前不在
LEDA_ONLY = {"绯亚娜"}      # 11-25 Yizhuo：迪不用刷绯亚娜的好感，只在蕾达同桌时带（刷蕾达的支援）
DI_RENOWN = (6, 7)
LEDA_MAX = 5


def rep(r, route):
    m = re.search(route + r"（名声(\d+)", (r[1] or "") + (r[2] or ""))
    return int(m.group(1)) if m else None


P = {}
for r in rows[1:]:
    if len(r) < 25 or r[8] in RECRUITED or r[8] in MAXED or r[8] in ABSENT:
        continue
    P[r[8]] = {"di": rep(r, "迪托利希"), "leda": rep(r, "蕾达"), "pref": [int(x) for x in r[13:25]], "tier": r[0]}
DI_T = [n for n, p in P.items() if p["di"] in DI_RENOWN and n not in LEDA_ONLY]
LEDA_T = [n for n, p in P.items() if p["leda"] is not None and p["leda"] <= LEDA_MAX]


def perfect(v):
    if min(v) == 0:
        return False
    sp = sorted(x - 1 for x in v)
    return sp[0] >= 1 or sp == [0, 2, 2]


SPK = ["讨厌", "普通", "喜欢", "最爱"]
spk = lambda v: "+".join(str(x - 1) for x in v)
out = {}
for i, d in enumerate(D):
    a = sorted(((P[x]["di"] + P[y]["di"], -sum(v), x, y, v) for x, y in itertools.combinations(DI_T, 2)
                if perfect(v := [di[i], P[x]["pref"][i], P[y]["pref"][i]])))
    b = sorted(((P[x]["leda"], -sum(v), x, v) for x in LEDA_T if perfect(v := [di[i], LEDA[i], P[x]["pref"][i]])))
    out[d] = {"di": [[x, y, v] for _, _, x, y, v in a], "leda": [[x, v] for _, _, x, v in b]}
json.dump(out, open("diet_combos.json", "w"), ensure_ascii=False, indent=0)
tag = lambda n: f"{n}（名声{P[n]['di']}）"
rows_out = [["菜", "迪好感", "首选：迪 + 两人（迪线名声 6、7）", "闪光", "备选", "蕾达同桌：迪 + 蕾达 + 一人（蕾达线名声 ≤5）"]]
for i, d in enumerate(D):
    a, b = out[d]["di"], out[d]["leda"]
    rows_out.append([d, SPK[di[i]], f"迪 + {tag(a[0][0])} + {tag(a[0][1])}" if a else "没有",
                     spk(a[0][2]) if a else "", "；".join(f"{x}+{y}（{spk(v)}）" for x, y, v in a[1:5]),
                     "；".join(f"{x}（蕾达名声{P[x]['leda']}，{spk(v)}）" for x, v in b) or "没有"])
json.dump(rows_out, open("diet_plan_rows.json", "w"), ensure_ascii=False, indent=0)
for r in rows_out:
    print(" | ".join(r))
print("迪线 6/7：", "、".join(tag(n) for n in DI_T))
print("蕾达线 ≤5：", "、".join(f"{n}（{P[n]['leda']}）" for n in LEDA_T))
for n in DI_T + LEDA_T:
    ds = [d for d in D if any(n in (x, y) for x, y, _ in out[d]["di"]) or any(n == x for x, _ in out[d]["leda"])]
    print(n, "→", "、".join(ds) or "没有")
