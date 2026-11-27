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
  const recOf = s => (s.exam ? "exam" : s.cls);

  function choiceOf(c, s, prog) {
    return ((prog && prog[U.keyOf(c, s)]) || {}).choice || recOf(s);
  }

  function resultOf(s, choice) {
    if (choice === "exam") return { exam: true };
    const g = (s.opts || []).find(o => o.classes.includes(choice));
    if (g) return g;
    if (choice === s.cls || choice === s.seenCls) {
      return { classes: [choice], gains: s.gains || [], cnt: s.cnt || 0, score: s.score || 0 };
    }
    return { classes: [choice], gains: [], cnt: 0, score: 0 };
  }

  function stepName(s) {
    const n = examName(s);
    if (!n) return "跳过";
    const trainTxt = s.train && s.trainOk ? `，Lv${s.trainLv} 考前练好 ` + s.train.join("、") : "";
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
      if (row.r.exam) {
        if (s.exam && s.cls) {
          const ch = ((prog && prog[U.keyOf(c, s)]) || {}).chance;
          const pass = ch != null ? s.roll < ch : (s.pct == null || s.roll < s.pct);
          if (pass) have.add(s.cls);
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

  return {
    charInfo, examName, recOf, choiceOf, resultOf, stepName, eqName,
    examVerdict, walk, remain, findDecisions, compactRouteSegments, skipLevelsFor, buildSheetValues,
    resolveRoutePick, summarizeRoutePicks, formatRoutePicksExport,
  };
});
