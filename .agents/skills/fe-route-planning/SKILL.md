---
name: fe-route-planning
description: 修改火焰纹章万紫千红的成长路线规划规则、录入新截图/种子或排查路线差异时使用。
---

# 路线规划模块修改指南（fe-route-planning）

## 职责边界
- **纯配置数据**：`config/route_config.json`、`levelup/rng/current_stats.json`、`levelup/rng/weights.json`、`levelup/rng/exam_chance.json`、`levelup/rng/decisions.json`
- **纯规划逻辑**：`levelup/rng/fe_growth.py`、`levelup/rng/planner.py`、`levelup/rng/run_plans.py`
- **数据服务层**：`modules/route/config_loader.py`、`modules/route/service.py`

## 修改步骤
1. **改数据先改 JSON**：
   - 角色优先级（P0/P1/P2）、已有职业 `owned`、必考 `required`、排除 `exclude`、特批训练 `trainCase`、保留种子 `noSkipSeeds`、名声 `renown` → 一律只改 `config/route_config.json`。
   - 新截图等级/能力/技能/观星 `seed_index` → 改 `levelup/rng/current_stats.json`。
2. **改规则必须记录决定**：
   - 在 `levelup/rng/decisions.json` 末尾追加记录，字段为 `date`、`scope`、`rule`、`where`（指向真实存在的 `模块.符号`）。
3. **避免历史踩坑**：
   - 不要新增 `CUR_CLASS_EXTRA` 类补丁；`owned` 唯一来源是 `config/route_config.json`。
   - `make_options.planner(..., train=True)` 必须给所有仍有技能差的职业补齐训练并移除旧 `exam_chance`，不能被 `TRAIN_CASE` 短路。
   - 比较路线必须使用同样多的乱数窗口，向用户报告时**点数、加权分、金币、训练段数必须分开列**。
4. **重建与验证**：
   ```bash
   bash levelup/rng/build.sh
   python3 -m unittest discover -s tests -v
   node --test web/tests/route_logic.test.js
   ```
   若规则有意变动导致 `G1` 报 diff，先向用户展示 diff，确认后再运行 `python3 levelup/rng/checks.py --update-golden` 并同步 `python3 levelup/rng/export_data.py`。
