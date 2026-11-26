/* 道具 / 材料采集 · 纯前端核心逻辑（零 DOM 依赖，完全可单元测试） */
(function (root, factory) {
  const utils = (typeof module === "object" && module.exports) ? require("./utils.js") : root.FE.utils;
  const api = factory(utils);
  if (typeof module === "object" && module.exports) module.exports = api;
  root.FE = root.FE || {};
  root.FE.itemsLogic = api;
})(typeof globalThis !== "undefined" ? globalThis : window, function (U) {
  function filterTowns(towns, category, query) {
    const q = String(query || "").trim().toLowerCase();
    const cat = category || "全部";
    const out = [];
    let totalItems = 0;
    for (const t of towns || []) {
      const townHit = q && ((t.cn || "") + (t.en || "") + (t.jp || "")).toLowerCase().includes(q);
      const items = (t.items || []).filter(it =>
        (cat === "全部" || it.cat === cat) &&
        (!q || townHit || ((it.cn || "") + (it.jp || "") + (it.note || "")).toLowerCase().includes(q))
      );
      if (!items.length) continue;
      totalItems += items.length;
      out.push({ ...t, items });
    }
    return { towns: out, townCount: out.length, itemCount: totalItems };
  }

  function filterBarter(barter, category, query) {
    const q = String(query || "").trim().toLowerCase();
    const cat = category || "全部";
    return (barter || []).filter(x =>
      (cat === "全部" || x.type === cat || (cat === "道具" && x.type === "戒指")) &&
      (!q || ((x.cn || "") + (x.jp || "") + (x.cost || "") + (x.note || "") + (x.location || "")).toLowerCase().includes(q))
    );
  }

  function filterMaterials(materials, category, query) {
    const q = String(query || "").trim().toLowerCase();
    const cat = category || "全部";
    const out = [];
    for (const m of materials || []) {
      const matHit = q && (m.material || "").toLowerCase().includes(q);
      const usedIn = (m.usedIn || []).filter(u =>
        (cat === "全部" || u.type === cat || (cat === "道具" && u.type === "戒指")) &&
        (!q || matHit || ((u.cn || "") + (u.jp || "") + (u.note || "") + (u.location || "")).toLowerCase().includes(q))
      );
      if (!usedIn.length) continue;
      out.push({ ...m, usedIn });
    }
    return out;
  }

  function highlightMatch(text, query) {
    const safe = U.esc(text);
    const q = String(query || "").trim();
    if (!q) return safe;
    const eq = U.esc(q);
    const idx = safe.toLowerCase().indexOf(eq.toLowerCase());
    if (idx < 0) return safe;
    return safe.slice(0, idx) + "<mark>" + safe.slice(idx, idx + eq.length) + "</mark>" + safe.slice(idx + eq.length);
  }

  return { filterTowns, filterBarter, filterMaterials, highlightMatch };
});
