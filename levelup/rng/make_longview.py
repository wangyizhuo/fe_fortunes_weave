"""长线观星（按单项能力）：每人从现在的种子起往后 40 级，职业加成统一按每项成长率 +15%（不分职业、不算坐骑），保底 2 项。
每项能力：40 级涨几点 vs 期望、运气百分位（二项分布）、只为这一项跳过 S 次时的最高 / 最低和跳过的位置。不算加权分。
输出 longview.json。"""
import json, os
from math import comb
import run_plans as R
from fe_growth import level_up, next_seed, STATS

HERE = os.path.dirname(os.path.abspath(__file__))
N, BONUS, MAXS = 40, 15, 20


def pct_le(k, n, p):
    """二项分布：涨 ≤k 次的概率（%）。"""
    return 100 * sum(comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(k + 1))


def luck_pct(k, n, p):
    """运气百分位：比 k 少的概率 + 一半等于 k 的概率（50 = 正好平均）。"""
    lo = pct_le(k - 1, n, p) if k > 0 else 0
    return round((lo + pct_le(k, n, p)) / 2)


out = {}
for name in R.OWNED:
    seed, lv = R.current_state(name)
    gr = [b + BONUS for b in R.data.characters[name]]
    hits = []          # hits[j][k] = 第 j 个种子这一项涨不涨
    s = seed
    for j in range(N + MAXS):
        hits.append(list(level_up(s, gr, 2).gains))
        s = next_seed(s)
    stats = []
    for k in range(9):
        p = max(0, min(100, gr[k])) / 100
        col = [h[k] for h in hits]
        got = sum(col[:N])
        exp = round(N * p, 1)
        per = []
        for S in range(MAXS + 1):
            win = col[:N + S]
            c = sum(win)
            mx = min(N, c)                      # 跳过 S 个「不涨这项」的级
            mn = c - min(S, c)                  # 跳过 S 个「涨这项」的级
            # 最高时跳过的位置：窗口里前 S 个不涨的级（换成哪几个不涨的都一样，取最早的）
            miss = [j for j in range(N + S) if not win[j]][:S]
            per.append({"S": S, "max": mx, "min": mn, "skip": miss})
        # 分段：每 10 级涨几次
        seg = [sum(col[i:i + 10]) for i in range(0, N, 10)]
        stats.append({"k": STATS[k], "rate": gr[k], "got": got, "exp": exp, "diff": round(got - exp, 1),
                      "luck": luck_pct(got, N, p), "seg": seg, "per": per})
    # ---- 加权：整体跳过（跳过加权分最低的级），规则同「到 Lv35」：每跳一次（初级考试）要多 ≥4 加权分 ----
    from planner import score
    w = R.W[name]
    wsc = [score(h, w) for h in hits]
    def wpick(S, worst=True):
        idx = sorted(range(N + S), key=(lambda j: (wsc[j], sum(hits[j]), -j)) if worst else (lambda j: (-wsc[j], -sum(hits[j]), -j)))[:S]
        ids = set(idx)
        used = [j for j in range(N + S) if j not in ids]
        tot = [sum(hits[j][k] for j in used) for k in range(9)]
        lvs, n = [], 0
        for j in range(N + S):
            if j in ids:
                lvs.append(lv + n)
            else:
                n += 1
        return {"S": S, "tot": tot, "pts": sum(tot), "sc": score(tot, w), "lvs": lvs}
    wcur = [wpick(S) for S in range(MAXS + 1)]
    wlo = [wpick(S, False) for S in range(MAXS + 1)]
    # 11-11：建议跳几次 = 按「到 Lv35」同一套跳过条件逐级走 40 级，数一共跳了几次
    tier = "P0" if name in R.P0 else "P2" if name in R.P2 else "other"
    rule = R.SKIP_RULE[tier]
    j, n_done, wrec = 0, 0, 0
    while n_done < N and wrec < MAXS:
        fut = [score(h, w) for h in hits[j + 1:j + 16]] or [wsc[j]]
        c1 = wsc[j] <= rule["cap"]; c2 = wsc[j] <= sum(fut) / len(fut) * (1 - rule["pct"])
        if (c1 or c2) if rule["or"] else (c1 and c2):
            wrec += 1
        else:
            n_done += 1
        j += 1
        if j >= len(hits) - 1:
            break
    tot_got = sum(x["got"] for x in stats)
    tot_exp = round(sum(x["exp"] for x in stats), 1)
    out[name] = {"level": lv, "end": lv + N, "growth": gr, "personal": list(R.data.characters[name]),
                 "hits": [h for h in hits], "stats": stats, "got": tot_got, "exp": tot_exp,
                 "w": w, "wsc": wsc, "wcur": wcur, "wlo": wlo, "wrec": wrec,
                 "wexp": round(sum(x["exp"] * ww for x, ww in zip(stats, w)), 1)}

