const test = require("node:test");
const assert = require("node:assert/strict");
const CL = require("../js/core/classes_logic.js");

const SAMPLE_CLASSES = [
  {
    name: "斗士",
    tier: "初级",
    unitType: "步兵",
    usableSkills: ["剑术", "斧术", "格斗术", "步兵术"],
    innate: [],
    mastery: "攻击的基本",
    requirement: "任选其一 剑术 D 斧术 D 格斗术 D",
    minStats: { hp: 20, str: 8, def: 3 },
  },
  {
    name: "轻骑兵",
    tier: "中级",
    unitType: "骑兵",
    usableSkills: ["剑术", "枪术", "马术"],
    innate: ["乘降术"],
    mastery: "体力强化",
    requirement: "主要 马术 D · 任选其一 剑术 C 枪术 C",
    minStats: { hp: 25, str: 10, spd: 8 },
  },
  {
    name: "天翼兵",
    tier: "中级",
    unitType: "飞行",
    limit: "女性",
    usableSkills: ["剑术", "枪术", "飞行术"],
    innate: ["乘降术"],
    mastery: "天马的护翼",
    requirement: "主要 飞行术 D · 任选其一 剑术 C 枪术 C",
    minStats: { hp: 25, spd: 10, res: 10 },
  },
  {
    name: "萨满巫师",
    tier: "中级",
    unitType: "步兵",
    usableSkills: ["黑魔术", "白魔术", "步兵术"],
    innate: ["黑魔术的探究"],
    mastery: "技巧咒缚",
    requirement: "主要 黑魔术 C",
    minStats: { hp: 20, mag: 10, res: 8 },
  },
  {
    name: "神鸵兵",
    tier: "上级",
    unitType: "骑兵",
    usableSkills: ["剑术", "枪术", "黑魔术", "马术"],
    innate: ["乘降术", "黑魔术的探究"],
    mastery: "驰骋",
    requirement: "主要 黑魔术 B 马术 D",
    minStats: { hp: 25, mag: 12, spd: 12 },
  },
];

test("filterClasses filters by tier", () => {
  const mid = CL.filterClasses(SAMPLE_CLASSES, { tier: "中级" });
  assert.deepEqual(mid.map(c => c.name), ["轻骑兵", "天翼兵", "萨满巫师"]);
  assert.equal(CL.filterClasses(SAMPLE_CLASSES, { tier: "全部" }).length, 5);
});

test("filterClasses supports AND (all) and OR (any) usableSkills checkboxes", () => {
  const andRes = CL.filterClasses(SAMPLE_CLASSES, {
    selectedSkills: ["剑术", "马术"],
    matchMode: "all",
  });
  assert.deepEqual(andRes.map(c => c.name), ["轻骑兵", "神鸵兵"]);

  const andMagicMount = CL.filterClasses(SAMPLE_CLASSES, {
    selectedSkills: ["黑魔术", "马术"],
    matchMode: "all",
  });
  assert.deepEqual(andMagicMount.map(c => c.name), ["神鸵兵"]);

  const orRes = CL.filterClasses(SAMPLE_CLASSES, {
    selectedSkills: ["飞行术", "格斗术"],
    matchMode: "any",
  });
  assert.deepEqual(orRes.map(c => c.name), ["斗士", "天翼兵"]);
});

test("filterClasses matches keyword across mastery, limit, innate, and skill names", () => {
  assert.deepEqual(CL.filterClasses(SAMPLE_CLASSES, { query: "女性" }).map(c => c.name), ["天翼兵"]);
  assert.deepEqual(CL.filterClasses(SAMPLE_CLASSES, { query: "驰骋" }).map(c => c.name), ["神鸵兵"]);
});

test("groupClassesByTier keeps canonical progression order and skips empty tiers", () => {
  const groups = CL.groupClassesByTier(SAMPLE_CLASSES);
  assert.deepEqual(groups.map(g => g.tier), ["初级", "中级", "上级"]);
  assert.equal(groups[1].classes.length, 3);
});

test("summarizeClasses counts totals per tier and per skill", () => {
  const s = CL.summarizeClasses(SAMPLE_CLASSES, ["剑术", "马术", "重装术"]);
  assert.equal(s.total, 5);
  assert.equal(s.tierCounts["中级"], 3);
  assert.equal(s.skillCounts["剑术"], 4);
  assert.equal(s.skillCounts["马术"], 2);
  assert.equal(s.skillCounts["重装术"], 0);
});

test("formatMinStats formats non-zero promotion floor stats compactly", () => {
  assert.equal(CL.formatMinStats({ hp: 25, str: 10, mag: 0, def: 8 }), "HP25 力10 防8");
  assert.equal(CL.formatMinStats({ hp: 0, str: 0 }), "—");
});
