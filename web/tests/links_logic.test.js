const test = require("node:test");
const assert = require("node:assert/strict");
const LL = require("../js/core/links_logic.js");

const VALID_VIEWS = ["next", "plan", "past", "l45", "long", "opts", "mine", "meal", "explore", "items", "classes", "skills", "chars"];

const SAMPLE_REGISTRY = LL.buildEntityRegistry({
  characters: [
    { name: "迪托利希" },
    { name: "努蒂奴" },
    { name: "哥莱亚斯" },
    { name: "米迦艾拉" },
  ],
  classes: [
    { name: "重装步兵" },
    { name: "飞鸵兵" },
    { name: "轻步兵" },
    { name: "士兵" },
    { name: "弓箭手" },
  ],
  skills: [
    { name: "体格+" },
    { name: "重装移动术+1" },
    { name: "大防御" },
  ],
});

test("parseRouteHash parses bare tabs, deep-linked entity targets, and fallbacks safely", () => {
  assert.deepEqual(LL.parseRouteHash("", VALID_VIEWS, "next"), { view: "next", target: "" });
  assert.deepEqual(LL.parseRouteHash("#meal", VALID_VIEWS, "next"), { view: "meal", target: "" });
  assert.deepEqual(LL.parseRouteHash("#chars/%E8%BF%AA%E6%89%98%E5%88%A9%E5%B8%8C", VALID_VIEWS, "next"), {
    view: "chars",
    target: "迪托利希",
  });
  assert.deepEqual(LL.parseRouteHash("#skills/%E4%BD%93%E6%A0%BC%2B", VALID_VIEWS, "next"), {
    view: "skills",
    target: "体格+",
  });
  assert.deepEqual(LL.parseRouteHash("#classes/重装步兵", VALID_VIEWS, "next"), {
    view: "classes",
    target: "重装步兵",
  });
  // 非法视图回落到默认视图且清空 target
  assert.deepEqual(LL.parseRouteHash("#unknown/abc", VALID_VIEWS, "next"), { view: "next", target: "" });
  // 畸形 URI 编码不抛异常
  assert.deepEqual(LL.parseRouteHash("#chars/%E0%A4%A", VALID_VIEWS, "next"), { view: "chars", target: "%E0%A4%A" });
});

test("buildEntityHref round-trips with parseRouteHash for char, class, and skill", () => {
  for (const [kind, name] of [
    ["char", "迪托利希"],
    ["class", "重装步兵"],
    ["skill", "体格+"],
    ["skill", "重装移动术+1"],
  ]) {
    const href = LL.buildEntityHref(kind, name);
    const parsed = LL.parseRouteHash(href, VALID_VIEWS, "next");
    assert.equal(parsed.view, LL.ENTITY_VIEWS[kind]);
    assert.equal(parsed.target, name);
  }
});

test("resolveEntity resolves exact names, aliases, and parenthetical notes without dead links", () => {
  assert.equal(LL.resolveEntity(SAMPLE_REGISTRY, "char", "迪托利希"), "迪托利希");
  assert.equal(LL.resolveEntity(SAMPLE_REGISTRY, "char", "迪"), "迪托利希");
  assert.equal(LL.resolveEntity(SAMPLE_REGISTRY, "char", "哥莱亚斯（满好感）"), "哥莱亚斯");
  assert.equal(LL.resolveEntity(SAMPLE_REGISTRY, "class", "飞驼兵"), "飞鸵兵");
  assert.equal(LL.resolveEntity(SAMPLE_REGISTRY, "skill", "体格+"), "体格+");
  assert.equal(LL.resolveEntity(SAMPLE_REGISTRY, "class", "跳过"), null);
  assert.equal(LL.resolveEntity(SAMPLE_REGISTRY, "skill", "不存在的技能"), null);
});

test("renderEntityLink generates stable hyperlink for known entities and plain escaped text for unknown", () => {
  const htmlChar = LL.renderEntityLink(SAMPLE_REGISTRY, "char", "哥莱亚斯（满好感）");
  assert.match(htmlChar, /^<a href="#chars\/[^"]+" class="ent-link ent-char" data-ent-kind="char" data-ent-name="哥莱亚斯"/);
  assert.match(htmlChar, />哥莱亚斯<\/a>（满好感）$/);

  const htmlAlias = LL.renderEntityLink(SAMPLE_REGISTRY, "class", "飞驼兵");
  assert.match(htmlAlias, /data-ent-kind="class" data-ent-name="飞鸵兵"/);
  assert.match(htmlAlias, />飞驼兵<\/a>$/);

  const htmlMissing = LL.renderEntityLink(SAMPLE_REGISTRY, "class", "跳过<script>");
  assert.equal(htmlMissing, "跳过&lt;script&gt;");
});

test("linkifyClassText links multiple known classes longest-first and escapes surrounding text", () => {
  const html = LL.linkifyClassText(SAMPLE_REGISTRY, "轻步兵 / 重装步兵 -> 跳过");
  assert.match(html, /data-ent-kind="class" data-ent-name="轻步兵"/);
  assert.match(html, /data-ent-kind="class" data-ent-name="重装步兵"/);
  assert.match(html, /-&gt; 跳过$/);
});
