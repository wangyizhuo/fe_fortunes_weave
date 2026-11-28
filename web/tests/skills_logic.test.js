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
    unitTypes: ["飞行"],
    classSources: [],
    charSources: [{ char: "伊欧", recruited: true, how: "飞行术 C" }],
    recruitedOwners: ["伊欧"],
  },
  {
    name: "重装移动术+1",
    enName: "Armored Mobility+1",
    category: "熟练度特技",
    categories: ["熟练度特技"],
    discipline: "重装术",
    disciplines: ["重装术"],
    scope: "common_learn",
    scopeLabel: "角色表限定（16/63 人熟练度）",
    rating: "A",
    effect: "[Armored] Grants Mov+1 (+2).",
    review: "重装限定生效",
    unitTypes: ["重装"],
    classSources: [],
    charSources: [{ char: "努蒂奴", recruited: true, how: "重装术 A" }],
    recruitedOwners: ["努蒂奴"],
  },
  {
    name: "穿铠",
    enName: "Armor Piercer",
    category: "战技",
    categories: ["战技"],
    discipline: "剑术",
    disciplines: ["剑术"],
    scope: "common_learn",
    scopeLabel: "角色表限定（12/63 人熟练度）",
    rating: "B",
    effect: "Effective against armor.",
    review: "对重装特攻，但任意兵种都能用",
    unitTypes: [],
    classSources: [],
    charSources: [{ char: "迪托利希", recruited: true, how: "剑术 C" }],
    recruitedOwners: ["迪托利希"],
  },
];

test("filterSkills filters by rating, scope, discipline, recruited and query", () => {
  assert.equal(SL.filterSkills(SAMPLE_SKILLS, { rating: "S" }).length, 2);
  assert.equal(SL.filterSkills(SAMPLE_SKILLS, { scope: "unique" }).map(s => s.name).join(","), "秘传·落燕+");
  assert.equal(SL.filterSkills(SAMPLE_SKILLS, { scope: "common_class" }).map(s => s.name).join(","), "大反击");
  assert.equal(SL.filterSkills(SAMPLE_SKILLS, { scope: "common" }).length, 5);
  assert.equal(SL.filterSkills(SAMPLE_SKILLS, { discipline: "白魔术" }).map(s => s.name).join(","), "传送");
  assert.equal(SL.filterSkills(SAMPLE_SKILLS, { onlyRecruited: true }).length, 5);
  assert.equal(SL.filterSkills(SAMPLE_SKILLS, { query: "重装步兵" }).map(s => s.name).join(","), "大反击");
  assert.equal(SL.filterSkills(SAMPLE_SKILLS, { query: "warp" }).map(s => s.name).join(","), "传送");
});

test("filterSkills filters by unitTypes checkboxes without confusing Effective-vs-armor", () => {
  assert.deepEqual(
    SL.filterSkills(SAMPLE_SKILLS, { unitTypes: ["重装"] }).map(s => s.name),
    ["重装移动术+1"]
  );
  assert.deepEqual(
    SL.filterSkills(SAMPLE_SKILLS, { unitTypes: ["重装", "飞行"] }).map(s => s.name),
    ["飞行战斗术", "重装移动术+1"]
  );
  const unrestricted = SL.filterSkills(SAMPLE_SKILLS, { unitTypes: ["无限制"] }).map(s => s.name);
  assert.ok(unrestricted.includes("穿铠"));
  assert.ok(unrestricted.includes("传送"));
  assert.ok(!unrestricted.includes("重装移动术+1"));
});

test("filterSkillChars filters by group, strengthTier, and skill keyword", () => {
  const chars = [
    { name: "迪托利希", enName: "Dietrich", recruited: true, dietrichRoute: true, strengthTier: "S", pserTier: "T0", role: "必杀战神主角", matrix: { 剑术: [{ name: "秘传·落燕+" }] } },
    { name: "凯伊", enName: "Cai", recruited: false, dietrichRoute: false, strengthTier: "S", pserTier: "T0", role: "高机动双刀主", matrix: { 白魔术: [{ name: "传送" }] } },
    { name: "蕾达", enName: "Leda", recruited: false, dietrichRoute: false, strengthTier: "SS", pserTier: "T0", role: "圣焰跳舞再动", matrix: {} },
  ];
  assert.equal(SL.filterSkillChars(chars, { group: "recruited" }).length, 1);
  assert.equal(SL.filterSkillChars(chars, { group: "all", query: "传送" }).map(c => c.name).join(","), "凯伊");
  assert.equal(SL.filterSkillChars(chars, { group: "all", strengthTier: "SS" }).map(c => c.name).join(","), "蕾达");
  assert.equal(SL.filterSkillChars(chars, { group: "all", strengthTier: "S" }).length, 2);
});

test("summarizeSkills counts ratings, scopes, and unitTypes accurately", () => {
  const s = SL.summarizeSkills(SAMPLE_SKILLS);
  assert.equal(s.total, 6);
  assert.equal(s.byRating.S, 2);
  assert.equal(s.byRating.A, 2);
  assert.equal(s.byRating.B, 1);
  assert.equal(s.byRating.C, 1);
  assert.equal(s.byScope.unique, 1);
  assert.equal(s.byScope.common_class, 1);
  assert.equal(s.byUnitType["重装"], 1);
  assert.equal(s.byUnitType["飞行"], 1);
  assert.equal(s.byUnitType["无限制"], 4);
});

test("groupCharSourcesByCondition groups by learn condition ordered D->C->B with recruited first", () => {
  const grouped = SL.groupCharSourcesByCondition([
    { char: "米迦艾拉", recruited: true, how: "重装术 B", discipline: "重装术", rank: "B" },
    { char: "凯伊", recruited: false, how: "重装术 C", discipline: "重装术", rank: "C" },
    { char: "努蒂奴", recruited: true, how: "重装术 C", discipline: "重装术", rank: "C" },
    { char: "妮涅", recruited: false, how: "重装术 D", discipline: "重装术", rank: "D" },
  ]);
  assert.deepEqual(grouped.map(g => g.condition), ["重装术 D", "重装术 C", "重装术 B"]);
  assert.deepEqual(grouped[1].chars.map(c => c.char), ["努蒂奴", "凯伊"]);
});
