import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import meal_planner as mp  # noqa: E402

CFG = json.load(open(os.path.join(os.path.dirname(__file__), "..", "meal_config.json"), encoding="utf-8"))


def test_perfect_rule():
    assert mp.is_perfect([2, 2, 2])          # 1+1+1
    assert mp.is_perfect([1, 3, 3])          # 0+2+2
    assert not mp.is_perfect([1, 2, 3])      # 0+1+2 未确认
    assert not mp.is_perfect([0, 3, 3])      # 讨厌不带
    assert not mp.is_perfect([1, 1, 3])


def test_plan_shape_and_order():
    p = mp.plan(CFG)
    assert len(p["dishes"]) == 12
    out = set(CFG["maxed"]) | set(CFG["absent"])
    for r in p["dishes"]:
        assert r["options"], r["dish"]
        for t in r["options"]:
            assert len(t["who"]) == 3 and len(set(t["who"])) == 3
            assert not out & set(t["who"])
            assert min(t["pref"]) > 0                      # 没人讨厌
            assert all(n in CFG["recruited"] for n in t["filler"])   # 凑数只用已入队的
            assert t["perfect"] == mp.is_perfect(t["pref"])
        assert "露露蒂雅" not in t["who"] or "蕾达" in t["who"]   # 迪线不招
        if r["perfect"]:
            assert all(x["perfect"] for x in r["options"])   # 有 perfect 就不列非 perfect
        # perfect 在前
        flags = [t["perfect"] for t in r["options"][:CFG["options_per_dish"]]]
        assert flags == sorted(flags, reverse=True)
        assert r["perfect"] == r["options"][0]["perfect"]


def test_partner_only_and_goal_coverage():
    p = mp.plan(CFG)
    for r in p["dishes"]:
        for t in r["options"]:
            if "绯亚娜" in t["who"]:
                assert "蕾达" in t["who"]                   # 迪不刷绯亚娜，只和蕾达同桌才有分
    pear = next(r for r in p["dishes"] if r["dish"] == "糖浆炖梨")
    assert pear["options"][0]["perfect"] and pear["options"][0]["score"] >= 5
    assert any("蕾达" in t["who"] and t["perfect"] for t in pear["options"])
    ham = next(r for r in p["dishes"] if r["dish"] == "岩盐火腿")
    assert any(set(t["who"]) == {"绯亚娜", "古扎岚", "蕾达"} and t["perfect"] for t in ham["options"])   # 不用带迪
