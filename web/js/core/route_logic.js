/* 路线规划 · 纯前端核心逻辑（零 DOM 依赖，完全可单元测试） */
(function (root, factory) {
  const utils = (typeof module === "object" && module.exports) ? require("./utils.js") : root.FE.utils;
  const api = factory(utils);
  if (typeof module === "object" && module.exports) module.exports = api;
  root.FE = root.FE || {};
  root.FE.routeLogic = api;
})(typeof globalThis !== "undefined" ? globalThis : window, function (U) {
  function charInfo(c, infoMap) {
    const i = (infoMap && infoMap[U.slug(c)]) || {};
    return {
      level: i.level ?? c.level,
      owned: i.owned ? [...i.owned] : [...(c.owned || [])],
      skills: { ...(c.skills || {}), ...(i.skills || {}) },
    };
  }

  const examName = s => (s && s.exam && s.cls ? s.cls : "");
  const isExamChoice = choice => choice === "exam" || (typeof choice === "string" && choice.startsWith("exam:"));
  function examChoiceCls(choice, s) {
    if (typeof choice === "string" && choice.startsWith("exam:")) return choice.slice(5);
    if (choice === "exam" && s && s.exam && s.cls) return s.cls;
    return "";
  }
  const recOf = s => (s.exam ? "exam" : s.cls);

  function choiceOf(c, s, prog) {
    return ((prog && prog[U.keyOf(c, s)]) || {}).choice || recOf(s);
  }

  function resultOf(s, choice) {
    if (isExamChoice(choice)) return { exam: true, examCls: examChoiceCls(choice, s) };
    const g = (s.opts || []).find(o => o.classes.includes(choice));
    if (g) return g;
    if (choice === s.cls || choice === s.seenCls) {
      return { classes: [choice], gains: s.gains || [], cnt: s.cnt || 0, score: s.score || 0 };
    }
    return { classes: [choice], gains: [], cnt: 0, score: 0 };
  }

  function stepName(s, row) {
    const n = (row && row.r && row.r.exam) ? (row.r.examCls || "") : examName(s);
    if (!n) return "跳过";
    const trainTxt = s.exam && s.cls === n && s.train && s.trainOk ? `，Lv${s.trainLv} 考前练好 ` + s.train.join("、") : "";
    return `考试（到 ${n}${trainTxt}）`;
  }

  function eqName(row) {
    if (row.choice === row.s.cls && row.s.eq && row.s.eq.length > 1) {
      return [row.s.cls, ...row.s.eq.filter(k => k !== row.s.cls)].join(" / ");
    }
    return row.choice;
  }

  function examVerdict(c, s, prog) {
    const ch = ((prog && prog[U.keyOf(c, s)]) || {}).chance;
    return { ch, pass: ch == null ? null : s.roll < ch };
  }

  function walk(c, prog, infoMap) {
    const ci = charInfo(c, infoMap);
    const out = [];
    let lv = c.steps.length ? (c.steps[0].frm ?? c.planFrom) : ci.level;
    for (const s of c.steps) {
      const choice = choiceOf(c, s, prog);
      const r = resultOf(s, choice);
      out.push({ s, choice, r, frm: lv, to: r.exam ? null : lv + 1 });
      if (!r.exam) lv++;
    }
    let laterDone = false;
    for (let i = out.length - 1; i >= 0; i--) {
      const row = out[i];
      const auto = row.r.exam ? (laterDone || !!row.s.autoDone) : row.to <= ci.level;
      if (!row.r.exam) laterDone = auto;
      const p = (prog && prog[U.keyOf(c, row.s)]) || {};
      row.auto = auto;
      row.done = p.done === undefined ? auto : p.done;
    }
    const have = new Set(ci.owned);
    for (const row of out) {
      const s = row.s;
      row.ownedBefore = [...have];
      if (row.r.exam) {
        const exCls = row.r.examCls || "";
        if (exCls) {
          const ch = ((prog && prog[U.keyOf(c, s)]) || {}).chance;
          const routeEx = (s.routes && s.routes.exams || []).find(e => e.cls === exCls);
          const pct = (s.exam && s.cls === exCls) ? s.pct : (routeEx ? routeEx.pct : null);
          const pass = ch != null ? s.roll < ch : (pct == null || s.roll < pct);
          if (pass) have.add(exCls);
          row.fail = !pass;
        }
      } else if (!row.done && s.src === "plan" && !have.has(row.choice)) {
        row.missing = true;
      }
    }
    let cur = c.curClass;
    for (const row of out) {
      if (row.done && !row.r.exam && (c.level == null || row.to > c.level)) cur = row.choice;
    }
    return { rows: out, endLevel: lv, ci, cur };
  }

  function remain(c, w, stats = U.DEFAULT_STATS) {
    const add = Array(stats.length).fill(0);
    let cnt = 0, sc = 0, lv = 0, str = c.str0 ?? null, tg = 0;
    for (const row of w.rows) {
      if (row.r.exam) continue;
      const v = U.statVec(row.r.gains, stats);
      if (row.s.src === "plan" && str != null) {
        const b = 3 * (Math.floor((str + v[1]) / 5) - Math.floor(str / 5));
        str += v[1];
        if (!row.done) tg += b;
      }
      if (!row.done) {
        v.forEach((x, i) => { add[i] += x; });
        cnt += row.r.cnt;
        sc += row.r.score;
        lv++;
      }
    }
    return { add, cnt, sc: sc + tg, tg, lv };
  }

  function findDecisions(chars, prog, infoMap, focus) {
    const out = [];
    for (const c of chars || []) {
      if (focus && U.slug(c) !== focus) continue;
      const w = walk(c, prog, infoMap);
      for (const row of w.rows) {
        const s = row.s;
        if (s.src !== "plan" || s.exam || row.done || !s.opts || !s.opts.length) continue;
        const own = s.opts.filter(g => g.owned.some(Boolean));
        const rec = own.find(g => g.classes.includes(recOf(s)));
        if (!rec) continue;
        const max = Math.max(...own.map(g => g.score));
        const alts = own.filter(g => g !== rec && (g.score === rec.score || (rec.score < max && g.score === max)));
        if (!alts.length) continue;
        out.push({
          c, s, row, rec, alts,
          kind: rec.score < max ? "推荐分低一点，有原因" : "加权分一样，加点不同",
        });
      }
    }
    return out;
  }

  function compactRouteSegments(steps) {
    const out = [];
    let cur = null;
    for (const x of steps || []) {
      if (x.exam) {
        cur = null;
        out.push({ kind: "exam", lv: x.lv, exam: x.exam });
        continue;
      }
      if (cur && cur.cls === x.cls && cur.to === x.lv) {
        cur.to = x.lv + 1;
        cur.sc += x.score;
        continue;
      }
      cur = { kind: "up", cls: x.cls, from: x.lv, to: x.lv + 1, sc: x.score };
      out.push(cur);
    }
    return out;
  }

  function skipLevelsFor(lv0, S, skipIndices) {
    const out = [];
    let n = 0;
    const set = new Set(skipIndices || []);
    for (let j = 0; j < 40 + S; j++) {
      if (set.has(j)) out.push(lv0 + n);
      else n++;
    }
    return out;
  }

  function buildSheetValues(routeData, prog, infoMap, nowLabel) {
    const ST = routeData.stats || U.DEFAULT_STATS;
    const skills = routeData.skills || [];
    const chars = routeData.chars || [];
    const v = [["整体成长（由成长路线页同步，别在这页手改，会被覆盖）", "", "", "同步时间", nowLabel || ""]];
    v.push(["角色", "当前等级", "终点等级", "还要涨（点数）", "加权分", ...ST.map(k => k + "（现在→终点）"), "已有职业", ...skills, "能力权重"]);
    for (const c of chars) {
      const w = walk(c, prog, infoMap), ci = w.ci, rm = remain(c, w, ST);
      v.push([
        c.name, ci.level ?? "", w.endLevel, rm.cnt, rm.sc,
        ...ST.map((_, i) => (c.stats ? `${c.stats[i]}→${c.stats[i] + rm.add[i]}` : "")),
        ci.owned.join("、"),
        ...skills.map(k => ci.skills[k] || ""),
        ST.map((k, i) => k + ((c.weights || [])[i] ?? "")).join(" "),
      ]);
    }
    v.push([""]);
    v.push(["角色", "来源", "等级", "原定", "我的选择", "已完成", "加点", "点数", "加权分", "这一步所有选择", "游戏显示成功率", "判定值"]);
    for (const c of chars) {
      for (const row of walk(c, prog, infoMap).rows) {
        const { s, r } = row;
        const ch = ((prog && prog[U.keyOf(c, s)]) || {}).chance;
        v.push([
          c.name,
          s.src === "record" ? (s.hidden ? "没记录" : "观星记录") : "规划",
          r.exam ? (examName(s) ? "考试" : "跳过") : `${row.frm}→${row.to}`,
          s.exam ? (s.cls ? "考试·" + s.cls : "跳过") : "升1级·" + s.cls,
          r.exam ? stepName(s) : "升1级·" + row.choice,
          row.done ? "✓" : "",
          r.exam ? "" : r.gains.join(" "),
          r.exam ? "" : r.cnt,
          r.exam ? "" : r.score,
          (s.opts || []).map(o => `${o.classes.join("/")}:${o.cnt}点${o.score}分`).join("；"),
          ch ?? "",
          s.roll ?? "",
        ]);
      }
    }
    const wd = Math.max(...v.map(r => r.length));
    return v.map(r => [...r, ...Array(wd - r.length).fill("")]);
  }

  function resolveRoutePick(proposal, routePicks) {
    if (!proposal) return { optionId: null, source: "pending", at: null, note: "", option: null };
    const saved = (routePicks || {})[proposal.name];
    const opts = proposal.options || [];
    if (saved && saved.optionId) {
      const opt = opts.find(o => o.id === saved.optionId) || null;
      if (opt) {
        return {
          optionId: opt.id,
          source: "user",
          at: saved.at || null,
          note: saved.note || "",
          option: opt,
        };
      }
    }
    if (proposal.defaultPick) {
      const opt = opts.find(o => o.id === proposal.defaultPick) || null;
      if (opt) {
        return {
          optionId: opt.id,
          source: proposal.status === "identical" ? "identical" : "default",
          at: null,
          note: (saved && saved.note) || "",
          option: opt,
        };
      }
    }
    return {
      optionId: null,
      source: "pending",
      at: null,
      note: (saved && saved.note) || "",
      option: null,
    };
  }

  function summarizeRoutePicks(proposals, routePicks) {
    const list = proposals || [];
    let userPicked = 0;
    let defaultConfirmed = 0;
    let identical = 0;
    let pending = 0;
    const rows = list.map(pr => {
      const r = resolveRoutePick(pr, routePicks);
      if (r.source === "user") userPicked++;
      else if (r.source === "default") defaultConfirmed++;
      else if (r.source === "identical") identical++;
      else pending++;
      return { proposal: pr, resolved: r };
    });
    return {
      total: list.length,
      confirmed: userPicked + defaultConfirmed + identical,
      userPicked,
      defaultConfirmed,
      identical,
      pending,
      rows,
    };
  }

  function formatRoutePicksExport(proposals, routePicks) {
    const sum = summarizeRoutePicks(proposals, routePicks);
    const lines = [`# 我的路线方案选择（已确认 ${sum.confirmed}/${sum.total}，待选 ${sum.pending}）`];
    for (const { proposal: pr, resolved: r } of sum.rows) {
      if (!r.option) {
        lines.push(`- ${pr.name} [${pr.tier}]：待选择`);
        continue;
      }
      const d = r.option.diffVsBaseline || {};
      const tag = r.source === "user" ? "网页已选" : r.source === "default" ? "默认已确认" : "新旧一致";
      const note = r.note ? `｜备注：${r.note}` : "";
      lines.push(
        `- ${pr.name} [${pr.tier}]（${tag}）：${r.option.title} [${r.option.id}]｜净值 ${r.option.net}（Δ${d.net >= 0 ? "+" : ""}${d.net ?? 0}）｜能力差：${d.statDiffText || "无"}${note}`
      );
    }
    return lines.join("\n");
  }

  const TIER_ORDER = { P0: 0, P1: 1, P2: 2 };
  const STRENGTH_ORDER = { SS: 0, S: 1, A: 2, B: 3, C: 4, D: 5 };

  function tierOrderOf(tier) {
    return Object.prototype.hasOwnProperty.call(TIER_ORDER, tier) ? TIER_ORDER[tier] : 9;
  }

  function strengthOrderOf(st) {
    return Object.prototype.hasOwnProperty.call(STRENGTH_ORDER, st) ? STRENGTH_ORDER[st] : 9;
  }

  function sortCharsByTier(chars, currentLord) {
    return [...(chars || [])].sort((a, b) => {
      const al = (a && (a.isLord || (currentLord && a.name === currentLord))) ? 0 : 1;
      const bl = (b && (b.isLord || (currentLord && b.name === currentLord))) ? 0 : 1;
      if (al !== bl) return al - bl;
      const dp = tierOrderOf(a && a.tier) - tierOrderOf(b && b.tier);
      if (dp !== 0) return dp;
      const ds = strengthOrderOf(a && a.strengthTier) - strengthOrderOf(b && b.strengthTier);
      if (ds !== 0) return ds;
      return String((a && a.name) || "").localeCompare(String((b && b.name) || ""), "zh-CN");
    });
  }

  function groupCharsByTier(chars, currentLord) {
    const sorted = sortCharsByTier(chars, currentLord);
    const out = [];
    for (const tier of ["P0", "P1", "P2"]) {
      const items = sorted.filter(c => (c && c.tier) === tier);
      if (items.length) out.push({ tier, chars: items });
    }
    const rest = sorted.filter(c => !c || !["P0", "P1", "P2"].includes(c.tier));
    if (rest.length) out.push({ tier: "其他", chars: rest });
    return out;
  }

  function summarizeNextActions(chars, prog, infoMap) {
    const ordered = sortCharsByTier(chars);
    return ordered.map(c => {
      const w = walk(c, prog, infoMap);
      const nx = w.rows.filter(r => !r.done);
      const doneKeys = new Set(w.rows.filter(r => r.done).map(r => r.s.key));
      const curLv = w.ci.level ?? c.level ?? null;
      const curClass = w.cur || c.curClass || "";

      let immediate = { kind: "done", lv: curLv, to: null, cls: curClass, fromCls: curClass, roll: null, pct: null };
      if (nx.length) {
        const first = nx[0];
        const s = first.s;
        if (first.r.exam) {
          const ex = examName(s);
          immediate = {
            kind: ex ? "exam" : "skip",
            lv: first.frm,
            to: null,
            cls: ex || "",
            fromCls: curClass,
            roll: s.roll ?? null,
            pct: s.pct ?? null,
          };
        } else if (first.missing) {
          immediate = {
            kind: "missing",
            lv: first.frm,
            to: first.to,
            cls: first.choice,
            fromCls: curClass,
            roll: null,
            pct: null,
          };
        } else if (curClass && first.choice && first.choice !== curClass) {
          immediate = {
            kind: "switch",
            lv: first.frm,
            to: first.to,
            cls: first.choice,
            fromCls: curClass,
            roll: null,
            pct: null,
          };
        } else {
          immediate = {
            kind: "level",
            lv: first.frm,
            to: first.to,
            cls: eqName(first),
            fromCls: curClass,
            roll: null,
            pct: null,
          };
        }
      }

      let nextExam = null;
      let nextSkip = null;
      let nextSwitch = null;
      let nextStop = null;
      let followingStop = null;
      let prevCls = curClass;

      for (let i = 0; i < nx.length; i++) {
        const row = nx[i];
        const s = row.s;
        let stopEntry = null;
        if (row.r.exam) {
          const ex = examName(s);
          if (ex) {
            if (!nextExam) {
              nextExam = {
                lv: row.frm,
                cls: ex,
                roll: s.roll ?? null,
                pct: s.pct ?? null,
                stepsAway: i,
                train: s.train && s.trainOk ? [...s.train] : [],
              };
            }
            stopEntry = {
              kind: "exam",
              lv: row.frm,
              cls: ex,
              fromCls: prevCls,
              roll: s.roll ?? null,
              pct: s.pct ?? null,
              stepsAway: i,
            };
          } else {
            if (!nextSkip) {
              nextSkip = {
                lv: row.frm,
                roll: s.roll ?? null,
                stepsAway: i,
              };
            }
            stopEntry = {
              kind: "skip",
              lv: row.frm,
              cls: "",
              fromCls: prevCls,
              roll: s.roll ?? null,
              pct: null,
              stepsAway: i,
            };
          }
        } else {
          if (row.missing) {
            stopEntry = {
              kind: "missing",
              lv: row.frm,
              to: row.to,
              cls: row.choice,
              fromCls: prevCls,
              stepsAway: i,
            };
          } else if (prevCls && row.choice && row.choice !== prevCls) {
            if (!nextSwitch) {
              nextSwitch = {
                frm: row.frm,
                to: row.to,
                fromCls: prevCls,
                toCls: row.choice,
                stepsAway: i,
                missing: !!row.missing,
              };
            }
            stopEntry = {
              kind: "switch",
              lv: row.frm,
              to: row.to,
              fromCls: prevCls,
              toCls: row.choice,
              cls: row.choice,
              stepsAway: i,
            };
          }
          if (row.choice) prevCls = row.choice;
        }
        if (stopEntry) {
          if (!nextStop) nextStop = stopEntry;
          else if (!followingStop) followingStop = stopEntry;
        }
      }

      const allTrains = (c.trainPlan || []).filter(t => !doneKeys.has(t.key));
      const nextTrain = allTrains.length ? allTrains[0] : null;

      return {
        char: c,
        name: c.name,
        tier: c.tier || "P1",
        strengthTier: c.strengthTier || "",
        pserTier: c.pserTier || "",
        role: c.role || "",
        priorityNote: c.priorityNote || "",
        curLv,
        curClass,
        endLevel: w.endLevel,
        remainingCount: nx.length,
        immediate,
        nextStop,
        followingStop,
        nextExam,
        nextSwitch,
        nextSkip,
        nextTrain,
        allTrains,
      };
    });
  }

  function summarizeOptionHighlights(optObj, weights, stats = U.DEFAULT_STATS) {
    if (!optObj || !Array.isArray(optObj.options)) return null;
    const okOpts = optObj.options.filter(x => x && x.ok && x.toT && Array.isArray(x.toT.g));
    if (!okOpts.length) return null;
    const wt = Array.isArray(weights) && weights.length === stats.length ? weights : [1, 5, 1, 5, 3, 2, 1, 1, 1];
    // 取除 HP(0) 外权重最高的两项核心属性（例如物理角色为 力+速，法师为 魔+速）
    const nonHpOrder = [1, 2, 3, 4, 5, 6, 7, 8].sort((a, b) => (wt[b] - wt[a]) || (a - b));
    const idxA = nonHpOrder[0];
    const idxB = nonHpOrder[1];

    const cands = [
      {
        cls: "不考新职业（基准）",
        isBaseline: true,
        lv: null,
        g: Array(stats.length).fill(0),
        pts: 0,
        total: 0,
        gold: 0,
        ranks: 0,
        floor: [],
        ruleBlocked: false,
      },
      ...okOpts.map(x => ({
        cls: x.cls,
        isBaseline: false,
        lv: x.lv,
        g: x.toT.g,
        pts: U.psum(x.toT.g),
        total: x.toT.total,
        gold: x.toT.gold,
        ranks: x.ranks || 0,
        floor: x.floor || [],
        ruleBlocked: !!x.ruleBlocked,
      })),
    ];

    const pairVal = x => (x.g[idxA] || 0) + (x.g[idxB] || 0);
    const byPair = [...cands].sort(
      (a, b) => (pairVal(b) - pairVal(a))
        || (Number(a.ruleBlocked) - Number(b.ruleBlocked))
        || (b.total - a.total)
        || (a.gold - b.gold)
    );
    const byA = [...cands].sort(
      (a, b) => ((b.g[idxA] || 0) - (a.g[idxA] || 0))
        || (pairVal(b) - pairVal(a))
        || (b.total - a.total)
        || (a.gold - b.gold)
    );
    const byB = [...cands].sort(
      (a, b) => ((b.g[idxB] || 0) - (a.g[idxB] || 0))
        || (pairVal(b) - pairVal(a))
        || (b.total - a.total)
        || (a.gold - b.gold)
    );
    const byW = [...cands].sort(
      (a, b) => (b.total - a.total)
        || (b.pts - a.pts)
        || (a.gold - b.gold)
    );

    const bestPairScore = pairVal(byPair[0]);
    const pairTop = byPair.filter((x, i) => i < 4 || pairVal(x) === bestPairScore).slice(0, 5);
    return {
      idxA,
      idxB,
      statA: stats[idxA],
      statB: stats[idxB],
      pairBest: bestPairScore,
      pairTop,
      statATop: byA.slice(0, 2),
      statBTop: byB.slice(0, 2),
      weightedTop: byW.slice(0, 2),
    };
  }

  function diffOptionGains(optGains, baseGains, stats = U.DEFAULT_STATS) {
    const a = U.statVec(optGains || [], stats);
    const b = U.statVec(baseGains || [], stats);
    const diffVec = a.map((v, i) => v - b[i]);
    const diffItems = [];
    for (let i = 0; i < stats.length; i++) {
      if (diffVec[i] !== 0) diffItems.push({ stat: stats[i], delta: diffVec[i] });
    }
    const text = diffItems.length
      ? diffItems.map(x => `${x.stat}${x.delta > 0 ? "+" : ""}${x.delta}`).join(" ")
      : "与预选相同";
    return { diffVec, diffItems, text };
  }

  function passableExamChoices(s, ownedBefore) {
    const ownedSet = new Set(ownedBefore || []);
    const list = (s && s.routes && Array.isArray(s.routes.exams)) ? s.routes.exams : [];
    const seen = new Set();
    const out = [];
    for (const e of list) {
      if (!e || !e.cls || e.pass === false || ownedSet.has(e.cls) || seen.has(e.cls)) continue;
      seen.add(e.cls);
      out.push({ cls: e.cls, pct: e.pct ?? null, pass: e.pass !== false });
    }
    if (s && s.exam && s.cls && !ownedSet.has(s.cls) && !seen.has(s.cls)) {
      out.unshift({ cls: s.cls, pct: s.pct ?? null, pass: s.pct == null || s.roll < s.pct });
    }
    return out;
  }

  function findEarlyExamSlot(c, w, targetStepKey, cls) {
    if (!w || !Array.isArray(w.rows) || !cls) return null;
    let best = null;
    for (const row of w.rows) {
      if (row.s.key === targetStepKey) break;
      if (row.done || row.s.src !== "plan" || row.r.exam) continue;
      const ownedSet = new Set(row.ownedBefore || []);
      if (ownedSet.has(cls)) return null;
      const ex = (row.s.routes && row.s.routes.exams || []).find(e => e.cls === cls && e.pass !== false);
      if (!ex) continue;
      const cand = {
        key: row.s.key,
        lv: row.frm,
        score: row.r.score ?? 0,
        cnt: row.r.cnt ?? 0,
        roll: row.s.roll,
        pct: ex.pct ?? null,
        cls,
      };
      if (!best || cand.score < best.score || (cand.score === best.score && cand.cnt < best.cnt)) {
        best = cand;
      }
    }
    return best;
  }

  return {
    charInfo, examName, isExamChoice, examChoiceCls, recOf, choiceOf, resultOf, stepName, eqName,
    examVerdict, walk, remain, findDecisions, compactRouteSegments, skipLevelsFor, buildSheetValues,
    resolveRoutePick, summarizeRoutePicks, formatRoutePicksExport,
    tierOrderOf, sortCharsByTier, groupCharsByTier, summarizeNextActions, summarizeOptionHighlights, diffOptionGains,
    passableExamChoices, findEarlyExamSlot,
  };
});
