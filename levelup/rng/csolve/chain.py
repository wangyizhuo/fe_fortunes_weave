"""从已知种子往回接记录：每一步在前驱种子里找和记录一致的（可插入最多 H 个没记录的步）。
chain.py 角色 种子 H "职业|加点" ...（从近到远）"""
import sys, os, subprocess
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from run_plans import data
from fe_growth import level_up, STATS
PREV = os.environ["PREV"]
name, seed, H = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
recs = [a.split("|") for a in sys.argv[4:]]
def prev(s): return list(map(int, subprocess.run([PREV, str(s)], capture_output=True, text=True).stdout.split()))
def gains(s, c): return set(STATS[k] for k, v in enumerate(level_up(s, data.growth(name, c, 20), 2).gains) if v)
def go(s, i, path):
    if i == len(recs):
        print("链：", " ← ".join(path)); return True
    cls, want = recs[i]; want = set(want.split())
    frontier = [(s, [])]
    for h in range(H + 1):
        nxt = []
        for t, hid in frontier:
            for p in prev(t):
                g = gains(p, cls)
                miss = len(g ^ want)
                if miss <= 1:
                    go(p, i + 1, path + [f"[跳{len(hid)}]" if hid else "", f"{p}:{cls}{'✓' if miss == 0 else '≈(差' + ' '.join(g ^ want) + ')'}"])
                nxt.append((p, hid + [p]))
        frontier = nxt
    return False
go(seed, 0, [str(seed)])
