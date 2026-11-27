/* 模块 1：友好度培养视图（四大主角、待挖角角色声望/友好度总览与迪线满足标记、吃饭 perfect 组合） */
(function (root) {
  const U = root.FE.utils;
  const AL = root.FE.affinityLogic;

  function renderAffinityView(data, state) {
    const D = data || {
      lords: [], roster: [], dishes: [], weights: [], goals: [],
      maxed: [], absent: [], pairsDone: [], currentRenown: null,
    };
    const summary = AL.summarizeAffinity(D);
    const rosterSum = AL.summarizeRoster(D.roster);
    const rFilter = state.affinityRosterFilter || "important";
    const filteredRoster = AL.filterRoster(D.roster, rFilter, state.affinityQuery);
    const filteredDishes = AL.filterDishes(D, state.affinityQuery, state.affinityOnlyPerfect);
    const matrix = AL.buildTargetDishMatrix(D);
    const lv2 = AL.listSupportTwoTargets(D);

    const ctierBadge = x => x.strengthTier
      ? ` <span class="ctier ctier-${U.esc(x.strengthTier)}" title="综合强度 ${U.esc(x.strengthTier)}（憨色 ${U.esc(x.pserTier || "")}）${x.role ? " · " + U.esc(x.role) : ""}">${U.esc(x.strengthTier)}</span>`
      : "";

    // 1) 四大主角（领主）卡片
    const lordsHtml = (D.lords || []).length ? `<section class="alerts">
      <h2>主角 / 领主（4 位 · 当前主线：${U.esc(D.lord || "迪托利希")}${D.currentRenown != null ? ` · 当前声望 Lv${D.currentRenown}` : ""}）</h2>
      <div class="grid">${D.lords.map(l => `<article class="card">
        <div class="ch"><div class="ct">
          <h3>${U.esc(l.name)}</h3>${ctierBadge(l)}
          ${l.isCurrent ? `<span class="tag ok">当前主角</span>` : `<span class="cat-pill">其他路线领主</span>`}
          <span class="r">待刷目标 ${l.activeTargets.length} 人 · 已达标 ${l.doneTargets.length} 人</span>
        </div></div>
        <div class="sec">
          ${(l.favoriteDishes || []).length
            ? `<p class="txt"><span class="lab">最爱的菜</span>${U.esc(l.favoriteDishes.join("、"))}</p>`
            : `<p class="txt"><span class="lab">喜欢的菜</span>${U.esc((l.likedDishes || []).join("、") || "—")}</p>`}
          ${(l.hatedDishes || []).length ? `<p class="hint" style="margin:0">讨厌：${U.esc(l.hatedDishes.join("、"))}</p>` : ""}
          ${(l.activeTargets || []).length ? `<p class="hint" style="margin:0">本线当前刷支援对象：<b>${U.esc(l.activeTargets.join("、"))}</b></p>` : ""}
          ${(l.doneTargets || []).length ? `<p class="hint" style="margin:0">本线友好度已达标：${U.esc(l.doneTargets.join("、"))}</p>` : ""}
        </div>
      </article>`).join("")}</div>
    </section>` : "";

    // 2) 主角与待挖角角色总览（基于 Recruit - Diet 表 + 当前记录标记）
    const filterTabs = [
      ["important", `迪线必招/可选（${rosterSum.importantTotal}）`],
      ["met", `迪线友好度已满足（${rosterSum.dietMet}）`],
      ["todo", `迪线待刷友好度（${rosterSum.dietTodo}）`],
      ["recruited", `已入队（${rosterSum.recruited}）`],
      ["other", `别线更易（${rosterSum.otherRoute}）`],
      ["all", `全部角色（${rosterSum.total}）`],
    ].map(([k, label]) =>
      `<button type="button" class="fchip" data-aff-rf="${k}" aria-pressed="${rFilter === k}">${U.esc(label)}</button>`
    ).join("");

    const statusBadge = x => {
      if (x.statusKey === "recruited") return `<span class="rec r3">✓ 已入队</span>`;
      if (x.statusKey === "met") return `<span class="rec r1">✓ ${U.esc(x.dietAffinityReason)}</span>`;
      if (x.statusKey === "todo") return `<span class="rec r2">${U.esc(x.dietAffinityReason)}</span>`;
      if (x.statusKey === "part2") return `<span class="rec r3">第二部</span>`;
      return `<span class="hint">${U.esc(x.dietAffinityReason)}</span>`;
    };

    const renownCell = x => {
      if (x.dietRenown == null) return "—";
      if (x.recruited) return `Lv${x.dietRenown}`;
      if (x.renownMet === true) return `<span class="ok">Lv${x.dietRenown} ✓</span>`;
      if (D.currentRenown != null) return `Lv${x.dietRenown} <small class="hint">(差${x.dietRenown - D.currentRenown})</small>`;
      return `Lv${x.dietRenown}`;
    };

    const rosterRows = filteredRoster.map(x => `<tr class="${x.statusKey === "met" ? "cur" : ""}">
      <td><b>${U.esc(x.name)}</b>${ctierBadge(x)}${x.isLord ? ` <span class="cat-pill">主角</span>` : ""}${x.jpName ? `<br><span class="jp">${U.esc(x.jpName)}</span>` : ""}</td>
      <td><span class="cat-pill">${U.esc(x.dietTier || "—")}</span></td>
      <td class="n">${renownCell(x)}</td>
      <td class="n">${x.dietSupport != null ? `支援 ${x.dietSupport}` : "—"}</td>
      <td>${statusBadge(x)}${(x.otherLords || []).map(o => `<br><small class="${o.met ? "ok" : "hint"}">${o.met ? "✓ " : ""}${U.esc(o.label)}</small>`).join("")}</td>
      <td class="note">${U.esc(x.condition || "—")}${x.chapter ? ` <small>（约第 ${U.esc(x.chapter)} 章）</small>` : ""}</td>
      <td class="note">${U.esc(x.easiestRoute || "—")}${x.secondRoute ? `<br><small>次易：${U.esc(x.secondRoute)}</small>` : ""}</td>
      <td class="note">${U.esc((x.favoriteDishes || []).join("、") || "—")}</td>
    </tr>`).join("");

    const rosterHtml = `<section class="alerts">
      <h2>主角与待挖角角色（迪线声望 & 友好度要求 · 当前声望 Lv${D.currentRenown ?? "?"}）</h2>
      <div class="lvsum" style="margin:4px 0 6px">
        <div class="hi"><small>迪线友好度已满足（待招）</small><b>${rosterSum.dietMet} 人</b></div>
        <div><small>迪线待刷友好度（必招/可选）</small><b>${rosterSum.dietTodo} 人</b></div>
        <div><small>已入队</small><b>${rosterSum.recruited} 人</b></div>
        <div><small>全表角色</small><b>${rosterSum.total} 人</b></div>
      </div>
      <div class="subtabs">${filterTabs}</div>
      <div class="scroll"><table>
        <tr><th>角色</th><th>迪线分类</th><th class="n">迪线声望</th><th class="n">友好度要求</th><th>迪线友好度状态</th><th>招募条件</th><th>最易 / 次易路线</th><th>最爱的菜</th></tr>
        ${rosterRows || `<tr><td colspan="8" class="note">当前筛选条件下没有匹配的角色</td></tr>`}
      </table></div>
    </section>`;

    // 3) 吃饭三人一桌组合 + 目标反查
    const spk = t => (t.sparkle || []).join("+");
    const who = t => (t.who || []).map(n => U.esc(U.shortName(n))).join(" + ");
    const tag = t => t.perfect ? `<span class="tag ok">perfect</span>` : `<span class="tag warn">非 perfect</span>`;
    const why = t => (t.pairs || []).map(([a, b]) => `${U.esc(U.shortName(a))}–${U.esc(U.shortName(b))}`).join("、")
      + (t.filler && t.filler.length ? `（${t.filler.map(n => U.esc(U.shortName(n))).join("、")} 凑数）` : "");

    const rows = filteredDishes.map(r => r.options.map((t, k) =>
      `<tr>${k ? "" : `<td rowspan="${r.options.length}"><b>${U.esc(r.dish)}</b>${r.perfect ? "" : `<br><small class="note">没有 perfect，下面是备选</small>`}</td>`}
      <td>${k ? "" : "<b>"}${who(t)}${k ? "" : "</b>"}</td><td>${tag(t)}</td><td class="n">${spk(t)}</td><td class="n">${t.score}</td><td class="note">${why(t)}</td></tr>`
    ).join("") || `<tr><td><b>${U.esc(r.dish)}</b></td><td colspan="5" class="note">没有能用的组合</td></tr>`).join("");

    const tgtRows = matrix.map(x =>
      `<tr><td>${U.esc(U.shortName(x.lord))}–${U.esc(U.shortName(x.target))}</td><td class="n">${x.score}</td>
      <td class="n">${x.support === 2 ? `<span class="tag ok">支援 2</span>` : x.support == null ? "—" : "支援 " + x.support}</td>
      <td class="note">${x.perfectDishes.length ? U.esc(x.perfectDishes.join("、")) : "—"}</td>
      <td class="note">${x.fallbackDishes.length ? U.esc(x.fallbackDishes.join("、")) : "—"}</td></tr>`
    ).join("");

    const notes = [
      "名册来源：Google Sheet「Recruit - Diet」（已同步至 meals/diet_tab.json）；已满足判定依据 meals/meal_config.json（recruited、maxed、pairs_done）与表格「满足」列。",
      "规则：闪光 最爱 2、喜欢 1、普通 0；三人是 1+1+1 或 2+2+0 才算 perfect。讨厌这道菜的人不上桌。2+1+0 还没确认，只当备选。",
      "只有领主和还要挖的目标上桌，每个座位都要涨有用的支援；已入队的人不上桌（吃饭是为了挖角）。",
      ...(D.goals || []).map(g => "分数：" + U.esc(g)),
      "支援 1 就能招的人不列进吃饭组合（不用吃饭）。每桌主角排第一，其他领主第二。",
      ...((D.pairsDone || []).length ? [`支援已经够了、不再刷：${D.pairsDone.map(([a, b]) => U.esc(U.shortName(a)) + "–" + U.esc(U.shortName(b))).join("、")}。`] : []),
      ...([...(D.maxed || []), ...(D.absent || [])].length ? [`不上桌：${[...(D.maxed || []).map(n => U.esc(n) + "（好感满了）"), ...(D.absent || []).map(n => U.esc(n) + "（不在）")].join("、")}。`] : []),
    ];

    return `<p class="lede">友好度培养模块：集中展示四大主角、全员挖角声望与友好度要求（标记迪线已满足状态），以及每道菜的三人 perfect 组合。</p>
      <div class="filterbar">
        <input type="search" id="affQuery" data-aff-q placeholder="搜角色、菜名或条件，比如 杰斯塔、哥莱亚斯、蕾达、糖浆炖梨" value="${U.esc(state.affinityQuery || "")}" aria-label="筛选角色或菜品">
        <label class="showdone" style="margin:0"><input type="checkbox" data-aff-pf${state.affinityOnlyPerfect ? " checked" : ""}> 菜单只看能 perfect 的菜</label>
      </div>
      ${lordsHtml}
      ${rosterHtml}
      <section class="alerts"><h2>每道菜带谁（${summary.perfectCount}/${summary.totalDishes} 道能 perfect，当前显示 ${filteredDishes.length} 道）</h2>
        <div class="scroll"><table><tr><th>菜</th><th>三人</th><th></th><th class="n">闪光</th><th class="n">分</th><th>涨哪些支援</th></tr>${rows || `<tr><td colspan="6" class="note">没有匹配的菜品或角色</td></tr>`}</table></div>
      </section>
      ${lv2.length ? `<section class="alerts"><h2>${U.esc(U.shortName(D.lord))}线还要招、支援 2 就能招（${lv2.length}）</h2><p class="txt">${lv2.map(x => U.esc(U.shortName(x.target))).join("、")}</p></section>` : ""}
      <section class="alerts"><h2>从目标查菜</h2>
        <div class="scroll"><table><tr><th>支援</th><th class="n">分</th><th class="n">招募要</th><th>perfect 的菜</th><th>只有备选的菜</th></tr>${tgtRows}</table></div>
      </section>
      <details class="notes"><summary>说明（友好度培养规则与数据来源）</summary><ul>${notes.map(x => `<li>${x}</li>`).join("")}</ul></details>`;
  }

  root.FE = root.FE || {};
  root.FE.views = root.FE.views || {};
  root.FE.views.renderAffinityView = renderAffinityView;
})(window);
