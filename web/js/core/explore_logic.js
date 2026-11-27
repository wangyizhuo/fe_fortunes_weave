/* 探索规划纯核心逻辑（零 DOM 依赖，Node.js 可直接单元测试） */
(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory();
  } else {
    root.FE = root.FE || {};
    root.FE.exploreLogic = factory();
  }
})(typeof globalThis !== "undefined" ? globalThis : window, function () {
  const TIER_META = {
    P0: { color: "#dc2626", stroke: "#ffffff", halo: "rgba(220,38,38,0.34)", label: "P0 必抢" },
    P1: { color: "#ea580c", stroke: "#ffffff", halo: "rgba(234,88,12,0.28)", label: "P1 重点" },
    P2: { color: "#2563eb", stroke: "#ffffff", halo: "rgba(37,99,235,0.22)", label: "P2 常规" },
  };

  const TYPE_SHORT = {
    "矿石": "矿",
    "道具": "箱",
    "鱼": "鱼",
    "蔬菜": "菜",
    "迷宫": "迷",
    "商会": "商",
  };

  function norm(s) {
    return String(s || "").trim().toLowerCase();
  }

  function escHtml(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, m => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    }[m]));
  }

  /**
   * 按优先级多选、类型多选、已采集过滤与关键词（地名/素材/兑换物/方位/驿站）筛选探索点位。
   */
  function filterExploreSpots(spots, opts) {
    const o = opts || {};
    const priorities = Array.isArray(o.priorities) ? o.priorities.filter(Boolean) : [];
    const types = Array.isArray(o.types) ? o.types.filter(Boolean) : [];
    const q = norm(o.query);
    const hideVisited = !!o.hideVisited;
    const visitedMap = o.visitedMap || {};

    return (spots || []).filter(sp => {
      if (priorities.length && !priorities.includes(sp.priority)) return false;
      if (types.length && !types.includes(sp.type)) return false;
      if (hideVisited && visitedMap[sp.id]) return false;
      if (q) {
        const itemHay = (sp.items || []).map(it => {
          const ex = (it.exchanges || []).map(e => `${e.reward} ${e.place}`).join(" ");
          return `${it.name} ${it.tag || ""} ${it.reason || ""} ${ex}`;
        }).join(" ");
        const hay = [
          sp.name,
          sp.placeName || "",
          sp.type,
          sp.priority,
          sp.region || "",
          sp.nearestStation || "",
          sp.desc || "",
          ...(sp.highlights || []),
          itemHay,
        ].join(" ").toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });
  }

  /**
   * 汇总筛选后的点位优先级、类型与采集进度统计。
   */
  function summarizeExplore(spots, visitedMap) {
    const vm = visitedMap || {};
    const byTier = { P0: 0, P1: 0, P2: 0 };
    const byType = { "矿石": 0, "道具": 0, "鱼": 0, "蔬菜": 0, "迷宫": 0, "商会": 0 };
    let visited = 0;
    for (const sp of spots || []) {
      if (byTier[sp.priority] != null) byTier[sp.priority] += 1;
      if (byType[sp.type] != null) byType[sp.type] += 1;
      if (vm[sp.id]) visited += 1;
    }
    const total = (spots || []).length;
    return { total, visited, remaining: total - visited, byTier, byType };
  }

  /**
   * 提取当前筛选点位中的高优先素材列表，供外部地图（fire-emblem-fw.site）收集清单同步使用。
   */
  function extractFwCollectItems(spots, routeKey) {
    const mats = [];
    const seen = new Set();
    for (const sp of spots || []) {
      if (sp.type === "商会" || sp.type === "迷宫") continue;
      for (const it of sp.items || []) {
        if (it.tier === "P0" || it.tier === "P1" || (spots || []).length <= 15) {
          if (!seen.has(it.name)) {
            seen.add(it.name);
            mats.push(it.name);
          }
        }
      }
    }
    return {
      routeKey: routeKey || "dietrich",
      items: mats.slice(0, 30),
    };
  }

  /**
   * 计算给定点位集合的紧凑 SVG viewBox，用于一键聚焦或自适应画布。
   */
  function computeFitViewBox(spots, fallbackBox, mapW, mapH) {
    const fb = Array.isArray(fallbackBox) && fallbackBox.length === 4 ? fallbackBox : [210, 230, 2900, 2100];
    const list = spots || [];
    if (!list.length) return fb.slice();
    let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
    for (const s of list) {
      if (s.x < minX) minX = s.x;
      if (s.x > maxX) maxX = s.x;
      if (s.y < minY) minY = s.y;
      if (s.y > maxY) maxY = s.y;
    }
    const padX = Math.max(220, (maxX - minX) * 0.14);
    const padY = Math.max(180, (maxY - minY) * 0.14);
    const w = Math.max(700, Math.min(mapW || 3328, (maxX - minX) + padX * 2));
    const h = Math.max(540, Math.min(mapH || 2560, (maxY - minY) + padY * 2));
    const x = Math.max(0, Math.min((mapW || 3328) - w, minX - padX));
    const y = Math.max(0, Math.min((mapH || 2560) - h, minY - padY));
    return [Math.round(x), Math.round(y), Math.round(w), Math.round(h)];
  }

  /**
   * 生成独立可离线打开的标记地图 HTML 文档（带高显眼 SVG 标号、图例与清单）。
   */
  function buildStandaloneMapHtml(opts) {
    const o = opts || {};
    const title = o.title || "万紫千红 · 探索规划标记地图";
    const mapImageDataUrl = o.mapImageDataUrl || "./assets/world_map.jpg";
    const mapW = o.mapWidth || 3328;
    const mapH = o.mapHeight || 2560;
    const vb = o.viewBox || [210, 230, 2900, 2100];
    const spots = o.spots || [];
    const stations = o.stations || [];

    const stSvg = stations.map(st =>
      `<g transform="translate(${st.x},${st.y})"><rect x="-15" y="-15" width="30" height="30" rx="6" fill="#0f766e" stroke="#fff" stroke-width="3"/><text y="6" text-anchor="middle" fill="#fff" font-size="16" font-weight="800">站</text></g>`
    ).join("");

    const pinSvg = spots.map(sp => {
      const tm = TIER_META[sp.priority] || TIER_META.P2;
      const r = sp.priority === "P0" ? 26 : (sp.priority === "P1" ? 20 : 15);
      const label = `#${sp.rank} ${sp.name}` + (sp.highlights && sp.highlights[0] ? ` · ${sp.highlights[0]}` : "");
      return `<g transform="translate(${sp.x},${sp.y})">
        <circle r="${r + 10}" fill="${tm.halo}"/>
        <circle r="${r}" fill="${tm.color}" stroke="#fff" stroke-width="4"/>
        <text y="${Math.round(r * 0.35)}" text-anchor="middle" fill="#fff" font-size="${sp.priority === "P0" ? 18 : 14}" font-weight="800">${sp.rank}</text>
        ${sp.priority !== "P2" ? `<rect x="${r + 8}" y="-16" width="${Math.min(280, label.length * 14 + 18)}" height="30" rx="6" fill="rgba(15,23,42,0.86)" stroke="${tm.color}" stroke-width="2"/><text x="${r + 16}" y="5" fill="#fff" font-size="16" font-weight="700">${escHtml(label)}</text>` : ""}
      </g>`;
    }).join("");

    const rows = spots.map(sp => {
      const items = (sp.items || []).slice(0, 6).map(it => `${it.name}${it.tag ? "(" + it.tag + ")" : ""}`).join("、");
      return `<tr><td><b>#${sp.rank}</b></td><td><span class="b ${sp.priority}">${sp.priority}</span></td><td><b>${escHtml(sp.name)}</b><br><small>${escHtml(sp.region || "")}${sp.nearestStation ? " · 近" + escHtml(sp.nearestStation) : ""}</small></td><td>${escHtml(sp.type)}</td><td>${escHtml(items)}</td></tr>`;
    }).join("");

    return `<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>${escHtml(title)}</title>
<style>body{font-family:system-ui,-apple-system,sans-serif;margin:0;padding:16px;background:#f8fafc;color:#0f172a}h1{margin:0 0 8px;font-size:20px}.meta{color:#475569;font-size:13px;margin-bottom:12px}.mapwrap{background:#0b132b;border-radius:12px;overflow:hidden;border:2px solid #cbd5e1}svg{display:block;width:100%;height:auto}table{width:100%;border-collapse:collapse;margin-top:16px;background:#fff;font-size:13px}th,td{border:1px solid #e2e8f0;padding:7px 9px;text-align:left;vertical-align:top}.b{display:inline-block;padding:1px 7px;border-radius:4px;color:#fff;font-weight:700;font-size:12px}.b.P0{background:#dc2626}.b.P1{background:#ea580c}.b.P2{background:#2563eb}</style></head>
<body><h1>${escHtml(title)}</h1><div class="meta">共标记 ${spots.length} 个探索点位（🔴 P0 必抢孤品 / 🟠 P1 强力兑换&amp;锻造 / 🔵 P2 常规食材）</div>
<div class="mapwrap"><svg viewBox="${vb.join(" ")}" xmlns="http://www.w3.org/2000/svg"><image href="${escHtml(mapImageDataUrl)}" x="0" y="0" width="${mapW}" height="${mapH}"/>${stSvg}${pinSvg}</svg></div>
<table><thead><tr><th>#</th><th>优先级</th><th>地点与方位</th><th>类型</th><th>核心产出</th></tr></thead><tbody>${rows}</tbody></table></body></html>`;
  }

  return {
    TIER_META,
    TYPE_SHORT,
    filterExploreSpots,
    summarizeExplore,
    extractFwCollectItems,
    computeFitViewBox,
    buildStandaloneMapHtml,
  };
});
