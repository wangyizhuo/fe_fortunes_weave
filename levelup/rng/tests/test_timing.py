"""timing.py：计时记录能写、能汇总（11-26 构建计时）。"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_timing_log_and_summary(tmp_path):
    log = tmp_path / "t.jsonl"
    code = "import timing\nwith timing.timed('a'):\n    pass\ntiming.count('n', 3)\n"
    env = dict(os.environ, FE_TIMING_LOG=str(log))
    subprocess.run([sys.executable, "-c", code], cwd=HERE, env=env, check=True)
    rows = [json.loads(x) for x in log.read_text(encoding="utf-8").splitlines()]
    labels = {r["label"] for r in rows}
    assert {"a", "#n", "总时间"} <= labels
    sys.path.insert(0, HERE)
    import timing
    out = timing.summary(str(log))
    assert "总时间" not in out.splitlines()[0] and "a" in out
