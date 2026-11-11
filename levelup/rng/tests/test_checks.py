"""把 checks.py 的每一项自动检查当成一个测试跑（页面类检查需要先 build 出 page_data.json，没有就跳过）。"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import checks  # noqa: E402


@pytest.mark.parametrize("cid,desc,fn", checks.CHECKS, ids=[c[0] for c in checks.CHECKS])
def test_check(cid, desc, fn):
    if cid.startswith("U") and checks.page() is None:
        pytest.skip("还没 build 出页面数据")
    problems = fn()
    assert not problems, f"{cid} {desc}:\n" + "\n".join(problems[:20])
