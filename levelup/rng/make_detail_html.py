"""detail.json + detail_template.html → ../html/角色成长档案.html"""
import json, os
OUT_DIR = os.environ.get("FE_OUT_DIR") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "out")   # 生成的网页放这里
os.makedirs(OUT_DIR, exist_ok=True)
HERE = os.path.dirname(os.path.abspath(__file__))
from make_detail import ORDER
D = json.load(open(os.path.join(HERE, "detail.json"), encoding="utf-8"))
SLUG = {"迪托利希": "di", "法毕欧": "fabio", "艾丝梅拉尔达": "esme", "米迦艾拉": "mika", "杨界": "yang",
        "伊欧": "io", "奇洛伊卡": "chiro", "努蒂奴": "nuti", "乌尔坦德": "ult"}
SUM = json.load(open(os.path.join(HERE, "summary.json"), encoding="utf-8"))
TXT = json.load(open(os.path.join(HERE, "summary_text.json"), encoding="utf-8"))
META = {"order": ORDER, "slug": SLUG, "sum": SUM, "txt": TXT,
        "foot": "数据：种子反推（levelup/rng）、11-05 截图、fire-emblem-fw.site / global.fireemblem.top 的初始能力和职业补正。考试成败由种子决定：判定值低于游戏显示的成功率才能过；没填游戏成功率的考试按能过算。2026-11-05 生成。"}
t = open(os.path.join(HERE, "detail_template.html"), encoding="utf-8").read()
t = t.replace("__DATA__", json.dumps(D, ensure_ascii=False)).replace("__META__", json.dumps(META, ensure_ascii=False))
os.makedirs(os.path.join(HERE, "..", "html"), exist_ok=True)
out = os.path.join(HERE, "..", "html", "角色成长档案.html")
open(out, "w", encoding="utf-8").write(t)
open(os.path.join(OUT_DIR, "growth-detail.html"), "w", encoding="utf-8").write(t)
print(len(t))
