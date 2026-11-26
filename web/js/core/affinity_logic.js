/* 友好度培养 · 纯前端核心逻辑（零 DOM 依赖，完全可单元测试） */
(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  root.FE = root.FE || {};
  root.FE.affinityLogic = api;
})(typeof globalThis !== "undefined" ? globalThis : window, function () {
  function summarizeAffinity(data) {
    const dishes = (data && data.dishes) || [];
    const perfectCount = dishes.filter(d => d.perfect).length;
    return { totalDishes: dishes.length, perfectCount };
  }

  function listSupportTwoTargets(data) {
    const weights = (data && data.weights) || [];
    const lord = data && data.lord;
    return weights.filter(x => x.support === 2 && x.lord === lord);
  }

  function buildTargetDishMatrix(data) {
    const dishes = (data && data.dishes) || [];
    const weights = (data && data.weights) || [];
    return weights.map(x => {
      const matched = dishes.filter(r =>
        (r.options || []).some(t => (t.pairs || []).some(([a, b]) => a === x.lord && b === x.target))
      );
      const perfectDishes = matched.filter(r =>
        (r.options || []).some(t => t.perfect && (t.pairs || []).some(([a, b]) => a === x.lord && b === x.target))
      );
      const fallbackDishes = matched.filter(r => !perfectDishes.includes(r));
      return {
        lord: x.lord,
        target: x.target,
        score: x.score,
        support: x.support,
        perfectDishes: perfectDishes.map(r => r.dish),
        fallbackDishes: fallbackDishes.map(r => r.dish),
      };
    });
  }

  function filterDishes(data, query, onlyPerfect) {
    const q = String(query || "").trim().toLowerCase();
    const dishes = (data && data.dishes) || [];
    return dishes.filter(r => {
      if (onlyPerfect && !r.perfect) return false;
      if (!q) return true;
      if (r.dish.toLowerCase().includes(q)) return true;
      return (r.options || []).some(t => (t.who || []).some(n => n.toLowerCase().includes(q)));
    });
  }

  return { summarizeAffinity, listSupportTwoTargets, buildTargetDishMatrix, filterDishes };
});
