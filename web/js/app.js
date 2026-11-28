/* 应用入口：动态加载独立模块数据（HTTP fetch JSON / file:// 回退）+ 路由 + 事件委托 */
(function (root) {
  const U = root.FE.utils;
  const RL = root.FE.routeLogic;
  const CL = root.FE.commentsLogic;
  const EL = root.FE.exploreLogic;
  const LL = root.FE.linksLogic;

  const ROUTE_VIEWS = ["next", "plan", "past", "l45", "long", "opts", "mine"];
  const ALL_VIEWS = [...ROUTE_VIEWS, "meal", "explore", "items", "classes", "skills", "chars"];

  let MANIFEST = null;
  let DATA = { affinity: null, items: null, explore: null, classes: null, skills: null, route: null };
  let ENTITY_REGISTRY = null;
  let pending = false;
  let pendingSelection = null; // { targetId, targetLabel, quote }

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
    if (v === "explore") return "explore";
    if (v === "classes") return "classes";
    if (v === "skills") return "skills";
    if (v === "chars") return "chars";
    return "route";
  }

  function refreshRegistry() {
    ENTITY_REGISTRY = LL.buildEntityRegistry({
      classes: (DATA.classes && DATA.classes.classes) || [],
      skills: (DATA.skills && DATA.skills.skills) || [],
      characters: (DATA.skills && DATA.skills.characters) || [],
    });
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
        const [manifest, affinity, items, explore, classes, skills, route] = await Promise.all([
          fetch("./data/manifest.json", { cache: "no-store" }).then(r => r.json()),
          fetch("./data/affinity.json", { cache: "no-store" }).then(r => r.json()),
          fetch("./data/items.json", { cache: "no-store" }).then(r => r.json()),
          fetch("./data/explore.json", { cache: "no-store" }).then(r => r.json()),
          fetch("./data/classes.json", { cache: "no-store" }).then(r => r.json()),
          fetch("./data/skills.json", { cache: "no-store" }).then(r => r.json()),
          fetch("./data/route.json", { cache: "no-store" }).then(r => r.json()),
        ]);
        MANIFEST = manifest;
        DATA = { affinity, items, explore, classes, skills, route };
        refreshRegistry();
        return;
      } catch (err) {
        const b = await loadBundleScript().catch(() => null);
        if (b) {
          MANIFEST = b.manifest;
          DATA = b;
          refreshRegistry();
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
      refreshRegistry();
      return;
    }
    throw new Error("未找到模块数据（请通过本地 HTTP 服务打开，或先运行 build_site.py 生成 out/data/）");
  }

  const store = root.FE.createStore(() => render(), setStatus);

  function clearEntityFocusFor(viewName) {
    if (store.state.entityFocus && (!viewName || store.state.entityFocus.view === viewName)) {
      store.state.entityFocus = null;
      const targetHash = "#" + store.state.view;
      if (location.hash !== targetHash) {
        history.replaceState(null, "", targetHash);
      }
    }
  }

  function hideSelPop() {
    const pop = document.getElementById("selCommentBtn");
    if (pop) pop.hidden = true;
    pendingSelection = null;
  }

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
    hideSelPop();
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
      const lord = (DATA.route && DATA.route.rulesMeta && DATA.route.rulesMeta.currentLord) || "";
      const groups = RL.groupCharsByTier(chars, lord);
      const allBtn = `<button type="button" data-who="" aria-pressed="${store.state.focus === ""}">全部</button>`;
      const grpHtml = groups.map(g => {
        const cls = g.tier === "P0" ? "r1" : g.tier === "P1" ? "r2" : "r3";
        const btns = g.chars.map(c => {
          const slug = U.slug(c);
          const crown = c.isLord || (lord && c.name === lord) ? "★" : "";
          const st = c.strengthTier ? ` <small class="who-st">${U.esc(c.strengthTier)}</small>` : "";
          return `<button type="button" data-who="${slug}" aria-pressed="${store.state.focus === slug}">${crown}${U.esc(U.shortName(c.name))}${st}</button>`;
        }).join("");
        return `<span class="who-grp" data-who-tier="${U.esc(g.tier)}"><span class="rec ${cls}">${U.esc(g.tier)}</span>${btns}</span>`;
      }).join("");
      whoEl.innerHTML = allBtn + grpHtml;
    }

    const syncBtn = document.getElementById("syncBtn");
    if (syncBtn) syncBtn.style.display = dom === "route" ? "" : "none";

    const opened = [...document.querySelectorAll("#view details[open][data-keep]")].map(d => d.dataset.keep);
    const V = root.FE.views;
    const ef = store.state.entityFocus;
    const focusTarget = ef && ef.view === view ? ef.target : "";
    const ctx = {
      registry: ENTITY_REGISTRY,
      focusTarget,
      routeData: DATA.route,
      affinityData: DATA.affinity,
    };
    let html = "";
    if (view === "meal") html = V.renderAffinityView(DATA.affinity, store.state, ctx);
    else if (view === "items") html = V.renderItemsView(DATA.items, store.state, ctx);
    else if (view === "explore") html = V.renderExploreView(DATA.explore, store.state, ctx);
    else if (view === "classes") html = V.renderClassesView(DATA.classes, store.state, ctx);
    else if (view === "skills") html = V.renderSkillsView(DATA.skills, store.state, ctx);
    else if (view === "chars") html = V.renderCharsView(DATA.skills, store.state, ctx);
    else html = V.renderRouteView(view, DATA.route, store.state, ctx);

    const viewEl = document.getElementById("view");
    viewEl.innerHTML = html;

    document.querySelectorAll("#view details.more").forEach((d, i) => {
      d.dataset.keep = (d.closest("[data-key]")?.dataset.key || "") + (d.closest("[data-slug]")?.dataset.slug || "") + i;
      if (opened.includes(d.dataset.keep)) d.open = true;
    });

    const foot = document.getElementById("foot");
    if (foot && DATA.route) {
      const rm = DATA.route.rulesMeta || {};
      const ver = MANIFEST && MANIFEST.version ? ` · 版本 v${MANIFEST.version}` : "";
      const built = MANIFEST && MANIFEST.builtAt ? ` · 数据构建于 ${MANIFEST.builtAt}` : "";
      foot.textContent = `架构：七大模块（路线规划 / 友好度培养 / 探索规划 / 道具与材料采集 / 职业图鉴 / 技能图鉴 / 角色图鉴）前后端数据与逻辑解耦加载，全站职业·技能·角色稳定深链互通（当前快照 ${rm.shotKey || "latest"}，名声 Lv${rm.renown ?? "?"}${ver}${built}）。页面勾选、采集进度、选择与 Plan Mode 批注均保存在当前浏览器本地存储。`;
    }

    if (focusInputId) {
      const nextInput = document.getElementById(focusInputId);
      if (nextInput) {
        nextInput.focus();
        if (selStart != null && selEnd != null) nextInput.setSelectionRange(selStart, selEnd);
      }
    } else if (store.state.commentDraft) {
      const box = document.getElementById("cmtDraftInput");
      if (box) {
        box.focus();
        box.scrollIntoView({ behavior: "smooth", block: "center" });
      }
    } else if (store.state.editingCommentId) {
      const box = document.getElementById("cmtEditInput");
      if (box) box.focus();
    } else {
      scrollTo(0, y);
    }
  }

  function setViewFromHash() {
    const parsed = LL.parseRouteHash(location.hash, ALL_VIEWS, "next");
    store.state.view = parsed.view;
    store.state.entityFocus = parsed.target ? { view: parsed.view, target: parsed.target } : null;
    render();
    if (parsed.target) {
      const hit = document.querySelector('[data-ent-focused="true"]');
      if (hit) hit.scrollIntoView({ behavior: "smooth", block: "center" });
      else scrollTo(0, 0);
    }
  }

  function bindEvents() {
    document.addEventListener("focusout", () => { if (pending) setTimeout(render, 0); });
    addEventListener("hashchange", () => { setViewFromHash(); if (!store.state.entityFocus) scrollTo(0, 0); });

    document.getElementById("who").addEventListener("click", e => {
      const b = e.target.closest("button[data-who]");
      if (!b) return;
      store.setFocus(b.dataset.who);
      render();
    });

    const viewEl = document.getElementById("view");

    // 输入过滤（友好度培养 / 道具与材料采集 / 探索规划 / 职业图鉴 / 技能图鉴 / 角色图鉴 / Plan Mode 草稿同步）
    viewEl.addEventListener("input", e => {
      if (e.target.matches("[data-aff-q]")) {
        store.state.affinityQuery = e.target.value;
        render();
      } else if (e.target.matches("[data-item-q]")) {
        store.state.itemsQuery = e.target.value;
        render();
      } else if (e.target.matches("[data-exp-q]")) {
        store.state.exploreQuery = e.target.value;
        render();
      } else if (e.target.matches("[data-cls-q]")) {
        clearEntityFocusFor("classes");
        store.state.classesQuery = e.target.value;
        render();
      } else if (e.target.matches("[data-sk-q]")) {
        clearEntityFocusFor("skills");
        store.state.skillsQuery = e.target.value;
        store.state.skillsShowAll = false;
        render();
      } else if (e.target.matches("[data-ch-q]")) {
        clearEntityFocusFor("chars");
        store.state.charsQuery = e.target.value;
        render();
      } else if (e.target.matches("[data-cmt-draft-text]") && store.state.commentDraft) {
        store.state.commentDraft.text = e.target.value;
      }
    });

    function getNearestAnchorId(el) {
      let cur = el && el.nodeType === 1 ? el : (el && el.parentElement);
      while (cur && cur !== document.body) {
        if (cur.id) return cur.id;
        cur = cur.parentElement;
      }
      return "view";
    }

    function getElementXPath(el) {
      let cur = el && el.nodeType === 1 ? el : (el && el.parentElement);
      if (!cur) return "";
      const segs = [];
      while (cur && cur.nodeType === 1 && cur !== document.documentElement) {
        if (cur.id) {
          segs.unshift(`//*[@id="${cur.id}"]`);
          return segs.join("/");
        }
        const tag = cur.tagName.toLowerCase();
        let idx = 1;
        let sib = cur.previousElementSibling;
        while (sib) {
          if (sib.tagName === cur.tagName) idx += 1;
          sib = sib.previousElementSibling;
        }
        segs.unshift(`${tag}[${idx}]`);
        cur = cur.parentElement;
      }
      return "/" + segs.join("/");
    }

    function getVersionMeta() {
      const rm = (DATA.route && DATA.route.rulesMeta) || {};
      return {
        version: (MANIFEST && MANIFEST.version) || "local",
        builtAt: (MANIFEST && MANIFEST.builtAt) || "",
        shotKey: (MANIFEST && MANIFEST.shotKey) || rm.shotKey || "",
        viewHash: "#" + store.state.view,
      };
    }

    // Plan Mode 快捷键：Ctrl/Cmd + Enter 直接保存批注，Esc 取消
    viewEl.addEventListener("keydown", e => {
      if (e.target.matches("[data-cmt-draft-text]")) {
        if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
          e.preventDefault();
          const d = store.state.commentDraft;
          if (d && (e.target.value || "").trim()) {
            const vm = getVersionMeta();
            store.addPlanComment({
              targetId: d.targetId,
              targetLabel: d.targetLabel,
              section: store.state.view,
              viewHash: d.viewHash || vm.viewHash,
              anchorId: d.anchorId || "",
              xpath: d.xpath || "",
              version: d.version || vm.version,
              quote: d.quote || "",
              text: e.target.value,
            });
            store.state.commentDraft = null;
            render();
          }
        } else if (e.key === "Escape") {
          store.state.commentDraft = null;
          render();
        }
      } else if (e.target.matches("[data-cmt-edit-text]")) {
        if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
          e.preventDefault();
          const cid = store.state.editingCommentId;
          if (cid && (e.target.value || "").trim()) {
            store.updatePlanComment(cid, e.target.value);
            store.state.editingCommentId = null;
            render();
          }
        } else if (e.key === "Escape") {
          store.state.editingCommentId = null;
          render();
        }
      }
    });

    // 统一点击事件委托
    viewEl.addEventListener("click", e => {
      // --- Plan Mode 批注工具栏与卡片内联批注 ---
      if (e.target.closest("[data-pm-toggle]")) {
        store.state.commentMode = !store.state.commentMode;
        if (!store.state.commentMode) {
          store.state.commentDraft = null;
          hideSelPop();
        }
        render();
        return;
      }
      if (e.target.closest("[data-pm-drawer]")) {
        store.state.commentDrawerOpen = !store.state.commentDrawerOpen;
        render();
        return;
      }
      if (e.target.closest("[data-pm-export]")) {
        const txt = CL.formatPlanReviewExport({
          comments: store.state.planComments,
          proposals: (DATA.route && DATA.route.routeProposals) || [],
          routePicks: store.state.routePicks,
          formatRoutePicksExport: RL.formatRoutePicksExport,
          includeResolved: false,
          meta: getVersionMeta(),
        });
        if (navigator.clipboard && navigator.clipboard.writeText) {
          navigator.clipboard.writeText(txt).then(() => {
            store.state.copyFeedback = "✓ 已复制全部 Plan Mode 批注（含 div id / XPath / 版本号）与路线选择，可直接粘贴发给我";
            render();
          }).catch(() => {
            store.state.copyFeedback = "已生成批注与选择文本（浏览器限制剪贴板权限，请展开批注清单查看）";
            store.state.commentDrawerOpen = true;
            render();
          });
        } else {
          store.state.copyFeedback = "已生成批注与选择汇总（已展开批注清单）";
          store.state.commentDrawerOpen = true;
          render();
        }
        return;
      }
      if (e.target.closest("[data-pm-clear]")) {
        store.clearAllPlanComments();
        store.state.commentDraft = null;
        store.state.editingCommentId = null;
        store.state.copyFeedback = "已清空全部本地批注";
        render();
        return;
      }
      const cmtOpen = e.target.closest("[data-cmt-open]");
      if (cmtOpen) {
        e.preventDefault();
        e.stopPropagation();
        const host = cmtOpen.closest("[data-cmt-target]") || cmtOpen;
        const vm = getVersionMeta();
        store.state.editingCommentId = null;
        store.state.commentDraft = {
          targetId: cmtOpen.dataset.cmtOpen,
          targetLabel: cmtOpen.dataset.cmtLabel || cmtOpen.dataset.cmtOpen,
          section: store.state.view,
          viewHash: vm.viewHash,
          anchorId: getNearestAnchorId(host),
          xpath: getElementXPath(host),
          version: vm.version,
          quote: "",
          text: "",
        };
        render();
        return;
      }
      if (e.target.closest("[data-cmt-save]")) {
        e.preventDefault();
        const box = e.target.closest("[data-cmt-box]");
        const ta = box && box.querySelector("[data-cmt-draft-text]");
        const txt = ta ? ta.value.trim() : (store.state.commentDraft && store.state.commentDraft.text || "").trim();
        if (store.state.commentDraft && txt) {
          const vm = getVersionMeta();
          store.addPlanComment({
            targetId: store.state.commentDraft.targetId,
            targetLabel: store.state.commentDraft.targetLabel,
            section: store.state.view,
            viewHash: store.state.commentDraft.viewHash || vm.viewHash,
            anchorId: store.state.commentDraft.anchorId || "",
            xpath: store.state.commentDraft.xpath || "",
            version: store.state.commentDraft.version || vm.version,
            quote: store.state.commentDraft.quote || "",
            text: txt,
          });
          store.state.commentDraft = null;
          store.state.copyFeedback = "";
          render();
        }
        return;
      }
      if (e.target.closest("[data-cmt-cancel]")) {
        e.preventDefault();
        store.state.commentDraft = null;
        render();
        return;
      }
      const cmtRes = e.target.closest("[data-cmt-resolve]");
      if (cmtRes) {
        e.preventDefault();
        store.toggleResolvePlanComment(cmtRes.dataset.cmtResolve);
        render();
        return;
      }
      const cmtEdit = e.target.closest("[data-cmt-edit]");
      if (cmtEdit) {
        e.preventDefault();
        store.state.commentDraft = null;
        store.state.editingCommentId = cmtEdit.dataset.cmtEdit;
        render();
        return;
      }
      const cmtEditSave = e.target.closest("[data-cmt-edit-save]");
      if (cmtEditSave) {
        e.preventDefault();
        const item = cmtEditSave.closest("[data-cmt-id]");
        const ta = item && item.querySelector("[data-cmt-edit-text]");
        if (ta && ta.value.trim()) {
          store.updatePlanComment(cmtEditSave.dataset.cmtEditSave, ta.value);
          store.state.editingCommentId = null;
          render();
        }
        return;
      }
      if (e.target.closest("[data-cmt-edit-cancel]")) {
        e.preventDefault();
        store.state.editingCommentId = null;
        render();
        return;
      }
      const cmtDel = e.target.closest("[data-cmt-del]");
      if (cmtDel) {
        e.preventDefault();
        store.deletePlanComment(cmtDel.dataset.cmtDel);
        if (store.state.editingCommentId === cmtDel.dataset.cmtDel) store.state.editingCommentId = null;
        render();
        return;
      }

      // --- 通用实体深链返回上一页 ---
      if (e.target.closest("[data-ent-back]")) {
        e.preventDefault();
        history.back();
        return;
      }

      // --- 角色图鉴筛选交互 ---
      const chGrp = e.target.closest("[data-ch-grp]");
      if (chGrp) {
        clearEntityFocusFor("chars");
        store.state.charsGroup = chGrp.dataset.chGrp;
        render();
        return;
      }
      const chTier = e.target.closest("[data-ch-tier]");
      if (chTier) {
        clearEntityFocusFor("chars");
        store.state.charsTier = chTier.dataset.chTier;
        render();
        return;
      }
      if (e.target.closest("[data-ch-showall]")) {
        clearEntityFocusFor("chars");
        store.state.charsGroup = "all";
        store.state.charsTier = "全部";
        store.state.charsQuery = "";
        render();
        return;
      }
      if (e.target.closest("[data-ch-clear]")) {
        clearEntityFocusFor("chars");
        store.state.charsTier = "全部";
        store.state.charsQuery = "";
        render();
        return;
      }

      // --- 技能图鉴筛选交互 ---
      const skRating = e.target.closest("[data-sk-rating]");
      if (skRating) {
        clearEntityFocusFor("skills");
        store.state.skillsRating = skRating.dataset.skRating;
        store.state.skillsShowAll = false;
        render();
        return;
      }
      const skScope = e.target.closest("[data-sk-scope]");
      if (skScope) {
        clearEntityFocusFor("skills");
        store.state.skillsScope = skScope.dataset.skScope;
        store.state.skillsShowAll = false;
        render();
        return;
      }
      const skCat = e.target.closest("[data-sk-cat]");
      if (skCat) {
        clearEntityFocusFor("skills");
        store.state.skillsCategory = skCat.dataset.skCat;
        store.state.skillsShowAll = false;
        render();
        return;
      }
      if (e.target.closest("[data-sk-all]")) {
        store.state.skillsShowAll = true;
        render();
        return;
      }
      if (e.target.closest("[data-sk-clear]")) {
        clearEntityFocusFor("skills");
        store.state.skillsRating = "全部";
        store.state.skillsScope = "全部";
        store.state.skillsCategory = "全部";
        store.state.skillsDiscipline = "全部";
        store.state.skillsUnitTypes = [];
        store.state.skillsOnlyRecruited = false;
        store.state.skillsQuery = "";
        store.state.skillsShowAll = false;
        render();
        return;
      }

      // --- 探索规划：路线/预设/缩放定位/PNG 与 HTML 导出/外部地图同步 ---
      const expRouteBtn = e.target.closest("[data-exp-route]");
      if (expRouteBtn) {
        store.state.exploreRoute = expRouteBtn.dataset.expRoute;
        store.state.exploreSelectedId = "";
        store.state.exploreViewBox = null;
        store.state.exploreFeedback = "";
        render();
        return;
      }
      const expPresetBtn = e.target.closest("[data-exp-preset]");
      if (expPresetBtn) {
        const pr = (root.FE.views.EXPLORE_PRESETS || []).find(x => x.id === expPresetBtn.dataset.expPreset);
        if (pr) {
          store.state.explorePriorities = [...pr.priorities];
          store.state.exploreTypes = [...pr.types];
          store.state.exploreOnlyBarterLack = !!pr.onlyBarterLack;
          store.state.exploreQuery = "";
          store.state.exploreViewBox = null;
          store.state.exploreFeedback = "";
          render();
        }
        return;
      }
      const expMatBtn = e.target.closest("[data-exp-mat]");
      if (expMatBtn && DATA.explore) {
        const mat = expMatBtn.dataset.expMat || "";
        store.state.exploreQuery = mat;
        store.state.exploreFeedback = "";
        if (mat) {
          store.state.explorePriorities = ["P0", "P1", "P2"];
          store.state.exploreTypes = ["矿石", "道具", "鱼", "蔬菜"];
          store.state.exploreOnlyBarterLack = false;
          const rObj = DATA.explore.routes[store.state.exploreRoute || DATA.explore.defaultRoute];
          const hits = EL.filterExploreSpots((rObj && rObj.spots) || [], {
            priorities: store.state.explorePriorities,
            types: store.state.exploreTypes,
            query: mat,
            hideVisited: store.state.exploreHideVisited,
            visitedMap: store.state.exploreVisited,
          });
          store.state.exploreSelectedId = hits[0] ? hits[0].id : "";
          store.state.exploreViewBox = EL.computeFitViewBox(
            hits,
            DATA.explore.defaultViewBox,
            DATA.explore.mapWidth || 3328,
            DATA.explore.mapHeight || 2560
          );
        } else {
          store.state.explorePriorities = ["P0"];
          store.state.exploreViewBox = null;
        }
        render();
        const stg = document.getElementById("expCanvasWrap");
        if (mat && stg) stg.scrollIntoView({ behavior: "smooth", block: "center" });
        return;
      }
      const expPin = e.target.closest("[data-exp-pin]");
      if (expPin) {
        store.state.exploreSelectedId = expPin.dataset.expPin;
        render();
        return;
      }
      const expFocusBtn = e.target.closest("[data-exp-focus]");
      if (expFocusBtn) {
        const sid = expFocusBtn.dataset.expFocus;
        const rObj = DATA.explore && DATA.explore.routes && DATA.explore.routes[store.state.exploreRoute || DATA.explore.defaultRoute];
        const sp = rObj && (rObj.spots || []).find(x => x.id === sid);
        if (sp) {
          // 确保目标点位的优先级与类型均处于开启状态，防止点击后因过滤隐藏
          const prSet = new Set(store.state.explorePriorities || ["P0"]);
          if (sp.priority) prSet.add(sp.priority);
          store.state.explorePriorities = [...prSet];
          const tpSet = new Set(store.state.exploreTypes || []);
          if (sp.type) tpSet.add(sp.type);
          store.state.exploreTypes = [...tpSet];
          if (store.state.exploreOnlyBarterLack && !sp.hasBarterShortage) {
            store.state.exploreOnlyBarterLack = false;
          }
          store.state.exploreSelectedId = sid;
          const mw = DATA.explore.mapWidth || 3328;
          const mh = DATA.explore.mapHeight || 2560;
          const w = 1150, h = 860;
          store.state.exploreViewBox = [
            Math.max(0, Math.min(mw - w, Math.round(sp.x - w / 2))),
            Math.max(0, Math.min(mh - h, Math.round(sp.y - h / 2))),
            w,
            h,
          ];
          render();
          const stg = document.getElementById("expCanvasWrap");
          if (stg) stg.scrollIntoView({ behavior: "smooth", block: "center" });
        }
        return;
      }
      const expRow = e.target.closest("tr[data-exp-row]");
      if (expRow && !e.target.closest("a,button,input,label")) {
        store.state.exploreSelectedId = expRow.dataset.expRow;
        render();
        return;
      }
      const expZoom = e.target.closest("[data-exp-zoom]");
      if (expZoom && DATA.explore) {
        const act = expZoom.dataset.expZoom;
        const mw = DATA.explore.mapWidth || 3328;
        const mh = DATA.explore.mapHeight || 2560;
        const defVb = DATA.explore.defaultViewBox || [210, 230, 2900, 2100];
        const cur = Array.isArray(store.state.exploreViewBox) ? store.state.exploreViewBox : defVb;
        if (act === "reset") {
          store.state.exploreViewBox = defVb.slice();
        } else if (act === "fit") {
          const rObj = DATA.explore.routes[store.state.exploreRoute || DATA.explore.defaultRoute];
          const fSpots = EL.filterExploreSpots((rObj && rObj.spots) || [], {
            priorities: store.state.explorePriorities,
            types: store.state.exploreTypes,
            query: store.state.exploreQuery,
            hideVisited: store.state.exploreHideVisited,
            onlyBarterLack: store.state.exploreOnlyBarterLack,
            visitedMap: store.state.exploreVisited,
          });
          store.state.exploreViewBox = EL.computeFitViewBox(fSpots, defVb, mw, mh);
        } else {
          const factor = act === "in" ? 0.72 : 1.38;
          const nw = Math.max(520, Math.min(mw, Math.round(cur[2] * factor)));
          const nh = Math.max(400, Math.min(mh, Math.round(cur[3] * factor)));
          const cx = cur[0] + cur[2] / 2;
          const cy = cur[1] + cur[3] / 2;
          store.state.exploreViewBox = [
            Math.max(0, Math.min(mw - nw, Math.round(cx - nw / 2))),
            Math.max(0, Math.min(mh - nh, Math.round(cy - nh / 2))),
            nw,
            nh,
          ];
        }
        render();
        return;
      }
      if (e.target.closest("[data-exp-fwcopy]") && DATA.explore) {
        const rk = store.state.exploreRoute || DATA.explore.defaultRoute;
        const rObj = DATA.explore.routes[rk];
        const fSpots = EL.filterExploreSpots((rObj && rObj.spots) || [], {
          priorities: store.state.explorePriorities,
          types: store.state.exploreTypes,
          query: store.state.exploreQuery,
          hideVisited: store.state.exploreHideVisited,
          onlyBarterLack: store.state.exploreOnlyBarterLack,
          visitedMap: store.state.exploreVisited,
        });
        const info = EL.extractFwCollectItems(fSpots, rk);
        const script =
          `localStorage.setItem("route",${JSON.stringify(info.routeKey)});` +
          `localStorage.setItem("collect",JSON.stringify(${JSON.stringify(info.items)}));` +
          `location.hash="#c";location.reload();`;
        if (navigator.clipboard && navigator.clipboard.writeText) {
          navigator.clipboard.writeText(script).then(() => {
            store.state.exploreFeedback = `✓ 已复制同步脚本（含 ${info.items.length} 种高优先素材）：打开 fire-emblem-fw.site/map.html 按 F12 在 Console 粘贴回车即可批量写入原站「收集清单」`;
            render();
          }).catch(() => {
            store.state.exploreFeedback = `同步脚本（${info.items.length} 种素材）：${script}`;
            render();
          });
        } else {
          store.state.exploreFeedback = `同步脚本（${info.items.length} 种素材）：${script}`;
          render();
        }
        return;
      }
      if (e.target.closest("[data-exp-png]") && DATA.explore) {
        exportExplorePng();
        return;
      }
      if (e.target.closest("[data-exp-html]") && DATA.explore) {
        exportExploreHtml();
        return;
      }

      // --- 友好度 / 道具 / 职业图鉴筛选交互 ---
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
      const itemWt = e.target.closest("[data-item-wt]");
      if (itemWt) {
        store.state.itemsWeaponTier = itemWt.dataset.itemWt;
        render();
        return;
      }
      const clsTier = e.target.closest("[data-cls-tier]");
      if (clsTier) {
        clearEntityFocusFor("classes");
        store.state.classesTier = clsTier.dataset.clsTier;
        render();
        return;
      }
      const clsMode = e.target.closest("[data-cls-mode]");
      if (clsMode) {
        clearEntityFocusFor("classes");
        store.state.classesMatchMode = clsMode.dataset.clsMode;
        render();
        return;
      }
      if (e.target.closest("[data-cls-clear]")) {
        clearEntityFocusFor("classes");
        store.state.classesTier = "全部";
        store.state.classesSkills = [];
        store.state.classesStats = [];
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
        w.querySelectorAll("ol.full li:not(.done) details").forEach(d => { d.open = open; });
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
      const ee = e.target.closest("[data-early-exam-cls]");
      if (ee) {
        const c = chars.find(x => U.slug(x) === ee.closest("[data-slug]").dataset.slug);
        const sEarly = c && c.steps.find(x => x.key === ee.dataset.earlyExamKey);
        const sUse = c && c.steps.find(x => x.key === ee.dataset.useKey);
        const cls = ee.dataset.earlyExamCls;
        if (c && sEarly && sUse && cls) {
          store.setProg(c, sEarly, p => { p.choice = (sEarly.exam && sEarly.cls === cls) ? undefined : ("exam:" + cls); });
          store.setProg(c, sUse, p => { p.choice = cls === RL.recOf(sUse) ? undefined : cls; });
          render();
        }
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
      if (e.target.matches("[data-sk-disc]")) {
        clearEntityFocusFor("skills");
        store.state.skillsDiscipline = e.target.value;
        store.state.skillsShowAll = false;
        render();
        return;
      }
      if (e.target.matches("[data-sk-rec]")) {
        clearEntityFocusFor("skills");
        store.state.skillsOnlyRecruited = e.target.checked;
        store.state.skillsShowAll = false;
        render();
        return;
      }
      if (e.target.matches("[data-sk-ut]")) {
        clearEntityFocusFor("skills");
        const ut = e.target.dataset.skUt;
        const cur = new Set(store.state.skillsUnitTypes || []);
        if (e.target.checked) cur.add(ut);
        else cur.delete(ut);
        store.state.skillsUnitTypes = [...cur];
        store.state.skillsShowAll = false;
        render();
        return;
      }
      if (e.target.matches("[data-exp-prio]")) {
        const pr = e.target.dataset.expPrio;
        const cur = new Set(store.state.explorePriorities || []);
        if (e.target.checked) cur.add(pr);
        else cur.delete(pr);
        store.state.explorePriorities = [...cur];
        store.state.exploreFeedback = "";
        render();
        return;
      }
      if (e.target.matches("[data-exp-type]")) {
        const tp = e.target.dataset.expType;
        const cur = new Set(store.state.exploreTypes || []);
        if (e.target.checked) cur.add(tp);
        else cur.delete(tp);
        store.state.exploreTypes = [...cur];
        store.state.exploreFeedback = "";
        render();
        return;
      }
      if (e.target.matches("[data-exp-opt]")) {
        const opt = e.target.dataset.expOpt;
        if (opt === "labels") store.state.exploreShowLabels = e.target.checked;
        else if (opt === "stations") store.state.exploreShowStations = e.target.checked;
        else if (opt === "arrows") store.state.exploreShowArrows = e.target.checked;
        else if (opt === "hideVisited") store.state.exploreHideVisited = e.target.checked;
        else if (opt === "onlyBarterLack") store.state.exploreOnlyBarterLack = e.target.checked;
        render();
        return;
      }
      if (e.target.matches("[data-exp-visit]")) {
        store.setExploreVisited(e.target.dataset.expVisit, e.target.checked);
        render();
        return;
      }
      if (e.target.matches("[data-aff-pf]")) {
        store.state.affinityOnlyPerfect = e.target.checked;
        render();
        return;
      }
      if (e.target.matches("[data-cls-skill]")) {
        clearEntityFocusFor("classes");
        const sk = e.target.dataset.clsSkill;
        const cur = new Set(store.state.classesSkills || []);
        if (e.target.checked) cur.add(sk);
        else cur.delete(sk);
        store.state.classesSkills = [...cur];
        render();
        return;
      }
      if (e.target.matches("[data-cls-stat]")) {
        clearEntityFocusFor("classes");
        const st = e.target.dataset.clsStat;
        const cur = new Set(store.state.classesStats || []);
        if (e.target.checked) cur.add(st);
        else cur.delete(st);
        store.state.classesStats = [...cur];
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
        const what = RL.isExamChoice(t.value)
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

    // Plan Mode 划词批注：在路线规划域选中任意文本后弹出浮动「💬 对选中内容添加批注」按钮
    const selPop = document.getElementById("selCommentBtn");
    document.addEventListener("mouseup", e => {
      if (e.target === selPop || (selPop && selPop.contains(e.target))) return;
      if (domainOf(store.state.view) !== "route" || !store.state.commentMode) {
        hideSelPop();
        return;
      }
      const sel = window.getSelection();
      const txt = sel ? sel.toString().trim() : "";
      if (!txt || txt.length < 2 || !sel.rangeCount) {
        hideSelPop();
        return;
      }
      const range = sel.getRangeAt(0);
      const anchor = range.commonAncestorContainer.nodeType === 1
        ? range.commonAncestorContainer
        : range.commonAncestorContainer.parentElement;
      if (!anchor || !viewEl.contains(anchor) || anchor.closest("textarea,input,.cmt-composer")) {
        hideSelPop();
        return;
      }
      const targetEl = anchor.closest("[data-cmt-target]");
      const targetId = targetEl ? targetEl.dataset.cmtTarget : "rules:global";
      const targetLabel = targetEl ? targetEl.dataset.cmtLabel : "全局路线规划规则";
      const rect = range.getBoundingClientRect();
      if (!rect || (!rect.width && !rect.height)) {
        hideSelPop();
        return;
      }
      const vm = getVersionMeta();
      pendingSelection = {
        targetId,
        targetLabel,
        viewHash: vm.viewHash,
        anchorId: getNearestAnchorId(anchor),
        xpath: getElementXPath(anchor),
        version: vm.version,
        quote: txt.slice(0, 180),
      };
      if (selPop) {
        const left = Math.max(12, Math.min(window.innerWidth - 200, rect.left + rect.width / 2 - 90));
        const top = Math.max(12, rect.top - 40);
        selPop.style.left = left + "px";
        selPop.style.top = top + "px";
        selPop.hidden = false;
      }
    });

    if (selPop) {
      selPop.addEventListener("click", () => {
        if (!pendingSelection) return;
        const ps = pendingSelection;
        hideSelPop();
        const sel = window.getSelection();
        if (sel) sel.removeAllRanges();
        store.state.editingCommentId = null;
        store.state.commentDraft = {
          targetId: ps.targetId,
          targetLabel: ps.targetLabel,
          section: store.state.view,
          viewHash: ps.viewHash,
          anchorId: ps.anchorId,
          xpath: ps.xpath,
          version: ps.version,
          quote: ps.quote,
          text: "",
        };
        render();
      });
    }

    const syncBtn = document.getElementById("syncBtn");
    if (syncBtn) {
      syncBtn.addEventListener("click", () => store.syncSheet(DATA.route, syncBtn, setSyncStatus));
    }

    // --- 探索规划 SVG 地图滚轮缩放与鼠标拖拽平移（直接改 viewBox 保持 60fps 流畅） ---
    let dragState = null;
    viewEl.addEventListener("mousedown", e => {
      const wrap = e.target.closest("#expCanvasWrap");
      if (!wrap || e.button !== 0 || e.target.closest("[data-exp-pin]")) return;
      const svg = wrap.querySelector("#expMapSvg");
      if (!svg) return;
      const vb = (svg.getAttribute("viewBox") || "210 230 2900 2100").split(/\s+/).map(Number);
      const rect = svg.getBoundingClientRect();
      if (!rect.width || !rect.height) return;
      dragState = { wrap, svg, startX: e.clientX, startY: e.clientY, vb, rect, moved: false };
      wrap.classList.add("dragging");
    });
    document.addEventListener("mousemove", e => {
      if (!dragState) return;
      const dxPx = e.clientX - dragState.startX;
      const dyPx = e.clientY - dragState.startY;
      if (Math.abs(dxPx) > 3 || Math.abs(dyPx) > 3) dragState.moved = true;
      const mw = Number(dragState.svg.dataset.mapW) || 3328;
      const mh = Number(dragState.svg.dataset.mapH) || 2560;
      const [vx, vy, vw, vh] = dragState.vb;
      const nx = Math.max(0, Math.min(mw - vw, vx - (dxPx / dragState.rect.width) * vw));
      const ny = Math.max(0, Math.min(mh - vh, vy - (dyPx / dragState.rect.height) * vh));
      const nextVb = [Math.round(nx), Math.round(ny), Math.round(vw), Math.round(vh)];
      dragState.svg.setAttribute("viewBox", nextVb.join(" "));
      store.state.exploreViewBox = nextVb;
    });
    document.addEventListener("mouseup", () => {
      if (!dragState) return;
      dragState.wrap.classList.remove("dragging");
      dragState = null;
    });
    viewEl.addEventListener("wheel", e => {
      const wrap = e.target.closest("#expCanvasWrap");
      if (!wrap) return;
      const svg = wrap.querySelector("#expMapSvg");
      if (!svg) return;
      e.preventDefault();
      const mw = Number(svg.dataset.mapW) || 3328;
      const mh = Number(svg.dataset.mapH) || 2560;
      const [vx, vy, vw, vh] = (svg.getAttribute("viewBox") || "210 230 2900 2100").split(/\s+/).map(Number);
      const rect = svg.getBoundingClientRect();
      if (!rect.width || !rect.height) return;
      const rx = (e.clientX - rect.left) / rect.width;
      const ry = (e.clientY - rect.top) / rect.height;
      const factor = e.deltaY > 0 ? 1.18 : 0.84;
      const nw = Math.max(520, Math.min(mw, vw * factor));
      const nh = Math.max(400, Math.min(mh, vh * factor));
      const nx = Math.max(0, Math.min(mw - nw, vx + rx * (vw - nw)));
      const ny = Math.max(0, Math.min(mh - nh, vy + ry * (vh - nh)));
      const nextVb = [Math.round(nx), Math.round(ny), Math.round(nw), Math.round(nh)];
      svg.setAttribute("viewBox", nextVb.join(" "));
      store.state.exploreViewBox = nextVb;
    }, { passive: false });
  }

  function getExploreExportContext() {
    if (!DATA.explore) return null;
    const rk = store.state.exploreRoute || DATA.explore.defaultRoute || "dietrich";
    const rObj = DATA.explore.routes && DATA.explore.routes[rk];
    if (!rObj) return null;
    const spots = EL.filterExploreSpots(rObj.spots || [], {
      priorities: store.state.explorePriorities,
      types: store.state.exploreTypes,
      query: store.state.exploreQuery,
      hideVisited: store.state.exploreHideVisited,
      onlyBarterLack: store.state.exploreOnlyBarterLack,
      visitedMap: store.state.exploreVisited,
    });
    return { rk, rObj, spots };
  }

  function loadImageEl(src) {
    return new Promise((resolve, reject) => {
      const img = new Image();
      img.crossOrigin = "anonymous";
      img.onload = () => resolve(img);
      img.onerror = () => reject(new Error("地图底图加载失败"));
      img.src = src;
    });
  }

  function triggerDownload(url, filename) {
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
  }

  async function exportExplorePng() {
    const ctxInfo = getExploreExportContext();
    if (!ctxInfo) return;
    try {
      const img = await loadImageEl(DATA.explore.mapImage || "./assets/world_map.jpg");
      const W = 1664, H = 1280;
      const sx = W / (DATA.explore.mapWidth || 3328);
      const sy = H / (DATA.explore.mapHeight || 2560);
      const cv = document.createElement("canvas");
      cv.width = W;
      cv.height = H;
      const g = cv.getContext("2d");
      g.drawImage(img, 0, 0, W, H);

      // 1) 驿站路标
      if (store.state.exploreShowStations !== false) {
        for (const st of ctxInfo.rObj.stations || []) {
          const x = st.x * sx, y = st.y * sy;
          g.fillStyle = "#0f766e";
          g.strokeStyle = "#ffffff";
          g.lineWidth = 2;
          g.fillRect(x - 8, y - 8, 16, 16);
          g.strokeRect(x - 8, y - 8, 16, 16);
          g.fillStyle = "#ffffff";
          g.font = "bold 10px sans-serif";
          g.textAlign = "center";
          g.textBaseline = "middle";
          g.fillText("站", x, y + 0.5);
        }
      }

      // 2) 高显眼优先级标记（P2 -> P1 -> P0）
      const ordered = [...ctxInfo.spots].sort((a, b) => {
        const tr = { P2: 0, P1: 1, P0: 2 };
        return (tr[a.priority] || 0) - (tr[b.priority] || 0) || (b.rank - a.rank);
      });
      for (const sp of ordered) {
        const tm = EL.TIER_META[sp.priority] || EL.TIER_META.P2;
        const vis = !!(store.state.exploreVisited && store.state.exploreVisited[sp.id]);
        const x = sp.x * sx, y = sp.y * sy;
        const r = sp.priority === "P0" ? 14 : (sp.priority === "P1" ? 11 : 8);
        g.save();
        g.globalAlpha = vis ? 0.45 : 1;
        // 外光环
        g.beginPath();
        g.arc(x, y, r + 6, 0, Math.PI * 2);
        g.fillStyle = vis ? "rgba(100,116,139,0.22)" : tm.halo;
        g.fill();
        // 主体
        g.fillStyle = vis ? "#64748b" : (sp.type === "商会" ? "#b45309" : tm.color);
        g.strokeStyle = sp.type === "商会" ? "#fef08a" : "#ffffff";
        g.lineWidth = 2.5;
        g.beginPath();
        if (sp.type === "迷宫") {
          g.moveTo(x, y - r - 2);
          g.lineTo(x + r + 2, y);
          g.lineTo(x, y + r + 2);
          g.lineTo(x - r - 2, y);
          g.closePath();
        } else if (sp.type === "商会") {
          g.rect(x - r, y - r, r * 2, r * 2);
        } else {
          g.arc(x, y, r, 0, Math.PI * 2);
        }
        g.fill();
        g.stroke();
        // 序号
        g.fillStyle = "#ffffff";
        g.font = `bold ${sp.priority === "P0" ? 11 : 9}px sans-serif`;
        g.textAlign = "center";
        g.textBaseline = "middle";
        g.fillText(vis ? "✓" : String(sp.rank), x, y + 0.5);

        // 常驻高对比度标签
        if (store.state.exploreShowLabels !== false && !vis && (sp.priority === "P0" || (sp.priority === "P1" && sp.score >= 70))) {
          const hi = sp.highlights && sp.highlights[0] ? ` · ${sp.highlights[0]}` : "";
          const txt = `${sp.name.replace("（旺达尔商会）", "·商")}${hi}`;
          g.font = "bold 11px sans-serif";
          const tw = Math.min(180, g.measureText(txt).width + 12);
          const lx = x > W * 0.78 ? x - r - 6 - tw : x + r + 6;
          g.fillStyle = "rgba(15,23,42,0.88)";
          g.strokeStyle = tm.color;
          g.lineWidth = 1.5;
          g.fillRect(lx, y - 10, tw, 20);
          g.strokeRect(lx, y - 10, tw, 20);
          g.fillStyle = "#ffffff";
          g.textAlign = "left";
          g.textBaseline = "middle";
          g.fillText(txt, lx + 6, y + 0.5, tw - 10);
        }
        g.restore();
      }

      // 3) 左上角标题与色标图例条
      g.fillStyle = "rgba(15,23,42,0.88)";
      g.fillRect(16, 16, 560, 44);
      g.fillStyle = "#ffffff";
      g.font = "bold 15px sans-serif";
      g.textAlign = "left";
      g.textBaseline = "middle";
      g.fillText(`万紫千红 · 探索规划（${ctxInfo.rObj.name}｜共 ${ctxInfo.spots.length} 处）  🔴P0必抢  🟠P1重点  🔵P2常规  ◇迷宫  ■商会`, 28, 38);

      const url = cv.toDataURL("image/png");
      triggerDownload(url, `万紫千红-探索规划-${ctxInfo.rObj.name}.png`);
      store.state.exploreFeedback = `✓ 已导出高清标记地图 PNG（1664×1280，共 ${ctxInfo.spots.length} 处标记）`;
      render();
    } catch (err) {
      store.state.exploreFeedback = "导出 PNG 失败：" + (err && err.message ? err.message : String(err));
      render();
    }
  }

  async function exportExploreHtml() {
    const ctxInfo = getExploreExportContext();
    if (!ctxInfo) return;
    let imgDataUrl = DATA.explore.mapImage || "./assets/world_map.jpg";
    try {
      const img = await loadImageEl(imgDataUrl);
      const cv = document.createElement("canvas");
      cv.width = img.naturalWidth || 1664;
      cv.height = img.naturalHeight || 1280;
      cv.getContext("2d").drawImage(img, 0, 0);
      imgDataUrl = cv.toDataURL("image/jpeg", 0.82);
    } catch (_) {}
    const html = EL.buildStandaloneMapHtml({
      title: `万紫千红 · 探索规划（${ctxInfo.rObj.name}）`,
      mapImageDataUrl: imgDataUrl,
      mapWidth: DATA.explore.mapWidth || 3328,
      mapHeight: DATA.explore.mapHeight || 2560,
      viewBox: store.state.exploreViewBox || DATA.explore.defaultViewBox,
      spots: ctxInfo.spots,
      stations: store.state.exploreShowStations !== false ? (ctxInfo.rObj.stations || []) : [],
    });
    const blob = new Blob([html], { type: "text/html;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    triggerDownload(url, `万紫千红-探索规划-${ctxInfo.rObj.name}.html`);
    setTimeout(() => URL.revokeObjectURL(url), 5000);
    store.state.exploreFeedback = `✓ 已导出离线独立标记地图 HTML（含内嵌高清世界底图与 ${ctxInfo.spots.length} 处优先级清单）`;
    render();
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
