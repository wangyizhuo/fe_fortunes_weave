"""真实浏览器（Playwright Chromium）端到端页面验证套件。

验证内容：
  1. 桌面（1200×900）与手机（390×844）双视口访问全部 9 个视图：
     #meal / #items / #next / #plan / #past / #l45 / #long / #opts / #mine
  2. 零 JS 报错、零 console.error、零失败网络请求（HTTP >= 400）、零横向溢出、零 undefined/NaN/[object Object]
  3. 验证页面确实通过 HTTP 动态加载独立的 ./data/*.json 模块数据
  4. 真实交互验证：友好度搜索与筛选、道具分类与材料反查、路线角色切换与展开、无过时 11-05 文案与无幽灵职业
"""
from __future__ import annotations

import http.server
import os
import socketserver
import threading
import unittest
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "out"
ALL_TABS = ["meal", "items", "classes", "skills", "next", "plan", "past", "l45", "long", "opts", "mine"]


class _QuietUTF8Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(OUT_DIR), **kwargs)

    def guess_type(self, path):
        t = super().guess_type(path)
        if t in ("text/html", "application/json", "text/plain", "text/css", "application/javascript"):
            return t + "; charset=utf-8"
        return t

    def log_message(self, format, *args):
        pass


class _ReuseTCPServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


