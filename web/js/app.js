/* 应用入口：动态加载独立模块数据（HTTP fetch JSON / file:// 回退）+ 路由 + 事件委托 */
(function (root) {
  const U = root.FE.utils;
  const RL = root.FE.routeLogic;

  const ROUTE_VIEWS = ["next", "plan", "past", "l45", "long", "opts", "mine"];
  const ALL_VIEWS = ["meal", "items", "classes", ...ROUTE_VIEWS];

  let MANIFEST = null;
  let DATA = { affinity: null, items: null, classes: null, route: null };
  let pending = false;

  function setStatus(text, k) {
    const el = document.getElementById("status");
    const live = document.getElementById("live");
    if (el) el.textContent = text;
    if (live) live.className = "live " + (k || "");
  }

  function setSyncStatus(text, warn) {
    const el = document.getElementById("syncStatus");
    if (!el) return;
    el.textContent = text;
    el.classList.toggle("warn", !!warn);
  }

  function domainOf(v) {
    if (v === "meal") return "affinity";
    if (v === "items") return "items";
    if (v === "classes") return "classes";
    return "route";
  }

  function loadBundleScript() {
    return new Promise((resolve, reject) => {
      if (root.FE_BUNDLE_DATA) return resolve(root.FE_BUNDLE_DATA);
      const sc = document.createElement("script");
      sc.src = "./data/bundle_data.js";
      sc.onload = () => (root.FE_BUNDLE_DATA ? resolve(root.FE_BUNDLE_DATA) : reject(new Error("bundle_data.js 未导出数据")));
      sc.onerror = () => reject(new Error("无法加载 ./data/bundle_data.js"));
      document.head.appendChild(sc);
    });
  }

  async function loadModuleData() {
    // 1) HTTP(S) 访问时，按功能模块独立 fetch JSON，彻底分离网页与数据（不重复下载 bundle_data.js）
    if (location.protocol === "http:" || location.protocol === "https:") {
      try {
        const [manifest, affinity, items, classes, route] = await Promise.all([
          fetch("./data/manifest.json", { cache: "no-store" }).then(r => r.json()),
          fetch("./data/affinity.json", { cache: "no-store" }).then(r => r.json()),
          fetch("./data/items.json", { cache: "no-store" }).then(r => r.json()),
          fetch("./data/classes.json", { cache: "no-store" }).then(r => r.json()),
          fetch("./data/route.json", { cache: "no-store" }).then(r => r.json()),
        ]);
        MANIFEST = manifest;
        DATA = { affinity, items, classes, route };
        return;
      } catch (err) {
        const b = await loadBundleScript().catch(() => null);
        if (b) {
          MANIFEST = b.manifest;
          DATA = b;
          return;
        }
        throw err;
      }
    }
    // 2) file:// 离线打开时，动态回退到独立数据文件 ./data/bundle_data.js
    const b = await loadBundleScript().catch(() => null);
    if (b) {
      MANIFEST = b.manifest;
      DATA = b;
      return;
    }
    throw new Error("未找到模块数据（请通过本地 HTTP 服务打开，或先运行 build_site.py 生成 out/data/）");
  }

  const store = root.FE.createStore(() => render(), setStatus);

  function render() {
    const a = document.activeElement;
    if (a && a.closest && a.closest("#view") && a.type === "number") {
      pending = true;
      return;
    }
    const focusInputId = a && a.closest && a.closest("#view") && a.type === "search" ? a.id : null;
    const selStart = focusInputId ? a.selectionStart : null;
    const selEnd = focusInputId ? a.selectionEnd : null;

    pending = false;
    const y = scrollY;
    const view = store.state.view;
    const dom = domainOf(view);

    document.querySelectorAll("#domains a").forEach(el => {
      el.setAttribute("aria-current", el.dataset.domain === dom ? "true" : "false");
    });

    const routeTabs = document.getElementById("routeTabs");
    routeTabs.hidden = dom !== "route";
    routeTabs.querySelectorAll("a").forEach(el => {
      el.setAttribute("aria-current", el.dataset.v === view ? "page" : "false");
    });

    const chars = (DATA.route && DATA.route.chars) || [];
    const whoEl = document.getElementById("who");
    whoEl.hidden = dom !== "route";
    if (dom === "route") {
      whoEl.innerHTML = [["", "全部"], ...chars.map(c => [U.slug(c), U.shortName(c.name)])]
        .map(([k, t]) => `<button type="button" data-who="${k}" aria-pressed="${store.state.focus === k}">${U.esc(t)}</button>`)
        .join("");
    }

    const syncBtn = document.getElementById("syncBtn");
    if (syncBtn) syncBtn.style.display = dom === "route" ? "" : "none";

    const opened = [...document.querySelectorAll("#view details[open][data-keep]")].map(d => d.dataset.keep);
    const V = root.FE.views;
    let html = "";
    if (view === "meal") html = V.renderAffinityView(DATA.affinity, store.state);
    else if (view === "items") html = V.renderItemsView(DATA.items, store.state);
    else if (view === "classes") html = V.renderClassesView(DATA.classes, store.state);
    else html = V.renderRouteView(view, DATA.route, store.state);

    const viewEl = document.getElementById("view");
    viewEl.innerHTML = html;

    document.querySelectorAll("#view details.more").forEach((d, i) => {
      d.dataset.keep = (d.closest("[data-key]")?.dataset.key || "") + (d.closest("[data-slug]")?.dataset.slug || "") + i;
      if (opened.includes(d.dataset.keep)) d.open = true;
    });

    const foot = document.getElementById("foot");
    if (foot && DATA.route) {
      const rm = DATA.route.rulesMeta || {};
      const built = MANIFEST && MANIFEST.builtAt ? ` · 数据构建于 ${MANIFEST.builtAt}` : "";
      foot.textContent = `架构：四大模块（友好度培养 / 道具与材料采集 / 职业图鉴 / 路线规划）前后端数据与逻辑解耦加载（当前快照 ${rm.shotKey || "latest"}，名声 Lv${rm.renown ?? "?"}${built}）。页面勾选与选择保存在当前浏览器本地存储。`;
    }

    if (focusInputId) {
      const nextInput = document.getElementById(focusInputId);
      if (nextInput) {
        nextInput.focus();
        if (selStart != null && selEnd != null) nextInput.setSelectionRange(selStart, selEnd);
      }
    } else {
      scrollTo(0, y);
    }
  }

  function setViewFromHash() {
    const h = location.hash.slice(1);
    store.state.view = ALL_VIEWS.includes(h) ? h : "meal";
    render();
  }

  function bindEvents() {
    document.addEventListener("focusout", () => { if (pending) setTimeout(render, 0); });
    addEventListener("hashchange", () => { setViewFromHash(); scrollTo(0, 0); });

    document.getElementById("who").addEventListener("click", e => {
      const b = e.target.closest("button[data-who]");
      if (!b) return;
      store.setFocus(b.dataset.who);
      render();
    });

    const viewEl = document.getElementById("view");

    // 输入过滤（友好度培养 / 道具与材料采集 / 职业图鉴）
    viewEl.addEventListener("input", e => {
      if (e.target.matches("[data-aff-q]")) {
        store.state.affinityQuery = e.target.value;
        render();
      } else if (e.target.matches("[data-item-q]")) {
        store.state.itemsQuery = e.target.value;
        render();
      } else if (e.target.matches("[data-cls-q]")) {
        store.state.classesQuery = e.target.value;
        render();
      }
    });

    // 统一点击事件委托
    viewEl.addEventListener("click", e => {
      const affRf = e.target.closest("[data-aff-rf]");
      if (affRf) {
        store.state.affinityRosterFilter = affRf.dataset.affRf;
        render();
        return;
      }
      const itemCat = e.target.closest("[data-item-cat]");
      if (itemCat) {
        store.state.itemsCategory = itemCat.dataset.itemCat;
        render();
        return;
      }
      const itemTab = e.target.closest("[data-item-tab]");
      if (itemTab) {
        store.state.itemsTab = itemTab.dataset.itemTab;
        render();
        return;
      }
      const clsTier = e.target.closest("[data-cls-tier]");
      if (clsTier) {
        store.state.classesTier = clsTier.dataset.clsTier;
        render();
        return;
      }
      const clsMode = e.target.closest("[data-cls-mode]");
      if (clsMode) {
        store.state.classesMatchMode = clsMode.dataset.clsMode;
        render();
        return;
      }
      if (e.target.closest("[data-cls-clear]")) {
        store.state.classesTier = "全部";
        store.state.classesSkills = [];
        store.state.classesMatchMode = "all";
        store.state.classesQuery = "";
        render();
        return;
      }
      if (e.target.closest("[data-rpick-copy]")) {
        const txt = RL.formatRoutePicksExport((DATA.route && DATA.route.routeProposals) || [], store.state.routePicks);
        if (navigator.clipboard && navigator.clipboard.writeText) {
          navigator.clipboard.writeText(txt).then(() => {
            store.state.copyFeedback = "✓ 已复制到剪贴板，可以直接粘贴发给我";
            render();
          }).catch(() => {
            store.state.copyFeedback = "已生成文本（浏览器限制剪贴板权限，请手动复制下方汇总表）";
            render();
          });
        } else {
          store.state.copyFeedback = "已汇总当前选择（请直接查看下方总览表）";
          render();
        }
        return;
      }
      if (e.target.closest("[data-rpick-reset]")) {
        store.resetAllRoutePicks();
        store.state.copyFeedback = "已重置全部网页选择";
        render();
        return;
      }
      const rpickClr = e.target.closest("[data-rpick-clear]");
      if (rpickClr) {
        store.clearRoutePick(rpickClr.dataset.rpickClear);
        render();
        return;
      }
      const longRec = e.target.closest("[data-longrec]");
      if (longRec) {
        e.preventDefault();
        delete store.state.longS[longRec.dataset.longrec];
        render();
        return;
      }
      const expBtn = e.target.closest("[data-expand-all]");
      if (expBtn) {
        const w = expBtn.closest(".fullwrap");
        const open = expBtn.textContent === "展开所有等级";
        const sd = w.querySelector(".sd");
        if (sd) sd.checked = open;
        w.querySelectorAll("ol.full details").forEach(d => { d.open = open; });
        w.querySelectorAll("ol.full li.done .opts").forEach(o => { o.style.display = open ? "grid" : ""; });
        expBtn.textContent = open ? "收起所有等级" : "展开所有等级";
        return;
      }
      const g = e.target.closest("[data-go]");
      if (g) {
        store.setFocus(g.dataset.go);
        if (g.getAttribute("href") === "#" + store.state.view) {
          e.preventDefault();
          render();
        }
        return;
      }

      const chars = (DATA.route && DATA.route.chars) || [];
      const ap = e.target.closest("[data-apply]");
      if (ap) {
        const c = chars.find(x => U.slug(x) === ap.closest("[data-slug]").dataset.slug);
        const s = c.steps.find(x => x.key === ap.closest("[data-key]").dataset.key);
        const v = ap.dataset.val;
        if (v != null) store.setProg(c, s, p => { p.choice = v === RL.recOf(s) ? undefined : v; });
        render();
        return;
      }
      const decBtn = e.target.closest("[data-dec]");
      if (decBtn) {
        const c = chars.find(x => U.slug(x) === decBtn.closest("[data-slug]").dataset.slug);
        const s = c.steps.find(x => x.key === decBtn.closest("[data-key]").dataset.key);
        const v = decBtn.dataset.val;
        store.setProg(c, s, p => {
          if (decBtn.dataset.dec === "ok" && v != null) p.choice = v === RL.recOf(s) ? undefined : v;
          p.ok = decBtn.dataset.dec === "ok" ? true : undefined;
        });
        render();
        return;
      }
      const doneBtn = e.target.closest("[data-do=done]");
      if (doneBtn) {
        const card = doneBtn.closest("[data-slug]");
        const c = chars.find(x => U.slug(x) === card.dataset.slug);
        const key = doneBtn.closest("[data-key]").dataset.key;
        const w = RL.walk(c, store.state.prog, store.state.info);
        const row = w.rows.find(r => r.s.key === key);
        if (!row.r.exam) {
          const ci = RL.charInfo(c, store.state.info);
          ci.level = Math.max(ci.level || 0, row.to);
          store.setCharInfo(c, ci);
          store.setProg(c, row.s, p => { if (p.done === false) delete p.done; });
        } else {
          const n = RL.examName(row.s);
          const v = RL.examVerdict(c, row.s, store.state.prog);
          if (n && v.pass !== false) {
            const ci = RL.charInfo(c, store.state.info);
            if (!ci.owned.includes(n)) {
              ci.owned = [...ci.owned, n];
              store.setCharInfo(c, ci);
            }
          }
          store.setProg(c, row.s, p => { p.done = true; });
        }
        render();
      }
    });

    // 表单变更事件委托
    viewEl.addEventListener("change", e => {
      if (e.target.matches("[data-aff-pf]")) {
        store.state.affinityOnlyPerfect = e.target.checked;
        render();
        return;
      }
      if (e.target.matches("[data-cls-skill]")) {
        const sk = e.target.dataset.clsSkill;
        const cur = new Set(store.state.classesSkills || []);
        if (e.target.checked) cur.add(sk);
        else cur.delete(sk);
        store.state.classesSkills = [...cur];
        render();
        return;
      }
      if (e.target.matches("[data-rpick]")) {
        store.setRoutePick(e.target.dataset.rpick, e.target.value, undefined);
        store.state.copyFeedback = "";
        render();
        return;
      }
      if (e.target.matches("[data-rpick-note]")) {
        const charName = e.target.dataset.rpickNote;
        const prop = ((DATA.route && DATA.route.routeProposals) || []).find(p => p.name === charName);
        const curPick = RL.resolveRoutePick(prop, store.state.routePicks);
        store.setRoutePick(charName, curPick.optionId || (prop && prop.defaultPick) || undefined, e.target.value.trim());
        render();
        return;
      }
      const rng = e.target.closest("input[data-long]");
      if (rng) {
        store.state.longS[rng.dataset.long] = +rng.value;
        render();
        return;
      }
      const t = e.target, f = t.dataset.f;
      if (!f) return;
      if (f === "pick") {
        const box = t.closest("[data-key]");
        const btn = box.querySelector("[data-apply]") || box.querySelector('[data-dec="ok"]');
        if (!btn) return;
        const lab = t.closest("label"), need = t.dataset.need === "1";
        const what = t.value === "exam"
          ? lab.querySelector(".oc").textContent.trim()
          : `用 ${t.value} 升级${need ? `（要先考试到 ${t.value}）` : ""}`;
        btn.dataset.val = t.value;
        if (btn.dataset.apply !== undefined) {
          if (t.value === btn.dataset.cur) { btn.style.display = "none"; return; }
          btn.style.display = "";
          btn.textContent = `确认：${btn.dataset.lv} 改成${what}`;
        } else {
          btn.textContent = `确认：${what}`;
        }
        return;
      }
      const chars = (DATA.route && DATA.route.chars) || [];
      const card = t.closest("[data-slug]");
      const c = chars.find(x => U.slug(x) === card.dataset.slug);
      if (f === "done" || f === "choice" || f === "chance") {
        const s = c.steps.find(x => x.key === t.closest("[data-key]").dataset.key);
        if (f === "choice") store.setProg(c, s, p => { p.choice = t.value === RL.recOf(s) ? undefined : t.value; });
        if (f === "chance") store.setProg(c, s, p => { const v = parseFloat(t.value); p.chance = v >= 0 && v <= 100 ? v : undefined; });
        if (f === "done") store.setProg(c, s, p => { p.done = t.checked; });
      } else {
        const ci = RL.charInfo(c, store.state.info);
        if (f === "level") { const v = parseInt(t.value, 10); if (!(v > 0)) return; ci.level = v; }
        if (f === "owned") ci.owned = [...card.querySelectorAll('[data-f="owned"]:checked')].map(x => x.value);
        if (f === "skill") {
          ci.skills = { ...ci.skills };
          if (t.value) ci.skills[t.dataset.k] = t.value;
          else delete ci.skills[t.dataset.k];
        }
        store.setCharInfo(c, ci);
      }
      if (t.type === "number") t.blur();
      render();
    });

    const syncBtn = document.getElementById("syncBtn");
    if (syncBtn) {
      syncBtn.addEventListener("click", () => store.syncSheet(DATA.route, syncBtn, setSyncStatus));
    }
  }

  async function boot() {
    bindEvents();
    try {
      await loadModuleData();
      store.loadFocus((DATA.route && DATA.route.chars) || []);
      setViewFromHash();
      await store.initSync();
    } catch (err) {
      setStatus("加载失败", "warn");
      document.getElementById("view").innerHTML = `<section class="alerts"><h2>数据加载失败</h2><p class="txt">${U.esc(err && err.message ? err.message : String(err))}</p></section>`;
    }
  }

  boot();
})(window);
