/* 状态存储与外部同步适配层（localStorage + 可选 Claude DB / Google Sheets） */
(function (root) {
  const U = root.FE.utils;
  const RL = root.FE.routeLogic;

  const SHEET_ID = "1sNlvXfRDNIhF0cVGieTvqqBEfn10JgG6mM0dOzOm0cg";
  const SHEET_TAB = "成长进度";
  const SERVER = "Google Sheets";
  const MCP_MSG = {
    server_not_connected: "没连上 Google Sheets：到 claude.ai 设置 → 连接器里添加",
    needs_reauth: "Google Sheets 登录过期：到 claude.ai 设置 → 连接器里重新连接",
    approval_required: "需要你先允许这个页面使用 Google Sheets",
    consent_required: "需要你先允许这个页面使用 Google Sheets",
    cancelled: "已取消",
    blocked_by_policy: "组织策略不允许这个页面用 Google Sheets",
    tool_error: "表格那边报错",
  };

  function createStore(onRender, onStatus) {
    const CL = root.FE.commentsLogic;
    const state = {
      prog: {},
      info: {},
      routePicks: {},
      planComments: [],
      commentMode: true,
      commentDrawerOpen: false,
      commentDraft: null, // { targetId, targetLabel, section, quote, text }
      editingCommentId: null,
      focus: "",
      view: "meal",
      longS: {},
      affinityQuery: "",
      affinityOnlyPerfect: false,
      affinityRosterFilter: "important",
      itemsCategory: "全部",
      itemsQuery: "",
      itemsTab: "all", // all | shops | barter | materials
      classesTier: "全部",
      classesSkills: [],
      classesStats: [],
      classesMatchMode: "all", // all | any
      classesQuery: "",
      skillsTab: "skills", // skills | chars
      skillsQuery: "",
      skillsRating: "全部",
      skillsScope: "全部",
      skillsCategory: "全部",
      skillsDiscipline: "全部",
      skillsUnitTypes: [],
      skillsOnlyRecruited: false,
      skillsCharGroup: "recruited", // recruited | dietrich | all
      skillsCharTier: "全部", // 全部 | SS | S | A | B | C | D
      skillsShowAll: false,
      exploreRoute: "dietrich",
      explorePriorities: ["P0"],
      exploreTypes: ["矿石", "道具", "鱼", "蔬菜"],
      exploreQuery: "",
      exploreVisited: {},
      exploreHideVisited: false,
      exploreShowLabels: true,
      exploreShowStations: true,
      exploreShowArrows: false,
      exploreSelectedId: "",
      exploreViewBox: null,
      exploreFeedback: "",
      copyFeedback: "",
      db: null,
      writing: false,
      dirty: new Map(),
    };

    function saveLocal() {
      try {
        localStorage.setItem(
          "route-state2",
          JSON.stringify({
            prog: state.prog,
            info: state.info,
            routePicks: state.routePicks,
            planComments: state.planComments,
            exploreVisited: state.exploreVisited,
          })
        );
      } catch (_) {}
    }

    function loadLocal() {
      try {
        const v = JSON.parse(localStorage.getItem("route-state2") || "{}");
        state.prog = v.prog || {};
        state.info = v.info || {};
        state.routePicks = v.routePicks || {};
        state.planComments = Array.isArray(v.planComments) ? v.planComments : [];
        state.exploreVisited = (v.exploreVisited && typeof v.exploreVisited === "object") ? v.exploreVisited : {};
      } catch (_) {}
    }

    function loadFocus(chars) {
      try { state.focus = localStorage.getItem("route-focus") || ""; } catch (_) {}
      if (state.focus && !(chars || []).some(c => U.slug(c) === state.focus)) state.focus = "";
    }

    function setFocus(slugVal) {
      state.focus = slugVal || "";
      try { localStorage.setItem("route-focus", state.focus); } catch (_) {}
    }

    async function flush() {
      if (state.writing || !state.db) return;
      state.writing = true;
      try {
        while (state.dirty.size) {
          const [path, val] = state.dirty.entries().next().value;
          const [coll, id] = path.split("/");
          const ref = state.db.collection(coll).doc(id);
          if (val) await ref.set(val);
          else await ref.delete();
          if (state.dirty.get(path) === val) state.dirty.delete(path);
        }
        onStatus("实时共享 · 已保存", "on");
      } catch (err) {
        onStatus("没保存上：" + (err && err.code === "permission_denied" ? "你只有查看权限" : "网络或权限问题，刷新后再试"), "warn");
      } finally {
        state.writing = false;
      }
    }

    function queue(path, val) {
      state.dirty.set(path, val);
      if (!state.db) {
        saveLocal();
        return;
      }
      flush();
    }

    function setProg(c, s, fn) {
      const key = U.keyOf(c, s);
      const p = { ...(state.prog[key] || {}) };
      fn(p);
      if (p.done !== undefined) {
        state.prog[key] = p;
        const auto = RL.walk(c, state.prog, state.info).rows.find(r => r.s === s).auto;
        if (p.done === auto) delete p.done;
      }
      const val = {};
      if (p.done !== undefined) val.done = p.done;
      if (p.choice) val.choice = p.choice;
      if (p.chance != null) val.chance = p.chance;
      if (p.ok) val.ok = true;
      if (Object.keys(val).length) {
        state.prog[key] = val;
        queue("progress/" + key, { ...val, at: new Date().toISOString() });
      } else {
        delete state.prog[key];
        queue("progress/" + key, null);
      }
    }

    function setCharInfo(c, ci) {
      const k = U.slug(c);
      state.info[k] = { level: ci.level, owned: ci.owned, skills: ci.skills };
      queue("chars/" + k, { ...state.info[k], at: new Date().toISOString() });
    }

    function setRoutePick(charName, optionId, note) {
      const prev = state.routePicks[charName] || {};
      const next = {
        optionId: optionId !== undefined ? optionId : prev.optionId,
        note: note !== undefined ? note : (prev.note || ""),
        at: new Date().toISOString(),
      };
      state.routePicks[charName] = next;
      queue("routePicks/" + U.slug({ name: charName }), { name: charName, ...next });
    }

    function clearRoutePick(charName) {
      delete state.routePicks[charName];
      queue("routePicks/" + U.slug({ name: charName }), null);
    }

    function resetAllRoutePicks() {
      const names = Object.keys(state.routePicks || {});
      state.routePicks = {};
      for (const n of names) queue("routePicks/" + U.slug({ name: n }), null);
      if (!names.length) saveLocal();
    }

    function addPlanComment(payload) {
      const prevLen = state.planComments.length;
      state.planComments = CL.addComment(state.planComments, payload);
      if (state.planComments.length > prevLen) {
        const created = state.planComments[state.planComments.length - 1];
        queue("planComments/" + created.id, created);
      }
    }

    function updatePlanComment(id, text) {
      state.planComments = CL.updateComment(state.planComments, id, text);
      const item = state.planComments.find(c => c.id === id);
      if (item) queue("planComments/" + id, item);
    }

    function toggleResolvePlanComment(id) {
      state.planComments = CL.toggleResolveComment(state.planComments, id);
      const item = state.planComments.find(c => c.id === id);
      if (item) queue("planComments/" + id, item);
    }

    function deletePlanComment(id) {
      state.planComments = CL.deleteComment(state.planComments, id);
      queue("planComments/" + id, null);
    }

    function clearAllPlanComments() {
      const ids = state.planComments.map(c => c.id);
      state.planComments = [];
      for (const id of ids) queue("planComments/" + id, null);
      if (!ids.length) saveLocal();
    }

    async function initSync() {
      const db = root.claude?.use ? await root.claude.use("db").catch(() => null) : null;
      state.db = db;
      if (!db) {
        loadLocal();
        onRender();
        onStatus("本地模式 · 进度保存在当前浏览器", "on");
        return;
      }
      const timer = setTimeout(() => onStatus("暂时连不上，显示的可能不是最新的", "warn"), 10000);
      const watch = (coll, apply) => db.collection(coll).onSnapshot(snap => {
        if (!snap.metadata.fromCache) clearTimeout(timer);
        const next = {};
        for (const d of snap.docs) next[d.id] = d.data();
        for (const [path, val] of state.dirty) {
          const [cl, id] = path.split("/");
          if (cl === coll) {
            if (val) next[id] = val;
            else delete next[id];
          }
        }
        apply(next);
        onRender();
        if (!snap.metadata.fromCache) onStatus("实时共享 · 已同步", "on");
      }, () => {
        clearTimeout(timer);
        onStatus("读取记录失败，刷新页面再试", "warn");
      });
      watch("progress", v => {
        state.prog = {};
        for (const [k, d] of Object.entries(v)) {
          const p = {};
          if (typeof d?.done === "boolean") p.done = d.done;
          if (d?.choice) p.choice = d.choice;
          if (typeof d?.chance === "number") p.chance = d.chance;
          if (d?.ok) p.ok = true;
          if (Object.keys(p).length) state.prog[k] = p;
        }
      });
      watch("chars", v => {
        state.info = {};
        for (const [k, d] of Object.entries(v)) {
          if (d) state.info[k] = { level: d.level, owned: d.owned, skills: d.skills || {} };
        }
      });
      watch("routePicks", v => {
        state.routePicks = {};
        for (const d of Object.values(v)) {
          if (d && d.name && d.optionId) {
            state.routePicks[d.name] = { optionId: d.optionId, note: d.note || "", at: d.at || null };
          }
        }
      });
      watch("planComments", v => {
        state.planComments = Object.values(v)
          .filter(d => d && d.id && d.text)
          .sort((a, b) => String(a.at || "").localeCompare(String(b.at || "")));
      });
    }

    async function syncSheet(routeData, btn, setSyncText) {
      const mcp = root.claude?.use ? await root.claude.use("mcp").catch(() => null) : null;
      if (!mcp) {
        setSyncText("当前为本地浏览器模式（Google Sheets 同步需在 Claude 环境内使用）", true);
        return;
      }
      btn.disabled = true;
      setSyncText("正在写入「成长进度」…", false);
      try {
        const now = new Date().toLocaleString("zh-CN", { hour12: false });
        const values = RL.buildSheetValues(routeData, state.prog, state.info, now);
        await mcp.callTool(SERVER, "batch_clear_values", { spreadsheetId: SHEET_ID, ranges: [SHEET_TAB + "!A1:Z400"] });
        await mcp.callTool(SERVER, "update_values", { spreadsheetId: SHEET_ID, range: SHEET_TAB + "!A1", values });
        setSyncText(`已同步 ${values.length} 行`, false);
      } catch (err) {
        setSyncText((MCP_MSG[err?.code] || "同步失败") + (err?.code === "tool_error" && err.message ? "：" + err.message.slice(0, 160) : ""), true);
      } finally {
        btn.disabled = false;
      }
    }

    function setExploreVisited(spotId, checked) {
      if (!spotId) return;
      state.exploreVisited = { ...(state.exploreVisited || {}) };
      if (checked) state.exploreVisited[spotId] = true;
      else delete state.exploreVisited[spotId];
      saveLocal();
    }

    return {
      state, loadLocal, loadFocus, setFocus, setProg, setCharInfo,
      setRoutePick, clearRoutePick, resetAllRoutePicks,
      addPlanComment, updatePlanComment, toggleResolvePlanComment, deletePlanComment, clearAllPlanComments,
      setExploreVisited,
      initSync, syncSheet,
    };
  }

  root.FE = root.FE || {};
  root.FE.createStore = createStore;
})(window);
