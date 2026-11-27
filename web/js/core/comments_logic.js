/* 路线规划 Plan Mode 批注系统纯核心逻辑（零 DOM 依赖，Node.js 可直接单元测试） */
(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory();
  } else {
    root.FE = root.FE || {};
    root.FE.commentsLogic = factory();
  }
})(typeof globalThis !== "undefined" ? globalThis : window, function () {
  function genId(existing, nowIso) {
    const base = "cmt-" + String(nowIso || "").replace(/[^0-9]/g, "").slice(0, 14) + "-";
    let n = (existing || []).length + 1;
    const used = new Set((existing || []).map(c => c.id));
    while (used.has(base + n)) n += 1;
    return base + n;
  }

  function addComment(list, payload) {
    const p = payload || {};
    const text = String(p.text || "").trim();
    if (!text) return [...(list || [])];
    const at = p.at || new Date().toISOString();
    const section = String(p.section || "mine");
    const next = {
      id: p.id || genId(list, at),
      targetId: String(p.targetId || "general"),
      targetLabel: String(p.targetLabel || "全局规划"),
      section,
      viewHash: String(p.viewHash || ("#" + section)),
      anchorId: String(p.anchorId || ""),
      xpath: String(p.xpath || ""),
      version: String(p.version || ""),
      quote: String(p.quote || "").trim().slice(0, 200),
      text,
      resolved: false,
      at,
    };
    return [...(list || []), next];
  }

  function updateComment(list, id, newText, at) {
    const txt = String(newText || "").trim();
    if (!txt) return [...(list || [])];
    return (list || []).map(c =>
      c.id === id ? { ...c, text: txt, at: at || new Date().toISOString() } : c
    );
  }

  function toggleResolveComment(list, id) {
    return (list || []).map(c => (c.id === id ? { ...c, resolved: !c.resolved } : c));
  }

  function deleteComment(list, id) {
    return (list || []).filter(c => c.id !== id);
  }

  function commentsForTarget(list, targetId, opts) {
    const includeResolved = !opts || opts.includeResolved !== false;
    return (list || []).filter(c => c.targetId === targetId && (includeResolved || !c.resolved));
  }

  function summarizeComments(list) {
    const arr = list || [];
    const byTarget = {};
    let open = 0;
    let resolved = 0;
    for (const c of arr) {
      if (c.resolved) resolved += 1;
      else open += 1;
      if (!byTarget[c.targetId]) byTarget[c.targetId] = { open: 0, resolved: 0, total: 0 };
      byTarget[c.targetId].total += 1;
      if (c.resolved) byTarget[c.targetId].resolved += 1;
      else byTarget[c.targetId].open += 1;
    }
    return { total: arr.length, open, resolved, byTarget };
  }

  function formatLocator(c) {
    const parts = [];
    const vh = c.viewHash || (c.section ? "#" + c.section : "");
    if (vh) parts.push(`视图 \`${vh}\``);
    if (c.anchorId) parts.push(`id \`#${c.anchorId}\``);
    if (c.xpath) parts.push(`XPath \`${c.xpath}\``);
    if (c.version) parts.push(`版本 \`${c.version}\``);
    return parts.join(" · ");
  }

  /**
   * 导出类似 Plan Mode 审阅批注的 Markdown 文本（含版本号、div id / XPath 精准定位、划词引用、批注内容及当前路线方案选择）。
   */
  function formatPlanReviewExport(opts) {
    const o = opts || {};
    const comments = (o.comments || []).filter(c => o.includeResolved || !c.resolved);
    const meta = o.meta || {};
    const lines = ["# 路线与职业规划 · Plan Mode 批注与选择导出"];
    const metaParts = [];
    if (meta.version) metaParts.push(`版本：\`${meta.version}\``);
    if (meta.builtAt) metaParts.push(`构建：\`${meta.builtAt}\``);
    if (meta.shotKey) metaParts.push(`快照：\`${meta.shotKey}\``);
    if (meta.viewHash) metaParts.push(`导出视图：\`${meta.viewHash}\``);
    if (metaParts.length) {
      lines.push(`> ${metaParts.join(" ｜ ")}`);
    }
    lines.push("");

    lines.push(`## 一、Plan Mode 批注（共 ${comments.length} 条${o.includeResolved ? "，含已解决" : "待处理"}）`);
    if (!comments.length) {
      lines.push("- （当前没有待处理批注）");
    } else {
      // 按 targetLabel 分组，保持首次出现顺序
      const groups = new Map();
      for (const c of comments) {
        const key = c.targetLabel || c.targetId || "全局规划";
        if (!groups.has(key)) groups.set(key, []);
        groups.get(key).push(c);
      }
      for (const [label, items] of groups.entries()) {
        lines.push(`### ${label}`);
        for (const c of items) {
          const st = c.resolved ? "[已解决] " : "";
          const loc = formatLocator(c);
          if (c.quote) {
            lines.push(`- ${st}引用：「${c.quote}」`);
            if (loc) lines.push(`  - 定位：${loc}`);
            lines.push(`  - 批注：${c.text}`);
          } else {
            lines.push(`- ${st}${c.text}`);
            if (loc) lines.push(`  - 定位：${loc}`);
          }
        }
      }
    }

    if (typeof o.formatRoutePicksExport === "function" && (o.proposals || []).length) {
      lines.push("");
      lines.push("## 二、当前路线方案选择汇总");
      lines.push(o.formatRoutePicksExport(o.proposals, o.routePicks || {}));
    }

    return lines.join("\n");
  }

  return {
    addComment,
    updateComment,
    toggleResolveComment,
    deleteComment,
    commentsForTarget,
    summarizeComments,
    formatLocator,
    formatPlanReviewExport,
  };
});
