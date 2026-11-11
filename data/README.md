# 数据（自动导出，只读）

由 `levelup/rng/export_data.py` 生成，`bash levelup/rng/build.sh` 最后会自动更新；
改数据请改 `levelup/rng/` 下的源文件（current_stats.json、run_plans.py 等，见 docs/ARCHITECTURE.md）。
`python3 levelup/rng/checks.py` 的 D5～D8 会检查这里是不是最新、种子链是否连续、能力和技能是否合理。

| 角色 | 优先级 | 规划起点 | 截图职业 | Lv35 加权分 | Lv45 加权分 |
|---|---|---|---|---|---|
| [迪托利希](characters/迪托利希.md) | P0 | Lv25 | 剑客 | 180 | 342 |
| [法毕欧](characters/法毕欧.md) | P0 | Lv22 | 诅咒师 | 173 | 307 |
| [艾丝梅拉尔达](characters/艾丝梅拉尔达.md) | P0 | Lv21 | 天翼兵 | 231 | 405 |
| [米迦艾拉](characters/米迦艾拉.md) | P0 | Lv22 | 斗士 | 224 | 351 |
| [杨界](characters/杨界.md) | P1 | Lv21 | 诅咒师 | 211 | 417 |
| [伊欧](characters/伊欧.md) | P0 | Lv23 | 战车兵 | 207 | 372 |
| [奇洛伊卡](characters/奇洛伊卡.md) | P1 | Lv17 | 猎兵 | 255 | 397 |
| [努蒂奴](characters/努蒂奴.md) | P2 | Lv17 | 飞鸵兵 | 217 | 373 |
| [乌尔坦德](characters/乌尔坦德.md) | P2 | Lv18 | 诅咒师 | 252 | 397 |

- `characters/<角色>.json / .md`：种子、观星记录（过去的成长）、等级、职业、能力、技能、权重、规划、吃饭喜好
- `classes.json`：职业数据和可考清单；`rules.json`：优先级、跳过条件等规则常数
- 装备、友好度：目前程序和表格里都没有，字段留空（null）待补
