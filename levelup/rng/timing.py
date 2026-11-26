"""
构建计时（11-26 Yizhuo：每一步都要快，代码和构建脚本里都要有计时）。

    from timing import timed
    with timed("plan 迪托利希"):          # 计一段代码
        ...
    @timed("make_options.build")           # 或者计一个函数
    def build(...): ...

记录写到环境变量 FE_TIMING_LOG 指定的文件（每行一条 JSON：script、label、秒数、调用次数），
build.sh 会设置它并在最后打印汇总；没设置时只在 FE_TIMING=1 时打印到 stderr，什么都不写。
每个脚本退出时自动记一条「script 总时间」。规划器另外记 _sim 模拟次数（planner.SIM_CALLS），
方便看出「哪个脚本重复模拟了多少遍」。
"""
from __future__ import annotations

import atexit
import functools
import json
import os
import sys
import time
from collections import defaultdict
from contextlib import ContextDecorator

_LOG = os.environ.get("FE_TIMING_LOG")
_ECHO = os.environ.get("FE_TIMING") == "1"
_SCRIPT = os.path.splitext(os.path.basename(sys.argv[0] or "python"))[0] or "python"
_T0 = time.perf_counter()
_TOTALS: dict[str, list[float]] = defaultdict(lambda: [0.0, 0])   # label -> [秒, 次数]
COUNTERS: dict[str, int] = defaultdict(int)                        # 计数器（例如 _sim 次数）


class timed(ContextDecorator):
    """计时：同一个 label 多次调用会累加，退出时每个 label 记一条。"""

    def __init__(self, label: str):
        self.label = label

    def __enter__(self):
        self._t = time.perf_counter()
        return self

    def __exit__(self, *exc):
        dt = time.perf_counter() - self._t
        t = _TOTALS[self.label]
        t[0] += dt
        t[1] += 1
        if _ECHO:
            print(f"[计时] {_SCRIPT} {self.label} {dt:.2f}s", file=sys.stderr)
        return False


def count(name: str, n: int = 1) -> None:
    COUNTERS[name] += n


def _flush():
    if not (_LOG or _ECHO):
        return
    total = time.perf_counter() - _T0
    rows = [{"script": _SCRIPT, "label": k, "sec": round(v[0], 3), "calls": v[1]} for k, v in _TOTALS.items()]
    rows += [{"script": _SCRIPT, "label": f"#{k}", "count": v} for k, v in COUNTERS.items()]
    rows.append({"script": _SCRIPT, "label": "总时间", "sec": round(total, 3), "calls": 1})
    if _LOG:
        try:
            with open(_LOG, "a", encoding="utf-8") as f:
                for r in rows:
                    f.write(json.dumps(r, ensure_ascii=False) + "\n")
        except OSError:
            pass
    if _ECHO:
        print(f"[计时] {_SCRIPT} 总时间 {total:.2f}s", file=sys.stderr)


atexit.register(_flush)


def summary(path: str) -> str:
    """把计时记录汇总成表（build.sh 最后调用：python3 timing.py <log>）。"""
    by_script: dict[str, list[dict]] = defaultdict(list)
    with open(path, encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            by_script[r["script"]].append(r)
    out = []
    order = sorted(by_script, key=lambda s: -next((r["sec"] for r in by_script[s] if r["label"] == "总时间"), 0))
    for s in order:
        rows = by_script[s]
        tot = next((r["sec"] for r in rows if r["label"] == "总时间"), 0)
        out.append(f"{s:<14} {tot:7.1f}s")
        for r in sorted((r for r in rows if "sec" in r and r["label"] != "总时间"), key=lambda r: -r["sec"])[:6]:
            out.append(f"    {r['label']:<28} {r['sec']:7.1f}s  ×{r['calls']}")
        for r in (r for r in rows if "count" in r):
            out.append(f"    {r['label']:<28} {r['count']:>8}")
    return "\n".join(out)


if __name__ == "__main__":
    print(summary(sys.argv[1]))
