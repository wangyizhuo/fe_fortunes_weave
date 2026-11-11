// 排版自检：每次 make_html.py 之后跑。node check_layout.js <html>；有问题退出码 1。
// 查：JS 报错、页面横向溢出、文字被挤成窄条（宽 < 110px 却折成 4 行以上）、渲染出 undefined/NaN。
const { chromium } = require('playwright');
(async () => {
  const file = process.argv[2], tabs = ['meal', 'next', 'plan', 'l45', 'past', 'long', 'mine'], problems = [];
  const b = await chromium.launch();
  for (const w of [1200, 390]) {
    const p = await b.newPage({ viewport: { width: w, height: 900 } });
    p.on('pageerror', e => problems.push(`[${w}] JS 报错：${e.message}`));
    for (const t of tabs) {
      await p.goto('file://' + file + '#' + t); await p.waitForTimeout(800);
      // 展开所有折叠块，连折叠内容一起查
      await p.evaluate(() => document.querySelectorAll('details').forEach(d => d.open = true));
      const r = await p.evaluate((w) => {
        const out = [];
        if (document.documentElement.scrollWidth > w + 1) out.push(`页面横向溢出 ${document.documentElement.scrollWidth}px`);
        for (const el of document.querySelectorAll('#view *')) {
          if (el.closest('.scroll, td, th')) continue;             // 表格在可横滑容器里，单独不算
          const own = [...el.childNodes].filter(n => n.nodeType === 3).map(n => n.textContent.trim()).join('');
          if (own.length < 12) continue;
          const rc = el.getBoundingClientRect(); if (!rc.width) continue;
          const lh = parseFloat(getComputedStyle(el).lineHeight) || 20;
          if (rc.width < 110 && rc.height > lh * 4) out.push(`文字被挤成窄条（宽 ${Math.round(rc.width)}px）：${own.slice(0, 30)}`);
        }
        // 渲染出来的文字里不能有 undefined / NaN / [object Object]（11-11：「我的决定」表曾整列显示 undefined）
        const txt = document.querySelector('#view')?.innerText || '';
        for (const bad of ['undefined', 'NaN', '[object Object]']) {
          const i = txt.indexOf(bad);
          if (i >= 0) out.push(`页面文字里有「${bad}」：…${txt.slice(Math.max(0, i - 20), i + 20).replace(/\s+/g, ' ')}…`);
        }
        return [...new Set(out)].slice(0, 8);
      }, w);
      r.forEach(x => problems.push(`[${w}px #${t}] ${x}`));
    }
    await p.close();
  }
  await b.close();
  if (problems.length) { console.log('排版检查没通过：\n' + problems.join('\n')); process.exit(1); }
  console.log(`排版检查通过（${tabs.length} 个页签 × 桌面/手机）`);
})();
