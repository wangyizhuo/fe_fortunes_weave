const test = require("node:test");
const assert = require("node:assert/strict");
const CL = require("../js/core/comments_logic.js");

test("Plan Mode comments CRUD: add, update, resolve, delete", () => {
  let list = [];
  list = CL.addComment(list, {
    targetId: "char:法毕欧",
    targetLabel: "法毕欧 (P1)",
    section: "mine",
    quote: "s15 萨满巫师（用 0 级）",
    text: "我要萨满精通，倾向保留 s2",
    at: "2026-11-26T10:00:00Z",
  });
  assert.equal(list.length, 1);
  assert.equal(list[0].resolved, false);
  const id = list[0].id;

  // Empty text is ignored
  assert.equal(CL.addComment(list, { targetId: "char:法毕欧", text: "   " }).length, 1);

  list = CL.updateComment(list, id, "改主意：还是先看转职保底和技+1", "2026-11-26T10:05:00Z");
  assert.match(list[0].text, /改主意/);

  list = CL.toggleResolveComment(list, id);
  assert.equal(list[0].resolved, true);
  assert.equal(CL.commentsForTarget(list, "char:法毕欧", { includeResolved: false }).length, 0);
  assert.equal(CL.commentsForTarget(list, "char:法毕欧", { includeResolved: true }).length, 1);

  const s = CL.summarizeComments(list);
  assert.equal(s.total, 1);
  assert.equal(s.open, 0);
  assert.equal(s.resolved, 1);

  list = CL.deleteComment(list, id);
  assert.equal(list.length, 0);
});

test("formatPlanReviewExport formats grouped quotes and route choices", () => {
  const comments = CL.addComment([], {
    targetId: "char:努蒂奴",
    targetLabel: "努蒂奴 (P2)",
    quote: "转职保底 +3",
    text: "提前 S/L 测 Lv16 重装",
    at: "2026-11-26T10:00:00Z",
  });
  const md = CL.formatPlanReviewExport({
    comments,
    proposals: [{ name: "努蒂奴" }],
    routePicks: {},
    formatRoutePicksExport: () => "- 努蒂奴：Lv16 重装步兵",
  });
  assert.match(md, /### 努蒂奴 \(P2\)/);
  assert.match(md, /引用：「转职保底 \+3」/);
  assert.match(md, /批注：提前 S\/L 测 Lv16 重装/);
  assert.match(md, /- 努蒂奴：Lv16 重装步兵/);
});
