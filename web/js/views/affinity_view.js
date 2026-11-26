/* 模块 1：友好度培养视图（吃饭 perfect 组合、支援目标反查） */
(function (root) {
  const U = root.FE.utils;
  const AL = root.FE.affinityLogic;

  function renderAffinityView(data, state) {
    const D = data || { dishes: [], weights: [], goals: [], maxed: [], absent: [], pairsDone: [] };
    const summary = AL.summarizeAffinity(D);
    const filteredDishes = AL.filterDishes(D, state.affinityQuery, state.affinityOnlyPerfect);
    const matrix = AL.buildTargetDishMatrix(D);
    const lv2 = AL.listSupportTwoTargets(D);

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
      "规则：闪光 最爱 2、喜欢 1、普通 0；三人是 1+1+1 或 2+2+0 才算 perfect。讨厌这道菜的人不上桌。2+1+0 还没确认，只当备选。",
      "只有领主和还要挖的目标上桌，每个座位都要涨有用的支援；已入队的人不上桌（吃饭是为了挖角）。排序：perfect 在前 → 分高 → 闪光多 → 招募表靠前。",
      ...(D.goals || []).map(g => "分数：" + U.esc(g)),
      "支援 1 就能招的人不列（不用吃饭）。每桌主角排第一，其他领主第二。",
      "任何三个人都能一桌，不用带当前主角。还没入队的人要先送过一次礼物才请得动。",
      ...((D.pairsDone || []).length ? [`支援已经够了、不再刷：${D.pairsDone.map(([a, b]) => U.esc(U.shortName(a)) + "–" + U.esc(U.shortName(b))).join("、")}。`] : []),
      ...([...(D.maxed || []), ...(D.absent || [])].length ? [`不上桌：${[...(D.maxed || []).map(n => U.esc(n) + "（好感满了）"), ...(D.absent || []).map(n => U.esc(n) + "（不在）")].join("、")}。`] : []),
      "模块数据：meals/meal_config.json + meals/diet_tab.json；纯算法：modules/affinity/planner.py。",
    ];

    return `<p class="lede">友好度培养模块：每道菜列出三人一桌的最佳组合（perfect 优先），支持按角色或菜名筛选，并从挖角目标反查对应菜品。</p>
      <div class="filterbar">
        <input type="search" id="affQuery" data-aff-q placeholder="搜菜名或角色，比如 蕾达、糖浆炖梨、绯亚娜" value="${U.esc(state.affinityQuery || "")}" aria-label="筛选菜品或角色">
        <label class="showdone" style="margin:0"><input type="checkbox" data-aff-pf${state.affinityOnlyPerfect ? " checked" : ""}> 只看能 perfect 的菜</label>
      </div>
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
