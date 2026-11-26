# FE 万紫千红（Fortune's Weave）模块化养成规划台

按三大功能清晰分模块，**纯配置数据 / 纯业务逻辑 / 数据生成 / 静态前端**彻底解耦，核心逻辑前后端均可单元测试。

## 三大功能模块

| 模块 | 纯配置 / 原始数据 | Python 纯业务逻辑 | 独立数据产物 | 前端纯核心逻辑（零 DOM） | 前端视图 |
|---|---|---|---|---|---|
| **友好度培养** | `meals/meal_config.json`, `meals/diet_tab.json` | `modules/affinity/` | `out/data/affinity.json` | `web/js/core/affinity_logic.js` | `web/js/views/affinity_view.js` |
| **道具 / 材料采集** | `config/items_config.json`, `dietrich/shops-src/weapons.tsv` | `modules/items/` | `out/data/items.json` | `web/js/core/items_logic.js` | `web/js/views/items_view.js` |
| **路线规划** | `config/route_config.json`, `levelup/rng/*.json` | `modules/route/`, `levelup/rng/` | `out/data/route.json` | `web/js/core/route_logic.js` | `web/js/views/route_views.js` |

## 目录概览
- `config/`：抽离出的纯 JSON 配置文件（`route_config.json`、`items_config.json`）
- `modules/`：按三大功能拆分的 Python 纯业务模块（无 HTML/DOM 耦合）
- `web/`：解耦的前端静态应用（`index.html`、`styles.css`、`js/core/`、`js/state/`、`js/views/`、`js/app.js`、`tests/`）
- `build_site.py`：分离式网站构建器（`--data-only` 只重算三大模块 JSON；`--web-only` 只部署前端静态文件）
- `levelup/rng/`：RNG 成长机制（`fe_growth.py`）、规划算法（`planner.py`）、38 项自动检查（`checks.py`）与构建管线（`build.sh`）
- `data/`：每个角色自动导出的可读 `.json` / `.md` 副本
- `AGENTS.md` & `.agents/skills/`：面向 AI Agent 与开发者的架构铁律、模块边界和防回归操作指南
- `docs/ARCHITECTURE.md` & `docs/检查规则.md`：系统架构与检查项说明

## 常用命令
```bash
# 1. 前端纯逻辑单元测试（Node.js 内置 test runner，无需安装依赖）
node --test web/tests/*.test.js

# 2. Python 三大模块与架构单元测试
python3 -m unittest discover -s tests -v

# 3. 完整构建（中间 JSON + 三大模块数据 + 前端部署 + data/ 导出 + 38 项自动检查）
bash levelup/rng/build.sh

# 4. 快速单独构建
python3 build_site.py --data-only   # 只重新生成 out/data/*.json
python3 build_site.py --web-only    # 只部署 web/ 静态资源（<0.1s）
python3 levelup/rng/checks.py       # 只跑 38 项自动检查
```

需要 Python 3.10+ 与 Node.js 18+（排版检查 `check_layout.js` 额外需要 Playwright）。
