/* 技能图鉴视图：全 584 项技能总表（评级 / 获取范围 / 生效兵种 / 按习得条件整理角色），全量职业与角色稳定超链接 */
(function (root) {
  const U = root.FE.utils;
  const SL = root.FE.skillsLogic;
  const LL = root.FE.linksLogic;

  const SCOPE_BTNS = [
    ["全部", "全部来源"],
    ["unique", "角色特有（唯一）"],
    ["rare", "稀有习得（≤5人）"],
    ["common_class", "全员通用（职业获取）"],
    ["common_learn", "角色表限定（>5人熟练度）"],
  ];

  const TIER_SUB = { S: "核心", A: "强力", B: "实用", C: "偏弱" };

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

  function renderOwners(sk, reg) {
    const list = sk.charSources || [];
    if (!list.length) return "";
    const groups = SL.groupCharSourcesByCondition(list);
    const limitPerGroup = 10;
    const renderChip = cs =>
      LL.renderEntityLink(reg, "char", cs.char, {
        label: U.shortName(cs.char),
        className: `sk-owner sk-char-link${cs.recruited ? " rec" : ""}`,
        title: `查看「${cs.char}」角色图鉴（${cs.how}）`,
      });

    const rowsHtml = groups.map(g => {
      const head = g.chars.slice(0, limitPerGroup).map(renderChip).join("");
      const extra = g.chars.length > limitPerGroup
        ? `<details class="sk-more"><summary>展开其余 ${g.chars.length - limitPerGroup} 人</summary><div class="sk-more-box">${g.chars.slice(limitPerGroup).map(renderChip).join("")}</div></details>`
        : "";
      return `<div class="sk-cond-row">
        <span class="sk-cond-lbl">${U.esc(g.condition)}</span>
        <div class="sk-cond-chars">${head}${extra}</div>
      </div>`;
    }).join("");

    return `<div class="sk-cond-list">${rowsHtml}</div>`;
  }

  function renderClassSources(sk, reg) {
    const list = sk.classSources || [];
    if (!list.length) return "";
    const chips = list.map(cs => {
      const inner = `${U.esc(cs.cls)}<small>${U.esc(cs.tier)}·${U.esc(cs.how)}${cs.masteryExp ? " " + cs.masteryExp + "EXP" : ""}</small>`;
      return LL.renderEntityLink(reg, "class", cs.cls, {
        className: "sk-cls-chip",
        title: `查看职业图鉴：${cs.cls}（${cs.tier}·${cs.how}）`,
        innerHtml: inner,
      });
    }).join("");
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

  function renderSkillsView(data, state, ctx) {
    if (!data) return `<p class="lede">技能图鉴数据加载中…</p>`;
    const C = ctx || {};
    const reg = C.registry;
    const focusName = C.focusTarget ? (LL.resolveEntity(reg, "skill", C.focusTarget) || C.focusTarget) : "";

    const meta = data.meta || {};
    const tierLegend = (data.tiers || []).map(t =>
      `<span class="sk-leg"><span class="sk-tier tier-${U.esc(t.key)}">${U.esc(t.label)}</span> <small>${U.esc(t.desc)}</small></span>`
    ).join("");
    const srcLinks = (meta.sources || []).map(s =>
      `<a href="${U.esc(s.url)}" target="_blank" rel="noopener">${U.esc(s.label)}</a>`
    ).join(" · ");

    const selectedUnitTypes = state.skillsUnitTypes || [];
    const allSkills = data.skills || [];
    let filtered;
    if (focusName) {
      const exact = allSkills.filter(sk => sk.name === focusName);
      filtered = exact.length ? exact : SL.filterSkills(allSkills, { query: focusName });
    } else {
      filtered = SL.filterSkills(allSkills, {
        query: state.skillsQuery,
        rating: state.skillsRating,
        scope: state.skillsScope,
        category: state.skillsCategory,
        discipline: state.skillsDiscipline,
        unitTypes: selectedUnitTypes,
        onlyRecruited: state.skillsOnlyRecruited,
      });
    }
    const sum = SL.summarizeSkills(filtered);
    const hasFilter =
      !!focusName ||
      state.skillsRating !== "全部" ||
      state.skillsScope !== "全部" ||
      state.skillsCategory !== "全部" ||
      state.skillsDiscipline !== "全部" ||
      selectedUnitTypes.length > 0 ||
      state.skillsOnlyRecruited ||
      !!(state.skillsQuery || "").trim();

    const ratingBtns = [["全部", `全部 (${allSkills.length})`], ...(data.tiers || []).map(t => [t.key, `${t.key} 级 (${data.summary.tierCounts[t.key] || 0})`])]
      .map(([k, label]) => `<button type="button" class="pill${!focusName && state.skillsRating === k ? " on" : ""}${k !== "全部" ? " tier-" + k : ""}" data-sk-rating="${U.esc(k)}">${U.esc(label)}</button>`)
      .join("");

    const scopeBtns = SCOPE_BTNS
      .map(([k, label]) => `<button type="button" class="pill${!focusName && state.skillsScope === k ? " on" : ""}" data-sk-scope="${U.esc(k)}">${U.esc(label)}</button>`)
      .join("");

    const catBtns = ["全部", ...(data.categories || [])]
      .map(k => `<button type="button" class="pill${!focusName && state.skillsCategory === k ? " on" : ""}" data-sk-cat="${U.esc(k)}">${U.esc(k)}</button>`)
      .join("");

    const unitTypeOrder = data.unitTypes || SL.UNIT_TYPE_ORDER;
    const utCounts = (data.summary && data.summary.unitTypeCounts) || {};
    const utChecks = unitTypeOrder.map(ut => {
      const checked = !focusName && selectedUnitTypes.includes(ut);
      const label = ut === "无限制" ? "无兵种限制（全兵种）" : ut;
      const cnt = utCounts[ut] != null ? utCounts[ut] : 0;
      return `<label class="skill-cb${checked ? " on" : ""}">
        <input type="checkbox" data-sk-ut="${U.esc(ut)}"${checked ? " checked" : ""}>
        <span>${U.esc(label)}</span><small>${cnt}</small>
      </label>`;
    }).join("");

    const discOpts = ["全部", ...(data.disciplines || []), "职业", "角色"]
      .map(d => `<option value="${U.esc(d)}"${!focusName && state.skillsDiscipline === d ? " selected" : ""}>熟练度：${U.esc(d)}</option>`)
      .join("");

    const focusBanner = focusName
      ? `<div class="ent-focus-bar">
          <span>🎯 当前定位技能：<b>${U.esc(focusName)}</b>（链接已固定在地址栏，可直接收藏或分享）</span>
          <span class="ent-focus-acts">
            <a class="btn pri" href="#skills" data-sk-clear>显示全部技能</a>
            <button type="button" class="btn ghost" data-ent-back>← 返回上一页</button>
          </span>
        </div>`
      : "";

    const showLimit = focusName || state.skillsShowAll ? filtered.length : 120;
    const shown = filtered.slice(0, showLimit);

    const rows = shown.map(sk => {
      const isFocused = focusName && sk.name === focusName;
      return `
      <tr class="sk-row tier-row-${U.esc(sk.rating)}${isFocused ? " ent-focused" : ""}" data-sk-name="${U.esc(sk.name)}"${isFocused ? ' data-ent-focused="true"' : ""}>
        <td class="sk-c-tier">
          <span class="sk-tier sk-tier-badge tier-${U.esc(sk.rating)}">${U.esc(sk.rating)} 级</span>
          ${TIER_SUB[sk.rating] ? `<div class="sk-tier-sub">${U.esc(TIER_SUB[sk.rating])}</div>` : ""}
        </td>
        <td class="sk-c-name">
          <div class="sk-name-line"><b class="sk-name">${LL.renderEntityLink(reg, "skill", sk.name, { className: "ent-self" })}</b>${sk.enName ? ` <span class="sk-en">${U.esc(sk.enName)}</span>` : ""}</div>
          <div class="sk-meta-line"><span class="cat-pill">${U.esc(sk.category)}</span>${sk.discipline && sk.discipline !== "角色" && sk.discipline !== "职业" ? ` <span class="cat-pill">${U.esc(sk.discipline)}</span>` : ""}${renderUnitTypeBadges(sk) ? ` ${renderUnitTypeBadges(sk)}` : ""}</div>
        </td>
        <td class="sk-c-scope">${renderScopePill(sk)}</td>
        <td class="sk-c-eff">
          ${renderParams(sk.params)}
          ${sk.effect ? `<div class="sk-eff">${U.esc(sk.effect)}</div>` : ""}
          ${sk.review ? `<div class="sk-review"><b>简评：</b>${U.esc(sk.review)}</div>` : ""}
        </td>
        <td class="sk-c-src">
          ${renderClassSources(sk, reg)}
          ${renderOwners(sk, reg)}
        </td>
      </tr>`;
    }).join("");

    const moreBtn = filtered.length > showLimit
      ? `<div style="text-align:center;margin:14px 0"><button type="button" class="btn" data-sk-all>展开剩余 ${filtered.length - showLimit} 条（共 ${filtered.length} 条）</button></div>`
      : "";

    return `
      <p class="lede">技能图鉴：收录全 <b>${data.summary.skillCount}</b> 项技能/战技/魔法/职业精通/个人特技，按习得条件整理角色并清晰区分「全员通用（职业获取）」「角色表限定」「稀有习得」与「角色特有」。点击任意<b>职业</b>或<b>角色</b>可直接跳转对应图鉴页（全 <b>${data.summary.charCount}</b> 位角色总览请见 <a href="#chars" class="ent-link">角色图鉴 →</a>）。</p>
      <section class="alerts">
        <div class="sk-legend">${tierLegend}</div>
        <p class="hint" style="margin:6px 0 0">${U.esc(meta.ratingNote || "")}<br>数据与参考来源：${srcLinks}</p>
      </section>
      ${focusBanner}
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
      ${shown.length ? `<div class="scroll"><table class="sk-tbl"><colgroup><col class="sk-col-tier"><col class="sk-col-name"><col class="sk-col-scope"><col class="sk-col-eff"><col class="sk-col-src"></colgroup><thead><tr><th class="sk-c-tier">评级</th><th>技能名</th><th>获取范围</th><th>效果与数值</th><th>习得途径（按习得条件整理）</th></tr></thead><tbody>${rows}</tbody></table></div>${moreBtn}` : `<section class="alerts"><p class="txt">没有符合条件的技能，试试放宽筛选或清空搜索词。</p></section>`}
    `;
  }

  root.FE = root.FE || {};
  root.FE.views = root.FE.views || {};
  root.FE.views.renderSkillsView = renderSkillsView;
})(window);
