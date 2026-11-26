---
name: fe-affinity-meals
description: 修改万紫千红的友好度培养、吃饭三人组合配置、已招/满好感/支援达标状态时使用。
---

# 友好度培养模块修改指南（fe-affinity-meals）

## 职责边界
- **纯配置数据**：`meals/meal_config.json`、`meals/diet_tab.json`
- **纯业务算法**：`modules/affinity/planner.py`、`modules/affinity/service.py`（`meals/meal_planner.py` 为兼容 CLI 入口）
- **前端核心与视图**：`web/js/core/affinity_logic.js`、`web/js/views/affinity_view.js`

## 规则守则
1. Perfect 判定固定为：无人讨厌（`min(pref) > 0`），且三人闪光（`pref - 1`）为 `1+1+1` 或 `2+2+0`。
2. `compute_pair_weights()` 必须保持纯函数，返回 `(weights, need)`，禁止引入全局或函数属性状态。
3. 所有人员状态变更（`recruited`、`maxed`、`absent`、`pairs_done`、`goals`）只改 `meals/meal_config.json`。

## 验证命令
```bash
python3 meals/meal_planner.py
python3 build_site.py --data-only
python3 -m unittest discover -s tests -v
node --test web/tests/affinity_logic.test.js
python3 levelup/rng/checks.py D8 A3
```
