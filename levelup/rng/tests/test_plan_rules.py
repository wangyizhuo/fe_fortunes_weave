"""规划规则的测试（11-11 起用 TDD 改规则）。运行：cd levelup/rng && python3 -m pytest -q tests"""
import os, sys, functools
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pytest
from run_plans import make_planner, EXAM_OPTIONS, PERMIT_GOLD
from make_sheet import TARGET, MAX_EXAMS
from planner import plan_all

NAMES = list(EXAM_OPTIONS)


@functools.lru_cache(None)
def plan(name):
    p = make_planner(name, TARGET[name])
    pls, k = plan_all(p, MAX_EXAMS)
    return p, pls[k]


def exams(pl):
    return [r.cls for r in pl.rows if r.action != "升级"]


# ---- 11-11 Yizhuo：考前要练技能的考试，训练也有成本 ----

def test_training_has_a_cost_per_rank():
    p, _ = plan("米迦艾拉")
    assert p.exam_train_ranks["诅咒师"] == 2      # 黑魔术 E→E+→D（段按游戏的 + 级算）
    assert p.exam_train_ranks["弓箭手"] == 2      # 箭术 D→D+→C
    assert "剑客" not in p.exam_train_ranks       # 剑术够，不用练


def test_mika_does_not_train_for_curse_mage():
    """米迦 Lv33 考诅咒师只多 魔+1（权重 1），不值得为它练黑魔术。"""
    _, pl = plan("米迦艾拉")
    assert "诅咒师" not in exams(pl)


def test_archer_break_even_follows_training_cost():
    """弓箭手（中级 500G、练箭术 2 段）比猎兵（初级 300G、不用练）多 5 加权分。
    多花 200G = 3.2 分，所以每段训练成本 < 0.9 分时考弓箭手，> 0.9 分时考猎兵。"""
    p = make_planner("米迦艾拉", TARGET["米迦艾拉"])
    for cost, want in ((0.5, "弓箭手"), (1.5, "猎兵")):
        p.TRAIN_PTS_PER_RANK = cost
        assert want in exams(plan_all(p, MAX_EXAMS)[0][plan_all(p, MAX_EXAMS)[1]]), cost


@pytest.mark.parametrize("name", NAMES)
def test_every_trained_exam_pays_for_its_training(name):
    """路线里每个要先练技能的考试：去掉它（改成按规则走），净值不能更高。"""
    p, pl = plan(name)
    for c in set(exams(pl)) & set(p.exam_train_ranks):
        others = [t for t in pl.targets if t != c]
        alt = p.rule_run(others)
        assert p.plan_net(pl.raw_actions, pl.total, pl.gold) >= p.plan_net(alt[0], alt[2], alt[3]) - 1e-6, c


@pytest.mark.parametrize("name", NAMES)
def test_every_exam_class_is_used(name):
    """考进的新职业至少用来升一级，否则应该显示成跳过。"""
    p, pl = plan(name)
    used = {r.cls for r in pl.rows if r.action == "升级"}
    for c in exams(pl):
        assert c == "跳过" or c in used or c in p.required, c


@pytest.mark.parametrize("name", NAMES)
def test_plan_reaches_target_level(name):
    p, pl = plan(name)
    assert sum(r.action == "升级" for r in pl.rows) == TARGET[name] - p.level
