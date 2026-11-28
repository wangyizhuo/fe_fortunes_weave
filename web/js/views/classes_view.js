/* 职业图鉴视图：按阶级（基础 / 初级 / 中级 / 上级 / 最上级 / 神将）分组，支持可用技能 Checkbox 筛选 */
(function (root) {
  const U = root.FE.utils;
  const CL = root.FE.classesLogic;
  const LL = root.FE.linksLogic;

  function fmtGrowthCell(val) {
    if (!val) return `<td class="n cls-z">—</td>`;
    if (val > 0) return `<td class="n cls-pos">+${val}</td>`;
    return `<td class="n cls-neg">${val}</td>`;
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
    const groups = CL.groupClassesByTier(filtered, tierOrder);
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
      }</span>
      ${focusName || selectedSkills.length || selectedStats.length || selectedTier !== "全部" || query
        ? `<button type="button" class="btn" data-cls-clear>清空筛选</button>`
        : ""}
    </div>`;

    // 3) 按阶级分组表格
    const groupsHtml = groups.length ? groups.map(grp => {
      const meta = tierMetaMap.get(grp.tier);
      const expNote = meta && meta.masteryExp ? ` · 精通 EXP ${meta.masteryExp}` : "";
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
        const growthCells = CL.STAT_KEYS.map(k => fmtGrowthCell(g[k])).join("");
        const growthLvExtra = (c.growthLv || []).length
          ? `<br><small class="hint">${U.esc(c.growthLvNote || "随等级提升成长率")}</small>`
          : "";

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
        ].join("");

        return `<tr class="${isFocused ? "ent-focused" : ""}" data-cls-name="${U.esc(c.name)}"${isFocused ? ' data-ent-focused="true"' : ""}>
          <td class="cls-name"><b>${LL.renderEntityLink(reg, "class", c.name, { className: "ent-self" })}</b><div class="cls-meta">${badges}</div></td>
          <td class="cls-skills"><div class="sk-list">${skillPills}</div></td>
          <td class="cls-prof">${advPills}${weakPills}</td>
          ${growthCells}
          <td class="n"><b>${c.growthTotal ?? 0}</b>${growthLvExtra}</td>
          <td class="note cls-min">${(() => { const ms = CL.formatMinStats(c.minStats); return ms && ms !== "—" ? U.esc(ms) : `<span class="hint">无转职保底</span>`; })()}</td>
          <td class="note">${reqBits}</td>
          <td class="note">${skillBits}</td>
        </tr>`;
      }).join("");

      return `<section class="alerts">
        <h2>${U.esc(grp.tier)}职业（${grp.classes.length} 个${U.esc(expNote)}）</h2>
        <div class="scroll"><table class="cls-tbl">
          <tr>
            <th>职业</th>
            <th>可用技能</th>
            <th>优势 / 劣势属性</th>
            ${CL.STAT_LABELS.map(l => `<th class="n">${l}</th>`).join("")}
            <th class="n">合计</th>
            <th>转职保底</th>
            <th>转职要求 / 技能 EXP</th>
            <th>固有特技 / 精通</th>
          </tr>
          ${rows}
        </table></div>
      </section>`;
    }).join("") : `<section class="alerts"><p class="txt">没有符合当前阶级、技能或优势属性条件的职业，可尝试切到「任一满足（OR）」或清空筛选。</p></section>`;

    const sourcesList = (D.sources || []).map(s =>
      `<li><a href="${U.esc(s.url)}" target="_blank" rel="noopener noreferrer">${U.esc(s.name)}</a>（${U.esc(s.url)}）</li>`
    ).join("");

    return `<p class="lede">职业图鉴：整理全阶级职业的可用技能、<b>优势 / 劣势属性</b>、成长率补正（%）、转职保底、转职要求、固有特技与精通奖励。点击任意固有特技或精通技能可直接跳转 <a href="#skills" class="ent-link">技能图鉴</a>。</p>
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
          <li>转职保底（minStats）：转职瞬间若裸属性低于该职业底线，将永久补足至底线值（参考 yuphastemple.com 实测数据）。</li>
          <li>「同时满足（AND）」适合找同时具备多种技能与优势属性的复合职业（如 重装术 + 优势「力、防」）；「任一满足（OR）」适合查看宽范围备选。</li>
        </ul>
      </details>`;
  }

  root.FE = root.FE || {};
  root.FE.views = root.FE.views || {};
  root.FE.views.renderClassesView = renderClassesView;
})(window);
