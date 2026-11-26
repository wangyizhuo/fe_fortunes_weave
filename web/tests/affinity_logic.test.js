const test = require("node:test");
const assert = require("node:assert/strict");
const AL = require("../js/core/affinity_logic.js");

const SAMPLE_AFFINITY = {
  lord: "迪托利希",
  dishes: [
    {
      dish: "糖浆炖梨",
      perfect: true,
      options: [
        { who: ["迪托利希", "丹提", "奥琳"], perfect: true, score: 5, sparkle: [1, 1, 1], pairs: [["迪托利希", "丹提"]] },
        { who: ["蕾达", "绯亚娜", "丹提"], perfect: true, score: 2, sparkle: [2, 2, 0], pairs: [["蕾达", "绯亚娜"]] },
      ],
    },
    {
      dish: "岩盐火腿",
      perfect: false,
      options: [
        { who: ["迪托利希", "丹提", "甲"], perfect: false, score: 3, sparkle: [1, 1, 0], pairs: [["迪托利希", "丹提"]] },
      ],
    },
  ],
  weights: [
    { lord: "迪托利希", target: "丹提", score: 4, support: 2 },
    { lord: "蕾达", target: "绯亚娜", score: 1, support: 3 },
  ],
};

test("summarizeAffinity counts total and perfect dishes", () => {
  assert.deepEqual(AL.summarizeAffinity(SAMPLE_AFFINITY), { totalDishes: 2, perfectCount: 1 });
});

test("listSupportTwoTargets filters support==2 for current lord only", () => {
  const res = AL.listSupportTwoTargets(SAMPLE_AFFINITY);
  assert.equal(res.length, 1);
  assert.equal(res[0].target, "丹提");
});

test("buildTargetDishMatrix splits perfect and fallback dishes per pair", () => {
  const m = AL.buildTargetDishMatrix(SAMPLE_AFFINITY);
  assert.deepEqual(m[0].perfectDishes, ["糖浆炖梨"]);
  assert.deepEqual(m[0].fallbackDishes, ["岩盐火腿"]);
  assert.deepEqual(m[1].perfectDishes, ["糖浆炖梨"]);
  assert.deepEqual(m[1].fallbackDishes, []);
});

test("filterDishes filters by query and onlyPerfect", () => {
  assert.equal(AL.filterDishes(SAMPLE_AFFINITY, "", true).length, 1);
  assert.equal(AL.filterDishes(SAMPLE_AFFINITY, "绯亚娜", false).length, 1);
  assert.equal(AL.filterDishes(SAMPLE_AFFINITY, "不存在", false).length, 0);
});
