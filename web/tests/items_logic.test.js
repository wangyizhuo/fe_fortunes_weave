const test = require("node:test");
const assert = require("node:assert/strict");
const IL = require("../js/core/items_logic.js");

const SAMPLE_TOWNS = [
  {
    cn: "帝都达格席翁", en: "Dagsion", jp: "帝都ダグシオン-武器屋",
    items: [
      { cat: "剑", cn: "银剑", jp: "銀の剣", price: 5000, stock: "1", note: "", src: "AppMedia" },
      { cat: "手形", cn: "上级试验手形", jp: "上級試験手形", price: 3000, stock: "少量", note: "名声 8 起卖", src: "GameWith" },
    ],
  },
  {
    cn: "菲娜渔村", en: "Fina", jp: "フィーナの漁村",
    items: [
      { cat: "剑", cn: "斩马刀", jp: "斬馬刀", price: 3000, stock: "1", note: "克骑", src: "AppMedia" },
    ],
  },
];

const SAMPLE_BARTER = [
  { cn: "斩马刀", jp: "斬馬刀", type: "剑", cost: "バクx10,キンバイx3", note: "克骑", location: "帝都达格席翁 · 范达尔商会" },
  { cn: "巨人戒指", jp: "Giant's Ring", type: "戒指", cost: "Paradise Fish ×1", note: "体格+4", location: "海都阿莱克托 · 范达尔商会" },
];

const SAMPLE_MATERIALS = [
  { material: "バク", totalUses: 1, usedIn: [{ cn: "斩马刀", jp: "斬馬刀", type: "剑", qty: 10, note: "克骑", location: "帝都" }] },
  { material: "Paradise Fish", totalUses: 1, usedIn: [{ cn: "巨人戒指", jp: "Giant's Ring", type: "戒指", qty: 1, note: "体格+4", location: "海都" }] },
];

test("filterTowns filters by category and keyword across town & item fields", () => {
  const byCat = IL.filterTowns(SAMPLE_TOWNS, "手形", "");
  assert.equal(byCat.townCount, 1);
  assert.equal(byCat.itemCount, 1);
  assert.equal(byCat.towns[0].items[0].cn, "上级试验手形");

  const byNote = IL.filterTowns(SAMPLE_TOWNS, "全部", "克骑");
  assert.equal(byNote.townCount, 1);
  assert.equal(byNote.towns[0].cn, "菲娜渔村");

  const byTown = IL.filterTowns(SAMPLE_TOWNS, "全部", "dagsion");
  assert.equal(byTown.itemCount, 2);
});

test("filterBarter maps 道具 category to include 戒指 and matches material query", () => {
  assert.equal(IL.filterBarter(SAMPLE_BARTER, "道具", "").length, 1);
  assert.equal(IL.filterBarter(SAMPLE_BARTER, "全部", "バク").length, 1);
});

test("filterMaterials supports reverse lookup by material name or target weapon", () => {
  assert.equal(IL.filterMaterials(SAMPLE_MATERIALS, "全部", "paradise").length, 1);
  assert.equal(IL.filterMaterials(SAMPLE_MATERIALS, "剑", "").length, 1);
});

test("highlightMatch escapes HTML and wraps matched substring safely", () => {
  assert.equal(IL.highlightMatch("银剑 <test>", "银剑"), "<mark>银剑</mark> &lt;test&gt;");
  assert.equal(IL.highlightMatch("Dagsion", "dag"), "<mark>Dag</mark>sion");
});
