# AGENTS.md — 万紫千红（fe_fortunes_weave）工程开发与架构守则

本仓库是《火焰纹章：万紫千红》（Fortune's Weave）的养成工具集。所有 Agent 与开发者在改动任何代码或数据前，**必须遵守以下架构边界与验证流程**。

---

## 1. 三大功能模块边界（严禁混写）

仓库按功能清晰划分为三个独立业务模块，前后端一一对应：

| 功能模块 | 纯配置 / 原始数据 | Python 纯业务逻辑 | 独立构建产物 | 前端纯核心逻辑（零 DOM） | 前端视图渲染 |
|---|---|---|---|---|---|
| **友好度培养** | `meals/meal_config.json`, `meals/diet_tab.json` | `modules/affinity/` | `out/data/affinity.json` | `web/js/core/affinity_logic.js` | `web/js/views/affinity_view.js` |
| **道具 / 材料采集** | `config/items_config.json`, `dietrich/shops-src/weapons.tsv` | `modules/items/` | `out/data/items.json` | `web/js/core/items_logic.js` | `web/js/views/items_view.js` |
| **路线规划** | `config/route_config.json`, `levelup/rng/*.json`, `levelup/观星凹点模拟备份-导入.json` | `modules/route/`, `levelup/rng/{fe_growth,planner,run_plans}.py` | `out/data/route.json` | `web/js/core/route_logic.js` | `web/js/views/route_views.js` |

---

## 2. 六条不可违反的工程铁律

1. **数据与逻辑分离**：
   - 角色优先级、已有/必考/排除职业、特批训练、跳过条件、商店翻译、以物易物配置等**必须写在 `config/*.json` 或 `meals/meal_config.json`**，禁止把配置表硬编码回 `.py` 文件。
   - 已有职业必须以 `config/route_config.json`（`owned`）为**唯一数据源**，禁止在视图层或导出脚本中打 `CUR_CLASS_EXTRA` 类补丁。
2. **网页生成逻辑与数据分离**：
   - `build_site.py --data-only` 只负责生成 `out/data/*.json`（及 `file://` 回退用 `out/data/bundle_data.js`）。
   - `build_site.py --web-only` 只负责拷贝纯静态前端 `web/` 到 `out/`，**不得依赖任何 Python 规划算法**。
   - `web/index.html` 必须是标准 HTML5（含 `<!DOCTYPE html>`、`<meta charset="utf-8">`、`<meta name="viewport">`），**禁止把 JSON 数据内联进 HTML**（禁止 `/*ROUTE_DATA*/` 占位符）。
3. **核心逻辑脱离 HTML/DOM，且必须可单元测试**：
   - 前端计算逻辑（步进推演 `walk`、体格加分 `remain`、过滤、反查、表格导出等）必须放在 `web/js/core/*.js`，**严禁出现 `document.`、`localStorage`、`innerHTML`、`addEventListener`**（由 `checks.py` 的 `A2` 强制拦截）。
   - 每个 `web/js/core/*.js` 文件都必须使用 UMD 导出，并在 `web/tests/*.test.js` 中配有 Node.js 单元测试。
4. **前端文案由数据驱动，禁止硬编码会过时的规则**：
   - 优先级名单、截图快照标识、名声等级、跳过规则说明等，必须从 `route.json` 的 `rulesMeta` 动态读取渲染，禁止在 HTML/JS 中手写诸如 `11-05 截图`、`法毕欧在 P0`、`不再要求中级` 等易过时文字。
5. **保持净值与成功率判定口径唯一**：
   - 净值统一调用 `Planner.plan_net(...)`（含保底分、手形金币与训练扣分），不要在外部脚本重写 `total - gold / gpp`。
   - 考试通过判定统一调用 `Planner.exam_ok(...)`，禁止用四舍五入后的百分比字符串比较。
6. **禁止污染全局状态与隐式副作用**：
   - 禁止在外部脚本中原地修改 `run_plans.EXAM_CHANCE` / `REQUIRED` / `EXAM_OPTIONS` 等模块全局字典。
   - 禁止用函数属性（如 `fn.attr = ...`）替代返回值；所有核心函数保持纯函数或显式参数传递。
   - `decisions.json` 的代码引用字段统一规范（`checks.py` `D4` 会同时校验 `where` 与 `code`）。

---

## 3. 配套项目 Skills（按任务选用）

详见 `.agents/skills/` 目录：
- `fe-route-planning`：修改路线规则、录入新截图/种子、核对 golden diff 的标准流程。
- `fe-affinity-meals`：修改吃饭配置、招募/支援状态与验证 perfect 组合的标准流程。
- `fe-items-materials`：维护城镇商店、以物易物与材料反查数据的标准流程。
- `fe-web-architecture`：修改前端页面、拆分核心 JS 逻辑与执行前后端分离构建的标准流程。

---

## 4. 提交 / 发布前必须全部通过的验证清单

每次修改后，**必须**在仓库根目录按顺序运行并确认全部通过：

```bash
# 1. 前端纯逻辑单元测试（Node.js 内置 test runner，零外部依赖）
node --test web/tests/*.test.js

# 2. Python 三大模块单元测试 + 全链路逻辑完整性 + 真实 Chromium 浏览器 E2E 校验
python3 -m unittest discover -s tests -v

# 3. 完整重建数据与网页（改了规则/数据需先重跑 levelup/rng/build.sh；只改前端只需 --web-only）
python3 build_site.py

# 4. 全部自动检查（D 数据 / P 规划 / U 页面 / E 公式 / A 架构守卫 / G 快照）
python3 levelup/rng/checks.py
```

若有意修改了规划规则导致 `G1` 快照变化：
1. 必须先核对 `checks.py` 输出的逐角色收益/成本 diff（按同样多的乱数窗口比较，点数/加权分/金币/训练分开报告）。
2. 在 `levelup/rng/decisions.json` 追加记录（包含 `date`、`scope`、`rule`、`where`）。
3. 确认无误后执行 `python3 levelup/rng/checks.py --update-golden` 并重跑 `python3 levelup/rng/export_data.py`。
