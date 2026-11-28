/* 纯实体超链接与哈希路由解析逻辑（零 DOM 依赖，Browser + Node.js 通用）
 * 统一管理全站「职业 / 技能 / 角色」三大实体的规范哈希、别名归一化与安全超链接生成。
 */
(function (root, factory) {
  const utils =
    typeof module === "object" && module.exports
      ? require("./utils.js")
      : root.FE.utils;
  const api = factory(utils);
  if (typeof module === "object" && module.exports) module.exports = api;
  root.FE = root.FE || {};
  root.FE.linksLogic = api;
})(typeof globalThis !== "undefined" ? globalThis : window, function (U) {
  const ENTITY_VIEWS = {
    char: "chars",
    class: "classes",
    skill: "skills",
  };

  const ENTITY_LABELS = {
    char: "角色图鉴",
    class: "职业图鉴",
    skill: "技能图鉴",
  };

  const CLASS_ALIASES = {
    "飞驼兵": "飞鸵兵",
  };

  const CHAR_ALIASES = {
    "迪": "迪托利希",
    "米迦": "米迦艾拉",
    "艾丝": "艾丝梅拉尔达",
    "奇洛": "奇洛伊卡",
  };

  function safeDecode(str) {
    try {
      return decodeURIComponent(str);
    } catch (_) {
      return str;
    }
  }

  /**
   * 解析 URL hash，支持 "#view" 以及 "#view/<entityTarget>" 两种格式。
   * 例如 "#chars/%E8%BF%AA%E6%89%98%E5%88%A9%E5%B8%8C" -> { view: "chars", target: "迪托利希" }
   */
  function parseRouteHash(hash, validViews, defaultView = "next") {
    const raw = String(hash || "").replace(/^#/, "").trim();
    if (!raw) return { view: defaultView, target: "" };
    const slash = raw.indexOf("/");
    const head = slash >= 0 ? raw.slice(0, slash) : raw;
    const tail = slash >= 0 ? safeDecode(raw.slice(slash + 1)).trim() : "";
    const view = Array.isArray(validViews) && validViews.includes(head) ? head : defaultView;
    return { view, target: view === head ? tail : "" };
  }

  /**
   * 构造稳定、可收藏/复用的规范实体哈希链接。
   */
  function buildEntityHref(kind, name) {
    const view = ENTITY_VIEWS[kind];
    if (!view || !name) return "#";
    return `#${view}/${encodeURIComponent(String(name).trim())}`;
  }

  /**
   * 根据模块数据构建三大实体规范索引表（用于校验超链接不出现死链）。
   */
  function buildEntityRegistry(sources) {
    const src = sources || {};
    const chars = new Set();
    const classes = new Set();
    const skills = new Set();

    for (const c of src.characters || []) {
      if (c && c.name) chars.add(String(c.name).trim());
    }
    for (const c of src.classes || []) {
      if (c && c.name) classes.add(String(c.name).trim());
    }
    for (const s of src.skills || []) {
      if (s && s.name) skills.add(String(s.name).trim());
    }

    const sortedClasses = [...classes, ...Object.keys(CLASS_ALIASES)]
      .filter((v, i, a) => v && a.indexOf(v) === i)
      .sort((a, b) => b.length - a.length);

    return { chars, classes, skills, sortedClasses };
  }

  /**
   * 将原始名称（含别名、括号附注如「哥莱亚斯（满好感）」）解析为图鉴内的规范名称；不存在则返回 null。
   */
  function resolveEntity(registry, kind, rawName) {
    if (!registry || !rawName) return null;
    const raw = String(rawName).trim();
    if (!raw) return null;
    const set =
      kind === "char" ? registry.chars
      : kind === "class" ? registry.classes
      : kind === "skill" ? registry.skills
      : null;
    if (!set) return null;
    if (set.has(raw)) return raw;

    const aliasMap = kind === "class" ? CLASS_ALIASES : kind === "char" ? CHAR_ALIASES : null;
    if (aliasMap && aliasMap[raw] && set.has(aliasMap[raw])) return aliasMap[raw];

    // 剥离尾部括号附注（如「哥莱亚斯（满好感）」）后再匹配
    const stripped = raw.replace(/[（(][^）)]*[）)]\s*$/, "").trim();
    if (stripped && stripped !== raw) {
      if (set.has(stripped)) return stripped;
      if (aliasMap && aliasMap[stripped] && set.has(aliasMap[stripped])) return aliasMap[stripped];
    }
    return null;
  }

  /**
   * 渲染单个实体超链接；若实体不在图鉴索引中则退化为安全转义文本，绝不产生死链。
   */
  function renderEntityLink(registry, kind, rawName, opts) {
    const o = opts || {};
    const raw = String(rawName ?? "").trim();
    const displayBase = o.label != null ? String(o.label) : raw;
    if (!raw) return U.esc(displayBase);

    const canon = resolveEntity(registry, kind, raw);
    if (!canon) return U.esc(displayBase);

    // 若未手动传入 label 且 raw 带有尾部括号附注（如「哥莱亚斯（满好感）」），把主体做成超链接、附注紧随其后
    let linkText = displayBase;
    let trailingNote = "";
    if (o.label == null) {
      const m = raw.match(/^(.*?)([（(][^）)]*[）)]\s*)$/);
      if (m && m[1].trim() && resolveEntity(registry, kind, m[1].trim()) === canon) {
        linkText = m[1].trim();
        trailingNote = m[2];
      }
    }

    const href = buildEntityHref(kind, canon);
    const cls = ["ent-link", `ent-${kind}`, o.className || ""].filter(Boolean).join(" ");
    const title = o.title || `查看${ENTITY_LABELS[kind] || "图鉴"}：${canon}`;
    const inner = o.innerHtml != null ? o.innerHtml : U.esc(linkText);
    const extra = o.extraAttrs ? " " + o.extraAttrs : "";
    return `<a href="${U.esc(href)}" class="${U.esc(cls)}" data-ent-kind="${U.esc(kind)}" data-ent-name="${U.esc(canon)}" title="${U.esc(title)}"${extra}>${inner}</a>${U.esc(trailingNote)}`;
  }

  /**
   * 将实体名称数组渲染为以 sep 连接的超链接串。
   */
  function linkifyList(registry, kind, items, sep = "、", optsFn) {
    return (items || [])
      .map((item, idx) => renderEntityLink(registry, kind, item, optsFn ? optsFn(item, idx) : undefined))
      .join(sep);
  }

  /**
   * 在结构化短句（如「轻步兵 / 士兵」「Lv20 弓箭手」）中将已收录职业名安全替换为超链接（最长优先匹配，其余文本原样转义）。
   */
  function linkifyClassText(registry, text, opts) {
    const s = String(text ?? "");
    if (!s || !registry || !registry.sortedClasses || !registry.sortedClasses.length) return U.esc(s);
    const escapedTokens = registry.sortedClasses.map(n => n.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
    const re = new RegExp(escapedTokens.join("|"), "g");
    let out = "";
    let last = 0;
    let m;
    while ((m = re.exec(s)) !== null) {
      if (m.index > last) out += U.esc(s.slice(last, m.index));
      const matched = m[0];
      out += renderEntityLink(registry, "class", matched, { ...(opts || {}), label: matched });
      last = m.index + matched.length;
    }
    if (last < s.length) out += U.esc(s.slice(last));
    return out;
  }

  return {
    ENTITY_VIEWS,
    ENTITY_LABELS,
    CLASS_ALIASES,
    CHAR_ALIASES,
    parseRouteHash,
    buildEntityHref,
    buildEntityRegistry,
    resolveEntity,
    renderEntityLink,
    linkifyList,
    linkifyClassText,
  };
});
