"""网页构建兼容入口（薄封装）。

原逻辑已按职责拆分为：
  - 数据层：modules/route/service.py、modules/affinity/service.py、modules/items/service.py
  - 前端层：web/index.html + web/styles.css + web/js/{core,state,views,app}.js
  - 构建器：build_site.py（支持 --data-only / --web-only 分离构建）

直接运行本脚本等价于 python3 ../../build_site.py，并仅在传 --check 且存在 Playwright 时跑排版检查。
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from build_site import DEFAULT_OUT, build_data, build_web  # noqa: E402


def main() -> None:
    out_dir = Path(os.environ.get("FE_OUT_DIR") or DEFAULT_OUT)
    build_data(out_dir)
    build_web(out_dir)
    if "--check" in sys.argv:
        r = subprocess.run(
            ["node", str(HERE / "check_layout.js"), str(out_dir / "growth-route.html")],
            capture_output=True,
            text=True,
        )
        print(r.stdout.strip())
        if r.returncode != 0:
            if r.stderr.strip():
                print(r.stderr.strip(), file=sys.stderr)
            sys.exit("排版自检失败，先修好再发布")


if __name__ == "__main__":
    main()
