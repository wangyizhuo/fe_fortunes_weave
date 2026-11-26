"""全链路业务逻辑完整性 TDD 测试套件（unittest / pytest 双兼容）。

覆盖：
  1. fe_growth RNG 引擎边界（种子域、严格小于判定、保底项数、>100% 成长、封顶属性）
  2. modules.affinity 友好度培养业务不变量
  3. modules.items 道具/材料采集双向一致性
  4. modules.route 路线规划数据完整性、rulesMeta 一致性与 bug 回归防线
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RNG_DIR = ROOT / "levelup" / "rng"
for p in (ROOT, RNG_DIR):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import fe_growth as FG  # noqa: E402
import run_plans as R  # noqa: E402
from planner import exam_rate  # noqa: E402
from modules.affinity.planner import compute_pair_weights, is_perfect, plan_meals  # noqa: E402
from modules.affinity.service import build_affinity_data  # noqa: E402
from modules.items.catalog import build_catalog, export_csv, parse_materials  # noqa: E402
from modules.items.service import build_items_data  # noqa: E402
from modules.route.service import build_route_data  # noqa: E402


class TestRNGMechanics(unittest.TestCase):
    def test_next_seed_stays_within_31_bit_unsigned_range(self):
        s = 1320706839
        seen = set()
        for _ in range(100):
            s = FG.next_seed(s)
            self.assertGreaterEqual(s, 0)
            self.assertLess(s, 1 << 31)
            seen.add(s)
        self.assertEqual(len(seen), 100)

    def test_exam_passes_strict_less_than_boundary(self):
        seed = 1060419758
        roll = FG.exam_roll(seed)
        self.assertGreaterEqual(roll, 0)
        self.assertLess(roll, 1_000_000)
        exact_pct = roll / 10_000
        self.assertFalse(FG.exam_passes(seed, exact_pct))
        self.assertTrue(FG.exam_passes(seed, exact_pct + 0.0001))

    def test_level_up_respects_floor_and_caps_and_over_100_growth(self):
        # 极低成长率 + 保底 2 项 => 至少涨 2 项
        res = FG.level_up(12345, [5, 5, 5, 5, 5, 5, 5, 5, 5], min_stats=2)
        self.assertGreaterEqual(sum(1 for g in res.gains if g > 0), 2)

        # 封顶属性绝不上涨
        capped = [True, True, True, False, False, True, True, True, True]
        res_cap = FG.level_up(12345, [90] * 9, min_stats=2, capped=capped)
        for i, is_cap in enumerate(capped):
            if is_cap:
                self.assertEqual(res_cap.gains[i], 0)
        self.assertEqual(res_cap.gains[3], 1)
        self.assertEqual(res_cap.gains[4], 1)

        # 120% 成长率至少 +1，最高 +2
        res_hi = FG.level_up(999, [120, 0, 0, 0, 0, 0, 0, 0, 0], min_stats=0)
        self.assertIn(res_hi.gains[0], (1, 2))

    def test_exam_rate_formula_monotonicity_and_bounds(self):
        self.assertEqual(exam_rate(0, 0), 100)
        self.assertEqual(exam_rate(5, 0), 100)
        self.assertEqual(exam_rate(-6, 0), 0)
        self.assertEqual(exam_rate(0, 6), 0)
        # 技能差越少，成功率越高
        rates = [exam_rate(0, g) for g in range(7)]
        self.assertEqual(rates, sorted(rates, reverse=True))


class TestAffinityIntegrity(unittest.TestCase):
    def test_all_tables_have_no_filler_no_hated_and_consistent_scores(self):
        data = build_affinity_data()
        with open(ROOT / "meals" / "meal_config.json", encoding="utf-8") as f:
            cfg = json.load(f)
        excluded = set(cfg["maxed"]) | set(cfg["absent"])
        recruited_non_lord = set(cfg["recruited"]) - {cfg["current_lord"]}
        pairs_done = {tuple(x) for x in cfg["pairs_done"]}

        self.assertEqual(len(data["dishes"]), 12)
        for dish in data["dishes"]:
            self.assertTrue(dish["options"], f"{dish['dish']} 没有任何可用组合")
            if dish["perfect"]:
                self.assertTrue(all(t["perfect"] for t in dish["options"]))
            for t in dish["options"]:
                self.assertEqual(len(t["who"]), 3)
                self.assertEqual(len(set(t["who"])), 3)
                self.assertEqual(t["filler"], [])
                self.assertGreater(min(t["pref"]), 0)
                self.assertEqual(t["perfect"], is_perfect(t["pref"]))
                self.assertFalse(excluded & set(t["who"]))
                self.assertFalse(recruited_non_lord & set(t["who"]))
                for pair in t["pairs"]:
                    self.assertNotIn(tuple(pair), pairs_done)


class TestItemsIntegrity(unittest.TestCase):
    def test_barter_and_reverse_materials_index_are_consistent(self):
        data = build_items_data()
        # 优先城镇（帝都达格席翁）排在首位
        self.assertEqual(data["towns"][0]["cn"], "帝都达格席翁")
        self.assertEqual(
            data["summary"]["shopItemCount"],
            sum(len(t["items"]) for t in data["towns"]),
        )
        # 校验每条以物易物所需材料都能在 materials 反查表里精确找到
        mat_lookup = {m["material"]: m["usedIn"] for m in data["materials"]}
        for b in data["barter"]:
            self.assertTrue(b["materials"], f"{b['cn']} 缺少结构化材料解析")
            for m in b["materials"]:
                self.assertIn(m["material"], mat_lookup)
                entries = [u for u in mat_lookup[m["material"]] if u["cn"] == b["cn"] and u["qty"] == m["qty"]]
                self.assertTrue(entries, f"材料 {m['material']} 反查表缺少 {b['cn']}×{m['qty']}")

    def test_csv_export_matches_catalog(self):
        with open(ROOT / "config" / "items_config.json", encoding="utf-8") as f:
            cfg = json.load(f)
        cat = build_catalog(cfg, ROOT / cfg["weaponsTsv"])
        with tempfile.TemporaryDirectory() as td:
            csv_path = Path(td) / "shops.csv"
            export_csv(cat["csvRows"], csv_path)
            lines = csv_path.read_text(encoding="utf-8-sig").splitlines()
            self.assertEqual(len(lines), len(cat["csvRows"]) + 1)
            self.assertTrue(lines[0].startswith("城镇,英文名,类别"))


class TestRouteDataIntegrity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.route_data = build_route_data()

    def test_owned_classes_match_config_without_ghost_patches(self):
        by_name = {c["name"]: c for c in self.route_data["chars"]}
        for name in R.ORDER:
            self.assertEqual(by_name[name]["owned"], R.OWNED[name], f"{name} 网页 owned 与 config/route_config.json 不一致")
        # 11-25 重开章节回归防线
        self.assertNotIn("天翼兵", by_name["艾丝梅拉尔达"]["owned"])
        self.assertNotIn("战车兵", by_name["伊欧"]["owned"])

    def test_rules_meta_reflects_live_config(self):
        rm = self.route_data["rulesMeta"]
        self.assertEqual(rm["shotKey"], R.SHOT_KEY)
        self.assertEqual(rm["renown"], R.RENOWN)
        self.assertIn("法毕欧", rm["tiers"]["P1"])
        self.assertNotIn("法毕欧", rm["tiers"]["P0"])
        self.assertTrue(rm["requireMidRule"])
        self.assertEqual(rm["balanceMinWeight"], 4)

    def test_step_routes_pass_matches_exact_exam_ok(self):
        by_name = {c["name"]: c for c in self.route_data["chars"]}
        for name in ("迪托利希", "乌尔坦德", "艾丝梅拉尔达"):
            p = R.make_planner(name, R.TARGET[name])
            plan_steps = [s for s in by_name[name]["steps"] if s["src"] == "plan"]
            lv = p.level
            for s in plan_steps:
                step_idx = int(s["key"]) - 1
                for e in s["routes"]["exams"]:
                    if e["pct"] is not None:
                        self.assertEqual(
                            e["pass"],
                            p.exam_ok(step_idx, e["cls"], lv),
                            f"{name} step {step_idx} {e['cls']} pass mismatch",
                        )
                if not s["exam"]:
                    lv += 1


if __name__ == "__main__":
    unittest.main()
