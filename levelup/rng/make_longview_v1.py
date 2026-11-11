"""长线观星：每人从现在的种子起往后 40 级，职业加成统一按每项成长率 +15%（不分职业、不算坐骑），
看不跳过 / 跳过最差几级（最高）/ 跳过最好几级（最低）各涨多少，跳过放在哪几级。输出 longview.json。"""
import json, os
import run_plans as R
from fe_growth import level_up, next_seed, STATS
from planner import score

HERE = os.path.dirname(os.path.abspath(__file__))
N, BONUS, MAXS = 40, 15, 20
out = {}
for name in R.OWNED:
    seed, lv = R.current_state(name)
    w = R.W[name]
    base = list(R.data.characters[name])
    gr = [b + BONUS for b in base]
    seq = []
    s = seed
    for i in range(N + MAXS):
        g = list(level_up(s, gr, 2).gains)
        seq.append({"i": i, "g": g, "pts": sum(g), "sc": score(g, w)})
        s = next_seed(s)
    def pick(S, worst):
        win = seq[:N + S]
        key = (lambda x: (x["sc"], x["pts"], -x["i"])) if worst else (lambda x: (-x["sc"], -x["pts"], -x["i"]))
        drop = sorted(win, key=key)[:S]
        ids = {d["i"] for d in drop}
        used = [x for x in win if x["i"] not in ids]
        tot = [sum(x["g"][k] for x in used) for k in range(9)]
        # 跳过的位置：第 i 个种子前已经升了几级 → 在 Lv(lv+那几级) 时考试
        skips = []
        for d in sorted(drop, key=lambda x: x["i"]):
            done = sum(1 for x in used if x["i"] < d["i"])
            skips.append({"lv": lv + done, "g": d["g"], "sc": d["sc"], "pts": d["pts"]})
        return {"S": S, "tot": tot, "pts": sum(tot), "sc": score(tot, w), "skips": skips}
    hi = [pick(S, True) for S in range(MAXS + 1)]
    lo = [pick(S, False) for S in range(MAXS + 1)]
    # 建议跳过次数：每跳一次要多 ≥4 加权分（同初级考试门槛）
    # 默认最多跳 10 次（平均 4 级一次）；跳 S 次的「超出门槛」= 多出的加权分 − 4×S；取最大的（同分取少跳）
    rec = max(range(11), key=lambda S: (hi[S]["sc"] - hi[0]["sc"] - 4 * S, -S))
    exp = [round(max(0, min(100, x)) * N / 100, 1) for x in gr]
    cur = R.CURRENT.get(name, {}).get("shot_1105", {})
    out[name] = {"level": lv, "end": lv + N, "growth": gr, "personal": base, "weights": w, "exp": exp,
                 "expSc": round(sum(a * b for a, b in zip(exp, w)), 1),
                 "seq": [{"g": x["g"], "sc": x["sc"], "pts": x["pts"]} for x in seq],
                 "hi": hi, "lo": lo, "rec": rec, "stats": cur.get("stats"), "shotLevel": cur.get("level")}
    h0, hr = hi[0], hi[rec]
    print(name, f"Lv{lv}→{lv+N}", "不跳", h0["pts"], h0["sc"], "| 建议跳", rec, hr["pts"], hr["sc"], "| 最低(跳好的", rec, ")", lo[rec]["pts"], lo[rec]["sc"], "| 期望", out[name]["expSc"],
          [x["sc"] - y["sc"] for x, y in zip(hi[1:8], hi[:7])])
json.dump(out, open(os.path.join(HERE, "longview.json"), "w", encoding="utf-8"), ensure_ascii=False)


# ---------- 养成建议（文字） ----------
CLS = [c for c in json.load(open(os.path.join(HERE, "fw_classes.json"), encoding="utf-8")) if c["tier"] in ("中级", "上级", "最上级")]
KEYS = ["hp", "str", "mag", "spd", "dex", "def", "res", "lck", "cha"]
MAGIC = {"法毕欧", "杨界", "乌尔坦德"}
for name, d in out.items():
    w, rec, exp = d["weights"], d["rec"], d["exp"]
    h0, hr, lr = d["hi"][0], d["hi"][rec], d["lo"][rec]
    adv = []
    luck = h0["sc"] - d["expSc"]
    adv.append(f"运气：不跳过 40 级加权 {h0['sc']}，平均运气 {d['expSc']}，" + (f"种子偏好（+{luck:.0f}）" if luck >= 15 else f"种子偏差（{luck:.0f}），靠跳过补回" if luck <= -15 else f"和平均差不多（{luck:+.0f}）") + "。")
    if rec:
        from collections import Counter
        cnt = Counter(s["lv"] for s in hr["skips"])
        lvs = "、".join(f"Lv{l}" + (f"（连考 {n} 次）" if n > 1 else "") for l, n in sorted(cnt.items()))
        adv.append(f"跳过：建议跳 {rec} 次（每次 1 张初级手形约 300G，共约 {rec*300}G），在 {lvs} 升级前考试，加权 +{hr['sc']-h0['sc']}、点数 +{hr['pts']-h0['pts']}。")
    else:
        adv.append("跳过：40 级里没有值得花一次考试跳过的等级，按顺序升就好。")
    # 最差 / 最好的连续 5 级（按不跳过的顺序）
    seq = d["seq"][:N]
    win = [(sum(x["sc"] for x in seq[i:i+5]), i) for i in range(N - 4)]
    lo_w, hi_w = min(win), max(win)
    adv.append(f"最差的一段：Lv{d['level']+lo_w[1]}～{d['level']+lo_w[1]+5}（5 级加权 {lo_w[0]}）；最好的一段：Lv{d['level']+hi_w[1]}～{d['level']+hi_w[1]+5}（{hi_w[0]}）。跳过的考试优先排在差的那段。")
    weak, strong = [], []
    for k in range(9):
        if w[k] >= 3 and hr["tot"][k] < exp[k] * 0.8 - 0.5:
            weak.append(k)
    if not weak:   # 没有明显偏低的，就提一下高权重里相对最弱的一项
        cand = [(hr["tot"][k] / exp[k], k) for k in range(9) if w[k] >= 4 and exp[k] > 0 and hr["tot"][k] < exp[k]]
        if cand:
            weak.append(min(cand)[1])
        if hr["tot"][k] >= exp[k] * 1.25 + 0.5:
            strong.append(k)
    if strong:
        adv.append("种子偏爱：" + "、".join(f"{STATS[k]}（{hr['tot'][k]} vs 平均 {exp[k]}）" for k in strong) + "。")
    if weak:
        parts = []
        for k in weak:
            pool = [c for c in CLS if (c["family"] == "魔道系") == (name in MAGIC)]
            best = sorted(pool, key=lambda c: -c["growth"][KEYS[k]])[:2]
            parts.append(f"{STATS[k]} 跳对了也只有 {hr['tot'][k]}（平均 {exp[k]}，权重 {w[k]}），实际职业里可用 " + "、".join(f"{c['name']}（{STATS[k]}+{c['growth'][KEYS[k]]}%）" for c in best) + " 补")
        adv.append("要补的：" + "；".join(parts) + "。")
    adv.append(f"区间：同样跳 {rec} 次，跳对了加权 {hr['sc']}，跳错（跳在最好的几级）只有 {lr['sc']}，差 {hr['sc']-lr['sc']}。")
    d["advice"] = adv
    print(name); [print("  ", a) for a in adv]
json.dump(out, open(os.path.join(HERE, "longview.json"), "w", encoding="utf-8"), ensure_ascii=False)
