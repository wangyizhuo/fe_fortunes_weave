/* 模块 3：路线规划视图（下一步 / 到目标级 / 回顾 / 到 Lv45 / 长线观星 / 职业选择 / 我的决定）
 * 说明区全部从 routeData.rulesMeta 动态渲染，不再硬编码会过时的规则文本。
 */
(function (root) {
  const U = root.FE.utils;
  const RL = root.FE.routeLogic;
  const CL = root.FE.commentsLogic;
  const LL = root.FE.linksLogic;
  const LONG_DEF = 5;
  const N_PTS = "<b>点数</b> = 不加权的加点总数；<b>加权分</b> = 每项加点 × 该角色的能力权重（权重在每张卡名字下面）。所有合计都同时给这两个数。";
  const notesBox = items => `<details class="notes"><summary>说明（规则和名词解释）</summary><ul>${items.map(x => `<li>${x}</li>`).join("")}</ul></details>`;
  const chip = g => `<span>${U.esc(g.includes("+") ? g : g + "+1")}</span>`;
  const vsTag = (sc, es) => {
    if (es == null) return "";
    const d = Math.round((sc - es) * 10) / 10;
    const k = d >= 2 ? "up" : d <= -2 ? "dn" : "eq";
    return `<span class="vs ${k}" title="平均运气这一级约 ${es} 分">${d >= 2 ? "好于平均" : d <= -2 ? "低于平均" : "平均"} ${U.sgn(d)}</span>`;
  };
  const dc = v => (v >= 3 ? "up" : v <= -3 ? "dn" : "eq");
  const cells = (g, mark) => g.map(v => `<td class="n ${mark && v > 0 ? "up" : ""} ${mark && v < 0 ? "dn" : ""}">${v === 0 && mark ? "" : (mark && v > 0 ? "+" + v : v)}</td>`).join("");

  function renderRouteView(view, D, state, ctx) {
    const reg = (ctx && ctx.registry) || null;
    const chLink = (n, useShort) => LL.renderEntityLink(reg, "char", n, useShort ? { label: U.shortName(n) } : undefined);
    const clsLink = n => LL.renderEntityLink(reg, "class", n);
    const clsList = (arr, sep = "、") => LL.linkifyList(reg, "class", arr, sep);
    const clsText = t => LL.linkifyClassText(reg, t);

    const CH = (D && D.chars) || [];
    const ST = (D && D.stats) || U.DEFAULT_STATS;
    const SKILLS = (D && D.skills) || [];
    const DECISIONS = (D && D.decisions) || [];
    const OPTS = (D && D.options) || {};
    const REASONS = (D && D.reasons) || {};
    const RM = (D && D.rulesMeta) || {};
    const PROPOSALS = (D && D.routeProposals) || [];
    const prog = state.prog, info = state.info, focus = state.focus, longS = state.longS;
    const routePicks = state.routePicks || {};
    const planComments = state.planComments || [];
    const commentMode = state.commentMode !== false;
    const commentDraft = state.commentDraft || null;
    const editingId = state.editingCommentId || null;
    const cmtSum = CL.summarizeComments(planComments);

    const walkOf = c => RL.walk(c, prog, info);
    const remainOf = (c, w) => RL.remain(c, w, ST);
    const verdictOf = (c, s) => RL.examVerdict(c, s, prog);
    const shotLabel = RM.shotKey ? `当前快照（${RM.shotKey}）` : "当前截图";

    function renderCommentBtn(targetId, targetLabel, btnLabel) {
      if (!commentMode) return "";
      const stat = cmtSum.byTarget[targetId];
      const badge = stat && stat.open ? ` <span class="cmt-cnt">${stat.open}</span>` : "";
      return `<button type="button" class="cmt-trig" data-cmt-open="${U.esc(targetId)}" data-cmt-label="${U.esc(targetLabel)}" title="为此项添加 Plan Mode 批注">💬 ${U.esc(btnLabel || "批注")}${badge}</button>`;
    }

    function renderCommentThread(targetId, targetLabel) {
      const list = CL.commentsForTarget(planComments, targetId, { includeResolved: true });
      const isComposing = commentDraft && commentDraft.targetId === targetId;
      if (!list.length && !isComposing) return "";
      const itemsHtml = list.map(c => {
        if (editingId === c.id) {
          return `<div class="cmt-item editing" data-cmt-id="${U.esc(c.id)}">
            ${c.quote ? `<blockquote class="cmt-quote">「${U.esc(c.quote)}」</blockquote>` : ""}
            <textarea class="cmt-input" id="cmtEditInput" data-cmt-edit-text rows="2">${U.esc(c.text)}</textarea>
            <div class="cmt-actions">
              <button type="button" class="btn pri" data-cmt-edit-save="${U.esc(c.id)}">保存修改</button>
              <button type="button" class="btn ghost" data-cmt-edit-cancel>取消</button>
            </div>
          </div>`;
        }
        const locBits = [c.viewHash || (c.section ? "#" + c.section : ""), c.anchorId ? "#" + c.anchorId : "", c.version ? "v" + c.version : ""].filter(Boolean).join(" · ");
        return `<div class="cmt-item${c.resolved ? " resolved" : ""}" data-cmt-id="${U.esc(c.id)}">
          ${c.quote ? `<blockquote class="cmt-quote">「${U.esc(c.quote)}」</blockquote>` : ""}
          <div class="cmt-text">${U.esc(c.text)}</div>
          <div class="cmt-meta">
            ${locBits ? `<span class="cmt-loc" title="${U.esc(c.xpath || "")}">${U.esc(locBits)}</span>` : ""}
            <span>${c.at ? U.esc(c.at.slice(5, 16).replace("T", " ")) : ""}</span>
            <button type="button" class="cmt-act" data-cmt-resolve="${U.esc(c.id)}">${c.resolved ? "↺ 重新打开" : "✓ 标为已解决"}</button>
            <button type="button" class="cmt-act" data-cmt-edit="${U.esc(c.id)}">编辑</button>
            <button type="button" class="cmt-act dn" data-cmt-del="${U.esc(c.id)}">删除</button>
          </div>
        </div>`;
      }).join("");

      const composerHtml = isComposing ? `
        <div class="cmt-composer" data-cmt-box>
          <div class="cmt-comp-head">
            <b>💬 Plan Mode 批注 · ${U.esc(commentDraft.targetLabel || targetLabel)}</b>
            <button type="button" class="cmt-act" data-cmt-cancel>关闭</button>
          </div>
          ${commentDraft.anchorId || commentDraft.xpath ? `<div class="hint" style="font-family:var(--mono);font-size:11px">定位：${U.esc(commentDraft.viewHash || ("#" + state.view))}${commentDraft.anchorId ? ` · #${U.esc(commentDraft.anchorId)}` : ""}${commentDraft.xpath ? ` · ${U.esc(commentDraft.xpath)}` : ""}${commentDraft.version ? ` · v${U.esc(commentDraft.version)}` : ""}</div>` : ""}
          ${commentDraft.quote ? `<blockquote class="cmt-quote">选中内容：「${U.esc(commentDraft.quote)}」</blockquote>` : ""}
          <textarea class="cmt-input" id="cmtDraftInput" data-cmt-draft-text rows="2" placeholder="写下你的审阅意见、改法或 case by case 决定（Ctrl/Cmd+Enter 保存）…">${U.esc(commentDraft.text || "")}</textarea>
          <div class="cmt-actions">
            <button type="button" class="btn pri" data-cmt-save>保存批注</button>
            <button type="button" class="btn ghost" data-cmt-cancel>取消</button>
          </div>
        </div>
      ` : "";

      return `<div class="cmt-thread">${itemsHtml}${composerHtml}</div>`;
    }

    function renderPlanModeBar() {
      const drawerItems = planComments.length
        ? planComments.map(c => {
            const locBits = [c.viewHash || (c.section ? "#" + c.section : ""), c.anchorId ? "#" + c.anchorId : "", c.xpath || "", c.version ? "v" + c.version : ""].filter(Boolean).join(" · ");
            return `<div class="cmt-drawer-row${c.resolved ? " resolved" : ""}">
              <div class="cmt-dr-top">
                <span class="cat-pill">${U.esc(c.targetLabel)}</span>
                <span class="hint">${c.at ? U.esc(c.at.slice(5, 16).replace("T", " ")) : ""}</span>
                <span class="r">
                  <button type="button" class="cmt-act" data-cmt-resolve="${U.esc(c.id)}">${c.resolved ? "↺ 重开" : "✓ 已解决"}</button>
                  <button type="button" class="cmt-act dn" data-cmt-del="${U.esc(c.id)}">删除</button>
                </span>
              </div>
              ${locBits ? `<div class="hint" style="font-family:var(--mono);font-size:11px;word-break:break-all">${U.esc(locBits)}</div>` : ""}
              ${c.quote ? `<blockquote class="cmt-quote">「${U.esc(c.quote)}」</blockquote>` : ""}
              <div class="cmt-text">${U.esc(c.text)}</div>
            </div>`;
          }).join("")
        : `<p class="hint" style="margin:4px 0">还没有批注。点击任意角色/方案/规则上的「💬 批注」，或者直接<b>划选任意文字</b>即可像 Plan Mode 一样就地批注。</p>`;

      return `<section class="pm-bar${commentMode ? " on" : ""}" aria-label="Plan Mode 批注工具栏">
        <div class="pm-row">
          <button type="button" class="pill${commentMode ? " on" : ""}" data-pm-toggle>💬 Plan Mode 批注：${commentMode ? "已开启" : "已关闭"}</button>
          <button type="button" class="pill${state.commentDrawerOpen ? " on" : ""}" data-pm-drawer>📋 批注清单（待处理 ${cmtSum.open}${cmtSum.resolved ? ` / 已解决 ${cmtSum.resolved}` : ""}）</button>
          <button type="button" class="btn pri" data-pm-export>复制批注 + 路线选择给 AI</button>
          ${commentMode ? `<button type="button" class="btn ghost" data-cmt-open="rules:global" data-cmt-label="全局路线规划规则">+ 全局批注</button>` : ""}
          ${planComments.length ? `<button type="button" class="btn ghost" data-pm-clear>清空批注</button>` : ""}
        </div>
        ${commentMode ? `<div class="pm-tip">💡 Plan Mode 已开启：点击任意卡片/候选方案的 <b>「💬 批注」</b>，或直接<b>鼠标划选任意文字</b>即可弹窗批注；所有批注自动保存在本地浏览器，点右侧按钮一键导出发给 AI 执行修改。</div>` : ""}
        ${state.copyFeedback ? `<div class="ok" style="font-size:13px;margin-top:6px">${U.esc(state.copyFeedback)}</div>` : ""}
        ${state.commentDrawerOpen ? `<div class="pm-drawer">${drawerItems}</div>` : ""}
        ${renderCommentThread("rules:global", "全局路线规划规则")}
      </section>`;
    }

    function fmtSignedStats(g) {
      const parts = [];
      for (let i = 0; i < ST.length; i++) {
        const v = (g || [])[i] || 0;
        if (!v) continue;
        parts.push(`<span class="sdiff ${v > 0 ? "up" : "dn"}">${U.esc(ST[i])}${v > 0 ? "+" + v : v}</span>`);
      }
      return parts.length ? parts.join(" ") : `<span class="sdiff eq">相同</span>`;
    }

    function fmtSignedNum(val, unit = "", invertColor = false) {
      if (val == null || val === 0) return `<span>0${U.esc(unit)}</span>`;
      const good = invertColor ? val < 0 : val > 0;
      const cls = good ? "up" : "dn";
      return `<b class="${cls}">${U.sgn(val)}${U.esc(unit)}</b>`;
    }

    function timingBox(e) {
      const t = e.timing || [];
      if (!t.length) return `<br><span class="hint">考试时机：窗口里没有别的乱数能考过，只能在这一级考。</span>`;
      // t 中的数值为「现在 − 改后」，界面展示「改去该级的变化 = 改后 − 现在」：更差标红为负、更好标绿为正
      const neg = x => ({ pts: -(x.pts || 0), w: -(x.w || 0) });
      const fmtPair = raw => {
        const x = neg(raw);
        const cls = x.w > 0 ? "up" : x.w < 0 ? "dn" : x.pts > 0 ? "up" : x.pts < 0 ? "dn" : "";
        return `<span class="${cls}">${U.sgn(x.pts)} 点 / ${U.sgn(x.w)} 分</span>`;
      };
      const hasBetter = t.some(x => x.total.w < 0 || (x.total.w === 0 && x.total.pts < 0));
      const explainLines = (t[0].explainAlt && t[0].explainAlt.length) ? t[0].explainAlt : (t[0].explain || []);
      return `<details class="more"><summary>换到别的乱数考（${t.length} 个能考过）：${hasBetter ? "存在比现在更高的时机（绿更好 / 红更差）" : "改去其他级都不如现在（均为负或持平）"}</summary>
        <div class="scroll"><table><tr><th>改在</th><th class="n">判定值 / 成功率</th><th class="n">① 考试用掉的乱数</th><th class="n">② 用不同职业升级</th><th class="n">③ 转职保底</th><th class="n">改去该级变化<br><small>（改后 − 现在）</small></th><th class="n">金币变化</th></tr>
        ${t.map(x => {
          const altTot = neg(x.total);
          const altGold = -(x.gold || 0);
          const totCls = altTot.w > 0 ? "up" : altTot.w < 0 ? "dn" : altTot.pts > 0 ? "up" : altTot.pts < 0 ? "dn" : "";
          return `<tr><td>Lv${x.lv}（第 ${x.step + 1} 个乱数）</td><td class="n">${x.roll}% / ${x.pct ?? "—"}%</td><td class="n">${fmtPair(x.exam)}</td><td class="n">${fmtPair(x.cls)}</td><td class="n">${fmtPair(x.floor)}</td><td class="n ${totCls}"><b>${U.sgn(altTot.pts)} 点 / ${U.sgn(altTot.w)} 分</b></td><td class="n">${fmtSignedNum(altGold, "G", true)}</td></tr>`;
        }).join("")}</table></div>
        <p class="hint">${explainLines.map(U.esc).join("<br>")}</p></details>`;
    }

    function trainBox(c, w) {
      const done = new Set(w.rows.filter(r => r.done).map(r => r.s.key));
      const todo = (c.trainPlan || []).filter(t => !done.has(t.key));
      if (!todo.length) return "";
      return `<div class="sec"><h4>要练的技能</h4><ul class="txt">${todo.map(t => `<li>🎯 <b>Lv${t.lv}</b> 考${clsLink(t.cls)}之前练好：${U.esc(t.train.join("、"))}（共 ${t.ranks} 段；训练场、指南书、委托都不涨人物经验，不影响种子）</li>`).join("")}</ul></div>`;
    }

    function renderStrengthBadge(obj) {
      if (!obj || !obj.strengthTier) return "";
      const tip = [
        `综合强度 ${obj.strengthTier}`,
        obj.pserTier ? `憨色 ${obj.pserTier}` : "",
        obj.role || "",
        obj.priorityNote || "",
      ].filter(Boolean).join(" · ");
      return `<span class="ctier ctier-${U.esc(obj.strengthTier)}" title="${U.esc(tip)}">${U.esc(obj.strengthTier)}</span>`;
    }

    function renderPTierBadge(tier, note) {
      if (!tier) return "";
      const cls = tier === "P0" ? "r1" : tier === "P1" ? "r2" : "r3";
      return `<span class="rec ${cls}"${note ? ` title="${U.esc(note)}"` : ""}>${U.esc(tier)}</span>`;
    }

    function head(c, w, right) {
      const n = w.rows.filter(r => r.done).length;
      const cmtBtn = renderCommentBtn("route:" + c.name, `${c.name}（路线规划）`, "批注");
      const isLord = Boolean(c.isLord || (RM.currentLord && c.name === RM.currentLord));
      return `<div class="ch" data-cmt-target="route:${U.esc(c.name)}" data-cmt-label="${U.esc(c.name)}（路线规划）"><div class="ct"><h3>${isLord ? '<span title="当前路线主角">★</span> ' : ""}${chLink(c.name)}</h3>${renderPTierBadge(c.tier, c.priorityNote)}${renderStrengthBadge(c)}<span class="lv">Lv${w.ci.level ?? "?"} ${clsLink(w.cur || "")}</span><span class="r">${right} ${cmtBtn}</span></div>
        ${c.steps.length ? `<div class="meter" title="完成 ${n} / ${c.steps.length}"><i style="width:${100 * n / c.steps.length}%"></i></div>` : ""}
        ${c.weights ? `<div class="wts" title="能力权重，加权分 = 每项加点 × 权重">${ST.map((k, i) => `<span class="w${c.weights[i]}">${k}<b>${c.weights[i]}</b></span>`).join("")}</div>` : ""}
        ${c.priorityNote ? `<p class="intro note2">📌 <b>路线优先级：</b>${U.esc(c.priorityNote)}</p>` : ""}
        ${c.text ? `<p class="intro">${U.esc(c.text.intro)}</p>` : ""}${c.text && c.text.note ? `<p class="intro note2">${U.esc(c.text.note)}</p>` : ""}${c.guide ? `<p class="intro note2"><b>攻略评价 ${U.esc(c.guide.tier)}</b>（憨色 Ver1.0）：${U.esc(c.guide.t)}</p>` : ""}
        ${renderCommentThread("route:" + c.name, `${c.name}（路线规划）`)}</div>`;
    }

    function renderStatDiffChips(diffVec, isBaseline) {
      if (isBaseline) return `<span class="hint">基准方案（对照原点）</span>`;
      const parts = [];
      for (let i = 0; i < ST.length; i++) {
        const v = (diffVec || [])[i] || 0;
        if (!v) continue;
        parts.push(`<span class="sdiff ${v > 0 ? "up" : "dn"}">${U.esc(ST[i])}${v > 0 ? "+" + v : v}</span>`);
      }
      return parts.length ? parts.join("") : `<span class="sdiff eq">9 项能力完全相同</span>`;
    }

    function renderProposalOptionsBody(pr, r, radioPrefix) {
      const optHtml = (pr.options || []).map(opt => {
        const picked = r.optionId === opt.id;
        const d = opt.diffVsBaseline || {};
        const isBase = opt.id === "old_baseline";
        const slHtml = (opt.slWarnings || []).map(w =>
          `<div class="slwarn">⚠️ <b>需提前 NS Online S/L 实测</b>：${U.esc(w.message)}</div>`
        ).join("");

        const examLine = (opt.exams || []).map(e => {
          const curP = e.curPct != null ? e.curPct : e.pct;
          const pctStr = curP != null ? `当前预估 ${curP}%` : "—";
          const skStr = e.skillSummary ? `｜当前：${U.esc(e.skillSummary)}` : "";
          const minStr = e.minReqText ? `｜<span class="changed">🎯 ${U.esc(e.minReqText)}</span>` : "";
          const flStr = e.promoFloor && e.promoFloor.length
            ? ` · <span class="ok">转职保底：${U.esc(e.promoFloor.join("、"))}</span>`
            : ` · <span class="hint">无转职保底</span>`;
          return `<div>Lv${e.lv}(第${e.step}步) <b>${clsLink(e.cls)}</b>（判定 ${e.roll}% / ${pctStr}${flStr}${skStr}${minStr}）</div>`;
        }).join("") || "不考新职业";

        const deltaBadge = (label, val, unit, invertColor) => {
          if (isBase) return `<span>${label} <b>${val}${unit || ""}</b></span>`;
          const sgn = val > 0 ? "+" + val : String(val);
          const good = invertColor ? val < 0 : val > 0;
          const bad = invertColor ? val > 0 : val < 0;
          const cls = good ? "up" : bad ? "dn" : "";
          return `<span>${label} <b class="${cls}">${sgn}${unit || ""}</b></span>`;
        };

        const metricsHtml = isBase
          ? `<div class="rp-metrics">
              <span>净值 <b>${opt.net}</b></span>
              <span>总点数 <b>${opt.rawPoints}</b></span>
              <span>升级分 <b>${opt.statWeighted}</b></span>
              <span>转职保底 <b>${opt.promoFloorWeighted}</b></span>
              <span>金币 <b>${opt.gold}G</b></span>
              <span>训练 <b>${opt.trainRanks} 段</b></span>
              <span>精通 <b>${opt.masteryLevels} 级</b></span>
            </div>`
          : `<div class="rp-metrics">
              <span>净值 <b>${opt.net}</b> (${deltaBadge("Δ", d.net, "", false)})</span>
              <span>点数 <b>${opt.rawPoints}</b> (${deltaBadge("Δ", d.pts, "", false)})</span>
              <span>升级分 <b>${opt.statWeighted}</b> (${deltaBadge("Δ", d.statW, "", false)})</span>
              <span>转职保底 <b>${opt.promoFloorWeighted}</b> (${deltaBadge("Δ", d.promoFloorW, "", false)})</span>
              <span>金币 <b>${opt.gold}G</b> (${deltaBadge("Δ", d.gold, "G", true)})</span>
              <span>训练 <b>${opt.trainRanks} 段</b> (${deltaBadge("Δ", d.trainRanks, "段", true)})</span>
              <span>精通 <b>${opt.masteryLevels} 级</b> (${deltaBadge("Δ", d.masteryLevels, "级", false)})</span>
            </div>`;

        const promoHtml = (opt.promoFloorDetails || []).length
          ? `<div class="hint">转职保底永久补足：<b class="ok">${U.esc(opt.promoFloorDetails.join("、"))}</b></div>`
          : `<div class="hint">转职保底：<b>无转职保底</b>（裸属性已全部达到目标职业底线）</div>`;

        const marginalsHtml = (opt.marginals || []).filter(m => !m.isRequired || m.usedLevels === 0).length
          ? `<div class="rp-marg">${opt.marginals.map(m =>
              `<div><span class="cat-pill">${m.isRequired ? "必考" : "额外"} ${clsLink(m.cls)}（升级用 ${m.usedLevels} 级）</span> 边际能力差：<b>${U.esc(m.statDiffText)}</b>｜Δ净值 ${U.sgn(m.deltaNet)}｜Δ金币 ${U.sgn(m.deltaGold)}G｜Δ训练 ${U.sgn(m.deltaTrainRanks)} 段</div>`
            ).join("")}</div>`
          : "";

        const finalVec = (opt.statVec || []).map((v, i) => `${ST[i]}+${v}`).join(" ");
        const optTid = `opt:${pr.name}:${opt.id}`;
        const optLbl = `${pr.name}（${pr.tier}）· ${opt.title}`;

        return `<div class="rp-opt-wrap" data-cmt-target="${U.esc(optTid)}" data-cmt-label="${U.esc(optLbl)}">
          <label class="rp-opt${picked ? " on" : ""}">
            <div class="rp-opt-head">
              <input type="radio" name="${U.esc(radioPrefix || "rpick-")}${U.esc(U.slug({ name: pr.name }))}" value="${U.esc(opt.id)}" data-rpick="${U.esc(pr.name)}"${picked ? " checked" : ""}>
              <b>${U.esc(opt.title)}</b>
              <span class="cat-pill">${U.esc(opt.tag)}</span>
              <span class="r">${renderCommentBtn(optTid, optLbl, "批注此方案")}</span>
            </div>
            <div class="rp-opt-body">
              ${slHtml}
              <div class="rp-sdiff"><span class="lab">相对旧路线 9 项能力差</span><div class="sdiff-list">${renderStatDiffChips(d.statDiff, isBase)}</div></div>
              ${metricsHtml}
              ${promoHtml}
              <div class="hint">考试安排：${examLine}${opt.skips ? `；纯跳过 ${opt.skips} 次` : ""}</div>
              <div class="hint">窗口总增量（Lv${pr.level}→Lv${opt.endLevel}）：${U.esc(finalVec)}</div>
              ${marginalsHtml}
            </div>
          </label>
          ${renderCommentThread(optTid, optLbl)}
        </div>`;
      }).join("");

      return `${optHtml}
        <div class="rp-note-row">
          <input type="text" class="rp-note" data-rpick-note="${U.esc(pr.name)}" placeholder="可选简短备注（例如 S/L 实测结果、个人偏好）" value="${U.esc(r.note || "")}">
          ${r.source === "user" ? `<button type="button" class="btn ghost" data-rpick-clear="${U.esc(pr.name)}">恢复默认</button>` : ""}
        </div>`;
    }

    function floorBadgeOf(charName, clsName, explicitFloor) {
      let fl = explicitFloor;
      if (!fl) {
        const o = OPTS[charName];
        const hit = o && (o.options || []).find(x => x.cls === clsName);
        fl = hit ? hit.floor : null;
      }
      if (fl && fl.length) return `<span class="ok">转职保底：${U.esc(fl.join("、"))}</span>`;
      return `<span class="hint">无转职保底</span>`;
    }

    function optsHtml(c, s, row, idp, w) {
      const name = idp + "o-" + U.keyOf(c, s);
      const groups = s.opts.length ? s.opts : (s.seenCls ? [{ classes: [s.seenCls], owned: [true], gains: s.gains, cnt: s.cnt, score: s.score }] : []);
      const baseG = !row.r.exam
        ? (groups.find(g => g.classes.includes(row.choice) || RL.resultOf(s, row.choice) === g) || null)
        : null;
      const ownedNow = new Set(row.ownedBefore || []);
      const earlyBtns = [];
      const seenEarly = new Set();

      const o = groups.map(g => {
        const val = g.classes.includes(s.cls) ? s.cls : (g.classes.find((x, i) => g.owned[i] || ownedNow.has(x)) || g.classes[0]);
        const have = s.src === "record" ? g.classes : g.classes.filter((x, i) => g.owned[i] || ownedNow.has(x));
        const need = s.src === "record" ? [] : g.classes.filter((x, i) => !g.owned[i] && !ownedNow.has(x));
        for (const nc of need) {
          if (seenEarly.has(nc)) continue;
          seenEarly.add(nc);
          const slot = w ? RL.findEarlyExamSlot(c, w, s.key, nc) : null;
          if (slot) {
            earlyBtns.push(`<button type="button" class="btn ghost" data-early-exam-key="${U.esc(slot.key)}" data-early-exam-cls="${U.esc(nc)}" data-use-key="${U.esc(s.key)}" title="把前面较差的乱数改为考${U.esc(nc)}，并把这一步改为用${U.esc(nc)}升级"><span>🎯 在前面最差乱数 Lv${slot.lv}（${slot.score}分，判定 ${slot.roll}%${slot.pct != null ? ` / 估 ${slot.pct}%` : ""}）提前考 <b>${U.esc(nc)}</b>，这里改用 ${U.esc(nc)}</span></button>`);
          }
        }
        const label = clsList(have, " / ") + (need.length ? `<span class="need">${have.length ? "　" : ""}要先考试：${clsList(need, " ")}</span>` : "");
        const on = row.choice === val || (!row.r.exam && row.r.classes && RL.resultOf(s, val) === row.r);
        let gainBody = "";
        let numBody = `${g.cnt}点 · ${g.score}分`;
        if (on) {
          gainBody = `<span class="tag ok">预选</span> ${U.esc(g.gains.join(" ") || "—")}`;
        } else if (baseG) {
          const df = RL.diffOptionGains(g.gains, baseG.gains, ST);
          const chips = df.diffItems.length
            ? df.diffItems.map(x => `<span class="sdiff ${x.delta > 0 ? "up" : "dn"}">${U.esc(x.stat)}${x.delta > 0 ? "+" : ""}${x.delta}</span>`).join(" ")
            : `<span class="sdiff eq">与预选相同</span>`;
          gainBody = `<span title="绝对加点：${U.esc(g.gains.join(" ") || "—")}（${g.cnt}点·${g.score}分）">${chips}</span>`;
          const dCnt = g.cnt - baseG.cnt;
          const dSc = g.score - baseG.score;
          numBody = `<span class="${dSc > 0 ? "ok" : dSc < 0 ? "bad" : ""}">${U.sgn(dCnt)}点 · ${U.sgn(dSc)}分</span>`;
        } else {
          gainBody = U.esc(g.gains.join(" ") || "—");
        }
        return `<label class="opt"><input type="radio" name="${name}" value="${U.esc(val)}" data-f="pick"${have.length ? "" : ' data-need="1"'}${on ? " checked" : ""}><span><span class="oc">${label}</span>　${gainBody}</span><span class="on">${numBody}</span></label>`;
      }).join("");

      const curExamCls = row.r.exam ? (row.r.examCls || "") : "";
      const passExams = RL.passableExamChoices(s, row.ownedBefore);
      const examOpts = passExams.map(e => {
        const val = (s.exam && s.cls === e.cls) ? "exam" : ("exam:" + e.cls);
        const checked = row.r.exam && curExamCls === e.cls;
        return `<label class="opt"><input type="radio" name="${name}" value="${U.esc(val)}" data-f="pick"${checked ? " checked" : ""}><span><span class="oc">考试（到 ${clsLink(e.cls)}）</span>　这一步不升级（判定值 ${s.roll ?? "—"}%${e.pct != null ? ` / 估 ${e.pct}%` : ""} · ${floorBadgeOf(c.name, e.cls, s.exam && s.cls === e.cls ? s.floor : null)}）</span><span class="on">考试</span></label>`;
      }).join("");
      const examFold = passExams.length
        ? `<details class="exam-pick-fold"${row.r.exam && curExamCls ? " open" : ""}><summary>${row.r.exam && curExamCls ? `当前选择：考试（到 ${U.esc(curExamCls)}）· 点此改考其他职业（共 ${passExams.length} 个可考）` : `🎯 改为考试（不升级 · 展开 ${passExams.length} 个可考职业）`}</summary><div class="exam-pick-list">${examOpts}</div></details>`
        : "";
      const skipVal = (s.exam && s.cls) ? "exam:" : "exam";
      const skipChecked = row.r.exam && !curExamCls;
      const skipOpt = `<label class="opt"><input type="radio" name="${name}" value="${U.esc(skipVal)}" data-f="pick"${skipChecked ? " checked" : ""}><span><span class="oc">跳过</span>　这一步不升级${s.roll != null ? `（判定值 ${s.roll}%）` : ""}</span><span class="on"></span></label>`;

      // 对规划目标职业在本步考不过的情况给出明确提示（如努蒂奴 Lv19 重装步兵 估 50% ≤ 判定 79.35%）
      const targetSet = new Set(c.targets || []);
      const failTargets = ((s.routes && s.routes.exams) || [])
        .filter(e => e && e.pass === false && targetSet.has(e.cls) && !ownedNow.has(e.cls));
      const failHintHtml = failTargets.length
        ? `<div class="hint" style="margin-top:4px">本步考不过：${failTargets.map(e => `<b>${clsLink(e.cls)}</b>（估 ${e.pct ?? "—"}% ≤ 判定 ${s.roll ?? "—"}% · ${floorBadgeOf(c.name, e.cls)}）`).join("、")}</div>`
        : "";

      const earlyHtml = earlyBtns.length
        ? `<div style="display:flex;flex-wrap:wrap;gap:6px;margin-top:6px">${earlyBtns.join("")}</div>`
        : "";
      const curVal = row.r.exam ? (curExamCls ? ((s.exam && s.cls === curExamCls) ? "exam" : ("exam:" + curExamCls)) : skipVal) : row.choice;
      return `<div class="opts" role="radiogroup" aria-label="这一步的选择">${o}${skipOpt}${examFold}</div>${failHintHtml}${earlyHtml}<button type="button" class="btn pri" data-apply data-cur="${U.esc(curVal)}" data-lv="${s.exam ? "这一步" : `Lv${row.frm}→${row.to}`}" style="display:none">确认更改</button>`;
    }

    function examBox(c, s) {
      const v = verdictOf(c, s), n = RL.examName(s);
      const verdict = v.pass == null ? "" : v.pass ? `<span class="ok">✓ 能过${n ? "，拿到" + clsLink(n) : ""}</span>`
        : `<span class="bad">✗ 会失败${n ? "，拿不到" + clsLink(n) + "，后面用它的步骤要改" : "，没关系，只当跳过"}</span>`;
      const curP = s.curPct != null ? s.curPct : s.pct;
      const skHint = s.skillSummary ? `（当前：${U.esc(s.skillSummary)}）` : "";
      const minHint = s.minReqText ? `<div class="changed" style="margin-top:3px">🎯 ${U.esc(s.minReqText)}</div>` : "";
      return `<div class="exambox"><div>判定值 <b>${s.roll}%</b>：游戏里显示的成功率要<b>高于</b>它才能过。过不过种子都前进一步。${curP != null ? ` 按${shotLabel}当前技能和考试等级预估显示 <b>${curP}%</b>${skHint}${curP > s.roll ? "，当前能过" : "，当前过不了"}。` : ""}${n ? ` · ${floorBadgeOf(c.name, n, s.floor)}` : ""}</div>${minHint}
        <div><label>游戏显示 <input type="number" min="0" max="100" step="0.01" data-f="chance" id="ch-${U.keyOf(c, s)}" value="${v.ch ?? ""}" aria-label="游戏显示的考试成功率">%</label> ${verdict}</div></div>`;
    }

    function routesBox(c, w, row) {
      const s = row.s, rt = s.routes;
      if (!rt || !s.opts || !s.opts.length) return "";
      const idx = w.rows.indexOf(row);
      let prev = w.cur;
      for (let i = idx - 1; i >= 0; i--) { const x = w.rows[i]; if (!x.r.exam) { prev = x.choice; break; } }
      const own = s.opts.filter(g => g.owned.some(Boolean));
      const g1 = own.find(g => g.classes.includes(prev));
      const g2 = own.filter(g => g !== g1).sort((a, b) => b.score - a.score)[0];
      const best = Math.max(...own.map(g => g.score));
      const pick = row.r.exam ? (RL.examName(s) ? 3 : 4) : (g1 && g1.classes.includes(row.choice) ? 1 : 2);
      const prob = e => e.pct == null ? `成功率未知（游戏显示要高于 ${rt.roll}% 才过）`
        : `成功率 <b>${e.pct}%</b>（估计）· 这个种子<b class="${e.pass ? "ok" : "bad"}">${e.pass ? "过" : "不过"}</b>`;
      const gline = g => g ? `${U.esc(g.gains.join(" ") || "—")}（${U.PW(g.cnt, g.score)}）` : "—";
      const pn = RL.examName(s) || "";
      const ex = [...rt.exams.filter(e => e.cls === pn), ...rt.exams.filter(e => e.cls !== pn)];
      const basic = rt.exams.find(e => e.tier === "初级");
      const gap = Math.round((rt.avg15 - best) * 10) / 10;
      const tierKey = c.tier === "P0" ? "P0" : c.tier === "P2" ? "P2" : "other";
      const sr = (RM.skipRule && RM.skipRule[tierKey]) || null;
      const ruleTxt = sr ? `（本档跳过线：≤${sr.cap} 分${sr.or ? " 或 " : " 且 "}低于后 15 级平均 ≥${Math.round(sr.pct * 100)}%）` : "";
      const li = (n, t, body) => `<li class="${pick === n ? "pk" : ""}"><span class="rn">${n}</span><div><b>${t}</b>${pick === n ? ' <span class="tag">规划</span>' : ""}<div>${body}</div></div></li>`;
      return `<details class="more routes"${row === w.rows.find(r => !r.done) ? " open" : ""}><summary>这一级的四种走法</summary><ol class="rts">
        ${li(1, `正常（${prev ? clsLink(prev) : "现在的职业"}）`, g1 ? gline(g1) : "现在的职业不在已有职业里")}
        ${li(2, "转职（换已有职业再升级）", g2 ? `${clsList(g2.classes.filter((x, i) => g2.owned[i]), " / ")}：${gline(g2)}${g1 && g2.score <= g1.score ? "，不比正常好" : ""}` : "没有别的已有职业")}
        ${li(3, "考试（考新职业，这一级不升级）", ex.length ? ex.map(e => `${e.cls === pn ? "<b>" : ""}${clsLink(e.cls)}${e.cls === pn ? "</b>" : ""}（${U.esc(e.tier)}）：${prob(e)} · ${floorBadgeOf(c.name, e.cls)}`).join("<br>") : "没有能考的新职业")}
        ${li(4, "跳过（300G 初级手形，这一级不升级）", `${basic ? `用${clsLink(basic.cls)}的考试：${prob(basic)}，过不过都行` : `用任意一场初级考试跳过：判定值 ${rt.roll}%，过不过都行`}<br>这一级最高 ${best} 分，未来 15 级平均 ${rt.avg15}（10 级 ${rt.avg10}），${gap > 0 ? `低 ${gap} 分（${Math.round(100 * gap / rt.avg15)}%）` : `高 ${-gap} 分`}${ruleTxt}`)}
      </ol></details>`;
    }

    function stateHtml(c, w) {
      const ci = w.ci, all = [...new Set([...c.owned, ...c.classChoices])];
      return `<details class="more"><summary>更新等级、职业、技能</summary><div class="state">
        <label>当前 Lv <input type="number" min="1" max="99" data-f="level" id="lv-${U.slug(c)}" value="${ci.level ?? ""}" style="width:64px"></label>
        <div><h4>已有职业</h4><div class="ownd">${all.map(k => `<label><input type="checkbox" data-f="owned" value="${U.esc(k)}"${ci.owned.includes(k) ? " checked" : ""}>${U.esc(k)}</label>`).join("")}</div></div>
        <div><h4>技能等级</h4><div class="skg">${SKILLS.map(k => `<label>${U.esc(k)}<select data-f="skill" data-k="${U.esc(k)}" id="sk-${U.slug(c)}-${U.esc(k)}"><option value="">—</option>${U.RANKS.map(r => `<option${ci.skills[k] === r ? " selected" : ""}>${r}</option>`).join("")}</select></label>`).join("")}</div></div>
      </div></details>`;
    }

    // ---------- 1. 下一步 ----------
    function viewNext() {
      const visibleChars = RL.sortCharsByTier(CH.filter(c => !focus || U.slug(c) === focus), RM.currentLord);
      const summaryRows = RL.summarizeNextActions(visibleChars, prog, info);

      const stop = [], go = [], alertRows = [];
      for (const c of visibleChars) {
        const w = walkOf(c), nx = w.rows.filter(r => !r.done);
        if (!nx.length) continue;
        const a = `<a href="#next" data-go="${U.slug(c)}">${U.esc(U.shortName(c.name))}</a>`;
        const first = nx[0], s = first.s;
        if (first.r.exam) {
          const n = RL.examName(s), v = verdictOf(c, s);
          stop.push([n ? "exam" : "skip", a, n ? `先考<b>${clsLink(n)}</b>（判定值 ${s.roll}%${s.pct != null ? `，估计显示 ${s.pct}%` : ""}）` : `先<b>跳过</b>一级（用任意一场初级考试，判定值 ${s.roll}%，过不过都行）`]);
          if (v.pass === false && n) alertRows.push(["bad", `${a}：考${clsLink(n)}会失败（游戏 ${v.ch}% ≤ 判定值 ${s.roll}%）。先把技能练上去再考。`]);
          else alertRows.push(["warn", `${a}：先${n ? "考试（到 " + clsLink(n) + "）" : "跳过"}，做完再升级。先升级的话种子会错位。`]);
        } else if (first.missing) {
          stop.push(["miss", a, `要用<b>${clsLink(first.choice)}</b>，但还没考到，先考`]);
        } else if (w.cur && first.choice !== w.cur) {
          stop.push(["cls", a, `先转职 ${clsLink(w.cur)} → <b>${clsLink(first.choice)}</b>，再升 Lv${first.frm}→${first.to}`]);
        } else {
          go.push(`${a} 用${clsText(RL.eqName(first))}升 Lv${first.frm}→${first.to}`);
        }
        const miss = nx.find(r => r.missing);
        if (miss) alertRows.push(["bad", `${a}：Lv${miss.frm}→${miss.to} 要用${clsLink(miss.choice)}，但前面没有考到它（或那场考试估计过不了）。`]);
        for (const row of nx.slice(0, 4)) {
          if (!row.r.exam || !RL.examName(row.s)) continue;
          const v = verdictOf(c, row.s);
          if (v.pass == null && row.s.pct != null && row.s.pct < 100 && row.s.roll >= row.s.pct - 20) {
            alertRows.push([row.s.roll >= row.s.pct ? "bad" : "warn", `${a}：${clsLink(row.s.cls)} 判定值 ${row.s.roll}%，估计显示 ${row.s.pct}%${row.s.roll >= row.s.pct ? "，过不了" : "，很险"}。`]);
          }
        }
      }
      if (!alertRows.length) alertRows.push(["ok", "最近几步没有要特别注意的。"]);

      const fmtImmediate = im => {
        if (im.kind === "exam") return `<span class="sev warn">先考试</span> <b>Lv${im.lv} 考 ${clsLink(im.cls)}</b>${im.roll != null ? `<span class="next-sub">判定 ${im.roll}%${im.pct != null ? ` / 估 ${im.pct}%` : ""}</span>` : ""}`;
        if (im.kind === "skip") return `<span class="sev warn">先跳过</span> <b>Lv${im.lv} 跳过</b>${im.roll != null ? `<span class="next-sub">任意初级考试（判定 ${im.roll}%）</span>` : ""}`;
        if (im.kind === "switch") return `<span class="sev ok">先转职</span> <b>${clsLink(im.fromCls)} → ${clsLink(im.cls)}</b><span class="next-sub">转完升 Lv${im.lv}→${im.to}</span>`;
        if (im.kind === "missing") return `<span class="sev bad">缺职业</span> <b>需先考 ${clsLink(im.cls)}</b><span class="next-sub">用于 Lv${im.lv}→${im.to}</span>`;
        if (im.kind === "level") return `<span class="sev ok">直升</span> <b>Lv${im.lv}→${im.to}</b>（${clsLink(im.cls)}）`;
        return `<span class="hint">全部完成</span>`;
      };

      const fmtStopAction = st => {
        if (!st) return "";
        if (st.kind === "exam") {
          return `<span class="cat-pill">考试</span><b>Lv${st.lv} 考 ${clsLink(st.cls)}</b>${st.roll != null ? ` <small class="hint">判定${st.roll}%${st.pct != null ? `/估${st.pct}%` : ""}</small>` : ""}`;
        }
        if (st.kind === "skip") {
          return `<span class="cat-pill">跳过</span><b>Lv${st.lv} 跳过</b>${st.roll != null ? ` <small class="hint">判定${st.roll}%（任意初级考试）</small>` : ""}`;
        }
        if (st.kind === "switch") {
          return `<span class="cat-pill">转职</span><b>Lv${st.lv}→${st.to}</b> ${clsLink(st.fromCls)}→<b>${clsLink(st.toCls)}</b>`;
        }
        if (st.kind === "missing") {
          return `<span class="sev bad">缺职业</span> <b>Lv${st.lv} 需先考 ${clsLink(st.cls)}</b>`;
        }
        return "";
      };

      const fmtNextStop = row => {
        const st = row.nextStop;
        if (!st) {
          return `<span class="ok">✅ 全程用 ${row.curClass ? clsLink(row.curClass) : "原职业"} 直升到 Lv${row.endLevel ?? "?"}</span><span class="next-sub">中间无需停下换职、考试或跳过</span>`;
        }
        const actionHtml = fmtStopAction(st);
        if (st.stepsAway === 0) {
          const fol = row.followingStop;
          const folHtml = fol
            ? `<div class="next-sub">完成本次后，下一次停下：${fol.kind === "exam" ? `Lv${fol.lv} 考 ${U.esc(fol.cls)}` : fol.kind === "skip" ? `Lv${fol.lv} 跳过` : fol.kind === "switch" ? `Lv${fol.lv} 换 ${U.esc(fol.toCls)}` : `Lv${fol.lv} 缺 ${U.esc(fol.cls)}`}</div>`
            : "";
          return `<div class="next-step-line"><span class="sev warn">立刻停下</span> <b>Lv${st.lv}</b> → ${actionHtml}</div>${folHtml}`;
        }
        return `<div class="next-step-line"><span class="sev ok">直升 ${st.stepsAway} 级</span> <b>到 Lv${st.lv} 停下</b>（先用 ${row.curClass ? clsLink(row.curClass) : "原职业"} 升级）</div><div class="next-step-line">→ ${actionHtml}</div>`;
      };

      const fmtTrain = row => {
        if (!row.nextTrain) return `<span class="hint">无需额外练习</span>`;
        const t = row.nextTrain;
        const more = row.allTrains.length > 1 ? ` <small class="hint">（另有 ${row.allTrains.length - 1} 项）</small>` : "";
        return `<b>Lv${t.lv} 考${clsLink(t.cls)}前</b>：${U.esc(t.train.join("、"))}<span class="next-sub">共 ${t.ranks} 段${more}</span>`;
      };

      const overviewTableHtml = `<section class="alerts" id="sec-next-overview" data-cmt-target="summary:next-overview" data-cmt-label="全员下一步总览（主角优先 · 按 P → 强度 → 名字）">
        <div class="pm-sec-head">
          <h2>全员下一步总览（主角优先 · 按 P 级 → 强度 → 名字排序 · 共 ${summaryRows.length} 人）</h2>
          ${renderCommentBtn("summary:next-overview", "全员下一步总览（主角优先 · 按 P → 强度 → 名字）", "批注总览")}
        </div>
        ${RM.priorityLinkNote ? `<p class="hint" style="margin:4px 0 8px">${U.esc(RM.priorityLinkNote)}（完整 63 人 SS~D 评级见 <a href="#chars" class="ent-link">「角色图鉴（全 63 人评级）」</a>）</p>` : ""}
        ${renderCommentThread("summary:next-overview", "全员下一步总览（主角优先 · 按 P → 强度 → 名字）")}
        <div class="scroll"><table class="next-tbl">
          <tr>
            <th>角色（P 级 · 强度）</th>
            <th>现在 Lv / 职业</th>
            <th>立刻要做</th>
            <th>何时停下当前职业升级（下一次转职 / 考试 / 跳过）</th>
            <th>下一次练习技能</th>
          </tr>
          ${summaryRows.map(r => {
            const needStop = ["exam", "skip", "switch", "missing"].includes(r.immediate.kind);
            const isLord = Boolean((r.char && r.char.isLord) || (RM.currentLord && r.name === RM.currentLord));
            return `<tr class="${needStop ? "cur" : ""}" data-next-row="${U.esc(r.name)}" data-tier="${U.esc(r.tier)}" data-strength="${U.esc(r.strengthTier)}">
              <td class="next-who">
                <a href="#next" data-go="${U.slug(r.char)}"><b>${isLord ? '<span title="当前路线主角">★</span> ' : ""}${U.esc(U.shortName(r.name))}</b></a>
                <span class="next-badges">${renderPTierBadge(r.tier, r.priorityNote)}${renderStrengthBadge(r)}</span>
                ${r.role ? `<span class="next-sub">${U.esc(r.role)} · ${chLink(r.name, false).replace(/>[^<]+<\/a>/, ">图鉴</a>")}</span>` : `<span class="next-sub">${chLink(r.name, false).replace(/>[^<]+<\/a>/, ">角色图鉴</a>")}</span>`}
              </td>
              <td class="next-who"><b>Lv${r.curLv ?? "?"}</b> ${r.curClass ? clsLink(r.curClass) : "—"}<span class="next-sub">规划终点 Lv${r.endLevel ?? "?"}</span></td>
              <td>${fmtImmediate(r.immediate)}</td>
              <td>${fmtNextStop(r)}</td>
              <td>${fmtTrain(r)}</td>
            </tr>`;
          }).join("")}
        </table></div>
      </section>`;

      const tag = { exam: ["warn", "考试"], skip: ["warn", "跳过"], miss: ["bad", "缺职业"], cls: ["ok", "转职"] };
      const gateHtml = `<section class="alerts"><h2>暂时不能直接升级</h2><ul>${stop.length ? stop.map(([k, a, t]) => `<li><span class="sev ${tag[k][0]}">${tag[k][1]}</span><span>${a}：${t}</span></li>`).join("") : `<li><span class="sev ok">无</span><span>所有人都可以直接升级</span></li>`}</ul>${go.length ? `<p class="txt" style="font-size:13px"><span class="lab">可以直接升级</span>${go.join("；")}</p>` : ""}</section>`;
      const alertsHtml = `<section class="alerts" aria-label="要注意"><h2>升级前先看</h2><ul>${alertRows.map(([k, t]) => `<li><span class="sev ${k}">${k === "bad" ? "会失败" : k === "warn" ? "注意" : "正常"}</span><span>${t}</span></li>`).join("")}</ul></section>`;

      const cards = visibleChars.map(c => {
        const w = walkOf(c), leftRows = w.rows.filter(r => !r.done), nx = leftRows.slice(0, 3), rm = remainOf(c, w);
        const items = nx.map((row, i) => {
          const s = row.s, r = row.r, first = i === 0;
          const changed = row.choice !== RL.recOf(s) ? ` <span class="changed">已改（原来：${clsText(s.exam ? RL.stepName(s) : s.cls)}）</span>` : "";
          const src = s.src === "record" ? (s.hidden ? "没记录的一步" : "观星已记录") : "规划";
          let body;
          if (r.exam) {
            const n = RL.examName(s);
            const curG = s.opts.find(g => g.classes.includes(w.cur));
            body = `<div class="what"><b>${n ? "考试（到 " + clsLink(n) + "）" : s.src === "record" ? "跳过（观星记录里这步没有升级）" : "跳过"}</b>${changed}</div>
              ${curG ? `<div class="hint">考前先观星确认种子：用${clsLink(w.cur)}升级应看到 <b>${U.esc(curG.gains.join(" ") || "—")}</b>（${U.PW(curG.cnt, curG.score)}）。对上了再去考。</div>` : ""}
              ${s.roll != null ? examBox(c, s) : ""}`;
          } else {
            body = `<div class="what"><b>升 Lv${row.frm}→${row.to}，用${clsText(RL.eqName(row))}</b>${changed}${row.missing ? ` <span class="changed">还没考到${clsLink(row.choice)}，这一级前要先考</span>` : ""}<span class="sc">${U.PW(r.cnt, r.score)} ${vsTag(r.score, s.es)}</span></div>
              <div class="chips">${r.gains.map(chip).join("") || '<span>—</span>'}</div>
              ${s.why && !/^已有职业里分最高/.test(s.why) ? `<div class="hint">${U.esc(s.why)}</div>` : ""}
              ${r.classes && r.classes.length > 1 ? `<div class="hint">加点相同的职业：${clsList(r.classes.filter(x => x !== row.choice), " ")}</div>` : ""}`;
          }
          return `<li class="${r.exam ? "exam " : ""}${first ? "first" : ""}" data-key="${s.key}">
            <div class="when"><span>${first ? "现在做" : i === 1 ? "然后" : "再然后"}</span><span class="src">${src}</span></div>
            ${body}${routesBox(c, w, row)}
            <div class="acts">${first ? `<button class="btn pri" type="button" data-do="done">✓ 做完了</button>` : ""}
              <details class="more"><summary>换个选择（这一步所有职业）</summary>${optsHtml(c, s, row, "n", w)}</details></div>
          </li>`;
        }).join("");
        return `<article class="card" data-slug="${U.slug(c)}" id="${U.slug(c)}">${head(c, w, `还剩 ${leftRows.length} 步 → Lv${w.endLevel}`)}
          ${nx.length ? `<ol class="next">${items}</ol>` : ""}${trainBox(c, w)}${nx.length ? "" : `<div class="empty">${c.steps.length ? "路线上的步骤都完成了。" : "还没有观星记录和种子，暂时没有路线。"}</div>`}
          <div class="cfoot">${c.steps.length ? `<span>按现在的选择到 Lv${w.endLevel} 还会升 <b>${rm.lv}</b> 级、涨 <b>${rm.cnt}</b> 点，加权分 <b>${rm.sc}</b>。<a href="#plan" data-go="${U.slug(c)}">看完整路线</a></span>` : ""}${stateHtml(c, w)}</div>
        </article>`;
      }).join("");
      return `<p class="lede">按优先级（P0 → P1 → P2）总览全员当前 Lv 与下一个跳过 / 转职 / 练习技能步骤；下方展开每人最近 3 步详情。点击任意角色名或职业名均可直接跳转对应图鉴。</p>${overviewTableHtml}${gateHtml}${alertsHtml}<div class="grid">${cards}</div>` + notesBox([
        "做完一步点「✓ 做完了」，等级、总览表和已完成状态会自动往后推。",
        "考试步骤把游戏里显示的成功率填进来，页面会直接判断能不能过：<b>判定值</b>低于游戏显示的成功率才过（等于也算失败）。考试不管过不过都消耗一个种子。",
        N_PTS,
      ]);
    }

    // ---------- 2. 到目标级 ----------
    const smDiff = d => `点数 ${U.sgn(d.pts)}、加权分 ${U.sgn(d.total)}${d.floorPts ? `、转职保底 ${U.sgn(d.floorPts)} 点` : ""}、金币 ${U.sgn(d.gold)}G`;
    function smHint(c, s) {
      const o = OPTS[c.name], w = o && o.skipMid && o.skipMid[0];
      if (!w || s.src !== "plan") return "";
      const r = w.skips.find(x => x.step === +s.key - 1);
      if (!r) return "";
      const ok = r.opts.filter(x => x.ok && !x.ruleBlocked), nb = r.opts.filter(x => x.ok && x.ruleBlocked).length;
      if (!ok.length) return `<br><span class="hint">改考中级：判定值 ${r.roll}%，${nb ? `不练技能考不过任何中级（另有 ${nb} 个要先练，${U.esc(c.tier || "")} 规则不练）` : "没有能考过的中级"}</span>`;
      const b = ok.filter(x => x.used).sort((p, q) => q.d.total - p.d.total || q.d.pts - p.d.pts || (q.inner - p.inner))[0];
      if (!b) return `<br><span class="hint">改考中级：${ok.length} 个能考过，但考进去之后都用不上（等于跳过）→ 照跳过（见「职业选择」）</span>`;
      return `<br><span class="hint">改考中级（${ok.length} 个能考过）：${b.d.total > 0 || b.d.pts > 0 ? "数值最好的是" : "用得上的最好是"} <b>${clsLink(b.cls)}</b>，${smDiff(b.d)}${b.ranks ? `、先练 ${b.ranks} 段` : ""}，用它升 ${b.used} 级 → ${b.worth ? "<b>值得</b>" : "不值得，照跳过"}（全部选项见「职业选择」）</span>`;
    }

    function viewPlan() {
      const ds = RL.findDecisions(CH, prog, info, focus);
      const pend = ds.filter(d => !(prog[U.keyOf(d.c, d.s)] || {}).ok);
      const rpSum = RL.summarizeRoutePicks(PROPOSALS, routePicks);
      const rpBanner = PROPOSALS.length
        ? `<section class="alerts"><h2>新路线方案待选（已确认 ${rpSum.confirmed}/${rpSum.total} 人${rpSum.pending ? ` · 待你选择 ${rpSum.pending} 人` : " · 全部已确认"}）</h2><p class="txt">全部 9 位角色的新旧路线对比（含<b>展开的 9 项具体能力差</b>与提前 S/L 提醒）已整理在 <a href="#mine">「我的决定」</a>，点选后会自动记录在本浏览器。</p></section>`
        : "";
      const decBox = rpBanner + (!ds.length
        ? `<section class="alerts"><h2>需要你决定</h2><p class="txt">${focus ? "这个角色" : "现在"}没有「加权分一样、加点不同」的级，全部按推荐走就行。</p></section>`
        : `<section class="alerts"><h2>需要你决定（${pend.length ? `还剩 ${pend.length} 处` : "都确认了"}）</h2><p class="txt">这些级换职业加权分一样（或只差一点），但涨的能力不同。点一下就改，下面的路线和总分跟着变。</p><ul class="decs">${ds.map(({ c, s, row, rec, alts, kind }) => {
            if ((prog[U.keyOf(c, s)] || {}).ok) return `<li data-slug="${U.slug(c)}"><div data-key="${s.key}" class="dh"><b>${chLink(c.name, true)} Lv${row.frm}→${row.to}</b><span class="ok">✓ 已确认：${clsLink(row.choice)}（${U.esc(row.r.gains.join(" ") || "—")}）</span><button type="button" class="btn ghost" data-dec="undo">重新选</button></div></li>`;
            const name = "dec-" + U.keyOf(c, s);
            const opt = g => {
              const val = g.classes.includes(s.cls) ? s.cls : g.classes.find((x, i) => g.owned[i]);
              const on = row.choice === val || (row.r.classes && row.r.classes.includes(val)) || g.classes.includes(row.choice);
              return `<label class="opt"><input type="radio" name="${name}" value="${U.esc(val)}" data-f="pick"${on ? " checked" : ""}><span><span class="oc">${clsList(g.classes.filter((x, i) => g.owned[i]), " / ")}${g === rec ? "（推荐）" : ""}</span>　${U.esc(g.gains.join(" ") || "—")}</span><span class="on">${g.cnt}点 · ${g.score}分</span></label>`;
            };
            return `<li data-slug="${U.slug(c)}"><div data-key="${s.key}"><div class="dh"><b>${chLink(c.name, true)} Lv${row.frm}→${row.to}</b><small>${kind}</small></div>${s.note ? `<div class="note">${U.esc(s.note)}</div>` : ""}<div class="opts" role="radiogroup" aria-label="这一步选哪个">${[rec, ...alts].map(opt).join("")}</div><button type="button" class="btn" data-dec="ok">确认：用 ${U.esc(row.choice)}</button></div></li>`;
          }).join("")}</ul></section>`);

      const sortedVisible = RL.sortCharsByTier(CH.filter(c => !focus || U.slug(c) === focus), RM.currentLord);
      const ovRows = sortedVisible.map(c => {
        const a = c.avg; if (!a) return "";
        const ap = U.psum(a.act), dv = Math.round(a.ws - a.wexp);
        const ex = []; let lv = null;
        for (const x of c.route || []) { if (x[0] === "up") { lv = x[3]; continue; } ex.push(x[1] ? `${clsLink(x[1])}（Lv${lv ?? c.planFrom}，判定 ${x[2]}%）` : ""); }
        const skips = (c.route || []).filter(x => x[0] === "exam" && !x[1]).length;
        const exs = ex.filter(Boolean);
        const isLord = Boolean(c.isLord || (RM.currentLord && c.name === RM.currentLord));
        return `<tr><td><a href="#plan" data-go="${U.slug(c)}">${isLord ? "★ " : ""}${U.esc(U.shortName(c.name))}</a>${c.tier ? ` <span class="rec ${c.tier === "P0" ? "r1" : c.tier === "P1" ? "r2" : "r3"}">${c.tier}</span>` : ""} ${renderStrengthBadge(c)}</td><td class="n">Lv${c.planFrom}→${c.planTo}</td><td class="n"><b>${a.ws}</b></td><td class="n">${ap}</td><td class="n ${dv >= 3 ? "up" : dv <= -3 ? "dn" : ""}">${U.sgn(dv)}</td><td class="note">${exs.length ? exs.join("、") : "不转新职业"}${skips ? `；跳过 ${skips} 次` : ""}</td></tr>`;
      }).join("");
      const ovBox = `<section class="alerts"><h2>路线一览（到目标级）</h2><div class="scroll"><table class="ovt"><tr><th>角色</th><th class="n">等级</th><th class="n">加权分</th><th class="n">点数</th><th class="n">比平均</th><th>要考的职业</th></tr>${ovRows}</table></div></section>`;

      const odd = [];
      const shortFlag = t => t.replace(/到 Lv\d+ (只)?涨 /, " +").replace(/，平均 ([\d.]+)/, "（平均 $1").replace(/（权重 (\d)）/, "，权重 $1").replace(/，明显偏(高|低).*$/, "）");
      for (const c of sortedVisible) {
        const fs = ((c.trend && c.trend.flags) || []).filter(f => f.lv !== "warn");
        if (!fs.length) continue;
        const hi = fs.filter(f => f.lv === "good").map(f => U.esc(shortFlag(f.t)));
        const lo = fs.filter(f => f.lv === "bad").map(f => U.esc(shortFlag(f.t)));
        odd.push(`<li class="oddc"><a href="#plan" data-go="${U.slug(c)}">${U.esc(U.shortName(c.name))}</a><span>${hi.length ? `<span class="sev ok">偏高</span> ${hi.join("、")}` : ""}${hi.length && lo.length ? "　" : ""}${lo.length ? `<span class="sev bad">偏低</span> ${lo.join("、")}` : ""}</span></li>`);
      }
      const oddBox = odd.length ? `<section class="alerts"><h2>明显异常的能力（不管权重高低）</h2><ul>${odd.join("")}</ul></section>` : "";

      const balRows = sortedVisible.flatMap(c => (c.balance || []).map(b =>
        `<li><span class="sev warn">均衡</span><span><a href="#plan" data-go="${U.slug(c)}">${U.esc(U.shortName(c.name))}</a> <b>${U.esc(b.lv)}</b>：用 <b>${clsLink(b.pick)}</b> 换 ${clsLink(b.orig)}（多 ${U.esc(b.more)}、少 ${U.esc(b.less)}；这一级加权 ${b.dsc > 0 ? "+" : ""}${b.dsc}）。原因：${U.esc(b.why)}</span></li>`
      ));
      const noneBal = sortedVisible.filter(c => !(c.balance || []).length).map(c => U.shortName(c.name));
      const balBox = `<section class="alerts"><h2>均衡加点换了职业的等级</h2>${balRows.length ? `<ul>${balRows.join("")}</ul>` : ""}<p class="hint" style="margin:4px 0 0">${noneBal.length ? U.esc(noneBal.join("、")) + "：没有。" : ""}</p></section>`;

      const propByName = new Map(PROPOSALS.map(pr => [pr.name, pr]));
      const cards = sortedVisible.map(c => {
        const w = walkOf(c), rm = remainOf(c, w), a = c.avg;
        const ap = U.psum(a ? a.act : []), ep = Math.round(U.psum(a ? a.exp : []));
        const right = a ? `推荐路线 ${U.PW(ap, a.ws)} · 平均 ${U.PW(ep, a.wexp.toFixed(0))}（${U.sgn(ap - ep)} 点 · ${U.sgn(Math.round(a.ws - a.wexp))} 分）` : "";

        // 变更清单
        const items = []; let cur = null; const ownedSet = new Set(c.owned);
        for (const x of c.route || []) {
          if (x[0] === "exam") {
            if (x[1]) items.push(`考试（到 <b>${clsLink(x[1])}</b>）（${ownedSet.has(x[1]) ? "已有" : "新职业"}；判定值 ${x[2]}%${x[3] == null ? "" : `，估计显示 ${x[3]}%`}）${(c.trainPlan || []).filter(t => t.cls === x[1]).map(t => ` <span class="changed">🎯 Lv${t.lv} 考前练好：${U.esc(t.train.join("、"))}</span>`).join("")}${x[4] != null ? `<div class="hint" style="margin:2px 0 0">之后到 Lv${c.planTo} 用它升 <b>${x[4]}</b> 级${x[4] ? `，比每级改用已有职业里最好的：<b>${U.esc(x[5])}</b>（${U.sgn(x[6])} 分）` : "（只为拿到职业或精通，不用来升级）"}</div>` : ""}`);
            else items.push(`跳过一级（判定值 ${x[2]}%，过不过都行）`);
            if (x[1]) ownedSet.add(x[1]);
            continue;
          }
          if (cur === null) items.push(`Lv${x[2]} 起用 <b>${clsLink(x[1])}</b>${c.curClass && x[1] !== c.curClass ? `（现在是${clsLink(c.curClass)}，先转职）` : ""}`);
          else if (x[1] !== cur) items.push(`Lv${x[2]} 转职 ${clsLink(cur)} → <b>${clsLink(x[1])}</b>`);
          cur = x[1];
        }
        const news = [...new Set((c.route || []).filter(x => x[0] === "exam" && x[1]).map(x => x[1]))];
        const changesHtml = `<p class="txt"><span class="lab">要考的职业</span>${news.length ? clsList(news, "、") : "不用考新职业"}　<span class="lab">已有</span>${clsList(c.owned, "、")}</p><ol class="chg">${items.map(t => `<li>${t}</li>`).join("")}</ol>`;
        const routeTxt = (c.route || []).map(x => x[0] === "up"
          ? `<span class="rt">Lv${x[2]}→${x[3]} ${clsLink(x[1])}</span>`
          : `<span class="rt x">${x[1] ? "考试（到 " + clsLink(x[1]) + "）" : "跳过"} · 判定值 ${x[2]}%${x[1] ? (x[3] == null ? "" : ` · 估计显示 ${x[3]}%`) : ""}</span>`
        ).join('<span class="ar">→</span>');

        // 能力表
        const base = c.stats || Array(9).fill(null), wt = c.weights || [];
        const exp = c.avg ? c.avg.exp : null, act = c.hist ? c.hist.total : null;
        const has = base.every(v => v != null), end = has ? base.map((v, i) => v + rm.add[i]) : null;
        const two = (p, q) => `<td class="n">${p}</td><td class="n">${q}</td>`;
        const statTable = `<div class="scroll"><table><tr><th></th>${ST.map(k => `<th class="n">${k}</th>`).join("")}<th class="n">点数</th><th class="n">加权分</th></tr>
          <tr class="w"><td>能力权重</td>${ST.map((_, i) => `<td class="n">${wt[i] ?? ""}</td>`).join("")}<td></td><td></td></tr>
          <tr><td>现在（截图）</td>${ST.map((_, i) => `<td class="n">${base[i] ?? "?"}</td>`).join("")}${has ? two(U.psum(base), U.wsum(base, wt)) : "<td></td><td></td>"}</tr>
          <tr><td>还会涨（再升 ${rm.lv} 级）</td>${ST.map((_, i) => `<td class="n ${rm.add[i] ? "up" : ""}">${rm.add[i] ? "+" + rm.add[i] : "·"}</td>`).join("")}${two("+" + rm.cnt, "+" + rm.sc)}</tr>
          <tr class="sum"><td>Lv${w.endLevel}</td>${ST.map((_, i) => `<td class="n">${base[i] == null ? "?" : base[i] + rm.add[i]}</td>`).join("")}${has ? two(U.psum(end), U.wsum(end, wt)) : "<td></td><td></td>"}</tr>
          ${exp && act ? `<tr><td>推荐路线比平均运气</td>${ST.map((_, i) => { const d = Math.round((act[i] - exp[i]) * 10) / 10; const cl = act[i] - exp[i] >= 1.5 ? "st" : act[i] - exp[i] <= -1.5 ? "wk" : ""; return `<td class="n ${cl}">${U.sgn(d)}</td>`; }).join("")}${two(U.sgn(Math.round((U.psum(act) - U.psum(exp)) * 10) / 10), U.sgn(Math.round(U.wsum(act, wt) - U.wsum(exp, wt))))}</tr>` : ""}
        </table></div>`;

        // 逐级列表
        const nd = w.rows.filter(r => r.done).length;
        const fullList = `<div class="fullwrap"><div class="acts"><button type="button" class="btn ghost" data-expand-all>展开所有等级</button>${nd ? `<label class="showdone"><input type="checkbox" class="sd"> 显示已经走过的 ${nd} 步</label>` : ""}</div><ol class="full">${w.rows.map(row => {
          const s = row.s, r = row.r;
          const exCls = r.exam ? (r.examCls || "") : "";
          const isOrigExam = r.exam && s.exam && s.cls === exCls;
          const customExamPct = r.exam && exCls && !isOrigExam ? ((s.routes && s.routes.exams || []).find(e => e.cls === exCls)?.pct ?? null) : s.pct;
          const curP = isOrigExam && s.curPct != null ? s.curPct : customExamPct;
          return `<li class="${row.done ? "done" : ""} ${r.exam ? "isx" : ""}" data-key="${s.key}">
            <input type="checkbox" data-f="done" id="d-${U.keyOf(c, s)}"${row.done ? " checked" : ""} aria-label="已完成">
            <label class="lvl" for="d-${U.keyOf(c, s)}">${r.exam ? `Lv${row.frm} ${exCls ? "考试" : "跳过"}` : `Lv${row.frm}→${row.to}`}</label>
            <div class="body">${r.exam ? `${exCls ? "考试（到 " + clsLink(exCls) + "）" : (s.skipNone ? `跳过 <span class="changed">没有可用的初级考试</span>` : s.skipFail && s.skipFail.length ? `跳过（考 ${clsList(s.skipFail, " / ")}，会考不过，不拿职业）` : s.skipCls ? `跳过（只能考 ${clsLink(s.skipCls)}，会考过，用掉一个可跳过的职业，还剩 ${s.skipLeft} 个）` : "跳过")}<span class="hint">　判定值 ${s.roll}%${exCls && curP != null ? `｜当前预估 ${curP}%` : ""}${isOrigExam && s.skillSummary ? `｜当前：${U.esc(s.skillSummary)}` : ""}${isOrigExam && s.renown ? `｜要名声 Lv${s.renown}` : ""}</span>${exCls ? ` · ${floorBadgeOf(c.name, exCls, isOrigExam ? s.floor : null)}` : ""}${isOrigExam && s.minReqText ? ` <span class="changed">🎯 ${U.esc(s.minReqText)}</span>` : (isOrigExam && s.train ? (s.trainOk ? ` <span class="changed">🎯 Lv${s.trainLv} 考试前练好：${U.esc(s.train.join("、"))}</span>` : ` <span class="changed">技能差：${U.esc(s.train.join("、"))}（不练，按实际成功率）</span>`) : "")}${!exCls ? smHint(c, s) : ""}${isOrigExam && s.use ? `<span class="hint">　之后到 Lv${c.planTo} 用它升 ${s.use[0]} 级${s.use[0] ? `：${U.esc(s.use[1])}（${U.sgn(s.use[2])} 分）` : ""}</span>` : ""}` : `<b>${clsText(RL.eqName(row))}</b>　${U.esc(r.gains.join(" ") || "—")}`}${row.choice !== RL.recOf(s) ? ` <span class="changed">已改</span>` : ""}${row.missing ? ` <span class="changed">还没考到</span>` : ""}${row.fail ? ` <span class="changed">估计考不过</span>` : ""}
              ${row.done ? "" : `<details class="more"><summary>选择</summary>${optsHtml(c, s, row, "f", w)}</details>`}</div>
            <span class="sc">${r.exam ? "—" : U.PW(r.cnt, r.score)}</span></li>`;
        }).join("")}</ol></div>`;

        // 趋势图与时间轴
        const tlRows = w.rows.filter(r => r.s.src === "plan" || !r.done);
        const mx = Math.max(20, ...tlRows.map(r => (r.r.exam ? 0 : r.r.score)));
        const tlHtml = tlRows.length ? `<div class="tl" role="img" aria-label="每一步的加权分">${tlRows.map(r => {
          if (r.r.exam) return `<div title="${U.esc(RL.stepName(r.s, r))}"><i class="x${r.done ? " done" : ""}"></i><span>${r.r.examCls ? "转" : "跳"}</span></div>`;
          const es = r.s.es, d = es == null ? null : r.r.score - es, k = d == null ? "" : d >= 2 ? "up" : d <= -2 ? "dn" : "eq";
          const h = Math.max(4, 64 * r.r.score / mx);
          return `<div title="Lv${r.frm}→${r.to} ${U.esc(r.choice)}：${U.PW(r.r.cnt, r.r.score)}"><i class="${k}${r.done ? " done" : ""}" style="height:${h}px">${es != null ? `<b style="bottom:${64 * es / mx}px"></b>` : ""}</i><span>${r.to}</span></div>`;
        }).join("")}</div><div class="legend"><span style="--k:var(--good)">好于平均 2 分以上</span><span style="--k:var(--bad)">低于平均 2 分以上</span><span style="--k:var(--muted)">差不多</span><span style="--k:var(--exam)">考试或跳过</span><span>横线 = 平均运气</span></div>` : "";

        // 每次考试值不值 + 替换当前单中级对比 + 多转一个中级（拆分为升级乱数能力差 vs 额外考试耗掉的乱数，附技能训练差与推荐度排序）
        const eb = (c.hist && c.hist.exam_benefit) || [];
        const altMid = c.altMid || [];
        const mg = c.midGain || [];
        const recPill = lv => {
          const cls = lv === "推荐" ? "r1" : lv === "可考虑" ? "r2" : "r3";
          return `<span class="rec ${cls}">${U.esc(lv || "不推荐")}</span>`;
        };
        const renderVariantTable = (list, mode) => `<div class="scroll"><table>
          <tr>
            <th>${mode === "alt" ? "改考（替换）" : "多转"}</th>
            <th>推荐度</th>
            <th>额外需练技能</th>
            <th>① 升级乱数能力差<br><small>（不含少升级）</small></th>
            <th>② 考试耗掉 / 置换的乱数</th>
            <th>合计能力差</th>
            <th class="n">加权差 / 净值差</th>
            <th class="n">手形</th>
          </tr>
          ${list.map(r => {
            const dn = r.dnetReal != null ? r.dnetReal : r.dnet;
            const upStr = r.upDiff ? `${U.esc(r.upDiff)}（${U.sgn(r.upDiffW ?? 0)}分，用${r.used}级）` : "—";
            const lossStr = r.examLoss ? `${U.esc(r.examLoss)}${r.examLossW ? `（${U.sgn(r.examLossW)}分）` : ""}` : "—";
            const clsLabel = mode === "alt" && r.replaces ? `<b>${clsLink(r.cls)}</b><br><small class="hint">替 ${clsLink(r.replaces)}</small>` : `<b>${clsLink(r.cls)}</b>`;
            return `<tr>
              <td>${clsLabel}</td>
              <td>${recPill(r.recLevel)}</td>
              <td class="note">${U.esc(r.trainText || "已达标（0 段）")}</td>
              <td class="note">${upStr}</td>
              <td class="note">${lossStr}</td>
              <td class="note">${U.esc(r.diff || "")}（${r.dpts == null ? "—" : U.sgn(r.dpts)}点）</td>
              <td class="n ${dn > 0 ? "up" : dn < 0 ? "dn" : ""}">${U.sgn(r.dsc)}分 / <b>${U.sgn(dn)}</b></td>
              <td class="n">${r.gold}G${r.dgold ? `<br><small class="hint">${U.sgn(r.dgold)}G</small>` : ""}</td>
            </tr>`;
          }).join("")}
        </table></div>`;

        const altMidHtml = altMid.length
          ? `<div id="sec-altmid-${U.slug(c)}" style="margin-top:8px" data-cmt-target="route:${U.esc(c.name)}" data-cmt-label="${U.esc(c.name)}（改考其他单中级对比）">
              <h4><span>改考其他单中级对比（替换 ${clsLink(altMid[0].replaces)}，同样只考 1 场）</span></h4>
              ${renderVariantTable(altMid, "alt")}
            </div>`
          : "";

        const mgPos = mg.filter(r => (r.dnetReal != null ? r.dnetReal : r.dnet) > 0);
        const mgNeg = mg.filter(r => (r.dnetReal != null ? r.dnetReal : r.dnet) <= 0);
        const midGainHtml = mg.length
          ? `<div id="sec-midgain-${U.slug(c)}" data-cmt-target="route:${U.esc(c.name)}" data-cmt-label="${U.esc(c.name)}（多转中级对比）">
              ${mgPos.length ? `<h4 style="margin-top:8px">多转一个中级值多少（有正净值收益）</h4>${renderVariantTable(mgPos, "add")}` : ""}
              ${mgNeg.length ? `<details class="more" style="margin-top:6px"><summary>多转一个中级排雷对比（以下 ${mgNeg.length} 个均无正净值收益，已按推荐度与净值排序并拆分少升级消耗）</summary>${renderVariantTable(mgNeg, "add")}</details>` : ""}
            </div>`
          : "";
        const examSec = `<div class="sec" id="sec-exam-${U.slug(c)}"><h4>每次考试值不值</h4>
          ${eb.length ? `<div class="scroll"><table><tr><th>考试</th><th class="n">判定值</th><th>比不考它的最好路线</th><th class="n">点数</th><th class="n">加权分</th><th class="n">多花</th></tr>${eb.map(e => `<tr><td>${clsLink(e.cls)}${e.req ? " · 必考" : ""}</td><td class="n">${e.roll}%</td><td>${U.esc(U.gtxt(e.diff, ST))}</td><td class="n">${U.sgn(U.psum(e.diff))}</td><td class="n">${U.sgn(e.wdiff)}</td><td class="n">${e.dgold == null ? "—" : e.dgold + "G"}</td></tr>`).join("")}</table></div>` : `<p class="txt">推荐路线不考试。</p>`}
          ${altMidHtml}
          ${midGainHtml}
        </div>`;

        // 该角色的待决定方案（直接嵌入角色卡内，与「我的决定」双向实时同步）
        const pr = propByName.get(c.name);
        let charDecisionHtml = "";
        if (pr && (pr.options || []).length > 1) {
          const rPick = RL.resolveRoutePick(pr, routePicks);
          const isPending = rPick.source === "pending";
          const decBadge = isPending
            ? `<span class="rec r2">⏳ 待你决定路线方案</span>`
            : `<span class="rec ${rPick.source === "user" ? "r1" : "r0"}">✓ 当前选择：${U.esc(rPick.option.title)}</span>`;
          charDecisionHtml = `<div class="sec rp-opts" id="sec-decision-${U.slug(c)}" data-cmt-target="char:${U.esc(pr.name)}" data-cmt-label="${U.esc(pr.name)}（待决定方案）">
            <details class="more"${isPending ? " open" : ""}>
              <summary>${decBadge} <small>（含相对旧路线 9 项能力差，与「我的决定」自动同步）</small></summary>
              <div class="rp-opts" style="margin-top:8px">${renderProposalOptionsBody(pr, rPick, "plan-rpick-")}</div>
            </details>
          </div>`;
        }

        return `<article class="card" data-slug="${U.slug(c)}" id="${U.slug(c)}" data-cmt-target="route:${U.esc(c.name)}" data-cmt-label="${U.esc(c.name)}（路线规划）">${head(c, w, right)}
          ${charDecisionHtml}
          <details class="more cbody"${focus ? " open" : ""}><summary>展开：路线、能力、考试和每一步</summary>
            ${c.examWarn ? `<div class="sec"><p class="txt"><span class="sev warn">注意</span> 这条路线考试 + 跳过一共 ${c.exams} 次，比较多（手形 ${c.planGold}G）。</p></div>` : ""}
            ${trainBox(c, w)}
            ${c.route ? `<div class="sec" id="sec-route-${U.slug(c)}"><h4>推荐路线</h4>${changesHtml}<details class="more"><summary>逐级一览</summary><div class="route">${routeTxt}</div></details></div>` : ""}
            <div class="sec" id="sec-stats-${U.slug(c)}"><h4>能力到 Lv${w.endLevel}</h4>${statTable}</div>
            ${examSec}
            ${tlHtml ? `<div class="sec" id="sec-tl-${U.slug(c)}"><h4>每一步的加权分<small>按现在的选择，剩 ${U.PW(rm.cnt, rm.sc)}</small></h4>${tlHtml}</div>` : ""}
            ${c.steps.length ? `<div class="sec" id="sec-steps-${U.slug(c)}"><details class="more" open><summary>逐级路线和所有选择（可以改）</summary>${fullList}</details></div>` : ""}
          </details>
        </article>`;
      }).join("");

      // 规则说明全部由 RM (rulesMeta) 动态生成，永不过时
      const tiers = RM.tiers || {};
      const sr = RM.skipRule || {};
      const skipDesc = sr.P0 && sr.other && sr.P2
        ? `① 这一级最好的分 ≤ 分数线（P0 ${sr.P0.cap}、P1 ${sr.other.cap}、P2 ${sr.P2.cap}）；② 比未来 15 级平均低 ≥ 百分比（P0 ${Math.round(sr.P0.pct * 100)}%、P1 ${Math.round(sr.other.pct * 100)}%、P2 ${Math.round(sr.P2.pct * 100)}%）。P0 满足其一就跳，P1/P2 两个都满足才跳。`
        : "按各档跳过规则执行。";
      const tierDesc = `P0 = ${(tiers.P0 || []).map(U.shortName).join("、")}；P1 = ${(tiers.P1 || []).map(U.shortName).join("、")}；P2 = ${(tiers.P2 || []).map(U.shortName).join("、")}。`;

      return `<p class="lede">每人到目标级（max(Lv35, 当前+15)）的推荐路线、终点能力和考试安排。改了某一步的职业，数字会即时重算。</p>${decBox}${ovBox}${oddBox}<div class="grid one">${cards}</div>${balBox}` + notesBox([
        N_PTS,
        "<b>体格阈值</b>（所有人）：力量每涨到 5 的倍数，体格 +1，那一级额外 +3 分，已算进加权分和路线选择。",
        `<b>跳过条件与优先级</b>：${skipDesc}${tierDesc}${RM.requireMidRule ? " 每人都要考进一个中级职业（已有中级的算满足）。" : ""}`,
        `<b>判定值与成功率</b>：判定值低于游戏显示成功率才过。估计成功率按 ${shotLabel} 的技能与拟合公式计算。`,
        `<b>均衡加点</b>：在权重 ≥ ${RM.balanceMinWeight || 4} 的能力之间做均衡，只用来决定同一级选哪个已有职业。`,
      ]);
    }

    // ---------- 3. 回顾 ----------
    function viewPast() {
      const list = CH.filter(c => c.hist && (!focus || U.slug(c) === focus));
      const th = ST.map(k => `<th class="n">${k}</th>`).join("");
      return `<p class="lede">从入队到现在每一级涨了什么，以及当前的裸能力拆解。</p>` + list.map((c, i) => {
        const h = c.hist, wt = c.weights || [], n = h.now;
        const pw = g => `<td class="n">${U.psum(g)}</td><td class="n">${U.wsum(g, wt)}</td>`;
        const gained = n.raw.map((v, idx) => v - h.join.stats[idx]);
        let pt = `<table><tr><th>等级</th><th>职业</th>${th}<th class="n">点数</th><th class="n">加权分</th><th>说明</th></tr>
          <tr><td>Lv${h.join.lv} 入队</td><td>${clsLink(h.join.cls)}</td>${cells(h.join.stats)}${pw(h.join.stats)}<td class="note">${U.esc(h.join.note || "初始能力（不含职业补正）")}</td></tr>`;
        if (h.gap) pt += `<tr><td>Lv${h.gap.frm}→${h.gap.to}</td><td>${h.gap.n} 级合计</td>${cells(h.gap.g, true)}${pw(h.gap.g)}<td class="note">无观星记录，仅合计</td></tr>`;
        for (const r of h.past) {
          if (r.kind === "考试") pt += `<tr class="exam"><td>${U.esc(r.lv)}</td><td>考试 ${clsLink(r.cls)}</td>${ST.map(() => "<td></td>").join("")}<td></td><td></td><td class="note">${U.esc(r.note)}</td></tr>`;
          else pt += `<tr><td>${U.esc(r.lv)}</td><td>${clsLink(r.cls)}</td>${cells(r.g, true)}${pw(r.g)}<td class="note">${U.esc(r.note)}</td></tr>`;
        }
        pt += `<tr class="sum"><td colspan="2">入队以来合计涨</td>${cells(gained, true)}${pw(gained)}<td class="note">每级平均 ${(U.psum(gained) / Math.max(1, n.lv - h.join.lv)).toFixed(1)} 点</td></tr>
          <tr class="sum"><td colspan="2">截图时裸能力</td>${cells(n.raw)}${pw(n.raw)}<td class="note">能力总和</td></tr></table>`;
        let nt = `<table><tr><th></th>${th}<th>说明</th></tr>
          <tr><td>${shotLabel} Lv${n.lv} ${clsLink(n.cls)}</td>${cells(n.shot)}<td class="note">游戏里显示的</td></tr>
          <tr><td>− 职业补正</td>${cells(n.bonus.map(v => -v), true)}<td class="note">${clsLink(n.cls)}自带</td></tr>
          <tr><td>− ▲加成</td>${cells(n.boost.map(v => -v), true)}<td class="note">${U.esc(n.boost_note)}</td></tr>
          <tr class="sum"><td>= 裸能力</td>${cells(n.raw)}<td></td></tr></table>`;
        return `<details class="char" id="${U.slug(c)}"${focus || i === 0 ? " open" : ""}><summary><h3>${chLink(c.name)}</h3><span>Lv${h.join.lv} ${clsLink(h.join.cls)} → Lv${n.lv} ${clsLink(n.cls)} · 裸能力 ${U.psum(h.join.stats)} → ${U.psum(n.raw)} 点</span></summary>
          <div class="sec"><h4>每一级</h4><div class="scroll">${pt}</div></div>
          <div class="sec"><h4>现在：截图 → 裸能力</h4><div class="scroll">${nt}</div></div></details>`;
      }).join("") + notesBox(["<b>裸能力</b> = 截图数值去掉职业补正和▲加成。", N_PTS]);
    }

    // ---------- 4. 到 Lv45 ----------
    function viewL45() {
      const list = CH.filter(c => c.l45 && (!focus || U.slug(c) === focus));
      const fmtCompact = steps => RL.compactRouteSegments(steps).map(x =>
        x.kind === "exam"
          ? (x.exam === "跳过" ? `<span class="need">Lv${x.lv} 跳过</span>` : `<b>Lv${x.lv} 考试（到 ${clsLink(x.exam)}）</b>`)
          : `Lv${x.from}→${x.to} ${clsLink(x.cls)}`
      ).join(" → ");
      const rows = list.map(c => {
        const L = c.l45;
        return `<tr><td><a href="#l45" data-go="${U.slug(c)}">${U.esc(U.shortName(c.name))}</a></td><td class="n">Lv${L.from}→45</td><td class="n">${L.pts}</td><td class="n"><b>${L.total}</b></td><td>${L.adv ? `${clsLink(L.adv.exam)}（Lv${L.adv.lv}）` : "不转上级更好"}</td><td class="n ${L.loss > 3 ? "dn" : ""}">${L.diffs.length ? L.loss : "—"}</td></tr>`;
      }).join("");
      const cards = list.map(c => {
        const L = c.l45;
        return `<article class="card" data-slug="${U.slug(c)}" id="${U.slug(c)}"><div class="ch"><div class="ct"><h3>${chLink(c.name)}</h3><span class="lv">Lv${L.from}→45</span><span class="r">${U.PW(L.pts, L.total)} · 到目标级 ${L.plan35.total} 分</span></div></div>
          <div class="sec"><h4>上级职业</h4><p class="txt">${L.adv ? `转 <b>${clsLink(L.adv.exam)}</b>（Lv${L.adv.lv}）` : "最优路线里不转上级"}。可选上级：${(L.advOptions || []).length ? clsList(L.advOptions, "、") : "无（技能或名声未达要求）"}。</p></div>
          <div class="sec"><h4>路线</h4><p class="txt">${fmtCompact(L.steps)}</p></div>
          <div class="sec"><h4>和到目标级的路线比</h4>${L.diffs.length ? `<p class="txt">35 级前安排不同。按 35 级路线走、之后再最优：${U.PW(L.follow.pts, L.follow.total)}；扣手形后差 <b>${L.loss}</b> 分。</p>` : `<p class="txt">35 级前的考试安排一样，没影响。</p>`}</div>
          <div class="sec"><h4>Lv45 时比现在多</h4><p class="txt">${U.esc(L.add.map((v, i) => (v ? ST[i] + "+" + v : "")).filter(Boolean).join(" "))}</p></div>
        </article>`;
      }).join("");
      return `<p class="lede">到 Lv45 的最优路线，可转一次上级职业（受当前名声 Lv${RM.renown ?? "?"} 与技能差距约束）。</p>
        <section class="alerts"><h2>一览</h2><div class="scroll"><table><tr><th>角色</th><th class="n">等级</th><th class="n">点数</th><th class="n">加权分</th><th>上级</th><th class="n">按目标级走差几分</th></tr>${rows}</table></div></section>
        <div class="grid one">${cards}</div>` + notesBox([N_PTS, "上级手形按 3000G 算，每人最多考一次上级。"]);
    }

    // ---------- 5. 长线观星 ----------
    function viewLong() {
      const list = CH.filter(c => c.long && (!focus || U.slug(c) === focus));
      const rows = CH.filter(c => c.long).map(c => {
        const L = c.long, st = L.stats, td = L.got - L.exp, wc = L.wcur, r = L.wrec;
        const srt = [...st].sort((a, b) => a.diff - b.diff || a.got - b.got);
        const s5 = st.reduce((a, x) => a + x.per[5].max, 0);
        return `<tr><td><a href="#long" data-go="${U.slug(c)}">${U.esc(U.shortName(c.name))}</a></td><td class="n">${L.got} / ${L.exp}</td><td class="n"><span class="vs ${td >= 5 ? "up" : td <= -5 ? "dn" : "eq"}">${U.f1(td)}</span></td>
          <td><span class="vs ${dc(srt[8].diff)}">${U.esc(srt[8].k)} ${U.f1(srt[8].diff)}</span></td><td><span class="vs ${dc(srt[0].diff)}">${U.esc(srt[0].k)} ${U.f1(srt[0].diff)}</span></td>
          <td class="n">${s5}</td><td class="n">${wc[0].sc}</td><td class="n up"><b>${wc[r].sc}</b></td><td class="n">${r}</td><td class="n">${U.sgn(wc[r].sc - wc[0].sc)}</td><td class="note">${U.esc(L.oneline || "")}</td></tr>`;
      }).join("");
      const cards = list.map((c, i) => {
        const L = c.long, k = U.slug(c), S = longS[k] ?? LONG_DEF, lv0 = L.level, wt = L.w, wc = L.wcur, wl = L.wlo, r = L.wrec;
        const segH = L.stats[0].seg.map((_, q) => `<th class="n">Lv${lv0 + q * 10}～</th>`).join("");
        const trs = L.stats.map((x, q) => {
          const p = x.per[S];
          return `<tr><td><b>${U.esc(x.k)}</b></td><td class="n">${wt[q]}</td><td class="n">${x.rate}%</td><td class="n"><b>${x.got}</b></td><td class="n">${x.exp}</td><td class="n ${dc(x.diff)}">${U.f1(x.diff)}</td>${x.seg.map(v => `<td class="n">${v}</td>`).join("")}<td class="n up">${p.max}</td><td class="n dn">${p.min}</td><td class="note">${U.esc(x.note || "")}</td><td class="note">${S ? U.lvTxt(RL.skipLevelsFor(lv0, S, p.skip)) : "—"}</td></tr>`;
        }).join("");
        const grid = L.stats.map((x, q) => `<div class="hrow"><span class="hk">${U.esc(x.k)}</span>${L.hits.slice(0, 40).map((h, j) => `<i class="${h[q] ? "on" : ""}${j % 10 === 0 ? " s" : ""}" title="Lv${lv0 + j}→${lv0 + j + 1}"></i>`).join("")}<span class="hn">${x.got}</span></div>`).join("")
          + `<div class="hrow"><span class="hk">加权</span>${L.wsc.slice(0, 40).map((v, j) => `<i class="w ${v >= 22 ? "g" : v <= 10 ? "b" : ""}${j % 10 === 0 ? " s" : ""}">${v}</i>`).join("")}<span class="hn"></span></div>`;
        return `<details class="char" id="${k}" data-slug="${k}"${focus || i === 0 ? " open" : ""}><summary><h3>${chLink(c.name)}</h3><span>Lv${L.level}→${L.end} · 点数 ${L.got}（期望 ${L.exp}，${U.f1(L.got - L.exp)}）· 加权最高 ${wc[r].sc}（跳 ${r} 次）</span></summary>
          <div class="sec">
            <h4>总结</h4><ul class="adv">${L.summary.map(a => `<li>${U.esc(a)}</li>`).join("")}</ul>
            <h4>养成建议</h4><ul class="adv">${L.advice.map(a => `<li>${U.esc(a)}</li>`).join("")}</ul>
            <h4>加权：整体跳过</h4>
            <div class="lvsum"><div><small>不跳过</small><b>${wc[0].sc} 分</b></div><div class="hi"><small>建议跳 ${r} 次（约 ${r * 300}G）</small><b>${wc[r].sc} 分</b></div><div class="lo"><small>跳错同样次数</small><b>${wl[r].sc} 分</b></div><div><small>跳满 20 次</small><b>${wc[20].sc} 分</b></div><div><small>平均运气</small><b>${L.wexp} 分</b></div></div>
            <p class="hint" style="margin:0"><b>建议跳过的级</b>：${U.lvTxt(wc[r].lvs)}</p>
            <h4>单项：只为一项跳过</h4>
            <div class="skctl"><label>每项最多跳过 <input type="range" min="0" max="20" value="${S}" data-long="${k}"></label><b>${S}</b> 次${S === LONG_DEF ? "" : `　<a href="#long" data-longrec="${k}">回到 ${LONG_DEF} 次</a>`}</div>
            <div class="scroll"><table><tr><th>能力</th><th class="n">权重</th><th class="n">成长率</th><th class="n">不跳</th><th class="n">期望</th><th class="n">差值</th>${segH}<th class="n">跳 ${S} 最高</th><th class="n">跳 ${S} 最低</th><th>总结</th><th>跳过位置</th></tr>${trs}</table></div>
            <h4>每一级涨了哪些</h4><div class="scroll"><div class="hgrid">${grid}</div></div>
          </div></details>`;
      }).join("");
      return `<p class="lede">从现在的种子往后看 40 级：哪项长得好、哪项差，跳过能多拿多少。</p>
        <section class="alerts"><h2>九人对比（40 级）</h2><div class="scroll"><table><tr><th>角色</th><th class="n">涨 / 期望</th><th class="n">差值</th><th>最好</th><th>最差</th><th class="n">单项跳5上限和</th><th class="n">不跳</th><th class="n">建议跳后</th><th class="n">跳次</th><th class="n">多</th><th>总结</th></tr>${rows}</table></div></section>
        <div class="grid one">${cards}</div>` + notesBox(["<b>成长率</b> = 个人 + 统一 15%，单次升级保底 2 项。", N_PTS]);
    }

    // ---------- 6. 职业选择与选择原因 ----------
    function viewOpts() {
      const smOpts = r => { const a = r.opts.filter(x => !x.ruleBlocked); return a.length ? a : [{ cls: "—", ok: false, why: "不练技能能考的中级都没有" }]; };
      const smTable = o => {
        const ws = (o.skipMid || []).filter(w => w.skips.length);
        if (!ws.length) return `<p class="txt" style="font-size:13px"><span class="lab">跳过那一级改考中级</span>当前规则路线里没有跳过的等级。</p>`;
        return ws.map(w => {
          const blk = [];
          for (const r of w.skips) for (const x of r.opts) if (x.ruleBlocked) blk.push(`Lv${r.lv} ${x.cls}（${x.ranks} 段）`);
          return `<p class="txt" style="font-size:13px"><span class="lab">跳过那一级改考中级 · ${w.target === o.target ? `到 Lv${w.target}` : "到 Lv45"}</span>同样 ${w.seeds} 个乱数对比</p>
            <div class="scroll"><table><tr><th class="n">跳过的等级</th><th class="n">判定值</th><th>改考</th><th class="n">成功率<br><small>练够 / 不练</small></th><th class="n">先练</th><th class="n">用它升级</th><th>能力差</th><th class="n">点数</th><th class="n">加权分</th><th class="n">转职保底</th><th class="n">金币</th><th>结论</th></tr>
            ${w.skips.map(r => smOpts(r).map((x, i, a) => `<tr${x.worth ? ' class="cur"' : ""}>${i ? "" : `<td class="n" rowspan="${a.length}">Lv${r.lv}</td><td class="n" rowspan="${a.length}">${r.roll}%</td>`}<td><b>${clsLink(x.cls)}</b></td><td class="n">${x.pct ?? "—"}% / ${x.pctNow ?? "—"}%</td>${x.ok ? `<td class="n">${x.ranks ? x.ranks + " 段" : "—"}</td><td class="n">${x.used} 级</td><td class="note">${fmtSignedStats(x.d.g)}</td><td class="n">${fmtSignedNum(x.d.pts)}</td><td class="n">${fmtSignedNum(x.d.total)}</td><td class="n">${x.d.floorPts ? `<b class="ok">${U.sgn(x.d.floorPts)} 点</b>` : `<span class="hint">无转职保底</span>`}</td><td class="n">${fmtSignedNum(x.d.gold, "G", true)}</td><td class="note">${x.worth ? "值得" : x.used ? "不值得" : "考过但用不上"}</td>` : `<td colspan="8" class="note">${U.esc(x.why)}</td>`}</tr>`).join("")).join("")}</table></div>
            ${blk.length ? `<p class="hint">规则不考虑（本档不练技能）：${U.esc(blk.join("、"))}</p>` : ""}`;
        }).join("");
      };

      const renderSeedDiffHtml = list => {
        if (!list || !list.length) return "";
        return `<div class="hint" style="margin-top:3px">🎲 <b>乱数消耗差异</b>：${list.map(x => U.esc(x)).join("；")}</div>`;
      };

      const renderHighlightsBox = (c, o) => {
        const hi = RL.summarizeOptionHighlights(o, c.weights, ST);
        if (!hi) return "";
        const fmtCand = x => {
          const nm = x.isBaseline ? `<b>${U.esc(x.cls)}</b>` : `<b>${clsLink(x.cls)}</b><small>（Lv${x.lv}${x.ruleBlocked ? "·本档不练" : ""}）</small>`;
          const aV = x.g[hi.idxA] || 0;
          const bV = x.g[hi.idxB] || 0;
          const sumV = aV + bV;
          const fl = x.floor && x.floor.length ? `· 转职保底 ${U.esc(x.floor.join("、"))}` : "· 无转职保底";
          return `${nm}：${U.esc(hi.statA)}${fmtSignedNum(aV)} / ${U.esc(hi.statB)}${fmtSignedNum(bV)}（${U.esc(hi.statA)}+${U.esc(hi.statB)} ${fmtSignedNum(sumV)}；总点数 ${fmtSignedNum(x.pts)}，加权 ${fmtSignedNum(x.total)}，金币 ${fmtSignedNum(x.gold, "G", true)} ${fl}）`;
        };
        const fmtSingle = (x, idx, label) => {
          const nm = x.isBaseline ? `<b>${U.esc(x.cls)}</b>` : `<b>${clsLink(x.cls)}</b>${x.ruleBlocked ? "<small>（本档不练）</small>" : ""}`;
          return `${nm} ${U.esc(label)}${fmtSignedNum(x.g[idx] || 0)}（加权 ${fmtSignedNum(x.total)}）`;
        };
        return `<div class="opts-hi" style="margin-bottom:10px;padding:10px 12px;border:1px solid var(--line);border-radius:8px;background:var(--bg)">
          <div style="font-weight:700;font-size:13px;margin-bottom:4px">🎯 核心属性最高选项速览（到目标 Lv${o.target}，相对不考基准 · 含转职保底）</div>
          <ul class="txt" style="margin:4px 0 0 18px;font-size:13px">
            <li><b>${U.esc(hi.statA)}+${U.esc(hi.statB)} 之和排行</b>：${hi.pairTop.map(fmtCand).join("；")}</li>
            <li><b>单项最高</b>：${U.esc(hi.statA)} 最高 → ${hi.statATop.map(x => fmtSingle(x, hi.idxA, hi.statA)).join(" / ")}；${U.esc(hi.statB)} 最高 → ${hi.statBTop.map(x => fmtSingle(x, hi.idxB, hi.statB)).join(" / ")}；加权分最高 → ${hi.weightedTop.map(x => `${x.isBaseline ? U.esc(x.cls) : clsLink(x.cls)}（${fmtSignedNum(x.total)} 分）`).join(" / ")}</li>
          </ul>
        </div>`;
      };

      const reasonsBox = name => {
        const r = REASONS[name]; if (!r) return "";
        const rt = r.route;
        const dtxt = d => `${fmtSignedStats(d.g)}；点数 ${fmtSignedNum(d.pts)}，加权分 ${fmtSignedNum(d.w)}${d.floorW != null ? `（已含转职保底差：${d.floorW ? fmtSignedNum(d.floorW, " 分") : `<span class="hint">无转职保底</span>`}）` : ""}；金币 ${fmtSignedNum(d.gold, "G", true)}；练技能 ${fmtSignedNum(d.train, " 段", true)}`;
        const ex = rt.exams.map(e => `<li><b>Lv${e.lv} ${clsLink(e.cls)}</b> <small>${U.esc(e.tier || "")}｜判定值 ${e.roll}%｜成功率 ${e.pct ?? "—"}%｜用它升 ${e.used} 级｜${floorBadgeOf(name, e.cls, e.floor)}</small><br>${U.esc(e.why)}${e.trainSkills && e.trainSkills.length ? `<br><span class="changed">🎯 Lv${e.lv} 考前练好：${U.esc(e.trainSkills.join("、"))}（共 ${e.trainRanks} 段）</span>` : ""}${timingBox(e)}${e.vsDrop ? `<br><span class="hint">和不考它比（同 ${rt.seeds} 个乱数 · 考到 Lv${rt.endLv} vs 不考到 Lv${e.vsDrop.lvDrop ?? "?"}，已含转职保底口径）：</span>${dtxt(e.vsDrop)}${renderSeedDiffHtml(e.vsDrop.seedDiff)}` : `<br><span class="hint">${U.esc(e.dropNote || "")}</span>`}</li>`).join("") || "<li>不考新职业</li>";
        const mids = r.mids.map(m => {
          const vr = m.vsRoute;
          const scopeStr = vr ? `同 ${vr.seeds || rt.seeds} 个乱数 · 考它到 Lv${vr.endA ?? "?"} vs 现路线到 Lv${vr.endB ?? rt.endLv}` : "";
          return `<li><b>${clsLink(m.cls)}</b> <small>（${floorBadgeOf(name, m.cls, m.floor)}）</small>：${U.esc(m.why)}${vr ? `<br><span class="hint">和现在路线比（${scopeStr}）：</span>${dtxt(vr)}${renderSeedDiffHtml(vr.seedDiff)}` : ""}</li>`;
        }).join("");
        const exc = r.excluded.length ? `<p class="hint">不考虑：${r.excluded.map(x => `${clsLink(x.cls)}（${U.esc(x.why)}）`).join("、")}</p>` : "";
        return `<div class="sec"><h4>选择原因</h4><p class="txt">路线到 Lv${rt.endLv}（用 ${rt.seeds} 个乱数）：${U.esc(rt.end.map((v, i) => ST[i] + v).join(" "))}；点数 +${rt.pts}，加权分 +${rt.w}；金币 ${rt.gold}G；练技能 ${rt.train} 段；跳过 ${rt.skips} 次。${U.esc(r.tier)} ${r.trainAllowed ? "可以" : "不"}练技能考试。</p><h4>路线里的考试</h4><ul>${ex}</ul>${mids ? `<h4>没选的中级职业（均与当前路线按同样 ${rt.seeds} 个乱数比到目标 Lv${r.target} · 含转职保底）</h4><ul>${mids}</ul>` : ""}${exc}</div>`;
      };

      const cards = CH.filter(c => !focus || U.slug(c) === focus).map(c => {
        const o = OPTS[c.name]; if (!o) return "";
        const diffCell = d => d
          ? `<td class="note">${fmtSignedStats(d.g)}${d.endA != null && d.endB != null && d.endA !== d.endB ? `<br><small class="hint">同 ${d.seeds} 乱数：考 Lv${d.endA} vs 不考 Lv${d.endB}</small>` : ""}${d.seedDiff && d.seedDiff.length ? `<details class="more" style="margin-top:3px"><summary style="font-size:11px">🎲 乱数消耗差异（${d.seedDiff.length} 处）</summary><div class="hint" style="font-size:11px;margin-top:2px">${d.seedDiff.map(U.esc).join("<br>")}</div></details>` : ""}</td><td class="n">${fmtSignedNum(U.psum(d.g))}</td><td class="n">${fmtSignedNum(d.total)}</td>`
          : `<td>—</td><td class="n">—</td><td class="n">—</td>`;
        const blk = o.options.filter(x => x.ok && x.ruleBlocked);
        const rows = o.options.filter(x => !(x.ok && x.ruleBlocked)).map(x => x.ok
          ? `<tr${x.rec ? ' class="cur"' : ""}><td><b>${clsLink(x.cls)}</b> <small>${U.esc(x.tier || "")}</small>${x.rec ? ' <span class="rec r1">现在推荐</span>' : ""}</td><td class="n">Lv${x.lv}</td><td class="n">${x.roll}%</td><td class="n">${o.trainAllowed ? `${x.pct ?? "—"}%${x.ranks ? `<br><small>不练 ${x.pctNow ?? "—"}%</small>` : ""}` : `${x.pctNow ?? "—"}%${x.ranks ? `<br><small>练后 ${x.pct ?? "—"}%</small>` : ""}`}</td><td class="note">${x.train.length ? U.esc(x.train.join("、")) : "无需练习"}<br>${x.floor && x.floor.length ? `<span class="ok">转职保底：${U.esc(x.floor.join("、"))}</span>` : `<span class="hint">无转职保底</span>`}</td><td class="n">${x.used} 级</td>${diffCell(x.toT)}<td class="n">${fmtSignedNum(x.toT.gold, "G", true)}</td></tr>`
          : `<tr><td><b>${clsLink(x.cls)}</b></td><td colspan="9" class="note">${U.esc(x.why)}（${floorBadgeOf(c.name, x.cls, x.floor)}）</td></tr>`
        ).join("") + (blk.length ? `<tr><td colspan="10" class="note">规则不考虑（本档不练）：${blk.map(x => `${clsLink(x.cls)}（${x.ranks} 段，到目标 Lv${o.target} 加权分 ${fmtSignedNum(x.toT.total)}，${x.floor && x.floor.length ? "转职保底：" + U.esc(x.floor.join("、")) : "无转职保底"}）`).join("、")}</td></tr>` : "");
        const rr = o.recRow ? `<tr class="sum"><td>现在推荐的组合：${clsList(o.recommended, " + ")}</td><td colspan="5"></td>${diffCell(o.recRow.toT)}<td class="n">${fmtSignedNum(o.recRow.toT.gold, "G", true)}</td></tr>` : "";
        const tid = "opts:" + c.name;
        const tlbl = `${c.name}（职业选择 · ${o.tier}）`;
        const hasCmt = (cmtSum.byTarget[tid] && cmtSum.byTarget[tid].total > 0) || (commentDraft && commentDraft.targetId === tid);
        const refSeeds = (o.recRow && o.recRow.toT && o.recRow.toT.seeds) || ((o.options.find(x => x.ok && x.toT) || {}).toT || {}).seeds || "";
        return `<details class="char" data-slug="${U.slug(c)}" data-cmt-target="${U.esc(tid)}" data-cmt-label="${U.esc(tlbl)}"${focus || hasCmt ? " open" : ""}><summary><h3>${chLink(c.name)}</h3><span>${o.tier} · Lv${o.level}→目标 Lv${o.target} · 已有 ${clsList(o.owned, "、")}${o.required.length ? ` · 必考 ${clsList(o.required, "、")}` : ""}${o.recommended.length ? ` · 推荐 ${clsList(o.recommended, "、")}` : " · 推荐：不考新职业"}</span></summary>
          <div class="sec" style="padding-bottom:0">${renderCommentBtn(tid, tlbl, "批注此角色职业选择")}${renderCommentThread(tid, tlbl)}</div>
          ${reasonsBox(c.name)}<div class="sec">${renderHighlightsBox(c, o)}<div class="scroll"><table><tr><th rowspan="2">职业</th><th class="n" rowspan="2">考的时机</th><th class="n" rowspan="2">判定值</th><th class="n" rowspan="2">成功率</th><th rowspan="2">要练 / 转职保底</th><th class="n" rowspan="2">用它升级<br><small>到 Lv${o.target}</small></th><th colspan="4" class="grp">到目标 Lv${o.target} 差距（同${refSeeds ? " " + refSeeds + " 个" : ""}乱数 · 含转职保底，相对不考）</th></tr><tr><th>能力差（到 Lv${o.target}）</th><th class="n">点数差</th><th class="n">加权分差</th><th class="n">金币差</th></tr>${rows}${rr}</table></div>${smTable(o)}</div></details>`;
      }).join("");
      return `<p class="lede">每个可考职业单独算：一定考到它、其余照规则走，和基准路线按同样多的乱数比到目标级（max(Lv35, 当前+15)；Lv35+ 可转上级职业不再拉长到 Lv45 失真），明确标出是否有转职保底，红绿着色区分增减，点数 / 加权分 / 金币 / 训练段数与乱数消耗差异分开展示。</p><div class="grid one">${cards}</div>`;
    }

    // ---------- 7. 我的决定（按档位 P0->P1->P2 排序 + 9 项能力差展开 + Plan Mode 批注） ----------
    function viewMine() {
      const sortedProps = RL.sortCharsByTier(PROPOSALS, RM.currentLord);
      const visibleProps = sortedProps.filter(pr => !focus || U.slug({ name: pr.name }) === focus);
      const sumAll = RL.summarizeRoutePicks(sortedProps, routePicks);
      const sumVis = RL.summarizeRoutePicks(visibleProps, routePicks);

      // 严格按 当前主角 -> P -> 强度 -> 名字排序
      const sortedRows = [...sumVis.rows];

      const proposalCards = sortedRows.map(({ proposal: pr, resolved: r }) => {
        const statusBadge =
          r.source === "user"
            ? `<span class="rec r1">✓ 你已选择：${U.esc(r.option.title)}</span>`
            : r.source === "default"
              ? `<span class="rec r0">✓ 默认已确认：${U.esc(r.option.title)}</span>`
              : r.source === "identical"
                ? `<span class="rec r3">新旧一致：${U.esc(r.option.title)}</span>`
                : `<span class="rec r2">⏳ 待你选择</span>`;

        const charTid = "char:" + pr.name;
        const charLbl = `${pr.name}（${pr.tier}）`;
        const isLord = Boolean(pr.isLord || (RM.currentLord && pr.name === RM.currentLord));

        return `<article class="card rp-card" id="rp-${U.esc(U.slug({ name: pr.name }))}" data-rp-char="${U.esc(pr.name)}" data-cmt-target="${U.esc(charTid)}" data-cmt-label="${U.esc(charLbl)}">
          <div class="ch"><div class="ct">
            <h3>${isLord ? '<span title="当前路线主角">★</span> ' : ""}${chLink(pr.name)}</h3>
            ${renderPTierBadge(pr.tier, pr.priorityNote)}
            ${renderStrengthBadge(pr)}
            <span class="lv">Lv${pr.level}→目标 Lv${pr.target}（${pr.seeds} 个乱数）</span>
            <span class="r">${statusBadge} ${renderCommentBtn(charTid, charLbl, "批注")}</span>
          </div>${pr.priorityNote ? `<p class="intro note2">📌 ${U.esc(pr.priorityNote)}</p>` : ""}</div>
          <div class="sec rp-opts">
            ${renderCommentThread(charTid, charLbl)}
            ${renderProposalOptionsBody(pr, r, "rpick-")}
          </div>
        </article>`;
      }).join("");

      const pickSummaryRows = sumAll.rows.map(({ proposal: pr, resolved: r }) => {
        const previewOpt = r.option || (pr.options || []).find(o => o.id === "new_best") || null;
        const d = previewOpt && previewOpt.diffVsBaseline ? previewOpt.diffVsBaseline : null;
        const isLord = Boolean(pr.isLord || (RM.currentLord && pr.name === RM.currentLord));
        const srcTag =
          r.source === "user" ? `<span class="tag ok">网页已选</span>`
          : r.source === "default" ? `<span class="cat-pill">默认已确认</span>`
          : r.source === "identical" ? `<span class="cat-pill">新旧一致</span>`
          : `<span class="tag warn">待选择</span>`;
        const cCnt = (cmtSum.byTarget["char:" + pr.name]?.open || 0)
          + (pr.options || []).reduce((acc, o) => acc + (cmtSum.byTarget[`opt:${pr.name}:${o.id}`]?.open || 0), 0);
        const planCell = r.option
          ? `<b>${clsText(r.option.title)}</b>`
          : (previewOpt ? `<span class="hint">候选：</span><b>${clsText(previewOpt.title)}</b>` : `<span class="hint">尚未选择</span>`);
        const netCell = previewOpt
          ? `${previewOpt.net}${d && previewOpt.id !== "old_baseline" ? ` (${U.sgn(d.net)})` : ""}${!r.option ? `<br><small class="hint">候选</small>` : ""}`
          : "—";
        const diffCell = previewOpt
          ? (previewOpt.id === "old_baseline"
              ? `<span class="hint">沿用旧路线</span>`
              : `<div class="sdiff-list">${renderStatDiffChips(d.statDiff, false)}</div>`)
          : "—";
        return `<tr class="${r.source === "pending" ? "cur" : ""}">
          <td><b>${isLord ? '<span title="当前路线主角">★</span> ' : ""}${chLink(pr.name, true)}</b> ${renderPTierBadge(pr.tier, pr.priorityNote)} ${renderStrengthBadge(pr)}${cCnt ? ` <span class="cmt-cnt">💬${cCnt}</span>` : ""}</td>
          <td>${srcTag}</td>
          <td>${planCell}</td>
          <td class="n">${netCell}</td>
          <td class="note">${diffCell}</td>
          <td class="note">${U.esc(r.note || "—")}</td>
          <td class="n">${r.at ? U.esc(r.at.slice(5, 16).replace("T", " ")) : "—"}</td>
        </tr>`;
      }).join("");

      const proposalSection = PROPOSALS.length ? `
        <section class="alerts" data-cmt-target="summary:proposals" data-cmt-label="全 9 人方案对比总表">
          <div class="pm-sec-head">
            <h2>新路线方案选择与确认（主角优先 · 按 P0→P1→P2 与强度排序 · 已确认 ${sumAll.confirmed} / ${sumAll.total} 人 · 待你选择 ${sumAll.pending} 人）</h2>
            ${renderCommentBtn("summary:proposals", "全 9 人方案对比总表", "批注总表")}
          </div>
          <p class="txt">每个候选方案均已展开<b>相对旧路线的 9 项具体能力差</b>、<b>转职保底</b>、金币/训练/精通差（职业精通不计入虚拟加权分，由你 case by case 拍板）与 S/L 提醒。你的每次点选与 Plan Mode 批注都会<b>自动保存在当前浏览器</b>。</p>
          ${RM.priorityLinkNote ? `<p class="hint" style="margin:2px 0 6px">${U.esc(RM.priorityLinkNote)}</p>` : ""}
          <div class="rp-toolbar">
            <button type="button" class="btn pri" data-rpick-copy>仅复制路线选择</button>
            ${sumAll.userPicked ? `<button type="button" class="btn ghost" data-rpick-reset>重置全部网页选择</button>` : ""}
          </div>
          ${renderCommentThread("summary:proposals", "全 9 人方案对比总表")}
          <div class="scroll" style="margin-top:8px"><table>
            <tr><th>角色</th><th>状态</th><th>当前方案</th><th class="n">净值 (Δ)</th><th>相对旧路线 9 项能力差</th><th>备注</th><th class="n">更新时间</th></tr>
            ${pickSummaryRows}
          </table></div>
        </section>
        <div class="grid one">${proposalCards}</div>
      ` : "";

      const rows = [];
      for (const c of CH) {
        if (focus && U.slug(c) !== focus) continue;
        for (const row of walkOf(c).rows) {
          const s = row.s, p = prog[U.keyOf(c, s)];
          if (!p) continue;
          const what = [];
          if (p.ok) what.push(`确认用 <b>${U.esc(row.choice)}</b>（${U.esc(row.r.gains.join(" ") || "—")}）`);
          if (p.choice) what.push(`改成 <b>${U.esc(p.choice === "exam" ? RL.stepName(s) : p.choice)}</b>（推荐是 ${U.esc(RL.recOf(s) || "—")}）`);
          if (p.chance != null) what.push(`游戏显示成功率 <b>${p.chance}%</b>`);
          if (!what.length) continue;
          const lv = s.exam ? `${RL.stepName(s)}（Lv${row.frm}）` : `Lv${row.frm}→${row.to}`;
          rows.push([p.at || "", `<tr><td><a href="#plan" data-go="${U.slug(c)}">${U.esc(U.shortName(c.name))}</a></td><td class="n">${U.esc(lv)}</td><td class="note">${what.join("；")}</td><td class="n">${p.at ? U.esc(p.at.slice(5, 16).replace("T", " ")) : "—"}</td></tr>`]);
        }
      }
      rows.sort((a, b) => b[0].localeCompare(a[0]));
      const live = rows.length
        ? `<div class="scroll"><table><tr><th>角色</th><th class="n">哪一步</th><th>你的决定</th><th class="n">时间（UTC）</th></tr>${rows.map(r => r[1]).join("")}</table></div>`
        : `<p class="txt">${focus ? "这个角色" : "页面上"}还没有单步改选记录。</p>`;
      const focusChar = focus ? CH.find(c => U.slug(c) === focus) : null;
      const rules = DECISIONS.filter(d => !focusChar || d.scope === "全部" || (d.scope || "").split("、").includes(U.shortName(focusChar.name)) || (d.scope || "").split("、").includes(focusChar.name)).slice().reverse();
      return `<p class="lede">在这里按档位（P0 → P1 → P2）对比并选择每位角色的新旧路线，或直接用上方 <b>Plan Mode 批注模式</b> 划词/就地添加批注并一键复制导出。</p>
        ${proposalSection}
        <section class="alerts"><h2>单步微调与实测记录（${rows.length}）</h2>${live}</section>
        <section class="alerts" data-cmt-target="rules:history" data-cmt-label="历史规划规则">
          <div class="pm-sec-head"><h2>历史规划规则（${rules.length}）</h2>${renderCommentBtn("rules:history", "历史规划规则", "批注规则")}</div>
          ${renderCommentThread("rules:history", "历史规划规则")}
          <div class="scroll"><table><tr><th class="n">日期</th><th>范围</th><th>规则</th></tr>${rules.map(d => `<tr><td class="n">${U.esc(d.date)}</td><td>${U.esc(d.scope)}</td><td class="note">${U.esc(d.rule)}</td></tr>`).join("")}</table></div>
        </section>`;
    }

    let body = "";
    if (view === "plan") body = viewPlan();
    else if (view === "past") body = viewPast();
    else if (view === "l45") body = viewL45();
    else if (view === "long") body = viewLong();
    else if (view === "opts") body = viewOpts();
    else if (view === "mine") body = viewMine();
    else body = viewNext();

    return renderPlanModeBar() + body;
  }

  root.FE = root.FE || {};
  root.FE.views = root.FE.views || {};
  root.FE.views.renderRouteView = renderRouteView;
})(window);
