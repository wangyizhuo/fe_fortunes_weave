/* 探索规划视图：基于采集物需求优先级的高显眼交互式世界地图 + 导出 PNG/HTML + 外部地图联动 */
(function (root) {
  const U = root.FE.utils;
  const EL = root.FE.exploreLogic;

  const PRESETS = [
    {
      id: "p0_gather",
      label: "🔴 P0 必抢采集（缺口+神矿+指南书）",
      priorities: ["P0"],
      types: ["矿石", "道具", "鱼", "蔬菜"],
      onlyBarterLack: false,
    },
    {
      id: "barter_p0",
      label: "🎯 仅看商会 P0 缺口（9 处）",
      priorities: ["P0"],
      types: ["矿石", "道具", "鱼", "蔬菜"],
      onlyBarterLack: true,
    },
    {
      id: "barter_p01",
      label: "🛒 全部商会缺口（P0+P1）",
      priorities: ["P0", "P1"],
      types: ["矿石", "道具", "鱼", "蔬菜"],
      onlyBarterLack: true,
    },
    {
      id: "p01_gather",
      label: "🔥 P0 + P1 全部重点采集",
      priorities: ["P0", "P1"],
      types: ["矿石", "道具", "鱼", "蔬菜"],
      onlyBarterLack: false,
    },
    {
      id: "ores",
      label: "⛏ 全图矿石点",
      priorities: ["P0", "P1", "P2"],
      types: ["矿石"],
      onlyBarterLack: false,
    },
    {
      id: "dungeons",
      label: "🏰 迷宫 S 武器 / 指南书 / 能力露",
      priorities: ["P0", "P1"],
      types: ["迷宫"],
      onlyBarterLack: false,
    },
    {
      id: "p0_barter",
      label: "🏪 P0 缺口 + 旺达尔商会",
      priorities: ["P0"],
      types: ["矿石", "道具", "鱼", "蔬菜", "商会"],
      onlyBarterLack: true,
    },
  ];

  function fwItemUrl(name) {
    return "https://fire-emblem-fw.site/map.html#q:" + encodeURIComponent(name);
  }

  function renderSpotPinSvg(sp, selectedId, visited, showLabels) {
    const tm = EL.TIER_META[sp.priority] || EL.TIER_META.P2;
    const isSel = selectedId === sp.id;
    const isP0 = sp.priority === "P0";
    const isP1 = sp.priority === "P1";
    const r = isP0 ? 27 : (isP1 ? 21 : 15);
    const fill = visited ? "#64748b" : tm.color;
    const halo = visited ? "rgba(100,116,139,0.22)" : tm.halo;
    const op = visited ? 0.55 : 1;

    let shape = "";
    if (sp.type === "迷宫") {
      const d = r + 3;
      shape = `<polygon points="0,${-d} ${d},0 0,${d} ${-d},0" fill="${fill}" stroke="#fff" stroke-width="${isSel ? 6 : 4}"/>`;
    } else if (sp.type === "商会") {
      const d = r;
      shape = `<rect x="${-d}" y="${-d}" width="${d * 2}" height="${d * 2}" rx="7" fill="${visited ? "#64748b" : "#b45309"}" stroke="#fef08a" stroke-width="${isSel ? 6 : 4}"/>`;
    } else {
      shape = `<circle r="${r}" fill="${fill}" stroke="#fff" stroke-width="${isSel ? 6 : 4}"/>`;
    }

    const pulse = !visited && (isP0 || isSel)
      ? `<circle class="exp-pulse" r="${r + 14}" fill="none" stroke="${isSel ? "#facc15" : tm.color}" stroke-width="${isSel ? 6 : 4}"/>`
      : "";

    const hiText = (sp.highlights && sp.highlights[0]) ? ` · ${sp.highlights[0]}` : "";
    const shortName = sp.name.replace("（旺达尔商会）", "·商会");
    const labelText = `${shortName}${hiText}`;
    const showThisLabel = showLabels && (isSel || (!visited && (isP0 || (isP1 && sp.score >= 70))));
    const boxW = Math.min(265, Math.max(96, labelText.length * 16 + 20));
    // 右半图把标签放到左边避免裁切
    const flipLeft = sp.x > 2550;
    const lx = flipLeft ? -(r + 10 + boxW) : (r + 10);
    const labelSvg = showThisLabel
      ? `<g class="exp-lbl" pointer-events="none">
          <rect x="${lx}" y="-19" width="${boxW}" height="36" rx="8" fill="rgba(15,23,42,0.90)" stroke="${isSel ? "#facc15" : fill}" stroke-width="${isSel ? 3.5 : 2.2}"/>
          <text x="${lx + 11}" y="6" fill="#ffffff" font-size="18" font-weight="700">${U.esc(labelText)}</text>
        </g>`
      : "";

    const innerText = visited ? "✓" : String(sp.rank);
    const typeTag = EL.TYPE_SHORT[sp.type] || "";
    const typePill = !visited && isP0
      ? `<g transform="translate(${r - 4},${-r + 2})"><circle r="11" fill="#0f172a" stroke="#fff" stroke-width="2"/><text y="4" text-anchor="middle" fill="#fde047" font-size="12" font-weight="800">${U.esc(typeTag)}</text></g>`
      : "";

    return `<g class="exp-pin${isSel ? " sel" : ""}${visited ? " vis" : ""}" data-exp-pin="${U.esc(sp.id)}" transform="translate(${sp.x},${sp.y})" opacity="${op}">
      <title>#${sp.rank} [${sp.priority}·${sp.type}] ${U.esc(sp.name)}：${U.esc((sp.highlights || []).join(" / "))}</title>
      <circle r="${r + 11}" fill="${halo}"/>
      ${pulse}
      ${shape}
      <text y="${Math.round(r * 0.35)}" text-anchor="middle" fill="#ffffff" font-size="${isP0 ? 19 : 15}" font-weight="800">${U.esc(innerText)}</text>
      ${typePill}
      ${labelSvg}
    </g>`;
  }

  function renderSelectedCard(sp, visited) {
    if (!sp) {
      return `<div class="exp-detail empty">👆 点击地图上任意彩色标记（或下方清单任意一行），即可查看完整产出素材、优先级理由、最近驿站，并一键跳转到 <code>fire-emblem-fw.site</code> 核对原图。</div>`;
    }
    const itemsHtml = (sp.items || []).map(it => {
      const exHtml = (it.exchanges || []).length
        ? ` <span class="exp-ex">⇄ ${U.esc(it.exchanges.map(e => `${e.reward}（${e.place}）`).join(" / "))}</span>`
        : "";
      const linkHtml = sp.type !== "商会" && sp.type !== "迷宫"
        ? ` <a class="exp-ext-mini" href="${fwItemUrl(it.name)}" target="_blank" rel="noopener" title="在 fire-emblem-fw.site 搜索该素材全部产出点">原图搜此物↗</a>`
        : "";
      return `<div class="exp-item-row">
        <span class="exp-tier t-${U.esc(it.tier)}">${U.esc(it.tier)}</span>
        <b>${U.esc(it.name)}</b>
        ${it.tag ? `<span class="cat-pill">${U.esc(it.tag)}</span>` : ""}
        ${it.reason ? `<span class="hint">${U.esc(it.reason)}</span>` : ""}
        ${exHtml}${linkHtml}
      </div>`;
    }).join("");

    return `<div class="exp-detail active">
      <div class="exp-det-head">
        <span class="exp-rank-big t-${U.esc(sp.priority)}">#${sp.rank}</span>
        <span class="exp-tier t-${U.esc(sp.priority)}">${U.esc(sp.priority)}</span>
        <span class="cat-pill">${U.esc(sp.type)}</span>
        <h3>${U.esc(sp.name)}</h3>
        <span class="hint">${U.esc(sp.region || "")}${sp.nearestStation ? ` · 最近驿站：<b>${U.esc(sp.nearestStation)}</b>` : ""}${sp.lv ? ` · 推荐 Lv${sp.lv}` : ""}</span>
        <span class="r">
          <label class="chk"><input type="checkbox" data-exp-visit="${U.esc(sp.id)}"${visited ? " checked" : ""}> 已采集</label>
          <a class="btn" href="${U.esc(sp.fwMapUrl)}" target="_blank" rel="noopener">在 fire-emblem-fw.site 定位 ↗</a>
          <button type="button" class="btn ghost" data-exp-focus="${U.esc(sp.id)}">地图居中</button>
        </span>
      </div>
      ${sp.desc ? `<p class="hint" style="margin:4px 0 6px">${U.esc(sp.desc)}</p>` : ""}
      <div class="exp-items-list">${itemsHtml}</div>
    </div>`;
  }

  function renderBarterBoard(bs, query) {
    if (!bs || !bs.entries || !bs.entries.length) return "";
    const lackMats = (bs.materials || []).filter(m => m.hasShortage);
    const curQ = String(query || "").trim();
    const matBtns = lackMats.map(m => {
      const isP0 = m.shortageTier === "P0";
      const lackN = isP0 ? m.lackP0 : m.lackP01;
      const on = curQ === m.material;
      const cls = isP0 ? "t-P0" : "t-P1";
      return `<button type="button" class="pill${on ? " on" : ""}" data-exp-mat="${U.esc(m.material)}" title="${U.esc(m.reason)}">
        <span class="exp-tier ${cls}">${U.esc(m.shortageTier)}</span> ${U.esc(m.material)} <b>缺${lackN}</b><small style="opacity:.8">（${m.dietrichSpots.length}处）</small>
      </button>`;
    }).join("");

    const changedList = (bs.entries || []).filter(e => e.changed);
    const changedText = changedList.map(e =>
      `<b>${U.esc(e.item)}</b>（${U.esc(e.changeReason)}）`
    ).join(" · ");

    const rows = (bs.entries || []).map(e => {
      const pCls = e.done ? "" : `t-${U.esc(e.priority)}`;
      const wBadge = e.weaponTier ? `<span class="sk-tier tier-${U.esc(e.weaponTier === "SS" ? "S" : e.weaponTier)}">${U.esc(e.weaponTier)}</span> ` : "";
      const chgBadge = e.changed ? `<span class="cat-pill" style="background:#fef3c7;color:#92400e">${U.esc(e.origPriority)}→${U.esc(e.priority)}</span>` : "";
      const costStr = (e.cost || []).map(c => `${c.mat}×${c.qty}（有${c.have}）`).join("；");
      return `<tr class="${e.done ? "exp-row vis" : ""}">
        <td>${e.done ? `<span class="cat-pill">已换</span>` : `<span class="exp-tier ${pCls}">${U.esc(e.priority)}</span>`} ${chgBadge}</td>
        <td>${wBadge}<b>${U.esc(e.item)}</b> <span class="hint">${U.esc(e.type)}</span></td>
        <td>${U.esc(e.place)}</td>
        <td>${U.esc(costStr)}</td>
        <td><b>${U.esc(e.lackText)}</b></td>
        <td class="hint">${U.esc(e.note)}</td>
      </tr>`;
    }).join("");

    const cnt = bs.counts || {};
    return `<section class="card" style="margin-top:10px">
      <div class="ch"><div class="ct">
        <h3>📋 旺达尔商会置换优先级（按 PR #31 武器榜 SS/S→P0 重整 · ${U.esc(bs.snapshotDate || "")} 库存）</h3>
        <span class="r">
          <span class="exp-tier t-P0">P0×${cnt.P0 || 0}</span>
          <span class="exp-tier t-P1">P1×${cnt.P1 || 0}</span>
          <span class="exp-tier t-P2">P2×${cnt.P2 || 0}</span>
          <span class="cat-pill">已换 ${cnt.done || 0}</span>
          ${bs.sheetUrl ? `<a class="btn ghost" href="${U.esc(bs.sheetUrl)}" target="_blank" rel="noopener">原 Google Sheet ↗</a>` : ""}
        </span>
      </div></div>
      <div class="sec">
        ${changedText ? `<p class="hint" style="margin:0 0 8px">🔄 <b>本次按 PR #31 调整：</b>${changedText}；已换完的 <b>巨人戒指 / 必圣宝珠</b> 素材（辉光鱼/赤金拜/红烁）及库存已够的 <b>太阳果 / 金鳟</b> 自动移出地图 P0。</p>` : ""}
        <div class="sk-filter-row" style="margin-top:0">
          <span class="sk-flbl">缺口直达</span>
          <div class="pills">
            ${matBtns}
            ${curQ ? `<button type="button" class="btn ghost" data-exp-mat="">清除素材聚焦</button>` : ""}
          </div>
        </div>
        <details class="more" style="margin-top:8px">
          <summary>展开完整 29 项商会置换重整表（含武器评级、实测库存与缺口）</summary>
          <div class="scroll" style="margin-top:8px">
            <table class="exp-tbl">
              <thead><tr><th>新优先级</th><th>道具（PR#31评级）</th><th>地点</th><th>配方（有/需）</th><th>缺口状态</th><th>理由与来源</th></tr></thead>
              <tbody>${rows}</tbody>
            </table>
          </div>
        </details>
      </div>
    </section>`;
  }

  function renderExploreView(data, state) {
    if (!data) return `<p class="lede">探索规划数据加载中…</p>`;
    const routeKey = state.exploreRoute || data.defaultRoute || "dietrich";
    const routeObj = (data.routes && data.routes[routeKey]) || Object.values(data.routes || {})[0];
    if (!routeObj) return `<p class="lede">未找到探索路线数据。</p>`;

    const visitedMap = state.exploreVisited || {};
    const priorities = state.explorePriorities || ["P0"];
    const types = state.exploreTypes || ["矿石", "道具", "鱼", "蔬菜"];
    const query = state.exploreQuery || "";
    const hideVisited = !!state.exploreHideVisited;
    const onlyBarterLack = !!state.exploreOnlyBarterLack;
    const showLabels = state.exploreShowLabels !== false;
    const showStations = state.exploreShowStations !== false;
    const showArrows = !!state.exploreShowArrows;

    const allSpots = routeObj.spots || [];
    const filtered = EL.filterExploreSpots(allSpots, {
      priorities,
      types,
      query,
      hideVisited,
      onlyBarterLack,
      visitedMap,
    });
    const sum = EL.summarizeExplore(filtered, visitedMap);
    const routeSum = routeObj.summary || {};

    const selectedSpot = filtered.find(s => s.id === state.exploreSelectedId)
      || allSpots.find(s => s.id === state.exploreSelectedId)
      || filtered[0]
      || null;
    const selId = selectedSpot ? selectedSpot.id : "";

    const vb = Array.isArray(state.exploreViewBox) && state.exploreViewBox.length === 4
      ? state.exploreViewBox
      : (data.defaultViewBox || [210, 230, 2900, 2100]);

    // 1) 路线切换胶囊
    const routeBtns = (data.routeOrder || Object.keys(data.routes || {})).map(rk => {
      const r = data.routes[rk];
      if (!r) return "";
      const cnt = r.summary ? r.summary.totalSpots : 0;
      return `<button type="button" class="pill${rk === routeKey ? " on" : ""}" data-exp-route="${U.esc(rk)}">${U.esc(r.name)}（${cnt}）</button>`;
    }).join("");

    // 2) 快捷场景预设
    const presetBtns = PRESETS.map(pr => {
      const active =
        !!pr.onlyBarterLack === onlyBarterLack &&
        pr.priorities.length === priorities.length &&
        pr.priorities.every(x => priorities.includes(x)) &&
        pr.types.length === types.length &&
        pr.types.every(x => types.includes(x));
      return `<button type="button" class="pill${active ? " on" : ""}" data-exp-preset="${U.esc(pr.id)}">${U.esc(pr.label)}</button>`;
    }).join("");

    // 3) 优先级 Checkbox
    const tierChecks = (data.tiers || []).map(t => {
      const checked = priorities.includes(t.key);
      const cnt = (routeSum.tierCounts && routeSum.tierCounts[t.key]) || 0;
      return `<label class="skill-cb exp-cb-${U.esc(t.key)}${checked ? " on" : ""}" title="${U.esc(t.desc)}">
        <input type="checkbox" data-exp-prio="${U.esc(t.key)}"${checked ? " checked" : ""}>
        <span>${U.esc(t.label)}</span><small>${cnt}</small>
      </label>`;
    }).join("");

    // 4) 点位类型 Checkbox
    const typeChecks = (data.pinTypes || []).map(tp => {
      const checked = types.includes(tp);
      const cnt = (routeSum.typeCounts && routeSum.typeCounts[tp]) || 0;
      return `<label class="skill-cb${checked ? " on" : ""}">
        <input type="checkbox" data-exp-type="${U.esc(tp)}"${checked ? " checked" : ""}>
        <span>${U.esc(tp)}</span><small>${cnt}</small>
      </label>`;
    }).join("");

    // 5) SVG 图层：箭头 + 据点参照 + 驿站 + 采集点位（P2 在下，P1 在中，P0 与选中点在最顶层！）
    const arrowsSvg = showArrows
      ? (data.arrows || []).map(a =>
          `<line x1="${a[0]}" y1="${a[1]}" x2="${a[2]}" y2="${a[3]}" stroke="#3a2608" stroke-width="8" stroke-opacity="0.45"/>` +
          `<line x1="${a[0]}" y1="${a[1]}" x2="${a[2]}" y2="${a[3]}" stroke="#fde047" stroke-width="4" stroke-dasharray="14 10" marker-end="url(#expArrHead)"/>`
        ).join("")
      : "";

    const hubsSvg = (routeObj.hubs || []).map(h =>
      `<g class="exp-hub" transform="translate(${h.x},${h.y})" pointer-events="none">
        <circle r="10" fill="#ffffff" stroke="#0f172a" stroke-width="3.5"/>
        <text y="-16" text-anchor="middle" fill="#ffffff" stroke="#0f172a" stroke-width="5" paint-order="stroke" font-size="19" font-weight="800">${U.esc(h.name)}</text>
      </g>`
    ).join("");

    const stationsSvg = showStations
      ? (routeObj.stations || []).map(st =>
          `<g class="exp-stn" transform="translate(${st.x},${st.y})" pointer-events="none">
            <rect x="-15" y="-15" width="30" height="30" rx="6" fill="#0f766e" stroke="#ffffff" stroke-width="3"/>
            <text y="6" text-anchor="middle" fill="#ffffff" font-size="17" font-weight="800">站</text>
            <text y="32" text-anchor="middle" fill="#ccfbf1" stroke="#0f172a" stroke-width="4.5" paint-order="stroke" font-size="15" font-weight="700">${U.esc(st.name)}</text>
          </g>`
        ).join("")
      : "";

    // 绘制顺序：P2 -> P1 -> P0 -> 选中点最顶层
    const drawOrder = [...filtered].sort((a, b) => {
      if (a.id === selId) return 1;
      if (b.id === selId) return -1;
      const tr = { P2: 0, P1: 1, P0: 2 };
      return (tr[a.priority] || 0) - (tr[b.priority] || 0) || (b.rank - a.rank);
    });
    const pinsSvg = drawOrder.map(sp => renderSpotPinSvg(sp, selId, !!visitedMap[sp.id], showLabels)).join("");

    // 6) 下方按优先级排序的探索路线清单表
    const tableRows = filtered.map(sp => {
      const vis = !!visitedMap[sp.id];
      const isSel = sp.id === selId;
      const chips = (sp.items || []).slice(0, 7).map(it => {
        const cls = it.tier === "P0" ? "t-P0" : (it.tier === "P1" ? "t-P1" : "t-P2");
        const ex = (it.exchanges || []).length ? `→${it.exchanges[0].reward}` : (it.tag ? `·${it.tag}` : "");
        return `<span class="exp-ichip ${cls}" title="${U.esc(it.reason || it.name)}">${U.esc(it.name)}${ex ? `<small>${U.esc(ex)}</small>` : ""}</span>`;
      }).join("");
      const moreCnt = (sp.items || []).length > 7 ? ` <span class="hint">+${sp.items.length - 7}</span>` : "";
      return `<tr class="exp-row${isSel ? " on" : ""}${vis ? " vis" : ""}" data-exp-row="${U.esc(sp.id)}">
        <td class="n"><b>#${sp.rank}</b></td>
        <td><span class="exp-tier t-${U.esc(sp.priority)}">${U.esc(sp.priority)}</span></td>
        <td>
          <b>${U.esc(sp.name)}</b>
          <div class="hint">${U.esc(sp.region || "")}${sp.nearestStation ? ` · 近 ${U.esc(sp.nearestStation)}` : ""}${sp.lv ? ` · 推荐 Lv${sp.lv}` : ""}</div>
        </td>
        <td><span class="cat-pill">${U.esc(sp.type)}</span></td>
        <td><div class="exp-chips">${chips}${moreCnt}</div></td>
        <td style="white-space:nowrap">
          <label class="chk"><input type="checkbox" data-exp-visit="${U.esc(sp.id)}"${vis ? " checked" : ""}> 已采</label>
        </td>
        <td style="white-space:nowrap">
          <button type="button" class="btn ghost" data-exp-focus="${U.esc(sp.id)}">地图标亮</button>
          <a class="btn ghost" href="${U.esc(sp.fwMapUrl)}" target="_blank" rel="noopener">原图↗</a>
        </td>
      </tr>`;
    }).join("");

    const extLinks = (data.externalMaps || []).map(m =>
      `<a class="btn ghost" href="${U.esc(m.url)}" target="_blank" rel="noopener">${U.esc(m.name)} ↗</a>`
    ).join(" ");

    const feedback = state.exploreFeedback
      ? `<div class="exp-toast">${U.esc(state.exploreFeedback)}</div>`
      : "";

    return `
      <p class="lede">按<b>采集物需求优先级（P0 必抢孤品 → P1 强力兑换&amp;锻造 → P2 常规食材）</b>直接在完整世界大地图上叠加<b>超大高显眼标号与常驻标签</b>，支持滚轮缩放/拖拽定位、勾选已采集，并可<b>一键导出 1664×1280 高清标记地图 PNG 图片 / 独立离线 HTML</b>，或复制同步代码写入 <code>fire-emblem-fw.site</code> 收集清单。</p>

      <section class="alerts exp-ctrl">
        <div class="sk-filter-row"><span class="sk-flbl">主角路线</span><div class="pills">${routeBtns}</div></div>
        <div class="sk-filter-row"><span class="sk-flbl">快捷方案</span><div class="pills">${presetBtns}</div></div>
        <div class="sk-filter-row"><span class="sk-flbl">优先级</span><div class="skill-cbs">${tierChecks}</div></div>
        <div class="sk-filter-row"><span class="sk-flbl">点位类型</span><div class="skill-cbs">${typeChecks}</div></div>
        <div class="toolbar" style="margin:6px 0 0">
          <input type="search" id="expSearch" data-exp-q value="${U.esc(query)}" placeholder="搜地名、素材（尤那魅 / 挪亚果 / 恩黎艾特 / 青津吉 / 亚尔玛梅托 / 奥利哈钢）或目标（雷电剑 / 伏力萨 / 屠马弓 / 指南书）…">
          <label class="chk"><input type="checkbox" data-exp-opt="onlyBarterLack"${onlyBarterLack ? " checked" : ""}> 只看商会实测缺口</label>
          <label class="chk"><input type="checkbox" data-exp-opt="labels"${showLabels ? " checked" : ""}> 常驻醒目标签</label>
          <label class="chk"><input type="checkbox" data-exp-opt="stations"${showStations ? " checked" : ""}> 驿站路标</label>
          <label class="chk"><input type="checkbox" data-exp-opt="arrows"${showArrows ? " checked" : ""}> 通行箭头</label>
          <label class="chk"><input type="checkbox" data-exp-opt="hideVisited"${hideVisited ? " checked" : ""}> 隐藏已采集</label>
          <span class="meta">当前地图显示 <b>${sum.total}</b> 处（🔴P0 ${sum.byTier.P0} · 🟠P1 ${sum.byTier.P1} · 🔵P2 ${sum.byTier.P2}｜已采 ${sum.visited}/${sum.total}）</span>
        </div>
        <div class="exp-actions">
          <button type="button" class="btn pri" data-exp-png>📥 下载高清标记地图 PNG</button>
          <button type="button" class="btn" data-exp-html>📄 下载独立标记地图 HTML</button>
          <button type="button" class="btn" data-exp-fwcopy>📋 复制 fire-emblem-fw.site 收集清单同步脚本</button>
          ${extLinks}
        </div>
        ${feedback}
      </section>

      ${renderBarterBoard(data.barterSummary, query)}

      <section class="exp-stage">
        <div class="exp-hud">
          <button type="button" class="btn" data-exp-zoom="in" title="放大">＋ 放大</button>
          <button type="button" class="btn" data-exp-zoom="out" title="缩小">－ 缩小</button>
          <button type="button" class="btn" data-exp-zoom="fit" title="自动缩放到当前筛选点位">🎯 适应筛选点</button>
          <button type="button" class="btn" data-exp-zoom="reset" title="重置完整大陆视野">🗺 重置视野</button>
          <span class="exp-hud-legend">
            <span><i class="dot p0"></i>P0 必抢孤品</span>
            <span><i class="dot p1"></i>P1 重点兑换/矿</span>
            <span><i class="dot p2"></i>P2 常规</span>
            <span><i class="dot dg"></i>◇ 迷宫宝箱</span>
            <span><i class="dot mer"></i>■ 旺达尔商会</span>
            <span><i class="dot stn"></i>站 驿站</span>
          </span>
        </div>
        <div class="exp-canvas-wrap" id="expCanvasWrap">
          <svg id="expMapSvg" class="exp-svg" viewBox="${vb.join(" ")}" preserveAspectRatio="xMidYMid meet" data-map-w="${data.mapWidth}" data-map-h="${data.mapHeight}">
            <defs>
              <marker id="expArrHead" viewBox="0 0 12 12" refX="10" refY="6" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
                <path d="M0,1 L12,6 L0,11 L3,6 Z" fill="#fde047" stroke="#3a2608" stroke-width="1"/>
              </marker>
            </defs>
            <image href="${U.esc(data.mapImage)}" x="0" y="0" width="${data.mapWidth}" height="${data.mapHeight}" preserveAspectRatio="none"/>
            <g class="exp-arrows">${arrowsSvg}</g>
            <g class="exp-hubs">${hubsSvg}</g>
            <g class="exp-stations">${stationsSvg}</g>
            <g class="exp-pins">${pinsSvg}</g>
          </svg>
        </div>
        ${renderSelectedCard(selectedSpot, !!(selectedSpot && visitedMap[selectedSpot.id]))}
      </section>

      <section class="card" style="margin-top:12px">
        <div class="ch"><div class="ct">
          <h3>${U.esc(routeObj.name)} · 按采集优先级排序清单（共 ${filtered.length} 处）</h3>
          <span class="r"><span class="hint">点击任意行可在上方地图立刻高亮定位 · 已采进度保存在当前浏览器</span></span>
        </div></div>
        <div class="sec">
          ${filtered.length ? `<div class="scroll"><table class="exp-tbl">
            <thead><tr><th>#</th><th>优先级</th><th>地点与最近驿站</th><th>类型</th><th>核心产出与兑换用途</th><th>进度</th><th>定位</th></tr></thead>
            <tbody>${tableRows}</tbody>
          </table></div>` : `<p class="hint">当前筛选条件没有命中点位，请勾选更多优先级或点位类型。</p>`}
        </div>
      </section>

      <section class="alerts" style="margin-top:12px">
        <p class="hint" style="margin:0;line-height:1.65"><b>说明：</b>${(data.notes || []).map(n => U.esc(n)).join("<br>")}</p>
      </section>
    `;
  }

  root.FE = root.FE || {};
  root.FE.views = root.FE.views || {};
  root.FE.views.renderExploreView = renderExploreView;
  root.FE.views.EXPLORE_PRESETS = PRESETS;
})(window);
