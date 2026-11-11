# FE 万紫千红（Fortune's Weave）养成规划程序

按游戏的升级种子（Xorshift128）推算每一级、每个职业的加点，按规则自动规划每个角色到 Lv35 / Lv45 的转职、考试和跳过，并生成网页。

## 目录
- `levelup/rng/` 主程序
  - `fe_growth.py` 升级和考试判定（种子 → 加点）
  - `planner.py` 规划算法（逐级选职业、跳过条件、考试选择、净值）
  - `run_plans.py` 规则和角色数据配置（权重、优先级、可考职业、必考、跳过条件、考前训练）
  - `make_*.py` 生成各个输出；`app_template.html` 网页模板；`check_layout.js` 排版检查
  - `decisions.json` 已经定下的规则记录
  - `tests/` 规则测试
  - `csolve/` 反推种子的工具
- `levelup/rules/` 规则文档
- `meals/` 吃饭组合；`dietrich/shops-src/` 迪线商店表

## 用法
```bash
cd levelup/rng
python3 -m pytest -q tests        # 测试（约 2 秒）
bash build.sh                     # 全部重建，网页输出到仓库根目录 out/（FE_OUT_DIR 可改）
python3 run_plans.py 迪托利希 --to 35   # 单个角色打印路线
```
需要 Python 3.10+；排版检查需要 Node 和 Playwright。
