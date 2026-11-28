/* 模块 2：道具 / 材料采集视图（城镇商店、范达尔商会以物易物、采集材料反查、PR #31 最强武器评级） */
(function (root) {
  const U = root.FE.utils;
  const IL = root.FE.itemsLogic;

  function renderWeaponTierBadge(tier, reason, forge) {
    if (!tier) return "";
    const tip = [
      `最强武器榜 ${tier} 级${forge ? "（" + forge + "）" : ""}`,
      reason || "",
    ].filter(Boolean).join(" · ");
    return `<span class="ctier ctier-${U.esc(tier)}" title="${U.esc(tip)}">${U.esc(tier)}</span> `;
  }

  function renderItemsView(data, state) {
    const D = data || { categories: ["全部"], towns: [], barter: [], materials: [], weaponTiers: null, notes: [], sources: "", summary: {} };
    const cat = state.itemsCategory || "全部";
    const q = state.itemsQuery || "";
    const tab = state.itemsTab || "all";
    const wtFilter = state.itemsWeaponTier || "全部";

    const wtData = D.weaponTiers || null;
    const allRatedWeapons = (wtData && wtData.weapons) || [];
    const ratedRes = IL.filterWeaponTiers(allRatedWeapons, cat, q, wtFilter);
    const shopRes = IL.filterTowns(D.towns, cat, q, wtFilter);
    const barterRes = IL.filterBarter(D.barter, cat, q, wtFilter);
    const matRes = IL.filterMaterials(D.materials, cat, q, wtFilter);

    const chips = (D.categories || ["全部"]).map(c =>
      `<button type="button" class="fchip" data-item-cat="${U.esc(c)}" aria-pressed="${c === cat}">${U.esc(c)}</button>`
    ).join("");

    const wtCounts = { SS: 0, S: 0, A: 0, B: 0 };
    for (const w of allRatedWeapons) {
      if (wtCounts[w.tier] != null) wtCounts[w.tier] += 1;
    }
    const wtChips = allRatedWeapons.length
      ? [["全部", `全评级`], ["SS", `SS（${wtCounts.SS}）`], ["S", `S（${wtCounts.S}）`], ["A", `A（${wtCounts.A}）`], ["B", `B（${wtCounts.B}）`]]
          .map(([k, label]) => `<button type="button" class="pill${wtFilter === k ? " on" : ""}${k !== "全部" ? " ctier-" + k : ""}" data-item-wt="${k}">${U.esc(label)}</button>`)
          .join("")
      : "";

    const subTabs = [
      ["all", `全部（${shopRes.itemCount} 商品 + ${barterRes.length} 兑换 + ${ratedRes.length} 强榜武器）`],
      ["tiers", `🏆 最强武器评级（${ratedRes.length}/${allRatedWeapons.length} 件）`],
      ["shops", `城镇商店（${shopRes.townCount} 城 / ${shopRes.itemCount} 条）`],
      ["barter", `以物易物（${barterRes.length} 件）`],
      ["materials", `采集材料反查（${matRes.length} 种材料）`],
    ].map(([id, label]) =>
      `<button type="button" class="fchip" data-item-tab="${id}" aria-pressed="${tab === id}">${U.esc(label)}</button>`
    ).join("");

    // 最强武器评级总表（PR #31：SS / S / A / B）
    const wtSrc = (wtData && wtData.source) || {};
    const wtRows = ratedRes.map(w => {
      const statsStr = [
        w.might != null ? `威${w.might}` : "",
        w.hit != null ? `命${w.hit}` : "",
        w.crit ? `必${w.crit}` : "",
        w.avoid ? `避${w.avoid}` : "",
        w.range ? `射${w.range}` : "",
        w.weight != null ? `重${w.weight}` : "",
        w.durability != null ? `耐${w.durability}` : "",
      ].filter(Boolean).join(" · ");
      const places = (w.shopPlaces || []).length
        ? w.shopPlaces.map(p => `<span class="cat-pill">${U.esc(p)}</span>`).join(" ")
        : `<span class="hint">迷宫 / 任务 / 锻造进化</span>`;
      const prioMap = w.tier === "SS" || w.tier === "S" ? `<span class="exp-tier t-P0">探索 P0</span>`
        : w.tier === "A" ? `<span class="exp-tier t-P1">探索 P1</span>`
        : `<span class="exp-tier t-P2">探索 P2</span>`;
      return `<tr>
        <td>${renderWeaponTierBadge(w.tier, w.reason, w.forge)}${prioMap}</td>
        <td><b>${IL.highlightMatch(w.name, q)}</b>${w.forge ? ` <span class="hint">${U.esc(w.forge)}</span>` : ""}${w.jp ? `<br><span class="jp">${U.esc(w.jp)}</span>` : ""}</td>
        <td><span class="cat-pill">${U.esc(w.type)}</span>${w.rank ? ` <span class="hint">${U.esc(w.rank)}</span>` : ""}</td>
        <td class="note" style="font-family:var(--mono);font-size:12px">${U.esc(statsStr || "—")}</td>
        <td class="note">${IL.highlightMatch(w.effect || w.description || "—", q)}</td>
        <td class="note">${IL.highlightMatch(w.reason || "—", q)}</td>
        <td class="note">${places}</td>
      </tr>`;
    }).join("");

    const wtHtml = allRatedWeapons.length && (tab === "all" || tab === "tiers") ? `<section class="alerts">
      <div class="ct" style="align-items:center">
        <h2>🏆 最强武器评级总榜（共 ${ratedRes.length} / ${allRatedWeapons.length} 件 · SS/S→探索 P0，A→P1，B→P2）</h2>
        ${wtSrc.url ? `<a class="btn ghost" href="${U.esc(wtSrc.url)}" target="_blank" rel="noopener" style="margin-left:auto">原评级攻略（${U.esc(wtSrc.title || "Archi-gjj")}）↗</a>` : ""}
      </div>
      ${wtSrc.note ? `<p class="hint" style="margin:2px 0 4px">${U.esc(wtSrc.note)}</p>` : ""}
      ${tab === "tiers"
        ? (ratedRes.length ? `<div class="scroll"><table class="wt-tbl"><tr><th>评级 / 优先级</th><th>武器名</th><th>类型</th><th>强化数值</th><th>特效 / 战技</th><th>评级理由</th><th>商店 / 商会获取</th></tr>${wtRows}</table></div>` : `<p class="txt">没有匹配当前筛选条件的评级武器。</p>`)
        : `<details class="more"${wtFilter !== "全部" ? " open" : ""}><summary>展开全部 ${ratedRes.length} 件最强武器评级详情（城镇商店 / 以物易物 / 材料反查已同步内联标注 SS / S / A / B 徽章）</summary><div class="scroll" style="margin-top:8px"><table class="wt-tbl"><tr><th>评级 / 优先级</th><th>武器名</th><th>类型</th><th>强化数值</th><th>特效 / 战技</th><th>评级理由</th><th>商店 / 商会获取</th></tr>${wtRows}</table></div></details>`}
    </section>` : "";

    const shopHtml = (tab === "all" || tab === "shops") ? (
      shopRes.towns.length ? shopRes.towns.map(t => `<details class="char" open>
        <summary><h3>${IL.highlightMatch(t.cn, q)}</h3><span>${U.esc(t.jp.replace("-武器屋", ""))}${t.en ? " · " + U.esc(t.en) : ""} · ${t.items.length} 件</span></summary>
        <div class="sec"><div class="scroll"><table>
          <tr><th>类别</th><th>评级</th><th>物品</th><th class="n">价格</th><th class="n">库存</th><th>备注 / 评级简评</th><th>来源</th></tr>
          ${t.items.map(it => `<tr${it.weaponTier === "SS" || it.weaponTier === "S" ? ' class="cur"' : ""}>
            <td><span class="cat-pill">${U.esc(it.cat)}</span></td>
            <td>${it.weaponTier ? renderWeaponTierBadge(it.weaponTier, it.weaponReason, it.weaponForge) : `<span class="hint">—</span>`}</td>
            <td><b>${IL.highlightMatch(it.cn, q)}</b> <span class="jp">${U.esc(it.jp)}</span></td>
            <td class="n">${it.price != null ? it.price.toLocaleString() + "G" : "—"}</td>
            <td class="n">${it.stock === "1" ? `<span class="one">1</span>` : U.esc(it.stock || "—")}</td>
            <td class="note">${IL.highlightMatch(it.note, q)}${it.weaponReason ? `${it.note ? " · " : ""}<span class="hint">【${U.esc(it.weaponTier)}评】${U.esc(it.weaponReason)}</span>` : ""}</td>
            <td class="hint">${U.esc(it.src)}</td>
          </tr>`).join("")}
        </table></div></div>
      </details>`).join("") : `<section class="alerts"><p class="txt">没有匹配的商店物品。换个关键词或把类别/评级切回「全部」。</p></section>`
    ) : "";

    const barterHtml = (tab === "all" || tab === "barter") ? `<section class="alerts">
      <h2>范达尔商会 · 以物易物（${barterRes.length} 件）</h2>
      ${barterRes.length ? `<div class="scroll"><table>
        <tr><th>类别</th><th>评级</th><th>物品</th><th>需要采集/钓鱼材料</th><th>地点</th><th>备注 / 评级简评</th></tr>
        ${barterRes.map(x => `<tr${x.weaponTier === "SS" || x.weaponTier === "S" ? ' class="cur"' : ""}>
          <td><span class="cat-pill">${U.esc(x.type)}</span></td>
          <td>${x.weaponTier ? renderWeaponTierBadge(x.weaponTier, x.weaponReason, x.weaponForge) : `<span class="hint">—</span>`}</td>
          <td><b>${IL.highlightMatch(x.cn, q)}</b> <span class="jp">${U.esc(x.jp)}</span></td>
          <td>${IL.highlightMatch(x.cost, q)}</td>
          <td class="hint">${U.esc(x.location || "帝都达格席翁 · 范达尔商会")}</td>
          <td class="note">${IL.highlightMatch(x.note, q)}${x.weaponReason ? `${x.note ? " · " : ""}<span class="hint">【${U.esc(x.weaponTier)}评】${U.esc(x.weaponReason)}</span>` : ""}</td>
        </tr>`).join("")}
      </table></div>` : `<p class="txt">没有匹配的以物易物装备。</p>`}
    </section>` : "";

    const matHtml = (tab === "all" || tab === "materials") ? `<section class="alerts">
      <h2>采集 / 钓鱼材料反查表（${matRes.length} 种材料 → 可兑换装备）</h2>
      ${matRes.length ? `<div class="scroll"><table>
        <tr><th>材料（原名）</th><th class="n">用途数</th><th>可兑换装备与数量</th></tr>
        ${matRes.map(m => `<tr>
          <td><b>${IL.highlightMatch(m.material, q)}</b></td>
          <td class="n">${m.usedIn.length}</td>
          <td class="note">${m.usedIn.map(u => `${u.weaponTier ? renderWeaponTierBadge(u.weaponTier) : ""}${IL.highlightMatch(u.cn, q)}（×${u.qty}${u.note ? "，" + U.esc(u.note) : ""}）`).join("；")}</td>
        </tr>`).join("")}
      </table></div>` : `<p class="txt">没有匹配的采集材料。</p>`}
    </section>` : "";

    const notes = [
      ...(D.notes || []).map(U.esc),
      wtSrc.url ? `最强武器评级来源：<a href="${U.esc(wtSrc.url)}" target="_blank" rel="noopener">${U.esc(wtSrc.title || "最强武器评级")}</a>（${U.esc(wtSrc.author || "")}）。` : "",
      `数据来源：${U.esc(D.sources || "")}。`,
      "模块数据：config/items_config.json + config/weapon_tier_ref.json + dietrich/shops-src/weapons.tsv；纯逻辑：modules/items/catalog.py。",
    ].filter(Boolean);

    return `<p class="lede">道具 / 材料采集模块：按城镇检索武器、教本、手形、武具箱与道具，同步融合 <b>PR #31 最强武器评级（SS / S / A / B）</b>、范达尔商会以物易物与「采集材料反查」。</p>
      <div class="filterbar">
        <input type="search" id="itemQuery" data-item-q placeholder="搜物品、城镇、评级（SS/S/A/B）、特性或材料，比如 雷电剑、伏力萨、克骑、バク、教本" value="${U.esc(q)}" aria-label="搜索道具与材料">
        <div class="fchips">${chips}</div>
      </div>
      ${wtChips ? `<div class="sk-filter-row"><span class="sk-flbl">武器评级</span><div class="pills">${wtChips}</div></div>` : ""}
      <div class="subtabs">${subTabs}</div>
      ${wtHtml}
      ${matHtml}
      ${barterHtml}
      <div class="grid one">${shopHtml}</div>
      <details class="notes"><summary>说明（商店与材料采集注意事项）</summary><ul>${notes.map(x => `<li>${x}</li>`).join("")}</ul></details>`;
  }

  root.FE = root.FE || {};
  root.FE.views = root.FE.views || {};
  root.FE.views.renderItemsView = renderItemsView;
})(window);
