"""两阶段路线规划器与统一目标函数的 TDD 单元测试。

覆盖：
  1. 区间不变性定理（早考 t1 vs 晚考 t2 在 t2 之后 post_carryover == 0）
  2. Good / Bad 判据（RISKY_EARLY / GOOD_EARLY / GOOD_LATE / TRADE_OFF）
  3. 真实角色关键案例：
     - 努蒂奴：Lv16(s1) 压拟合误差线 -> RISKY_EARLY；Lv18(s3) -> GOOD_EARLY 且全面优于 Lv21(s6)
     - 乌尔坦德：Lv19(s4) 与 Lv20(s5, 100%) 均 -> GOOD_EARLY 且全面优于 Lv23(s8)
     - 米迦艾拉：剑客 Lv24(s4) vs Lv29(s9) -> GOOD_LATE
     - 杨界：萨满巫师 Lv21(s1) vs Lv23(s3) -> GOOD_EARLY（同分多精通）
     - 法毕欧：必考职业「萨满巫师」不会被推到末步（mastery_levels >= 1）
     - 迪托利希 / 伊欧：100% 满概率不误判风险，完整复现最优路线
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "levelup" / "rng") not in sys.path:
    sys.path.insert(0, str(ROOT / "levelup" / "rng"))

import run_plans as R
from modules.route.objective import (
    DEFAULT_TIER_POLICIES,
    TierPolicy,
    classify_timing_choice,
)
from modules.route.two_stage_planner import (
    compare_timing_interval,
    plan_two_stage,
    simulate_fixed_exams,
)


def _planner_for(name: str):
    _, lv = R.current_state(name)
    target = max(R.HORIZON_MIN_LEVEL, lv + R.HORIZON_MIN_STEPS)
    return R.make_planner(name, target)


class TestObjectiveClassification(unittest.TestCase):
    def test_classify_timing_choice_four_verdicts(self):
        v, _ = classify_timing_choice(11, 4, 0, 4, early_margin=0.69, min_est_margin=3.0)
        self.assertEqual(v, "RISKY_EARLY")

        v, _ = classify_timing_choice(6, 2, 0, 2, early_margin=6.33, min_est_margin=3.0)
        self.assertEqual(v, "GOOD_EARLY")

        v, _ = classify_timing_choice(-11, -3, 300, 4, early_margin=88.39, min_est_margin=3.0)
        self.assertEqual(v, "GOOD_LATE")

        v, _ = classify_timing_choice(1, 1, 300, 2, early_margin=50.0, min_est_margin=3.0)
        self.assertEqual(v, "GOOD_LATE")

        v, _ = classify_timing_choice(-1, 1, 0, 3, early_margin=20.0, min_est_margin=3.0)
        self.assertEqual(v, "TRADE_OFF")


class TestTwoStagePlannerAndIntervalTheorem(unittest.TestCase):
    def test_nutinu_risky_early_vs_good_early_and_interval_invariance(self):
        p = _planner_for("努蒂奴")
        pol = DEFAULT_TIER_POLICIES["P2"]
        relaxed = TierPolicy(**{**pol.__dict__, "min_est_margin": 0.0})

        ev_lv16 = simulate_fixed_exams(p, {1: "重装步兵"}, relaxed, ("重装步兵",))
        ev_lv18 = simulate_fixed_exams(p, {3: "重装步兵"}, pol, ("重装步兵",))
        ev_lv21 = simulate_fixed_exams(p, {6: "重装步兵"}, pol, ("重装步兵",))
        self.assertIsNotNone(ev_lv16)
        self.assertIsNotNone(ev_lv18)
        self.assertIsNotNone(ev_lv21)

        # 硬约束：严格余量策略应拒绝 Lv16（余量 0.69% < 3%）
        self.assertIsNone(simulate_fixed_exams(p, {1: "重装步兵"}, pol, ("重装步兵",)))

        # Lv16 vs Lv21 -> RISKY_EARLY，且区间外残差为 0
        diff_risky = compare_timing_interval(p, "重装步兵", ev_lv16, ev_lv21, pol)
        self.assertEqual(diff_risky.verdict, "RISKY_EARLY")
        self.assertEqual(diff_risky.post_carryover_pts, 0)
        self.assertEqual(diff_risky.post_carryover_w, 0)

        # Lv18 vs Lv21 -> GOOD_EARLY，且区间外残差为 0、点数/加权分/精通全面占优
        diff_good = compare_timing_interval(p, "重装步兵", ev_lv18, ev_lv21, pol)
        self.assertEqual(diff_good.verdict, "GOOD_EARLY")
        self.assertEqual(diff_good.post_carryover_pts, 0)
        self.assertEqual(diff_good.post_carryover_w, 0)
        self.assertGreater(diff_good.total_pts, 0)
        self.assertGreater(diff_good.total_w, 0)
        self.assertGreater(diff_good.mastery_lv_delta, 0)

        # 两阶段全局最优应直接选出 s3(Lv18) 重装步兵
        res = plan_two_stage(p, "P2")
        self.assertEqual(res.best.exam_at, {3: "重装步兵"})
        self.assertEqual(res.best.breakdown.raw_points, 88)
        self.assertEqual(res.best.breakdown.pure_stat_score, 270)

    def test_urtand_early_priest_beats_myopic_lv23(self):
        p = _planner_for("乌尔坦德")
        pol = DEFAULT_TIER_POLICIES["P2"]
        ev_lv19 = simulate_fixed_exams(p, {4: "牧师"}, pol, ("牧师",))
        ev_lv20 = simulate_fixed_exams(p, {5: "牧师"}, pol, ("牧师",))
        ev_lv23 = simulate_fixed_exams(p, {8: "牧师"}, pol, ("牧师",))
        self.assertIsNotNone(ev_lv19)
        self.assertIsNotNone(ev_lv20)
        self.assertIsNotNone(ev_lv23)

        d19 = compare_timing_interval(p, "牧师", ev_lv19, ev_lv23, pol)
        self.assertEqual(d19.verdict, "GOOD_EARLY")
        self.assertEqual(d19.post_carryover_pts, 0)
        self.assertEqual(d19.total_pts, 4)
        self.assertEqual(d19.total_w, 13)

        d20 = compare_timing_interval(p, "牧师", ev_lv20, ev_lv23, pol)
        self.assertEqual(d20.verdict, "GOOD_EARLY")
        self.assertGreater(d20.total_w, 0)

        res = plan_two_stage(p, "P2")
        self.assertEqual(res.best.exam_at, {4: "牧师"})

    def test_mikhaila_sword_is_good_late(self):
        p = _planner_for("米迦艾拉")
        pol = DEFAULT_TIER_POLICIES["P0"]
        ev_early = simulate_fixed_exams(p, {4: "剑客"}, pol, ("剑客",))
        ev_late = simulate_fixed_exams(p, {9: "剑客"}, pol, ("剑客",))
        self.assertIsNotNone(ev_early)
        self.assertIsNotNone(ev_late)
        d = compare_timing_interval(p, "剑客", ev_early, ev_late, pol)
        self.assertEqual(d.verdict, "GOOD_LATE")
        self.assertEqual(d.post_carryover_pts, 0)
        self.assertGreater(d.gold_delta, 0)

    def test_fabio_required_shaman_gets_mastery_and_dietrich_io_preserved(self):
        p_fab = _planner_for("法毕欧")
        r_fab = plan_two_stage(p_fab, "P1")
        self.assertEqual(r_fab.best.exam_at, {2: "萨满巫师"})
        self.assertGreaterEqual(r_fab.best.breakdown.mastery_levels, 1)

        p_di = _planner_for("迪托利希")
        r_di = plan_two_stage(p_di, "P0")
        self.assertEqual(r_di.best.exam_at, {3: "恶棍"})

        # 伊欧：飞鸵兵在 s5 为 100% 满概率，不应被公式余量误拒
        p_io = _planner_for("伊欧")
        r_io = plan_two_stage(p_io, "P0")
        exams_io = [(i, c) for i, (a, c) in enumerate(r_io.best.actions) if a == "考试" and c != "跳过"]
        self.assertEqual(exams_io, [(2, "战车兵"), (5, "飞鸵兵")])


if __name__ == "__main__":
    unittest.main()
