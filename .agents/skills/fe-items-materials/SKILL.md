---
name: fe-items-materials
description: 更新万紫千红的城镇商店物品、范达尔商会以物易物或采集/钓鱼材料反查数据时使用。
---

# 道具 / 材料采集模块修改指南（fe-items-materials）

## 职责边界
- **纯配置与原始表**：`config/items_config.json`、`dietrich/shops-src/weapons.tsv`
- **纯业务逻辑**：`modules/items/catalog.py`、`modules/items/service.py`（`dietrich/shops-src/build.py` 为 CSV 导出入口）
- **前端核心与视图**：`web/js/core/items_logic.js`、`web/js/views/items_view.js`

## 修改规范
1. 新增商店非武器道具、翻译映射、地名或以物易物戒指 → 只改 `config/items_config.json`。
2. 新增武器行 → 追加到 `dietrich/shops-src/weapons.tsv`，并确保 `config/items_config.json` 的 `weaponNames` 和 `towns` 已包含对应日文键。
3. 以物易物的材料字段需遵循 `材料名x数量`（多项用逗号分隔），以便 `parse_materials()` 自动生成「采集材料反查表」。

## 验证命令
```bash
python3 dietrich/shops-src/build.py
python3 build_site.py --data-only
python3 -m unittest discover -s tests -v
node --test web/tests/items_logic.test.js
```
