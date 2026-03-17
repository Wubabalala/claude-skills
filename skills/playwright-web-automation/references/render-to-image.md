# 渲染 HTML/图表为图片

将 HTML 内容（Mermaid 图表、自定义图、报告等）用 Playwright 渲染为 PNG。

## 核心模式

```javascript
// 1. 构造 HTML（内联或拼接）
const html = `<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>body { margin: 0; padding: 40px; background: #fff; }</style>
</head><body>
  <div id="content">渲染内容</div>
  <!-- 如需外部库，用 CDN script/module -->
</body></html>`;

// 2. 加载并等待渲染
await page.setContent(html, { waitUntil: 'networkidle', timeout: 30000 });
await page.waitForSelector('#content svg', { timeout: 15000 }); // 等目标元素
await sleep(500); // 渲染缓冲

// 3. 截图导出
await page.locator('body').screenshot({ path: 'output.png' });
// 或精确截取: await page.locator('#content').screenshot({ path: 'output.png' });
```

## Mermaid 图表渲染

```javascript
function buildMermaidHtml(mermaidCode, title) {
  return `<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
  body { margin: 0; padding: 40px; background: #fff;
         display: flex; flex-direction: column; align-items: center;
         font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
  h2 { margin-bottom: 24px; color: #1a1a2e; }
  #diagram { display: flex; justify-content: center; min-width: 600px; }
</style>
</head><body>
<h2>${title}</h2>
<div id="diagram" class="mermaid">${mermaidCode}</div>
<script type="module">
  import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs';
  mermaid.initialize({ startOnLoad: true, theme: 'default',
    flowchart: { useMaxWidth: false, htmlLabels: true },
    sequence: { useMaxWidth: false, wrap: true } });
</script>
</body></html>`;
}

// 使用
await page.setContent(buildMermaidHtml(code, '标题'), {
  waitUntil: 'networkidle', timeout: 30000
});
await page.waitForSelector('#diagram svg', { timeout: 15000 });
await sleep(1000);
await page.locator('body').screenshot({ path: 'output.png' });
```

## 批量渲染

多张图时，为每张图创建新 page，避免残留状态：

```javascript
for (const diagram of diagrams) {
  const page = await context.newPage();
  await page.setContent(buildHtml(diagram.code, diagram.title), ...);
  await page.waitForSelector('svg', { timeout: 15000 });
  await page.locator('body').screenshot({ path: `${diagram.name}.png` });
  await page.close();
}
```

## 关键配置

| 配置 | 说明 |
|------|------|
| `headless: true` | 渲染导出不需要看浏览器，默认 headless |
| `deviceScaleFactor: 2` | 高清输出（2x 分辨率） |
| `waitUntil: 'networkidle'` | 等 CDN 资源加载完 |
| `waitForSelector('svg')` | 等渲染库生成目标元素 |

## 常见问题

| 问题 | 原因 | 解决 |
|------|------|------|
| CDN 加载超时 | 网络问题 | 增大 timeout 或换 CDN |
| SVG 未生成 | 渲染库初始化慢 | `waitForSelector` + sleep 缓冲 |
| 中文乱码 | 缺少 `<meta charset>` | HTML 头部加 `<meta charset="utf-8">` |
| 图片截断 | viewport 太小 | 增大 viewport 或用 `fullPage: true` |
| 背景透明 | body 无背景色 | CSS 加 `background: #fff` |
