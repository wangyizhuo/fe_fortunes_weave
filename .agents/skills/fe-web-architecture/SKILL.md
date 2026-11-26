---
name: fe-web-architecture
description: 修改网页结构、CSS 样式、前端 JS 核心逻辑或网站构建脚本 build_site.py 时使用。
---

# 前端架构与数据解耦开发指南（fe-web-architecture）

## 分层架构
- `web/index.html`：标准 HTML5 壳（含 `<!DOCTYPE html>`、`charset="utf-8"`、`viewport`），三大模块导航，**严禁内联业务 JSON**。
- `web/styles.css`：共享设计系统（深浅色主题、响应式表格、模块筛选栏）。
- `web/js/core/*.js`：**零 DOM 依赖纯函数层**（UMD 导出，同时支持浏览器与 Node.js）。禁止引用 `document.`、`localStorage`、`innerHTML`、`addEventListener`。
- `web/js/state/store.js`：状态管理、localStorage 持久化、可选外部同步。
- `web/js/views/*.js`：按功能域拆分的视图渲染函数，所有用户输入和动态文本必须经 `U.esc()` 转义。
- `web/js/app.js`：HTTP 下通过 `fetch('./data/*.json')` 加载独立模块数据，`file://` 下回退至 `./data/bundle_data.js`。

## 开发与验证流程
1. 新增或修改任何前端计算逻辑（状态推演、过滤、排序、高亮、汇总）→ 必须先写在 `web/js/core/*.js`，再在 `web/tests/*.test.js` 补单元测试。
2. 只改了前端代码时，用轻量构建即可，无需重跑规划算法：
   ```bash
   python3 build_site.py --web-only
   ```
3. 必跑验证：
   ```bash
   node --test web/tests/*.test.js
   python3 levelup/rng/checks.py U6 U7 A1 A2 A3
   ```
