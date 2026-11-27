/* 模块 3：路线规划视图（下一步 / 到目标级 / 回顾 / 到 Lv45 / 长线观星 / 职业选择 / 我的决定）
 * 说明区全部从 routeData.rulesMeta 动态渲染，不再硬编码会过时的规则文本。
 */
(function (root) {
  const U = root.FE.utils;
  const RL = root.FE.routeLogic;
  const CL = root.FE.commentsLogic;
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

  function renderRouteView(view, D, state) {
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
        return `<div class="cmt-item${c.resolved ? " resolved" : ""}" data-cmt-id="${U.esc(c.id)}">
          ${c.quote ? `<blockquote class="cmt-quote">「${U.esc(c.quote)}」</blockquote>` : ""}
          <div class="cmt-text">${U.esc(c.text)}</div>
          <div class="cmt-meta">
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
        ? planComments.map(c => `
            <div class="cmt-drawer-row${c.resolved ? " resolved" : ""}">
              <div class="cmt-dr-top">
                <span class="cat-pill">${U.esc(c.targetLabel)}</span>
                <span class="hint">${c.at ? U.esc(c.at.slice(5, 16).replace("T", " ")) : ""}</span>
                <span class="r">
                  <button type="button" class="cmt-act" data-cmt-resolve="${U.esc(c.id)}">${c.resolved ? "↺ 重开" : "✓ 已解决"}</button>
                  <button type="button" class="cmt-act dn" data-cmt-del="${U.esc(c.id)}">删除</button>
                </span>
              </div>
              ${c.quote ? `<blockquote class="cmt-quote">「${U.esc(c.quote)}」</blockquote>` : ""}
              <div class="cmt-text">${U.esc(c.text)}</div>
            </div>`).join("")
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

    function timingBox(e) {
      const t = e.timing || [];
      if (!t.length) return `<br><span class="hint">考试时机：窗口里没有别的乱数能考过，只能在这一级考。</span>`;
      const P = x => `${x.pts > 0 ? "+" : ""}${x.pts} 点 / ${x.w > 0 ? "+" : ""}${x.w}`;
      return `<details class="more"><summary>换到别的乱数考（${t.length} 个能考过）：现在这场比它们 ${t.every(x => x.total.w >= 0) ? "都不差" : "有更好的"}</summary>
        <div class="scroll" style="max-width:calc(100vw - 100px)"><table><tr><th>改在</th><th class="n">判定值 / 成功率</th><th>① 考试用掉的乱数</th><th>② 用不同职业升级</th><th>③ 转职保底</th><th>合计（现在减它）</th><th class="n">金币</th></tr>
        ${t.map(x => `<tr><td>Lv${x.lv}（第 ${x.step + 1} 个乱数）</td><td class="n">${x.roll} / ${x.pct ?? "—"}%</td><td class="n">${P(x.exam)}</td><td class="n">${P(x.cls)}</td><td class="n">${P(x.floor)}</td><td class="n ${x.total.w > 0 ? "up" : x.total.w < 0 ? "dn" : ""}"><b>${P(x.total)}</b></td><td class="n">${x.gold > 0 ? "+" : ""}${x.gold}G</td></tr>`).join("")}</table></div>
        <p class="hint" style="max-width:calc(100vw - 100px)">${t[0].explain.map(U.esc).join("<br>")}</p></details>`;
    }

    function trainBox(c, w) {
      const done = new Set(w.rows.filter(r => r.done).map(r => r.s.key));
      const todo = (c.trainPlan || []).filter(t => !done.has(t.key));
      if (!todo.length) return "";
      return `<div class="sec"><h4>要练的技能</h4><ul class="txt">${todo.map(t => `<li>🎯 <b>Lv${t.lv}</b> 考${U.esc(t.cls)}之前练好：${U.esc(t.train.join("、"))}（共 ${t.ranks} 段；训练场、指南书、委托都不涨人物经验，不影响种子）</li>`).join("")}</ul></div>`;
    }

    function head(c, w, right) {
      const n = w.rows.filter(r => r.done).length;
      const cmtBtn = renderCommentBtn("route:" + c.name, `${c.name}（路线规划）`, "批注");
      return `<div class="ch" data-cmt-target="route:${U.esc(c.name)}" data-cmt-label="${U.esc(c.name)}（路线规划）"><div class="ct"><h3>${U.esc(c.name)}</h3><span class="lv">Lv${w.ci.level ?? "?"} ${U.esc(w.cur || "")}</span><span class="r">${right} ${cmtBtn}</span></div>
        ${c.steps.length ? `<div class="meter" title="完成 ${n} / ${c.steps.length}"><i style="width:${100 * n / c.steps.length}%"></i></div>` : ""}
        ${c.weights ? `<div class="wts" title="能力权重，加权分 = 每项加点 × 权重">${ST.map((k, i) => `<span class="w${c.weights[i]}">${k}<b>${c.weights[i]}</b></span>`).join("")}</div>` : ""}
        ${c.text ? `<p class="intro">${U.esc(c.text.intro)}</p>` : ""}${c.text && c.text.note ? `<p class="intro note2">${U.esc(c.text.note)}</p>` : ""}${c.guide ? `<p class="intro note2"><b>攻略评价 ${U.esc(c.guide.tier)}</b>（憨色 Ver1.0）：${U.esc(c.guide.t)}</p>` : ""}
        ${renderCommentThread("route:" + c.name, `${c.name}（路线规划）`)}</div>`;
    }

    function optsHtml(c, s, row, idp) {
      const name = idp + "o-" + U.keyOf(c, s);
      const groups = s.opts.length ? s.opts : (s.seenCls ? [{ classes: [s.seenCls], owned: [true], gains: s.gains, cnt: s.cnt, score: s.score }] : []);
      const o = groups.map(g => {
        const val = g.classes.includes(s.cls) ? s.cls : (g.classes.find((x, i) => g.owned[i]) || g.classes[0]);
        const have = s.src === "record" ? g.classes : g.classes.filter((x, i) => g.owned[i]);
        const need = s.src === "record" ? [] : g.classes.filter((x, i) => !g.owned[i]);
        const label = U.esc(have.join(" / ")) + (need.length ? `<span class="need">${have.length ? "　" : ""}要先考试：${U.esc(need.join(" "))}</span>` : "");
        const on = row.choice === val || (!row.r.exam && row.r.classes && RL.resultOf(s, val) === row.r);
        return `<label class="opt"><input type="radio" name="${name}" value="${U.esc(val)}" data-f="pick"${have.length ? "" : ' data-need="1"'}${on ? " checked" : ""}><span><span class="oc">${label}</span>　${U.esc(g.gains.join(" ") || "—")}</span><span class="on">${g.cnt}点 · ${g.score}分</span></label>`;
      }).join("");
      const ex = `<label class="opt"><input type="radio" name="${name}" value="exam" data-f="pick"${row.r.exam ? " checked" : ""}><span><span class="oc">${RL.examName(s) ? "考试（到 " + U.esc(RL.examName(s)) + "）" : "跳过"}</span>　这一步不升级${s.roll != null ? `（判定值 ${s.roll}%）` : ""}</span><span class="on"></span></label>`;
      return `<div class="opts" role="radiogroup" aria-label="这一步的选择">${o}${ex}</div><button type="button" class="btn pri" data-apply data-cur="${U.esc(row.r.exam ? "exam" : row.choice)}" data-lv="${s.exam ? "这一步" : `Lv${row.frm}→${row.to}`}" style="display:none">确认更改</button>`;
    }

    function examBox(c, s) {
      const v = verdictOf(c, s), n = RL.examName(s);
      const verdict = v.pass == null ? "" : v.pass ? `<span class="ok">✓ 能过${n ? "，拿到" + U.esc(n) : ""}</span>`
        : `<span class="bad">✗ 会失败${n ? "，拿不到" + U.esc(n) + "，后面用它的步骤要改" : "，没关系，只当跳过"}</span>`;
      return `<div class="exambox"><div>判定值 <b>${s.roll}%</b>：游戏里显示的成功率要<b>高于</b>它才能过。过不过种子都前进一步。${s.pct != null ? ` 按${shotLabel}技能和考试时的等级估计显示 <b>${s.pct}%</b>${s.pct > s.roll ? "，能过" : "，过不了"}。` : ""}</div>
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
        ${li(1, `正常（${U.esc(prev || "现在的职业")}）`, g1 ? gline(g1) : "现在的职业不在已有职业里")}
        ${li(2, "转职（换已有职业再升级）", g2 ? `${U.esc(g2.classes.filter((x, i) => g2.owned[i]).join(" / "))}：${gline(g2)}${g1 && g2.score <= g1.score ? "，不比正常好" : ""}` : "没有别的已有职业")}
        ${li(3, "考试（考新职业，这一级不升级）", ex.length ? ex.map(e => `${e.cls === pn ? "<b>" : ""}${U.esc(e.cls)}${e.cls === pn ? "</b>" : ""}（${U.esc(e.tier)}）：${prob(e)}`).join("<br>") : "没有能考的新职业")}
        ${li(4, "跳过（300G 初级手形，这一级不升级）", `${basic ? `用${U.esc(basic.cls)}的考试：${prob(basic)}，过不过都行` : `用任意一场初级考试跳过：判定值 ${rt.roll}%，过不过都行`}<br>这一级最高 ${best} 分，未来 15 级平均 ${rt.avg15}（10 级 ${rt.avg10}），${gap > 0 ? `低 ${gap} 分（${Math.round(100 * gap / rt.avg15)}%）` : `高 ${-gap} 分`}${ruleTxt}`)}
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
      const stop = [], go = [], alertRows = [];
      for (const c of CH) {
        if (focus && U.slug(c) !== focus) continue;
        const w = walkOf(c), nx = w.rows.filter(r => !r.done);
        if (!nx.length) continue;
        const a = `<a href="#next" data-go="${U.slug(c)}">${U.esc(U.shortName(c.name))}</a>`;
        const first = nx[0], s = first.s;
        if (first.r.exam) {
          const n = RL.examName(s), v = verdictOf(c, s);
          stop.push([n ? "exam" : "skip", a, n ? `先考<b>${U.esc(n)}</b>（判定值 ${s.roll}%${s.pct != null ? `，估计显示 ${s.pct}%` : ""}）` : `先<b>跳过</b>一级（用任意一场初级考试，判定值 ${s.roll}%，过不过都行）`]);
          if (v.pass === false && n) alertRows.push(["bad", `${a}：考${U.esc(n)}会失败（游戏 ${v.ch}% ≤ 判定值 ${s.roll}%）。先把技能练上去再考。`]);
          else alertRows.push(["warn", `${a}：先${n ? "考试（到 " + U.esc(n) + "）" : "跳过"}，做完再升级。先升级的话种子会错位。`]);
        } else if (first.missing) {
          stop.push(["miss", a, `要用<b>${U.esc(first.choice)}</b>，但还没考到，先考`]);
        } else if (w.cur && first.choice !== w.cur) {
          stop.push(["cls", a, `先转职 ${U.esc(w.cur)} → <b>${U.esc(first.choice)}</b>，再升 Lv${first.frm}→${first.to}`]);
        } else {
          go.push(`${a} 用${U.esc(RL.eqName(first))}升 Lv${first.frm}→${first.to}`);
        }
        const miss = nx.find(r => r.missing);
        if (miss) alertRows.push(["bad", `${a}：Lv${miss.frm}→${miss.to} 要用${U.esc(miss.choice)}，但前面没有考到它（或那场考试估计过不了）。`]);
        for (const row of nx.slice(0, 4)) {
          if (!row.r.exam || !RL.examName(row.s)) continue;
          const v = verdictOf(c, row.s);
          if (v.pass == null && row.s.pct != null && row.s.pct < 100 && row.s.roll >= row.s.pct - 20) {
            alertRows.push([row.s.roll >= row.s.pct ? "bad" : "warn", `${a}：${U.esc(row.s.cls)} 判定值 ${row.s.roll}%，估计显示 ${row.s.pct}%${row.s.roll >= row.s.pct ? "，过不了" : "，很险"}。`]);
          }
        }
      }
      if (!alertRows.length) alertRows.push(["ok", "最近几步没有要特别注意的。"]);
      const tag = { exam: ["warn", "考试"], skip: ["warn", "跳过"], miss: ["bad", "缺职业"], cls: ["ok", "转职"] };
      const gateHtml = `<section class="alerts"><h2>暂时不能直接升级</h2><ul>${stop.length ? stop.map(([k, a, t]) => `<li><span class="sev ${tag[k][0]}">${tag[k][1]}</span><span>${a}：${t}</span></li>`).join("") : `<li><span class="sev ok">无</span><span>所有人都可以直接升级</span></li>`}</ul>${go.length ? `<p class="txt" style="font-size:13px"><span class="lab">可以直接升级</span>${go.join("；")}</p>` : ""}</section>`;
      const alertsHtml = `<section class="alerts" aria-label="要注意"><h2>升级前先看</h2><ul>${alertRows.map(([k, t]) => `<li><span class="sev ${k}">${k === "bad" ? "会失败" : k === "warn" ? "注意" : "正常"}</span><span>${t}</span></li>`).join("")}</ul></section>`;

      const cards = CH.filter(c => !focus || U.slug(c) === focus).map(c => {
        const w = walkOf(c), leftRows = w.rows.filter(r => !r.done), nx = leftRows.slice(0, 3), rm = remainOf(c, w);
        const items = nx.map((row, i) => {
          const s = row.s, r = row.r, first = i === 0;
          const changed = row.choice !== RL.recOf(s) ? ` <span class="changed">已改（原来：${U.esc(s.exam ? RL.stepName(s) : s.cls)}）</span>` : "";
          const src = s.src === "record" ? (s.hidden ? "没记录的一步" : "观星已记录") : "规划";
          let body;
          if (r.exam) {
            const n = RL.examName(s);
            const curG = s.opts.find(g => g.classes.includes(w.cur));
            body = `<div class="what"><b>${n ? "考试（到 " + U.esc(n) + "）" : s.src === "record" ? "跳过（观星记录里这步没有升级）" : "跳过"}</b>${changed}</div>
              ${curG ? `<div class="hint">考前先观星确认种子：用${U.esc(w.cur)}升级应看到 <b>${U.esc(curG.gains.join(" ") || "—")}</b>（${U.PW(curG.cnt, curG.score)}）。对上了再去考。</div>` : ""}
              ${s.roll != null ? examBox(c, s) : ""}`;
          } else {
            body = `<div class="what"><b>升 Lv${row.frm}→${row.to}，用${U.esc(RL.eqName(row))}</b>${changed}${row.missing ? ` <span class="changed">还没考到${U.esc(row.choice)}，这一级前要先考</span>` : ""}<span class="sc">${U.PW(r.cnt, r.score)} ${vsTag(r.score, s.es)}</span></div>
              <div class="chips">${r.gains.map(chip).join("") || '<span>—</span>'}</div>
              ${s.why && !/^已有职业里分最高/.test(s.why) ? `<div class="hint">${U.esc(s.why)}</div>` : ""}
              ${r.classes && r.classes.length > 1 ? `<div class="hint">加点相同的职业：${U.esc(r.classes.filter(x => x !== row.choice).join(" "))}</div>` : ""}`;
          }
          return `<li class="${r.exam ? "exam " : ""}${first ? "first" : ""}" data-key="${s.key}">
            <div class="when"><span>${first ? "现在做" : i === 1 ? "然后" : "再然后"}</span><span class="src">${src}</span></div>
            ${body}${routesBox(c, w, row)}
            <div class="acts">${first ? `<button class="btn pri" type="button" data-do="done">✓ 做完了</button>` : ""}
              <details class="more"><summary>换个选择（这一步所有职业）</summary>${optsHtml(c, s, row, "n")}</details></div>
          </li>`;
        }).join("");
        return `<article class="card" data-slug="${U.slug(c)}" id="${U.slug(c)}">${head(c, w, `还剩 ${leftRows.length} 步 → Lv${w.endLevel}`)}
          ${nx.length ? `<ol class="next">${items}</ol>` : ""}${trainBox(c, w)}${nx.length ? "" : `<div class="empty">${c.steps.length ? "路线上的步骤都完成了。" : "还没有观星记录和种子，暂时没有路线。"}</div>`}
          <div class="cfoot">${c.steps.length ? `<span>按现在的选择到 Lv${w.endLevel} 还会升 <b>${rm.lv}</b> 级、涨 <b>${rm.cnt}</b> 点，加权分 <b>${rm.sc}</b>。<a href="#plan" data-go="${U.slug(c)}">看完整路线</a></span>` : ""}${stateHtml(c, w)}</div>
        </article>`;
      }).join("");
      return `<p class="lede">每人最近 3 步，第一步是现在要做的。</p>${gateHtml}${alertsHtml}<div class="grid">${cards}</div>` + notesBox([
        "做完一步点「✓ 做完了」，等级和已完成会自动往后推。",
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
      return `<br><span class="hint">改考中级（${ok.length} 个能考过）：${b.d.total > 0 || b.d.pts > 0 ? "数值最好的是" : "用得上的最好是"} <b>${U.esc(b.cls)}</b>，${smDiff(b.d)}${b.ranks ? `、先练 ${b.ranks} 段` : ""}，用它升 ${b.used} 级 → ${b.worth ? "<b>值得</b>" : "不值得，照跳过"}（全部选项见「职业选择」）</span>`;
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
            if ((prog[U.keyOf(c, s)] || {}).ok) return `<li data-slug="${U.slug(c)}"><div data-key="${s.key}" class="dh"><b>${U.esc(U.shortName(c.name))} Lv${row.frm}→${row.to}</b><span class="ok">✓ 已确认：${U.esc(row.choice)}（${U.esc(row.r.gains.join(" ") || "—")}）</span><button type="button" class="btn ghost" data-dec="undo">重新选</button></div></li>`;
            const name = "dec-" + U.keyOf(c, s);
            const opt = g => {
              const val = g.classes.includes(s.cls) ? s.cls : g.classes.find((x, i) => g.owned[i]);
              const on = row.choice === val || (row.r.classes && row.r.classes.includes(val)) || g.classes.includes(row.choice);
              return `<label class="opt"><input type="radio" name="${name}" value="${U.esc(val)}" data-f="pick"${on ? " checked" : ""}><span><span class="oc">${U.esc(g.classes.filter((x, i) => g.owned[i]).join(" / "))}${g === rec ? "（推荐）" : ""}</span>　${U.esc(g.gains.join(" ") || "—")}</span><span class="on">${g.cnt}点 · ${g.score}分</span></label>`;
            };
            return `<li data-slug="${U.slug(c)}"><div data-key="${s.key}"><div class="dh"><b>${U.esc(U.shortName(c.name))} Lv${row.frm}→${row.to}</b><small>${kind}</small></div>${s.note ? `<div class="note">${U.esc(s.note)}</div>` : ""}<div class="opts" role="radiogroup" aria-label="这一步选哪个">${[rec, ...alts].map(opt).join("")}</div><button type="button" class="btn" data-dec="ok">确认：用 ${U.esc(row.choice)}</button></div></li>`;
          }).join("")}</ul></section>`);

      const ovRows = CH.filter(c => !focus || U.slug(c) === focus).map(c => {
        const a = c.avg; if (!a) return "";
        const ap = U.psum(a.act), dv = Math.round(a.ws - a.wexp);
        const ex = []; let lv = null;
        for (const x of c.route || []) { if (x[0] === "up") { lv = x[3]; continue; } ex.push(x[1] ? `${U.esc(x[1])}（Lv${lv ?? c.planFrom}，判定 ${x[2]}%）` : ""); }
        const skips = (c.route || []).filter(x => x[0] === "exam" && !x[1]).length;
        const exs = ex.filter(Boolean);
        return `<tr><td><a href="#plan" data-go="${U.slug(c)}">${U.esc(U.shortName(c.name))}</a>${c.tier ? ` <span class="rec ${c.tier === "P0" ? "r1" : c.tier === "P1" ? "r2" : "r3"}">${c.tier}</span>` : ""}</td><td class="n">Lv${c.planFrom}→${c.planTo}</td><td class="n"><b>${a.ws}</b></td><td class="n">${ap}</td><td class="n ${dv >= 3 ? "up" : dv <= -3 ? "dn" : ""}">${U.sgn(dv)}</td><td class="note">${exs.length ? exs.join("、") : "不转新职业"}${skips ? `；跳过 ${skips} 次` : ""}</td></tr>`;
      }).join("");
      const ovBox = `<section class="alerts"><h2>路线一览（到目标级）</h2><div class="scroll"><table class="ovt"><tr><th>角色</th><th class="n">等级</th><th class="n">加权分</th><th class="n">点数</th><th class="n">比平均</th><th>要考的职业</th></tr>${ovRows}</table></div></section>`;

      const odd = [];
      const shortFlag = t => t.replace(/到 Lv\d+ (只)?涨 /, " +").replace(/，平均 ([\d.]+)/, "（平均 $1").replace(/（权重 (\d)）/, "，权重 $1").replace(/，明显偏(高|低).*$/, "）");
      for (const c of CH) {
        if (focus && U.slug(c) !== focus) continue;
        const fs = ((c.trend && c.trend.flags) || []).filter(f => f.lv !== "warn");
        if (!fs.length) continue;
        const hi = fs.filter(f => f.lv === "good").map(f => U.esc(shortFlag(f.t)));
        const lo = fs.filter(f => f.lv === "bad").map(f => U.esc(shortFlag(f.t)));
        odd.push(`<li class="oddc"><a href="#plan" data-go="${U.slug(c)}">${U.esc(U.shortName(c.name))}</a><span>${hi.length ? `<span class="sev ok">偏高</span> ${hi.join("、")}` : ""}${hi.length && lo.length ? "　" : ""}${lo.length ? `<span class="sev bad">偏低</span> ${lo.join("、")}` : ""}</span></li>`);
      }
      const oddBox = odd.length ? `<section class="alerts"><h2>明显异常的能力（不管权重高低）</h2><ul>${odd.join("")}</ul></section>` : "";

      const balRows = CH.filter(c => !focus || U.slug(c) === focus).flatMap(c => (c.balance || []).map(b =>
        `<li><span class="sev warn">均衡</span><span><a href="#plan" data-go="${U.slug(c)}">${U.esc(U.shortName(c.name))}</a> <b>${U.esc(b.lv)}</b>：用 <b>${U.esc(b.pick)}</b> 换 ${U.esc(b.orig)}（多 ${U.esc(b.more)}、少 ${U.esc(b.less)}；这一级加权 ${b.dsc > 0 ? "+" : ""}${b.dsc}）。原因：${U.esc(b.why)}</span></li>`
      ));
      const noneBal = CH.filter(c => (!focus || U.slug(c) === focus) && !(c.balance || []).length).map(c => U.shortName(c.name));
      const balBox = `<section class="alerts"><h2>均衡加点换了职业的等级</h2>${balRows.length ? `<ul>${balRows.join("")}</ul>` : ""}<p class="hint" style="margin:4px 0 0">${noneBal.length ? U.esc(noneBal.join("、")) + "：没有。" : ""}</p></section>`;

      const cards = CH.filter(c => !focus || U.slug(c) === focus).map(c => {
        const w = walkOf(c), rm = remainOf(c, w), a = c.avg;
        const ap = U.psum(a ? a.act : []), ep = Math.round(U.psum(a ? a.exp : []));
        const right = a ? `推荐路线 ${U.PW(ap, a.ws)} · 平均 ${U.PW(ep, a.wexp.toFixed(0))}（${U.sgn(ap - ep)} 点 · ${U.sgn(Math.round(a.ws - a.wexp))} 分）` : "";

        // 变更清单
        const items = []; let cur = null; const ownedSet = new Set(c.owned);
        for (const x of c.route || []) {
          if (x[0] === "exam") {
            if (x[1]) items.push(`考试（到 <b>${U.esc(x[1])}</b>）（${ownedSet.has(x[1]) ? "已有" : "新职业"}；判定值 ${x[2]}%${x[3] == null ? "" : `，估计显示 ${x[3]}%`}）${(c.trainPlan || []).filter(t => t.cls === x[1]).map(t => ` <span class="changed">🎯 Lv${t.lv} 考前练好：${U.esc(t.train.join("、"))}</span>`).join("")}${x[4] != null ? `<div class="hint" style="margin:2px 0 0">之后到 Lv${c.planTo} 用它升 <b>${x[4]}</b> 级${x[4] ? `，比每级改用已有职业里最好的：<b>${U.esc(x[5])}</b>（${U.sgn(x[6])} 分）` : "（只为拿到职业或精通，不用来升级）"}</div>` : ""}`);
            else items.push(`跳过一级（判定值 ${x[2]}%，过不过都行）`);
            if (x[1]) ownedSet.add(x[1]);
            continue;
          }
          if (cur === null) items.push(`Lv${x[2]} 起用 <b>${U.esc(x[1])}</b>${c.curClass && x[1] !== c.curClass ? `（现在是${U.esc(c.curClass)}，先转职）` : ""}`);
          else if (x[1] !== cur) items.push(`Lv${x[2]} 转职 ${U.esc(cur)} → <b>${U.esc(x[1])}</b>`);
          cur = x[1];
        }
        const news = [...new Set((c.route || []).filter(x => x[0] === "exam" && x[1]).map(x => x[1]))];
        const changesHtml = `<p class="txt"><span class="lab">要考的职业</span>${news.length ? news.map(U.esc).join("、") : "不用考新职业"}　<span class="lab">已有</span>${U.esc(c.owned.join("、"))}</p><ol class="chg">${items.map(t => `<li>${t}</li>`).join("")}</ol>`;
        const routeTxt = (c.route || []).map(x => x[0] === "up"
          ? `<span class="rt">Lv${x[2]}→${x[3]} ${U.esc(x[1])}</span>`
          : `<span class="rt x">${x[1] ? "考试（到 " + U.esc(x[1]) + "）" : "跳过"} · 判定值 ${x[2]}%${x[1] ? (x[3] == null ? "" : ` · 估计显示 ${x[3]}%`) : ""}</span>`
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
          return `<li class="${row.done ? "done" : ""} ${r.exam ? "isx" : ""}" data-key="${s.key}">
            <input type="checkbox" data-f="done" id="d-${U.keyOf(c, s)}"${row.done ? " checked" : ""} aria-label="已完成">
            <label class="lvl" for="d-${U.keyOf(c, s)}">${r.exam ? (RL.examName(s) ? "考试" : "跳过") : `Lv${row.frm}→${row.to}`}</label>
            <div class="body">${r.exam ? `${RL.examName(s) ? "考试（到 " + U.esc(RL.examName(s)) + "）" : (s.skipNone ? `跳过 <span class="changed">没有可用的初级考试</span>` : s.skipFail && s.skipFail.length ? `跳过（考 ${U.esc(s.skipFail.join(" / "))}，会考不过，不拿职业）` : s.skipCls ? `跳过（只能考 ${U.esc(s.skipCls)}，会考过，用掉一个可跳过的职业，还剩 ${s.skipLeft} 个）` : "跳过")}${s.train && RL.examName(s) ? (s.trainOk ? ` <span class="changed">🎯 Lv${s.trainLv} 考试前练好：${U.esc(s.train.join("、"))}</span>` : ` <span class="changed">技能差：${U.esc(s.train.join("、"))}（不练，按实际成功率）</span>`) : ""}<span class="hint">　判定值 ${s.roll}%${RL.examName(s) && s.pct != null ? `｜估计成功率 ${s.pct}%${s.train && s.trainOk ? "（练够之后）" : ""}` : ""}${s.renown && RL.examName(s) ? `｜要名声 Lv${s.renown}` : ""}</span>${s.floor && s.floor.length ? ` <span class="changed">转职保底：${U.esc(s.floor.join("、"))}</span>` : ""}${!RL.examName(s) ? smHint(c, s) : ""}${s.use && RL.examName(s) ? `<span class="hint">　之后到 Lv${c.planTo} 用它升 ${s.use[0]} 级${s.use[0] ? `：${U.esc(s.use[1])}（${U.sgn(s.use[2])} 分）` : ""}</span>` : ""}` : `<b>${U.esc(RL.eqName(row))}</b>　${U.esc(r.gains.join(" ") || "—")}`}${row.choice !== RL.recOf(s) ? ` <span class="changed">已改</span>` : ""}${row.missing ? ` <span class="changed">还没考到</span>` : ""}${row.fail ? ` <span class="changed">估计考不过</span>` : ""}
              ${row.done ? "" : `<details class="more"><summary>选择</summary>${optsHtml(c, s, row, "f")}</details>`}</div>
            <span class="sc">${r.exam ? "—" : U.PW(r.cnt, r.score)}</span></li>`;
        }).join("")}</ol></div>`;

        // 趋势图与时间轴
        const tlRows = w.rows.filter(r => r.s.src === "plan" || !r.done);
        const mx = Math.max(20, ...tlRows.map(r => (r.r.exam ? 0 : r.r.score)));
        const tlHtml = tlRows.length ? `<div class="tl" role="img" aria-label="每一步的加权分">${tlRows.map(r => {
          if (r.r.exam) return `<div title="${U.esc(RL.stepName(r.s))}"><i class="x${r.done ? " done" : ""}"></i><span>${RL.examName(r.s) ? "转" : "跳"}</span></div>`;
          const es = r.s.es, d = es == null ? null : r.r.score - es, k = d == null ? "" : d >= 2 ? "up" : d <= -2 ? "dn" : "eq";
          const h = Math.max(4, 64 * r.r.score / mx);
          return `<div title="Lv${r.frm}→${r.to} ${U.esc(r.choice)}：${U.PW(r.r.cnt, r.r.score)}"><i class="${k}${r.done ? " done" : ""}" style="height:${h}px">${es != null ? `<b style="bottom:${64 * es / mx}px"></b>` : ""}</i><span>${r.to}</span></div>`;
        }).join("")}</div><div class="legend"><span style="--k:var(--good)">好于平均 2 分以上</span><span style="--k:var(--bad)">低于平均 2 分以上</span><span style="--k:var(--muted)">差不多</span><span style="--k:var(--exam)">考试或跳过</span><span>横线 = 平均运气</span></div>` : "";

        // 每次考试值不值 + 多转一个中级
        const eb = (c.hist && c.hist.exam_benefit) || [];
        const mg = c.midGain || [];
        const examSec = `<div class="sec"><h4>每次考试值不值</h4>
          ${eb.length ? `<div class="scroll"><table><tr><th>考试</th><th class="n">判定值</th><th>比不考它的最好路线</th><th class="n">点数</th><th class="n">加权分</th><th class="n">多花</th></tr>${eb.map(e => `<tr><td>${U.esc(e.cls)}${e.req ? " · 必考" : ""}</td><td class="n">${e.roll}%</td><td>${U.esc(U.gtxt(e.diff, ST))}</td><td class="n">${U.sgn(U.psum(e.diff))}</td><td class="n">${U.sgn(e.wdiff)}</td><td class="n">${e.dgold == null ? "—" : e.dgold + "G"}</td></tr>`).join("")}</table></div>` : `<p class="txt">推荐路线不考试。</p>`}
          ${mg.length ? `<h4 style="margin-top:8px">多转一个中级值多少</h4><div class="scroll"><table><tr><th>多转</th><th class="n">用它升级</th><th>能力差</th><th class="n">点数差</th><th class="n">加权分</th><th class="n">比现在</th><th class="n">手形</th><th>说明</th></tr>${mg.map(r => `<tr><td>${U.esc(r.cls)}</td><td class="n">${r.used}</td><td class="note">${U.esc(r.diff || "")}</td><td class="n">${r.dpts == null ? "—" : U.sgn(r.dpts)}</td><td class="n">${r.total}</td><td class="n">${U.sgn(r.dsc)}</td><td class="n">${r.gold}G</td><td class="note">${r.dnet > 0 ? "净值略高（被组合顺序挡住），值得看看" : "综合金币与训练后不选"}</td></tr>`).join("")}</table></div>` : ""}
        </div>`;

        return `<article class="card" data-slug="${U.slug(c)}" id="${U.slug(c)}">${head(c, w, right)}
          <details class="more cbody"${focus ? " open" : ""}><summary>展开：路线、能力、考试和每一步</summary>
            ${c.examWarn ? `<div class="sec"><p class="txt"><span class="sev warn">注意</span> 这条路线考试 + 跳过一共 ${c.exams} 次，比较多（手形 ${c.planGold}G）。</p></div>` : ""}
            ${trainBox(c, w)}
            ${c.route ? `<div class="sec"><h4>推荐路线</h4>${changesHtml}<details class="more"><summary>逐级一览</summary><div class="route">${routeTxt}</div></details></div>` : ""}
            <div class="sec"><h4>能力到 Lv${w.endLevel}</h4>${statTable}</div>
            ${examSec}
            ${tlHtml ? `<div class="sec"><h4>每一步的加权分<small>按现在的选择，剩 ${U.PW(rm.cnt, rm.sc)}</small></h4>${tlHtml}</div>` : ""}
            ${c.steps.length ? `<div class="sec"><details class="more" open><summary>逐级路线和所有选择（可以改）</summary>${fullList}</details></div>` : ""}
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
          <tr><td>Lv${h.join.lv} 入队</td><td>${U.esc(h.join.cls)}</td>${cells(h.join.stats)}${pw(h.join.stats)}<td class="note">${U.esc(h.join.note || "初始能力（不含职业补正）")}</td></tr>`;
        if (h.gap) pt += `<tr><td>Lv${h.gap.frm}→${h.gap.to}</td><td>${h.gap.n} 级合计</td>${cells(h.gap.g, true)}${pw(h.gap.g)}<td class="note">无观星记录，仅合计</td></tr>`;
        for (const r of h.past) {
          if (r.kind === "考试") pt += `<tr class="exam"><td>${U.esc(r.lv)}</td><td>考试 ${U.esc(r.cls)}</td>${ST.map(() => "<td></td>").join("")}<td></td><td></td><td class="note">${U.esc(r.note)}</td></tr>`;
          else pt += `<tr><td>${U.esc(r.lv)}</td><td>${U.esc(r.cls)}</td>${cells(r.g, true)}${pw(r.g)}<td class="note">${U.esc(r.note)}</td></tr>`;
        }
        pt += `<tr class="sum"><td colspan="2">入队以来合计涨</td>${cells(gained, true)}${pw(gained)}<td class="note">每级平均 ${(U.psum(gained) / Math.max(1, n.lv - h.join.lv)).toFixed(1)} 点</td></tr>
          <tr class="sum"><td colspan="2">截图时裸能力</td>${cells(n.raw)}${pw(n.raw)}<td class="note">能力总和</td></tr></table>`;
        let nt = `<table><tr><th></th>${th}<th>说明</th></tr>
          <tr><td>${shotLabel} Lv${n.lv} ${U.esc(n.cls)}</td>${cells(n.shot)}<td class="note">游戏里显示的</td></tr>
          <tr><td>− 职业补正</td>${cells(n.bonus.map(v => -v), true)}<td class="note">${U.esc(n.cls)}自带</td></tr>
          <tr><td>− ▲加成</td>${cells(n.boost.map(v => -v), true)}<td class="note">${U.esc(n.boost_note)}</td></tr>
          <tr class="sum"><td>= 裸能力</td>${cells(n.raw)}<td></td></tr></table>`;
        return `<details class="char" id="${U.slug(c)}"${focus || i === 0 ? " open" : ""}><summary><h3>${U.esc(c.name)}</h3><span>Lv${h.join.lv} ${U.esc(h.join.cls)} → Lv${n.lv} ${U.esc(n.cls)} · 裸能力 ${U.psum(h.join.stats)} → ${U.psum(n.raw)} 点</span></summary>
          <div class="sec"><h4>每一级</h4><div class="scroll">${pt}</div></div>
          <div class="sec"><h4>现在：截图 → 裸能力</h4><div class="scroll">${nt}</div></div></details>`;
      }).join("") + notesBox(["<b>裸能力</b> = 截图数值去掉职业补正和▲加成。", N_PTS]);
    }

    // ---------- 4. 到 Lv45 ----------
    function viewL45() {
      const list = CH.filter(c => c.l45 && (!focus || U.slug(c) === focus));
      const fmtCompact = steps => RL.compactRouteSegments(steps).map(x =>
        x.kind === "exam"
          ? (x.exam === "跳过" ? `<span class="need">Lv${x.lv} 跳过</span>` : `<b>Lv${x.lv} 考试（到 ${U.esc(x.exam)}）</b>`)
          : `Lv${x.from}→${x.to} ${U.esc(x.cls)}`
      ).join(" → ");
      const rows = list.map(c => {
        const L = c.l45;
        return `<tr><td><a href="#l45" data-go="${U.slug(c)}">${U.esc(U.shortName(c.name))}</a></td><td class="n">Lv${L.from}→45</td><td class="n">${L.pts}</td><td class="n"><b>${L.total}</b></td><td>${L.adv ? `${U.esc(L.adv.exam)}（Lv${L.adv.lv}）` : "不转上级更好"}</td><td class="n ${L.loss > 3 ? "dn" : ""}">${L.diffs.length ? L.loss : "—"}</td></tr>`;
      }).join("");
      const cards = list.map(c => {
        const L = c.l45;
        return `<article class="card" data-slug="${U.slug(c)}" id="${U.slug(c)}"><div class="ch"><div class="ct"><h3>${U.esc(c.name)}</h3><span class="lv">Lv${L.from}→45</span><span class="r">${U.PW(L.pts, L.total)} · 到目标级 ${L.plan35.total} 分</span></div></div>
          <div class="sec"><h4>上级职业</h4><p class="txt">${L.adv ? `转 <b>${U.esc(L.adv.exam)}</b>（Lv${L.adv.lv}）` : "最优路线里不转上级"}。可选上级：${U.esc((L.advOptions || []).join("、") || "无（技能或名声未达要求）")}。</p></div>
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
        return `<details class="char" id="${k}" data-slug="${k}"${focus || i === 0 ? " open" : ""}><summary><h3>${U.esc(c.name)}</h3><span>Lv${L.level}→${L.end} · 点数 ${L.got}（期望 ${L.exp}，${U.f1(L.got - L.exp)}）· 加权最高 ${wc[r].sc}（跳 ${r} 次）</span></summary>
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
            ${w.skips.map(r => smOpts(r).map((x, i, a) => `<tr${x.worth ? ' class="cur"' : ""}>${i ? "" : `<td class="n" rowspan="${a.length}">Lv${r.lv}</td><td class="n" rowspan="${a.length}">${r.roll}%</td>`}<td><b>${U.esc(x.cls)}</b></td><td class="n">${x.pct ?? "—"}% / ${x.pctNow ?? "—"}%</td>${x.ok ? `<td class="n">${x.ranks ? x.ranks + " 段" : "—"}</td><td class="n">${x.used} 级</td><td>${U.esc(U.gtxt(x.d.g, ST))}</td><td class="n">${U.sgn(x.d.pts)}</td><td class="n ${x.d.total > 0 ? "up" : x.d.total < 0 ? "dn" : ""}">${U.sgn(x.d.total)}</td><td class="n">${x.d.floorPts ? U.sgn(x.d.floorPts) : "—"}</td><td class="n">${U.sgn(x.d.gold)}G</td><td class="note">${x.worth ? "值得" : x.used ? "不值得" : "考过但用不上"}</td>` : `<td colspan="8" class="note">${U.esc(x.why)}</td>`}</tr>`).join("")).join("")}</table></div>
            ${blk.length ? `<p class="hint">规则不考虑（本档不练技能）：${U.esc(blk.join("、"))}</p>` : ""}`;
        }).join("");
      };

      const reasonsBox = name => {
        const r = REASONS[name]; if (!r) return "";
        const rt = r.route;
        const dtxt = d => `${U.esc(U.gtxt(d.g, ST))}；点数 ${U.sgn(d.pts)}，加权分 ${U.sgn(d.w)}；金币 ${U.sgn(d.gold)}G；练技能 ${U.sgn(d.train)} 段`;
        const ex = rt.exams.map(e => `<li><b>Lv${e.lv} ${U.esc(e.cls)}</b> <small>${U.esc(e.tier || "")}｜判定值 ${e.roll}%｜成功率 ${e.pct ?? "—"}%｜用它升 ${e.used} 级</small><br>${U.esc(e.why)}${e.trainSkills && e.trainSkills.length ? `<br><span class="changed">🎯 Lv${e.lv} 考前练好：${U.esc(e.trainSkills.join("、"))}（共 ${e.trainRanks} 段）</span>` : ""}${timingBox(e)}${e.vsDrop ? `<br><span class="hint">和不考它比（同样 ${rt.seeds} 个乱数）：${dtxt(e.vsDrop)}</span>` : `<br><span class="hint">${U.esc(e.dropNote || "")}</span>`}</li>`).join("") || "<li>不考新职业</li>";
        const mids = r.mids.map(m => `<li><b>${U.esc(m.cls)}</b>：${U.esc(m.why)}${m.vsRoute ? `<br><span class="hint">和现在路线比：${dtxt(m.vsRoute)}</span>` : ""}</li>`).join("");
        const exc = r.excluded.length ? `<p class="hint">不考虑：${U.esc(r.excluded.map(x => `${x.cls}（${x.why}）`).join("、"))}</p>` : "";
        return `<div class="sec"><h4>选择原因</h4><p class="txt">路线到 Lv${rt.endLv}（用 ${rt.seeds} 个乱数）：${U.esc(rt.end.map((v, i) => ST[i] + v).join(" "))}；点数 +${rt.pts}，加权分 +${rt.w}；金币 ${rt.gold}G；练技能 ${rt.train} 段；跳过 ${rt.skips} 次。${U.esc(r.tier)} ${r.trainAllowed ? "可以" : "不"}练技能考试。</p><h4>路线里的考试</h4><ul>${ex}</ul>${mids ? `<h4>没选的中级职业</h4><ul>${mids}</ul>` : ""}${exc}</div>`;
      };

      const cards = CH.filter(c => !focus || U.slug(c) === focus).map(c => {
        const o = OPTS[c.name]; if (!o) return "";
        const diffCell = d => d ? `<td>${U.esc(U.gtxt(d.g, ST))}</td><td class="n">${U.sgn(U.psum(d.g))}</td><td class="n ${d.total > 0 ? "up" : d.total < 0 ? "dn" : ""}">${U.sgn(d.total)}</td>` : `<td>—</td><td class="n">—</td><td class="n">—</td>`;
        const blk = o.options.filter(x => x.ok && x.ruleBlocked);
        const rows = o.options.filter(x => !(x.ok && x.ruleBlocked)).map(x => x.ok
          ? `<tr${x.rec ? ' class="cur"' : ""}><td><b>${U.esc(x.cls)}</b> <small>${U.esc(x.tier || "")}</small>${x.rec ? ' <span class="rec r1">现在推荐</span>' : ""}</td><td class="n">Lv${x.lv}</td><td class="n">${x.roll}%</td><td class="n">${o.trainAllowed ? `${x.pct ?? "—"}%${x.ranks ? `<br><small>不练 ${x.pctNow ?? "—"}%</small>` : ""}` : `${x.pctNow ?? "—"}%${x.ranks ? `<br><small>练后 ${x.pct ?? "—"}%</small>` : ""}`}</td><td class="note">${x.train.length ? U.esc(x.train.join("、")) : "—"}${x.floor.length ? `<br>转职保底 ${U.esc(x.floor.join("、"))}` : ""}</td><td class="n">${x.used}/${x.used45}</td>${diffCell(x.toT)}<td class="n">${U.sgn(x.toT.gold)}G</td>${diffCell(x.after)}</tr>`
          : `<tr><td><b>${U.esc(x.cls)}</b></td><td colspan="12" class="note">${U.esc(x.why)}</td></tr>`
        ).join("") + (blk.length ? `<tr><td colspan="13" class="note">规则不考虑（本档不练）：${U.esc(blk.map(x => `${x.cls}（${x.ranks} 段，加权分 ${U.sgn(x.toT.total)}）`).join("、"))}</td></tr>` : "");
        const rr = o.recRow ? `<tr class="sum"><td>现在推荐的组合：${U.esc(o.recommended.join(" + "))}</td><td colspan="5"></td>${diffCell(o.recRow.toT)}<td class="n">${U.sgn(o.recRow.toT.gold)}G</td>${diffCell(o.recRow.after)}</tr>` : "";
        const tid = "opts:" + c.name;
        const tlbl = `${c.name}（职业选择 · ${o.tier}）`;
        const hasCmt = (cmtSum.byTarget[tid] && cmtSum.byTarget[tid].total > 0) || (commentDraft && commentDraft.targetId === tid);
        return `<details class="char" data-slug="${U.slug(c)}" data-cmt-target="${U.esc(tid)}" data-cmt-label="${U.esc(tlbl)}"${focus || hasCmt ? " open" : ""}><summary><h3>${U.esc(c.name)}</h3><span>${o.tier} · Lv${o.level}→${o.target} · 已有 ${U.esc(o.owned.join("、"))}${o.required.length ? ` · 必考 ${U.esc(o.required.join("、"))}` : ""}${o.recommended.length ? ` · 推荐 ${U.esc(o.recommended.join("、"))}` : " · 推荐：不考新职业"}</span></summary>
          <div class="sec" style="padding-bottom:0">${renderCommentBtn(tid, tlbl, "批注此角色职业选择")}${renderCommentThread(tid, tlbl)}</div>
          ${reasonsBox(c.name)}<div class="sec"><div class="scroll"><table><tr><th rowspan="2">职业</th><th class="n" rowspan="2">考的时机</th><th class="n" rowspan="2">判定值</th><th class="n" rowspan="2">成功率</th><th rowspan="2">要练 / 转职保底</th><th class="n" rowspan="2">用它升级<br><small>目标/45</small></th><th colspan="4" class="grp">到 Lv${o.target}（和不考比）</th><th colspan="3" class="grp">Lv${o.target}→45 额外影响</th></tr><tr><th>能力</th><th class="n">点数</th><th class="n">加权分</th><th class="n">金币</th><th>能力</th><th class="n">点数</th><th class="n">加权分</th></tr>${rows}${rr}</table></div>${smTable(o)}</div></details>`;
      }).join("");
      return `<p class="lede">每个可考职业单独算：一定考到它、其余照规则走，和基准路线按同样多的乱数比，点数/加权分/金币/训练段数分开展示。</p><div class="grid one">${cards}</div>`;
    }

    // ---------- 7. 我的决定（按档位 P0->P1->P2 排序 + 9 项能力差展开 + Plan Mode 批注） ----------
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

    function viewMine() {
      const visibleProps = PROPOSALS.filter(pr => !focus || U.slug({ name: pr.name }) === focus);
      const sumAll = RL.summarizeRoutePicks(PROPOSALS, routePicks);
      const sumVis = RL.summarizeRoutePicks(visibleProps, routePicks);

      // 严格按档位（P0 -> P1 -> P2）排序（PROPOSALS 已按档位排好）
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

        const optHtml = (pr.options || []).map(opt => {
          const picked = r.optionId === opt.id;
          const d = opt.diffVsBaseline || {};
          const isBase = opt.id === "old_baseline";
          const slHtml = (opt.slWarnings || []).map(w =>
            `<div class="slwarn">⚠️ <b>需提前 NS Online S/L 实测</b>：${U.esc(w.message)}</div>`
          ).join("");

          const examLine = (opt.exams || []).map(e => {
            const pctStr = e.pct != null ? `估 ${e.pct}%` : "—";
            const trStr = e.trainRanks ? ` · 练 ${e.trainRanks} 段` : "";
            const flStr = e.promoFloor && e.promoFloor.length ? ` · 转职保底 ${e.promoFloor.join("、")}` : "";
            return `Lv${e.lv}(第${e.step}步) <b>${U.esc(e.cls)}</b>（判定 ${e.roll}% / ${pctStr}${trStr}${flStr}）`;
          }).join("；") || "不考新职业";

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
            ? `<div class="hint">转职保底永久补足：<b>${U.esc(opt.promoFloorDetails.join("、"))}</b></div>`
            : "";

          const marginalsHtml = (opt.marginals || []).filter(m => !m.isRequired || m.usedLevels === 0).length
            ? `<div class="rp-marg">${opt.marginals.map(m =>
                `<div><span class="cat-pill">${m.isRequired ? "必考" : "额外"} ${U.esc(m.cls)}（升级用 ${m.usedLevels} 级）</span> 边际能力差：<b>${U.esc(m.statDiffText)}</b>｜Δ净值 ${U.sgn(m.deltaNet)}｜Δ金币 ${U.sgn(m.deltaGold)}G｜Δ训练 ${U.sgn(m.deltaTrainRanks)} 段</div>`
              ).join("")}</div>`
            : "";

          const finalVec = (opt.statVec || []).map((v, i) => `${ST[i]}+${v}`).join(" ");
          const optTid = `opt:${pr.name}:${opt.id}`;
          const optLbl = `${pr.name}（${pr.tier}）· ${opt.title}`;

          return `<div class="rp-opt-wrap" data-cmt-target="${U.esc(optTid)}" data-cmt-label="${U.esc(optLbl)}">
            <label class="rp-opt${picked ? " on" : ""}">
              <div class="rp-opt-head">
                <input type="radio" name="rpick-${U.esc(U.slug({ name: pr.name }))}" value="${U.esc(opt.id)}" data-rpick="${U.esc(pr.name)}"${picked ? " checked" : ""}>
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

        return `<article class="card rp-card" data-rp-char="${U.esc(pr.name)}" data-cmt-target="${U.esc(charTid)}" data-cmt-label="${U.esc(charLbl)}">
          <div class="ch"><div class="ct">
            <h3>${U.esc(pr.name)}</h3>
            <span class="rec ${pr.tier === "P0" ? "r1" : pr.tier === "P1" ? "r2" : "r3"}">${U.esc(pr.tier)}</span>
            <span class="lv">Lv${pr.level}→目标 Lv${pr.target}（${pr.seeds} 个乱数）</span>
            <span class="r">${statusBadge} ${renderCommentBtn(charTid, charLbl, "批注")}</span>
          </div></div>
          <div class="sec rp-opts">
            ${renderCommentThread(charTid, charLbl)}
            ${optHtml}
            <div class="rp-note-row">
              <input type="text" class="rp-note" data-rpick-note="${U.esc(pr.name)}" placeholder="可选简短备注（例如 S/L 实测结果、个人偏好）" value="${U.esc(r.note || "")}">
              ${r.source === "user" ? `<button type="button" class="btn ghost" data-rpick-clear="${U.esc(pr.name)}">恢复默认</button>` : ""}
            </div>
          </div>
        </article>`;
      }).join("");

      const pickSummaryRows = sumAll.rows.map(({ proposal: pr, resolved: r }) => {
        const d = r.option && r.option.diffVsBaseline ? r.option.diffVsBaseline : null;
        const srcTag =
          r.source === "user" ? `<span class="tag ok">网页已选</span>`
          : r.source === "default" ? `<span class="cat-pill">默认已确认</span>`
          : r.source === "identical" ? `<span class="cat-pill">新旧一致</span>`
          : `<span class="tag warn">待选择</span>`;
        const cCnt = (cmtSum.byTarget["char:" + pr.name]?.open || 0)
          + (pr.options || []).reduce((acc, o) => acc + (cmtSum.byTarget[`opt:${pr.name}:${o.id}`]?.open || 0), 0);
        return `<tr class="${r.source === "pending" ? "cur" : ""}">
          <td><b>${U.esc(U.shortName(pr.name))}</b> <small>${U.esc(pr.tier)}</small>${cCnt ? ` <span class="cmt-cnt">💬${cCnt}</span>` : ""}</td>
          <td>${srcTag}</td>
          <td>${r.option ? `<b>${U.esc(r.option.title)}</b>` : `<span class="hint">尚未选择</span>`}</td>
          <td class="n">${r.option ? `${r.option.net}${d && r.option.id !== "old_baseline" ? ` (${U.sgn(d.net)})` : ""}` : "—"}</td>
          <td class="note">${r.option ? (r.option.id === "old_baseline" ? "沿用旧路线" : U.esc(d.statDiffText)) : "—"}</td>
          <td class="note">${U.esc(r.note || "—")}</td>
          <td class="n">${r.at ? U.esc(r.at.slice(5, 16).replace("T", " ")) : "—"}</td>
        </tr>`;
      }).join("");

      const proposalSection = PROPOSALS.length ? `
        <section class="alerts" data-cmt-target="summary:proposals" data-cmt-label="全 9 人方案对比总表">
          <div class="pm-sec-head">
            <h2>新路线方案选择与确认（按档位 P0→P1→P2 · 已确认 ${sumAll.confirmed} / ${sumAll.total} 人 · 待你选择 ${sumAll.pending} 人）</h2>
            ${renderCommentBtn("summary:proposals", "全 9 人方案对比总表", "批注总表")}
          </div>
          <p class="txt">每个候选方案均已展开<b>相对旧路线的 9 项具体能力差</b>、<b>转职保底</b>、金币/训练/精通差（职业精通不计入虚拟加权分，由你 case by case 拍板）与 S/L 提醒。你的每次点选与 Plan Mode 批注都会<b>自动保存在当前浏览器</b>。</p>
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
