"""到 Lv35 路线总结：每级实际加权分 vs 期望（随机种子模拟，含保底重抽），各项能力实际 vs 期望。存 summary.json。"""
import json, os, random
from fe_growth import STATS, level_up
from run_plans import data, W
HERE = os.path.dirname(os.path.abspath(__file__))
D = json.load(open(os.path.join(HERE, "detail.json"), encoding="utf-8"))
random.seed(1)
SEEDS = [random.getrandbits(31) for _ in range(1500)]
_cache = {}
def expect(name, cls, lv):
    k = (name, cls, lv)
    if k not in _cache:
        g = data.growth(name, cls, lv)
        tot = [0] * 9
        for s in SEEDS:
            for i, v in enumerate(level_up(s, g, 2).gains):
                tot[i] += v
        _cache[k] = [t / len(SEEDS) for t in tot]
    return _cache[k]
out = {}
for name, d in D.items():
    w = W[name]
    rows, exp_tot = [], [0.0] * 9
    for f in d["future"]:
        if f["kind"] != "升级":
            continue
        lv = int(f["lv"][2:].split("→")[0])
        e = expect(name, f["cls"], lv)
        exp_tot = [a + b for a, b in zip(exp_tot, e)]
        es = sum(a * b for a, b in zip(e, w))
        rows.append(dict(lv=f["lv"], cls=f["cls"], s=f["s"], es=round(es, 1), diff=round(f["s"] - es, 1),
                         g=" ".join(STATS[i] for i in range(9) if f["g"][i])))
    exams = [dict(step=f["step"], cls=f["cls"], roll=f["roll"], skip_s=f["s"]) for f in d["future"] if f["kind"] == "考试"]
    act = d["total"]
    out[name] = dict(rows=rows, exp=[round(x, 1) for x in exp_tot], act=act, w=w,
                     ws=sum(a * b for a, b in zip(act, w)), wexp=round(sum(a * b for a, b in zip(exp_tot, w)), 1),
                     exams=exams, end=d["end"], now=d["now"]["raw"], lv=d["now"]["start_lv"])
json.dump(out, open(os.path.join(HERE, "summary.json"), "w"), ensure_ascii=False)
for n, o in out.items():
    print(f"\n{n} Lv{o['lv']}→35 加权 {o['ws']} vs 期望 {o['wexp']}  考试 {[(e['cls'] or '跳过', e['roll']) for e in o['exams']]}")
    print("  各项 实际/期望:", "  ".join(f"{STATS[i]}{o['act'][i]}/{o['exp'][i]}(w{o['w'][i]})" for i in range(9)))
    hi = sorted(o["rows"], key=lambda r: -r["diff"])[:3]; lo = sorted(o["rows"], key=lambda r: r["diff"])[:3]
    print("  最好:", [(r["lv"], r["cls"], r["g"], r["diff"]) for r in hi])
    print("  最差:", [(r["lv"], r["cls"], r["g"], r["diff"]) for r in lo])
    print("  Lv35:", dict(zip(STATS, o["end"])))
