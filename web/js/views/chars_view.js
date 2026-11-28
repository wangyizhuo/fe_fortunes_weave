/* 角色图鉴视图：全 63 角色综合强度评级（SS~D）、初始/已有职业、12 项熟练度习得表、挖角与路线直达 */
(function (root) {
  const U = root.FE.utils;
  const SL = root.FE.skillsLogic;
  const LL = root.FE.linksLogic;

  function renderCharsView(skillsData, state, ctx) {
    if (!skillsData) return `<p class="lede">角色图鉴数据加载中…</p>`;
    const C = ctx || {};
    const reg = C.registry;
    const focusName = C.focusTarget ? (LL.resolveEntity(reg, "char", C.focusTarget) || C.focusTarget) : "";

    const allChars = skillsData.characters || [];
    const routeByName = new Map(((C.routeData && C.routeData.chars) || []).map(c => [c.name, c]));
    const rosterByName = new Map(((C.affinityData && C.affinityData.roster) || []).map(r => [r.name, r]));

    const group = state.charsGroup || "recruited";
    const ctier = state.charsTier || "全部";
    const query = state.charsQuery || "";

    let chars;
    if (focusName) {
      const exact = allChars.filter(c => c.name === focusName);
      chars = exact.length ? exact : SL.filterSkillChars(allChars, { query: focusName, group: "all", strengthTier: "全部" });
    } else {
      chars = SL.filterSkillChars(allChars, { query, group, strengthTier: ctier });
    }

    const recCnt = allChars.filter(c => c.recruited).length;
    const dietCnt = allChars.filter(c => c.dietrichRoute).length;
    const allCnt = allChars.length;
    const sc = (skillsData.summary && skillsData.summary.strengthCounts) || {};

    const grpBtns = [
      ["recruited", `我方已招（${recCnt}）`],
      ["dietrich", `迪线可入队（${dietCnt}）`],
      ["all", `全角色（${allCnt}）`],
    ].map(([k, label]) => `<button type="button" class="pill${!focusName && group === k ? " on" : ""}" data-ch-grp="${k}">${U.esc(label)}</button>`).join("");

    const tierKeys = ["全部", "SS", "S", "A", "B", "C", "D"];
    const tierBtns = tierKeys.map(k => {
      const label = k === "全部" ? `全强度（${allCnt}）` : `${k}（${sc[k] || 0}）`;
      return `<button type="button" class="pill${!focusName && ctier === k ? " on" : ""}${k !== "全部" ? " ctier-" + k : ""}" data-ch-tier="${k}">${U.esc(label)}</button>`;
    }).join("");

    const scaleLegend = (skillsData.characterTierScale || []).map(s =>
      `<span class="sk-leg"><span class="ctier ctier-${U.esc(s.tier)}">${U.esc(s.tier)}</span> <small>${U.esc(s.pserMap)} · 基准 ${U.esc(s.defaultP)}</small></span>`
    ).join("");

    const focusBanner = focusName
      ? `<div class="ent-focus-bar">
          <span>🎯 当前定位角色：<b>${U.esc(focusName)}</b>（链接已固定在地址栏，可直接收藏或分享）</span>
          <span class="ent-focus-acts">
            <a class="btn pri" href="#chars" data-ch-showall>显示全部角色</a>
            <button type="button" class="btn ghost" data-ent-back>← 返回上一页</button>
          </span>
        </div>`
      : "";

    const discs = skillsData.disciplines || [];
    const cards = chars.map(ch => {
      const isFocused = focusName && ch.name === focusName;
      const rt = routeByName.get(ch.name);
      const ros = rosterByName.get(ch.name);

      const matRows = discs.filter(d => (ch.matrix[d] || []).length).map(d => {
        const pills = (ch.matrix[d] || []).map(it => {
          const uniq = it.scope === "unique" ? `<i class="sk-star" title="角色唯一特有">★</i>` : "";
          const inner = `${U.esc(it.name)}<small>${U.esc(it.rank || "")}</small>${uniq}`;
          return LL.renderEntityLink(reg, "skill", it.name, {
            className: `sk-mpill tier-${it.rating}`,
            title: `查看技能图鉴：${it.name}（${it.category} · ${it.rating}级）`,
            innerHtml: inner,
          });
        }).join("");
        return `<div class="sk-mrow"><span class="sk-mdisc">${U.esc(d)}</span><div class="sk-mpills">${pills}</div></div>`;
      }).join("");

      const psHtml = ch.personalSkill
        ? `<div class="sk-ch-line"><b>个人特技：</b>${LL.renderEntityLink(reg, "skill", ch.personalSkill.name, {
            className: "sk-mpill tier-A",
            title: `查看技能图鉴：${ch.personalSkill.name}`,
          })} <span class="hint">${U.esc(ch.personalSkill.text)}</span></div>`
        : "";

      const lvHtml = (ch.lvSkills || []).length
        ? `<div class="sk-ch-line"><b>等级特技：</b>${ch.lvSkills.map(x => {
            const inner = `${U.esc(x.name)}<small>${U.esc(x.lv ? "Lv" + x.lv : (x.cond || ""))}</small>`;
            const link = LL.renderEntityLink(reg, "skill", x.name, {
              className: "sk-mpill tier-B",
              title: `查看技能图鉴：${x.name}`,
              innerHtml: inner,
            });
            return `${link}${x.effect ? ` <span class="hint">${U.esc(x.effect)}</span>` : ""}`;
          }).join(" ")}</div>`
        : "";

      const bmHtml = (ch.bloodMarks || []).length
        ? `<div class="sk-ch-line"><b>血印：</b>${ch.bloodMarks.map(x => `<span class="cat-pill">${U.esc(x.name)}</span> <span class="hint">${U.esc(x.text)}</span>`).join(" ")}</div>`
        : "";

      const ownedHtml = rt && (rt.owned || []).length
        ? `<div class="sk-ch-line"><b>我方已有职业：</b>${LL.linkifyList(reg, "class", rt.owned, "、")}${
            (rt.required || []).length ? `　<b>必考职业：</b>${LL.linkifyList(reg, "class", rt.required, "、")}` : ""
          }</div>`
        : "";

      const affBits = [];
      if (ros) {
        if (ros.dietTier) affBits.push(`迪线：${ros.dietTier}`);
        if (ros.dietRenown != null) affBits.push(`声望 Lv${ros.dietRenown}`);
        if (ros.dietSupport != null) affBits.push(`支援 ${ros.dietSupport}`);
        if (ros.easiestRoute) affBits.push(`最易路线：${ros.easiestRoute}`);
        if ((ros.favoriteDishes || []).length) affBits.push(`最爱的菜：${ros.favoriteDishes.join("、")}`);
      }
      const affHtml = affBits.length
        ? `<div class="sk-ch-line"><b>招募与喜好：</b><span class="hint">${U.esc(affBits.join(" · "))}</span></div>`
        : "";

      const prioTag = ch.dietrichPriority
        ? `<span class="rec ${ch.dietrichPriority === "P0" ? "r1" : ch.dietrichPriority === "P1" ? "r2" : "r3"}" title="${U.esc(ch.priorityNote || "")}">迪线 ${U.esc(ch.dietrichPriority)}</span>`
        : (ch.defaultPriority ? `<span class="cat-pill" title="综合强度基准优先级（各路线可按培养需求调整）">基准 ${U.esc(ch.defaultPriority)}</span>` : "");

      const routeSlug = U.SLUG && U.SLUG[ch.name];
      const routeLink = routeSlug
        ? `<a class="btn ghost" href="#plan" data-go="${U.esc(routeSlug)}" style="font-size:12px;padding:2px 8px">查看路线规划 →</a>`
        : "";

      const startClsHtml = ch.startClass
        ? `<span class="lv">初始 ${LL.renderEntityLink(reg, "class", ch.startClass)} · 成长和 ${ch.growthTotal}%</span>`
        : "";

      return `<article class="card sk-ch-card${ch.recruited ? " is-rec" : ""}${isFocused ? " ent-focused" : ""}" id="ch-card-${U.esc(ch.name)}" data-ch-card="${U.esc(ch.name)}"${isFocused ? ' data-ent-focused="true"' : ""}>
        <div class="ch"><div class="ct">
          ${ch.strengthTier ? `<span class="ctier ctier-${U.esc(ch.strengthTier)}" title="综合强度 ${U.esc(ch.strengthTier)}（憨色 ${U.esc(ch.pserTier || "")}）">${U.esc(ch.strengthTier)}</span>` : ""}
          <h3>${LL.renderEntityLink(reg, "char", ch.name, { className: "ent-self" })}</h3>
          ${ch.enName ? `<span class="sk-en">${U.esc(ch.enName)}</span>` : ""}
          ${ch.pserTier ? `<span class="cat-pill" title="Pser_hanser Ver1.0 原梯度">${U.esc(ch.pserTier)}</span>` : ""}
          ${ch.role ? `<span class="cat-pill">${U.esc(ch.role)}</span>` : ""}
          ${prioTag}
          ${ch.recruited ? `<span class="rec r1">我方已招</span>` : (ch.dietrichRoute ? `<span class="rec r2">迪线可招</span>` : "")}
          ${ch.faction ? `<span class="cat-pill">${U.esc(ch.faction)}</span>` : ""}
          ${startClsHtml}
          <span class="r">
            ${routeLink}
            ${(ch.sSkills || []).length ? `<span class="sk-tier tier-S">S×${ch.sSkills.length}</span>` : ""}
            ${(ch.aSkills || []).length ? `<span class="sk-tier tier-A">A×${ch.aSkills.length}</span>` : ""}
          </span>
        </div></div>
        <div class="sec">
          ${ch.tierSummary ? `<p class="sk-review" style="margin:0 0 6px"><b>综合评价（${U.esc(ch.strengthTier)} / ${U.esc(ch.pserTier)}）：</b>${U.esc(ch.tierSummary)}</p>` : ""}
          ${ch.priorityNote ? `<p class="hint" style="margin:0 0 6px">📌 迪线优先级说明：${U.esc(ch.priorityNote)}</p>` : ""}
          ${ch.note ? `<p class="hint" style="margin:0 0 8px">技能要点：${U.esc(ch.note)}</p>` : ""}
          ${ownedHtml}${affHtml}${psHtml}${lvHtml}${bmHtml}
          ${(ch.skillsGood || []).length ? `<div class="hint" style="margin-bottom:6px">擅长技能：<b>${U.esc(ch.skillsGood.join("、"))}</b></div>` : ""}
          <div class="sk-matrix">${matRows || `<span class="hint">暂无熟练度习得数据</span>`}</div>
        </div>
      </article>`;
    }).join("");

    return `
      <p class="lede">角色图鉴：收录全 <b>${allCnt}</b> 位角色综合强度评级（<b>SS~D</b>）、初始/已有职业、招募条件与 12 项熟练度习得技能表。点击任意<b>职业名</b>或<b>技能名</b>均可直接跳转对应图鉴页。</p>
      ${focusBanner}
      <div class="toolbar">
        <div class="pills">${grpBtns}</div>
        <input type="search" id="charSearch" data-ch-q value="${U.esc(query)}" placeholder="搜角色名、定位、强度（SS~D）、初始职业或任意技能名（如 传送 / 体格+）…">
        ${query.trim() || focusName || ctier !== "全部" ? `<a class="btn ghost" href="#chars" data-ch-clear>清空筛选</a>` : ""}
        <span class="meta">展示 <b>${chars.length}</b> 位角色 · ★ 表示角色唯一特有技能</span>
      </div>
      <div class="sk-filter-row"><span class="sk-flbl">角色强度</span><div class="pills">${tierBtns}</div></div>
      ${scaleLegend ? `<div class="sk-callout"><div class="sk-legend" style="margin-bottom:4px">${scaleLegend}</div>${U.esc(skillsData.priorityLinkNote || "")}${skillsData.characterTierSource ? `<br>${U.esc(skillsData.characterTierSource)}` : ""}</div>` : ""}
      <div class="grid one" style="margin-top:10px">${cards || `<section class="alerts"><p class="txt">没有匹配的角色。</p></section>`}</div>
    `;
  }

  root.FE = root.FE || {};
  root.FE.views = root.FE.views || {};
  root.FE.views.renderCharsView = renderCharsView;
})(window);
