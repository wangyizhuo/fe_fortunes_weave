"""纯以终为始两阶段规划器与统一目标函数的 TDD 单元测试（按 11-26 审阅规则更新）。

覆盖：
  1. 区间不变性定理（早考 t1 vs 晚考 t2 在 t2 之后 post_carryover == 0）
  2. Good / Bad 判据（GOOD_EARLY / GOOD_EARLY_NEEDS_SL / GOOD_LATE / TRADE_OFF）
  3. 去补丁化核心特性：
     - 不设 3% 禁考红线：努蒂奴 Lv16(s1) 正常夺冠并给出 SLTestWarning + 稳过备选 Lv18(s3)
     - 乌尔坦德 Lv19(s4) 正常夺冠并给出 SLTestWarning + 稳过备选 Lv21(s6)
     - 去掉 no_skip_seeds 人工锁种子：迪托利希不误跳（stat=262, net=254.0），伊欧总面板反而提升
     - 不设初级/中级职业数量上限：艾丝梅拉尔达可扩展至 3 个职业（斗拳手+重装+天翼）并输出每个职业边际收益
     - 不强制考完必须用来升级：法毕欧允许必考萨满巫师在窗口内用 0 级换取更高升级分
     - 全档位允许照常训练：P1/P2 统一按每段训练成本折算，不再需要特批补丁
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

from modules.route.objective import (
    DEFAULT_TIER_POLICIES,
    classify_timing_choice,
)
from modules.route.two_stage_planner import (
    compare_timing_interval,
    plan_two_stage,
    prepare_goal_first_planner,
    simulate_fixed_exams,
)


class TestObjectiveClassification(unittest.TestCase):
    def test_classify_timing_choice_four_verdicts(self):
        # 差值 < 5% 时不拒绝，标为 GOOD_EARLY_NEEDS_SL 提醒提前 S/L 实测
        v, msg = classify_timing_choice(11, 4, 0, 4, early_margin=0.69, sl_warn_margin=5.0)
        self.assertEqual(v, "GOOD_EARLY_NEEDS_SL")
        self.assertIn("S/L", msg)

        v, _ = classify_timing_choice(6, 2, 0, 2, early_margin=6.33, sl_warn_margin=5.0)
        self.assertEqual(v, "GOOD_EARLY")

        v, _ = classify_timing_choice(-11, -3, 300, 4, early_margin=88.39, sl_warn_margin=5.0)
        self.assertEqual(v, "GOOD_LATE")

        v, _ = classify_timing_choice(1, 1, 300, 2, early_margin=50.0, sl_warn_margin=5.0)
        self.assertEqual(v, "GOOD_LATE")

        v, _ = classify_timing_choice(-1, 1, 0, 3, early_margin=20.0, sl_warn_margin=5.0)
        self.assertEqual(v, "TRADE_OFF")


class TestPurifiedGoalFirstPlanner(unittest.TestCase):
    def test_nutinu_lv16_wins_with_sl_warning_and_lv18_safe_fallback(self):
        p, tier = prepare_goal_first_planner("努蒂奴")
        pol = DEFAULT_TIER_POLICIES[tier]

        ev_lv16 = simulate_fixed_exams(p, {1: "重装步兵"}, pol, ("重装步兵",))
        ev_lv18 = simulate_fixed_exams(p, {3: "重装步兵"}, pol, ("重装步兵",))
        ev_lv21 = simulate_fixed_exams(p, {6: "重装步兵"}, pol, ("重装步兵",))
        self.assertIsNotNone(ev_lv16)
        self.assertIsNotNone(ev_lv18)
        self.assertIsNotNone(ev_lv21)

        # 转职保底差：Lv16/Lv18 裸防 7->10 (+9分)，Lv21 裸防 8->10 (+6分)，早转多白嫖 +3 转职保底分
        self.assertEqual(ev_lv16.breakdown.promo_floor_weighted, 9)
        self.assertEqual(ev_lv18.breakdown.promo_floor_weighted, 9)
        self.assertEqual(ev_lv21.breakdown.promo_floor_weighted, 6)

        # 区间不变性定理 + 提醒提前 S/L 实测
        diff16 = compare_timing_interval(p, "重装步兵", ev_lv16, ev_lv21, pol)
        self.assertEqual(diff16.verdict, "GOOD_EARLY_NEEDS_SL")
        self.assertTrue(diff16.needs_sl_test)
        self.assertEqual(diff16.post_carryover_pts, 0)
        self.assertEqual(diff16.promo_floor_w, 3)

        diff18 = compare_timing_interval(p, "重装步兵", ev_lv18, ev_lv21, pol)
        self.assertEqual(diff18.verdict, "GOOD_EARLY")
        self.assertFalse(diff18.needs_sl_test)
        self.assertEqual(diff18.post_carryover_pts, 0)

        # 全局最优：不因余量小而硬杀 Lv16，产出 S/L 提醒 + 稳过备选 Lv18
        res = plan_two_stage(p, tier)
        self.assertEqual(res.best.exam_at, {1: "重装步兵"})
        self.assertEqual(len(res.best.sl_warnings), 1)
        self.assertEqual(res.best.sl_warnings[0].cls, "重装步兵")
        self.assertIsNotNone(res.safe_fallback)
        self.assertEqual(res.safe_fallback.exam_at, {3: "重装步兵"})
        self.assertEqual(res.safe_fallback.sl_warnings, ())

    def test_urtand_lv19_wins_with_sl_warning_and_safe_fallback(self):
        p, tier = prepare_goal_first_planner("乌尔坦德")
        res = plan_two_stage(p, tier)
        self.assertEqual(res.best.exam_at, {4: "牧师"})
        self.assertEqual(res.best.breakdown.raw_points, 92)
        self.assertEqual(len(res.best.sl_warnings), 1)
        self.assertIsNotNone(res.safe_fallback)
        self.assertEqual(res.safe_fallback.sl_warnings, ())
        self.assertGreater(res.safe_fallback.breakdown.pure_stat_score, 264)

    def test_no_skip_seeds_removed_dietrich_and_io_work_cleanly(self):
        # 迪托利希：不靠 no_skip_seeds 也能 0 跳过复现 s3 恶棍（262分 / 254净值）
        p_di, t_di = prepare_goal_first_planner("迪托利希")
        self.assertEqual(p_di.no_skip_seeds, set())
        r_di = plan_two_stage(p_di, t_di)
        self.assertEqual(r_di.best.exam_at, {3: "恶棍"})
        self.assertEqual(r_di.best.breakdown.skips, 0)
        self.assertEqual(r_di.best.breakdown.pure_stat_score, 262)

        # 伊欧：不人工锁种子，最终面板与净值显著高于锁种子旧方案（224分 / 206.4净值）
        p_io, t_io = prepare_goal_first_planner("伊欧")
        self.assertEqual(p_io.no_skip_seeds, set())
        r_io = plan_two_stage(p_io, t_io)
        self.assertGreater(r_io.best.breakdown.pure_stat_score, 224)
        self.assertGreater(r_io.best.breakdown.net_without_mastery, 206.4)

    def test_unlimited_classes_marginal_gains_and_zero_use_allowed(self):
        # 艾丝梅拉尔达：初级/中级不限个数，可扩展至 3 个职业并清晰报告额外职业边际收益
        p_es, t_es = prepare_goal_first_planner("艾丝梅拉尔达")
        r_es = plan_two_stage(p_es, t_es)
        self.assertEqual(len(r_es.best.targets), 3)
        self.assertIn("斗拳手", r_es.best.targets)
        by_cls = {m.cls: m for m in r_es.marginal_gains}
        self.assertGreaterEqual(by_cls["斗拳手"].delta_objective, DEFAULT_TIER_POLICIES["P0"].min_marginal_gain)

        # 法毕欧：不强制考完必须用来升级（允许 0 级使用换更高升级分）
        p_fb, t_fb = prepare_goal_first_planner("法毕欧")
        r_fb = plan_two_stage(p_fb, t_fb)
        self.assertEqual(r_fb.best.exam_at, {15: "萨满巫师"})
        self.assertEqual(r_fb.best.breakdown.mastery_levels, 0)
        self.assertEqual(r_fb.best.breakdown.pure_stat_score, 183)

    def test_mikhaila_sword_is_still_good_late(self):
        p, tier = prepare_goal_first_planner("米迦艾拉")
        pol = DEFAULT_TIER_POLICIES[tier]
        # 纯时机对比（关闭自动跳过）：严格满足区间不变性（post_carryover == 0）
        e4_ns = simulate_fixed_exams(p, {4: "剑客"}, pol, ("剑客",), allow_skips=False)
        e9_ns = simulate_fixed_exams(p, {9: "剑客"}, pol, ("剑客",), allow_skips=False)
        d_ns = compare_timing_interval(p, "剑客", e4_ns, e9_ns, pol)
        self.assertEqual(d_ns.post_carryover_pts, 0)
        self.assertEqual(d_ns.post_carryover_w, 0)

        # 含自动跳过：早考依然吃亏（GOOD_LATE）
        ev_early = simulate_fixed_exams(p, {4: "剑客"}, pol, ("剑客",))
        ev_late = simulate_fixed_exams(p, {9: "剑客"}, pol, ("剑客",))
        self.assertIsNotNone(ev_early)
        self.assertIsNotNone(ev_late)
        d = compare_timing_interval(p, "剑客", ev_early, ev_late, pol)
        self.assertEqual(d.verdict, "GOOD_LATE")
        self.assertLessEqual(d.total_w, -3)


if __name__ == "__main__":
    unittest.main()
