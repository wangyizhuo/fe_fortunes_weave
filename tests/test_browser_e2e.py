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
ALL_TABS = ["meal", "items", "next", "plan", "past", "l45", "long", "opts", "mine"]


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


class _ReuseTCPServer(socketserver.TCPServer):
    allow_reuse_address = True


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
        cls.browser = cls.pw.chromium.launch(args=["--disable-dev-shm-usage"])

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()
        cls.httpd.shutdown()
        cls.httpd.server_close()

    def test_all_tabs_desktop_and_mobile_no_errors_no_overflow(self):
        fetched_json = set()
        for width, height in ((1200, 900), (390, 844)):
            page = self.browser.new_page(viewport={"width": width, "height": height})
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

            for tab in ALL_TABS:
                page.goto(f"{self.base_url}#{tab}", wait_until="domcontentloaded")
                page.wait_for_selector("#view > *", timeout=8000)
                page.wait_for_timeout(150)

                # 展开所有折叠块一起检查排版和渲染内容
                page.evaluate("() => document.querySelectorAll('#view details').forEach(d => d.open = true)")
                page.wait_for_timeout(50)

                check = page.evaluate(
                    """(vw) => {
                      const sw = document.documentElement.scrollWidth;
                      const txt = document.querySelector('#view')?.innerText || '';
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
            page.close()

        # 确认浏览器通过 HTTP 动态拉取了四大独立 JSON 数据文件
        self.assertTrue(
            {"manifest.json", "affinity.json", "items.json", "route.json"} <= fetched_json,
            f"未检测到独立 JSON 加载，实际加载: {fetched_json}",
        )

    def test_interactive_flows_across_three_domains(self):
        page = self.browser.new_page(viewport={"width": 1200, "height": 900})
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

        # 3) 路线规划：验证角色筛选、动态规则说明（无过时文案）、以及重开章节修复
        page.click('#domains a[data-domain="route"]')
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

        # 可选截图导出（供视觉验收）
        shot_dir = os.environ.get("FE_E2E_SCREENSHOT_DIR")
        if shot_dir:
            Path(shot_dir).mkdir(parents=True, exist_ok=True)
            for tab, fname in (("meal", "01_affinity.png"), ("items", "02_items.png"), ("plan", "03_route.png")):
                page.goto(f"{self.base_url}#{tab}", wait_until="domcontentloaded")
                page.wait_for_selector("#view > *")
                page.wait_for_timeout(200)
                if tab == "plan":
                    page.click('#who button[data-who=""]')
                    page.wait_for_timeout(150)
                page.screenshot(path=str(Path(shot_dir) / fname), full_page=False)

        self.assertEqual(page_errors, [])
        page.close()


if __name__ == "__main__":
    unittest.main()
