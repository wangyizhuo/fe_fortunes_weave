/* 纯工具函数（零 DOM 依赖，Browser + Node.js 通用） */
(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  root.FE = root.FE || {};
  root.FE.utils = api;
})(typeof globalThis !== "undefined" ? globalThis : window, function () {
  const RANKS = ["E", "E+", "D", "D+", "C", "C+", "B", "B+", "A", "A+", "S", "S+"];
  const SLUG = {
    "迪托利希": "dietrich", "法毕欧": "fabio", "米迦艾拉": "michaela",
    "杨界": "yokai", "努蒂奴": "nutino", "乌尔坦德": "urtand",
    "艾丝梅拉尔达": "esmeralda", "伊欧": "io", "奇洛伊卡": "chiloica",
  };
  const SHORT = {
    "迪托利希": "迪", "法毕欧": "法毕欧", "米迦艾拉": "米迦",
    "杨界": "杨界", "努蒂奴": "努蒂奴", "乌尔坦德": "乌尔坦德",
    "艾丝梅拉尔达": "艾丝", "伊欧": "伊欧", "奇洛伊卡": "奇洛",
  };
  const DEFAULT_STATS = ["HP", "力", "魔", "速", "技", "防", "魔防", "幸", "魅"];

  const esc = t => String(t ?? "").replace(/[&<>"]/g, ch => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[ch]));
  const sgn = v => (v > 0 ? "+" : "") + v;
  const f1 = v => (v > 0 ? "+" : "") + (Math.round(v * 10) / 10);
  const psum = g => g.reduce((a, v) => a + v, 0);
  const wsum = (g, w) => g.reduce((a, v, i) => a + v * ((w && w[i]) || 0), 0);
  const PW = (p, w) => `${p} 点 · ${w} 分`;
  const shortName = n => SHORT[n] || n;
  const slug = (c, idx) => SLUG[c.name] || ("c" + (idx ?? 0));
  const keyOf = (c, s, idx) => slug(c, idx) + "-" + s.key;

  function statVec(gains, stats = DEFAULT_STATS) {
    const v = Array(stats.length).fill(0);
    for (const g of gains || []) {
      const [k, n] = String(g).split("+");
      const i = stats.indexOf(k);
      if (i >= 0) v[i] += n ? +n : 1;
    }
    return v;
  }

  function gtxt(g, stats = DEFAULT_STATS) {
    return g.map((v, i) => (v ? stats[i] + sgn(v) : "")).filter(Boolean).join(" ") || "—";
  }

  function lvTxt(arr) {
    const m = {};
    for (const v of arr || []) m[v] = (m[v] || 0) + 1;
    return Object.keys(m).map(Number).sort((a, b) => a - b).map(v => "Lv" + v + (m[v] > 1 ? "×" + m[v] : "")).join(" ") || "—";
  }

  return {
    RANKS, SLUG, SHORT, DEFAULT_STATS,
    esc, sgn, f1, psum, wsum, PW, shortName, slug, keyOf, statVec, gtxt, lvTxt,
  };
});
