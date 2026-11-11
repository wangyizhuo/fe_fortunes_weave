#!/bin/bash
# 一条命令重建全部：规则都在 run_plans.py / planner.py（数据在 *.json），这里按顺序生成所有输出。
# 用法：bash build.sh（生成的网页默认放仓库根目录 out/，可用 FE_OUT_DIR 改）   （网络盘偶尔 I/O 错，每步自动重试 3 次；最后一步 make_html 自带排版检查）
cd "$(dirname "$0")"
for s in make_sheet make_detail make_summary make_choices make_longview plan45 make_html; do
  for i in 1 2 3; do python3 $s.py > /tmp/build_$s.log 2>&1 && break; sleep 1; done || { echo "失败：$s"; tail -5 /tmp/build_$s.log; exit 1; }
  echo "ok $s"
done
tail -2 /tmp/build_make_html.log
