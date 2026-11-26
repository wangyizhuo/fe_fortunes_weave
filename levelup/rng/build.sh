#!/bin/bash
# 一条命令重建全部：规则都在 run_plans.py / planner.py（数据在 *.json），这里生成所有输出，最后跑自动检查。
# 用法：bash build.sh（生成的网页默认放仓库根目录 out/，可用 FE_OUT_DIR 改）
# 网络盘偶尔 I/O 错，每步自动重试 3 次；make_html 自带排版检查；checks.py 任何一项不过 → 退出码 1，不要发布。
#
# 11-26 提速 + 计时（Yizhuo：每一步都要快，要有 instrumentation）：
#   互不依赖的步骤并行跑（4 组），每步计时；结束时打印每个脚本、每个人、每项检查花了多久。
#   计时记录：$LOG/build_timings.jsonl（每行一条 JSON，见 timing.py），每次构建另外追加一行总结到输出目录的 build_history.tsv。
#   只跑某几步：bash build.sh make_options make_html（不跑检查）
cd "$(dirname "$0")"
LOG=${TMPDIR:-/tmp}
export FE_TIMING_LOG=$LOG/build_timings.jsonl
: > "$FE_TIMING_LOG"
T0=$(date +%s.%N)
mkdir -p "${FE_OUT_DIR:-../../out}"
STEPS_LOG=$LOG/build_steps.tsv
: > "$STEPS_LOG"

now() { date +%s.%N; }
# 跑一步：重试 3 次，记录秒数
step() {
  local s=$1 a b i
  a=$(now)
  for i in 1 2 3; do python3 $s.py > $LOG/build_$s.log 2>&1 && break; sleep 1; done || { echo "失败：$s"; tail -5 $LOG/build_$s.log; return 1; }
  b=$(now)
  printf "%s\t%.1f\n" "$s" "$(echo "$b - $a" | bc)" >> "$STEPS_LOG"
  printf "ok %-14s %6.1fs\n" "$s" "$(echo "$b - $a" | bc)"
}
# 一组按顺序跑（组内有依赖）
chain() { local s; for s in "$@"; do step $s || return 1; done; }

if [ $# -gt 0 ]; then chain "$@"; exit $?; fi

# 依赖：make_detail → detail.json → make_summary / make_choices；make_options → make_reasons；make_html / export_data 要全部 json
chain make_detail make_summary make_choices & P1=$!
chain plan45 & P2=$!
chain make_options make_reasons & P3=$!   # make_reasons 读 options.json
chain make_sheet make_longview & P4=$!
fail=0
for p in $P1 $P2 $P3 $P4; do wait $p || fail=1; done
[ $fail = 0 ] || { echo "有步骤失败，停止"; exit 1; }
# make_html 和 export_data 都要全部 json（export_data 读 plan45/reasons），互不依赖 → 并行；export_data 要在 checks 前（D5 比对 data/）
chain make_html & H1=$!
chain export_data & H2=$!
wait $H1 || exit 1
wait $H2 || exit 1
tail -2 $LOG/build_make_html.log
a=$(now)
python3 checks.py; rc=$?
printf "checks\t%.1f\n" "$(echo "$(now) - $a" | bc)" >> "$STEPS_LOG"
TOTAL=$(echo "$(now) - $T0" | bc)
echo
echo "==== 计时（总 $(printf %.1f $TOTAL) 秒，并行；下面是每个脚本自己的时间） ===="
python3 timing.py "$FE_TIMING_LOG"
printf "%s\t%.1f\t%s\n" "$(date -u +%FT%TZ)" "$TOTAL" "$(paste -sd' ' "$STEPS_LOG" | tr '\t' '=')" >> "${FE_OUT_DIR:-../../out}/build_history.tsv"
[ $rc = 0 ] || { echo "自动检查没通过：先修好再发布（规则有意改了就 python3 checks.py --update-golden）"; exit 1; }
