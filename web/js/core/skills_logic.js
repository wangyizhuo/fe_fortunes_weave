/* 技能图鉴纯核心逻辑（零 DOM 依赖，Node.js 可直接单元测试） */
(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory();
  } else {
    root.FE = root.FE || {};
    root.FE.skillsLogic = factory();
  }
})(typeof globalThis !== "undefined" ? globalThis : window, function () {
  function norm(s) {
    return String(s || "").trim().toLowerCase();
  }

  const UNIT_TYPE_ORDER = ["重装", "步兵", "骑兵", "飞行", "仅限本职业", "无限制"];

  /**
   * 按评级、获取范围（特有/稀有/通用）、分类、熟练度、生效兵种限制、已招角色与关键字筛选技能。
   */
  function filterSkills(skills, opts) {
    const o = opts || {};
    const q = norm(o.query);
    const rating = o.rating || "全部";
    const scope = o.scope || "全部"; // 全部 | unique | rare | common | common_class | common_learn
    const category = o.category || "全部";
    const discipline = o.discipline || "全部";
    const onlyRecruited = !!o.onlyRecruited;
    const unitTypes = Array.isArray(o.unitTypes) ? o.unitTypes.filter(Boolean) : [];

    return (skills || []).filter(sk => {
      if (rating !== "全部" && sk.rating !== rating) return false;
      if (scope !== "全部") {
        if (scope === "common") {
          if (sk.scope !== "common_class" && sk.scope !== "common_learn") return false;
        } else if (scope === "exclusive") {
          if (sk.scope !== "unique" && sk.scope !== "rare") return false;
        } else if (sk.scope !== scope) {
          return false;
        }
      }
      if (category !== "全部") {
        const cats = sk.categories && sk.categories.length ? sk.categories : [sk.category];
        if (!cats.includes(category)) return false;
      }
      if (discipline !== "全部") {
        const discs = sk.disciplines && sk.disciplines.length ? sk.disciplines : [sk.discipline];
        if (!discs.includes(discipline)) return false;
      }
      if (unitTypes.length) {
        const uts = Array.isArray(sk.unitTypes) ? sk.unitTypes : [];
        const hit = unitTypes.some(u => (u === "无限制" ? uts.length === 0 : uts.includes(u)));
        if (!hit) return false;
      }
      if (onlyRecruited) {
        const hasRec = (sk.recruitedOwners && sk.recruitedOwners.length > 0) || sk.scope === "common_class";
        if (!hasRec) return false;
      }
      if (q) {
        const hay = [
          sk.name,
          sk.enName,
          sk.category,
          sk.discipline,
          sk.scopeLabel,
          ...(sk.unitTypes || []),
          sk.effect,
          sk.review,
          ...(sk.classSources || []).map(cs => cs.cls),
          ...(sk.charSources || []).map(cs => `${cs.char} ${cs.how}`),
        ].join(" ").toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });
  }

  /**
   * 筛选角色技能速览列表（recruited: 已招 9 人 | dietrich: 迪线角色 | all: 全部 63 人，并可按 SS~D 强度筛选）。
   */
  function filterSkillChars(characters, opts) {
    const o = opts || {};
    const q = norm(o.query);
    const group = o.group || "recruited";
    const strengthTier = o.strengthTier || "全部";

    return (characters || []).filter(ch => {
      if (group === "recruited" && !ch.recruited) return false;
      if (group === "dietrich" && !ch.dietrichRoute) return false;
      if (strengthTier !== "全部" && ch.strengthTier !== strengthTier) return false;
      if (q) {
        const matNames = [];
        for (const list of Object.values(ch.matrix || {})) {
          for (const it of list || []) matNames.push(it.name);
        }
        const hay = [
          ch.name,
          ch.enName,
          ch.faction,
          ch.startClass,
          ch.strengthTier,
          ch.pserTier,
          ch.role,
          ch.tierSummary,
          ch.note,
          ch.personalSkill ? `${ch.personalSkill.name} ${ch.personalSkill.text}` : "",
          ...(ch.lvSkills || []).map(x => x.name),
          ...(ch.bloodMarks || []).map(x => x.name),
          ...matNames,
        ].join(" ").toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });
  }

  /**
   * 汇总筛选后技能的评级分布、获取范围与生效兵种统计。
   */
  function summarizeSkills(skills) {
    const byRating = { S: 0, A: 0, B: 0, C: 0 };
    const byScope = { unique: 0, rare: 0, common_learn: 0, common_class: 0 };
    const byUnitType = Object.fromEntries(UNIT_TYPE_ORDER.map(u => [u, 0]));
    for (const sk of skills || []) {
      if (byRating[sk.rating] != null) byRating[sk.rating] += 1;
      if (byScope[sk.scope] != null) byScope[sk.scope] += 1;
      const uts = Array.isArray(sk.unitTypes) ? sk.unitTypes : [];
      if (!uts.length) {
        byUnitType["无限制"] += 1;
      } else {
        for (const u of uts) {
          if (byUnitType[u] != null) byUnitType[u] += 1;
        }
      }
    }
    return { total: (skills || []).length, byRating, byScope, byUnitType };
  }

  return {
    UNIT_TYPE_ORDER,
    filterSkills,
    filterSkillChars,
    summarizeSkills,
  };
});
