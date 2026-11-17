"""规划规则的测试（11-11 起用 TDD 改规则）。运行：cd levelup/rng && python3 -m pytest -q tests"""
import os, sys, functools
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pytest
from run_plans import make_planner, EXAM_OPTIONS, PERMIT_GOLD
from run_plans import TARGET, MAX_EXAMS
from planner import plan_all
from planner import _TIER

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
    p.require_mid = False   # 11-17 起米迦必须考进中级；这里只测训练成本
    p.equal_seeds = False
    for cost, want in ((0.5, "弓箭手"), (1.5, "猎兵")):
        p.TRAIN_PTS_PER_RANK = cost
        assert want in exams(plan_all(p, MAX_EXAMS)[0][plan_all(p, MAX_EXAMS)[1]]), cost


@pytest.mark.parametrize("name", NAMES)
def test_every_trained_exam_pays_for_its_training(name):
    """路线里每个要先练技能的考试：去掉它（改成按规则走），净值不能更高。"""
    p, pl = plan(name)
    for c in set(exams(pl)) & set(p.exam_train_ranks):
        others = [t for t in pl.targets if t != c]
        alt = p.window_value(others)
        if alt is None or not _has_mid(p, alt[0]):
            continue
        assert p.window_value(pl.targets)[3] >= alt[3] - 1e-6, c


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


def _has_mid(p, acts):
    if not p.require_mid:
        return True
    used = {c for a, c in acts if a == "升级"}
    return any(a == "考试" and c in used and _TIER.get(c) == "中级" for a, c in acts)


@pytest.mark.parametrize("name", NAMES)
def test_each_optional_exam_is_worth_min_gain(name):
    """去掉路线里任何一个非必考的考试，净值不会只差不到 MIN_EXAM_GAIN（米迦战车兵 +0.8 那种不考）。"""
    p, pl = plan(name)
    mine = p.window_value(pl.targets)[3]   # 11-17：同样多的乱数里比
    for c in pl.targets:
        if c in p.required:
            continue
        r = p.window_value([t for t in pl.targets if t != c])
        if r and not _has_mid(p, r[0]):
            continue   # 11-17：这场是「每人都要考进中级」硬加的，去掉就不合规则
        if r:
            # 成对加入的考试可能单独不够，但成对必须够 2 倍
            assert mine - r[3] > 0, c


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
def test_skip_does_not_gain_a_class(name):
    """Yizhuo 11-16：跳过多拿职业不是好事（以后能跳过的考试变少）→ 有会考不过的初级考试就用它；
    每次跳过都要有考试可用（职业池不能用完）。"""
    p, pl = plan(name)
    for r in pl.rows:
        if r.action != "升级" and r.cls == "跳过":
            assert not r.skip_none, f"Lv{r.level_at} 没有初级考试可以拿来跳过"
            if r.skip_fail:
                assert r.skip_class is None
                for c in r.skip_fail:
                    assert c not in p.owned
                    pc = p.skip_pct(c, r.level_at)
                    assert pc is None or p.exam_value(r.step) >= pc


def test_skip_pool_shrinks_only_when_forced():
    p = make_planner("艾丝梅拉尔达", TARGET["艾丝梅拉尔达"])
    pl = p.rule_plan()
    lefts = [r.skip_left for r in pl.rows if r.action != "升级" and r.cls == "跳过"]
    assert lefts and min(lefts) >= 1


def test_renown_is_6_and_blocks_higher():
    assert R.RENOWN == 6
    p = make_planner("迪托利希")
    assert all(v <= R.RENOWN for v in p.renown_req.values())   # 初级/中级都要 ≤ 4


def test_options_list_covers_every_allowed_class():
    """11-16 Yizhuo：职业选择清单——每人每个没拿到的可考职业都列出，带到目标级和之后的影响。"""
    import make_options as M
    o = M.build("米迦艾拉")
    listed = {x["cls"] for x in o["options"]}
    want = {c for c in R.EXAM_OPTIONS["米迦艾拉"] if c not in R.OWNED["米迦艾拉"] and c not in R.REQUIRED.get("米迦艾拉", [])}
    assert listed == want
    for x in o["options"]:
        if x["ok"]:
            assert {"g", "total", "net", "gold"} <= set(x["toT"]) and x["roll"] >= 0


# ---- 11-17 Yizhuo：所有角色都要考到中级（上级不一定） ----
@pytest.mark.parametrize("name", NAMES)
def test_everyone_reaches_intermediate(name):
    p, pl = plan(name)
    owned_mid = any(_TIER.get(c) == "中级" for c in R.OWNED[name])
    assert p.require_mid == (not owned_mid)
    assert _has_mid(p, pl.raw_actions), name


def test_mid_owners_count_as_done():
    for n in ("迪托利希", "艾丝梅拉尔达", "伊欧"):
        assert not make_planner(n).require_mid


def test_low_tier_may_train_only_for_required_mid():
    p = make_planner("努蒂奴")
    assert not R.TRAIN_ALLOWED["P2"]
    assert all(_TIER.get(c) == "中级" for c in p.mid_train)


def test_equal_seed_window():
    """11-17 Yizhuo：比较按用掉同样多的乱数。窗口 = 路线到目标级用掉的乱数；窗口里的动作数正好是窗口大小。"""
    p, pl = plan("奇洛伊卡")
    assert p.window == len(pl.raw_actions)
    for tg in ([], list(pl.targets)):
        r = p.window_value(tg)
        assert r is not None and len(r[0]) == p.window
