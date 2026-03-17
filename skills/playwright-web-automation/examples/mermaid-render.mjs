/**
 * Mermaid Diagram Renderer
 * 路径 B 示例：直接编写脚本，将 Mermaid 代码渲染为 PNG
 *
 * Usage: node mermaid-render.mjs
 * Output: output-*.png
 */

import { createRequire } from 'module';
const require = createRequire(import.meta.url);
const { chromium } = require('playwright');
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const sleep = (ms) => new Promise(r => setTimeout(r, ms));

// ============================================
// 图表定义 — 修改这里
// ============================================
const diagrams = [
  {
    name: 'example-flow',
    title: '示例流程图',
    code: `flowchart TD
    A([开始]) --> B{条件判断}
    B -->|是| C[执行操作]
    B -->|否| D[跳过]
    C --> E([结束])
    D --> E`
  }
];

// ============================================
// HTML 构建
// ============================================
function buildHtml(mermaidCode, title) {
  return `<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
  body { margin: 0; padding: 40px; background: #fff;
         display: flex; flex-direction: column; align-items: center;
         font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
  h2 { margin-bottom: 24px; color: #1a1a2e; font-size: 22px; }
  #diagram { display: flex; justify-content: center; min-width: 600px; }
</style>
</head><body>
<h2>${title}</h2>
<div id="diagram" class="mermaid">${mermaidCode}</div>
<script type="module">
  import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs';
  mermaid.initialize({ startOnLoad: true, theme: 'default',
    flowchart: { useMaxWidth: false, htmlLabels: true, curve: 'basis' },
    sequence: { useMaxWidth: false, wrap: true, width: 180 },
    fontSize: 14 });
</script>
</body></html>`;
}

// ============================================
// 主流程
// ============================================
(async () => {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    deviceScaleFactor: 2,
    viewport: { width: 1920, height: 1080 },
  });

  try {
    for (const diagram of diagrams) {
      const page = await context.newPage();
      await page.setContent(buildHtml(diagram.code, diagram.title), {
        waitUntil: 'networkidle', timeout: 30000
      });
      await page.waitForSelector('#diagram svg', { timeout: 15000 });
      await sleep(1000);

      const outPath = resolve(__dirname, `output-${diagram.name}.png`);
      await page.locator('body').screenshot({ path: outPath });
      console.log(`OK: ${outPath}`);
      await page.close();
    }
    console.log('\nAll diagrams rendered!');
  } finally {
    await browser.close();
  }
})();
