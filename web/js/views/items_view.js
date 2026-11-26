/* 模块 2：道具 / 材料采集视图（城镇商店、范达尔商会以物易物、采集材料反查） */
(function (root) {
  const U = root.FE.utils;
  const IL = root.FE.itemsLogic;

  function renderItemsView(data, state) {
    const D = data || { categories: ["全部"], towns: [], barter: [], materials: [], notes: [], sources: "", summary: {} };
    const cat = state.itemsCategory || "全部";
    const q = state.itemsQuery || "";
    const tab = state.itemsTab || "all";

    const shopRes = IL.filterTowns(D.towns, cat, q);
    const barterRes = IL.filterBarter(D.barter, cat, q);
    const matRes = IL.filterMaterials(D.materials, cat, q);

    const chips = (D.categories || ["全部"]).map(c =>
      `<button type="button" class="fchip" data-item-cat="${U.esc(c)}" aria-pressed="${c === cat}">${U.esc(c)}</button>`
    ).join("");

    const subTabs = [
      ["all", `全部（${shopRes.itemCount} 商品 + ${barterRes.length} 兑换）`],
      ["shops", `城镇商店（${shopRes.townCount} 城 / ${shopRes.itemCount} 条）`],
      ["barter", `以物易物（${barterRes.length} 件）`],
      ["materials", `采集材料反查（${matRes.length} 种材料）`],
    ].map(([id, label]) =>
      `<button type="button" class="fchip" data-item-tab="${id}" aria-pressed="${tab === id}">${U.esc(label)}</button>`
    ).join("");

    const shopHtml = (tab === "all" || tab === "shops") ? (
      shopRes.towns.length ? shopRes.towns.map(t => `<details class="char" open>
        <summary><h3>${IL.highlightMatch(t.cn, q)}</h3><span>${U.esc(t.jp.replace("-武器屋", ""))}${t.en ? " · " + U.esc(t.en) : ""} · ${t.items.length} 件</span></summary>
        <div class="sec"><div class="scroll"><table>
          <tr><th>类别</th><th>物品</th><th class="n">价格</th><th class="n">库存</th><th>备注</th><th>来源</th></tr>
          ${t.items.map(it => `<tr>
            <td><span class="cat-pill">${U.esc(it.cat)}</span></td>
            <td>${IL.highlightMatch(it.cn, q)} <span class="jp">${U.esc(it.jp)}</span></td>
            <td class="n">${it.price != null ? it.price.toLocaleString() + "G" : "—"}</td>
            <td class="n">${it.stock === "1" ? `<span class="one">1</span>` : U.esc(it.stock || "—")}</td>
            <td class="note">${IL.highlightMatch(it.note, q)}</td>
            <td class="hint">${U.esc(it.src)}</td>
          </tr>`).join("")}
        </table></div></div>
      </details>`).join("") : `<section class="alerts"><p class="txt">没有匹配的商店物品。换个关键词或把类别切回「全部」。</p></section>`
    ) : "";

    const barterHtml = (tab === "all" || tab === "barter") ? `<section class="alerts">
      <h2>范达尔商会 · 以物易物（${barterRes.length} 件）</h2>
      ${barterRes.length ? `<div class="scroll"><table>
        <tr><th>类别</th><th>物品</th><th>需要采集/钓鱼材料</th><th>地点</th><th>备注</th></tr>
        ${barterRes.map(x => `<tr>
          <td><span class="cat-pill">${U.esc(x.type)}</span></td>
          <td>${IL.highlightMatch(x.cn, q)} <span class="jp">${U.esc(x.jp)}</span></td>
          <td>${IL.highlightMatch(x.cost, q)}</td>
          <td class="hint">${U.esc(x.location || "帝都达格席翁 · 范达尔商会")}</td>
          <td class="note">${IL.highlightMatch(x.note, q)}</td>
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
          <td class="note">${m.usedIn.map(u => `${IL.highlightMatch(u.cn, q)}（×${u.qty}${u.note ? "，" + U.esc(u.note) : ""}）`).join("；")}</td>
        </tr>`).join("")}
      </table></div>` : `<p class="txt">没有匹配的采集材料。</p>`}
    </section>` : "";

    const notes = [
      ...(D.notes || []).map(U.esc),
      `数据来源：${U.esc(D.sources || "")}。`,
      "模块数据：config/items_config.json + dietrich/shops-src/weapons.tsv；纯逻辑：modules/items/catalog.py。",
    ];

    return `<p class="lede">道具 / 材料采集模块：按城镇检索武器、教本、手形、武具箱与道具，并整合范达尔商会以物易物与「采集材料反查」。</p>
      <div class="filterbar">
        <input type="search" id="itemQuery" data-item-q placeholder="搜物品、城镇、特性或材料，比如 银剑、梅盖拉、克骑、バク、教本" value="${U.esc(q)}" aria-label="搜索道具与材料">
        <div class="fchips">${chips}</div>
      </div>
      <div class="subtabs">${subTabs}</div>
      ${matHtml}
      ${barterHtml}
      <div class="grid one">${shopHtml}</div>
      <details class="notes"><summary>说明（商店与材料采集注意事项）</summary><ul>${notes.map(x => `<li>${x}</li>`).join("")}</ul></details>`;
  }

  root.FE = root.FE || {};
  root.FE.views = root.FE.views || {};
  root.FE.views.renderItemsView = renderItemsView;
})(window);
