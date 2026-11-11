"""生成 brute 的输入：mk.py 角色 'cls[@mount:lv]|gains|same' ...   gains 用空格分隔的属性名，? = 不核对"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from run_plans import data
from fe_growth import STATS
name = sys.argv[1]
for spec in sys.argv[2:]:
    cls, gains, same = (spec.split("|") + ["0"])[:3]
    mount, mlv = None, 0
    if "@" in cls:
        cls, m = cls.split("@"); mount, mlv = m.split(":"); mlv = int(mlv)
    lv = 20
    g = data.growth(name, cls, lv, mount, mlv)
    mask = -1 if gains.strip() == "?" else sum(1 << STATS.index(x) for x in gains.split())
    print(*g, mask, same)
