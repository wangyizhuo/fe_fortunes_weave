const test = require("node:test");
const assert = require("node:assert/strict");
const EL = require("../js/core/explore_logic.js");

const SAMPLE_SPOTS = [
  {
    id: "1",
    route: "dietrich",
    rank: 1,
    name: "亚特拉山顶",
    type: "矿石",
    x: 1000,
    y: 600,
    priority: "P0",
    score: 160,
    region: "帝都西北",
    nearestStation: "卡尔托多站",
    highlights: ["奥利哈钢", "太阳石"],
    items: [
      { name: "奥利哈钢", tier: "P0", score: 100, tag: "终极神矿", reason: "孤品矿" },
      { name: "太阳石", tier: "P0", score: 84, tag: "高阶矿石", reason: "高阶锻造" },
    ],
  },
  {
    id: "2",
    route: "dietrich",
    rank: 2,
    name: "布隆提斯湖",
    type: "鱼",
    x: 1200,
    y: 1700,
    priority: "P0",
    score: 112,
    region: "帝都正南",
    nearestStation: "萨拉基亚站",
    highlights: ["辉光鱼"],
    items: [
      { name: "辉光鱼", tier: "P0", score: 96, tag: "换巨人戒指", reason: "换巨人戒指", exchanges: [{ place: "海都阿雷库托", reward: "巨人戒指", qty: 1 }] },
    ],
  },
  {
    id: "3",
    route: "dietrich",
    rank: 10,
    name: "塔尔伯斯平原",
    type: "蔬菜",
    x: 900,
    y: 1200,
    priority: "P1",
    score: 74,
    region: "帝都正西",
    nearestStation: "凯隆站",
    highlights: ["椰枣"],
    items: [
      { name: "椰枣", tier: "P1", score: 74, tag: "高频兑换材", reason: "换达米纳弓" },
    ],
  },
  {
    id: "4",
    route: "dietrich",
    rank: 20,
    name: "微风之丘",
    type: "蔬菜",
    x: 1500,
    y: 1100,
    priority: "P2",
    score: 20,
    region: "帝都周边",
    nearestStation: "西阿玛尔忒娅站",
    highlights: ["姬金鱼草"],
    items: [
      { name: "姬金鱼草", tier: "P2", score: 15, tag: "", reason: "" },
    ],
  },
];

test("filterExploreSpots filters by priority, type, query, and hideVisited", () => {
  assert.deepEqual(
    EL.filterExploreSpots(SAMPLE_SPOTS, { priorities: ["P0"] }).map(s => s.name),
    ["亚特拉山顶", "布隆提斯湖"]
  );
  assert.deepEqual(
    EL.filterExploreSpots(SAMPLE_SPOTS, { types: ["蔬菜"] }).map(s => s.name),
    ["塔尔伯斯平原", "微风之丘"]
  );
  assert.deepEqual(
    EL.filterExploreSpots(SAMPLE_SPOTS, { query: "巨人戒指" }).map(s => s.name),
    ["布隆提斯湖"]
  );
  assert.deepEqual(
    EL.filterExploreSpots(SAMPLE_SPOTS, { priorities: ["P0"], hideVisited: true, visitedMap: { "1": true } }).map(s => s.name),
    ["布隆提斯湖"]
  );
});

test("summarizeExplore computes tier, type, and visited counts", () => {
  const s = EL.summarizeExplore(SAMPLE_SPOTS, { "1": true });
  assert.equal(s.total, 4);
  assert.equal(s.visited, 1);
  assert.equal(s.remaining, 3);
  assert.equal(s.byTier.P0, 2);
  assert.equal(s.byTier.P1, 1);
  assert.equal(s.byTier.P2, 1);
  assert.equal(s.byType["矿石"], 1);
  assert.equal(s.byType["蔬菜"], 2);
});

test("extractFwCollectItems extracts prioritized gathering materials cleanly", () => {
  const res = EL.extractFwCollectItems(SAMPLE_SPOTS.slice(0, 3), "dietrich");
  assert.equal(res.routeKey, "dietrich");
  assert.ok(res.items.includes("奥利哈钢"));
  assert.ok(res.items.includes("辉光鱼"));
  assert.ok(res.items.includes("椰枣"));
});

test("computeFitViewBox and buildStandaloneMapHtml produce valid bounds and HTML", () => {
  const vb = EL.computeFitViewBox(SAMPLE_SPOTS.slice(0, 2), [0, 0, 3328, 2560], 3328, 2560);
  assert.equal(vb.length, 4);
  assert.ok(vb[2] >= 700 && vb[3] >= 540);
  const html = EL.buildStandaloneMapHtml({
    title: "测试探索图",
    spots: SAMPLE_SPOTS.slice(0, 2),
    stations: [{ name: "卡尔托多站", x: 1050, y: 620 }],
    viewBox: vb,
  });
  assert.ok(html.startsWith("<!DOCTYPE html>"));
  assert.ok(html.includes("亚特拉山顶"));
  assert.ok(html.includes("布隆提斯湖"));
});
