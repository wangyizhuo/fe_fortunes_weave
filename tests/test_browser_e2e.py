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
ALL_TABS = ["next", "plan", "past", "l45", "long", "opts", "mine", "meal", "explore", "items", "classes", "skills", "chars"]


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
    request_queue_size = 128


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

    @classmethod
    def tearDownClass(cls):
        cls.pw.stop()
        cls.httpd.shutdown()
        cls.httpd.server_close()

    def setUp(self):
        args = ["--disable-gpu", "--no-sandbox", "--disable-dev-shm-usage", "--disable-setuid-sandbox"]
        try:
            self.browser = self.pw.chromium.launch(channel="chromium", args=args)
        except Exception:
            self.browser = self.pw.chromium.launch(args=args)

    def tearDown(self):
        if getattr(self, "browser", None):
            self.browser.close()

    def _new_ctx_page(self, width: int, height: int):
        ctx = self.browser.new_context(viewport={"width": width, "height": height})
        ctx.route("**/*fonts.g*/*", lambda r: r.fulfill(status=200, content_type="text/css", body=""))
        page = ctx.new_page()
        return ctx, page

    def _goto_safe(self, ctx, page, url: str, on_new_page=None):
        """在容器环境中若 Chromium 渲染进程偶发崩溃，重建标签页重试导航（不吞 JS/断言错误）。"""
        for attempt in range(3):
            try:
                page.goto(url, wait_until="domcontentloaded")
                return page
            except Exception as exc:
                if "Page crashed" not in str(exc) or attempt == 2:
                    raise
                try:
                    page.close()
                except Exception:
                    pass
                page = ctx.new_page()
                if on_new_page:
                    on_new_page(page)
        return page

    def test_all_tabs_desktop_and_mobile_no_errors_no_overflow(self):
        import json as _json
        with open(OUT_DIR / "data" / "classes.json", encoding="utf-8") as fh:
            cls_names = {c["name"] for c in _json.load(fh)["classes"]}
        with open(OUT_DIR / "data" / "skills.json", encoding="utf-8") as fh:
            sk_data = _json.load(fh)
        sk_names = {s["name"] for s in sk_data["skills"]}
        ch_names = {c["name"] for c in sk_data["characters"]}
        valid_by_kind = {"class": cls_names, "skill": sk_names, "char": ch_names}

        fetched_json = set()
        seen_link_kinds = set()
        for width, height in ((1200, 900), (390, 844)):
            ctx, page = self._new_ctx_page(width, height)
            page_errors = []
            console_errors = []
            failed_reqs = []

            def _bind(pg):
                pg.on("pageerror", lambda err: page_errors.append(str(err)))
                pg.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
                pg.on(
                    "response",
                    lambda resp: (
                        fetched_json.add(resp.url.split("/")[-1]) if resp.url.endswith(".json") and resp.status == 200 else None,
                        failed_reqs.append(f"{resp.status} {resp.url}") if resp.status >= 400 and "fonts.googleapis" not in resp.url else None,
                    ),
                )

            _bind(page)

            for idx, tab in enumerate(ALL_TABS):
                if idx == 0:
                    page = self._goto_safe(ctx, page, f"{self.base_url}#{tab}", _bind)
                else:
                    page.evaluate("t => { location.hash = '#' + t; }", tab)
                page.wait_for_selector("#view > *", timeout=20000)
                page.wait_for_timeout(120)

                if idx == 0 and width == 1200:
                    dom_order = page.evaluate("""() => [...document.querySelectorAll('#domains a')].map(a => a.dataset.domain)""")
                    self.assertEqual(
                        dom_order,
                        ["route", "affinity", "explore", "items", "classes", "skills", "chars"],
                        f"顶部导航 Tab 顺序不符: {dom_order}",
                    )

                # 展开所有折叠块一起检查排版、渲染内容和实体超链接有效性
                page.evaluate("() => document.querySelectorAll('#view details').forEach(d => d.open = true)")
                page.wait_for_timeout(40)

                check = page.evaluate(
                    """(vw) => {
                      const sw = document.documentElement.scrollWidth;
                      const txt = document.querySelector('#view')?.textContent || '';
                      const badWords = ['undefined', 'NaN', '[object Object]'].filter(w => txt.includes(w));
                      const entLinks = [...document.querySelectorAll('#view a[data-ent-kind]')].map(a => ({
                        kind: a.dataset.entKind,
                        name: a.dataset.entName,
                        href: a.getAttribute('href') || '',
                      }));
                      return { overflow: sw > vw + 1 ? sw : 0, badWords, textLen: txt.trim().length, entLinks };
                    }""",
                    width,
                )
                self.assertGreater(check["textLen"], 50, f"[{width}px #{tab}] 页面渲染内容为空")
                self.assertEqual(check["overflow"], 0, f"[{width}px #{tab}] 页面横向溢出 {check['overflow']}px > {width}px")
                self.assertEqual(check["badWords"], [], f"[{width}px #{tab}] 页面出现异常文字: {check['badWords']}")
                for lk in check["entLinks"]:
                    k = lk["kind"]
                    seen_link_kinds.add(k)
                    self.assertIn(k, valid_by_kind, f"[{width}px #{tab}] 未知实体链接类型: {lk}")
                    self.assertIn(lk["name"], valid_by_kind[k], f"[{width}px #{tab}] 死链实体: {lk}")
                    self.assertTrue(lk["href"].startswith("#"), f"[{width}px #{tab}] 非规范 hash 链接: {lk}")

            self.assertEqual(page_errors, [], f"[{width}px] JS pageerror: {page_errors}")
            self.assertEqual(console_errors, [], f"[{width}px] console.error: {console_errors}")
            self.assertEqual(failed_reqs, [], f"[{width}px] HTTP 错误请求: {failed_reqs}")
            ctx.close()

        self.assertEqual(seen_link_kinds, {"class", "skill", "char"}, f"应覆盖全部三类实体超链接，实际: {seen_link_kinds}")

        # 确认浏览器通过 HTTP 动态拉取了全部独立 JSON 数据文件
        self.assertTrue(
            {"manifest.json", "affinity.json", "items.json", "explore.json", "classes.json", "skills.json", "route.json"} <= fetched_json,
            f"未检测到独立 JSON 加载，实际加载: {fetched_json}",
        )

    def test_interactive_flows_across_three_domains(self):
        ctx, page = self._new_ctx_page(1200, 900)
        page_errors = []
        page.on("pageerror", lambda err: page_errors.append(str(err)))

        # 1) 友好度培养：四大主角、待挖角名册与迪线已满足筛选 + 菜单搜索
        on_err = lambda pg: pg.on("pageerror", lambda err: page_errors.append(str(err)))
        page = self._goto_safe(ctx, page, f"{self.base_url}#meal", on_err)
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

        # 2) 道具 / 材料采集：点一级导航切换 + 武器评级总榜 + 分类筛选 + 材料反查搜索
        page.click('#domains a[data-domain="items"]')
        page.wait_for_selector("#itemQuery")
        items_init_txt = page.inner_text("#view")
        self.assertIn("最强武器评级总榜", items_init_txt)
        page.click('button[data-item-tab="tiers"]')
        page.wait_for_timeout(100)
        wt_txt = page.inner_text("#view")
        self.assertIn("雷电剑", wt_txt)
        self.assertIn("净化剑", wt_txt)
        self.assertIn("伏力萨", wt_txt)
        page.click('button[data-item-tab="all"]')
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

        # 2.5) 探索规划：采集材料缺口交叉验证表 + 铁枪 P0 + 高显眼世界地图标记 + 缺口直达定位
        page.click('#domains a[data-domain="explore"]')
        page.wait_for_selector("#expMapSvg")
        self.assertGreater(page.locator("#expMapSvg .exp-pin").count(), 15)
        exp_txt = page.inner_text("#view")
        self.assertIn("亚特拉山顶", exp_txt)
        self.assertIn("采集材料缺口交叉验证", exp_txt)
        self.assertIn("铁枪", exp_txt)
        self.assertIn("下载高清标记地图 PNG", exp_txt)
        self.assertGreater(page.locator("table.exp-gap-tbl tbody tr").count(), 5)
        page.click('button[data-exp-mat="尤那魅"]')
        page.wait_for_timeout(100)
        exp_q_txt = page.inner_text("#view")
        self.assertIn("达玛先海岬", exp_q_txt)
        self.assertIn("流浪者古庭", exp_q_txt)
        page.click('button[data-exp-preset="barter_p0"]')
        page.wait_for_timeout(100)
        bp0_txt = page.inner_text("#view")
        self.assertIn("观日岭", bp0_txt)
        self.assertIn("阳光花园", bp0_txt)
        page.click('button[data-exp-preset="dungeons"]')
        page.wait_for_timeout(100)
        self.assertIn("迦连堡垒残迹", page.inner_text("#view"))
        page.click('button[data-exp-preset="p0_gather"]')
        page.wait_for_timeout(80)

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
        # 职业保底每属性一列 + 阶段内独立排序（点击 防 降序/升序，初级与中级各自独立排序不跨阶段混排）+ 数值列宽度守卫
        self.assertIn("职业保底 / 转职保底（每属性一列", page.inner_text("#view"))
        max_num_w = page.evaluate("""() => Math.max(...[...document.querySelectorAll('table.cls-tbl td.n')].map(td => Math.round(td.getBoundingClientRect().width)))""")
        self.assertLessEqual(max_num_w, 90, f"职业表格数值列异常撑宽：{max_num_w}px > 90px")
        page.locator('button[data-cls-sort="min:def"]').first.click()
        page.wait_for_timeout(100)
        sorted_desc = page.evaluate("""() => ({
          basic: [...document.querySelectorAll('[data-cls-tier-sec="初级"] tr[data-cls-name]')].map(r => r.dataset.clsName),
          mid: [...document.querySelectorAll('[data-cls-tier-sec="中级"] tr[data-cls-name]')].map(r => r.dataset.clsName),
        })""")
        self.assertEqual(len(sorted_desc["basic"]), 5)
        self.assertEqual(len(sorted_desc["mid"]), 12)
        self.assertEqual(sorted_desc["basic"][0], "士兵")
        self.assertEqual(sorted_desc["basic"][-1], "诅咒师")
        self.assertIn(sorted_desc["mid"][0], ("重装步兵", "轻骑兵", "战车兵", "骑甲鸵兵"))
        page.locator('button[data-cls-sort="min:def"]').first.click()
        page.wait_for_timeout(100)
        sorted_asc_basic = page.evaluate("""() => [...document.querySelectorAll('[data-cls-tier-sec="初级"] tr[data-cls-name]')].map(r => r.dataset.clsName)""")
        self.assertEqual(sorted_asc_basic[0], "诅咒师")
        self.assertEqual(sorted_asc_basic[-1], "士兵")
        page.click('button[data-cls-sort-reset]')
        page.wait_for_timeout(80)

        # 4) 技能图鉴：一个技能一行表格 + 生效兵种 Checkbox 筛选 + 评级筛选 S + 角色表限定说明 + 角色特有筛选 + 切换角色 SS~D 评级与 12 项熟练度矩阵
        page.click('#domains a[data-domain="skills"]')
        page.wait_for_selector("#skSearch")
        self.assertGreater(page.locator("table.sk-tbl tbody tr.sk-row").count(), 20)
        # 生效兵种 Checkbox：勾选重装 -> 命中重装移动术+1、排除体格+（无兵种限制）与穿铠（对敌特攻），并验证列间零重叠 + 点击角色跳转角色页
        page.check('input[data-sk-ut="重装"]')
        page.wait_for_timeout(100)
        arm_txt = page.inner_text("#view")
        self.assertIn("重装移动术+1", arm_txt)
        self.assertIn("限 重装", arm_txt)
        self.assertIn("S 级", arm_txt)
        self.assertIn("重装术 D", arm_txt)
        self.assertIn("重装术 C", arm_txt)
        self.assertIn("重装术 B", arm_txt)
        self.assertNotIn("穿铠", arm_txt)
        self.assertNotIn("传送", arm_txt)
        # 校验表格所有单元格无横向文字溢出导致相邻列重叠，且评级列紧凑
        layout_chk = page.evaluate("""() => {
          const tbl = document.querySelector('table.sk-tbl');
          const tierW = tbl.querySelector('td.sk-c-tier').getBoundingClientRect().width;
          const overflows = [];
          for (const td of tbl.querySelectorAll('tbody td')) {
            if (td.scrollWidth > td.clientWidth + 2) {
              overflows.push({ cls: td.className, sw: td.scrollWidth, cw: td.clientWidth });
            }
          }
          return { tierW, overflows };
        }""")
        self.assertLess(layout_chk["tierW"], 95, f"评级列过宽: {layout_chk['tierW']}px")
        self.assertEqual(layout_chk["overflows"], [], f"技能表单元格文字溢出重叠: {layout_chk['overflows']}")
        # 点击技能行内角色超链接 -> 自动切到独立 #chars/努蒂奴 深链定位页
        page.click('a.sk-char-link[data-ent-kind="char"][data-ent-name="努蒂奴"]')
        page.wait_for_selector('[data-ent-focused="true"]')
        jump_txt = page.inner_text("#view")
        self.assertIn("当前定位角色：努蒂奴", jump_txt)
        self.assertIn("查看路线规划", jump_txt)
        # 在角色卡内点击初始职业「飞驼兵」（自动归一化至 飞鸵兵） -> 跳至 #classes/飞鸵兵 深链定位页
        page.click('a.ent-link[data-ent-kind="class"][data-ent-name="飞鸵兵"]')
        page.wait_for_selector('tr[data-cls-name="飞鸵兵"][data-ent-focused="true"]')
        cls_jump_txt = page.inner_text("#view")
        self.assertIn("当前定位职业：飞鸵兵", cls_jump_txt)
        # 在职业行内点击技能超链接 -> 跳回 #skills/<技能名> 深链定位页
        page.click('tr[data-cls-name="飞鸵兵"] a.ent-link[data-ent-kind="skill"]')
        page.wait_for_selector('tr.sk-row[data-ent-focused="true"]')
        self.assertIn("当前定位技能：", page.inner_text("#view"))

        page.click('a[data-sk-clear]')
        page.wait_for_timeout(80)
        page.check('input[data-sk-ut="飞行"]')
        page.wait_for_timeout(100)
        arm_fly_txt = page.inner_text("#view")
        self.assertIn("高速飞行术+", arm_fly_txt)
        self.assertIn("限 飞行", arm_fly_txt)
        page.click('button[data-sk-clear]')
        page.wait_for_timeout(80)
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

        # 4.5) 独立顶栏「角色图鉴」（#chars）：验证 63 角色筛选与 SS 档 3 人
        page.click('#domains a[data-domain="chars"]')
        page.wait_for_selector("#charSearch")
        ch_txt = page.inner_text("#view")
        self.assertIn("迪托利希", ch_txt)
        self.assertIn("个人特技", ch_txt)
        page.click('button[data-ch-grp="all"]')
        page.click('button[data-ch-tier="SS"]')
        page.wait_for_timeout(100)
        ss_txt = page.inner_text("#view")
        for top3 in ("救世主", "蕾达", "赛奥朵拉"):
            self.assertIn(top3, ss_txt)
        self.assertIn("展示 3 位角色", ss_txt)

        # 5) 路线规划：验证顶部 #who 分列 P0/P1/P2 且当前主角首位，#next 总览表同序
        page.click('#domains a[data-domain="route"]')
        page.wait_for_selector('tr[data-next-row]')
        who_tiers = page.evaluate("""() => [...document.querySelectorAll('#who [data-who-tier]')].map(e => e.dataset.whoTier)""")
        self.assertEqual(who_tiers, ["P0", "P1", "P2"])
        next_rows = page.evaluate(
            """() => [...document.querySelectorAll('tr[data-next-row]')].map(tr => ({
                name: tr.dataset.nextRow, tier: tr.dataset.tier, strength: tr.dataset.strength
            }))"""
        )
        self.assertEqual(
            [r["name"] for r in next_rows],
            ["迪托利希", "艾丝梅拉尔达", "米迦艾拉", "法毕欧", "奇洛伊卡", "伊欧", "杨界", "努蒂奴", "乌尔坦德"],
        )
        self.assertEqual(next(r["tier"] for r in next_rows if r["name"] == "伊欧"), "P1")
        next_txt = page.inner_text("#view")
        self.assertIn("全员下一步总览（主角优先 · 按 P 级 → 强度 → 名字排序", next_txt)
        self.assertIn("何时停下当前职业升级", next_txt)
        self.assertNotIn("下一次跳过", next_txt)

        page.wait_for_selector('#who button[data-who="esmeralda"]')
        page.click('#routeTabs a[data-v="plan"]')
        page.wait_for_timeout(150)
        plan_txt = page.inner_text("#view")
        self.assertNotIn("11-05 截图", plan_txt)
        self.assertNotIn("11-11 起不再要求", plan_txt)
        self.assertIn("恶棍（Lv26，判定 58.16%）", plan_txt)
        self.assertIn("防 +10（平均 5.8）", plan_txt)
        self.assertIn("弓箭手（Lv25", plan_txt)
        self.assertIn("天翼兵（Lv21", plan_txt)
        self.assertIn("Lv34 留作上级转职停止", plan_txt)
        self.assertIn("严格更优", plan_txt)

        # 聚焦杨界验证「改考其他单中级对比（替 萨满巫师 -> 牧师）」及折叠式考试选择器、等级+考试标签与提前考按钮
        page.click('#who button[data-who="yokai"]')
        page.wait_for_timeout(150)
        self.assertGreater(page.locator("details.exam-pick-fold").count(), 0)
        page.evaluate("() => document.querySelectorAll('#view details').forEach(d => d.open = true)")
        yk_txt = page.inner_text("#view")
        self.assertIn("改考其他单中级对比（替换 萨满巫师", yk_txt)
        self.assertIn("Lv26 考试", yk_txt)
        self.assertIn("考试（到 牧师）", yk_txt)
        self.assertIn("提前考 牧师", yk_txt)

        # 聚焦艾丝梅拉尔达：P0 不计金币成本自动推荐 Lv21 天翼兵 + Lv30 重装步兵，确认「展开所有等级」不勾已完成
        page.click('#who button[data-who="esmeralda"]')
        page.wait_for_timeout(150)
        page.click('button[data-expand-all]')
        page.wait_for_timeout(100)
        sd_el = page.query_selector('.fullwrap input.sd')
        if sd_el:
            self.assertFalse(sd_el.is_checked(), "展开所有等级不应自动勾选显示已经走过的步骤")
        self.assertIn("预选", page.inner_text("#view"))
        page.evaluate("() => document.querySelectorAll('#view details').forEach(d => d.open = true)")
        es_txt = page.inner_text("#view")
        self.assertIn("考试（到 天翼兵）（新职业", es_txt)
        self.assertIn("考试（到 重装步兵）（新职业", es_txt)

        # 验证 #opts（职业选择）：移除 Lv35->45 额外影响列 + 明确标注转职保底/无转职保底 + 红绿着色 + 改去该级变化 + 核心属性速览 + 严格更优/同分口径
        page.click('#who button[data-who="michaela"]')
        page.click('#routeTabs a[data-v="opts"]')
        page.wait_for_timeout(150)
        page.evaluate("() => document.querySelectorAll('#view details').forEach(d => d.open = true)")
        opts_txt = page.inner_text("#view")
        self.assertNotIn("→45 额外影响", opts_txt)
        self.assertNotIn("现在减它", opts_txt)
        self.assertIn("无转职保底", opts_txt)
        self.assertIn("已含转职保底口径", opts_txt)
        self.assertIn("核心属性最高选项速览", opts_txt)
        self.assertIn("改去该级变化", opts_txt)
        self.assertIn("严格更优", opts_txt)
        self.assertGreater(page.locator("#view .sdiff.up, #view .sdiff.dn").count(), 0)

        # 努蒂奴：展示 力+速 之和排行 与「仅吃转职保底 · 不升级」方案；杨界：跳过/考试改用纯整数加权分（无 7.5 小数）
        page.click('#who button[data-who="nutino"]')
        page.wait_for_timeout(120)
        nu_opts_txt = page.inner_text("#view")
        self.assertIn("力+速 之和排行", nu_opts_txt)
        self.assertIn("仅吃转职保底 · 不升级", nu_opts_txt)
        page.click('#who button[data-who="yokai"]')
        page.wait_for_timeout(120)
        yk_opts_txt = page.inner_text("#view")
        self.assertNotIn("7.5 分", yk_opts_txt)
        self.assertIn("加权 8 分", yk_opts_txt)

        # 6) 我的决定（#mine）：验证角色排序同序、新路线方案选择、展开 9 项具体能力差、技能等级预估、Plan Mode 内联批注与持久化
        page.click('#who button[data-who=""]')
        page.click('#routeTabs a[data-v="mine"]')
        page.wait_for_selector('input[data-rpick="努蒂奴"]')
        mine_chars = page.evaluate("""() => [...document.querySelectorAll('article[data-rp-char]')].map(el => el.dataset.rpChar)""")
        self.assertEqual(
            mine_chars,
            ["迪托利希", "艾丝梅拉尔达", "米迦艾拉", "法毕欧", "奇洛伊卡", "伊欧", "杨界", "努蒂奴", "乌尔坦德"],
        )
        mine_txt = page.inner_text("#view")
        self.assertIn("新路线方案选择与确认", mine_txt)
        self.assertIn("防+3", mine_txt)
        self.assertIn("当前预估 8%", mine_txt)
        self.assertIn("格斗术 E→D+", mine_txt)
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

        # 重新打开页面确认方案选择 + Plan Mode 批注均已保存在浏览器 localStorage
        page2 = ctx.new_page()
        page.close()
        page = page2
        on_err(page)
        page = self._goto_safe(ctx, page, f"{self.base_url}#mine", on_err)
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
                ("next", "01_next.png"),
                ("meal", "02_affinity.png"),
                ("explore", "03_explore.png"),
                ("items", "04_items.png"),
                ("classes", "05_classes.png"),
                ("skills", "06_skills.png"),
                ("chars", "07_chars.png"),
                ("opts", "08_opts.png"),
            ):
                page.goto(f"{self.base_url}#{tab}", wait_until="domcontentloaded")
                page.wait_for_selector("#view > *")
                page.wait_for_timeout(200)
                page.screenshot(path=str(Path(shot_dir) / fname), full_page=False)

        self.assertEqual(page_errors, [])
        page.close()
        ctx.close()


if __name__ == "__main__":
    unittest.main()
