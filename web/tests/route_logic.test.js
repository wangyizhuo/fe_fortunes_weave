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

test("resolveRoutePick, summarizeRoutePicks and formatRoutePicksExport track user, default, and pending states", () => {
  const proposals = [
    {
      name: "努蒂奴",
      tier: "P2",
      status: "pending",
      defaultPick: null,
      options: [
        { id: "new_best", title: "Lv16 考重装步兵", net: 253.0, diffVsBaseline: { net: 11.0, statDiffText: "HP+1、力+1、防+3" } },
        { id: "safe_fallback", title: "Lv18 考重装步兵", net: 248.0, diffVsBaseline: { net: 6.0, statDiffText: "防+2" } },
      ],
    },
    {
      name: "伊欧",
      tier: "P0",
      status: "confirmed_default",
      defaultPick: "new_best",
      options: [
        { id: "new_best", title: "Lv23 考飞鸵兵", net: 230.2, diffVsBaseline: { net: 23.8, statDiffText: "HP+2、速+1" } },
      ],
    },
  ];
  const s0 = RL.summarizeRoutePicks(proposals, {});
  assert.equal(s0.pending, 1);
  assert.equal(s0.defaultConfirmed, 1);
  assert.equal(s0.confirmed, 1);

  const picks = { "努蒂奴": { optionId: "safe_fallback", note: "先稳过", at: "2026-11-26T23:00:00Z" } };
  const r = RL.resolveRoutePick(proposals[0], picks);
  assert.equal(r.source, "user");
  assert.equal(r.optionId, "safe_fallback");
  assert.equal(r.note, "先稳过");

  const s1 = RL.summarizeRoutePicks(proposals, picks);
  assert.equal(s1.pending, 0);
  assert.equal(s1.userPicked, 1);
  const txt = RL.formatRoutePicksExport(proposals, picks);
  assert.match(txt, /努蒂奴 \[P2\]（网页已选）：Lv18 考重装步兵/);
  assert.match(txt, /备注：先稳过/);
});

test("summarizeNextActions sorts by P0→P1→P2 and extracts next exam, switch, skip, and train steps", () => {
  const chars = [
    {
      name: "努蒂奴",
      tier: "P2",
      strengthTier: "B",
      level: 16,
      curClass: "弓手",
      owned: ["弓手"],
      planFrom: 16,
      trainPlan: [],
      steps: [
        { key: "1", src: "plan", exam: false, cls: "弓手", frm: 16, gains: ["力"], cnt: 1, score: 5, opts: [] },
        { key: "2", src: "plan", exam: true, cls: "", roll: 50, opts: [] },
      ],
    },
    {
      name: "伊欧",
      tier: "P1",
      strengthTier: "B",
      level: 23,
      curClass: "轻骑兵",
      owned: ["轻骑兵", "剑客"],
      planFrom: 23,
      trainPlan: [],
      steps: [
        { key: "1", src: "plan", exam: false, cls: "剑客", frm: 23, gains: ["速"], cnt: 1, score: 5, opts: [] },
      ],
    },
    {
      ...SAMPLE_CHAR,
      tier: "P0",
      strengthTier: "S",
      trainPlan: [{ key: "1", lv: 23, cls: "恶棍", train: ["斧术 D→C"], ranks: 2 }],
    },
  ];
  const rows = RL.summarizeNextActions(chars, {}, {});
  assert.deepEqual(rows.map(r => r.name), ["迪托利希", "伊欧", "努蒂奴"]);
  assert.deepEqual(rows.map(r => r.tier), ["P0", "P1", "P2"]);

  // 迪托利希: immediate exam + nextSwitch to 恶棍 + trainPlan
  assert.equal(rows[0].immediate.kind, "exam");
  assert.equal(rows[0].nextExam.cls, "恶棍");
  assert.equal(rows[0].nextExam.stepsAway, 0);
  assert.equal(rows[0].nextSwitch.toCls, "恶棍");
  assert.equal(rows[0].nextTrain.cls, "恶棍");
  assert.equal(rows[0].nextSkip, null);

  // 伊欧: immediate class switch 轻骑兵 -> 剑客
  assert.equal(rows[1].immediate.kind, "switch");
  assert.equal(rows[1].nextSwitch.fromCls, "轻骑兵");
  assert.equal(rows[1].nextSwitch.toCls, "剑客");

  // 努蒂奴: immediate level up, nextSkip 1 step away
  assert.equal(rows[2].immediate.kind, "level");
  assert.equal(rows[2].nextSkip.lv, 17);
  assert.equal(rows[2].nextSkip.stepsAway, 1);

  // 严格按 当前主角 -> P -> 强度 -> 名字（zh-CN 拼音）排序
  const mixed = [
    { name: "米迦艾拉", tier: "P0", strengthTier: "A" },
    { name: "迪托利希", tier: "P0", strengthTier: "S", isLord: true },
    { name: "艾丝梅拉尔达", tier: "P0", strengthTier: "S" },
    { name: "法毕欧", tier: "P1", strengthTier: "S" },
    { name: "乌尔坦德", tier: "P2", strengthTier: "B" },
    { name: "努蒂奴", tier: "P2", strengthTier: "B" },
  ];
  assert.deepEqual(
    RL.sortCharsByTier(mixed, "迪托利希").map(c => c.name),
    ["迪托利希", "艾丝梅拉尔达", "米迦艾拉", "法毕欧", "努蒂奴", "乌尔坦德"]
  );
  const groups = RL.groupCharsByTier(mixed, "迪托利希");
  assert.deepEqual(groups.map(g => g.tier), ["P0", "P1", "P2"]);
  assert.deepEqual(groups[0].chars.map(c => c.name), ["迪托利希", "艾丝梅拉尔达", "米迦艾拉"]);
  assert.deepEqual(groups[1].chars.map(c => c.name), ["法毕欧"]);
  assert.deepEqual(groups[2].chars.map(c => c.name), ["努蒂奴", "乌尔坦德"]);
});

