/* 技能图鉴视图：技能总表（评级 / 通用与特有 / 职业与角色来源） + 角色 12 项熟练度矩阵速览 */
(function (root) {
  const U = root.FE.utils;
  const SL = root.FE.skillsLogic;

  const SCOPE_BTNS = [
    ["全部", "全部来源"],
    ["unique", "角色特有（唯一）"],
    ["rare", "稀有习得（≤5人）"],
    ["common_class", "全员通用（职业获取）"],
    ["common_learn", "角色表限定（>5人熟练度）"],
  ];

  function renderParams(p) {
    if (!p) return "";
    const parts = [];
    if (p.cost != null) parts.push(`消耗 ${p.cost}`);
    if (p.mt != null) parts.push(`威力 ${p.mt}`);
    if (p.hit != null) parts.push(`命中 ${p.hit}`);
    if (p.crit != null) parts.push(`必杀 ${p.crit}`);
    if (p.rng != null) parts.push(`射程 ${p.rng}`);
    if (p.uses != null) parts.push(`回数 ${p.uses}`);
    if (p.wt != null) parts.push(`重 ${p.wt}`);
    if (!parts.length) return "";
    return `<div class="sk-params">${parts.map(x => `<span>${U.esc(x)}</span>`).join("")}</div>`;
  }

  function renderScopePill(sk) {
    const cls =
      sk.scope === "unique" ? "sc-unique"
      : sk.scope === "rare" ? "sc-rare"
      : sk.scope === "common_class" ? "sc-cls"
      : "sc-learn";
    return `<span class="sk-scope ${cls}">${U.esc(sk.scopeLabel)}</span>`;
  }

  function renderOwners(sk) {
    const list = sk.charSources || [];
    if (!list.length) return "";
    const limit = 12;
    const renderChip = cs =>
      `<span class="sk-owner${cs.recruited ? " rec" : ""}" title="${U.esc(cs.how)}">${U.esc(U.shortName(cs.char))}<small>${U.esc(cs.rank || (cs.lv ? "Lv" + cs.lv : cs.how))}</small></span>`;
    const head = list.slice(0, limit).map(renderChip).join("");
    if (list.length <= limit) {
      return `<div class="sk-owners"><span class="sk-lbl">习得角色（${sk.ownerCount}）</span>${head}</div>`;
    }
    const rest = list.slice(limit).map(renderChip).join("");
    return `<div class="sk-owners"><span class="sk-lbl">习得角色（${sk.ownerCount}）</span>${head}
      <details class="sk-more"><summary>展开其余 ${list.length - limit} 人</summary><div class="sk-more-box">${rest}</div></details></div>`;
  }

  function renderClassSources(sk) {
    const list = sk.classSources || [];
    if (!list.length) return "";
    const chips = list.map(cs =>
      `<span class="sk-cls-chip">${U.esc(cs.cls)}<small>${U.esc(cs.tier)}·${U.esc(cs.how)}${cs.masteryExp ? " " + cs.masteryExp + "EXP" : ""}</small></span>`
    ).join("");
    return `<div class="sk-owners"><span class="sk-lbl">职业获取（全员通用）</span>${chips}</div>`;
  }

  function renderUnitTypeBadges(sk) {
    const uts = sk.unitTypes || [];
    if (!uts.length) return "";
    return uts.map(u => {
      const label = u === "仅限本职业" ? "限 本职业" : `限 ${u}`;
      return `<span class="sk-ut ut-${U.esc(u)}" title="仅在自身为「${U.esc(u)}」时生效">${U.esc(label)}</span>`;
    }).join(" ");
  }

  function renderSkillsTable(data, state) {
    const selectedUnitTypes = state.skillsUnitTypes || [];
    const filtered = SL.filterSkills(data.skills || [], {
      query: state.skillsQuery,
      rating: state.skillsRating,
      scope: state.skillsScope,
      category: state.skillsCategory,
      discipline: state.skillsDiscipline,
      unitTypes: selectedUnitTypes,
      onlyRecruited: state.skillsOnlyRecruited,
    });
    const sum = SL.summarizeSkills(filtered);
    const hasFilter =
      state.skillsRating !== "全部" ||
      state.skillsScope !== "全部" ||
      state.skillsCategory !== "全部" ||
      state.skillsDiscipline !== "全部" ||
      selectedUnitTypes.length > 0 ||
      state.skillsOnlyRecruited ||
      !!(state.skillsQuery || "").trim();

    const ratingBtns = [["全部", `全部 (${(data.skills || []).length})`], ...(data.tiers || []).map(t => [t.key, `${t.key} 级 (${data.summary.tierCounts[t.key] || 0})`])]
      .map(([k, label]) => `<button type="button" class="pill${state.skillsRating === k ? " on" : ""}${k !== "全部" ? " tier-" + k : ""}" data-sk-rating="${U.esc(k)}">${U.esc(label)}</button>`)
      .join("");

    const scopeBtns = SCOPE_BTNS
      .map(([k, label]) => `<button type="button" class="pill${state.skillsScope === k ? " on" : ""}" data-sk-scope="${U.esc(k)}">${U.esc(label)}</button>`)
      .join("");

    const catBtns = ["全部", ...(data.categories || [])]
      .map(k => `<button type="button" class="pill${state.skillsCategory === k ? " on" : ""}" data-sk-cat="${U.esc(k)}">${U.esc(k)}</button>`)
      .join("");

    const unitTypeOrder = data.unitTypes || SL.UNIT_TYPE_ORDER;
    const utCounts = (data.summary && data.summary.unitTypeCounts) || {};
    const utChecks = unitTypeOrder.map(ut => {
      const checked = selectedUnitTypes.includes(ut);
      const label = ut === "无限制" ? "无兵种限制（全兵种）" : ut;
      const cnt = utCounts[ut] != null ? utCounts[ut] : 0;
      return `<label class="skill-cb${checked ? " on" : ""}">
        <input type="checkbox" data-sk-ut="${U.esc(ut)}"${checked ? " checked" : ""}>
        <span>${U.esc(label)}</span><small>${cnt}</small>
      </label>`;
    }).join("");

    const discOpts = ["全部", ...(data.disciplines || []), "职业", "角色"]
      .map(d => `<option value="${U.esc(d)}"${state.skillsDiscipline === d ? " selected" : ""}>熟练度：${U.esc(d)}</option>`)
      .join("");

    // 默认单页展示前 120 条，避免 584 张卡片一次撑大 DOM；可一键展开全部或通过筛选精确查找
    const showLimit = state.skillsShowAll ? filtered.length : 120;
    const shown = filtered.slice(0, showLimit);

    const rows = shown.map(sk => `
      <tr class="sk-row tier-row-${U.esc(sk.rating)}">
        <td class="sk-c-tier"><span class="sk-tier tier-${U.esc(sk.rating)}">${U.esc(sk.rating)}</span></td>
        <td class="sk-c-name">
          <div class="sk-name-line"><b class="sk-name">${U.esc(sk.name)}</b>${sk.enName ? ` <span class="sk-en">${U.esc(sk.enName)}</span>` : ""}</div>
          <div class="sk-meta-line"><span class="cat-pill">${U.esc(sk.category)}</span>${sk.discipline && sk.discipline !== "角色" && sk.discipline !== "职业" ? ` <span class="cat-pill">${U.esc(sk.discipline)}</span>` : ""}${renderUnitTypeBadges(sk) ? ` ${renderUnitTypeBadges(sk)}` : ""}</div>
        </td>
        <td class="sk-c-scope">${renderScopePill(sk)}</td>
        <td class="sk-c-eff">
          ${renderParams(sk.params)}
          ${sk.effect ? `<div class="sk-eff">${U.esc(sk.effect)}</div>` : ""}
          ${sk.review ? `<div class="sk-review"><b>简评：</b>${U.esc(sk.review)}</div>` : ""}
        </td>
        <td class="sk-c-src">
          ${renderClassSources(sk)}
          ${renderOwners(sk)}
        </td>
      </tr>
    `).join("");

    const moreBtn = filtered.length > showLimit
      ? `<div style="text-align:center;margin:14px 0"><button type="button" class="btn" data-sk-all>展开剩余 ${filtered.length - showLimit} 条（共 ${filtered.length} 条）</button></div>`
      : "";

    return `
      <div class="toolbar">
        <input type="search" id="skSearch" data-sk-q value="${U.esc(state.skillsQuery || "")}" placeholder="搜技能中/英文、效果、职业（如 重装步兵）或角色（如 迪托利希 / 传送 / 体格）…">
        <select data-sk-disc class="sk-select">${discOpts}</select>
        <label class="chk"><input type="checkbox" data-sk-rec${state.skillsOnlyRecruited ? " checked" : ""}> 只看已招 9 人可获取（含全员通用职业）</label>
        ${hasFilter ? `<button type="button" class="btn ghost" data-sk-clear>清空筛选</button>` : ""}
        <span class="meta">命中 <b>${sum.total}</b> 项（S ${sum.byRating.S} · A ${sum.byRating.A} · B ${sum.byRating.B} · C ${sum.byRating.C}｜特有 ${sum.byScope.unique} · 稀有 ${sum.byScope.rare} · 职业通用 ${sum.byScope.common_class} · 角色表限定 ${sum.byScope.common_learn}）</span>
      </div>
      <div class="sk-filter-row"><span class="sk-flbl">评级</span><div class="pills">${ratingBtns}</div></div>
      <div class="sk-filter-row"><span class="sk-flbl">获取范围</span><div class="pills">${scopeBtns}</div></div>
      <div class="sk-filter-row"><span class="sk-flbl">分类</span><div class="pills">${catBtns}</div></div>
      <div class="sk-filter-row"><span class="sk-flbl">生效兵种</span><div class="skill-cbs">${utChecks}</div></div>
      <div class="sk-callout"><b>获取范围 &amp; 生效兵种说明：</b>「<b>全员通用（职业获取）</b>」指任意角色转职该职业即可获得的职业固有/精通技能；「<b>角色表限定（N/63 人熟练度）</b>」指仅写在对应角色个人熟练度习得表里的技能（如 <b>体格 / 体格+</b> 不在习得名单内练满重装术也学不到）。<b>生效兵种</b>按自身兵种条件标注（如 <code>[Armored]</code>=重装、<code>[Infantry]</code>=步兵、<code>[Cavalry]/【骑兵】</code>=骑兵、<code>[Flying]</code>=飞行；<b>体格 / 体格+ / 大防御</b> 虽属重装术习得但<b>无兵种限制</b>，任意职业都能生效；「对重装特攻」等对敌特攻也不计入自身兵种限制）。</div>
      ${shown.length ? `<div class="scroll"><table class="sk-tbl"><thead><tr><th>评级</th><th>技能名</th><th>获取范围</th><th>效果与数值</th><th>习得途径（职业 / 角色）</th></tr></thead><tbody>${rows}</tbody></table></div>${moreBtn}` : `<section class="alerts"><p class="txt">没有符合条件的技能，试试放宽筛选或清空搜索词。</p></section>`}
    `;
  }

  function renderCharsShowcase(data, state) {
    const group = state.skillsCharGroup || "recruited";
    const ctier = state.skillsCharTier || "全部";
    const allChars = data.characters || [];
    const chars = SL.filterSkillChars(allChars, {
      query: state.skillsQuery,
      group,
      strengthTier: ctier,
    });
    const recCnt = allChars.filter(c => c.recruited).length;
    const dietCnt = allChars.filter(c => c.dietrichRoute).length;
    const allCnt = allChars.length;
    const sc = (data.summary && data.summary.strengthCounts) || {};

    const grpBtns = [
      ["recruited", `我方已招（${recCnt}）`],
      ["dietrich", `迪线可入队（${dietCnt}）`],
      ["all", `全角色（${allCnt}）`],
    ].map(([k, label]) => `<button type="button" class="pill${group === k ? " on" : ""}" data-sk-cgrp="${k}">${U.esc(label)}</button>`).join("");

    const tierKeys = ["全部", "SS", "S", "A", "B", "C", "D"];
    const tierBtns = tierKeys.map(k => {
      const label = k === "全部" ? `全强度（${allCnt}）` : `${k}（${sc[k] || 0}）`;
      return `<button type="button" class="pill${ctier === k ? " on" : ""}${k !== "全部" ? " ctier-" + k : ""}" data-sk-ctier="${k}">${U.esc(label)}</button>`;
    }).join("");

    const scaleLegend = (data.characterTierScale || []).map(s =>
      `<span class="sk-leg"><span class="ctier ctier-${U.esc(s.tier)}">${U.esc(s.tier)}</span> <small>${U.esc(s.pserMap)} · 基准 ${U.esc(s.defaultP)}</small></span>`
    ).join("");

    const discs = data.disciplines || [];
    const cards = chars.map(ch => {
      const matRows = discs.filter(d => (ch.matrix[d] || []).length).map(d => {
        const pills = (ch.matrix[d] || []).map(it => {
          const uniq = it.scope === "unique" ? `<i class="sk-star" title="角色唯一特有">★</i>` : "";
          return `<span class="sk-mpill tier-${U.esc(it.rating)}" title="${U.esc(it.category)} · ${U.esc(it.rating)}级">${U.esc(it.name)}<small>${U.esc(it.rank || "")}</small>${uniq}</span>`;
        }).join("");
        return `<div class="sk-mrow"><span class="sk-mdisc">${U.esc(d)}</span><div class="sk-mpills">${pills}</div></div>`;
      }).join("");

      const psHtml = ch.personalSkill
        ? `<div class="sk-ch-line"><b>个人特技：</b><span class="sk-mpill tier-A">${U.esc(ch.personalSkill.name)}</span> <span class="hint">${U.esc(ch.personalSkill.text)}</span></div>`
        : "";
      const lvHtml = (ch.lvSkills || []).length
        ? `<div class="sk-ch-line"><b>等级特技：</b>${ch.lvSkills.map(x => `<span class="sk-mpill tier-B">${U.esc(x.name)}<small>${U.esc(x.lv ? "Lv" + x.lv : (x.cond || ""))}</small></span>${x.effect ? ` <span class="hint">${U.esc(x.effect)}</span>` : ""}`).join(" ")}</div>`
        : "";
      const bmHtml = (ch.bloodMarks || []).length
        ? `<div class="sk-ch-line"><b>血印：</b>${ch.bloodMarks.map(x => `<span class="cat-pill">${U.esc(x.name)}</span> <span class="hint">${U.esc(x.text)}</span>`).join(" ")}</div>`
        : "";

      const prioTag = ch.dietrichPriority
        ? `<span class="rec ${ch.dietrichPriority === "P0" ? "r1" : ch.dietrichPriority === "P1" ? "r2" : "r3"}" title="${U.esc(ch.priorityNote || "")}">迪线 ${U.esc(ch.dietrichPriority)}</span>`
        : (ch.defaultPriority ? `<span class="cat-pill" title="综合强度基准优先级（各路线可按培养需求调整）">基准 ${U.esc(ch.defaultPriority)}</span>` : "");

      return `<article class="card sk-ch-card${ch.recruited ? " is-rec" : ""}">
        <div class="ch"><div class="ct">
          ${ch.strengthTier ? `<span class="ctier ctier-${U.esc(ch.strengthTier)}" title="综合强度 ${U.esc(ch.strengthTier)}（憨色 ${U.esc(ch.pserTier || "")}）">${U.esc(ch.strengthTier)}</span>` : ""}
          <h3>${U.esc(ch.name)}</h3>
          ${ch.enName ? `<span class="sk-en">${U.esc(ch.enName)}</span>` : ""}
          ${ch.pserTier ? `<span class="cat-pill" title="Pser_hanser Ver1.0 原梯度">${U.esc(ch.pserTier)}</span>` : ""}
          ${ch.role ? `<span class="cat-pill">${U.esc(ch.role)}</span>` : ""}
          ${prioTag}
          ${ch.recruited ? `<span class="rec r1">我方已招</span>` : (ch.dietrichRoute ? `<span class="rec r2">迪线可招</span>` : "")}
          ${ch.faction ? `<span class="cat-pill">${U.esc(ch.faction)}</span>` : ""}
          ${ch.startClass ? `<span class="lv">初始 ${U.esc(ch.startClass)} · 成长和 ${ch.growthTotal}%</span>` : ""}
          <span class="r">
            ${(ch.sSkills || []).length ? `<span class="sk-tier tier-S">S×${ch.sSkills.length}</span>` : ""}
            ${(ch.aSkills || []).length ? `<span class="sk-tier tier-A">A×${ch.aSkills.length}</span>` : ""}
          </span>
        </div></div>
        <div class="sec">
          ${ch.tierSummary ? `<p class="sk-review" style="margin:0 0 6px"><b>综合评价（${U.esc(ch.strengthTier)} / ${U.esc(ch.pserTier)}）：</b>${U.esc(ch.tierSummary)}</p>` : ""}
          ${ch.priorityNote ? `<p class="hint" style="margin:0 0 6px">📌 迪线优先级说明：${U.esc(ch.priorityNote)}</p>` : ""}
          ${ch.note ? `<p class="hint" style="margin:0 0 8px">技能要点：${U.esc(ch.note)}</p>` : ""}
          ${psHtml}${lvHtml}${bmHtml}
          ${(ch.skillsGood || []).length ? `<div class="hint" style="margin-bottom:6px">擅长技能：<b>${U.esc(ch.skillsGood.join("、"))}</b></div>` : ""}
          <div class="sk-matrix">${matRows || `<span class="hint">暂无熟练度习得数据</span>`}</div>
        </div>
      </article>`;
    }).join("");

    return `
      <div class="toolbar">
        <div class="pills">${grpBtns}</div>
        <input type="search" id="skCharSearch" data-sk-q value="${U.esc(state.skillsQuery || "")}" placeholder="搜角色名、定位、强度（SS~D）或任意技能名（如 传送 / 托隆 / 体格+）…">
        <span class="meta">展示 <b>${chars.length}</b> 位角色 · ★ 表示角色唯一特有技能</span>
      </div>
      <div class="sk-filter-row"><span class="sk-flbl">角色强度</span><div class="pills">${tierBtns}</div></div>
      ${scaleLegend ? `<div class="sk-callout"><div class="sk-legend" style="margin-bottom:4px">${scaleLegend}</div>${U.esc(data.priorityLinkNote || "")}${data.characterTierSource ? `<br>${U.esc(data.characterTierSource)}` : ""}</div>` : ""}
      <div class="grid one" style="margin-top:10px">${cards || `<section class="alerts"><p class="txt">没有匹配的角色。</p></section>`}</div>
    `;
  }

  function renderSkillsView(data, state) {
    if (!data) return `<p class="lede">技能图鉴数据加载中…</p>`;
    const tab = state.skillsTab || "skills";
    const meta = data.meta || {};
    const tierLegend = (data.tiers || []).map(t =>
      `<span class="sk-leg"><span class="sk-tier tier-${U.esc(t.key)}">${U.esc(t.label)}</span> <small>${U.esc(t.desc)}</small></span>`
    ).join("");
    const srcLinks = (meta.sources || []).map(s =>
      `<a href="${U.esc(s.url)}" target="_blank" rel="noopener">${U.esc(s.label)}</a>`
    ).join(" · ");

    return `
      <p class="lede">收录全 <b>${data.summary.skillCount}</b> 项技能/战技/魔法/职业精通/个人特技与 <b>${data.summary.charCount}</b> 位角色综合强度评级（<b>SS~D</b>）及 12 项熟练度习得表，清晰区分「全员通用（职业获取）」「角色表限定（多人熟练度）」「稀有习得」与「角色特有」。</p>
      <section class="alerts">
        <div class="sk-subtabs">
          <button type="button" class="pill${tab === "skills" ? " on" : ""}" data-sk-tab="skills">技能总表（评级 · 获取范围 · 职业/角色反查）</button>
          <button type="button" class="pill${tab === "chars" ? " on" : ""}" data-sk-tab="chars">全 63 角色评级（SS~D）与熟练度矩阵</button>
        </div>
        <div class="sk-legend">${tierLegend}</div>
        <p class="hint" style="margin:6px 0 0">${U.esc(meta.ratingNote || "")}<br>数据与参考来源：${srcLinks}</p>
      </section>
      ${tab === "chars" ? renderCharsShowcase(data, state) : renderSkillsTable(data, state)}
    `;
  }

  root.FE = root.FE || {};
  root.FE.views = root.FE.views || {};
  root.FE.views.renderSkillsView = renderSkillsView;
})(window);
