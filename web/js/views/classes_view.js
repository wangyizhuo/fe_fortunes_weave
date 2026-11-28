/* 职业图鉴视图：按阶级（基础 / 初级 / 中级 / 上级 / 最上级 / 神将）分组，支持可用技能 Checkbox 筛选 */
(function (root) {
  const U = root.FE.utils;
  const CL = root.FE.classesLogic;
  const LL = root.FE.linksLogic;

  function fmtGrowthCell(val, isSorted) {
    const cls = isSorted ? " cls-sort-td" : "";
    if (!val) return `<td class="n cls-z${cls}">—</td>`;
    if (val > 0) return `<td class="n cls-pos${cls}">+${val}</td>`;
    return `<td class="n cls-neg${cls}">${val}</td>`;
  }

  function fmtMinCell(val, isSorted, isTierMax, isFirst) {
    const sep = isFirst ? " cls-grp-sep" : "";
    const sc = isSorted ? " cls-sort-td" : "";
    if (!val || val <= 0) return `<td class="n cls-z${sep}${sc}">—</td>`;
    const hi = isTierMax ? " cls-min-hi" : "";
    return `<td class="n cls-min-val${sep}${sc}${hi}">${val}</td>`;
  }

  function renderClassesView(data, state, ctx) {
    const D = data || {
      classes: [],
      tierOrder: CL.TIER_ORDER,
      tiers: [],
      skillGroups: [],
      summary: { classCount: 0, tierCounts: {}, skillCounts: {} },
      sources: [],
    };
    const C = ctx || {};
    const reg = C.registry;
    const focusName = C.focusTarget ? (LL.resolveEntity(reg, "class", C.focusTarget) || C.focusTarget) : "";

    const allClasses = D.classes || [];
    const tierOrder = D.tierOrder || CL.TIER_ORDER;
    const skillGroups = D.skillGroups || [];
    const allSkills = skillGroups.flatMap(g => g.skills || []);
    const selectedTier = focusName ? "全部" : (state.classesTier || "全部");
    const selectedSkills = focusName ? [] : (state.classesSkills || []);
    const selectedStats = focusName ? [] : (state.classesStats || []);
    const matchMode = state.classesMatchMode === "any" ? "any" : "all";
    const query = focusName ? "" : (state.classesQuery || "");
    const sortKey = state.classesSortKey || "";
    const sortDir = state.classesSortDir === "asc" ? "asc" : "desc";
    const sortLabel = CL.sortLabelOf(sortKey);
    const statLabels = D.statLabels || CL.STAT_LABELS;

    const sumAll = CL.summarizeClasses(allClasses, allSkills);
    let filtered;
    if (focusName) {
      const exact = allClasses.filter(c => c.name === focusName);
      filtered = exact.length ? exact : CL.filterClasses(allClasses, { query: focusName });
    } else {
      filtered = CL.filterClasses(allClasses, {
        tier: selectedTier,
        selectedSkills,
        selectedStats,
        matchMode,
        query,
      });
    }
    const groups = CL.groupClassesByTier(filtered, tierOrder, { key: sortKey, dir: sortDir });
    const tierMetaMap = new Map((D.tiers || []).map(t => [t.tier, t]));

    const focusBanner = focusName
      ? `<div class="ent-focus-bar">
          <span>🎯 当前定位职业：<b>${U.esc(focusName)}</b>（链接已固定在地址栏，可直接收藏或分享）</span>
          <span class="ent-focus-acts">
            <a class="btn pri" href="#classes" data-cls-clear>显示全部职业</a>
            <button type="button" class="btn ghost" data-ent-back>← 返回上一页</button>
          </span>
        </div>`
      : "";

    // 1) 阶级快捷筛选按钮
    const tierChips = [
      ["全部", `全部阶级（${sumAll.total}）`],
      ...tierOrder
        .filter(t => (sumAll.tierCounts[t] || 0) > 0)
        .map(t => [t, `${t}（${sumAll.tierCounts[t]}）`]),
    ].map(([k, label]) =>
      `<button type="button" class="fchip" data-cls-tier="${U.esc(k)}" aria-pressed="${!focusName && selectedTier === k}">${U.esc(label)}</button>`
    ).join("");

    // 2) 可用技能 + 优势属性 Checkbox 筛选面板
    const skillGroupsHtml = skillGroups.map(g => `
      <div class="skill-group">
        <span class="skill-glab">${U.esc(g.label)}</span>
        <div class="skill-cbs">
          ${(g.skills || []).map(sk => {
            const checked = selectedSkills.includes(sk);
            const cnt = sumAll.skillCounts[sk] || 0;
            return `<label class="skill-cb${checked ? " on" : ""}">
              <input type="checkbox" data-cls-skill="${U.esc(sk)}"${checked ? " checked" : ""}>
              <span>${U.esc(sk)}</span><small>${cnt}</small>
            </label>`;
          }).join("")}
        </div>
      </div>
    `).join("");

    const statCheckboxesHtml = `
      <div class="skill-group">
        <span class="skill-glab">优势属性（成长率 + 职业常驻加成综合突出）</span>
        <div class="skill-cbs">
          ${statLabels.map(st => {
            const checked = selectedStats.includes(st);
            const cnt = (sumAll.advantageCounts && sumAll.advantageCounts[st]) || 0;
            return `<label class="skill-cb${checked ? " on" : ""}">
              <input type="checkbox" data-cls-stat="${U.esc(st)}"${checked ? " checked" : ""}>
              <span>${U.esc(st)}</span><small>${cnt}</small>
            </label>`;
          }).join("")}
        </div>
      </div>
    `;

    const sortHintHtml = sortLabel
      ? ` · 当前各阶段内排序：<b>${U.esc(sortLabel)} ${sortDir === "desc" ? "↓（从高到低）" : "↑（从低到高）"}</b>`
      : ` · 提示：点击下方表格的<b>职业保底</b>或<b>成长率</b>任意属性列头即可在各阶段内排序`;

    const modeHtml = `<div class="skill-ctrl">
      <div class="subtabs">
        <button type="button" class="fchip" data-cls-mode="all" aria-pressed="${matchMode === "all"}">同时满足（AND）</button>
        <button type="button" class="fchip" data-cls-mode="any" aria-pressed="${matchMode === "any"}">任一满足（OR）</button>
      </div>
      <span class="hint">当前匹配 <b>${filtered.length}</b> / ${sumAll.total} 个职业${
        selectedSkills.length
          ? ` · 已选技能：<b>${U.esc(selectedSkills.join(matchMode === "all" ? " + " : " / "))}</b>`
          : ""
      }${
        selectedStats.length
          ? ` · 已选优势属性：<b>${U.esc(selectedStats.join(matchMode === "all" ? " + " : " / "))}</b>`
          : ""
      }${sortHintHtml}</span>
      ${sortKey ? `<button type="button" class="btn ghost" data-cls-sort-reset>恢复默认排序</button>` : ""}
      ${focusName || selectedSkills.length || selectedStats.length || selectedTier !== "全部" || query || sortKey
        ? `<button type="button" class="btn" data-cls-clear>清空筛选</button>`
        : ""}
    </div>`;

    const renderSortTh = (key, label, extraCls = "") => {
      const active = sortKey === key;
      const arrow = active ? (sortDir === "desc" ? "▼" : "▲") : "⇅";
      const ariaSort = active ? (sortDir === "desc" ? "descending" : "ascending") : "none";
      return `<th class="n cls-sort-th${active ? " on" : ""}${extraCls ? " " + extraCls : ""}" aria-sort="${ariaSort}"><button type="button" class="cls-sort-btn" data-cls-sort="${U.esc(key)}" title="按${U.esc(CL.sortLabelOf(key))}在各阶段内排序">${U.esc(label)}<span class="cls-sort-ico">${arrow}</span></button></th>`;
    };

    // 3) 按阶级分组表格（排序严格限定在每个阶级分组内部，不跨阶级混排）
    const groupsHtml = groups.length ? groups.map(grp => {
      const meta = tierMetaMap.get(grp.tier);
      const expNote = meta && meta.masteryExp ? ` · 精通 EXP ${meta.masteryExp}` : "";

      // 计算本阶段内每项转职保底的最大值（>0 才高亮）
      const tierMinMax = {};
      for (const k of CL.STAT_KEYS) {
        let mx = 0;
        for (const c of grp.classes) {
          const v = Number((c.minStats || {})[k] || 0);
          if (v > mx) mx = v;
        }
        tierMinMax[k] = mx;
      }

      const rows = grp.classes.map(c => {
        const isFocused = focusName && c.name === focusName;
        const badges = [
          c.unitType ? `<span class="cat-pill">${U.esc(c.unitType)}</span>` : "",
          c.limit ? `<span class="tag warn">${U.esc(c.limit)}专用</span>` : "",
          c.move != null ? `<span class="cat-pill">移 ${c.move}</span>` : "",
        ].filter(Boolean).join(" ");

        const skillPills = (c.usableSkills || []).map(sk => {
          const hit = selectedSkills.includes(sk);
          return `<span class="sk-pill${hit ? " hit" : ""}">${U.esc(sk)}</span>`;
        }).join("");

        const advList = c.advantageStats || [];
        const weakList = c.disadvantageStats || [];
        const baseMap = c.baseStats || {};
        const growthMap = c.growth || {};
        const statTip = lbl => {
          const idx = CL.STAT_LABELS.indexOf(lbl);
          if (idx < 0) return "";
          const k = CL.STAT_KEYS[idx];
          const gv = growthMap[k] || 0;
          const bv = baseMap[k] || 0;
          return `${lbl}：成长 ${gv >= 0 ? "+" : ""}${gv}% · 职业加成 ${bv >= 0 ? "+" : ""}${bv}`;
        };
        const advPills = advList.length
          ? `<div class="sk-list">${advList.map(st => {
              const hit = selectedStats.includes(st);
              return `<span class="st-pill st-adv${hit ? " hit" : ""}" title="${U.esc(statTip(st))}">▲${U.esc(st)}</span>`;
            }).join("")}</div>`
          : `<span class="hint">均衡</span>`;
        const weakPills = weakList.length
          ? `<div class="sk-list" style="margin-top:3px">${weakList.map(st =>
              `<span class="st-pill st-weak" title="${U.esc(statTip(st))}">▼${U.esc(st)}</span>`
            ).join("")}</div>`
          : "";

        const g = c.growth || {};
        const growthCells = CL.STAT_KEYS.map(k => fmtGrowthCell(g[k], sortKey === `growth:${k}`)).join("");
        const hasGrowthLv = (c.growthLv || []).length > 0;
        const growthLvTip = c.growthLvNote || "随等级提升成长率";
        const growthLvBadge = hasGrowthLv
          ? `<br><span class="tag ok cls-lv-tag" title="${U.esc(growthLvTip)}">Lv35↑</span>`
          : "";

        const ms = c.minStats || {};
        const minTot = CL.minStatsTotal(ms);
        const minCells = CL.STAT_KEYS.map((k, idx) => {
          const v = Number(ms[k] || 0);
          return fmtMinCell(v, sortKey === `min:${k}`, v > 0 && v === tierMinMax[k] && grp.classes.length > 1, idx === 0);
        }).join("");

        const reqBits = [
          U.esc(c.requirement || "—"),
          c.skillExp ? `<br><small class="hint">技能EXP：${U.esc(c.skillExp)}</small>` : "",
          c.unlock ? `<br><small class="hint">解锁：${U.esc(c.unlock)}</small>` : "",
        ].join("");

        const skillBits = [
          (c.innate || []).length ? `<span>${LL.linkifyList(reg, "skill", c.innate, "、")}</span>` : `<span class="hint">—</span>`,
          c.mastery && c.mastery !== "—"
            ? `<br><small>精通：<b>${LL.renderEntityLink(reg, "skill", c.mastery)}</b>${c.masteryExp ? ` (EXP ${c.masteryExp})` : ""}</small>`
            : "",
          hasGrowthLv ? `<br><small class="hint">${U.esc(growthLvTip)}</small>` : "",
        ].join("");

        return `<tr class="${isFocused ? "ent-focused" : ""}" data-cls-name="${U.esc(c.name)}"${isFocused ? ' data-ent-focused="true"' : ""}>
          <td class="cls-name"><b>${LL.renderEntityLink(reg, "class", c.name, { className: "ent-self" })}</b><div class="cls-meta">${badges}</div></td>
          <td class="cls-skills"><div class="sk-list">${skillPills}</div></td>
          <td class="cls-prof">${advPills}${weakPills}</td>
          ${growthCells}
          <td class="n cls-gtot${sortKey === "growth:total" ? " cls-sort-td" : ""}"><b>${c.growthTotal ?? 0}</b>${growthLvBadge}</td>
          ${minCells}
          <td class="n cls-min-tot${sortKey === "min:total" ? " cls-sort-td" : ""}">${minTot > 0 ? `<b>${minTot}</b>` : `<span class="cls-z">—</span>`}</td>
          <td class="note cls-grp-sep cls-req">${reqBits}</td>
          <td class="note cls-innate">${skillBits}</td>
        </tr>`;
      }).join("");

      const growthHeaders = CL.STAT_KEYS.map((k, i) => renderSortTh(`growth:${k}`, CL.STAT_LABELS[i])).join("")
        + renderSortTh("growth:total", "合计");
      const minHeaders = CL.STAT_KEYS.map((k, i) => renderSortTh(`min:${k}`, CL.STAT_LABELS[i], i === 0 ? "cls-grp-sep" : "")).join("")
        + renderSortTh("min:total", "合计");

      return `<section class="alerts" data-cls-tier-sec="${U.esc(grp.tier)}">
        <h2>${U.esc(grp.tier)}职业（${grp.classes.length} 个${U.esc(expNote)}）${sortLabel ? `<small class="hint" style="margin-left:8px;font-weight:400">按 ${U.esc(sortLabel)} ${sortDir === "desc" ? "↓" : "↑"}</small>` : ""}</h2>
        <div class="scroll"><table class="cls-tbl">
          <tr>
            <th rowspan="2" class="cls-sticky-th">职业</th>
            <th rowspan="2">可用技能</th>
            <th rowspan="2">优势 / 劣势属性</th>
            <th colspan="10" class="grp">成长率补正（% · 点击排序）</th>
            <th colspan="10" class="grp cls-grp-sep">职业保底 / 转职保底（每属性一列 · 点击排序）</th>
            <th rowspan="2" class="cls-grp-sep">转职要求 / 技能 EXP</th>
            <th rowspan="2">固有特技 / 精通</th>
          </tr>
          <tr>
            ${growthHeaders}
            ${minHeaders}
          </tr>
          ${rows}
        </table></div>
      </section>`;
    }).join("") : `<section class="alerts"><p class="txt">没有符合当前阶级、技能或优势属性条件的职业，可尝试切到「任一满足（OR）」或清空筛选。</p></section>`;

    const sourcesList = (D.sources || []).map(s =>
      `<li><a href="${U.esc(s.url)}" target="_blank" rel="noopener noreferrer">${U.esc(s.name)}</a>（${U.esc(s.url)}）</li>`
    ).join("");

    return `<p class="lede">职业图鉴：整理全阶级职业的可用技能、<b>优势 / 劣势属性</b>、成长率补正（%）、<b>职业保底（转职保底，每属性一列）</b>、转职要求、固有特技与精通奖励。点击任意成长率或职业保底列头即可在<b>各自阶段（基础 / 初级 / 中级 / 上级 / 最上级 / 神将）内独立排序</b>；点击固有特技或精通技能可直接跳转 <a href="#skills" class="ent-link">技能图鉴</a>。</p>
      ${focusBanner}
      <div class="filterbar">
        <input type="search" id="clsQuery" data-cls-q placeholder="搜职业名、优势属性、特技、精通、转职要求，比如 重装、天翼、乘降术、流星" value="${U.esc(query)}" aria-label="搜索职业">
        <div class="fchips">${tierChips}</div>
      </div>
      <section class="alerts skill-panel">
        <h2>按可用技能与优势属性筛选职业（Checkbox 多选）</h2>
        ${skillGroupsHtml}
        ${statCheckboxesHtml}
        ${modeHtml}
      </section>
      ${groupsHtml}
      <details class="notes">
        <summary>数据来源与算法说明</summary>
        <ul>
          ${D.advantageAlgorithm ? `<li><b>优势 / 劣势属性算法</b>：${U.esc(D.advantageAlgorithm)}（悬停属性徽章可查看该项成长率补正与常驻职业加成）。</li>` : ""}
          ${sourcesList}
          <li><b>职业保底（转职保底 / minStats）</b>：转职瞬间若裸属性低于该职业底线，将永久补足至底线值（同阶段内每项属性最大值会加粗高亮；点击任意列头会在各阶段内独立按降序 → 升序 → 默认顺序切换）。</li>
          <li>「同时满足（AND）」适合找同时具备多种技能与优势属性的复合职业（如 重装术 + 优势「力、防」）；「任一满足（OR）」适合查看宽范围备选。</li>
        </ul>
      </details>`;
  }

  root.FE = root.FE || {};
  root.FE.views = root.FE.views || {};
  root.FE.views.renderClassesView = renderClassesView;
})(window);
