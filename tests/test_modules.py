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
        self.assertEqual(len(d["dishes"]), 12)
        self.assertTrue(any(x["perfect"] for x in d["dishes"]))


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


if __name__ == "__main__":
    unittest.main()
