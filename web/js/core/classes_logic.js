/* 职业图鉴 · 纯前端核心逻辑（零 DOM 依赖，UMD 导出，Node.js 可直接单测） */
(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  root.FE = root.FE || {};
  root.FE.classesLogic = api;
})(typeof globalThis !== "undefined" ? globalThis : window, function () {
  const TIER_ORDER = ["基础", "初级", "中级", "上级", "最上级", "神将"];
  const STAT_KEYS = ["hp", "str", "mag", "spd", "dex", "def", "res", "lck", "cha"];
  const STAT_LABELS = ["HP", "力", "魔", "速", "技", "防", "魔防", "幸", "魅"];

  function filterClasses(classes, opts) {
    const list = classes || [];
    const o = opts || {};
    const tier = o.tier && o.tier !== "全部" ? o.tier : null;
    const selected = (o.selectedSkills || []).filter(Boolean);
    const selectedStats = (o.selectedStats || []).filter(Boolean);
    const matchMode = o.matchMode === "any" ? "any" : "all";
    const q = String(o.query || "").trim().toLowerCase();

    return list.filter(c => {
      if (tier && c.tier !== tier) return false;
      const usable = c.usableSkills || [];
      if (selected.length) {
        if (matchMode === "all") {
          if (!selected.every(sk => usable.includes(sk))) return false;
        } else {
          if (!selected.some(sk => usable.includes(sk))) return false;
        }
      }
      const adv = c.advantageStats || [];
      if (selectedStats.length) {
        if (matchMode === "all") {
          if (!selectedStats.every(st => adv.includes(st))) return false;
        } else {
          if (!selectedStats.some(st => adv.includes(st))) return false;
        }
      }
      if (!q) return true;
      const hay = [
        c.name,
        c.tier,
        c.unitType,
        c.family,
        c.limit,
        c.requirement,
        c.skillExp,
        c.mastery,
        c.unlock,
        ...(c.innate || []),
        ...usable,
        ...adv,
        ...(c.disadvantageStats || []),
      ].filter(Boolean).join(" ").toLowerCase();
      return hay.includes(q);
    });
  }

  function groupClassesByTier(classes, tierOrder) {
    const order = tierOrder && tierOrder.length ? tierOrder : TIER_ORDER;
    const buckets = new Map();
    for (const c of (classes || [])) {
      const t = c.tier || "其他";
      if (!buckets.has(t)) buckets.set(t, []);
      buckets.get(t).push(c);
    }
    const groups = [];
    for (const t of order) {
      if (buckets.has(t)) {
        groups.push({ tier: t, classes: buckets.get(t) });
        buckets.delete(t);
      }
    }
    for (const [t, arr] of buckets.entries()) {
      groups.push({ tier: t, classes: arr });
    }
    return groups;
  }

  function summarizeClasses(classes, allSkills) {
    const list = classes || [];
    const tierCounts = {};
    const skillCounts = {};
    const advantageCounts = {};
    for (const sk of (allSkills || [])) skillCounts[sk] = 0;
    for (const st of STAT_LABELS) advantageCounts[st] = 0;
    for (const c of list) {
      const t = c.tier || "其他";
      tierCounts[t] = (tierCounts[t] || 0) + 1;
      for (const sk of (c.usableSkills || [])) {
        skillCounts[sk] = (skillCounts[sk] || 0) + 1;
      }
      for (const st of (c.advantageStats || [])) {
        advantageCounts[st] = (advantageCounts[st] || 0) + 1;
      }
    }
    return { total: list.length, tierCounts, skillCounts, advantageCounts };
  }

  function formatMinStats(minStats) {
    if (!minStats) return "—";
    const parts = [];
    for (let i = 0; i < STAT_KEYS.length; i++) {
      const v = minStats[STAT_KEYS[i]];
      if (v && v > 0) parts.push(`${STAT_LABELS[i]}${v}`);
    }
    return parts.length ? parts.join(" ") : "—";
  }

  return {
    TIER_ORDER,
    STAT_KEYS,
    STAT_LABELS,
    filterClasses,
    groupClassesByTier,
    summarizeClasses,
    formatMinStats,
  };
});
