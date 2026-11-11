"""analysis.json → 主表新页「过去成长反推」的行（past_sheet.json）。"""
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))  # 一次性脚本放在 tools/，数据和模块在上一层
_os.chdir(_sys.path[0])
import json, os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
A = json.load(open(os.path.join(HERE, "analysis.json"), encoding="utf-8"))
U = json.load(open(os.path.join(HERE, "uncertain.json"), encoding="utf-8"))
VD = json.load(open(os.path.join(HERE, "verdict.json"), encoding="utf-8"))
WT = json.load(open(os.path.join(HERE, "weights.json"), encoding="utf-8"))["weights"]
ST = ["HP", "力", "魔", "速", "技", "防", "魔防", "幸", "魅"]
f1 = lambda x: round(x, 1) if x is not None else ""
sgn = lambda x: f"{x:+.1f}"
v = [["一、总结（数字都是「加点项数」；期望 = 同职业同等级、随机种子下的平均，含保底 2 项）"]]
v.append(["角色", "当前Lv", "记录起点", "过去升级", "过去跳过", "其中没记录的步", "过去实际加点", "过去期望", "偏差",
          "被跳掉的几级：实际项数", "被跳掉的：期望", "已观星还没做（升/跳）", "未来路线", "未来加点", "未来期望", "偏差", "未来加权分", "加权期望", "加权偏差",
          "其中种子本身（不考、主职业直升）", "直升期望", "结论"])
for c in A["chars"]:
    pa, pe, f = c["past"], c["pending"], c["future"]
    row = [c["name"], c["now"], f"Lv{c['first_level']}", pa["ups"], pa["skips"], pa["hidden"], pa["cnt"], f1(pa["e_cnt"]),
           sgn(pa["cnt"] - pa["e_cnt"]), pa["score"], f1(pa["e_score"]), sgn(pa["score"] - pa["e_score"]), pa["skip_cnt"] if pa["skip_n"] else "", f1(pa["skip_e"]) if pa["skip_n"] else "",
           f"{pe['ups']} / {pe['skips']}"]
    if f:
        row += [f"Lv{f['frm']}→{f['to']}（考{f['exams']}次）", f["cnt"], f1(f["e_cnt"]), sgn(f["cnt"] - f["e_cnt"]),
                f["score"], f1(f["e_score"]), sgn(f["score"] - f["e_score"]), f["noexam_cnt"], f1(f["noexam_e"])]
    else:
        row += ["没有种子"] + [""] * 8
    row.append(VD.get(c["name"], ""))
    v.append(row)
v.append([""])
v.append(["二、单项：实际/期望（▲▼ = 明显偏离，|z|≥1.5）；乱数 = 第一轮抽到的乱数平均，0.5 平均，越小越好（★ 明显好，✗ 明显差）"])
v.append(["角色", "范围"] + ST + ["加权偏差", "明显偏离的单项"])
def zu(u, n):
    return (u - 0.5) / (0.2887 / n ** 0.5) if u is not None and n else 0
for c in A["chars"]:
    w = WT[c["name"]]
    for lab, ps in [("过去已升的级", c["past_ps"]), ("乱数本身（已走的所有步）", c["rolls_ps"]), ("未来路线", (c["future"] or {}).get("ps"))]:
        if not ps:
            continue
        cells, hi = [], []
        for i in range(9):
            a, e, z = ps["act"][i], ps["exp"][i], ps["z"][i]
            mk = "▲" if z >= 1.5 else ("▼" if z <= -1.5 else "")
            cells.append(f"{a}/{e:.1f}{mk}")
            if mk:
                hi.append(f"{ST[i]}{mk}")
        v.append([c["name"], lab] + cells + [sgn(sum(wi * (a - e) for wi, a, e in zip(w, ps["act"], ps["exp"]))), "、".join(hi)])
        if lab != "过去已升的级":
            uc, uh = [], []
            for i in range(9):
                u, n = ps["u"][i], ps["un"][i]
                z = zu(u, n)
                mk = "★" if z <= -1.8 else ("✗" if z >= 1.8 else "")
                uc.append("" if u is None else f"{u:.2f}{mk}")
                if mk:
                    uh.append(f"{ST[i]}{mk}")
            v.append([c["name"], lab.replace("（已走的所有步）", "") + "·乱数平均"] + uc + ["", "、".join(uh)])
v.append([""])
v.append(["三、不确定的地方"])
v.append(["角色", "哪一步", "不确定什么", "现在怎么处理"])
for u in U:
    v.append([u["name"], u["where"], u["what"], u["how"]])
v.append([""])
v.append(["四、逐步列表（每一条 = 种子前进一步）"])
v.append(["角色", "记录#", "等级", "动作", "职业", "观星记录的加点", "种子算出的加点", "对上？", "项数", "期望项数", "加权分", "期望加权分", "状态", "备注"])
for r in A["rows"]:
    act = "没记录的一步" if r["hidden"] else ("升级" if r["ok"] else "考试跳过")
    lv = f"{r['frm']}→{r['to']}" if r["ok"] else f"(Lv{r['frm']})"
    m = "" if r["match"] is None else ("✓" if r["match"] else "✗")
    v.append([r["name"], r["idx"], lv, act, r["cls"], r["recorded"], r["predicted"], m,
              r["cnt"] if r["cnt"] is not None else "", f1(r["e_cnt"]), r["score"] if r["score"] is not None else "",
              f1(r["e_score"]), "已完成" if r["done"] else "已观星，还没做", r["note"]])
w = max(len(x) for x in v)
json.dump([x + [""] * (w - len(x)) for x in v], open(os.path.join(HERE, "past_sheet.json"), "w"), ensure_ascii=False)
print(len(v), "rows", w, "cols")
