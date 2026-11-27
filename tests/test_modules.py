"""三大功能模块与前后端分离架构的 Python 单元测试（unittest / pytest 双兼容）。

运行：
    python3 -m unittest discover -s tests -v
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "levelup" / "rng") not in sys.path:
    sys.path.insert(0, str(ROOT / "levelup" / "rng"))

from modules.affinity.planner import compute_pair_weights, is_perfect, plan_meals
from modules.affinity.service import build_affinity_data
from modules.classes.service import build_classes_data
from modules.items.catalog import parse_materials
from modules.items.service import build_items_data
from modules.route.config_loader import load_route_config
import build_site
import make_options
import run_plans as R


class TestAffinityModule(unittest.TestCase):
    def test_perfect_rules(self):
        self.assertTrue(is_perfect([2, 2, 2]))
        self.assertTrue(is_perfect([1, 3, 3]))
        self.assertFalse(is_perfect([1, 2, 3]))
        self.assertFalse(is_perfect([0, 3, 3]))

    def test_compute_pair_weights_is_pure(self):
        people = [
            {"name": "迪托利希", "pref": [2] * 12, "rep": {}, "sup": {}, "tier": ""},
            {"name": "丹提", "pref": [2] * 12, "rep": {"迪托利希": 8}, "sup": {"迪托利希": 2}, "tier": "可选"},
        ]
        cfg = {
            "recruited": ["迪托利希"],
            "goals": [{"lord": "迪托利希", "route": "迪托利希", "renown_weight": {"6": 3}, "support_weight": {"2": 1}, "min_support": 2, "tiers": ["必招", "可选"]}],
        }
        w, need = compute_pair_weights(people, cfg)
        self.assertEqual(w, {("迪托利希", "丹提"): 1})
        self.assertEqual(need, {("迪托利希", "丹提"): 2})

    def test_build_affinity_data_schema(self):
        d = build_affinity_data()
        self.assertEqual(d["module"], "affinity")
        self.assertEqual(d["schemaVersion"], 2)
        self.assertEqual(len(d["dishes"]), 12)
        self.assertTrue(any(x["perfect"] for x in d["dishes"]))
        self.assertEqual([x["name"] for x in d["lords"]], ["迪托利希", "蕾达", "凯伊", "赛奥朵拉"])
        by_name = {x["name"]: x for x in d["roster"]}
        self.assertGreaterEqual(len(by_name), 40)
        # 迪线已满足友好度（待招）角色
        for met_name in ("哥莱亚斯", "班迪兹", "杰斯塔", "奥琳琵娅", "莱桑达", "索绯雅", "乌修拉"):
            self.assertIn(met_name, by_name)
            self.assertTrue(by_name[met_name]["dietAffinityMet"], f"{met_name} 应标记为迪线友好度已满足")
            self.assertEqual(by_name[met_name]["statusKey"], "met")
        # 迪线待刷友好度角色
        for todo_name in ("希蒙", "穆", "丹提"):
            self.assertEqual(by_name[todo_name]["statusKey"], "todo")
            self.assertFalse(by_name[todo_name]["dietAffinityMet"])
        # 已入队角色
        self.assertEqual(by_name["迪托利希"]["statusKey"], "recruited")



class TestItemsModule(unittest.TestCase):
    def test_parse_materials(self):
        self.assertEqual(
            parse_materials("バクx10,キンバイx3"),
            [{"material": "バク", "qty": 10}, {"material": "キンバイ", "qty": 3}],
        )
        self.assertEqual(
            parse_materials("Paradise Fish ×1"),
            [{"material": "Paradise Fish", "qty": 1}],
        )

    def test_build_items_data_schema_and_reverse_index(self):
        d = build_items_data()
        self.assertEqual(d["module"], "items")
        self.assertGreater(d["summary"]["townCount"], 10)
        self.assertGreater(d["summary"]["barterCount"], 5)
        self.assertGreater(d["summary"]["materialCount"], 5)
        mats = {m["material"]: m for m in d["materials"]}
        self.assertIn("バク", mats)
        self.assertGreaterEqual(mats["バク"]["totalUses"], 2)


class TestRouteConfigAndBugfixes(unittest.TestCase):
    def test_route_config_loaded_from_json(self):
        cfg = load_route_config()
        self.assertEqual(cfg.order, R.ORDER)
        self.assertEqual(cfg.p0, R.P0)
        self.assertEqual(cfg.p2, R.P2)
        self.assertEqual(cfg.renown, R.RENOWN)
        for n in cfg.order:
            self.assertIn("平民", cfg.owned[n])

    def test_make_options_train_true_does_not_short_circuit_on_train_case(self):
        for name in ("奇洛伊卡", "努蒂奴", "乌尔坦德"):
            p = make_options.planner(name, R.TARGET[name], True)
            remaining_gaps = {c: r for c, r in p.exam_req.items() if r[1] > 0}
            self.assertEqual(remaining_gaps, {}, f"{name} train=True still had untrained skill gaps")

    def test_web_only_build_is_decoupled_from_data(self):
        with tempfile.TemporaryDirectory() as td:
            out_dir = Path(td)
            copied = build_site.build_web(out_dir)
            self.assertIn("index.html", copied)
            self.assertIn("styles.css", copied)
            self.assertFalse((out_dir / "data").exists())
            html = (out_dir / "index.html").read_text(encoding="utf-8")
            self.assertIn("<!DOCTYPE html>", html)
            self.assertNotIn("/*ROUTE_DATA*/", html)


class TestClassesModule(unittest.TestCase):
    def test_build_classes_data_schema_and_tiers(self):
        d = build_classes_data()
        self.assertEqual(d["module"], "classes")
        self.assertEqual(d["tierOrder"], ["基础", "初级", "中级", "上级", "最上级", "神将"])
        self.assertEqual(d["summary"]["classCount"], 60)
        self.assertEqual(d["summary"]["tierCounts"]["初级"], 5)
        self.assertEqual(d["summary"]["tierCounts"]["中级"], 12)
        self.assertTrue(all(len(c["usableSkills"]) >= 1 for c in d["classes"]))
        # 验证按阶级顺序排列
        tier_indices = [d["tierOrder"].index(c["tier"]) for c in d["classes"]]
        self.assertEqual(tier_indices, sorted(tier_indices))

    def test_route_proposals_include_9stat_diffs_and_defaults(self):
        from modules.route.choice_builder import build_route_proposals
        props = build_route_proposals()
        self.assertEqual(len(props), 9)
        # 严格按档位 P0 -> P1 -> P2 排序
        tier_rank = {"P0": 0, "P1": 1, "P2": 2}
        ranks = [tier_rank[p["tier"]] for p in props]
        self.assertEqual(ranks, sorted(ranks))
        by_name = {p["name"]: p for p in props}
        for confirmed in ("伊欧", "奇洛伊卡", "米迦艾拉", "杨界"):
            self.assertEqual(by_name[confirmed]["defaultPick"], "new_best")
        for pending in ("迪托利希", "努蒂奴", "乌尔坦德", "法毕欧", "艾丝梅拉尔达"):
            self.assertIsNone(by_name[pending]["defaultPick"])
        # 努蒂奴必须同时有 new_best (含 S/L 提醒 + 9项具体能力差) 与 safe_fallback
        nu_opts = {o["id"]: o for o in by_name["努蒂奴"]["options"]}
        self.assertIn("new_best", nu_opts)
        self.assertIn("safe_fallback", nu_opts)
        self.assertEqual(len(nu_opts["new_best"]["diffVsBaseline"]["statDiff"]), 9)
        self.assertIn("防+3", nu_opts["new_best"]["diffVsBaseline"]["statDiffText"])
        self.assertGreaterEqual(len(nu_opts["new_best"]["slWarnings"]), 1)


class TestSkillsModule(unittest.TestCase):
    def test_build_skills_data_completeness_and_scopes(self):
        from modules.skills.service import build_skills_data
        d = build_skills_data()
        self.assertGreater(d["summary"]["skillCount"], 500)
        self.assertEqual(d["summary"]["charCount"], 63)
        self.assertEqual(d["summary"]["recruitedCount"], 9)
        by_name = {s["name"]: s for s in d["skills"]}
        self.assertEqual(by_name["传送"]["rating"], "S")
        self.assertEqual(by_name["体格+"]["rating"], "S")
        self.assertEqual(by_name["秘传·落燕+"]["scope"], "unique")
        self.assertEqual(by_name["秘传·落燕+"]["charSources"][0]["char"], "迪托利希")
        self.assertEqual(by_name["大反击"]["scope"], "common_class")
        self.assertEqual(by_name["大反击"]["classSources"][0]["cls"], "重装步兵")
        # 角色表已招 9 人排在最前面
        self.assertTrue(all(c["recruited"] for c in d["characters"][:9]))


if __name__ == "__main__":
    unittest.main()
