#!/bin/bash
# 一条命令重建全部：
#   1) 并行生成各中间分析 JSON（detail/summary/choices/plan45/options/reasons/sheet/longview）
#   2) build_site.py 分离输出三大模块数据（out/data/*.json）与纯前端资源（web/ -> out/）
#   3) export_data.py 导出可读 data/
#   4) 跑自动检查（checks.py）+ 前后端单元测试（Python unittest + Node.js web/tests）
#
# 不再依赖 bc（改用 python3 算耗时）；只跑前端部署可用：python3 ../../build_site.py --web-only
set -o pipefail
cd "$(dirname "$0")"
ROOT="$(cd ../.. && pwd)"
LOG=${TMPDIR:-/tmp}
export FE_TIMING_LOG=$LOG/build_timings.jsonl
: > "$FE_TIMING_LOG"
T0=$(python3 -c 'import time; print(time.perf_counter())')
mkdir -p "${FE_OUT_DIR:-$ROOT/out}"
STEPS_LOG=$LOG/build_steps.tsv
: > "$STEPS_LOG"

now() { python3 -c 'import time; print(time.perf_counter())'; }
elapsed() { python3 -c "print(f'{$2 - $1:.1f}')"; }

step() {
  local s=$1 a b i dt ok=0
  a=$(now)
  for i in 1 2 3; do
    if python3 "$s.py" > "$LOG/build_$s.log" 2>&1; then ok=1; break; fi
    sleep 1
  done
  if [ "$ok" != 1 ]; then
    echo "失败：$s"
    tail -15 "$LOG/build_$s.log"
    return 1
  fi
  b=$(now)
  dt=$(elapsed "$a" "$b")
  printf "%s\t%s\n" "$s" "$dt" >> "$STEPS_LOG"
  printf "ok %-14s %6ss\n" "$s" "$dt"
}
chain() { local s; for s in "$@"; do step "$s" || return 1; done; }

if [ $# -gt 0 ]; then chain "$@"; exit $?; fi

chain make_detail make_summary make_choices & P1=$!
chain plan45 & P2=$!
chain make_options make_reasons & P3=$!
chain make_sheet make_longview & P4=$!
fail=0
for p in $P1 $P2 $P3 $P4; do wait $p || fail=1; done
[ $fail = 0 ] || { echo "有步骤失败，停止"; exit 1; }

a=$(now)
python3 "$ROOT/build_site.py" > "$LOG/build_site.log" 2>&1 & H1=$!
chain export_data & H2=$!
wait $H1 || { echo "失败：build_site.py"; cat "$LOG/build_site.log"; exit 1; }
wait $H2 || exit 1
cat "$LOG/build_site.log"
printf "build_site\t%s\n" "$(elapsed "$a" "$(now)")" >> "$STEPS_LOG"

a=$(now)
python3 checks.py; rc=$?
printf "checks\t%s\n" "$(elapsed "$a" "$(now)")" >> "$STEPS_LOG"

TOTAL=$(elapsed "$T0" "$(now)")
echo
echo "==== 计时（总 ${TOTAL} 秒，并行）===="
python3 timing.py "$FE_TIMING_LOG"
printf "%s\t%s\t%s\n" "$(date -u +%FT%TZ)" "$TOTAL" "$(paste -sd' ' "$STEPS_LOG" | tr '\t' '=')" >> "${FE_OUT_DIR:-$ROOT/out}/build_history.tsv"
[ $rc = 0 ] || { echo "自动检查没通过：先修好再发布（规则有意改了就 python3 checks.py --update-golden）"; exit 1; }
