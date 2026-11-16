"""规划规则的测试（11-11 起用 TDD 改规则）。运行：cd levelup/rng && python3 -m pytest -q tests"""
import os, sys, functools
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pytest
from run_plans import make_planner, EXAM_OPTIONS, PERMIT_GOLD
from run_plans import TARGET, MAX_EXAMS
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
    assert p.exam_train_ranks["弓箭手"] == 2      # 箭术 D→D+→C
    assert "剑客" not in p.exam_train_ranks       # 剑术够，不用练


def test_mika_does_not_train_for_curse_mage():
    """米迦 Lv33 考诅咒师只多 魔+1（权重 1），不值得为它练黑魔术。"""
    _, pl = plan("米迦艾拉")
    assert "诅咒师" not in exams(pl)


def test_archer_break_even_follows_training_cost():
    """弓箭手（中级 500G、练箭术 2 段）比猎兵（初级 300G、不用练）多 5 加权分。
    多花 200G = 3.2 分，所以每段训练成本 < 0.9 分时考弓箭手，> 0.9 分时考猎兵。"""
    p = make_planner("米迦艾拉", 35)
    p.min_exam_gain = 0   # 只测训练成本这一条
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


# ---- 11-16 Yizhuo 定的规则 ----
import run_plans as R


def test_horizon_is_lv35_or_15_levels_ahead():
    for n in R.ORDER:
        lv = R.current_state(n)[1]
        assert TARGET[n] == max(35, lv + 15), n
        assert TARGET[n] - lv >= 15


def test_wing_soldier_female_only():
    for n in R.ORDER:
        male = R._SEX.get(n) == "男"
        assert ("天翼兵" in EXAM_OPTIONS[n]) != male, n


def test_no_magic_classes_when_magic_weight_is_1():
    """米迦曾因魔力（权重 1）被排去萨满：魔力权重 ≤1 的角色不考法系职业。"""
    for n in R.ORDER:
        if R.W[n][2] <= 1:
            assert not set(R.MAGIC) & set(EXAM_OPTIONS[n]), n
    assert "萨满巫师" not in exams(plan("米迦艾拉")[1])


def test_personal_exclusions():
    assert "战车兵" not in EXAM_OPTIONS["杨界"]
    assert "牧师" not in EXAM_OPTIONS["奇洛伊卡"]


@pytest.mark.parametrize("name", NAMES)
def test_low_tiers_do_not_train(name):
    """P1/P2 不为考试练技能：路线里的考试技能都已经够，训练段数为 0。"""
    p, pl = plan(name)
    if R.TRAIN_ALLOWED[R.tier_of(name)]:
        return
    assert p.train_ranks(pl.raw_actions) == 0
    assert not p.exam_train_ranks          # 不假设先练够
    done = 0
    for st, (a, c) in enumerate(pl.raw_actions):
        if a == "升级":
            done += 1
        elif c != "跳过":   # 技能差的考试按实际成功率（差 1 段 50%）也必须考得过
            assert p.exam_ok(st, c, p.level + done), c


def test_training_cost_by_tier():
    assert R.TRAIN_PTS["P0"] < R.TRAIN_PTS["P1"] < R.TRAIN_PTS["P2"]
    assert make_planner("米迦艾拉").TRAIN_PTS_PER_RANK == R.TRAIN_PTS["P0"]


@pytest.mark.parametrize("name", NAMES)
def test_each_optional_exam_is_worth_min_gain(name):
    """去掉路线里任何一个非必考的考试，净值不会只差不到 MIN_EXAM_GAIN（米迦战车兵 +0.8 那种不考）。"""
    p, pl = plan(name)
    mine = p.plan_net(pl.raw_actions, pl.total, pl.gold)
    for c in pl.targets:
        if c in p.required:
            continue
        r = p.rule_run([t for t in pl.targets if t != c])
        if r:
            # 成对加入的考试可能单独不够，但成对必须够 2 倍
            assert mine - p.plan_net(r[0], r[2], r[3]) > 0, c


def test_brigand_floor_from_yuphas():
    assert R.FLOORS["土匪"] == [30, 10, 0, 5, 3, 3, 0, 0, 0]


def test_floor_lift_counts_in_net():
    p = make_planner("努蒂奴", 35)
    p.raw_stats = [1] * 9   # 裸能力全 1：考进任何有保底的职业都会补
    acts = (("考试", "重装步兵"),) + (("升级", "飞鸵兵"),) * 18
    if p.exam_ok(0, "重装步兵", p.level):
        lifts = p.floor_lifts(acts)
        assert 0 in lifts and p.floor_value(acts) > 0
    assert p.floor_lifts((("考试", "跳过"),)) == {}


def test_renown_requirement_parsed():
    assert R.renown_req("剑客") == 4


@pytest.mark.parametrize("name", NAMES)
def test_skip_rows_offer_free_basic_class(name):
    """跳过时如果有还没有、能考过的初级职业，就写出来（同样 300G，白拿职业）。"""
    p, pl = plan(name)
    for r in pl.rows:
        if r.action != "升级" and r.cls == "跳过" and r.skip_class:
            assert r.skip_class not in p.owned and R._TIER_OF(r.skip_class) == "初级"
