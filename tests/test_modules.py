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
        # 验证按阶级顺序排列，并计算优势/劣势属性
        tier_indices = [d["tierOrder"].index(c["tier"]) for c in d["classes"]]
        self.assertEqual(tier_indices, sorted(tier_indices))
        by_cls = {c["name"]: c for c in d["classes"]}
        self.assertIn("防", by_cls["重装步兵"]["advantageStats"])
        self.assertIn("力", by_cls["重装步兵"]["advantageStats"])
        self.assertIn("魔防", by_cls["重装步兵"]["disadvantageStats"])
        self.assertIn("魔", by_cls["萨满巫师"]["advantageStats"])
        self.assertIn("防", by_cls["萨满巫师"]["disadvantageStats"])

    def test_route_proposals_include_9stat_diffs_and_defaults(self):
        from modules.route.choice_builder import build_route_proposals
        props = build_route_proposals()
        self.assertEqual(len(props), 9)
        # 严格按 当前主角 -> P -> 综合强度(SS~D) -> 名字(拼音) 排序，且伊欧已下调至 P1
        self.assertEqual(
            [p["name"] for p in props],
            ["迪托利希", "艾丝梅拉尔达", "米迦艾拉", "法毕欧", "奇洛伊卡", "伊欧", "杨界", "努蒂奴", "乌尔坦德"],
        )
        by_name = {p["name"]: p for p in props}
        self.assertEqual(by_name["伊欧"]["tier"], "P1")
        self.assertEqual(by_name["伊欧"]["strengthTier"], "B")
        self.assertEqual(by_name["迪托利希"]["strengthTier"], "S")
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
        # 艾丝梅拉尔达 斗拳手按当前等级与技能计算真实预估率（8%），并按判定值 45.60% 反推最低要求（格斗术 E→D+，练 3 段 → 估 50%）
        es_best = next(o for o in by_name["艾丝梅拉尔达"]["options"] if o["id"] == "new_best")
        brawler_ex = next(e for e in es_best["exams"] if e["cls"] == "斗拳手")
        self.assertEqual(brawler_ex["curPct"], 8)
        self.assertEqual(brawler_ex["minTrainRanks"], 3)
        self.assertEqual(brawler_ex["minPassPct"], 50)
        self.assertIn("格斗术 E→D+", brawler_ex["minReqText"])
        self.assertIn("格斗术 E（要求 C，差4段）", brawler_ex["skillSummary"])


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
        # 体格/体格+ 属于角色个人熟练度习得表，而非职业固有技能
        self.assertEqual(by_name["体格"]["scope"], "common_learn")
        self.assertIn("角色表限定", by_name["体格"]["scopeLabel"])
        self.assertEqual(len(by_name["体格"]["classSources"]), 0)
        self.assertEqual(by_name["体格"]["ownerCount"], 39)
        self.assertEqual(by_name["体格+"]["ownerCount"], 24)
        self.assertEqual(by_name["秘传·落燕+"]["scope"], "unique")
        self.assertEqual(by_name["秘传·落燕+"]["charSources"][0]["char"], "迪托利希")
        self.assertEqual(by_name["大反击"]["scope"], "common_class")
        self.assertIn("全员通用", by_name["大反击"]["scopeLabel"])
        self.assertEqual(by_name["大反击"]["classSources"][0]["cls"], "重装步兵")
        # 生效兵种限制校验：严格区分自身兵种条件（如 [Armored]）与对敌特攻/通用重装术习得（如体格）
        self.assertEqual(by_name["重装移动术+1"]["unitTypes"], ["重装"])
        self.assertEqual(by_name["步行再移动"]["unitTypes"], ["步兵"])
        self.assertEqual(by_name["骑兵移动术+"]["unitTypes"], ["骑兵"])
        self.assertEqual(by_name["与爱马连携"]["unitTypes"], ["骑兵"])
        self.assertEqual(by_name["高速飞行术+"]["unitTypes"], ["飞行"])
        self.assertEqual(by_name["乘降术"]["unitTypes"], ["仅限本职业"])
        self.assertEqual(by_name["体格+"]["unitTypes"], [])
        self.assertEqual(by_name["穿铠"]["unitTypes"], [])
        utc = d["summary"]["unitTypeCounts"]
        self.assertGreaterEqual(utc["重装"], 15)
        self.assertGreaterEqual(utc["步兵"], 25)
        self.assertGreaterEqual(utc["骑兵"], 7)
        self.assertGreaterEqual(utc["飞行"], 4)
        self.assertGreaterEqual(utc["仅限本职业"], 45)
        # 角色表已招 9 人排在最前面，且全部 63 人均配有 SS~D 综合强度评级
        self.assertTrue(all(c["recruited"] for c in d["characters"][:9]))
        valid_tiers = {"SS", "S", "A", "B", "C", "D"}
        self.assertTrue(all(c["strengthTier"] in valid_tiers for c in d["characters"]))
        c_by_name = {c["name"]: c for c in d["characters"]}
        self.assertEqual(c_by_name["迪托利希"]["strengthTier"], "S")
        self.assertEqual(c_by_name["救世主"]["strengthTier"], "SS")
        self.assertEqual(c_by_name["蕾达"]["strengthTier"], "SS")
        self.assertEqual(c_by_name["伊欧"]["strengthTier"], "B")
        self.assertEqual(c_by_name["伊欧"]["dietrichPriority"], "P1")


