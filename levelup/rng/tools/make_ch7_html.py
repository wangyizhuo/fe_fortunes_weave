import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))  # 一次性脚本放在 tools/，数据和模块在上一层
_os.chdir(_sys.path[0])
import json, os
OUT_DIR = os.environ.get("FE_OUT_DIR") or os.path.join(_sys.path[0], "..", "..", "out")   # 生成的网页放这里
os.makedirs(OUT_DIR, exist_ok=True)
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = json.load(open(os.path.join(HERE, "ch7.json"), encoding="utf-8"))
ST = ["HP", "力", "魔", "速", "技", "防", "魔防", "幸", "魅"]
SHORT = {"迪托利希": "迪", "法毕欧": "法毕欧", "艾丝梅拉尔达": "艾丝", "米迦艾拉": "米迦", "杨界": "杨界", "伊欧": "伊欧", "奇洛伊卡": "奇洛"}
# 结论（人写）
VERDICT = {
    "杨界": ("值得重开", "多 +45 分（81 点 vs 70 点），但要考 6 次（原来 1 次，其中跳过 4 次）。Lv17、22 用平民，Lv23 考萨满巫师、Lv26 考牧师，后面主用牧师：技 +3，魔、速、魅各 +2。"),
    "法毕欧": ("值得重开", "多 +22 分，但要考 7 次（跳过 5 次）；同样考 3 次只 +8。Lv15 连跳 3 次、Lv23 考牧师、Lv30 考萨满巫师，后面主用牧师：速 +3、魔防 +3、幸 +2、魅 +2，魔少 1。"),
    "艾丝梅拉尔达": ("可以重开", "多 +12 分，考 7 次（原来 6 次）；同样 6 次只 +2。Lv16 考斗士、Lv19 重装步兵、Lv20 骑甲鸵兵，之后主用重装步兵：防 +3，魔、魅各少 1。重装步兵 45.53、骑甲鸵兵 45.6 两场判定值偏高，技能要够。"),
    "米迦艾拉": ("可以重开", "多 +9 分（和现在要考重装的路线比），考试次数一样：HP、速、防各 +1，力少 1。"),
    "伊欧": ("差别很小", "多 +3 分，考试次数一样。Lv25 才考战车兵、Lv27 考剑客，轻骑兵用得多：魔防 +1、幸 −1。"),
    "迪托利希": ("不用重开", "只多 +1 分，路线几乎一样（剑客到 Lv31、考恶棍）。"),
    "奇洛伊卡": ("不用重开", "重排反而 −3 分（现在的路线从 Lv17 重新规划后已经更好），保持原路线。"),
}
ORDER = ["杨界", "法毕欧", "艾丝梅拉尔达", "米迦艾拉", "伊欧", "迪托利希", "奇洛伊卡"]
for n in ORDER:
    D[n]["verdict"] = VERDICT[n]
data = json.dumps({"order": ORDER, "chars": D, "st": ST, "short": SHORT}, ensure_ascii=False)
html = open(os.path.join(HERE, "ch7_template.html"), encoding="utf-8").read().replace("/*DATA*/{}", data)
open(os.path.join(OUT_DIR, "ch7-plan.html"), "w", encoding="utf-8").write(html)
os.makedirs(os.path.join(HERE, "..", "html"), exist_ok=True)
open(os.path.join(HERE, "..", "html", "第七章重开规划.html"), "w", encoding="utf-8").write(html)
print(len(html))
