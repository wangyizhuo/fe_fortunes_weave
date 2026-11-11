"""给主表「成长路线」生成格式请求（Sheets batchUpdate），存为 fmt_req.json。列布局见 make_sheet.py。"""
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))  # 一次性脚本放在 tools/，数据和模块在上一层
_os.chdir(_sys.path[0])
import json
import re

SID = 313323284
rows = json.load(open("sheet_rows.json", encoding="utf-8"))["routes"]
N, C = len(rows), len(rows[0])          # C = 19
STAT0, SCORE = 6, 15                    # HP..魅 = 列 6-14，加权分 = 15


def rgb(h):
    return {k: round(int(h[j:j + 2], 16) / 255, 3) for k, j in (("red", 0), ("green", 2), ("blue", 4))}


def rng(r0, r1, c0, c1):
    return {"sheetId": SID, "startRowIndex": r0, "endRowIndex": r1, "startColumnIndex": c0, "endColumnIndex": c1}


def cell(r0, r1, c0, c1, fmt, fields):
    return {"repeatCell": {"range": rng(r0, r1, c0, c1), "cell": {"userEnteredFormat": fmt}, "fields": fields}}


def width(c, px):
    return {"updateDimensionProperties": {"range": {"sheetId": SID, "dimension": "COLUMNS", "startIndex": c, "endIndex": c + 1},
                                          "properties": {"pixelSize": px}, "fields": "pixelSize"}}


req = [
    {"unmergeCells": {"range": rng(0, 200, 0, C)}},
    cell(0, 200, 0, C, {}, "userEnteredFormat"),
    cell(0, N, 0, C, {"verticalAlignment": "MIDDLE", "textFormat": {"fontSize": 10}, "wrapStrategy": "CLIP"},
         "userEnteredFormat(verticalAlignment,textFormat,wrapStrategy)"),
    cell(0, N, 1, SCORE + 1, {"horizontalAlignment": "CENTER"}, "userEnteredFormat.horizontalAlignment"),
    cell(0, N, 5, 6, {"horizontalAlignment": "LEFT", "wrapStrategy": "WRAP", "textFormat": {"fontSize": 9, "foregroundColor": rgb("555555")}},
         "userEnteredFormat(horizontalAlignment,wrapStrategy,textFormat)"),
    cell(0, N, SCORE + 1, C, {"wrapStrategy": "WRAP"}, "userEnteredFormat.wrapStrategy"),
    cell(1, N, 4, 5, {"textFormat": {"bold": True}}, "userEnteredFormat.textFormat.bold"),
    cell(0, 1, 0, C, {"backgroundColor": rgb("374750"), "horizontalAlignment": "CENTER", "wrapStrategy": "WRAP",
                      "textFormat": {"bold": True, "foregroundColor": rgb("FFFFFF")}},
         "userEnteredFormat(backgroundColor,horizontalAlignment,wrapStrategy,textFormat)"),
    {"updateSheetProperties": {"properties": {"sheetId": SID, "gridProperties": {"frozenRowCount": 1, "frozenColumnCount": 3}},
                               "fields": "gridProperties(frozenRowCount,frozenColumnCount)"}},
]
for c, px in [(0, 110), (1, 36), (2, 62), (3, 86), (4, 76), (5, 150), (SCORE, 56), (16, 250), (17, 300), (18, 320)]:
    req.append(width(c, px))
for c in range(STAT0, SCORE):
    req.append(width(c, 34))

for i, r in enumerate(rows[1:], start=1):
    if r[0] and not r[1] and r[2] != "合计":        # 角色标题行
        req += [cell(i, i + 1, 0, C, {"backgroundColor": rgb("C5CAE9"), "textFormat": {"bold": True}, "wrapStrategy": "WRAP"},
                     "userEnteredFormat(backgroundColor,textFormat,wrapStrategy)"),
                # 冻结列和非冻结列不能合并，所以角色名用「溢出」显示，不合并
                cell(i, i + 1, 0, 1, {"textFormat": {"bold": True, "fontSize": 12}, "wrapStrategy": "OVERFLOW_CELL"},
                     "userEnteredFormat(textFormat,wrapStrategy)"),
                {"mergeCells": {"range": rng(i, i + 1, 6, SCORE + 1), "mergeType": "MERGE_ALL"}},
                {"updateDimensionProperties": {"range": {"sheetId": SID, "dimension": "ROWS", "startIndex": i, "endIndex": i + 1},
                                               "properties": {"pixelSize": 44}, "fields": "pixelSize"}}]
    elif r[3] == "跳过（考试）":
        req.append(cell(i, i + 1, 0, C, {"backgroundColor": rgb("FFF3E0"), "textFormat": {"italic": True}},
                        "userEnteredFormat(backgroundColor,textFormat)"))
    elif r[2] == "合计":
        req.append(cell(i, i + 1, 0, C, {"backgroundColor": rgb("ECEFF1"), "textFormat": {"bold": True},
                                         "borders": {"top": {"style": "SOLID_MEDIUM", "color": rgb("607D8B")}}},
                        "userEnteredFormat(backgroundColor,textFormat,borders)"))

# 各角色的步骤行连成一块（标题行、合计行除外），条件格式用块范围，减少请求大小
blocks, start = [], None
for i, r in enumerate(rows + [["", "", "", ""]]):
    step_row = bool(r[1]) and i > 0
    if step_row and start is None:
        start = i
    if not step_row and start is not None:
        blocks.append((start, i)); start = None
req.append({"addConditionalFormatRule": {"index": 0, "rule": {"ranges": [rng(a, b, STAT0, SCORE) for a, b in blocks], "booleanRule": {
    "condition": {"type": "NUMBER_GREATER_THAN_EQ", "values": [{"userEnteredValue": "1"}]},
    "format": {"backgroundColor": rgb("C8E6C9"), "textFormat": {"bold": True, "foregroundColor": rgb("1B5E20")}}}}}})
req.append({"addConditionalFormatRule": {"index": 1, "rule": {"ranges": [rng(a, b, SCORE, SCORE + 1) for a, b in blocks], "gradientRule": {
    "minpoint": {"color": rgb("F8BBD0"), "type": "NUMBER", "value": "6"},
    "midpoint": {"color": rgb("FFFFFF"), "type": "NUMBER", "value": "14"},
    "maxpoint": {"color": rgb("81C784"), "type": "NUMBER", "value": "22"}}}}})
def expand(m):
    return ",".join(f"{m.group(1)}.{f}" for f in m.group(2).split(","))


for r in req:                           # 字段掩码不用括号写法（接口不认）
    for v in r.values():
        if "fields" in v:
            v["fields"] = re.sub(r"(\w+)\(([^)]*)\)", expand, v["fields"])
json.dump(req, open("fmt_req.json", "w"), ensure_ascii=False, separators=(",", ":"))
print(len(req))