class TestExploreModule(unittest.TestCase):
    def test_build_explore_data_priorities_and_spots(self):
        from modules.explore.service import build_explore_data
        d = build_explore_data()
        self.assertEqual(d["module"], "explore")
        self.assertEqual(d["defaultRoute"], "dietrich")
        self.assertIn("dietrich", d["routes"])
        # 验证基于 PR #31 武器评级（SS/S→P0、A→P1、忽视 +3 后缀）重整的商会置换优先级
        bs = d["barterSummary"]
        by_entry = {(e["item"], e["place"]): e for e in bs["entries"]}
        self.assertEqual(by_entry[("雷电剑", "帝都鞑古席翁")]["priority"], "P0")
        self.assertEqual(by_entry[("雷电剑", "帝都鞑古席翁")]["weaponTier"], "SS")
        self.assertEqual(by_entry[("伏力萨", "帝都鞑古席翁")]["priority"], "P0")
        self.assertEqual(by_entry[("伏力萨", "帝都鞑古席翁")]["weaponTier"], "S")
        self.assertEqual(by_entry[("屠马弓", "帝都鞑古席翁")]["priority"], "P0")
        self.assertEqual(by_entry[("屠马弓", "帝都鞑古席翁")]["weaponTier"], "S")
        self.assertEqual(by_entry[("达·米纳手甲", "佐托湖")]["priority"], "P1")
        self.assertEqual(by_entry[("达·米纳手甲", "佐托湖")]["weaponTier"], "A")
        self.assertEqual(by_entry[("铁枪", "帝都鞑古席翁")]["priority"], "P2")
        self.assertTrue(by_entry[("巨人戒指", "海都阿雷库托")]["done"])

        dt = d["routes"]["dietrich"]
        self.assertGreater(dt["summary"]["totalSpots"], 150)
        self.assertGreater(dt["summary"]["tierCounts"]["P0"], 30)
        by_name = {s["name"]: s for s in dt["spots"]}
        self.assertEqual(by_name["亚特拉山顶"]["priority"], "P0")
        self.assertIn("奥利哈钢", by_name["亚特拉山顶"]["highlights"])
        # P0 真实缺口素材采集点：尤那魅(SS雷电剑)、挪亚果(S伏力萨+封魔盾)、恩黎艾特(S屠马弓)、青津吉(P0祝胜宝珠)
        self.assertEqual(by_name["达玛先海岬"]["priority"], "P0")
        self.assertTrue(by_name["达玛先海岬"]["hasBarterLack"])
        self.assertEqual(by_name["观日岭"]["priority"], "P0")
        self.assertEqual(by_name["阳光花园"]["priority"], "P0")
        self.assertEqual(by_name["内皮亚之森"]["priority"], "P0")
        # 迷宫宝箱 S 级武器猎兽弓同步升为 P0
        self.assertEqual(by_name["迦连堡垒残迹"]["priority"], "P0")
        # 巨人戒指已换完，布隆提斯湖(辉光鱼)自动降为 P2 不再干扰地图 P0
        self.assertEqual(by_name["布隆提斯湖"]["priority"], "P2")
        self.assertTrue(by_name["亚特拉山顶"]["nearestStation"])
        self.assertTrue(by_name["亚特拉山顶"]["fwMapUrl"].startswith("https://fire-emblem-fw.site/map.html#n:"))


if __name__ == "__main__":
    unittest.main()
