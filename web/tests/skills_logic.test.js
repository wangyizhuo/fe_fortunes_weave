const test = require("node:test");
const assert = require("node:assert/strict");
const SL = require("../js/core/skills_logic.js");

const SAMPLE_SKILLS = [
  {
    name: "传送",
    enName: "Warp",
    category: "白魔术",
    categories: ["白魔术"],
    discipline: "白魔术",
    disciplines: ["白魔术"],
    scope: "common_learn",
    scopeLabel: "通用（8 人熟练度）",
    rating: "S",
    effect: "Moves an ally to a space within 5 spaces.",
    review: "顶级战略白魔法",
    classSources: [],
    charSources: [{ char: "凯伊", recruited: false, how: "白魔术 S" }],
    recruitedOwners: [],
  },
  {
    name: "秘传·落燕+",
    enName: "Secret Swallow+",
    category: "战技",
    categories: ["战技"],
    discipline: "剑术",
    disciplines: ["剑术"],
    scope: "unique",
    scopeLabel: "角色特有（唯一）",
    rating: "S",
    effect: "High-tier sword art.",
    review: "迪托利希专属",
    classSources: [],
    charSources: [{ char: "迪托利希", recruited: true, how: "剑术 S" }],
    recruitedOwners: ["迪托利希"],
  },
  {
    name: "大反击",
    enName: "Great Counter",
    category: "职业精通",
    categories: ["职业精通"],
    discipline: "职业",
    disciplines: ["职业"],
    scope: "common_class",
    scopeLabel: "通用（职业精通/固有）",
    rating: "A",
    effect: "If foe attacks first, grants Atk +3.",
    review: "重装精通",
    classSources: [{ cls: "重装步兵", tier: "中级", how: "精通" }],
    charSources: [],
    recruitedOwners: [],
  },
  {
    name: "飞行战斗术",
    enName: "Aerial Combat",
    category: "熟练度特技",
    categories: ["熟练度特技"],
    discipline: "飞行术",
    disciplines: ["飞行术"],
    scope: "common_learn",
    scopeLabel: "通用（12 人熟练度）",
    rating: "C",
    effect: "Grants Hit/Avo when flying.",
    review: "收益偏低",
    classSources: [],
    charSources: [{ char: "伊欧", recruited: true, how: "飞行术 C" }],
    recruitedOwners: ["伊欧"],
  },
];

test("filterSkills filters by rating, scope, discipline, recruited and query", () => {
  assert.equal(SL.filterSkills(SAMPLE_SKILLS, { rating: "S" }).length, 2);
  assert.equal(SL.filterSkills(SAMPLE_SKILLS, { scope: "unique" }).map(s => s.name).join(","), "秘传·落燕+");
  assert.equal(SL.filterSkills(SAMPLE_SKILLS, { scope: "common_class" }).map(s => s.name).join(","), "大反击");
  assert.equal(SL.filterSkills(SAMPLE_SKILLS, { scope: "common" }).length, 3);
  assert.equal(SL.filterSkills(SAMPLE_SKILLS, { discipline: "白魔术" }).map(s => s.name).join(","), "传送");
  assert.equal(SL.filterSkills(SAMPLE_SKILLS, { onlyRecruited: true }).length, 3); // 秘传·落燕+ + 飞行战斗术 + 通用职业大反击
  assert.equal(SL.filterSkills(SAMPLE_SKILLS, { query: "重装步兵" }).map(s => s.name).join(","), "大反击");
  assert.equal(SL.filterSkills(SAMPLE_SKILLS, { query: "warp" }).map(s => s.name).join(","), "传送");
});

test("filterSkillChars filters by group and skill keyword", () => {
  const chars = [
    { name: "迪托利希", enName: "Dietrich", recruited: true, dietrichRoute: true, matrix: { 剑术: [{ name: "秘传·落燕+" }] } },
    { name: "凯伊", enName: "Cai", recruited: false, dietrichRoute: false, matrix: { 白魔术: [{ name: "传送" }] } },
  ];
  assert.equal(SL.filterSkillChars(chars, { group: "recruited" }).length, 1);
  assert.equal(SL.filterSkillChars(chars, { group: "all", query: "传送" }).map(c => c.name).join(","), "凯伊");
});

test("summarizeSkills counts ratings and scopes accurately", () => {
  const s = SL.summarizeSkills(SAMPLE_SKILLS);
  assert.equal(s.total, 4);
  assert.equal(s.byRating.S, 2);
  assert.equal(s.byRating.A, 1);
  assert.equal(s.byRating.C, 1);
  assert.equal(s.byScope.unique, 1);
  assert.equal(s.byScope.common_class, 1);
});