test("diffOptionGains computes stat-by-stat deltas against preselected option", () => {
  const d = RL.diffOptionGains(["力", "速", "技", "防", "魔防"], ["HP", "力", "速", "防"]);
  assert.equal(d.text, "HP-1 技+1 魔防+1");
  assert.deepEqual(d.diffItems, [
    { stat: "HP", delta: -1 },
    { stat: "技", delta: 1 },
    { stat: "魔防", delta: 1 },
  ]);
  assert.equal(RL.diffOptionGains(["力", "速"], ["力", "速"]).text, "与预选相同");
});

test("walk supports custom exam:<cls> choices and findEarlyExamSlot picks worst earlier RNG step", () => {
  const char = {
    name: "杨界",
    level: 20,
    curClass: "诅咒师",
    owned: ["诅咒师", "平民"],
    planFrom: 20,
    steps: [
      { key: "1", src: "plan", exam: false, cls: "诅咒师", frm: 20, gains: ["魔", "速", "技"], cnt: 3, score: 18, roll: 15.26, routes: { exams: [{ cls: "牧师", pct: 100, pass: true }] }, opts: [{ classes: ["诅咒师"], owned: [true], gains: ["魔", "速", "技"], cnt: 3, score: 18 }] },
      { key: "2", src: "plan", exam: false, cls: "平民", frm: 21, gains: ["HP", "幸"], cnt: 2, score: 7, roll: 36.85, routes: { exams: [{ cls: "牧师", pct: 100, pass: true }] }, opts: [{ classes: ["平民"], owned: [true], gains: ["HP", "幸"], cnt: 2, score: 7 }] },
      { key: "3", src: "plan", exam: false, cls: "诅咒师", frm: 22, gains: ["魔", "技"], cnt: 2, score: 14, roll: 78.03, routes: { exams: [{ cls: "牧师", pct: 100, pass: true }] }, opts: [
        { classes: ["牧师"], owned: [false], gains: ["HP", "魔", "速", "技", "幸"], cnt: 5, score: 22 },
        { classes: ["诅咒师"], owned: [true], gains: ["魔", "技"], cnt: 2, score: 14 },
      ] },
    ],
  };
  const w0 = RL.walk(char, {}, {});
  assert.deepEqual(RL.passableExamChoices(char.steps[1], w0.rows[1].ownedBefore).map(e => e.cls), ["牧师"]);
  const slot = RL.findEarlyExamSlot(char, w0, "3", "牧师");
  assert.equal(slot.key, "2");
  assert.equal(slot.score, 7);

  // Applying early exam on step 2 + using 牧师 on step 3 clears missing flag
  const U = require("../js/core/utils.js");
  const prog = {
    [U.keyOf(char, char.steps[1])]: { choice: "exam:牧师" },
    [U.keyOf(char, char.steps[2])]: { choice: "牧师" },
  };
  const w1 = RL.walk(char, prog, {});
  assert.equal(w1.rows[1].r.exam, true);
  assert.equal(w1.rows[1].r.examCls, "牧师");
  assert.equal(w1.rows[2].choice, "牧师");
  assert.equal(Boolean(w1.rows[2].missing), false);
});



