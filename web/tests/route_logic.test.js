const test = require("node:test");
const assert = require("node:assert/strict");
const U = require("../js/core/utils.js");
const RL = require("../js/core/route_logic.js");

const SAMPLE_CHAR = {
  name: "迪托利希",
  level: 23,
  curClass: "剑客",
  stats: [37, 25, 17, 26, 29, 16, 6, 21, 25],
  weights: [3, 5, 1, 5, 5, 3, 2, 2, 1],
  owned: ["剑客", "斗士", "士兵", "平民"],
  skills: { 剑术: "B+" },
  str0: 24,
  planFrom: 23,
  steps: [
    {
      key: "1", src: "plan", exam: true, cls: "恶棍", roll: 12.5, pct: 100,
      train: ["斧术 D→C"], trainOk: true, trainLv: 23,
      opts: [{ classes: ["剑客"], owned: [true], gains: ["力"], cnt: 1, score: 5 }],
    },
    {
      key: "2", src: "plan", exam: false, cls: "恶棍", frm: 23,
      gains: ["力", "速", "技"], cnt: 3, score: 15, eq: ["恶棍", "剑客"],
      opts: [
        { classes: ["恶棍", "剑客"], owned: [true, true], gains: ["力", "速", "技"], cnt: 3, score: 15 },
        { classes: ["斗士"], owned: [true], gains: ["HP", "力", "速"], cnt: 3, score: 13 },
      ],
    },
  ],
};

test("walk tracks exam acquisition, level progression, and done states", () => {
  const w = RL.walk(SAMPLE_CHAR, {}, {});
  assert.equal(w.endLevel, 24);
  assert.equal(w.rows.length, 2);
  assert.equal(w.rows[0].r.exam, true);
  assert.equal(w.rows[0].fail, false);
  assert.equal(w.rows[1].missing, undefined);
  assert.equal(RL.eqName(w.rows[1]), "恶棍 / 剑客");
});

test("walk flags missing class when exam fails via user-entered low chance", () => {
  const prog = { "dietrich-1": { chance: 10 } }; // roll 12.5 >= 10 -> fail
  const w = RL.walk(SAMPLE_CHAR, prog, {});
  assert.equal(w.rows[0].fail, true);
  assert.equal(w.rows[1].missing, true);
});

test("remain adds +3 physique bonus when strength crosses multiple of 5", () => {
  const w = RL.walk(SAMPLE_CHAR, {}, {});
  const rm = RL.remain(SAMPLE_CHAR, w);
  // str0=24, gains 力+1 -> 25 (crosses multiple of 5 => +3)
  assert.equal(rm.cnt, 3);
  assert.equal(rm.tg, 3);
  assert.equal(rm.sc, 18);
  assert.equal(rm.lv, 1);
});

test("compactRouteSegments merges consecutive level-ups of same class", () => {
  const segs = RL.compactRouteSegments([
    { lv: 23, cls: "剑客", score: 12 },
    { lv: 24, cls: "剑客", score: 15 },
    { lv: 25, exam: "恶棍" },
    { lv: 25, cls: "恶棍", score: 18 },
  ]);
  assert.deepEqual(segs, [
    { kind: "up", cls: "剑客", from: 23, to: 25, sc: 27 },
    { kind: "exam", lv: 25, exam: "恶棍" },
    { kind: "up", cls: "恶棍", from: 25, to: 26, sc: 18 },
  ]);
});

test("stepName includes training reminder when trainOk is true", () => {
  assert.match(RL.stepName(SAMPLE_CHAR.steps[0]), /Lv23 考前练好 斧术 D→C/);
  assert.equal(RL.stepName({ exam: true, cls: "" }), "跳过");
});

test("buildSheetValues outputs rectangular table rows", () => {
  const routeData = { stats: U.DEFAULT_STATS, skills: ["剑术"], chars: [SAMPLE_CHAR] };
  const vals = RL.buildSheetValues(routeData, {}, {}, "2026-11-26");
  const widths = new Set(vals.map(r => r.length));
  assert.equal(widths.size, 1);
  assert.ok(vals.length >= 6);
});

test("examVerdict enforces strict roll < chance boundary", () => {
  const step = SAMPLE_CHAR.steps[0]; // roll = 12.5
  assert.equal(RL.examVerdict(SAMPLE_CHAR, step, { "dietrich-1": { chance: 12.5 } }).pass, false);
  assert.equal(RL.examVerdict(SAMPLE_CHAR, step, { "dietrich-1": { chance: 12.51 } }).pass, true);
  assert.equal(RL.examVerdict(SAMPLE_CHAR, step, {}).pass, null);
});

test("walk auto-marks steps done when character level advances in infoMap", () => {
  const w = RL.walk(SAMPLE_CHAR, {}, { dietrich: { level: 24 } });
  assert.equal(w.rows[0].done, true);
  assert.equal(w.rows[1].done, true);
  assert.equal(w.cur, "恶棍");
});

test("findDecisions detects tied score options with different stat gains", () => {
  const c = {
    ...SAMPLE_CHAR,
    steps: [
      {
        key: "1", src: "plan", exam: false, cls: "剑客", frm: 23,
        gains: ["力", "速"], cnt: 2, score: 10,
        opts: [
          { classes: ["剑客"], owned: [true], gains: ["力", "速"], cnt: 2, score: 10 },
          { classes: ["斗士"], owned: [true], gains: ["力", "技"], cnt: 2, score: 10 },
        ],
      },
    ],
  };
  const decs = RL.findDecisions([c], {}, {}, "");
  assert.equal(decs.length, 1);
  assert.equal(decs[0].kind, "加权分一样，加点不同");
});

test("skipLevelsFor maps seed skip indices to exact character levels", () => {
  assert.deepEqual(RL.skipLevelsFor(20, 2, [0, 3]), [20, 22]);
});