class TestBrowserE2E(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not (OUT_DIR / "index.html").exists():
            raise RuntimeError("请先运行 python3 build_site.py 生成 out/")
        cls.httpd = _ReuseTCPServer(("127.0.0.1", 0), _QuietUTF8Handler)
        cls.port = cls.httpd.server_address[1]
        cls.base_url = f"http://127.0.0.1:{cls.port}/index.html"
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()

        cls.pw = sync_playwright().start()
        cls.browser = cls.pw.chromium.launch(args=["--disable-gpu"])

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()
        cls.httpd.shutdown()
        cls.httpd.server_close()

    def _new_page(self, width: int, height: int):
        return self.browser.new_page(viewport={"width": width, "height": height})

    def test_all_tabs_desktop_and_mobile_no_errors_no_overflow(self):
        fetched_json = set()
        for width, height in ((1200, 900), (390, 844)):
            ctx = self.browser.new_context(viewport={"width": width, "height": height})
            page = ctx.new_page()
            page_errors = []
            console_errors = []
            failed_reqs = []

            page.on("pageerror", lambda err: page_errors.append(str(err)))
            page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
            page.on(
                "response",
                lambda resp: (
                    fetched_json.add(resp.url.split("/")[-1]) if resp.url.endswith(".json") and resp.status == 200 else None,
                    failed_reqs.append(f"{resp.status} {resp.url}") if resp.status >= 400 and "fonts.googleapis" not in resp.url else None,
                ),
            )

            for idx, tab in enumerate(ALL_TABS):
                if idx == 0:
                    page.goto(f"{self.base_url}#{tab}", wait_until="domcontentloaded")
                else:
                    page.evaluate("t => { location.hash = '#' + t; }", tab)
                page.wait_for_selector("#view > *", timeout=8000)
                page.wait_for_timeout(120)

                # 展开所有折叠块一起检查排版和渲染内容
                page.evaluate("() => document.querySelectorAll('#view details').forEach(d => d.open = true)")
                page.wait_for_timeout(40)

                check = page.evaluate(
                    """(vw) => {
                      const sw = document.documentElement.scrollWidth;
                      const txt = document.querySelector('#view')?.textContent || '';
                      const badWords = ['undefined', 'NaN', '[object Object]'].filter(w => txt.includes(w));
                      return { overflow: sw > vw + 1 ? sw : 0, badWords, textLen: txt.trim().length };
                    }""",
                    width,
                )
                self.assertGreater(check["textLen"], 50, f"[{width}px #{tab}] 页面渲染内容为空")
                self.assertEqual(check["overflow"], 0, f"[{width}px #{tab}] 页面横向溢出 {check['overflow']}px > {width}px")
                self.assertEqual(check["badWords"], [], f"[{width}px #{tab}] 页面出现异常文字: {check['badWords']}")

            self.assertEqual(page_errors, [], f"[{width}px] JS pageerror: {page_errors}")
            self.assertEqual(console_errors, [], f"[{width}px] console.error: {console_errors}")
            self.assertEqual(failed_reqs, [], f"[{width}px] HTTP 错误请求: {failed_reqs}")
            ctx.close()

        # 确认浏览器通过 HTTP 动态拉取了全部独立 JSON 数据文件
        self.assertTrue(
            {"manifest.json", "affinity.json", "items.json", "classes.json", "skills.json", "route.json"} <= fetched_json,
            f"未检测到独立 JSON 加载，实际加载: {fetched_json}",
        )

    def test_interactive_flows_across_three_domains(self):
        page = self._new_page(1200, 900)
        page_errors = []
        page.on("pageerror", lambda err: page_errors.append(str(err)))

        # 1) 友好度培养：四大主角、待挖角名册与迪线已满足筛选 + 菜单搜索
        page.goto(f"{self.base_url}#meal", wait_until="domcontentloaded")
        page.wait_for_selector("#affQuery")
        meal_txt = page.inner_text("#view")
        for lord in ("迪托利希", "蕾达", "凯伊", "赛奥朵拉"):
            self.assertIn(lord, meal_txt)
        self.assertIn("主角与待挖角角色", meal_txt)
        page.click('button[data-aff-rf="met"]')
        page.wait_for_timeout(100)
        met_txt = page.inner_text("#view")
        for met_name in ("哥莱亚斯", "班迪兹", "杰斯塔", "奥琳琵娅", "莱桑达", "索绯雅", "乌修拉"):
            self.assertIn(met_name, met_txt)
        page.click('button[data-aff-rf="todo"]')
        page.wait_for_timeout(100)
        self.assertIn("希蒙", page.inner_text("#view"))
        page.click('button[data-aff-rf="important"]')
        page.fill("#affQuery", "糖浆炖梨")
        page.wait_for_timeout(100)
        self.assertIn("当前显示 1 道", page.inner_text("#view"))
        page.fill("#affQuery", "")
        page.wait_for_timeout(50)

        # 2) 道具 / 材料采集：点一级导航切换 + 分类筛选 + 材料反查搜索
        page.click('#domains a[data-domain="items"]')
        page.wait_for_selector("#itemQuery")
        page.click('button[data-item-cat="教本"]')
        page.wait_for_timeout(100)
        self.assertIn("魔法教本", page.inner_text("#view"))

        page.click('button[data-item-cat="全部"]')
        page.click('button[data-item-tab="materials"]')
        page.fill("#itemQuery", "バク")
        page.wait_for_timeout(100)
        mat_txt = page.inner_text("#view")
        self.assertIn("采集 / 钓鱼材料反查表", mat_txt)
        self.assertIn("斩马刀", mat_txt)

        # 3) 职业图鉴：按阶级分组 + 可用技能 Checkbox 筛选（AND / OR + 清空）
        page.click('#domains a[data-domain="classes"]')
        page.wait_for_selector("#clsQuery")
        cls_txt = page.inner_text("#view")
        for t in ("基础职业", "初级职业", "中级职业", "上级职业", "最上级职业", "神将职业"):
            self.assertIn(t, cls_txt)
        page.check('input[data-cls-skill="剑术"]')
        page.check('input[data-cls-skill="马术"]')
        page.wait_for_timeout(100)
        and_txt = page.inner_text("#view")
        self.assertIn("轻骑兵", and_txt)
        self.assertNotIn("萨满巫师", and_txt)
        page.click('button[data-cls-tier="中级"]')
        page.wait_for_timeout(100)
        mid_txt = page.inner_text("#view")
        self.assertIn("轻骑兵", mid_txt)
        self.assertNotIn("上级职业", mid_txt)
        page.click('button[data-cls-clear]')
        page.wait_for_timeout(100)
        self.assertIn("当前匹配 60 / 60", page.inner_text("#view"))
        # 优势属性 Checkbox 筛选：力 + 防 -> 命中重装步兵，不命中萨满巫师
        page.check('input[data-cls-stat="力"]')
        page.check('input[data-cls-stat="防"]')
        page.wait_for_timeout(100)
        adv_txt = page.inner_text("#view")
        self.assertIn("重装步兵", adv_txt)
        self.assertNotIn("萨满巫师", adv_txt)
        page.click('button[data-cls-clear]')
        page.wait_for_timeout(80)

        # 4) 技能图鉴：评级筛选 S + 角色表限定说明 + 角色特有筛选 + 切换角色 SS~D 评级与 12 项熟练度矩阵
        page.click('#domains a[data-domain="skills"]')
        page.wait_for_selector("#skSearch")
        page.click('button[data-sk-rating="S"]')
        page.wait_for_timeout(100)
        s_txt = page.inner_text("#view")
        self.assertIn("体格+", s_txt)
        self.assertIn("角色表限定", s_txt)
        self.assertIn("传送", s_txt)
        page.click('button[data-sk-scope="unique"]')
        page.wait_for_timeout(100)
        u_txt = page.inner_text("#view")
        self.assertIn("秘传·落燕+", u_txt)
        self.assertIn("角色特有（唯一）", u_txt)
        page.click('button[data-sk-tab="chars"]')
        page.wait_for_timeout(100)
        ch_txt = page.inner_text("#view")
        self.assertIn("迪托利希", ch_txt)
        self.assertIn("个人特技", ch_txt)
        page.click('button[data-sk-cgrp="all"]')
        page.click('button[data-sk-ctier="SS"]')
        page.wait_for_timeout(100)
        ss_txt = page.inner_text("#view")
        for top3 in ("救世主", "蕾达", "赛奥朵拉"):
            self.assertIn(top3, ss_txt)
        self.assertIn("展示 3 位角色", ss_txt)

        # 5) 路线规划：验证 #next 全员总览表严格按 P → 强度 → 名字排序（且伊欧在 P1）、角色筛选、动态规则说明
        page.click('#domains a[data-domain="route"]')
        page.wait_for_selector('tr[data-next-row]')
        next_rows = page.evaluate(
            """() => [...document.querySelectorAll('tr[data-next-row]')].map(tr => ({
                name: tr.dataset.nextRow, tier: tr.dataset.tier, strength: tr.dataset.strength
            }))"""
        )
        self.assertEqual(
            [r["name"] for r in next_rows],
            ["艾丝梅拉尔达", "迪托利希", "米迦艾拉", "法毕欧", "奇洛伊卡", "伊欧", "杨界", "努蒂奴", "乌尔坦德"],
        )
        self.assertEqual(next(r["tier"] for r in next_rows if r["name"] == "伊欧"), "P1")
        next_txt = page.inner_text("#view")
        self.assertIn("全员下一步总览（按 P 级 → 强度 → 名字排序", next_txt)

        page.wait_for_selector('#who button[data-who="esmeralda"]')
        page.click('#routeTabs a[data-v="plan"]')
        page.wait_for_timeout(150)
        plan_txt = page.inner_text("#view")
        self.assertNotIn("11-05 截图", plan_txt)
        self.assertNotIn("11-11 起不再要求", plan_txt)

        # 聚焦艾丝梅拉尔达，确认天翼兵不再被误标为「已有」
        page.click('#who button[data-who="esmeralda"]')
        page.wait_for_timeout(150)
        page.evaluate("() => document.querySelectorAll('#view details').forEach(d => d.open = true)")
        es_txt = page.inner_text("#view")
        self.assertIn("考试（到 天翼兵）（新职业", es_txt)

        # 6) 我的决定（#mine）：验证新路线方案选择、展开 9 项具体能力差、Plan Mode 内联批注（含定位与版本号）与持久化
        page.click('#who button[data-who=""]')
        page.click('#routeTabs a[data-v="mine"]')
        page.wait_for_selector('input[data-rpick="努蒂奴"]')
        mine_txt = page.inner_text("#view")
        self.assertIn("新路线方案选择与确认", mine_txt)
        self.assertIn("防+3", mine_txt)
        self.assertIn("需提前 NS Online S/L 实测", mine_txt)
        self.assertIn("Plan Mode 批注：已开启", mine_txt)
        page.click('input[data-rpick="努蒂奴"][value="safe_fallback"]')
        page.wait_for_timeout(100)
        self.assertIn("你已选择：Lv18 考重装步兵", page.inner_text("#view"))

        # Plan Mode 内联批注：打开法毕欧卡片批注、验证定位与版本号显示、输入并保存、刷新确认持久化
        page.click('button[data-cmt-open="char:法毕欧"]')
        page.wait_for_selector("#cmtDraftInput")
        page.fill("#cmtDraftInput", "法毕欧我要萨满精通，先留着 s2 方案")
        page.click("button[data-cmt-save]")
        page.wait_for_timeout(100)
        saved_txt = page.inner_text("#view")
        self.assertIn("法毕欧我要萨满精通", saved_txt)
        self.assertIn("#mine", saved_txt)
        self.assertIn("待处理 1", saved_txt)

        # 刷新页面确认方案选择 + Plan Mode 批注均已保存在浏览器 localStorage
        page.reload(wait_until="domcontentloaded")
        page.wait_for_selector('input[data-rpick="努蒂奴"]')
        self.assertTrue(page.is_checked('input[data-rpick="努蒂奴"][value="safe_fallback"]'))
        self.assertIn("你已选择：Lv18 考重装步兵", page.inner_text("#view"))
        self.assertIn("法毕欧我要萨满精通", page.inner_text("#view"))

        # 展开批注清单抽屉验证展示与解决
        page.click("button[data-pm-drawer]")
        page.wait_for_timeout(80)
        self.assertIn("法毕欧（P1）", page.inner_text(".pm-drawer"))

        # 可选截图导出（供视觉验收）
        shot_dir = os.environ.get("FE_E2E_SCREENSHOT_DIR")
        if shot_dir:
            Path(shot_dir).mkdir(parents=True, exist_ok=True)
            for tab, fname in (
                ("meal", "01_affinity.png"),
                ("items", "02_items.png"),
                ("classes", "04_classes.png"),
                ("skills", "06_skills.png"),
                ("plan", "03_route.png"),
                ("mine", "05_mine.png"),
            ):
                page.goto(f"{self.base_url}#{tab}", wait_until="domcontentloaded")
                page.wait_for_selector("#view > *")
                page.wait_for_timeout(200)
                if tab == "plan":
                    page.click('#who button[data-who=""]')
                    page.wait_for_timeout(150)
                page.screenshot(path=str(Path(shot_dir) / fname), full_page=False)
            # 也截一张角色技能矩阵速览
            page.goto(f"{self.base_url}#skills", wait_until="domcontentloaded")
            page.wait_for_selector('button[data-sk-tab="chars"]')
            page.click('button[data-sk-tab="chars"]')
            page.wait_for_timeout(200)
            page.screenshot(path=str(Path(shot_dir) / "07_skills_chars.png"), full_page=False)

        self.assertEqual(page_errors, [])
        page.close()


if __name__ == "__main__":
    unittest.main()
