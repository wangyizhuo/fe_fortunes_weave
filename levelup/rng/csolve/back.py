"""从已知种子往回推，列出每一层的候选种子在各职业下的加点，找和记录对得上的。
用法：back.py 角色 种子 深度 职业1,职业2 ["记录1" "记录2" ...]（记录从近到远）"""
import sys, os, subprocess
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from run_plans import data
from fe_growth import level_up, STATS
PREV = os.environ["PREV"]
name, seed, depth, classes = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4].split(",")
mount = os.environ.get("MOUNT")
def nm(g): return " ".join(STATS[i] for i, v in enumerate(g) if v)
layer = [(seed, [])]
for d in range(1, depth + 1):
    nxt = []
    for s, path in layer:
        for p in map(int, subprocess.run([PREV, str(s)], capture_output=True, text=True).stdout.split()):
            outs = {c: nm(level_up(p, data.growth(name, c, 20), 2).gains) for c in classes}
            nxt.append((p, path + [outs]))
    layer = nxt
    print(f"-- 往回 {d} 步：{len(layer)} 个候选")
    for p, path in layer[:40]:
        print("  ", p, " | ".join(f"{c}:{g}" for c, g in path[-1].items()))
