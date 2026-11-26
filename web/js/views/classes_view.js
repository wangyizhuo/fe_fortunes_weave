/* 职业图鉴视图：按阶级（基础 / 初级 / 中级 / 上级 / 最上级 / 神将）分组，支持可用技能 Checkbox 筛选 */
(function (root) {
  const U = root.FE.utils;
  const CL = root.FE.classesLogic;

  function fmtGrowthCell(val) {
    if (!val) return `<td class="n cls-z">—</td>`;
    if (val > 0) return `<td class="n cls-pos">+${val}</td>`;
    return `<td class="n cls-neg">${val}</td>`;
  }

  function renderClassesView(data, state) {
    const D = data || {
      classes: [],
      tierOrder: CL.TIER_ORDER,
      tiers: [],
      skillGroups: [],
      summary: { classCount: 0, tierCounts: {}, skillCounts: {} },
      sources: [],
    };
    const allClasses = D.classes || [];
    const tierOrder = D.tierOrder || CL.TIER_ORDER;
    const skillGroups = D.skillGroups || [];
    const allSkills = skillGroups.flatMap(g => g.skills || []);
    const selectedTier = state.classesTier || "全部";
    const selectedSkills = state.classesSkills || [];
    const matchMode = state.classesMatchMode === "any" ? "any" : "all";
    const query = state.classesQuery || "";

    const sumAll = CL.summarizeClasses(allClasses, allSkills);
    const filtered = CL.filterClasses(allClasses, {
      tier: selectedTier,
      selectedSkills,
      matchMode,
      query,
    });
    const groups = CL.groupClassesByTier(filtered, tierOrder);
    const tierMetaMap = new Map((D.tiers || []).map(t => [t.tier, t]));

    // 1) 阶级快捷筛选按钮
    const tierChips = [
      ["全部", `全部阶级（${sumAll.total}）`],
      ...tierOrder
        .filter(t => (sumAll.tierCounts[t] || 0) > 0)
        .map(t => [t, `${t}（${sumAll.tierCounts[t]}）`]),
    ].map(([k, label]) =>
      `<button type="button" class="fchip" data-cls-tier="${U.esc(k)}" aria-pressed="${selectedTier === k}">${U.esc(label)}</button>`
    ).join("");

    // 2) 可用技能 Checkbox 筛选面板
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

    const modeHtml = `<div class="skill-ctrl">
      <div class="subtabs">
        <button type="button" class="fchip" data-cls-mode="all" aria-pressed="${matchMode === "all"}">同时可用（AND）</button>
        <button type="button" class="fchip" data-cls-mode="any" aria-pressed="${matchMode === "any"}">任一可用（OR）</button>
      </div>
      <span class="hint">当前匹配 <b>${filtered.length}</b> / ${sumAll.total} 个职业${
        selectedSkills.length
          ? ` · 已选技能：<b>${U.esc(selectedSkills.join(matchMode === "all" ? " + " : " / "))}</b>`
          : ""
      }</span>
      ${selectedSkills.length || selectedTier !== "全部" || query
        ? `<button type="button" class="btn" data-cls-clear>清空筛选</button>`
        : ""}
    </div>`;

    // 3) 按阶级分组表格
    const groupsHtml = groups.length ? groups.map(grp => {
      const meta = tierMetaMap.get(grp.tier);
      const expNote = meta && meta.masteryExp ? ` · 精通 EXP ${meta.masteryExp}` : "";
      const rows = grp.classes.map(c => {
        const badges = [
          c.unitType ? `<span class="cat-pill">${U.esc(c.unitType)}</span>` : "",
          c.limit ? `<span class="tag warn">${U.esc(c.limit)}专用</span>` : "",
          c.move != null ? `<span class="cat-pill">移 ${c.move}</span>` : "",
        ].filter(Boolean).join(" ");

        const skillPills = (c.usableSkills || []).map(sk => {
          const hit = selectedSkills.includes(sk);
          return `<span class="sk-pill${hit ? " hit" : ""}">${U.esc(sk)}</span>`;
        }).join("");

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
          (c.innate || []).length ? `<span>${U.esc(c.innate.join("、"))}</span>` : `<span class="hint">—</span>`,
          c.mastery && c.mastery !== "—"
            ? `<br><small>精通：<b>${U.esc(c.mastery)}</b>${c.masteryExp ? ` (EXP ${c.masteryExp})` : ""}</small>`
            : "",
        ].join("");

        return `<tr>
          <td class="cls-name"><b>${U.esc(c.name)}</b><div class="cls-meta">${badges}</div></td>
          <td class="cls-skills"><div class="sk-list">${skillPills}</div></td>
          ${growthCells}
          <td class="n"><b>${c.growthTotal ?? 0}</b>${growthLvExtra}</td>
          <td class="note cls-min">${U.esc(CL.formatMinStats(c.minStats))}</td>
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
            ${CL.STAT_LABELS.map(l => `<th class="n">${l}</th>`).join("")}
            <th class="n">合计</th>
            <th>转职保底</th>
            <th>转职要求 / 技能 EXP</th>
            <th>固有特技 / 精通</th>
          </tr>
          ${rows}
        </table></div>
      </section>`;
    }).join("") : `<section class="alerts"><p class="txt">没有符合当前阶级与可用技能条件的职业，可尝试切到「任一可用（OR）」或清空筛选。</p></section>`;

    const sourcesList = (D.sources || []).map(s =>
      `<li><a href="${U.esc(s.url)}" target="_blank" rel="noopener noreferrer">${U.esc(s.name)}</a>（${U.esc(s.url)}）</li>`
    ).join("");

    return `<p class="lede">职业图鉴：整理全阶级职业的可用技能、成长率补正（%）、转职保底、转职要求、固有特技与精通奖励。勾选下方技能 Checkbox 可精准反查可装备该技能组合的职业。</p>
      <div class="filterbar">
        <input type="search" id="clsQuery" data-cls-q placeholder="搜职业名、特技、精通、转职要求，比如 重装、天翼、乘降术、流星" value="${U.esc(query)}" aria-label="搜索职业">
        <div class="fchips">${tierChips}</div>
      </div>
      <section class="alerts skill-panel">
        <h2>按可用技能筛选职业（Checkbox 多选）</h2>
        ${skillGroupsHtml}
        ${modeHtml}
      </section>
      ${groupsHtml}
      <details class="notes">
        <summary>数据来源与字段说明</summary>
        <ul>
          ${sourcesList}
          <li>转职保底（minStats）：转职瞬间若裸属性低于该职业底线，将永久补足至底线值（参考 yuphastemple.com 实测数据）。</li>
          <li>「同时可用（AND）」适合找同时能用多种技能的复合职业（如 剑术 + 马术、黑魔术 + 飞行术）；「任一可用（OR）」适合查看某几类技能的全部可选职业。</li>
        </ul>
      </details>`;
  }

  root.FE = root.FE || {};
  root.FE.views = root.FE.views || {};
  root.FE.views.renderClassesView = renderClassesView;
})(window);