# ---------- 总结（全部用「和期望的差值」，不用百分位） ----------
f1 = lambda v: f"{v:+.1f}".replace(".0", "")
for name, d in out.items():
    st = d["stats"]
    by_d = sorted(st, key=lambda x: (x["diff"], x["got"]))
    best_d, worst_d = by_d[-1], by_d[0]
    by_got = sorted(st, key=lambda x: (x["got"], x["rate"]))
    top_g, low_g = by_got[-1], by_got[0]
    good = [x for x in st if x["diff"] >= 3]
    bad = [x for x in st if x["diff"] <= -3]
    tot = d["got"] - d["exp"]
    s = []
    s.append(f"整体：40 级共涨 {d['got']} 点，期望 {d['exp']}，差 {f1(tot)}" + ("，偏好运。" if tot >= 5 else "，偏差运。" if tot <= -5 else "，接近期望。"))
    s.append(f"涨得最多：{top_g['k']} {top_g['got']} 点（成长率 {top_g['rate']}%）；涨得最少：{low_g['k']} {low_g['got']} 点（成长率 {low_g['rate']}%）。")
    s.append(f"比期望多得最多：{best_d['k']} {f1(best_d['diff'])}（{best_d['got']} vs {best_d['exp']}）；少得最多：{worst_d['k']} {f1(worst_d['diff'])}（{worst_d['got']} vs {worst_d['exp']}）。")
    if good:
        s.append("比期望多 3 点以上：" + "、".join(f"{x['k']} {f1(x['diff'])}" for x in good) + "。")
    if bad:
        s.append("比期望少 3 点以上：" + "、".join(f"{x['k']} {f1(x['diff'])}" for x in bad) + "。")
    adv = []
    for x in sorted(bad, key=lambda x: x["diff"])[:3]:
        p10 = x["per"][5]
        adv.append(f"{x['k']}少 {-x['diff']:.0f}：专门为它跳 5 次最多到 {p10['max']}（不跳 {x['got']}，期望 {x['exp']}）；"
                   + ("跳过补得回来。" if p10["max"] >= x["exp"] else "跳过也补不到期望，要靠职业成长加成或道具。"))
    for x in sorted(good, key=lambda x: -x["diff"])[:2]:
        adv.append(f"{x['k']}多 {x['diff']:.0f}：不跳也有 {x['got']}（期望 {x['exp']}），定位可以往这项靠。")
    if not adv:
        adv.append("各项都在期望 ±3 以内，没有特别要补的；跳过按「到 Lv35」页的路线来就行。")
    # 加权（整体跳过）
    wc, wr = d["wcur"], d["wrec"]
    s.insert(1, f"加权：不跳过 {wc[0]['sc']}（期望 {d['wexp']}）；按跳过条件（和到 Lv35 同一套）是 {wc[wr]['sc']}，要跳 {wr} 次（约 {wr * 300}G 初级手形），比不跳多 {wc[wr]['sc'] - wc[0]['sc']}。再多跳也只到 {wc[MAXS]['sc']}（跳 {MAXS} 次），不划算。")
    soon = [l for l in wc[wr]["lvs"] if l < d["level"] + 10]
    if soon:
        adv.insert(0, f"最近 10 级里值得跳的：" + "、".join(f"Lv{l}" for l in soon) + "（升级前考一次试）；具体职业和考试以「到 Lv35」页为准。")
    # 定位相关：高权重（≥4）里比期望少的
    role = [x for x, ww in zip(st, d["w"]) if ww >= 4 and x["diff"] <= -2]
    if role:
        adv.append("主力能力（权重≥4）里偏少的：" + "、".join(f"{x['k']} {f1(x['diff'])}" for x in role) + "，选职业时优先挑这几项成长高的。")
    d["summary"], d["advice"] = s, adv
    hi_ = "、".join(f"{x['k']}{f1(x['diff'])}" for x in sorted(good, key=lambda x: -x["diff"])[:3]) or "无"
    lo_ = "、".join(f"{x['k']}{f1(x['diff'])}" for x in sorted(bad, key=lambda x: x["diff"])[:3]) or "无"
    tone = "整体好运" if tot >= 5 else "整体差运" if tot <= -5 else "整体接近期望"
    d["oneline"] = f"{tone}（{f1(tot)}）；多：{hi_}；少：{lo_}；加权最高 {d['wcur'][d['wrec']]['sc']}（跳 {d['wrec']} 次）。"
    for x in st:
        if x["diff"] >= 3:
            t = f"比期望多 {x['diff']:.0f}，好运"
        elif x["diff"] <= -3:
            p10 = x["per"][5]
            t = f"比期望少 {-x['diff']:.0f}，差运；" + ("单项跳 5 次能补到期望" if p10["max"] >= x["exp"] else "跳过也补不到期望")
        else:
            t = "接近期望"
        x["note"] = t
    print(name, d["oneline"])
json.dump(out, open(os.path.join(HERE, "longview.json"), "w", encoding="utf-8"), ensure_ascii=False)
